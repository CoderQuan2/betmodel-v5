#!/usr/bin/env python3
"""fit_ep_hockey.py — BetFi Xii pricing Build M: the
Elite Prospects-mirror hockey fit builder (DEL, ICE
Hockey League, Denmark Metal Ligaen, Norway
EliteHockey Ligaen, France Ligue Magnus).

These five leagues' own data routes resisted the
hunt in this build (DEL: TYPO3 site, no public JSON
feed surfaced; ICE: its hockeydata.net API is
key-gated; Denmark: league site unreachable and the
federation site carries no data API; Norway and
France: league/federation sites carry no public
results API) — so the fits come from the maintained
public mirror the hunt order names last: Elite
Prospects' league scores pages, which are
server-rendered with date / home / visiting / score
per game and paginate ?page=N. Regular-season
separation is STRUCTURAL, declared before the exam:
EP lists RS + playoffs on one page, but each
league's RS is a fixed round-robin format (every
pair meeting exactly K times — DEL K=4, ICE K=4,
Metal Ligaen K=6, EliteHockey K=5, Ligue Magnus
K=4) and the playoffs start only after it ends, so
the RS is exactly the date-ordered PREFIX in which
every pair completes its Kth meeting. A completed
season whose prefix does not close exactly (all
pairs at K, total = C(teams,2)*K) is EXCLUDED and
reported, never silently fitted (ICE 2023-24 fails:
its intermediate round breaks the prefix). EP's
Denmark coverage begins 2025-26 (its older season
pages return no game rows — verified). The current
partial season (2026-27) takes all listed games;
its playoffs have not begun.

Writes data/v5-<league>.json in the house fit shape
with the NHL lane's Elo protocol and walk-forward
exam — see fit_ahl.py's docstring (K=8, HFA_ELO=32,
no MOV multiplier, naive = the overall home-win-rate
baseline; the lane prices only if Brier < naive).
Per-team game counts ride along for the engine's
sigma-integrated logistic.

Cache: data/cache/ep_<slug>_games.json (validated
RS games + the per-season validation report).

Usage: fit_ep_hockey.py <del|icehl|denmark|norway|
ligue-magnus> [out_path]
"""
import collections
import json
import os
import re
import statistics
import sys
import urllib.request
from datetime import datetime

LEAGUES = {
    "del": {"label": "German DEL", "slug": "del", "k": 4,
            "fit": "v5-del.json"},
    "icehl": {"label": "ICE Hockey League (Austria)",
              "slug": "icehl", "k": 4, "fit": "v5-icehl.json"},
    "denmark": {"label": "Denmark Metal Ligaen",
                "slug": "denmark", "k": 6,
                "fit": "v5-denmark.json"},
    "norway": {"label": "Norway EliteHockey Ligaen",
               "slug": "norway", "k": 5,
               "fit": "v5-norway.json"},
    "ligue-magnus": {"label": "France Ligue Magnus",
                     "slug": "ligue-magnus", "k": 4,
                     "fit": "v5-ligue-magnus.json"},
}
SEASONS = ("2023-2024", "2024-2025", "2025-2026")
CURRENT_SEASON = "2026-2027"
K = 8.0                 # the NHL lane's ENGINE PARAMS,
HFA_ELO = 32.0          # carried over un-tuned
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROW = re.compile(
    r'data-stat="date"><time dateTime="(\d{4}-\d{2}-\d{2})'
    r'.*?data-stat="home">.*?href="/team/\d+/[^"]*">([^<]+)</a>'
    r'.*?data-stat="visiting">.*?href="/team/\d+/[^"]*">'
    r'([^<]+)</a>.*?data-stat="score">.*?>\s*(\d+)'
    r'\s*<!-- -->\s*-\s*<!-- -->\s*(\d+)\s*<',
    re.S)
# EP name variants for one club across seasons — merged
# to the club's current EP form so its history is one
# entity (verified: both forms are HC Pustertal).
NAME_FIX = {"Pustertal/Val Pusteria": "HC Pustertal"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "ignore")


