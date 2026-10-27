#!/usr/bin/env python3
"""fit_ahl.py — BetFi Xii pricing Build M: the AHL fit
builder.

Fits the AHL lane (FanDuel files its fixtures under the
"nhl" page, competition "USA - AHL - Matches") from REAL
results: the HockeyTech / LeagueStat feed that powers
theahl.com itself (lscluster.hockeytech.com modulekit
JSON; the app key is the one the league site's own
statview JS publishes — base.r3.js appKey — no private
credential). Seasons are discovered through the feed's
own seasons view and only "Regular Season" entries are
taken (2023-24 .. 2026-27); finals only (final == "1").

Writes data/v5-ahl.json in the house fit shape:

  * the NHL lane's Elo protocol, verbatim (betmodel5
    run_elo's nhl branch): sequential Elo, K=8,
    HFA_ELO=32, NO margin-of-victory multiplier,
    ratings carried across seasons in date order,
    start 1500.
  * walk-forward exam, scored BEFORE any engine wiring:
    every game's prediction is made from ratings built
    ONLY on prior games; backtest = Brier of those
    walk-forward probabilities vs the naive baseline
    that predicts the overall home-win rate for every
    game (fit_nba's exact baseline, the house gate's
    naive_brier). The lane prices only if Brier < naive.
  * per-team game counts ride along: the engine prices
    with the NHL lane's sigma-integrated logistic
    (nhl_win_prob), whose sigmas come from the NHL
    rating_sigma schedule over these counts.

Cache: data/cache/ahl_games_2023-27.json — a re-run with
the cache present refits without re-pulling.

Usage: fit_ahl.py [out_path]   (default:
../data/v5-ahl.json relative to this script's repo root)
"""
import json
import os
import statistics
import sys
import urllib.request
from datetime import datetime

FEED = ("https://lscluster.hockeytech.com/feed/"
        "?feed=modulekit&view={view}&key={key}&fmt=json"
        "&client_code=ahl{extra}")
# The app key theahl.com's own statview JS publishes
# (statview-1.4.1/js/client/ahl/base.r3.js: appKey).
APP_KEY = "ccb91f29d6744675"
SEASON_NAMES = ("2023-24", "2024-25", "2025-26", "2026-27")
K = 8.0                 # the NHL lane's ENGINE PARAMS,
HFA_ELO = 32.0          # carried over un-tuned
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "data", "cache",
                          "ahl_games_2023-27.json")


def fetch(view, extra=""):
    url = FEED.format(view=view, key=APP_KEY, extra=extra)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            blob = json.load(f)
        print(f"cache: {len(blob['games'])} games "
              f"({blob['fetched_at']})", file=sys.stderr)
        return blob["games"], blob["fetched_at"]
    seasons = fetch("seasons")["SiteKit"]["Seasons"]
    wanted = {s["season_id"]: s["season_name"]
              for s in seasons
              if s.get("playoff") == "0"
              and s.get("shortname") in SEASON_NAMES
              and "Regular Season" in s.get("season_name", "")}
    print(f"RS seasons: {wanted}", file=sys.stderr)
    games = []
    for sid, sname in sorted(wanted.items(),
                             key=lambda kv: kv[1]):
        sched = fetch("schedule",
                      f"&season_id={sid}")["SiteKit"]["Schedule"]
        for g in sched:
            if g.get("final") != "1":
                continue
            games.append({
                "date": g["date_played"],
                "home": g["home_team_name"],
                "away": g["visiting_team_name"],
                "hs": int(g["home_goal_count"]),
                "as": int(g["visiting_goal_count"]),
                "final": True})
    games.sort(key=lambda g: g["date"])
    fetched_at = datetime.now().astimezone().isoformat(
        timespec="seconds")
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"fetched_at": fetched_at,
                   "source": "HockeyTech/LeagueStat AHL "
                             "modulekit feed (theahl.com)",
                   "games": games}, f, indent=1)
    print(f"pulled: {len(games)} games", file=sys.stderr)
    return games, fetched_at


def fit(games, fetched_at):
    """The NHL lane's run_elo protocol (sport='nhl'):
    K=8, HFA=32, multiplier 1.0 (no MOV), walk-forward
    records scored before each update."""
    played = [g for g in games if g["final"]
              and g["hs"] is not None and g["hs"] != g["as"]]
    R, recs, counts = {}, [], {}
    def r(t):
        return R.get(t, 1500.0)
    for g in played:
        d = r(g["home"]) + HFA_ELO - r(g["away"])
        p = 1 / (1 + 10 ** (-d / 400))
        y = 1.0 if g["hs"] > g["as"] else 0.0
        recs.append({"p": p, "y": y})
        delta = K * (y - p)
        R[g["home"]] = r(g["home"]) + delta
        R[g["away"]] = r(g["away"]) - delta
        counts[g["home"]] = counts.get(g["home"], 0) + 1
        counts[g["away"]] = counts.get(g["away"], 0) + 1
    brier = statistics.mean([(x["p"] - x["y"]) ** 2
                             for x in recs])
    home_rate = statistics.mean([x["y"] for x in recs])
    naive = statistics.mean([(home_rate - x["y"]) ** 2
                             for x in recs])
    n = len(recs)
    return {"sport": "ahl",
            "season": "2023-24 to 2026-27 regular seasons",
            "fitted_at": datetime.now().astimezone().isoformat(
                timespec="seconds"),
            "source": f"HockeyTech/LeagueStat AHL modulekit "
                      f"feed (cached {fetched_at}; "
                      f"data/cache/ahl_games_2023-27.json)",
            "params": {"K": K, "hfa_elo": HFA_ELO},
            "ratings": {k: round(v, 1)
                        for k, v in sorted(R.items())},
            "games": dict(sorted(counts.items())),
            "backtest": {"brier": round(brier, 4),
                         "naive_brier": round(naive, 4),
                         "naive_home_brier": round(naive, 4),
                         "n": n,
                         "protocol": "walk-forward (pre-game "
                                     "ratings, sequential Elo, "
                                     "NHL-lane protocol)"}}


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "data", "v5-ahl.json")
    games, fetched_at = collect()
    teams = sorted({g["home"] for g in games}
                   | {g["away"] for g in games})
    print(f"teams ({len(teams)}): {', '.join(teams)}",
          file=sys.stderr)
    blob = fit(games, fetched_at)
    bt = blob["backtest"]
    passed = bt["brier"] < bt["naive_home_brier"]
    print(f"exam: walk-forward Brier {bt['brier']} vs naive "
          f"{bt['naive_home_brier']}, n={bt['n']} -> "
          f"{'PASSED' if passed else 'FAILED-EXAM'}")
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=1)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
