#!/usr/bin/env python3
"""
betmodel v5.2 — the full overhaul (design: MODEL-V5.md; ordered by the
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
out-of-sample benchmark reports UNCALIBRATED — since v5.2 that is a
DISPLAYED TAG on the card, not a grade cap: grades come from the edge
math on every lane, and the phi diagnostics stay printed (Record /
SCALE) where they inform the reader instead of silently capping.

Organ 3 — Unconventional Relationships (coherence). One margin
distribution must reconcile ML, spread and total: favourite flips
across sources, cross-source total disagreement >= 1.0, spread
disagreement >= 4.0 (the lab audit threshold), and within-source
ML/spread triangle breaks > 6 pts all print as AUDIT FLAGS.

Organ 4 — the Record on the Card. Every price leads with the
producing lane's scored Win # / Lose #. No scored record -> Win 0 /
Lose 0; the ladder counts record-less as a soft condition and the
lane's calibration tag shows the defect (v5.2: no grade cap).

Organ 5 — the Verdict Ladder (v5.1; Pilot order 2026-10-19,
MODEL-V5.md "VERDICT LADDER" — supersedes the v5.0 binary gate).
Five computed verdicts, never vibes: GOLDEN BET / BET HERE /
RISK BET (BET) / RISK BET (DO NOT BET) / DO NOT BET, each printed
with its verdict_reason (the deciding condition, named). The old
gate's conditions survive as the ladder's inputs. v5.2 grading
policy (Pilot order 2026-10-20): calibration no longer caps a
grade and no longer gates a verdict — it prints as a tag
(CALIBRATED / PROVISIONAL / UNCALIBRATED). GOLDEN BET requires an
A-band grade, a priced market, the pessimistic-end edge at/above
the golden threshold (+2.0 pts since v5.3 — Pilot order
2026-10-22; +3.0 through v5.2) and a named mechanism; BET HERE is
an A- or B-band grade with positive edge and no hard condition.
Grades: the GRADING.md rubric on the phi edge, moderately widened
in v5.2 (see base_grade), + v4 modifiers (FRAGILE -2 when the
lane's bias favours the bet, -1 otherwise; provisional-register
cap B). Every priced bet also carries a STANCE (BULLISH /
CONSERVATIVE / RISK) derived from its own probability, edge and
price — see bet_stance.

Totals engine — STUB, by design: until a pace/scoring companion
distribution exists AND has a scored record, totals print UNPRICED,
grade cap C, DO NOT BET (soccer totals DO price — off the Poisson grid,
which is a real fitted scoring distribution).

Totals, US lanes (Xii FIX-THE-LAZINESS, CODER GLOW): the stub above
is now CLOSED lane by lane where a real distribution earned it.
tools/fit_totals.py fits per-team off/def scoring rates x the
league's own home/away scoring environment (Normal totals for
nfl/ncaaf/nba, Poisson for nhl), walk-forward against the naive
league-average baseline. Lanes that PASS price totals through
totals_price() with the lane tagged UNTESTED (no scored totals
record exists yet — the tag, not a cap, carries that fact). A lane
whose fit FAILS its walk-forward ships FAILED-EXAM in its fit file
and keeps stamping UNPRICED with the exam numbers printed. NHL is
FAILED-EXAM as of this build (see data/v5-totals-nhl.json).

Round 2 (CODER GLOW): TEAM totals are their own cell — a team's
own scoring distribution (v5-teamtotals-<lane>.json), fitted and
examined separately from the game total; all four lanes PASSED
their team-level walk-forward (NFL/NCAAF/NBA solidly, NHL thinly)
and price through team_totals_price(). NHL GAME totals got their
one allowed refit with genuinely new information (starting-goalie
environment at 100% coverage of 1,312 games + rest/back-to-back
multipliers) and FAILED again (MAE 1.873 vs naive 1.841, Brier
0.2626 vs 0.2509) — terminally FAILED-EXAM for this loop; the
attempt lives in the fit file's refit_attempt_2 block. Props:
tools/fetch_gamelogs.py resolves players from a live pull to
ESPN athlete ids (search v2) and caches their game logs +
data/cache/athlete_index.json; athlete_info() reads that index,
so a prop prices whenever the player's log is on file and stays
UNPRICED BY NAME when it is not.

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

v5.4 (2026-10-24, BetFi Xii) — Organ 8, the Universal Fit
Registry: universal_registry() indexes every fit file in DATA
(soccer EPL + leagues, NBA, phi, CFB/NHL ratings + histories,
NFL pricing, lane history, recal params) and reports per
sport/league the fit kind, covered teams/players count,
fitted_at/source and the backtest block VERBATIM; a league with
no file is absent, never synthesized. universal_coverage()
reports, per sport/league on a pull, PRICED-capable vs UNPRICED
with the named missing piece — pure reporting, no verdict
changes. Soccer goes multi-league: data/v5-soccer-leagues.json
(tools/fit_soccer_leagues.py, real football-data.co.uk results,
same walk-forward protocol as fit_soccer) is selected by TEAM
MEMBERSHIP when both teams sit in exactly one league's
strengths. The shipped EPL fit keeps first precedence and its
numbers are unchanged — EPL grading is byte-for-byte v5.3's.
"""

import argparse
import gzip
import itertools
import json
import math
import os
import random
import statistics
import sys
import time
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
RESULTS = os.path.join(HERE, "..", "results")
CACHE = os.path.join(DATA, "cache")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(RESULTS, exist_ok=True)
PHI_PATH = os.path.join(DATA, "v5-phi.json")
HISTORY_PATH = os.path.join(DATA, "v5-lane-history.json")
NFL_PRICING_PATH = os.path.join(DATA, "nfl-week6-pricing.json")

ENGINE_VERSION = "5.4"   # v5.4 — BetFi Xii: Organ 8 universal fit registry + coverage, multi-league soccer (v5.3 was golden bar +2.0 + CLV/drift + Kelly)
# policy (Pilot order 2026-10-20); v5.1 was the verdict ladder

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
                       "nhl": 7524, "soccer": 1,
                       # v5.4 fix-guy R2: the rest of FanDuel's
                       # own menu tree (application-context
                       # EVENT_TYPES, enumerated live R1). These
                       # pages ARE pulled now — their markets
                       # arrive and stamp UNPRICED with a
                       # sport-level named reason until a checker
                       # is fitted for them. Invisible -> named.
                       "tennis": 2, "mma": 26420387, "golf": 3,
                       "boxing": 6, "cricket": 4, "darts": 3503,
                       "motorsport": 8, "rugby-union": 5,
                       "rugby-league": 1477, "lacrosse": 28608997,
                       "snooker": 6422, "table-tennis": 2593174}
# Engine keys for tree sports that are pulled but have NO
# checker/fit yet (R2). engine_price and universal_coverage
# stamp them with the sport-level named reason.
# R3 (fix-guy): tennis and mma left this list — both have
# fitted lanes now (v5-tennis.json / v5-mma.json). Table
# tennis, snooker and darts were ATTEMPTED in R3 and stay:
# no public match-results source exists for them (evidence
# in SPORT_CLOSERS / XII-SPORT-INVENTORY.md).
# R4 (fix-guy): cricket, rugby league, rugby union and
# motorsport left this list — each has a fitted + examined
# lane now (v5-cricket.json / v5-rugby.json / v5-f1.json;
# several lanes FAILED their exams and stamp FAILED-EXAM
# from their own branches, which is a verdict, not an
# absence). Golf, boxing and lacrosse stay: their branches
# stamp NAMED source/form terminals (BoxRec + DataGolf are
# gated — evidence in SPORT_CLOSERS), never a bare
# "no checker".
UNCHECKED_SPORTS = ("golf", "boxing",
                    "darts", "lacrosse", "snooker",
                    "table-tennis")
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


# ----------------------------------------------------------------
# Fit caching (v5.4, Snapdragon pass — item 10c). The checker
# pass used to RE-FIT the CFB/NHL lanes from their game pools on
# every market (fit_ratings ran the full sequential Elo over
# hundreds of games per call; cProfile on a 991-market pull:
# 281 fit_ratings calls ≈ 0.89 s of a 1.71 s pass) and re-read
# fit JSON from disk per market. Fits are pure functions of
# their files, so they are cached keyed by (path, mtime): a
# file rewritten on disk (a refit, a fresher pack seed) changes
# its mtime and the cache misses honestly. Cached values are
# returned as the SAME object — callers must not mutate them
# (the checkers never did; they read).

_FIT_CACHE = {}


def _mtime_key(paths):
    out = []
    for p in paths:
        try:
            out.append((p, os.path.getmtime(p)))
        except OSError:
            out.append((p, None))
    return tuple(out)


def _cached(key, builder):
    if key not in _FIT_CACHE:
        _FIT_CACHE[key] = builder()
    return _FIT_CACHE[key]


def _load_json_cached(path):
    """json.load with the mtime cache (missing file -> None)."""
    if not os.path.exists(path):
        return None
    key = ("json",) + _mtime_key([path])

    def build():
        with open(path) as f:
            return json.load(f)
    return _cached(key, build)


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


def _norm_name_uncached(s):
    """Name comparison form: lowercased, diacritics stripped
    ('San José' -> 'san jose'), apostrophes dropped ('Hawai'i'
    -> 'hawaii'). FanDuel prints both plain-ASCII forms; the
    ESPN-sourced fit keys do not always."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("'", "").replace("’", "").strip().lower()


@lru_cache(maxsize=65536)
def _norm_name_cached(s):
    return _norm_name_uncached(s)


def _norm_name(s):
    """Memoized wrapper for the pure name normalizer. Only
    strings use the cache, preserving the historical behavior
    for every other input type exactly."""
    if isinstance(s, str):
        return _norm_name_cached(s)
    return _norm_name_uncached(s)


_RESOLUTION_INDEX_CACHE = {}


def _resolution_index(ratings, aliases):
    """Precomputed normalized forms for one ratings/aliases pair.

    The resolver's semantics are deliberately unchanged: this
    index only avoids normalizing every candidate key on every
    lookup. Strong references in the cache entry prevent id()
    reuse from ever pairing an index with a different dict, and
    the cache is bounded because fit dictionaries are the only
    long-lived inputs expected here."""
    key = (id(ratings), id(aliases) if aliases is not None else None)
    ent = _RESOLUTION_INDEX_CACHE.get(key)
    if ent is not None and ent[0] is ratings and ent[1] is aliases:
        return ent[2]
    pairs = tuple((k, _norm_name(k)) for k in ratings)
    exact = {}
    for k, nk in pairs:
        exact.setdefault(nk, k)
    alias_exact = {}
    if aliases:
        for name, target in aliases.items():
            if target in ratings:
                alias_exact.setdefault(_norm_name(name), target)
    index = (pairs, exact, alias_exact)
    if len(_RESOLUTION_INDEX_CACHE) >= 64:
        _RESOLUTION_INDEX_CACHE.clear()
    _RESOLUTION_INDEX_CACHE[key] = (ratings, aliases, index)
    return index


def _resolve_or_none(ratings, query, aliases=None):
    """Canonical team-membership resolution (v5.4 fix-guy): the
    ONE resolver the checkers and universal_coverage both use.
    Order: exact key -> explicit alias (only when its target is
    itself a key in this ratings dict) -> unique word-boundary
    PREFIX match (the school-name form: 'Georgia Tech' in
    'Georgia Tech Yellow Jackets') -> unique substring match.
    All comparisons run through _norm_name. Ambiguous after
    aliases -> None: a name that could be two real teams NEVER
    resolves into one of them by guessing."""
    if query is None:
        return None
    q = _norm_name(query)
    if not q:
        return None
    pairs, exact, alias_exact = _resolution_index(ratings, aliases)
    if q in exact:
        return exact[q]
    if aliases and q in alias_exact:
        return alias_exact[q]
    hits = [t for t, nt in pairs if nt.startswith(q + " ")]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        return None
    hits = [t for t, nt in pairs if q in nt]
    if len(hits) == 1:
        return hits[0]
    return None


def resolve_team(ratings, query, aliases=None):
    hit = _resolve_or_none(ratings, query, aliases)
    if hit is not None:
        return hit
    q = _norm_name(query)
    hits = [t for t in ratings if q in _norm_name(t)]
    if not hits:
        raise SystemExit(f"[betmodel] team not found in fitted data: '{query}'")
    raise SystemExit(f"[betmodel] ambiguous team '{query}': {sorted(hits)}")


# FanDuel prints SCHOOL names for college football ('Georgia',
# 'Alabama', 'Ohio'); the fit keys carry mascots ('Georgia
# Bulldogs'). Where a school name is a prefix of more than one
# fit key, the flagship program is the school FanDuel means —
# enumerated explicitly here, every target verified as a key of
# the CFB pool. An alias fires only when its target is in the
# ratings dict being queried, so it can never invent a team.
FD_CFB_SCHOOL_ALIASES = {
    "Alabama": "Alabama Crimson Tide",
    "Appalachian State": "App State Mountaineers",
    "Arizona": "Arizona Wildcats",
    "Arkansas": "Arkansas Razorbacks",
    "Colorado": "Colorado Buffaloes",
    "Delaware": "Delaware Blue Hens",
    "FIU": "Florida International Panthers",
    "Florida": "Florida Gators",
    "Georgia": "Georgia Bulldogs",
    "Houston": "Houston Cougars",
    "Illinois": "Illinois Fighting Illini",
    "Indiana": "Indiana Hoosiers",
    "Iowa": "Iowa Hawkeyes",
    "Kansas": "Kansas Jayhawks",
    "Louisiana": "Louisiana Ragin' Cajuns",
    "Miami": "Miami Hurricanes",
    "Miami Florida": "Miami Hurricanes",
    "Miami Ohio": "Miami (OH) RedHawks",
    "Michigan": "Michigan Wolverines",
    "Missouri": "Missouri Tigers",
    "Montana": "Montana Grizzlies",
    "Idaho": "Idaho Vandals",
    "New Mexico": "New Mexico Lobos",
    "North Carolina": "North Carolina Tar Heels",
    "North Dakota": "North Dakota Fighting Hawks",
    "South Carolina": "South Carolina Gamecocks",
    "South Dakota": "South Dakota Coyotes",
    "Northwestern": "Northwestern Wildcats",
    "Ohio": "Ohio Bobcats",
    "Oklahoma": "Oklahoma Sooners",
    "Oregon": "Oregon Ducks",
    "Sam Houston State": "Sam Houston Bearkats",
    "Tennessee": "Tennessee Volunteers",
    "Texas": "Texas Longhorns",
    "UMass": "Massachusetts Minutemen",
    "Utah": "Utah Utes",
    "Virginia": "Virginia Cavaliers",
    "Washington": "Washington Huskies",
}

# FanDuel prints full MLB names; the MLB fit (v5-mlb.json, R2)
# keys on ESPN abbreviations — the same lookup-table pattern as
# the NFL/NBA maps. A name that misses the map stays UNPRICED
# with its name printed, never silently dropped.
FD_MLB_TEAM_CODES = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Chicago White Sox": "CHW",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL", "Detroit Tigers": "DET",
    "Houston Astros": "HOU", "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Athletics": "ATH",
    "Oakland Athletics": "ATH", "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD",
    "San Francisco Giants": "SF", "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH"}


def resolve_mlb_team(query, ratings=None):
    """Full FanDuel name (or a bare code) -> the MLB fit's ESPN
    abbreviation, or None (same contract as resolve_nfl_team)."""
    if query is None:
        return None
    q = str(query).strip()
    if ratings is not None and q.upper() in ratings:
        return q.upper()
    for name, code in FD_MLB_TEAM_CODES.items():
        if name.lower() == q.lower():
            if ratings is None or code in ratings:
                return code
    if ratings is not None and q in ratings:
        return q
    return None


# FanDuel prints full NBA names; the NBA fit keys on codes (the
# FD_NFL_TEAM_CODES pattern, one lane over). Every code verified
# as a key of the shipped v5-nba fit.
FD_NBA_TEAM_CODES = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN", "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET", "Golden State Warriors": "GS",
    "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NO", "New York Knicks": "NY",
    "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SA", "Toronto Raptors": "TOR",
    "Utah Jazz": "UTAH", "Washington Wizards": "WSH",
}


def resolve_nba_team(query, ratings=None):
    """Full FanDuel name (or a bare code) -> the NBA fit's code,
    or None. `ratings` defaults to the shipped fit's ratings."""
    if query is None:
        return None
    if ratings is None:
        fit = load_nba()
        ratings = (fit or {}).get("ratings") or {}
    q = str(query).strip()
    if q in ratings:
        return q
    if q.upper() in ratings:
        return q.upper()
    for name, code in FD_NBA_TEAM_CODES.items():
        if name.lower() == q.lower() and code in ratings:
            return code
    return None


def resolve_nfl_team(query, ratings=None):
    """Full FanDuel name (or a bare code) -> the NFL lane's code,
    via FD_NFL_TEAM_CODES (defined with the menu stack; resolved
    at call time). None when the name maps to no fitted team."""
    if query is None:
        return None
    q = str(query).strip()
    if ratings is not None and q.upper() in ratings:
        return q.upper()
    for name, code in FD_NFL_TEAM_CODES.items():
        if name.lower() == q.lower():
            if ratings is None or code in ratings:
                return code
    if ratings is not None and q in ratings:
        return q
    return None


# Teams FanDuel files under a US sport key that belong to a
# DIFFERENT competition this app does not model. Coverage names
# the real competition instead of blaming the lane's fit — but
# only for teams on this explicit list, and only when the lane's
# own resolver has already failed on the name (so a listed name
# can never shadow a fitted team). Rosters: CFL 9 (2025), AHL 32
# (2025-26), NBL 10 (2025-26), WNBA 13 (2025), plus the NCAA
# hockey programs observed on the hockey board.
OTHER_COMPETITION_TEAMS = {}
for _t in ("BC Lions", "Calgary Stampeders", "Edmonton Elks",
           "Hamilton Tiger-Cats", "Montreal Alouettes",
           "Ottawa Redblacks", "Saskatchewan Roughriders",
           "Toronto Argonauts", "Winnipeg Blue Bombers"):
    OTHER_COMPETITION_TEAMS[_t] = "CFL"
for _t in ("Abbotsford Canucks", "Bakersfield Condors",
           "Belleville Senators", "Bridgeport Islanders",
           "Calgary Wranglers", "Charlotte Checkers",
           "Chicago Wolves", "Cleveland Monsters",
           "Coachella Valley Firebirds", "Colorado Eagles",
           "Grand Rapids Griffins", "Hartford Wolf Pack",
           "Henderson Silver Knights", "Hershey Bears",
           "Iowa Wild", "Laval Rocket",
           "Lehigh Valley Phantoms", "Manitoba Moose",
           "Milwaukee Admirals", "Ontario Reign",
           "Providence Bruins", "Rochester Americans",
           "Rockford IceHogs", "San Diego Gulls",
           "San Jose Barracuda", "Springfield Thunderbirds",
           "Syracuse Crunch", "Texas Stars", "Toronto Marlies",
           "Tucson Roadrunners", "Utica Comets",
           "Wilkes-Barre/Scranton Penguins"):
    OTHER_COMPETITION_TEAMS[_t] = "AHL"
for _t in ("Bentley Falcons", "Boston University Terriers",
           "Denver Pioneers", "Ferris State Bulldogs",
           "Miami Ohio Redhawks", "Niagara Purple Eagles",
           "Providence Friars"):
    OTHER_COMPETITION_TEAMS[_t] = "NCAA hockey"
for _t in ("Adelaide 36ers", "Brisbane Bullets",
           "Cairns Taipans", "Illawarra Hawks",
           "Melbourne United", "New Zealand Breakers",
           "Perth Wildcats", "South East Melbourne Phoenix",
           "Sydney Kings", "Tasmania JackJumpers"):
    OTHER_COMPETITION_TEAMS[_t] = "NBL (Australia)"
for _t in ("Atlanta Dream", "Chicago Sky", "Connecticut Sun",
           "Dallas Wings", "Golden State Valkyries",
           "Indiana Fever", "Las Vegas Aces", "Los Angeles Sparks",
           "Minnesota Lynx", "New York Liberty", "Phoenix Mercury",
           "Seattle Storm", "Washington Mystics"):
    OTHER_COMPETITION_TEAMS[_t] = "WNBA"
# R4 (fix-guy): FanDuel's Baseball page also files OTHER
# leagues' fixtures under "mlb" (NPB / KBO / CPBL observed
# live 2026-10-24), and its Basketball page files CBA and
# other overseas leagues under "nba" (observed live the same
# day). Rosters: NPB 12, KBO 10, CPBL 6 (2026), CBA 20
# (2025-26); the BBL / B.League / British entries are the
# teams observed on the live board.
for _t in ("Chiba Lotte Marines", "Chunichi Dragons",
           "Fukuoka Hawks", "Fukuoka SoftBank Hawks",
           "Hanshin Tigers", "Hiroshima Toyo Carp",
           "Hokkaido Nippon-Ham Fighters", "Orix Buffaloes",
           "Saitama Seibu Lions",
           "Tohoku Rakuten Golden Eagles",
           "Tokyo Yakult Swallows", "Yokohama Dena Baystars",
           "Yokohama DeNA BayStars", "Yomiuri Giants"):
    OTHER_COMPETITION_TEAMS[_t] = "NPB (Japan)"
for _t in ("Doosan Bears", "Hanwha Eagles", "Kia Tigers",
           "Kiwoom Heroes", "KT Wiz", "LG Twins",
           "Lotte Giants", "NC Dinos", "Samsung Lions",
           "SSG Landers"):
    OTHER_COMPETITION_TEAMS[_t] = "KBO (Korea)"
for _t in ("CTBC Brothers", "Fubon Guardians",
           "Rakuten Monkeys", "TSG Hawks",
           "Uni-President 7-Eleven Lions", "Wei Chuan Dragons"):
    OTHER_COMPETITION_TEAMS[_t] = "CPBL (Taiwan)"
for _t in ("Beijing Ducks", "Beijing Royal Fighters",
           "Fujian Sturgeons", "Guangdong Southern Tigers",
           "Guangzhou Loong Lions", "Jiangsu Dragons",
           "Jilin Northeast Tigers", "Liaoning Flying Leopards",
           "Nanjing Monkey Kings", "Ningbo Rockets",
           "Qingdao Eagles", "Shandong Heroes", "Shanghai Sharks",
           "Shanxi Loongs", "Shenzhen Aviators",
           "Sichuan Blue Whales", "Tianjin Pioneers",
           "Xinjiang Flying Tigers", "Zhejiang Golden Bulls",
           "Zhejiang Guangsha Lions"):
    OTHER_COMPETITION_TEAMS[_t] = "CBA (China)"
for _t in ("Phoenix Hagen", "Basketball Lowen Braunschweig"):
    OTHER_COMPETITION_TEAMS[_t] = "BBL (Germany)"
for _t in ("Tokyo Sun Rockers", "Nagoya Diamond Dolphins"):
    OTHER_COMPETITION_TEAMS[_t] = "B.League (Japan)"
for _t in ("Cheshire Phoenix", "Surrey 89ers"):
    OTHER_COMPETITION_TEAMS[_t] = "British Basketball League"
del _t


def other_competition_for(home, away):
    """(team, competition) for the first of home/away that sits
    on OTHER_COMPETITION_TEAMS, else None. ONE lookup used by
    every checker and by coverage, so the two layers can never
    name different truths for the same fixture."""
    for t in (home, away):
        if t is not None and t in OTHER_COMPETITION_TEAMS:
            return t, OTHER_COMPETITION_TEAMS[t]
    return None


def competition_missing(sport, home, away):
    """The standard competition-truth stamp, or None when
    neither team is a known other-competition team."""
    hit = other_competition_for(home, away)
    if not hit:
        return None
    team, comp = hit
    return (f"competition not in this app: {comp} ({team}) — "
            f"FanDuel files it under {sport}, it is not a "
            f"{sport} team")


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


def _athlete_index():
    """The fetched-athlete index (data/cache/athlete_index.json,
    built by Glow's tools/fetch_gamelogs.py): name -> {id,
    league_path, season, team} for every player whose gamelog
    this program has resolved + cached. Absent file = empty
    index. R4 (fix-guy): ported so the seeded on-device cache
    resolves the same players the lab cache does."""
    return _load_json_cached(os.path.join(
        CACHE, "athlete_index.json")) or {}


def athlete_info(name):
    """Resolve a player to their ESPN gamelog coordinates: the
    hand-resolved ATHLETES table first (the v3 three), then the
    fetched athlete index. KeyError when neither knows the
    player — the props checker stamps that UNPRICED by name."""
    if name in ATHLETES:
        return dict(ATHLETES[name])
    ent = _athlete_index().get(name)
    if ent:
        return {"id": ent["id"], "team": ent.get("team"),
                "league_path": ent.get("league_path")
                or "football/college-football",
                "season": ent.get("season") or 2026}
    raise KeyError(name)


def fetch_gamelog(name):
    info = athlete_info(name)
    cache_name = f"gamelog_{info['id']}.json"
    path = info.get("league_path") or "football/college-football"
    season = info.get("season") or 2026
    url = ("https://site.api.espn.com/apis/common/v3/sports/"
           f"{path}/athletes/{info['id']}/gamelog?season={season}")
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
    v5.2 (Pilot order 2026-10-20): the bands are MODERATELY WIDENED —
    every threshold from A+ through D- sits ~1 pt lower than the
    frozen v3.1/v5.1 rubric, so a solid-but-not-extreme edge reaches
    B (now +2.0) and the A band opens at +4.0. Old -> new floors:
    A+ 8->7, A 6->5, A- 5->4, B+ 4->3, B 3->2, B- 2->1.5,
    C+ 1->0.5, C -1->-1.5, C- -2->-2.5, D+ -3->-3.5, D -4->-4.5,
    D- -5->-5.5, F below. D-band interpolation as before: GRADING.md
    gives D as one band and names no D+/D-; equal steps mirror the
    B and C bands."""
    for lo, g in [(7, "A+"), (5, "A"), (4, "A-"), (3, "B+"), (2, "B"),
                  (1.5, "B-"), (0.5, "C+"), (-1.5, "C"), (-2.5, "C-"),
                  (-3.5, "D+"), (-4.5, "D"), (-5.5, "D-")]:
        if edge_pts >= lo:
            return g
    return "F"


# v5.2 grade bands as data (the Equations page prints this table;
# it must match base_grade above — the regression asserts it).
GRADE_BANDS_V52 = [(7, "A+"), (5, "A"), (4, "A-"), (3, "B+"),
                   (2, "B"), (1.5, "B-"), (0.5, "C+"), (-1.5, "C"),
                   (-2.5, "C-"), (-3.5, "D+"), (-4.5, "D"),
                   (-5.5, "D-")]


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
    (v1 load_games — today's games are excluded by POOL_CUTOFF).
    v5.4: the fit is computed ONCE per games-file mtime and
    cached (see _FIT_CACHE) — identical numbers, no refit per
    market."""
    fn = "cfb_games_2026.json" if sport == "cfb" \
        else "nhl_games_2026-27.json"
    key = ("fit_ratings", sport) + _mtime_key(
        [os.path.join(DATA, fn)])
    return _cached(key, lambda: _fit_ratings_uncached(sport))


