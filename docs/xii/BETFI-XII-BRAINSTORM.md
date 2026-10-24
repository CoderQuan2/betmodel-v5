# BetFi Xii — Brainstorm, Feature Map & Work Notes
Pilot order 2026-10-24. App-only. Repo: CoderQuan2/betmodel-v5. Base: 11.0.2 (build 15), engine v5.3 → Xii = 12.0.0 (build 16), engine v5.4.

## The doctrine (Pilot, verbatim intent)
A serious application — people's livelihoods and names at stake. Every sport,
every league, every player covered; fits updated with each pull; if no pull,
auto-pull every 4 minutes; auto-pull on start; full histories for all teams,
leagues and players; nothing made up; rigorous, sport-specific,
league-specific, bet-specific math for any and all bet analysis. Good grades
get bets placed — and the app must protect the user. The user wants to win money.

## The Universal Model (governs ALL analytics in the app)
One registry, one law, per-lane math:

- **Fit Registry (engine Organ 8).** Every fit in the app registers itself:
  sport, league, fit kind, coverage count (teams/players), fitted_at, source,
  and its walk-forward backtest printed verbatim. A league with no history
  file is ABSENT from the registry — never synthesized, never borrowed from a
  neighbouring league (the Serie A/EPL lesson).
- **Coverage audit on every pull.** Every sport/league present in the FanDuel
  pull is reported: PRICED-capable (fit exists, both sides in fit) or
  UNPRICED with the named missing piece. The pull itself defines the universe
  the app owes coverage for — the menu is the checklist.
- **Specialization is three-axis (Pilot clarification 2026-10-24: the math
  upgrades are for EVERYTHING in the app, not soccer alone):** per TEAM
  (ratings/strengths, home-away where data supports), per LEAGUE (scoring
  environment, pace, home advantage — fitted per league, never one global
  value), and per BET TYPE (moneyline ≠ cover ≠ totals ≠ props: each gets
  its own distribution; a league priced for moneylines can still stamp its
  totals UNPRICED "no totals distribution for this lane yet"). Coverage is
  reported at (sport, league, bet-type) grain, and every missing cell goes
  on XII-COVERAGE-QUEUE.md as the explicit work queue.
- **Sport-specific math, per lane:**
  - Soccer (per league): Poisson goals grid from that league's own home/away
    scoring rates × team attack/defense strengths + Elo — 1X2 out of the grid.
  - NFL/CFB: Elo/ratings lanes (phi, ratings files) with their own histories.
  - NBA/NHL: Elo lanes over full game histories (v5-nba, NHL ratings+games).
  - Player props: the player's own gamelog distribution (cached game logs),
    never a team-average stand-in.
  - Each lane's calibration state (CALIBRATED / PROVISIONAL / UNCALIBRATED /
    UNTESTED) rides every card; grades come from edge per GRADING.md;
    GOLDEN = pessimistic edge ≥ +2.0 with every other condition hard.
- **Freshness law.** Pull on start; auto-pull every 4 minutes while open;
  a failed pull keeps the last good pull stamped STALE/UNVERIFIED. Fits are
  re-read with each pull cycle. Prices only ever from the live pull.

## Protection law (the app protects the user)
- UNPRICED ⇒ DO NOT BET with the named reason. No fit, no price, no grade.
- GOLDEN panel never backfilled; honestly empty when nothing qualifies.
- Kelly sizing is quarter-Kelly, 5%-of-roll hard cap, damped on
  UNCALIBRATED lanes with the reason printed. Max loss on any protected
  slip = its total stake, printed before anything else happens.
- Kill-ledger + coherence checks run on every grouping; same-game slips
  stamp UNPRICED under engine law.
- Placement: GOLDEN / BET HERE markets auto-build a **Protected Slip**
  (legs, stakes, max loss, warnings). The user places it on FanDuel and
  marks it placed in-app; the mark appends to the Pilot Book as
  PLACED (user-marked) with timestamp. The app itself never auto-places
  and never touches a sportsbook account — there is no sportsbook channel
  in the app, and a standing Pilot law requires explicit instruction per
  bet. Auto-building the protected slip is as far as automation goes
  without that channel; anything further needs the Pilot's explicit
  per-bet go.

## Feature addition map
| # | Feature | Where | Gate |
|---|---------|-------|------|
| X1 | Rename BetFi_Xii / "BetFi Xii" on phone + under icon; XII icon (X-ray) | shell + workflow + assets/icon.png | harness pins 12.0.0/16 |
| X2 | Universal Fit Registry + coverage audit (Organ 8) | engine v5.4 | registry/coverage assertions |
| X3 | Soccer multi-league fits: Serie A, La Liga, Bundesliga, Ligue 1 (+EPL control) from real results history | tools/fit_soccer_leagues.py → data/v5-soccer-leagues.json | EPL control ≈ existing fit; per-league backtest printed |
| X4 | Auto-pull on start + every 4 min, no overlap, honest stale stamps | shell | constants + worker guards asserted |
| X5 | Copy mechanic on NAMES (team/player name alone copies; slip label kept secondary) | cards | harness assertion on name-copy helper |
| X6 | Xii Charts: in-app, from current pull, rebuilt per pull; edge distribution, priced-vs-unpriced by sport, model-vs-implied; zoom via gesture +/−/reset buttons; NO sliders; tap-for-detail | 3D destination (nav stays 5) | empty-pull render asserted |
| X7 | Protected Slip for GOLDEN/BET HERE + user-marked placement → Pilot Book | Slip screen | confirm step shows legs + total stake |
| X8 | Design rescue: X-ray identity (Artist entity) | assets + DESIGN-RESCUE.md | icon reads at 96px |

## Split entities (Pilot order)
- **Artist** — X-ray icon (1024/512/192) + design-rescue spec.
- **Coder** — X1–X7 implementation + gates.
- **Praxis (combine)** — merge icon into repo, independent verification
  (harness, smoke_serialize, regression spot-check, live pull smoke,
  ESCB verify), reflection, push.

## Work notes / known limits, stated plain
- "Every league" is discharged as: every league IN THE PULL gets a coverage
  line; leagues with real downloadable history get real fits this build
  (soccer big-five first); a league with no obtainable history stays
  UNPRICED with its name on the missing list — that list IS the work queue
  for the next fits, not a silent gap.
- Player coverage = every player whose props appear in the pull gets the
  gamelog-distribution checker; a player with no cached history stamps
  UNPRICED with the named reason, as today.
- The 11.1 hardening items (TypedDicts, section markers, Poisson unit
  tests) remain queued after Xii unless the coder's gates absorb the
  Poisson tests via the fit-builder control check.
