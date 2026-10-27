#!/usr/bin/env python3
"""fit_greece_a1.py — BetFi Xii pricing Build K: the Greece
A1 fit builder.

Fits the Greece A1 lane (FanDuel files its fixtures under
the "nba" page, competition "Greece - A1") from REAL
results: the league's own official Game Center (ESAKE,
esake.gr/el/action/EsakeResults), which serves
server-rendered result blocks for every championship back
to 1992-93. The enumeration is the page's own filter
template (ShowProgram() in the served page):
idchampionship (season) x idseason=00000001 (Α Φάση, the
regular phase) x series (the round, 1..N) — verified by
fetch: series=1/2/10/26 return rounds 01/02/10/26, six
games each. Each game block carries the round, the date
(Greek month abbreviations, no year — the year is the
championship's, with the Oct->Jun rollover), both clubs'
official ESAKE team ids (in the crest image paths), their
Greek display names, and the final score. Games are keyed
and deduped by the site's own idgame.

Seasons pulled: 2022-23 .. 2026-27 (the last in progress;
unplayed fixtures carry no final score and drop out).
Writes data/v5-greece-a1.json in the v5-nba.json shape (plus
a "teams" id->name map, because this source's keys are hex
club ids, not readable codes), the fit_eurocup.py pattern:

  * sequential Elo, K=20, HFA=100 Elo points (the NBA lane's
    ENGINE PARAMS, carried over un-tuned — no parameter was
    searched for this lane), the NBA lane's margin-of-victory
    multiplier, ratings carried across seasons in date order
    (standard Elo practice; no per-season reset). Regular
    phase only (idseason Α Φάση), played games only.
  * walk-forward exam, scored BEFORE any engine wiring:
    every game's prediction is made from ratings built ONLY
    on prior games; backtest = Brier of those walk-forward
    probabilities vs the naive baseline that predicts the
    overall home-win rate for every game (fit_nba's exact
    baseline). The lane prices only if Brier < naive.
  * margin map: OLS with intercept of margin on the
    walk-forward Elo diff, residual SD — fit_nba's map,
    verbatim (cover prices inherit its in-sample caveat and
    ride FRAGILE, exactly like the NBA lane's spreads).

Cache: data/cache/greece_a1_games_2022-27.json (the wnba
cache pattern) — a re-run with the cache present refits
without re-pulling.

Usage: fit_greece_a1.py [out_path]   (default:
../data/v5-greece-a1.json relative to this script's repo
root)
"""
import json
import math
import os
import re
import statistics
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

URL = ("https://www.esake.gr/el/action/EsakeResults"
       "?idchampionship={}&idteam=&idseason=00000001"
       "&series={}")
# championship id -> (label, season start year): the Game
# Center's own season select, verified at fit time.
CHAMPIONSHIPS = (
    ("DC917125", "Basket League 2022-2023", 2022),
    ("C1AF5EF5", "Stoiximan Basket League 2023-2024", 2023),
    ("4820C134", "Stoiximan GBL 2024-2025", 2024),
    ("44B80BEB", "Stoiximan GBL 2025-2026", 2025),
    ("184645B9", "Stoiximan GBL 2026-2027", 2026),
)
MAX_ROUND = 32          # 13-team seasons run 26 rounds
K = 20                  # the NBA lane's ENGINE PARAMS, un-tuned
HFA_ELO = 100
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "data", "cache",
                          "greece_a1_games_2022-27.json")
# Greek month abbreviations as printed by the Game Center,
# tonos-stripped capitals (ΙΟΥΝ June vs ΙΟΥΛ July differ at
# the fourth letter — match the longest key).
MONTHS = {"ΙΑΝ": 1, "ΦΕΒ": 2, "ΜΑΡ": 3, "ΑΠΡ": 4, "ΜΑΙ": 5,
          "ΙΟΥΝ": 6, "ΙΟΥΛ": 7, "ΑΥΓ": 8, "ΣΕΠ": 9, "ΟΚΤ": 10,
          "ΝΟΕ": 11, "ΔΕΚ": 12}
_TONOS = str.maketrans("ΆΈΉΊΌΎΏΪΫ", "ΑΕΗΙΟΥΩΙΥ")