def _fit_ratings_uncached(sport):
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
    the v1.1-B form. Returns slope, residual SD, pool size.
    v5.4: cached per games-file mtime (see _FIT_CACHE)."""
    key = ("fit_margin_lane",) + _mtime_key(
        [os.path.join(DATA, "cfb_games_2026.json")])
    return _cached(key, _fit_margin_lane_uncached)


def _fit_margin_lane_uncached():
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
    _al = FD_CFB_SCHOOL_ALIASES if sport == "cfb" else None
    home = resolve_team(dists, home, _al)
    away = resolve_team(dists, away, _al)
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
                    + (" (this lane's known bias leans toward this "
                       "bet)" if bias_favours else ""))
    give = flags.get("price_discipline_pts") or 0
    if give > 0:
        steps = max(1, int(give) // 50)
        idx = min(idx + steps, len(LADDER) - 1)
        tags.append(f"PRICE DISCIPLINE -{steps} step"
                    f"{'s' if steps != 1 else ''} (price moved "
                    f"{give} against the opener)")
    weakest = flags.get("weakest_leg_grade")
    if weakest:
        idx = max(idx, LADDER.index(weakest))
        tags.append(f"GROUPING CAP — the slip grades at its "
                    f"weakest leg ({weakest})")
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
    info = athlete_info(name)
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
        if sd == 0:
            # Zero-variance log (every game identical \u2014 e.g.
            # a 10-game run of zeros): the fitted distribution
            # is a point mass at the mean and both families
            # degenerate to its step. That IS the limit of the
            # normal/lognormal as sd -> 0, not an invention;
            # dividing by sd=0 here used to ZeroDivisionError
            # the checker (found Round 3: Treadwell, Fields).
            step = 1.0 if mean > line else \
                (0.0 if mean < line else 0.5)
            fams["normal"] = step
            fams["lognormal"] = step
            fams["lognormal_note"] = ("zero-variance log: both "
                                      "families degenerate to "
                                      "the point mass at the mean")
        else:
            fams["normal"] = norm_sf(line, mean, sd)
        pos = [x for x in series if x > 0]
        if sd == 0:
            pass  # degenerate case handled above
        elif len(pos) == n and n > 1:
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


# NFL derived fair-spread map (R2, fix-guy): fair_spread_home =
# NFL_FAIR_MAP_A + NFL_FAIR_MAP_B * (ratings diff incl. the
# lane's 55-pt home-field Elo bump). Refit by least squares on
# the saved slate's 13 (diff, fair) pairs in
# nfl-week6-pricing.json: in-sample MAE 0.017 pts, max 0.04;
# leave-one-out MAE 0.020. The map reproduces how the slate's
# own fairs were built from these ratings — it is a derivation
# from the lane's fitted ratings, validated, not an invention.
NFL_FAIR_MAP_A = 4.3591
NFL_FAIR_MAP_B = -0.087898


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
               "per MODEL-V5.md R4 — a displayed tag since v5.2; "
               "grades no longer cap on it.")),
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
    return _load_json_cached(PHI_PATH)


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
    """The lane's calibration defect, if any: the lane failed its
    phi benchmark test (registry status UNCALIBRATED), or it has no
    scored record (organ 4). Returns a reason string or None.
    v5.2: this is a DIAGNOSTIC — it feeds the displayed calibration
    tag (calibration_tag) and the Record/SCALE lines. Through v5.1
    it was also a grade cap (cap C); the Pilot's v5.2 policy removed
    the cap — the defect is shown, not silently enforced."""
    if lane in ("nfl-ml", "nfl"):
        fit = load_phi_registry()
        if fit and fit["status"] == "UNCALIBRATED":
            return "UNCALIBRATED (phi failed its out-of-sample test)"
    w, l, _ = lane_record(lane)
    if w + l == 0:
        return "UNTESTED (no scored record yet)"
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
        flags.append("FAVORITE FLIP across sources: "
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
# GRADING.md rubric on the PHI edge (v5.2 widened bands — base_grade)
# + v4 modifiers (via grade_v4). Through v5.1 this layer also applied
# the v5 caps (UNCALIBRATED / no-record -> C); v5.2 removed them by
# Pilot order — calibration is a displayed tag now (calibration_tag),
# and the phi diagnostics stay computed and printed.

def grade_v5(phi_edge_pts, lane, card, mechanism, flags=None):
    flags = flags or {}
    grade, tags, why = grade_v4(phi_edge_pts, lane, card, mechanism,
                                flags)
    return grade, tags, why


# ================================================================ stance (v5.2)
# Every priced bet also carries a STANCE — a plain-language posture
# derived ONLY from numbers the engine already produced for the bet
# itself (its final model probability, its phi edge in points, its
# book price). No new pricing, no new data. Thresholds (documented
# on the app's Terms and Equations pages):
#   CONSERVATIVE — the boring-favourite profile: model probability
#     >= 0.65 with an edge under the B floor (+2.0 pts): you are
#     paying for likelihood, not for edge.
#   BULLISH — a strong position: edge >= +2.0 pts (the B-band floor)
#     with model probability >= 0.45 and implied probability > 0.35:
#     real edge on a side the model genuinely rates.
#   LONGSHOT — the longshot / high-variance profile: implied probability
#     <= 0.35, or plus-money at +200 or longer, or model probability
#     <= 0.45 without the BULLISH shape — the return comes from the
#     payout shape, not from likelihood.
#   A priced bet matching none of the three shapes above falls to
#   CONSERVATIVE when its model probability is >= 0.60 (likelihood
#   is the story) and to LONGSHOT otherwise (variance is).
STANCE_BULLISH_MIN_EDGE = 2.0     # the v5.2 B-band floor, in pts
STANCE_CONSERVATIVE_MIN_P = 0.65
STANCE_RISK_MAX_P = 0.35
STANCES = ["BULLISH", "CONSERVATIVE", "LONGSHOT"]


def bet_stance(p_final, edge_pts, price):
    """(v5.2) The stance of one priced bet, from its own numbers.
    Returns one of STANCES, or None when the bet is not priced
    (UNPRICED bets get no stance — they stay DO NOT BET with the
    named reason)."""
    if p_final is None or edge_pts is None or price is None:
        return None
    implied = implied_prob(price)
    if p_final >= STANCE_CONSERVATIVE_MIN_P \
            and edge_pts < STANCE_BULLISH_MIN_EDGE:
        return "CONSERVATIVE"
    if edge_pts >= STANCE_BULLISH_MIN_EDGE and p_final >= 0.45 \
            and implied > STANCE_RISK_MAX_P:
        return "BULLISH"
    if implied <= STANCE_RISK_MAX_P or price >= 200 \
            or p_final <= 0.45:
        return "LONGSHOT"
    if p_final >= 0.60:
        return "CONSERVATIVE"
    return "LONGSHOT"


def parlay_stance(leg_stances):
    """(v5.2) The combined stance of a parlay, from its legs'
    stances (the Terms page states this rule): the longest shot
    sets the slip — any LONGSHOT leg makes the parlay LONGSHOT; else any
    BULLISH leg makes it BULLISH; a slip whose legs are all
    CONSERVATIVE is CONSERVATIVE. None when a leg has no stance."""
    if not leg_stances or any(s is None for s in leg_stances):
        return None
    if "LONGSHOT" in leg_stances:
        return "LONGSHOT"
    if "BULLISH" in leg_stances:
        return "BULLISH"
    return "CONSERVATIVE"


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


GOLDEN_THRESHOLD_PTS = 2.0  # v5.3 (Pilot order 2026-10-22): the
# GOLDEN pessimistic-edge bar — +3.0 in v5.0-v5.2, loosened one notch
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


CALIBRATION_TAGS = ["CALIBRATED", "PROVISIONAL", "UNCALIBRATED",
                    "UNTESTED"]


def calibration_tag(lane, card):
    """(v5.2) The DISPLAYED calibration tag for a lane — the word
    the card, the feed and the Record print. Four states, kept
    apart because they are not the same thing:
      UNCALIBRATED — a phi was walk-forward TESTED and FAILED its
        benchmark (the NFL lane after R4).
      UNTESTED — the lane has no scored record yet: nothing has
        been tested because there is nothing to test against. A
        lane with no record has not failed anything.
      PROVISIONAL — a record exists but the phi is untested
        (NOT-YET-FITTED), or the lane's register is provisional.
      CALIBRATED — a tested phi stands on a scored lane.
    Through v5.1 the FAILED state capped grades at C and gated the
    ladder; under the v5.2 policy the tag informs the reader and
    blocks nothing."""
    if calibration_state(lane, card) == "FAILED":
        return "UNCALIBRATED"
    w, l, _ = lane_record(lane)
    if w + l == 0:
        return "UNTESTED"
    return calibration_state(lane, card)


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
    survives, >= +2 survives with the golden spare (v5.3), < +1 is the
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
    (4) Record-less is the ladder's own soft condition.

    v5.2 readings (Pilot order 2026-10-20, superseding the v5.1
    calibration rules): (5) calibration_state is accepted and
    named in affirmative reasons, but it is NO LONGER a hard or
    soft condition in either direction — a FAILED (UNCALIBRATED)
    lane's bets climb the ladder on their grade and edge alone,
    and a CALIBRATED lane earns no rung it did not earn on the
    numbers. The tag prints on the card instead (calibration_tag).
    (6) GOLDEN BET: A-band grade (A+/A/A-), priced, pessimistic-end
    edge >= +2.0 (the golden threshold — +3.0 through v5.2,
    loosened one notch by Pilot order 2026-10-22, v5.3), and a named
    mechanism — no soft condition outstanding. Absent the mechanism
    tag, a golden-shaped bet prints BET HERE with the withholding
    named. (7) BET HERE: A- or B-band grade, positive edge, no hard
    condition, no soft condition outstanding."""
    if not priced:
        return DO_NOT_BET, ("UNPRICED: no probability the system "
                            "can defend")
    coh = list(coherence_flags or [])
    signal = bool((raw_edge_pts is not None and raw_edge_pts > 0)
                  or coh)
    # v5.2: calibration is NOT among the softs or the hards — it
    # is a displayed tag (reading 5). The tag word for reasons:
    tag = {"FAILED": "UNCALIBRATED"}.get(cal_state, cal_state)
    softs = []
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
    if pess_edge_pts is not None and pess_edge_pts <= 0:
        hards.append("at the model's pessimistic number, the edge "
                     "is gone")
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
        return DO_NOT_BET, (f"grade {grade} is below the ladder's "
                            f"B- floor")
    # ---- the affirmative zone: gate-grade edge, no hard condition
    if not softs:
        golden_shape = (LADDER.index(grade) <= LADDER.index("A-")
                        and pess_edge_pts is not None
                        and pess_edge_pts >= GOLDEN_THRESHOLD_PTS)
        if golden_shape and mechanism in MECHANISMS:
            return GOLDEN_BET, (
                f"edge still {pess_edge_pts:+.1f} pts at the "
                f"band's pessimistic end; reason the market may "
                f"be wrong: {mechanism}; calibration tag {tag} — "
                f"displayed, not a gate")
        if golden_shape:
            return BET_HERE, ("not golden: no named reason the "
                              "market may be wrong (no mechanism "
                              "tag)")
        return BET_HERE, ("clean bet by the ladder's rules: "
                          "A/B-band grade, edge positive, no "
                          "cautions standing, edge still positive "
                          f"at the band's low end; calibration tag "
                          f"{tag} — displayed, not a gate")
    if len(softs) == 1:
        return RISK_BET_YES, softs[0]
    return RISK_BET_NO, ("two or more cautions on one bet — the "
                         "ladder allows one: "
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
    cal_tag = calibration_tag(lane, card)
    stance = (bet_stance(p_final, edge, price)
              if p_final is not None else None)
    if stance:
        out.append(f"Stance {stance} · calibration {cal_tag}")
    w_m, w_k, w_note = ensemble_weights(lane)
    if p_final is None:
        detail = (f"odds {int(price):+d} | stake ${stake:.2f} | "
                  f"UNPRICED — no probability the system can defend")
    else:
        detail = (f"odds {int(price):+d} | payout {dec:.2f}x / "
                  f"${stake * dec:.2f} | stake ${stake:.2f} | win% "
                  f"{p_final * 100:.1f} vs {implied * 100:.1f} implied "
                  f"| edge {edge:+.1f} pts | EV "
                  f"{'+' if ev >= 0 else '-'}${abs(ev):.2f} per $1 | "
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
                 "cal_tag": cal_tag, "stance": stance,
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
    print(f"  odds {int(price):+d} | stake ${stake:.2f} | total "
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
MLB_FIT_PATH = os.path.join(DATA, "v5-mlb.json")
TENNIS_FIT_PATH = os.path.join(DATA, "v5-tennis.json")
MMA_FIT_PATH = os.path.join(DATA, "v5-mma.json")
CRICKET_FIT_PATH = os.path.join(DATA, "v5-cricket.json")
RUGBY_FIT_PATH = os.path.join(DATA, "v5-rugby.json")
F1_FIT_PATH = os.path.join(DATA, "v5-f1.json")
SOCCER_FIT_PATH = os.path.join(DATA, "v5-soccer.json")
SOCCER_LEAGUES_PATH = os.path.join(DATA, "v5-soccer-leagues.json")
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
    return _load_json_cached(NBA_FIT_PATH)


def load_mlb():
    return _load_json_cached(MLB_FIT_PATH)


def mlb_probs(fit, home, away):
    """P(home win) from the MLB fit's Elo (the same logistic
    family as the other lanes, home field = the fit's fitted
    hfa_elo). None when either team misses the fit."""
    elo = (fit or {}).get("elo") or {}
    ch = resolve_mlb_team(home, elo)
    ca = resolve_mlb_team(away, elo)
    if ch is None or ca is None:
        return None
    hfa = (fit.get("params") or {}).get("hfa_elo", 24.0)
    d = elo[ch] + hfa - elo[ca]
    return 1 / (1 + 10 ** (-d / 400))


def load_tennis():
    return _load_json_cached(TENNIS_FIT_PATH)


def load_mma():
    return _load_json_cached(MMA_FIT_PATH)


def load_cricket():
    return _load_json_cached(CRICKET_FIT_PATH)


def load_rugby():
    return _load_json_cached(RUGBY_FIT_PATH)


def load_f1():
    return _load_json_cached(F1_FIT_PATH)


# --- R4 shared MLB gate (fix-guy): ONE membership decision for
# the checker and for coverage. Glow's flag was coverage saying
# "team not in the mlb fit: DET" while the checker priced DET —
# two layers resolving differently. Both layers now call
# mlb_lane_gate + mlb_membership and print their strings, so
# agreement holds by construction, and a harness check proves
# it on codes, full names and other-competition fixtures.
def mlb_lane_gate(fit):
    """None when the MLB lane may price, else the reason."""
    if fit is None:
        return "MLB fit not run (tools/fit_mlb.py)"
    bt = fit.get("backtest") or {}
    if not _exam_passed(bt):
        return ("MLB lane FAILED-EXAM — walk-forward Brier "
                f"{bt.get('brier')} did not beat the naive "
                f"baseline {bt.get('naive_brier')}; lane does "
                "not price until a refit passes")
    return None


def mlb_membership(fit, home, away):
    """(p_home, None) when both teams resolve in the MLB fit,
    else (None, reason) — the reason names the real competition
    for NPB/KBO/CPBL fixtures FanDuel files under baseball."""
    elo = (fit or {}).get("elo") or {}
    for t in (home, away):
        if resolve_mlb_team(t, elo) is None:
            comp = competition_missing("mlb", home, away)
            if comp:
                return None, comp
            return None, f"team not in the MLB fit: {t}"
    return mlb_probs(fit, home, away), None


# --- R4 cricket (fix-guy): lanes keyed by FORMAT + competition
# (v5-cricket.json, tools/fit_cricket.py — Cricsheet). The same
# two nations play T20 / ODI / Test under DIFFERENT ratings, so
# the lane is chosen by the FanDuel competition the pull names
# (fd_parse carries it as mkt["competition"]); the team-only
# fallback fires only when exactly one lane holds both teams.
CRICKET_COMPETITION_LANES = {
    "International Twenty20 Matches": "t20i_m",
    "One Day Internationals": "odi_m",
    "One Day Internationals - Women": "odi_f",
    "Test Matches": "test_m",
    "South Africa - T20 Challenge": "csa_t20",
    "Australia - Twenty20 Big Bash": "bbl",
    "Indian Premier League": "ipl",
    "WBBL": "wbbl",
    "ICC Cricket World Cup League 2": "odi_m",
    "ICC Cricket World Cup Challenge League": "lista_m",
    "ICC Men's T20 WC Africa Qualifiers": "t20i_m",
    "ICC Men's T20 WC Asia Qualifiers": "t20i_m",
}
CRICKET_TEAM_ALIASES = {
    "North West Dragons": "North West",
    "Tuskers": "KwaZulu-Natal Inland",
    "United States": "United States of America",
    "USA": "United States of America",
}


def resolve_cricket_team(name, ratings):
    if name is None:
        return None
    n = str(name).strip()
    for suffix in (" W", " Women"):
        if n.endswith(suffix):
            n = n[: -len(suffix)]
            break
    if n in ratings:
        return n
    alias = CRICKET_TEAM_ALIASES.get(n)
    if alias in ratings:
        return alias
    return _resolve_or_none(ratings, n)


def cricket_lane_for(fit, competition, home, away):
    """(lane_key, None) or (None, reason)."""
    lanes = (fit or {}).get("lanes") or {}
    if competition and competition in CRICKET_COMPETITION_LANES:
        return CRICKET_COMPETITION_LANES[competition], None
    holders = []
    for key, blk in lanes.items():
        ratings = blk.get("ratings") or {}
        if resolve_cricket_team(home, ratings) is not None \
                and resolve_cricket_team(away, ratings) is not None:
            holders.append(key)
    if len(holders) == 1:
        return holders[0], None
    if len(holders) > 1:
        return None, ("cricket format not named by the pull and "
                      f"the teams sit in {len(holders)} fitted "
                      "formats (T20/ODI/Test ratings differ) — "
                      "stamped rather than guessed")
    return None, (f"team not in any cricket fit "
                  f"({home}/{away})")


def cricket_probs(fit, lane, home, away, side):
    """(p, None) or (None, reason) for one side of a cricket
    moneyline. Test lane is three-way: the Draw runner prices
    from the lane's fitted draw rate."""
    blk = ((fit or {}).get("lanes") or {}).get(lane) or {}
    bt = blk.get("backtest") or {}
    if not _exam_passed(bt):
        return None, (f"cricket {lane} lane FAILED-EXAM — "
                      f"walk-forward Brier {bt.get('brier')} did "
                      f"not beat the naive baseline "
                      f"{bt.get('naive_brier')}, n={bt.get('n')}; "
                      "lane does not price until a refit passes")
    ratings = blk.get("ratings") or {}
    ch = resolve_cricket_team(home, ratings)
    ca = resolve_cricket_team(away, ratings)
    if ch is None or ca is None:
        miss = home if ch is None else away
        return None, (f"team not in the cricket {lane} fit: "
                      f"{miss}")
    p_home = 1 / (1 + 10 ** (-(ratings[ch] - ratings[ca]) / 400))
    if lane.startswith("test"):
        p_draw = blk.get("draw_rate")
        if p_draw is None:
            return None, "test lane carries no fitted draw rate"
        if side == "draw":
            return p_draw, None
        p_home = (1 - p_draw) * p_home
        return (p_home if side == "home"
                else (1 - p_draw) - p_home), None
    if side == "draw":
        return None, ("no draw leg in limited-overs cricket "
                      "moneylines (ties settle by Super Over / "
                      "countback, not a priced draw outcome)")
    return (p_home if side == "home" else 1 - p_home), None


# --- R4 rugby (fix-guy): v5-rugby.json (tools/fit_rugby.py).
# Rugby league lanes are INTERNATIONAL pools split by sex —
# the FanDuel board's league fixtures are World Cup matches,
# and the women's game is never pooled with the men's.
def rugby_league_lane(competition, home, away):
    blob = f"{competition or ''} {home or ''} {away or ''}"
    if "Women" in blob or " W" in f" {home} " or \
            " W" in f" {away} ":
        return "intl_f"
    return "intl_m"


def rugby_probs(fit, code, lane, home, away):
    """(p_home, None) or (None, reason). code: 'league'|'union'."""
    blk = (((fit or {}).get(code) or {}).get(lane)) or {}
    if not blk:
        return None, (f"no rugby {code} fit for lane {lane} "
                      "(tools/fit_rugby.py)")
    bt = blk.get("backtest") or {}
    if not _exam_passed(bt):
        return None, (f"rugby {code} {lane} lane FAILED-EXAM — "
                      f"walk-forward Brier {bt.get('brier')} did "
                      f"not beat the naive baseline "
                      f"{bt.get('naive_brier')}, n={bt.get('n')}; "
                      "lane does not price until a refit passes")
    ratings = blk.get("ratings") or {}

    def clean(t):
        # FanDuel suffixes women's national teams ("New
        # Zealand W"); the RLP archive rates them unsuffixed.
        n = str(t or "").strip()
        for suffix in (" W", " Women"):
            if n.endswith(suffix):
                return n[: -len(suffix)]
        return n

    ch = _resolve_or_none(ratings, clean(home))
    ca = _resolve_or_none(ratings, clean(away))
    if ch is None or ca is None:
        miss = home if ch is None else away
        return None, f"team not in the rugby {lane} fit: {miss}"
    d = ratings[ch] - ratings[ca]
    return 1 / (1 + 10 ** (-d / 400)), None


def _exam_passed(backtest):
    """The house exam gate (shared by the MLB lane and the R3
    head-to-head lanes): a lane prices only when its fitted
    walk-forward Brier BEAT the naive baseline it prints next
    to. A lane that failed ships FAILED-EXAM with its numbers
    and does not price — no variant is fished for a pass."""
    bt = backtest or {}
    return (bt.get("brier") is not None
            and bt.get("naive_brier") is not None
            and bt["brier"] < bt["naive_brier"])


_TENNIS_INDEX_CACHE = {}


def _tennis_index(tour_blk, tour):
    """Normalized-name indexes for one tour fit block.

    Built once per fit-block object (fit files are loaded through
    the mtime cache and treated as immutable). Every index stores
    keys in the fit's original iteration order; the resolver below
    applies the same stages and ambiguity rules as before."""
    key = (id(tour_blk), tour)
    ent = _TENNIS_INDEX_CACHE.get(key)
    elo = tour_blk.get("elo") or {}
    if ent is not None and ent[0] is tour_blk and ent[1] is elo:
        return ent[2]
    if tour == "atp":
        exact = {}
        by_tokens = {}
        by_surname = {}
        for k in elo:
            nk = _norm_name(k)
            exact.setdefault(nk, k)
            token_key = tuple(sorted(
                nk.replace("-", " ").split()))
            by_tokens.setdefault(token_key, []).append(k)
            kt = nk.split()
            if len(kt) >= 2:
                by_surname.setdefault(
                    " ".join(kt[:-1]), []).append((k, kt[-1]))
        index = (exact, by_tokens, by_surname)
    else:
        exact = {}
        by_surname_initial = {}
        for k in elo:
            toks = str(k).replace(".", " ").split()
            if len(toks) >= 2 and len(toks[-1]) == 1:
                sn = " ".join(toks[:-1]).lower()
                ini = toks[-1].lower()
                exact.setdefault(f"{sn} {ini}", k)
                by_surname_initial.setdefault(
                    (sn, ini), []).append(k)
        index = (exact, by_surname_initial)
    if len(_TENNIS_INDEX_CACHE) >= 16:
        _TENNIS_INDEX_CACHE.clear()
    _TENNIS_INDEX_CACHE[key] = (tour_blk, elo, index)
    return index


def resolve_tennis_player(query, tour_blk, tour):
    """FanDuel name -> the tour fit's player key, or None.

    ATP keys are Sackmann's 'Surname... Firstname' (first
    name is the key's LAST token): match by exact normalized
    form, then by token multiset (FanDuel prints 'Firstname
    Surname'), then by surname + first initial ('J. Sinner').
    WTA keys are the tennis-data archive's 'Surname I.' form:
    match by surname (any suffix of the FanDuel name's tokens)
    + first initial. Every hit is a real key of the fit by
    construction; ambiguous -> None, never a guess."""
    if query is None or not tour_blk:
        return None
    elo = tour_blk.get("elo") or {}
    q = _norm_name(query)
    if not q:
        return None
    if tour == "atp":
        exact, by_tokens, by_surname = _tennis_index(tour_blk, tour)
        if q in exact:
            return exact[q]
        # token multiset, hyphens split ('Jan-Lennard' and
        # 'Jan Lennard' are the same name tokens; key order
        # varies between sources)
        qtok = tuple(sorted(q.replace("-", " ").split()))
        hits = by_tokens.get(qtok, [])
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            return None
        parts = q.split()
        if len(parts) >= 2:
            surname, first = " ".join(parts[1:]), parts[0]
            hits = [k for k, last in by_surname.get(surname, [])
                    if last == first
                    or last.startswith(first[0])]
            if len(hits) == 1:
                return hits[0]
        return None
    # wta: keys 'Surname I.'
    exact, by_surname_initial = _tennis_index(tour_blk, tour)
    q_form = q.replace(".", " ").strip()
    if q_form in exact:
        return exact[q_form]
    parts = q.split()
    if len(parts) >= 2:
        ini = parts[0][0]
        # surname candidates: every suffix of the name's
        # tokens (FanDuel prints multi-part given names —
        # 'Carol Young Suh Lee' has surname 'Lee')
        surnames = {" ".join(parts[k:]).lower()
                    for k in range(1, len(parts))}
        hits = []
        for sn in surnames:
            hits.extend(by_surname_initial.get((sn, ini), []))
        if len(hits) == 1:
            return hits[0]
    return None


def tennis_probs(fit, home, away):
    """(tour, p_home) for a tennis fixture, or (None, reason).
    The tour is decided by membership: both players must
    resolve in ONE tour's fit. A player resolving in neither
    names themselves; players resolving only in different
    tours are a cross-tour fixture no fit holds."""
    tours = (fit or {}).get("tours") or {}
    rh, ra = {}, {}
    for t, blk in tours.items():
        kh = resolve_tennis_player(home, blk, t)
        if kh:
            rh[t] = kh
        ka = resolve_tennis_player(away, blk, t)
        if ka:
            ra[t] = ka
    common = sorted(set(rh) & set(ra))
    if len(common) == 1:
        t = common[0]
        elo = tours[t]["elo"]
        d = elo[rh[t]] - elo[ra[t]]
        return t, 1 / (1 + 10 ** (-d / 400))
    if len(common) > 1:
        return None, (f"player names resolve in more than one "
                      f"tour fit ({home}/{away}) — ambiguous, "
                      f"not guessed")
    if not rh:
        return None, f"player not in the tennis fit: {home}"
    if not ra:
        return None, f"player not in the tennis fit: {away}"
    return None, ("players resolve in different tour fits — "
                  "no single tour fit holds both "
                  f"({home}/{away})")


# FanDuel prints some fighters under a different name form
# than the source CSV the fit was built from (a respaced
# Korean given name, a full first name for a shortened one,
# a dropped hyphen). Explicit aliases: the canonical
# resolver fires one only when its target is itself a fit
# key; each target below is verified present in v5-mma.json.
MMA_FIGHTER_ALIASES = {
    "Jung Young Lee": "JeongYeong Lee",
    "Joseph Kropschot": "Joe Kropschot",
    "Jean Paul Lebosnoyani": "Jean-Paul Lebosnoyani",
}


def resolve_mma_fighter(query, elo):
    """FanDuel name -> the MMA fit's fighter key (the source
    CSV's 'Firstname Lastname' form), via the canonical
    resolver (exact -> explicit alias -> prefix/substring),
    then the token-form fallback below."""
    if query is None or not elo:
        return None
    hit = _resolve_or_none(elo, query, MMA_FIGHTER_ALIASES)
    if hit:
        return hit
    q = sorted(_norm_name(query).split())
    hits = [k for k in elo
            if sorted(_norm_name(k).split()) == q]
    return hits[0] if len(hits) == 1 else None


def mma_probs(fit, home, away):
    """P(first-named fighter wins) from the MMA fit's Elo
    (neutral cage, no home edge). (p, None) or (None, reason)."""
    elo = (fit or {}).get("elo") or {}
    ch = resolve_mma_fighter(home, elo)
    if ch is None:
        return None, f"fighter not in the MMA fit: {home}"
    ca = resolve_mma_fighter(away, elo)
    if ca is None:
        return None, f"fighter not in the MMA fit: {away}"
    d = elo[ch] - elo[ca]
    return 1 / (1 + 10 ** (-d / 400)), None


def nba_probs(fit, home, away):
    """(p_home, margin_mu, margin_sd) from the fitted NBA lane.
    Names resolve through the canonical NBA resolver (full
    FanDuel names -> fit codes); an unresolvable name is not in
    the fit and returns None."""
    R = fit["ratings"]
    home = resolve_nba_team(home, R)
    away = resolve_nba_team(away, R)
    if home is None or away is None:
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
    return _load_json_cached(SOCCER_FIT_PATH)


def soccer_fixture_grid(fit, home, away):
    hk = soccer_fit_key(fit, home)
    ak = soccer_fit_key(fit, away)
    if hk is None or ak is None:
        return None
    lh, la = soccer_lambdas(fit["strengths"], fit["league"], hk, ak)
    return soccer_grid(lh, la)


# ----------------------------------------------------------------
# Soccer name resolution (v5.4 fix — "fix the laziness" pass).
# FanDuel prints DISPLAY names ("AC Milan", "Man Utd",
# "Paris St-G", "Los Angeles FC"); the fits key teams by their
# fit-source names (the shipped EPL fit by CODE — MAN/LEE/SUN;
# football-data by its short forms — "Milan", "Ath Bilbao",
# "M'gladbach"; the MLS fit by ESPN display names). Before this
# layer, every name-form mismatch stamped UNPRICED even when the
# club's fitted math was sitting in the app — the single biggest
# UNPRICED bucket on the live coverage queue (soccer moneyline,
# 252 markets). ONE canonical resolver now serves every soccer
# consumer: soccer_fit_for, soccer_league_for, _soccer_grid_or_none
# (via soccer_fixture_grid) and universal_coverage.
#
# Safety law: an alias maps a name INTO THE SAME CLUB's fit entry,
# never into a different club, and resolution only ever runs
# against ONE fit's own team list at a time, so a name can never
# wander into another league's fit through an alias. A fixture
# whose teams resolve into DIFFERENT league fits still stamps
# UNPRICED "teams split across league fits" — cross-competition
# honesty is unchanged.

def _soccer_norm_uncached(name):
    """Accent/punctuation-insensitive normal form of a team name."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("'", "").replace("’", "")
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split())


@lru_cache(maxsize=65536)
def _soccer_norm_cached(name):
    return _soccer_norm_uncached(name)


def _soccer_norm(name):
    if isinstance(name, str):
        return _soccer_norm_cached(name)
    return _soccer_norm_uncached(name)


# FanDuel display name (normalized) -> fit-source name
# (normalized), for the pairs normalization alone cannot bridge:
# renames, initials and abbreviations. Targets are the names the
# fits themselves print.
SOCCER_NAME_ALIASES = {
    # Italy (football-data I1/I2 forms)
    "ac milan": "milan", "inter milan": "inter",
    "internazionale": "inter", "as roma": "roma",
    "hellas verona": "verona", "us sassuolo": "sassuolo",
    # France (F1/F2)
    "paris st g": "paris sg", "paris st germain": "paris sg",
    "paris saint germain": "paris sg", "psg": "paris sg",
    "estac troyes": "troyes", "ea guingamp": "guingamp",
    "stade lavallois": "laval", "stade brestois 29": "brest",
    "stade rennais": "rennes",
    # Spain (SP1/SP2)
    "athletic bilbao": "ath bilbao", "athletic club": "ath bilbao",
    "atletico madrid": "ath madrid",
    "atletico de madrid": "ath madrid",
    "celta vigo": "celta", "rc celta": "celta",
    "real betis": "betis", "real sociedad": "sociedad",
    "rayo vallecano": "vallecano", "deportivo alaves": "alaves",
    # FanDuel's bare "Deportivo" on a Spanish fixture is
    # Deportivo La Coruna, whose football-data key is
    # "La Coruna" (held by the la-liga-2 fit and the Spain
    # country system). Safe as a full-name alias: the lookup
    # is by whole normalized name, so "deportivo cali" is a
    # different key and still resolves to the Colombian club.
    "deportivo": "la coruna",
    "ca osasuna": "osasuna", "racing santander": "santander",
    "sporting gijon": "sp gijon", "real sporting": "sp gijon",
    "real valladolid": "valladolid", "ud las palmas": "las palmas",
    "rcd mallorca": "mallorca", "cd leganes": "leganes",
    # Germany (D1/D2)
    "eintracht frankfurt": "ein frankfurt",
    "borussia monchengladbach": "mgladbach",
    "borussia m gladbach": "mgladbach",
    "borussia mgladbach": "mgladbach",
    "bayer leverkusen": "leverkusen",
    "bayer 04 leverkusen": "leverkusen",
    "vfb stuttgart": "stuttgart", "vfl wolfsburg": "wolfsburg",
    "tsg hoffenheim": "hoffenheim",
    "1 fc union berlin": "union berlin",
    "sc freiburg": "freiburg", "fc augsburg": "augsburg",
    "1 fc heidenheim": "heidenheim", "fsv mainz 05": "mainz",
    "mainz 05": "mainz", "werder": "werder bremen",
    "hamburger sv": "hamburg", "hertha bsc": "hertha",
    "1 fc koln": "fc koln", "schalke": "schalke 04",
    "hannover": "hannover 96", "fortuna dusseldorf": "dusseldorf",
    "1 fc kaiserslautern": "kaiserslautern",
    "karlsruher sc": "karlsruhe", "sc paderborn": "paderborn",
    "sc paderborn 07": "paderborn", "paderborn 07": "paderborn",
    "1 fc magdeburg": "magdeburg",
    "dortmund": "borussia dortmund",
    # European cup pool (ESPN uefa.* forms — the pool's keys;
    # FanDuel lists the short forms)
    "feyenoord": "feyenoord rotterdam",
    "shakhtar": "shakhtar donetsk",
    # USL (FanDuel forms -> ESPN usa.usl.1 fit names; FC Tulsa
    # is the Tulsa Roughnecks franchise under its current name)
    "tulsa roughnecks": "fc tulsa",
    "tulsa roughnecks fc": "fc tulsa",
    "colorado switchbacks": "colorado springs switchbacks",
    "colorado switchbacks fc": "colorado springs switchbacks",
    # Peru (FanDuel full names -> ESPN per.1 fit names)
    "universitario de deportes": "universitario",
    "juan pablo ii college": "juan pablo ii",
    # England (E1 short forms)
    "sheffield wednesday": "sheffield weds",
    "stoke city": "stoke", "swansea city": "swansea",
    "cardiff city": "cardiff", "blackburn rovers": "blackburn",
    "luton town": "luton", "oxford united": "oxford",
    "queens park rangers": "qpr", "norwich city": "norwich",
    "coventry city": "coventry", "hull city": "hull",
    "west bromwich albion": "west brom",
    # Netherlands / Portugal / Greece / Scotland / Belgium
    "psv": "psv eindhoven", "az": "az alkmaar",
    "sporting lisbon": "sp lisbon", "sporting cp": "sp lisbon",
    "sporting clube de portugal": "sp lisbon",
    "sporting braga": "sp braga", "sc braga": "sp braga",
    "braga": "sp braga",
    "sl benfica": "benfica", "vitoria guimaraes": "guimaraes",
    "olympiacos": "olympiakos", "aek": "aek athens",
    "ofi": "ofi crete",
    "heart of midlothian": "hearts",
    "rsc anderlecht": "anderlecht", "krc genk": "genk",
    "kaa gent": "gent", "union saint gilloise": "st gilloise",
    "union sg": "st gilloise",
    "union st gilloise": "st gilloise",
    "royale union saint gilloise": "st gilloise",
    "standard liege": "standard", "oh leuven": "oud heverlee leuven",
    "sint truiden": "st truiden",
    # MLS (FanDuel forms -> ESPN fit names)
    "los angeles fc": "lafc",
    "new york red bulls": "red bull new york",
    "ny red bulls": "red bull new york",
    "dc utd": "d c united", "dc united": "d c united",
    "kansas city": "sporting kansas city",
    "orlando city": "orlando city sc",
    "inter miami": "inter miami cf",
    "nycfc": "new york city fc", "new york city": "new york city fc",
    "atlanta utd": "atlanta united",
    "toronto": "toronto fc", "montreal impact": "cf montreal",
    "vancouver whitecaps": "vancouver whitecaps fc",
    "seattle sounders": "seattle sounders fc",
    "new england": "new england revolution",
    "chicago fire": "chicago fire fc",
    "columbus": "columbus crew",
    "houston dynamo": "houston dynamo fc",
    "austin": "austin fc", "charlotte": "charlotte fc",
    "colorado": "colorado rapids",
    "philadelphia": "philadelphia union",
    "salt lake": "real salt lake", "utah": "real salt lake",
    "nashville": "nashville sc",
    "st louis city": "st louis city sc",
    "st louis": "st louis city sc", "san diego": "san diego fc",
    # Brazil (FanDuel forms -> ESPN bra.1 fit names)
    "se palmeiras": "palmeiras",
    "atletico mineiro": "atletico mg",
    "spfc": "sao paulo", "sao paulo fc": "sao paulo",
    "sc corinthians": "corinthians",
    "corinthians paulista": "corinthians",
    "gremio fbpa": "gremio", "sc internacional": "internacional",
    "cr flamengo": "flamengo", "fluminense fc": "fluminense",
    "ec bahia": "bahia", "ec vitoria": "vitoria",
    "vasco": "vasco da gama", "botafogo rj": "botafogo",
    "cruzeiro ec": "cruzeiro", "america mg": "america mineiro",
    "athletico paranaense": "athletico pr",
    "atletico goianiense": "atletico go",
    # Liga MX (FanDuel -> ESPN mex.1)
    "pumas": "pumas unam", "tigres": "tigres uanl",
    "club america": "america", "cf america": "america",
    "chivas": "guadalajara", "cd guadalajara": "guadalajara",
    "atletico san luis": "atletico de san luis",
    "mazatlan fc": "mazatlan",
    "club tijuana": "tijuana", "xolos": "tijuana",
    "club leon": "leon", "club puebla": "puebla",
    "club necaxa": "necaxa", "santos laguna": "santos",
    "club santos laguna": "santos",
    "queretaro fc": "queretaro", "juarez": "fc juarez",
    # Argentina (FanDuel -> ESPN arg.1)
    "newells": "newells old boys",
    "belgrano": "belgrano cordoba",
    "racing": "racing club", "racing club avellaneda": "racing club",
    "ca river plate": "river plate", "ca boca juniors": "boca juniors",
    "ca independiente": "independiente",
    "ca huracan": "huracan", "ca talleres": "talleres",
    "talleres cordoba": "talleres",
    "velez": "velez sarsfield",
    "colon": "colon santa fe",
    # Primera Nacional (arg.2 — FanDuel short forms -> the
    # nacional-b fit's full club names; every target verified
    # present in the shipped fit, Build D)
    "chacarita": "chacarita juniors",
    "cd maipu": "deportivo maipu",
    "estudiantes de caseros": "estudiantes buenos aires",
    "gimnasia jujuy": "gimnasia y esgrima jujuy",
    "club atletico mitre": "mitre santiago del estero",
    "club gimnasia y tiro": "gimnasia y tiro salta",
    "godoy cruz": "godoy cruz antonio tomba",
    # Round 2 leagues (FanDuel -> ESPN fit names, verified
    # against each fit's own key list; one club each)
    # Paraguay (par.1)
    "club 2 de mayo": "2 de mayo",
    "club 2 de mayo de pedro juan cab": "2 de mayo",
    "club 2 de mayo de pedro juan caballero": "2 de mayo",
    # Costa Rica (crc.1)
    "puntarenas f c": "puntarenas fc",
    "inter san carlos": "inter de san carlos",
    # Bolivia (bol.1): ABB is the club's own short name in the
    # source — Academia de Balompie Boliviano
    "academia de balompie boliviano": "abb",
    "club independiente petrolero": "independiente petrolero",
    # USL Championship (usa.usl.1)
    "sporting club jacksonville": "sporting jax",
    "orange county blues": "orange county sc",
    "louisville fc": "louisville city fc",
    # Colombia (col.1)
    "america de cali s a": "america de cali",
    # Venezuela (ven.1)
    "puerto cabello": "academia puerto cabello",
    # Ecuador (ecu.1): LDU = Liga Deportiva Universitaria
    "ldu": "liga de quito", "ldu quito": "liga de quito",
    # NWSL (FanDuel (W) display form -> ESPN usa.nwsl fit
    # name; the forms layer strips the (W) marker before the
    # alias lookup, so the key is the bare normalized name)
    "nj ny gotham fc": "gotham fc",
}

# Competition-scoped name forms: normalized competition (as the
# pull stamps it) -> {normalized display name: the fit's own
# name}. For display names shared by clubs in DIFFERENT
# countries, where a global alias would misname one of them:
# FanDuel's "Fortaleza FC" is Fortaleza CEIF on a Colombian
# Primera A fixture and Fortaleza of Brazil on a Brazilian one
# ("fortaleza fc" already resolves to the Brazilian club through
# its fit's plain "Fortaleza" key — no alias needed there).
# Only the market's own competition can say which club is
# meant, so these are applied at the one pricing point that
# carries the competition (engine_price's soccer branch), never
# in the global resolver.
SOCCER_SCOPED_NAME_ALIASES = {
    "colombian primera a": {"fortaleza fc": "Fortaleza CEIF"},
}


def _soccer_scoped_names(home, away, competition):
    """(home, away) with the competition's scoped name forms
    applied, or None when the competition names no scope or no
    side changes."""
    if not competition:
        return None
    scope = SOCCER_SCOPED_NAME_ALIASES.get(_soccer_norm(competition))
    if not scope:
        return None
    out = []
    changed = False
    for name in (home, away):
        tgt = scope.get(_soccer_norm(name)) \
            if isinstance(name, str) else None
        if tgt:
            out.append(tgt)
            changed = True
        else:
            out.append(name)
    return tuple(out) if changed else None

# The shipped EPL fit keys teams by CODE (v5-soccer.json). FanDuel
# prints names; this table bridges name -> code for that fit only.
EPL_CODE_BY_NAME = {
    "arsenal": "ARS", "aston villa": "AVL", "brighton": "BHA",
    "brighton and hove albion": "BHA", "brighton hove albion": "BHA",
    "bournemouth": "BOU", "afc bournemouth": "BOU",
    "brentford": "BRE", "burnley": "BUR", "chelsea": "CHE",
    "crystal palace": "CRY", "everton": "EVE", "fulham": "FUL",
    "leeds": "LEE", "leeds united": "LEE", "liverpool": "LIV",
    "man utd": "MAN", "man united": "MAN",
    "manchester united": "MAN", "man city": "MNC",
    "manchester city": "MNC", "newcastle": "NEW",
    "newcastle united": "NEW", "nottm forest": "NFO",
    "nottingham forest": "NFO", "sunderland": "SUN",
    "tottenham": "TOT", "tottenham hotspur": "TOT", "spurs": "TOT",
    "west ham": "WHU", "west ham united": "WHU",
    "wolves": "WOL", "wolverhampton": "WOL",
    "wolverhampton wanderers": "WOL",
}

# Club-affix tokens that naming variants add or drop freely
# ("FC Porto" vs "Porto", "AJ Auxerre" vs "Auxerre"). Stripping is
# token-exact and only ever produces EXTRA candidate forms — the
# exact normalized name is always tried first.
SOCCER_STRIP_LEAD = {"fc", "afc", "sc", "ac", "ca", "cd", "rc",
                     "as", "ogc", "aj", "us", "ea"}
SOCCER_STRIP_TAIL = {"fc", "sc", "cf", "ec", "fk"}


def _soccer_name_forms_uncached(name):
    """Every normalized form under which `name` may sit as a fit
    key: itself, affix-stripped variants, utd->united and
    saint->st token swaps, the explicit alias target (and its own
    affix-stripped variants), and — for EPL names — the shipped
    fit's team code."""
    base = _soccer_norm(name)
    if not base:
        return set()
    # Seed forms: the name itself; the (W)-stripped form (FanDuel
    # marks women's fixtures with a trailing (W), which
    # _soccer_norm renders as a trailing " w" token — which fits
    # a (W) name may resolve into is gated in soccer_fit_for /
    # soccer_league_for via SOCCER_WOMENS_KEYS, so a stripped
    # women's name can never land on the men's club of the same
    # name, or the reverse); and the explicit alias target.
    # EVERY seed then gets the affix/token variants — variants
    # must apply to the stripped seed too ("Club Necaxa (W)"
    # needs club-stripping AFTER the (W) comes off, or the
    # women's fit's "Necaxa" is unreachable).
    seeds = {base}
    if base.endswith(" w") and len(base) > 2:
        seeds.add(base[:-2])
    tgt = SOCCER_NAME_ALIASES.get(base)
    if tgt:
        seeds.add(tgt)
    for s in list(seeds):
        t2 = SOCCER_NAME_ALIASES.get(s)
        if t2:
            seeds.add(t2)
    forms = set(seeds)
    for s in seeds:
        toks = s.split()
        if len(toks) > 1 and toks[0] in SOCCER_STRIP_LEAD:
            forms.add(" ".join(toks[1:]))
        if len(toks) > 1 and toks[-1] in SOCCER_STRIP_TAIL:
            forms.add(" ".join(toks[:-1]))
        if "utd" in toks:
            forms.add(" ".join("united" if t == "utd" else t
                               for t in toks))
        if "saint" in toks:
            forms.add(" ".join("st" if t == "saint" else t
                               for t in toks))
    code = EPL_CODE_BY_NAME.get(base)
    if code:
        forms.add(_soccer_norm(code))
    return forms


@lru_cache(maxsize=65536)
def _soccer_name_forms_cached(name):
    return frozenset(_soccer_name_forms_uncached(name))


def _soccer_name_forms(name):
    """The historical set-returning API over the memoized forms."""
    if isinstance(name, str):
        return set(_soccer_name_forms_cached(name))
    return _soccer_name_forms_uncached(name)


_SOCCER_FIT_INDEX_CACHE = {}


def _soccer_fit_index(fit):
    """(strengths, [(key, forms), ...]) for one fit, built once.

    Entries preserve the strengths dict's iteration order, which
    is the historical resolver's tie/order behavior. The cache
    holds strong references and validates the strengths object,
    so a rebuilt fit can never inherit another fit's index."""
    key = id(fit)
    ent = _SOCCER_FIT_INDEX_CACHE.get(key)
    if ent is not None and ent[0] is fit:
        strengths = fit.get("strengths") or {}
        if ent[1] is strengths:
            return strengths, ent[2]
    strengths = fit.get("strengths") or {}
    entries = tuple(
        (k, _soccer_name_forms_cached(k)
         if isinstance(k, str)
         else frozenset(_soccer_name_forms_uncached(k)))
        for k in strengths)
    if len(_SOCCER_FIT_INDEX_CACHE) >= 128:
        _SOCCER_FIT_INDEX_CACHE.clear()
    _SOCCER_FIT_INDEX_CACHE[key] = (fit, strengths, entries)
    return strengths, entries


def soccer_fit_key(fit, name):
    """The key under which `name` sits in fit's strengths, resolved
    through the alias layer, or None. Resolution is scoped to THIS
    fit's own team list — a name resolves only into a club this fit
    actually holds."""
    if not fit or name is None:
        return None
    st, entries = _soccer_fit_index(fit)
    if name in st:
        return name
    want = (_soccer_name_forms_cached(name)
            if isinstance(name, str)
            else _soccer_name_forms_uncached(name))
    if not want:
        return None
    for k, forms in entries:
        if forms & want:
            return k
    return None


# ----------------------------------------------------------------
# Soccer, multi-league (v5.4, BetFi Xii). data/v5-soccer-leagues
# .json (built by tools/fit_soccer_leagues.py from real
# football-data.co.uk results) carries one fit per league in the
# v5-soccer.json schema family. Selection is by TEAM MEMBERSHIP:
# the shipped EPL fit (v5-soccer.json) is consulted FIRST and its
# numbers are untouched — EPL grading is byte-for-byte what it
# was before this file existed. Only when a fixture is NOT in
# the EPL fit does the leagues file get a say, and only when both
# teams sit in exactly ONE league's strengths (zero = no fit;
# two or more = ambiguous, and an ambiguous fixture is not
# priced on a coin flip). The leagues file's "control" block
# (the EPL refit) is never priced from — it exists to be
# compared against the shipped fit.

def load_soccer_leagues():
    return _load_json_cached(SOCCER_LEAGUES_PATH)


# League keys in the leagues file that hold WOMEN'S competitions.
# FanDuel marks their fixtures with a trailing (W); a (W) name may
# only resolve into these fits, and a bare name never resolves
# into them — "Pachuca (W)" is the women's club, "Pachuca" the
# men's, and the two fits are different leagues with different
# strengths. The gate is what makes the (W)-stripped name form
# (added in _soccer_name_forms) safe to use.
SOCCER_WOMENS_KEYS = {"nwsl", "liga-mx-femenil", "wsl",
                      "a-league-women"}


def _soccer_womens_hint(*names):
    """True when any raw FanDuel name carries the (W) marker
    (normalized: a trailing ' w' token)."""
    for n in names:
        if n and _soccer_norm(n).endswith(" w"):
            return True
    return False


def soccer_league_for(home, away, blob=None):
    """The one league key whose strengths hold BOTH teams, or
    None (no league holds both, or more than one does). Team
    membership is tested through the alias resolver
    (soccer_fit_key), so FanDuel display names resolve into the
    fit's own name forms. Women's fixtures ((W) marker) search
    only the women's fits; all other fixtures search only the
    rest — see SOCCER_WOMENS_KEYS."""
    blob = blob if blob is not None else load_soccer_leagues()
    if not blob:
        return None
    womens = _soccer_womens_hint(home, away)
    hits = [k for k, lg in (blob.get("leagues") or {}).items()
            if (k in SOCCER_WOMENS_KEYS) == womens
            and soccer_fit_key(lg, home) is not None
            and soccer_fit_key(lg, away) is not None]
    return hits[0] if len(hits) == 1 else None


def soccer_system_for(home, away, blob=None):
    """(fit_view, system_key) for a CROSS-TIER fixture: both
    clubs held by one country system fit (both tiers of a
    pyramid pooled on a shared strengths/Elo scale — see
    tools/fit_soccer_leagues.py COUNTRY_SYSTEMS). The view
    prices with the HOME club's tier rates: a cup tie is played
    in the home club's scoring environment. Returns
    (None, None) when no single system holds both, or more
    than one does. Men's competitions only — the systems are
    the men's pyramids."""
    if _soccer_womens_hint(home, away):
        return None, None
    blob = blob if blob is not None else load_soccer_leagues()
    if not blob:
        return None, None
    hits = []
    for key, sysfit in (blob.get("systems") or {}).items():
        hk = soccer_fit_key(sysfit, home)
        ak = soccer_fit_key(sysfit, away)
        if hk is not None and ak is not None:
            hits.append((key, sysfit, hk))
    if len(hits) != 1:
        return None, None
    key, sysfit, hk = hits[0]
    tier = (sysfit.get("team_tier") or {}).get(hk, "tier1")
    rates = (sysfit.get("tier_rates") or {}).get(tier) \
        or sysfit.get("league") or {}
    view = {"strengths": sysfit.get("strengths"),
            "elo": sysfit.get("elo"),
            "league": rates,
            "params": sysfit.get("params"),
            "source": sysfit.get("source"),
            "fitted_at": sysfit.get("fitted_at"),
            "backtest": sysfit.get("backtest"),
            "season": sysfit.get("season"),
            "league_name": sysfit.get("league_name"),
            "system": key, "home_tier": tier}
    return view, f"system-{key}"


def soccer_cup_for(home, away, blob=None):
    """(fit, cup_key) for a CROSS-COMPETITION fixture from a
    pooled cup fit (blob['cups'] — one walk-forward pool per
    cup family, strengths shared across the pool; see
    tools/fit_soccer_leagues.py CUP_POOLS). A pool prices ONLY
    when its gate shipped it (walk-forward brier3 at or under
    the stated bar) AND both clubs are in the pool. Pools are
    tried in a fixed order — europe, france, argentina — and
    the first shipped pool holding both clubs prices the
    fixture; the order is stated here because a pair of French
    clubs can sit in both the European and the Coupe de
    France pool, and the European pool is the deeper exam.
    Men's competitions only — the pools are the men's cups."""
    if _soccer_womens_hint(home, away):
        return None, None
    blob = blob if blob is not None else load_soccer_leagues()
    if not blob:
        return None, None
    for key in ("europe", "france", "argentina"):
        cup = (blob.get("cups") or {}).get(key)
        if not cup or not (cup.get("gate") or {}).get("ships"):
            continue
        if soccer_fit_key(cup, home) is not None \
                and soccer_fit_key(cup, away) is not None:
            return cup, f"cup-{key}"
    return None, None


def soccer_missing_reason(home, away):
    """Why a fixture has no fit, named exactly, most specific
    truth first: (1) a pooled cup fit was attempted for this
    pairing and HELD at its gate — the attempt and its numbers
    are the stamp; (2) a club belongs to a competition proven
    to have no match-level results source (blob['no_source'])
    — the NO-SOURCE stamp, which fires only for a club held by
    NO fit, so a fitted club of a similar name is never
    stamped; (3) BOTH clubs are held by some priceable fit but
    never the same one — the fixture is cross-competition (a
    cup / Champions-League pairing) and the honest stamp is
    the split, not 'team not in the fit'. Country system fits
    and shipped cup pools count as holders."""
    blob = load_soccer_leagues() or {}
    cups = blob.get("cups") or {}
    for key in ("europe", "france", "argentina"):
        cup = cups.get(key)
        if cup and not (cup.get("gate") or {}).get("ships") \
                and soccer_fit_key(cup, home) is not None \
                and soccer_fit_key(cup, away) is not None:
            gate = cup.get("gate") or {}
            bt = cup.get("backtest") or {}
            return (f"pooled cup fit attempted and HELD — "
                    f"{cup.get('league_name') or key}: "
                    f"walk-forward brier3 {bt.get('brier3')} vs "
                    f"bar {gate.get('bar')} (median league fit "
                    f"+ {gate.get('tolerance')}); a pool that "
                    f"fails its exam prices nothing")
    fits = [load_soccer()] + list(
        (blob.get("leagues") or {}).values()) + list(
        (blob.get("systems") or {}).values()) + [
        c for c in cups.values()
        if (c.get("gate") or {}).get("ships")]
    known = [any(f and soccer_fit_key(f, t) is not None
                 for f in fits)
             for t in (home, away)]
    for rec in (blob.get("no_source") or {}).values():
        clubs = {_soccer_norm(c) for c in rec.get("clubs") or []}
        for t, is_known in zip((home, away), known):
            if not is_known and _soccer_norm(t) in clubs:
                return rec.get("stamp")
    if all(known):
        return ("teams split across league fits — no single "
                "league fit holds both")
    return None


def soccer_fit_for(home, away):
    """(fit, league_key) for a fixture: the shipped EPL fit when
    it holds both teams (league_key 'epl'), else the unique
    leagues-file fit, else a country system fit when the pair
    is cross-tier within one pyramid (key 'system-<country>'),
    else (None, None). Membership goes through soccer_fit_key,
    so exact fit names price byte-for-byte as before and
    FanDuel display names resolve to the same clubs."""
    if not _soccer_womens_hint(home, away):
        fit = load_soccer()
        if fit is not None and soccer_fit_key(fit, home) is not None \
                and soccer_fit_key(fit, away) is not None:
            return fit, "epl"
    blob = load_soccer_leagues()
    key = soccer_league_for(home, away, blob)
    if key is not None:
        return blob["leagues"][key], key
    view, syskey = soccer_system_for(home, away, blob)
    if view is not None:
        return view, syskey
    cup, cupkey = soccer_cup_for(home, away, blob)
    if cup is not None:
        return cup, cupkey
    return None, None


# ================================================================ ORGAN 8
# The Universal Fit Registry (v5.4, BetFi Xii). One index over
# every fit the engine owns, read from the files in DATA — the
# registry REPORTS the fits; it never computes one. A sport or
# league with no file on disk is ABSENT from the registry, never
# synthesized, and universal_coverage() names that absence on any
# pull that carries the league. Coverage is pure reporting: it
# reads the same fits the checkers read and changes no verdict.

def _registry_entry(sport, league, kind, path, covered=None,
                    teams=None, fitted_at=None, source=None,
                    backtest=None, note=None):
    e = {"sport": sport, "league": league, "kind": kind,
         "file": os.path.basename(path),
         "present": os.path.exists(path),
         "covered": covered, "fitted_at": fitted_at,
         "source": source, "backtest": backtest}
    if teams is not None:
        e["teams"] = teams
    if note:
        e["note"] = note
    return e


def _load_json(path):
    # registry reads ride the same mtime cache (item 10c):
    # the registry is read per render, never per market, and
    # now never re-reads disk while files are unchanged.
    try:
        return _load_json_cached(path)
    except Exception:
        return None



def _teamtotals_bet_type(data_dir, sport):
    """The registry/coverage line for a lane's TEAM-totals cell
    (Round 2): the team's own scoring distribution, a different
    model from the game total — its own fit file, its own exam."""
    tf = _load_json(os.path.join(
        data_dir, f"v5-teamtotals-{sport}.json"))
    if tf is None:
        return ("UNPRICED \u2014 no team-totals distribution for "
                "this lane yet \u2014 close by: fit one "
                "(tools/fit_totals.py team)")
    bt, exam_label = _latest_exam(tf)
    if tf.get("status") != "FITTED":
        return (f"UNPRICED \u2014 team-totals fit FAILED-EXAM "
                f"({exam_label} Brier {bt.get('brier_model')} vs "
                f"naive {bt.get('brier_naive')}, MAE "
                f"{bt.get('mae_model')} vs {bt.get('mae_naive')}, "
                f"n={bt.get('n')}) \u2014 close by: a refit that "
                f"beats the naive team-mean baseline")
    dist = (tf.get("params") or {}).get("distribution", "normal")
    return (f"PRICED-capable (team-totals distribution \u2014 "
            f"{dist}, the team's own off/def rates + sigma_team; "
            f"walk-forward MAE {bt.get('mae_model')} vs naive "
            f"{bt.get('mae_naive')}, Brier {bt.get('brier_model')} "
            f"vs {bt.get('brier_naive')}, n={bt.get('n')}; lane "
            f"UNTESTED \u2014 no scored team-totals record yet)")


def universal_registry(data_dir=None):
    """Every registered fit, organized per (sport, league,
    bet-type, team/player) — the Universal Model's index. Each
    entry names: the lane's SPECIALIZED math kind; the bet
    types it can price vs the ones it stamps (with the missing
    piece); the LEAGUE-level parameters AS FITTED FOR THAT
    LEAGUE (scoring environment / home advantage — never one
    global value); the TEAM-level entries it holds (rating or
    strengths per team); fitted_at/source; and the walk-forward
    backtest block VERBATIM from its file (None when the file
    carries none — reported as none, never filled in)."""
    d = data_dir or DATA
    out = []

    def P(name):
        return os.path.join(d, name)

    # R5 lines (segments + outrights), read off their fit
    # files like everything else in this registry.
    _seg_doc = _load_json(P("v5-segments.json")) or {}
    _seg_lanes = _seg_doc.get("lanes") or {}
    _seg_soc = _seg_doc.get("soccer-1h") or {}
    _out_doc = _load_json(P("v5-outrights.json")) or {}
    _out_bt = _out_doc.get("backtest") or {}

    def _seg_us_line(lane_key, form="1st-half"):
        lane = _seg_lanes.get(lane_key) or {}
        bt = lane.get("backtest") or {}
        if lane.get("status") == "FITTED":
            return (f"PRICED-capable ({form} distributions; "
                    f"walk-forward totals MAE "
                    f"{bt.get('mae_total')} vs naive "
                    f"{bt.get('mae_total_naive')}, n={bt.get('n')})")
        if lane:
            return (f"UNPRICED — FAILED-EXAM: {form} totals MAE "
                    f"{bt.get('mae_total')} vs naive "
                    f"{bt.get('mae_total_naive')}, margin MAE "
                    f"{bt.get('mae_margin')} vs "
                    f"{bt.get('mae_margin_naive')}, "
                    f"n={bt.get('n')}")
        return "UNPRICED — no segment fit on file"

    def _seg_nhl_line(lanes):
        # R7: per-period, per-form — read off the same
        # lanes the checker prices from.
        parts = []
        for pnum, plab in ((1, "1P"), (2, "2P"), (3, "3P")):
            lane = lanes.get(f"nhl-{pnum}p") or {}
            forms = lane.get("forms") or {}
            if not lane:
                parts.append(f"{plab}: no fit on file")
                continue
            if not forms:
                bt = lane.get("backtest") or {}
                parts.append(
                    f"{plab} totals "
                    f"{'PRICED-capable' if lane.get('status') == 'FITTED' else 'FAILED-EXAM'} "
                    f"(MAE {bt.get('mae_model')} vs naive "
                    f"{bt.get('mae_naive')})")
                continue
            seg = []
            for form in ("total", "moneyline"):
                f = forms.get(form) or {}
                if f.get("status") == "FITTED":
                    seg.append(f"{form} PRICED-capable")
                elif form == "total":
                    seg.append(
                        f"total FAILED-EXAM (MAE "
                        f"{f.get('mae_model')} vs "
                        f"{f.get('mae_naive')}, Brier "
                        f"{f.get('brier_model')} vs "
                        f"{f.get('brier_naive')})")
                else:
                    seg.append(
                        f"moneyline FAILED-EXAM (Brier3 "
                        f"{f.get('brier3_model')} vs "
                        f"{f.get('brier3_naive')})")
            parts.append(f"{plab}: " + "; ".join(seg))
        return " | ".join(parts)

    def _seg_soc_line(key):
        blk = _seg_soc.get(key)
        if blk is None:
            return ("UNPRICED — no half-share exam on file "
                    "for this league (examined sets: "
                    "football-data R6, ESPN period scores R7)")
        if blk.get("status") == "NO-DATA":
            cov = blk.get("coverage") or {}
            return (f"UNPRICED — NO-DATA (ESPN period "
                    f"scores): {cov.get('games_ht_covered')} "
                    f"of {cov.get('games_completed')} games "
                    "HT-covered, below the exam floor; "
                    "evidence in v5-segments.json")
        bt = blk.get("backtest") or {}
        forms = blk.get("forms") or {}
        res = (forms.get("result") or {}).get("status")
        tot = (forms.get("total") or {}).get("status")
        nums = (f"1H result Brier3 {bt.get('brier3_1h')} vs "
                f"naive {bt.get('brier3_1h_naive')}, 1H total "
                f"Brier {bt.get('brier_over15')} vs naive "
                f"{bt.get('brier_over15_naive')}")
        if res == "FITTED" and tot == "FITTED":
            return (f"PRICED-capable (both 1H forms off the "
                    f"half-share grid, shares {blk.get('share_h')}/"
                    f"{blk.get('share_a')}; walk-forward {nums})")
        if res == "FITTED":
            return (f"PRICED-capable for the 1H RESULT form "
                    f"(+ handicaps) off the half-share grid; "
                    f"1H TOTAL UNPRICED — FAILED-EXAM (R6 "
                    f"per-form bar); walk-forward {nums}")
        if tot == "FITTED":
            return (f"PRICED-capable for the 1H TOTAL form "
                    f"off the half-share grid; 1H RESULT "
                    f"UNPRICED — FAILED-EXAM (R6 per-form "
                    f"bar); walk-forward {nums}")
        if blk.get("status") == "FITTED":
            return (f"PRICED-capable (1H off the half-share "
                    f"grid, shares {blk.get('share_h')}/"
                    f"{blk.get('share_a')}; walk-forward {nums})")
        return (f"UNPRICED — FAILED-EXAM (R6 per-form bar, "
                f"both forms): {nums}")

    def _outright_line(key):
        # R6: per-league exam + live artifact, read off the
        # same file the checker prices from.
        lg = (_out_doc.get("leagues") or {}).get(key)
        exam = (lg or {}).get("exam")
        if exam is None and key == "epl":
            exam = _out_bt
        if not exam:
            return ("UNPRICED — no outright exam on file for "
                    "this league")
        if exam.get("verdict") != "PASS":
            return (f"UNPRICED — FAILED-EXAM (league exam): "
                    f"mean Brier {exam.get('mean_brier_model')} "
                    f"vs naive {exam.get('mean_brier_naive')}, "
                    f"mean log-loss "
                    f"{exam.get('mean_logloss_model')} vs "
                    f"{exam.get('mean_logloss_naive')} "
                    f"({exam.get('seasons_won')}/"
                    f"{len(exam.get('seasons') or []) or 3} "
                    "seasons won)")
        if lg and lg.get("shares"):
            return (f"PRICED-capable (title outrights — Monte "
                    f"Carlo season sim, {lg.get('sims')} sims; "
                    f"league exam PASS: mean Brier "
                    f"{exam.get('mean_brier_model')} vs naive "
                    f"{exam.get('mean_brier_naive')})")
        return ("UNPRICED — league exam PASSED but no live "
                "shares on file for this league")

    def entry(sport, league, kind, path, **kw):
        e = _registry_entry(sport, league, kind, path, **kw)
        out.append(e)
        return e

    soc = _load_json(P("v5-soccer.json"))
    if soc is not None:
        st = soc.get("strengths") or {}
        e = entry("soccer", "epl", "Poisson goals grid + Elo "
                  "check", P("v5-soccer.json"), covered=len(st),
                  teams=sorted(st), fitted_at=soc.get("fitted_at"),
                  source=soc.get("source"),
                  backtest=soc.get("backtest"))
        e["league_params"] = {"league_rates": soc.get("league"),
                              "params": soc.get("params")}
        e["team_entries"] = st
        e["bet_types"] = {
            "moneyline": "PRICED-capable (1X2 off the grid)",
            "spread": "PRICED-capable (.5 handicaps off the grid)",
            "alt-spread": "PRICED-capable (.5 handicaps off the "
                          "grid)",
            "totals": "PRICED-capable (grid totals)",
            "alt-total": "PRICED-capable (grid totals)",
            "btts": "PRICED-capable", "draw-no-bet": "PRICED-capable",
            "double-chance": "PRICED-capable",
            "correct-score": "PRICED-capable",
            "team-props": "PRICED-capable (team totals off the grid)",
            "segment": _seg_soc_line("epl"),
            "futures": _outright_line("epl")}
    blob = _load_json(P("v5-soccer-leagues.json"))
    if blob is not None:
        for key, lg in sorted((blob.get("leagues") or {}).items()):
            st = lg.get("strengths") or {}
            e = entry("soccer", key, "Poisson goals grid + Elo "
                      "check", P("v5-soccer-leagues.json"),
                      covered=len(st), teams=sorted(st),
                      fitted_at=lg.get("fitted_at"),
                      source=lg.get("source"),
                      backtest=lg.get("backtest"))
            e["league_params"] = {
                "league_rates": lg.get("league"),
                "params": lg.get("params"),
                "season": lg.get("season")}
            e["team_entries"] = st
            e["bet_types"] = {
                "moneyline": "PRICED-capable (1X2 off the grid)",
                "spread": "PRICED-capable (.5 handicaps)",
                "alt-spread": "PRICED-capable (.5 handicaps)",
                "totals": "PRICED-capable (grid totals)",
                "alt-total": "PRICED-capable (grid totals)",
                "btts": "PRICED-capable",
                "draw-no-bet": "PRICED-capable",
                "double-chance": "PRICED-capable",
                "correct-score": "PRICED-capable",
                "team-props": "PRICED-capable"}
        for key, lg in sorted((blob.get("systems") or {}).items()):
            st = lg.get("strengths") or {}
            e = entry("soccer", f"system-{key}", "Poisson goals "
                      "grid + Elo check, pooled country system "
                      "(shared scale, per-tier rates) — "
                      "cross-tier fixtures only",
                      P("v5-soccer-leagues.json"),
                      covered=len(st), teams=sorted(st),
                      fitted_at=lg.get("fitted_at"),
                      source=lg.get("source"),
                      backtest=lg.get("backtest_by_tier"))
            e["league_params"] = {
                "tier_rates": lg.get("tier_rates"),
                "params": lg.get("params"),
                "season": lg.get("season"),
                "validation": lg.get("validation")}
            e["team_entries"] = st
            e["bet_types"] = {
                "moneyline": "PRICED-capable (1X2 off the grid, "
                             "cross-tier pairs only)",
                "spread": "PRICED-capable (.5 handicaps)",
                "totals": "PRICED-capable (grid totals)",
                "btts": "PRICED-capable",
                "draw-no-bet": "PRICED-capable",
                "double-chance": "PRICED-capable",
                "correct-score": "PRICED-capable",
                "team-props": "PRICED-capable"}
        for key, cp in sorted((blob.get("cups") or {}).items()):
            st = cp.get("strengths") or {}
            gate = cp.get("gate") or {}
            ships = bool(gate.get("ships"))
            e = entry("soccer", f"cup-{key}", "Poisson goals "
                      "grid + Elo check, pooled cup fit (one "
                      "walk-forward pool across the cup family "
                      "— cross-competition fixtures only)",
                      P("v5-soccer-leagues.json"),
                      covered=len(st), teams=sorted(st),
                      fitted_at=cp.get("fitted_at"),
                      source=cp.get("source"),
                      backtest=cp.get("backtest"),
                      note=None if ships else
                      "HELD at its gate — the pool is on record "
                      "with its walk-forward numbers and prices "
                      "nothing")
            e["league_params"] = {
                "league_rates": cp.get("league"),
                "params": cp.get("params"),
                "season": cp.get("season"),
                "competitions": cp.get("competitions"),
                "gate": gate}
            e["team_entries"] = st
            if ships:
                e["bet_types"] = {
                    "moneyline": "PRICED-capable (1X2 off the "
                                 "grid, both clubs in the pool)",
                    "spread": "PRICED-capable (.5 handicaps)",
                    "totals": "PRICED-capable (grid totals)",
                    "btts": "PRICED-capable",
                    "draw-no-bet": "PRICED-capable",
                    "double-chance": "PRICED-capable",
                    "correct-score": "PRICED-capable",
                    "team-props": "PRICED-capable"}
            else:
                e["bet_types"] = {
                    bt: "UNPRICED — pooled cup fit HELD at its "
                        "gate (see league_params.gate)"
                    for bt in ("moneyline", "spread", "totals",
                               "btts", "draw-no-bet",
                               "double-chance", "correct-score",
                               "team-props")}
        for key, lg in sorted((blob.get("control") or {}).items()):
            st = lg.get("strengths") or {}
            e = entry("soccer", f"{key}-control",
                      "Poisson goals grid + Elo check",
                      P("v5-soccer-leagues.json"), covered=len(st),
                      teams=sorted(st), fitted_at=lg.get("fitted_at"),
                      source=lg.get("source"),
                      backtest=lg.get("backtest"),
                      note="control refit — compared against the "
                           "shipped fit, never priced from")
            e["league_params"] = {"league_rates": lg.get("league"),
                                  "params": lg.get("params")}
            e["team_entries"] = st
    nba = _load_json(P("v5-nba.json"))
    if nba is not None:
        r = nba.get("ratings") or {}
        e = entry("nba", nba.get("season") or "nba",
                  "Elo (sequential, K=20, HFA=100) + OLS margin map",
                  P("v5-nba.json"), covered=len(r), teams=sorted(r),
                  fitted_at=nba.get("fitted_at"),
                  source=nba.get("source"),
                  backtest=nba.get("backtest"))
        e["league_params"] = {"margin_map": nba.get("margin_map"),
                              "params": nba.get("params")}
        e["team_entries"] = r
        e["bet_types"] = {
            "moneyline": "PRICED-capable (Elo)",
            "spread": "PRICED-capable (margin map — FRAGILE lineage)",
            "alt-spread": "PRICED-capable (margin map — FRAGILE "
                          "lineage)",
            "totals": _totals_bet_type("nba", d),
            "alt-total": _totals_bet_type("nba", d),
            "segment": _seg_us_line("nba-1h") + " | 1Q: "
                       + _seg_us_line("nba-1q", "1st-quarter")}
    nflp = _load_json(P("nfl-week6-pricing.json"))
    if isinstance(nflp, dict) and isinstance(
            nflp.get("ratings"), dict):
        r = nflp["ratings"]
        e = entry("nfl", "nfl",
                  "phi/Elo moneyline + margin distribution "
                  "N(mu, 13.9) for covers",
                  P("nfl-week6-pricing.json"), covered=len(r),
                  teams=sorted(r))
        e["league_params"] = {"margin_sd": NFL_MARGIN_SD,
                              "games_on_file": len(
                                  nflp.get("games") or [])}
        e["team_entries"] = r
        e["bet_types"] = {
            "moneyline": "PRICED-capable (phi/Elo lane)",
            "spread": "PRICED-capable (margin distribution)",
            "alt-spread": "PRICED-capable (margin distribution)",
            "totals": _totals_bet_type("nfl", d),
            "alt-total": _totals_bet_type("nfl", d),
            "segment": _seg_us_line("nfl-1h") + " | 1Q: "
                       + _seg_us_line("nfl-1q", "1st-quarter")}
    cfb = _load_json(P("ratings_cfb.json"))
    if isinstance(cfb, dict):
        e = entry("ncaaf", "cfb",
                  "distributional ratings (Elo mu/sigma per team) "
                  "+ margin lane (like-for-like OLS)",
                  P("ratings_cfb.json"), covered=len(cfb),
                  teams=sorted(cfb))
        try:
            lane = fit_margin_lane()
        except Exception:
            lane = None
        e["league_params"] = {"margin_lane": lane,
                              "hfa_elo": CFB_HFA_ELO}
        e["team_entries"] = cfb
        e["bet_types"] = {
            "moneyline": "PRICED-capable (margin distribution)",
            "spread": "PRICED-capable (margin lane)",
            "alt-spread": "PRICED-capable (margin lane)",
            "totals": _totals_bet_type("ncaaf", d),
            "alt-total": _totals_bet_type("ncaaf", d),
            "segment": _seg_us_line("ncaaf-1h") + " | 1Q: "
                       + _seg_us_line("ncaaf-1q", "1st-quarter")
                       + " | 2Q: "
                       + _seg_us_line("ncaaf-2q", "2nd-quarter")}
    nhl = _load_json(P("ratings_nhl.json"))
    if isinstance(nhl, dict):
        e = entry("nhl", "nhl",
                  "Elo (sigma-integrated win prob) + home-ice",
                  P("ratings_nhl.json"), covered=len(nhl),
                  teams=sorted(nhl))
        e["league_params"] = {"K": NHL_K, "hfa_elo": NHL_HFA_ELO}
        e["team_entries"] = nhl
        e["bet_types"] = {
            "moneyline": "PRICED-capable (Elo)",
            "spread": "UNPRICED — no NHL engine for spread/"
                      "puck-line (moneyline only)",
            "alt-spread": "UNPRICED — no NHL engine for spread/"
                          "puck-line (moneyline only)",
            "totals": _totals_bet_type("nhl", d),
            "alt-total": _totals_bet_type("nhl", d),
            "segment": _seg_nhl_line(_seg_lanes)}
    mlb = _load_json(P("v5-mlb.json"))
    if mlb is not None:
        elo = mlb.get("elo") or {}
        bt = mlb.get("backtest") or {}
        passed = (bt.get("brier") is not None
                  and bt.get("naive_brier") is not None
                  and bt["brier"] < bt["naive_brier"])
        e = entry("mlb", "mlb",
                  "Elo (sequential, K=4) + runs model "
                  "(off/def run rates)",
                  P("v5-mlb.json"), covered=len(elo),
                  teams=sorted(elo),
                  fitted_at=mlb.get("fitted_at"),
                  source=mlb.get("source"), backtest=bt or None)
        e["league_params"] = {"params": mlb.get("params"),
                              "league": mlb.get("league"),
                              "totals_candidate":
                                  mlb.get("totals_candidate")}
        e["team_entries"] = mlb.get("runs") or {}
        e["bet_types"] = {
            "moneyline": ("PRICED-capable (Elo, walk-forward "
                          "passed naive)" if passed else
                          "UNPRICED — FAILED-EXAM: walk-forward "
                          "Brier did not beat the naive baseline "
                          "(numbers in the fit file)"),
            "spread": "UNPRICED — no run-line distribution "
                      "fitted for this lane",
            "totals": _totals_bet_type("mlb", d),
            "alt-total": _totals_bet_type("mlb", d)}
    ten = _load_json(P("v5-tennis.json"))
    if ten is not None:
        for tour, blk in sorted((ten.get("tours") or {}).items()):
            elo = blk.get("elo") or {}
            bt = blk.get("backtest") or {}
            e = entry("tennis", tour,
                      "Elo (sequential, K=32) per tour — "
                      "overall + per-surface ratings carried",
                      P("v5-tennis.json"), covered=len(elo),
                      teams=sorted(elo),
                      fitted_at=ten.get("fitted_at"),
                      source=ten.get("source"), backtest=bt)
            e["league_params"] = {
                "params": ten.get("params"),
                "window": blk.get("window"),
                "surfaces": sorted(
                    (blk.get("surface_elo") or {}).keys()),
                "surface_backtest": blk.get("surface_backtest")}
            e["team_entries"] = elo
            e["bet_types"] = {
                "moneyline": ("PRICED-capable (Elo, "
                              "walk-forward passed naive)"
                              if _exam_passed(bt) else
                              "UNPRICED — FAILED-EXAM: "
                              "walk-forward Brier did not beat "
                              "the naive baseline (numbers in "
                              "the fit file)"),
                "spread": "UNPRICED — no set/handicap "
                          "distribution fitted for this lane",
                "totals": "UNPRICED — no game-totals "
                          "distribution fitted for this lane"}
    cri = _load_json(P("v5-cricket.json"))
    if cri is not None:
        for lane, blk in sorted((cri.get("lanes") or {}).items()):
            r = blk.get("ratings") or {}
            bt = blk.get("backtest") or {}
            e = entry("cricket", lane,
                      "team Elo (sequential, K=20, no home "
                      "edge) per format/competition"
                      + (" + fitted draw rate (three-way)"
                         if lane.startswith("test") else ""),
                      P("v5-cricket.json"), covered=len(r),
                      teams=sorted(r),
                      fitted_at=cri.get("fitted_at"),
                      source=cri.get("source"), backtest=bt)
            e["league_params"] = {
                "draw_rate": blk.get("draw_rate"),
                "n_matches": blk.get("n_matches")}
            e["team_entries"] = r
            e["bet_types"] = {
                "moneyline": ("PRICED-capable (Elo, "
                              "walk-forward passed naive)"
                              if _exam_passed(bt) else
                              "UNPRICED — FAILED-EXAM: "
                              "walk-forward Brier did not beat "
                              "the naive baseline (numbers in "
                              "the fit file)"),
                "totals": "UNPRICED — no ball-by-ball totals "
                          "distribution fitted for this lane"}
    rug = _load_json(P("v5-rugby.json"))
    if rug is not None:
        for lane, blk in sorted((rug.get("league") or {}).items()):
            r = blk.get("ratings") or {}
            bt = blk.get("backtest") or {}
            e = entry("rugby-league", lane,
                      "national-team Elo (sequential, K=20) "
                      "from international results",
                      P("v5-rugby.json"), covered=len(r),
                      teams=sorted(r),
                      fitted_at=rug.get("fitted_at"),
                      source=blk.get("source"), backtest=bt)
            e["team_entries"] = r
            e["bet_types"] = {
                "moneyline": ("PRICED-capable (Elo)"
                              if _exam_passed(bt) else
                              "UNPRICED — FAILED-EXAM: "
                              "walk-forward Brier did not beat "
                              "the naive baseline (numbers in "
                              "the fit file)"),
                "futures": "UNPRICED — no outright model"}
        for lane, blk in sorted((rug.get("union") or {}).items()):
            r = blk.get("ratings") or {}
            bt = blk.get("backtest") or {}
            e = entry("rugby-union", lane,
                      "team Elo (sequential, K=20) + expanding "
                      "margin map (NPC)",
                      P("v5-rugby.json"), covered=len(r),
                      teams=sorted(r),
                      fitted_at=rug.get("fitted_at"),
                      source=blk.get("source"), backtest=bt)
            e["league_params"] = {"margin_map":
                                  blk.get("margin_map")}
            e["team_entries"] = r
            e["bet_types"] = {
                "moneyline": ("PRICED-capable (Elo)"
                              if _exam_passed(bt) else
                              "UNPRICED — FAILED-EXAM: "
                              "walk-forward Brier did not beat "
                              "the naive baseline (numbers in "
                              "the fit file)"),
                "spread": ("PRICED-capable (margin map) only "
                           "while the winner exam passes"
                           if _exam_passed(bt) else
                           "UNPRICED — lane FAILED-EXAM"),
                "futures": "UNPRICED — no outright model"}
    f1 = _load_json(P("v5-f1.json"))
    if f1 is not None:
        r = f1.get("ratings") or {}
        bt = f1.get("backtest") or {}
        a1 = f1.get("attempt_1") or {}
        e = entry("motorsport", "f1",
                  "driver Elo (teammate head-to-heads) + "
                  "constructor effect; winner = softmax over "
                  "the field (attempt 2; attempt 1 was a pure "
                  "driver Elo)",
                  P("v5-f1.json"), covered=len(r),
                  teams=sorted(r),
                  fitted_at=f1.get("fitted_at"),
                  source=f1.get("source"), backtest=bt)
        e["team_entries"] = r
        e["bet_types"] = {
            "futures": ("UNPRICED — FAILED-EXAM (TERMINAL): "
                        f"attempt 1 driver Elo log-loss "
                        f"{a1.get('log_loss')} vs naive "
                        f"{a1.get('naive_log_loss')}; attempt 2 "
                        f"driver+constructor log-loss "
                        f"{bt.get('log_loss')} vs naive "
                        f"{bt.get('naive_log_loss')}, Brier "
                        f"{bt.get('brier')} vs "
                        f"{bt.get('naive_brier')} — both attempts "
                        "lost; race-winner form only — fastest "
                        "lap / podium / manufacturer forms were "
                        "never the fitted form")}
    mma = _load_json(P("v5-mma.json"))
    if mma is not None:
        elo = mma.get("elo") or {}
        bt = mma.get("backtest") or {}
        e = entry("mma", "ufc",
                  "fighter Elo (sequential, K=32, neutral cage)",
                  P("v5-mma.json"), covered=len(elo),
                  teams=sorted(elo),
                  fitted_at=mma.get("fitted_at"),
                  source=mma.get("source"), backtest=bt or None)
        e["league_params"] = {"params": mma.get("params"),
                              "weight_classes": sorted(set(
                                  (mma.get("weight_class")
                                   or {}).values()))}
        e["team_entries"] = mma.get("record") or {}
        e["bet_types"] = {
            "moneyline": ("PRICED-capable (fighter Elo, "
                          "walk-forward passed naive)"
                          if _exam_passed(bt) else
                          "UNPRICED — FAILED-EXAM: walk-forward "
                          "Brier did not beat the naive baseline "
                          "(numbers in the fit file)"),
            "method-of-victory": "UNPRICED — no finish-method "
                                 "distribution fitted (the "
                                 "source carries win_by; a "
                                 "method model is a separate "
                                 "fit, not built)",
            "round-markets": "UNPRICED — no round distribution "
                             "fitted"}
    phi = _load_json(P("v5-phi.json"))
    if phi is not None:
        e = entry("multi", phi.get("lane") or "phi",
                  "reparametrization (phi)", P("v5-phi.json"),
                  fitted_at=phi.get("fitted_at"),
                  source=phi.get("status"),
                  backtest={"selected": phi.get("selected"),
                            "cv_brier": phi.get("cv_brier"),
                            "os_test": phi.get("os_test")})
        e["league_params"] = {"status_reason":
                              phi.get("status_reason")}
    for fn, sport, kind in (
            ("nhl_games_2026-27.json", "nhl", "game history"),
            ("cfb_games_2026.json", "ncaaf", "game history")):
        games = _load_json(P(fn))
        if isinstance(games, list):
            entry(sport, sport, kind, P(fn), covered=len(games),
                  note="games on file (history, not a fit)")
    hist = _load_json(P("v5-lane-history.json"))
    if isinstance(hist, dict):
        e = entry("multi", "lane-history", "scored lane history",
                  P("v5-lane-history.json"), covered=len(hist),
                  teams=sorted(hist))
        e["team_entries"] = hist
    recal = _load_json(P("recal_params.json"))
    if isinstance(recal, dict):
        e = entry("multi", "recal", "recalibration params",
                  P("recal_params.json"), covered=len(recal),
                  teams=sorted(recal))
        e["league_params"] = recal
    # props + live + groupings: engine organs whose data is not
    # a single fit file — registered from what is on disk, with
    # their limits named, never inflated.
    cache_dir = os.path.join(d, "cache")
    gamelogs = []
    if os.path.isdir(cache_dir):
        gamelogs = [f for f in os.listdir(cache_dir)
                    if f.startswith("gamelog_")
                    and f.endswith(".json")]
    e = entry("props", "player-props",
              "per-player gamelog distribution (two-family band: "
              "normal vs lognormal on the player's own game log)",
              P("cache"), covered=len(gamelogs),
              note="distributions keyed by athlete id in "
                   "data/cache/gamelog_<id>.json; a player with "
                   "no cached gamelog has no distribution — the "
                   "checker stamps those props UNPRICED")
    e["bet_types"] = {"player-props": "PRICED-capable only where "
                                      "the player's gamelog is "
                                      "cached"}
    states = [f for f in os.listdir(d)
              if f.startswith("state-") and f.endswith(".json")] \
        if os.path.isdir(d) else []
    e = entry("live", "live",
              "Live Matrix (in-game state pricing)",
              P("state-*.json"), covered=len(states),
              note="in-game states on file; live markets price "
                   "only from a recorded state, never assumed")
    e["bet_types"] = {"live": "PRICED-capable only from a "
                              "recorded in-game state"}
    e = entry("multi", "parlay",
              "groupings: combined probability under printed "
              "independence + weakest-leg grade cap",
              P("betmodel5.py"), covered=None,
              note="same-game groupings stamp UNPRICED — no "
                   "correlation engine exists for them")
    e["bet_types"] = {
        "parlay": "PRICED-capable across games (independence "
                  "printed on the slip)",
        "same-game-parlay": "UNPRICED — no correlation engine "
                            "for same-game groupings"}

    for lane in TOTALS_LANES:
        tf = _load_json(P(f"v5-totals-{lane}.json"))
        if tf is None:
            continue
        teams = tf.get("teams") or {}
        dist = (tf.get("params") or {}).get("distribution",
                                            "normal")
        e = entry(lane, f"{lane}-totals",
                  f"totals distribution ({dist}) \u2014 team "
                  f"off/def scoring rates x the league's home/"
                  f"away scoring environment",
                  P(f"v5-totals-{lane}.json"),
                  covered=len(teams), teams=sorted(teams),
                  fitted_at=tf.get("fitted_at"),
                  source=tf.get("source"),
                  backtest=tf.get("backtest"),
                  note=(None if tf.get("status") == "FITTED"
                        else "FAILED-EXAM \u2014 this lane's "
                             "totals fit did not beat the naive "
                             "baseline walk-forward; totals stay "
                             "UNPRICED with the exam numbers "
                             "printed"))
        e["league_params"] = {"league_rates": tf.get("league"),
                              "sigma": tf.get("sigma"),
                              "params": tf.get("params"),
                              "status": tf.get("status"),
                              "history_n": tf.get("history_n")}
        e["team_entries"] = teams
        e["bet_types"] = {"totals": _totals_bet_type(lane, d),
                          "alt-total": _totals_bet_type(lane, d),
                          "team-props": _teamtotals_bet_type(d,
                                                             lane)}
    return out


def universal_coverage(markets, data_dir=None):
    """Coverage at (sport, league, bet-type) grain. For every
    cell present in `markets`: how many markets are
    PRICED-capable (the lane's specialized math exists AND both
    sides / the player are in it) vs UNPRICED, each UNPRICED
    with the named missing piece — per BET TYPE, so a league
    can show PRICED-capable moneylines while its totals stamp
    'no totals distribution for this lane yet'. Pure reporting
    over the same fits the checkers use; no verdict changes."""
    d = data_dir or DATA
    reg = universal_registry(d)
    team_sets = {}
    for e in reg:
        if e.get("teams"):
            team_sets.setdefault(e["sport"], set()).update(
                e["teams"])
    reg_sports = {e["sport"] for e in reg}

    def league_of(mkt):
        if mkt.get("sport") == "cricket":
            lane, _r = cricket_lane_for(
                load_cricket(), mkt.get("competition"),
                mkt.get("home"), mkt.get("away"))
            return lane or "cricket"
        if mkt.get("sport") == "rugby-league":
            return rugby_league_lane(mkt.get("competition"),
                                     mkt.get("home"),
                                     mkt.get("away"))
        if mkt.get("sport") == "rugby-union":
            return "npc"
        if mkt.get("sport") == "soccer":
            _fit, key = soccer_fit_for(mkt.get("home"),
                                       mkt.get("away"))
            if key:
                return key
            blob = load_soccer_leagues()
            hits = set()
            for k, lg in (blob or {}).get("leagues", {}).items():
                st = lg.get("strengths") or {}
                if mkt.get("home") in st or mkt.get("away") in st:
                    hits.add(k)
            if len(hits) == 1:
                return hits.pop()
            soc = load_soccer()
            if soc and (mkt.get("home") in soc["strengths"]
                        or mkt.get("away") in soc["strengths"]):
                return "epl"
            return "unresolved"
        return mkt.get("league") or mkt.get("sport") or "?"

    def cell_missing(mkt, league):
        sport = mkt.get("sport") or "?"
        bt = mkt.get("market") or "?"
        if bt in ("parlay", "same-game-parlay"):
            return ("no correlation engine for same-game "
                    "groupings — legs price individually only")
        if bt == "segment":
            # R5: coverage reads the same segment_price the
            # checker prices through — capable iff it returns
            # a probability for this very market form.
            p, info = segment_price(
                sport, mkt.get("home"), mkt.get("away"),
                mkt.get("segment"), mkt.get("side", "home"),
                mkt.get("line"), mkt.get("competition"))
            return None if p is not None else str(info)
        if bt == "futures" and sport == "soccer":
            p, info = outright_price(mkt)
            return None if p is not None else str(info)
        if sport == "soccer":
            fit, _k = soccer_fit_for(mkt.get("home"),
                                     mkt.get("away"))
            if fit is not None:
                return None
            reason = soccer_missing_reason(mkt.get("home"),
                                           mkt.get("away"))
            if reason is not None:
                return reason
            fits = [load_soccer()] + list(
                (load_soccer_leagues() or {}).get(
                    "leagues", {}).values())
            for team in (mkt.get("home"), mkt.get("away")):
                if not any(f and soccer_fit_key(f, team) is not None
                           for f in fits):
                    return f"team not in the soccer fit: {team}"
            return ("teams split across league fits — no single "
                    "league fit holds both")
        if sport in ("tennis", "mma"):
            return h2h_lane_missing(mkt)
        if sport in ("cricket", "rugby-league", "rugby-union",
                     "boxing"):
            return r4_lane_missing(mkt)
        if sport in ("nba", "mlb") and bt in (
                "totals", "alt-total", "player-props",
                "team-props", "game-props"):
            # R4 competition truth in coverage too: the cell
            # names the real competition, not an NBA gap.
            comp = competition_missing(sport, mkt.get("home"),
                                       mkt.get("away"))
            if comp:
                return comp
        if bt in ("totals", "alt-total"):
            # R5: read the lane's totals fit — the same file
            # totals_price() prices from, so coverage and the
            # checker cannot disagree about this cell.
            if sport not in TOTALS_LANES:
                return ("no totals distribution for this lane "
                        "yet — close by: fit one "
                        "(tools/fit_totals.py)")
            tf = _load_json_cached(_totals_path(sport, d))
            if tf is None:
                return ("no totals distribution for this lane "
                        "yet — close by: fit one "
                        "(tools/fit_totals.py)")
            if tf.get("status") != "FITTED":
                bt_blk, exam_label = _latest_exam(tf)
                return (f"totals fit FAILED-EXAM for this lane "
                        f"({exam_label} Brier "
                        f"{bt_blk.get('brier_model')} vs naive "
                        f"{bt_blk.get('brier_naive')}, "
                        f"n={bt_blk.get('n')}) — close by: a "
                        f"refit that beats the naive baseline")
            tteams = tf.get("teams") or {}
            taliases = tf.get("aliases") or {}
            for side_ in ("home", "away"):
                t = mkt.get(side_)
                if t is None or t in tteams:
                    continue
                if sport == "nfl" and resolve_nfl_team(
                        t, tteams) is not None:
                    continue  # engine_price pre-resolves it too
                if sport == "ncaaf" and _resolve_or_none(
                        tteams, t,
                        FD_CFB_SCHOOL_ALIASES) is not None:
                    continue  # engine_price pre-resolves it too
                try:
                    resolve_team(tteams, taliases.get(t, t))
                except SystemExit:
                    return (f"team not in the {sport} totals "
                            f"fit: {t}")
            return None
        if bt == "team-props" and sport in TOTALS_LANES:
            tf = _load_json(os.path.join(
                d, f"v5-teamtotals-{sport}.json"))
            if tf is None:
                return ("no team-totals distribution for this "
                        "lane yet \u2014 close by: fit one "
                        "(tools/fit_totals.py team)")
            if tf.get("status") != "FITTED":
                bt_blk, exam_label = _latest_exam(tf)
                return (f"team-totals fit FAILED-EXAM for this "
                        f"lane ({exam_label} Brier "
                        f"{bt_blk.get('brier_model')} vs naive "
                        f"{bt_blk.get('brier_naive')}, "
                        f"n={bt_blk.get('n')}) \u2014 close by: a "
                        f"refit that beats the naive team-mean "
                        f"baseline")
            tteams = tf.get("teams") or {}
            taliases = tf.get("aliases") or {}
            for side in ("home", "away"):
                t = mkt.get(side)
                if t is None or t in tteams:
                    continue
                try:
                    resolve_team(tteams, taliases.get(t, t))
                except SystemExit:
                    return (f"team not in the {sport} team-totals "
                            f"fit: {t}")
            return None
        if bt in ("player-props", "team-props", "game-props"):
            pid = mkt.get("player_id") or mkt.get("athlete_id")
            if pid and os.path.exists(os.path.join(
                    d, "cache", f"gamelog_{pid}.json")):
                return None
            who = mkt.get("player") or "this player"
            return (f"no fitted gamelog distribution on file "
                    f"for player: {who}")
        if sport == "nhl" and bt in ("spread", "alt-spread"):
            return ("no NHL engine for spread/puck-line "
                    "(moneyline only)")
        if sport == "motorsport":
            fit = load_f1()
            bt1 = (fit or {}).get("backtest") or {}
            if "Grand Prix" in str(mkt.get("home") or ""):
                a1 = (fit or {}).get("attempt_1") or {}
                return ("F1 lane FAILED-EXAM (TERMINAL) — "
                        f"attempt 1 driver Elo log-loss "
                        f"{a1.get('log_loss')} vs naive "
                        f"{a1.get('naive_log_loss')}; attempt 2 "
                        f"driver+constructor log-loss "
                        f"{bt1.get('log_loss')} vs naive "
                        f"{bt1.get('naive_log_loss')} — both "
                        "attempts lost to the win-share "
                        "baseline; lane closed")
            return ("NASCAR source terminal — results publish "
                    "as R data files only (nascaR.data .rda, no "
                    "verified CSV route); closer: an R/pyreadr "
                    "conversion or a verified CSV mirror")
        if sport == "golf":
            return ("golf source terminal — full-field results "
                    "source key-gated (DataGolf HTTP 403); no "
                    "honest group-form exam exists; closer: a "
                    "DataGolf key or a verified full-field "
                    "archive")
        if sport == "lacrosse":
            return ("lacrosse outright terminal — arriving "
                    "markets are season outrights; a team Elo "
                    "does not price a championship outright "
                    "without a season simulator; closer: an "
                    "NLL season-simulator outright model")
        if sport in UNCHECKED_SPORTS:
            return (f"no checker registered for {sport} yet "
                    f"— see coverage queue")
        if sport in ("ncaaf", "nfl", "nba", "nhl", "mlb"):
            return us_lane_missing(mkt, league, reg_sports)
        entries = team_sets.get(sport)
        if not entries:
            return f"no fit registered for league {league}"
        for side in ("home", "away"):
            t = mkt.get(side)
            if t is not None and t not in entries:
                return f"team not in the {league} fit: {t}"
        return None

    def h2h_lane_missing(mkt):
        """Membership for the R3 head-to-head lanes (tennis,
        mma), decided by the SAME resolvers + exam gate the
        checkers use — coverage cannot disagree with a checker
        about whether a player is in a fit or a lane passed."""
        sport = mkt.get("sport")
        bt = mkt.get("market")
        if sport == "tennis":
            fit = load_tennis()
            if fit is None:
                return "no fit registered for league tennis"
            if bt == "futures":
                return TENNIS_FUTURES_TERMINAL
            if bt != "moneyline":
                return ("no tennis engine for this market "
                        "(moneyline only — set/handicap and game "
                        "totals not fitted)")
            tour, p_or_reason = tennis_probs(
                fit, mkt.get("home"), mkt.get("away"))
            if tour is None:
                return p_or_reason
            blk = (fit.get("tours") or {}).get(tour) or {}
            if not _exam_passed(blk.get("backtest")):
                return (f"tennis {tour.upper()} lane "
                        "FAILED-EXAM — walk-forward Brier did "
                        "not beat the naive baseline; lane does "
                        "not price")
            return None
        fit = load_mma()
        if fit is None:
            return "no fit registered for league mma"
        if not _exam_passed(fit.get("backtest")):
            return ("MMA lane FAILED-EXAM — walk-forward Brier "
                    "did not beat the naive baseline; lane does "
                    "not price")
        if bt != "moneyline":
            return ("no MMA engine for this market (moneyline "
                    "only — method-of-victory and round markets "
                    "not fitted)")
        _p, reason = mma_probs(fit, mkt.get("home"),
                               mkt.get("away"))
        return reason

    def r4_lane_missing(mkt):
        """Membership for the R4 lanes (cricket, both rugbys,
        boxing), decided by the SAME helpers + exam gates the
        checkers use — coverage cannot disagree with a checker
        about a lane's verdict or a team's membership."""
        sport = mkt.get("sport")
        bt = mkt.get("market")
        if sport == "boxing":
            if bt != "moneyline":
                return (f"no boxing engine for this market "
                        f"({bt}) — and the moneyline lane itself "
                        "is source-gated (BoxRec 403)")
            _p, reason = engine_price(
                "boxing", "moneyline", mkt.get("home"),
                mkt.get("away"))
            return reason
        if sport == "cricket":
            fit = load_cricket()
            if fit is None:
                return "no fit registered for league cricket"
            if bt == "futures":
                return ("no cricket engine for outright/futures "
                        "markets (moneyline only)")
            if bt != "moneyline":
                return ("no cricket engine for this market "
                        "(moneyline only — no ball-by-ball "
                        "totals/scoring distribution fitted)")
            lane, reason = cricket_lane_for(
                fit, mkt.get("competition"), mkt.get("home"),
                mkt.get("away"))
            if lane is None:
                return reason
            _p, reason = cricket_probs(fit, lane, mkt.get("home"),
                                       mkt.get("away"),
                                       mkt.get("side", "home"))
            return reason
        if sport == "rugby-league":
            fit = load_rugby()
            if fit is None:
                return "no fit registered for league rugby-league"
            if bt == "futures":
                return ("rugby league outright — the fitted "
                        "lanes price fixtures, not World Cup "
                        "outrights (no outright model)")
            if bt != "moneyline":
                return ("no rugby league engine for this "
                        "market (moneyline only)")
            lane = rugby_league_lane(mkt.get("competition"),
                                     mkt.get("home"),
                                     mkt.get("away"))
            _p, reason = rugby_probs(fit, "league", lane,
                                     mkt.get("home"),
                                     mkt.get("away"))
            return reason
        # rugby-union
        fit = load_rugby()
        if fit is None:
            return "no fit registered for league rugby-union"
        if bt == "futures":
            return ("rugby union outright — no outright model "
                    "(the fitted NPC lane prices fixtures only, "
                    "and it FAILED-EXAM)")
        npc = ((fit.get("union") or {}).get("npc")) or {}
        ratings = npc.get("ratings") or {}
        for t in (mkt.get("home"), mkt.get("away")):
            if t is not None and \
                    _resolve_or_none(ratings, t) is None:
                return ("no rugby union fit for this fixture's "
                        "competition — the fitted union lane is "
                        "the New Zealand NPC only")
        _p, reason = rugby_probs(fit, "union", "npc",
                                 mkt.get("home"), mkt.get("away"))
        if reason:
            return reason
        if bt in ("moneyline", "spread", "alt-spread"):
            return None
        return "no rugby union engine for this market"

    def us_lane_missing(mkt, league, reg_sports):
        """Membership for the US team lanes, decided by the SAME
        resolvers the checkers use (v5.4 fix-guy) — coverage can
        no longer disagree with a checker about whether a team
        is in a fit. A name that fails its lane's resolver AND
        sits on the explicit other-competition list names that
        competition instead of blaming this lane's fit."""
        sport = mkt.get("sport")
        if sport not in reg_sports:
            return f"no fit registered for league {league}"
        if sport == "ncaaf":
            keys = fit_ratings("cfb")

            def res(t):
                return _resolve_or_none(keys, t,
                                        FD_CFB_SCHOOL_ALIASES)
        elif sport == "nhl":
            keys = fit_ratings("nhl")

            def res(t):
                return _resolve_or_none(keys, t)
        elif sport == "nba":
            fit = load_nba()
            if fit is None:
                return f"no fit registered for league {league}"
            keys = fit.get("ratings") or {}

            def res(t):
                return resolve_nba_team(t, keys)
        elif sport == "mlb":
            # R4: the SHARED gate + resolver (mlb_lane_gate /
            # resolve_mlb_team via mlb_membership) — the same
            # code the checker runs, so the layers agree by
            # construction (harness-proved).
            fit = load_mlb()
            gate = mlb_lane_gate(fit)
            if gate:
                return gate
            if mkt.get("market") in ("spread", "alt-spread"):
                return ("no run-line distribution fitted for "
                        "the MLB lane (moneyline only)")
            keys = fit.get("elo") or {}

            def res(t):
                return resolve_mlb_team(t, keys)
        else:  # nfl
            pricing = _load_json_cached(NFL_PRICING_PATH) or {}
            keys = pricing.get("ratings") or {}
            if not keys:
                return f"no fit registered for league {league}"

            def res(t):
                return resolve_nfl_team(t, keys)
        for side in ("home", "away"):
            t = mkt.get(side)
            if t is None:
                continue
            if res(t) is not None:
                continue
            comp = OTHER_COMPETITION_TEAMS.get(t)
            if comp:
                return (f"competition not in this app: {comp} "
                        f"({t}) — FanDuel files it under "
                        f"{sport}, it is not a {league} team")
            return f"team not in the {league} fit: {t}"
        if sport == "nfl" and mkt.get("market") in (
                "spread", "alt-spread"):
            # R2: spreads price for ANY resolved fixture — the
            # saved slate's fair where the fixture is on it, a
            # ratings-derived fair (validated map, MAE 0.02 vs
            # the slate's fairs) where it is not. Checker and
            # coverage use the same rule, so they agree.
            return None
        return None

    out = {}
    for mkt in markets or []:
        sport = mkt.get("sport") or "?"
        league = league_of(mkt)
        bt = mkt.get("market") or "?"
        key = (sport, league, bt)
        slot = out.setdefault(key, {
            "sport": sport, "league": league, "bet_type": bt,
            "markets": 0, "priced_capable": 0, "unpriced": 0,
            "missing": []})
        slot["markets"] += 1
        missing = cell_missing(mkt, league)
        if missing is None:
            slot["priced_capable"] += 1
        else:
            slot["unpriced"] += 1
            if missing not in slot["missing"]:
                slot["missing"].append(missing)
    rows = [out[k] for k in sorted(out)]
    # NOT PULLED: sports FanDuel offers that pull_menu() never
    # fetches are invisible in the app — not UNPRICED, absent.
    # They ride the coverage output as their own rows so the
    # gap is named wherever coverage is read.
    for inv in sport_inventory():
        if not inv["pulled"]:
            rows.append({
                "sport": inv["engine_key"], "league": inv["name"],
                "bet_type": "not-pulled", "markets": 0,
                "priced_capable": 0, "unpriced": 0,
                "not_pulled": True,
                "missing": [
                    f"NOT PULLED — FanDuel offers {inv['name']} "
                    f"(eventTypeId {inv['event_type_id']}) but "
                    f"pull_menu() never fetches it; closer: "
                    f"{inv['closer']}"]})
    return rows


# FanDuel's full sport menu, as named by the menu tree itself
# (application-context EVENT_TYPES, fetched live from this
# worktree 2026-10-24 — the tree decides this list, not memory).
FD_EVENT_TYPE_NAMES = {
    1: "Soccer", 2: "Tennis", 3: "Golf", 4: "Cricket",
    5: "Rugby Union", 6: "Boxing", 8: "Motor Sport",
    1477: "Rugby League", 3503: "Darts", 6422: "Snooker",
    6423: "American Football", 7511: "Baseball",
    7522: "Basketball", 7524: "Ice Hockey",
    2593174: "Table Tennis", 26420387: "Mixed Martial Arts",
    28608997: "Lacrosse",
}
# eventTypeId -> engine sport keys its page feeds when pulled.
FD_TREE_ROUTES = {
    6423: ["nfl", "ncaaf"], 7522: ["nba"], 7524: ["nhl"],
    7511: ["mlb"], 1: ["soccer"],
    # R2: every remaining tree sport routes to its own engine
    # key and is pulled (see FANDUEL_EVENT_TYPES).
    2: ["tennis"], 26420387: ["mma"], 3: ["golf"], 6: ["boxing"],
    4: ["cricket"], 3503: ["darts"], 8: ["motorsport"],
    5: ["rugby-union"], 1477: ["rugby-league"],
    28608997: ["lacrosse"], 6422: ["snooker"],
    2593174: ["table-tennis"],
}
# The named closer for every tree sport with no fit: the real
# math that would have to exist, fitted and backtested, before
# the app may price it. Naming the work is the deliverable for
# these sports this round — no fit is built here.
SPORT_CLOSERS = {
    "mlb": "moneyline lane FITTED (v5-mlb.json, Elo + runs "
           "model); game totals FITTED but FAILED-EXAM "
           "(v5-totals-mlb.json: walk-forward Brier 0.2533 vs "
           "naive 0.2511, MAE 3.641 vs 3.622, n=2233 — stamps, "
           "does not price); remaining: a totals refit that "
           "beats the naive baseline + starting-pitcher "
           "adjustment",
    "mma": "moneyline lane FITTED but FAILED-EXAM "
           "(v5-mma.json, fighter Elo on 5,902 decided UFC "
           "fights: walk-forward Brier 0.2454 vs naive 0.2451 "
           "— did not beat the baseline, so the lane stamps "
           "FAILED-EXAM and does not price); remaining: a "
           "refit that passes (fresher source — the mirror "
           "snapshot ends 2021 — and/or a richer fighter "
           "model), plus method-of-victory + round "
           "distributions",
    "motorsport": "F1 FAILED-EXAM, TERMINAL after both "
                  "attempts (v5-f1.json, Ergast/Jolpica "
                  "2015-2025, walk-forward vs the win-share "
                  "naive 2.0574): attempt 1 driver Elo log-loss "
                  "2.5036; attempt 2 (R5) driver+constructor "
                  "log-loss 2.2126, Brier 0.8182 vs naive "
                  "0.8122 — the constructor effect closed most "
                  "of the gap and still lost both metrics, so "
                  "the lane is closed); NASCAR source terminal "
                  "(results publish as R .rda only). Closer: an "
                  "R/pyreadr conversion for NASCAR",
    "rugby-union": "NPC lane FITTED and PRICED "
                   "(v5-rugby.json, Elo on Wikipedia Bunnings "
                   "NPC 2021-2026: Brier 0.2182 vs naive "
                   "0.2188, margin MAE 13.945 vs 15.051, "
                   "n=283 — a thin pass, labelled as such); "
                   "other union competitions not "
                   "fitted. Closer: per-competition fits as "
                   "boards arrive",
    "rugby-league": "international lanes FITTED but "
                    "FAILED-EXAM (v5-rugby.json, Elo on Rugby "
                    "League Project internationals 2016-2026: "
                    "men 0.2392 vs naive 0.2308, women 0.2377 "
                    "vs 0.2354). Closer: a passing refit with "
                    "richer inputs (recency/squad weighting)",
    "table-tennis": "per-player Elo from ITTF/WTT match "
                    "results — ATTEMPTED R3 (2026-10-24): no "
                    "public match-level results source found "
                    "(GitHub repo/code search; the one ITTF "
                    "scrape repo carries weekly rankings "
                    "snapshots, not matches; WTT results sit "
                    "behind paid data APIs). Closer: a public "
                    "ITTF/WTT match-results archive",
    "tennis": "moneyline lane FITTED (v5-tennis.json, ATP + "
              "WTA Elo — both tours passed their walk-forward "
              "vs the naive win-rate baseline); remaining: "
              "set/handicap + game-totals distributions, and a "
              "fresher ATP window (the Sackmann mirror's last "
              "season is 2024)",
    "golf": "SOURCE TERMINAL — group-winner/top-region forms "
            "need full-field historical finishes for an honest "
            "exam; DataGolf is key-gated (HTTP 403, verified "
            "2026-10-24) and no verified public full-field "
            "archive exists. Closer: a DataGolf API key or a "
            "verified full-field results archive",
    "mixed martial arts": "per-fighter history fit — record, "
              "finish rates, weight class — from a public "
              "stats source (e.g. UFCStats)",
    "boxing": "SOURCE TERMINAL — BoxRec (the only complete "
              "pro archive) is access-gated (HTTP 403 / bot "
              "wall, verified 2026-10-24); the public GitHub "
              "candidate is a 78-fight popular-match subset, "
              "not an archive. Closer: a licensed BoxRec export "
              "or a verified full pro results archive",
    "cricket": "moneyline lanes FITTED per format from "
               "Cricsheet (v5-cricket.json): t20i_m/f, odi_m/f, "
               "test_m (three-way) and csa_t20 PASSED their "
               "walk-forward exams and price; bbl / wbbl / "
               "ipl / lista_m / test_f FAILED-EXAM and stamp "
               "with numbers. Known source gap: the Cricsheet "
               "snapshot carries no Afghanistan fixtures, so "
               "their matches stamp team-not-in-fit until the "
               "archive restores them. Remaining: totals/"
               "scoring distributions",
    "darts": "per-player 3-dart-average / checkout-percentage "
             "distributions + match-winner Elo from PDC "
             "results — ATTEMPTED R3 (2026-10-24): no public "
             "PDC match-results archive found (the OpenDarts "
             "repo is empty; only single-tournament Kaggle "
             "exports exist). Closer: a maintained public PDC "
             "results history",
    "motor sport": "see the motorsport entry (F1 FAILED-"
                   "EXAM; NASCAR source terminal)",
    "rugby union": "see the rugby-union entry (NPC fitted, "
                   "FAILED-EXAM)",
    "rugby league": "see the rugby-league entry (international "
                    "lanes fitted, FAILED-EXAM)",
    "lacrosse": "OUTRIGHT TERMINAL — the arriving markets are "
                "season outrights (NLL Cup / NCAA championship); "
                "NLL results exist (ESPN route) but a team Elo "
                "does not price a championship outright without "
                "a season simulator. Closer: an NLL season-"
                "simulator outright model",
    "snooker": "per-player frame-level Elo from match "
               "history — ATTEMPTED R3 (2026-10-24): the "
               "snooker.org API requires an approved "
               "X-Requested-By header value (registration-"
               "gated, per its own API page; ungated calls "
               "return 401) and no GitHub match-results CSV "
               "exists. Closer: snooker.org API approval or a "
               "public results archive",
    "table tennis": "per-player Elo from ITTF/WTT match "
                    "results — ATTEMPTED R3: no public "
                    "match-level results source found (see "
                    "the table-tennis entry)",
}
SPORT_FIT_NOTES = {
    "nfl": "phi/Elo moneyline + margin distribution (rides "
           "the American Football page)",
    "ncaaf": "CFB distributional ratings + margin lane (rides "
             "the American Football page)",
    "nba": "NBA Elo + margin map (Basketball page; other "
           "competitions on that page — WNBA/NBL — are not the "
           "NBA fit)",
    "nhl": "NHL Elo, moneyline (Ice Hockey page; AHL/NCAA "
           "hockey on that page are not the NHL fit)",
    "mlb": "MLB Elo + runs model, moneyline (v5-mlb.json; "
           "totals not wired — runs model carried in the fit "
           "file for the totals lane)",
    "soccer": "per-league Poisson goals grid + Elo (EPL + the "
              "leagues file)",
    "tennis": "ATP + WTA player Elo (v5-tennis.json; both "
              "tours walk-forward passed — moneyline PRICED "
              "where both players are in a tour fit)",
    "mma": "UFC fighter Elo fitted (v5-mma.json) but "
           "FAILED-EXAM — walk-forward Brier 0.2454 vs naive "
           "0.2451; every market stamps FAILED-EXAM until a "
           "refit passes",
    "golf": "no fit registered", "boxing": "no fit registered",
    "cricket": "no fit registered", "darts": "no fit registered",
    "motorsport": "no fit registered",
    "rugby-union": "no fit registered",
    "rugby-league": "no fit registered",
    "lacrosse": "no fit registered",
    "snooker": "no fit registered",
    "table-tennis": "no fit registered",
}


def sport_inventory(event_types=None):
    """FanDuel's FULL sport menu vs this app, one row per tree
    sport: (a) does pull_menu() fetch its page today, (b) does
    a checker/fit exist, (c) what would a market for it stamp.
    `event_types` may carry a live tree ({id: name} as
    build_menu_tree returns); the default is the tree captured
    live 2026-10-24 in FD_EVENT_TYPE_NAMES. A sport the pull
    never fetches is NOT PULLED — invisible, not UNPRICED —
    and is named as such, with its closer."""
    types = event_types or FD_EVENT_TYPE_NAMES
    pulled_ids = {tid for tid, keys in FD_TREE_ROUTES.items()
                  if any(k in FANDUEL_EVENT_TYPES for k in keys)}
    rows = []
    for tid, name in sorted(types.items(),
                            key=lambda kv: str(kv[1])):
        keys = FD_TREE_ROUTES.get(tid) or []
        pulled = tid in pulled_ids and bool(keys)
        slug = name.lower().replace(" ", "-")
        fit = "; ".join(SPORT_FIT_NOTES.get(k, "no fit "
                        "registered") for k in keys) if keys \
            else "no fit registered"
        has_fit = bool(keys) and any(
            SPORT_FIT_NOTES.get(k) not in (None, "no fit "
            "registered") for k in keys)
        if not pulled:
            stamp = ("NOT PULLED — pull_menu() never fetches "
                     "this page; its markets never reach the "
                     "app at all")
        elif has_fit:
            stamp = ("priced by its lane's checkers where the "
                     "fit holds; UNPRICED with the missing piece "
                     "named where it does not")
        else:
            stamp = ("pulled, but no fit/engine prices it — "
                     "every market stamps UNPRICED (no engine "
                     "for this sport)")
        rows.append({
            "event_type_id": tid, "name": name,
            "engine_key": keys[0] if keys else slug,
            "engine_sports": keys, "pulled": pulled,
            "fit": fit, "stamp_today": stamp,
            "closer": (SPORT_CLOSERS.get(slug)
                       or SPORT_CLOSERS.get(name.lower())
                       or SPORT_CLOSERS.get(keys[0] if keys
                                            else "", "—"))})
    return rows


# ----------------------------------------------------------------
# Game totals distribution lanes (fits by CODER GLOW,
# tools/fit_totals.py; artifacts data/v5-totals-<lane>.json).
# Ported into this tree in R5 (fix-guy) with the formulas and
# fit-file format unchanged, so the ALT-TOTAL wire runs through
# the SAME distribution function the straight totals checker
# uses — one function prices both market forms, and parity at
# the main line holds by construction (proved in the R5
# battery). Model per lane: lam_home = LH*off[h]*def[a],
# lam_away = LA*off[a]*def[h] from team scoring rates shrunk
# to the league mean; the total follows the lane's fitted
# distribution (Normal for NFL/NCAAF/NBA/MLB, Poisson for NHL)
# at the lane's walk-forward sigma. A lane prices only when
# its fit file's status is FITTED (walk-forward PASS vs the
# naive baseline on MAE and Brier); FAILED-EXAM lanes (NHL and
# MLB game totals) stamp the exam numbers and never price.

TOTALS_LANES = ("nfl", "ncaaf", "nba", "nhl", "mlb")


def _latest_exam(tf):
    """The most recent walk-forward exam recorded in a fit
    file: the highest refit_attempt_N block when refits exist,
    else the original backtest block. Every stamp that quotes
    exam numbers reads through here — never hardcoded, never
    a stale attempt. Returns (exam_block, label)."""
    best = (tf or {}).get("backtest") or {}
    n_best, label = (1 if best else 0), "walk-forward"
    for k, v in (tf or {}).items():
        if not (isinstance(k, str)
                and k.startswith("refit_attempt_")):
            continue
        tail = k[len("refit_attempt_"):]
        if tail.isdigit() and isinstance(v, dict) \
                and int(tail) > n_best:
            best, n_best = v, int(tail)
            label = f"refit attempt {n_best}"
    return best, label


def _totals_path(sport, data_dir=None):
    return os.path.join(data_dir or DATA, f"v5-totals-{sport}.json")


def load_totals_fit(sport):
    if sport not in TOTALS_LANES:
        return None
    return _load_json_cached(_totals_path(sport))


def _totals_bet_type(sport, data_dir=None):
    """The registry/coverage line for a lane's totals cell,
    read off its totals fit file: PRICED-capable with the
    walk-forward receipt when the fit PASSED, FAILED-EXAM
    with the numbers when it did not, and the named closer
    when no fit exists."""
    tf = _load_json_cached(_totals_path(sport, data_dir))
    if tf is None:
        return ("UNPRICED — no totals distribution for this "
                "lane yet — close by: fit one "
                "(tools/fit_totals.py)")
    bt, exam_label = _latest_exam(tf)
    if tf.get("status") != "FITTED":
        return (f"UNPRICED — totals fit FAILED-EXAM "
                f"({exam_label} Brier {bt.get('brier_model')} vs "
                f"naive {bt.get('brier_naive')}, MAE "
                f"{bt.get('mae_model')} vs {bt.get('mae_naive')}, "
                f"n={bt.get('n')})")
    return (f"PRICED-capable (totals distribution; "
            f"walk-forward MAE {bt.get('mae_model')} vs naive "
            f"{bt.get('mae_naive')}, Brier {bt.get('brier_model')} "
            f"vs {bt.get('brier_naive')}, n={bt.get('n')})")


def _pois_cdf(k, lam):
    if k < 0:
        return 0.0
    return sum(_pois(i, lam) for i in range(int(k) + 1))


def _totals_p_over(mu, sigma, dist, line):
    """(P(over wins), push mass). Integer lines condition the
    push mass out — a push refunds, it is not a loss dressed
    as one — and report it so the card can print it."""
    line = float(line)
    if dist == "poisson":
        if line == int(line):
            L = int(line)
            p_win = 1.0 - _pois_cdf(L, mu)
            p_push = _pois_cdf(L, mu) - _pois_cdf(L - 1, mu)
            p_lose = _pois_cdf(L - 1, mu)
            denom = p_win + p_lose
            return (p_win / denom if denom > 0 else 0.5), p_push
        return 1.0 - _pois_cdf(math.floor(line), mu), 0.0
    if line == int(line):
        L = int(line)
        p_win = 1.0 - norm_cdf((L + 0.5 - mu) / sigma)
        p_lose = norm_cdf((L - 0.5 - mu) / sigma)
        p_push = 1.0 - p_win - p_lose
        denom = p_win + p_lose
        return (p_win / denom if denom > 0 else 0.5), p_push
    return 1.0 - norm_cdf((line - mu) / sigma), 0.0


def totals_price(sport, home, away, side="over", line=None):
    """(p, info) for a game total from the lane's fitted
    distribution, or (None, named reason). Straight totals
    and alt totals both price through here (R5)."""
    fit = load_totals_fit(sport)
    if fit is None:
        return None, (f"no totals distribution fitted for the "
                      f"{sport} lane yet — close by: fit one "
                      f"(tools/fit_totals.py)")
    bt, exam_label = _latest_exam(fit)
    if fit.get("status") != "FITTED":
        return None, (
            f"{sport} totals fit FAILED-EXAM — {exam_label} "
            f"Brier {bt.get('brier_model')} vs naive "
            f"{bt.get('brier_naive')}, MAE {bt.get('mae_model')} "
            f"vs {bt.get('mae_naive')} (n={bt.get('n')}); the lane "
            f"does not price totals until a refit beats the naive "
            f"baseline")
    teams = fit.get("teams") or {}
    aliases = fit.get("aliases") or {}
    try:
        h = resolve_team(teams, aliases.get(home, home))
        a = resolve_team(teams, aliases.get(away, away))
    except SystemExit as e:
        return None, str(e)
    if line is None:
        return None, "no line supplied for this total"
    lg = fit["league"]
    th, ta = teams[h], teams[a]
    lam_h = lg["LH"] * th["off"] * ta["def"]
    lam_a = lg["LA"] * ta["off"] * th["def"]
    mu = lam_h + lam_a
    dist = (fit.get("params") or {}).get("distribution", "normal")
    sigma = fit.get("sigma")
    p_over, p_push = _totals_p_over(mu, sigma, dist, line)
    p = p_over if side == "over" else 1.0 - p_over
    detail = (f"{sport.upper()} totals distribution ({dist}; "
              f"fit {fit.get('fitted_at')}; history "
              f"n={fit.get('history_n')}): lambda "
              f"{lam_h:.2f}/{lam_a:.2f} -> mu {mu:.1f}"
              + (f", sigma {sigma}" if dist != "poisson" else "")
              + f"; walk-forward MAE {bt.get('mae_model')} vs "
                f"naive {bt.get('mae_naive')}, Brier "
                f"{bt.get('brier_model')} vs "
                f"{bt.get('brier_naive')} (n={bt.get('n')}) — "
                f"lane UNTESTED (no scored totals record yet)")
    if p_push:
        detail += (f" | push mass {p_push * 100:.1f}% "
                   f"conditioned out")
    return p, {"detail": detail}


# ------------------------------------------------------- team totals
# Team totals (Xii Round 2, CODER GLOW). A team total is ONE
# team's own scoring distribution — NOT the game total split or
# stretched. Fit artifacts: data/v5-teamtotals-<lane>.json, built
# by tools/fit_totals.py (`team` mode): lam_team from the lane's
# off/def rates, sigma_team fitted from actual team-score
# walk-forward residuals (per-team, shrunk toward the lane pool).
# Same house contract as game totals: a lane prices only when
# its fit file's status is FITTED (walk-forward PASS vs the
# team's own expanding-mean naive baseline, MAE and Brier);
# FAILED-EXAM lanes stamp the exam numbers. NHL team totals
# PASSED their (genuinely different) team-level exam in Round 2
# while NHL GAME totals are terminally FAILED-EXAM — the two
# cells are different models and are never blended.

TEAMTOTALS_LANES = TOTALS_LANES


def load_teamtotals_fit(sport):
    if sport not in TEAMTOTALS_LANES:
        return None
    return _load_json_cached(os.path.join(
        DATA, f"v5-teamtotals-{sport}.json"))


def team_totals_price(sport, home, away, team_side="home",
                      line=None, side="over"):
    """(p, info) for a team total from the team's own fitted
    scoring distribution, or (None, named reason)."""
    fit = load_teamtotals_fit(sport)
    if fit is None:
        return None, (f"no team-totals distribution fitted for "
                      f"the {sport} lane yet — close by: fit one "
                      f"(tools/fit_totals.py team)")
    bt, exam_label = _latest_exam(fit)
    if fit.get("status") != "FITTED":
        return None, (
            f"{sport} team-totals fit FAILED-EXAM — {exam_label} "
            f"Brier {bt.get('brier_model')} vs naive "
            f"{bt.get('brier_naive')}, MAE {bt.get('mae_model')} "
            f"vs {bt.get('mae_naive')} (n={bt.get('n')}); the lane "
            f"does not price team totals until a refit beats the "
            f"naive team-mean baseline")
    teams = fit.get("teams") or {}
    aliases = fit.get("aliases") or {}
    try:
        h = resolve_team(teams, aliases.get(home, home))
        a = resolve_team(teams, aliases.get(away, away))
    except SystemExit as e:
        return None, str(e)
    if line is None:
        return None, "no line supplied for this team total"
    lg = fit["league"]
    team_key, opp_key = (h, a) if team_side == "home" else (a, h)
    is_home = team_side == "home"
    th, to = teams[team_key], teams[opp_key]
    rate = lg["LH"] if is_home else lg["LA"]
    lam = rate * th["off"] * to["def"]
    dist = (fit.get("params") or {}).get("distribution", "normal")
    sigma = th.get("sigma_team") or lg.get("sigma_pool_team_score")
    if dist == "poisson":
        if float(line) == int(line):
            L = int(line)
            p_win = 1.0 - _pois_cdf(L, lam)
            p_push = _pois_cdf(L, lam) - _pois_cdf(L - 1, lam)
            p_lose = _pois_cdf(L - 1, lam)
            den = p_win + p_lose
            p_over = p_win / den if den > 0 else 0.5
        else:
            p_over = 1.0 - _pois_cdf(math.floor(line), lam)
            p_push = 0.0
    else:
        if float(line) == int(line):
            L = int(line)
            p_win = 1.0 - norm_cdf((L + 0.5 - lam) / sigma)
            p_lose = norm_cdf((L - 0.5 - lam) / sigma)
            p_push = 1.0 - p_win - p_lose
            den = p_win + p_lose
            p_over = p_win / den if den > 0 else 0.5
        else:
            p_over = 1.0 - norm_cdf((line - lam) / sigma)
            p_push = 0.0
    p = p_over if side == "over" else 1.0 - p_over
    detail = (f"{sport.upper()} team-totals distribution "
              f"({dist}; fit {fit.get('fitted_at')}; history "
              f"n={fit.get('history_n')}): {team_key} lambda "
              f"{lam:.2f}"
              + (f", sigma_team {sigma}" if dist != "poisson"
                 else "")
              + f"; walk-forward MAE {bt.get('mae_model')} vs "
                f"naive {bt.get('mae_naive')}, Brier "
                f"{bt.get('brier_model')} vs "
                f"{bt.get('brier_naive')} (n={bt.get('n')}) — "
                f"lane UNTESTED (no scored team-totals record "
                f"yet)")
    if p_push:
        detail += (f" | push mass {p_push * 100:.1f}% "
                   f"conditioned out")
    return p, {"detail": detail}


def engine_price(sport, kind, home, away, side="home", line=None,
                 competition=None, segment=None):
    if kind == "segment":
        return segment_price(sport, home, away, segment, side,
                             line, competition)
    if sport == "nfl":
        if kind in ("totals", "alt-total"):
            # the totals fit keys are codes; full FanDuel names
            # resolve through the lane's own code map first —
            # the same membership the moneyline branch uses.
            tt = (load_totals_fit("nfl") or {}).get("teams") or {}
            h = resolve_nfl_team(home, tt) or home
            a = resolve_nfl_team(away, tt) or away
            return totals_price("nfl", h, a, side, line)
        # canonical membership: full FanDuel names resolve to the
        # lane's codes through FD_NFL_TEAM_CODES, same as the
        # menu router does when it builds the slate.
        pricing = _load_json_cached(NFL_PRICING_PATH) or {}
        ratings = pricing.get("ratings") or {}
        ch = resolve_nfl_team(home, ratings)
        ca = resolve_nfl_team(away, ratings)
        if ch is None or ca is None:
            return None, f"team not in the NFL fit ({home}/{away})"
        try:
            p_home, g = nfl_price(ch, ca)
        except SystemExit:
            # The fixture is not on the saved slate of record, but
            # both teams ARE in the lane's fitted ratings — the
            # moneyline prices from those ratings (the same Elo
            # logistic nfl_price recomputes for slated games,
            # home field 55, neutral=False).
            d = ratings[ch] + 55 - ratings[ca]
            p_home = 1 / (1 + 10 ** (-d / 400))
            if kind == "moneyline":
                return (p_home if side == "home" else 1 - p_home), \
                    {"detail": "NFL lane Elo ratings (fixture not "
                               "on the saved slate; priced from "
                               "the lane's fitted ratings)"}
            if kind in ("spread", "alt-spread"):
                # R2 (fix-guy): spreads price off a fair spread
                # DERIVED from the same ratings through the map
                # validated against the saved slate's own fairs:
                # the slate's fair_spread_home is an affine
                # function of (ratings diff + 55 HFA) — refit on
                # its 13 games: MAE 0.017 pts in-sample, 0.020
                # leave-one-out (tools/validate_nfl_fair_map
                # logic, numbers in the R2 report). The cover
                # probability then uses the lane's existing
                # margin distribution N(mu, NFL_MARGIN_SD),
                # exactly as the saved-slate path does. Marked
                # FRAGILE: the fair is a derivation validated on
                # n=13, not the slate of record.
                fair = NFL_FAIR_MAP_A + NFL_FAIR_MAP_B * d
                mu = -fair
                s = line if side == "home" else -line
                p_cover_home = 1 - norm_cdf((-s - mu)
                                            / NFL_MARGIN_SD)
                return (p_cover_home if side == "home"
                        else 1 - p_cover_home), \
                    {"detail": f"margin N({mu:+.1f}, "
                               f"{NFL_MARGIN_SD}) from a fair "
                               f"spread derived from the lane's "
                               f"ratings (fair {fair:+.1f}; map "
                               f"validated vs the saved slate's "
                               f"fairs: MAE 0.02 pts, n=13)",
                     "fragile": True,
                     "fragile_note": "fair spread derived from "
                                     "ratings, not the saved "
                                     "slate of record"}
            return None, "no NFL engine for this market"
        if kind == "moneyline":
            return (p_home if side == "home" else 1 - p_home), \
                {"detail": "NFL lane Elo (saved pricing file)"}
        if kind in ("spread", "alt-spread"):
            if g.get("fair_spread_home") is None:
                return None, ("fixture not in the saved NFL "
                              "pricing file — no saved fair spread "
                              "for this game; spread not priced")
            mu = -g["fair_spread_home"]
            s = line if side == "home" else -line
            p_cover_home = 1 - norm_cdf((-s - mu) / NFL_MARGIN_SD)
            return (p_cover_home if side == "home"
                    else 1 - p_cover_home), \
                {"detail": f"margin N({mu:+.1f}, {NFL_MARGIN_SD}) "
                           f"from the lane's saved fair spread"}
        return None, "no NFL engine for this market"
    if sport == "ncaaf":
        if kind in ("totals", "alt-total"):
            # membership truth, shared with the moneyline
            # lane: bare FanDuel school names resolve through
            # FD_CFB_SCHOOL_ALIASES (the totals fit keys carry
            # mascots, so 'Georgia' alone is ambiguous to a
            # bare substring resolver), and a CFL fixture
            # filed under the NCAAF page names the CFL.
            tt = (load_totals_fit("ncaaf") or {}).get("teams") \
                or {}
            fixed = []
            for name in (home, away):
                comp = OTHER_COMPETITION_TEAMS.get(name)
                if comp:
                    return None, (f"competition not in this "
                                  f"app: {comp} ({name}) — "
                                  "FanDuel files it under "
                                  "ncaaf, it is not a ncaaf team")
                fixed.append(_resolve_or_none(
                    tt, name, FD_CFB_SCHOOL_ALIASES) or name)
            return totals_price("ncaaf", fixed[0], fixed[1],
                                side, line)
        try:
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
        except SystemExit as e:
            # membership failure names itself (not found /
            # ambiguous after aliases) — a named UNPRICED, not a
            # checker crash.
            return None, str(e)
        return None, "no NCAAF engine for this market"
    if sport == "nhl":
        if kind in ("totals", "alt-total"):
            return totals_price("nhl", home, away, side, line)
        if kind == "moneyline":
            try:
                w = nhl_win_prob(home, away)
            except SystemExit as e:
                return None, str(e)
            return (w["p_home"] if side == "home" else 1 - w["p_home"]), \
                {"detail": "v4 NHL Elo (sigma-integrated)"}
        return None, "no NHL engine for this market (spread/puck-line " \
                     "not built)"
    if sport == "nba":
        if kind in ("totals", "alt-total"):
            return totals_price("nba", home, away, side, line)
        fit = load_nba()
        if fit is None:
            return None, "NBA fit not run (betmodel5.py fit-nba)"
        pr = nba_probs(fit, home, away)
        if pr is None:
            # R4: name the real competition when FanDuel filed
            # a WNBA / NBL / CBA fixture under the NBA page —
            # the same stamp coverage prints (one helper).
            comp = competition_missing("nba", home, away)
            if comp:
                return None, comp
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
    if sport == "mlb":
        if kind in ("totals", "alt-total"):
            # the MLB game-totals fit has its own exam (it
            # FAILED — totals_price stamps the numbers); it
            # does not ride the moneyline lane's gate.
            return totals_price("mlb", home, away, side, line)
        # R4: gate + membership come from the SHARED helpers
        # (mlb_lane_gate / mlb_membership) that coverage uses —
        # checker and coverage agree by construction.
        fit = load_mlb()
        gate = mlb_lane_gate(fit)
        if gate:
            return None, gate
        if kind == "moneyline":
            p_home, reason = mlb_membership(fit, home, away)
            if p_home is None:
                return None, reason
            bt = fit.get("backtest") or {}
            return (p_home if side == "home" else 1 - p_home), \
                {"detail": f"MLB Elo lane (fit "
                           f"{fit['fitted_at']}; walk-forward "
                           f"Brier {bt['brier']} vs naive "
                           f"{bt['naive_brier']}, n={bt['n']})"}
        return None, ("no MLB engine for this market "
                      "(moneyline only — run-line/totals not "
                      "fitted)")
    if sport == "tennis":
        fit = load_tennis()
        if fit is None:
            return None, "tennis fit not run (tools/fit_tennis.py)"
        if kind != "moneyline":
            return None, ("no tennis engine for this market "
                          "(moneyline only — set/handicap and "
                          "game totals need a set-level "
                          "distribution, not fitted)")
        tour, p_or_reason = tennis_probs(fit, home, away)
        if tour is None:
            return None, p_or_reason
        blk = (fit.get("tours") or {}).get(tour) or {}
        bt = blk.get("backtest") or {}
        if not _exam_passed(bt):
            return None, (f"tennis {tour.upper()} lane "
                          f"FAILED-EXAM — walk-forward Brier "
                          f"{bt.get('brier')} did not beat the "
                          f"naive baseline {bt.get('naive_brier')}; "
                          "lane does not price until a refit "
                          "passes")
        p_home = p_or_reason
        return (p_home if side == "home" else 1 - p_home), \
            {"detail": f"Tennis Elo lane ({tour.upper()}; fit "
                       f"{fit['fitted_at']}; walk-forward Brier "
                       f"{bt['brier']} vs naive "
                       f"{bt['naive_brier']}, n={bt['n']})"}
    if sport == "mma":
        fit = load_mma()
        if fit is None:
            return None, "MMA fit not run (tools/fit_mma.py)"
        bt = fit.get("backtest") or {}
        if not _exam_passed(bt):
            return None, (f"MMA lane FAILED-EXAM — walk-forward "
                          f"Brier {bt.get('brier')} did not beat "
                          f"the naive baseline "
                          f"{bt.get('naive_brier')}, n={bt.get('n')}; "
                          "lane does not price until a refit "
                          "passes")
        if kind != "moneyline":
            return None, ("no MMA engine for this market "
                          "(moneyline only — method-of-victory "
                          "and round markets need finish/round "
                          "distributions, not fitted)")
        p_home, reason = mma_probs(fit, home, away)
        if p_home is None:
            return None, reason
        return (p_home if side == "home" else 1 - p_home), \
            {"detail": f"MMA fighter Elo lane (fit "
                       f"{fit['fitted_at']}; walk-forward Brier "
                       f"{bt['brier']} vs naive "
                       f"{bt['naive_brier']}, n={bt['n']})"}
    if sport == "cricket":
        fit = load_cricket()
        if fit is None:
            return None, "cricket fit not run (tools/fit_cricket.py)"
        if kind != "moneyline":
            return None, ("no cricket engine for this market "
                          "(moneyline only — no ball-by-ball "
                          "totals/scoring distribution fitted)")
        lane, reason = cricket_lane_for(fit, competition,
                                        home, away)
        if lane is None:
            return None, reason
        p, reason = cricket_probs(fit, lane, home, away, side)
        if p is None:
            return None, reason
        blk = (fit.get("lanes") or {}).get(lane) or {}
        bt = blk.get("backtest") or {}
        return p, {"detail": f"cricket {lane} Elo lane (fit "
                             f"{fit['fitted_at']}; walk-forward "
                             f"Brier {bt.get('brier')} vs naive "
                             f"{bt.get('naive_brier')}, "
                             f"n={bt.get('n')})"}
    if sport == "rugby-league":
        fit = load_rugby()
        if fit is None:
            return None, "rugby fit not run (tools/fit_rugby.py)"
        if kind != "moneyline":
            return None, ("no rugby league engine for this "
                          "market (moneyline only)")
        lane = rugby_league_lane(competition, home, away)
        p, reason = rugby_probs(fit, "league", lane, home, away)
        if p is None:
            return None, reason
        return (p if side == "home" else 1 - p), \
            {"detail": f"rugby league {lane} Elo lane"}
    if sport == "rugby-union":
        fit = load_rugby()
        if fit is None:
            return None, "rugby fit not run (tools/fit_rugby.py)"
        npc = ((fit.get("union") or {}).get("npc")) or {}
        ratings = npc.get("ratings") or {}
        if _resolve_or_none(ratings, home) is None \
                or _resolve_or_none(ratings, away) is None:
            return None, ("no rugby union fit for this fixture's "
                          "competition — the fitted union lane is "
                          "the New Zealand NPC only; internationals "
                          "and other club competitions are not "
                          "fitted (closer: a results archive + fit "
                          "for the arriving competition)")
        p, reason = rugby_probs(fit, "union", "npc", home, away)
        if p is None:
            return None, reason
        if kind == "moneyline":
            return (p if side == "home" else 1 - p), \
                {"detail": "rugby union NPC Elo lane"}
        if kind in ("spread", "alt-spread"):
            mm = npc.get("margin_map") or {}
            if not mm.get("sd"):
                return None, "NPC margin map not fitted"
            ch = _resolve_or_none(ratings, home)
            ca = _resolve_or_none(ratings, away)
            mu = mm["a"] + mm["b"] * (ratings[ch] - ratings[ca])
            s = line if side == "home" else -line
            p_cover = 1 - norm_cdf((-s - mu) / mm["sd"])
            return (p_cover if side == "home" else 1 - p_cover), \
                {"detail": f"NPC margin map N({mu:+.1f}, "
                           f"{mm['sd']}) (walk-forward winner "
                           "exam passed; margin map fit on prior "
                           "matches only)",
                 "fragile": True}
        return None, "no rugby union engine for this market"
    if sport == "boxing":
        # R4 named terminal (evidence in XII-SPORT-INVENTORY):
        # BoxRec — the only complete professional results
        # archive — is access-gated (HTTP 403 / bot wall on
        # every route probed 2026-10-24); the public GitHub
        # candidate was verified as a 78-fight popular-match
        # subset, not an archive. No Elo is fitted on toy data.
        return None, ("boxing results source gated — BoxRec "
                      "(the only complete pro archive) refuses "
                      "automated access (HTTP 403, verified "
                      "2026-10-24) and no verified public "
                      "results archive exists; closer: a licensed "
                      "BoxRec export or a verified full pro "
                      "results archive, then a fighter Elo + "
                      "walk-forward exam")
    if sport in UNCHECKED_SPORTS:
        # R2: pulled, inventoried, and stamped — the sport has
        # no checker/fit yet, and the stamp names that at sport
        # level instead of a bare "unknown sport".
        return None, (f"no checker registered for {sport} yet "
                      f"— see coverage queue")
    if sport == "soccer":
        fit, _league_key = soccer_fit_for(home, away)
        if fit is None:
            # Competition-scoped namesakes (see
            # SOCCER_SCOPED_NAME_ALIASES): retry once under the
            # scoped forms the market's own competition names.
            # The plain attempt above is untouched, and the
            # scoped names are committed only when they
            # actually find the fit.
            scoped = _soccer_scoped_names(home, away, competition)
            if scoped is not None:
                sfit, skey = soccer_fit_for(*scoped)
                if sfit is not None:
                    home, away = scoped
                    fit, _league_key = sfit, skey
        if fit is None:
            if load_soccer() is None \
                    and load_soccer_leagues() is None:
                return None, "soccer fit not run (betmodel5.py fit-soccer)"
            return None, soccer_missing_reason(home, away) \
                or f"team not in the soccer fit ({home}/{away})"
        grid = soccer_fixture_grid(fit, home, away)
        if grid is None:
            return None, soccer_missing_reason(home, away) \
                or f"team not in the soccer fit ({home}/{away})"
        M = grid["matrix"]
        det = (f"Poisson grid λ {grid['lambda_home']:.2f} / "
               f"{grid['lambda_away']:.2f} (fit {fit['fitted_at']}; "
               f"walk-forward 3-way Brier {fit['backtest']['brier3']})")
        if kind == "moneyline":
            p = {"home": grid["p_home"], "draw": grid["p_draw"],
                 "away": grid["p_away"]}[side]
            elo = fit["elo"]
            hk = soccer_fit_key(fit, home) or home
            ak = soccer_fit_key(fit, away) or away
            elo_fav = "home" if elo.get(hk, 1500.0) + SOC_HFA \
                >= elo.get(ak, 1500.0) else "away"
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
    if sport == "mlb":
        # Totals only in this tree (Glow lane): Guy's moneyline
        # fit (v5-mlb.json) wires at combine. The game-totals fit
        # was examined walk-forward and FAILED (see
        # data/v5-totals-mlb.json) — totals_price stamps the exam
        # numbers. Team totals PASSED their own exam and price
        # via the team-props checker.
        if kind in ("totals", "alt-total"):
            return totals_price("mlb", home, away, side, line)
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

# ----------------------------------------------------------------
# R5 lanes: segments (half/quarter/period) and soccer title
# outrights. Fit artifacts: data/v5-segments.json (tools/
# fit_segments.py + tools/fit_soccer_halves.py) and data/
# v5-outrights.json (tools/fit_outrights.py). Same house
# contract as every lane: a cell prices only when its exam
# PASSED; FAILED-EXAM cells stamp their numbers.
# R6: soccer 1H exams split PER FORM (result / total price
# independently); NCAAF 1H + NBA/NFL 1Q segment lanes
# examined; outright exams run per league.

SEGMENTS_PATH = os.path.join(DATA, "v5-segments.json")
OUTRIGHTS_PATH = os.path.join(DATA, "v5-outrights.json")

# R6 determination: tennis tournament-winner futures are
# FORM TERMINAL. A knockout tournament price is a function
# of the DRAW — the bracket path (who a player can meet, in
# what order), seeding, and the surface — none of which the
# arriving entries carry (they arrive as a competition name
# plus a runners list with prices: no draw, no bracket
# slots, no surface split). Pricing them off raw Elo title
# shares would be the banned shortcut: the fitted Elo prices
# head-to-head moneylines, a different claim. One stamp,
# shared by the checker and coverage so they cannot drift.
TENNIS_FUTURES_TERMINAL = (
    "tennis outright FORM TERMINAL — a tournament-winner "
    "price is draw-dependent: it is a function of the "
    "bracket path (who a player can meet, in what order), "
    "seeding and the surface, and the arriving entries "
    "carry runners + prices only — no draw structure, no "
    "bracket slots, no surface split — so no honest number "
    "exists to grade; raw Elo title shares are refused "
    "(the Elo fit prices head-to-head moneylines, a "
    "different claim). Closer: a draw-aware tournament "
    "simulator (published draw + surface-specific Elo + "
    "path simulation), examined against completed "
    "tournament winners")


def load_segments():
    # resolved against the CURRENT DATA at call time (the
    # shell repoints DATA into app storage on device)
    return _load_json_cached(os.path.join(DATA, "v5-segments.json"))


def load_outrights():
    return _load_json_cached(os.path.join(DATA, "v5-outrights.json"))


def _segment_kind(segment):
    s = str(segment or "").strip().lower().replace("-", " ")
    if s in ("1st half", "first half", "1h", "half 1"):
        return "1h"
    if s in ("1st period", "first period", "1p", "period 1"):
        return "1p"
    if s in ("2nd period", "second period", "2p", "period 2"):
        return "2p"
    if s in ("3rd period", "third period", "3p", "period 3"):
        return "3p"
    if s in ("1st quarter", "first quarter", "1q", "q1"):
        return "1q"
    if s in ("2nd quarter", "second quarter", "2q", "q2"):
        return "2q"
    return None


def _seg_exam_stamp(lane_name, bt, form_note=""):
    return (f"{lane_name} FAILED-EXAM — walk-forward totals "
            f"MAE {bt.get('mae_total', bt.get('mae_model'))} vs "
            f"naive {bt.get('mae_total_naive', bt.get('mae_naive'))}, "
            f"Brier {bt.get('brier_total', bt.get('brier_model'))} "
            f"vs {bt.get('brier_total_naive', bt.get('brier_naive'))} "
            f"(n={bt.get('n')}); segment-specific team rates did "
            f"not beat the scaled baseline, so the lane stamps "
            f"and does not price{form_note}")


def segment_price(sport, home, away, segment, side="home",
                  line=None, competition=None):
    """(p, info) for a segment (half/period) market, or
    (None, named reason). Prices only from lanes whose
    walk-forward exam passed."""
    kind = _segment_kind(segment)
    if kind is None:
        return None, (f"unrecognized segment form {segment!r} — "
                      "the fitted segment forms are 1st half "
                      "(NBA/NFL/NCAAF/soccer), 1st + 2nd quarter "
                      "(NCAAF; NBA/NFL 1st quarter), and NHL "
                      "periods 1-3 (totals + moneyline forms)")
    seg = load_segments()
    if seg is None:
        return None, ("segment fits not run "
                      "(tools/fit_segments.py)")
    if sport in ("nba", "nfl", "ncaaf"):
        # R6: quarter lanes (nba-1q / nfl-1q) and the NCAAF
        # 1H lane join the R5 half lanes — same machinery,
        # same exam contract: a lane prices only when its
        # own walk-forward exam passed.
        if sport == "ncaaf":
            # R7: the quarter lanes (ncaaf-1q / ncaaf-2q) are
            # examined on the same linescores under the R6
            # share-scaled naive — the R6 "not examined"
            # stamp is retired.
            if kind == "1h":
                lane_key, flabel = "ncaaf-1h", "1H"
            elif kind == "1q":
                lane_key, flabel = "ncaaf-1q", "1Q"
            elif kind == "2q":
                lane_key, flabel = "ncaaf-2q", "2Q"
            else:
                return None, (f"NCAAF {segment} not fitted — "
                              "the examined segment forms for "
                              "this lane are the 1st half and "
                              "the 1st + 2nd quarters (ESPN "
                              "linescores)")
        elif kind == "1h":
            lane_key, flabel = f"{sport}-1h", "1H"
        elif kind == "1q":
            lane_key, flabel = f"{sport}-1q", "1Q"
        else:
            return None, (f"{sport.upper()} {segment} not fitted "
                          "— the examined segment forms for this "
                          "league are the 1st half and the 1st "
                          "quarter (a rescaled half would be a "
                          "guessed number)")
        lane = (seg.get("lanes") or {}).get(lane_key)
        if lane is None:
            return None, f"no {sport} segment fit on file"
        bt = lane.get("backtest") or {}
        if lane.get("status") != "FITTED":
            note = ""
            cov = lane.get("coverage")
            if cov:
                note = (f"; linescore coverage: "
                        f"{cov.get('games_with_linescores')} "
                        f"usable games of {cov.get('events')} "
                        f"events seen")
            return None, _seg_exam_stamp(
                f"{sport.upper()} {flabel} segments", bt,
                form_note=note)
        teams = lane.get("teams") or {}
        if sport == "nfl":
            h = resolve_nfl_team(home, teams)
            a = resolve_nfl_team(away, teams)
            if h is None or a is None:
                return None, (f"team not in the NFL segment fit "
                              f"({home}/{away})")
        elif sport == "ncaaf":
            # lane teams are ESPN abbreviations; the names map
            # (abbrev -> ESPN displayName) plus the FanDuel
            # school-alias table resolves the slate's names.
            names = lane.get("team_names") or {}
            lookup = {ab: ab for ab in teams}
            for ab, dn in names.items():
                if ab in teams:
                    lookup[dn] = ab
            hh = _resolve_or_none(lookup, home,
                                  FD_CFB_SCHOOL_ALIASES)
            aa = _resolve_or_none(lookup, away,
                                  FD_CFB_SCHOOL_ALIASES)
            h = lookup[hh] if hh is not None else None
            a = lookup[aa] if aa is not None else None
            if h is None or a is None:
                return None, (f"team not in the NCAAF segment "
                              f"fit ({home}/{away})")
        else:
            try:
                h = resolve_team(teams, home)
                a = resolve_team(teams, away)
            except SystemExit as e:
                return None, str(e)
        lg = lane["league"]
        lam_h = lg["LH1"] * teams[h]["off"] * teams[a]["def"]
        lam_a = lg["LA1"] * teams[a]["off"] * teams[h]["def"]
        det = (f"{sport.upper()} {flabel} segment distribution "
               f"(fit {seg.get('fitted_at')}; walk-forward "
               f"totals MAE {bt.get('mae_total')} vs naive "
               f"{bt.get('mae_total_naive')}, margin MAE "
               f"{bt.get('mae_margin')} vs "
               f"{bt.get('mae_margin_naive')}, n={bt.get('n')})")
        if side in ("over", "under"):
            if line is None:
                return None, "no line supplied for this segment total"
            mu = lam_h + lam_a
            p_over = 1 - norm_cdf((line - mu) / lane["sigma_total"])
            return (p_over if side == "over" else 1 - p_over), \
                {"detail": det + f" | {flabel} total mu {mu:.1f}"}
        mu_m = lam_h - lam_a
        sd_m = lane["sigma_margin"]
        if line is None:
            p_home = 1 - norm_cdf((0 - mu_m) / sd_m)
            return (p_home if side == "home" else 1 - p_home), \
                {"detail": det + f" | {flabel} moneyline off the "
                                  "margin distribution"}
        s = line if side == "home" else -line
        p_cover = 1 - norm_cdf((-s - mu_m) / sd_m)
        return (p_cover if side == "home" else 1 - p_cover), \
            {"detail": det + f" | {flabel} margin N({mu_m:+.1f}, {sd_m})"}
    if sport == "nhl":
        # R7: every period (1P/2P/3P) examined on TWO forms
        # (tools/fit_segments.py exam_nhl_periods) — totals
        # (Poisson, the R5 protocol per period) and
        # moneyline (period result off the same Poisson
        # grid). Each form prices only on its own
        # walk-forward pass; .5 period spreads read off the
        # moneyline form's grid. The 1P totals form is the
        # shipped R5 exam verbatim.
        if kind not in ("1p", "2p", "3p"):
            return None, ("NHL half/quarter forms do not "
                          "exist — the examined segment forms "
                          "for this league are periods 1-3 "
                          "(totals + moneyline per period)")
        lane = (seg.get("lanes") or {}).get(f"nhl-{kind}")
        if lane is None:
            return None, "no NHL segment fit on file"
        forms = lane.get("forms") or {}
        bt = lane.get("backtest") or {}
        teams = lane.get("teams") or {}
        try:
            h = resolve_team(teams, home)
            a = resolve_team(teams, away)
        except SystemExit as e:
            return None, str(e)
        lg = lane["league"]
        lh_rate = lg.get("LH1P", lg.get("LH"))
        la_rate = lg.get("LA1P", lg.get("LA"))
        lam_h = lh_rate * teams[h]["off"] * teams[a]["def"]
        lam_a = la_rate * teams[a]["off"] * teams[h]["def"]
        plabel = {"1p": "1st", "2p": "2nd", "3p": "3rd"}[kind]
        if side in ("over", "under"):
            ft = forms.get("total") or {}
            if forms and ft.get("status") != "FITTED":
                return None, (
                    f"NHL {plabel}-period totals FAILED-EXAM "
                    f"(R7 per-form bar) — walk-forward MAE "
                    f"{ft.get('mae_model')} vs naive "
                    f"{ft.get('mae_naive')}, Brier "
                    f"{ft.get('brier_model')} vs "
                    f"{ft.get('brier_naive')} (n={ft.get('n')}); "
                    "the moneyline form's numbers ride its own "
                    "stamp")
            if not forms and lane.get("status") != "FITTED":
                return None, _seg_exam_stamp(
                    f"NHL {plabel}-period totals", bt)
            if line is None:
                return None, ("no line supplied for this "
                              "segment total")
            mu = lam_h + lam_a
            p_over, _push = _totals_p_over(mu, None, "poisson",
                                           line)
            return (p_over if side == "over" else 1 - p_over), \
                {"detail": f"NHL {plabel}P totals distribution "
                           f"(Poisson mu {mu:.2f} from period "
                           f"rates; walk-forward MAE "
                           f"{ft.get('mae_model', bt.get('mae_model'))}"
                           f" vs naive "
                           f"{ft.get('mae_naive', bt.get('mae_naive'))}"
                           f", n={ft.get('n', bt.get('n'))})"}
        fm = forms.get("moneyline") or {}
        if forms and fm.get("status") != "FITTED":
            return None, (
                f"NHL {plabel}-period moneyline FAILED-EXAM "
                f"(R7 per-form bar) — walk-forward Brier3 "
                f"{fm.get('brier3_model')} vs naive "
                f"{fm.get('brier3_naive')}, margin MAE "
                f"{fm.get('mae_margin_model')} vs "
                f"{fm.get('mae_margin_naive')} "
                f"(n={fm.get('n')}); period spreads read off "
                "the same grid and stamp with it")
        if not forms:
            return None, ("the NHL segment lane on file "
                          "predates the R7 period-forms exam — "
                          "period moneylines not examined "
                          "(tools/fit_segments.py --lane="
                          "nhlperiods)")
        grid = soccer_grid(lam_h, lam_a)
        det = (f"NHL {plabel}P result off the Poisson period "
               f"grid (rates {lam_h:.2f}/{lam_a:.2f}; "
               f"walk-forward Brier3 {fm.get('brier3_model')} "
               f"vs naive {fm.get('brier3_naive')}, "
               f"n={fm.get('n')})")
        if line is None:
            p = {"home": grid["p_home"], "draw": grid["p_draw"],
                 "away": grid["p_away"]}[side]
            return p, {"detail": det + " | period moneyline"}
        if abs(line % 1) != 0.5:
            return None, ("NHL period spreads price on .5 "
                          "lines only (integer lines carry "
                          "push mass)")
        p_cover = _grid_handicap(grid["matrix"], line)
        return (p_cover if side == "home" else 1 - p_cover), \
            {"detail": det + " | period spread off the grid"}
    if sport == "soccer":
        if kind != "1h":
            return None, ("soccer segment form fitted is the "
                          "1st half only")
        fit, key = soccer_fit_for(home, away)
        if fit is None:
            return None, (f"team not in the soccer fit "
                          f"({home}/{away})")
        blk = (seg.get("soccer-1h") or {}).get(key)
        if blk is None:
            return None, (f"no half-share exam on file for "
                          f"league {key} — the examined sets "
                          "are the football-data.co.uk leagues "
                          "(R6) and the ESPN-sourced leagues "
                          "(R7, ESPN period scores); a league "
                          "in neither set has no 1H exam "
                          "(tools/fit_soccer_halves.py, "
                          "tools/fit_soccer_halves_espn.py)")
        if blk.get("status") == "NO-DATA":
            cov = blk.get("coverage") or {}
            return None, (
                f"{key} 1st-half segments NO-DATA — "
                f"{blk.get('evidence')} (coverage: "
                f"{cov.get('games_ht_covered')} of "
                f"{cov.get('games_completed')} completed "
                "games HT-covered); no half-share exists "
                "to price from, and none is guessed")
        bt = blk.get("backtest") or {}
        # R6 per-form bar (pre-stated in the R6 assignment):
        # each form prices on its OWN walk-forward pass —
        # result iff Brier3 beat the fixed-share naive, total
        # iff its Brier beat the 0.44-share naive. A failing
        # form stamps quoting BOTH forms' numbers.
        forms = blk.get("forms") or {}
        need = "total" if side in ("over", "under") else "result"
        fneed = forms.get(need) or {}
        if forms:
            form_ok = fneed.get("status") == "FITTED"
        else:  # pre-R6 artifact: the joint status governs
            form_ok = blk.get("status") == "FITTED"
        if not form_ok:
            fres = forms.get("result") or {}
            ftot = forms.get("total") or {}
            return None, (
                f"{key} 1st-half {need} FAILED-EXAM "
                f"(per-form bar, R6 protocol) — 1H total "
                f"over-1.5 Brier "
                f"{ftot.get('brier_over15', bt.get('brier_over15'))} "
                f"vs naive "
                f"{ftot.get('brier_over15_naive', bt.get('brier_over15_naive'))} "
                f"[{ftot.get('status', blk.get('status'))}], "
                f"1H result Brier3 "
                f"{fres.get('brier3_1h', bt.get('brier3_1h'))} vs "
                f"naive "
                f"{fres.get('brier3_1h_naive', bt.get('brier3_1h_naive'))} "
                f"[{fres.get('status', blk.get('status'))}] "
                f"(n={bt.get('n')}); each form prices only on "
                "its own walk-forward pass")
        grid = soccer_fixture_grid(fit, home, away)
        if grid is None:
            return None, (f"team not in the soccer fit "
                          f"({home}/{away})")
        g1 = soccer_grid(grid["lambda_home"] * blk["share_h"],
                         grid["lambda_away"] * blk["share_a"])
        M = g1["matrix"]
        det = (f"{key} 1H grid (half-shares "
               f"{blk['share_h']}/{blk['share_a']} fitted on "
               f"{blk.get('ht_source', 'HTHG/HTAG')}; "
               f"walk-forward over-1.5 Brier "
               f"{bt.get('brier_over15')} vs naive "
               f"{bt.get('brier_over15_naive')}, 1H Brier3 "
               f"{bt.get('brier3_1h')} vs "
               f"{bt.get('brier3_1h_naive')}, n={bt.get('n')})")
        if side in ("over", "under"):
            if line is None:
                return None, "no line supplied for this segment total"
            p_over = _grid_over(M, line)
            return (p_over if side == "over" else 1 - p_over), \
                {"detail": det + " | 1H total off the grid"}
        if line is None:
            p = {"home": g1["p_home"], "draw": g1["p_draw"],
                 "away": g1["p_away"]}[side]
            return p, {"detail": det + " | 1H result off the grid"}
        if abs(line % 1) != 0.5:
            return None, ("soccer handicaps price on .5 lines "
                          "only (integer lines carry push mass)")
        p_home_cover = _grid_handicap(M, line)
        return (p_home_cover if side == "home"
                else 1 - p_home_cover), \
            {"detail": det + " | 1H handicap off the grid"}
    return None, (f"no segment distributions fitted for "
                  f"{sport} — the examined forms are NBA/NFL "
                  "1st half + 1st quarter, NCAAF 1st half + "
                  "1st/2nd quarters, NHL periods 1-3 (totals + "
                  "moneyline), soccer 1st half")


EPL_NAME_TO_CODE = {
    "Arsenal": "ARS", "Aston Villa": "AVL", "Brighton": "BHA",
    "Brighton & Hove Albion": "BHA", "Bournemouth": "BOU",
    "Brentford": "BRE", "Burnley": "BUR", "Chelsea": "CHE",
    "Crystal Palace": "CRY", "Everton": "EVE", "Fulham": "FUL",
    "Leeds": "LEE", "Leeds United": "LEE", "Liverpool": "LIV",
    "Manchester United": "MAN", "Man Utd": "MAN",
    "Manchester City": "MNC", "Man City": "MNC",
    "Newcastle": "NEW", "Newcastle United": "NEW",
    "Nottingham Forest": "NFO", "Nottm Forest": "NFO",
    "Sunderland": "SUN", "Tottenham": "TOT", "Spurs": "TOT",
    "Tottenham Hotspur": "TOT", "West Ham": "WHU",
    "West Ham United": "WHU", "Wolves": "WOL",
    "Wolverhampton": "WOL", "Wolverhampton Wanderers": "WOL",
    "Coventry": "COV", "Coventry City": "COV",
    "Hull": "HUL", "Hull City": "HUL", "Ipswich": "IPS",
    "Ipswich Town": "IPS"}


def _outright_league_key(mkt):
    blob = " ".join(str(mkt.get(k) or "") for k in
                    ("competition", "home", "away")).lower()
    # R7: second tiers are examined too — their checks run
    # BEFORE the top-flight ones (a "La Liga 2" blob also
    # contains "la liga"). USL Championship is a different
    # competition family and stays uncovered (None).
    if "usl" in blob:
        return None
    if "championship" in blob:
        return "championship"
    if "la liga 2" in blob or "segunda" in blob:
        return "la-liga-2"
    if "serie b" in blob and "brazil" not in blob \
            and "brasil" not in blob:
        return "serie-b"
    if "ligue 2" in blob:
        return "ligue-2"
    if "bundesliga" in blob and ("2." in blob or " 2" in blob):
        return "bundesliga-2"
    if "premier league" in blob and "scottish" not in blob:
        return "epl"
    if "la liga" in blob:
        return "la-liga"
    if "serie a" in blob and "brazil" not in blob \
            and "brasil" not in blob:
        return "serie-a"
    if "ligue 1" in blob:
        return "ligue-1"
    if "bundesliga" in blob and "2." not in blob:
        return "bundesliga"
    if "major league soccer" in blob or " mls" in blob \
            or blob.startswith("mls"):
        return "mls"
    return None


def outright_price(mkt):
    """(p, info) for a soccer title outright, or (None, named
    reason). R6: the Monte Carlo protocol runs PER LEAGUE
    (EPL pilot R5; La Liga / Bundesliga / Serie A / Ligue 1
    / MLS in R6) — a league's outrights price only when
    THAT league's exam passed and its live shares are on
    file in data/v5-outrights.json."""
    doc = load_outrights()
    if doc is None:
        return None, ("soccer outright exams not run "
                      "(tools/fit_outrights.py)")
    key = _outright_league_key(mkt)
    if key is None:
        return None, ("this outright is not a league title "
                      "the outright protocol covers — the "
                      "examined forms are the league "
                      "championships of the EPL, La Liga, "
                      "Bundesliga, Serie A, Ligue 1 and MLS "
                      "plus the second tiers (Championship, "
                      "Serie B, La Liga 2, Bundesliga 2, "
                      "Ligue 2) (per-league Monte Carlo exams "
                      "in v5-outrights.json); cup outrights "
                      "and other leagues have no simulation "
                      "artifact, and other outright forms "
                      "(relegation, top-4, golden boot) stay "
                      "named, unexamined")
    lg = (doc.get("leagues") or {}).get(key)
    exam = (lg or {}).get("exam")
    if exam is None and key == "epl":
        exam = doc.get("backtest") or {}
    if not exam:
        return None, (f"no outright exam on file for {key} "
                      "— closer: run the protocol for this "
                      "league (tools/fit_outrights.py)")
    n_seasons = len(exam.get("seasons") or []) or 3
    if exam.get("verdict") != "PASS":
        return None, (f"{key} title outright FAILED-EXAM — "
                      f"this league's Monte Carlo exam lost "
                      f"to the standings-share naive: mean "
                      f"Brier {exam.get('mean_brier_model')} "
                      f"vs naive {exam.get('mean_brier_naive')}, "
                      f"mean log-loss "
                      f"{exam.get('mean_logloss_model')} vs "
                      f"{exam.get('mean_logloss_naive')} "
                      f"({exam.get('seasons_won')}/{n_seasons} "
                      "seasons won); the league stamps and "
                      "does not price")
    shares = (lg or {}).get("shares") or {}
    if not shares:
        err = (lg or {}).get("live_error")
        return None, (f"outright exam PASSED for {key} "
                      f"(mean Brier "
                      f"{exam.get('mean_brier_model')} vs naive "
                      f"{exam.get('mean_brier_naive')}, mean "
                      f"log-loss {exam.get('mean_logloss_model')} "
                      f"vs {exam.get('mean_logloss_naive')}) but "
                      "no live shares are on file for it"
                      + (f" — {err}" if err else
                         " — closer: generate the league's "
                         "live artifact (tools/fit_outrights.py)"))
    sel = mkt.get("runner") or mkt.get("selection")
    if not sel:
        top = sorted(shares.items(), key=lambda kv: -kv[1])[:3]
        tops = ", ".join(f"{t} {p * 100:.1f}%"
                         for t, p in top if p > 0)
        return None, (f"outright simulation is on file for "
                      f"{key} ({lg.get('played')} played, "
                      f"{lg.get('remaining')} remaining, "
                      f"{lg.get('sims')} sims; leaders: "
                      f"{tops}) but this entry arrives "
                      "collapsed — no runner selection on it, "
                      "so there is no single probability to "
                      "grade; it prices per runner when a "
                      "selection rides along")
    cand = None
    if key == "epl":
        cand = EPL_NAME_TO_CODE.get(str(sel).strip())
    if cand not in shares:
        names = lg.get("names") or {}
        lookup = {ab: ab for ab in shares}
        for ab, nm in names.items():
            if ab in shares:
                lookup[nm] = ab
        hit = _resolve_or_none(lookup, str(sel))
        if hit is not None:
            cand = lookup[hit]
    if cand not in shares:
        try:
            cand = resolve_team({t: 1 for t in shares}, str(sel))
        except SystemExit:
            return None, (f"runner {sel!r} is not in the {key} "
                          "outright simulation (a team outside "
                          "the league, or a name the resolver "
                          "cannot place)")
    p = shares[cand]
    return p, {"detail": f"{key} title outright — Monte Carlo "
                         f"season simulation ({lg.get('sims')} "
                         f"sims from the current table: "
                         f"{lg.get('played')} played, "
                         f"{lg.get('remaining')} remaining; "
                         f"league exam PASS: mean Brier "
                         f"{exam.get('mean_brier_model')} vs naive "
                         f"{exam.get('mean_brier_naive')}, mean "
                         f"log-loss {exam.get('mean_logloss_model')} "
                         f"vs {exam.get('mean_logloss_naive')}, "
                         f"{exam.get('seasons_won')}/{n_seasons} "
                         "seasons)"}


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
            "detail": detail,
            # v5.2: stamped centrally by run_slate on priced
            # verdicts — the displayed calibration tag and the
            # bet's stance. None on UNPRICED / ungraded verdicts.
            "cal_tag": None, "stance": None}


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
                           mkt.get("side", "home"), mkt.get("line"),
                           competition=mkt.get("competition"),
                           segment=mkt.get("segment"))
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
    if mkt.get("sport") == "soccer" \
            or mkt.get("sport") in TOTALS_LANES:
        return _straight(mkt, ctx, "totals")
    if mkt.get("sport") in ("nba", "mlb"):
        # R4 competition truth: a WNBA/NBL/NPB total filed
        # under the NBA/MLB page names its real competition
        # FIRST — it is not an NBA totals gap.
        comp = competition_missing(mkt.get("sport"),
                                   mkt.get("home"), mkt.get("away"))
        if comp:
            return _verdict(mkt, "UNPRICED", note=comp)
    if mkt.get("sport") in TOTALS_LANES:
        # R5: straight totals price through totals_price()
        # (the lane's fitted distribution; FAILED-EXAM lanes
        # stamp their exam numbers through the same call).
        return _straight(mkt, ctx, "totals")
    return _verdict(mkt, "UNPRICED",
                    note="totals engine not built — no pace/scoring "
                         "companion distribution with a scored "
                         "record; stamped, not guessed")


@register("alt-total")
def _chk_alt_total(mkt, ctx):
    if mkt.get("sport") == "soccer" \
            or mkt.get("sport") in TOTALS_LANES:
        return _straight(mkt, ctx, "alt-total")
    if mkt.get("sport") in ("nba", "mlb"):
        # R4 competition truth, same as straight totals.
        comp = competition_missing(mkt.get("sport"),
                                   mkt.get("home"), mkt.get("away"))
        if comp:
            return _verdict(mkt, "UNPRICED", note=comp)
    if mkt.get("sport") in TOTALS_LANES:
        # R5: an alt total is another point on the SAME
        # distribution the straight checker prices — routed
        # through totals_price() via engine_price, so at the
        # main line the alt price equals the straight price
        # exactly (parity battery in the R5 report).
        return _straight(mkt, ctx, "alt-total")
    return _verdict(mkt, "UNPRICED",
                    note="alt totals follow the totals engine, which "
                         "is not built (see totals)")


@register("player-props")
def _chk_player_props(mkt, ctx):
    if mkt.get("sport") in ("nba", "mlb"):
        # R4 competition truth: a WNBA player prop filed under
        # the NBA page names the WNBA — it must never fall
        # through to NBA gamelogs (Glow's flag).
        comp = competition_missing(mkt.get("sport"),
                                   mkt.get("home"), mkt.get("away"))
        if comp:
            return _verdict(mkt, "UNPRICED",
                            note=comp + "; player props for this "
                                        "competition are not "
                                        "fitted in this round")
    try:
        band = prop_band(mkt["player"], mkt["stat"],
                            float(mkt["line"]), mkt.get("side", "over"))
    except (KeyError, SystemExit, TypeError, ValueError) as e:
        return _verdict(mkt, "UNPRICED",
                        note=f"no game-log band for this player/stat "
                             f"({type(e).__name__}) — player not in "
                             f"the fitted gamelog cache "
                             f"(data/cache/athlete_index.json) or "
                             f"stat not in their log; close by: "
                             f"tools/fetch_gamelogs.py")
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
    if mkt.get("sport") in ("nba", "mlb"):
        # R4 competition truth: an NBL team total filed under
        # the NBA page names the NBL (Glow's flag).
        comp = competition_missing(mkt.get("sport"),
                                   mkt.get("home"), mkt.get("away"))
        if comp:
            return _verdict(mkt, "UNPRICED", note=comp)
    if mkt.get("sport") == "soccer":
        fit, _league_key = soccer_fit_for(mkt["home"], mkt["away"])
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
    if mkt.get("sport") in TEAMTOTALS_LANES:
        p, info = team_totals_price(
            mkt["sport"], mkt["home"], mkt["away"],
            team_side=mkt.get("team", "home"),
            line=float(mkt["line"]),
            side=mkt.get("side", "over"))
        if p is None:
            return _verdict(mkt, "UNPRICED", note=info)
        grade, _, verdict, verdict_reason, _ = _grade_and_gate(
            mkt, p, p, p, ctx)
        note = info["detail"]
        if grade is not None:
            note += f" | grade {grade}"
        return _verdict(mkt, "PRICED", p=p, grade=grade,
                        verdict=verdict,
                        verdict_reason=verdict_reason, note=note)
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
                         "reconstruction scoped, not built; never a "
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
    # R5: segment lanes are fitted and examined (NBA/NFL 1H,
    # NHL 1P, soccer 1H per league). Every one of the US
    # lanes FAILED its pre-stated exam in R5, so in practice
    # this routes to a FAILED-EXAM stamp with the numbers;
    # the soccer leagues that passed price off the half-share
    # grid. Either way the answer comes from the exam, never
    # from a rescaled full-game guess.
    return _straight(mkt, ctx, "segment")


@register("futures")
def _chk_futures(mkt, ctx):
    sport = mkt.get("sport")
    form = str(mkt.get("away") or "")
    if sport == "motorsport":
        # R4: motorsport arrives ONLY in field forms (the
        # parser collapses them to futures entries with the
        # market name in the away slot). Each form names its
        # own terminal — a race winner is not a fastest lap.
        fit = load_f1()
        bt = (fit or {}).get("backtest") or {}
        if "Grand Prix" in str(mkt.get("home") or ""):
            if form == "Race Winner":
                a1 = (fit or {}).get("attempt_1") or {}
                return _verdict(
                    mkt, "UNPRICED",
                    note="F1 lane FAILED-EXAM (TERMINAL — both "
                         "attempts on file, Ergast/Jolpica "
                         "2015-2025, walk-forward vs the "
                         "win-share naive): attempt 1, driver "
                         f"Elo — log-loss {a1.get('log_loss')} "
                         f"vs naive {a1.get('naive_log_loss')}, "
                         f"Brier {a1.get('brier')} vs "
                         f"{a1.get('naive_brier')}; attempt 2 "
                         "(R5, the named closer: driver Elo "
                         "from teammate head-to-heads + shrunk "
                         "constructor effect) — log-loss "
                         f"{bt.get('log_loss')} vs naive "
                         f"{bt.get('naive_log_loss')}, Brier "
                         f"{bt.get('brier')} vs "
                         f"{bt.get('naive_brier')}, "
                         f"n={bt.get('n')}; the constructor "
                         "effect closed most of the gap and "
                         "still lost both metrics, so the lane "
                         "is closed — nothing in this sport "
                         "prices")
            return _verdict(
                mkt, "UNPRICED",
                note=f"F1 {form} is a different form from race "
                     "winner (pace/podium/manufacturer markets "
                     "need their own distributions); the race-"
                     "winner lane itself is FAILED-EXAM "
                     "TERMINAL after two attempts (driver Elo "
                     "log-loss 2.5036, driver+constructor "
                     f"{bt.get('log_loss')}, naive "
                     f"{bt.get('naive_log_loss')}) — nothing "
                     "in this sport prices")
        return _verdict(
            mkt, "UNPRICED",
            note="NASCAR source terminal — real Cup results "
                 "exist only as R data files (nascaR.data "
                 "publishes .rda, no CSV route verified "
                 "2026-10-24) and this form "
                 f"({form}) needs a field model, not a fixture "
                 "model; closer: an R/pyreadr conversion of "
                 "nascaR.data or a verified CSV results mirror, "
                 "then driver ratings + a favorite-baseline exam")
    if sport == "golf":
        return _verdict(
            mkt, "UNPRICED",
            note="golf source terminal — group-winner and "
                 "top-region forms need full-field historical "
                 "finishes to examine honestly; the complete "
                 "results source (DataGolf) is key-gated (HTTP "
                 "403 'invalid api key', verified 2026-10-24) "
                 "and no verified public full-field archive was "
                 "found, so no exam exists for the group form "
                 "and nothing prices; closer: a DataGolf API key "
                 "or a verified full-field results archive, "
                 "then player ratings + a walk-forward group "
                 "exam vs equal share")
    if sport == "lacrosse":
        return _verdict(
            mkt, "UNPRICED",
            note="lacrosse outright terminal — the arriving "
                 "markets are season outrights (NLL Cup, NCAA "
                 "championship, 12-77 runners); NLL results "
                 "exist (ESPN league route verified) but a team "
                 "Elo does not price a championship outright "
                 "without a season simulator, and the NCAA "
                 "field has no fitted source; closer: an NLL "
                 "season-simulator outright model, examined "
                 "against historical Cup outcomes")
    if sport == "tennis":
        # R6: FORM TERMINAL (see TENNIS_FUTURES_TERMINAL) —
        # draw-dependent knockout prices, no draw structure
        # on the arriving entries.
        return _verdict(mkt, "UNPRICED",
                        note=TENNIS_FUTURES_TERMINAL)
    if sport == "soccer":
        # Title outrights by Monte Carlo season simulation
        # — R5 EPL pilot, R6 per-league exams (La Liga /
        # Bundesliga / Serie A / Ligue 1 / MLS): a runner
        # selection prices at its simulated title share only
        # when THAT league's exam passed; collapsed entries,
        # failed leagues and uncovered competitions stamp
        # with the reason.
        p, info = outright_price(mkt)
        if p is None:
            return _verdict(mkt, "UNPRICED", note=str(info))
        detail = info.get("detail", "") if isinstance(info, dict) \
            else ""
        grade = verdict = verdict_reason = None
        if mkt.get("price") is not None:
            grade, _tags, verdict, verdict_reason, _fails = \
                _grade_and_gate(mkt, p, p, p, ctx)
        return _verdict(mkt, "PRICED", p=p, grade=grade,
                        verdict=verdict,
                        verdict_reason=verdict_reason,
                        note=detail, detail=detail)
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
    note = ("joint P = product of leg probabilities (assumes the "
            "legs are independent — same-game legs rarely are)")
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
    fit, _league_key = soccer_fit_for(mkt["home"], mkt["away"])
    if fit is None:
        if load_soccer() is None and load_soccer_leagues() is None:
            return None, "soccer fit not run (betmodel5.py fit-soccer)"
        return None, soccer_missing_reason(
            mkt["home"], mkt["away"]) or "team not in the soccer fit"
    grid = soccer_fixture_grid(fit, mkt["home"], mkt["away"])
    if grid is None:
        return None, soccer_missing_reason(
            mkt["home"], mkt["away"]) or "team not in the soccer fit"
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
    combo = str(mkt.get("side", "1X")).strip().upper().replace(" ", "")
    combos = {"1X": grid["p_home"] + grid["p_draw"],
              "12": grid["p_home"] + grid["p_away"],
              "X2": grid["p_draw"] + grid["p_away"]}
    if combo not in combos:
        return _verdict(mkt, "UNPRICED",
                        note=f"double-chance side {mkt.get('side')!r} "
                             f"is not a 1X / 12 / X2 token — the "
                             f"board's spelling is unparsed, named "
                             f"rather than guessed")
    p = combos[combo]
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
    card = load_scorecard()
    for mkt in slate.get("markets", []):
        v = run_checker(mkt, ctx)
        # v5.2 central stamping: every PRICED verdict carries its
        # lane's calibration tag and its own stance, computed here
        # so every checker (and both shells) shows the same values.
        if v["state"] == "PRICED" and v["p"] is not None:
            lane = _lane_for(mkt)
            v["cal_tag"] = calibration_tag(lane, card)
            if mkt.get("price") is not None:
                v["stance"] = bet_stance(
                    v["p"],
                    (v["p"] - implied_prob(mkt["price"])) * 100,
                    mkt["price"])
        verdicts.append(v)
        line = f"[{v['state']}] {v['market']} — {v['desc']}"
        if v["p"] is not None:
            line += f" | P {v['p'] * 100:.1f}%"
        if v["grade"]:
            line += f" | Grade {v['grade']}"
        if v.get("stance"):
            line += f" | Stance {v['stance']}"
        if v.get("cal_tag"):
            line += f" | {v['cal_tag']}"
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
        "Accept": "application/json",
        "Accept-Encoding": "gzip"})
    # A fresh opener per call keeps fd_get/fetch_menu_json safe to
    # call from the pull's worker threads: no request state is
    # shared between calls. Gzip is decoded only when the server
    # explicitly labels the response with that content encoding.
    opener = urllib.request.build_opener()
    with opener.open(req, timeout=25) as resp:
        raw = resp.read()
        encoding = (resp.headers.get("Content-Encoding")
                    or "").lower()
        if "gzip" in (part.strip() for part in encoding.split(",")):
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8"))


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