def season_games(slug, season):
    games, page = [], 1
    while page <= 12:
        html = fetch(f"https://www.eliteprospects.com/"
                     f"league/{slug}/scores/{season}"
                     f"?page={page}")
        rows = ROW.findall(html)
        if not rows:
            break
        for date, home, away, hs, as_ in rows:
            games.append({"date": date,
                          "home": NAME_FIX.get(
                              home.strip(), home.strip()),
                          "away": NAME_FIX.get(
                              away.strip(), away.strip()),
                          "hs": int(hs), "as": int(as_),
                          "final": True})
        page += 1
    games.sort(key=lambda g: g["date"])
    return games


def rs_prefix(games, k):
    """The date-ordered prefix in which every pair
    completes its kth meeting — (prefix, report)."""
    pairs = collections.Counter()
    kept = []
    for g in games:
        key = tuple(sorted((g["home"], g["away"])))
        pairs[key] += 1
        if pairs[key] > k:
            return None, (f"pair {key} exceeded {k} "
                          f"meetings at {g['date']} before "
                          f"the round robin closed")
        kept.append(g)
        teams = set()
        for a, b in pairs:
            teams.add(a)
            teams.add(b)
        if (len(pairs) == len(teams) * (len(teams) - 1) // 2
                and all(v == k for v in pairs.values())):
            return kept, (f"closed: {len(kept)} games, "
                          f"{len(teams)} teams, all pairs "
                          f"at {k}")
    return None, "round robin never closed"


def collect(cfg):
    cache_path = os.path.join(
        ROOT, "data", "cache", f"ep_{cfg['slug']}_games.json")
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            blob = json.load(f)
        print(f"cache: {len(blob['games'])} games "
              f"({blob['fetched_at']})", file=sys.stderr)
        for line in blob.get("report", []):
            print(f"  {line}", file=sys.stderr)
        return blob["games"], blob["fetched_at"]
    games, report = [], []
    for season in SEASONS:
        listed = season_games(cfg["slug"], season)
        if not listed:
            report.append(f"{season}: no game rows on EP "
                          f"(coverage gap — excluded)")
            continue
        kept, why = rs_prefix(listed, cfg["k"])
        if kept is None:
            report.append(f"{season}: EXCLUDED — {why} "
                          f"(listed {len(listed)})")
            continue
        report.append(f"{season}: RS {why} "
                      f"(listed {len(listed)})")
        games += kept
    current = season_games(cfg["slug"], CURRENT_SEASON)
    report.append(f"{CURRENT_SEASON}: partial season, "
                  f"{len(current)} games taken as listed")
    games += current
    games.sort(key=lambda g: g["date"])
    fetched_at = datetime.now().astimezone().isoformat(
        timespec="seconds")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump({"fetched_at": fetched_at,
                   "source": "Elite Prospects league "
                             "scores pages (public mirror)",
                   "report": report, "games": games}, f,
                  indent=1)
    for line in report:
        print(f"  {line}", file=sys.stderr)
    print(f"pulled: {len(games)} RS games", file=sys.stderr)
    return games, fetched_at


def fit(games, fetched_at, cfg):
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
    return {"sport": cfg["slug"],
            "league": cfg["label"],
            "season": "validated regular seasons "
                      "2023-24..2025-26 + 2026-27 partial "
                      "(see cache report)",
            "fitted_at": datetime.now().astimezone().isoformat(
                timespec="seconds"),
            "source": f"Elite Prospects league scores "
                      f"pages (public mirror; cached "
                      f"{fetched_at}; data/cache/"
                      f"ep_{cfg['slug']}_games.json)",
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
    key = sys.argv[1]
    cfg = LEAGUES[key]
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        ROOT, "data", cfg["fit"])
    games, fetched_at = collect(cfg)
    teams = sorted({g["home"] for g in games}
                   | {g["away"] for g in games})
    print(f"teams ({len(teams)}): {', '.join(teams)}",
          file=sys.stderr)
    blob = fit(games, fetched_at, cfg)
    bt = blob["backtest"]
    passed = bt["brier"] < bt["naive_home_brier"]
    print(f"exam [{cfg['label']}]: walk-forward Brier "
          f"{bt['brier']} vs naive {bt['naive_home_brier']}, "
          f"n={bt['n']} -> "
          f"{'PASSED' if passed else 'FAILED-EXAM'}")
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=1)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
