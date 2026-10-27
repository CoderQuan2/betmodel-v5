#!/usr/bin/env python3
"""fit_shl.py — BetFi Xii pricing Build M: the Swedish
SHL fit builder.

Fits the SHL lane (FanDuel files its fixtures under the
"nhl" page, competition "Swedish SHL") from REAL results:
the SHL site's own Sportality API (www.shl.se/api/
sports-v2 — the same JSON the league's game center
renders). The season/series/game-type ids come from the
API's own season-series-game-types-filter document
(series SHL, gameType "regular" = Grundserie); only the
regular season is pulled (seasons 2023/24 .. 2026/27,
the last partial), post-game state only. Ratings key on
the API's club codes, exactly like the EuroLeague fit
keys on its organizer's codes. No key required.

Writes data/v5-shl.json in the house fit shape with
the NHL lane's Elo protocol and walk-forward exam —
see fit_ahl.py's docstring for the protocol statement
(K=8, HFA_ELO=32, no MOV multiplier, naive = the
overall home-win-rate baseline; the lane prices only
if Brier < naive). Per-team game counts ride along
for the engine's sigma-integrated logistic.

Cache: data/cache/shl_games_2023-27.json.

Usage: fit_shl.py [out_path]   (default:
../data/v5-shl.json relative to this script's repo root)
"""
import json
import os
import statistics
import sys
import urllib.request
from datetime import datetime

FILTER_URL = ("https://www.shl.se/api/sports-v2/"
              "season-series-game-types-filter")
SCHEDULE_URL = ("https://www.shl.se/api/sports-v2/"
                "game-schedule?seasonUuid={}&seriesUuid={}"
                "&gameTypeUuid={}")
SEASON_CODES = ("2023", "2024", "2025", "2026")
K = 8.0                 # the NHL lane's ENGINE PARAMS,
HFA_ELO = 32.0          # carried over un-tuned
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "data", "cache",
                          "shl_games_2023-27.json")


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            blob = json.load(f)
        print(f"cache: {len(blob['games'])} games "
              f"({blob['fetched_at']})", file=sys.stderr)
        return blob["games"], blob["fetched_at"], blob["teams"]
    filt = fetch(FILTER_URL)
    series = next(s for s in filt["series"]
                  if s["code"] == "SHL")["uuid"]
    gtype = next(g for g in filt["gameType"]
                 if g["code"] == "regular")["uuid"]
    seasons = {s["code"]: s["uuid"] for s in filt["season"]}
    games, teams = [], {}
    for code in SEASON_CODES:
        sched = fetch(SCHEDULE_URL.format(
            seasons[code], series, gtype))
        for t in sched.get("teamList", []):
            teams[t["teamCode"]] = t["teamCode"]
        for g in sched.get("gameInfo", []):
            if g.get("state") != "post-game":
                continue
            h, a = g["homeTeamInfo"], g["awayTeamInfo"]
            teams[h["code"]] = (h.get("names") or {}).get(
                "long", h["code"])
            teams[a["code"]] = (a.get("names") or {}).get(
                "long", a["code"])
            games.append({
                "date": (g.get("startDateTime") or "")[:10],
                "home": h["code"], "away": a["code"],
                "home_name": teams[h["code"]],
                "away_name": teams[a["code"]],
                "hs": int(h["score"]), "as": int(a["score"]),
                "final": True})
    games.sort(key=lambda g: g["date"])
    fetched_at = datetime.now().astimezone().isoformat(
        timespec="seconds")
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"fetched_at": fetched_at,
                   "source": "shl.se Sportality API "
                             "(sports-v2 game-schedule)",
                   "games": games, "teams": teams}, f,
                  indent=1)
    print(f"pulled: {len(games)} games", file=sys.stderr)
    return games, fetched_at, teams


def fit(games, fetched_at, teams):
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
    return {"sport": "shl",
            "season": "2023-24 to 2026-27 regular seasons",
            "fitted_at": datetime.now().astimezone().isoformat(
                timespec="seconds"),
            "source": f"shl.se official Sportality API "
                      f"(cached {fetched_at}; "
                      f"data/cache/shl_games_2023-27.json)",
            "params": {"K": K, "hfa_elo": HFA_ELO},
            "ratings": {k: round(v, 1)
                        for k, v in sorted(R.items())},
            "games": dict(sorted(counts.items())),
            "teams": teams,
            "backtest": {"brier": round(brier, 4),
                         "naive_brier": round(naive, 4),
                         "naive_home_brier": round(naive, 4),
                         "n": n,
                         "protocol": "walk-forward (pre-game "
                                     "ratings, sequential Elo, "
                                     "NHL-lane protocol)"}}


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "data", "v5-shl.json")
    games, fetched_at, teams = collect()
    print(f"teams ({len(teams)}): "
          + ", ".join(f"{c}={teams[c]}" for c in sorted(teams)),
          file=sys.stderr)
    blob = fit(games, fetched_at, teams)
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
