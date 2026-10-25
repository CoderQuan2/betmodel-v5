#!/usr/bin/env python3
"""
fit_soccer_leagues.py — BetFi Xii (v12) multi-league soccer fits.

Pulls REAL completed-season results CSVs from football-data.co.uk
and fits each league with the SAME protocol the engine's own
fit_soccer() used for the EPL fit in data/v5-soccer.json:

  * league home/away scoring rates with the engine's priors
    (LH 1.40 / LA 1.15, 10-game prior weight),
  * attack/defence strengths per team (prior shrinkage of
    SOC_PRIOR_GAMES = 8 games at the league scoring rate),
  * sequential Elo (K = 20, HFA = 65 Elo points, score 1 / 0.5 / 0),
  * a WALK-FORWARD backtest: every game is predicted from the
    strengths/Elo accumulated from PRIOR games only, then graded
    (3-way Brier, argmax accuracy, n) — updates land AFTER the
    prediction, exactly as in fit_soccer.

The Poisson grid and lambda construction are the engine's own
(betmodel5.soccer_grid / betmodel5.soccer_lambdas, imported —
never re-implemented), so a league fit here prices identically to
how the engine prices the EPL fit.

Leagues (football-data.co.uk mmz4281, season 2425 = 2024-25):
  I1  Serie A        SP1 La Liga       D1  Bundesliga
  F1  Ligue 1        E0  Premier League — the CONTROL: fitted by
      the same code and stored under "control", NOT under
      "leagues", so it can be compared against the shipped
      v5-soccer.json without ever shadowing it in the checker
      (EPL grading stays byte-for-byte the shipped fit's).

  "Fix the laziness" extension (CODER X): every other league
  that actually shows up on FanDuel pulls got the same fit —
    E1 Championship      I2 Serie B        SP2 La Liga 2
    F2 Ligue 2           D2 Bundesliga 2   N1 Eredivisie
    P1 Primeira Liga     T1 Super Lig      G1 Super League (GR)
    B1 Jupiler Pro       SC0 Scottish Premiership
  plus MLS (usa.1) from ESPN scoreboard DAY PULLS — the same
  source family the original EPL fit used — over the full 2025
  regular season (2025-02-22 .. 2025-10-18, Decision Day;
  playoffs excluded: knockout games are not league fixtures).
  A league whose source fails is OMITTED and printed, never
  fabricated (the law above is unchanged).

Output: data/v5-soccer-leagues.json, same schema family as
v5-soccer.json per league (league rates / elo / strengths /
backtest / params / source / fitted_at).

Honesty law: a league whose download or parse fails is OMITTED
and its failure printed — a league is never fabricated, padded,
or borrowed from another league's numbers.

Run:  python3 tools/fit_soccer_leagues.py [--out PATH]
"""
import csv
import io
import json
import os
import statistics
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CLONE = os.path.dirname(HERE)
sys.path.insert(0, CLONE)

import betmodel5 as b5  # the engine — grid/lambda math imported

BASE = "https://www.football-data.co.uk/mmz4281/2425"
LEAGUES = {
    "serie-a":    ("I1", "Serie A (Italy)"),
    "la-liga":    ("SP1", "La Liga (Spain)"),
    "bundesliga": ("D1", "Bundesliga (Germany)"),
    "ligue-1":    ("F1", "Ligue 1 (France)"),
    # --- "fix the laziness" extension: the other leagues that
    # appear on FanDuel pulls, same source, same protocol ---
    "championship":         ("E1", "Championship (England)"),
    "serie-b":              ("I2", "Serie B (Italy)"),
    "la-liga-2":            ("SP2", "La Liga 2 (Spain)"),
    "ligue-2":              ("F2", "Ligue 2 (France)"),
    "bundesliga-2":         ("D2", "Bundesliga 2 (Germany)"),
    "eredivisie":           ("N1", "Eredivisie (Netherlands)"),
    "primeira-liga":        ("P1", "Primeira Liga (Portugal)"),
    "super-lig":            ("T1", "Super Lig (Turkey)"),
    "super-league-greece":  ("G1", "Super League (Greece)"),
    "jupiler-pro":          ("B1", "Jupiler Pro League (Belgium)"),
    "scottish-premiership": ("SC0", "Scottish Premiership"),
}

# The non-football-data leagues come from ESPN scoreboard day
# pulls (the source family the original EPL fit used): one
# scoreboard call per day over each regular-season window,
# completed events only, deduped by ESPN event id, fitted with
# the identical walk-forward code. Windows cover the last
# completed seasons; playoff / liguilla phases are excluded
# (knockout games are not league fixtures).
ESPN_SOCCER = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_LEAGUES = [
    {"key": "mls", "slug": "usa.1", "name": "MLS (USA)",
     "season": "2025", "label": "2025 MLS regular season",
     "windows": [(date(2025, 2, 22), date(2025, 10, 18))]},
    {"key": "brasileirao", "slug": "bra.1",
     "name": "Serie A (Brazil)", "season": "2025",
     "label": "2025 Brazilian Serie A",
     "windows": [(date(2025, 3, 29), date(2025, 12, 7))]},
    {"key": "liga-mx", "slug": "mex.1", "name": "Liga MX (Mexico)",
     "season": "2025",
     "label": "2025 Liga MX regular seasons (Clausura + "
              "Apertura; liguilla excluded)",
     "windows": [(date(2025, 1, 10), date(2025, 4, 21)),
                 (date(2025, 7, 11), date(2025, 11, 10))]},
    {"key": "liga-profesional", "slug": "arg.1",
     "name": "Liga Profesional (Argentina)", "season": "2025",
     "label": "2025 Liga Profesional regular phases (Apertura "
              "+ Clausura; playoffs excluded)",
     "windows": [(date(2025, 1, 23), date(2025, 5, 5)),
                 (date(2025, 7, 11), date(2025, 11, 17))]},
    {"key": "brasileirao-b", "slug": "bra.2",
     "name": "Serie B (Brazil)", "season": "2025",
     "label": "2025 Brazilian Serie B",
     "windows": [(date(2025, 4, 5), date(2025, 11, 23))]},
    {"key": "nacional-b", "slug": "arg.2",
     "name": "Primera Nacional (Argentina)", "season": "2025",
     "label": "2025 Primera Nacional regular phase (reducido "
              "playoffs excluded)",
     "windows": [(date(2025, 2, 7), date(2025, 10, 5))]},
]

