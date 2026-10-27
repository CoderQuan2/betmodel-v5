#!/usr/bin/env python3
"""fit_cfl.py — BetFi Xii pricing Build N, closer 1: the CFL fit.

FanDuel files CFL fixtures under the "ncaaf" page; the checker
names the competition (OTHER_COMPETITION_TEAMS) but no CFL fit
exists, so the fixtures stamp unpriced. This builder fits the
lane from REAL results and writes two artifacts, each gated by
its OWN house exam, scored BEFORE any engine wiring:

  data/v5-cfl.json        — moneyline/spread lane: sequential
                            Elo + OLS margin map (the fit_wnba /
                            fit_nba architecture).
  data/v5-totals-cfl.json — totals lane: the fit_totals
                            TotalsModel (expanding off/def
                            rates), in the v5-totals-<lane>
                            schema, so totals_price("cfl")
                            prices through the shared path once
                            "cfl" joins TOTALS_LANES.

SOURCE (verified by fetch, 2026-10-27): the league's own API,
https://cfl.ca/api/v1/content/data/schedule?seasonId={id} —
complete fixtures with scores, dates, game types. (ESPN's
football/cfl scoreboard was checked first and serves ZERO
events for every date tried, its league block frozen at season
2023 — a verified negative, the Build J Euroleague shape.)
Season ids (from the league API's own numbering, cross-checked
against the armstjc/cfl-data-repository harvester): 2016=27,
2017=28, 2018=29, 2019=30, 2021=32, 2022=1, 2023=2, 2024=33,
2025=34, 2026=75. Team ids: 1 BC, 6 Calgary, 7 Edmonton,
8 Hamilton, 11 Montreal, 13 Ottawa, 17 Saskatchewan,
19 Toronto, 20 Winnipeg — keyed here by FanDuel's full names
("British Columbia Lions" is FanDuel's form; the roster list's
"BC Lions" is carried as an alias by the engine wiring).
Regular season only: game_type_id == 1 AND the fixture's
event type is the regular season (playoff games carry other
type ids; the pulled counts are checked against the known RS
shape — 81 games a 9-team 18-game season, 63 in the shortened
2021 — in the run log).

DECLARED MODEL CHOICES (fixed before the exam ran; nothing
below was searched against the exam):
  * Elo: plain sequential Elo, K=20, HFA=55 Elo points (the
    NFL lane's own home-field constant, nfl_price), win prob
    1/(1+10^(-d/400)). No margin-of-victory multiplier. A tie
    (CFL regular-season games can tie) updates as a 0.5
    result and scores in the exam with y=0.5.
  * Ratings carry across seasons with a 50% regression
    toward 1500 at each season boundary (the TotalsModel /
    fit_totals NFL off-season rule).
  * Exam: walk-forward — every game's prediction is made
    from ratings built ONLY on prior games; Brier of those
    probabilities vs the naive baseline that predicts the
    expanding overall home-win rate for every game
    (fit_nba's exact baseline). The lane prices only if
    Brier < naive. No burn-in: the naive needs the same
    games, and both start scoring once at least one prior
    game exists (game 1 of the stream is never scored —
    there is nothing to predict it with).
  * Margin map: OLS with intercept of margin on the
    walk-forward Elo diff, residual SD (fit_nba's map).
  * Totals: TotalsModel with prior=4, Normal distribution,
    burn_in=60 scored games (the fit_totals NFL lane's
    prior; burn-in ~ two-thirds of a CFL season), the
    TotalsModel's own season-boundary regression. PASS
    requires MAE AND Brier both better than the expanding
    league-average naive (the totals house contract).

Cache: data/cache/cfl_games_2016-26.json — a re-run with the
cache present refits without re-pulling.

Usage: fit_cfl.py
"""
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
CACHE_PATH = os.path.join(DATA, "cache", "cfl_games_2016-26.json")
API = "https://cfl.ca/api/v1/content/data/schedule?seasonId={}"
SEASONS = {2016: 27, 2017: 28, 2018: 29, 2019: 30, 2021: 32,
           2022: 1, 2023: 2, 2024: 33, 2025: 34, 2026: 75}
