# BRIEF-001 — Jules: BetFi Xii design system + motion exploration (sandbox)

**From:** Praxis (lead) · **For:** Jules · **Lane:** design/flair ONLY
**Status:** open · Praxis reviews before anything merges.

## Context

BetFi Xii is converting to native Android: Jetpack Compose UI with
the existing Python engine embedded via Chaquopy. The scaffold is at
`native/` in this repo — a Compose shell with six destinations
(Board, Finds, Slip, Lab, 3D, Stocks), a dark slate board with an
ice accent (#38BDF8), and a parity spike on the Board. Phases 0–1
are load-bearing and Praxis-owned. Your lane is the one that runs
safely in parallel: **what the native app should feel like.**

## The work

Design exploration, delivered as a **self-contained sandbox** under
`native/design-sandbox/` on your own branch:

1. **Theme** — a Compose theme for BetFi Xii: color scheme (evolve
   the slate + ice identity, don't discard it), typography scale,
   shape system. Show it on a specimen screen that renders every
   token (swatches, type ramp, buttons, chips, cards) so it can be
   judged at a glance.
2. **Card motion** — the verdict card is the app's atom. Explore:
   expand/collapse motion for the card's depth sections, the BET NOW
   pulse (the shipping app breathes a glow behind the box — give it
   a native motion language), and list-enter motion for a board of
   cards. Working composables in the sandbox, not descriptions.
3. **Fold postures** — the Pilot's phone is a Galaxy Z Fold7.
   Explore what Board does half-open and fully open: rail vs bar,
   two-pane board + detail, tabletop posture. Sketches as working
   layouts where you can; notes where you can't.
4. **A short DESIGN.md** in the sandbox: the tokens, the motion
   durations/curves and why, and which explorations you recommend
   adopting — with your reasoning stated plainly.

## Hard limits

- **No engine files** (`betmodel5.py` anywhere), **no bridge**
  (`bridge.py`, `EngineBridge.kt`, `Parity.kt`), **no `main.py`**,
  **no build config changes** (no edits to any `build.gradle.kts`,
  `settings.gradle.kts`, `gradle.properties`, or the workflows).
- Nothing outside `native/design-sandbox/` except your branch's own
  notes. The sandbox must not be wired into the app module — it is
  read as a specimen, then adopted piecemeal by Praxis if approved.
- Verdict numbers in specimens must be obviously sample data —
  never present invented prices/probabilities as engine output.

## Delivery

One branch, one PR against `main`, description led by what you
recommend adopting and why. Praxis reviews; adoption lands as
separate Praxis commits into the app module. Questions go in the PR
thread — Praxis answers there.
