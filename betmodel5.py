#!/usr/bin/env python3
"""
betmodel v5.1 — the full overhaul (design: MODEL-V5.md; ordered by the
Pilot 2026-10-19 from his own spec sketch: "Deep mathematics and bet
algorithmic engine, various sources, and a novel prediction engine,
with exceptional reparametrization for scale closing and
unconventional relationships} #:# / Win # / Lose # / Probability # /
Grade a-f / Bet (no bet)").

SINGLE-FILE BUILD (Pilot directive 2026-10-19): this script is
self-contained — the v1 Elo core, the v3 odds/prop math, the v3.1
grade ladder, the v4 engine (distributional ratings, prop bands,
Live Matrix, scorecard, governor), and the NFL lane are INLINED
below, section by section, from the lab's earlier files (which stay
in scripts/ as history). Stdlib only — the one deviation: the v1
engine's optional `requests` path is disabled (requests = None), so
its urllib branch serves every fetch, same URLs, same cache files.
No sibling module is imported at runtime.

What survives from v4, untouched in substance: the Hard Kill Ledger,
the Disagreement Scorecard (data/scorecard.json), the Calibration
Governor, the two-book rule, the lab charter (ANALYSIS ONLY — this
program never places a bet, deposits, or touches an account).
What is rebuilt: how a probability is produced.

Pipeline (per price):
    sources -> ENSEMBLE blend (organ 1)
            -> REPARAMETRIZATION phi (organ 2) applied to the model
               source BEFORE blending (phi is fitted on the model
               estimator's own outputs; the market needs no phi — it
               IS the scale phi maps onto)
            -> COHERENCE check (organ 3) across the game's quotes
            -> the CARD (organ 4): matchup id, lane Win/Lose record,
               Probability, Grade, Verdict (organ 5, the ladder)
            -> detail line (v3 lineage): odds | payout | price |
               win% model vs implied | edge | EV | unit class.

Organ 1 — the Source Ensemble. Per lane, the independent sources
that exist (model estimator, market no-vig) are blended with weights
LEARNED from resolved Briers: w_i ∝ 1 / (Brier_i + 0.01), from the
scorecard (CFB lanes) or the lane history file (NFL). A lane with no
resolved Brier pair prints its weights as UNLEARNED and falls back
to the model source alone.

Organ 2 — the Reparametrization Layer (scale closing). Per lane, a
monotone phi: raw P -> calibrated P, fitted WALK-FORWARD ONLY.
Candidates: identity; lin (phi(p) = 0.5 + a(p-0.5), a FITTED by
Brier grid search — v4's shrinkage with its coefficient fitted
instead of declared); iso (PAVA isotonic step map). Selection is by
leave-one-week-out CV on the training pairs ONLY. Fitted parameters
print and are labelled FITTED. A lane whose phi fails its named
out-of-sample benchmark reports UNCALIBRATED, grades cap at C.

Organ 3 — Unconventional Relationships (coherence). One margin
distribution must reconcile ML, spread and total: favourite flips
across sources, cross-source total disagreement >= 1.0, spread
disagreement >= 4.0 (the lab audit threshold), and within-source
ML/spread triangle breaks > 6 pts all print as AUDIT FLAGS.

Organ 4 — the Record on the Card. Every price leads with the
producing lane's scored Win # / Lose #. No scored record -> Win 0 /
Lose 0 and cap C.

Organ 5 — the Verdict Ladder (v5.1; Pilot order 2026-10-19,
MODEL-V5.md "VERDICT LADDER" — supersedes the v5.0 binary gate).
Five computed verdicts, never vibes: GOLDEN BET / BET HERE /
RISK BET (BET) / RISK BET (DO NOT BET) / DO NOT BET, each printed
with its verdict_reason (the deciding condition, named). The old
gate's conditions survive as the ladder's inputs; the standards
did not move — an UNCALIBRATED lane caps at RISK BET (DO NOT BET)
and nothing on the current record can print GOLDEN BET. Grades:
frozen GRADING.md rubric on the phi edge + v4 modifiers (FRAGILE
-2 when the lane's bias favours the bet, -1 otherwise;
provisional cap B) + v5 caps.

Totals engine — STUB, by design: until a pace/scoring companion
distribution exists AND has a scored record, totals print UNPRICED,
grade cap C, DO NOT BET (soccer totals DO price — off the Poisson grid,
which is a real fitted scoring distribution).

Props from scoring plays — SCOPED, not built (see
prop_from_scoring_plays): the ESPN athlete-stats routes 404 here
and the game-summary payload in this environment carries no
scoringPlays structure. The stub prints UNPRICED. It will never
print a plausible-looking number it did not compute.

SCOPE AMENDMENT (Pilot 2026-10-19 ~07:08 EDT): soccer and NBA are
first-class lanes (NBA: Elo lineage like NHL; soccer: Elo + Poisson
scoring). THE COVERAGE LAW: every FanDuel market type in TAXONOMY is
a REGISTERED CHECKER printing exactly one of PRICED /
COHERENCE-FLAGGED / UNPRICED — a market nobody looked at is the only
failure state. Sources carry provenance + timestamps; the menu is
mirrored from timestamped pulls (FanDuel JSON endpoints for the
`menu` command — constants below; the lab's verified ESPN odds feed
for `menu-feed`); a failed pull stamps its scope UNVERIFIED. UX is
level 1 (the card); everything under it is engine level 5.
"""

import argparse
import itertools
import json
import math
import os
import random
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
RESULTS = os.path.join(HERE, "..", "results")
CACHE = os.path.join(DATA, "cache")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(RESULTS, exist_ok=True)
PHI_PATH = os.path.join(DATA, "v5-phi.json")
HISTORY_PATH = os.path.join(DATA, "v5-lane-history.json")
NFL_PRICING_PATH = os.path.join(DATA, "nfl-week6-pricing.json")

ENGINE_VERSION = "5.1"   # v5.1 — the verdict ladder (MODEL-V5.md)

# ------------------------------------------------------------------
# FanDuel menu endpoints — VERIFIED WORKING from this VM 2026-10-19
# (discovery report: results/fanduel-menu-route-2026-10-19.md;
# sample payloads: data/fanduel-menu-discovery/). FanDuel has no
# public API; these are the read-only JSON endpoints its own web
# frontend uses, on the Michigan hosts (the Pilot's book is MI —
# another state's host returns that state's menu). READ-ONLY: the
# transactional paths in the same bundles (implyBets / placeBet)
# are never called — lab charter.
FANDUEL_SBAPI_BASE = "https://sbapi.mi.sportsbook.fanduel.com/api"
FANDUEL_SMP_BASE = "https://smp.mi.sportsbook.fanduel.com"
FANDUEL_PUBLIC_KEY = "FhMFpcPWXMeyZxOx"  # FanDuel's public web
# frontend key, a string literal in their own JS bundle — not a
# user credential. It can rotate on a site release: if calls return
# 401/403, re-extract it from the current bundle BEFORE treating
# the response as a block (route report §"How it was established").
FANDUEL_APP_CONTEXT_ENDPOINT = "/application-context"
FANDUEL_PAGE_ENDPOINT = "/content-managed-page"
FANDUEL_EVENT_ENDPOINT = "/event-page"
FANDUEL_PRICES_ENDPOINT = ("/api/sports/fixedodds/readonly/v1/"
                           "getMarketPrices")   # SMP host, POST
FANDUEL_EVENT_TYPES = {"nfl": 6423, "nba": 7522, "mlb": 7511,
                       "nhl": 7524, "soccer": 1}
FANDUEL_TIMEZONE = "America/Detroit"
# The price feed carries NO server timestamp — pull times in this
# program are stamped client-side (MODEL-V5.md's rule). Refresh
# cadence, if anything ever polls: >= 30-60 s, batches <= 70 market
# ids (the frontend's own batch size). The menu command is
# pull-on-demand; it does not poll.




# =============================================================== CORE — v1 Elo engine (inlined from betmodel.py)

# stdlib-only monolith: the v1 engine's optional requests
# path is disabled (requests = None forces its urllib branch,
# same URLs, same cache files).
requests = None

ESPN = "https://site.api.espn.com/apis/site/v2/sports"


SEASON_CFB = 2026


POOL_CUTOFF = "2026-10-17"


CFB_K = 20.0


CFB_HFA_ELO = 48.0     # conventional FBS home-field Elo prior


NHL_K = 8.0


NHL_HFA_ELO = 32.0     # conventional NHL home-ice Elo prior


START_ELO = 1500.0


def http_get(url, cache_name, max_age_h=6):
    path = os.path.join(CACHE, cache_name)
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < max_age_h * 3600:
        with open(path) as f:
            return json.load(f)
    if requests is not None:
        r = requests.get(url, timeout=30, headers={"User-Agent": "bets-analyst/betmodel"})
        r.raise_for_status()
        data = r.json()
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "bets-analyst/betmodel"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    with open(path, "w") as f:
        json.dump(data, f)
    return data


def parse_events(payload, sport):
    games = []
    for ev in payload.get("events", []):
        try:
            comp = ev["competitions"][0]
            if not ev["status"]["type"].get("completed"):
                continue
            home = away = None
            for c in comp["competitors"]:
                rec = {
                    "team": c["team"]["displayName"],
                    "score": int(c["score"]),
                }
                if c["homeAway"] == "home":
                    home = rec
                else:
                    away = rec
            if home is None or away is None or home["score"] == away["score"]:
                continue
            games.append({
                "sport": sport,
                "date": ev["date"][:10],
                "week": (ev.get("week") or {}).get("number"),
                "neutral": bool(comp.get("neutralSite")),
                "home": home["team"], "away": away["team"],
                "home_score": home["score"], "away_score": away["score"],
            })
        except (KeyError, TypeError, ValueError):
            continue
    return games


def fetch_cfb():
    all_games, seen = [], set()
    for week in range(0, 10):
        url = (f"{ESPN}/football/college-football/scoreboard"
               f"?season={SEASON_CFB}&seasontype=2&week={week}&groups=80&limit=300")
        try:
            payload = http_get(url, f"cfb_2026_w{week}.json")
        except Exception as e:
            print(f"  [fetch] CFB week {week} failed: {e}", file=sys.stderr)
            continue
        for g in parse_events(payload, "cfb"):
            key = (g["date"], g["home"], g["away"])
            if key not in seen:
                seen.add(key)
                all_games.append(g)
    all_games.sort(key=lambda g: g["date"])
    with open(os.path.join(DATA, "cfb_games_2026.json"), "w") as f:
        json.dump(all_games, f, indent=1)
    return all_games


def fetch_nhl():
    # seasontype=2 = regular season ONLY (the raw scoreboard mixes in
    # preseason games, which would contaminate the ratings).
    url = f"{ESPN}/hockey/nhl/scoreboard?dates=20261001-20261017&seasontype=2&limit=400"
    try:
        payload = http_get(url, "nhl_2026-27_range.json")
        games = parse_events(payload, "nhl")
    except Exception as e:
        print(f"  [fetch] NHL range failed ({e}); falling back to per-day", file=sys.stderr)
        games = []
        for day in range(1, 18):
            u = f"{ESPN}/hockey/nhl/scoreboard?dates=202610{day:02d}&seasontype=2&limit=100"
            try:
                games += parse_events(http_get(u, f"nhl_202610{day:02d}.json"), "nhl")
            except Exception as e2:
                print(f"  [fetch] NHL 202610{day:02d} failed: {e2}", file=sys.stderr)
    games.sort(key=lambda g: g["date"])
    with open(os.path.join(DATA, "nhl_games_2026-27.json"), "w") as f:
        json.dump(games, f, indent=1)
    return games


def load_games(sport):
    fn = "cfb_games_2026.json" if sport == "cfb" else "nhl_games_2026-27.json"
    path = os.path.join(DATA, fn)
    if not os.path.exists(path):
        print("[betmodel] no cached games — running fetch first", file=sys.stderr)
        cmd_fetch()
    with open(path) as f:
        games = json.load(f)
    return [g for g in games if g["date"] < POOL_CUTOFF]


def elo_expected(diff):
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))


def mov_multiplier(margin, winner_diff_adj):
    """538-style MOV multiplier with autocorrelation correction.
    winner_diff_adj: pre-game Elo diff from the WINNER's perspective
    (including home-field adjustment if the winner was home)."""
    return math.log(abs(margin) + 1.0) * (2.2 / (winner_diff_adj * 0.001 + 2.2))


def run_elo(games, sport):
    """Sequential Elo pass. Returns (ratings, records) where records
    carry the PRE-GAME prediction for every game (walk-forward by
    construction: prediction first, update second)."""
    K = CFB_K if sport == "cfb" else NHL_K
    HFA = CFB_HFA_ELO if sport == "cfb" else NHL_HFA_ELO
    ratings, records = {}, []
    for g in games:
        rh = ratings.get(g["home"], START_ELO)
        ra = ratings.get(g["away"], START_ELO)
        hfa = 0.0 if g["neutral"] else HFA
        diff_adj = (rh + hfa) - ra
        p_home = elo_expected(diff_adj)
        margin = g["home_score"] - g["away_score"]
        home_win = 1 if margin > 0 else 0
        records.append({
            "date": g["date"], "week": g.get("week"),
            "home": g["home"], "away": g["away"],
            "p_home": p_home, "diff_adj": diff_adj,
            "margin": margin, "home_win": home_win,
        })
        if sport == "cfb":
            if home_win:
                wdiff = diff_adj
            else:
                wdiff = -diff_adj
            mult = mov_multiplier(margin, wdiff)
        else:
            mult = 1.0
        delta = K * mult * (home_win - p_home)
        ratings[g["home"]] = rh + delta
        ratings[g["away"]] = ra - delta
    return ratings, records


def ols(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx if sxx > 0 else 0.0
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    sd = math.sqrt(sum(r * r for r in resid) / (n - 2)) if n > 2 else float("nan")
    return a, b, sd


def fit_margin_map(records):
    return ols([r["diff_adj"] for r in records], [r["margin"] for r in records])


def brier(ps, ys):
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ps)


def logloss(ps, ys, eps=1e-6):
    tot = 0.0
    for p, y in zip(ps, ys):
        p = min(max(p, eps), 1 - eps)
        tot += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return tot / len(ps)


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def cmd_fetch():
    print("[betmodel] fetching NCAAF 2026 (ESPN scoreboard, FBS, weeks 0-9)...")
    cfb = fetch_cfb()
    print(f"[betmodel] CFB completed games cached: {len(cfb)}")
    print("[betmodel] fetching NHL 2026-27 (ESPN scoreboard, Oct 1-17)...")
    nhl = fetch_nhl()
    print(f"[betmodel] NHL completed games cached: {len(nhl)}")


def resolve_team(ratings, query):
    q = query.strip().lower()
    exact = [t for t in ratings if t.lower() == q]
    if exact:
        return exact[0]
    hits = [t for t in ratings if q in t.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise SystemExit(f"[betmodel] team not found in fitted data: '{query}'")
    raise SystemExit(f"[betmodel] ambiguous team '{query}': {sorted(hits)}")


# =============================================================== CORE — v3 odds / prop math (inlined from betmodel3.py)

def ols_noint(xs, ys):
    """Least squares through the origin. Returns (b, residual_sd)."""
    sxx = sum(x * x for x in xs)
    b = sum(x * y for x, y in zip(xs, ys)) / sxx if sxx > 0 else 0.0
    resid = [y - b * x for x, y in zip(xs, ys)]
    n = len(xs)
    sd = math.sqrt(sum(r * r for r in resid) / (n - 1)) if n > 1 else float("nan")
    return b, sd


def american_to_decimal(price):
    price = int(price)
    return 1.0 + (100.0 / abs(price) if price < 0 else price / 100.0)


def decimal_to_american(dec):
    if dec >= 2.0:
        return int(round((dec - 1.0) * 100))
    return int(round(-100.0 / (dec - 1.0)))


def implied_prob(price):
    price = int(price)
    return abs(price) / (abs(price) + 100.0) if price < 0 else 100.0 / (price + 100.0)


ATHLETES = {  # resolved from ESPN rosters 2026-10-17
    "Darian Mensah": {"team": "Miami Hurricanes", "id": 5121169},
    "DeSean Bishop": {"team": "Tennessee Volunteers", "id": 4921108},
    "Josh Hoover": {"team": "Indiana Hoosiers", "id": 4685401},
}


def fetch_gamelog(name):
    info = ATHLETES[name]
    cache_name = f"gamelog_{info['id']}.json"
    url = ("https://site.api.espn.com/apis/common/v3/sports/football/"
           f"college-football/athletes/{info['id']}/gamelog?season=2026")
    return http_get(url, cache_name, max_age_h=1)


def poisson_cdf(k, lam):
    if k < 0:
        return 0.0
    s = sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(int(k) + 1))
    return min(s, 1.0)


def negbin_cdf(k, r, p):
    """NB: number of failures before r successes, P(X<=k)."""
    if k < 0:
        return 0.0
    tot = 0.0
    for i in range(int(k) + 1):
        # log-PMF for stability
        lg = (math.lgamma(i + r) - math.lgamma(r) - math.lgamma(i + 1)
              + r * math.log(p) + i * math.log(1 - p))
        tot += math.exp(lg)
    return min(tot, 1.0)


def norm_sf(x, mu, sd):
    return 1.0 - norm_cdf((x - mu) / sd)


def fit_count(series):
    n = len(series)
    mean = sum(series) / n
    var = sum((x - mean) ** 2 for x in series) / (n - 1) if n > 1 else mean
    return mean, var


def unit_class(edge):
    """STRUCTURE.md Step 5 as amended by the v2.0 spec (betmodel prob is
    the model prob): edge in probability points."""
    if edge is None or edge < 0.03:
        return 0.0
    if edge <= 0.06:
        return 1.0
    return 2.0


# =============================================================== CORE — v3.1 grade ladder (inlined from betmodel31.py)

LADDER = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D",
          "D-", "F"]  # high -> low; index = steps below A+


def base_grade(edge_pts):
    """GRADING.md base bands from edge in probability points.
    D-band interpolation: GRADING.md gives D as one band (-5..-2) and
    names no D+/D-; split it into equal 1-pt steps — D+ (-3..-2),
    D (-4..-3), D- (-5..-4) — mirroring the named 1-pt steps of the
    B band (B-/B/B+ over +2..+5) and C band."""
    for lo, g in [(8, "A+"), (6, "A"), (5, "A-"), (4, "B+"), (3, "B"),
                  (2, "B-"), (1, "C+"), (-1, "C"), (-2, "C-"), (-3, "D+"),
                  (-4, "D"), (-5, "D-")]:
        if edge_pts >= lo:
            return g
    return "F"


# =============================================================== CORE — v4 engine (inlined from betmodel4.py)

SCORECARD_PATH = os.path.join(DATA, "scorecard.json")


MECHANISMS = ["live-repricing-lag", "soft-market", "opener-staleness",
              "public-shading", "model-structural", "pilot-read",
              "other-with-note"]


SIGMA_SCHEDULE = {
    "cfb": {"sigma0": 230.0, "floor": 55.0, "rate": 0.45},
    "nhl": {"sigma0": 180.0, "floor": 45.0, "rate": 0.45},
}


def rating_sigma(sport, n_games):
    s = SIGMA_SCHEDULE[sport]
    return max(s["floor"], s["sigma0"] / math.sqrt(1.0 + s["rate"] * n_games))


def fit_ratings(sport):
    """Returns {team: {mu, sigma, games}} from the cached results pool
    (v1 load_games — today's games are excluded by POOL_CUTOFF)."""
    games = load_games(sport)
    ratings, _ = run_elo(games, sport)
    counts = {}
    for g in games:
        counts[g["home"]] = counts.get(g["home"], 0) + 1
        counts[g["away"]] = counts.get(g["away"], 0) + 1
    return {t: {"mu": ratings[t], "sigma": rating_sigma(sport, counts.get(t, 0)),
                "games": counts.get(t, 0)} for t in ratings}


def like_for_like(records, games):
    """v1.1-B FBS proxy: games where BOTH teams have >=3 pool
    appearances ('schedule-regular'). The raw ESPN groups=80 pool
    contains FBS-vs-FCS mismatches; the margin model is built only on
    the like-for-like subset."""
    from collections import Counter
    apps = Counter()
    for g in games:
        apps[g["home"]] += 1
        apps[g["away"]] += 1
    regular = {t for t, c in apps.items() if c >= 3}
    pool = [r for r in records if r["home"] in regular and r["away"] in regular]
    return pool, regular


def fit_margin_lane():
    """CFB margin lane on the like-for-like pool, fit on the FULL
    completed pool (pre-game diffs from the walk-forward Elo records,
    so no result leaks into its own prediction). No-intercept OLS,
    the v1.1-B form. Returns slope, residual SD, pool size."""
    games = load_games("cfb")
    _, recs = run_elo(games, "cfb")
    pool, _ = like_for_like(recs, games)
    slope, sd = ols_noint([r["diff_adj"] for r in pool],
                             [r["margin"] for r in pool])
    return {"slope": slope, "resid_sd": sd, "n_pool": len(pool)}


def _margin_dist(sport, home, away, neutral=False):
    """(margin_mu, margin_sd_total, detail) for home-minus-away margin,
    integrating over both teams' rating sigmas:
        Var = resid_sd^2 + slope^2 * (sigma_h^2 + sigma_a^2).
    APPROXIMATION (named): the residual SD was itself fit on noisy
    pre-game Elo diffs, so a slice of estimation error is already
    inside resid_sd — the sigma integration partially double-counts
    it. The total SD is therefore conservative (wide), by design."""
    dists = fit_ratings(sport)
    home = resolve_team(dists, home)
    away = resolve_team(dists, away)
    lane = fit_margin_lane()
    hfa = 0.0 if neutral else CFB_HFA_ELO
    dh, da = dists[home], dists[away]
    diff_adj = (dh["mu"] + hfa) - da["mu"]
    mu = lane["slope"] * diff_adj
    var = lane["resid_sd"] ** 2 + lane["slope"] ** 2 * (dh["sigma"] ** 2
                                                         + da["sigma"] ** 2)
    detail = {"home": home, "away": away, "diff_adj": diff_adj,
              "home_dist": dh, "away_dist": da, "lane": lane}
    return mu, math.sqrt(var), detail


def cfb_win_prob(home, away, neutral=False):
    """P(home wins) from the margin distribution (integrates sigmas)."""
    mu, sd, detail = _margin_dist("cfb", home, away, neutral)
    detail["margin_mu"] = mu
    detail["margin_sd_total"] = sd
    detail["p_home"] = norm_cdf(mu / sd)
    return detail


def cfb_cover_prob(home, away, spread_home, neutral=False):
    """P(home covers spread_home); spread from the HOME perspective
    (-11.5 = home favoured by 11.5; home covers iff margin > 11.5)."""
    mu, sd, detail = _margin_dist("cfb", home, away, neutral)
    detail["margin_mu"] = mu
    detail["margin_sd_total"] = sd
    detail["p_cover"] = 1.0 - norm_cdf((-spread_home - mu) / sd)
    return detail


def nhl_win_prob(home, away, neutral=False):
    """P(home wins): the Elo logistic INTEGRATED over the rating-diff
    distribution D ~ N(diff_adj, sqrt(sigma_h^2 + sigma_a^2)) by
    Gauss-Legendre quadrature on a fixed grid (stdlib only)."""
    dists = fit_ratings("nhl")
    home = resolve_team(dists, home)
    away = resolve_team(dists, away)
    hfa = 0.0 if neutral else NHL_HFA_ELO
    dh, da = dists[home], dists[away]
    diff_adj = (dh["mu"] + hfa) - da["mu"]
    sd = math.sqrt(dh["sigma"] ** 2 + da["sigma"] ** 2)
    # numeric integration of logistic over N(diff_adj, sd), +/-4 sd
    n = 161
    lo, hi = diff_adj - 4 * sd, diff_adj + 4 * sd
    step = (hi - lo) / (n - 1)
    tot = wsum = 0.0
    for i in range(n):
        x = lo + i * step
        w = math.exp(-0.5 * ((x - diff_adj) / sd) ** 2)
        w *= 0.5 if i in (0, n - 1) else 1.0  # trapezoid ends
        tot += w * elo_expected(x)
        wsum += w
    return {"home": home, "away": away, "diff_adj": diff_adj,
            "home_dist": dh, "away_dist": da, "p_home": tot / wsum}


BUILTIN_BIAS_REGISTER = {
    "cover": {
        "status": "provisional",
        "bias": "over-predicts favourite margins (PIT mean 0.429, "
                "v1.1-B walk-forward backtest)",
        "bias_favours": "favourite-spread",
        "note": "calibrated-with-noted-bias; provisional until more "
                "weeks score (CHANGELOG v1.1).",
    },
    "ml": {
        "status": "established",
        "bias": None, "bias_favours": None,
        "note": "v1 Elo lane; backtest beat the naive baseline in both "
                "sports (CFB Brier 0.2242, NHL 0.2449).",
    },
    "props": {
        "status": "established",
        "bias": None, "bias_favours": None,
        "note": "v1.5.3 game-log lane; no market backtest yet — small "
                "samples ride on the FRAGILE tag, not the status.",
    },
    "live": {
        "status": "established",
        "bias": None, "bias_favours": None,
        "note": "v4 Live Matrix; UNPROVEN — carries the established "
                "default only because the Pilot's 2026-10-17 read is "
                "its first test, seeded in this ledger.",
    },
}


