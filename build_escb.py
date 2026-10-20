#!/usr/bin/env python3
"""
build_escb.py — the .escb v2 builder (ESCB/2 ruleset).

Reads the canonical repo pair (main.py + betmodel5.py), wraps them
VERBATIM (zero adaptations — v2 eliminates v1's three) in a ZIP
container prefixed with a shebang line, which makes the bundle:
  * executable:   python3 BetFi-10.escb        (zipapp semantics)
  * a plain zip:  cp BetFi-10.escb x.zip && unzip x.zip
Entries, in order: ESCB.json (manifest, STORED so it is readable
without decompression), __main__.py (bootstrap: verify, resurface,
run), then the payload files (DEFLATE, level 9).

Usage: python3 build_escb.py SRC_DIR OUT.escb PRODUCT MAJOR
"""
import sys, os, json, zipfile, hashlib, datetime

BOOTSTRAP = r'''#!/usr/bin/env python3
"""ESCB/2 bootstrap (__main__.py inside the bundle).

On execution: locate the containing archive, verify every payload
file against ESCB.json (sha256 + size), resurface the payload
byte-identical into a cache directory keyed by the bundle hash, and
run the entry point from there — so the payload runs under its real
filenames, with its real imports, unmodified.

Modes:
  (none)          verify, resurface, run the entry point
  --verify        verify only; print the manifest summary
  --resurface DIR extract payload files to DIR; run nothing
  --engine        resurface, import the engine, print its version
                  and the file fingerprint the app itself computes
"""
import os, sys, json, zipfile, hashlib, runpy

def _archive_path():
    loader = globals().get("__loader__")
    arc = getattr(loader, "archive", None)
    if arc and os.path.isfile(arc):
        return arc
    return os.path.abspath(sys.argv[0])

def _load():
    arc = _archive_path()
    zf = zipfile.ZipFile(arc)
    man = json.loads(zf.read("ESCB.json").decode("utf-8"))
    return arc, zf, man

def _verify(zf, man):
    for f in man["files"]:
        data = zf.read(f["name"])
        h = hashlib.sha256(data).hexdigest()
        if h != f["sha256"] or len(data) != f["bytes"]:
            raise SystemExit(f"ESCB verify FAILED: {f['name']} hash/size mismatch")
    return True

def _resurface(zf, man, dest):
    os.makedirs(dest, exist_ok=True)
    for f in man["files"]:
        name = f["name"]
        if name.startswith("/") or ".." in name.split("/"):
            raise SystemExit(f"ESCB resurface REFUSED: unsafe entry {name}")
        out = os.path.join(dest, name)
        if os.path.isfile(out) and os.path.getsize(out) == f["bytes"] and \
           hashlib.sha256(open(out, "rb").read()).hexdigest() == f["sha256"]:
            continue
        with open(out, "wb") as fh:
            fh.write(zf.read(name))
    return dest

def _cache_dir(man):
    base = os.environ.get("ESCB_CACHE") or os.path.join(
        os.path.expanduser("~"), ".cache", "escb")
    return os.path.join(base, f"{man['product']}-{man['bundle_id'][:12]}")

def main(argv):
    arc, zf, man = _load()
    _verify(zf, man)
    if "--verify" in argv:
        print(f"ESCB/2 OK · {man['product']} {man['app_version']} "
              f"(build {man['build']}) · engine {man['engine_version']} · "
              f"bundle {man['bundle_id'][:12]} · {len(man['files'])} files verified")
        return 0
    if "--resurface" in argv:
        dest = argv[argv.index("--resurface") + 1]
        _resurface(zf, man, dest)
        print(f"Resurfaced {len(man['files'])} files to {dest}")
        return 0
    dest = _resurface(zf, man, _cache_dir(man))
    if "--engine" in argv:
        sys.path.insert(0, dest)
        import betmodel5 as b5
        import hashlib as hl
        blob = open(os.path.join(dest, "betmodel5.py"), "rb").read()
        print(f"engine {b5.ENGINE_VERSION} · sha256 {hl.sha256(blob).hexdigest()[:12]}"
              f" · {len(blob)} bytes · from {dest}")
        return 0
    sys.path.insert(0, dest)
    sys.argv = [os.path.join(dest, man["entrypoint"])] + \
               [a for a in argv[1:] if not a.startswith("--escb")]
    runpy.run_path(sys.argv[0], run_name="__main__")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
'''

def sha(b): return hashlib.sha256(b).hexdigest()

def main():
    src, out, product, major = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    files = []
    blobs = {}
    for name in ("betmodel5.py", "main.py"):
        data = open(os.path.join(src, name), "rb").read()
        blobs[name] = data
        files.append({"name": name, "bytes": len(data), "sha256": sha(data)})
    bundle_id = sha("".join(f["sha256"] for f in files).encode())
    # app/engine versions read from the sources themselves, never typed twice
    eng_ver = next(l.split('"')[1] for l in blobs["betmodel5.py"].decode().splitlines()
                   if l.startswith("ENGINE_VERSION"))
    app_ver = next(l.split('"')[1] for l in blobs["main.py"].decode().splitlines()
                   if l.startswith("APP_VERSION"))
    build = next(l.split("=")[1].strip() for l in blobs["main.py"].decode().splitlines()
                 if l.startswith("BUILD_NUMBER"))
    manifest = {
        "format": "escb/2", "product": product, "major": int(major),
        "app_version": app_ver, "build": int(build), "engine_version": eng_ver,
        "entrypoint": "main.py", "bundle_id": bundle_id,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "compression": "zip-deflate-9", "files": files,
    }
    man_bytes = json.dumps(manifest, indent=2).encode()
    with open(out, "wb") as fh:
        fh.write(b"#!/usr/bin/env python3\n")
        with zipfile.ZipFile(fh, "w") as zf:
            zf.writestr(zipfile.ZipInfo("ESCB.json"), man_bytes,
                        compress_type=zipfile.ZIP_STORED)
            zf.writestr(zipfile.ZipInfo("__main__.py"), BOOTSTRAP.encode(),
                        compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            for name, data in blobs.items():
                zf.writestr(zipfile.ZipInfo(name), data,
                            compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    print(f"Wrote {out}: {os.path.getsize(out)} bytes · bundle {bundle_id[:12]} · "
          f"engine {eng_ver} · app {app_ver} build {build}")

if __name__ == "__main__":
    main()