def fd_event_menu(event_id):
    """One game's FULL menu across its tabs (the event-page
    route cmd_menu --event proved): base event page -> layout
    tabs -> one event-page fetch per tab, collecting every
    market name on every tab. Returns a compact inventory —
    {event_id, name, tabs: {tab: [distinct market names]},
    n_market_instances, n_distinct} — not market bodies: the
    pull keeps the menu CURRENT and inventoried; pricing stays
    with the sport-page slate and its checkers. Raises on
    failure; the caller stamps that event UNVERIFIED."""
    page = fd_get(FANDUEL_EVENT_ENDPOINT, {
        "eventId": event_id,
        "useCombinedTouchdownsVirtualMarket": "true",
        "useQuickBets": "true"})
    tabs = (page.get("layout") or {}).get("tabs") or {}
    ev_name = next(iter(((page.get("attachments") or {})
                         .get("events") or {}).values()),
                   {}).get("name", str(event_id))
    out_tabs = {}
    total = 0
    distinct = set()
    for tab_id in tabs:
        tp = fd_get(FANDUEL_EVENT_ENDPOINT, {
            "eventId": event_id,
            "useCombinedTouchdownsVirtualMarket": "true",
            "useQuickBets": "true", "tab": tab_id})
        names = sorted({mk.get("marketName") for mk in
                        ((tp.get("attachments") or {})
                         .get("markets") or {}).values()
                        if mk.get("marketName")})
        out_tabs[str(tab_id)] = names
        total += sum(1 for _ in ((tp.get("attachments") or {})
                                 .get("markets") or {}).values())
        distinct.update(names)
    return {"event_id": event_id, "name": ev_name,
            "tabs": out_tabs, "tab_count": len(out_tabs),
            "n_market_instances": total,
            "n_distinct": len(distinct)}


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
    competitions = att.get("competitions") or {}
    inventory = {}
    slate = []
    games = {}
    routed = {}
    for ev in events.values():
        name = ev.get("name", "")
        if " @ " in name:
            away, home = (s.strip() for s in name.split(" @ ", 1))
            games[ev["eventId"]] = (away, home, ev)
        elif " v " in name:
            # " v " fixtures: soccer names matches home-first,
            # world style ("Inter v Fiorentina"); the R2 sports
            # (tennis, MMA, boxing, cricket, both rugbys,
            # snooker, table tennis) name head-to-heads the
            # same way ("Kayla Harrison v Amanda Nunes"). The
            # first-named side takes the home slot; runner
            # prices attach by name, so the convention cannot
            # misprice a side. games[] stores (away, home) like
            # every other sport.
            home, away = (s.strip() for s in name.split(" v ", 1))
            games[ev["eventId"]] = (away, home, ev)
    for mk in markets.values():
        inventory[mk.get("marketName")] = \
            inventory.get(mk.get("marketName"), 0) + 1
        ev = events.get(str(mk.get("eventId"))) or \
            events.get(mk.get("eventId"))
        if ev is None:
            continue
        if ev["eventId"] not in games:
            if sport in UNCHECKED_SPORTS or sport in (
                    "cricket", "rugby-union", "rugby-league",
                    "motorsport"):
                # R2: an outright/futures market on a pulled but
                # unchecked sport (a golf tournament's Group A /
                # Winner markets, a darts World Championship
                # outright, a lacrosse championship winner) —
                # it ARRIVES as a futures slate entry and stamps
                # UNPRICED with the futures reason, instead of
                # being silently dropped at the parser.
                # R4: the same arrival for the newly fitted
                # sports' outrights (Six Nations, World Cups),
                # and the entry now carries the competition
                # FanDuel names + the runner list (names and
                # prices) — a field market's runners ARE its
                # content, and field-form checkers read them.
                comp = competitions.get(
                    str(ev.get("competitionId"))) or {}
                slate.append({
                    "sport": sport,
                    "home": (ev.get("name") or "").strip(),
                    "away": mk.get("marketName") or "Outright",
                    "fd_event_id": ev["eventId"],
                    "fd_market_id": mk.get("marketId"),
                    "market_time": mk.get("marketTime"),
                    "competition": comp.get("name"),
                    "fd_competition_id": ev.get("competitionId"),
                    "market": "futures", "side": "home",
                    "price": None,
                    "runners_n": len(mk.get("runners") or []),
                    "runners": [
                        {"name": r.get("runnerName"),
                         "price": _fd_runner_price(r)}
                        for r in (mk.get("runners") or [])
                        if r.get("runnerName")]})
                routed[sport] = routed.get(sport, 0) + 1
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
        comp = competitions.get(str(ev.get("competitionId"))) or {}
        base = {"sport": routed_sport, "home": home, "away": away,
                "fd_event_id": ev["eventId"],
                "fd_market_id": mk.get("marketId"),
                "market_time": mk.get("marketTime"),
                # R4: the competition FanDuel itself names for
                # this event (its attachments carry it) — lanes
                # whose ratings differ per competition/format
                # (cricket above all) select by it, and stamps
                # quote it, instead of inferring from team names.
                "competition": comp.get("name"),
                "fd_competition_id": ev.get("competitionId")}
        mname = mk.get("marketName")
        if sport == "soccer" and mname == "Moneyline (3-way)":
            # FanDuel's soccer 1X2 market name; the engine's
            # moneyline route (with its draw leg) prices it
            mname = "Moneyline"
        if mname == "Moneyline":
            for side, team in (("home", raw_home),
                               ("away", raw_away)):
                r = by_name.get(team)
                price = _fd_runner_price(r) if r else None
                if price is not None:
                    slate.append({**base, "market": "moneyline",
                                  "side": side, "price": price})
            if sport == "soccer":
                # the 1X2 market's third leg (v5.2): FanDuel lists
                # the Draw as its own runner. The soccer engine
                # prices side="draw" off the Poisson grid; leaving
                # the leg out misdescribed a three-way market as a
                # two-way one.
                r = by_name.get("Draw")
                price = _fd_runner_price(r) if r else None
                if price is not None:
                    slate.append({**base, "market": "moneyline",
                                  "side": "draw", "price": price})
            if sport in ("cricket", "rugby-union"):
                # R4: the same third leg where the sport has one
                # (Test cricket posts a Draw runner; the test
                # lane prices it from its fitted draw rate).
                r = by_name.get("Draw")
                price = _fd_runner_price(r) if r else None
                if price is not None:
                    slate.append({**base, "market": "moneyline",
                                  "side": "draw", "price": price})
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




