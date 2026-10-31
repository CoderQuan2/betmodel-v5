# PARITY — the engine-parity contract for the native build

Phase 1's whole question: does the byte-identical engine, embedded
via Chaquopy, produce the same verdicts on-device as it does on
desktop? This file defines what "the same" means, records what has
been proven where, and documents exactly how the engine finds its
data (the finding the embedding is built on).

## Engine data-path findings (inspected in betmodel5.py, build 54)

All line numbers are the shipping engine at HEAD 5b8e828.

- **Import-time roots** (lines 171–174):
  `HERE = dirname(abspath(__file__))`,
  `DATA = join(HERE, "..", "data")`,
  `RESULTS = join(HERE, "..", "results")`,
  `CACHE = join(DATA, "cache")`.
- **~40 module-level `*_PATH` constants** are derived from `DATA` at
  import time: `PHI_PATH` (v5-phi.json), `HISTORY_PATH`
  (v5-lane-history.json), `NFL_PRICING_PATH`, `SCORECARD_PATH`, and
  one `*_FIT_PATH` per lane (NBA/WNBA/MLB/tennis/MMA/cricket/rugby/
  F1/soccer/CFL, the European basketball leagues, the European
  hockey leagues, segments, outrights, …). Because they bind at
  import, repointing `b5.DATA` alone does NOT move them — any
  runtime adaptation must rewrite each constant (the Flet shell
  repoints a hand-maintained subset; `bridge.py` rewrites every
  string attribute rooted under the old DATA/RESULTS, generically,
  so future lanes are covered automatically).
- **Dynamic joins**: several loaders build paths from `DATA` at call
  time (`os.path.join(DATA, fn)`), so those follow a repoint for free.
- **The engine is pure stdlib.** Import list (lines 155–169):
  argparse, gzip, itertools, json, math, os, random, statistics,
  sys, time, unicodedata, urllib.request, concurrent.futures,
  datetime, functools. `requests` is forced to None by design; the
  urllib branch serves every fetch. **Chaquopy needs zero pip
  installs.**
- **`run_slate` is read-only.** Proven by manifest diff: a full
  1,402-market run against the bundle changed/added/removed zero
  data files. The engine's writes live in other flows (fetch-through
  caches, scorecard saves, fit refits) — those are why `bridge.init`
  still seeds a writable data dir on device.
- **Two data dirs exist in the lab and they diverge.** The lab's
  live dir (`mobile/data`, what a desktop run from the repo root
  reads) and the app-shipping bundle (`data/` in the repo, what the
  Flet app carries) agree byte-for-byte on every top-level fit JSON
  sampled, but their `cache/` trees differ: the bundle carries the
  stripped gamelog cache + league game-history caches the app needs;
  the lab dir carries fresher full gamelogs and the CFB/NHL daily
  files. The native app ships **the bundle** — it is the app's
  record, and on the 25-market parity sample the two data sets
  produce identical verdicts (cross-check below).
- **Nothing the engine needs fails to ship.** Every file `run_slate`
  reads is a plain JSON in the bundle. The one path family not
  exercised by `run_slate`: the `menu-fanduel-*.json` latest-pull
  reader and the `RESULTS` listings live in `run_regression()` and
  diagnostics only. On device `bridge` repoints `RESULTS` onto the
  data dir (the shipping shell does the same) so no flow reaches
  for a sibling that does not exist in the APK layout. Flagged for
  Phase 2, when pull flows arrive — not a parity blocker.

## The shipped layout (why no engine edit was needed)

```
app/src/main/python/bridge.py            the only adapter
app/src/main/python/engine/betmodel5.py  byte-identical (md5 below)
app/src/main/python/data/...             the bundle: HERE/../data
                                         resolves correctly by
                                         construction
app/src/main/assets/sample_slate.json    25 markets (below)
app/src/main/assets/reference_verdicts.json   copy of parity/reference_verdicts.json
parity/reference_verdicts.json           canonical reference dump
```

Engine md5 (all copies): `8b0e6565469b29d5435a7b77138517b1`.
Reference/assets md5: `53435a87f6cdfba257abc06339029b97` — the
assets copy and the parity copy must always regenerate together.

## The sample slate

25 markets drawn deterministically (even spread per bucket) from
`perf-ab/slate.json` (the 1,402-market reference pull): **18 PRICED
(8 with bet_now true, 10 without) + 7 UNPRICED**, across ncaaf, nba,
soccer, tennis, boxing, nhl, lacrosse. Top-level slate context
(pulled_at/source/verified) preserved. Sanity anchors from the full
run: 1,140 PRICED / 262 UNPRICED / 491 bet_now — the recorded
pricing census, reproduced exactly by the bundle data. Subset
verdicts equal the full-slate verdicts at the same indices (checked),
so the sample represents the slate, not an artifact of subsetting.

## The canonical comparison

- **Key**: `sport|market|desc` from the verdict itself (unique on
  the sample — checked; if a future sample collides, extend the key,
  never loosen the compare).
- **Order**: both sides sorted by key.
- **Counts** must be equal.
- **Discrete fields** (string / boolean / null): exactly equal.
- **Numeric fields**: `|a−b| ≤ 1e-9 · max(1, |a|, |b|)`. Verdicts
  are flat (str/bool/float/null only — verified), and JSON doubles
  round-trip exactly between CPython and org.json, so the tolerance
  is a guard band, not expected drift.
- Implemented identically in `Parity.kt` (device) and the desktop
  drives (which use the stronger zero-tolerance form).

## What is proven, and where

| Proof | Where | Result |
|---|---|---|
| Engine copy byte-identical | desktop, md5 | PASS |
| Full slate on bundle data = recorded census (1,140/262/491) | desktop | PASS |
| Subset verdicts = full-slate verdicts at same indices | desktop | PASS |
| Reference generation (plain engine, bundle data) | desktop | `parity/reference_verdicts.json` |
| **Bridge drive**: `bridge.run_slate_json(sample)` == reference | desktop | **PASS — exact, all fields, all floats** |
| Cross-layout: lab data dir verdicts == bundle reference | desktop | PASS — exact |
| `bridge.init` seed + repoint, then run | desktop (fake filesDir) | PASS — 63 + 431 files seeded, paths moved, run still exact, device files survive re-init |
| Same comparison on-device (Chaquopy runtime) | **GitHub Actions build + device** | NOT YET RUN — this is the Phase 1 gate |

## Regenerating the reference

Any engine or bundle-data change invalidates the reference. Recipe
(desktop, from the worktree root): import the engine from
`native/app/src/main/python/engine` (so DATA resolves to the
bundle), run `run_slate(sample, print_out=False)` on
`assets/sample_slate.json`, dump with `json.dump(..., indent=1,
sort_keys=True)` to BOTH `parity/reference_verdicts.json` and
`assets/reference_verdicts.json`, then re-run the bridge drive and
record the result in BUILD-LOG.md. Never hand-edit a verdict.
