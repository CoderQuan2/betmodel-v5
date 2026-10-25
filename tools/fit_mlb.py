#!/usr/bin/env python3
"""fit_mlb.py — BetFi Xii (fix-guy R2): the MLB fit builder.

Fits the baseball lane from REAL results: ESPN MLB scoreboard
day-pulls over the full 2025 regular season (2025-03-27 ..
2025-09-28, the house method — the NBA Elo lane was fit the
same way over 1,235 ESPN games). Writes data/v5-mlb.json:

  * sequential Elo (K=4 — low, because a 162-game season of
    high-variance single games wants slow ratings; home field
    as an Elo bump), walk-forward: every game's prediction is
    made from ratings built ONLY on prior games, then the
    rating updates. Backtest = Brier of those walk-forward
    probabilities vs a naive baseline that predicts the
    running league home-win rate for every game.
  * a runs model: per-team runs scored / allowed rates
    (shrunk toward the league mean, 10-game prior), league
    average runs, and the full-season game-total mean/SD —
    carried under `totals_candidate` for the totals lane
    (Glow/Praxis). This builder does NOT wire a totals
    checker; moneylines price off the Elo.

Usage: fit_mlb.py [out_path]   (default: ../data/v5-mlb.json
relative to this script's repo root)
"""
import json
import math
import os
import sys
import urllib.request
from datetime import date, timedelta

ESPN_MLB = ("https://site.api.espn.com/apis/site/v2/sports/"
            "baseball/mlb/scoreboard")
SEASON_START = date(2025, 3, 27)
SEASON_END = date(2025, 9, 28)
K = 4.0
HFA_ELO = 24.0          # home-field bump, Elo points
PRIOR_GAMES = 10        # shrinkage prior for run rates
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}


def fetch_day(d):
    url = f"{ESPN_MLB}?dates={d.strftime('%Y%m%d')}&limit=200"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


CLUBS = {"ARI", "ATH", "ATL", "BAL", "BOS", "CHC", "CHW", "CIN",
         "CLE", "COL", "DET", "HOU", "KC", "LAA", "LAD", "MIA",
         "MIL", "MIN", "NYM", "NYY", "PHI", "PIT", "SD", "SEA",
         "SF", "STL", "TB", "TEX", "TOR", "WSH"}


