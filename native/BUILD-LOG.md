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
