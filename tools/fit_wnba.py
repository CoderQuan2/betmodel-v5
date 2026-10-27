#!/usr/bin/env python3
"""fit_wnba.py — BetFi Xii pricing Build I: the WNBA fit builder.

Fits the WNBA lane (FanDuel files its fixtures under the "nba"
page) from REAL results: ESPN WNBA scoreboard day-pulls over
the 2023, 2024, 2025 and 2026 regular seasons — the house
method, the NBA Elo lane fit the same way (betmodel5.fit_nba
over ESPN day pulls). Writes data/v5-wnba.json in the exact
v5-nba.json shape:

  * sequential Elo, K=20, HFA=100 Elo points (the NBA lane's
    ENGINE PARAMS, carried over un-tuned — no parameter was
    searched for this lane), the NBA lane's margin-of-victory
    multiplier, ratings carried across seasons in date order
    (standard Elo practice; no per-season reset). Regular
    season only (event season.type == 2), completed games
    only, exhibition squads (All-Star "TEAM X" sides) excluded.
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

Cache: data/cache/wnba_games_2023-26.json (the nba cache
pattern) — a re-run with the cache present refits without
re-pulling.

Usage: fit_wnba.py [out_path]   (default: ../data/v5-wnba.json
relative to this script's repo root)
"""
import json
import math
import os
import statistics
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

ESPN_WNBA = ("https://site.api.espn.com/apis/site/v2/sports/"
             "basketball/wnba/scoreboard")
SEASON_YEARS = (2023, 2024, 2025, 2026)
PULL_START = (4, 1)     # Apr 1 — every season's RS starts later
PULL_END = (11, 1)      # Nov 1 — every season's RS ends earlier
K = 20                  # the NBA lane's ENGINE PARAMS, un-tuned
HFA_ELO = 100
# The league's franchises across 2023-2026 (13 through 2025 —
# the OTHER_COMPETITION_TEAMS WNBA roster in betmodel5.py —
# plus the 2026 expansion pair Portland Fire / Toronto Tempo).
# ESPN also files exhibition sides in this feed (Team USA,
# Team WNBA — Olympic / All-Star exhibitions); a league fit
# holds league fixtures only, so any game touching a code
# outside this set is excluded at fit time.
CLUBS = {"ATL", "CHI", "CON", "DAL", "GS", "IND", "LA", "LV",
         "MIN", "NY", "PHX", "POR", "SEA", "TOR", "WSH"}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "data", "cache",
                          "wnba_games_2023-26.json")


def fetch_day(d):
    url = f"{ESPN_WNBA}?dates={d.strftime('%Y%m%d')}&limit=200"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_day(j):
    out = []
    for ev in j.get("events", []):
        if (ev.get("season") or {}).get("type") != 2:
            continue                    # regular season only
        comp = ev["competitions"][0]
        cs = comp["competitors"]
        home = next(c for c in cs if c["homeAway"] == "home")
        away = next(c for c in cs if c["homeAway"] == "away")
        hn = home["team"].get("displayName",
                              home["team"]["abbreviation"])
        an = away["team"].get("displayName",
                              away["team"]["abbreviation"])
        if hn.startswith("TEAM ") or an.startswith("TEAM "):
            continue                    # All-Star exhibition
        if not ev["status"]["type"]["completed"]:
            continue
        if home.get("score") in (None, "") or \
                away.get("score") in (None, ""):
            continue
        out.append({
            "date": ev.get("date", "")[:10],
            "home": home["team"]["abbreviation"],
            "away": away["team"]["abbreviation"],
            "home_name": hn, "away_name": an,
            "hs": int(home["score"]), "as": int(away["score"]),
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
    days = []
    for y in SEASON_YEARS:
        d = date(y, *PULL_START)
        end = date(y, *PULL_END)
        while d <= end:
            days.append(d)
            d += timedelta(days=1)

    def one(day):
        try:
            return parse_day(fetch_day(day))
        except Exception:
            return None

    games, errors = [], 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for out in ex.map(one, days):
            if out is None:
                errors += 1
            else:
                games += out
    games.sort(key=lambda g: g["date"])
    fetched_at = datetime.now().astimezone().isoformat(
        timespec="seconds")
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"fetched_at": fetched_at,
                   "source": "ESPN WNBA scoreboard day pulls",
                   "errors": errors, "games": games}, f, indent=1)
    print(f"pulled: {len(games)} games, {errors} day errors",
          file=sys.stderr)
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
    return {"sport": "wnba",
            "season": "2023-2026 regular seasons",
            "fitted_at": datetime.now().astimezone().isoformat(
                timespec="seconds"),
            "source": f"ESPN WNBA scoreboard day pulls (cached "
                      f"{fetched_at}; "
                      f"data/cache/wnba_games_2023-26.json)",
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
        ROOT, "data", "v5-wnba.json")
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