def collect():
    games = []
    d = SEASON_START
    while d <= SEASON_END:
        if d.day == 1:
            print(f"[fit-mlb] ... {d} games so far: {len(games)}",
                  flush=True)
        try:
            blob = fetch_day(d)
        except Exception as e:
            print(f"[fit-mlb] {d} FAILED: {type(e).__name__}: {e}")
            d += timedelta(days=1)
            continue
        for ev in blob.get("events") or []:
            for comp in ev.get("competitions") or []:
                cs = comp.get("competitors") or []
                if len(cs) != 2:
                    continue
                by = {c.get("homeAway"): c for c in cs}
                h, a = by.get("home"), by.get("away")
                if not h or not a:
                    continue
                st = (comp.get("status") or {}).get("type") or {}
                if not st.get("completed"):
                    continue
                try:
                    hs = float(h.get("score"))
                    as_ = float(a.get("score"))
                except (TypeError, ValueError):
                    continue
                hab = (h.get("team") or {}).get("abbreviation")
                aab = (a.get("team") or {}).get("abbreviation")
                if hab not in CLUBS or aab not in CLUBS:
                    # exhibition rows (All-Star AL/NL, spring
                    # split squads) are not league games — they
                    # never enter the fit.
                    continue
                games.append({
                    "date": ev.get("date"),
                    "home": hab, "away": aab,
                    "home_runs": hs, "away_runs": as_})
        d += timedelta(days=1)
    games.sort(key=lambda g: g["date"] or "")
    return games


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data",
        "v5-mlb.json")
    games = collect()
    print(f"[fit-mlb] completed games: {len(games)}")
    if len(games) < 1000:
        raise SystemExit("[fit-mlb] too few games — refusing to "
                         "fit on a partial season pull")

    ratings = {}
    rs = {}   # runs scored per game (expanding)
    ra = {}   # runs allowed per game
    gp = {}
    tot_runs = 0.0
    tot_sq = 0.0
    home_wins = 0
    n_pred = 0
    brier = 0.0
    naive_brier = 0.0
    correct = 0

    def rate(t):
        return ratings.get(t, 1500.0)

    for g in games:
        h, a = g["home"], g["away"]
        hr, ar = g["home_runs"], g["away_runs"]
        if hr == ar:
            continue  # baseball cannot tie; a tie row is bad data
        # walk-forward prediction BEFORE the update
        d = rate(h) + HFA_ELO - rate(a)
        p_home = 1 / (1 + 10 ** (-d / 400))
        y = 1.0 if hr > ar else 0.0
        naive = (home_wins / n_pred) if n_pred >= 30 else 0.5
        brier += (p_home - y) ** 2
        naive_brier += (naive - y) ** 2
        n_pred += 1
        if (p_home >= 0.5) == (y == 1.0):
            correct += 1
        home_wins += int(y)
        # Elo update
        e_home = p_home
        ratings[h] = rate(h) + K * (y - e_home)
        ratings[a] = rate(a) + K * ((1 - y) - (1 - e_home))
        # run rates
        for t, s, al in ((h, hr, ar), (a, ar, hr)):
            rs[t] = rs.get(t, 0.0) + s
            ra[t] = ra.get(t, 0.0) + al
            gp[t] = gp.get(t, 0) + 1
        tot = hr + ar
        tot_runs += tot
        tot_sq += tot * tot

    n = n_pred
    league_avg = tot_runs / (2 * n)     # runs per team per game
    tot_mean = tot_runs / n
    tot_sd = math.sqrt(max(tot_sq / n - tot_mean ** 2, 0.0))
    runs = {}
    for t in sorted(gp):
        runs[t] = {
            "off": (rs[t] + PRIOR_GAMES * league_avg)
                   / (gp[t] + PRIOR_GAMES),
            "def": (ra[t] + PRIOR_GAMES * league_avg)
                   / (gp[t] + PRIOR_GAMES),
            "gp": gp[t]}
    from datetime import datetime, timezone
    blob = {
        "sport": "mlb",
        "league": {"avg_runs_per_team": round(league_avg, 3)},
        "fitted_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "source": ("ESPN MLB scoreboard day pulls, 2025 regular "
                   "season 2025-03-27..2025-09-28 (site.api.espn"
                   ".com baseball/mlb scoreboard?dates=)"),
        "params": {"K": K, "hfa_elo": HFA_ELO,
                   "prior_games": PRIOR_GAMES},
        "elo": {t: round(ratings[t], 1) for t in sorted(ratings)},
        "runs": runs,
        "backtest": {
            "brier": round(brier / n, 4),
            "naive_brier": round(naive_brier / n, 4),
            "accuracy": round(correct / n, 4),
            "n": n,
            "protocol": "walk-forward (Elo from prior games "
                        "only; naive = running league home-win "
                        "rate)"},
        "totals_candidate": {
            "note": "runs model + full-season game-total "
                    "distribution, carried for the totals lane "
                    "(Glow/Praxis) — NOT wired to a totals "
                    "checker by this fit",
            "league_total_mean": round(tot_mean, 3),
            "league_total_sd": round(tot_sd, 3)},
    }
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=1)
    print(f"[fit-mlb] wrote {out_path}")
    print(f"[fit-mlb] teams={len(ratings)} n={n} "
          f"brier={blob['backtest']['brier']} "
          f"naive={blob['backtest']['naive_brier']} "
          f"acc={blob['backtest']['accuracy']} "
          f"league_avg_runs={league_avg:.3f} "
          f"total mean/sd={tot_mean:.2f}/{tot_sd:.2f}")


if __name__ == "__main__":
    main()
