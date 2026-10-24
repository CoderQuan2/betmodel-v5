# BetFi Xii — 3D Panel Update Plan
Pilot order 2026-10-24: plan the 3D panel update — updates on pull, navigation.
Status: PLAN (implementation is the last pre-push item, after the math loop
closes and the label-unification pass, because this panel is user-facing and
must speak the purged, unified language from day one).

## Where the 3D destination stands (Xii as built)
- 5th nav destination capped by law (Board · Slip · Lab · 3D · More).
- Xii Charts sit on top (native-container bars from the current pull:
  edge distribution, priced-vs-unpriced by sport, model-vs-implied top 40),
  rebuilt on every render after a pull; button zoom 0.5–6.0, no sliders.
- Below: the 11 snapshot instruments, served over loopback, opened via
  UrlLauncher (Flet 1.0.4 has no WebView), each with its snapshot label.

## Why 3D at all (Pilot, 2026-10-24 — the panel's reason to exist)
It is 3D because we can ACTIVELY MAKE PREDICTIONS and SEE CORRELATIONS
that a 2D version hides. Depth is data depth, not decoration:
- A win-probability SURFACE (score diff x clock x WP) shows the whole
  state space at once; a game's journey across it, and the gap between
  priced states and the model surface, IS the market-vs-model
  disagreement — invisible as a line (proven in the lab instruments:
  priced states deviated from the surface by up to ~7 pts).
- An edge landscape (model p x implied p x edge) clusters value that a
  sortable 2D table ranks but never shows as structure.
- Parlay legs in correlation space: clustered legs are one bet wearing
  costumes; spread legs are real diversification. 2D lists hide this.
- Team-strength space (attack x defense x rating, per league) shows
  tiers and outliers as geography.
- Price/CLV drift over successive pulls needs time as a true axis.
ACTIVE PREDICTION is the second half: the surfaces are instruments,
not pictures — probe any state (diff/time, lambda, line) and the engine
prices it on the spot (the WP instrument's probe already does this:
move the state, read the price). What-if is a first-class input:
steppers/taps set the state (no sliders — standing law), the surface
and its readout update from the engine's own functions, never from a
second implementation of the math.

### Build consequences (added to the update scope)
- The WebGL2 instruments (WP surface, stock-vol) are the reference
  builds: orbit, probe, stated-vs-model heights with the gap labeled.
- On every pull, pull-derived instruments get FRESH DATA injected: the
  serving layer regenerates the instrument payloads from the current
  slate (current games' journeys/states on the WP surface, current
  priced set on the edge landscape) instead of serving frozen data.
  Snapshot instruments that take no slate input keep their stamps.
- New surface for Xii: the EDGE LANDSCAPE from the current pull
  (model p x implied p x edge, point per priced market, tap a point =
  that market, jump to its card), and a CORRELATION view for the
  Protected Slip's legs (shared team/game/league exposure as proximity).
- The 2D native charts stay as summaries; they are not the 3D panel's
  substance and must not be presented as such.

## The update — "the panel is alive"
1. **Everything in the panel updates on pull.** Each successful pull
   (start, 4-minute auto, manual) re-renders:
   - Xii Charts (already true — keep, extend below).
   - A new COVERAGE graph: priced share per league (the loop's burn-down
     as a picture), from universal_coverage() on the current pull.
   - A new REGISTRY MAP: leagues as tiles — fit kind, teams covered,
     backtest headline, status in the unified label set.
   - Pull-derived instruments (WP surfaces, trajectories) re-render from
     the current slate where the instrument takes slate input; pure
     snapshot instruments keep their snapshot stamp, now with the pull
     time beside it so "snapshot of what, when" is never ambiguous.
   - Every section header carries the pull timestamp + the stale state
     (frozen gold treatment at >=4 min, per the motion spec).
2. **In-panel navigation.** One segmented control inside the panel:
   Charts | Coverage | Instruments | Registry — switching is
   AnimatedSwitcher, lazy-built per segment (Snapdragon budget), state
   (segment + chart zoom + tapped detail) preserved across pulls so an
   auto-pull never kicks the user out of what they're looking at.
3. **Cross-navigation.** Tapping a league in Coverage/Registry jumps to
   the Board filtered to that league; tapping a chart bar's detail line
   offers "show on Board" for that market; a card's depth gains a
   "chart" affordance that opens the panel on Charts with that market's
   bar highlighted. Back returns to where you were (nav state stack,
   one level).
4. **Full-screen graph viewer.** Any chart opens full-screen in-app:
   pinch + button zoom (1–6x), pan, tap-hold crosshair readout, pull
   time in the header, no sliders anywhere (standing law).
5. **Labels.** The panel ships only after the label-unification pass:
   unified status set, no developer language on any surface (see
   XII-LABEL-STANDARD in the loop ledger / combine checklist).

## Non-goals / laws kept
- Nav stays 5 destinations. No new dependencies (flet-charts stays out;
  native containers proved sufficient). Instruments keep honest
  snapshot/live labels — a snapshot never dresses as live.
- Snapdragon budget: one panel segment built at a time, aggregates only,
  no per-market control explosions, animations within the standing caps.

## Sequence
Loop closes (all cells terminal) -> label unification + dev-language purge
-> this plan implemented -> full gates -> all-leagues list -> push.
