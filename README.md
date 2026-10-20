# BetFi 10 — betmodel v5.2 engine, the Android app

**Public name: BetFi. Internal id: Bet_Finder. App release: v10.0.0
(build 10)** with the betmodel **v5.2** engine. The service's core:
the betmodel engine (deep mathematics, a multi-source ensemble, a
fitted reparametrization layer, a cross-market coherence audit, and
a coverage law — no bet left unchecked) behind a phone app whose
face is one card. Analysis only: the app never places a bet, never
asks for, touches, or stores FanDuel credentials. The menu pull
reads the public board through the engine's read-only FanDuel sbapi
route (Michigan), pull-on-demand, stamped with the pull time.

## The two files (and why there are exactly two)

The Pilot's preference is **1 script**. The engine honours it fully:
`betmodel5.py` is one single self-contained script — the whole brain.
Flet's build, however, requires the app entry point to be named
`main.py`, so the shell is a second single file that *imports* the
engine. Two Python files, no package tree, no module sprawl:

| File | What it is |
|---|---|
| `betmodel5.py` | The engine (v5.2). Byte-identical copy of the lab's `scripts/betmodel5.py` — do not edit it here; engine changes happen in the lab and are re-copied. |
| `main.py` | The entire Flet app: Cards, Parse, Parlay, Solver, More (+ BetFi, Record, Terms, Equations, Dev). |
| `requirements.txt` | `flet==1.0.4` and nothing else (the engine is stdlib-only). |
| `.github/workflows/build-apk.yml` | The GitHub Actions build (below). |
| `BetFi-10.escb` | The Complete Edition — the whole app as ONE file (see the `.escb` section below). Generated, never hand-edited. |

## The `.escb` file — Embedded Single-file Complete Bundle

**Type:** `.escb` = **Embedded Single-file Complete Bundle**. A plain
-text file (Python source, UTF-8) that carries an entire two-file
application inside one file, for canvas drops, chat handoffs, and
offline reading — anywhere a repo can't go but one file can.

**Meaning:** `BetFi-10.escb` is BetFi 10 complete: the v5.2 engine
and the v10.0.0 shell, reincorporated into a single runnable script.
It is the same code the APK is built from, in the Pilot's preferred
1-script form — not a port, not a summary, not a demo build.

**Structure:** two parts under one header. PART 1 is `betmodel5.py`
embedded **verbatim** as a source string and bound as the module
`b5` at startup (its `__main__` guard stays inert). PART 2 is
`main.py` with exactly three marked adaptations: (1) its
`from __future__` import moved into the bundle header, (2) its
`import betmodel5 as b5` line replaced by the embedded binding,
(3) the Dev-screen engine fingerprint hashing the embedded source
instead of a sibling file. No engine or shell logic changes.

**Usage:**
- Run the app: `python3 BetFi-10.escb` (needs `flet==1.0.4`
  installed — the shell's only dependency; the engine is stdlib-only).
- Use the engine alone: import the file as a module; the engine is
  the `b5` attribute, fully usable with no UI and no network until a
  pull is requested.
- Verify a bundle: the Dev screen's fingerprint (short sha256 +
  byte count) identifies the embedded engine exactly; a bundle whose
  fingerprint differs from the repo engine's is a different build.
- **Never hand-edit an `.escb`.** It is generated from `main.py` +
  `betmodel5.py`; edits land in those sources and the bundle is
  regenerated. The two-file layout remains canonical because Flet's
  APK build requires an entry point named `main.py` — the `.escb`
  is the distribution form, the repo pair is the source form.

## The screens

Bottom nav, five destinations: **Cards · Parse · Parlay · Solver ·
More**. More links to BetFi, Record, Terms, Equations and Dev.

- **Cards** — every market the engine checked on the current pull,
  as a card. Face, in fixed order: matchup (soccer lists the home
  team first, world style), the lane's Win/Lose record, the pulled
  odds (soccer shows decimal first, American in parentheses), the
  hero **Probability** with the **edge in points** beside it, the
  **Grade** as colored text with the **calibration chip**
  (CALIBRATED / PROVISIONAL / UNCALIBRATED / UNTESTED — a status
  dot and the tag), then the **verdict pill** with the **stance
  pill** beside it (BULLISH / CONSERVATIVE / LONGSHOT — the cool
  tints, never a verdict color). UNPRICED gets the app's only
  outlined pill, so no-signal never reads as the DO NOT BET red.
  Depth stays in the card, collapsed: **PRICE ANATOMY**,
  **SCALE**, **COHERENCE**, **PROVENANCE**, each with a plain
  one-line gloss. Toggles — Priced only · Golden only · Hide DO
  NOT BET · one switch per sport on the pull — and seven sorts
  (verdict ladder / edge (pts) / do-not-bets first / grade /
  probability / kickoff / pull order) re-render the cached checker
  pass; they never re-price. A filtered list says so:
  "{shown} of {total} markets".
