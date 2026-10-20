# .escb — Embedded Single-file Complete Bundle

Pronounced "dot ess-see-bee." A file type coined for BetFi (2026-10-20).
One file that carries a complete multi-file application: runnable as-is,
openable with ordinary tools, and lossless back to its sources.

## v1 — the prototype (shipped, repo commit e2ce7b1, v10.0; regenerated b3f96d5, v10.1)

Plain-text Python. PART 1: the engine source embedded verbatim as a
string, bound as module `b5`. PART 2: the shell with exactly three
marked adaptations (future-import hoisted to the header, the engine
import replaced by the binding, the Dev-screen fingerprint hashing the
embedded source). Size: 322,151 bytes (v10.0) / 327,088 bytes (v10.1) —
the full raw size of the sources; no compression.

Verified on the prototype (2026-10-20): bundle mirror byte-identical
between the repo clone and the lab mirror; embedded engine
byte-identical to repo `betmodel5.py` (sha256 d66da4238c1c…).

v1 errata, logged for the record (fixed by v2 design, not patched in v1):
- The bundle header's run line and the engine's `__file__` fallback
  still name the retired filename `BetFi-10-complete.py`.
- A naive `importlib` import of a `.escb` fails — Python does not
  know the extension; a `SourceFileLoader` must be named explicitly.
- No generator script existed in the repo: "generated, never
  hand-edited" was a rule without its tool.

## v2 — the ruleset (this spec; prototype built and verified 2026-10-20)

Design decision in one line: **an .escb v2 file is a ZIP archive with
a shebang line** — Python executes ZIP archives that contain a
`__main__.py` (zipapp semantics, shebang prefix explicitly supported),
and ZIP readers find the archive regardless of the prefix. One file,
three natures: executable, archive, and — through resurfacing — its
own sources again.

### The rules

- **R1 · Name.** Extension `.escb`, lowercase. Filename
  `<Product>-<Major>.escb`; product and major MUST match the manifest.
- **R2 · Container.** The file MUST be a valid ZIP archive, prefixed
  by nothing but one shebang line. It MUST open in Python `zipfile`,
  Info-ZIP `unzip`, and GUI archivers. Renaming it to `.zip` changes
  the name only, never a byte — **backwards compatible with .zip** is
  a conformance test, not a slogan.
- **R3 · Compression.** Payload entries MUST be ZIP DEFLATE
  (method 8), level 9 — native to the ZIP standard and the only codec
  every ZIP tool reads. BZIP2/LZMA ZIP entries are PROHIBITED in
  canonical bundles despite better ratios (measured below): a bundle
  Windows Explorer cannot open has failed its purpose.
- **R4 · Contents, exactly four kinds of entry, in order:**
  `ESCB.json` (manifest, STORED — readable without decompression),
  `__main__.py` (the bootstrap), then the payload files. No extras.
- **R5 · Manifest.** `ESCB.json` MUST carry: `format` ("escb/2"),
  `product`, `major`, `app_version`, `build`, `engine_version`,
  `entrypoint`, `bundle_id`, `created_utc`, `compression`, and
  `files[]` = {`name`, `bytes`, `sha256`} per payload file.
  `bundle_id` = sha256 of the concatenated per-file sha256 hex
  strings. Versions MUST be read from the sources by the builder,
  never retyped.
- **R6 · Payload verbatim.** Payload files MUST be byte-identical to
  the canonical sources. **Zero adaptations** — v2 deletes v1's
  three. Any hash mismatch with the manifest is a different build.
- **R7 · Bootstrap.** Stdlib only. On execution it locates its own
  archive, verifies every payload file against the manifest
  (sha256 + size) BEFORE running anything, and refuses on mismatch.
- **R8 · Resurfacing (extraction upon execution).** After verifying,
  the bootstrap resurfaces the payload — byte-identical, under its
  real filenames — into a cache keyed by product + bundle_id, and
  executes the entry point from there. The app therefore runs with
  its real imports, its real file-based fingerprint, and its real
  `main.py` entry name (the Flet build constraint) — unmodified.
  Cache hits are re-verified by hash, never trusted blind.
  Modes: `--resurface DIR` extracts and runs nothing; `--verify`
  verifies only; `--engine` imports the resurfaced engine and prints
  its version + fingerprint.
