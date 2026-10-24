# BetFi Xii — FanDuel Sport Inventory (fix-guy, 2026-10-24)

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