GAME_RE = re.compile(
    r'<div class="esake-program-game">(.*?)'
    r'(?=<div class="esake-program-game">|</body>)', re.S)
ROUND_RE = re.compile(r'<h5>(\d+)η Αγωνιστική</h5>')
DATE_RE = re.compile(
    r'(\d{1,2})\s+([Α-Ωα-ωΪΫίϊΐύϋΰ]+)\s*-\s*\d{2}:\d{2}')
SCORE_CELL_RE = re.compile(r'<span>(\d+)&nbsp;-&nbsp;(\d+)</span>')
IMG_ID_RE = re.compile(r'/dat/esaketeam/([0-9A-F]+)/')
SPAN_RE = re.compile(r'<span>(.*?)</span>', re.S)
SCORE_CELL_RE = re.compile(r'<span>(\d+)&nbsp;-&nbsp;(\d+)</span>')
GAME_ID_RE = re.compile(r'EsakegameView\?idgame=([0-9A-F]+)')


def _txt(s):
    return re.sub(r"\s+", " ",
                  s.replace("<br/>", " ").replace("<br>", " ")
                  ).strip()


def month_of(abbrev):
    a = abbrev.upper().translate(_TONOS)
    for key in sorted(MONTHS, key=len, reverse=True):
        if a.startswith(key) or key.startswith(a):
            return MONTHS[key]
    raise ValueError(f"unknown Greek month abbrev: {abbrev!r}")


def parse_page(html, champ, label, start_year):
    """One round page -> game dicts (played games only: a
    block without a final score is an unplayed fixture)."""
    out = []
    for block in GAME_RE.findall(html):
        sm = SCORE_CELL_RE.search(block)
        if not sm:
            continue                    # unplayed fixture
        gid = GAME_ID_RE.search(block)
        rm = ROUND_RE.search(block)
        dm = DATE_RE.search(block)
        ids = IMG_ID_RE.findall(block)
        spans = [_txt(s) for s in SPAN_RE.findall(block)]
        # spans: player-stat lines ride along below the score
        # row; the two team names are the spans that wrap the
        # score cell — take the span immediately before and
        # after the score span by document order.
        score_idx = None
        raw_spans = SPAN_RE.findall(block)
        for i, s in enumerate(raw_spans):
            if SCORE_CELL_RE.fullmatch("<span>" + s + "</span>"):
                score_idx = i
                break
        if len(ids) < 2 or score_idx is None \
                or score_idx == 0 or score_idx + 1 >= len(raw_spans):
            continue
        day = int(dm.group(1)) if dm else 1
        mon = month_of(dm.group(2)) if dm else 10
        year = start_year if mon >= 9 else start_year + 1
        out.append({
            "idgame": gid.group(1) if gid else None,
            "championship": label,
            "round": int(rm.group(1)) if rm else None,
            "date": f"{year:04d}-{mon:02d}-{day:02d}",
            "home": ids[0], "away": ids[1],
            "home_name": _txt(raw_spans[score_idx - 1]),
            "away_name": _txt(raw_spans[score_idx + 1]),
            "hs": int(sm.group(1)), "as": int(sm.group(2)),
            "final": True})
    return out


def fetch_round(args):
    champ, label, start_year, rnd = args
    url = URL.format(champ, rnd)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            html = resp.read().decode("utf-8", "replace")
    except Exception:
        return champ, rnd, None
    return champ, rnd, parse_page(html, champ, label,
                                  start_year)


def collect():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            blob = json.load(f)
        print(f"cache: {len(blob['games'])} games "
              f"({blob['fetched_at']})", file=sys.stderr)
        return blob["games"], blob["fetched_at"], blob.get(
            "errors", 0), blob.get("teams", {})
    jobs = [(c, label, y, r)
            for (c, label, y) in CHAMPIONSHIPS
            for r in range(1, MAX_ROUND + 1)]
    by_key, errors = {}, 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for champ, rnd, games in ex.map(fetch_round, jobs):
            if games is None:
                errors += 1
                continue
            for g in games:
                by_key[g["idgame"] or
                       (g["date"], g["home"], g["away"])] = g
    games = sorted(by_key.values(),
                   key=lambda g: (g["date"], g["round"] or 0))
    teams = {}
    for g in games:
        teams[g["home"]] = g["home_name"]
        teams[g["away"]] = g["away_name"]
    fetched_at = datetime.now().astimezone().isoformat(
        timespec="seconds")
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"fetched_at": fetched_at,
                   "source": "ESAKE official Game Center "
                             "(esake.gr EsakeResults; "
                             "championship x regular phase x "
                             "round)",
                   "errors": errors, "teams": teams,
                   "games": games}, f, indent=1,
                  ensure_ascii=False)
    print(f"pulled: {len(games)} games, {errors} page "
          f"errors, {len(teams)} teams", file=sys.stderr)
    return games, fetched_at, errors, teams