# Round 2 (BetFi Xii loop): the leagues the Round-1 report named as
# the remainder — USL first (on every US pull), then the South /
# Central American regionals as they appear on pulls, then the
# women's leagues behind the (W) fixtures. Slugs were discovered
# from ESPN's own scoreboard index (a slug that 400s is not a
# league: chile is chi.1, not chl.1; Nicaragua has no ESPN slug —
# nic.1 / nca.1 / nic.primera all attempted, none resolves to a
# Nicaraguan league, so Nicaragua stays named in the queue).
# Windows: the last completed season PLUS the current season to
# date, so promoted / expansion clubs (Cucuta, Denver Summit,
# Brooklyn FC) carry real games instead of priors alone.
ESPN_LEAGUES_R2 = [
    {"key": "usl-championship", "slug": "usa.usl.1",
     "name": "USL Championship (USA)", "season": "2025+2026",
     "label": "USL Championship 2025 + 2026 to date",
     "windows": [(date(2025, 3, 8), date(2025, 10, 25)),
                 (date(2026, 3, 7), date(2026, 10, 24))]},
    {"key": "usl-league-one", "slug": "usa.usl.l1",
     "name": "USL League One (USA)", "season": "2025+2026",
     "label": "USL League One 2025 + 2026 to date",
     "windows": [(date(2025, 3, 7), date(2025, 10, 25)),
                 (date(2026, 3, 6), date(2026, 10, 24))]},
    {"key": "peru-liga-1", "slug": "per.1",
     "name": "Liga 1 (Peru)", "season": "2025+2026",
     "label": "Peruvian Liga 1 2025 + 2026 to date",
     "windows": [(date(2025, 2, 7), date(2025, 11, 23)),
                 (date(2026, 2, 6), date(2026, 10, 24))]},
    {"key": "colombia-primera", "slug": "col.1",
     "name": "Primera A (Colombia)", "season": "2025+2026",
     "label": "Colombian Primera A 2025 + 2026 to date "
              "(regular phases; cuadrangulares tails included "
              "in window ends are league fixtures of the same "
              "clubs and are fitted as pulled)",
     "windows": [(date(2025, 1, 24), date(2025, 12, 7)),
                 (date(2026, 1, 23), date(2026, 10, 24))]},
    {"key": "ecuador-ligapro", "slug": "ecu.1",
     "name": "LigaPro (Ecuador)", "season": "2025+2026",
     "label": "Ecuadorian LigaPro 2025 + 2026 to date",
     "windows": [(date(2025, 2, 14), date(2025, 11, 30)),
                 (date(2026, 2, 20), date(2026, 10, 24))]},
    {"key": "uruguay-primera", "slug": "uru.1",
     "name": "Primera Division (Uruguay)", "season": "2025+2026",
     "label": "Uruguayan Primera 2025 + 2026 to date",
     "windows": [(date(2025, 1, 31), date(2025, 12, 7)),
                 (date(2026, 1, 30), date(2026, 10, 24))]},
    {"key": "paraguay-primera", "slug": "par.1",
     "name": "Primera Division (Paraguay)", "season": "2025+2026",
     "label": "Paraguayan Primera 2025 + 2026 to date",
     "windows": [(date(2025, 1, 24), date(2025, 11, 30)),
                 (date(2026, 1, 23), date(2026, 10, 24))]},
    {"key": "bolivia-profesional", "slug": "bol.1",
     "name": "Liga Profesional (Bolivia)", "season": "2025+2026",
     "label": "Bolivian Liga Profesional 2025 + 2026 to date",
     "windows": [(date(2025, 3, 28), date(2025, 12, 14)),
                 (date(2026, 3, 20), date(2026, 10, 24))]},
    {"key": "venezuela-primera", "slug": "ven.1",
     "name": "Primera Division (Venezuela)", "season": "2025+2026",
     "label": "Venezuelan Primera 2025 + 2026 to date",
     "windows": [(date(2025, 1, 24), date(2025, 11, 30)),
                 (date(2026, 1, 30), date(2026, 10, 24))]},
    {"key": "costa-rica-primera", "slug": "crc.1",
     "name": "Primera Division (Costa Rica)", "season": "2025-26",
     "label": "Costa Rican Primera Apertura 2025 + Clausura "
              "2026 + Apertura 2026 to date",
     "windows": [(date(2025, 7, 25), date(2025, 12, 21)),
                 (date(2026, 1, 9), date(2026, 10, 24))]},
    {"key": "guatemala-liga", "slug": "gua.1",
     "name": "Liga Nacional (Guatemala)", "season": "2025-26",
     "label": "Guatemalan Liga Nacional Apertura 2025 + "
              "Clausura 2026 + Apertura 2026 to date",
     "windows": [(date(2025, 7, 19), date(2025, 12, 21)),
                 (date(2026, 1, 16), date(2026, 10, 24))]},
    {"key": "chile-primera", "slug": "chi.1",
     "name": "Primera Division (Chile)", "season": "2025+2026",
     "label": "Chilean Primera 2025 + 2026 to date",
     "windows": [(date(2025, 2, 14), date(2025, 12, 7)),
                 (date(2026, 2, 13), date(2026, 10, 24))]},
    {"key": "nwsl", "slug": "usa.nwsl",
     "name": "NWSL (USA Women)", "season": "2025+2026",
     "label": "NWSL 2025 + 2026 to date",
     "windows": [(date(2025, 3, 14), date(2025, 11, 2)),
                 (date(2026, 3, 13), date(2026, 10, 24))]},
    {"key": "liga-mx-femenil", "slug": "mex.w.1",
     "name": "Liga MX Femenil (Mexico Women)",
     "season": "2025-26",
     "label": "Liga MX Femenil Apertura 2025 + Clausura 2026 "
              "+ Apertura 2026 to date (liguilla tails included "
              "in window ends are league fixtures of the same "
              "clubs and are fitted as pulled)",
     "windows": [(date(2025, 7, 11), date(2025, 11, 23)),
                 (date(2026, 1, 9), date(2026, 10, 24))]},
    {"key": "wsl", "slug": "eng.w.1",
     "name": "Women's Super League (England)",
     "season": "2024-25+2025-26",
     "label": "WSL 2024-25 + 2025-26 completed seasons",
     "windows": [(date(2024, 9, 20), date(2025, 5, 10)),
                 (date(2025, 9, 5), date(2026, 5, 16))]},
    {"key": "a-league-women", "slug": "aus.w.1",
     "name": "A-League Women (Australia)", "season": "2025-26",
     "label": "A-League Women 2025-26 (incl. finals)",
     "windows": [(date(2025, 10, 31), date(2026, 5, 2))]},
    {"key": "a-league", "slug": "aus.1",
     "name": "A-League (Australia)", "season": "2025-26",
     "label": "A-League Men 2025-26 (incl. finals)",
     "windows": [(date(2025, 10, 17), date(2026, 5, 30))]},
    # Round 3 repair: these two jobs were in the Round-2
    # artifact's provenance (bra.3: 374 day pulls; arg.3: 548)
    # but missing from this builder copy — the artifact they
    # fed is the only reason anyone knew. Restored with full-
    # season windows so a builder run reproduces the artifact
    # whole; they are also the tier-3 members of the Brazil /
    # Argentina country systems below.
    {"key": "brasileirao-c", "slug": "bra.3",
     "name": "Serie C (Brazil)", "season": "2025+2026",
     "label": "Brazilian Serie C 2025 + 2026 to date",
     "windows": [(date(2025, 4, 12), date(2025, 10, 25)),
                 (date(2026, 4, 11), date(2026, 10, 24))]},
    {"key": "primera-b-ar", "slug": "arg.3",
     "name": "Primera B (Argentina)", "season": "2025+2026",
     "label": "Argentine Primera B 2025 + 2026 to date",
     "windows": [(date(2025, 2, 7), date(2025, 12, 21)),
                 (date(2026, 2, 6), date(2026, 10, 24))]},
    # Round 3: Mexico's second tier (slug mex.2 verified live
    # against ESPN's index 2026-10-24) — a league in its own
    # right and the missing member of the Mexico country
    # system below.
    {"key": "liga-expansion", "slug": "mex.2",
     "name": "Liga de Expansion MX (Mexico)", "season": "2025+2026",
     "label": "Liga de Expansion MX 2025 + 2026 to date",
     "windows": [(date(2025, 1, 3), date(2025, 12, 21)),
                 (date(2026, 1, 2), date(2026, 10, 24))]},
]