- **Parse** — paste a bet line ("Lions -3.5 (-110)", "Over 47.5
  (-110)", "Team ML +150"…). The app reads selection, market, line,
  odds and implied probability, and when the last pull holds that
  market it shows the pull's own card for it. What it can't read
  or can't match, it says so — stamped, not guessed.
- **Parlay** — build a slip of up to four PRICED legs from the
  last pull. Combined American + decimal odds, combined model
  probability (product of the legs' probabilities — independence
  assumed, printed on the page), EV per $1, a verdict in the
  ladder's language, leg-conflict notes (over + under on the same
  game), and the slip's stance: the longest shot sets it.
- **Solver** — three solvers: stake for a target profit; Kelly
  sizing (full / half / quarter stakes, with the warning printed
  in full — BetFi sizes at quarter-Kelly); an equal-return hedge
  solver that prints a locked loss as a loss.
- **BetFi** (under More; internal: the Bet_Finder feed) — the
  **GOLDEN BETS panel** on top: every card whose engine verdict
  is GOLDEN BET, and when there are none it prints **"No golden
  bets on this pull"**, never backfilled. Below, the **finds
  feed**: PRICED cards ranked by verdict ladder, then edge.
  COHERENCE-FLAGGED markets get their own group; everything else
  collapses into one "Checked — no edge" counter. BetFi finds
  and ranks; it never upgrades a verdict.
- **Record** — the latest-pull summary (markets checked, PRICED,
  GOLDEN, coherence-flagged, calibration-tag counts, stance
  counts) and the lane ledger: each lane's Win/Lose, governor
  status and its calibration tag.
- **Terms / Equations** — the glossary and the math, in the open:
  every verdict term, edge, EV, implied probability, the grade
  band table, the stance rules, shrinkage, Kelly, parlay and
  hedge formulas, each with a plain-English gloss.
- **Dev** — app version + build, engine version + fingerprint
  (sha256 prefix + byte size) of the bundled `betmodel5.py`, the
  data-source line, and the credit: *BetFi — by T. Abram. Engine:
  betmodel. Built with Praxis.*

Buttons (on the Cards screen): **Pull Menu** (live pull; on
failure the stamp reads UNVERIFIED and nothing is assumed) and
**Price Slate** (re-runs the engine's coverage checkers over the
pull). Offline, the app opens on the last pull, stamped with its
original pull time — the engine's own stamp calls an old pull
STALE. Stale is labelled stale.

## Grading policy (v5.2 — Pilot-ordered)