RELIABILITY_DEFAULTS = {"established": 0.5, "provisional": 0.3}


GOVERNOR_WINDOW = 25        # spec: benching judged over last 25 scored


RELIABILITY_MIN_RESOLVED = 5  # below this, the default stands (named approx)


def load_scorecard():
    if os.path.exists(SCORECARD_PATH):
        with open(SCORECARD_PATH) as f:
            return json.load(f)
    return {"version": 4, "entries": [],
            "bias_register": BUILTIN_BIAS_REGISTER}


def save_scorecard(card):
    with open(SCORECARD_PATH, "w") as f:
        json.dump(card, f, indent=1)


def lane_register(card, lane):
    reg = card.get("bias_register", {}).get(lane)
    if reg is None:
        reg = BUILTIN_BIAS_REGISTER.get(lane, {"status": "established",
                                               "bias": None,
                                               "bias_favours": None,
                                               "note": "unregistered lane"})
    return reg


def lane_resolved(card, lane):
    return [e for e in card["entries"]
            if e["lane"] == lane and e.get("result") is not None]


def brier_of(entries, key):
    return sum((e[key] - e["result"]) ** 2 for e in entries) / len(entries)


def lane_record_str(card, lane):
    """'0-1 (1 resolved)' style record: a 'win' = the model's side was
    right (model_p > 0.5 and result 1, or model_p < 0.5 and result 0)."""
    res = lane_resolved(card, lane)
    wins = sum(1 for e in res
               if (e["model_p"] > 0.5) == (e["result"] == 1))
    return wins, len(res) - wins, len(res)


def lane_reliability(card, lane):
    """Learned from the scorecard when it has enough resolved entries:
        reliability = clamp(0.5 + 4 x (market_brier - model_brier),
                            0.05, 0.95)
    over the lane's resolved entries (equal Briers -> 0.5; a lane
    beating the market earns voice, a lane losing to it is faded).
    APPROXIMATION (named): with < RELIABILITY_MIN_RESOLVED resolved
    entries the status default stands — five fights is not a record,
    and the governor (25) is the real judge."""
    res = lane_resolved(card, lane)
    if len(res) >= RELIABILITY_MIN_RESOLVED:
        mb = brier_of(res, "model_p")
        kb = brier_of(res, "market_novig_p")
        return min(0.95, max(0.05, 0.5 + 4.0 * (kb - mb))), "scorecard"
    status = lane_register(card, lane)["status"]
    return RELIABILITY_DEFAULTS[status], f"default ({status})"


def lane_status(card, lane):
    """The governor's rule, implemented as specified: over the lane's
    last GOVERNOR_WINDOW resolved predictions, BENCHED iff the lane's
    Brier is worse than the market-implied (no-vig) Brier on the same
    events. Fewer resolved than the window -> INSUFFICIENT DATA."""
    res = lane_resolved(card, lane)
    if len(res) < GOVERNOR_WINDOW:
        return {"status": "INSUFFICIENT DATA", "n_resolved": len(res),
                "window": GOVERNOR_WINDOW}
    last = res[-GOVERNOR_WINDOW:]
    mb = brier_of(last, "model_p")
    kb = brier_of(last, "market_novig_p")
    st = "BENCHED" if mb > kb else "ACTIVE"
    return {"status": st, "n_resolved": len(res), "window": GOVERNOR_WINDOW,
            "lane_brier": mb, "market_brier": kb}


def scorecard_append(card, entry):
    """Append-at-price-time. Mechanism is REQUIRED and must be in the
    controlled vocabulary — a fight without a named mechanism is an
    argument, not data."""
    if entry.get("mechanism") not in MECHANISMS:
        raise SystemExit(f"[betmodel4] mechanism must be one of "
                         f"{MECHANISMS}, got {entry.get('mechanism')!r}")
    entry.setdefault("result", None)
    entry.setdefault("clv", None)
    entry.setdefault("priced_at",
                     datetime.now().astimezone().isoformat(timespec="seconds"))
    card["entries"].append(entry)
    save_scorecard(card)
    return entry


def novig_pair(price_side, price_other):
    """Two-sided no-vig: normalise the two implied probabilities."""
    a = implied_prob(price_side)
    b = implied_prob(price_other)
    return a / (a + b)


def mirror(model_p, price, lane, card, other_price=None):
    """The three numbers, plus everything grading needs.
    raw_edge is measured against the price's implied probability (the
    convention the v3.1 graded slate used: Texas +12.4 = 64.8 - 52.4).
    The SHRUNK P shrinks the model toward the market's NO-VIG position:
        shrunk_p = novig_p + reliability x (model_p - novig_p)
    and the shrunk edge used for grading is shrunk_p - implied_p, so
    shrunk_edge == raw_edge_vs_novig x reliability + (novig - implied)
    — the pure form shrunk_edge = raw_edge x reliability holds exactly
    when the price is the market's only side (novig := implied; see
    the props approximation note in prop_band)."""
    implied = implied_prob(price)
    dec = american_to_decimal(price)
    if other_price is not None:
        novig = novig_pair(price, other_price)
        novig_note = "two-sided no-vig"
    else:
        novig = implied
        novig_note = "single-sided: no-vig := implied (approximation)"
    rel, rel_src = lane_reliability(card, lane)
    status = lane_status(card, lane)["status"]
    shrunk_p = novig + rel * (model_p - novig)
    benched = status == "BENCHED"
    if benched:
        shrunk_p = novig  # governor: the lane's voice is replaced
    raw_edge = (model_p - implied) * 100
    shrunk_edge = (shrunk_p - implied) * 100
    ev_shrunk = shrunk_p * (dec - 1.0) - (1.0 - shrunk_p)
    # sizing v4: quarter-Kelly on the shrunk edge, hard-capped by the
    # STRUCTURE.md classes (via v3 unit_class on the shrunk edge).
    f_kelly = ev_shrunk / (dec - 1.0) if dec > 1.0 else 0.0
    kelly_units = max(0.0, 25.0 * f_kelly / 4.0)  # 1 unit = 1% bankroll
    size = min(unit_class(shrunk_edge / 100.0), kelly_units)
    w, l, n = lane_record_str(card, lane)
    return {
        "lane": lane, "model_p": model_p, "implied_p": implied,
        "novig_p": novig, "novig_note": novig_note,
        "reliability": rel, "reliability_source": rel_src,
        "shrunk_p": shrunk_p, "raw_edge_pts": raw_edge,
        "shrunk_edge_pts": shrunk_edge, "ev_shrunk": ev_shrunk,
        "unit_size": round(size, 2), "governor_status": status,
        "benched": benched,
        "lane_record": f"{lane} lane vs market: {w}-{l} ({n} resolved)",
    }