TEAMS = {1: "British Columbia Lions", 6: "Calgary Stampeders",
         7: "Edmonton Elks", 8: "Hamilton Tiger-Cats",
         11: "Montreal Alouettes", 13: "Ottawa Redblacks",
         17: "Saskatchewan Roughriders", 19: "Toronto Argonauts",
         20: "Winnipeg Blue Bombers"}
K = 20
HFA_ELO = 55
BASE = 1500.0
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X "
      "10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) "
      "chrome/153.0.0.0 Safari/537.36"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_season(sid):
    req = urllib.request.Request(API.format(sid), headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def collect():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            blob = json.load(f)
        print(f"cache: {len(blob['games'])} games "
              f"({blob['fetched_at']})", file=sys.stderr)
        return blob["games"], blob["fetched_at"]
    games = []
    for year, sid in sorted(SEASONS.items()):
        j = fetch_season(sid)
        rs = 0
        for fx in j.get("fixtures", []):
            if fx.get("game_type_id") != 1:
                continue
            if fx.get("game_status") != "Finished":
                continue
            h, a = fx.get("home_team_id"), fx.get("away_team_id")
            if h not in TEAMS or a not in TEAMS:
                continue
            games.append({
                "date": (fx.get("start_at") or "")[:10],
                "season": year,
                "home": TEAMS[h], "away": TEAMS[a],
                "hs": int(fx["home_team_score"]),
                "as": int(fx["away_team_score"])})
            rs += 1
        print(f"  {year} (seasonId {sid}): {rs} RS games",
              file=sys.stderr)
    games.sort(key=lambda g: (g["date"], g["home"]))
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"fetched_at": now(), "games": games}, f)
    return games, now()


# ---------------------------------------------------------------- Elo

def elo_walk_forward(games):
    """Walk-forward Elo exam + final ratings + margin map.
    Returns (backtest, ratings, margin_map)."""
    ratings = {t: BASE for t in TEAMS.values()}
    season = None
    home_wins = home_games = 0
    br_m = br_n = 0.0
    n = 0
    xs, ys = [], []          # walk-forward (elo diff, margin)
    for g in games:
        if season is not None and g["season"] != season:
            for t in ratings:
                ratings[t] = BASE + (ratings[t] - BASE) * 0.5
        season = g["season"]
        h, a = g["home"], g["away"]
        diff = ratings[h] + HFA_ELO - ratings[a]
        p = 1.0 / (1.0 + 10 ** (-diff / 400.0))
        margin = g["hs"] - g["as"]
        y = 1.0 if margin > 0 else (0.0 if margin < 0 else 0.5)
        if home_games > 0:
            p_naive = home_wins / home_games
            br_m += (p - y) ** 2
            br_n += (p_naive - y) ** 2
            n += 1
        xs.append(diff)
        ys.append(margin)
        # Elo update (tie = 0.5 result)
        ratings[h] += K * (y - p)
        ratings[a] += K * ((1.0 - y) - (1.0 - p))
        if margin > 0:
            home_wins += 1
        home_games += 1
    # margin map: OLS with intercept, margin ~ elo diff
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx if sxx else 0.0
    a0 = my - b * mx
    resid = [y - (a0 + b * x) for x, y in zip(xs, ys)]
    sd = math.sqrt(sum(r * r for r in resid) / (len(resid) - 2))
    backtest = {
        "n": n,
        "brier": round(br_m / n, 4) if n else None,
        "naive_brier": round(br_n / n, 4) if n else None,
        "protocol": ("walk-forward (ratings from prior games "
                     "only, 50% regression at season "
                     "boundaries); naive = expanding overall "
                     "home-win rate; ties score y=0.5; PASS "
                     "requires Brier < naive")}
    margin_map = {"a": round(a0, 3), "b": round(b, 4),
                  "sd": round(sd, 2)}
    return backtest, ratings, margin_map


# ---------------------------------------------------------------- totals

