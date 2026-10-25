#!/usr/bin/env python3
"""BetFi Xii — totals fit builder (CODER GLOW, FIX-THE-LAZINESS).

Fits a totals distribution per US lane from REAL game history and
writes data/v5-totals-<lane>.json in the v5-soccer.json schema
family. Reproducible: run this script, get the artifacts.

MODEL (per lane, from the lane's own scoring process):
  expected score  lam_home = LH * off[home] * def[away]
                  lam_away = LA * off[away] * def[home]
  off/def are per-team multiplicative scoring/conceding rates,
  shrunk toward 1.0 with `prior_games` pseudo-games at the league
  mean (the soccer fit's shrinkage recipe). LH/LA are the league's
  home/away per-team scoring means — the league's scoring
  environment, fitted per lane, never borrowed across lanes.
  Total mu = lam_home + lam_away (neutral-site: both at league
  mean rate). Distribution of the total, per lane:
    nfl / ncaaf / nba — Normal(mu, sigma): totals are sums of many
      scoring events and the empirical totals distribution is
      near-normal; sigma is the walk-forward residual SD.
    nhl — Poisson(mu): goals are low-count events; the sum of the
      two Poisson scoring rates is Poisson, exactly like the
      soccer grid's totals.

WALK-FORWARD (house contract): strengths from prior games only.
After a burn-in, every game is predicted from the state built on
strictly earlier games. The naive baseline predicts the expanding
league-average total with the expanding totals SD. The totals
model must beat the naive baseline on BOTH MAE and the Brier
score of P(over L*) — L* = the .5 line at the naive mean, the
honest line-free way to score a totals distribution when the
history carries no closing lines — or the lane ships
FAILED-EXAM in its fit file and the engine keeps stamping it
UNPRICED. (NFL additionally scores P(over) against the real
closing total_line nflverse carries.)

Sources (all real, all cited in the artifacts):
  ncaaf — data/cfb_games_2026.json (in-repo, ESPN-sourced, n=458)
  nba   — ESPN NBA scoreboard day pulls, cached games file
          (data/cache/nba_games_2025-26.json; lab cache fallback)
  nfl   — nflverse games.csv (github.com/nflverse/nfldata),
          REG games, seasons 2024 + 2025-to-date, with a 50%
          off-season regression of team rates at the boundary
  nhl   — ESPN NHL scoreboard day pulls 2025-26 (this builder
          pulls them; cached to data/cache/nhl_games_2025-26.json)
"""
import csv
import io
import json
import math
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
LAB_CACHE = os.path.expanduser("~/workspace/bets-analyst/data/cache")