# ================================================================ v5.3 organs
# Two display-side organs (Pilot order 2026-10-22, F5b). Neither
# feeds a grade, a verdict, or a calibration tag in v5.3 — the
# CLV ledger MEASURES, the Kelly engine ADVISES; the ladder
# above is untouched by both. Each carries regression fixtures
# in ADDENDUM v5.3, including perturbed-fixture checks.

# ----------------------------------------------------------------
# Organ 6 — the CLV & drift ledger (measurement)
#
# Closing line value is the market's own grade of a price: a bet
# taken at a price whose implied probability is BELOW the final
# pre-start price's implied probability beat the close. Sign
# convention, stated once and used everywhere below:
#   clv_pts = implied(close) - implied(bet), in points.
# Positive = beat the close. Drift is the same differencing
# applied to a market across timestamped menu pulls:
#   drift_pts = implied(last snapshot) - implied(first snapshot).
# The ledger invents nothing: a market seen in one pull has no
# drift ("insufficient snapshots"), a bet with no closing
# snapshot has no CLV ("no closing snapshot"), and an input that
# is not a timestamped menu pull is classified, not forced.

def clv_market_key(mkt):
    """A market's identity across pulls: the FanDuel ids when
    the pull carries them, the matchup + market + side + line
    otherwise. The line is part of the identity — a spread that
    moved from -3.5 to -4 is a different bet, and its drift is
    reported as a line move on the sibling key, never silently
    merged."""
    ident = mkt.get("fd_market_id") or mkt.get("market")
    return (mkt.get("sport"), mkt.get("fd_event_id"),
            ident, mkt.get("side"), mkt.get("line"),
            mkt.get("player"), mkt.get("stat"))


