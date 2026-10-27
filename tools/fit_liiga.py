#!/usr/bin/env python3
"""fit_liiga.py — BetFi Xii pricing Build M: the Finnish
Liiga fit builder.

Fits the Liiga lane (FanDuel files its fixtures under the
"nhl" page, competition "Finnish SM-Liiga") from REAL
results: the league's own public API at liiga.fi
(/api/v2/games?tournament=runkosarja&season={year} —
"runkosarja" is the regular season; the season parameter
is the ENDING year, so 2025 is 2024-25). No key required.
Seasons 2023..2027 (2022-23 .. 2026-27, the last partial).
Ended games only (ended == true); a level score after
regulation is impossible in the feed's finals (OT/SO
decides), and any tie row is dropped by the NHL
protocol's own rule.

Writes data/v5-liiga.json in the house fit shape with
the NHL lane's Elo protocol and walk-forward exam —
see fit_ahl.py's docstring for the protocol statement
(K=8, HFA_ELO=32, no MOV multiplier, naive = the
overall home-win-rate baseline; the lane prices only
if Brier < naive). Per-team game counts ride along
for the engine's sigma-integrated logistic.

Cache: data/cache/liiga_games_2023-27.json.

Usage: fit_liiga.py [out_path]   (default:
../data/v5-liiga.json relative to this script's repo
root)
"""
import json
import os
import statistics
import sys
import urllib.request
from datetime import datetime

API = ("https://liiga.fi/api/v2/games"
       "?tournament=runkosarja&season={}")
SEASONS = (2023, 2024, 2025, 2026, 2027)
K = 8.0                 # the NHL lane's ENGINE PARAMS,
HFA_ELO = 32.0          # carried over un-tuned
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "data", "cache",
                          "liiga_games_2023-27.json")


def fetch_season(year):
    url = API.format(year)
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
    games = []
    for year in SEASONS:
        for g in fetch_season(year):
            if not g.get("ended"):
                continue
            games.append({
                "date": (g.get("start") or "")[:10],
                "home": g["homeTeam"]["teamName"],
                "away": g["awayTeam"]["teamName"],
                "hs": int(g["homeTeam"]["goals"]),
                "as": int(g["awayTeam"]["goals"]),
                "final": True})
    games.sort(key=lambda g: g["date"])
    fetched_at = datetime.now().astimezone().isoformat(
        timespec="seconds")
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"fetched_at": fetched_at,
                   "source": "liiga.fi official API v2 "
                             "(runkosarja)",
                   "games": games}, f, indent=1)
    print(f"pulled: {len(games)} games", file=sys.stderr)
    return games, fetched_at


def fit(games, fetched_at):
    """The NHL lane's run_elo protocol — see fit_ahl.py."""
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
    return {"sport": "liiga",
            "season": "2022-23 to 2026-27 regular seasons "
                      "(runkosarja)",
            "fitted_at": datetime.now().astimezone().isoformat(
                timespec="seconds"),
            "source": f"liiga.fi official API v2 "
                      f"(cached {fetched_at}; "
                      f"data/cache/liiga_games_2023-27.json)",
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
        ROOT, "data", "v5-liiga.json")
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