- **R9 · Safety.** Entry names MUST be flat relative filenames;
  absolute paths and `..` MUST be rejected. Nothing executes that was
  not hash-verified in the same run. The bundle writes only to its
  cache or an explicit `--resurface` target.
- **R10 · Transmission armor (ESCB-T).** For text-only channels
  (chat, canvas, email): the whole bundle base85-encoded (the
  most compact ASCII armor in the stdlib, 5 bytes → 4… 4 → 5),
  wrapped at 100 columns inside an executable Python stub whose
  header carries the inner bundle's sha256. The armored file MUST
  execute (decode → verify hash → cache → delegate to the bundle's
  own modes, plus `--dearmor FILE`), MUST be 100% printable ASCII,
  and MUST round-trip byte-identical. Armor is a transport form;
  the canonical form is the binary ZIP bundle.
- **R11 · Generation.** Never hand-edit an `.escb`. It is generated
  from the canonical sources by the named builder (`build_escb.py`)
  and regenerated in the same commit as any source change. The
  sources stay canonical; the bundle is the distribution form.
- **R12 · Legacy.** v1 plain-text bundles remain readable for
  inspection. Builders MUST NOT emit v1.
- **R13 · The floor.** If a future change breaks rename-to-`.zip`,
  stdlib-only execution, or hash-verified resurfacing, it is not
  an `.escb` anymore, whatever its extension says.

### Measured on the BetFi corpus (v10.1 sources: engine 218,335 B + shell 107,908 B = 326,243 B raw)

| Form | Bytes | vs v1 (327,088) |
|---|---|---|
| v1 plain-text prototype | 327,088 | — |
| zlib-9 raw (not a container) | 91,830 | 28.1% |
| bzip2-9 raw (prohibited in zip by R3) | 74,778 | 22.9% |
| lzma-9e raw (prohibited in zip by R3) | 76,540 | 23.4% |
| **v2 canonical (.escb = shebang + ZIP DEFLATE-9)** | **94,977** | **29.0%** |
| v2 armored (ESCB-T, all-ASCII, executable) | 121,653 | 37.2% |

### Prototype verification (2026-10-20, from repo HEAD b3f96d5 sources)

Built by `build_escb.py` (product BetFi, major 10) into this folder:
`BetFi-10.escb` (94,977 B) and `BetFi-10-armored.escb` (121,653 B).

- `unzip -l` on the `.escb` itself lists all 4 entries; renamed to
  `.zip` it extracts `main.py` + `betmodel5.py` **byte-identical**
  to the HEAD sources (cmp clean).
- `python3 BetFi-10.escb --verify` → ESCB/2 OK, 2 files verified.
- `--resurface DIR` → both files byte-identical (cmp clean).
- `--engine` → engine 5.2, sha256 d66da4238c1c · 218,335 bytes —
  identical to the repo engine fingerprint the Dev screen prints.
- Armor: compiles as plain Python, 100% printable ASCII,
  `--dearmor` output byte-identical to the binary bundle,
  `--verify` passes through the armor.
- Full execution: the bundle resurfaces, verifies, and runs
  `main.py` to its `ft.run(main)` call (line 2478) and into Flet's
  web-server startup. In the test venv it stops inside flet-web
  (`FastAPI.__init__() got an unexpected keyword argument
  'openapi_prefix'` — a flet-web/FastAPI version conflict).
  Control test: the plain HEAD `main.py`, run directly in the same
  venv, fails at the identical line — the bundle is
  behavior-equivalent to the sources; the failure is the venv's,
  not the format's.

### Open items / catches

- Source `BUILD_NUMBER` still reads 10 although the v10.1 commit
  message says build 11 — the manifest reports what the source says
  (R5); the discrepancy is the source's to fix.
- ESCB/2 was adopted into this repo after the prototype above:
  `BetFi-10.escb` here is the ESCB/2 bundle, and `build_escb.py`,
  `armor.py`, and this spec ship alongside it.