def _pull_markets(pull):
    """(pulled_at, markets) for a menu rec; (None, None) for
    anything that is not a timestamped menu pull."""
    if not isinstance(pull, dict):
        return None, None
    markets = pull.get("markets")
    if not isinstance(markets, list) or not pull.get("pulled_at"):
        return None, None
    return pull["pulled_at"], markets


def drift_ledger(pulls):
    """Difference every market across the given pulls (menu
    recs, any order — snapshots sort by pulled_at). Returns
    {state, snapshots, markets_seen, markets_tracked, rows,
    skipped}: each row carries the first/last price, the drift
    in odds points and in implied-probability points, and its
    own state — 'tracked' (>= 2 snapshots) or 'insufficient
    snapshots' (seen once: the honest answer, printed)."""
    snaps = []
    skipped = 0
    for pull in pulls or []:
        at, markets = _pull_markets(pull)
        if markets is None:
            skipped += 1
            continue
        snaps.append((str(at), markets))
    snaps.sort(key=lambda t: t[0])
    seen = {}
    for at, markets in snaps:
        for mkt in markets:
            if mkt.get("price") is None:
                continue
            seen.setdefault(clv_market_key(mkt), []).append(
                (at, int(mkt["price"])))
    rows = []
    for key, hist in sorted(seen.items(), key=lambda kv: str(kv[0])):
        first_at, first_price = hist[0]
        last_at, last_price = hist[-1]
        tracked = len(hist) >= 2
        rows.append({
            "key": key, "snapshots": len(hist),
            "first_at": first_at, "last_at": last_at,
            "first_price": first_price, "last_price": last_price,
            "drift_odds_pts": last_price - first_price,
            "drift_prob_pts": (implied_prob(last_price)
                               - implied_prob(first_price)) * 100,
            "state": "tracked" if tracked
                     else "insufficient snapshots"})
    tracked_rows = [r for r in rows if r["state"] == "tracked"]
    return {"state": "ok" if snaps else "no menu pulls",
            "snapshots": len(snaps), "skipped_inputs": skipped,
            "markets_seen": len(rows),
            "markets_tracked": len(tracked_rows),
            "median_abs_drift_pts": (
                statistics.median(abs(r["drift_prob_pts"])
                                  for r in tracked_rows)
                if tracked_rows else None),
            "rows": rows}


