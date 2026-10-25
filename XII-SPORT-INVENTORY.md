# BetFi Xii — FanDuel Sport Inventory (fix-guy, 2026-10-24)

R3 UPDATE (fix-guy, 2026-10-24): the head-to-head sports got
their Elo lanes — one model family (sequential Elo,
walk-forward vs the naive running-win-rate baseline), fitted
honestly per sport:

- **Tennis — FITTED, PRICING.** data/v5-tennis.json
  (tools/fit_tennis.py). NOTE on the assigned source: Jeff
  Sackmann's original GitHub repos (JeffSackmann/tennis_atp,
  tennis_wta) are GONE — deleted by the owner (verified
  2026-10-24: his account lists only
  tennis_MatchChartingProject; the raw CSV URLs 404). The
  ATP fit uses his CSVs via the public mirror
  bornamilkovic/ATP-Matches (data/atp_matches_2015..2024.csv,
  Sackmann schema verbatim, n=26,896: walk-forward Brier
  0.2182 vs naive 0.2353, acc 0.6425 — PASS). The WTA fit
  uses the tennis-data.co.uk archive format via
  fmmarino1/wta-tennis (wta.csv, 2015+, n=25,526: Brier
  0.2201 vs naive 0.2353, acc 0.6407 — PASS). Per-surface
  ratings are fitted and carried (their walk-forward block
  is reported in the fit file) but NOT priced from — a
  slate entry carries no surface, and its diagnostic Brier
  (ATP 0.2197 / WTA 0.2229) did not beat the overall model
  anyway; no variant was tuned to change that. Fresh live
  pull (1,589 markets): tennis moneylines 106/124 PRICED
  (53/62 fixtures). The 18 unpriced: 5 doubles pairs (not
  singles players), challenger/junior names with no
  main-tour archive record (named per player).
- **MMA — FITTED, FAILED-EXAM (terminal until a refit
  passes).** data/v5-mma.json (tools/fit_mma.py) from
  raw_total_fight_data.csv (ufcstats.com scrape; Kaggle
  rajeevratan84/ufcdata via GitHub mirror
  pantazos/kaggle-UFC-data-CSV): 5,902 decided fights
  (110 draws/NC excluded), fighter Elo K=32 — walk-forward
  Brier 0.2454 vs naive 0.2451. The Elo did NOT beat the
  naive career-win-rate baseline, so the lane stamps
  FAILED-EXAM with those numbers and prices nothing (all
  28 live markets). No K/window variant was tried to flip
  the sign — house law. Named gaps inside the failure: the
  mirror snapshot ends 2021 (only 8/28 fighters on the live
  card resolve at all), so the refit closer is a fresher
  source first, richer model second. Method-of-victory /
  round markets stay UNPRICED with their named closers
  (the source carries win_by; a finish distribution is a
  separate fit).
- **Table tennis — ATTEMPTED, no source (stays named).**
  GitHub repo/code search + web search: the one ITTF
  scrape repo (romanzdk/ittf-data-scrape) carries weekly
  RANKINGS snapshots, not match results; WTT/ITTF match
  results sit behind paid data APIs. The FanDuel cell is
  Polish TT-Cup-level fixtures — no public results archive
  covers it. Closer unchanged in substance: a public
  ITTF/WTT match-results archive.
- **Snooker — ATTEMPTED, source gated (stays named).**
  api.snooker.org requires an approved X-Requested-By
  header value (registration-gated, per its own API page;
  ungated calls return 401) and no GitHub match-results
  CSV exists. Closer: snooker.org API approval or a public
  results archive.
- **Darts — ATTEMPTED, no source (stays named).** The
  OpenDarts repo is empty (0-byte readme, no data); the
  only PDC data found is a single-tournament Kaggle export
  (Players Championship 2024). The live cell is 1 futures
  market (PDC World Championship outright). Closer: a
  maintained public PDC results history.

R4 is STAGED for Coder Guy (starts when R3 lands): the
team-sport remainder (golf groups, boxing, cricket, both
rugbys, lacrosse NLL, motor sport), NBA-page competition
truth for props/team markets, the MLB coverage-resolver
alignment, and pack-seeding recursion for the gamelog
cache in main.py.