Through v5.1, a lane whose calibration test had failed (the NFL
lane: its phi does not beat its shrinkage/market benchmark) had
its grades **capped at C** and its verdicts gated — the failure
was enforced silently, in the grade itself. **v5.2 removes the
cap.** Letter grades A+–F are computed from the model's edge math
on every lane, and the grade bands are widened (B now starts at a
+2.0-pt phi edge; the full table is on the app's Equations page
and in the engine's `GRADE_BANDS_V52`). Calibration is now a
**displayed tag** on every card — CALIBRATED / PROVISIONAL /
UNCALIBRATED / UNTESTED — that informs the reader and blocks
nothing. GOLDEN BET no longer requires a calibrated lane; it
requires an A-band grade, a priced market, an edge still ≥ +3.0
pts at the band's pessimistic end, and a named mechanism. The
phi/reliability diagnostics are still computed and shown (Record
screen); they set the tag, not a cap. The hard rules did not
move: prices only from the live menu, UNPRICED ⇒ DO NOT BET with
the named reason, the golden panel never backfilled. The engine
regression (R1–R7 + the v5.2 addendum) is green under the new
policy; R4's expectation was rewritten to assert the tag instead
of the cap, and says so in its own text.

**Stance (v10):** every priced bet also carries a stance,
computed by the engine from the bet's own probability, edge and
price: **BULLISH** (strong edge on a side the model rates),
**CONSERVATIVE** (high probability, thin edge — the
boring-favorite profile), **LONGSHOT** (low probability or
plus-money payout shape). Stance describes the shape of the bet,
never whether to take it — the verdict decides that. UNPRICED
bets get no stance.

## The five verdicts (the ladder — engine-issued, app-printed verbatim)

1. **GOLDEN BET** — A-band grade, priced, edge ≥ +3.0 pts at the
   band's pessimistic end, a named mechanism, no cautions.
2. **BET HERE** — A/B-band grade, positive edge, no hard failure
   and no caution standing.
3. **RISK BET (BET)** — a real edge with exactly one named
   caution (FRAGILE, record-less lane, a thin band floor).
4. **RISK BET (DO NOT BET)** — a signal blocked by a named hard
   failure (kill ledger, Governor bench, C-band grade, coherence
   flag, a dead band floor) or by stacked cautions.
5. **DO NOT BET** — the plain no: no edge, negative edge, or
   UNPRICED. Nothing there.

## Build it (GitHub route — the only live route)

`flet build apk` is the build. (The Buildozer/Kivy route from old
guides does not apply to a Flet app and is dead.)

1. Create a GitHub repo named **`betmodel-v5`** (private is fine).
2. Push **this folder's contents** to it — `main.py`,
   `betmodel5.py`, `requirements.txt`, `README.md`, and
   `.github/` — with the files at the repo root, not inside a
   subfolder.
3. In the repo: **Actions → "Build BetFi APK" → Run workflow**
   (it also runs automatically on pushes to `main`). First run
   takes a while: Flet fetches its Flutter SDK and builds with
   JDK 17.
4. When the run is green, open it and download the artifact
   **`betfi-10-apk`** — that zip contains exactly two files:
   **BetFi-10.apk** (release, the one to install) and
   **BetFi-10-debug.apk** (debug build).
5. Copy the APK to the phone and sideload it (allow "install via
   USB" / install the file; it's signed with the build's default
   key for personal use — no Play Store involved).

If the Actions build ever rejects the pinned Flet 1.0.4 (the 1.x
line is current and still settling), the known-stable fallback is
the last 0.x line: change `requirements.txt` to `flet==0.86.5`
and re-run. The shell deliberately uses only long-stable Flet API
surface either way.

## Smoke-test checklist (first run on the phone)

- [ ] App **opens** to the Cards screen; header reads BetFi /
      BetFi 10 · engine betmodel v5.2 · analysis only.
- [ ] With no pull yet, the menu stamp reads **UNVERIFIED** and
      the screen says so — nothing is pre-filled or assumed.
- [ ] **Pull Menu**: the stamp updates to the pull time and
      source; the status line reports how many primary markets
      were pulled per sport (or names the failed scopes).
- [ ] **Price Slate**: cards appear; each shows Win/Lose,
      Probability (or UNPRICED), a Grade, a calibration chip, the
      verdict pill and — when priced — a stance pill; the four
      collapsible sections open, led by the verdict_reason line.
- [ ] Cards toggles flip the list and the count reads
      "{shown} of {total} markets"; all seven sorts reorder
      without re-pricing.
- [ ] **Parse**: the six example shapes parse; a matched bet
      shows the pull's card.
- [ ] **Parlay**: two legs combine; the combined odds, model %,
      EV and slip stance print.
- [ ] **Solver**: all three solvers compute; bad input prints
      "Enter a number for every field." — never a crash.
- [ ] **More → BetFi**: the GOLDEN BETS panel sits on top
      (golden cards, or "No golden bets on this pull").
- [ ] **More → Record / Terms / Equations / Dev** all render;
      Dev shows the engine fingerprint and the credit.
- [ ] Kill and relaunch the app offline: it reopens on the last
      pull, stamped with the original pull time (STALE once old).

## Honesty rules carried into the app

- A failed pull stamps UNVERIFIED; a market the engine cannot
  price stamps UNPRICED with its reason named. The app invents
  nothing — every number traces to an engine output with
  provenance.
- On-device, the engine's lab data files (scorecard, phi
  registry, lane history) are absent unless synced into app
  storage, so lanes report "no scored record" and carry the
  UNTESTED tag — the engine's own rules, not an app error.
  Under v5.2 that tag no longer caps anything; it is printed so
  the reader can see it.
