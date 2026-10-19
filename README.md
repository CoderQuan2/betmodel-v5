# BetFi v7 — betmodel v5 engine, the Android app

**Public name: BetFi. Internal id: Bet_Finder. App release: v7**
(the engine is the unchanged betmodel v5.1 code). The service's core:
the betmodel v5 engine (deep mathematics, a multi-source ensemble, a
fitted reparametrization layer, a cross-market coherence audit, and a
coverage law — no bet left unchecked) behind a phone app whose face
is one card. Analysis only: the app never places a bet, never asks
for, touches, or stores FanDuel credentials. The menu pull reads the
public board through the engine's read-only FanDuel sbapi route
(Michigan), pull-on-demand, stamped with the pull time.

## The two files (and why there are exactly two)

The Pilot's preference is **1 script**. The engine honours it fully:
`betmodel5.py` is one single self-contained script — the whole brain.
Flet's build, however, requires the app entry point to be named
`main.py`, so the shell is a second single file that *imports* the
engine. Two Python files, no package tree, no module sprawl:

| File | What it is |
|---|---|
| `betmodel5.py` | The engine. Byte-identical copy of the lab's `scripts/betmodel5.py` — do not edit it here; engine changes happen in the lab and are re-copied. |
| `main.py` | The entire Flet app: Card screen, BetFi screen, Record view. |
| `requirements.txt` | `flet==1.0.4` and nothing else (the engine is stdlib-only). |
| `.github/workflows/build-apk.yml` | The GitHub Actions build (below). |

## The screens

- **Card** — every market the engine checked on the current pull, as
  a Level-3 card. Face: matchup `#:#` (the FanDuel event id), Win # /
  Lose # (the lane's scored record), Probability #, Grade A–F, and
  the engine's **verdict term, verbatim** (see the ladder below).
  The depth is *in* the card, collapsed by default, and its first
  line is the engine's `verdict_reason` — the deciding condition,
  named: **PRICE ANATOMY** (ensemble sources, the pulled price,
  implied %, the phi edge), **SCALE** (the fitted φ and its state,
  the lane record, calibration), **COHERENCE** (the ML/spread/total
  audit), **PROVENANCE** (source, pull timestamp, market time, ids).
