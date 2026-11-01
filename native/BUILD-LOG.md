# BUILD-LOG — native/ Phase 0/1

Authored 2026-10-31 in `xii-jetpack` (worktree copy of the shipping
clone at HEAD 5b8e828). **Not pushed.** Praxis verifies, combines,
pushes. The Flet app is untouched by this workstream.

## Verified locally (desktop VM, Python 3.12.3)

- [x] Worktree copy integrity: 1,961 files, git HEAD 5b8e828,
      engine md5 identical to the shipping clone.
- [x] Engine copied byte-identical:
      `betmodel5.py` md5 `8b0e6565469b29d5435a7b77138517b1`
      (clone root == native/app/src/main/python/engine/).
- [x] Data bundle replicated from the repo's app-shipping `data/`
      (63 top-level entries + cache/, 22 MB) into
      `native/app/src/main/python/data/` — the engine's import-time
      `DATA = HERE/../data` resolves to it by construction.
- [x] Engine data-path inspection (full findings in
      `parity/PARITY.md`): pure-stdlib imports; ~40 `*_PATH`
      constants bound at import; `run_slate` read-only (manifest
      diff over a full run: 0 files changed/added/removed).
- [x] Full-slate run on bundle data: 1,402 verdicts in ~0.5 s —
      1,140 PRICED / 262 UNPRICED / 491 bet_now, exactly the
      recorded pricing census. Verdict dump 1,056,993 bytes,
      matching the build-53 zero-diff dump size.
- [x] Sample slate: 25 markets (18 PRICED incl. 8 bet_now, 7
      UNPRICED, 7 sports); subset verdicts == full-slate verdicts
      at the same indices; canonical keys unique.
- [x] Reference generated with the plain engine on the bundle:
      `parity/reference_verdicts.json` (== assets copy,
      md5 `53435a87f6cdfba257abc06339029b97`).
- [x] **Bridge drive**: fresh process, `bridge.run_slate_json` on
      the sample == reference — **EXACT** (list equality incl. all
      floats; canonical-string equality).
- [x] Cross-layout check: engine run against the lab's live data
      dir (mobile/data) == bundle reference on the sample — EXACT.
- [x] `bridge.init` drive (fake filesDir): seeded 63 top-level +
      431 cache files; DATA/CACHE/SCORECARD_PATH/NBA_FIT_PATH
      repointed; post-init run still EXACT; device marker file
      survived a second init (no clobbering).
- [x] `bridge.ping()` returns engine_version 5.4, the imported
      engine file path, and the active data dir.

## Version pins (all unverified until Actions compiles them)

| Pin | Value | Flag |
|---|---|---|
| Android Gradle Plugin | 9.4.1 | VERIFY at first Actions build |
| Kotlin + Compose compiler plugin | 2.4.20 | VERIFY |
| Compose BOM | 2026.09.00 | VERIFY |
| activity-compose | 1.11.0 | VERIFY |
| navigation-compose | 2.9.5 | VERIFY |
| Gradle (workflow pin; no wrapper yet) | 9.7.1 | VERIFY |
| JDK (workflow) | temurin 17 | VERIFY |
| compileSdk / targetSdk | 36 / 36 | VERIFY; raise to 37 when the runner carries Android 17 |
| Chaquopy plugin | 17.2.0 | from vendor changelog (2026-10-26); supports AGP 9.0–9.4 |
| Chaquopy Python runtime | 3.12 | matches the desktop proof's interpreter series (3.12.3) |
| applicationId | com.betfi.xii | deliberate: coexists with the Flet app |

## Actions-gated (cannot be proven on this VM — no JDK/SDK)

- [ ] Project configures; the Chaquopy 17 KTS DSL block shape.
- [ ] Kotlin compiles (MainActivity / EngineBridge / Parity).
- [ ] Chaquopy packages the Python tree (incl. the 22 MB bundle)
      and the runtime starts on-device.
- [ ] Debug APK assembles and installs beside the Flet app.
- [ ] **On-device parity spike prints MATCH** — the Phase 1 gate.
- [ ] Gradle wrapper generated from the proven version and
      committed (README has the follow-up).

## Known risks

1. **First-build pin churn** — the expected failure mode is a
   version/DSL rejection in the first Actions run, fixed by
   adjusting pins here and recording the working set in this log.
2. **Chaquopy extraction semantics** — bridge.init's repoint is
   written against the possibility that the extracted Python tree
   is read-only or update-wiped; desktop drives prove the logic,
   not the on-device paths. The spike's ping line prints the active
   data dir so a wrong path is visible, not silent.
3. **APK size** — the 22 MB data bundle plus a Python runtime per
   ABI (arm64-v8a + x86_64). Acceptable for a debug spike; ABI
   splits / bundle trimming are Phase 4 concerns.
4. **Float formatting across runtimes** — desktop proof is exact
   under CPython 3.12; the device comparison's 1e-9 guard band
   (PARITY.md) exists for the Chaquopy runtime, and a DIFF result
   prints the first mismatching field rather than failing silently.

---

# BUILD-LOG — v1.0.0 Complete Edition (Scare Bets), 2026-10-31