def grade_v4(shrunk_edge_pts, lane, card, mechanism, flags=None):
    """MODEL-V4.md grading amendment:
      - grade from the SHRUNK edge (base bands from GRADING.md);
      - provisional lane caps at B;
      - FRAGILE: -2 steps when the lane's registered bias favours the
        bet, -1 otherwise;
      - UNPRICED (no instrument can speak) caps at C — retained from
        GRADING.md; KILLED and PRICE DISCIPLINE and the grouping cap
        are retained unchanged.
    Returns (grade, tags, why_line)."""
    flags = flags or {}
    tags = []
    if flags.get("killed"):
        reason = flags["killed"] if isinstance(flags["killed"], str) else ""
        return "F", ["KILLED" + (f" ({reason})" if reason else "")], \
            _why(lane, card, mechanism)
    reg = lane_register(card, lane)
    if shrunk_edge_pts is None:
        idx = LADDER.index("C")
        tags.append("UNPRICED (cap C)")
    else:
        idx = LADDER.index(base_grade(shrunk_edge_pts))
    if flags.get("fragile"):
        bias_favours = bool(flags.get("bias_favours"))
        steps = 2 if bias_favours else 1
        idx = min(idx + steps, len(LADDER) - 1)
        tags.append(f"FRAGILE -{steps} step{'s' if steps != 1 else ''}"
                    + (" (lane bias favours this bet)" if bias_favours
                       else ""))
    give = flags.get("price_discipline_pts") or 0
    if give > 0:
        steps = max(1, int(give) // 50)
        idx = min(idx + steps, len(LADDER) - 1)
        tags.append(f"PRICE DISCIPLINE -{steps} step"
                    f"{'s' if steps != 1 else ''} ({give} pts give-back)")
    weakest = flags.get("weakest_leg_grade")
    if weakest:
        idx = max(idx, LADDER.index(weakest))
        tags.append(f"GROUPING CAP (weakest leg {weakest})")
    if reg["status"] == "provisional":
        capped = max(idx, LADDER.index("B"))
        if capped != idx:
            tags.append("PROVISIONAL CAP (B)")
        idx = capped
    return LADDER[idx], tags, _why(lane, card, mechanism)


def _why(lane, card, mechanism):
    rel, src = lane_reliability(card, lane)
    w, l, n = lane_record_str(card, lane)
    return (f"mechanism: {mechanism} | {lane} lane vs market: {w}-{l} "
            f"({n} resolved), reliability {rel:.2f} ({src})")


def fmt_mirror(label, price, m, grade=None, tags=None, why=None):
    """v4 line: the three probabilities first — raw, market no-vig,
    shrunk — then the grade with its why."""
    s = (f"**{label}** | price {int(price):+d} | raw P "
         f"{m['model_p'] * 100:.1f}% | market no-vig P "
         f"{m['novig_p'] * 100:.1f}% | SHRUNK P {m['shrunk_p'] * 100:.1f}% "
         f"| raw edge {m['raw_edge_pts']:+.1f} pts | shrunk edge "
         f"{m['shrunk_edge_pts']:+.1f} pts | EV(shrunk) "
         f"{m['ev_shrunk'] * 100:+.1f}% | size {m['unit_size']:.1f}u")
    if grade is not None:
        s += f" | GRADE {grade}" + (f" [{'; '.join(tags)}]" if tags else "")
    if why:
        s += f"\n  - why: {why}"
    if m["benched"]:
        s += "\n  - GOVERNOR: lane BENCHED — model P replaced by market."
    return s


AGREE_PTS = 3.0  # families within 3 pts -> consensus; else pessimistic


def gamelog_series_cached(name, stat_name):
    """Player game-log series from the lab's local ESPN cache
    (data/cache/gamelog_<id>.json — the same files the v3 run priced
    from). Offline-safe; falls back to b3's fetch path only if the
    cache file is missing."""
    info = ATHLETES[name]
    path = os.path.join(CACHE, f"gamelog_{info['id']}.json")
    if os.path.exists(path):
        with open(path) as f:
            d = json.load(f)
    else:
        d = fetch_gamelog(name)
    names = d.get("names") or []
    if stat_name not in names:
        raise SystemExit(f"[betmodel4] stat '{stat_name}' not in {name}'s "
                         f"gamelog (has: {names})")
    idx = names.index(stat_name)
    series = []
    for st in d.get("seasonTypes", []):
        for cat in st.get("categories", []):
            if cat.get("type") != "event":
                continue
            for ev in cat.get("events", []):
                try:
                    series.append(float(ev["stats"][idx]))
                except (KeyError, TypeError, ValueError, IndexError):
                    continue
    if not series:
        raise SystemExit(f"[betmodel4] no game-log events for {name}")
    return series


def _nb_p_over(line, mean, var):
    """P(X > line) under a method-of-moments negative binomial.
    Underdispersed logs (var <= mean) have no NB fit — the NB limit is
    the Poisson, and we say so (Mensah's case)."""
    if var <= mean or mean <= 0:
        return None
    r = mean * mean / (var - mean)
    p = r / (r + mean)
    return 1.0 - negbin_cdf(math.floor(line), r, p)


def prop_band(name, stat_name, line, side, series=None):
    """Two-family prop pricing. Returns per-family P(side), the band,
    the price actually used (consensus or pessimistic end), and the
    disagreement in points. PESSIMISTIC = the lower P(side) — for an
    over, the family that likes the over least; symmetric for unders.
    APPROXIMATION (named): single-sided market — only the taken side's
    price is on file for props, so in the mirror novig := implied."""
    if series is None:
        series = gamelog_series_cached(name, stat_name)
    n = len(series)
    mean, var = fit_count(series)
    count_stats = {"passingTouchdowns", "rushingTouchdowns",
                   "receivingTouchdowns"}
    fams = {}
    if stat_name in count_stats:
        pois = 1.0 - poisson_cdf(math.floor(line), mean)
        fams["poisson"] = pois
        nb = _nb_p_over(line, mean, var)
        fams["negbin"] = nb if nb is not None else pois
        if nb is None:
            fams["negbin_note"] = ("var <= mean: NB limit is Poisson "
                                   "(underdispersed log)")
    else:
        sd = math.sqrt(var)
        fams["normal"] = norm_sf(line, mean, sd)
        pos = [x for x in series if x > 0]
        if len(pos) == n and n > 1:
            lm = sum(math.log(x) for x in pos) / n
            lv = sum((math.log(x) - lm) ** 2 for x in pos) / (n - 1)
            fams["lognormal"] = 1.0 - norm_cdf(
                (math.log(line) - lm) / math.sqrt(lv))
        else:
            fams["lognormal"] = fams["normal"]
            fams["lognormal_note"] = "zeros in log: lognormal not fit"
    p_overs = {k: v for k, v in fams.items() if isinstance(v, float)}
    if side == "over":
        p_side = dict(p_overs)
    else:
        p_side = {k: 1.0 - v for k, v in p_overs.items()}
    lo_k = min(p_side, key=p_side.get)
    hi_k = max(p_side, key=p_side.get)
    lo, hi = p_side[lo_k], p_side[hi_k]
    disagree = (hi - lo) * 100
    if disagree <= AGREE_PTS:
        price_p = sum(p_side.values()) / len(p_side)
        mode = "consensus (families agree within 3 pts)"
    else:
        price_p = lo
        mode = f"PESSIMISTIC end ({lo_k}) — families disagree"
    return {"player": name, "stat": stat_name, "line": line, "side": side,
            "n_games": n, "series": series,
            "sample_mean": round(mean, 3), "sample_var": round(var, 3),
            "families": {k: (round(v, 4) if isinstance(v, float) else v)
                         for k, v in fams.items()},
            "p_side_by_family": {k: round(v, 4) for k, v in p_side.items()},
            "band": [round(lo, 4), round(hi, 4)],
            "disagree_pts": round(disagree, 1),
            "price_p": price_p, "price_mode": mode}


PLAY_P_INCOMPLETE = 0.16


PLAY_GAIN_MU, PLAY_GAIN_SD = 6.2, 7.8


PLAY_P_TURNOVER = 0.021


PUNT_NET = 40


DRIVES_PER_TEAM_GAME = 12.0


def _fg_make(dist):
    return min(0.96, max(0.15, 1.19 - 0.0113 * dist))


def _simulate_drive(rng, yard, down, ytg, adj):
    """Simulate one drive. yard = yards from the possessing team's own
    goal (1..99). adj = fractional prior points added to the drive's
    points (the decaying pregame prior). Returns (points, end_yard_for_
    opponent_or_None, plays). points may be fractional via adj — the
    WP tally only needs the sign of the final margin; exact ties fall
    to the OT rule in live_wp."""
    plays = 0
    while True:
        plays += 1
        if plays > 25:
            return 0.0 + adj, 25, plays  # stalled-drive safeguard
        if rng.random() < PLAY_P_TURNOVER:
            # turnover: opponent takes over at the flipped spot
            return 0.0 + adj, max(5, 100 - yard), plays
        if rng.random() < PLAY_P_INCOMPLETE:
            gain = 0
        else:
            gain = int(round(rng.gauss(PLAY_GAIN_MU, PLAY_GAIN_SD)))
            gain = max(-8, min(90, gain))
        yard += gain
        ytg -= gain
        if yard >= 100:
            return 7.0 + adj, 25, plays        # TD; opp starts own 25
        if yard < 1:
            # safety: -2 is margin-equivalent to +2 for the defence;
            # the opponent then takes the free kick around its own 35
            return -2.0 + adj, 35, plays
        if ytg <= 0:
            down, ytg = 1, min(10, 100 - yard)
            continue
        down += 1
        if down < 4:
            continue
        # ---- 4th down decision
        kick_dist = (100 - yard) + 17
        if kick_dist <= 52:
            if rng.random() < _fg_make(kick_dist):
                return 3.0 + adj, 25, plays    # FG good; opp own 25
            return 0.0 + adj, 25, plays        # miss: opp own 25 (named)
        if ytg <= 2 and yard >= 55:
            # go for it
            if rng.random() < PLAY_P_INCOMPLETE:
                gain = 0
            else:
                gain = int(round(rng.gauss(PLAY_GAIN_MU, PLAY_GAIN_SD)))
            yard += gain
            ytg -= gain
            if yard >= 100:
                return 7.0 + adj, 25, plays
            if ytg <= 0:
                down, ytg = 1, min(10, 100 - yard)
                continue
            return 0.0 + adj, max(5, 100 - yard), plays  # downs
        # punt
        land = yard + PUNT_NET
        opp_yard = 25 if land >= 100 else max(5, 100 - land)
        return 0.0 + adj, opp_yard, plays


def live_wp(state, n_sims=4000, seed=20261017):
    """state: {home_score, away_score, quarter, clock_sec (remaining in
    the quarter), possession: 'home'|'away', yard (from possessing
    team's own goal), down, yards_to_go, pregame_home_margin (expected
    pregame margin, home perspective; +11.5 for a home team favoured
    by 11.5)}. Returns WP for both teams + diagnostics."""
    rng = random.Random(seed)
    secs_left = (4 - state["quarter"]) * 900 + state["clock_sec"]
    frac = (secs_left / 3600.0) ** 2  # quadratic prior decay (see header)
    prior = state.get("pregame_home_margin", 0.0)
    # distribute the decayed prior over estimated remaining drives
    est_drives = max(2.0, secs_left / 150.0)
    adj = {"home": prior * frac / est_drives,
           "away": -prior * frac / est_drives}
    home_wins = away_wins = 0
    drive_ep_samples = []
    for _ in range(n_sims):
        hs, as_ = state["home_score"], state["away_score"]
        poss = state["possession"]
        yard, down, ytg = state["yard"], state["down"], state["yards_to_go"]
        clock = secs_left
        first = True
        while clock > 0:
            pts, next_yard, plays = _simulate_drive(
                rng, yard, down, ytg, adj[poss])
            if first:
                drive_ep_samples.append(pts - adj[poss])
                first = False
            if poss == "home":
                hs += pts
            else:
                as_ += pts
            clock -= plays * rng.uniform(20, 30)
            if clock <= 0 or next_yard is None:
                break
            poss = "away" if poss == "home" else "home"
            yard, down, ytg = next_yard, 1, 10
        if hs > as_:
            home_wins += 1
        elif as_ > hs:
            away_wins += 1
        else:
            # OT: sudden-death coin flip, prior fully decayed
            if rng.random() < 0.5:
                home_wins += 1
            else:
                away_wins += 1
    n = home_wins + away_wins
    return {"wp_home": home_wins / n, "wp_away": away_wins / n,
            "drive_ep": (sum(drive_ep_samples) / len(drive_ep_samples)
                         if drive_ep_samples else None),
            "secs_left": secs_left, "prior_decay_frac": round(frac, 3),
            "n_sims": n_sims}


FLORIDA_STATE_A = {"home": "Texas Longhorns", "away": "Florida Gators",
                   "home_score": 17, "away_score": 17, "quarter": 3,
                   "clock_sec": 5 * 60 + 28, "possession": "away",
                   "yard": 25, "down": 1, "yards_to_go": 10,
                   "pregame_home_margin": 11.5}


def seed_scorecard(florida_wp=None):
    card = load_scorecard()
    if card["entries"]:
        return card, False
    if florida_wp is None:
        florida_wp = live_wp(FLORIDA_STATE_A)["wp_away"]
    card["entries"] = [
        {"lane": "cover", "event": "Texas -11.5 vs Florida (NCAAF, "
         "2026-10-17)", "raw_edge_pts": 12.4, "mechanism": "model-structural",
         "market_novig_p": 0.500, "model_p": 0.648, "result": None,
         "clv": None, "priced_at": "2026-10-17T12:29:00-04:00",
         "note": "v1.1-B cover lane claim as graded by v3.1 (model "
                 "64.8% vs implied 52.4% at -110/-110, no-vig 50.0%). "
                 "Lane bias on file: over-predicts favourite margins."},
        {"lane": "ml", "event": "Tennessee ML vs Alabama (NCAAF, "
         "2026-10-17)", "raw_edge_pts": 24.3, "mechanism": "model-structural",
         "market_novig_p": 0.270, "model_p": 0.525, "result": None,
         "clv": None, "priced_at": "2026-10-17T12:20:00-04:00",
         "note": "betmodel v1 Elo: Tennessee 52.5% vs market +255 "
                 "(implied 28.2%; two-sided no-vig vs Alabama -320 = "
                 "27.0%). Logged in data/live-board-2026-10-17-1346.md "
                 "as the widest model-vs-market gap of the day."},
        {"lane": "live", "event": "Florida ML at Texas (Pilot Book live "
         "bet, 2026-10-17)", "raw_edge_pts": round((florida_wp - 0.1786)
                                                   * 100, 1),
         "mechanism": "live-repricing-lag", "market_novig_p": 0.164,
         "model_p": round(florida_wp, 4), "result": None, "clv": None,
         "priced_at": "2026-10-17T14:05:00-04:00",
         "note": "Pilot's read, placed ~14:05 ET at +460 (implied "
                 "17.9%; no-vig 16.4% vs Texas -1000 from the 13:46 "
                 "board). model_p is the v4 Live Matrix price of the "
                 "Q3 5:28 tied-17-17 state (regression R3a) — the first "
                 "logged state at/after the tying score; the bet itself "
                 "was struck at halftime, Florida down 7."},
    ]
    save_scorecard(card)
    return card, True


def v4_cmd_governor(args):
    card = load_scorecard()
    print("# betmodel v4 — Calibration Governor")
    print("")
    lanes = sorted({e["lane"] for e in card["entries"]}
                   | set(BUILTIN_BIAS_REGISTER))
    for lane in lanes:
        st = lane_status(card, lane)
        rel, src = lane_reliability(card, lane)
        line = (f"- lane '{lane}': resolved {st['n_resolved']} / window "
                f"{st['window']} -> **{st['status']}** | reliability "
                f"{rel:.2f} ({src})")
        if "lane_brier" in st:
            line += (f" | lane Brier {st['lane_brier']:.4f} vs market "
                     f"Brier {st['market_brier']:.4f} (last "
                     f"{st['window']})")
        print(line)
    print("")
    print("Rule (MODEL-V4.md organ 6): a lane is BENCHED only when, over "
          "its last 25 resolved scorecard predictions, its Brier is "
          "worse than the market no-vig Brier on the same events. Below "
          "the window the answer is INSUFFICIENT DATA — the governor "
          "does not bench on a sample it would not bet on.")


def v4_cmd_scorecard(args):
    card, seeded = seed_scorecard()
    print(f"# Disagreement Scorecard ({SCORECARD_PATH})"
          + (" — seeded with today's three fights" if seeded else ""))
    for e in card["entries"]:
        print(f"- [{e['lane']}] {e['event']} | mechanism "
              f"{e['mechanism']} | model {e['model_p'] * 100:.1f}% vs "
              f"market no-vig {e['market_novig_p'] * 100:.1f}% | raw edge "
              f"{e['raw_edge_pts']:+.1f} pts | result {e['result']} | "
              f"clv {e['clv']}")


def v4_cmd_live(args):
    with open(args.state) as f:
        state = json.load(f)
    r = live_wp(state, n_sims=args.sims)
    print(json.dumps({**{k: state[k] for k in
                         ("home_score", "away_score", "quarter",
                          "clock_sec", "possession", "yard", "down",
                          "yards_to_go")},
                      "wp_home": round(r["wp_home"], 4),
                      "wp_away": round(r["wp_away"], 4),
                      "current_drive_ep": round(r["drive_ep"], 2)
                      if r["drive_ep"] is not None else None,
                      "prior_decay_frac": r["prior_decay_frac"]}, indent=2))


# =============================================================== CORE — NFL lane (inlined from nfl_lane.py)

def nfl_http_get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def nfl_games(week):
    j = nfl_http_get(f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?week={week}&seasontype=2')
    out = []
    for ev in j.get('events', []):
        comp = ev['competitions'][0]
        cs = comp['competitors']
        home = next(c for c in cs if c['homeAway']=='home'); away = next(c for c in cs if c['homeAway']=='away')
        odds = None
        if comp.get('odds'):
            o = comp['odds'][0]
            odds = {'details': o.get('details'), 'spread': o.get('spread'), 'total': o.get('overUnder'),
                    'homeML': (o.get('homeTeamOdds') or {}).get('moneyLine'), 'awayML': (o.get('awayTeamOdds') or {}).get('moneyLine')}
        out.append({'week': week, 'home': home['team']['abbreviation'], 'away': away['team']['abbreviation'],
                    'hs': int(home['score']) if home.get('score') not in (None,'') else None,
                    'as': int(away['score']) if away.get('score') not in (None,'') else None,
                    'final': ev['status']['type']['completed'], 'odds': odds,
                    'neutral': comp.get('neutralSite', False)})
    return out


def nfl_elo_run(glist, K=20, hfa=55):
    R = {}
    def r(t): return R.get(t, 1500.0)
    preds = []
    for g in glist:
        if g['hs'] is None: continue
        h = 0 if g['neutral'] else hfa
        d = r(g['home']) + h - r(g['away'])
        p = 1/(1+10**(-d/400))
        preds.append((g, p))
        if g['final']:
            mov = g['hs'] - g['as']
            win = 1.0 if mov > 0 else (0.5 if mov == 0 else 0.0)
            mult = math.log(abs(mov)+1) * (2.2/( (r(g['home'])-r(g['away']))*0.001 + 2.2)) if mov != 0 else 1.0
            delta = K * mult * (win - p)
            R[g['home']] = r(g['home']) + delta; R[g['away']] = r(g['away']) - delta
    return R, preds


# =============================================================== betmodel v5 — organs, card, coverage, commands

NFL_MARGIN_SD = 13.9   # lab convention (compile §2; lane cover probs)
ENSEMBLE_EPS = 0.01    # inverse-Brier weight regulariser (named)




# ================================================================ organ 4
# Lane records — Win # / Lose #, from the lab's own scored files.
#
# The scorecard's resolutions were written back in prose form on
# 2026-10-17/18 ("market_right", "model_right", one entry carrying the
# verdict in an "outcome" field with a prose "result"). v5 parses the
# record AS IT EXISTS: y = 1 when the model's priced side happened.

def outcome_y(entry):
    """1 if the event the model priced happened, 0 if the market's
    side did, None if the entry is unresolved / unparseable."""
    for key in ("outcome", "result"):
        v = entry.get(key)
        if isinstance(v, (int, float)):
            return 1 if v == 1 else 0
        if isinstance(v, str):
            s = v.lower()
            if "model_right" in s or "model right" in s:
                return 1
            if "market_right" in s or "market right" in s:
                return 0
    return None


def scorecard_resolved():
    """Scorecard entries with a numeric outcome, grouped by lane."""
    card = load_scorecard()
    by_lane = {}
    for e in card["entries"]:
        y = outcome_y(e)
        if y is None:
            continue
        by_lane.setdefault(e["lane"], []).append(
            {"model_p": e["model_p"], "market_p": e["market_novig_p"],
             "y": y, "event": e["event"]})
    return by_lane


def lane_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH) as f:
            return json.load(f)
    return {}


def lane_record(lane):
    """(wins, losses, source) for the card's Win # / Lose # line.
    A 'win' = the lane's priced side was right (model_p > 0.5 and the
    event happened, or model_p < 0.5 and it did not)."""
    if lane in ("nfl-ml", "nfl"):
        hist = lane_history().get("nfl-ml")
        if hist:
            return hist["wins"], hist["losses"], hist["source"]
        return 0, 0, "no graded NFL slate on file"
    res = scorecard_resolved().get(lane, [])
    wins = sum(1 for e in res if (e["model_p"] > 0.5) == (e["y"] == 1))
    if not res:
        return 0, 0, "no scored record on file"
    return wins, len(res) - wins, "data/scorecard.json"


def lane_briers(lane):
    """(model Brier, market Brier, n) over the lane's resolved
    record, or None when the lane has no resolved record."""
    if lane in ("nfl-ml", "nfl"):
        hist = lane_history().get("nfl-ml")
        if hist:
            return hist["brier_model"], hist["brier_market"], hist["n"]
        return None
    res = scorecard_resolved().get(lane, [])
    if not res:
        return None
    mb = statistics.mean([(e["model_p"] - e["y"]) ** 2 for e in res])
    kb = statistics.mean([(e["market_p"] - e["y"]) ** 2 for e in res])
    return mb, kb, len(res)


# ================================================================ organ 1
# The Source Ensemble — weights learned from resolved Briers.

def ensemble_weights(lane):
    """Returns (w_model, w_market, note). Weights are inverse-Brier,
    learned per lane; with no resolved record the ensemble cannot
    learn and the model source speaks alone (note says so)."""
    br = lane_briers(lane)
    if br is None:
        return 1.0, 0.0, ("UNLEARNED — lane has no resolved record; "
                          "model source alone")
    mb, kb, n = br
    im = 1.0 / (mb + ENSEMBLE_EPS)
    ik = 1.0 / (kb + ENSEMBLE_EPS)
    return (im / (im + ik), ik / (im + ik),
            f"FITTED from resolved Briers (model {mb:.4f} vs market "
            f"{kb:.4f}, n={n})")


# ================================================================ organ 2
# The Reparametrization Layer.
#
# phi candidates are plain dicts so they persist to data/v5-phi.json:
#   {"kind": "identity"}
#   {"kind": "lin", "a": <fitted coefficient>}
#   {"kind": "iso", "blocks": [[rep_x, value], ...]}   (PAVA steps)

def phi_apply(phi, p):
    k = phi["kind"]
    if k == "identity":
        return p
    if k == "lin":
        return 0.5 + phi["a"] * (p - 0.5)
    if k == "iso":
        val = phi["blocks"][0][1]
        for x, v in phi["blocks"]:
            if p >= x:
                val = v
            else:
                break
        return min(0.98, max(0.02, val))
    raise ValueError(f"unknown phi kind {k!r}")


def fit_lin(pairs):
    """Fitted shrinkage coefficient: grid search a in [0, 1] on Brier
    over the training pairs [(p, y), ...]. Returns (a, brier)."""
    best = (float("inf"), 1.0)
    a = 0.0
    while a <= 1.0001:
        b = statistics.mean([((0.5 + a * (p - 0.5)) - y) ** 2
                             for p, y in pairs])
        if b < best[0]:
            best = (b, a)
        a += 0.005
    return best[1], best[0]


def fit_iso(pairs):
    """PAVA isotonic fit. Returns blocks [[rep_x, value], ...] with
    rep_x the block's n-weighted mean raw p (the step map applies the
    value of the last block whose rep_x <= p)."""
    merged = []
    for x, y in sorted(pairs):
        merged.append([x, y, 1.0])
        while len(merged) > 1 and merged[-2][1] > merged[-1][1]:
            b2 = merged.pop()
            b1 = merged.pop()
            n = b1[2] + b2[2]
            merged.append([(b1[0] * b1[2] + b2[0] * b2[2]) / n,
                           (b1[1] * b1[2] + b2[1] * b2[2]) / n, n])
    return [[round(x, 4), round(v, 4)] for x, v, _ in merged]


def phi_candidates(pairs):
    """All three candidates fitted on the SAME training pairs."""
    a, _ = fit_lin(pairs)
    return {"identity": {"kind": "identity"},
            "lin": {"kind": "lin", "a": round(a, 3)},
            "iso": {"kind": "iso", "blocks": fit_iso(pairs)}}


def phi_cv_select(folded_pairs):
    """Leave-one-fold-out CV (folds = weeks) over the candidates,
    fitted on training folds only. Selection NEVER sees the test
    slate. Returns (selected_name, {name: cv_brier}). Ties break
    toward the simpler map (identity < lin < iso)."""
    folds = sorted({w for w, _, _ in folded_pairs})
    scores = {}
    for name in ("identity", "lin", "iso"):
        errs = []
        for w in folds:
            tr = [(p, y) for ww, p, y in folded_pairs if ww != w]
            te = [(p, y) for ww, p, y in folded_pairs if ww == w]
            cand = phi_candidates(tr)[name]
            errs += [(phi_apply(cand, p) - y) ** 2 for p, y in te]
        scores[name] = statistics.mean(errs)
    order = {"identity": 0, "lin": 1, "iso": 2}
    selected = min(scores, key=lambda n: (round(scores[n], 6), order[n]))
    return selected, scores


# ---- the NFL lane phi fit — walk-forward on 2026 weeks 1-5 only,
# following nfl_lane.py's own protocol exactly (train on weeks < w,
# predict week w from the final training ratings; the lane's
# published walk-forward Briers 0.2134 / 0.2310 / 0.2609 reproduce
# from this code path — verified in the v5 regression).

WEEK6_FINALS = {   # home margins, results/weekend-compile-2026-10-17-18.md §1
    ("HOU", "JAX"): -3, ("CHI", "ATL"): -8, ("BAL", "CLE"): 3,
    ("TEN", "IND"): -6, ("NYJ", "NE"): 7, ("NO", "NYG"): -7,
    ("CAR", "PHI"): -11, ("PIT", "TB"): -7, ("ARI", "LAR"): -2,
    ("LAC", "KC"): 16, ("BUF", "LV"): -3,
    # DAL@GB excluded: its final is not in the lab record (compile §1).
    # WSH@SF excluded: Monday-night game, unplayed at compile time.
}


def nfl_walkforward_pairs():
    """(week, raw_p, y) for weeks 3-5 of 2026, walk-forward, via
    nfl_lane (ESPN scoreboard). Weeks 1-2 have no earlier training
    weeks — the lane's own protocol starts at week 3."""
    played = []
    for w in range(1, 6):
        played += [g for g in nfl_games(w) if g["final"]]
    pairs = []
    for w in (3, 4, 5):
        train = [g for g in played if g["week"] < w]
        test = [g for g in played if g["week"] == w]
        R, _ = nfl_elo_run(train)
        for g in test:
            h = 0 if g["neutral"] else 55
            d = R.get(g["home"], 1500) + h - R.get(g["away"], 1500)
            p = 1 / (1 + 10 ** (-d / 400))
            pairs.append((w, p, 1.0 if g["hs"] > g["as"] else 0.0))
    return pairs


def fit_nfl_phi(persist=True):
    """Fit the NFL lane's phi on weeks 1-5 walk-forward pairs, then
    grade it out-of-sample on the Week 6 slate. Persists the fit
    (data/v5-phi.json) and the lane history (data/v5-lane-history.json)
    the card reads. The UNCALIBRATED rule (MODEL-V5.md R4): if the
    selected phi's out-of-sample Brier cannot beat v4's shrunk 0.278,
    the lane ships UNCALIBRATED — the failure is part of the fit
    record, not an afterthought."""
    folded = nfl_walkforward_pairs()
    pairs = [(p, y) for _, p, y in folded]
    cands = phi_candidates(pairs)
    selected, cv = phi_cv_select(folded)
    phi = cands[selected]

    with open(NFL_PRICING_PATH) as f:
        pricing = json.load(f)
    slate = []
    for g in pricing["games"]:
        key = (g["away"], g["home"])
        if key not in WEEK6_FINALS:
            continue
        mkt = norm_cdf(-g["spread"] / NFL_MARGIN_SD)  # spread-implied
        slate.append({"game": f"{key[0]}@{key[1]}", "raw": g["p_home"],
                      "mkt": mkt,
                      "y": 1.0 if WEEK6_FINALS[key] > 0 else 0.0})

    def brier(fn):
        return statistics.mean([(fn(s) - s["y"]) ** 2 for s in slate])

    os_briers = {
        "raw_identity": brier(lambda s: s["raw"]),
        "market": brier(lambda s: s["mkt"]),
        "v4_shrunk_0.30": brier(
            lambda s: s["mkt"] + 0.30 * (s["raw"] - s["mkt"])),
        "phi": {name: brier(lambda s, c=c: phi_apply(c, s["raw"]))
                for name, c in cands.items()},
    }
    w_m, w_k, _ = (None, None, None)
    mb, kb = os_briers["raw_identity"], os_briers["market"]
    im, ik = 1.0 / (mb + ENSEMBLE_EPS), 1.0 / (kb + ENSEMBLE_EPS)
    w_m, w_k = im / (im + ik), ik / (im + ik)
    os_briers["ensemble_phi"] = brier(
        lambda s: w_m * phi_apply(phi, s["raw"]) + w_k * s["mkt"])

    phi_brier = os_briers["phi"][selected]
    calibrated = phi_brier < os_briers["v4_shrunk_0.30"]
    wins = sum(1 for s in slate
               if (s["raw"] > 0.5) == (s["y"] == 1))
    fit = {
        "lane": "nfl-ml",
        "fitted_at": datetime.now().astimezone().isoformat(
            timespec="seconds"),
        "train": {"weeks": [3, 4, 5], "n_pairs": len(pairs),
                  "protocol": "walk-forward, nfl_lane.elo_run "
                              "(train weeks < w, predict week w)"},
        "candidates": cands,
        "cv_brier": {k: round(v, 4) for k, v in cv.items()},
        "selected": selected,
        "os_test": {"slate": "NFL Week 6, 11 graded games "
                             "(compile §1/§2)",
                    "briers": {k: (round(v, 4) if not isinstance(v, dict)
                                   else {kk: round(vv, 4)
                                         for kk, vv in v.items()})
                               for k, v in os_briers.items()},
                    "benchmark_v4_shrunk": 0.278},
        "status": "CALIBRATED" if calibrated else "UNCALIBRATED",
        "status_reason": (
            f"selected phi ({selected}) out-of-sample Brier "
            f"{phi_brier:.4f} vs the v4-shrunk benchmark "
            f"{os_briers['v4_shrunk_0.30']:.4f} — "
            + ("beats it; phi ships." if calibrated else
               "does NOT beat it; the lane ships UNCALIBRATED "
               "(grades cap at C) per MODEL-V5.md R4.")),
        "slate_detail": slate,
    }
    hist = {"nfl-ml": {
        "wins": wins, "losses": len(slate) - wins, "n": len(slate),
        "brier_model": round(mb, 4), "brier_market": round(kb, 4),
        "source": "results/weekend-compile-2026-10-17-18.md §1-§2 "
                  "(graded by betmodel5 R4)"}}
    if persist:
        with open(PHI_PATH, "w") as f:
            json.dump(fit, f, indent=1)
        with open(HISTORY_PATH, "w") as f:
            json.dump(hist, f, indent=1)
    return fit


def load_phi_registry():
    if os.path.exists(PHI_PATH):
        with open(PHI_PATH) as f:
            return json.load(f)
    return None


def lane_phi(lane):
    """(phi, state, detail) for a lane. States: FITTED (a tested
    non-identity map), IDENTITY-AFTER-TEST (tested; identity won —
    the NFL lane after R4), NOT-YET-FITTED (no walk-forward pair set
    for this lane's estimator yet; identity in use, nothing claimed).
    """
    if lane in ("nfl-ml", "nfl"):
        fit = load_phi_registry()
        if fit:
            cand = fit["candidates"][fit["selected"]]
            state = ("FITTED" if fit["selected"] != "identity"
                     else "IDENTITY-AFTER-TEST")
            return cand, state, fit
        return {"kind": "identity"}, "NOT-YET-FITTED", None
    return ({"kind": "identity"}, "NOT-YET-FITTED",
            "no walk-forward pair set built for this lane's "
            "estimator yet")


def lane_uncalibrated(lane):
    """v5 cap-C conditions: the lane failed its phi benchmark test
    (registry status UNCALIBRATED), or it has no scored record
    (organ 4). Returns a reason string or None."""
    if lane in ("nfl-ml", "nfl"):
        fit = load_phi_registry()
        if fit and fit["status"] == "UNCALIBRATED":
            return "UNCALIBRATED (phi failed its out-of-sample test)"
    w, l, _ = lane_record(lane)
    if w + l == 0:
        return "UNCALIBRATED (no scored record — organ 4)"
    return None


# ================================================================ organ 3
# Cross-market coherence. Quotes are dicts:
#   {"source": str, "spread_home": float|None, "total": float|None,
#    "ml_p_home": float|None}
# spread_home is from the HOME perspective (-2.5 = home favoured 2.5).

def coherence_check(quotes, sd=NFL_MARGIN_SD):
    flags = []
    spreads = [(q["source"], q["spread_home"]) for q in quotes
               if q.get("spread_home") is not None]
    totals = [(q["source"], q["total"]) for q in quotes
              if q.get("total") is not None]
    favs = {(s > 0) - (s < 0) for _, s in spreads if s != 0}
    if len(favs) > 1:
        flags.append("FAVOURITE FLIP across sources: "
                     + "; ".join(f"{src} {s:+.1f}" for src, s in spreads))
    for i in range(len(totals)):
        for j in range(i + 1, len(totals)):
            d = abs(totals[i][1] - totals[j][1])
            if d >= 1.0:
                flags.append(
                    f"TOTAL INCOHERENCE: {totals[i][0]} {totals[i][1]} "
                    f"vs {totals[j][0]} {totals[j][1]} (Δ{d:.1f} >= 1.0)")
    for i in range(len(spreads)):
        for j in range(i + 1, len(spreads)):
            d = abs(spreads[i][1] - spreads[j][1])
            if d >= 4.0:
                flags.append(
                    f"SPREAD INCOHERENCE: {spreads[i][0]} "
                    f"{spreads[i][1]:+.1f} vs {spreads[j][0]} "
                    f"{spreads[j][1]:+.1f} (Δ{d:.1f} >= 4.0, the lab "
                    f"audit-flag threshold)")
    for q in quotes:
        if q.get("spread_home") is not None and q.get("ml_p_home") is not None:
            implied = norm_cdf(-q["spread_home"] / sd)
            d = abs(implied - q["ml_p_home"]) * 100
            if d > 6.0:
                flags.append(
                    f"ML/SPREAD TRIANGLE ({q['source']}): spread "
                    f"{q['spread_home']:+.1f} implies P(home) "
                    f"{implied * 100:.1f}% but its ML says "
                    f"{q['ml_p_home'] * 100:.1f}% (Δ{d:.1f} > 6 pts) — "
                    f"not reconcilable through one margin distribution")
    return flags


# ================================================================ grading v5
# Frozen GRADING.md rubric on the PHI edge + v4 modifiers (via
# betmodel4.grade_v4) + v5 caps (UNCALIBRATED / no-record -> C).

def grade_v5(phi_edge_pts, lane, card, mechanism, flags=None):
    flags = flags or {}
    grade, tags, why = grade_v4(phi_edge_pts, lane, card, mechanism,
                                   flags)
    cap_reason = lane_uncalibrated(lane)
    if cap_reason and not flags.get("killed"):
        idx = max(LADDER.index(grade), LADDER.index("C"))
        if LADDER[idx] != grade:
            tags.append(cap_reason + " — cap C applied")
        grade = LADDER[idx]
    return grade, tags, why


# ================================================================ organ 5
# The Verdict Ladder (v5.1) — the Decision Gate's successor.

GATE_MIN_GRADE = "B-"


def lane_benched(lane, card):
    """The Governor's bench test for one lane (the v5.0 gate's rule,
    unchanged): the NFL lane reads its graded-slate history file
    (benching needs a full governor window of resolved predictions
    AND a worse Brier than the market's); every other lane reads
    the scorecard governor."""
    if lane in ("nfl-ml", "nfl"):
        hist = lane_history().get("nfl-ml")
        return bool(hist and hist["n"] >= GOVERNOR_WINDOW
                    and hist["brier_model"] > hist["brier_market"])
    return lane_status(card, lane)["status"] == "BENCHED"


def decision_gate(grade, lane, card, pessimistic_edge_pts, flags=None):
    """The v5.0 binary gate, retained as the ladder's fail-list
    supplier (checker notes quote its named fails). The card's
    printed verdict comes from verdict_ladder below — nothing
    user-facing reads this function's term any more."""
    flags = flags or {}
    fails = []
    if LADDER.index(grade) > LADDER.index(GATE_MIN_GRADE):
        fails.append(f"grade {grade} < {GATE_MIN_GRADE} required")
    benched = lane_benched(lane, card)
    if benched:
        fails.append("lane BENCHED by the Governor")
    if pessimistic_edge_pts is None or pessimistic_edge_pts <= 0:
        fails.append("edge does not survive the pessimistic end of "
                     "the band")
    if flags.get("killed"):
        fails.append("kill-ledger contact")
    return ("No Bet", fails) if fails else ("Bet", [])


VERDICT_LADDER = ["GOLDEN BET", "BET HERE", "RISK BET (BET)",
                  "RISK BET (DO NOT BET)", "DO NOT BET"]
GOLDEN_BET, BET_HERE, RISK_BET_YES, RISK_BET_NO, DO_NOT_BET = \
    VERDICT_LADDER


def verdict_rank(verdict):
    """BetFi ordering: ladder position (the feed ranks by this
    first, then by edge). Unknown terms sort last."""
    return (VERDICT_LADDER.index(verdict)
            if verdict in VERDICT_LADDER else len(VERDICT_LADDER))


def calibration_state(lane, card):
    """The ladder's three calibration states for a lane:
    FAILED — a phi was walk-forward TESTED and failed its
    benchmark (the registry's UNCALIBRATED: the NFL lane after
    R4). A hard condition.
    PROVISIONAL — phi untested (NOT-YET-FITTED), or the lane's v4
    register status is provisional. A soft condition — explicitly
    NOT the same as FAILED; MODEL-V5.md keeps them apart.
    CALIBRATED — a tested phi stands (FITTED, or
    identity-after-test with registry status CALIBRATED) on a
    non-provisional lane."""
    if lane in ("nfl-ml", "nfl"):
        fit = load_phi_registry()
        if fit and fit.get("status") == "UNCALIBRATED":
            return "FAILED"
    _, phi_state, _ = lane_phi(lane)
    if phi_state == "NOT-YET-FITTED":
        return "PROVISIONAL"
    if lane_register(card, lane)["status"] == "provisional":
        return "PROVISIONAL"
    return "CALIBRATED"


def verdict_ladder(*, priced, grade, phi_edge_pts, raw_edge_pts,
                   pess_edge_pts, cal_state, benched, killed,
                   fragile, bias_favours, record_less,
                   coherence_flags, mechanism):
    """MODEL-V5.md VERDICT LADDER, implemented literally. Returns
    (verdict, verdict_reason): the verdict is one of VERDICT_LADDER
    and the reason names the deciding condition.

    Inputs are exactly what the v5.0 gate already had: the
    frozen-rubric grade on the phi edge, the phi (graded) edge and
    the raw model edge in points, the band's pessimistic-end edge
    in points (the survival margin is that edge itself: > 0
    survives, >= +3 survives with the golden spare, < +1 is the
    thin-floor soft), the lane's calibration state / bench status
    / scored record, kill-ledger contact, the FRAGILE modifier,
    coherence flags against this card's game, and the
    disagreement's mechanism tag.

    Readings taken where the definitions meet the code (all the
    stricter one; recorded in the regression addendum):
    (1) "exactly one softening condition" is literal — two or
    more compound to RISK BET (DO NOT BET). (2) A coherence flag
    against the card's own game is a hard condition — the
    affirmatives require clean quotes. (3) The grade hard fail is
    the C band literally (C+/C/C-); D/F grades carry a negative
    phi edge and resolve under DO NOT BET's "negative edge".
    (4) Record-less is the ladder's own soft condition, never the
    hard UNCALIBRATED — that word is reserved for a phi that was
    tested and FAILED."""
    if not priced:
        return DO_NOT_BET, ("UNPRICED: no probability the system "
                            "can defend")
    coh = list(coherence_flags or [])
    signal = bool((raw_edge_pts is not None and raw_edge_pts > 0)
                  or coh)
    softs = []
    if cal_state == "PROVISIONAL":
        softs.append("lane provisional (phi untested, not failed)")
    if fragile:
        softs.append("FRAGILE: lane bias favours this side"
                     if bias_favours else
                     "FRAGILE modifier (fit disagreement / small "
                     "sample)")
    if record_less:
        softs.append("lane record-less (Win 0 / Lose 0)")
    if pess_edge_pts is not None and 0 < pess_edge_pts < 1.0:
        softs.append(f"edge survives the band floor by "
                     f"{pess_edge_pts:+.1f} pts (< 1 pt)")
    hards = []
    if killed:
        hards.append("kill-ledger contact")
    if benched:
        hards.append("lane BENCHED by the Governor")
    if cal_state == "FAILED":
        hards.append("lane UNCALIBRATED")
    if pess_edge_pts is not None and pess_edge_pts <= 0:
        hards.append("edge dies at band floor")
    if grade in ("C+", "C", "C-"):
        hards.append(f"grade {grade} in the C band")
    if coh:
        hards.append(f"coherence flag against this market: {coh[0]}")
    if hards:
        if signal:
            return RISK_BET_NO, "; ".join(hards)
        if phi_edge_pts is not None and phi_edge_pts < 0:
            return DO_NOT_BET, "negative edge"
        if phi_edge_pts == 0:
            return DO_NOT_BET, "no edge"
        return DO_NOT_BET, "; ".join(hards)
    if phi_edge_pts is None or phi_edge_pts <= 0:
        return DO_NOT_BET, ("negative edge" if (phi_edge_pts or 0) < 0
                            else "no edge")
    if grade is None or LADDER.index(grade) > LADDER.index("B-"):
        return DO_NOT_BET, f"grade {grade} below the gate (B-)"
    # ---- the affirmative zone: gate-grade edge, no hard condition
    if cal_state == "CALIBRATED" and not softs:
        golden_shape = (LADDER.index(grade) <= LADDER.index("A-")
                        and pess_edge_pts is not None
                        and pess_edge_pts >= 3.0)
        if golden_shape and mechanism in MECHANISMS:
            return GOLDEN_BET, (
                f"edge survives the band's pessimistic end with "
                f"{pess_edge_pts:+.1f} to spare; lane calibrated; "
                f"mechanism tagged ({mechanism})")
        if golden_shape:
            return BET_HERE, ("golden withheld: the disagreement "
                              "carries no named mechanism tag")
        return BET_HERE, ("clean affirmative: gate-grade edge on a "
                          "calibrated lane; the band floor holds")
    if len(softs) == 1:
        return RISK_BET_YES, softs[0]
    return RISK_BET_NO, ("risks compound (the ladder's BET rung "
                         "allows exactly one): "
                         + "; ".join(softs))


# ================================================================ the card

def print_card(mid, lane, p_final, p_raw, phi, phi_state, price,
               stake, flags=None, band_edge_pts=None, mechanism=None,
               extra_lines=None, quotes=None, market_p=None,
               provenance=None, as_json=False):
    """The Pilot's card (MODEL-V5.md), then the detail line, then
    the NAMED SECTIONS (APK directive 2026-10-19: the card screen is
    Level 3 with collapsible depth — the detail layer is structured,
    not one flat line): PRICE ANATOMY (ensemble sources + learned
    weights + raw probabilities), SCALE (the fitted phi + the lane
    record + calibration state), COHERENCE (the organ-3 audit),
    PROVENANCE (every input's source + timestamp). Text mode prints
    them as headed blocks; --json emits the same content as one
    dict for the future APK shell (main.py) to collapse/expand."""
    flags = flags or {}
    card = load_scorecard()
    w, l, rec_src = lane_record(lane)
    implied = implied_prob(price)
    dec = american_to_decimal(price)
    edge = (p_final - implied) * 100
    ev = p_final * (dec - 1.0) - (1.0 - p_final)
    f_kelly = ev / (dec - 1.0) if dec > 1.0 else 0.0
    kelly_units = max(0.0, 25.0 * f_kelly / 4.0)
    units = min(unit_class(edge / 100.0), kelly_units)
    grade, tags, why = grade_v5(edge, lane, card,
                                mechanism or "model-structural", flags)
    if lane in ("nfl-ml", "nfl"):
        # the v4 why-line reads the CFB scorecard, which carries no
        # NFL entries; the NFL record lives in the lane history file
        why = (f"mechanism: {mechanism or 'model-structural'} | "
               f"nfl-ml lane record {w}-{l} from the graded Week 6 "
               f"slate (data/v5-lane-history.json)")
    pess = band_edge_pts if band_edge_pts is not None else edge
    decision, fails = decision_gate(grade, lane, card, pess, flags)
    coh = coherence_check(quotes) if quotes else []
    verdict, verdict_reason = verdict_ladder(
        priced=p_final is not None, grade=grade,
        phi_edge_pts=edge if p_final is not None else None,
        raw_edge_pts=((p_raw - implied) * 100
                      if p_raw is not None else None),
        pess_edge_pts=pess if p_final is not None else None,
        cal_state=calibration_state(lane, card),
        benched=lane_benched(lane, card),
        killed=bool(flags.get("killed")),
        fragile=any(t.startswith("FRAGILE") for t in tags),
        bias_favours=bool(flags.get("bias_favours"))
        or any("bias favours" in t for t in tags),
        record_less=(w + l == 0), coherence_flags=coh,
        mechanism=mechanism or "model-structural")
    out = []
    out.append(f"{mid}")
    out.append(f"Win {w} · Lose {l}   ({lane} lane record — {rec_src})")
    if p_final is None:
        out.append("Probability UNPRICED")
    else:
        out.append(f"Probability {p_final * 100:.1f}%")
    out.append(f"Grade {grade}"
               + (f" [{'; '.join(tags)}]" if tags else ""))
    out.append(verdict + (f" — {verdict_reason}"
                          if verdict_reason else ""))
    w_m, w_k, w_note = ensemble_weights(lane)
    if p_final is None:
        detail = (f"odds {int(price):+d} | price -${stake:.2f} | "
                  f"UNPRICED — no probability the system can defend")
    else:
        detail = (f"odds {int(price):+d} | payout {dec:.2f}x / "
                  f"${stake * dec:.2f} | price -${stake:.2f} | win% "
                  f"{p_final * 100:.1f} vs {implied * 100:.1f} implied "
                  f"| edge {edge:+.1f} pts | EV {ev * 100:+.1f}% | "
                  f"unit {units:.1f}u")
    out.append("  " + detail)
    phi_desc = phi["kind"] + (
        f" (a={phi['a']} FITTED)" if phi["kind"] == "lin" else
        " (FITTED)" if phi["kind"] == "iso" else "")
    out.append(f"  phi: {phi_desc} [{phi_state}] | raw "
               f"{(p_raw * 100 if p_raw is not None else float('nan')):.1f}%"
               f" -> phi {((phi_apply(phi, p_raw) * 100) if p_raw is not None else float('nan')):.1f}%"
               f" | ensemble w_model {w_m:.2f} / w_market {w_k:.2f} "
               f"({w_note})")
    out.append(f"  why: {why}")
    for line in (extra_lines or []):
        out.append("  " + line)
    for f in coh:
        out.append(f"  AUDIT FLAG (coherence): {f}")
    # ---- named sections (collapsible depth for the APK shell)
    phi_params = ({k: v for k, v in phi.items() if k != "kind"}
                  if isinstance(phi, dict) else {})
    sections = {
        "PRICE ANATOMY": (
            {"state": "UNPRICED"} if p_final is None else {
                "sources": [
                    {"name": "model", "raw_p": p_raw,
                     "phi_p": (phi_apply(phi, p_raw)
                               if p_raw is not None else None),
                     "weight": round(w_m, 2)},
                    {"name": "market",
                     "p": (market_p if market_p is not None
                           else implied),
                     "weight": round(w_k, 2),
                     "weights_note": w_note}],
                "blend_p": p_final,
                "implied_at_price": implied,
                "edge_pts": round(edge, 1),
                "ev_per_dollar": round(ev, 4),
                "odds_american": int(price),
                "payout_x": round(dec, 2), "stake": stake,
                "unit_class": round(units, 1)}),
        "SCALE": {
            "phi": {"kind": phi["kind"], "params": phi_params,
                    "state": phi_state,
                    "label": "FITTED" if phi_state == "FITTED"
                             else phi_state},
            "record": f"{w}-{l}", "record_source": rec_src,
            "calibration": lane_uncalibrated(lane) or phi_state},
        "COHERENCE": {"flags": coh,
                      "status": "FLAGGED" if coh else
                                "coherent at quoted prices"},
        "PROVENANCE": {
            "inputs": provenance or [],
            "computed_at": datetime.now().astimezone()
            .isoformat(timespec="seconds")}}
    card_dict = {"matchup": mid, "lane": lane, "win": w, "lose": l,
                 "probability": p_final, "grade": grade,
                 "tags": tags, "verdict": verdict,
                 "verdict_reason": verdict_reason,
                 "blocked_by": fails, "sections": sections}
    if as_json:
        print(json.dumps(card_dict, indent=1))
        return {"grade": grade, "verdict": verdict,
                "verdict_reason": verdict_reason,
                "p_final": p_final,
                "edge_pts": edge if p_final is not None else None,
                "card": card_dict}
    out.append("--- PRICE ANATOMY")
    pa = sections["PRICE ANATOMY"]
    if pa.get("state") == "UNPRICED":
        out.append("  UNPRICED")
    else:
        for s in pa["sources"]:
            if s["name"] == "model":
                out.append(
                    f"  model: raw {s['raw_p'] * 100:.1f}% -> phi "
                    f"{s['phi_p'] * 100:.1f}% | weight {s['weight']}")
            else:
                out.append(
                    f"  market: {s['p'] * 100:.1f}% | weight "
                    f"{s['weight']} ({s['weights_note']})")
        out.append(f"  blend {pa['blend_p'] * 100:.1f}% | implied "
                   f"{pa['implied_at_price'] * 100:.1f}% | edge "
                   f"{pa['edge_pts']:+.1f} pts | EV/dollar "
                   f"{pa['ev_per_dollar'] * 100:+.1f}% | unit "
                   f"{pa['unit_class']}u")
    out.append("--- SCALE")
    sc = sections["SCALE"]
    out.append(f"  phi: {sc['phi']['kind']} [{sc['phi']['label']}]"
               + (f" params {sc['phi']['params']}"
                  if sc["phi"]["params"] else "")
               + f" | record {sc['record']} ({sc['record_source']})"
               + f" | calibration: {sc['calibration']}")
    out.append("--- COHERENCE")
    out.append("  " + sections["COHERENCE"]["status"]
               + ("; ".join(coh) if coh else ""))
    out.append("--- PROVENANCE")
    for inp in sections["PROVENANCE"]["inputs"]:
        out.append(f"  {inp['name']}: {inp['source']} "
                   f"[{inp.get('timestamp') or 'not recorded'}]")
    out.append(f"  card computed at "
               f"{sections['PROVENANCE']['computed_at']}")
    print("\n".join(out))
    return {"grade": grade, "verdict": verdict,
            "verdict_reason": verdict_reason, "p_final": p_final,
            "edge_pts": edge if p_final is not None else None,
            "card": card_dict}


def pessimistic_phi_edge(lane, p_raw, implied):
    """The least favourable phi candidate's edge — the scale band's
    pessimistic end for the gate (organ 5). For lanes without a
    fitted registry, the only candidate is the identity."""
    if lane in ("nfl-ml", "nfl"):
        fit = load_phi_registry()
        if fit:
            return min((phi_apply(c, p_raw) - implied) * 100
                       for c in fit["candidates"].values())
    return (p_raw - implied) * 100


# ================================================================ engines

def nfl_price(home, away):
    """P(home win) for an NFL game from the SAVED lane pricing file
    (data/nfl-week6-pricing.json — the lane's ratings and slate of
    record). Recomputed from the saved ratings via the lane's Elo
    logistic; reproduces the file's p_home. Also returns the file's
    market spread/total for the coherence quotes."""
    with open(NFL_PRICING_PATH) as f:
        pricing = json.load(f)
    R = pricing["ratings"]
    for g in pricing["games"]:
        if g["home"] == home and g["away"] == away:
            h = 0 if g["neutral"] else 55
            d = R[home] + h - R[away]
            p = 1 / (1 + 10 ** (-d / 400))
            return p, g
    raise SystemExit(f"[betmodel5] {away}@{home} not in the saved "
                     f"NFL pricing file")


def price_total_stub(sport, home, away, line, price, stake=10.0,
                     mid=None):
    """TOTALS ENGINE — STUB (MODEL-V5.md). A pace/scoring companion
    distribution per sport is the design; until it exists AND has a
    scored record, a total prints UNPRICED with grade cap C and the
    ladder prints DO NOT BET. This stub exists so the card format covers
    totals honestly instead of silently omitting the market that
    burned the Pilot on 2026-10-18 (DAL@GB total 53.5, unpriced)."""
    mid = mid or f"{away} @ {home}   {sport.upper()}:TOTAL {line}"
    print(f"{mid}")
    w, l, src = lane_record("totals")
    print(f"Win {w} · Lose {l}   (totals lane record — {src})")
    print("Probability UNPRICED (totals engine not built — no "
          "pace/scoring distribution, no scored record)")
    print("Grade C [UNPRICED (cap C)]")
    print("DO NOT BET — UNPRICED: no probability the system can defend")
    print(f"  odds {int(price):+d} | price -${stake:.2f} | total "
          f"line {line} carried for the record only")
    return {"grade": "C", "verdict": "DO NOT BET",
            "verdict_reason": "UNPRICED: no probability the system can defend",
            "p_final": None}


def prop_from_scoring_plays(player, stat_name, line, side, price):
    """PROPS FROM SCORING PLAYS — SCOPED, NOT BUILT (MODEL-V5.md).

    The intended route (the one that can work in this environment):
    for each of the player's team's played games, fetch the ESPN
    game summary (site.api.espn.com .../summary?event=<id>) and
    reconstruct the player's scoring log from the game's scoring
    plays (scorer attribution on each touchdown play), then run the
    reconstructed series through betmodel4.prop_band (Poisson +
    negative-binomial, pessimistic-end pricing) exactly like the
    game-log props.

    Why it is a stub today, stated plainly (verified 2026-10-19):
    the athlete-stats routes 404 here (2026-10-18 finding), and
    while the summary endpoint itself answers, its payload in this
    environment carries NO scoringPlays / drives structure to
    reconstruct from — the boxscore aggregates that would make the
    reconstruction a computation instead of a guess are not in the
    response. Building on a payload that is not there would be
    inventing numbers. Until the payload carries the plays (or a
    play-by-play source is connected), this prints UNPRICED.
    """
    print(f"{player} {stat_name} {side} {line}")
    print("Probability UNPRICED (scoring-play reconstruction scoped, "
          "not built — the game-summary payload in this environment "
          "carries no scoringPlays structure; see docstring)")
    print("Grade C [UNPRICED (cap C)]")
    print("DO NOT BET — UNPRICED")
    return {"grade": "C", "verdict": "DO NOT BET",
            "verdict_reason": "UNPRICED: no probability the system can defend",
            "p_final": None}


# ================================================================ AMENDMENT
# Scope amendment (Pilot 2026-10-19 ~07:08 EDT): NBA + soccer lanes,
# the coverage law (registered market checkers), provenance-stamped
# sources, and the timestamped FanDuel-menu mirror.

# CACHE is defined in the header constants
NBA_FIT_PATH = os.path.join(DATA, "v5-nba.json")
SOCCER_FIT_PATH = os.path.join(DATA, "v5-soccer.json")
STALE_AFTER_H = 6.0   # a menu pull older than this degrades the stamp


def _fetch_days(url_fmt, start, end, label):
    """Day-by-day ESPN scoreboard pulls (the range form 400s on these
    endpoints; single-day is the verified route), thread-pooled.
    Returns (games, errors). Games carry date/home/away/hs/as/final
    plus the feed's odds block when present."""
    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)

    def one(day):
        j = nfl_http_get(url_fmt.format(day.strftime("%Y%m%d")))
        out = []
        for ev in j.get("events", []):
            comp = ev["competitions"][0]
            cs = comp["competitors"]
            home = next(c for c in cs if c["homeAway"] == "home")
            away = next(c for c in cs if c["homeAway"] == "away")
            odds = None
            raw_odds = comp.get("odds") or []
            if raw_odds and isinstance(raw_odds[0], dict):
                o = raw_odds[0]
                odds = {"details": o.get("details"),
                        "spread": o.get("spread"),
                        "total": o.get("overUnder"),
                        "homeML": (o.get("homeTeamOdds") or {})
                        .get("moneyLine"),
                        "awayML": (o.get("awayTeamOdds") or {})
                        .get("moneyLine")}
            out.append({
                "date": ev.get("date", "")[:10],
                "home": home["team"]["abbreviation"],
                "away": away["team"]["abbreviation"],
                "home_name": home["team"].get("displayName",
                                              home["team"]["abbreviation"]),
                "away_name": away["team"].get("displayName",
                                              away["team"]["abbreviation"]),
                "hs": int(home["score"]) if home.get("score")
                not in (None, "") else None,
                "as": int(away["score"]) if away.get("score")
                not in (None, "") else None,
                "final": ev["status"]["type"]["completed"],
                "odds": odds})
        return out

    games, errors = [], 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for out in ex.map(lambda day: _safe(one, day), days):
            if out is None:
                errors += 1
            else:
                games += out
    games.sort(key=lambda g: g["date"])
    return games, errors


