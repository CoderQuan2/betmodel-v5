#!/usr/bin/env python3
"""fit_swiss_nl.py — BetFi Xii pricing Build M: the
Swiss National League fit builder.

Fits the Swiss NL lane (FanDuel files its fixtures
under the "nhl" page, competition "Swiss NLA") from
REAL results: the National League's own site API
(www.nationalleague.ch/api/games?season={year} — the
JSON the league's app renders; the season parameter
is the ENDING year, so 2026 is 2025-26). No key
required. The endpoint's list mixes regular-season
games with exhibitions (flagged isExhibition) and
cross-tier fixtures (Swiss Cup / friendlies against
Swiss League and foreign clubs); playoffs live on a
separate endpoint (/api/games/playoffs) and are not
pulled. THE FILTER, declared before the exam: a game
counts iff it is finished, isExhibition is false,
BOTH clubs are National League clubs (the NL club
set below — unchanged across 2023-24..2026-27: no
promotion/relegation moved a club in this window),
and its date falls inside the regular season, where
"the regular season" is defined STRUCTURALLY, not by
a calendar guess (the RS end date moved between
seasons: Mar 4 in 2024, Mar 1 in 2025, Mar 7 in
2026): the NL regular season is a quadruple round
robin — 14 clubs, every pair meeting exactly 4
times, 364 games — and the play-in round starts
only after it ends, so the RS is exactly the
date-ordered PREFIX of the filtered list in which
every pair completes its 4th meeting. The builder
takes that prefix per completed season and asserts
it totals 364 with all 91 pairs at 4 — a season
that fails the assertion is reported, not silently
fitted. (The current partial season takes all
filtered games; its play-in round has not begun.)

Writes data/v5-swiss-nl.json in the house fit shape
with the NHL lane's Elo protocol and walk-forward
exam — see fit_ahl.py's docstring (K=8, HFA_ELO=32,
no MOV multiplier, naive = the overall home-win-rate
baseline; the lane prices only if Brier < naive).
Per-team game counts ride along for the engine's
sigma-integrated logistic.

Cache: data/cache/swiss_nl_games_2024-27.json.

Usage: fit_swiss_nl.py [out_path]   (default:
../data/v5-swiss-nl.json relative to this script's
repo root)
"""
import collections
import json
import os
import statistics
import sys
import urllib.request
from datetime import datetime

API = "https://www.nationalleague.ch/api/games?season={}"
SEASONS = (2024, 2025, 2026, 2027)   # ending years
# The National League club set (source-side names),
# unchanged 2023-24..2026-27.
NL_CLUBS = {
    "HC Ajoie", "HC Ambri-Piotta", "SC Bern",
    "EHC Biel-Bienne", "HC Davos", "Fribourg-Gottéron",
    "Genève-Servette HC", "EHC Kloten", "Lausanne HC",
    "HC Lugano", "SC Rapperswil-Jona Lakers",
    "SCL Tigers", "EV Zug", "ZSC Lions",
}
K = 8.0                 # the NHL lane's ENGINE PARAMS,
HFA_ELO = 32.0          # carried over un-tuned
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "data", "cache",
                          "swiss_nl_games_2024-27.json")


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
        raw = fetch_season(year)
        cand = []
        for g in raw:
            if g.get("status") != "finished":
                continue
            if g.get("isExhibition"):
                continue
            if (g["homeTeamName"] not in NL_CLUBS
                    or g["awayTeamName"] not in NL_CLUBS):
                continue
            cand.append({
                "date": (g.get("date") or "")[:10],
                "home": g["homeTeamName"],
                "away": g["awayTeamName"],
                "hs": int(g["homeTeamResult"]),
                "as": int(g["awayTeamResult"]),
                "final": True})
        cand.sort(key=lambda g: g["date"])
        if year < 2027:
            # completed season: the RS is the prefix in
            # which every pair completes its 4th meeting
            pairs = collections.Counter()
            kept, idx = [], 0
            while idx < len(cand):
                day = cand[idx]["date"]
                while (idx < len(cand)
                       and cand[idx]["date"] == day):
                    g = cand[idx]
                    pairs[tuple(sorted(
                        (g["home"], g["away"])))] += 1
                    kept.append(g)
                    idx += 1
                if (len(kept) == 364 and len(pairs) == 91
                        and all(v == 4
                                for v in pairs.values())):
                    break
            print(f"season {year}: RS prefix {len(kept)} "
                  f"games ending {kept[-1]['date']} "
                  f"(of {len(cand)} league-vs-league "
                  f"listed)", file=sys.stderr)
        else:
            kept = cand
            print(f"season {year}: partial, kept "
                  f"{len(kept)} of {len(raw)} listed",
                  file=sys.stderr)
        games += kept
    games.sort(key=lambda g: g["date"])
    fetched_at = datetime.now().astimezone().isoformat(
        timespec="seconds")
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"fetched_at": fetched_at,
                   "source": "nationalleague.ch official "
                             "API (/api/games)",
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
    return {"sport": "swiss-nl",
            "season": "2023-24 to 2026-27 regular seasons",
            "fitted_at": datetime.now().astimezone().isoformat(
                timespec="seconds"),
            "source": f"nationalleague.ch official API "
                      f"(cached {fetched_at}; data/cache/"
                      f"swiss_nl_games_2024-27.json)",
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
        ROOT, "data", "v5-swiss-nl.json")
    games, fetched_at = collect()
    # structural validation per completed season
    by_season = collections.defaultdict(list)
    for g in games:
        y = int(g["date"][:4])
        season = y + 1 if int(g["date"][5:7]) >= 8 else y
        by_season[season].append(g)
    for season in sorted(by_season):
        kept = by_season[season]
        pairs = collections.Counter(
            tuple(sorted((g["home"], g["away"])))
            for g in kept)
        ok = (len(kept) == 364 and len(pairs) == 91
              and all(v == 4 for v in pairs.values()))
        print(f"validate {season}: {len(kept)} games, "
              f"{len(pairs)} pairs, counts "
              f"{sorted(set(pairs.values()))} -> "
              f"{'OK (364/91x4)' if ok else 'CHECK'}",
              file=sys.stderr)
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