- **BetFi** (internal: the Bet_Finder feed) — the powerhouse space.
  At the top, the **GOLDEN BETS panel**: every card on the current
  pull whose engine verdict is GOLDEN BET, with full collapsible
  depth — and when there are none it prints **"No golden bets on
  this pull"**, never backfilled with lesser verdicts. Below it, the
  **finds feed**: verdict-bearing PRICED cards **ranked by the
  verdict ladder first, then by reparametrized edge descending**
  (the edge applies the engine's own phi-edge formula to the
  engine's returned probability and the pulled price).
  COHERENCE-FLAGGED markets get their own group — a flag is a find
  too. Everything else the engine checked collapses into one
  **"Checked — no edge"** counter, kept off the feed. BetFi finds
  and ranks; it never upgrades a verdict — the verdict term and
  every stamp (UNCALIBRATED on the face, UNPRICED, UNVERIFIED) print
  exactly as the engine issued them.

## The five verdicts (the ladder — engine-issued, app-printed verbatim)

Every card carries the engine's `verdict` + `verdict_reason`. In
ladder order:

1. **GOLDEN BET** — the rarest stamp: grade A− or better (φ edge
   ≥ +5), lane calibrated, the edge clearing the band's pessimistic
   end by ≥ +3, no coherence flag, a named mechanism on any market
   disagreement. The golden panel's only residents.
2. **BET HERE** — the clean affirmative: grade ≥ B−, lane
   calibrated and not benched, edge survives the band floor, no
   kill-ledger contact.
3. **RISK BET (BET)** — affirmative with exactly one named
   softening condition: provisional lane, FRAGILE modifier,
   record-less lane, or under a point of band-floor clearance.
4. **RISK BET (DO NOT BET)** — a real signal blocked by a named
   hard failure: benched or UNCALIBRATED lane, band floor, kill
   ledger, or a C-band grade. Visibly different from an empty
   market.
5. **DO NOT BET** — the plain no: no edge, negative edge,
   UNPRICED, or incoherent prices. Nothing there.

The ladder terms require engine **v5.1+** (which emits `verdict` +
`verdict_reason` on every card's JSON). If the bundled engine is
still v5.0, the app renders that engine's own issued decision
(Bet / No Bet) verbatim in the same place — the app never
translates one engine's terms into another's, and it picks up the
ladder automatically the moment a v5.1 engine copy is dropped in.
- **Record** — each lane's Win/Lose with its source, governor status,
  and the engine version string plus a fingerprint (sha256 prefix +
  byte size) of the bundled `betmodel5.py`, so a stale build is
  visible at a glance.

Buttons: **Pull Menu** (live pull; on failure the stamp reads
UNVERIFIED and nothing is assumed) and **Price Slate** (runs the
engine's coverage checkers over the pull). Offline, the app opens on
the last pull, stamped with its original pull time — the engine's
own stamp calls an old pull STALE. Stale is labelled stale.

## Build it (GitHub route — the only live route)

`flet build apk` is the build. (The Buildozer/Kivy route from old
guides does not apply to a Flet app and is dead.)

1. Create a GitHub repo named **`betmodel-v5`** (private is fine).
2. Push **this folder's contents** to it — `main.py`, `betmodel5.py`,
   `requirements.txt`, `README.md`, and `.github/` — with the files
   at the repo root, not inside a subfolder.
3. In the repo: **Actions → "Build BetFi APK" → Run workflow**
   (it also runs automatically on pushes to `main`). First run takes
   a while: Flet fetches its Flutter SDK and builds with JDK 17.
4. When the run is green, open it and download the artifact
   **`betmodel-v7-apk`** — that zip contains exactly two files:
   **Betmodel-v7.apk** (release, the one to install) and
   **Betmodel-v7-debug.apk** (debug build).
5. Copy the APK to the phone and sideload it (allow "install via
   USB" / install the file; it's signed with the build's default key
   for personal use — no Play Store involved).

If the Actions build ever rejects the pinned Flet 1.0.4 (the 1.x
line is current and still settling), the known-stable fallback is
the last 0.x line: change `requirements.txt` to `flet==0.86.5` and
re-run. The shell deliberately uses only long-stable Flet API
surface either way.

## Smoke-test checklist (first run on the phone)

- [ ] App **opens** to the Card screen; header reads BetFi /
      v7.0 / betmodel v5 / Bet_Finder.
- [ ] With no pull yet, the menu stamp reads **UNVERIFIED** and the
      screen says so — nothing is pre-filled or assumed.
- [ ] **Pull Menu**: the stamp updates to the pull time and source;
      the status line reports how many primary markets were pulled
      per sport (or names the UNVERIFIED scopes if a pull failed).
- [ ] **Price Slate**: cards appear; each shows Win/Lose,
      Probability (or UNPRICED), a Grade, and the engine's verdict
      term; the four collapsible sections open, led by the
      verdict_reason line.
- [ ] **BetFi tab**: the GOLDEN BETS panel sits on top (golden
      cards, or "No golden bets on this pull"); the feed is ranked
      ladder-first, then edge; flagged markets are grouped; the
      "Checked — no edge" counter matches the slate size.
- [ ] **Record tab**: lane records render and the **engine version
      string + fingerprint** are visible.
- [ ] Kill and relaunch the app offline: it reopens on the last
      pull, stamped with the original pull time (STALE once old).

## Honesty rules carried into the app

- A failed pull stamps UNVERIFIED; a market the engine cannot price
  stamps UNPRICED with its reason named. The app invents nothing —
  every number traces to an engine output with provenance.
- On-device, the engine's lab data files (scorecard, phi registry,
  lane history) are absent unless synced into app storage, so lanes
  report "no scored record" / UNCALIBRATED and cap their grades
  accordingly — the engine's own rules, not an app error.