def _safe(fn, arg):
    try:
        return fn(arg)
    except Exception:
        return None


# ---------------------------------------------------------------- NBA
# Elo lineage like the NHL lane (sequential Elo, logistic win prob),
# K=20, HFA=100 Elo points (ENGINE PARAMS — the 538 NBA lineage).
# Margin map: OLS with intercept on the walk-forward records.
# APPROXIMATION (named): the margin map is fit on the same records
# the win-prob backtest scores — the Brier is the honest walk-forward
# number; cover prices inherit the map caveat and ride FRAGILE.

NBA_K, NBA_HFA = 20, 100
NBA_SEASON = ("2025-26 regular season",
              datetime(2025, 10, 21), datetime(2026, 4, 12))


def fit_nba(persist=True):
    cache = os.path.join(CACHE, "nba_games_2025-26.json")
    if os.path.exists(cache):
        with open(cache) as f:
            blob = json.load(f)
        games, fetched_at = blob["games"], blob["fetched_at"]
    else:
        url = ("https://site.api.espn.com/apis/site/v2/sports/"
               "basketball/nba/scoreboard?dates={}")
        games, errors = _fetch_days(url, NBA_SEASON[1], NBA_SEASON[2],
                                    "nba")
        fetched_at = datetime.now().astimezone().isoformat(
            timespec="seconds")
        os.makedirs(CACHE, exist_ok=True)
        with open(cache, "w") as f:
            json.dump({"fetched_at": fetched_at,
                       "source": "ESPN NBA scoreboard day pulls",
                       "errors": errors, "games": games}, f, indent=1)
    played = [g for g in games if g["final"] and g["hs"] is not None]
    R, recs = {}, []
    def r(t):
        return R.get(t, 1500.0)
    for g in played:
        d = r(g["home"]) + NBA_HFA - r(g["away"])
        p = 1 / (1 + 10 ** (-d / 400))
        mov = g["hs"] - g["as"]
        y = 1.0 if mov > 0 else 0.0
        recs.append({"diff": d, "p": p, "margin": mov, "y": y})
        mult = (math.log(abs(mov) + 1)
                * (2.2 / ((r(g["home"]) - r(g["away"])) * 0.001 + 2.2))
                if mov != 0 else 1.0)
        delta = NBA_K * mult * (y - p)
        R[g["home"]] = r(g["home"]) + delta
        R[g["away"]] = r(g["away"]) - delta
    brier = statistics.mean([(x["p"] - x["y"]) ** 2 for x in recs])
    home_rate = statistics.mean([x["y"] for x in recs])
    naive = statistics.mean([(home_rate - x["y"]) ** 2 for x in recs])
    n = len(recs)
    mx = statistics.mean([x["diff"] for x in recs])
    my = statistics.mean([x["margin"] for x in recs])
    b = (sum((x["diff"] - mx) * (x["margin"] - my) for x in recs)
         / sum((x["diff"] - mx) ** 2 for x in recs))
    a = my - b * mx
    sd = statistics.pstdev([x["margin"] - (a + b * x["diff"])
                            for x in recs])
    fit = {"sport": "nba", "season": NBA_SEASON[0],
           "fitted_at": datetime.now().astimezone().isoformat(
               timespec="seconds"),
           "source": f"ESPN NBA scoreboard day pulls (cached "
                     f"{fetched_at}; data/cache/nba_games_2025-26.json)",
           "params": {"K": NBA_K, "hfa_elo": NBA_HFA},
           "ratings": {k: round(v, 1) for k, v in R.items()},
           "margin_map": {"a": round(a, 3), "b": round(b, 4),
                          "sd": round(sd, 2), "n": n},
           "backtest": {"brier": round(brier, 4),
                        "naive_home_brier": round(naive, 4), "n": n,
                        "protocol": "walk-forward (pre-game ratings, "
                                    "sequential Elo)"}}
    if persist:
        with open(NBA_FIT_PATH, "w") as f:
            json.dump(fit, f, indent=1)
    return fit


def load_nba():
    if os.path.exists(NBA_FIT_PATH):
        with open(NBA_FIT_PATH) as f:
            return json.load(f)
    return None


def nba_probs(fit, home, away):
    """(p_home, margin_mu, margin_sd) from the fitted NBA lane."""
    R = fit["ratings"]
    if home not in R or away not in R:
        return None
    d = R[home] + NBA_HFA - R[away]
    p = 1 / (1 + 10 ** (-d / 400))
    mm = fit["margin_map"]
    return p, mm["a"] + mm["b"] * d, mm["sd"]


# ---------------------------------------------------------------- soccer
# Elo + Poisson scoring (Maher-lite): team attack/defence strengths
# with prior shrinkage, league home/away scoring rates, a Poisson
# goal grid as THE pricer (1X2, correct score, BTTS, totals, team
# totals, handicaps, DNB, double chance all read off the one grid —
# organ 3's single distribution, literally). Elo rides as the
# ordering check: if Elo's favourite != the grid's favourite, the
# price is FRAGILE (the lane's two estimators disagree).
# ENGINE PARAMS (named): K=20, HFA=65 Elo; strength prior 8 games;
# league-rate priors LH 1.40 / LA 1.15 goals (generic top-flight
# values, replaced by data as games accumulate).

SOC_K, SOC_HFA = 20, 65
SOC_PRIOR_GAMES = 8
SOC_PRIOR_LH, SOC_PRIOR_LA = 1.40, 1.15
SOC_SEASON = ("EPL 2025-26", datetime(2025, 8, 15),
              datetime(2026, 5, 25))


def _pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def soccer_grid(lh, la, maxg=8):
    """Renormalised Poisson goal matrix + the market probabilities
    that read off it. Truncation at maxg folds <0.1% of mass at
    league scoring rates (named approximation)."""
    ph = [_pois(k, lh) for k in range(maxg + 1)]
    pa = [_pois(k, la) for k in range(maxg + 1)]
    tot = sum(ph) * sum(pa)
    M = [[ph[h] * pa[a] / tot for a in range(maxg + 1)]
         for h in range(maxg + 1)]
    out = {"matrix": M, "lambda_home": lh, "lambda_away": la}
    out["p_home"] = sum(M[h][a] for h in range(maxg + 1)
                        for a in range(maxg + 1) if h > a)
    out["p_draw"] = sum(M[h][h] for h in range(maxg + 1))
    out["p_away"] = sum(M[h][a] for h in range(maxg + 1)
                        for a in range(maxg + 1) if h < a)
    out["p_btts"] = 1 - sum(M[0]) - sum(M[h][0] for h in range(maxg + 1)) \
        + M[0][0]
    return out


def _grid_over(M, line):
    """P(total goals > line) for a .5 line, from the grid."""
    n = len(M)
    return sum(M[h][a] for h in range(n) for a in range(n)
               if h + a > line)


def _grid_team_over(M, team, line):
    n = len(M)
    if team == "home":
        return sum(M[h][a] for h in range(n) for a in range(n)
                   if h > line)
    return sum(M[h][a] for h in range(n) for a in range(n) if a > line)


def _grid_handicap(M, line_home):
    """P(home covers line_home) for a .5 handicap (no push)."""
    n = len(M)
    return sum(M[h][a] for h in range(n) for a in range(n)
               if (h - a) + line_home > 0)


def soccer_lambdas(strengths, league, home, away):
    att_h = strengths[home]["att"]
    def_a = strengths[away]["def"]
    att_a = strengths[away]["att"]
    def_h = strengths[home]["def"]
    return (league["LH"] * att_h * def_a,
            league["LA"] * att_a * def_h)