def fit(games, fetched_at, teams):
    """fit_nba's body, verbatim math: sequential Elo with the
    MOV multiplier, walk-forward records, OLS margin map.
    A league fit holds league fixtures only — every pulled
    game is one by construction (the championship ids are
    the league's own), so the CLUBS guard of the sibling
    builders is the pulled team set itself."""
    clubs = set(teams)
    played = [g for g in games if g["final"]
              and g["hs"] is not None
              and g["home"] in clubs and g["away"] in clubs]
    R, recs = {}, []

    def r(t):
        return R.get(t, 1500.0)

    for g in played:
        d = r(g["home"]) + HFA_ELO - r(g["away"])
        p = 1 / (1 + 10 ** (-d / 400))
        mov = g["hs"] - g["as"]
        y = 1.0 if mov > 0 else 0.0
        recs.append({"diff": d, "p": p, "margin": mov, "y": y})
        mult = (math.log(abs(mov) + 1)
                * (2.2 / ((r(g["home"]) - r(g["away"]))
                          * 0.001 + 2.2))
                if mov != 0 else 1.0)
        delta = K * mult * (y - p)
        R[g["home"]] = r(g["home"]) + delta
        R[g["away"]] = r(g["away"]) - delta
    brier = statistics.mean([(x["p"] - x["y"]) ** 2
                             for x in recs])
    home_rate = statistics.mean([x["y"] for x in recs])
    naive = statistics.mean([(home_rate - x["y"]) ** 2
                             for x in recs])
    n = len(recs)
    mx = statistics.mean([x["diff"] for x in recs])
    my = statistics.mean([x["margin"] for x in recs])
    b = (sum((x["diff"] - mx) * (x["margin"] - my) for x in recs)
         / sum((x["diff"] - mx) ** 2 for x in recs))
    a = my - b * mx
    sd = statistics.pstdev([x["margin"] - (a + b * x["diff"])
                            for x in recs])
    return {"sport": "greece-a1",
            "season": "2022-23 to 2026-27 regular phase "
                      "(Α Φάση)",
            "fitted_at": datetime.now().astimezone().isoformat(
                timespec="seconds"),
            "source": f"ESAKE official Game Center results "
                      f"(cached {fetched_at}; "
                      f"data/cache/greece_a1_games_2022-27"
                      f".json)",
            "params": {"K": K, "hfa_elo": HFA_ELO},
            "teams": teams,
            "ratings": {k: round(v, 1)
                        for k, v in sorted(R.items())},
            "margin_map": {"a": round(a, 3), "b": round(b, 4),
                           "sd": round(sd, 2), "n": n},
            "backtest": {"brier": round(brier, 4),
                         "naive_brier": round(naive, 4),
                         "naive_home_brier": round(naive, 4),
                         "n": n,
                         "protocol": "walk-forward (pre-game "
                                     "ratings, sequential Elo)"}}


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "data", "v5-greece-a1.json")
    games, fetched_at, _errors, teams = collect()
    print(f"teams ({len(teams)}): "
          + ", ".join(f"{c}={teams[c]}" for c in sorted(teams)),
          file=sys.stderr)
    blob = fit(games, fetched_at, teams)
    bt = blob["backtest"]
    passed = bt["brier"] < bt["naive_home_brier"]
    print(f"exam: walk-forward Brier {bt['brier']} vs naive "
          f"{bt['naive_home_brier']}, n={bt['n']} -> "
          f"{'PASSED' if passed else 'FAILED-EXAM'}")
    print(f"margin map: a={blob['margin_map']['a']} "
          f"b={blob['margin_map']['b']} sd={blob['margin_map']['sd']}")
    print(f"ratings: {blob['ratings']}")
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=1, ensure_ascii=False)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