The Jetpack scaffold filled to production-ready under the
Pilot's order ("Grand BetFi" at order time; rebranded mid-build,
see below). **Not pushed, not committed** — Praxis verifies,
combines, pushes. The Flet app (13.2.0 / build 55) remains the
shipping app until native parity + the Pilot's device verdict.

## Rebrand — SCARE BETS (Pilot order, 2026-10-31 evening)

"Betfi is no more." Display name is now **Scare Bets** (app
label, strings, Compose titles/headers, docs). Logo: the
Pilot-supplied chrome-ghost/barbell artwork, source file
`~/workspace/user/files/91941_2_959z.jpg` (2048×2048 JPEG),
copied byte-identical to `res/drawable/scare_bets_logo.jpg` and
shown in the Board header; launcher icons generated from it
with PIL — legacy `mipmap-{mdpi..xxxhdpi}/ic_launcher(.png|_round.png)`
(48–192 px) and an adaptive icon (`mipmap-anydpi-v26/ic_launcher.xml`:
foreground = logo fitted into the safe zone on the board color
#0B0F14, `res/values/colors.xml`). UNVERIFIED until an Actions
compile + device install: adaptive-icon masking/rendering on
the Fold. Internals deliberately NOT renamed: applicationId
stays `com.betfi.xii`; package/class names stay; engine file
names stay (one-engine law).

## Tier 1 — bridge completeness (desktop-verified, this VM)

`native/app/src/main/python/engine/history_store.py` verified
byte-identical to the shipping copy (md5
`2ea2d7b7f0451790055123efd91a003e`, both). Engine md5 across all
copies (clone root, native, lab scripts, apk-repo):
`8b0e6565469b29d5435a7b77138517b1` — unchanged.

bridge.py grew (all adaptation in the bridge; engine and store
never edited): writable history store via init(); `build_and_run`
replicating main.py's FanDuel pull path — full pull + scoped
pull with build-55 slice honesty (a scoped pull records ONLY
its slice; the error merge dedupes to a no-op; the scoped menu
harvest runs inline instead of the Flet background thread — a
flagged deviation, same token-guarded merge); card payloads
with bet identity + the five depth sections as data
(PRICE ANATOMY / THE MATHEMATICS / SCALE / COHERENCE /
PROVENANCE via `depth_json_text`); finds distillation; the
Protected Slip (quarter-Kelly, 5% cap, combined odds, max loss
= total stake, persisted mark-placed); Lab payload (recorder
health: history_begins + counts); `slate_json` / `history_json`
in the DATA-CONTRACT shapes with named errors
(unknown_graph / unknown_window); Stocks bridge (Nasdaq pull
ports + engine Organ 9 views; WATCH-only; <5 DTE suppression
comes from the engine view itself; the only SELL text anywhere
is the holdings stamp "SELL: WATCH (no examined lane)"); and
`spatial_json` for the 3D destination. Text-arg wrappers
(`slip_json_text` / `depth_json_text` / `mark_placed_text` /
`set_holding_text_json`) give Kotlin one parse rule
(main.py's _parse_bankroll: blank/invalid -> None).

Desktop drive results (fresh store, this VM):
- Parity: `run_slate_json(sample)` == reference verdicts —
  EXACT, 25/25, all fields, all floats.
- Board over the 1,402-market reference slate reproduces the
  recorded pricing census exactly: 1,140 PRICED / 262 UNPRICED /
  491 bet_now / 0 GOLDEN; slate payload = 462 events.
- Recorder: two recorded pulls -> 2 records / 2,804 recorded
  markets on file; a re-record of the same stamp dedupes.
- Depth: all five sections present for a priced card.
- Slip: empty pull -> 0 candidates, honest empty payload;
  mark-placed on an empty slip -> {"error": "empty_slip"},
  nothing written.
- Spatial: after two pulls, terrain grid 46/576 cells filled,
  200 paths (the G1 cap, stated in the payload), slate cloud
  1,140 points, 0 unknown-z points.
- LIVE FanDuel scoped pull (nfl) from this VM: LANDED — 253
  markets, 253 priced, 108 bet_now, 37 GOLDEN on the live
  slate, recorder status "recorded". (The live slate is not
  the stale census slate; counts differ because the menu is
  live, and the GOLDEN count is the engine's own verdicts.)
- LIVE Nasdaq pull (MSTR) from this VM: LANDED — spot 130.51,
  17 chain expiries; options grid for 2026-11-06 (6 DTE, not
  short-dated): 47 rows; tape view action WATCH. One wart,
  stated plainly: the historical-bars parse came back with 0
  rows under the probe's key on this pull, so realized vol may
  print unavailable until the history shape is re-checked
  against the live response — quotes/chains are unaffected.

A repeatable drive script lives at `native/drives/drive_bridge.py`.

## Tiers 2–5 — Kotlin (UNVERIFIED compile)

Seven destinations in the shell (Board, Finds, Slip, Lab, 3D,
Stocks, Betterama), adaptive rail/bar, AppViewModel + StateFlow,
every Python call on EngineBridge.PythonDispatcher (single
thread) or Dispatchers.IO — never the main thread. Board:
receipt line, sport chips, Show control (All default), full +
scoped pulls, flashing BET NOW box (1.6 s, alpha 0.45↔1.0)
opening the exact QuickSlip URL via Intent when armed, and the
pull-again honesty state when ids are absent. Finds: GOLDEN
panel under the unchanged gate law. Slip: Protected Slip with
two-step mark-placed, persisted. Lab: engine identity, recorder
health verbatim, parity spike kept working. Stocks: TAPE /
MATRIX / OPTIONS / HOLDINGS against the real bridge shapes,
holdings persist via the bridge state files.

3D is TRUE spatial 3D: `SpatialRenderer.kt` (OpenGL ES 2.0,
GLSurfaceView) — perspective projection, terrain as a triangle
mesh from `spatial_json` grid heights (null cells stay holes),
slate point cloud as GL_POINTS (golden = #FFD700, bet_now =
ice), axes + ground grid, drag-orbit + pinch/button zoom.
Axis mapping (also in PROGRAM.md and the renderer header):
x = implied probability, y = edge, z = time in hours. TIME
control: Live | 1 Month | Season. The Flet HTML instruments
are NOT in the native app (an interim WebView variant +
loopback server written during the build was removed in
reconciliation; nothing references it).

Betterama: shell only — title "Betterama" + the verbatim stamp
"Betterama — new. Definition being locked." No features, no
fake data.

Production config: versionName "1.0.0" / versionCode 1;
release minify + shrinkResources + `proguard-rules.pro`
(Chaquopy keeps); signing from optional gitignored
`keystore.properties` — ABSENT here, so the release is
UNSIGNED, and the CI release artifact is likewise unsigned
(workflow says so). build-native.yml also runs
assembleRelease and uploads both artifacts. Manifest gained
INTERNET + ACCESS_NETWORK_STATE (the pull path needs them)
and the Scare Bets icon wiring.

## NOT verified (unsoftened)

- **Kotlin has never been compiled.** No JDK exists in this
  VM; the first GitHub Actions run is the first compile. The
  known first-build risks from Phase 0/1 stand (version pins,
  the Chaquopy KTS DSL block), now joined by ~4,900 lines of
  new Kotlin that no compiler has seen. Expect pin/syntax
  churn on the first run; BUILD-LOG records the working set
  when it lands.
- On-device parity spike has not printed MATCH (needs the
  Actions APK + the Fold).
- Adaptive icon rendering on-device is unverified (above).
- Chaquopy extraction of the 22 MB bundle + the writable-store
  seeding are desktop-proven logic, not device-proven paths.
- The Nasdaq history-bars wart (above): RV may print
  unavailable on live pulls until re-checked.

## Praxis combine entry — 2026-10-31 (supersedes the "not verified" tail above)

- **Kotlin HAS been compiled — locally.** Toolchain installed in
  the authoring VM (~/workspace/toolchain: Temurin JDK 17.0.21,
  Gradle 9.7.1, Android SDK platforms 36/37, build-tools 36/37).
  The Phase 0/1 scaffold compiled first (debug + release), then
  THIS tree: **assembleDebug BUILD SUCCESSFUL, assembleRelease
  BUILD SUCCESSFUL** (R8 minify + resource shrink executed).
  Logs: ~/workspace/toolchain/scare-debug-build.log and
  scare-release-build.log.
- Compile fixes required (2 files, 7 line edits — already in this
  tree): LabScreen.kt now reads the typed LabInfo model fields
  (engine / markedSlips / recorder / latestPull) instead of raw
  JSONObject access; MainActivity.kt gained the missing
  `androidx.compose.ui.unit.dp` import. After the fixes: zero
  errors, zero warnings.
- One pin defect the local build caught (would have failed on
  Actions identically): the Compose BOM 2026.09.00 line
  (androidx.compose.ui 1.12.1) requires API 37 — compileSdk and
  targetSdk raised 36 → 37 in app/build.gradle.kts, and
  build-native.yml now installs platforms;android-37.0 +
  build-tools;37.0.0 with an explicit sdkmanager step.
- aapt2 badging (both APKs): com.betfi.xii, versionCode 1,
  versionName 1.0.0, label "Scare Bets", compileSdk/targetSdk 37.
  Debug APK 55,024,193 bytes; release (unsigned) 44,297,502 bytes.
  Logo packaged byte-identical (431,531 B); Chaquopy app bundle
  carries bridge + engine + history_store + the data bundle.
- **The Nasdaq history-bars wart is DEAD.** Praxis live-pulled
  all six names through this bridge: 6 of 6 fresh, realized vol
  populated for every name (MSTR cc20 73.96% / cc60 86.53% /
  EWMA94 78.24%, 250 returns). The 0-rows readings were probe
  artifacts (wrong key / wrong window in the probes, not the app
  path — the bridge parser emits "bars" exactly as main.py and
  the engine's stock_quote_view reads "bars").
- Still genuinely unverified: on-device runtime (parity spike
  MATCH, spatial GL rendering, adaptive-icon masking, Chaquopy
  on-device extraction). Compilation, packaging, and every
  desktop drive are proven; the device verdict is the Pilot's.