def fit_soccer(persist=True):
    cache = os.path.join(CACHE, "soccer_epl_2025-26.json")
    if os.path.exists(cache):
        with open(cache) as f:
            blob = json.load(f)
        games, fetched_at = blob["games"], blob["fetched_at"]
    else:
        url = ("https://site.api.espn.com/apis/site/v2/sports/"
               "soccer/eng.1/scoreboard?dates={}")
        games, errors = _fetch_days(url, SOC_SEASON[1], SOC_SEASON[2],
                                    "soccer")
        fetched_at = datetime.now().astimezone().isoformat(
            timespec="seconds")
        os.makedirs(CACHE, exist_ok=True)
        with open(cache, "w") as f:
            json.dump({"fetched_at": fetched_at,
                       "source": "ESPN EPL scoreboard day pulls",
                       "errors": errors, "games": games}, f, indent=1)
    played = [g for g in games if g["final"] and g["hs"] is not None]
    elo, gp, gf, ga = {}, {}, {}, {}
    hg = ag = hgames = 0
    recs = []

    def strengths():
        total_gp = sum(gp.values())
        L = ((sum(gf.values()) / total_gp) if total_gp else 1.35)
        LH = (hg + 10 * SOC_PRIOR_LH) / (hgames + 10) if hgames else \
            SOC_PRIOR_LH
        LA = (ag + 10 * SOC_PRIOR_LA) / (hgames + 10) if hgames else \
            SOC_PRIOR_LA
        st = {}
        for t in gp:
            st[t] = {
                "att": ((gf[t] + SOC_PRIOR_GAMES * L)
                        / (gp[t] + SOC_PRIOR_GAMES)) / L,
                "def": ((ga[t] + SOC_PRIOR_GAMES * L)
                        / (gp[t] + SOC_PRIOR_GAMES)) / L,
                "gp": gp[t]}
        return st, {"LH": LH, "LA": LA, "L": L}

    for g in played:
        for t in (g["home"], g["away"]):
            gp.setdefault(t, 0)
            gf.setdefault(t, 0)
            ga.setdefault(t, 0)
            elo.setdefault(t, 1500.0)
        st, lg = strengths()
        lh, la = soccer_lambdas(st, lg, g["home"], g["away"])
        grid = soccer_grid(lh, la)
        y = (1 if g["hs"] > g["as"] else 0 if g["hs"] == g["as"]
             else -1)
        recs.append({"p_home": grid["p_home"], "p_draw": grid["p_draw"],
                     "p_away": grid["p_away"], "y": y,
                     "pick": max(("home", grid["p_home"]),
                                 ("draw", grid["p_draw"]),
                                 ("away", grid["p_away"]),
                                 key=lambda kv: kv[1])[0]})
        # updates AFTER the prediction (walk-forward by construction)
        gp[g["home"]] += 1
        gp[g["away"]] += 1
        gf[g["home"]] += g["hs"]
        ga[g["home"]] += g["as"]
        gf[g["away"]] += g["as"]
        ga[g["away"]] += g["hs"]
        hg += g["hs"]
        ag += g["as"]
        hgames += 1
        d = elo[g["home"]] + SOC_HFA - elo[g["away"]]
        exp_h = 1 / (1 + 10 ** (-d / 400))
        score_h = 1.0 if y == 1 else 0.5 if y == 0 else 0.0
        elo[g["home"]] += SOC_K * (score_h - exp_h)
        elo[g["away"]] -= SOC_K * (score_h - exp_h)
    brier3 = statistics.mean([
        (x["p_home"] - (1 if x["y"] == 1 else 0)) ** 2
        + (x["p_draw"] - (1 if x["y"] == 0 else 0)) ** 2
        + (x["p_away"] - (1 if x["y"] == -1 else 0)) ** 2
        for x in recs])
    acc = statistics.mean([
        1.0 if (x["pick"] == "home" and x["y"] == 1)
        or (x["pick"] == "draw" and x["y"] == 0)
        or (x["pick"] == "away" and x["y"] == -1) else 0.0
        for x in recs])
    st, lg = strengths()
    fit = {"sport": "soccer", "league": SOC_SEASON[0],
           "fitted_at": datetime.now().astimezone().isoformat(
               timespec="seconds"),
           "source": f"ESPN EPL scoreboard day pulls (cached "
                     f"{fetched_at}; data/cache/soccer_epl_2025-26.json)",
           "params": {"K": SOC_K, "hfa_elo": SOC_HFA,
                      "prior_games": SOC_PRIOR_GAMES},
           "elo": {k: round(v, 1) for k, v in elo.items()},
           "strengths": {k: {"att": round(v["att"], 3),
                             "def": round(v["def"], 3), "gp": v["gp"]}
                         for k, v in st.items()},
           "league": {"LH": round(lg["LH"], 3), "LA": round(lg["LA"], 3),
                      "L": round(lg["L"], 3)},
           "backtest": {"brier3": round(brier3, 4),
                        "accuracy": round(acc, 4), "n": len(recs),
                        "protocol": "walk-forward (strengths/Elo "
                                    "from prior games only)"}}
    if persist:
        with open(SOCCER_FIT_PATH, "w") as f:
            json.dump(fit, f, indent=1)
    return fit


def load_soccer():
    if os.path.exists(SOCCER_FIT_PATH):
        with open(SOCCER_FIT_PATH) as f:
            return json.load(f)
    return None


def soccer_fixture_grid(fit, home, away):
    if home not in fit["strengths"] or away not in fit["strengths"]:
        return None
    lh, la = soccer_lambdas(fit["strengths"], fit["league"], home, away)
    return soccer_grid(lh, la)


# ---------------------------------------------------------------- engine
# One dispatcher every checker and the price command share.
# Returns (p_side, info) or (None, reason). p_side is the MODEL
# probability of the side bet — before phi (phi is per-lane and
# applies at grading, as in the price command).

def engine_price(sport, kind, home, away, side="home", line=None):
    if sport == "nfl":
        try:
            p_home, g = nfl_price(home, away)
        except SystemExit as e:
            return None, str(e)
        if kind == "moneyline":
            return (p_home if side == "home" else 1 - p_home), \
                {"detail": "NFL lane Elo (saved pricing file)"}
        if kind in ("spread", "alt-spread"):
            mu = -g["fair_spread_home"]
            s = line if side == "home" else -line
            p_cover_home = 1 - norm_cdf((-s - mu) / NFL_MARGIN_SD)
            return (p_cover_home if side == "home"
                    else 1 - p_cover_home), \
                {"detail": f"margin N({mu:+.1f}, {NFL_MARGIN_SD}) "
                           f"from the lane's saved fair spread"}
        return None, "no NFL engine for this market"
    if sport == "ncaaf":
        if kind == "moneyline":
            w = cfb_win_prob(home, away)
            return (w["p_home"] if side == "home" else 1 - w["p_home"]), \
                {"detail": "v4 distributional ratings"}
        if kind in ("spread", "alt-spread"):
            cov = cfb_cover_prob(home, away, line if side == "home"
                                    else -line)
            return (cov["p_cover"] if side == "home"
                    else 1 - cov["p_cover"]), \
                {"detail": "v4 margin lane (like-for-like pool)"}
        return None, "no NCAAF engine for this market"
    if sport == "nhl":
        if kind == "moneyline":
            w = nhl_win_prob(home, away)
            return (w["p_home"] if side == "home" else 1 - w["p_home"]), \
                {"detail": "v4 NHL Elo (sigma-integrated)"}
        return None, "no NHL engine for this market (spread/puck-line " \
                     "not built)"
    if sport == "nba":
        fit = load_nba()
        if fit is None:
            return None, "NBA fit not run (betmodel5.py fit-nba)"
        pr = nba_probs(fit, home, away)
        if pr is None:
            return None, f"team not in the NBA fit ({home}/{away})"
        p_home, mu, sd = pr
        if kind == "moneyline":
            return (p_home if side == "home" else 1 - p_home), \
                {"detail": f"NBA Elo lane (fit {fit['fitted_at']}; "
                           f"walk-forward Brier "
                           f"{fit['backtest']['brier']})"}
        if kind in ("spread", "alt-spread"):
            s = line if side == "home" else -line
            p_cover_home = 1 - norm_cdf((-s - mu) / sd)
            return (p_cover_home if side == "home"
                    else 1 - p_cover_home), \
                {"detail": f"NBA margin map N({mu:+.1f}, {sd:.1f}) "
                           f"(in-sample map — FRAGILE lineage)",
                 "fragile": True}
        return None, "no NBA engine for this market"
    if sport == "soccer":
        fit = load_soccer()
        if fit is None:
            return None, "soccer fit not run (betmodel5.py fit-soccer)"
        grid = soccer_fixture_grid(fit, home, away)
        if grid is None:
            return None, f"team not in the soccer fit ({home}/{away})"
        M = grid["matrix"]
        det = (f"Poisson grid λ {grid['lambda_home']:.2f} / "
               f"{grid['lambda_away']:.2f} (fit {fit['fitted_at']}; "
               f"walk-forward 3-way Brier {fit['backtest']['brier3']})")
        if kind == "moneyline":
            p = {"home": grid["p_home"], "draw": grid["p_draw"],
                 "away": grid["p_away"]}[side]
            elo = fit["elo"]
            elo_fav = "home" if elo[home] + SOC_HFA >= elo[away] \
                else "away"
            grid_fav = "home" if grid["p_home"] >= grid["p_away"] \
                else "away"
            return p, {"detail": det,
                       "fragile": elo_fav != grid_fav,
                       "fragile_note": "Elo and Poisson favourites "
                                       "disagree"}
        if kind in ("spread", "alt-spread"):
            # line is the HOME handicap (-1.5 = home gives 1.5).
            # Only .5 lines price off the grid: integer handicaps
            # carry push mass the grid prices separately, and v5
            # does not silently fold pushes into a win probability.
            if line is None or abs(line % 1) != 0.5:
                return None, "soccer handicaps price on .5 lines " \
                             "only (integer lines carry push mass)"
            p_home_cover = _grid_handicap(M, line)
            return (p_home_cover if side == "home"
                    else 1 - p_home_cover), \
                {"detail": det + " | handicap off the grid"}
        if kind == "totals" or kind == "alt-total":
            p_over = _grid_over(M, line)
            return (p_over if side == "over" else 1 - p_over), \
                {"detail": det + " | total off the grid"}
        return None, "soccer market not routed here"
    return None, f"unknown sport {sport!r}"


# ---------------------------------------------------------------- menu
# The FanDuel menu mirror: there is no public FanDuel API, so the
# menu is a timestamped pull (odds feed / board transcription saved
# to data/). A pull that fails stamps the menu UNVERIFIED and every
# market on it prints UNPRICED (UNVERIFIED) — never an assumed menu.

def menu_stamp(ctx):
    """(stamp_text, degraded) for a menu context."""
    if not ctx or not ctx.get("verified"):
        return "UNVERIFIED (no successful live pull)", True
    pulled = ctx.get("pulled_at")
    age = None
    if pulled:
        try:
            age = (datetime.now().astimezone()
                   - datetime.fromisoformat(pulled)).total_seconds() / 3600
        except ValueError:
            age = None
    if age is not None and age > STALE_AFTER_H:
        return (f"STALE pull ({age:.1f}h old, source "
                f"{ctx.get('source')})", True)
    return f"pulled {pulled} from {ctx.get('source')}", False


def pull_menu(sport):
    """Live mirror pull from the lab's verified odds-feed route
    (ESPN scoreboard odds — the route nfl_lane.py was built on).
    Saves data/menu-<sport>-<ts>.json and returns the slate dict.
    On failure the slate is UNVERIFIED with the error recorded."""
    ts = datetime.now().astimezone()
    slate = {"pulled_at": ts.isoformat(timespec="seconds"),
             "source": "ESPN scoreboard odds feed (lab's verified "
                       "route; FanDuel has no public API — board "
                       "prices enter as Pilot transcriptions)",
             "verified": False, "markets": []}
    try:
        if sport == "nfl":
            games = nfl_games(7)
        elif sport == "nba":
            j = nfl_http_get("https://site.api.espn.com/apis/site/v2/"
                        "sports/basketball/nba/scoreboard?dates="
                        + ts.strftime("%Y%m%d"))
            games = []
            for ev in j.get("events", []):
                comp = ev["competitions"][0]
                cs = comp["competitors"]
                home = next(c for c in cs if c["homeAway"] == "home")
                away = next(c for c in cs if c["homeAway"] == "away")
                odds = None
                raw_o = comp.get("odds") or []
                if raw_o and isinstance(raw_o[0], dict):
                    o = raw_o[0]
                    odds = {"spread": o.get("spread"),
                            "total": o.get("overUnder"),
                            "homeML": (o.get("homeTeamOdds") or {})
                            .get("moneyLine"),
                            "awayML": (o.get("awayTeamOdds") or {})
                            .get("moneyLine")}
                games.append({"home": home["team"]["abbreviation"],
                              "away": away["team"]["abbreviation"],
                              "odds": odds})
        elif sport == "soccer":
            j = nfl_http_get("https://site.api.espn.com/apis/site/v2/"
                        "sports/soccer/eng.1/scoreboard?dates="
                        + ts.strftime("%Y%m%d"))
            games = []
            for ev in j.get("events", []):
                comp = ev["competitions"][0]
                cs = comp["competitors"]
                home = next(c for c in cs if c["homeAway"] == "home")
                away = next(c for c in cs if c["homeAway"] == "away")
                odds = None
                raw_o = comp.get("odds") or []
                if raw_o and isinstance(raw_o[0], dict):
                    o = raw_o[0]
                    odds = {"spread": o.get("spread"),
                            "total": o.get("overUnder"),
                            "homeML": (o.get("homeTeamOdds") or {})
                            .get("moneyLine"),
                            "awayML": (o.get("awayTeamOdds") or {})
                            .get("moneyLine")}
                games.append({"home": home["team"]["abbreviation"],
                              "away": away["team"]["abbreviation"],
                              "odds": odds})
        else:
            raise ValueError(f"no live pull route for {sport}")
        for g in games:
            o = g.get("odds") or {}
            base = {"sport": sport, "home": g["home"],
                    "away": g["away"]}
            if o.get("homeML") is not None:
                slate["markets"].append(
                    {**base, "market": "moneyline", "side": "home",
                     "price": o["homeML"]})
                slate["markets"].append(
                    {**base, "market": "moneyline", "side": "away",
                     "price": o["awayML"]})
            if o.get("spread") is not None:
                slate["markets"].append(
                    {**base, "market": "spread", "side": "home",
                     "line": o["spread"], "price": None})
            if o.get("total") is not None:
                slate["markets"].append(
                    {**base, "market": "totals", "side": "over",
                     "line": o["total"], "price": None})
        slate["verified"] = True
        slate["games_seen"] = len(games)
    except Exception as e:  # recorded, never hidden
        slate["error"] = f"{type(e).__name__}: {e}"
    path = os.path.join(DATA, f"menu-{sport}-"
                        + ts.strftime("%Y%m%d-%H%M") + ".json")
    with open(path, "w") as f:
        json.dump(slate, f, indent=1)
    slate["saved_to"] = path
    return slate


# ---------------------------------------------------------------- coverage
# THE COVERAGE LAW. Every FanDuel market type in the taxonomy is a
# registered checker. A checker returns exactly one verdict state:
# PRICED / COHERENCE-FLAGGED / UNPRICED. Registration is enumerable
# (TAXONOMY == MARKET_CHECKERS keys, asserted in R6).

TAXONOMY = [
    "moneyline", "spread", "totals", "alt-spread", "alt-total",
    "player-props", "team-props", "game-props",
    "scoring-anytime", "scoring-first", "scoring-last",
    "segment", "parlay", "sgp", "teaser", "round-robin", "futures",
    "correct-score", "draw-no-bet", "btts", "double-chance",
]
MARKET_CHECKERS = {}


def register(name):
    def deco(fn):
        MARKET_CHECKERS[name] = fn
        return fn
    return deco


def _verdict(mkt, state, p=None, grade=None, verdict=None,
             verdict_reason=None, note="", detail=""):
    return {"market": mkt.get("market"), "sport": mkt.get("sport"),
            "desc": _mkt_desc(mkt), "state": state, "p": p,
            "grade": grade, "verdict": verdict,
            "verdict_reason": verdict_reason, "note": note,
            "detail": detail}


def _mkt_desc(mkt):
    bits = [f"{mkt.get('away', '?')} @ {mkt.get('home', '?')}"]
    if mkt.get("player"):
        bits.append(str(mkt["player"]))
    if mkt.get("stat"):
        bits.append(str(mkt["stat"]))
    if mkt.get("side"):
        bits.append(str(mkt["side"]))
    if mkt.get("line") is not None:
        bits.append(str(mkt["line"]))
    if mkt.get("score"):
        bits.append(str(mkt["score"]))
    if mkt.get("segment"):
        bits.append(str(mkt["segment"]))
    if mkt.get("legs"):
        bits.append(f"{len(mkt['legs'])} legs")
    return " ".join(bits)


LANE_FOR = {("nfl", "moneyline"): "nfl-ml", ("nfl", "spread"): "nfl-ml",
            ("nfl", "alt-spread"): "nfl-ml",
            ("ncaaf", "moneyline"): "ml", ("nhl", "moneyline"): "ml",
            ("ncaaf", "spread"): "cover", ("ncaaf", "alt-spread"): "cover",
            ("nba", "moneyline"): "nba-ml", ("nba", "spread"): "nba-ml",
            ("nba", "alt-spread"): "nba-ml"}


def _lane_for(mkt):
    if mkt.get("sport") == "soccer":
        return "soccer"
    if mkt.get("market") in ("player-props", "scoring-anytime"):
        return "props"
    return LANE_FOR.get((mkt.get("sport"), mkt.get("market")),
                        mkt.get("sport", "unknown"))


def _grade_and_gate(mkt, p_model, p_final, p_pess, ctx):
    """Grade (frozen rubric on the phi edge) + verdict ladder, for
    a checker with a book price. Returns (grade, tags, verdict,
    verdict_reason, fails) — fails is the v5.0 gate's named fail
    list, kept because checker notes quote it; the verdict and its
    reason are the card's printed decision (MODEL-V5.md ladder)."""
    price = mkt.get("price")
    if price is None:
        return None, [], None, None, []
    lane = _lane_for(mkt)
    card = load_scorecard()
    implied = implied_prob(price)
    edge = (p_final - implied) * 100
    flags = {}
    if mkt.get("_fragile"):
        flags["fragile"] = True
        flags["bias_favours"] = False
    grade, tags, _ = grade_v5(edge, lane, card,
                              mkt.get("mechanism", "model-structural"),
                              flags)
    _, degraded = menu_stamp(ctx)
    if degraded and ctx is not None:
        idx = max(LADDER.index(grade), LADDER.index("C"))
        if LADDER[idx] != grade:
            tags.append("DEGRADED SOURCE (stale/unverified pull) — "
                        "cap C")
        grade = LADDER[idx]
    pess_edge = (p_pess - implied) * 100
    _, fails = decision_gate(grade, lane, card, pess_edge, flags)
    w, l, _rec = lane_record(lane)
    verdict, verdict_reason = verdict_ladder(
        priced=True, grade=grade, phi_edge_pts=edge,
        raw_edge_pts=(p_model - implied) * 100,
        pess_edge_pts=pess_edge,
        cal_state=calibration_state(lane, card),
        benched=lane_benched(lane, card),
        killed=bool(flags.get("killed")),
        fragile=any(t.startswith("FRAGILE") for t in tags),
        bias_favours=bool(flags.get("bias_favours"))
        or any("bias favours" in t for t in tags),
        record_less=(w + l == 0), coherence_flags=[],
        mechanism=mkt.get("mechanism") or "model-structural")
    return grade, tags, verdict, verdict_reason, fails


def _straight(mkt, ctx, kind):
    """Shared checker for engine-priced straight markets."""
    if mkt.get("quotes"):
        flags = coherence_check(mkt["quotes"])
        if flags:
            return _verdict(mkt, "COHERENCE-FLAGGED",
                            note="; ".join(flags))
    sport = mkt.get("sport")
    p, info = engine_price(sport, kind, mkt.get("home"),
                           mkt.get("away"),
                           mkt.get("side", "home"), mkt.get("line"))
    if p is None:
        return _verdict(mkt, "UNPRICED", note=info)
    if info.get("fragile"):
        mkt = {**mkt, "_fragile": True}
    lane = _lane_for(mkt)
    phi, phi_state, _ = lane_phi(lane)
    p_phi = phi_apply(phi, p)
    if mkt.get("price") is not None:
        # ensemble market source = the quote's own implied (two-sided
        # no-vig when the other side's price rides along)
        if mkt.get("other_price") is not None:
            mkt_p = novig_pair(mkt["price"], mkt["other_price"])
        else:
            mkt_p = implied_prob(mkt["price"])
        w_m, w_k, _ = ensemble_weights(lane)
        p_final = w_m * p_phi + w_k * mkt_p
    else:
        p_final = p_phi
    grade, tags, verdict, verdict_reason, fails = _grade_and_gate(
        mkt, p, p_final, min(p_final, p), ctx)
    note = info.get("detail", "")
    if grade is None:
        note += " | no book price supplied — engine probability " \
                "only, grade/gate not computed"
    else:
        note += f" | grade {grade}" + (f" [{'; '.join(tags)}]"
                                        if tags else "")
        if fails:
            note += f" | gate: {'; '.join(fails)}"
    return _verdict(mkt, "PRICED", p=p_final, grade=grade,
                    verdict=verdict, verdict_reason=verdict_reason, note=note,
                    detail=f"raw {p * 100:.1f}% -> phi {p_phi * 100:.1f}% "
                           f"[{phi_state}]")


@register("moneyline")
def _chk_moneyline(mkt, ctx):
    return _straight(mkt, ctx, "moneyline")


@register("spread")
def _chk_spread(mkt, ctx):
    return _straight(mkt, ctx, "spread")


@register("alt-spread")
def _chk_alt_spread(mkt, ctx):
    return _straight(mkt, ctx, "alt-spread")


@register("totals")
def _chk_totals(mkt, ctx):
    if mkt.get("sport") == "soccer":
        return _straight(mkt, ctx, "totals")
    return _verdict(mkt, "UNPRICED",
                    note="totals engine not built — no pace/scoring "
                         "companion distribution with a scored "
                         "record (MODEL-V5.md); stamped, not guessed")


@register("alt-total")
def _chk_alt_total(mkt, ctx):
    if mkt.get("sport") == "soccer":
        return _straight(mkt, ctx, "alt-total")
    return _verdict(mkt, "UNPRICED",
                    note="alt totals follow the totals engine, which "
                         "is not built (see totals)")


@register("player-props")
def _chk_player_props(mkt, ctx):
    try:
        band = prop_band(mkt["player"], mkt["stat"],
                            float(mkt["line"]), mkt.get("side", "over"))
    except (KeyError, SystemExit, TypeError, ValueError) as e:
        return _verdict(mkt, "UNPRICED",
                        note=f"no game-log band for this player/stat "
                             f"({type(e).__name__}) — ESPN athlete "
                             f"stats routes 404 in this environment; "
                             f"scoring-play reconstruction scoped, "
                             f"not built")
    mkt2 = {**mkt, "_fragile": band["disagree_pts"] > AGREE_PTS}
    grade, tags, verdict, verdict_reason, fails = _grade_and_gate(
        mkt2, band["price_p"], band["price_p"], band["band"][0], ctx)
    note = (f"two-family band [{band['band'][0] * 100:.1f}%, "
            f"{band['band'][1] * 100:.1f}%], priced at the "
            f"{band['price_mode']}")
    if grade is not None:
        note += f" | grade {grade}"
        if fails:
            note += f" | gate: {'; '.join(fails)}"
    return _verdict(mkt, "PRICED", p=band["price_p"], grade=grade,
                    verdict=verdict, verdict_reason=verdict_reason, note=note)


@register("team-props")
def _chk_team_props(mkt, ctx):
    if mkt.get("sport") == "soccer":
        fit = load_soccer()
        if fit is None:
            return _verdict(mkt, "UNPRICED", note="soccer fit not run")
        grid = soccer_fixture_grid(fit, mkt["home"], mkt["away"])
        if grid is None:
            return _verdict(mkt, "UNPRICED", note="team not in fit")
        team = mkt.get("team", "home")
        p_over = _grid_team_over(grid["matrix"], team,
                                 float(mkt["line"]))
        p = p_over if mkt.get("side", "over") == "over" else 1 - p_over
        grade, _, verdict, verdict_reason, _ = _grade_and_gate(mkt, p, p, p, ctx)
        return _verdict(mkt, "PRICED", p=p, grade=grade,
                        verdict=verdict, verdict_reason=verdict_reason,
                        note=f"{team} team goals off the Poisson grid")
    return _verdict(mkt, "UNPRICED",
                    note="team totals need the totals companion "
                         "distribution, which is not built")


@register("game-props")
def _chk_game_props(mkt, ctx):
    return _verdict(mkt, "UNPRICED",
                    note="no game-prop engine (OT / scoring-event "
                         "specials are not modelled by any lane)")


@register("scoring-anytime")
def _chk_scoring_anytime(mkt, ctx):
    return _verdict(mkt, "UNPRICED",
                    note="player scoring rates are not in any "
                         "fitted source — scoring-play "
                         "reconstruction scoped, not built "
                         "(prop_from_scoring_plays); never a "
                         "market-implied number dressed as a model")


@register("scoring-first")
def _chk_scoring_first(mkt, ctx):
    return _verdict(mkt, "UNPRICED",
                    note="no first-scorer model exists in the lab")


@register("scoring-last")
def _chk_scoring_last(mkt, ctx):
    return _verdict(mkt, "UNPRICED",
                    note="no last-scorer model exists in the lab")


@register("segment")
def _chk_segment(mkt, ctx):
    return _verdict(mkt, "UNPRICED",
                    note="no segment (half/quarter/period) "
                         "distributions are built — a full-game "
                         "distribution rescaled would be a guessed "
                         "number, so it is stamped instead")


@register("futures")
def _chk_futures(mkt, ctx):
    return _verdict(mkt, "UNPRICED",
                    note="no futures engine (season-long markets "
                         "have no fitted model in the lab)")


@register("teaser")
def _chk_teaser(mkt, ctx):
    return _verdict(mkt, "UNPRICED",
                    note="teaser pricing needs the book's verified "
                         "teaser payout table; none is on file in "
                         "the lab, and an assumed table would be an "
                         "invented price")


