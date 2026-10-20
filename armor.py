#!/usr/bin/env python3
"""
armor.py — ESCB/2 encoded-transmission profile (ESCB-T).

Wraps a binary .escb bundle as a single all-text Python file:
base85 of the exact bundle bytes, 100-char lines, between
BEGIN/END markers, with the bundle sha256 in the header. The
armored file is itself executable: it decodes its payload to the
bundle cache, then runs the decoded bundle's own modes
(--verify / --resurface / --engine / app). Armor MUST round-trip
byte-identical: sha256(decoded) == header sha256, or it refuses.

Usage: python3 armor.py BetFi-10.escb BetFi-10-armored.escb
"""
import sys, base64, hashlib, textwrap

STUB_HEAD = '''#!/usr/bin/env python3
"""
ESCB-T armored transmission form of {name}.
Inner bundle: ESCB/2, sha256 {digest}
Decode: strip this stub, base85-decode PAYLOAD, write the .escb.
This file decodes itself: python3 {name} [--verify|--resurface D|--engine]
"""
import base64, hashlib, os, sys

_DIGEST = "{digest}"
_NAME = "{name}"

'''

STUB_TAIL = '''

def _main():
    raw = base64.b85decode("".join(PAYLOAD.split()))
    if hashlib.sha256(raw).hexdigest() != _DIGEST:
        raise SystemExit("ESCB-T armor FAILED: inner bundle hash mismatch")
    if "--dearmor" in sys.argv:
        dest = sys.argv[sys.argv.index("--dearmor") + 1]
        with open(dest, "wb") as fh:
            fh.write(raw)
        print(f"Dearmored to {dest} ({len(raw)} bytes, sha256 verified)")
        return 0
    cache = os.path.join(os.environ.get("ESCB_CACHE") or
                         os.path.join(os.path.expanduser("~"), ".cache", "escb"),
                         "armor")
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, _NAME)
    if not (os.path.isfile(path) and
            hashlib.sha256(open(path, "rb").read()).hexdigest() == _DIGEST):
        with open(path, "wb") as fh:
            fh.write(raw)
    os.execv(sys.executable, [sys.executable, path] +
             [a for a in sys.argv[1:]])

if __name__ == "__main__":
    raise SystemExit(_main())
'''

def main():
    src, out = sys.argv[1], sys.argv[2]
    raw = open(src, "rb").read()
    digest = hashlib.sha256(raw).hexdigest()
    name = src.split("/")[-1]
    b85 = base64.b85encode(raw).decode()
    wrapped = "\n".join(textwrap.wrap(b85, 100))
    with open(out, "w") as fh:
        fh.write(STUB_HEAD.format(name=name, digest=digest))
        fh.write('PAYLOAD = """\n' + wrapped + '\n"""\n')
        fh.write(STUB_TAIL)
    import os
    print(f"Wrote {out}: {os.path.getsize(out)} bytes (bundle {len(raw)}, "
          f"armor overhead {os.path.getsize(out)-len(raw):+}) sha256 {digest[:12]}")

if __name__ == "__main__":
    main()