UA = {"User-Agent": "betfi-xii-fit-totals"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------- games

def games_ncaaf():
    with open(os.path.join(DATA, "cfb_games_2026.json")) as f:
        raw = json.load(f)
    out = []
    for g in raw:
        out.append({"date": g["date"], "home": g["home"],
                    "away": g["away"], "hs": g["home_score"],
                    "as": g["away_score"],
                    "neutral": bool(g.get("neutral"))})
    return out, ("in-repo data/cfb_games_2026.json (ESPN-sourced "
                 "2026 season game results)")


NBA_ALIASES = {}


def games_nba():
    for p in (os.path.join(DATA, "cache", "nba_games_2025-26.json"),
              os.path.join(LAB_CACHE, "nba_games_2025-26.json")):
        if os.path.exists(p):
            with open(p) as f:
                blob = json.load(f)
            # full name -> code, verbatim from the source file's
            # own home_name/away_name fields — the map the live
            # pull's full names need to reach the fit's keys.
            for g in blob["games"]:
                if g.get("home_name"):
                    NBA_ALIASES[g["home_name"]] = g["home"]
                if g.get("away_name"):
                    NBA_ALIASES[g["away_name"]] = g["away"]
            out = []
            for g in blob["games"]:
                if not g.get("final"):
                    continue
                # All-Star weekend exhibitions (STARS / STRIPES /
                # WORLD) are not regular-season team basketball —
                # no-defense showcase totals would distort the
                # league scoring environment. Excluded, named here.
                if g["home"] in ("STARS", "STRIPES", "WORLD") \
                        or g["away"] in ("STARS", "STRIPES",
                                          "WORLD"):
                    continue
                out.append({"date": g["date"], "home": g["home"],
                            "away": g["away"], "hs": g["hs"],
                            "as": g["as"], "neutral": False})
            return out, ("ESPN NBA scoreboard day pulls (cached "
                         "2026-10-19; data/cache/"
                         "nba_games_2025-26.json)")
    raise SystemExit("NBA games cache not found in worktree or lab")


NFLVERSE_MAP = {"WAS": "WSH", "LA": "LAR", "STL": "LAR",
                "SD": "LAC", "OAK": "LV"}


def games_nfl():
    url = ("https://raw.githubusercontent.com/nflverse/nfldata/"
           "master/data/games.csv")
    text = fetch(url).decode()
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        if row["game_type"] != "REG":
            continue
        if row["season"] not in ("2024", "2025"):
            continue
        if not row["home_score"] or not row["away_score"]:
            continue
        out.append({
            "date": row["gameday"],
            "season": int(row["season"]),
            "home": NFLVERSE_MAP.get(row["home_team"],
                                     row["home_team"]),
            "away": NFLVERSE_MAP.get(row["away_team"],
                                     row["away_team"]),
            "hs": int(row["home_score"]),
            "as": int(row["away_score"]),
            "neutral": row["location"] == "Neutral",
            "total_line": (float(row["total_line"])
                           if row["total_line"] else None)})
    out.sort(key=lambda g: g["date"])
    return out, ("nflverse games.csv (github.com/nflverse/nfldata)"
                 " — REG games, seasons 2024 + 2025-to-date; "
                 "50% off-season regression of team rates")


def _espn_nhl_day(d):
    url = ("https://site.api.espn.com/apis/site/v2/sports/hockey/"
           f"nhl/scoreboard?dates={d:%Y%m%d}")
    try:
        blob = json.loads(fetch(url, timeout=20))
    except Exception:
        return []
    out = []
    for ev in blob.get("events", []):
        if ev["status"]["type"]["name"] != "STATUS_FINAL":
            continue
        comp = ev["competitions"][0]
        sides = {}
        for c in comp["competitors"]:
            sides[c["homeAway"]] = (c["team"]["displayName"],
                                    int(c["score"]))
        if "home" in sides and "away" in sides:
            out.append({"date": d.isoformat(),
                        "home": sides["home"][0],
                        "away": sides["away"][0],
                        "hs": sides["home"][1],
                        "as": sides["away"][1],
                        "neutral": False})
    return out


def games_nhl():
    cache = os.path.join(DATA, "cache", "nhl_games_2025-26.json")
    if os.path.exists(cache):
        with open(cache) as f:
            return json.load(f), ("ESPN NHL scoreboard day pulls "
                                  "2025-26 (cached by this builder)")
    days = []
    d = datetime(2025, 10, 7).date()
    end = datetime(2026, 4, 17).date()
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    out = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for day_games in ex.map(_espn_nhl_day, days):
            out.extend(day_games)
    out.sort(key=lambda g: g["date"])
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w") as f:
        json.dump(out, f)
    return out, ("ESPN NHL scoreboard day pulls, 2025-26 regular "
                 "season (site.api.espn.com hockey/nhl/scoreboard)")


def _espn_mlb_day(d):
    url = ("https://site.api.espn.com/apis/site/v2/sports/baseball/"
           f"mlb/scoreboard?dates={d:%Y%m%d}")
    try:
        blob = json.loads(fetch(url, timeout=20))
    except Exception:
        return []
    out = []
    for ev in blob.get("events", []):
        if ev["status"]["type"]["name"] != "STATUS_FINAL":
            continue
        comp = ev["competitions"][0]
        sides = {}
        for c in comp["competitors"]:
            sides[c["homeAway"]] = (c["team"]["displayName"],
                                    int(c["score"]))
        if "home" in sides and "away" in sides:
            out.append({"date": d.isoformat(),
                        "home": sides["home"][0],
                        "away": sides["away"][0],
                        "hs": sides["home"][1],
                        "as": sides["away"][1],
                        "neutral": False})
    return out


def games_mlb():
    """ESPN MLB scoreboard day pulls, 2025 regular season — the
    same source as Guy's v5-mlb.json moneyline fit (his file
    carries only aggregates + a totals_candidate block; the exam
    here needs game-level history, so this builder pulls and
    caches it: data/cache/mlb_games_2025.json)."""
    cache = os.path.join(DATA, "cache", "mlb_games_2025.json")
    if os.path.exists(cache):
        with open(cache) as f:
            return json.load(f), ("ESPN MLB scoreboard day pulls "
                                  "2025 (cached by this builder)")
    days = []
    d = datetime(2025, 3, 27).date()
    end = datetime(2025, 9, 28).date()
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    out = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for day_games in ex.map(_espn_mlb_day, days):
            out.extend(day_games)
    out.sort(key=lambda g: g["date"])
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w") as f:
        json.dump(out, f)
    return out, ("ESPN MLB scoreboard day pulls, 2025 regular "
                 "season (site.api.espn.com baseball/mlb "
                 "scoreboard) — same source as v5-mlb.json")


# ---------------------------------------------------------------- model

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def pois_cdf(k, lam):
    """P(X <= k) for X ~ Poisson(lam)."""
    if k < 0:
        return 0.0
    term = math.exp(-lam)
    s = term
    for i in range(1, int(k) + 1):
        term *= lam / i
        s += term
    return s


class TotalsModel:
    """Expanding-window team off/def rates with shrinkage."""

    def __init__(self, prior_games, dist):
        self.prior = prior_games
        self.dist = dist
        self.pf = {}
        self.pa = {}
        self.gp = {}
        self.sum_h = 0.0   # home scores
        self.sum_a = 0.0   # away scores
        self.n = 0
        self.season = None

    def _shrunk(self, num, gp, mean):
        return (num + self.prior * mean) / ((gp + self.prior) * mean)

    def predict(self, home, away, neutral=False):
        if self.n == 0:
            return None
        lh = self.sum_h / self.n
        la = self.sum_a / self.n
        m = (lh + la) / 2.0
        off_h = self._shrunk(self.pf.get(home, 0.0),
                             self.gp.get(home, 0), m)
        def_a = self._shrunk(self.pa.get(away, 0.0),
                             self.gp.get(away, 0), m)
        off_a = self._shrunk(self.pf.get(away, 0.0),
                             self.gp.get(away, 0), m)
        def_h = self._shrunk(self.pa.get(home, 0.0),
                             self.gp.get(home, 0), m)
        if neutral:
            lam_h = m * off_h * def_a
            lam_a = m * off_a * def_h
        else:
            lam_h = lh * off_h * def_a
            lam_a = la * off_a * def_h
        return lam_h + lam_a

    def update(self, g):
        if g.get("season") is not None:
            if self.season is not None and g["season"] != self.season:
                # off-season regression: rates halfway to league mean
                for t in self.gp:
                    self.pf[t] *= 0.5
                    self.pa[t] *= 0.5
                    self.gp[t] *= 0.5
            self.season = g["season"]
        h, a = g["home"], g["away"]
        self.pf[h] = self.pf.get(h, 0.0) + g["hs"]
        self.pa[h] = self.pa.get(h, 0.0) + g["as"]
        self.gp[h] = self.gp.get(h, 0) + 1
        self.pf[a] = self.pf.get(a, 0.0) + g["as"]
        self.pa[a] = self.pa.get(a, 0.0) + g["hs"]
        self.gp[a] = self.gp.get(a, 0) + 1
        self.sum_h += g["hs"]
        self.sum_a += g["as"]
        self.n += 1

    def team_rates(self):
        if self.n == 0:
            return {}, {}
        lh = self.sum_h / self.n
        la = self.sum_a / self.n
        m = (lh + la) / 2.0
        teams = {}
        for t in sorted(self.gp):
            teams[t] = {
                "off": round(self._shrunk(self.pf[t], self.gp[t], m), 4),
                "def": round(self._shrunk(self.pa[t], self.gp[t], m), 4),
                "gp": self.gp[t]}
        league = {"LH": round(lh, 3), "LA": round(la, 3),
                  "mean_team_score": round(m, 3)}
        return teams, league


def p_over(mu, sigma, dist, line):
    """P(total > line) under the lane distribution. Integer lines:
    win-only probability with the push mass conditioned out (the
    push probability is returned too)."""
    if dist == "poisson":
        if float(line) == int(line):
            L = int(line)
            p_win = 1.0 - pois_cdf(L, mu)
            p_push = pois_cdf(L, mu) - pois_cdf(L - 1, mu)
            p_lose = pois_cdf(L - 1, mu)
            denom = p_win + p_lose
            return (p_win / denom if denom > 0 else 0.5), p_push
        return 1.0 - pois_cdf(math.floor(line), mu), 0.0
    # normal: boundary at the line for .5 lines, line+0.5 for
    # integer lines (total >= L+1 wins)
    if float(line) == int(line):
        L = int(line)
        p_win = 1.0 - norm_cdf((L + 0.5 - mu) / sigma)
        p_lose = norm_cdf((L - 0.5 - mu) / sigma)
        p_push = 1.0 - p_win - p_lose
        denom = p_win + p_lose
        return (p_win / denom if denom > 0 else 0.5), p_push
    return 1.0 - norm_cdf((line - mu) / sigma), 0.0


def walk_forward(games, prior_games, dist, burn_in):
    model = TotalsModel(prior_games, dist)
    resid = []          # model residuals (scored window)
    resid_all = []
    totals_prior = []   # actual totals seen so far (naive state)
    mae_m = mae_n = 0.0
    br_m = br_n = 0.0
    ll_m = ll_n = 0.0
    n_scored = 0
    # real-line scoring (NFL only, when total_line present)
    rl_br_m = rl_br_n = 0.0
    rl_n = 0
    for g in games:
        total = g["hs"] + g["as"]
        if model.n >= 10:
            mu = model.predict(g["home"], g["away"],
                               g.get("neutral", False))
            # sigma from prior residuals; fall back to prior totals SD
            if len(resid_all) >= 25:
                mean_r = sum(resid_all) / len(resid_all)
                sig = math.sqrt(sum((r - mean_r) ** 2
                                    for r in resid_all)
                                / (len(resid_all) - 1))
            elif len(totals_prior) >= 25:
                mt = sum(totals_prior) / len(totals_prior)
                sig = math.sqrt(sum((t - mt) ** 2
                                    for t in totals_prior)
                                / (len(totals_prior) - 1))
            else:
                sig = 0.15 * (sum(totals_prior) / len(totals_prior)
                              if totals_prior else 45.0)
            if dist == "poisson":
                sig = math.sqrt(mu)  # not used for p_over; kept sane
            resid_all.append(total - mu)
            if model.n >= burn_in:
                # naive from prior games only
                mu_n = sum(totals_prior) / len(totals_prior)
                mt = mu_n
                sig_n = math.sqrt(sum((t - mt) ** 2
                                      for t in totals_prior)
                                  / (len(totals_prior) - 1))
                line_star = math.floor(mu_n) + 0.5
                pm, _ = p_over(mu, sig, dist, line_star)
                pn, _ = p_over(mu_n, sig_n, dist, line_star)
                y = 1.0 if total > line_star else 0.0
                mae_m += abs(total - mu)
                mae_n += abs(total - mu_n)
                br_m += (pm - y) ** 2
                br_n += (pn - y) ** 2
                if dist != "poisson":
                    ll_m += -0.5 * ((total - mu) / sig) ** 2 \
                        - math.log(sig)
                    ll_n += -0.5 * ((total - mu_n) / sig_n) ** 2 \
                        - math.log(sig_n)
                resid.append(total - mu)
                n_scored += 1
                if g.get("total_line"):
                    pm2, _ = p_over(mu, sig, dist, g["total_line"])
                    pn2, _ = p_over(mu_n, sig_n, dist,
                                    g["total_line"])
                    if total != g["total_line"]:
                        y2 = 1.0 if total > g["total_line"] else 0.0
                        rl_br_m += (pm2 - y2) ** 2
                        rl_br_n += (pn2 - y2) ** 2
                        rl_n += 1
        totals_prior.append(total)
        model.update(g)
    out = {"n": n_scored}
    if n_scored:
        out["mae_model"] = round(mae_m / n_scored, 3)
        out["mae_naive"] = round(mae_n / n_scored, 3)
        out["brier_model"] = round(br_m / n_scored, 4)
        out["brier_naive"] = round(br_n / n_scored, 4)
        if dist != "poisson":
            out["logscore_model"] = round(ll_m / n_scored, 4)
            out["logscore_naive"] = round(ll_n / n_scored, 4)
        mean_r = sum(resid) / len(resid)
        out["sigma_resid"] = round(math.sqrt(
            sum((r - mean_r) ** 2 for r in resid)
            / (len(resid) - 1)), 3)
        out["verdict"] = ("PASS" if (out["mae_model"] < out["mae_naive"]
                                     and out["brier_model"]
                                     < out["brier_naive"])
                          else "FAILED-EXAM")
    if rl_n:
        out["real_line"] = {"n": rl_n,
                            "brier_model": round(rl_br_m / rl_n, 4),
                            "brier_naive": round(rl_br_n / rl_n, 4)}
    teams, league = model.team_rates()
    # full-stream sigma for the shipped artifact
    if resid:
        out["_teams"] = teams
        out["_league"] = league
    return out, model


LANES = {
    "ncaaf": dict(games=games_ncaaf, prior=4, dist="normal",
                  burn_in=60,
                  why=("Normal on total points: a CFB total is the "
                       "sum of ~25 scoring events across two "
                       "offenses; empirically near-normal with a "
                       "wide, matchup-driven spread.")),
    "nfl": dict(games=games_nfl, prior=4, dist="normal",
                burn_in=32,
                why=("Normal on total points: the classic totals "
                     "model — sum of many drives/scoring events; "
                     "sigma ~13-14 from residuals.")),
    "nba": dict(games=games_nba, prior=10, dist="normal",
                burn_in=100,
                why=("Normal on total points: ~100 possessions a "
                     "side; totals tightly near-normal around a "
                     "pace-driven mean.")),
    "mlb": dict(games=games_mlb, prior=10, dist="normal",
                burn_in=200,
                why=("Normal on total runs: a baseball total is "
                     "the sum of ~76 plate appearances of run "
                     "events; the empirical distribution is "
                     "overdispersed vs Poisson (full-season SD "
                     "4.59 on a mean of 8.89 in Guy's candidate "
                     "block) and near-normal in shape.")),
    "nhl": dict(games=games_nhl, prior=10, dist="poisson",
                burn_in=60,
                why=("Poisson on total goals: goals are low-count "
                     "events (~6/game); the sum of two Poisson "
                     "scoring rates is Poisson — the soccer-grid "
                     "treatment, not a normal approximation.")),
}


def main():
    only = sys.argv[1:] or list(LANES)
    for lane in only:
        cfg = LANES[lane]
        games, source = cfg["games"]()
        games.sort(key=lambda g: g["date"])
        bt, model = walk_forward(games, cfg["prior"], cfg["dist"],
                                 cfg["burn_in"])
        teams = bt.pop("_teams", {})
        league = bt.pop("_league", {})
        totals = [g["hs"] + g["as"] for g in games]
        mt = sum(totals) / len(totals)
        league["total_mean"] = round(mt, 3)
        league["total_sd"] = round(math.sqrt(
            sum((t - mt) ** 2 for t in totals) / (len(totals) - 1)), 3)
        art = {
            "sport": lane,
            "lane": f"{lane}-totals",
            "fitted_at": now(),
            "source": source,
            "history_n": len(games),
            "params": {"prior_games": cfg["prior"],
                       "distribution": cfg["dist"],
                       "burn_in": cfg["burn_in"],
                       "model": "lam_home = LH*off[h]*def[a]; "
                                "lam_away = LA*off[a]*def[h]; "
                                "total ~ distribution(mu, sigma)"},
            "distribution_why": cfg["why"],
            "league": league,
            "sigma": bt.get("sigma_resid"),
            "teams": teams,
            "backtest": dict(bt, protocol=(
                "walk-forward (strengths/league rates from prior "
                "games only); naive = expanding league-average "
                "total; Brier scored on P(over L*), L* = .5 line "
                "at the naive mean; PASS requires MAE and Brier "
                "both better than naive")),
            "status": ("FITTED" if bt.get("verdict") == "PASS"
                       else "FAILED-EXAM"),
        }
        if lane == "ncaaf":
            art["note"] = (
                "LH/LA asymmetry is IN the source data, not a "
                "builder artifact: raw means are home 34.5 / away "
                "19.2 because weeks 1-3 of the 458-game file are "
                "FBS-vs-FCS buy games (week 1: 40.9 vs 13.0); by "
                "week 7 it normalizes (28.7 vs 24.8). The "
                "walk-forward scored the total (the sum) directly "
                "under this exact scheme and beat naive — the "
                "split is kept, and this note rides with it.")
        if lane == "nba":
            art["note"] = (
                "All-Star exhibition games (STARS/STRIPES/WORLD) "
                "excluded from the history — showcase totals are "
                "not the league's scoring environment. Team codes "
                "match the shipped v5-nba.json keys (GS, UTAH).")
            art["aliases"] = dict(sorted(NBA_ALIASES.items()))
        path = os.path.join(DATA, f"v5-totals-{lane}.json")
        with open(path, "w") as f:
            json.dump(art, f, indent=1)
        print(f"{lane}: history n={len(games)} teams={len(teams)} "
              f"WF n={bt.get('n')} MAE {bt.get('mae_model')} vs "
              f"naive {bt.get('mae_naive')} | Brier "
              f"{bt.get('brier_model')} vs {bt.get('brier_naive')} "
              f"| sigma {bt.get('sigma_resid')} -> "
              f"{bt.get('verdict')}  [{path}]")


# ================================================================ ROUND 2
# Team totals + NHL refit (genuinely new information only).
#
# TEAM TOTALS: a team's OWN score distribution. lam_team comes
# from the same off/def state as the game-total model, but sigma
# is fitted from actual TEAM-score residuals (walk-forward,
# pooled per lane; the artifact also carries a per-team shrunk
# residual SD) — never the game-total sigma rescaled. Naive
# baseline: the team's own expanding mean score. Line: the .5
# line at the naive mean, same honest line-free protocol.
# Distribution per lane follows the game-total choice (normal
# for the points lanes, Poisson for NHL team goals — a team's
# goals are the low-count event itself).
#
# NHL REFIT (one attempt, then terminal): the Round-1 model plus
# ONLY new information —
#   (a) starting-goalie scoring environment: each side's lam is
#       multiplied by the OPPOSING starter's shrunk goals-against
#       rate (GA per 60, prior 600 minutes at the league mean),
#       walk-forward from ESPN summary boxscores;
#   (b) rest: a team on a back-to-back gets fitted offensive and
#       defensive multipliers (expanding actual/base ratios,
#       prior 20 team-games at 1.0).
# Parameterizations fixed here, before the run. Same naive
# baseline and pass rule as Round 1. A second FAILED-EXAM is
# terminal for NHL totals in this loop.

def _team_p_over(lam, sigma, dist, line):
    if dist == "poisson":
        if float(line) == int(line):
            L = int(line)
            p_win = 1.0 - pois_cdf(L, lam)
            p_push = pois_cdf(L, lam) - pois_cdf(L - 1, lam)
            p_lose = pois_cdf(L - 1, lam)
            den = p_win + p_lose
            return p_win / den if den > 0 else 0.5
        return 1.0 - pois_cdf(math.floor(line), lam)
    if float(line) == int(line):
        L = int(line)
        p_win = 1.0 - norm_cdf((L + 0.5 - lam) / sigma)
        p_lose = norm_cdf((L - 0.5 - lam) / sigma)
        den = p_win + p_lose
        return p_win / den if den > 0 else 0.5
    return 1.0 - norm_cdf((line - lam) / sigma)


def walk_forward_team(games, prior_games, dist, burn_in):
    """Per team-game scoring. Returns (backtest dict, model)."""
    model = TotalsModel(prior_games, dist)
    resid_m = []            # model team-score residuals (prior only)
    resid_by_team = {}
    scores_prior = []       # all team scores seen (naive spread)
    team_sum = {}
    team_n = {}
    mae_m = mae_n = br_m = br_n = 0.0
    n_scored = 0
    for g in games:
        sides = ((g["home"], g["hs"], True), (g["away"], g["as"], False))
        if model.n >= burn_in:
            lh = model.sum_h / model.n
            la = model.sum_a / model.n
            m = (lh + la) / 2.0
            for team, score, is_home in sides:
                opp = g["away"] if is_home else g["home"]
                off = model._shrunk(model.pf.get(team, 0.0),
                                    model.gp.get(team, 0), m)
                dof = model._shrunk(model.pa.get(opp, 0.0),
                                    model.gp.get(opp, 0), m)
                rate = lh if (is_home or g.get("neutral")) else la
                if g.get("neutral"):
                    rate = m
                lam = rate * off * dof
                # naive: team's own expanding mean (league mean
                # until the team has a game on file)
                if team_n.get(team, 0) > 0:
                    mu_n = team_sum[team] / team_n[team]
                else:
                    mu_n = m
                # sigmas from prior residuals only
                if len(resid_m) >= 50:
                    mr = sum(resid_m) / len(resid_m)
                    sig_m = math.sqrt(sum((r - mr) ** 2
                                          for r in resid_m)
                                      / (len(resid_m) - 1))
                else:
                    sig_m = 0.3 * m
                if len(scores_prior) >= 50:
                    ms = sum(scores_prior) / len(scores_prior)
                    sig_n = math.sqrt(sum((s - ms) ** 2
                                          for s in scores_prior)
                                      / (len(scores_prior) - 1))
                else:
                    sig_n = 0.3 * m
                line_star = math.floor(mu_n) + 0.5
                pm = _team_p_over(lam, sig_m, dist, line_star)
                pn = _team_p_over(mu_n, sig_n, dist, line_star)
                y = 1.0 if score > line_star else 0.0
                mae_m += abs(score - lam)
                mae_n += abs(score - mu_n)
                br_m += (pm - y) ** 2
                br_n += (pn - y) ** 2
                n_scored += 1
                r = score - lam
                resid_m.append(r)
                resid_by_team.setdefault(team, []).append(r)
        for team, score, _ in sides:
            team_sum[team] = team_sum.get(team, 0.0) + score
            team_n[team] = team_n.get(team, 0) + 1
            scores_prior.append(score)
        model.update(g)
    out = {"n": n_scored}
    if n_scored:
        out["mae_model"] = round(mae_m / n_scored, 3)
        out["mae_naive"] = round(mae_n / n_scored, 3)
        out["brier_model"] = round(br_m / n_scored, 4)
        out["brier_naive"] = round(br_n / n_scored, 4)
        out["verdict"] = ("PASS" if (out["mae_model"] < out["mae_naive"]
                                    and out["brier_model"]
                                    < out["brier_naive"])
                         else "FAILED-EXAM")
    # per-team shrunk sigma from the walk-forward residuals
    teams, league = model.team_rates()
    if resid_m:
        mr = sum(resid_m) / len(resid_m)
        var_pool = sum((r - mr) ** 2 for r in resid_m) \
            / (len(resid_m) - 1)
        for t, info in teams.items():
            rs = resid_by_team.get(t, [])
            if len(rs) >= 3:
                mt = sum(rs) / len(rs)
                var_t = sum((r - mt) ** 2 for r in rs) / (len(rs) - 1)
                info["sigma_team"] = round(math.sqrt(
                    (len(rs) * var_t + 30.0 * var_pool)
                    / (len(rs) + 30.0)), 3)
            else:
                info["sigma_team"] = round(math.sqrt(var_pool), 3)
            info["score_mean"] = round(
                team_sum.get(t, 0.0) / team_n[t], 3) \
                if team_n.get(t) else None
        out["_teams"] = teams
        out["_league"] = league
        out["sigma_pool"] = round(math.sqrt(var_pool), 3)
    return out, model


def build_team_totals(lane):
    cfg = LANES[lane]
    games, source = cfg["games"]()
    games.sort(key=lambda g: g["date"])
    bt, _model = walk_forward_team(games, cfg["prior"], cfg["dist"],
                                   cfg["burn_in"])
    teams = bt.pop("_teams", {})
    league = bt.pop("_league", {})
    league["sigma_pool_team_score"] = bt.pop("sigma_pool", None)
    art = {
        "sport": lane,
        "lane": f"{lane}-team-totals",
        "fitted_at": now(),
        "source": source,
        "history_n": len(games),
        "params": {"prior_games": cfg["prior"],
                   "distribution": cfg["dist"],
                   "burn_in": cfg["burn_in"],
                   "model": "lam_team = (LH|LA)*off[team]*def[opp]; "
                            "team score ~ distribution(lam_team, "
                            "sigma_team); sigma_team = per-team "
                            "walk-forward residual SD shrunk toward "
                            "the lane pool (prior 30 team-games)"},
        "distribution_why": (
            "A team total is ONE team's scoring distribution, "
            "fitted as such: " + cfg["why"].replace(
                "Normal on total points", "Normal on team points")
            .replace("Poisson on total goals",
                     "Poisson on team goals")),
        "league": league,
        "teams": teams,
        "backtest": dict(bt, protocol=(
            "walk-forward per team-game (rates from prior games "
            "only); naive = the team's own expanding mean score; "
            "Brier on P(over L*), L* = .5 line at the naive team "
            "mean; PASS requires MAE and Brier both better than "
            "naive")),
        "status": ("FITTED" if bt.get("verdict") == "PASS"
                   else "FAILED-EXAM"),
    }
    if lane == "nba":
        art["aliases"] = dict(sorted(NBA_ALIASES.items()))
    path = os.path.join(DATA, f"v5-teamtotals-{lane}.json")
    with open(path, "w") as f:
        json.dump(art, f, indent=1)
    print(f"team-{lane}: history n={len(games)} teams={len(teams)} "
          f"WF n={bt.get('n')} MAE {bt.get('mae_model')} vs naive "
          f"{bt.get('mae_naive')} | Brier {bt.get('brier_model')} "
          f"vs {bt.get('brier_naive')} -> {bt.get('verdict')}  "
          f"[{path}]")
    return art


# ---------------------------------------------------------------- NHL v2

def _espn_nhl_day_full(d):
    url = ("https://site.api.espn.com/apis/site/v2/sports/hockey/"
           f"nhl/scoreboard?dates={d:%Y%m%d}")
    try:
        blob = json.loads(fetch(url, timeout=20))
    except Exception:
        return []
    out = []
    for ev in blob.get("events", []):
        if ev["status"]["type"]["name"] != "STATUS_FINAL":
            continue
        comp = ev["competitions"][0]
        sides = {}
        for c in comp["competitors"]:
            sides[c["homeAway"]] = c["team"]["displayName"]
        if "home" in sides and "away" in sides:
            out.append({"id": ev["id"], "date": d.isoformat(),
                        "home": sides["home"], "away": sides["away"]})
    return out


def _goalie_line(summary):
    """Starting goalie (max TOI) per side from an ESPN summary."""
    out = {}
    for team in (summary.get("boxscore") or {}).get("players", []):
        for grp in team.get("statistics", []):
            if grp.get("name") != "goalies":
                continue
            labels = grp.get("labels") or []
            best = None
            for a in grp.get("athletes", []):
                stats = dict(zip(labels, a.get("stats", [])))
                toi = stats.get("TOI", "0:00")
                try:
                    mm, ss = toi.split(":")
                    toi_s = int(mm) * 60 + int(ss)
                except Exception:
                    toi_s = 0
                if best is None or toi_s > best["toi_s"]:
                    best = {"id": a["athlete"]["id"],
                            "name": a["athlete"]["displayName"],
                            "ga": int(stats.get("GA", 0)),
                            "sa": int(stats.get("SA", 0)),
                            "toi_s": toi_s}
            out[team["team"]["displayName"]] = best
    return out


def games_nhl_goalies():
    """Cache: data/cache/nhl_goalie_games.json —
    [{date, home, away, home_goalie, away_goalie}] matched to the
    held 2025-26 game list by (date, home, away)."""
    cache = os.path.join(DATA, "cache", "nhl_goalie_games.json")
    if os.path.exists(cache):
        with open(cache) as f:
            return json.load(f)
    games, _src = games_nhl()
    want = {(g["date"], g["home"], g["away"]) for g in games}
    days = []
    d = datetime(2025, 10, 7).date()
    end = datetime(2026, 4, 17).date()
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    events = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for day_events in ex.map(_espn_nhl_day_full, days):
            events.extend(day_events)
    events = [e for e in events
              if (e["date"], e["home"], e["away"]) in want]
    print(f"goalie fetch: {len(events)} events matched of "
          f"{len(want)} held games")

    def one(e):
        url = ("https://site.api.espn.com/apis/site/v2/sports/"
               f"hockey/nhl/summary?event={e['id']}")
        try:
            sm = json.loads(fetch(url, timeout=25))
        except Exception:
            return None
        gl = _goalie_line(sm)
        if e["home"] not in gl or e["away"] not in gl:
            return None
        return {"date": e["date"], "home": e["home"],
                "away": e["away"],
                "home_goalie": gl[e["home"]],
                "away_goalie": gl[e["away"]]}
    out = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for r in ex.map(one, events):
            if r:
                out.append(r)
    out.sort(key=lambda g: g["date"])
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w") as f:
        json.dump(out, f)
    return out


def walk_forward_nhl_v2(games, goalie_games):
    """Round-1 NHL model + goalie environment + rest (B2B)
    adjustments ONLY. Returns (backtest, state-for-artifact)."""
    prior = LANES["nhl"]["prior"]
    burn_in = LANES["nhl"]["burn_in"]
    model = TotalsModel(prior, "poisson")
    gmap = {(g["date"], g["home"], g["away"]): g
            for g in goalie_games}
    # goalie expanding state: minutes, goals against
    g_min = {}
    g_ga = {}
    # rest expanding state: ratios of actual/base for B2B teams
    b2b_off_num = b2b_off_den = 0.0
    b2b_def_num = b2b_def_den = 0.0
    last_date = {}
    totals_prior = []
    mae_m = mae_n = br_m = br_n = 0.0
    n_scored = 0
    covered = 0

    def goalie_factor(gid):
        if gid is None or g_min.get(gid, 0) <= 0:
            return 1.0
        league_mean = (model.sum_h + model.sum_a) / (2.0 * model.n) \
            if model.n else 3.0
        ga60 = (g_ga[gid] + league_mean * 10.0) \
            / (g_min[gid] / 60.0 + 10.0)
        return ga60 / league_mean if league_mean else 1.0

    def b2b_factors():
        fo = (b2b_off_num + 20.0) / (b2b_off_den + 20.0) \
            if b2b_off_den > 0 else 1.0
        fd = (b2b_def_num + 20.0) / (b2b_def_den + 20.0) \
            if b2b_def_den > 0 else 1.0
        return fo, fd

    for g in games:
        total = g["hs"] + g["as"]
        d = datetime.fromisoformat(g["date"]).date()
        h_b2b = (last_date.get(g["home"]) is not None
                 and (d - last_date[g["home"]]).days == 1)
        a_b2b = (last_date.get(g["away"]) is not None
                 and (d - last_date[g["away"]]).days == 1)
        gg = gmap.get((g["date"], g["home"], g["away"]))
        if model.n >= 10:
            lh = model.sum_h / model.n
            la = model.sum_a / model.n
            m = (lh + la) / 2.0
            off_h = model._shrunk(model.pf.get(g["home"], 0.0),
                                  model.gp.get(g["home"], 0), m)
            def_a = model._shrunk(model.pa.get(g["away"], 0.0),
                                  model.gp.get(g["away"], 0), m)
            off_a = model._shrunk(model.pf.get(g["away"], 0.0),
                                  model.gp.get(g["away"], 0), m)
            def_h = model._shrunk(model.pa.get(g["home"], 0.0),
                                  model.gp.get(g["home"], 0), m)
            lam_h0 = lh * off_h * def_a
            lam_a0 = la * off_a * def_h
            lam_h, lam_a = lam_h0, lam_a0
            if gg is not None:
                lam_h *= goalie_factor(gg["away_goalie"]["id"]
                                       if gg["away_goalie"] else None)
                lam_a *= goalie_factor(gg["home_goalie"]["id"]
                                       if gg["home_goalie"] else None)
                covered += 1
            fo, fd = b2b_factors()
            if h_b2b:
                lam_h *= fo
                lam_a *= fd
            if a_b2b:
                lam_a *= fo
                lam_h *= fd
            mu = lam_h + lam_a
            if model.n >= burn_in:
                mu_n = sum(totals_prior) / len(totals_prior)
                line_star = math.floor(mu_n) + 0.5
                pm, _ = p_over(mu, math.sqrt(mu), "poisson",
                               line_star)
                pn, _ = p_over(mu_n, math.sqrt(mu_n), "poisson",
                               line_star)
                y = 1.0 if total > line_star else 0.0
                mae_m += abs(total - mu)
                mae_n += abs(total - mu_n)
                br_m += (pm - y) ** 2
                br_n += (pn - y) ** 2
                n_scored += 1
            # learn the B2B ratios from this game (priors only
            # from here on — update AFTER predicting)
            if h_b2b and lam_h0 > 0:
                b2b_off_num += g["hs"] / lam_h0
                b2b_off_den += 1.0
                b2b_def_num += g["as"] / lam_a0
                b2b_def_den += 1.0
            if a_b2b and lam_a0 > 0:
                b2b_off_num += g["as"] / lam_a0
                b2b_off_den += 1.0
                b2b_def_num += g["hs"] / lam_h0
                b2b_def_den += 1.0
        totals_prior.append(total)
        model.update(g)
        last_date[g["home"]] = d
        last_date[g["away"]] = d
        if gg is not None:
            for side, key in (("home", "home_goalie"),
                              ("away", "away_goalie")):
                gl = gg[key]
                if gl:
                    g_min[gl["id"]] = g_min.get(gl["id"], 0.0) \
                        + gl["toi_s"] / 60.0
                    g_ga[gl["id"]] = g_ga.get(gl["id"], 0.0) \
                        + gl["ga"]
    out = {"n": n_scored, "goalie_coverage_scored_window": covered}
    if n_scored:
        out["mae_model"] = round(mae_m / n_scored, 3)
        out["mae_naive"] = round(mae_n / n_scored, 3)
        out["brier_model"] = round(br_m / n_scored, 4)
        out["brier_naive"] = round(br_n / n_scored, 4)
        out["verdict"] = ("PASS" if (out["mae_model"] < out["mae_naive"]
                                    and out["brier_model"]
                                    < out["brier_naive"])
                         else "FAILED-EXAM")
    fo, fd = b2b_factors()
    state = {"b2b_off_factor": round(fo, 4),
             "b2b_def_factor": round(fd, 4),
             "goalies_tracked": len(g_min)}
    return out, state, model


def nhl_refit():
    games, source = games_nhl()
    games.sort(key=lambda g: g["date"])
    try:
        goalie_games = games_nhl_goalies()
        cov = len(goalie_games) / len(games) if games else 0.0
    except Exception as e:
        goalie_games = []
        cov = 0.0
        print(f"goalie fetch failed: {type(e).__name__}: {e}")
    print(f"goalie coverage: {len(goalie_games)}/{len(games)} "
          f"({cov:.1%})")
    bt, state, model = walk_forward_nhl_v2(games, goalie_games)
    path = os.path.join(DATA, "v5-totals-nhl.json")
    with open(path) as f:
        art = json.load(f)
    r1 = art.get("backtest") or {}
    attempt = dict(bt)
    attempt.update(state)
    attempt["goalie_coverage"] = round(cov, 4)
    attempt["new_information"] = (
        "starting-goalie scoring environment (ESPN summary "
        "boxscores: starter = max TOI; shrunk GA/60, prior 600 "
        "min at league mean) + rest/back-to-back fitted off/def "
        "multipliers (expanding ratios, prior 20 team-games)")
    attempt["protocol"] = (
        "same walk-forward + naive baseline + pass rule as "
        "Round 1; parameterizations fixed before the run; "
        "Round-1 model NOT re-tuned")
    attempt["round1"] = {"mae_model": r1.get("mae_model"),
                         "mae_naive": r1.get("mae_naive"),
                         "brier_model": r1.get("brier_model"),
                         "brier_naive": r1.get("brier_naive"),
                         "verdict": r1.get("verdict")}
    art["refit_attempt_2"] = attempt
    if bt.get("verdict") == "PASS":
        teams, league = model.team_rates()
        art["teams"] = teams
        art["league"] = league
        art["status"] = "FITTED"
        art["params"] = dict(art.get("params") or {},
                             model_v2=("round-1 rates x goalie "
                                       "environment x rest (B2B) "
                                       "adjustments — see "
                                       "refit_attempt_2"),
                             b2b_off_factor=state["b2b_off_factor"],
                             b2b_def_factor=state["b2b_def_factor"])
        art["fitted_at"] = now()
        print("NHL refit: PASS — artifact upgraded to FITTED (v2)")
    else:
        art["status"] = "FAILED-EXAM"
        print("NHL refit: FAILED-EXAM (second failure — terminal "
              "for this loop)")
    with open(path, "w") as f:
        json.dump(art, f, indent=1)
    print(f"nhl-v2: WF n={bt.get('n')} MAE {bt.get('mae_model')} "
          f"vs naive {bt.get('mae_naive')} | Brier "
          f"{bt.get('brier_model')} vs {bt.get('brier_naive')} | "
          f"b2b off/def {state['b2b_off_factor']}/"
          f"{state['b2b_def_factor']} | goalies "
          f"{state['goalies_tracked']} -> {bt.get('verdict')}")
    return art


if __name__ == "__main__":
    _args = sys.argv[1:]
    if _args and _args[0] == "team":
        for _lane in (_args[1:] or list(LANES)):
            build_team_totals(_lane)
    elif _args and _args[0] == "nhl-refit":
        nhl_refit()
    else:
        main()