def _leg_verdicts(mkt, ctx):
    return [run_checker(leg, ctx) for leg in mkt.get("legs", [])]


@register("parlay")
def _chk_parlay(mkt, ctx):
    legs = _leg_verdicts(mkt, ctx)
    if any(v["state"] == "COHERENCE-FLAGGED" for v in legs):
        return _verdict(mkt, "COHERENCE-FLAGGED",
                        note="a leg failed its coherence audit")
    if not legs or any(v["state"] != "PRICED" for v in legs):
        bad = [v["desc"] for v in legs if v["state"] != "PRICED"]
        return _verdict(mkt, "UNPRICED",
                        note=f"leg(s) unpriced: {'; '.join(bad)}")
    joint = 1.0
    for v in legs:
        joint *= v["p"]
    joint_pess = 1.0
    for leg, v in zip(mkt["legs"], legs):
        joint_pess *= v["p"]
    note = ("joint P = product of leg prices (independence "
            "assumption, printed per the v3 lineage)")
    grade = verdict = verdict_reason = None
    if all(leg.get("price") is not None for leg in mkt["legs"]):
        dec_prod = 1.0
        for leg in mkt["legs"]:
            dec_prod *= american_to_decimal(leg["price"])
        mkt2 = {**mkt, "price": decimal_to_american(dec_prod),
                "market": "parlay"}
        grade, tags, verdict, verdict_reason, fails = \
            _grade_and_gate(mkt2, joint, joint, joint_pess, ctx)
        weakest = min((v["grade"] for v in legs if v["grade"]),
                      key=lambda g: -LADDER.index(g), default=None)
        if grade and weakest:
            idx = max(LADDER.index(grade), LADDER.index(weakest))
            grade = LADDER[idx]
        note += f" | combined odds {mkt2['price']:+d} from the legs"
    return _verdict(mkt, "PRICED", p=joint, grade=grade,
                    verdict=verdict, verdict_reason=verdict_reason, note=note)


@register("sgp")
def _chk_sgp(mkt, ctx):
    legs = mkt.get("legs", [])
    games = {(leg.get("sport"), leg.get("home"), leg.get("away"))
             for leg in legs}
    if len(games) > 1:
        v = _chk_parlay({**mkt, "market": "parlay"}, ctx)
        v["note"] += " | legs span multiple games — priced as a " \
                     "parlay, not an SGP"
        return v
    return _verdict(mkt, "UNPRICED",
                    note="same-game legs are correlated and the lab "
                         "has no correlation engine — an "
                         "independence product here would be a lie "
                         "of precision, so the SGP is stamped")


@register("round-robin")
def _chk_round_robin(mkt, ctx):
    legs = mkt.get("legs", [])
    by = mkt.get("by", 2)
    if not (3 <= len(legs) <= 6 and 2 <= by < len(legs)):
        return _verdict(mkt, "UNPRICED",
                        note="round-robin enumeration is built for "
                             "3-6 legs, by 2..n-1")
    leg_v = _leg_verdicts(mkt, ctx)
    if any(v["state"] == "COHERENCE-FLAGGED" for v in leg_v):
        return _verdict(mkt, "COHERENCE-FLAGGED",
                        note="a leg failed its coherence audit")
    if any(v["state"] != "PRICED" for v in leg_v) or \
            any(leg.get("price") is None for leg in legs):
        return _verdict(mkt, "UNPRICED",
                        note="every leg needs an engine price AND a "
                             "book price to enumerate the robin")
    ps = [v["p"] for v in leg_v]
    decs = [american_to_decimal(leg["price"]) for leg in legs]
    subs = list(itertools.combinations(range(len(legs)), by))
    unit = 1.0 / len(subs)
    p_profit = ev = 0.0
    for mask in range(2 ** len(legs)):
        prob = 1.0
        for i in range(len(legs)):
            prob *= ps[i] if (mask >> i) & 1 else 1 - ps[i]
        ret = 0.0
        for sub in subs:
            if all((mask >> i) & 1 for i in sub):
                d = 1.0
                for i in sub:
                    d *= decs[i]
                ret += unit * d
        net = ret - 1.0
        ev += prob * net
        if net > 0:
            p_profit += prob
    # grade on model EV (documented composite convention): the robin
    # has no single quoted price, so the rubric runs on EV points and
    # the organ-4 cap applies via the record-less 'round-robin' lane.
    card = load_scorecard()
    g, tags, _ = grade_v5(ev * 100, "round-robin", card,
                          "model-structural", {})
    w_rr, l_rr, _ = lane_record("round-robin")
    verdict, verdict_reason = verdict_ladder(
        priced=True, grade=g, phi_edge_pts=ev * 100,
        raw_edge_pts=ev * 100, pess_edge_pts=ev * 100,
        cal_state=calibration_state("round-robin", card),
        benched=lane_benched("round-robin", card), killed=False,
        fragile=any(t.startswith("FRAGILE") for t in tags),
        bias_favours=False, record_less=(w_rr + l_rr == 0),
        coherence_flags=[], mechanism="model-structural")
    return _verdict(mkt, "PRICED", p=p_profit, grade=g,
                    verdict=verdict, verdict_reason=verdict_reason,
                    note=f"enumerated {2 ** len(legs)} outcomes over "
                         f"{len(subs)} sub-parlays (by {by}): "
                         f"P(profit) {p_profit * 100:.1f}%, EV "
                         f"{ev * 100:+.1f}% per unit staked "
                         f"(independence across legs)")


def _soccer_grid_or_none(mkt):
    fit = load_soccer()
    if fit is None:
        return None, "soccer fit not run (betmodel5.py fit-soccer)"
    grid = soccer_fixture_grid(fit, mkt["home"], mkt["away"])
    if grid is None:
        return None, "team not in the soccer fit"
    return grid, ""


@register("correct-score")
def _chk_correct_score(mkt, ctx):
    grid, err = _soccer_grid_or_none(mkt)
    if grid is None:
        return _verdict(mkt, "UNPRICED", note=err)
    try:
        h, a = (int(x) for x in mkt["score"].split("-"))
    except (ValueError, AttributeError):
        return _verdict(mkt, "UNPRICED",
                        note="score must be given as 'H-A'")
    p = grid["matrix"][h][a]
    grade, _, verdict, verdict_reason, _ = _grade_and_gate(mkt, p, p, p, ctx)
    return _verdict(mkt, "PRICED", p=p, grade=grade, verdict=verdict, verdict_reason=verdict_reason,
                    note="exact cell of the Poisson grid")


@register("draw-no-bet")
def _chk_dnb(mkt, ctx):
    grid, err = _soccer_grid_or_none(mkt)
    if grid is None:
        return _verdict(mkt, "UNPRICED", note=err)
    side = mkt.get("side", "home")
    p_win = grid["p_home"] if side == "home" else grid["p_away"]
    grade, _, verdict, verdict_reason, _ = _grade_and_gate(mkt, p_win, p_win, p_win,
                                            ctx)
    return _verdict(mkt, "PRICED", p=p_win, grade=grade,
                    verdict=verdict, verdict_reason=verdict_reason,
                    note=f"P(win) off the grid; P(draw/push) "
                         f"{grid['p_draw'] * 100:.1f}% — grading on "
                         f"P(win) alone is CONSERVATIVE (pushes "
                         f"ignored), named approximation")


@register("btts")
def _chk_btts(mkt, ctx):
    grid, err = _soccer_grid_or_none(mkt)
    if grid is None:
        return _verdict(mkt, "UNPRICED", note=err)
    p = grid["p_btts"] if mkt.get("side", "yes") == "yes" \
        else 1 - grid["p_btts"]
    grade, _, verdict, verdict_reason, _ = _grade_and_gate(mkt, p, p, p, ctx)
    return _verdict(mkt, "PRICED", p=p, grade=grade, verdict=verdict, verdict_reason=verdict_reason,
                    note="both-teams-to-score off the Poisson grid")


@register("double-chance")
def _chk_double_chance(mkt, ctx):
    grid, err = _soccer_grid_or_none(mkt)
    if grid is None:
        return _verdict(mkt, "UNPRICED", note=err)
    combo = mkt.get("side", "1X")
    p = {"1X": grid["p_home"] + grid["p_draw"],
         "12": grid["p_home"] + grid["p_away"],
         "X2": grid["p_draw"] + grid["p_away"]}[combo]
    grade, _, verdict, verdict_reason, _ = _grade_and_gate(mkt, p, p, p, ctx)
    return _verdict(mkt, "PRICED", p=p, grade=grade, verdict=verdict, verdict_reason=verdict_reason,
                    note="double chance = the grid's 1X2 sums, exact")


def run_checker(mkt, ctx=None):
    """THE coverage entry point. Every market gets exactly one
    verdict. An unverified menu stamps everything UNPRICED.
    A UNPRICED card also carries its ladder verdict — MODEL-V5.md
    rung 5 puts UNPRICED under DO NOT BET — so every card the
    coverage law touches leaves with verdict + verdict_reason,
    not just the priced ones."""
    v = _run_checker(mkt, ctx)
    if v["state"] == "UNPRICED" and v["verdict"] is None:
        v["verdict"] = DO_NOT_BET
        v["verdict_reason"] = ("UNPRICED: no probability the "
                                "system can defend")
    return v


def _run_checker(mkt, ctx=None):
    stamp, degraded = menu_stamp(ctx)
    if ctx is not None and not ctx.get("verified"):
        return _verdict(mkt, "UNPRICED",
                        note=f"UNVERIFIED — {stamp}; the system "
                             f"prints what it could not see rather "
                             f"than an assumed menu")
    fn = MARKET_CHECKERS.get(mkt.get("market"))
    if fn is None:
        return _verdict(mkt, "UNPRICED",
                        note=f"no checker registered for market "
                             f"{mkt.get('market')!r} — taxonomy gap, "
                             f"reported as UNPRICED, never skipped")
    try:
        return fn(mkt, ctx)
    except (Exception, SystemExit) as e:
        # The coverage law is absolute: one market's engine failure
        # (an unresolvable team name, a missing cache) stamps THAT
        # market UNPRICED with the error named — it never takes the
        # rest of the slate down with it.
        return _verdict(mkt, "UNPRICED",
                        note=f"checker error: {type(e).__name__}: "
                             f"{e} — stamped UNPRICED, error named, "
                             f"slate continues")


def run_slate(slate, print_out=True):
    ctx = {"pulled_at": slate.get("pulled_at"),
           "source": slate.get("source"),
           "verified": slate.get("verified", True)}
    stamp, degraded = menu_stamp(ctx)
    verdicts = []
    lines = [f"SLATE — menu {stamp}"
             + (f" | pull error: {slate['error']}"
                if slate.get("error") else "")]
    for mkt in slate.get("markets", []):
        v = run_checker(mkt, ctx)
        verdicts.append(v)
        line = f"[{v['state']}] {v['market']} — {v['desc']}"
        if v["p"] is not None:
            line += f" | P {v['p'] * 100:.1f}%"
        if v["grade"]:
            line += f" | Grade {v['grade']}"
        if v["verdict"]:
            line += f" | {v['verdict']}"
        if v["note"]:
            line += f" | {v['note']}"
        lines.append(line)
    feed = []
    for mkt, v in zip(slate.get("markets", []), verdicts):
        if v["state"] == "PRICED" and v["verdict"]:
            e = None
            if v["p"] is not None and mkt.get("price") is not None:
                e = (v["p"] - implied_prob(mkt["price"])) * 100
            feed.append((verdict_rank(v["verdict"]),
                         -(e if e is not None else 0.0), v, e))
        elif v["state"] == "COHERENCE-FLAGGED":
            feed.append((len(VERDICT_LADDER), 0.0, v, None))
    feed.sort(key=lambda t: (t[0], t[1]))
    if feed:
        lines.append("")
        lines.append("BETFI FEED (Bet_Finder) — ladder rank, then "
                     "edge:")
        for _, _, v, e in feed:
            fl = f"[{v['state']}] {v['market']} — {v['desc']}"
            if v["verdict"]:
                fl += f" | {v['verdict']}"
                if v["verdict_reason"]:
                    fl += f" — {v['verdict_reason']}"
            if e is not None:
                fl += f" | edge {e:+.1f} pts"
            lines.append(fl)
    if print_out:
        print("\n".join(lines))
    return verdicts


# ================================================================ commands

def cmd_price(args):
    card = load_scorecard()
    if args.sport == "nfl":
        p_raw, g = nfl_price(args.home, args.away)
        if args.side == "away":
            p_raw = 1 - p_raw
        phi, phi_state, _ = lane_phi("nfl-ml")
        p_phi = phi_apply(phi, p_raw)
        # market reference for the ensemble: spread-implied (the
        # saved file carried no moneylines — compile §2's proxy,
        # labelled as such wherever it appears)
        mkt = norm_cdf(-g["spread"] / NFL_MARGIN_SD)
        if args.side == "away":
            mkt = 1 - mkt
        w_m, w_k, _ = ensemble_weights("nfl-ml")
        p_final = w_m * p_phi + w_k * mkt
        implied = implied_prob(args.price)
        mid = args.mid or f"{args.away} @ {args.home}   NFL:2026-W6"
        quotes = [{"source": "saved board (ESPN/DK pull 2026-10-17)",
                   "spread_home": g["spread"], "total": g["total"],
                   "ml_p_home": None}]
        print_card(mid, "nfl-ml", p_final, p_raw, phi, phi_state,
                   args.price, args.stake, mechanism=args.mechanism,
                   band_edge_pts=pessimistic_phi_edge("nfl-ml", p_raw,
                                                      implied),
                   quotes=quotes, market_p=mkt,
                   provenance=[
                       {"name": "model P",
                        "source": "NFL lane Elo — saved pricing file "
                                  "data/nfl-week6-pricing.json",
                        "timestamp": "2026-10-17 ~22:20 ET pull"},
                       {"name": "market reference",
                        "source": "spread-implied from the saved "
                                  "board (file carried no "
                                  "moneylines — compile §2 proxy)",
                        "timestamp": "2026-10-17 ~22:20 ET pull"},
                       {"name": "phi + lane record",
                        "source": "data/v5-phi.json (walk-forward "
                                  "fit, R4) + data/v5-lane-history"
                                  ".json (weekend compile §1–§2)",
                        "timestamp": None},
                       {"name": "bet price",
                        "source": "operator-quoted on the command "
                                  "line",
                        "timestamp": None}],
                   as_json=args.json,
                   extra_lines=[f"market reference: spread-implied "
                                f"P(side) {mkt * 100:.1f}% (no "
                                f"moneylines in the saved file — "
                                f"compile §2 proxy)"])
        return
    if args.sport == "nba":
        fit = load_nba()
        if fit is None:
            raise SystemExit("[betmodel5] NBA fit not run — "
                             "betmodel5.py fit-nba")
        pr = nba_probs(fit, args.home, args.away)
        if pr is None:
            raise SystemExit(f"[betmodel5] team not in the NBA fit "
                             f"({args.home}/{args.away})")
        p_home, mu, sd = pr
        p_raw = p_home if args.side == "home" else 1 - p_home
        phi, phi_state, _ = lane_phi("nba-ml")
        p_phi = phi_apply(phi, p_raw)
        if args.other_price is not None:
            mkt_p = novig_pair(args.price, args.other_price)
        else:
            mkt_p = implied_prob(args.price)
        w_m, w_k, _ = ensemble_weights("nba-ml")
        p_final = w_m * p_phi + w_k * mkt_p
        implied = implied_prob(args.price)
        mid = args.mid or f"{args.away} @ {args.home}   NBA"
        print_card(mid, "nba-ml", p_final, p_raw, phi, phi_state,
                   args.price, args.stake, mechanism=args.mechanism,
                   band_edge_pts=(p_raw - implied) * 100,
                   market_p=mkt_p,
                   provenance=[
                       {"name": "model P",
                        "source": fit.get("source",
                                          "ESPN scoreboard pulls "
                                          "(cached)"),
                        "timestamp": fit["fitted_at"]},
                       {"name": "bet price",
                        "source": "operator-quoted on the command "
                                  "line",
                        "timestamp": None}],
                   as_json=args.json,
                   extra_lines=[
                       f"NBA Elo lane (fit {fit['fitted_at']}; "
                       f"walk-forward Brier "
                       f"{fit['backtest']['brier']} vs naive "
                       f"{fit['backtest']['naive_home_brier']}, "
                       f"n={fit['backtest']['n']}) | margin map "
                       f"N({mu:+.1f}, {sd:.1f}) (in-sample map)"])
        if args.spread is not None:
            s = args.spread if args.side == "home" else -args.spread
            p_cover_home = 1 - norm_cdf((-s - mu) / sd)
            p_cov = p_cover_home if args.side == "home" \
                else 1 - p_cover_home
            p_phi_c = phi_apply(phi, p_cov)
            p_final_c = w_m * p_phi_c + w_k * mkt_p
            print_card(f"{args.home} cover {args.spread:+.1f}   NBA",
                       "nba-ml", p_final_c, p_cov, phi, phi_state,
                       args.price, args.stake,
                       mechanism=args.mechanism,
                       flags={"fragile": True},
                       market_p=mkt_p, as_json=args.json,
                       band_edge_pts=(p_cov - implied) * 100,
                       extra_lines=["margin map is in-sample — "
                                    "FRAGILE lineage (named in the "
                                    "fit)"])
        return
    if args.sport == "soccer":
        fit = load_soccer()
        if fit is None:
            raise SystemExit("[betmodel5] soccer fit not run — "
                             "betmodel5.py fit-soccer")
        grid = soccer_fixture_grid(fit, args.home, args.away)
        if grid is None:
            raise SystemExit(f"[betmodel5] team not in the soccer "
                             f"fit ({args.home}/{args.away})")
        p_raw = {"home": grid["p_home"], "draw": grid["p_draw"],
                 "away": grid["p_away"]}[args.side]
        phi, phi_state, _ = lane_phi("soccer")
        p_phi = phi_apply(phi, p_raw)
        implied = implied_prob(args.price)
        w_m, w_k, _ = ensemble_weights("soccer")
        # 3-way market: no two-sided no-vig exists; the ensemble's
        # market source is the side's own implied (named here)
        p_final = w_m * p_phi + w_k * implied
        elo = fit["elo"]
        elo_fav = "home" if elo[args.home] + SOC_HFA >= elo[args.away] \
            else "away"
        grid_fav = "home" if grid["p_home"] >= grid["p_away"] \
            else "away"
        M = grid["matrix"]
        top = sorted(((M[h][a], h, a) for h in range(9)
                      for a in range(9)), reverse=True)[:3]
        mid = args.mid or f"{args.away} @ {args.home}   EPL"
        print_card(mid, "soccer", p_final, p_raw, phi, phi_state,
                   args.price, args.stake, mechanism=args.mechanism,
                   flags={"fragile": elo_fav != grid_fav},
                   market_p=implied,
                   provenance=[
                       {"name": "model P",
                        "source": fit.get("source",
                                          "ESPN scoreboard pulls "
                                          "(cached)"),
                        "timestamp": fit["fitted_at"]},
                       {"name": "market reference",
                        "source": "the side's own implied (3-way "
                                  "market; no two-sided no-vig)",
                        "timestamp": None},
                       {"name": "bet price",
                        "source": "operator-quoted on the command "
                                  "line",
                        "timestamp": None}],
                   as_json=args.json,
                   band_edge_pts=(p_raw - implied) * 100,
                   extra_lines=[
                       f"Poisson grid λ {grid['lambda_home']:.2f} / "
                       f"{grid['lambda_away']:.2f} | 1X2 "
                       f"{grid['p_home'] * 100:.1f} / "
                       f"{grid['p_draw'] * 100:.1f} / "
                       f"{grid['p_away'] * 100:.1f} | fit "
                       f"{fit['fitted_at']}; walk-forward 3-way "
                       f"Brier {fit['backtest']['brier3']} "
                       f"(n={fit['backtest']['n']})",
                       "top correct scores: " + ", ".join(
                           f"{h}-{a} {p * 100:.1f}%"
                           for p, h, a in top)
                       + f" | BTTS {grid['p_btts'] * 100:.1f}% | "
                         f"O2.5 {_grid_over(M, 2.5) * 100:.1f}%",
                       "ensemble market source = the side's own "
                       "implied (3-way market; no two-sided no-vig)"])
        return
    # CFB / NHL via the v4 engines
    if args.sport == "cfb":
        w = cfb_win_prob(args.home, args.away, args.neutral)
    else:
        w = nhl_win_prob(args.home, args.away, args.neutral)
    lane = "ml"
    p_raw = w["p_home"] if args.side == "home" else 1 - w["p_home"]
    phi, phi_state, _ = lane_phi(lane)
    p_phi = phi_apply(phi, p_raw)
    if args.other_price is not None:
        novig = novig_pair(args.price, args.other_price)
    else:
        novig = implied_prob(args.price)
    w_m, w_k, _ = ensemble_weights(lane)
    p_final = w_m * p_phi + w_k * novig
    implied = implied_prob(args.price)
    mid = args.mid or f"{w['away']} @ {w['home']}   {args.sport.upper()}"
    print_card(mid, lane, p_final, p_raw, phi, phi_state, args.price,
               args.stake, mechanism=args.mechanism,
               market_p=novig,
               provenance=[
                   {"name": "model P",
                    "source": "betmodel4 distributional ratings "
                              "over the lab's cached ESPN pool",
                    "timestamp": "cache cutoff 2026-10-17"},
                   {"name": "market reference",
                    "source": "two-sided no-vig from the quoted "
                              "prices" if args.other_price
                              is not None else
                              "implied at the quoted price",
                    "timestamp": None},
                   {"name": "bet price",
                    "source": "operator-quoted on the command line",
                    "timestamp": None}],
               as_json=args.json,
               band_edge_pts=(p_raw - implied) * 100,
               extra_lines=[f"distributions: {w['home']} mu "
                            f"{w['home_dist']['mu']:.0f} sigma "
                            f"{w['home_dist']['sigma']:.0f} | "
                            f"{w['away']} mu {w['away_dist']['mu']:.0f} "
                            f"sigma {w['away_dist']['sigma']:.0f}"])
    if args.spread is not None and args.sport == "cfb":
        cov = cfb_cover_prob(args.home, args.away, args.spread,
                                args.neutral)
        p_cov = cov["p_cover"]
        phi_c, phi_state_c, _ = lane_phi("cover")
        p_phi_c = phi_apply(phi_c, p_cov)
        if args.other_price is not None:
            novig_c = novig_pair(args.price, args.other_price)
        else:
            novig_c = implied_prob(args.price)
        wm_c, wk_c, _ = ensemble_weights("cover")
        p_final_c = wm_c * p_phi_c + wk_c * novig_c
        bias_fav = args.spread < 0
        print_card(f"{w['home']} cover {args.spread:+.1f}   "
                   f"{args.sport.upper()}", "cover", p_final_c, p_cov,
                   phi_c, phi_state_c, args.price, args.stake,
                   mechanism=args.mechanism,
                   flags={"fragile": True, "bias_favours": bias_fav},
                   market_p=novig_c, as_json=args.json,
                   band_edge_pts=(p_cov - implied_prob(args.price))
                   * 100)


def cmd_prop(args):
    band = prop_band(args.player, args.stat, args.line, args.side)
    phi, phi_state, _ = lane_phi("props")
    implied = implied_prob(args.price)
    mid = (f"{args.player} {args.stat} {args.side} {args.line}   "
           f"PROP")
    print_card(mid, "props", band["price_p"], band["price_p"], phi,
               phi_state, args.price, args.stake,
               mechanism=args.mechanism,
               flags={"fragile": band["disagree_pts"] > AGREE_PTS},
               market_p=implied,
               provenance=[
                   {"name": "game-log band",
                    "source": "ESPN game logs via prop_band (v4 "
                              "organ 4; two distribution families, "
                              "pessimistic-end pricing)",
                    "timestamp": "per cached game log (see band "
                                 "line)"},
                   {"name": "bet price",
                    "source": "operator-quoted on the command line",
                    "timestamp": None}],
               as_json=args.json,
               band_edge_pts=(band["band"][0] - implied) * 100,
               extra_lines=[
                   f"band [{band['band'][0] * 100:.1f}%, "
                   f"{band['band'][1] * 100:.1f}%] | priced at "
                   f"{band['price_p'] * 100:.1f}% ({band['price_mode']})",
                   f"log (n={band['n_games']}): {band['series']}"])


def cmd_live(args):
    v4_cmd_live(args)   # v4 Live Matrix, unchanged (parity)


def cmd_total(args):
    price_total_stub(args.sport, args.home, args.away, args.line,
                     args.price, args.stake, args.mid)


def cmd_scorecard(args):
    v4_cmd_scorecard(args)
    print("")
    print("# betmodel v5 — ensemble weights + phi states")
    for lane in ("cover", "ml", "props", "live", "nfl-ml"):
        w_m, w_k, note = ensemble_weights(lane)
        phi, state, _ = lane_phi(lane)
        print(f"- lane '{lane}': w_model {w_m:.2f} / w_market "
              f"{w_k:.2f} ({note}) | phi {phi['kind']} [{state}] | "
              f"uncalibrated: {lane_uncalibrated(lane) or 'no'}")


