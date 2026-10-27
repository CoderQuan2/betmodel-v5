#!/usr/bin/env python3
"""fit_eurocup.py — BetFi Xii pricing Build K: the EuroCup
fit builder.

Fits the EuroCup lane (FanDuel files its fixtures under the
"nba" page, competition "EuroCup") from REAL results: the
EuroLeague Basketball official API (api-live.euroleague.net
v2 season game lists) over the U2023, U2024, U2025 and U2026
seasons — the SAME verified route Build J used for the
EuroLeague (competition "E"); the EuroCup is the same
organizer's second competition (code "U", verified by fetch:
U2024 game 196 = the 2025 final, Gran Canaria 94 – Hapoel
Tel Aviv, with full club/score/phase detail). Writes
data/v5-eurocup.json in the exact v5-nba.json shape, the
fit_euroleague.py pattern:

  * sequential Elo, K=20, HFA=100 Elo points (the NBA lane's
    ENGINE PARAMS, carried over un-tuned — no parameter was
    searched for this lane), the NBA lane's margin-of-victory
    multiplier, ratings carried across seasons in date order
    (standard Elo practice; no per-season reset). Regular
    season only (phaseType.code == "RS" — the group phase;
    the 8F/4F/2F/Final playoff phases are excluded, exactly
    as Build J excluded the EuroLeague's non-RS phases),
    played games only.
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

Cache: data/cache/eurocup_games_2023-26.json (the wnba
cache pattern) — a re-run with the cache present refits
without re-pulling.

Usage: fit_eurocup.py [out_path]   (default:
../data/v5-eurocup.json relative to this script's repo
root)
"""
import json
import math
import os
import statistics
import sys
import urllib.request
from datetime import datetime

API = ("https://api-live.euroleague.net/v2/competitions/U/"
       "seasons/{}/games")
SEASON_CODES = ("U2023", "U2024", "U2025", "U2026")
K = 20                  # the NBA lane's ENGINE PARAMS, un-tuned
HFA_ELO = 100
# Every club code the official API lists across U2023-U2026
# (43; verified against the live season game lists at fit
# time). A league fit holds league fixtures only, so any
# game touching a code outside this set is excluded at fit
# time (the fit_wnba CLUBS guard, one lane over).
CLUBS = {"ARI", "BAH", "BCR", "BES", "BGS", "BLK", "BOS",
         "BOU", "BUD", "BUR", "CAN", "CLU", "FRA", "HAM",
         "HTA", "JER", "JOV", "KLA", "LEM", "LJU", "LKB",
         "LLI", "MAN", "MRO", "NAP", "NIN", "NIO", "PAM",
         "PAO", "PMT", "PRS", "RIG", "RTK", "SIA", "TNF",
         "TRN", "TRT", "TSO", "TTK", "ULM", "VNC", "WOL",
         "WRO"}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "data", "cache",
                          "eurocup_games_2023-26.json")


def fetch_season(code):
    url = API.format(code)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_season(j):
    out = []
    for g in j.get("data", []):
        if (g.get("phaseType") or {}).get("code") != "RS":
            continue                    # regular season only
        if not g.get("played"):
            continue
        loc, road = g.get("local") or {}, g.get("road") or {}
        lc, rc = loc.get("club") or {}, road.get("club") or {}
        if loc.get("score") is None or road.get("score") is None:
            continue
        if lc.get("isVirtual") or rc.get("isVirtual"):
            continue
        out.append({
            "date": (g.get("date") or "")[:10],
            "home": lc.get("code"), "away": rc.get("code"),
            "home_name": lc.get("name", ""),
            "away_name": rc.get("name", ""),
            "hs": int(loc["score"]), "as": int(road["score"]),
            "final": True})
    return out


def collect():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            blob = json.load(f)
        print(f"cache: {len(blob['games'])} games "
              f"({blob['fetched_at']})", file=sys.stderr)
        return blob["games"], blob["fetched_at"], blob.get(
            "errors", 0)
    games, errors = [], 0
    for code in SEASON_CODES:
        try:
            games += parse_season(fetch_season(code))
        except Exception:
            errors += 1
    games.sort(key=lambda g: g["date"])
    fetched_at = datetime.now().astimezone().isoformat(
        timespec="seconds")
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"fetched_at": fetched_at,
                   "source": "EuroLeague Basketball official "
                             "API v2 season game lists "
                             "(EuroCup, competition U)",
                   "errors": errors, "games": games}, f,
                  indent=1)
    print(f"pulled: {len(games)} games, {errors} season "
          f"errors", file=sys.stderr)
    return games, fetched_at, errors


def fit(games, fetched_at):
    """fit_nba's body, verbatim math: sequential Elo with the
    MOV multiplier, walk-forward records, OLS margin map."""
    played = [g for g in games if g["final"]
              and g["hs"] is not None
              and g["home"] in CLUBS and g["away"] in CLUBS]
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
    return {"sport": "eurocup",
            "season": "2023-24 to 2026-27 regular seasons",
            "fitted_at": datetime.now().astimezone().isoformat(
                timespec="seconds"),
            "source": f"EuroLeague Basketball official API "
                      f"v2 season game lists (EuroCup; "
                      f"cached {fetched_at}; "
                      f"data/cache/eurocup_games_2023-26"
                      f".json)",
            "params": {"K": K, "hfa_elo": HFA_ELO},
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
        ROOT, "data", "v5-eurocup.json")
    games, fetched_at, _errors = collect()
    names = {}
    for g in games:
        names[g["home"]] = g["home_name"]
        names[g["away"]] = g["away_name"]
    print(f"teams ({len(names)}): "
          + ", ".join(f"{c}={names[c]}" for c in sorted(names)),
          file=sys.stderr)
    blob = fit(games, fetched_at)
    bt = blob["backtest"]
    passed = bt["brier"] < bt["naive_home_brier"]
    print(f"exam: walk-forward Brier {bt['brier']} vs naive "
          f"{bt['naive_home_brier']}, n={bt['n']} -> "
          f"{'PASSED' if passed else 'FAILED-EXAM'}")
    print(f"margin map: a={blob['margin_map']['a']} "
          f"b={blob['margin_map']['b']} sd={blob['margin_map']['sd']}")
    print(f"ratings: {blob['ratings']}")
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=1)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
