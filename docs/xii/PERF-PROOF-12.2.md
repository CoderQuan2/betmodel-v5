# BetFi Xii 12.2.0 (build 18) — performance proof

Worktree: `~/workspace/bets-analyst/mobile/xii-perf`
Changed files: `betmodel5.py`, `main.py`, `harness.py`, `README.md`,
`.github/workflows/build-apk.yml`. The clone and lab were not touched.
Nothing was committed or pushed.

## Verdict identity A/B — saved slate `/tmp/perf_slate.json`

Method: the same saved 1,400-market slate, both engines loaded through
the shell's harness repoint/storage path, each market priced with
`run_checker(mkt, {"verified": True})`. The old engine was extracted
from the clone at HEAD (`git show HEAD:betmodel5.py`).

| Engine | Price-pass wall time | PRICED | Verdict SHA-256 |
|---|---:|---:|---|
| Old (HEAD) | 6.4316 s | 790 | `f1a4770cf0325ee19ba8c6d5d5e4538d590a40d7c08bd7ccb4e284f48ea17873` |
| New (12.2.0) | 0.2974 s | 790 | identical |

Field-by-field comparison: **1,400 identical, 0 differing.**

Note on the baseline: Praxis's profile quoted 19.19 s; on this machine
and this saved slate the old engine measured 6.4316 s. The measured
speedup on the same slate and same harness path is therefore
**21.6×** (6.4316 s → 0.2974 s), not a comparison against the 19.19 s
profile number.

## Live pull A/B — `pull_menu()`

| Shell | Wall time | Markets | Sport errors | Event menus / errors |
|---|---:|---:|---:|---:|
| Old sequential shell (clone) | 73.641 s | 1,402 | 0 | 8 / 0 |
| New parallel shell (worktree) | 13.645 s | 1,404 | 0 | 8 / 0 |

Speedup: **5.4×**. The market-count difference is live-board drift
between the two runs (about a minute apart): table tennis went
32 → 34; every other per-sport count was identical, the sport
sequence was identical, and the event-menu key set and per-menu
distinct-market counts were identical. The raw market hashes differ
only because odds/board entries moved between the two live runs.

## Fingerprint-cache proof — full 1,400-market slate

Using the shell's `_price_markets_cached` helper:

- First pass: **1,400 checker calls, 0.428 s**, verdicts exactly equal
  to a full `run_slate` pass on the same slate.
- Second pass over the same slate: **0 checker calls, 0.018 s**,
  verdicts identical to the first pass.
- Five markets' odds mutated (indices 0, 349, 699, 1049, 1399):
  **exactly 5 checker calls, 0.019 s**, and the result exactly
  equals a full fresh `run_slate` pass over the mutated slate
  (same SHA-256).

## Gzip / thread-safety proof

`fd_get` previously used the shared `urllib.request.urlopen` global
opener. `fetch_menu_json` now builds a fresh opener per call, sends
`Accept-Encoding: gzip`, and decompresses only when the response
`Content-Encoding` contains `gzip`. A local threaded HTTP test
returned gzip JSON on 16 parallel calls: all 16 decoded correctly
and every request carried `Accept-Encoding: gzip`.

## Harness

- `harness.py`: **159/160 checks passed**.
- Sole failure: `one-engine law: clone engine == lab engine` —
  expected in the worktree, because the lab copy is still the old
  engine and Praxis syncs it at merge. It was not silenced by
  editing the lab.
- `smoke_serialize.py`: **PASS — 3,803 controls scanned, no
  set-valued fields**.
- `py_compile` clean on `betmodel5.py`, `main.py`, `harness.py`.

## Design notes / caveats

- Name indexes assume fit dictionaries are immutable after load, the
  same contract as the existing `_FIT_CACHE`. Index caches hold
  strong references to the indexed dicts (so `id()` cannot be
  recycled onto a different dict), and the soccer and tennis
  indexes additionally validate the strengths/elo object identity.
- The verdict fingerprint covers the complete market record (a
  conservative superset of the requested sport/event/teams/market/
  selection/line/odds fields), plus a hash of fit/record file
  mtimes and sizes, plus the slate context that can change a
  verdict (verified/source/degraded state; the full stamp for an
  unverified slate). A fit rewrite, scorecard change, or slate
  context change invalidates the cache.
- Live-pull timings are network-dependent; the saved-slate numbers
  are the reproducible primary evidence.
