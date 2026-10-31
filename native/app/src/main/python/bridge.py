"""BetFi Xii native bridge — the ONLY adapter between the Compose shell
and the embedded engine.

The engine (betmodel5.py) is byte-identical to the shipping engine and
is NEVER edited for the native app (one-engine law, see ../PROGRAM.md).
Everything device-specific lives here:

Layout contract
---------------
The engine resolves its data at import time:

    HERE = dirname(abspath(__file__))          # engine/betmodel5.py
    DATA = join(HERE, "..", "data")            # -> python/data
    RESULTS = join(HERE, "..", "results")
    CACHE = join(DATA, "cache")
    ~40 module-level *_PATH constants derived from DATA

This tree ships exactly that layout:

    python/bridge.py            (this file)
    python/engine/betmodel5.py  (byte-identical engine)
    python/data/...             (the evidence-pack bundle: fit JSONs,
                                 scorecard, lane history, phi registry,
                                 gamelog/league caches — the same files
                                 the Flet app bundles from repo data/)

so with NO init() call the engine's defaults already resolve to the
bundled data (that is how the desktop parity drive runs).

On device the Chaquopy-extracted tree may be read-only or wiped on
app update, and other engine flows (pull caches, scorecard saves)
need somewhere writable. The shell therefore calls init() once with
the app's private files dir BEFORE the first run: init seeds a
writable data dir from the bundle (missing files only — device state
is never overwritten) and repoints every engine path global onto it,
the same runtime adaptation the Flet shell performs. run_slate
itself only reads; the repoint protects the flows that write.
"""

import json
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENGINE_DIR = os.path.join(_HERE, "engine")
_BUNDLED_DATA = os.path.join(_HERE, "data")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

_engine = None
_data_dir = _BUNDLED_DATA


def _load_engine():
    global _engine
    if _engine is None:
        import betmodel5 as b5
        _engine = b5
    return _engine


def _repoint(b5, data):
    """Move every engine path global that was derived from the
    import-time DATA/RESULTS roots onto `data`. Generic on purpose:
    the engine grows new *_PATH constants as lanes are added, and a
    hand-maintained list silently misses the new ones."""
    old_data = os.path.abspath(b5.DATA)
    old_results = os.path.abspath(b5.RESULTS)
    for name in dir(b5):
        if name in ("DATA", "RESULTS", "CACHE"):
            continue
        val = getattr(b5, name)
        if not isinstance(val, str):
            continue
        ap = os.path.abspath(val)
        for old in (old_data, old_results):
            if ap == old or ap.startswith(old + os.sep):
                setattr(b5, name, os.path.join(data, os.path.relpath(ap, old)))
                break
    b5.DATA = data
    b5.RESULTS = data
    b5.CACHE = os.path.join(data, "cache")


def init(writable_dir):
    """Seed + repoint. Called by the shell once, before any run.

    writable_dir: an app-private writable directory (Android
    filesDir). The engine data lives under <writable_dir>/engine-data.
    Returns the active data dir. Never raises: on any failure the
    engine keeps its bundled defaults and the failure is reported
    in the return value's companion — see init_status()."""
    global _data_dir
    try:
        data = os.path.join(writable_dir, "engine-data")
        os.makedirs(os.path.join(data, "cache"), exist_ok=True)
        # Seed missing files from the bundle (top level + cache/).
        for base_src, base_dst in ((_BUNDLED_DATA, data),
                                   (os.path.join(_BUNDLED_DATA, "cache"),
                                    os.path.join(data, "cache"))):
            if not os.path.isdir(base_src):
                continue
            for fn in sorted(os.listdir(base_src)):
                sp = os.path.join(base_src, fn)
                dp = os.path.join(base_dst, fn)
                if os.path.isfile(sp) and not os.path.exists(dp):
                    shutil.copyfile(sp, dp)
        _repoint(_load_engine(), data)
        _data_dir = data
        _init_status.update(ok=True, data_dir=data, error=None)
    except Exception as e:  # the shell must never die over storage
        _init_status.update(ok=False, data_dir=_data_dir,
                            error=f"{type(e).__name__}: {e}")
    return _data_dir


_init_status = {"ok": None, "data_dir": _BUNDLED_DATA, "error": None}


def init_status():
    return json.dumps(_init_status)


def ping():
    """Engine identity for the shell's status line: version, the
    file actually imported, and the active data dir."""
    b5 = _load_engine()
    return json.dumps({
        "engine_version": getattr(b5, "ENGINE_VERSION", "unknown"),
        "engine_file": os.path.abspath(b5.__file__),
        "data_dir": os.path.abspath(b5.DATA),
        "init": _init_status,
    })


def run_slate_json(slate_json_str):
    """slate JSON text -> verdicts JSON text.

    The exact desktop-proven path: json.loads -> b5.run_slate ->
    json.dumps. run_slate returns one verdict dict per market, in
    slate order; every value is JSON-native (proven on desktop)."""
    b5 = _load_engine()
    slate = json.loads(slate_json_str)
    verdicts = b5.run_slate(slate, print_out=False)
    return json.dumps(verdicts)