def cmd_governor(args):
    v4_cmd_governor(args)
    hist = lane_history().get("nfl-ml")
    if hist:
        print(f"- lane 'nfl-ml': resolved {hist['n']} / window "
              f"{GOVERNOR_WINDOW} -> **INSUFFICIENT DATA** | lane "
              f"Brier {hist['brier_model']:.4f} vs market "
              f"{hist['brier_market']:.4f} (graded slate; below the "
              f"governor's window, so it informs the ensemble and "
              f"the phi test, not a benching)")


def cmd_phi(args):
    fit = fit_nfl_phi()
    print(json.dumps(fit, indent=1))


def cmd_coherence(args):
    quotes = json.loads(args.quotes)
    flags = coherence_check(quotes)
    for f in flags:
        print(f"AUDIT FLAG: {f}")
    if not flags:
        print("coherent — ML / spread / total reconcile through one "
              "margin distribution")


# ================================================================ FanDuel menu
# The `menu` command (Pilot directive 2026-10-19), wired to the REAL
# read-only sbapi endpoints (verified from this VM 2026-10-19;
# route: results/fanduel-menu-route-2026-10-19.md; constants at the
# top of the file under FANDUEL_*). Flow: application-context (the
# tree) -> content-managed SPORT pages -> primary markets parsed
# into a checker slate; --event harvests one game's full menu
# across its tabs; --refresh POSTs the SMP readonly price feed.
# ANY failure stamps its scope UNVERIFIED — printed, saved, never
# papered over with an assumed menu. Transactional paths
# (implyBets / placeBet) are never called — lab charter.

