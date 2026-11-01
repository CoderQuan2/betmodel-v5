# Scare Bets — Native Program (Jetpack Compose + Chaquopy)

The Pilot's decision (2026-10-31): convert BetFi to a native Android
app — **Jetpack Compose UI + the existing Python engine embedded
in-process via Chaquopy**. Kotlin lane ports come later, one lane at
a time, each gated on parity tests against the Python reference.
The One UI 9 manual (`~/workspace/your_files/ai-manual-android-one-ui-9/`)
is the platform reference: Compose is the native path, adaptive
layouts are mandatory on ≥600dp (the Fold7 case), native libraries
are 16 KB-aligned, target the newest API available.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│ Compose UI (Kotlin)                                        │
│ Board · Finds · Slip · Lab · 3D · Stocks                   │
│ adaptive: NavigationRail ≥600dp, NavigationBar below       │
└──────────────────────┬─────────────────────────────────────┘
                       │ EngineBridge.kt — the only door
                       ▼
┌────────────────────────────────────────────────────────────┐
│ bridge.py — the only adapter                               │
│ init(filesDir): seed writable data dir from the bundle,    │
│ repoint every engine path global onto it                   │
│ run_slate_json(text) -> text · ping() -> engine identity   │
└──────────────────────┬─────────────────────────────────────┘
                       ▼
┌────────────────────────────────────────────────────────────┐
│ betmodel5.py — the engine, byte-identical, never edited    │
│ pure stdlib · data bundle rides beside it (engine/../data) │
└────────────────────────────────────────────────────────────┘
```

Data flows as JSON text across the bridge — the same shape the Flet
shell already uses — so the UI never learns Python types and the
engine never learns Android.

## The one-engine law

`betmodel5.py` is **byte-identical everywhere**: the lab copy, the
Flet shipping copy, and `native/app/src/main/python/engine/`. The
native copy is *synced from* the shipping engine at combine time and
**never edited independently** — any engine change lands in the
engine's own lane, gets its harness + zero-diff proofs there, and
only then is re-copied here (with the parity reference regenerated,
see `parity/PARITY.md`). One md5 set across all copies is the check;
BUILD-LOG.md carries the current hash.

## Phasing

- **Phase 0 — Scaffold** *(this delivery)*: Gradle project, Compose
  shell with the six destinations, Chaquopy wired, CI assembling a
  debug APK on Actions.
- **Phase 1 — Parity spike** *(this delivery, desktop-proven)*:
  Board runs the embedded engine over a bundled 25-market sample
  and compares against the desktop reference verdicts under the
  canonical comparison (`parity/PARITY.md`). The phase closes when
  the same comparison prints MATCH on the Pilot's device.
- **Phase 2 — Board live pull** *(built in v1.0.0, see status
  below)*: the FanDuel menu pull path lives behind the bridge;
  Board renders real verdict cards from a live pull.
- **Phase 3 — Destination parity** *(built in v1.0.0, see status
  below)*: Finds, Slip, Lab, 3D, Stocks at parity with the Flet
  app, each driven on desktop against the bridge.
- **Phase 4 — Flair + cutover decision**: motion, Fold postures,
  the design system (Jules' lane, BRIEF-001 onward). Cutover is a
  Pilot decision, not a phase default.

## v1.0.0 Complete Edition — status (2026-10-31)

Per-destination status, never rounded up (BUILT = the full
surface is implemented against the bridge and driven on desktop;
the Kotlin side is compile-proven only by GitHub Actions — see
BUILD-LOG.md):

| Destination | Status | Notes |
|---|---|---|
| Board | BUILT | live full + scoped pulls, sport chips, Show control (default All), five depth sections, flashing BET NOW QuickSlip box |
| Finds | BUILT | GOLDEN panel under the unchanged gate law; honestly empty when nothing qualifies |
| Slip | BUILT | Protected Slip (quarter-Kelly, 5% cap, max loss = total stake printed), persisted mark-placed (PLACED, user-marked) |
| Lab | BUILT | recorder health (history_begins + record/market counts), engine identity, parity spike (must print MATCH on device) |
| 3D | BUILT | TRUE spatial 3D: OpenGL ES renderer — see below |
| Stocks | BUILT | TAPE / MATRIX / OPTIONS / HOLDINGS mirroring Flet build 53; WATCH-only |
| Betterama | PARTIAL | shell only, by Pilot order: its definition is being locked; no features invented |

### True spatial 3D

The 3D destination is a real OpenGL ES scene (GLSurfaceView,
perspective projection, depth, drag-orbit camera, pinch/button
zoom) — not a canvas projection and not the Flet HTML
instruments (those are NOT shipped in the native app at all).
Market/history data sits at real coordinates from
`bridge.spatial_json`, with this axis mapping:

- **x = implied probability** from the quoted price (0..1)
- **y = edge** (model probability − implied probability)
- **z = time** (hours; terrain: since the window's first point;
  slate cloud: from the pull stamp to the market's start)

The Edge Terrain renders as a triangle surface mesh over a
24×24 (x, z) grid binned from the history store's G1 paths; a
cell's height is the mean edge of its points, and cells with no
points stay holes — no height is interpolated or invented. The
current slate rides as a point cloud (GOLDEN points gold, BET
NOW points ice).

### Rebrand: Scare Bets (Pilot order, 2026-10-31 evening)

"Betfi is no more." The product's display name is **Scare
Bets**; the official logo (chrome ghost lifting a barbell over
SCARE BETS; Pilot-supplied `~/workspace/user/files/91941_2_959z.jpg`,
2048×2048) ships in the tree as the branding image and launcher
icon source. This is a DISPLAY-brand change only: the
applicationId stays `com.betfi.xii`, package/class names stay,
and the engine files (betmodel5.py, history_store.py, bridge.py)
keep their names — the one-engine law and the parity references
depend on them.

## The standing rule

**The Flet app remains the shipping app** — the one that gets built,
pushed, and judged on the device — **until native parity is proven
AND the Pilot gives the device verdict.** The native app carries a
distinct applicationId (`com.betfi.xii`) so it can sit beside the
Flet app on the same phone without touching its data. Nothing in
this tree changes `main.py`, `betmodel5.py`, `harness.py`,
`README.md`, or the Flet workflow.

## Team rules

- **Praxis leads**: writes the briefs, builds the load-bearing
  pieces, reviews everything, gates all merges, owns the pushes.
- **Jules works branches under brief** (see `team/jules/`): scoped
  lanes with hard limits written into each brief; a branch is input
  to review, never a merge. Jules' first lane is design/flair
  (BRIEF-001) — deliberately away from engine, bridge, and build
  config while the parity phases are load-bearing.
- Nobody pushes engine changes through the native tree (one-engine
  law above). Nobody force-pushes. A Jules PR landing unreviewed
  (the build-54 precedent) is superseded by this structure.