def clv_points(bet_price, close_price):
    """One settled bet's CLV in implied-probability points
    (module sign convention above). None when either price is
    missing — an unclosed bet has no CLV, never an assumed one."""
    if bet_price is None or close_price is None:
        return None
    return (implied_prob(int(close_price))
            - implied_prob(int(bet_price))) * 100


def lane_clv_ledger(bets):
    """Per-lane CLV aggregates over settled bets
    [{lane, price, close_price}]. A bet without a closing
    snapshot is counted as unclosed and excluded from the
    mean — the lane's state says how much of it is real:
    'measured' (>= 1 closed bet) or 'insufficient settled
    bets' (none closed: the honest answer, printed)."""
    lanes = {}
    for bet in bets or []:
        lane = bet.get("lane") or "?"
        row = lanes.setdefault(lane, {"lane": lane, "closed": 0,
                                      "unclosed": 0, "clv_sum": 0.0,
                                      "beats": 0})
        pts = clv_points(bet.get("price"), bet.get("close_price"))
        if pts is None:
            row["unclosed"] += 1
        else:
            row["closed"] += 1
            row["clv_sum"] += pts
            if pts > 0:
                row["beats"] += 1
    out = []
    for lane in sorted(lanes):
        row = lanes[lane]
        n = row["closed"]
        out.append({
            "lane": lane, "closed": n, "unclosed": row["unclosed"],
            "mean_clv_pts": (row["clv_sum"] / n) if n else None,
            "beat_rate": (row["beats"] / n) if n else None,
            "state": "measured" if n else
                     "insufficient settled bets"})
    return out