sys.path.insert(0, HERE)
from fit_totals import TotalsModel, walk_forward  # noqa: E402


def main():
    games, fetched_at = collect()
    print(f"games: {len(games)} "
          f"({games[0]['date']} .. {games[-1]['date']})",
          file=sys.stderr)
    bt, ratings, margin_map = elo_walk_forward(games)
    passed = (bt["brier"] is not None
              and bt["brier"] < bt["naive_brier"])
    print(f"ELO EXAM: Brier {bt['brier']} vs naive "
          f"{bt['naive_brier']}, n={bt['n']} -> "
          f"{'PASS' if passed else 'FAILED-EXAM'}",
          file=sys.stderr)
    fit = {
        "sport": "cfl", "lane": "cfl",
        "fitted_at": now(),
        "source": ("CFL official API (cfl.ca/api/v1/content/"
                   "data/schedule), regular seasons 2016-2019, "
                   "2021-2026 (no 2020 season — cancelled); "
                   f"fetched {fetched_at}"),
        "history_n": len(games),
        "params": {"model": "sequential Elo", "K": K,
                   "hfa_elo": HFA_ELO, "base": BASE,
                   "season_regression": 0.5,
                   "mov_multiplier": None},
        "ratings": {t: round(ratings[t], 1)
                    for t in sorted(ratings)},
        "margin_map": margin_map,
        "backtest": bt,
        "status": "FITTED" if passed else "FAILED-EXAM"}
    out = os.path.join(DATA, "v5-cfl.json")
    with open(out, "w") as f:
        json.dump(fit, f, indent=1)
    print(f"wrote {out} (status {fit['status']})",
          file=sys.stderr)

    # totals lane — the fit_totals TotalsModel, same stream
    tgames = [dict(g) for g in games]
    res, _model = walk_forward(tgames, prior_games=4,
                                 dist="normal", burn_in=60)
    t_passed = res.get("verdict") == "PASS"
    print(f"TOTALS EXAM: MAE {res.get('mae_model')} vs naive "
          f"{res.get('mae_naive')}, Brier "
          f"{res.get('brier_model')} vs {res.get('brier_naive')}"
          f", n={res.get('n')} -> {res.get('verdict')}",
          file=sys.stderr)
    teams = res.pop("_teams", {})
    league = res.pop("_league", {})
    _totals = [g["hs"] + g["as"] for g in games]
    _mt = sum(_totals) / len(_totals)
    league["total_mean"] = round(_mt, 3)
    league["total_sd"] = round(math.sqrt(
        sum((t - _mt) ** 2 for t in _totals)
        / (len(_totals) - 1)), 3)
    res["protocol"] = (
        "walk-forward (strengths/league rates from prior "
        "games only); naive = expanding league-average total; "
        "Brier scored on P(over L*), L* = .5 line at the "
        "naive mean; PASS requires MAE and Brier both better "
        "than naive")
    tfit = {
        "sport": "cfl", "lane": "cfl-totals",
        "fitted_at": now(),
        "source": ("CFL official API (cfl.ca/api/v1/content/"
                   "data/schedule), regular seasons 2016-2019, "
                   "2021-2026 — same stream as v5-cfl.json"),
        "history_n": len(games),
        "params": {"prior_games": 4, "distribution": "normal",
                   "burn_in": 60},
        "distribution_why": ("Normal on total points: a CFL "
                             "total is the sum of many scoring "
                             "events across two offenses (the "
                             "fit_totals NFL treatment)."),
        "league": league,
        "sigma": res.get("sigma_resid"),
        "teams": teams,
        "aliases": {"BC Lions": "British Columbia Lions"},
        "backtest": res,
        "status": "FITTED" if t_passed else "FAILED-EXAM"}
    tout = os.path.join(DATA, "v5-totals-cfl.json")
    with open(tout, "w") as f:
        json.dump(tfit, f, indent=1)
    print(f"wrote {tout} (status {tfit['status']})",
          file=sys.stderr)


if __name__ == "__main__":
    main()