# Country systems (Round 2): both tiers of one country's pyramid
# fitted as ONE pool — strengths and Elo on a shared scale, league
# scoring rates kept per tier — so a cross-tier cup fixture prices
# off shared-scale strengths and the home club's tier rates.
COUNTRY_SYSTEMS = [
    {"key": "england", "name": "England (Premier League + "
     "Championship system)", "tier1": ("E0", "tier1"),
     "tier2": ("E1", "tier2"),
     "sep1": None, "sep2": "championship"},
    {"key": "italy", "name": "Italy (Serie A + Serie B system)",
     "tier1": ("I1", "tier1"), "tier2": ("I2", "tier2"),
     "sep1": "serie-a", "sep2": "serie-b"},
    {"key": "spain", "name": "Spain (La Liga + La Liga 2 system)",
     "tier1": ("SP1", "tier1"), "tier2": ("SP2", "tier2"),
     "sep1": "la-liga", "sep2": "la-liga-2"},
    {"key": "france", "name": "France (Ligue 1 + Ligue 2 system)",
     "tier1": ("F1", "tier1"), "tier2": ("F2", "tier2"),
     "sep1": "ligue-1", "sep2": "ligue-2"},
    {"key": "germany", "name": "Germany (Bundesliga + "
     "Bundesliga 2 system)", "tier1": ("D1", "tier1"),
     "tier2": ("D2", "tier2"),
     "sep1": "bundesliga", "sep2": "bundesliga-2"},
]
# A country system ships only if its pooled walk-forward on
# TOP-TIER games is not materially worse than the separate top
# tier fit's (brier3 delta <= this line — stated, not tuned).
SYSTEM_TIER1_TOLERANCE = 0.01
CONTROL = ("epl", "E0", "Premier League (England) — control")

# Americas country systems (Round 3): the Round-2 pooled recipe
# extended to the multi-tier pyramids the ESPN passes fit —
# members are league keys from the ESPN passes above, in tier
# order (tier1 first). Same ship gate as the European systems:
# pooled tier-1 walk-forward brier3 within +0.01 of the separate
# tier-1 league fit, printed per country either way.
AMERICAS_SYSTEMS = [
    {"key": "brazil", "name": "Brazil (Serie A + Serie B + "
     "Serie C system)",
     "members": [("brasileirao", "tier1"),
                 ("brasileirao-b", "tier2"),
                 ("brasileirao-c", "tier3")]},
    {"key": "argentina", "name": "Argentina (Liga Profesional "
     "+ Primera Nacional + Primera B system)",
     "members": [("liga-profesional", "tier1"),
                 ("nacional-b", "tier2"),
                 ("primera-b-ar", "tier3")]},
    {"key": "usa", "name": "USA (MLS + USL Championship + USL "
     "League One system)",
     "members": [("mls", "tier1"),
                 ("usl-championship", "tier2"),
                 ("usl-league-one", "tier3")]},
    {"key": "mexico", "name": "Mexico (Liga MX + Liga de "
     "Expansion system)",
     "members": [("liga-mx", "tier1"),
                 ("liga-expansion", "tier2")]},
]

# Cup pools (Round 3): ONE pooled fit per cup family — every
# tie from every listed competition and season in a single
# walk-forward pool, strengths shared across the pool — so a
# cross-competition fixture (Champions League, Coupe de
# France, Copa Argentina) prices when BOTH clubs are in the
# pool. A pool SHIPS (prices) only if its walk-forward brier3
# beats a bar stated before the run: the median league fit's
# brier3 + CUP_POOL_TOLERANCE. A held pool is still written to
# the artifact — fit, gate and numbers on record — and the
# engine stamps its fixtures with the attempt instead of a
# price. Qualifying competitions are part of their cup: the
# ties FanDuel lists for August ARE qualifiers.
CUP_POOL_TOLERANCE = 0.03
_EU_MAIN_WIN = [(date(2023, 8, 1), date(2024, 6, 30)),
                (date(2024, 8, 1), date(2025, 6, 30)),
                (date(2025, 8, 1), date(2026, 6, 30)),
                (date(2026, 8, 1), date(2026, 10, 24))]
_EU_QUAL_WIN = [(date(y, 7, 1), date(y, 9, 30))
                for y in (2023, 2024, 2025, 2026)]
CUP_POOLS = [
    {"key": "europe", "name": "European cups pool (Champions "
     "League + Europa League + Conference League, incl. "
     "qualifying)",
     "parts": [("uefa.champions", _EU_MAIN_WIN),
               ("uefa.champions_qual", _EU_QUAL_WIN),
               ("uefa.europa", _EU_MAIN_WIN),
               ("uefa.europa_qual", _EU_QUAL_WIN),
               ("uefa.europa.conf", _EU_MAIN_WIN),
               ("uefa.europa.conf_qual", _EU_QUAL_WIN)]},
    {"key": "france", "name": "Coupe de France pool",
     "parts": [("fra.coupe_de_france",
                [(date(2023, 9, 1), date(2024, 6, 30)),
                 (date(2024, 9, 1), date(2025, 6, 30)),
                 (date(2025, 9, 1), date(2026, 6, 30)),
                 (date(2026, 9, 1), date(2026, 10, 24))])]},
    {"key": "argentina", "name": "Copa Argentina pool",
     "parts": [("arg.copa",
                [(date(2024, 2, 1), date(2024, 12, 31)),
                 (date(2025, 2, 1), date(2025, 12, 31)),
                 (date(2026, 2, 1), date(2026, 10, 24))])]},
]

# NO-SOURCE terminals (Round 3): competitions whose clubs show
# up on FanDuel pulls but for which NO match-level results
# source exists after a genuine search. The record below is
# the evidence trail; the club lists are the distinctive club
# names (as listed on pulls / in the published standings) the
# engine may stamp — the stamp fires only for a club held by
# NO fit, so a fitted club of a similar name is never touched.
NO_SOURCE = {
    "torneo-federal-a": {
        "label": "Torneo Federal A (Argentina)",
        "status": "NO-SOURCE terminal",
        "clubs": ["Ciudad de Bolivar", "Atletico Rafaela",
                  "9 de Julio", "Gimnasia Chivilcoy",
                  "Sportivo Belgrano", "Olimpo", "Cipolletti",
                  "Villa Mitre", "Guillermo Brown",
                  "Douglas Haig", "Juventud Antoniana",
                  "Circulo Deportivo", "Kimberley",
                  "Sol de Mayo", "El Linqueno", "Boca Unidos",
                  "Huracan Las Heras", "Santamarina",
                  "Ben Hur", "Crucero del Norte", "Gutierrez",
                  "Costa Brava", "Deportivo Rincon",
                  "Sarmiento La Banda", "Sportivo Las Parejas"],
        "evidence": "ESPN's core league index (220 leagues, "
                    "fetched 2026-10-24) carries arg.1/arg.2/"
                    "arg.3 (Primera B)/arg.4 (Primera C) and "
                    "NO Federal A slug; arg.3.f and arg.federal "
                    "scoreboard probes return HTTP 400. "
                    "football-data.co.uk carries no Argentine "
                    "league. RSSSF's Argentina 2025 page "
                    "publishes the Federal A final standings "
                    "only — aggregate W/D/L, no match results "
                    "to walk forward. TheSportsDB API answers "
                    "403/400 from this network. No match-level "
                    "source found; the competition is declared, "
                    "not skipped.",
        "stamp": "club plays in Torneo Federal A (Argentina) "
                 "— no match-level results source exists for "
                 "that competition (proven NO-SOURCE terminal, "
                 "see no_source in the leagues file)"},
    "nicaragua-liga-primera": {
        "label": "Liga Primera (Nicaragua)",
        "status": "NO-SOURCE terminal",
        "clubs": ["CD Walter Ferreti", "Rancho Santana",
                  "San Marcos", "Indigenas de Matagalpa FC"],
        "evidence": "Club names as listed on FanDuel pulls of "
                    "2026-10-24. ESPN's core league index "
                    "(220 leagues, fetched 2026-10-24) contains "
                    "NO Nicaraguan league at all; scoreboard "
                    "probes nic.1 / nca.1 / nic.primera / "
                    "nic.liga / nic.pre all return HTTP 400 "
                    "(Rounds 2-3). RSSSF country pages for "
                    "Nicaragua 2023/2024/2025 return 404. "
                    "TheSportsDB API answers 403/400 from this "
                    "network. No machine-readable results "
                    "source found; the competition is declared, "
                    "not skipped.",
        "stamp": "club plays in Liga Primera (Nicaragua) — "
                 "no machine-readable results source exists "
                 "for that league (proven NO-SOURCE terminal, "
                 "see no_source in the leagues file)"},
    # France's tier 3 (Championnat National) has no ESPN
    # slug (index-verified: fra.1/fra.2 only; fra.3 and
    # variants 400) and no football-data file — but its named
    # Round-3 case, Le Mans, was CLOSED by the Coupe de
    # France pool (the fresh 189-game pool holds the club),
    # so no no_source record stands for it: a record for a
    # club that prices would be false on its face. Other
    # tier-3-only clubs carry the generic stamp until a
    # source or a cup pool holds them.
}