def clv_report(pulls, bets=None):
    """The ledger as the Lab prints it: drift across the pulls
    on file + per-lane CLV over the settled bets on file. Both
    halves carry their own honest states; nothing is backfilled
    from the other."""
    return {"drift": drift_ledger(pulls),
            "lanes": lane_clv_ledger(bets)}


# ----------------------------------------------------------------
# Organ 7 — the Kelly staking engine (money)
#
# Advisory stakes only: this organ never places, queues, or
# approves a bet, and no grade or verdict reads it. Conventions,
# stated once: stakes size off the PESSIMOTIC probability — the
# band's pessimistic-end edge when the caller supplies it
# (pess_edge_pts), else half the model's edge over the price
# (the half-edge convention, named wherever it prints). The
# default fraction is quarter-Kelly; a hard cap holds any single
# bet at 5% of bankroll. An UNCALIBRATED lane's advice is damped
# to half with the reason named; an UNPRICED bet gets no stake
# at all, with its reason named. 1 unit = 1% of bankroll (the
# app's standing unit law).

KELLY_DEFAULT_FRACTION = 0.25
KELLY_HARD_CAP_FRAC = 0.05
KELLY_UNCALIBRATED_DAMP = 0.5
_RUIN_FLOOR = 0.10   # a path is ruined under 10% of its start