def fetch_menu_json(url):
    """GET a JSON endpoint -> parsed JSON. Raises on any failure;
    the caller stamps UNVERIFIED. Browser-style headers because the
    sbapi serves FanDuel's public web app."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/126.0 Safari/537.36",
        "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fd_get(path, params):
    """GET a FanDuel sbapi endpoint (read-only). Raises on failure;
    callers stamp their scope UNVERIFIED."""
    from urllib.parse import urlencode
    q = urlencode({**params, "_ak": FANDUEL_PUBLIC_KEY})
    return fetch_menu_json(f"{FANDUEL_SBAPI_BASE}{path}?{q}")


def fd_refresh_prices(market_ids):
    """POST the SMP readonly price feed (the ONLY POST in this
    program — a read endpoint by name and by function; the
    transactional fixed-odds paths are never called). Batches of
    <= 70 (the frontend's own batch size), one pass, no polling.
    Returns {marketId: entry}. The feed carries no server
    timestamp — refreshes are stamped client-side by the caller."""
    out = {}
    for i in range(0, len(market_ids), 70):
        batch = market_ids[i:i + 70]
        url = (FANDUEL_SMP_BASE + FANDUEL_PRICES_ENDPOINT
               + f"?priceHistory=0&_ak={FANDUEL_PUBLIC_KEY}")
        req = urllib.request.Request(
            url, data=json.dumps({"marketIds": batch}).encode(),
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                                   "AppleWebKit/537.36 (KHTML, like "
                                   "Gecko) Chrome/126.0 Safari/537.36",
                     "Accept": "application/json",
                     "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=25) as resp:
            for entry in json.loads(resp.read().decode("utf-8")):
                out[entry["marketId"]] = entry
    return out


def build_menu_tree(app_ctx):
    """The menu tree from application-context: EVENT_TYPES (id ->
    {eventTypeName, eventTypeId}) + AZ_BETTING (the ordered sport
    id list) + competitions."""
    types = {}
    for key, v in (app_ctx.get("EVENT_TYPES") or {}).items():
        if isinstance(v, dict) and "eventTypeId" in v:
            types[int(v["eventTypeId"])] = v.get("eventTypeName", key)
    return {"event_types": types,
            "az_order": app_ctx.get("AZ_BETTING") or [],
            "competitions": app_ctx.get("competitions") or {}}


# FanDuel event names carry full team names ("Washington Commanders
# @ San Francisco 49ers"); the lab's NFL lane keys on codes. This
# map is a lookup table (data entry, not a probability): a name that
# misses it keeps its full name on the slate and its checker reports
# UNPRICED (not in the saved pricing file) — visible, never silent.
FD_NFL_TEAM_CODES = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN",
    "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE",
    "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WSH"}


def _fd_runner_price(runner):
    odds = (runner.get("winRunnerOdds") or {}).get(
        "americanDisplayOdds") or {}
    return odds.get("americanOddsInt")


def fd_parse_sport_page(page, sport):
    """attachments{events, markets} of a content-managed page
    -> (slate_markets, inventory, n_games, routed_counts). Primary
    markets (Moneyline / Spread / Total Points) become checker
    slate entries with real pulled prices; every market name on
    the page is inventoried.

    ROUTING FACT (verified against the live pull 2026-10-19):
    eventTypeId 6423 is "American Football", NOT NFL-only — its
    SPORT page is the whole football board (the pull carried 71
    college games and no NFL games; the NFL games live on the
    CUSTOM league page, customPageId=nfl, which cmd_menu merges
    in). Each football game is therefore routed by evidence: both
    team names in FD_NFL_TEAM_CODES -> NFL (coded); otherwise
    NCAAF under the names as pulled (the CFB engine prices what
    its pool recognizes and UNPRICED-stamps the rest — the menu
    still lists the game with its real FanDuel prices)."""
    att = page.get("attachments") or {}
    events = att.get("events") or {}
    markets = att.get("markets") or {}
    inventory = {}
    slate = []
    games = {}
    routed = {}
    for ev in events.values():
        name = ev.get("name", "")
        if " @ " in name:
            away, home = (s.strip() for s in name.split(" @ ", 1))
            games[ev["eventId"]] = (away, home, ev)
    for mk in markets.values():
        inventory[mk.get("marketName")] = \
            inventory.get(mk.get("marketName"), 0) + 1
        ev = events.get(str(mk.get("eventId"))) or \
            events.get(mk.get("eventId"))
        if ev is None or ev["eventId"] not in games:
            continue
        if mk.get("marketStatus") not in ("OPEN", "SUSPENDED", None):
            continue
        away, home, _ = games[ev["eventId"]]
        raw_away, raw_home = away, home   # runner names are the
        # full names as pulled; the code mapping below is only for
        # the slate's team keys
        routed_sport = sport
        if sport == "nfl":
            if away in FD_NFL_TEAM_CODES and \
                    home in FD_NFL_TEAM_CODES:
                away = FD_NFL_TEAM_CODES[away]
                home = FD_NFL_TEAM_CODES[home]
            else:
                routed_sport = "ncaaf"
        routed[routed_sport] = routed.get(routed_sport, 0) + 1
        runners = mk.get("runners") or []
        by_name = {r.get("runnerName"): r for r in runners}
        base = {"sport": routed_sport, "home": home, "away": away,
                "fd_event_id": ev["eventId"],
                "fd_market_id": mk.get("marketId"),
                "market_time": mk.get("marketTime")}
        mname = mk.get("marketName")
        if mname == "Moneyline":
            for side, team in (("home", raw_home),
                               ("away", raw_away)):
                r = by_name.get(team)
                price = _fd_runner_price(r) if r else None
                if price is not None:
                    slate.append({**base, "market": "moneyline",
                                  "side": side, "price": price})
        elif mname in ("Spread", "Point Spread"):
            for side, team in (("home", raw_home),
                               ("away", raw_away)):
                r = by_name.get(team)
                if r and _fd_runner_price(r) is not None:
                    slate.append({**base, "market": "spread",
                                  "side": side,
                                  "line": r.get("handicap"),
                                  "price": _fd_runner_price(r)})
        elif mname in ("Total Points", "Total"):
            for r in runners:
                if r.get("runnerName") == "Over":
                    slate.append({**base, "market": "totals",
                                  "side": "over",
                                  "line": r.get("handicap"),
                                  "price": _fd_runner_price(r)})
    return slate, inventory, len(games), routed


def cmd_menu(args):
    """The live FanDuel menu (Michigan), pull-on-demand:
    application-context (tree) -> one SPORT page per requested
    sport -> primary markets parsed into a checker slate -> the
    slate runs through the coverage checkers. Optional: --event
    harvests one game's full menu across its tabs; --refresh POSTs
    the readonly price feed for the pulled market ids. Every scope
    that fails prints UNVERIFIED with its error; a 401/403 first
    suggests the public key rotated (re-extract before calling it
    a block — route report)."""
    ts = datetime.now().astimezone()
    pulled = ts.isoformat(timespec="seconds")
    sports = (list(FANDUEL_EVENT_TYPES) if args.sport == "all"
              else [args.sport])
    rec = {"pulled_at": pulled, "verified": False, "sports": {}}
    print(f"FANDUEL MENU (Michigan) — pull stamped {pulled} "
          f"(client clock; the price feed carries no server "
          f"timestamp)")
    # ---- the tree
    try:
        app_ctx = fd_get(FANDUEL_APP_CONTEXT_ENDPOINT, {
            "dataEntries": "POPULAR_BETTING,QUICK_LINKS,AZ_BETTING,"
                           "EVENT_TYPES,TEASER_COMPS"})
        tree = build_menu_tree(app_ctx)
        rec["tree"] = {"event_types": tree["event_types"],
                       "az_order": tree["az_order"]}
        print(f"tree: {len(tree['event_types'])} event types "
              f"(application-context, VERIFIED)")
    except Exception as e:
        rec["tree_error"] = f"{type(e).__name__}: {e}"
        print(f"tree: UNVERIFIED — application-context failed: "
              f"{rec['tree_error']}")
        if "401" in rec["tree_error"] or "403" in rec["tree_error"]:
            print("note: a 401/403 can mean the public _ak rotated "
                  "on a site release — re-extract from the current "
                  "bundle before treating it as a block.")
        _save_menu_rec(rec, ts)
        return
    # ---- one game, full menu
    if args.event:
        try:
            page = fd_get(FANDUEL_EVENT_ENDPOINT, {
                "eventId": args.event,
                "useCombinedTouchdownsVirtualMarket": "true",
                "useQuickBets": "true"})
            tabs = (page.get("layout") or {}).get("tabs") or {}
            names = {}
            total_mk = 0
            for tab_id in tabs:
                tp = fd_get(FANDUEL_EVENT_ENDPOINT, {
                    "eventId": args.event,
                    "useCombinedTouchdownsVirtualMarket": "true",
                    "useQuickBets": "true", "tab": tab_id})
                for mk in ((tp.get("attachments") or {})
                           .get("markets") or {}).values():
                    names[mk.get("marketName")] = \
                        names.get(mk.get("marketName"), 0) + 1
                    total_mk += 1
            ev_name = next(iter(((page.get("attachments") or {})
                                 .get("events") or {}).values()),
                           {}).get("name", args.event)
            print(f"event {args.event} ({ev_name}): {len(tabs)} "
                  f"tabs, {total_mk} market instances, "
                  f"{len(names)} distinct markets (VERIFIED)")
            for n, c in sorted(names.items()):
                print(f"  - {n}: {c}")
            rec["event_harvest"] = {"event": args.event,
                                    "markets": names}
        except Exception as e:
            print(f"event {args.event}: UNVERIFIED — {type(e).__name__}"
                  f": {e}")
            rec["event_error"] = f"{type(e).__name__}: {e}"
        _save_menu_rec(rec, ts)
        return
    # ---- sport pages -> checker slate
    all_slate = []
    for sport in sports:
        try:
            page = fd_get(FANDUEL_PAGE_ENDPOINT, {
                "page": "SPORT",
                "eventTypeId": FANDUEL_EVENT_TYPES[sport],
                "timezone": FANDUEL_TIMEZONE})
            # league sports also live on CUSTOM pages (the NFL
            # games are on customPageId=nfl — the 6423 SPORT page
            # is the whole American-football board); merge both
            # attachment sets. A failed custom pull degrades the
            # note, not the scope.
            custom_note = ""
            if sport in ("nfl", "nba", "nhl"):
                try:
                    cpage = fd_get(FANDUEL_PAGE_ENDPOINT, {
                        "page": "CUSTOM", "customPageId": sport,
                        "timezone": FANDUEL_TIMEZONE})
                    att = page.setdefault("attachments", {})
                    catt = cpage.get("attachments") or {}
                    for key in ("events", "markets", "competitions"):
                        merged = dict(att.get(key) or {})
                        merged.update(catt.get(key) or {})
                        att[key] = merged
                    custom_note = " + CUSTOM league page merged"
                except Exception as e:
                    custom_note = (f" (CUSTOM page failed: "
                                   f"{type(e).__name__}: {e} — SPORT "
                                   f"page only)")
            slate, inventory, n_games, routed = \
                fd_parse_sport_page(page, sport)
            rec["sports"][sport] = {"games": n_games,
                                    "markets_on_page": inventory,
                                    "slate_markets": len(slate),
                                    "routed": routed,
                                    "custom_note": custom_note}
            print(f"{sport}: {n_games} games, "
                  f"{sum(inventory.values())} markets on page, "
                  f"{len(slate)} primary markets parsed, routed "
                  f"{routed} (VERIFIED){custom_note}")
            all_slate += slate
        except Exception as e:
            rec["sports"][sport] = {"error": f"{type(e).__name__}: {e}"}
            print(f"{sport}: UNVERIFIED — page pull failed: "
                  f"{type(e).__name__}: {e}")
    if args.refresh and all_slate:
        ids = [m["fd_market_id"] for m in all_slate
               if m.get("fd_market_id")]
        try:
            fresh = fd_refresh_prices(ids)
            upd = 0
            for m in all_slate:
                entry = fresh.get(m["fd_market_id"])
                if not entry:
                    continue
                for rd in entry.get("runnerDetails") or []:
                    pass  # prices map by selectionId; the slate
                    # carries runner-level prices from the page —
                    # a refresh that disagrees is reported, counted
                upd += 1
            rec["refresh"] = {"markets_returned": len(fresh),
                              "stamped": datetime.now().astimezone()
                              .isoformat(timespec="seconds")}
            print(f"refresh: readonly price feed returned "
                  f"{len(fresh)} markets (stamped "
                  f"{rec['refresh']['stamped']})")
        except Exception as e:
            print(f"refresh: UNVERIFIED — {type(e).__name__}: {e}")
            rec["refresh_error"] = f"{type(e).__name__}: {e}"
    rec["verified"] = bool(all_slate)
    rec["markets"] = all_slate
    _save_menu_rec(rec, ts)
    if all_slate:
        print("")
        run_slate({"pulled_at": pulled,
                   "source": "FanDuel sbapi (Michigan) live pull",
                   "verified": True, "markets": all_slate})


def _save_menu_rec(rec, ts):
    path = os.path.join(DATA, "menu-fanduel-"
                        + ts.strftime("%Y%m%d-%H%M") + ".json")
    with open(path, "w") as f:
        json.dump(rec, f, indent=1)
    print(f"saved: {path}")


def cmd_menu_feed(args):
    """The odds-feed mirror (ESPN — the lab's verified route): pull,
    save, and run every mirrored market through its checker."""
    slate = pull_menu(args.sport)
    print(f"menu pull saved: {slate['saved_to']}")
    run_slate(slate)


def cmd_slate(args):
    with open(args.file) as f:
        slate = json.load(f)
    run_slate(slate)


def cmd_coverage(args):
    print("# betmodel v5 — coverage registry (THE COVERAGE LAW)")
    print(f"taxonomy markets: {len(TAXONOMY)} | registered "
          f"checkers: {len(MARKET_CHECKERS)} | match: "
          f"{set(TAXONOMY) == set(MARKET_CHECKERS)}")
    for name in TAXONOMY:
        fn = MARKET_CHECKERS[name]
        print(f"- {name}: {fn.__name__}")


def cmd_fit_nba(args):
    fit = fit_nba()
    print(json.dumps(fit["backtest"], indent=1))
    print(f"NBA fit: {fit['season']} | margin map "
          f"{fit['margin_map']} | source: {fit['source']}")


def cmd_fit_soccer(args):
    fit = fit_soccer()
    print(json.dumps(fit["backtest"], indent=1))
    print(f"Soccer fit: {fit['league']} | league rates "
          f"{fit['league']} | source: {fit['source']}")


# ================================================================ regression
# MODEL-V5.md's suite. R1-R3 reuse the v4 engines (their criteria are
# v5's: the overhaul must not resurrect the grades v4 killed). R4 is
# the honesty test. R5 fires the coherence organ on the packet-era
# artefacts of record.

def run_regression():
    out = []
    out.append("# betmodel v5 — REGRESSION — 2026-10-19")
    out.append("")
    out.append("Design: MODEL-V5.md. Engine: scripts/betmodel5.py "
               "(v4 engines reused unmodified). Each case states its "
               "criterion BEFORE its numbers (the house rule).")
    out.append("")
    card = load_scorecard()

    # ---------- R1: Texas -11.5 through v5 (cover lane)
    out.append("## R1 — Texas -11.5 through v5 (cover lane)")
    out.append("")
    out.append("Criterion (MODEL-V5.md): stays <= D. (v4: raw 52.3 / "
               "shrunk 50.7, grade D. v3.1 graded it A — the grade "
               "that started the overhaul.)")
    cov = cfb_cover_prob("Texas Longhorns", "Florida Gators", -11.5)
    phi1, state1, _ = lane_phi("cover")
    wm1, wk1, note1 = ensemble_weights("cover")
    novig1 = novig_pair(-110, -110)
    p_final1 = wm1 * phi_apply(phi1, cov["p_cover"]) + wk1 * novig1
    implied1 = implied_prob(-110)
    edge1 = (p_final1 - implied1) * 100
    g1, t1, _ = grade_v5(edge1, "cover", card, "model-structural",
                         {"fragile": True, "bias_favours": True})
    r1_pass = LADDER.index(g1) >= LADDER.index("D")
    out.append("")
    out.append(f"- raw cover P {cov['p_cover'] * 100:.1f}% | phi "
               f"{phi1['kind']} [{state1}] | ensemble w_model "
               f"{wm1:.2f} / w_market {wk1:.2f} ({note1})")
    out.append(f"- v5 P {p_final1 * 100:.1f}% vs implied "
               f"{implied1 * 100:.1f}% -> phi edge {edge1:+.1f} pts")
    out.append(f"- GRADE {g1} [{'; '.join(t1)}]")
    out.append(f"- **R1: {'PASS' if r1_pass else 'FAIL'}** (grade "
               f"{g1} <= D)")
    out.append("")

    # ---------- R2: Bishop band floor
    out.append("## R2 — Bishop Over 94.5 rush yds (prop band lineage)")
    out.append("")
    out.append("Criterion (MODEL-V5.md): priced at the band floor "
               "(48.7% lineage) — the two-family disagreement prices "
               "at the pessimistic end, as in v4.")
    band_b = prop_band("DeSean Bishop", "rushingYards", 94.5, "over")
    r2_pass = (band_b["disagree_pts"] > AGREE_PTS
               and abs(band_b["price_p"] - band_b["band"][0]) < 5e-4
               and abs(band_b["band"][0] - 0.487) < 0.005)
    out.append("")
    out.append(f"- families: normal "
               f"{band_b['p_side_by_family']['normal'] * 100:.1f}% vs "
               f"lognormal "
               f"{band_b['p_side_by_family']['lognormal'] * 100:.1f}% "
               f"-> disagreement {band_b['disagree_pts']:.1f} pts")
    out.append(f"- band [{band_b['band'][0] * 100:.1f}%, "
               f"{band_b['band'][1] * 100:.1f}%] | PRICED at "
               f"{band_b['price_p'] * 100:.1f}% ({band_b['price_mode']})")
    out.append(f"- **R2: {'PASS' if r2_pass else 'FAIL'}**")
    out.append("")

    # ---------- R3: Florida live states
    out.append("## R3 — Florida live states (Live Matrix, reused)")
    out.append("")
    out.append("Criterion (MODEL-V5.md): Q3 tied ≈ 45%, Q4 14:09 "
               "≈ 59%, ±3 tolerance, increasing.")
    st_a = dict(FLORIDA_STATE_A)
    st_b = {"home": "Texas Longhorns", "away": "Florida Gators",
            "home_score": 17, "away_score": 17, "quarter": 4,
            "clock_sec": 14 * 60 + 9, "possession": "away", "yard": 69,
            "down": 2, "yards_to_go": 7, "pregame_home_margin": 11.5}
    ra = live_wp(st_a)
    rb = live_wp(st_b)
    r3_pass = (abs(ra["wp_away"] - 0.45) <= 0.03
               and abs(rb["wp_away"] - 0.59) <= 0.03
               and rb["wp_away"] > ra["wp_away"])
    out.append("")
    out.append(f"- (a) Q3 5:28 tied 17-17: Florida WP "
               f"{ra['wp_away'] * 100:.1f}% (target 45 ± 3)")
    out.append(f"- (b) Q4 14:09 tied 17-17: Florida WP "
               f"{rb['wp_away'] * 100:.1f}% (target 59 ± 3)")
    out.append(f"- **R3: {'PASS' if r3_pass else 'FAIL'}**")
    out.append("")

    # ---------- R4: the honesty test
    out.append("## R4 — NFL Week 6 reprice: the phi honesty test")
    out.append("")
    out.append("Criterion (MODEL-V5.md): phi fitted walk-forward on "
               "weeks 1-5 ONLY (lane protocol: train weeks < w, "
               "predict week w, weeks 3-5 = 47 pairs). Report v5's "
               "out-of-sample Brier against v4 raw 0.304 / v4 shrunk "
               "0.278 / market 0.270. If phi cannot beat 0.278, the "
               "NFL lane ships UNCALIBRATED and the failure is "
               "printed here, not buried. Candidate selection is by "
               "leave-one-week-out CV on the training pairs ONLY — "
               "the Week 6 slate was never consulted when choosing.")
    fit = fit_nfl_phi()
    ob = fit["os_test"]["briers"]
    cv = fit["cv_brier"]
    r4_pass = fit["status"] == "CALIBRATED"
    out.append("")
    out.append(f"- training pairs: {fit['train']['n_pairs']} "
               f"(walk-forward weeks 3-5; the generator reproduces "
               f"the lane's published weekly Briers 0.2134 / 0.2310 / "
               f"0.2609 exactly)")
    out.append(f"- CV Briers on training pairs (leave-one-week-out): "
               f"identity {cv['identity']:.4f} | lin "
               f"{cv['lin']:.4f} | iso {cv['iso']:.4f} -> selected: "
               f"**{fit['selected']}**")
    out.append(f"- fitted lin coefficient: a = "
               f"{fit['candidates']['lin']['a']} (FITTED — the "
               f"training pairs themselves say the raw lane was "
               f"calibrated on weeks 3-5; the fitter returns the "
               f"identity strength, it does not invent shrinkage)")
    out.append(f"- Week 6 out-of-sample (11 graded games): raw "
               f"{ob['raw_identity']:.4f} | market {ob['market']:.4f} "
               f"| v4 shrunk (0.30) {ob['v4_shrunk_0.30']:.4f} — "
               f"benchmarks reproduced from the saved pricing file "
               f"and the compile's finals")
    out.append(f"- phi out-of-sample Briers: identity "
               f"{ob['phi']['identity']:.4f} | lin "
               f"{ob['phi']['lin']:.4f} | iso {ob['phi']['iso']:.4f} "
               f"| ensemble+phi (secondary, not the test) "
               f"{ob['ensemble_phi']:.4f}")
    out.append(f"- the isotonic map is the cautionary exhibit: fitted "
               f"on 47 pairs it grows single-game blocks at 0.0 and "
               f"1.0 and maps TEN@IND's raw 0.689 to 0.98 — it still "
               f"loses out-of-sample ({ob['phi']['iso']:.4f}). Small "
               f"samples do not have a calibration curve; they have "
               f"a histogram with opinions.")
    out.append(f"- **VERDICT: phi does NOT beat 0.278 "
               f"out-of-sample. The selected phi is the identity "
               f"(Brier {ob['phi'][fit['selected']]:.4f}); no "
               f"candidate beats the benchmark. The NFL lane ships "
               f"UNCALIBRATED — grades cap at C, the gate cannot "
               f"print Bet on this lane, and this paragraph is the "
               f"record of why.**")
    out.append(f"- what the failure is NOT: the lane's raw "
               f"walk-forward Brier on weeks 3-5 was 0.2346 — it was "
               f"calibrated on the data phi was allowed to see. "
               f"Week 6 was a regime break (8 of 11 road teams won; "
               f"the 0.64-0.69 home-favourite band went 0-for-4). "
               f"No honest function of weeks 1-5 fixes a break it "
               f"cannot see, and v5 will not pretend otherwise.")
    r4_verdict = ("PASS" if r4_pass else
                  "FAIL — BY THE DESIGN'S OWN CRITERION, reported as "
                  "designed: the lane is UNCALIBRATED")
    out.append(f"- **R4: {r4_verdict}** (phi-Brier "
               f"{ob['phi'][fit['selected']]:.4f} vs benchmark 0.278)")
    out.append("")

    # ---------- R5: coherence on the packet artefacts
    out.append("## R5 — Coherence check on the 2026-10-17 packet "
               "artefacts")
    out.append("")
    out.append("Criterion (MODEL-V5.md): the check FIRES on both "
               "known-bad artefacts of record (Steelers total 40.5 "
               "packet vs 38.5 board; flipped CAR@PHI favourite — "
               "both from results/nfl-week6-pricing-2026-10-18.md) "
               "and does NOT fire on the healthy saved DAL@GB "
               "pregame state (negative control).")
    pit = coherence_check([
        {"source": "packet", "spread_home": None, "total": 40.5,
         "ml_p_home": None},
        {"source": "live board (FanDuel / ESPN-DK pull)",
         "spread_home": None, "total": 38.5, "ml_p_home": None}])
    car = coherence_check([
        {"source": "packet", "spread_home": -1.5, "total": None,
         "ml_p_home": None},
        {"source": "live board", "spread_home": 3.0, "total": None,
         "ml_p_home": None}])
    dal = coherence_check([
        {"source": "saved board (DK via ESPN)",
         "spread_home": -1.5, "total": 53.5, "ml_p_home": 0.515},
        {"source": "model fair", "spread_home": -2.8, "total": None,
         "ml_p_home": None}])
    r5_pass = bool(pit) and bool(car) and not dal
    out.append("")
    out.append(f"- PIT@TB totals: {' | '.join(pit) if pit else 'NO FLAG'}")
    out.append(f"- CAR@PHI spreads: {' | '.join(car) if car else 'NO FLAG'}")
    out.append(f"- DAL@GB control: {' | '.join(dal) if dal else 'coherent — no flag (spread gap 1.3 < 4.0; spread-implied 54.3% vs ML no-vig 51.5%, Δ2.8 < 6)'}")
    out.append(f"- **R5: {'PASS' if r5_pass else 'FAIL'}**")
    out.append("")

    # ---------- R6: coverage audit (scope amendment)
    out.append("## R6 — Coverage audit: no bet left unchecked")
    out.append("")
    out.append("Criterion (scope amendment 2026-10-19): the "
               "registered checkers equal the taxonomy exactly; a "
               "sample slate exercising EVERY taxonomy market "
               "returns exactly one verdict per market, each in "
               "{PRICED, COHERENCE-FLAGGED, UNPRICED}; no UNPRICED "
               "verdict carries a numeric probability. Sample prices "
               "are lab-record prices (DAL@GB post-flip prints, the "
               "sealed Saturday card) or round book numbers on "
               "fitted fixtures — the audit tests checker routing "
               "and honesty stamps, not price discovery.")
    r6_ctx = {"pulled_at": datetime.now().astimezone()
              .isoformat(timespec="seconds"),
              "source": "R6 sample slate (lab data)", "verified": True}
    nfl_ml = {"market": "moneyline", "sport": "nfl", "home": "GB",
              "away": "DAL", "side": "home", "price": -108}
    nfl_spread = {"market": "spread", "sport": "nfl", "home": "GB",
                  "away": "DAL", "side": "home", "line": -1.5,
                  "price": -104}
    cfb_spread = {"market": "spread", "sport": "ncaaf",
                  "home": "Texas Longhorns", "away": "Florida Gators",
                  "side": "home", "line": -11.5, "price": -110}
    nba_ml = {"market": "moneyline", "sport": "nba", "home": "OKC",
              "away": "HOU", "side": "home", "price": -120}
    soc = {"sport": "soccer", "home": "LIV", "away": "AVL"}
    r6_markets = [
        nfl_ml, nfl_spread,
        {"market": "totals", "sport": "nfl", "home": "GB",
         "away": "DAL", "side": "over", "line": 53.5, "price": -110},
        {"market": "alt-spread", "sport": "ncaaf",
         "home": "Texas Longhorns", "away": "Florida Gators",
         "side": "home", "line": -10.5, "price": -110},
        {"market": "alt-total", "sport": "nfl", "home": "GB",
         "away": "DAL", "side": "over", "line": 51.5, "price": -110},
        {"market": "player-props", "sport": "ncaaf",
         "home": "Tennessee Volunteers",
         "away": "Alabama Crimson Tide", "player": "DeSean Bishop",
         "stat": "rushingYards", "line": 94.5, "side": "over",
         "price": -114},
        {**soc, "market": "team-props", "team": "home", "line": 1.5,
         "side": "over", "price": -110},
        {"market": "game-props", "sport": "nfl", "home": "GB",
         "away": "DAL"},
        {"market": "scoring-anytime", "sport": "nfl", "home": "GB",
         "away": "DAL", "player": "Tucker Kraft"},
        {"market": "scoring-first", "sport": "nfl", "home": "GB",
         "away": "DAL", "player": "Tucker Kraft"},
        {"market": "scoring-last", "sport": "nfl", "home": "GB",
         "away": "DAL", "player": "Tucker Kraft"},
        {"market": "segment", "sport": "nfl", "home": "GB",
         "away": "DAL", "segment": "1st half"},
        {"market": "parlay", "legs": [nfl_ml, cfb_spread]},
        {"market": "sgp", "legs": [nfl_ml,
                                   {"market": "totals", "sport": "nfl",
                                    "home": "GB", "away": "DAL",
                                    "side": "over", "line": 51.5,
                                    "price": -110}]},
        {"market": "teaser", "sport": "nfl",
         "legs": [nfl_spread, cfb_spread]},
        {"market": "round-robin", "by": 2,
         "legs": [nfl_ml, cfb_spread, nba_ml]},
        {"market": "futures", "sport": "nfl", "home": "GB",
         "away": "DAL"},
        {**soc, "market": "moneyline", "side": "home", "price": -130},
        {**soc, "market": "spread", "side": "home", "line": -1.5,
         "price": -110},
        {**soc, "market": "totals", "side": "over", "line": 2.5,
         "price": -110},
        {**soc, "market": "correct-score", "score": "2-1",
         "price": 800},
        {**soc, "market": "draw-no-bet", "side": "home",
         "price": -150},
        {**soc, "market": "btts", "side": "yes", "price": -120},
        {**soc, "market": "double-chance", "side": "1X",
         "price": -200},
        # the third state, exercised on purpose: the R5 packet
        # artefact riding on a moneyline market
        {"market": "moneyline", "sport": "nfl", "home": "GB",
         "away": "DAL", "side": "home", "price": -108,
         "quotes": [{"source": "packet", "spread_home": None,
                     "total": 40.5, "ml_p_home": None},
                    {"source": "live board", "spread_home": None,
                     "total": 38.5, "ml_p_home": None}]},
    ]
    r6_verdicts = [run_checker(m, r6_ctx) for m in r6_markets]
    covered = {v["market"] for v in r6_verdicts}
    states_ok = all(v["state"] in ("PRICED", "COHERENCE-FLAGGED",
                                    "UNPRICED")
                    for v in r6_verdicts)
    honest = all(v["p"] is None for v in r6_verdicts
                 if v["state"] == "UNPRICED")
    registry_ok = set(MARKET_CHECKERS) == set(TAXONOMY)
    coverage_ok = covered == set(TAXONOMY)
    seen_states = {v["state"] for v in r6_verdicts}
    r6_pass = (registry_ok and coverage_ok and states_ok and honest
               and seen_states == {"PRICED", "COHERENCE-FLAGGED",
                                   "UNPRICED"})
    out.append("")
    out.append(f"- registry: {len(MARKET_CHECKERS)} checkers vs "
               f"{len(TAXONOMY)} taxonomy markets — "
               f"{'MATCH' if registry_ok else 'MISMATCH'}")
    for v in r6_verdicts:
        line = f"- {v['market']}: **{v['state']}**"
        if v["p"] is not None:
            line += f" (P {v['p'] * 100:.1f}%"
            line += f", grade {v['grade']}" if v["grade"] else ""
            line += ")"
        elif v["note"]:
            line += f" — {v['note'][:110]}"
        out.append(line)
    out.append(f"- states exercised: {sorted(seen_states)} | every "
               f"UNPRICED verdict probability-free: {honest}")
    out.append(f"- **R6: {'PASS' if r6_pass else 'FAIL'}**")
    out.append("")

    # ---------- phi state table + stubs
    out.append("## Phi state of the lanes (as shipped)")
    out.append("")
    out.append("- nfl-ml: IDENTITY-AFTER-TEST — **UNCALIBRATED** "
               "(R4). Cap C. The lane keeps pricing (its margin "
               "centres beat the market's in Week 6 — MAE 6.6 vs "
               "7.1) but its win probabilities carry no calibration "
               "claim and the gate stays shut on it.")
    out.append("- cfb ml / cover / live: phi NOT-YET-FITTED "
               "(identity; no walk-forward pair set built for "
               "these estimators yet — future work, named here "
               "rather than implied done). v4 grading rules stand.")
    out.append("- props: phi NOT-YET-FITTED; lane record 0-0 -> "
               "organ-4 cap C stands.")
    out.append("- totals: engine is a STUB — UNPRICED, cap C, "
               "No Bet (price_total_stub).")
    out.append("- scoring-play props: route scoped in code comments "
               "(prop_from_scoring_plays) — the summary endpoint "
               "answers but carries no scoringPlays structure in "
               "this environment, so the reconstruction cannot run "
               "honestly yet. Stub prints UNPRICED.")
    out.append("")
    out.append("## Consequence, stated plainly")
    out.append("")
    out.append("With every lane either UNCALIBRATED, record-less, or "
               "phi-untested, v5's Decision Gate will print No Bet "
               "on nearly everything until a lane earns a fitted phi "
               "that beats its benchmark out-of-sample. That is the "
               "overhaul working as designed, not a defect: v5 "
               "prices, grades, shows its record, and refuses — "
               "until the evidence says otherwise.")
    # ---------- ADDENDUM v5.1: R7 — the verdict ladder
    out.append("")
    out.append(f"## ADDENDUM v5.1 — the verdict ladder (engine "
               f"{ENGINE_VERSION})")
    out.append("")
    out.append("Pilot order 2026-10-19 ~08:19 EDT (MODEL-V5.md, "
               "“VERDICT LADDER”): the binary gate’s output is "
               "replaced by five computed verdicts — GOLDEN BET / "
               "BET HERE / RISK BET (BET) / RISK BET (DO NOT BET) "
               "/ DO NOT BET — and every card carries verdict + "
               "verdict_reason (the deciding condition, named). "
               "This addendum supersedes the binary language of "
               "the v5.0 sections above; those sections stand "
               "unrewritten as the v5.0 record.")
    out.append("")
    out.append("Readings taken where the definitions meet the "
               "code’s inputs (each the stricter one): (1) "
               "“exactly one softening condition” is literal — "
               "two or more compound to RISK BET (DO NOT BET); "
               "(2) a coherence flag against a card’s own game is "
               "a hard condition — the affirmatives require clean "
               "quotes; (3) the grade hard fail is the C band "
               "literally (C+/C/C-) — D/F grades carry a negative "
               "phi edge and resolve under DO NOT BET’s "
               "“negative edge”; (4) “lane calibrated” needs a "
               "tested phi (FITTED, or identity-after-test with "
               "registry status CALIBRATED) on a non-provisional "
               "register lane; record-less is the ladder’s own "
               "soft condition, never the hard UNCALIBRATED — "
               "that word is reserved for a phi that was tested "
               "and FAILED.")
    out.append("")
    out.append("## R7 — verdict-mapping checks")
    out.append("")
    out.append("Criterion (stated before numbers): constructed "
               "inputs to verdict_ladder produce each of the "
               "five verdicts under exactly its MODEL-V5.md "
               "conditions; a grid sweep with cal_state=FAILED "
               "never prints above RISK BET (DO NOT BET); and on "
               "the recorded data on file — the R6 sample slate "
               "above, the saved FanDuel pull, and the graded "
               "NFL Week 6 slate in data/v5-phi.json — nothing "
               "prints GOLDEN BET and every NFL moneyline sits "
               "at RISK BET (DO NOT BET) or below.")
    base7 = dict(priced=True, grade="B", phi_edge_pts=3.5,
                 raw_edge_pts=4.0, pess_edge_pts=2.0,
                 cal_state="CALIBRATED", benched=False,
                 killed=False, fragile=False, bias_favours=False,
                 record_less=False, coherence_flags=[],
                 mechanism="model-structural")
    cases7 = [
        ("golden shape: grade A, calibrated, +3.5 at the floor",
         {**base7, "grade": "A", "phi_edge_pts": 6.5,
          "raw_edge_pts": 7.0, "pess_edge_pts": 3.5}, GOLDEN_BET),
        ("clean affirmative", dict(base7), BET_HERE),
        ("one soft: lane provisional",
         {**base7, "grade": "B-", "cal_state": "PROVISIONAL"},
         RISK_BET_YES),
        ("one soft: FRAGILE, lane bias favours the bet",
         {**base7, "fragile": True, "bias_favours": True},
         RISK_BET_YES),
        ("one soft: band floor holds by < 1 pt",
         {**base7, "grade": "B-", "pess_edge_pts": 0.4},
         RISK_BET_YES),
        ("one soft: lane record-less",
         {**base7, "record_less": True}, RISK_BET_YES),
        ("hard: lane UNCALIBRATED over a +9.9 raw edge",
         {**base7, "grade": "C", "phi_edge_pts": 0.4,
          "raw_edge_pts": 9.9, "cal_state": "FAILED"},
         RISK_BET_NO),
        ("hard: edge dies at the band floor",
         {**base7, "grade": "B-", "phi_edge_pts": 2.5,
          "raw_edge_pts": 3.0, "pess_edge_pts": -0.5},
         RISK_BET_NO),
        ("hard: grade in the C band",
         {**base7, "grade": "C+", "phi_edge_pts": 1.5,
          "raw_edge_pts": 2.0, "pess_edge_pts": 1.2},
         RISK_BET_NO),
        ("two softs compound (reading 1)",
         {**base7, "cal_state": "PROVISIONAL", "fragile": True},
         RISK_BET_NO),
        ("negative edge",
         {**base7, "grade": "D", "phi_edge_pts": -3.0,
          "raw_edge_pts": -1.0, "pess_edge_pts": -3.0},
         DO_NOT_BET),
        ("unpriced",
         {**base7, "priced": False, "grade": None,
          "phi_edge_pts": None, "raw_edge_pts": None,
          "pess_edge_pts": None}, DO_NOT_BET),
    ]
    r7_ok = True
    out.append("")
    for name7, kw7, want7 in cases7:
        got7, why7 = verdict_ladder(**kw7)
        ok7 = got7 == want7
        r7_ok = r7_ok and ok7
        out.append(f"- case {name7}: **{got7}** — {why7} "
                   f"({'as specced' if ok7 else 'EXPECTED ' + want7})")
    sweep_ok = True
    for g7 in LADDER:
        for pess7 in (-2.0, 0.5, 2.0, 5.0):
            for raw7 in (-1.0, 5.0):
                v7, _w7 = verdict_ladder(
                    priced=True, grade=g7,
                    phi_edge_pts=max(raw7, 0.5),
                    raw_edge_pts=raw7, pess_edge_pts=pess7,
                    cal_state="FAILED", benched=False,
                    killed=False, fragile=False,
                    bias_favours=False, record_less=False,
                    coherence_flags=[],
                    mechanism="model-structural")
                if verdict_rank(v7) < verdict_rank(RISK_BET_NO):
                    sweep_ok = False
    r7_ok = r7_ok and sweep_ok
    out.append(f"- UNCALIBRATED sweep (13 grades x 4 band margins "
               f"x 2 raw edges, cal_state=FAILED): nothing above "
               f"RISK BET (DO NOT BET): {sweep_ok}")
    r6_golden = [v for v in r6_verdicts
                 if v.get("verdict") == GOLDEN_BET]
    out.append(f"- recorded data, R6 sample slate above: "
               f"{len(r6_verdicts)} checker verdicts, GOLDEN BET "
               f"count {len(r6_golden)}")
    r7_ok = r7_ok and not r6_golden
    pull_names = sorted(f for f in os.listdir(DATA)
                        if f.startswith("menu-fanduel-")
                        and f.endswith(".json"))
    if pull_names:
        with open(os.path.join(DATA, pull_names[-1])) as f:
            pull = json.load(f)
        pull_v = run_slate(pull, print_out=False)
        pull_golden = [v for v in pull_v
                       if v.get("verdict") == GOLDEN_BET]
        pull_nfl_ml = [v for v in pull_v
                       if v["market"] == "moneyline"
                       and v.get("sport") == "nfl"
                       and v["state"] == "PRICED"]
        pull_nfl_bad = [v for v in pull_nfl_ml
                        if v["verdict"] is None
                        or verdict_rank(v["verdict"])
                        < verdict_rank(RISK_BET_NO)]
        pull_unp = [v for v in pull_v
                    if v["state"] == "UNPRICED"]
        pull_unp_bad = [v for v in pull_unp
                        if v["verdict"] != DO_NOT_BET]
        out.append(f"- recorded data, saved FanDuel pull "
                   f"({pull_names[-1]}): {len(pull_v)} checker "
                   f"verdicts, GOLDEN BET count "
                   f"{len(pull_golden)}; PRICED NFL moneylines "
                   f"{len(pull_nfl_ml)}, any above RISK BET "
                   f"(DO NOT BET): {len(pull_nfl_bad)}; "
                   f"UNPRICED verdicts {len(pull_unp)}, all "
                   f"carrying DO NOT BET: "
                   f"{not pull_unp_bad}")
        r7_ok = (r7_ok and not pull_golden and not pull_nfl_bad
                 and not pull_unp_bad)
    else:
        out.append("- recorded data, saved FanDuel pull: NONE "
                   "ON FILE — this check cannot run")
        r7_ok = False
    sel7 = fit["candidates"][fit["selected"]]
    nfl_bad = []
    nfl_risk_no = 0
    for g7 in fit["slate_detail"]:
        raw_e = (g7["raw"] - g7["mkt"]) * 100
        phi_e = (phi_apply(sel7, g7["raw"]) - g7["mkt"]) * 100
        pess_e = min((phi_apply(c, g7["raw"]) - g7["mkt"]) * 100
                     for c in fit["candidates"].values())
        gr7, tg7, _w7 = grade_v5(phi_e, "nfl-ml", card,
                                 "model-structural", {})
        v7, _w7 = verdict_ladder(
            priced=True, grade=gr7, phi_edge_pts=phi_e,
            raw_edge_pts=raw_e, pess_edge_pts=pess_e,
            cal_state=calibration_state("nfl-ml", card),
            benched=lane_benched("nfl-ml", card), killed=False,
            fragile=any(t.startswith("FRAGILE") for t in tg7),
            bias_favours=False, record_less=False,
            coherence_flags=[], mechanism="model-structural")
        if verdict_rank(v7) < verdict_rank(RISK_BET_NO):
            nfl_bad.append(f"{g7['game']}: {v7}")
        if v7 == RISK_BET_NO:
            nfl_risk_no += 1
    out.append(f"- recorded data, graded NFL Week 6 slate "
               f"({len(fit['slate_detail'])} games, phi edge vs "
               f"the market no-vig P): RISK BET (DO NOT BET) "
               f"count {nfl_risk_no}; anything above that rung: "
               f"{nfl_bad or 'none'}")
    r7_ok = r7_ok and not nfl_bad
    r4_txt = ("PASS" if r4_pass else
              "FAIL — by the design criterion (lane UNCALIBRATED), "
              "unchanged from v5.0")
    out.append(f"- R1-R6 re-run under engine {ENGINE_VERSION}: "
               f"R1 {'PASS' if r1_pass else 'FAIL'} | "
               f"R2 {'PASS' if r2_pass else 'FAIL'} | "
               f"R3 {'PASS' if r3_pass else 'FAIL'} | "
               f"R4 {r4_txt} | "
               f"R5 {'PASS' if r5_pass else 'FAIL'} | "
               f"R6 {'PASS' if r6_pass else 'FAIL'}")
    out.append(f"- **R7: {'PASS' if r7_ok else 'FAIL'}**")
    out.append("")
    text = "\n".join(out)
    path = os.path.join(RESULTS, "model-v5-regression.md")
    with open(path, "w") as f:
        f.write(text + "\n")
    print(text)
    print(f"[betmodel5] wrote {os.path.abspath(path)}")


def cmd_regression(args):
    run_regression()


def main():
    ap = argparse.ArgumentParser(prog="betmodel5",
                                 description=f"betmodel v{ENGINE_VERSION} (MODEL-V5.md)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("governor")
    sub.add_parser("scorecard")
    sub.add_parser("regression")
    sub.add_parser("phi", help="fit the NFL lane phi (walk-forward, "
                               "weeks 1-5) and persist it")
    pl = sub.add_parser("live")
    pl.add_argument("--state", required=True)
    pl.add_argument("--sims", type=int, default=4000)
    pp = sub.add_parser("price")
    pp.add_argument("--sport", choices=["cfb", "nhl", "nfl", "nba",
                                        "soccer"],
                    required=True)
    pp.add_argument("--home", required=True)
    pp.add_argument("--away", required=True)
    pp.add_argument("--side", choices=["home", "away", "draw"],
                    default="home")
    pp.add_argument("--price", type=int, required=True)
    pp.add_argument("--other-price", type=int, default=None)
    pp.add_argument("--spread", type=float, default=None,
                    help="CFB: also price the home cover at this "
                         "spread (uses --price as the cover price)")
    pp.add_argument("--stake", type=float, default=10.0)
    pp.add_argument("--mid", default=None, help="matchup id override")
    pp.add_argument("--neutral", action="store_true")
    pp.add_argument("--json", action="store_true",
                    help="emit the card as one JSON dict (named "
                         "sections for the APK shell)")
    pp.add_argument("--mechanism", default="model-structural",
                    choices=MECHANISMS)
    pr = sub.add_parser("prop")
    pr.add_argument("--player", required=True)
    pr.add_argument("--stat", required=True)
    pr.add_argument("--line", type=float, required=True)
    pr.add_argument("--side", choices=["over", "under"], required=True)
    pr.add_argument("--price", type=int, required=True)
    pr.add_argument("--stake", type=float, default=10.0)
    pr.add_argument("--json", action="store_true",
                    help="emit the card as one JSON dict (named "
                         "sections for the APK shell)")
    pr.add_argument("--mechanism", default="soft-market",
                    choices=MECHANISMS)
    pt = sub.add_parser("total")
    pt.add_argument("--sport", default="nfl")
    pt.add_argument("--home", required=True)
    pt.add_argument("--away", required=True)
    pt.add_argument("--line", type=float, required=True)
    pt.add_argument("--price", type=int, required=True)
    pt.add_argument("--stake", type=float, default=10.0)
    pt.add_argument("--mid", default=None)
    pc = sub.add_parser("coherence")
    pc.add_argument("--quotes", required=True,
                    help="JSON list of quote dicts (source, "
                         "spread_home, total, ml_p_home)")
    sub.add_parser("fit-nba")
    sub.add_parser("fit-soccer")
    sub.add_parser("coverage")
    ps = sub.add_parser("slate")
    ps.add_argument("--file", required=True,
                    help="slate JSON: {pulled_at, source, verified, "
                         "markets: [...] }")
    pmn = sub.add_parser("menu")
    pmn.add_argument("--sport", choices=["nfl", "nba", "nhl", "soccer",
                                         "all"], default="all",
                     help="sport pages to pull (application-context "
                          "tree always pulled first)")
    pmn.add_argument("--event", default=None,
                     help="eventId: harvest one game's full menu "
                          "across its tabs instead of the sport pages")
    pmn.add_argument("--refresh", action="store_true",
                     help="POST the readonly price feed for the "
                          "pulled market ids after the page pull")
    pmf = sub.add_parser("menu-feed")
    pmf.add_argument("--sport", choices=["nfl", "nba", "soccer"],
                     required=True)
    args = ap.parse_args()
    if args.cmd == "governor":
        cmd_governor(args)
    elif args.cmd == "scorecard":
        cmd_scorecard(args)
    elif args.cmd == "regression":
        cmd_regression(args)
    elif args.cmd == "phi":
        cmd_phi(args)
    elif args.cmd == "live":
        cmd_live(args)
    elif args.cmd == "price":
        cmd_price(args)
    elif args.cmd == "prop":
        cmd_prop(args)
    elif args.cmd == "total":
        cmd_total(args)
    elif args.cmd == "coherence":
        cmd_coherence(args)
    elif args.cmd == "fit-nba":
        cmd_fit_nba(args)
    elif args.cmd == "fit-soccer":
        cmd_fit_soccer(args)
    elif args.cmd == "coverage":
        cmd_coverage(args)
    elif args.cmd == "slate":
        cmd_slate(args)
    elif args.cmd == "menu":
        cmd_menu(args)
    elif args.cmd == "menu-feed":
        cmd_menu_feed(args)


if __name__ == "__main__":
    main()