# the engine's fit_soccer protocol constants, named once here
SOC_K, SOC_HFA = b5.SOC_K, b5.SOC_HFA
SOC_PRIOR_GAMES = b5.SOC_PRIOR_GAMES
SOC_PRIOR_LH, SOC_PRIOR_LA = b5.SOC_PRIOR_LH, b5.SOC_PRIOR_LA


def fetch_csv(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "BetFi-Xii fit builder "
                                   "(stdlib urllib)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def parse_games(text):
    """football-data rows -> [{home, away, hs, as}] in date order.
    Rows without a full-time score are skipped (postponed /
    unplayed fixtures carry no result to fit on)."""
    games = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            hs = int(float(row["FTHG"]))
            hs_as = int(float(row["FTAG"]))
        except (KeyError, TypeError, ValueError):
            continue
        home = (row.get("HomeTeam") or "").strip()
        away = (row.get("AwayTeam") or "").strip()
        if not home or not away:
            continue
        games.append({"date": row.get("Date") or "",
                      "home": home, "away": away,
                      "hs": hs, "as": hs_as})
    return games


def fit_league(games, source):
    """fit_soccer's walk-forward construction, verbatim in
    structure: strengths() snapshot -> grid prediction -> grade
    the record -> THEN update gp/gf/ga, league totals and Elo."""
    elo, gp, gf, ga = {}, {}, {}, {}
    hg = ag = hgames = 0
    recs = []

    def strengths():
        total_gp = sum(gp.values())
        L = ((sum(gf.values()) / total_gp) if total_gp else 1.35)
        if L <= 0:
            # A season whose opening games are all goalless (the
            # Scottish Premiership 2024-25 file opens 0-0, 0-0)
            # makes the raw rate 0 and the att/def map divide by
            # it. Fall back to the prior scoring rate until the
            # season has a goal — the prior is what a zero-game
            # snapshot already uses, so no fitted league whose
            # early games had goals changes at all.
            L = (SOC_PRIOR_LH + SOC_PRIOR_LA) / 2
        LH = (hg + 10 * SOC_PRIOR_LH) / (hgames + 10) if hgames \
            else SOC_PRIOR_LH
        LA = (ag + 10 * SOC_PRIOR_LA) / (hgames + 10) if hgames \
            else SOC_PRIOR_LA
        st = {}
        for t in gp:
            st[t] = {
                "att": ((gf[t] + SOC_PRIOR_GAMES * L)
                        / (gp[t] + SOC_PRIOR_GAMES)) / L,
                "def": ((ga[t] + SOC_PRIOR_GAMES * L)
                        / (gp[t] + SOC_PRIOR_GAMES)) / L,
                "gp": gp[t]}
        return st, {"LH": LH, "LA": LA, "L": L}

    for g in games:
        for t in (g["home"], g["away"]):
            gp.setdefault(t, 0)
            gf.setdefault(t, 0)
            ga.setdefault(t, 0)
            elo.setdefault(t, 1500.0)
        st, lg = strengths()
        lh, la = b5.soccer_lambdas(st, lg, g["home"], g["away"])
        grid = b5.soccer_grid(lh, la)
        y = (1 if g["hs"] > g["as"] else 0 if g["hs"] == g["as"]
             else -1)
        recs.append({"p_home": grid["p_home"],
                     "p_draw": grid["p_draw"],
                     "p_away": grid["p_away"], "y": y,
                     "pick": max((("home", grid["p_home"]),
                                  ("draw", grid["p_draw"]),
                                  ("away", grid["p_away"])),
                                 key=lambda kv: kv[1])[0]})
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
    return {
        "params": {"K": SOC_K, "hfa_elo": SOC_HFA,
                   "prior_games": SOC_PRIOR_GAMES},
        "source": source,
        "elo": {k: round(v, 1) for k, v in elo.items()},
        "strengths": {k: {"att": round(v["att"], 3),
                          "def": round(v["def"], 3),
                          "gp": v["gp"]}
                      for k, v in st.items()},
        "league": {"LH": round(lg["LH"], 3),
                   "LA": round(lg["LA"], 3),
                   "L": round(lg["L"], 3)},
        "backtest": {"brier3": round(brier3, 4),
                     "accuracy": round(acc, 4),
                     "n": len(recs),
                     "protocol": "walk-forward (strengths/Elo "
                                 "from prior games only)"}}


def fetch_espn_day(slug, day):
    """One ESPN scoreboard day pull -> completed games only, as
    [{date, id, home, away, hs, as}]. Raises on HTTP/parse
    failure so the caller can omit the league honestly."""
    url = (f"{ESPN_SOCCER}/{slug}/scoreboard"
           f"?dates={day.strftime('%Y%m%d')}")
    req = urllib.request.Request(
        url, headers={"User-Agent": "BetFi-Xii fit builder "
                                   "(stdlib urllib)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        blob = json.loads(r.read().decode("utf-8", "replace"))
    games = []
    for ev in blob.get("events") or []:
        try:
            if not (ev.get("status", {}).get("type", {})
                    .get("completed")):
                continue
            comp = (ev.get("competitions") or [{}])[0]
            cs = {c["homeAway"]: c
                  for c in comp.get("competitors") or []}
            home, away = cs["home"], cs["away"]
            games.append({
                "date": day.isoformat(), "id": str(ev.get("id")),
                "home": home["team"]["displayName"],
                "away": away["team"]["displayName"],
                "hs": int(float(home["score"])),
                "as": int(float(away["score"]))})
        except (KeyError, TypeError, ValueError):
            continue
    return games


def fetch_espn_season(slug, windows):
    """Day pulls across every (start, end) window, deduped by
    event id and ordered by (date, id) so the walk-forward is
    deterministic regardless of fetch order."""
    days = []
    for start, end in windows:
        d = start
        while d <= end:
            days.append(d)
            d += timedelta(days=1)
    by_id = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for games in pool.map(
                lambda day: fetch_espn_day(slug, day), days):
            for g in games:
                by_id[g["id"]] = g
    return sorted(by_id.values(),
                  key=lambda g: (g["date"], g["id"]))


def fetch_espn_season_tolerant(slug, windows):
    """Round-2 variant of fetch_espn_season: a single failed day
    (timeout / 5xx on one date in a ~600-day sweep) must not kill
    a whole league. Failed days are COUNTED and returned so the
    fit's provenance states exactly how much of the window was
    actually pulled. Returns (games, failed_days, total_days)."""
    days = []
    for start, end in windows:
        d = start
        while d <= end:
            days.append(d)
            d += timedelta(days=1)

    def one(day):
        try:
            return fetch_espn_day(slug, day), True
        except Exception:
            return [], False

    by_id, failed = {}, 0
    with ThreadPoolExecutor(max_workers=12) as pool:
        for games, ok in pool.map(one, days):
            if not ok:
                failed += 1
            for g in games:
                by_id[g["id"]] = g
    return (sorted(by_id.values(),
                   key=lambda g: (g["date"], g["id"])),
            failed, len(days))


def _csv_date(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y").date().isoformat()
    except (TypeError, ValueError):
        return s or ""


def fit_country_system(games, source):
    """One pool, two tiers. `games` carry a 'tier' tag ('tier1' /
    'tier2') and ISO dates. Strengths and Elo update on the
    SHARED pool (one scale for the whole pyramid); the scoring
    rates accumulate PER TIER, and each game's prediction reads
    its own tier's rates — so the walk-forward grades tier1 and
    tier2 separately on the shared scale. Everything else is
    fit_league's construction verbatim."""
    elo, gp, gf, ga = {}, {}, {}, {}
    thg = {"tier1": 0, "tier2": 0}
    tag_ = {"tier1": 0, "tier2": 0}
    thgames = {"tier1": 0, "tier2": 0}
    team_tier = {}
    recs = []

    def snapshot():
        total_gp = sum(gp.values())
        L = ((sum(gf.values()) / total_gp) if total_gp else 1.35)
        if L <= 0:
            L = (SOC_PRIOR_LH + SOC_PRIOR_LA) / 2
        st = {}
        for t in gp:
            st[t] = {
                "att": ((gf[t] + SOC_PRIOR_GAMES * L)
                        / (gp[t] + SOC_PRIOR_GAMES)) / L,
                "def": ((ga[t] + SOC_PRIOR_GAMES * L)
                        / (gp[t] + SOC_PRIOR_GAMES)) / L,
                "gp": gp[t]}
        rates = {}
        for tier in ("tier1", "tier2"):
            n = thgames[tier]
            rates[tier] = {
                "LH": (thg[tier] + 10 * SOC_PRIOR_LH) / (n + 10)
                      if n else SOC_PRIOR_LH,
                "LA": (tag_[tier] + 10 * SOC_PRIOR_LA) / (n + 10)
                      if n else SOC_PRIOR_LA,
                "L": L}
        return st, rates

    for g in games:
        for t in (g["home"], g["away"]):
            gp.setdefault(t, 0)
            gf.setdefault(t, 0)
            ga.setdefault(t, 0)
            elo.setdefault(t, 1500.0)
        st, rates = snapshot()
        lg = rates[g["tier"]]
        lh, la = b5.soccer_lambdas(st, lg, g["home"], g["away"])
        grid = b5.soccer_grid(lh, la)
        y = (1 if g["hs"] > g["as"] else 0 if g["hs"] == g["as"]
             else -1)
        recs.append({"p_home": grid["p_home"],
                     "p_draw": grid["p_draw"],
                     "p_away": grid["p_away"], "y": y,
                     "tier": g["tier"],
                     "pick": max((("home", grid["p_home"]),
                                  ("draw", grid["p_draw"]),
                                  ("away", grid["p_away"])),
                                 key=lambda kv: kv[1])[0]})
        gp[g["home"]] += 1
        gp[g["away"]] += 1
        gf[g["home"]] += g["hs"]
        ga[g["home"]] += g["as"]
        gf[g["away"]] += g["as"]
        ga[g["away"]] += g["hs"]
        thg[g["tier"]] += g["hs"]
        tag_[g["tier"]] += g["as"]
        thgames[g["tier"]] += 1
        team_tier[g["home"]] = g["tier"]
        team_tier[g["away"]] = g["tier"]
        d = elo[g["home"]] + SOC_HFA - elo[g["away"]]
        exp_h = 1 / (1 + 10 ** (-d / 400))
        score_h = 1.0 if y == 1 else 0.5 if y == 0 else 0.0
        elo[g["home"]] += SOC_K * (score_h - exp_h)
        elo[g["away"]] -= SOC_K * (score_h - exp_h)

    def bt_of(rs):
        if not rs:
            return {"brier3": None, "accuracy": None, "n": 0}
        b = statistics.mean([
            (x["p_home"] - (1 if x["y"] == 1 else 0)) ** 2
            + (x["p_draw"] - (1 if x["y"] == 0 else 0)) ** 2
            + (x["p_away"] - (1 if x["y"] == -1 else 0)) ** 2
            for x in rs])
        a = statistics.mean([
            1.0 if (x["pick"] == "home" and x["y"] == 1)
            or (x["pick"] == "draw" and x["y"] == 0)
            or (x["pick"] == "away" and x["y"] == -1) else 0.0
            for x in rs])
        return {"brier3": round(b, 4), "accuracy": round(a, 4),
                "n": len(rs)}

    st, rates = snapshot()
    by_tier = {t: bt_of([r for r in recs if r["tier"] == t])
               for t in ("tier1", "tier2")}
    for t in by_tier:
        by_tier[t]["protocol"] = (
            "walk-forward, shared pool (strengths/Elo from "
            "prior games only, both tiers)")
    return {
        "params": {"K": SOC_K, "hfa_elo": SOC_HFA,
                   "prior_games": SOC_PRIOR_GAMES},
        "source": source,
        "system": True,
        "elo": {k: round(v, 1) for k, v in elo.items()},
        "strengths": {k: {"att": round(v["att"], 3),
                          "def": round(v["def"], 3),
                          "gp": v["gp"]}
                      for k, v in st.items()},
        "league": {"LH": round(rates["tier1"]["LH"], 3),
                   "LA": round(rates["tier1"]["LA"], 3),
                   "L": round(rates["tier1"]["L"], 3)},
        "tier_rates": {t: {"LH": round(rates[t]["LH"], 3),
                           "LA": round(rates[t]["LA"], 3),
                           "L": round(rates[t]["L"], 3)}
                       for t in rates},
        "team_tier": team_tier,
        "backtest_by_tier": by_tier,
        "backtest": bt_of(recs)}


def fit_pooled_system(games, tiers, source):
    """fit_country_system generalized to N tiers (Round 3,
    Americas pyramids): one shared strengths/Elo pool, scoring
    rates per tier, walk-forward graded per tier and overall.
    `games` carry a 'tier' tag from `tiers`; everything else is
    the two-tier construction verbatim."""
    elo, gp, gf, ga = {}, {}, {}, {}
    thg = {t: 0 for t in tiers}
    tag_ = {t: 0 for t in tiers}
    thgames = {t: 0 for t in tiers}
    team_tier = {}
    recs = []

    def snapshot():
        total_gp = sum(gp.values())
        L = ((sum(gf.values()) / total_gp) if total_gp else 1.35)
        if L <= 0:
            L = (SOC_PRIOR_LH + SOC_PRIOR_LA) / 2
        st = {}
        for t in gp:
            st[t] = {
                "att": ((gf[t] + SOC_PRIOR_GAMES * L)
                        / (gp[t] + SOC_PRIOR_GAMES)) / L,
                "def": ((ga[t] + SOC_PRIOR_GAMES * L)
                        / (gp[t] + SOC_PRIOR_GAMES)) / L,
                "gp": gp[t]}
        rates = {}
        for tier in tiers:
            n = thgames[tier]
            rates[tier] = {
                "LH": (thg[tier] + 10 * SOC_PRIOR_LH) / (n + 10)
                      if n else SOC_PRIOR_LH,
                "LA": (tag_[tier] + 10 * SOC_PRIOR_LA) / (n + 10)
                      if n else SOC_PRIOR_LA,
                "L": L}
        return st, rates

    for g in games:
        for t in (g["home"], g["away"]):
            gp.setdefault(t, 0)
            gf.setdefault(t, 0)
            ga.setdefault(t, 0)
            elo.setdefault(t, 1500.0)
        st, rates = snapshot()
        lg = rates[g["tier"]]
        lh, la = b5.soccer_lambdas(st, lg, g["home"], g["away"])
        grid = b5.soccer_grid(lh, la)
        y = (1 if g["hs"] > g["as"] else 0 if g["hs"] == g["as"]
             else -1)
        recs.append({"p_home": grid["p_home"],
                     "p_draw": grid["p_draw"],
                     "p_away": grid["p_away"], "y": y,
                     "tier": g["tier"],
                     "pick": max((("home", grid["p_home"]),
                                  ("draw", grid["p_draw"]),
                                  ("away", grid["p_away"])),
                                 key=lambda kv: kv[1])[0]})
        gp[g["home"]] += 1
        gp[g["away"]] += 1
        gf[g["home"]] += g["hs"]
        ga[g["home"]] += g["as"]
        gf[g["away"]] += g["as"]
        ga[g["away"]] += g["hs"]
        thg[g["tier"]] += g["hs"]
        tag_[g["tier"]] += g["as"]
        thgames[g["tier"]] += 1
        team_tier[g["home"]] = g["tier"]
        team_tier[g["away"]] = g["tier"]
        d = elo[g["home"]] + SOC_HFA - elo[g["away"]]
        exp_h = 1 / (1 + 10 ** (-d / 400))
        score_h = 1.0 if y == 1 else 0.5 if y == 0 else 0.0
        elo[g["home"]] += SOC_K * (score_h - exp_h)
        elo[g["away"]] -= SOC_K * (score_h - exp_h)

    def bt_of(rs):
        if not rs:
            return {"brier3": None, "accuracy": None, "n": 0}
        b = statistics.mean([
            (x["p_home"] - (1 if x["y"] == 1 else 0)) ** 2
            + (x["p_draw"] - (1 if x["y"] == 0 else 0)) ** 2
            + (x["p_away"] - (1 if x["y"] == -1 else 0)) ** 2
            for x in rs])
        a = statistics.mean([
            1.0 if (x["pick"] == "home" and x["y"] == 1)
            or (x["pick"] == "draw" and x["y"] == 0)
            or (x["pick"] == "away" and x["y"] == -1) else 0.0
            for x in rs])
        return {"brier3": round(b, 4), "accuracy": round(a, 4),
                "n": len(rs)}

    st, rates = snapshot()
    t1 = tiers[0]
    by_tier = {t: bt_of([r for r in recs if r["tier"] == t])
               for t in tiers}
    for t in by_tier:
        by_tier[t]["protocol"] = (
            "walk-forward, shared pool (strengths/Elo from "
            "prior games only, all tiers)")
    return {
        "params": {"K": SOC_K, "hfa_elo": SOC_HFA,
                   "prior_games": SOC_PRIOR_GAMES},
        "source": source,
        "system": True,
        "elo": {k: round(v, 1) for k, v in elo.items()},
        "strengths": {k: {"att": round(v["att"], 3),
                          "def": round(v["def"], 3),
                          "gp": v["gp"]}
                      for k, v in st.items()},
        "league": {"LH": round(rates[t1]["LH"], 3),
                   "LA": round(rates[t1]["LA"], 3),
                   "L": round(rates[t1]["L"], 3)},
        "tier_rates": {t: {"LH": round(rates[t]["LH"], 3),
                           "LA": round(rates[t]["LA"], 3),
                           "L": round(rates[t]["L"], 3)}
                       for t in tiers},
        "team_tier": team_tier,
        "backtest_by_tier": by_tier,
        "backtest": bt_of(recs)}


def main(argv):
    out_path = os.path.join(CLONE, "data", "v5-soccer-leagues.json")
    if "--out" in argv:
        out_path = argv[argv.index("--out") + 1]
    fitted_at = datetime.now().astimezone().isoformat(
        timespec="seconds")
    blob = {"sport": "soccer", "fitted_at": fitted_at,
            "leagues": {}, "control": {},
            "note": "Per-league fits (football-data.co.uk, season "
                    "2024-25; ESPN day-pull leagues as labelled "
                    "per fit). 'systems' holds pooled two-tier "
                    "country fits (shared strengths/Elo scale, "
                    "per-tier rates) used ONLY for cross-tier "
                    "fixtures no single league fit holds; each "
                    "system carries its walk-forward validation "
                    "against the separate fits. 'cups' holds "
                    "pooled cup fits (Round 3): one walk-forward "
                    "pool per cup family, gated by a bar stated "
                    "in each pool's 'gate' block — only a pool "
                    "with gate.ships true may price. "
                    "'no_source' records the competitions "
                    "proven to have no match-level results "
                    "source, with their evidence. 'control' is "
                    "the EPL fitted "
                    "by this "
                    "same code for comparison against the shipped "
                    "v5-soccer.json; the checker never prices "
                    "from control — EPL prices from v5-soccer.json "
                    "exactly as before."}
    # Cup pools are swept FIRST, on a fresh connection budget.
    # The Round-3 run taught the lesson: a cup sweep taken
    # after ~22k league day-pulls comes back load-degraded —
    # empty HTTP-200 days are indistinguishable from genuinely
    # empty days, and Copa Argentina harvested 31 games tired
    # against 180 fresh. Fetch order is therefore data-
    # integrity order; the pools are still FITTED (and gated)
    # at the end, once the league median exists.
    cup_raw = {}
    for spec in CUP_POOLS:
        parts = []
        for slug, windows in spec["parts"]:
            games, failed_days, total_days = \
                fetch_espn_season_tolerant(slug, windows)
            parts.append((slug, games, failed_days, total_days))
        cup_raw[spec["key"]] = parts
        print(f"[CUPS-PRE] {spec['name']}: " + "; ".join(
            f"{s}: {len(g)} games, {f}/{t} day pulls failed"
            for s, g, f, t in parts))
    jobs = [(key, code, name, False)
            for key, (code, name) in LEAGUES.items()]
    jobs.append((CONTROL[0], CONTROL[1], CONTROL[2], True))
    for key, code, name, is_control in jobs:
        url = f"{BASE}/{code}.csv"
        try:
            games = parse_games(fetch_csv(url))
            if len(games) < 50:
                raise ValueError(
                    f"only {len(games)} scored games parsed — "
                    f"too few to fit honestly")
            fit = fit_league(
                games, f"football-data.co.uk results CSV {url}")
            fit["league_name"] = name
            fit["fitted_at"] = fitted_at
            fit["season"] = "2024-25"
        except Exception as e:
            print(f"[FAIL] {name} ({code}): "
                  f"{type(e).__name__}: {e} — league OMITTED, "
                  f"never fabricated")
            continue
        (blob["control"] if is_control else blob["leagues"])[key] \
            = fit
        bt = fit["backtest"]
        print(f"[OK] {name} ({code}): n={bt['n']} games · "
              f"brier3={bt['brier3']} · accuracy={bt['accuracy']} "
              f"· LH={fit['league']['LH']} LA={fit['league']['LA']} "
              f"· teams={len(fit['strengths'])}")
    # ESPN day-pull leagues — MLS was the biggest named bucket
    # on the live coverage queue; Brazil / Liga MX / Argentina
    # are the next ones. All fitted by the identical code.
    # The raw games of every ESPN pass are kept (espn_games) so
    # the Round-3 Americas systems pool the SAME pulls the
    # league fits used — never a second, different fetch.
    espn_games = {}
    for job in ESPN_LEAGUES:
        source = (f"ESPN scoreboard day pulls ({job['slug']}, "
                  f"{job['label']})")
        try:
            games = fetch_espn_season(job["slug"], job["windows"])
            # Exhibition all-star events sit inside season
            # windows as league-slug events (MLS All-Stars vs
            # Liga MX All-Stars, 2025-07-23). They are not
            # league fixtures — excluding them leaves exactly
            # the regular-season games of the member clubs.
            games = [g for g in games
                     if "All-Stars" not in g["home"]
                     and "All-Stars" not in g["away"]]
            if len(games) < 50:
                raise ValueError(
                    f"only {len(games)} completed games pulled "
                    f"— too few to fit honestly")
            fit = fit_league(games, source)
            fit["league_name"] = job["name"]
            fit["fitted_at"] = fitted_at
            fit["season"] = job["season"]
            blob["leagues"][job["key"]] = fit
            espn_games[job["key"]] = games
            bt = fit["backtest"]
            print(f"[OK] {job['name']} (ESPN {job['slug']}): "
                  f"n={bt['n']} games · brier3={bt['brier3']} · "
                  f"accuracy={bt['accuracy']} "
                  f"· LH={fit['league']['LH']} "
                  f"LA={fit['league']['LA']} "
                  f"· teams={len(fit['strengths'])}")
        except Exception as e:
            print(f"[FAIL] {job['name']} (ESPN {job['slug']}): "
                  f"{type(e).__name__}: {e} — league OMITTED, "
                  f"never fabricated")
    # Round 2 ESPN leagues — tolerant day fetching (failed days
    # counted in the fit's provenance, never silently dropped).
    for job in ESPN_LEAGUES_R2:
        try:
            games, failed_days, total_days = \
                fetch_espn_season_tolerant(job["slug"],
                                           job["windows"])
            games = [g for g in games
                     if "All-Stars" not in g["home"]
                     and "All-Stars" not in g["away"]]
            if len(games) < 50:
                raise ValueError(
                    f"only {len(games)} completed games pulled "
                    f"— too few to fit honestly")
            source = (f"ESPN scoreboard day pulls "
                      f"({job['slug']}, {job['label']}; "
                      f"{failed_days} of {total_days} day pulls "
                      f"failed and were re-counted as absent, "
                      f"not filled)")
            fit = fit_league(games, source)
            fit["league_name"] = job["name"]
            fit["fitted_at"] = fitted_at
            fit["season"] = job["season"]
            blob["leagues"][job["key"]] = fit
            espn_games[job["key"]] = games
            bt = fit["backtest"]
            print(f"[OK] {job['name']} (ESPN {job['slug']}): "
                  f"n={bt['n']} games · brier3={bt['brier3']} · "
                  f"accuracy={bt['accuracy']} "
                  f"· LH={fit['league']['LH']} "
                  f"LA={fit['league']['LA']} "
                  f"· teams={len(fit['strengths'])} "
                  f"· failed_days={failed_days}/{total_days}")
        except Exception as e:
            print(f"[FAIL] {job['name']} (ESPN {job['slug']}): "
                  f"{type(e).__name__}: {e} — league OMITTED, "
                  f"never fabricated")
    # Country systems: both tiers of one pyramid in ONE pool.
    # Ships only if the pooled walk-forward on top-tier games is
    # within SYSTEM_TIER1_TOLERANCE (brier3) of the separate
    # top-tier fit — otherwise the country keeps separate fits
    # and cross-tier fixtures keep their named split reason.
    blob["systems"] = {}
    for spec in COUNTRY_SYSTEMS:
        try:
            pooled = []
            for code, tier in (spec["tier1"], spec["tier2"]):
                rows = parse_games(fetch_csv(f"{BASE}/{code}.csv"))
                if len(rows) < 50:
                    raise ValueError(
                        f"{code}: only {len(rows)} games — too "
                        f"few for a system fit")
                for r in rows:
                    r["date"] = _csv_date(r["date"])
                    r["tier"] = tier
                pooled.extend(rows)
            pooled.sort(key=lambda g: (g["date"], g["home"]))
            source = (f"football-data.co.uk results CSVs "
                      f"{BASE}/{spec['tier1'][0]}.csv + "
                      f"{BASE}/{spec['tier2'][0]}.csv, pooled "
                      f"(shared strengths/Elo scale, per-tier "
                      f"scoring rates)")
            fit = fit_country_system(pooled, source)
            fit["league_name"] = spec["name"]
            fit["fitted_at"] = fitted_at
            fit["season"] = "2024-25"
            sep1 = (blob["control"].get("epl")
                    if spec["sep1"] is None
                    else blob["leagues"].get(spec["sep1"]))
            sep2 = blob["leagues"].get(spec["sep2"])
            t1 = fit["backtest_by_tier"]["tier1"]
            t2 = fit["backtest_by_tier"]["tier2"]
            d1 = (round(t1["brier3"] - sep1["backtest"]["brier3"],
                        4) if sep1 and t1["brier3"] is not None
                  else None)
            d2 = (round(t2["brier3"] - sep2["backtest"]["brier3"],
                        4) if sep2 and t2["brier3"] is not None
                  else None)
            fit["validation"] = {
                "tier1_brier3_system": t1["brier3"],
                "tier1_brier3_separate": (
                    sep1["backtest"]["brier3"] if sep1 else None),
                "tier1_delta": d1,
                "tier2_brier3_system": t2["brier3"],
                "tier2_brier3_separate": (
                    sep2["backtest"]["brier3"] if sep2 else None),
                "tier2_delta": d2,
                "tolerance": SYSTEM_TIER1_TOLERANCE,
                "rule": "system ships iff tier1_delta <= "
                        "tolerance"}
            if d1 is not None and d1 > SYSTEM_TIER1_TOLERANCE:
                print(f"[HELD] {spec['name']}: pooled tier1 "
                      f"brier3 {t1['brier3']} vs separate "
                      f"{sep1['backtest']['brier3']} "
                      f"(delta {d1} > {SYSTEM_TIER1_TOLERANCE}) "
                      f"— separate fits kept, cross-tier "
                      f"fixtures keep the named split reason")
                continue
            blob["systems"][spec["key"]] = fit
            print(f"[OK] SYSTEM {spec['name']}: teams="
                  f"{len(fit['strengths'])} · tier1 brier3="
                  f"{t1['brier3']} (separate "
                  f"{fit['validation']['tier1_brier3_separate']}"
                  f", delta {d1}) · tier2 brier3={t2['brier3']}"
                  f" (separate "
                  f"{fit['validation']['tier2_brier3_separate']}"
                  f", delta {d2}) · n={fit['backtest']['n']}")
        except Exception as e:
            print(f"[FAIL] SYSTEM {spec['name']}: "
                  f"{type(e).__name__}: {e} — system OMITTED, "
                  f"separate fits stand")
    # Americas country systems (Round 3): the European pooled
    # recipe over the ESPN passes' own games. Same ship gate
    # (pooled tier-1 brier3 within +0.01 of the separate tier-1
    # fit); a held system's validation is written to
    # systems_held WITHOUT strengths — on record, never priced.
    blob.setdefault("systems_held", {})
    for spec in AMERICAS_SYSTEMS:
        try:
            pooled, tiers = [], []
            for lkey, tier in spec["members"]:
                if lkey not in espn_games:
                    raise ValueError(
                        f"member league {lkey} was not fitted "
                        f"— system cannot pool what it lacks")
                tiers.append(tier)
                for g in espn_games[lkey]:
                    pooled.append({**g, "tier": tier})
            pooled.sort(key=lambda g: (g["date"],
                                       g.get("id") or "",
                                       g["home"]))
            srcs = " + ".join(
                f"{lkey} ({blob['leagues'][lkey]['source']})"
                for lkey, _t in spec["members"])
            source = (f"ESPN scoreboard day pulls, pooled "
                      f"country system (shared strengths/Elo "
                      f"scale, per-tier scoring rates): {srcs}")
            fit = fit_pooled_system(pooled, tiers, source)
            fit["league_name"] = spec["name"]
            fit["fitted_at"] = fitted_at
            fit["season"] = "2025+2026"
            t1key = spec["members"][0][0]
            sep1 = blob["leagues"][t1key]
            validation = {"tolerance": SYSTEM_TIER1_TOLERANCE,
                          "rule": "system ships iff tier1_delta "
                                  "<= tolerance",
                          "tier1_separate_key": t1key}
            for lkey, tier in spec["members"]:
                bt_t = fit["backtest_by_tier"][tier]
                sep = blob["leagues"][lkey]["backtest"]
                validation[f"{tier}_brier3_system"] = \
                    bt_t["brier3"]
                validation[f"{tier}_brier3_separate"] = \
                    sep["brier3"]
                validation[f"{tier}_delta"] = (
                    round(bt_t["brier3"] - sep["brier3"], 4)
                    if bt_t["brier3"] is not None else None)
            fit["validation"] = validation
            d1 = validation["tier1_delta"]
            if d1 is not None and d1 > SYSTEM_TIER1_TOLERANCE:
                blob["systems_held"][spec["key"]] = {
                    "league_name": spec["name"],
                    "validation": validation,
                    "reason": "pooled tier-1 walk-forward worse "
                              "than the separate tier-1 fit by "
                              "more than the stated tolerance — "
                              "separate fits kept, cross-tier "
                              "fixtures keep the named split "
                              "reason"}
                print(f"[HELD] SYSTEM {spec['name']}: tier1 "
                      f"delta {d1} > {SYSTEM_TIER1_TOLERANCE} "
                      f"— separate fits kept")
                continue
            blob["systems"][spec["key"]] = fit
            print(f"[OK] SYSTEM {spec['name']}: teams="
                  f"{len(fit['strengths'])} · " + " · ".join(
                      f"{t} brier3="
                      f"{fit['backtest_by_tier'][t]['brier3']} "
                      f"(separate "
                      f"{validation[f'{t}_brier3_separate']}, "
                      f"delta {validation[f'{t}_delta']})"
                      for _k, t in spec["members"])
                  + f" · n={fit['backtest']['n']}")
        except Exception as e:
            print(f"[FAIL] SYSTEM {spec['name']}: "
                  f"{type(e).__name__}: {e} — system OMITTED, "
                  f"separate fits stand")
    # Cup pools (Round 3): one pooled walk-forward fit per cup
    # family. The bar is computed from THIS run's league fits
    # (median brier3 + CUP_POOL_TOLERANCE, stated in advance of
    # the pool runs). Ships or held, the pool is written with
    # its gate — the engine prices only a shipped pool.
    blob["cups"] = {}
    league_briers = sorted(
        lg["backtest"]["brier3"]
        for lg in blob["leagues"].values()
        if lg.get("backtest", {}).get("brier3") is not None)
    median_brier = statistics.median(league_briers) \
        if league_briers else None
    cup_bar = (round(median_brier + CUP_POOL_TOLERANCE, 4)
               if median_brier is not None else None)
    print(f"Cup pool bar: median league brier3 {median_brier} "
          f"+ {CUP_POOL_TOLERANCE} = {cup_bar}")
    for spec in CUP_POOLS:
        try:
            pooled, failed_note = [], []
            for slug, games, failed_days, total_days in \
                    cup_raw.get(spec["key"], []):
                pooled.extend(games)
                failed_note.append(
                    f"{slug}: {failed_days}/{total_days} day "
                    f"pulls failed")
            by_id = {}
            for g in pooled:
                by_id[g["id"]] = g
            pooled = sorted(by_id.values(),
                            key=lambda g: (g["date"], g["id"]))
            pooled = [g for g in pooled
                      if "All-Stars" not in g["home"]
                      and "All-Stars" not in g["away"]]
            if len(pooled) < 50:
                # Too thin to fit honestly — but the attempt
                # is data: record it in the artifact rather
                # than letting it vanish into a log line.
                blob.setdefault("cups_attempted", {})[
                    spec["key"]] = {
                    "league_name": spec["name"],
                    "competitions": [s for s, _w in
                                     spec["parts"]],
                    "games_pulled": len(pooled),
                    "minimum": 50,
                    "fitted_at": fitted_at,
                    "outcome": "not fitted — the source's day "
                               "archive yielded fewer completed "
                               "games than the honesty floor; "
                               "the pool prices nothing and its "
                               "fixtures keep their named "
                               "reasons"}
                print(f"[THIN] CUP POOL {spec['name']}: only "
                      f"{len(pooled)} completed games pulled "
                      f"(< 50 floor) — attempt recorded in "
                      f"cups_attempted, not fitted")
                continue
            source = (f"ESPN scoreboard day pulls, pooled cup "
                      f"fit ({'; '.join(s for s, _w in spec['parts'])}"
                      f", 2023-24 .. 2026-27 to date; "
                      + "; ".join(failed_note) + ")")
            fit = fit_league(pooled, source)
            bt = fit["backtest"]
            ships = (cup_bar is not None
                     and bt["brier3"] <= cup_bar)
            fit["league_name"] = spec["name"]
            fit["fitted_at"] = fitted_at
            fit["season"] = "2023-24 .. 2026-27"
            fit["competitions"] = [s for s, _w in spec["parts"]]
            fit["gate"] = {
                "median_league_brier3": median_brier,
                "tolerance": CUP_POOL_TOLERANCE,
                "bar": cup_bar,
                "pool_brier3": bt["brier3"],
                "ships": bool(ships),
                "rule": "pool prices iff its walk-forward "
                        "brier3 <= median league brier3 + "
                        "tolerance (bar stated before the run)"}
            blob["cups"][spec["key"]] = fit
            print(f"[{'OK' if ships else 'HELD'}] CUP POOL "
                  f"{spec['name']}: n={bt['n']} · brier3="
                  f"{bt['brier3']} · accuracy={bt['accuracy']} "
                  f"· teams={len(fit['strengths'])} · bar="
                  f"{cup_bar} · ships={bool(ships)}")
        except Exception as e:
            print(f"[FAIL] CUP POOL {spec['name']}: "
                  f"{type(e).__name__}: {e} — pool OMITTED, "
                  f"fixtures keep their split reason")
    # NO-SOURCE terminals: the evidence record ships in the
    # artifact so the engine's stamps and the coverage report
    # name these competitions instead of a bare 'not in fit'.
    blob["no_source"] = NO_SOURCE
    if not blob["leagues"]:
        print("No league fitted — file NOT written.")
        return 1
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=1)
    print(f"Wrote {out_path}: leagues="
          f"{sorted(blob['leagues'])} control="
          f"{sorted(blob['control'])} systems="
          f"{sorted(blob.get('systems') or {})} "
          f"systems_held={sorted(blob.get('systems_held') or {})} "
          f"cups={sorted(blob.get('cups') or {})} "
          f"no_source={sorted(blob.get('no_source') or {})}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