def _full_kelly(p, price):
    dec = american_to_decimal(int(price))
    b = dec - 1.0
    if b <= 0:
        return 0.0
    return (b * p - (1.0 - p)) / b


def kelly_advice(p, price, bankroll=None,
                 fraction=KELLY_DEFAULT_FRACTION,
                 pess_edge_pts=None, cal_tag=None, priced=True):
    """The advisory stake for one priced bet, as a RANGE: the
    low end sizes off the pessimistic probability, the high end
    off the model's headline probability — both at the stated
    Kelly fraction, both damped for an UNCALIBRATED lane, both
    hard-capped. Returns a dict whose 'state' names the outcome
    (ADVISORY / NO EDGE / UNPRICED) and whose 'reasons' prints
    every adjustment applied — a stake never moves in silence."""
    if not priced or p is None or price is None:
        return {"state": "UNPRICED", "stake_frac": 0.0,
                "stake_frac_hi": 0.0, "stake_units": 0.0,
                "stake_units_hi": 0.0, "stake_dollars": None,
                "stake_dollars_hi": None, "full_kelly": None,
                "reasons": ["UNPRICED: no probability the system "
                            "can defend — no stake is advised"]}
    implied = implied_prob(int(price))
    if pess_edge_pts is not None:
        p_pess = implied + pess_edge_pts / 100.0
        pess_basis = "the band's pessimistic-end edge"
    else:
        p_pess = implied + 0.5 * (p - implied)
        pess_basis = "half-edge convention (no band supplied)"
    f_lo = _full_kelly(p_pess, price)
    f_hi = _full_kelly(p, price)
    reasons = [f"sized off {pess_basis}: pessimistic "
               f"P {p_pess * 100:.1f}% vs headline "
               f"{p * 100:.1f}% at {int(price):+d}"]
    stake_lo = max(0.0, fraction * f_lo)
    stake_hi = max(0.0, fraction * f_hi)
    if cal_tag == "UNCALIBRATED":
        stake_lo *= KELLY_UNCALIBRATED_DAMP
        stake_hi *= KELLY_UNCALIBRATED_DAMP
        reasons.append("lane UNCALIBRATED — advisory damped "
                       "to half, by rule")
    capped = False
    if stake_lo > KELLY_HARD_CAP_FRAC:
        stake_lo = KELLY_HARD_CAP_FRAC
        capped = True
    if stake_hi > KELLY_HARD_CAP_FRAC:
        stake_hi = KELLY_HARD_CAP_FRAC
        capped = True
    if capped:
        reasons.append("hard cap: no single bet above "
                       "5% of bankroll")
    state = "ADVISORY" if stake_lo > 0 else "NO EDGE"
    if state == "NO EDGE":
        reasons.append("at the pessimistic number the Kelly "
                       "fraction is not positive — the advised "
                       "stake is zero")
    return {"state": state,
            "stake_frac": stake_lo, "stake_frac_hi": stake_hi,
            "stake_units": stake_lo / 0.01,
            "stake_units_hi": stake_hi / 0.01,
            "stake_dollars": (bankroll * stake_lo
                              if bankroll else None),
            "stake_dollars_hi": (bankroll * stake_hi
                                 if bankroll else None),
            "full_kelly": f_hi, "reasons": reasons}


def lane_history_entry(lane, history=None):
    """One lane's scored-history entry (v5-lane-history.json via
    HISTORY_PATH), or None. `history` may inject a parsed dict
    (the regression's fixtures do)."""
    if history is None:
        try:
            with open(HISTORY_PATH) as f:
                history = json.load(f)
        except Exception:
            return None
    if isinstance(history, dict):
        entry = history.get(lane)
        if isinstance(entry, dict) and entry.get("n"):
            return entry
    return None


def kelly_mc_bands(p, price, stake_frac, lane=None, history=None,
                   n_bets=50, n_paths=400, seed=20261022):
    """Monte Carlo drawdown / ruin bands for repeating this bet
    at this stake fraction, simulated from the lane's scored
    history: the per-bet win probability blends the model's p
    with the lane's empirical rate, 50/50 (named wherever it
    prints — the lane's record is evidence about the model,
    not a substitute for it). A lane with < 10 scored bets has
    no bands: state 'insufficient scored history', printed,
    never simulated from air. Ruin = the path's bankroll falls
    below 10% of its start at any point (stated definition).
    Deterministic under the seed."""
    entry = lane_history_entry(lane, history) if lane else None
    if entry is None or int(entry.get("n") or 0) < 10:
        return {"state": "insufficient scored history",
                "lane": lane,
                "note": "no Monte Carlo bands — the lane has "
                        "fewer than 10 scored bets on file"}
    wins = int(entry.get("wins") or 0)
    n = int(entry["n"])
    p_sim = 0.5 * p + 0.5 * (wins / n)
    dec = american_to_decimal(int(price))
    b = dec - 1.0
    rng = random.Random(seed)
    finals, max_dds, ruins = [], [], 0
    for _ in range(n_paths):
        bank = peak = 1.0
        max_dd = 0.0
        ruined = False
        for _ in range(n_bets):
            if rng.random() < p_sim:
                bank *= (1.0 + stake_frac * b)
            else:
                bank *= (1.0 - stake_frac)
            peak = max(peak, bank)
            max_dd = max(max_dd, (peak - bank) / peak)
            if bank < _RUIN_FLOOR:
                ruined = True
        finals.append(bank)
        max_dds.append(max_dd)
        ruins += 1 if ruined else 0
    finals.sort()
    max_dds.sort()

    def _pct(xs, q):
        return xs[min(len(xs) - 1, max(0, int(q * len(xs))))]

    return {"state": "simulated", "lane": lane,
            "basis": f"lane {lane} scored {wins}-{n - wins} "
                     f"(n={n}); per-bet P blended 50/50 model "
                     f"({p * 100:.1f}%) / empirical "
                     f"({wins / n * 100:.1f}%) = {p_sim * 100:.1f}%",
            "p_sim": p_sim, "paths": n_paths, "bets_per_path": n_bets,
            "median_final": _pct(finals, 0.5),
            "p10_final": _pct(finals, 0.1),
            "p90_final": _pct(finals, 0.9),
            "median_max_dd_pct": _pct(max_dds, 0.5) * 100,
            "p90_max_dd_pct": _pct(max_dds, 0.9) * 100,
            "ruin_rate": ruins / n_paths}

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
    # v5.2 expectation (Pilot order 2026-10-20): the phi fact is
    # unchanged — no candidate beats the benchmark, and that fact
    # prints below, unburied. What the regression asserts changed
    # with the grading policy: (a) the lane's DISPLAYED calibration
    # tag is UNCALIBRATED (the tag is asserted, not a cap); (b)
    # grade_v5 applies NO calibration cap on this lane — a
    # constructed +9.0-pt edge grades above the C band.
    tag4 = calibration_tag("nfl-ml", card)
    g4_probe, _, _ = grade_v5(9.0, "nfl-ml", card,
                              "model-structural", {})
    r4_pass = (fit["status"] == "UNCALIBRATED"
               and tag4 == "UNCALIBRATED"
               and LADDER.index(g4_probe) < LADDER.index("C"))
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
               f"UNCALIBRATED, and this paragraph is the record of "
               f"why. Under the v5.2 grading policy the word is a "
               f"DISPLAYED TAG, not a cap or a gate: the tag is "
               f"asserted here (calibration_tag(nfl-ml) = {tag4}), "
               f"and grade_v5 applies no cap on this lane — a "
               f"constructed +9.0-pt edge grades {g4_probe}, above "
               f"the C band the v5.1 cap would have forced. The "
               f"lane's probabilities still carry no calibration "
               f"claim; the reader sees the tag on every card and "
               f"judges.**")
    out.append(f"- what the failure is NOT: the lane's raw "
               f"walk-forward Brier on weeks 3-5 was 0.2346 — it was "
               f"calibrated on the data phi was allowed to see. "
               f"Week 6 was a regime break (8 of 11 road teams won; "
               f"the 0.64-0.69 home-favourite band went 0-for-4). "
               f"No honest function of weeks 1-5 fixes a break it "
               f"cannot see, and v5 will not pretend otherwise.")
    r4_verdict = ("PASS — under the v5.2 expectation: phi still "
                  "fails its benchmark (the fact above), the lane's "
                  "tag asserts UNCALIBRATED, and no grade cap "
                  "applies (probe grades "
                  f"{g4_probe})" if r4_pass else
                  "FAIL — the v5.2 expectation did not hold (tag or "
                  "cap probe disagrees with the policy)")
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
               "(R4). Since v5.2 the tag displays; it does not cap "
               "or gate. The lane keeps pricing (its margin "
               "centres beat the market's in Week 6 — MAE 6.6 vs "
               "7.1) but its win probabilities carry no calibration "
               "claim, and every card says so.")
    out.append("- cfb ml / cover / live: phi NOT-YET-FITTED "
               "(identity; no walk-forward pair set built for "
               "these estimators yet — future work, named here "
               "rather than implied done). Tag: PROVISIONAL.")
    out.append("- props: phi NOT-YET-FITTED; lane record 0-0 -> "
               "the ladder's record-less soft condition stands; "
               "tag PROVISIONAL/UNCALIBRATED by the record rule.")
    out.append("- totals: engine is a STUB — UNPRICED, grade C "
               "convention on the stub line, DO NOT BET "
               "(price_total_stub).")
    out.append("- scoring-play props: route scoped in code comments "
               "(prop_from_scoring_plays) — the summary endpoint "
               "answers but carries no scoringPlays structure in "
               "this environment, so the reconstruction cannot run "
               "honestly yet. Stub prints UNPRICED.")
    out.append("")
    out.append("## Consequence, stated plainly")
    out.append("")
    out.append("With every lane either UNCALIBRATED, record-less, or "
               "phi-untested, v5 as designed printed No Bet on "
               "nearly everything until a lane earned a fitted phi "
               "that beat its benchmark out-of-sample. v5.2 (Pilot "
               "order 2026-10-20) changes the presentation, not "
               "the evidence: the tags print on every card, grades "
               "and verdicts follow the edge math, and the reader "
               "— not a silent cap — weighs what an UNCALIBRATED "
               "tag means. The phi facts in this report are "
               "unchanged.")
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
               "“negative edge”; (4) record-less is the ladder’s "
               "own soft condition.")
    out.append("")
    out.append("v5.2 supersedes the v5.1 calibration readings "
               "(Pilot order 2026-10-20): calibration_state no "
               "longer enters the ladder as a hard or soft "
               "condition at all — FAILED (UNCALIBRATED), "
               "PROVISIONAL and CALIBRATED lanes climb on grade "
               "and edge alone, and the tag prints on the card. "
               "GOLDEN BET (v5.2): A-band grade, priced, "
               "pessimistic-end edge >= +2.0 (v5.3 — Pilot order "
               "2026-10-22; the bar was +3.0 through v5.2), named mechanism, "
               "no soft condition outstanding. BET HERE: A/B-band "
               "grade, positive edge, no hard or soft condition. "
               "The checks below assert the v5.2 mapping.")
    out.append("")
    out.append("## R7 — verdict-mapping checks")
    out.append("")
    out.append("Criterion (stated before numbers): constructed "
               "inputs to verdict_ladder produce each of the "
               "five verdicts under exactly its stated conditions; "
               "a grid sweep asserts TAG INVARIANCE — identical "
               "inputs under cal_state FAILED / PROVISIONAL / "
               "CALIBRATED print identical verdicts; and on the "
               "recorded data on file — the R6 sample slate "
               "above, the saved FanDuel pull, and the graded "
               "NFL Week 6 slate in data/v5-phi.json — every "
               "PRICED NFL verdict carries the UNCALIBRATED tag, "
               "every GOLDEN BET satisfies the golden (v5.3 bar) "
               "criteria, and every UNPRICED verdict is DO NOT BET.")
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
        ("tag only: lane PROVISIONAL no longer demotes (v5.2)",
         {**base7, "grade": "B-", "cal_state": "PROVISIONAL"},
         BET_HERE),
        ("tag only: golden shape on an UNCALIBRATED lane (v5.2)",
         {**base7, "grade": "A", "phi_edge_pts": 6.5,
          "raw_edge_pts": 7.0, "pess_edge_pts": 3.5,
          "cal_state": "FAILED"}, GOLDEN_BET),
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
         {**base7, "fragile": True, "record_less": True},
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
                vs7 = set()
                for cal7 in ("FAILED", "PROVISIONAL", "CALIBRATED"):
                    v7, _w7 = verdict_ladder(
                        priced=True, grade=g7,
                        phi_edge_pts=max(raw7, 0.5),
                        raw_edge_pts=raw7, pess_edge_pts=pess7,
                        cal_state=cal7, benched=False,
                        killed=False, fragile=False,
                        bias_favours=False, record_less=False,
                        coherence_flags=[],
                        mechanism="model-structural")
                    vs7.add(v7)
                if len(vs7) != 1:
                    sweep_ok = False
    r7_ok = r7_ok and sweep_ok
    out.append(f"- TAG INVARIANCE sweep (13 grades x 4 band "
               f"margins x 2 raw edges x 3 calibration states): "
               f"the verdict never moves with the tag: {sweep_ok}")
    r6_golden = [v for v in r6_verdicts
                 if v.get("verdict") == GOLDEN_BET]
    r6_golden_bad = [v for v in r6_golden
                     if v.get("grade") not in ("A+", "A", "A-")]
    out.append(f"- recorded data, R6 sample slate above: "
               f"{len(r6_verdicts)} checker verdicts, GOLDEN BET "
               f"count {len(r6_golden)} (v5.2 asserts each one "
               f"carries an A-band grade: "
               f"{not r6_golden_bad})")
    r7_ok = r7_ok and not r6_golden_bad
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
                        if v.get("cal_tag") != "UNCALIBRATED"]
        pull_golden_bad = [v for v in pull_golden
                           if v.get("grade")
                           not in ("A+", "A", "A-")
                           or not v.get("cal_tag")]
        pull_unp = [v for v in pull_v
                    if v["state"] == "UNPRICED"]
        pull_unp_bad = [v for v in pull_unp
                        if v["verdict"] != DO_NOT_BET]
        out.append(f"- recorded data, saved FanDuel pull "
                   f"({pull_names[-1]}): {len(pull_v)} checker "
                   f"verdicts, GOLDEN BET count "
                   f"{len(pull_golden)} (each satisfying the "
                   f"v5.2 golden criteria: "
                   f"{not pull_golden_bad}); PRICED NFL "
                   f"moneylines {len(pull_nfl_ml)}, all carrying "
                   f"the UNCALIBRATED tag: {not pull_nfl_bad}; "
                   f"UNPRICED verdicts {len(pull_unp)}, all "
                   f"carrying DO NOT BET: "
                   f"{not pull_unp_bad}")
        r7_ok = (r7_ok and not pull_golden_bad and not pull_nfl_bad
                 and not pull_unp_bad)
    else:
        out.append("- recorded data, saved FanDuel pull: NONE "
                   "ON FILE — this check cannot run")
        r7_ok = False
    sel7 = fit["candidates"][fit["selected"]]
    nfl_dist = {}
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
        nfl_dist[v7] = nfl_dist.get(v7, 0) + 1
    out.append(f"- recorded data, graded NFL Week 6 slate "
               f"({len(fit['slate_detail'])} games, phi edge vs "
               f"the market no-vig P): verdict distribution under "
               f"v5.2 (the lane's tag asserts UNCALIBRATED — R4 "
               f"above; rungs now follow the edge math): "
               f"{nfl_dist}")
    r4_txt = ("PASS (v5.2 expectation: tag asserted, no cap)" if
              r4_pass else "FAIL (v5.2 expectation)")
    out.append(f"- R1-R6 re-run under engine {ENGINE_VERSION}: "
               f"R1 {'PASS' if r1_pass else 'FAIL'} | "
               f"R2 {'PASS' if r2_pass else 'FAIL'} | "
               f"R3 {'PASS' if r3_pass else 'FAIL'} | "
               f"R4 {r4_txt} | "
               f"R5 {'PASS' if r5_pass else 'FAIL'} | "
               f"R6 {'PASS' if r6_pass else 'FAIL'}")
    out.append(f"- **R7: {'PASS' if r7_ok else 'FAIL'}**")
    out.append("")

    # ---------- ADDENDUM v5.2: stance + bands + tag checks
    out.append(f"## ADDENDUM v5.2 — stance, widened bands, "
               f"calibration-as-tag (engine {ENGINE_VERSION})")
    out.append("")
    out.append("Pilot order 2026-10-20: less rigid grading — "
               "grades from the edge math on every lane, "
               "calibration as a displayed tag (CALIBRATED / "
               "PROVISIONAL / UNCALIBRATED / UNTESTED), widened "
               "grade bands, and a STANCE on every priced bet "
               "(bet_stance — derived from the bet's own "
               "probability, edge and price; UNPRICED bets get "
               "none). Criterion (stated before numbers): the "
               "constructed profiles below land on their named "
               "stances; parlay_stance follows its stated rule; "
               "base_grade reproduces the published v5.2 band "
               "table at every floor.")
    stance_cases = [
        ("boring favourite: p 0.72, edge +0.6, price -250",
         (0.72, 0.6, -250), "CONSERVATIVE"),
        ("strong position: p 0.55, edge +5.0, price -105",
         (0.55, 5.0, -105), "BULLISH"),
        ("longshot: p 0.30, edge +8.0, price +250",
         (0.30, 8.0, 250), "LONGSHOT"),
        ("plus money: p 0.40, edge +1.0, price +220",
         (0.40, 1.0, 220), "LONGSHOT"),
        ("heavy favourite with a real edge: p 0.70, edge +4.0, "
         "price -230", (0.70, 4.0, -230), "BULLISH"),
        ("coin flip, thin edge: p 0.50, edge +0.5, price -110",
         (0.50, 0.5, -110), "LONGSHOT"),
    ]
    r52_ok = True
    for name_s, args_s, want_s in stance_cases:
        got_s = bet_stance(*args_s)
        ok_s = got_s == want_s
        r52_ok = r52_ok and ok_s
        out.append(f"- stance {name_s}: **{got_s}** "
                   f"({'as specced' if ok_s else 'EXPECTED ' + want_s})")
    none_s = (bet_stance(None, None, -110) is None
              and bet_stance(0.5, 1.0, None) is None)
    r52_ok = r52_ok and none_s
    out.append(f"- stance of an unpriced bet: None (UNPRICED bets "
               f"get no stance): {none_s}")
    parlay_cases = [
        (["CONSERVATIVE", "CONSERVATIVE"], "CONSERVATIVE"),
        (["CONSERVATIVE", "BULLISH"], "BULLISH"),
        (["BULLISH", "LONGSHOT"], "LONGSHOT"),
        (["CONSERVATIVE", None], None),
    ]
    for legs_s, want_s in parlay_cases:
        got_s = parlay_stance(legs_s)
        ok_s = got_s == want_s
        r52_ok = r52_ok and ok_s
        out.append(f"- parlay stance {legs_s}: **{got_s}** "
                   f"({'as specced' if ok_s else 'EXPECTED ' + str(want_s)})")
    bands_ok = True
    for i, (lo_b, g_b) in enumerate(GRADE_BANDS_V52):
        if base_grade(lo_b) != g_b:
            bands_ok = False
        nxt = (GRADE_BANDS_V52[i + 1][1]
               if i + 1 < len(GRADE_BANDS_V52) else "F")
        if base_grade(lo_b - 0.01) != nxt:
            bands_ok = False
    r52_ok = r52_ok and bands_ok
    out.append(f"- band table: base_grade reproduces every v5.2 "
               f"floor and the grade just below it: {bands_ok}")
    out.append(f"- **ADDENDUM v5.2 checks: "
               f"{'PASS' if r52_ok else 'FAIL'}**")
    out.append("")
    # ---------- ADDENDUM v5.3: golden bar +2.0, CLV/drift
    # ledger, Kelly staking engine (Pilot order 2026-10-22)
    out.append(f"## ADDENDUM v5.3 — golden threshold +2.0, "
               f"CLV & drift ledger, Kelly staking engine "
               f"(engine {ENGINE_VERSION})")
    out.append("")
    out.append("Pilot order 2026-10-22 (F5): (a) the GOLDEN "
               "pessimistic-edge bar moves from +3.0 to +2.0 phi "
               "points — grade A, priced, named mechanism and "
               "no softs unchanged; GRADING.md amended in "
               "writing the same day. (b) Two display-side "
               "organs: the CLV & drift ledger (measurement — "
               "never an input to a grade, verdict or tag) and "
               "the Kelly staking engine (advisory — never "
               "places or queues a bet). Criterion (stated "
               "before numbers): the boundary cases below land "
               "exactly on the +2.0 bar; the CLV/drift fixtures "
               "reproduce their hand-computed values AND fail "
               "on deliberately perturbed fixtures; the Kelly "
               "fixtures reproduce hand-computed fractions, "
               "the 5% hard cap binds, the UNCALIBRATED damp "
               "halves, and the Monte Carlo bands are "
               "deterministic under their seed and move when "
               "the lane history is perturbed.")
    r53_ok = True
    gbase = dict(priced=True, grade="A", phi_edge_pts=6.5,
                 raw_edge_pts=7.0, cal_state="CALIBRATED",
                 benched=False, killed=False, fragile=False,
                 bias_favours=False, record_less=False,
                 coherence_flags=[], mechanism="model-structural")
    golden_cases = [
        ("pess +2.4, grade A, mechanism, no softs",
         {**gbase, "pess_edge_pts": 2.4}, GOLDEN_BET),
        ("pess +2.0 exactly — the v5.3 bar is inclusive",
         {**gbase, "pess_edge_pts": 2.0}, GOLDEN_BET),
        ("pess +1.9 — one notch under the bar",
         {**gbase, "pess_edge_pts": 1.9}, BET_HERE),
        ("pess +2.4 with a soft (FRAGILE) — no golden at "
         "any edge", {**gbase, "pess_edge_pts": 2.4,
                      "fragile": True}, RISK_BET_YES),
        ("pess +12.0 with a soft (record-less lane)",
         {**gbase, "pess_edge_pts": 12.0, "record_less": True},
         RISK_BET_YES),
        ("pess +2.4, no mechanism named — withheld",
         {**gbase, "pess_edge_pts": 2.4, "mechanism": None},
         BET_HERE),
    ]
    for name_g, kw_g, want_g in golden_cases:
        got_g, _why_g = verdict_ladder(**kw_g)
        ok_g = got_g == want_g
        r53_ok = r53_ok and ok_g
        out.append(f"- golden boundary {name_g}: **{got_g}** "
                   f"({'as specced' if ok_g else 'EXPECTED ' + want_g})")
    # ---- CLV & drift fixtures (hand-computed; perturbed twins
    # must NOT reproduce the expected values)
    _mk = lambda price: {"sport": "nfl", "fd_event_id": 1,  # noqa: E731
                         "fd_market_id": "m1", "market": "spread",
                         "side": "home", "line": -3.5,
                         "price": price}
    pull_a = {"pulled_at": "2026-10-19T12:00:00+00:00",
              "markets": [_mk(-110)]}
    pull_b = {"pulled_at": "2026-10-19T13:00:00+00:00",
              "markets": [_mk(-120)]}
    pull_b_bad = {"pulled_at": "2026-10-19T13:00:00+00:00",
                  "markets": [_mk(-105)]}
    d_fix = drift_ledger([pull_a, pull_b])
    row_fix = d_fix["rows"][0]
    drift_ok = (d_fix["markets_tracked"] == 1
                and row_fix["state"] == "tracked"
                and abs(row_fix["drift_prob_pts"] - 2.16) < 0.01)
    d_pert = drift_ledger([pull_a, pull_b_bad])
    drift_ok = drift_ok and (
        abs(d_pert["rows"][0]["drift_prob_pts"] - 2.16) > 0.5
        and abs(d_pert["rows"][0]["drift_prob_pts"]
                - (-1.16)) < 0.01)
    r53_ok = r53_ok and drift_ok
    out.append(f"- drift fixture: -110 -> -120 across two pulls "
               f"is +2.16 pts tracked; perturbed close (-105) "
               f"does not reproduce it: {drift_ok}")
    d_one = drift_ledger([pull_a])
    insuf_ok = (d_one["markets_tracked"] == 0
                and d_one["rows"][0]["state"]
                == "insufficient snapshots")
    d_skip = drift_ledger([{"games": []}])
    insuf_ok = insuf_ok and d_skip["skipped_inputs"] == 1 \
        and d_skip["state"] == "no menu pulls"
    r53_ok = r53_ok and insuf_ok
    out.append(f"- drift honesty: one pull => 'insufficient "
               f"snapshots'; a non-pull input is classified, "
               f"not forced: {insuf_ok}")
    clv_ok = abs(clv_points(-110, -130) - 4.14) < 0.01 \
        and clv_points(-110, None) is None
    lanes_fix = lane_clv_ledger([
        {"lane": "nfl-ml", "price": -110, "close_price": -130},
        {"lane": "nfl-ml", "price": 150, "close_price": 120},
        {"lane": "props", "price": -110, "close_price": None}])
    by_lane = {r["lane"]: r for r in lanes_fix}
    clv_ok = clv_ok and (
        abs(by_lane["nfl-ml"]["mean_clv_pts"] - 4.80) < 0.01
        and by_lane["nfl-ml"]["beat_rate"] == 1.0
        and by_lane["props"]["state"]
        == "insufficient settled bets")
    r53_ok = r53_ok and clv_ok
    out.append(f"- CLV fixtures: -110 into a -130 close is "
               f"+4.14 pts; lane mean/beat-rate aggregate; an "
               f"unclosed lane states 'insufficient settled "
               f"bets': {clv_ok}")
    # ---- Kelly fixtures (hand-computed above in the organ's
    # docstring conventions)
    k_fix = kelly_advice(0.60, -110, bankroll=1000)
    kelly_ok = (k_fix["state"] == "ADVISORY"
                and abs(k_fix["stake_frac"] - 0.02) < 1e-9
                and abs(k_fix["stake_units"] - 2.0) < 1e-9
                and abs(k_fix["stake_dollars"] - 20.0) < 1e-9
                and abs(k_fix["stake_frac_hi"] - 0.04) < 1e-9)
    k_pert = kelly_advice(0.55, -110, bankroll=1000)
    kelly_ok = kelly_ok and abs(k_pert["stake_frac"] - 0.02) > 0.005
    r53_ok = r53_ok and kelly_ok
    out.append(f"- Kelly fixture: p .60 at -110 sizes 2.0u "
               f"($20 of $1000) at the pessimistic end, 4.0u at "
               f"the headline; perturbed p (.55) does not "
               f"reproduce it: {kelly_ok}")
    k_cap = kelly_advice(0.95, -110)
    k_damp = kelly_advice(0.60, -110, cal_tag="UNCALIBRATED")
    k_unp = kelly_advice(None, -110, priced=False)
    k_noedge = kelly_advice(0.50, -110)
    kelly2_ok = (k_cap["stake_frac"] == KELLY_HARD_CAP_FRAC
                 and abs(k_damp["stake_frac"] - 0.01) < 1e-9
                 and any("UNCALIBRATED" in r
                         for r in k_damp["reasons"])
                 and k_unp["state"] == "UNPRICED"
                 and k_unp["stake_frac"] == 0.0
                 and k_noedge["state"] == "NO EDGE"
                 and k_noedge["stake_frac"] == 0.0)
    r53_ok = r53_ok and kelly2_ok
    out.append(f"- Kelly guards: 5% hard cap binds at p .95; "
               f"UNCALIBRATED halves with the reason named; "
               f"UNPRICED and no-edge advise zero: {kelly2_ok}")
    mc_a = kelly_mc_bands(0.55, -110, 0.02, lane="nfl-ml")
    mc_b = kelly_mc_bands(0.55, -110, 0.02, lane="nfl-ml")
    mc_ok = (mc_a["state"] == "simulated" and mc_a == mc_b
             and 0.0 <= mc_a["ruin_rate"] <= 1.0
             and mc_a["median_max_dd_pct"] >= 0.0)
    mc_pert = kelly_mc_bands(
        0.55, -110, 0.02, lane="nfl-ml",
        history={"nfl-ml": {"wins": 8, "losses": 3, "n": 11}})
    mc_ok = mc_ok and mc_pert["median_final"] != mc_a["median_final"]
    mc_none = kelly_mc_bands(0.55, -110, 0.02, lane="nba-ml")
    mc_ok = mc_ok and mc_none["state"] == \
        "insufficient scored history"
    r53_ok = r53_ok and mc_ok
    out.append(f"- Kelly MC: bands simulate from the nfl-ml "
               f"scored history, deterministic under the seed, "
               f"move under a perturbed history, and refuse "
               f"an unscored lane: {mc_ok}")
    out.append(f"- **ADDENDUM v5.3 checks: "
               f"{'PASS' if r53_ok else 'FAIL'}**")
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

