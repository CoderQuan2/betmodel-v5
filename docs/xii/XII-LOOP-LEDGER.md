# BetFi Xii — Laziness-Closing Loop Ledger
Pilot standing order 2026-10-24: "Keep them in loops closing until we meet all."
Three coders (X, Guy, Glow), one purpose: close UNPRICED cells with real,
fitted, backtested math. Praxis merges + verifies between rounds and
re-dispatches each coder onto the next tranche of the coverage queue
WITHOUT waiting for a new instruction.

## Loop exit condition ("meet all")
Every (sport, league, bet-type) cell in the FanDuel sport inventory ends in
exactly one terminal state:
- PRICED — fitted from real history, walk-forward backtest passed vs the
  naive baseline, numbers printed; OR
- FAILED-EXAM — math was built and honestly failed its backtest; numbers
  printed, stays UNPRICED until a refit passes; OR
- NON-STATISTICAL — proven one-off/novelty market with no fittable process.
No NOT-BUILT / NOT-PULLED cell may remain. The pre-push ALL-LEAGUES list is
generated from the final inventory, and the Xii push waits for this ledger
to show zero NOT-BUILT cells (FAILED-EXAM and NON-STATISTICAL cells are
listed to the Pilot by name on that list).

## Round 1 (dispatched 2026-10-24 ~17:54 ET)
- Coder X (soccer): alias layer (AC Milan/Man Utd forms), MLS fit first,
  then remaining soccer leagues by downloadable source. Worktree xii-fix-x.
- Coder Guy (US membership + inventory): checker-vs-coverage truth for
  NCAAF/NFL/NBA/NHL, one canonical resolver per lane, league-truth naming
  (CFL/AHL/NBL named, not blamed on the wrong fit), FULL FanDuel sport
  inventory (pulled / not-pulled / fit states + named closers, incl. UFC).
  Worktree xii-fix-guy.
- Coder Glow (totals): totals distributions for NCAAF/NFL/NBA from real
  history, walk-forward vs naive, FAILED-EXAM stamps where they fail.
  Worktree xii-fix-glow.

## Pre-staged Round 2 tranches (assigned on each coder's Round-1 landing)
- X: remaining soccer competitions from the inventory (Brazil/Argentina/
  Mexico/USL/women's leagues by source), then soccer totals/handicap
  coherence where the grid supports it.
- Guy: pull expansion — wire the NOT-PULLED sports into pull_menu so they
  at least arrive and stamp (UFC, tennis, golf, boxing, racing, darts),
  then MLB fit attempt from real results history.
- Glow: NHL totals (if data supports), props coverage — gamelog fetching
  for players named on the pull so prop cells close player by player.

## Loop log
- 2026-10-24 17:54 — Round 1 dispatched (3 agents, worktrees created by agents).
- 2026-10-24 17:58 — Pilot added UFC/all-sports inventory to Guy's lane.
- 2026-10-24 18:00 — Pilot ordered the loop itself: keep closing until all met.
- 2026-10-24 18:04 — GUY ROUND 1 LANDED + PRAXIS-VERIFIED (spot checks reproduced: Alabama@Georgia spread PRICED 0.545, 76ers@Bulls PRICED, GT@BC 0.5444). Diagnosis: NCAAF checker substring-ambiguity SystemExit + coverage exact-match bug (both layers), NBA checker code-vs-name, NFL full-names/off-slate, NHL blame-only. Fixes: canonical resolver + 37 CFB aliases + NBA code table + competition-truth naming (CFL/AHL/NCAA hockey/WNBA/NBL) + NFL ML from fitted ratings. Counts: saved pull 116→256/355; live pull 148→321/834. Inventory: 17 FanDuel event types, 12 NOT PULLED named (Tennis, MMA, Golf, Boxing, Cricket, Darts, Motor Sport, Rugby Union, Rugby League, Lacrosse, Snooker, Table Tennis).
- 2026-10-24 18:05 — GUY ROUND 2 DISPATCHED (same worktree): pull expansion for the 12 not-pulled sports (invisible -> named), MLB fit attempt (ESPN season, walk-forward), NFL spread pricing from fitted ratings w/ validation vs saved fairs.
- 2026-10-24 18:05 — GLOW ROUND 1 LANDED + PRAXIS-VERIFIED (NBA total PRICED 0.4623; NFL total PRICED on code names; NCAAF total PRICED; NHL total stamps FAILED-EXAM w/ numbers). NFL totals PASS thin (WF MAE 10.492 vs naive 10.572, Brier 0.2475 vs 0.2494, n=512; also beats naive on real closing lines), NCAAF PASS thin (12.773 vs 12.861; 0.2415 vs 0.2502), NBA PASS solid (15.149 vs 16.018; 0.2327 vs 0.2500). NHL totals FAILED-EXAM terminal-candidate (MAE tie 1.841, Brier 0.2514 vs naive 0.2509, n=1252 — team rates add nothing; goalie variance dominates). Known cross-worktree item: NFL full-name totals await Guy's canonical resolver at merge (Glow flag #3, shared resolver). Glow flags: pack-seeding must copy v5-totals-*.json; team totals = next cell.
- 2026-10-24 18:06 — GLOW ROUND 2 DISPATCHED (same worktree): team totals σ fit per lane, props gamelog coverage expansion (live-pull players fetched + fitted), ONE NHL totals refit attempt with goalie/rest info only (no re-tuning the failed model).

## Label standard + dev-language purge (Pilot order 2026-10-24 18:13)
Continue the loop until ALL build labels reach proper unified status; THEN
developer language is purged from user-facing surfaces.
- Unified product labels everywhere (app, README, workflow, ESCB, docs):
  BetFi Xii / BetFi_Xii / 12.0.0 / build 16 / engine v5.4 (build number
  bumps as a unit if the loop's changes force a new build).
- Unified status vocabulary (one set, everywhere a user can see):
  PRICED / UNPRICED + plain-language reason; terminal loop states in plain
  words on user surfaces (FAILED-EXAM -> "benched — failed its backtest,
  numbers in the record"; NOT-PULLED -> "not on the board yet").
  Internal docs/registry may keep the precise terms; surfaces may not
  mix synonyms (no cell may be called two different things in two places).
- Dev-language purge list (user surfaces): organ numbers, file names,
  internal codes (phi/kappa-style symbols without a plain gloss), harness/
  regression talk, "stub", "lane" without context. Verdict ladder and
  calibration tags stay — they are product language, used consistently.
- This pass runs AFTER the math loop closes (labels can't unify while
  coders are still minting them) and BEFORE the 3D panel implementation.
## Menus (Pilot order 2026-10-24): keep + update ALL menus — FanDuel-side
(sport pages + per-game full menus) refreshed every pull cycle; app-side
menus derive from the pull only. Sent into Guy Round 2 (pull owner).
## 3D panel: plan written (XII-3D-PANEL-PLAN.md) — panel goes alive:
coverage graph + registry map update on every pull, in-panel segmented
navigation (Charts|Coverage|Instruments|Registry), cross-navigation to
Board, full-screen zoomable graph viewer; implemented last pre-push,
after label unification.
- 2026-10-24 18:16 — Pilot defined the 3D panel's purpose: 3D exists to ACTIVELY MAKE PREDICTIONS and SEE CORRELATIONS a 2D version hides. Deep. Plan amended (XII-3D-PANEL-PLAN.md): surfaces are instruments not pictures (probe any state -> engine prices it), pull-derived instruments get fresh slate data injected on every pull, new EDGE LANDSCAPE surface (model p x implied p x edge) + correlation view for Protected Slip legs; 2D charts demoted to summaries, never presented as the 3D substance.