R2 UPDATE (fix-guy, 2026-10-24): the NOT-PULLED bucket is
CLOSED. All 12 unfetched event types are wired into
FANDUEL_EVENT_TYPES / FD_TREE_ROUTES and pull_menu() fetches
every one of them on the same sbapi SPORT-page route. A/B live
pull, same methodology minutes apart: 1,173 markets (5-sport
pull) -> 1,591 markets (17-sport pull), +418 markets arriving
from the 12 new sports (tennis 126, golf 104, boxing 66,
cricket 34, MMA 28, table tennis 24, motor sport 22,
rugby league 6, rugby union 3, lacrosse 2, snooker 2, darts 1).
Every new-sport market stamps UNPRICED with the sport-level
named reason ("no checker registered for <sport> yet — see
coverage queue"; outrights stamp the futures reason). Baseball
also gained a fit in R2 (v5-mlb.json — see the inventory row).
The table below is the R1 record; the (a)/(c) columns for the
12 sports now read YES / UNPRICED-named.

Source of the sport list: FanDuel's own menu tree —
`application-context` EVENT_TYPES + AZ_BETTING, fetched **live**
from this worktree on 2026-10-24 (sbapi.mi.sportsbook.fanduel.com).
The tree names **17 event types**. The tree decides this list.

For every sport: (a) does `pull_menu()` fetch its page today,
(b) does a checker/fit exist, (c) what a market for it stamps
today. `pull_menu()` iterates `FANDUEL_EVENT_TYPES`, which has
exactly 5 entries — so 5 of 17 tree pages are ever fetched.

| eventTypeId | FanDuel sport | (a) Pulled today | (b) Checker / fit | (c) Stamp today |
|---|---|---|---|---|
| 6423 | American Football | YES (as nfl+ncaaf) | NFL phi/Elo + margin distribution; CFB distributional ratings + margin lane | Priced where the fits hold; UNPRICED with the missing piece named |
| 7522 | Basketball | YES (as nba) | NBA Elo + margin map (NBA teams only — WNBA/NBL teams on this page are not the NBA fit; coverage now names their competition) | Priced for NBA fixtures; UNPRICED otherwise, competition named |
| 7524 | Ice Hockey | YES (as nhl) | NHL Elo, moneyline only | Priced for NHL fixtures; UNPRICED otherwise (AHL/NCAA hockey named as their competition in coverage) |
| 7511 | Baseball | YES (as mlb) | MLB Elo + runs model (v5-mlb.json, R2 — ESPN 2025 season, walk-forward vs naive in the fit file) | Moneylines PRICED where the fit holds and its walk-forward passed; run-line/totals UNPRICED named. Remaining closer: totals distribution + starting-pitcher adjustment |
| 1 | Soccer | YES | Per-league Poisson goals grid + Elo (EPL + leagues file) | Priced where a league fit holds both teams; UNPRICED named |
| 2 | Tennis | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: per-player surface-specific Elo (hard/clay/grass) from ATP/WTA results history |
| 26420387 | Mixed Martial Arts | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: per-fighter history fit (record, finish rates, weight class) from a public stats source (e.g. UFCStats) |
| 3 | Golf | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: course-fit strokes-gained model from PGA Tour round history |
| 6 | Boxing | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: per-fighter Elo + finish-rate fit from bout history (thin public data) |
| 4 | Cricket | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: per-team format-specific ratings (T20/ODI/Test separately) from results history |
| 3503 | Darts | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: per-player 3-dart-average / checkout-% distributions from PDC results |
| 8 | Motor Sport | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: per-driver/team pace model per series (F1 and NASCAR are separate fits) from race history |
| 5 | Rugby Union | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: per-team Elo + scoring (Poisson) fit for rugby union from results history |
| 1477 | Rugby League | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: per-team Elo + scoring (Poisson) fit for rugby league from results history |
| 28608997 | Lacrosse | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: per-team Elo per league (PLL/NLL separate) from results history (thin public data) |
| 6422 | Snooker | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: per-player frame-level Elo from match history |
| 2593174 | Table Tennis | **NO — NOT PULLED** | none | Invisible — never fetched. Closer: per-player Elo from ITTF/WTT results history (thin public data) |

## The headline

- **12 of FanDuel's 17 sports are NOT PULLED** — Tennis, MMA,
  Golf, Boxing, Cricket, Darts, Motor Sport, Rugby Union,
  Rugby League, Lacrosse, Snooker, Table Tennis. Their markets
  never reach the app; they are not UNPRICED, they are absent.
  This is the deepest coverage gap in the app and it was
  invisible until the tree was enumerated against the pull.
- 1 pulled sport (Baseball) has no fit at all.
- `betmodel5.sport_inventory()` returns this table from the
  engine (tree captured in `FD_EVENT_TYPE_NAMES`, closers in
  `SPORT_CLOSERS`), and `universal_coverage()` now appends one
  NOT-PULLED row per unfetched sport, so the gap is named
  wherever coverage is read — including the queue below.

Regenerate the tree half: fetch application-context and call
`build_menu_tree()`; if FanDuel adds a sport, it appears here
as NOT PULLED until someone routes and fits it.

---

## R4 addendum (fix-guy, 2026-10-24)

Every sport that arrived with R2's pull expansion now has a
fitted + examined lane or a named terminal with evidence
(full table in XII-COVERAGE-QUEUE.md's R4 addendum):

- **Cricket — FITTED (Cricsheet).** 11 format lanes; the six
  lanes the live board uses most (t20i_m/f, odi_m/f, test_m
  three-way with a fitted draw rate, csa_t20) PASS and price
  — 24 of the pull's 34 cricket markets priced. bbl/wbbl/
  ipl/lista_m/test_f FAILED-EXAM and stamp with numbers.
  Source gap: the archive snapshot has no Afghanistan.
- **Rugby union — FITTED (NPC only).** Elo + margin map from
  Wikipedia Bunnings NPC rugbybox data; PASS (thin) — the
  NPC final's spread prices. Other competitions name
  themselves unfitted; the Six Nations outright arrives and
  stamps as an outright.
- **Rugby league — FITTED, FAILED-EXAM.** International
  Elo pools (RLP archive), men 0.2392 vs 0.2308, women
  0.2377 vs 0.2354. Stamps with numbers; outrights named.
- **Motorsport — F1 FITTED, FAILED-EXAM; NASCAR terminal.**
  Driver Elo cannot beat the win-share favorite baseline in
  a constructor sport (log-loss 2.5036 vs 2.0574). NASCAR
  results exist only as R data files — named closer.
- **Golf — SOURCE TERMINAL.** DataGolf is key-gated (403);
  no honest group-form exam exists without full-field
  finishes. Group/top-region forms named, nothing priced.
- **Boxing — SOURCE TERMINAL.** BoxRec 403 on every route;
  the public GitHub candidate is a 78-fight subset. No Elo
  on toy data.
- **Lacrosse — FORM TERMINAL.** The arriving markets are
  season outrights; a team Elo is not an outright price.
  Closer: an NLL season simulator.

Parser (R4): every slate entry now carries FanDuel's own
competition name/id; Test cricket's Draw runner arrives as
a priced leg; outrights for the R4 sports arrive as futures
entries WITH their runner lists (names + prices) instead of
being dropped or collapsed.

## R5 addendum (fix-guy, 2026-10-24) — the market forms

R5 closed the remaining FORMS (alt lines, segments, futures)
across the lanes that already had distributions:

- **Alt lines — WIRED (parity-proven).** Alt-spread and
  alt-total route through the SAME distribution functions
  as the straight forms; at the main line the alt price
  equals the straight price to Δp = 0.0 (8-case battery:
  NFL/NCAAF/NBA spreads, NFL/NCAAF/NBA/soccer totals);
  cross-parity against the totals lane's own engine on 42
  fixture/line combos matched exactly.
- **US totals — FITTED (v5-totals-*.json).** NFL PASS
  (thin), NCAAF PASS (thin), NBA PASS — straight and alt
  totals price. NHL FAILED-EXAM (refit attempt 2: Brier
  0.2626 vs naive 0.2509) and MLB FAILED-EXAM (0.2533 vs
  0.2511) stamp with numbers and never price.
- **Segments — EXAMINED.** NBA 1H, NFL 1H and NHL first-
  period totals all FAILED-EXAM vs the scaled-full-game
  naive (segment-specific team rates do not beat the
  scaled baseline; numbers in v5-segments.json). Soccer
  first halves: fitted half-share per league, joint bar
  (1H-total AND 1H-result vs the fixed-0.44 naive) — 4 of
  16 leagues FITTED (Championship, Serie B, La Liga,
  Eredivisie); the 1H-result cell beat the naive in all
  16 — a per-form bar is the named closer for the rest.
- **F1 — FAILED-EXAM, TERMINAL.** The one allowed refit
  (driver Elo from teammate head-to-heads + shrunk
  constructor effect) improved log-loss 2.5036 → 2.2126
  and still lost to the win-share naive (2.0574). Both
  attempts are in the stamp chain; the lane is closed.
- **Soccer outrights — PILOT PASSED, WIRED.** Monte Carlo
  season simulation from fitted strengths beat the
  standings-share naive on Brier AND log-loss in 3/3 EPL
  backtest seasons (means 0.3532 vs 0.8953, 0.6240 vs
  2.5225). Premier League title outrights price per runner
  at the simulated share; other leagues name the pilot's
  scope as their closer.

Fresh-pull receipt (2026-10-24 23:38Z, 1,562 markets,
pre-R5 engine vs R5 engine on the same pull): **476 →
537 priced (+61)** — NFL totals 0→27/27, NCAAF totals
0→26/28 (the two unpriced are CFL fixtures, competition
named), NBA totals 0→8/11 (the three unpriced are
WNBA/NBL fixtures, competition named); every other cell
identical. Futures entries on the pull (151 across golf /
motorsport / lacrosse / darts / rugby) stay named —
they arrive collapsed; soccer outrights price when a
runner selection rides along. Battery invariance vs the
R4 canonical battery: 511/511 priced items keep their
exact probability; 71 newly priced, all US totals
(n = 582).

## R6 addendum (fix-guy, 2026-10-24) — the closer round

- **Soccer 1H, per-form exams — SPLIT AND WIRED.** The R6
  bar was pre-stated before the builder re-ran: 1H result
  passes iff its walk-forward Brier3 beats the fixed-share
  naive's; 1H total passes iff its Brier beats the
  0.44-share naive's. The exam reproduced R5's numbers
  exactly. **Result: 16/16 leagues PASS. Total: 4/16 PASS**
  (Championship, Serie B, La Liga, Eredivisie — the R5
  joint-passed four keep both forms). The other 12 leagues
  now price their 1H result + 1H handicap forms; their 1H
  totals stamp FAILED-EXAM quoting BOTH forms' numbers.
  (Primeira Liga's total is an exact tie, 0.2207 vs
  0.2207 — a tie is not a beat, so it stamps.)
- **NCAAF segments — EXAMINED.** ESPN FBS linescores,
  seasons 2024+2025: coverage 1,878 events seen / 1,878
  usable (100% — the thin-coverage case did not arise).
  1H exam, same scaled-naive bar: **FAILED-EXAM** (n=1,778:
  total MAE 8.953 vs 8.758, margin Brier 0.2245 vs
  0.2160; loses all four cells). The cell is terminal
  with numbers, not an assumption.
- **Quarter forms — EXAMINED.** NBA 1Q and NFL 1Q ran the
  same segment machinery under the share-scaled naive:
  both **FAILED-EXAM** (NBA 1Q n=2,519 — total Brier won
  0.2450 vs 0.2471, the other three cells lost; NFL 1Q
  n=512 — total Brier won 0.2303 vs 0.2374, MAEs and
  margin Brier lost). Quarter cells now carry exams.
- **Outrights beyond the EPL — PER-LEAGUE EXAMS.**
  La Liga PASS (2/3), Bundesliga PASS (3/3), Serie A
  PASS (2/3), Ligue 1 PASS (3/3) — live artifacts built,
  title outrights price per runner at the simulated
  shares. **MLS FAILED-EXAM (1/3; mean Brier 1.0244 vs
  naive 0.9533)** — the Cup-bracket simulation ran the
  full protocol (2023-25, wild card + best-of-3 +
  shootouts) and lost: MLS playoff parity defeats the
  mid-season standings sim on Brier. MLS outrights stamp
  the league's own numbers. Title winner only, as
  piloted; relegation / top-4 / golden boot stay named.
- **Tennis outrights — FORM TERMINAL.** Tournament
  winners are draw-dependent knockout prices; the
  arriving entries carry runners + prices only (no draw,
  no bracket path, no surface split), so no honest
  number exists and raw Elo title shares are refused.
  Closer named: a draw-aware tournament simulator.
