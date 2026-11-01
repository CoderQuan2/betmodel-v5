"""Grand BetFi native bridge — the ONLY adapter between the Compose
shell and the embedded engine.

The engine (betmodel5.py) and the pull-history store
(history_store.py) are byte-identical to the shipping copies and
are NEVER edited for the native app (one-engine law, see
../PROGRAM.md). Everything device-specific lives here, including
the faithful ports of the Flet shell's (main.py's) pull assembly,
card naming/depth, finds distillation, Protected Slip arithmetic
and Nasdaq stocks pull — the shell's presentation logic moves
behind the bridge so the UI stays a renderer of JSON, exactly as
the Flet shell rendered engine verdicts. Every port names its
main.py source in its docstring; where the native shape forces a
deviation it is flagged inline and in ../BUILD-LOG.md.

Layout contract
---------------
The engine resolves its data at import time:

    HERE = dirname(abspath(__file__))          # engine/betmodel5.py
    DATA = join(HERE, "..", "data")            # -> python/data
    RESULTS = join(HERE, "..", "results")
    CACHE = join(DATA, "cache")
    ~40 module-level *_PATH constants derived from DATA

This tree ships exactly that layout:

    python/bridge.py              (this file)
    python/engine/betmodel5.py    (byte-identical engine)
    python/engine/history_store.py (byte-identical store)
    python/data/...               (the evidence-pack bundle)

so with NO init() call the engine's defaults already resolve to
the bundled data (that is how the desktop parity drive runs).

On device the Chaquopy-extracted tree may be read-only or wiped
on app update, and the pull flows (caches, the history store, the
last-pull snapshot, holdings, marked slips) need somewhere
writable. The shell therefore calls init() once with the app's
private files dir BEFORE the first run: init seeds a writable
data dir from the bundle (missing files only — device state is
never overwritten), repoints every engine path global onto it,
and arms the writable state files under the same dir.
"""

import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENGINE_DIR = os.path.join(_HERE, "engine")
_BUNDLED_DATA = os.path.join(_HERE, "data")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

_engine = None
_history = None
_data_dir = _BUNDLED_DATA
_writable_dir = None
_store_dir = os.path.join(_HERE, "history-store")


def _load_engine():
    global _engine
    if _engine is None:
        import betmodel5 as _b5mod
        _engine = _b5mod
        globals()["b5"] = _b5mod
        globals()["_NFL_FULL_NAMES"] = {
            code: name for name, code
            in _b5mod.FD_NFL_TEAM_CODES.items()}
    return _engine


def _load_history():
    global _history
    if _history is None:
        import history_store as hs
        _history = hs
    return _history


def _repoint(b5, data):
    """Move every engine path global that was derived from the
    import-time DATA/RESULTS roots onto `data`. Generic on
    purpose: the engine grows new *_PATH constants as lanes are
    added, and a hand-maintained list silently misses the new
    ones. (Unchanged from the Phase 0/1 scaffold.)"""
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
                setattr(b5, name,
                        os.path.join(data, os.path.relpath(ap, old)))
                break
    b5.DATA = data
    b5.RESULTS = data
    b5.CACHE = os.path.join(data, "cache")


def init(writable_dir):
    """Seed + repoint + arm the writable state. Called by the
    shell once, before any run.

    writable_dir: an app-private writable directory (Android
    filesDir). Engine data seeds under <writable_dir>/engine-data;
    the pull-history store lives under <writable_dir>/history-store
    (history_store appends its own pull-history/ dir); the last-pull
    snapshot, stocks snapshot, holdings and marked slips persist as
    JSON files directly under <writable_dir> — the Flet app's
    storage shapes, in the native app's own storage.

    Returns the active data dir. Never raises: on any failure the
    engine keeps its bundled defaults and the failure is reported
    through init_status(). Idempotent: seeding copies missing files
    only, so device state survives re-init."""
    global _data_dir, _writable_dir, _store_dir
    try:
        _writable_dir = writable_dir
        data = os.path.join(writable_dir, "engine-data")
        os.makedirs(os.path.join(data, "cache"), exist_ok=True)
        # Seed missing files from the bundle (top level + cache/).
        for base_src, base_dst in ((_BUNDLED_DATA, data),
                                   (os.path.join(_BUNDLED_DATA,
                                                 "cache"),
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
        _store_dir = os.path.join(writable_dir, "history-store")
        os.makedirs(_store_dir, exist_ok=True)
        _restore_state()
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

    The exact desktop-proven parity path: json.loads ->
    b5.run_slate -> json.dumps. run_slate returns one verdict
    dict per market, in slate order; every value is JSON-native
    (proven on desktop)."""
    b5 = _load_engine()
    slate = json.loads(slate_json_str)
    verdicts = b5.run_slate(slate, print_out=False)
    return json.dumps(verdicts)


# ==================================================================
# Standing state (the Flet shell's state["slate"] / state["stocks"]
# / state["holdings"], behind the bridge)
# ==================================================================

_standing = {"slate": None, "verdicts": None}
_stocks_state = {"names": {}, "note": ""}
_holdings = {}
_RECORDER_HEALTH = {"recorded": 0, "last_stamp": None,
                    "last_error": None}


def _state_path(name):
    if _writable_dir is None:
        return None
    return os.path.join(_writable_dir, name)


def _save_json_file(name, obj):
    path = _state_path(name)
    if path is None:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f)
    except Exception:
        pass  # persistence never breaks a pull (save_snapshot law)


def _load_json_file(name, default=None):
    path = _state_path(name)
    if path is None or not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_flagged(name, obj):
    """Save a snapshot dict with the divergence marker stamped
    on the FILE copy: "native_advanced": true. The native app's
    snapshots describe state the native bridge advanced; if a
    Flet-side loader ever meets one of these files (a shared-
    storage route, a manual copy), the flag is its instruction
    to SKIP the file rather than import native-advanced state
    as its own. The in-memory object is never stamped, so
    verdicts never see the key. (The two apps also hold separate
    private storage on-device — distinct applicationId — so the
    flag is defence in depth; see ../PROGRAM.md.)"""
    try:
        stamped = dict(obj)
        stamped["native_advanced"] = True
    except Exception:
        stamped = obj
    _save_json_file(name, stamped)


def _restore_state():
    """Boot restore, mirroring the Flet shell: the last pull is
    restored from its snapshot (load_snapshot), the stocks
    snapshot and holdings with it. Verdicts are NOT persisted —
    the shell reprices the restored slate through run_slate on
    first ask, exactly as the Flet shell's verdict cache starts
    cold."""
    global _holdings
    rec = _load_json_file("last-pull.json")
    if isinstance(rec, dict) and "markets" in rec:
        rec.pop("native_advanced", None)
        _standing["slate"] = rec
        _standing["verdicts"] = None
    names = _load_json_file("stocks-snapshot.json")
    if isinstance(names, dict) and names:
        names.pop("native_advanced", None)
        _stocks_state["names"] = names
    h = _load_json_file("holdings.json")
    if isinstance(h, dict):
        _holdings = {s: {"shares": float(v.get("shares") or 0),
                         "avg_cost": float(v.get("avg_cost") or 0)}
                     for s, v in h.items() if isinstance(v, dict)}


def _ensure_verdicts():
    """The standing slate's verdicts, priced through the engine's
    batch path (run_slate performs the same central stamping the
    Flet shell's per-market run_checker cache applies — cal_tag +
    stance on every PRICED verdict)."""
    rec = _standing.get("slate")
    if not rec:
        return None
    if _standing.get("verdicts") is None:
        b5 = _load_engine()
        _standing["verdicts"] = b5.run_slate(rec, print_out=False)
    return _standing["verdicts"]


# ==================================================================
# The FanDuel pull — ported from main.py (build 55): _fetch_sport_
# page / _sport_entry / _soonest_events / _fetch_event_menus /
# pull_menu / pull_menu_sport / merge_menu_harvest /
# merge_sport_pull, over engine functions only (b5.fd_get,
# b5.fd_parse_sport_page, b5.build_menu_tree, b5.fd_event_menu).
# ==================================================================

MENU_SOURCE = "FanDuel sbapi (Michigan) live pull"
EVENT_MENU_CAP = 8


def _fetch_sport_page(sport):
    """Fetch (only) one sport page, with its custom-page merge.
    Returns (sport, page, error): page XOR error. [main.py]"""
    b5 = _load_engine()
    try:
        page = b5.fd_get(b5.FANDUEL_PAGE_ENDPOINT, {
            "page": "SPORT",
            "eventTypeId": b5.FANDUEL_EVENT_TYPES[sport],
            "timezone": b5.FANDUEL_TIMEZONE})
        if sport in ("nfl", "nba", "nhl"):
            try:
                cpage = b5.fd_get(b5.FANDUEL_PAGE_ENDPOINT, {
                    "page": "CUSTOM", "customPageId": sport,
                    "timezone": b5.FANDUEL_TIMEZONE})
                att = page.setdefault("attachments", {})
                catt = cpage.get("attachments") or {}
                for key in ("events", "markets", "competitions"):
                    merged = dict(att.get(key) or {})
                    merged.update(catt.get(key) or {})
                    att[key] = merged
            except Exception:
                pass  # SPORT page only — degraded, not failed
        return sport, page, None
    except Exception as e:
        return sport, None, f"{type(e).__name__}: {e}"


def _sport_entry(sport, page, pulled_at):
    """Parse one fetched sport page into (stats entry, slate).
    [main.py]"""
    b5 = _load_engine()
    slate, inventory, n_games, routed = \
        b5.fd_parse_sport_page(page, sport)
    entry = {"games": n_games, "markets_on_page":
             sum(inventory.values()), "slate_markets": len(slate),
             "routed": routed, "pulled_at": pulled_at}
    return entry, slate


def _soonest_events(markets):
    """The soonest EVENT_MENU_CAP distinct events on a market
    list, as (event_id, market_time) pairs, soonest first.
    [main.py]"""
    seen = {}
    for m in markets:
        eid = m.get("fd_event_id")
        if eid is not None and eid not in seen:
            seen[eid] = m.get("market_time") or "9999"
    return sorted(seen.items(),
                  key=lambda kv: kv[1])[:EVENT_MENU_CAP]


def _fetch_event_menus(markets, pulled_at):
    """The per-game full-menu harvest over one market list.
    [main.py]"""
    b5 = _load_engine()
    soonest = _soonest_events(markets)

    def _fetch_one(item):
        eid, _t = item
        try:
            menu = b5.fd_event_menu(eid)
            menu["fetched_at"] = pulled_at
            return eid, menu
        except Exception as e:
            return eid, {"event_id": eid,
                         "error": f"{type(e).__name__}: {e}",
                         "fetched_at": pulled_at}

    menus = {}
    if soonest:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for eid, menu in pool.map(_fetch_one, soonest):
                menus[str(eid)] = menu
    return menus


def pull_menu() -> dict:
    """The full pull. [main.py pull_menu, verbatim structure]"""
    b5 = _load_engine()
    ts = datetime.now().astimezone()
    rec = {"pulled_at": ts.isoformat(timespec="seconds"),
           "source": MENU_SOURCE, "verified": False,
           "markets": [], "sports": {}}
    try:
        app_ctx = b5.fd_get(b5.FANDUEL_APP_CONTEXT_ENDPOINT, {
            "dataEntries": "POPULAR_BETTING,QUICK_LINKS,AZ_BETTING,"
                           "EVENT_TYPES,TEASER_COMPS"})
        tree = b5.build_menu_tree(app_ctx)
        rec["tree"] = {"event_types": tree["event_types"],
                       "az_order": tree["az_order"]}
    except Exception as e:
        rec["tree_error"] = f"{type(e).__name__}: {e}"
        return rec
    markets = []
    sports_in_order = list(b5.FANDUEL_EVENT_TYPES)
    with ThreadPoolExecutor(max_workers=8) as pool:
        fetched_pages = list(pool.map(_fetch_sport_page,
                                      sports_in_order))
    for sport, page, fetch_error in fetched_pages:
        if fetch_error is not None:
            rec["sports"][sport] = {
                "error": fetch_error,
                "attempted_at": rec["pulled_at"]}
            continue
        try:
            entry, slate = _sport_entry(sport, page,
                                        rec["pulled_at"])
            rec["sports"][sport] = entry
            markets += slate
        except Exception as e:
            rec["sports"][sport] = {
                "error": f"{type(e).__name__}: {e}",
                "attempted_at": rec["pulled_at"]}
    rec["markets"] = markets
    rec["verified"] = bool(markets)
    rec["event_menus"] = {}
    try:
        rec["event_menus"] = _fetch_event_menus(
            markets, rec["pulled_at"])
    except Exception as e:
        rec["event_menus_error"] = f"{type(e).__name__}: {e}"
    return rec


def pull_menu_sport(sport: str) -> dict:
    """The scoped pull: one sport's page only, no harvest (the
    harvest follows in build_and_run, inline — see the deviation
    note there). [main.py pull_menu_sport]"""
    b5 = _load_engine()
    if sport not in b5.FANDUEL_EVENT_TYPES:
        raise ValueError(f"unknown sport: {sport!r}")
    ts = datetime.now().astimezone()
    stamp = ts.isoformat(timespec="seconds")
    partial = {"pulled_at": stamp, "source": MENU_SOURCE,
               "verified": False, "sport": sport, "markets": [],
               "sports": {}, "event_menus": {},
               "menus_pending": []}
    _sport, page, fetch_error = _fetch_sport_page(sport)
    if fetch_error is not None:
        partial["sports"][sport] = {"error": fetch_error,
                                    "attempted_at": stamp}
        return partial
    try:
        entry, slate = _sport_entry(sport, page, stamp)
    except Exception as e:
        partial["sports"][sport] = {
            "error": f"{type(e).__name__}: {e}",
            "attempted_at": stamp}
        return partial
    pending = [str(eid) for eid, _t in _soonest_events(slate)]
    entry["menus_pending"] = pending
    partial["sports"][sport] = entry
    partial["markets"] = slate
    partial["verified"] = True
    partial["menus_pending"] = pending
    return partial


def merge_menu_harvest(slate, sport, menus, token):
    """Merge a menu harvest into the standing slate, guarded by
    the pull token. Returns the merged slate or None when the
    harvest is stale. [main.py merge_menu_harvest]"""
    if not slate:
        return None
    sports = slate.get("sports") or {}
    entry = sports.get(sport) or {}
    if entry.get("pulled_at") != token:
        return None
    on_slate = {str(m.get("fd_event_id"))
                for m in slate.get("markets") or []
                if m.get("fd_event_id") is not None}
    fresh = {k: v for k, v in (menus or {}).items()
             if k in on_slate}
    merged = dict(slate)
    all_menus = dict(slate.get("event_menus") or {})
    all_menus.update(fresh)
    merged["event_menus"] = all_menus
    new_entry = dict(entry)
    remaining = [eid for eid in new_entry.get("menus_pending")
                 or [] if eid not in fresh]
    if remaining:
        new_entry["menus_pending"] = remaining
    else:
        new_entry.pop("menus_pending", None)
    new_sports = dict(sports)
    new_sports[sport] = new_entry
    merged["sports"] = new_sports
    return merged


def merge_sport_pull(slate, partial):
    """Accumulate one sport's partial pull into the standing
    slate: the pulled sport's slice is REPLACED, every other
    sport's markets keep their objects and their order, each
    sport's stats entry keeps its own pulled_at. A FAILED
    scoped pull destroys nothing. [main.py merge_sport_pull]"""
    sport = partial["sport"]
    entry = (partial.get("sports") or {}).get(sport) or {}
    old = slate or {}
    old_sports = old.get("sports") or {}
    if "error" in entry:
        if not old.get("markets") and not old_sports:
            return {"pulled_at": partial["pulled_at"],
                    "source": old.get("source") or MENU_SOURCE,
                    "verified": False, "markets": [],
                    "sports": {sport: dict(entry)},
                    "event_menus": {}}
        sports = dict(old_sports)
        prev = dict(sports.get(sport) or {})
        prev["last_error"] = entry["error"]
        prev["last_attempt_at"] = partial["pulled_at"]
        sports[sport] = prev
        merged = dict(old)
        merged["sports"] = sports
        return merged
    drop = {sport}
    for src_entry in (old_sports.get(sport) or {}, entry):
        routed = src_entry.get("routed") or {}
        if isinstance(routed, dict):
            drop.update(routed.keys())
    drop.update(m.get("sport")
                for m in partial.get("markets") or [])
    drop.discard(None)
    old_markets = old.get("markets") or []
    kept = []
    insert_at = None
    dropped_ids = set()
    for m in old_markets:
        if m.get("sport") in drop:
            if insert_at is None:
                insert_at = len(kept)
            eid = m.get("fd_event_id")
            if eid is not None:
                dropped_ids.add(str(eid))
        else:
            kept.append(m)
    if insert_at is None:
        insert_at = len(kept)
    new_markets = (kept[:insert_at]
                   + list(partial.get("markets") or [])
                   + kept[insert_at:])
    new_ids = {str(m.get("fd_event_id"))
               for m in partial.get("markets") or []
               if m.get("fd_event_id") is not None}
    menus = {k: v for k, v in (old.get("event_menus") or {}).items()
             if k not in dropped_ids | new_ids}
    menus.update(partial.get("event_menus") or {})
    sports = dict(old_sports)
    sports[sport] = entry
    merged = dict(old)
    merged.update({
        "pulled_at": partial["pulled_at"],
        "source": old.get("source") or MENU_SOURCE,
        "verified": bool(new_markets),
        "markets": new_markets,
        "sports": sports,
        "event_menus": menus})
    merged.pop("event_menus_error", None)
    if partial.get("event_menus_error"):
        merged["event_menus_error"] = partial["event_menus_error"]
    return merged


# ==================================================================
# The recorder (main.py's record_pull closure, build 55) + the
# pull entry point the shell calls.
# ==================================================================

def _note_record_result(res, stamp):
    if res.get("status") == "recorded":
        _RECORDER_HEALTH["recorded"] += 1
        _RECORDER_HEALTH["last_stamp"] = stamp
        _RECORDER_HEALTH["last_error"] = None


def _record(rec, verdicts, partial=None):
    """Record one landed pull in the history store. A full pull
    records the whole slate; a scoped pull records ONLY the slice
    it actually pulled (its own markets under its own stamp),
    with verdicts sliced from the merged pass by market identity.
    A failure stamps the recorder health (the Lab's line) and
    NEVER breaks the pull. [main.py record_pull closure]"""
    hs = _load_history()
    try:
        if partial is not None:
            stamp = partial.get("pulled_at")
            markets = partial.get("markets") or []
            if hs.has_pull(_store_dir, stamp) == len(markets):
                return  # this slice is already on file
            by_id = {id(m): i for i, m in enumerate(
                rec.get("markets") or [])}
            sliced = [verdicts[by_id[id(m)]]
                      if id(m) in by_id
                      and by_id[id(m)] < len(verdicts)
                      else None for m in markets]
            res = hs.record_pull(
                _store_dir,
                {"pulled_at": stamp, "markets": markets,
                 "sports": {}},
                sliced)
        else:
            stamp = rec.get("pulled_at")
            if hs.has_pull(_store_dir, stamp) \
                    == len(rec.get("markets") or []):
                return  # already recorded when it landed
            if verdicts is None:
                return
            res = hs.record_pull(_store_dir, rec, verdicts)
        _note_record_result(res, stamp)
    except Exception as e:
        _RECORDER_HEALTH["last_error"] = (
            f"{type(e).__name__}: {e}")


def _save_snapshot():
    """Every save moment persists the standing slate (the Flet
    shell's save_snapshot) — the boot restore source. The file
    copy carries the native_advanced divergence flag."""
    rec = _standing.get("slate")
    if rec:
        _save_flagged("last-pull.json", rec)


def build_and_run(sports_json):
    """The pull entry point. sports_json: a JSON array of sport
    keys ([] or null = the full pull over every sport in
    b5.FANDUEL_EVENT_TYPES; ["nfl"] = the scoped pull, merged
    into the standing slate).

    Returns the board payload for the STANDING slate: the pull
    receipt + one card entry per market (market + verdict +
    display blocks), the recorder's outcome riding along.

    DEVIATION (native shape, logged): the scoped pull's per-game
    menu harvest runs INLINE here instead of as the Flet shell's
    background follow-up thread — the merge is token-guarded
    identically and the merged result is the same; the bridge
    call already runs on the shell's background dispatcher, so
    the wall time lands where the Flet background thread put it.
    Menus change no market and no price, and are never recorded.
    """
    b5 = _load_engine()
    try:
        sports = json.loads(sports_json) if sports_json else []
    except ValueError:
        sports = []
    if not isinstance(sports, list):
        sports = []
    recorder = {"status": "not-run"}
    if not sports:
        rec = pull_menu()
        _standing["slate"] = rec
        _standing["verdicts"] = None
        verdicts = _ensure_verdicts()
        before = _RECORDER_HEALTH["recorded"]
        _record(rec, verdicts)
        recorder = {
            "status": ("recorded" if _RECORDER_HEALTH["recorded"]
                       > before else "duplicate-or-skipped"),
            "last_error": _RECORDER_HEALTH["last_error"]}
        _save_snapshot()
        scope = "full"
    else:
        scope = "sport:" + ",".join(sports)
        for sport in sports:
            partial = pull_menu_sport(sport)
            merged = merge_sport_pull(_standing.get("slate"),
                                      partial)
            _standing["slate"] = merged
            _standing["verdicts"] = None
            verdicts = _ensure_verdicts()
            entry = (partial.get("sports") or {}).get(sport) or {}
            before = _RECORDER_HEALTH["recorded"]
            if "error" in entry:
                # the error merge re-saves an unchanged slate —
                # the store dedupes the call to a no-op
                _record(merged, verdicts)
            else:
                _record(merged, verdicts, partial=partial)
            recorder = {
                "status": ("recorded"
                           if _RECORDER_HEALTH["recorded"] > before
                           else "duplicate-or-skipped"),
                "last_error": _RECORDER_HEALTH["last_error"]}
            if "error" not in entry:
                try:
                    menus = _fetch_event_menus(
                        partial.get("markets") or [],
                        partial["pulled_at"])
                    harvested = merge_menu_harvest(
                        _standing["slate"], sport, menus,
                        partial["pulled_at"])
                    if harvested is not None:
                        _standing["slate"] = harvested
                except Exception:
                    pass  # a harvest failure stamps nothing
            _save_snapshot()
    return json.dumps(_board_payload(scope=scope,
                                     recorder=recorder))


def current_board_json():
    """The board payload for the standing slate without pulling
    (boot restore / destination re-entry)."""
    return json.dumps(_board_payload(scope="standing",
                                     recorder={"status": "not-run"}))


# ==================================================================
# Card naming + display — ported from main.py: SPORT_LABELS,
# _v11_SPORT_LABELS, team_name, _stat_words, _fmt_line,
# fd_market_name, selection_words, matchup_title, bet_name,
# side_label, market_display_name, _market_dt, _row_texts,
# card_verdict, market_edge_pts, bet_now, fanduel_bet_url,
# fanduel_link_state, game_quotes, stamp_of.
# ==================================================================

SPORT_LABELS = {"nfl": "American football",
                "ncaaf": "College football", "nba": "Basketball",
                "nhl": "Hockey", "mlb": "Baseball",
                "soccer": "Soccer", "tennis": "Tennis",
                "mma": "MMA", "golf": "Golf", "boxing": "Boxing",
                "cricket": "Cricket", "darts": "Darts",
                "motorsport": "Motorsport",
                "rugby-union": "Rugby union",
                "rugby-league": "Rugby league",
                "lacrosse": "Lacrosse", "snooker": "Snooker",
                "table-tennis": "Table tennis"}

_v11_SPORT_LABELS = {"nfl": "American football",
                     "ncaaf": "College football",
                     "nba": "Basketball", "nhl": "Hockey",
                     "mlb": "Baseball", "soccer": "Soccer"}

VERDICT_LADDER = ["GOLDEN BET", "BET HERE", "RISK BET (BET)",
                  "RISK BET (DO NOT BET)", "DO NOT BET"]
_AFFIRMATIVE_RUNGS = ("GOLDEN BET", "BET HERE", "RISK BET (BET)")


def _nfl_full_names():
    b5 = _load_engine()
    return {code: name for name, code
            in b5.FD_NFL_TEAM_CODES.items()}


_STAT_WORDS = {"td": "TDs", "yds": "yards", "att": "attempts",
               "rec": "receptions", "fg": "field goals"}


def team_name(mkt, side):
    raw = mkt.get(side) or "?"
    if mkt.get("sport") == "nfl":
        return _nfl_full_names().get(raw, raw)
    return raw


def _stat_words(stat):
    if not stat:
        return ""
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", str(stat)).split()
    return " ".join(_STAT_WORDS.get(w.lower(), w.lower())
                    for w in words)


def _fmt_line(line):
    s = f"{float(line):+g}"
    return s.replace("-", "−")


def fd_market_name(mkt):
    market = mkt.get("market") or ""
    if mkt.get("player") and mkt.get("stat"):
        return f"{_stat_words(mkt['stat']).title()} — player prop"
    if mkt.get("sport") == "soccer":
        return {"moneyline": "Moneyline (3-way)",
                "spread": "Handicap (spread)",
                "alt-spread": "Handicap (spread)",
                "totals": "Total goals (over/under)",
                "alt-total": "Total goals (over/under)",
                "btts": "Both Teams To Score"}.get(market, market)
    return {"moneyline": "Moneyline",
            "spread": "Point Spread",
            "alt-spread": "Alternate Point Spread",
            "totals": "Total Points",
            "alt-total": "Alternate Total Points",
            "btts": "Both Teams To Score",
            "player-props": "Player Props",
            "team-props": "Team Props",
            "game-props": "Game Props",
            "parlay": "Parlay"}.get(market, market)


def side_label(mkt):
    side = mkt.get("side") or ""
    if mkt.get("sport") == "soccer" and side == "draw":
        return "Draw"
    return side


def selection_words(mkt):
    side = mkt.get("side") or ""
    line = mkt.get("line")
    if mkt.get("player"):
        stat = _stat_words(mkt.get("stat"))
        direction = {"over": "Over", "under": "Under"}.get(
            side, side.capitalize())
        base = f"{direction} {line:g} {stat}".strip()
        return base if line is not None else \
            f"{direction} {stat}".strip()
    if mkt.get("market") in ("totals", "alt-total"):
        direction = {"over": "Over", "under": "Under"}.get(
            side, side.capitalize())
        unit = "total goals" if mkt.get("sport") == "soccer" \
            else "total points"
        return f"{direction} {line:g} {unit}" if line is not None \
            else f"{direction} {unit}"
    if mkt.get("market") in ("spread", "alt-spread"):
        team = team_name(mkt, side if side in ("home", "away")
                         else "home")
        return f"{team} {_fmt_line(line)}" if line is not None \
            else team
    if mkt.get("market") == "btts":
        return "Both teams to score — " + \
            ("Yes" if side == "yes" else "No" if side == "no"
             else side_label(mkt))
    if side == "draw":
        return "Draw"
    if side in ("home", "away"):
        return team_name(mkt, side)
    return side_label(mkt)


def matchup_title(mkt, verdict):
    if mkt.get("sport") == "soccer":
        return f"{mkt.get('home', '?')} vs {mkt.get('away', '?')}"
    return (verdict or {}).get("desc") or \
        f"{mkt.get('away', '?')} @ {mkt.get('home', '?')}"


def bet_name(mkt, verdict=None):
    """The bet's one name, in every surface's shape. [main.py]"""
    verdict = verdict or {}
    market = fd_market_name(mkt)
    selection = selection_words(mkt)
    matchup = matchup_title(mkt, verdict)
    headline = mkt["player"] if mkt.get("player") else market
    league = SPORT_LABELS.get(mkt.get("sport"),
                              (mkt.get("sport") or "?").upper())
    if mkt.get("player"):
        tab = f"Player Props → {mkt['player']} " \
              f"{_stat_words(mkt.get('stat'))}"
    else:
        tab = market
    parts = [selection]
    if mkt.get("price") is not None:
        parts.append(f"({int(mkt['price']):+d})")
    parts.append(f"· {market} · {matchup}")
    return {"headline": headline, "market": market,
            "selection": selection, "matchup": matchup,
            "slip_label": " ".join(parts),
            "fd_path": f"FanDuel → {league} → {matchup} → {tab}"}


def market_display_name(mkt):
    market = mkt.get("market") or ""
    if mkt.get("sport") == "soccer":
        return {"moneyline": "Match result (1X2)",
                "spread": "Handicap (spread)",
                "alt-spread": "Handicap (spread)",
                "totals": "Total goals (over/under)",
                "alt-total": "Total goals (over/under)"}.get(
                    market, market)
    return {"moneyline": "Moneyline", "spread": "Spread",
            "alt-spread": "Alt spread", "totals": "Totals",
            "alt-total": "Alt total", "btts": "BTTS",
            "parlay": "Parlay"}.get(market, market)


def card_verdict(verdict):
    """(term, reason) exactly as the engine issued them.
    [main.py]"""
    verdict = verdict or {}
    term = verdict.get("verdict") or verdict.get("decision") \
        or verdict.get("state") or ""
    reason = verdict.get("verdict_reason")
    if not reason and verdict.get("blocked_by"):
        reason = "blocked by: " + "; ".join(verdict["blocked_by"])
    return term, reason


def verdict_rank(term):
    if term in VERDICT_LADDER:
        return VERDICT_LADDER.index(term)
    if term == "Bet":
        return VERDICT_LADDER.index("BET HERE")
    if term == "No Bet":
        return VERDICT_LADDER.index("DO NOT BET")
    return len(VERDICT_LADDER)


def market_edge_pts(mkt, verdict):
    """The reparametrized (phi) edge in points. [main.py]"""
    b5 = _load_engine()
    p = (verdict or {}).get("p")
    price = (mkt or {}).get("price")
    if p is None or price is None:
        return None
    return (p - b5.implied_prob(price)) * 100


def bet_now(verdict):
    """The BET NOW condition: the verdict ladder's own
    pessimistic-end test — the engine's stamps win when present.
    [main.py bet_now]"""
    verdict = verdict or {}
    bn = verdict.get("bet_now")
    if bn is not None:
        return bool(bn)
    pe = verdict.get("pess_edge_pts")
    if pe is not None:
        return pe > 0
    term, _reason = card_verdict(verdict)
    return term in _AFFIRMATIVE_RUNGS


def fanduel_bet_url(mkt):
    """The FanDuel QuickSlip deep link for this exact bet, or
    None — no URL is ever guessed. [main.py]"""
    mkt = mkt or {}
    market_id = mkt.get("fd_market_id")
    selection_id = mkt.get("fd_selection_id")
    if market_id and selection_id:
        return ("https://sportsbook.fanduel.com/addToBetslip"
                f"?marketId={market_id}"
                f"&selectionId={selection_id}")
    return None


def fanduel_link_state(mkt):
    return "armed" if fanduel_bet_url(mkt) \
        else "predates-link-ids"


def _market_dt(mkt):
    raw = (mkt or {}).get("market_time")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _row_texts(mkt, verdict, edge_pts=None):
    """The collapsed card's strings: the headline is the
    SELECTION with the market title after the em dash; the event
    line is matchup · start · league; the odds column is decimal
    first for soccer, American otherwise. [main.py _row_texts]"""
    b5 = _load_engine()
    name = bet_name(mkt, verdict)
    bits = [name["matchup"]]
    dt = _market_dt(mkt)
    if dt is not None:
        bits.append(dt.strftime("%a %b %d · %I:%M %p")
                    .replace(" 0", " "))
    bits.append(_v11_SPORT_LABELS.get(
        mkt.get("sport"), (mkt.get("sport") or "?").upper()))
    p = (verdict or {}).get("p")
    if mkt.get("price") is None:
        odds = "—"
    elif mkt.get("sport") == "soccer":
        odds = f"{b5.american_to_decimal(int(mkt['price'])):.2f}"
    else:
        odds = f"{int(mkt['price']):+d}"
    return {"name": name,
            "headline": f"{name['selection']} — "
                        f"{name['market']}",
            "event": " · ".join(bits),
            "model": f"{p * 100:.0f}%" if p is not None else "—",
            "odds": odds,
            "edge": (f"{edge_pts:+.1f}"
                     if edge_pts is not None else "—"),
            "grade": (verdict or {}).get("grade") or "—"}


def game_quotes(markets):
    """Per-game quote dicts in the engine coherence_check's own
    shape. [main.py]"""
    b5 = _load_engine()
    games = {}
    for m in markets:
        key = (m.get("sport"), m.get("away"), m.get("home"))
        g = games.setdefault(key, {"spread_home": None,
                                   "total": None, "_ml": {}})
        if m.get("market") == "spread" and m.get("side") == "home":
            g["spread_home"] = m.get("line")
        elif m.get("market") == "totals":
            g["total"] = m.get("line")
        elif m.get("market") == "moneyline" \
                and m.get("price") is not None:
            g["_ml"][m.get("side")] = b5.implied_prob(m["price"])
    quotes = {}
    for key, g in games.items():
        ml = g.pop("_ml")
        ml_p_home = None
        if "home" in ml and "away" in ml \
                and (ml["home"] + ml["away"]) > 0:
            ml_p_home = ml["home"] / (ml["home"] + ml["away"])
        quotes[key] = {"source": MENU_SOURCE,
                       "spread_home": g["spread_home"],
                       "total": g["total"],
                       "ml_p_home": ml_p_home}
    return quotes


def stamp_of(rec):
    """The engine's menu stamp (menu_stamp) for a pull record.
    [main.py]"""
    b5 = _load_engine()
    if not rec:
        return "UNVERIFIED (no successful live pull)", True
    ctx = {"pulled_at": rec.get("pulled_at"),
           "source": rec.get("source"),
           "verified": rec.get("verified", False)}
    return b5.menu_stamp(ctx)


def _card_key(mkt):
    mid = mkt.get("fd_market_id")
    if mid:
        return (mkt.get("sport"), mid)
    return (mkt.get("sport"), mkt.get("away"), mkt.get("home"),
            mkt.get("market"), mkt.get("side"),
            mkt.get("player"), mkt.get("line"))


_RENDER_STAMPS = {}


def _render_stamp(key):
    stamp = _RENDER_STAMPS.get(key)
    if stamp is None:
        stamp = datetime.now().astimezone().isoformat(
            timespec="seconds")
        _RENDER_STAMPS[key] = stamp
    return stamp


def _card_entry(idx, mkt, verdict):
    """One board card: the raw market + verdict (the engine's
    own words) plus every display block the native card renders,
    computed once here so the UI adds no math of its own."""
    hs = _load_history()
    edge = market_edge_pts(mkt, verdict)
    term, reason = card_verdict(verdict)
    return {
        "idx": idx,
        "key": hs.market_key(mkt),
        "market": mkt,
        "verdict": verdict,
        "edge_pts": edge,
        "term": term,
        "verdict_reason": reason,
        "metal": (verdict or {}).get("metal"),
        "grade": (verdict or {}).get("grade"),
        "state": (verdict or {}).get("state"),
        "name": bet_name(mkt, verdict),
        "row": _row_texts(mkt, verdict, edge),
        "bet_now": bet_now(verdict),
        "link_state": fanduel_link_state(mkt),
        "bet_url": fanduel_bet_url(mkt),
    }


def _board_payload(scope="standing", recorder=None):
    rec = _standing.get("slate")
    if not rec:
        return {"scope": scope, "pulled_at": None, "source": None,
                "verified": False, "sports": {}, "receipt": None,
                "recorder": recorder or {"status": "not-run"},
                "cards": []}
    verdicts = _ensure_verdicts() or []
    markets = rec.get("markets") or []
    cards = [_card_entry(i, m, v)
             for i, (m, v) in enumerate(zip(markets, verdicts))]
    receipt = {
        "markets": len(markets),
        "priced": sum(1 for v in verdicts
                      if v.get("state") == "PRICED"),
        "unpriced": sum(1 for v in verdicts
                        if v.get("state") != "PRICED"),
        "bet_now": sum(1 for c in cards if c["bet_now"]),
        "golden": sum(1 for c in cards
                      if c["term"] == "GOLDEN BET"),
        "flagged": sum(1 for v in verdicts
                       if v.get("state") == "COHERENCE-FLAGGED"),
    }
    stamp_text, degraded = stamp_of(rec)
    return {"scope": scope,
            "pulled_at": rec.get("pulled_at"),
            "source": rec.get("source"),
            "verified": rec.get("verified"),
            "stamp": stamp_text, "stamp_degraded": degraded,
            "sports": rec.get("sports") or {},
            "tree": rec.get("tree"),
            "receipt": receipt,
            "recorder": recorder or {"status": "not-run"},
            "cards": cards}


# ==================================================================
# Card depth — ported from main.py: _card_facts,
# _mathematics_lines (+ _fair_american/_fair_text), _depth_
# sections. The five sections, in the Flet order, gloss first.
# ==================================================================

def _fair_american(p):
    if p is None or p <= 0.0 or p >= 1.0:
        return None
    if p >= 0.5:
        return -100.0 * p / (1.0 - p)
    return 100.0 * (1.0 - p) / p


def _fair_text(p):
    f = _fair_american(p)
    return f"{f:+.0f}" if f is not None else "—"


def _card_facts(mkt, verdict):
    """The card's shared inputs, straight from the engine.
    [main.py _card_facts, direct-engine branch]"""
    b5 = _load_engine()
    verdict = verdict or {}
    lane = b5._lane_for(mkt)
    w, l, rec_src = b5.lane_record(lane)
    phi, phi_state, _detail = b5.lane_phi(lane)
    uncal = b5.lane_uncalibrated(lane)
    cal_tag = verdict.get("cal_tag") or \
        b5.calibration_tag(lane, b5.load_scorecard())
    if verdict.get("cal_tag"):
        cal_tag = verdict["cal_tag"]
    term, vreason = card_verdict(verdict)
    return {"lane": lane, "w": w, "l": l, "rec_src": rec_src,
            "phi": phi, "phi_state": phi_state, "uncal": uncal,
            "cal_tag": cal_tag, "p": verdict.get("p"),
            "grade": verdict.get("grade"), "term": term,
            "vreason": vreason,
            "state": verdict.get("state") or "",
            "stance": verdict.get("stance")}


def _mathematics_lines(mkt, verdict, f, edge_pts, bankroll):
    """THE MATHEMATICS: one card's proof chain. [main.py]"""
    b5 = _load_engine()
    p, price = f["p"], mkt.get("price")
    if p is None:
        return ["no mathematics to show — this market carries "
                "no probability the system can defend "
                f"({f['state'] or 'UNPRICED'}), so there is no "
                "projection to prove and no position to size."]
    if price is None:
        return ["no mathematics to show — the engine priced a "
                "probability for this market, but no FanDuel "
                "price rides with it, so there is no price to "
                "prove the projection against and no position "
                "to size."]
    price = int(price)
    q = b5.implied_prob(price)
    dec = b5.american_to_decimal(price)
    edge = edge_pts if edge_pts is not None else (p - q) * 100
    lines = [
        f"win probability (engine final): {p * 100:.1f}%",
        "the engine's final probability — calibration-mapped "
        "(phi) and blended toward the market's own number; "
        "not the raw model probability",
        f"FanDuel odds: {price:+d} — implied probability "
        f"{q * 100:.1f}% (decimal {dec:.2f})",
        f"true odds at the engine's number: {_fair_text(p)} "
        f"— the fair price, where this bet breaks even"]
    pe = verdict.get("pess_edge_pts")
    if pe is not None:
        p_pess = q + pe / 100.0
        lines += [
            f"pessimistic probability (verdict ladder's "
            f"basis): {p_pess * 100:.1f}% — the band's low "
            f"end the ladder grades survival on",
            f"pessimistic edge: {pe:+.1f} pts · true odds "
            f"at the pessimistic end: {_fair_text(p_pess)} · "
            f"EV at the pessimistic end: "
            f"{p_pess * dec - 1.0:+.3f} per unit"]
    else:
        lines.append(
            "pessimistic end (verdict ladder's basis): the "
            "ladder's low-end number is not carried on this "
            "verdict — the ladder applied it itself, and its "
            "outcome is the rung in the proof below")
    lines.append(
        f"proof: engine {p * 100:.1f}% vs implied "
        f"{q * 100:.1f}% → edge {edge:+.1f} pts → EV "
        f"{p * dec - 1.0:+.3f} per unit → verdict {f['term']}"
        + (f" · grade {f['grade']}" if f["grade"] else ""))
    adv = b5.kelly_advice(p, price, bankroll=bankroll,
                          cal_tag=f["cal_tag"])
    lines.append("position — Kelly advisory (the engine's "
                 "kelly_advice: quarter-Kelly range under a "
                 "5% hard cap; advice only — the app never "
                 "places a bet)")
    if adv["state"] == "UNPRICED":
        lines.append(adv["reasons"][0])
    else:
        stake = (f"advised stake: "
                 f"{adv['stake_frac'] * 100:.2f}%–"
                 f"{adv['stake_frac_hi'] * 100:.2f}% of "
                 f"bankroll ({adv['stake_units']:.1f}u–"
                 f"{adv['stake_units_hi']:.1f}u)")
        if adv["stake_dollars"] is not None:
            stake += (f" = ${adv['stake_dollars']:,.0f}–"
                      f"${adv['stake_dollars_hi']:,.0f} on a "
                      f"${bankroll:,.0f} bankroll")
        else:
            stake += (" — no bankroll set in the app, so "
                      "the stake prints as a fraction of "
                      "bankroll only")
        lines.append(stake)
        lines.extend(adv["reasons"])
    return lines


def _depth_sections(mkt, verdict, rec, quotes_by_game,
                    edge_pts=None, bankroll=None):
    """The card's depth, as data: [(title, [gloss, *lines])].
    [main.py _depth_sections]"""
    b5 = _load_engine()
    f = _card_facts(mkt, verdict)
    w, l = f["w"], f["l"]
    rec_src, phi, phi_state = f["rec_src"], f["phi"], \
        f["phi_state"]
    uncal, cal_tag = f["uncal"], f["cal_tag"]
    p, state, stance = f["p"], f["state"], f["stance"]
    term, vreason = f["term"], f["vreason"]

    key = (mkt.get("sport"), mkt.get("away"), mkt.get("home"))
    quote = quotes_by_game.get(key)
    if quote and any(quote.get(k) is not None for k in
                     ("spread_home", "total", "ml_p_home")):
        flags = b5.coherence_check([quote])
        coh_lines = flags or ["coherent at quoted prices"]
    else:
        coh_lines = ["insufficient quotes in this pull to audit"]

    anatomy = []
    if vreason:
        anatomy.append(f"{term} — {vreason}")
    elif term:
        anatomy.append(f"verdict: {term}")
    if verdict.get("metal"):
        anatomy.append(f"metal tier: {verdict['metal']}")
    anatomy.append(f"state: {state}")
    if stance:
        anatomy.append(f"stance: {stance} — the shape of the "
                       f"bet (Terms); the verdict above decides")
    anatomy.append(f"calibration tag: {cal_tag or '—'}")
    if p is not None:
        anatomy.append(f"model probability (after calibration "
                       f"— see Terms: phi): {p * 100:.1f}%")
    if mkt.get("price") is not None:
        anatomy.append(
            f"pulled price: {int(mkt['price']):+d} "
            f"(implied "
            f"{b5.implied_prob(mkt['price']) * 100:.1f}%)"
            f" · decimal odds "
            f"{b5.american_to_decimal(int(mkt['price'])):.2f}")
    if edge_pts is not None:
        anatomy.append(f"edge: {edge_pts:+.1f} pts (model P - "
                       f"implied P at the pulled price)")
    if mkt.get("line") is not None:
        anatomy.append(f"line: {mkt['line']} · side: "
                       f"{side_label(mkt)}")
    if verdict.get("detail"):
        anatomy.append(f"checker detail: {verdict['detail']}")
    if verdict.get("note"):
        anatomy.append(f"checker note: {verdict['note']}")

    phi_params = ({k: v for k, v in phi.items() if k != "kind"}
                  if isinstance(phi, dict) else {})
    scale = [
        f"phi: "
        f"{phi.get('kind', '?') if isinstance(phi, dict) else '?'}"
        f" [{phi_state}]"
        + (f" params {phi_params}" if phi_params else ""),
        f"lane record: {w}-{l} ({rec_src})",
        f"calibration tag: {cal_tag or '—'}"
        + (f" — {uncal}" if uncal else "")]

    stamp_text, _degraded = stamp_of(rec)
    provenance = [f"menu: {stamp_text}",
                  f"source: {rec.get('source')}",
                  f"pulled at: {rec.get('pulled_at')}"]
    if mkt.get("market_time"):
        provenance.append(f"kickoff: {mkt['market_time']} (local)")
    if mkt.get("fd_event_id"):
        provenance.append(f"FanDuel event id: "
                          f"{mkt['fd_event_id']}")
    if mkt.get("fd_market_id"):
        provenance.append(f"FanDuel market id: "
                          f"{mkt['fd_market_id']}")
    if mkt.get("fd_selection_id"):
        provenance.append(f"FanDuel selection id: "
                          f"{mkt['fd_selection_id']}")
    provenance.append(f"card rendered: "
                      f"{_render_stamp(_card_key(mkt))}")

    return [
        ("PRICE ANATOMY", ["where the probability came from"]
         + anatomy),
        ("THE MATHEMATICS",
         ["the projection proved with its own numbers — "
          "probability against price, the ladder's "
          "pessimistic end, the position"]
         + _mathematics_lines(mkt, verdict, f, edge_pts,
                              bankroll)),
        ("SCALE",
         ["phi — the fitted map that adjusts this lane's raw "
          "probabilities toward what its record has earned"]
         + scale),
        ("COHERENCE",
         ["do this game's prices agree with each other?"
          if mkt.get("sport") != "soccer" else
          "do this match's prices agree with each other?"]
         + coh_lines),
        ("PROVENANCE",
         ["where every number came from, and when"]
         + provenance)]


def depth_json(idx, bankroll=None):
    """The five depth sections for the standing slate's market
    at index idx, as [{title, gloss, lines}]. The index is the
    card's own idx from the board payload it rides on."""
    rec = _standing.get("slate")
    verdicts = _ensure_verdicts()
    if not rec or not verdicts or idx is None \
            or not (0 <= int(idx) < len(rec.get("markets")
                                        or [])):
        return json.dumps({"error": "no_such_card",
                           "idx": idx})
    idx = int(idx)
    mkt = rec["markets"][idx]
    verdict = verdicts[idx]
    quotes = game_quotes(rec.get("markets") or [])
    sections = _depth_sections(
        mkt, verdict, rec, quotes,
        edge_pts=market_edge_pts(mkt, verdict),
        bankroll=bankroll)
    return json.dumps({
        "idx": idx,
        "sections": [{"title": t, "gloss": lines[0],
                      "lines": lines[1:]}
                     for t, lines in sections]})


# ==================================================================
# Finds — ported from main.py distill_finds.
# ==================================================================

def distill_finds(markets, verdicts):
    """(golden, finds, flagged, checked_no_edge) from a priced
    slate. [main.py distill_finds]"""
    golden, finds, flagged, counter = [], [], [], []
    for mkt, verdict in zip(markets, verdicts):
        edge = market_edge_pts(mkt, verdict)
        term, _reason = card_verdict(verdict)
        if term == "GOLDEN BET":
            golden.append((mkt, verdict, edge))
        if verdict.get("state") == "COHERENCE-FLAGGED":
            flagged.append((mkt, verdict, edge))
        elif verdict.get("state") == "PRICED":
            finds.append((mkt, verdict, edge))
        else:
            counter.append((mkt, verdict, edge))
    finds.sort(key=lambda t: (verdict_rank(card_verdict(t[1])[0]),
                              -(t[2] if t[2] is not None
                                else -1e9)))
    return golden, finds, flagged, counter


def finds_json():
    """The Finds destination payload: the GOLDEN panel (empty
    when nothing qualifies — the gate is the engine's verdict,
    not copy), the ranked finds (page-capped at 40 like the
    Flet feed, the overflow counted), the price-conflict list,
    and the checked-no-edge counter lines."""
    rec = _standing.get("slate")
    if not rec:
        return json.dumps({"has_slate": False, "golden": [],
                           "finds": [], "flagged": [],
                           "counter": [], "overflow": 0})
    verdicts = _ensure_verdicts() or []
    markets = rec.get("markets") or []
    index_of = {id(m): i for i, m in enumerate(markets)}
    golden, finds, flagged, counter = distill_finds(markets,
                                                    verdicts)

    def entry(t, rank=None):
        m, v, _e = t
        c = _card_entry(index_of[id(m)], m, v)
        if rank is not None:
            c["rank"] = rank
        return c

    counter_lines = []
    for m, v, e in counter:
        nm = bet_name(m, v)
        counter_lines.append(
            f"{nm['selection']} · {nm['market']} — "
            f"{v.get('state')}"
            + (f" · edge {e:+.1f} pts" if e is not None else ""))
    return json.dumps({
        "has_slate": True,
        "golden": [entry(t) for t in golden],
        "finds": [entry(t, rank=i + 1)
                  for i, t in enumerate(finds[:40])],
        "overflow": max(0, len(finds) - 40),
        "flagged": [entry(t) for t in flagged],
        "counter": counter_lines})


# ==================================================================
# The Protected Slip — ported from main.py: protected_candidates,
# render_protected's arithmetic, slip_correlation, the marked-
# slips store. The app NEVER places anything; a slip is written
# ONLY when the user confirms the mark.
# ==================================================================

def _protected_candidates():
    rec = _standing.get("slate")
    if not rec:
        return []
    verdicts = _ensure_verdicts() or []
    out = []
    for m, v in zip(rec.get("markets", []), verdicts):
        term, _r = card_verdict(v)
        if v.get("state") == "PRICED" \
                and term in ("GOLDEN BET", "BET HERE") \
                and v.get("p") is not None \
                and m.get("price") is not None:
            out.append((m, v))
    out.sort(key=lambda t: (
        verdict_rank(card_verdict(t[1])[0]),
        -(market_edge_pts(t[0], t[1]) or 0)))
    return out


def slip_correlation(legs):
    """Group a Protected Slip's legs by what they share.
    [main.py slip_correlation]"""
    legs = list(legs or [])

    def label(m):
        return bet_name(m)["selection"]

    clusters, used = [], set()
    by_game = {}
    for m in legs:
        by_game.setdefault((m.get("sport"), m.get("home"),
                            m.get("away")), []).append(m)
    for _g, ms in by_game.items():
        if len(ms) >= 2:
            clusters.append({
                "kind": "same game",
                "title": f"Same game — {ms[0].get('away')} at "
                         f"{ms[0].get('home')}",
                "legs": [label(m) for m in ms]})
            used.update(id(m) for m in ms)
    rest = [m for m in legs if id(m) not in used]
    by_team = {}
    for m in rest:
        for t in {m.get("home"), m.get("away")}:
            if t:
                by_team.setdefault((m.get("sport"), t),
                                   []).append(m)
    used2 = set()
    for (_s, t), ms in by_team.items():
        ms = [m for m in ms if id(m) not in used2]
        if len(ms) >= 2:
            clusters.append({"kind": "shared team",
                             "title": f"Shared team — {t}",
                             "legs": [label(m) for m in ms]})
            used2.update(id(m) for m in ms)
    singles = []
    by_sport = {}
    for m in rest:
        if id(m) not in used2:
            by_sport.setdefault(m.get("sport"), []).append(m)
    for s, ms in by_sport.items():
        if len(ms) >= 2:
            clusters.append({
                "kind": "same league",
                "title": f"Same league — "
                         f"{SPORT_LABELS.get(s, (s or '?').upper())}",
                "legs": [label(m) for m in ms]})
        else:
            singles += [label(m) for m in ms]
    return {"clusters": clusters, "singles": singles,
            "n_legs": len(legs),
            "n_clustered": sum(len(c["legs"])
                               for c in clusters)}


SLIP_CLUSTER_NOTES = {
    "same game": ("Legs that share a game are one bet in "
                  "costumes — a single game can sink every leg "
                  "in this group at once."),
    "shared team": ("The same team carries more than one leg "
                    "— its day decides all of them together."),
    "same league": ("Same league — one slate, one set of "
                    "conditions; results can move together.")}


def _build_slip(bankroll=None):
    """The Protected Slip as data. [main.py render_protected's
    arithmetic, factored to data]"""
    b5 = _load_engine()
    cands = _protected_candidates()
    out = {"candidates": len(cands), "legs": [],
           "any_golden": False, "warnings": [],
           "total_units": 0.0, "total_dollars": None,
           "combined_decimal": None, "combined_american": None,
           "combined_model_p": None, "correlation": None,
           "pull": (_standing.get("slate") or {}).get("pulled_at")}
    if not cands:
        return out
    total_units = 0.0
    total_dollars = 0.0 if bankroll else None
    warnings = []
    legs = []
    seen_games = {}
    any_golden = False
    for m, v in cands:
        term, _r = card_verdict(v)
        any_golden = any_golden or term == "GOLDEN BET"
        adv = b5.kelly_advice(
            v["p"], m["price"], bankroll=bankroll,
            cal_tag=v.get("cal_tag"), priced=True)
        nm = bet_name(m, v)
        stake_txt = f"{adv['stake_units']:.1f}u"
        if adv["stake_dollars"] is not None:
            stake_txt += f" (${adv['stake_dollars']:,.0f})"
            total_dollars += adv["stake_dollars"]
        total_units += adv["stake_units"]
        legs.append({"name": nm["slip_label"], "term": term,
                     "selection": nm["selection"],
                     "market": nm["market"],
                     "matchup": nm["matchup"],
                     "price": int(m["price"]),
                     "stake_units": adv["stake_units"],
                     "stake_dollars": adv["stake_dollars"],
                     "stake_text": stake_txt})
        for reason in adv["reasons"]:
            if "UNCALIBRATED" in reason or "hard cap" in reason:
                warnings.append(f"{nm['selection']}: {reason}")
        if v.get("note"):
            warnings.append(f"{nm['selection']}: {v['note']}")
        gkey = (m.get("sport"), m.get("home"), m.get("away"))
        if gkey in seen_games:
            warnings.append(
                "Multiple legs from the same game "
                f"({nm['matchup']}) — they are not "
                "independent; one game can sink several "
                "legs at once.")
        seen_games[gkey] = True
    dec = 1.0
    mp = 1.0
    for (_m, _v), _leg in zip(cands, legs):
        pr = int(_leg["price"])
        dec *= 1.0 + (pr / 100.0 if pr > 0 else 100.0 / abs(pr))
        mp *= float(_v.get("p") or 0.0)
    amer = (int(round((dec - 1) * 100)) if dec >= 2
            else int(round(-100.0 / (dec - 1))))
    corr = slip_correlation([m for m, _v in cands])
    for c in corr["clusters"]:
        c["note"] = SLIP_CLUSTER_NOTES.get(c["kind"], "")
    out.update({
        "legs": legs, "any_golden": any_golden,
        "warnings": list(dict.fromkeys(warnings)),
        "total_units": total_units,
        "total_dollars": total_dollars,
        "combined_decimal": dec, "combined_american": amer,
        "combined_model_p": mp, "correlation": corr})
    return out


def protected_slip_json(bankroll=None):
    return json.dumps(_build_slip(bankroll))


def _load_marked_slips():
    slips = _load_json_file("marked-slips.json", default=[])
    return slips if isinstance(slips, list) else []


def mark_placed_json(bankroll=None):
    """Write the user's OWN placement mark — called only after
    the shell's confirm step, mirroring _protected_mark. Returns
    the slip written, or an error object when the slip is empty
    (nothing is ever written for an empty slip)."""
    slip_data = _build_slip(bankroll)
    if not slip_data["legs"]:
        return json.dumps({"error": "empty_slip"})
    slip = {"marked_at": datetime.now().astimezone()
            .isoformat(timespec="seconds"),
            "status": "PLACED (user-marked)",
            "legs": [{"name": leg["name"], "term": leg["term"],
                      "price": leg["price"],
                      "stake_units": leg["stake_units"],
                      "stake_dollars": leg["stake_dollars"]}
                     for leg in slip_data["legs"]],
            "total_units": slip_data["total_units"],
            "total_dollars": slip_data["total_dollars"],
            "pull": slip_data["pull"]}
    slips = _load_marked_slips()
    slips.append(slip)
    _save_json_file("marked-slips.json", slips)
    return json.dumps({"marked": slip, "count": len(slips)})


def marked_slips_json():
    return json.dumps(_load_marked_slips())


# ==================================================================
# Lab + the history API payloads (the DATA-CONTRACT shapes from
# main.py's _slate_payload / history_payload, verbatim).
# ==================================================================

def history_health_line():
    """The Lab's data-health line for the pull-history recorder.
    [main.py history_health_line]"""
    hs = _load_history()
    try:
        begins = hs.history_begins(_store_dir)
    except Exception:
        begins = None
    err = _RECORDER_HEALTH.get("last_error")
    if err:
        return (f"Pull-history recorder: FAILED on the last "
                f"attempt — {err}. Pulls and prices are "
                f"unaffected; the 3D history windows are "
                f"missing that pull."
                + (f" History on file begins {begins}."
                   if begins else ""))
    if begins is None:
        return ("Pull-history recorder: armed — no pulls "
                "recorded yet. On-device history begins with "
                "the first pull this build records; before "
                "the recorder, the app kept only the latest "
                "pull, so there is no earlier history to show "
                "and none is invented.")
    return (f"Pull-history recorder: recording — history "
            f"begins {begins} (on-device; nothing before the "
            f"recorder shipped exists, and none is invented) · "
            f"{_RECORDER_HEALTH['recorded']} pull(s) recorded "
            f"this session.")


def lab_json():
    b5 = _load_engine()
    hs = _load_history()
    try:
        season = hs.load_window(_store_dir, "season",
                                datetime.now(hs.DETROIT))
        n_records = len(season["records"])
        n_recorded_markets = sum(
            len(r.get("markets") or []) for r in season["records"])
    except Exception:
        n_records, n_recorded_markets = None, None
    out = {"engine": json.loads(ping()),
           "recorder": {
               "recorded_session": _RECORDER_HEALTH["recorded"],
               "last_stamp": _RECORDER_HEALTH["last_stamp"],
               "last_error": _RECORDER_HEALTH["last_error"],
               "history_begins": hs.history_begins(_store_dir),
               "health_line": history_health_line(),
               "records_on_file": n_records,
               "recorded_markets_on_file": n_recorded_markets},
           "marked_slips": len(_load_marked_slips()),
           "slate": None}
    rec = _standing.get("slate")
    if rec:
        verdicts = _ensure_verdicts() or []
        priced_v = [v for v in verdicts
                    if v.get("state") == "PRICED"]
        from collections import Counter
        tags = Counter(v.get("cal_tag") for v in priced_v)
        stances = Counter(v.get("stance") for v in priced_v)
        stamp_text, _deg = stamp_of(rec)
        out["slate"] = {
            "pulled_at": rec.get("pulled_at"),
            "stamp": stamp_text,
            "markets": len(rec.get("markets") or []),
            "priced": len(priced_v),
            "golden": sum(1 for v in verdicts
                          if card_verdict(v)[0] == "GOLDEN BET"),
            "flagged": sum(1 for v in verdicts
                           if v.get("state")
                           == "COHERENCE-FLAGGED"),
            "cal_tags": {t: tags.get(t, 0)
                         for t in b5.CALIBRATION_TAGS},
            "stances": {s.capitalize(): stances.get(s, 0)
                        for s in b5.STANCES}}
    return json.dumps(out)


def slate_json():
    """The current pull for /api/slate.json: per-event summaries
    with the team-name labels the pull record deliberately does
    not carry. [main.py _slate_payload, verbatim]"""
    hs = _load_history()
    rec = _standing.get("slate")
    if not rec:
        return json.dumps({"pulled_at": None, "source": None,
                           "verified": None, "events": [],
                           "markets": 0})
    events = {}
    for m in rec.get("markets") or []:
        eid = m.get("fd_event_id")
        if eid is None:
            continue
        slot = events.get(str(eid))
        if slot is None:
            label = " vs ".join(
                x for x in (m.get("home"), m.get("away")) if x) \
                or m.get("competition") or ""
            slot = events[str(eid)] = {
                "fd_event_id": eid, "sport": m.get("sport"),
                "label": label,
                "competition": m.get("competition"),
                "market_time": m.get("market_time"),
                "n_markets": 0, "keys": []}
        slot["n_markets"] += 1
        slot["keys"].append(hs.market_key(m))
    return json.dumps({
        "pulled_at": rec.get("pulled_at"),
        "source": rec.get("source"),
        "verified": rec.get("verified"),
        "markets": len(rec.get("markets") or []),
        "events": sorted(
            events.values(),
            key=lambda e: (-e["n_markets"],
                           str(e["fd_event_id"])))})


def history_json(window, graph, event_id=None):
    """The DATA-CONTRACT payload for one (window, graph) ask
    against the on-device store — the body the native WebView
    layer serves for /api/history.json. A bad window or graph
    returns the Flet handler's named error body ({"error": ...})
    instead of raising, so the served contract is identical.
    [main.py history_payload + handler error mapping]"""
    hs = _load_history()
    try:
        win = hs.load_window(_store_dir, window,
                             datetime.now(hs.DETROIT))
    except ValueError as e:
        return json.dumps({"error": "unknown_window",
                           "detail": str(e), "window": window,
                           "graph": graph})
    try:
        series = hs.shape_for(graph, win["records"], event_id)
    except ValueError as e:
        return json.dumps({"error": str(e), "detail": str(e),
                           "window": window, "graph": graph})
    return json.dumps({"window": win["window"],
                       "grain": win["grain"],
                       "from": win["from"],
                       "to": win["to"],
                       "history_begins": win["history_begins"],
                       "graph": graph,
                       "series": series})


# ==================================================================
# Stocks — the Nasdaq pull ported from main.py (build 53):
# fetch -> raw dicts -> pure parses, then the engine's Organ 9
# views (b5.stock_quote_view / b5.option_grid_view). Every block
# carries {source, pulled_at, delay_class}; spot is the quote's
# regular close, NEVER the chain's stale embedded lastTrade.
# WATCH-only: no stock lane has passed its exam, so no surface
# here emits a buy or sell signal — the engine's own stamps say
# so, verbatim.
# ==================================================================

STOCK_UNIVERSE = ["MSTR", "CRM", "META", "AVGO", "SMCI", "BAC"]
NASDAQ_BASE = "https://api.nasdaq.com/api/quote"
NASDAQ_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
NASDAQ_SOURCE = "Nasdaq API"
NASDAQ_MIN_INTERVAL_S = 0.5

_nasdaq_last_call = [0.0]
_nasdaq_lock = threading.Lock()


def _stock_stamp(delay_class):
    return {"source": NASDAQ_SOURCE,
            "pulled_at": datetime.now().astimezone().isoformat(
                timespec="seconds"),
            "delay_class": delay_class}


def _nasdaq_get(url):
    """One paced GET -> parsed JSON. Raises on HTTP/JSON
    failure. [main.py]"""
    with _nasdaq_lock:
        wait = NASDAQ_MIN_INTERVAL_S - (
            time.monotonic() - _nasdaq_last_call[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={
            "User-Agent": NASDAQ_UA,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
        finally:
            _nasdaq_last_call[0] = time.monotonic()
    return json.loads(body)


def _nasdaq_num(raw):
    if raw is None:
        return None
    s = str(raw).strip().replace("$", "").replace(",", "") \
        .replace("%", "")
    if s in ("", "--", "N/A", "NA", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _nasdaq_int(raw):
    v = _nasdaq_num(raw)
    return None if v is None else int(v)


def parse_nasdaq_quote(raw, sym):
    """Raw quote/info JSON -> the quote block. [main.py]"""
    data = (raw or {}).get("data") or {}
    p = data.get("primaryData") or {}
    s = data.get("secondaryData") or {}

    def block(b):
        return {
            "last": _nasdaq_num(b.get("lastSalePrice")),
            "net_change": _nasdaq_num(b.get("netChange")),
            "pct_change": _nasdaq_num(b.get("percentageChange")),
            "bid": _nasdaq_num(b.get("bidPrice")),
            "ask": _nasdaq_num(b.get("askPrice")),
            "bid_size": _nasdaq_int(b.get("bidSize")),
            "ask_size": _nasdaq_int(b.get("askSize")),
            "volume": _nasdaq_num(b.get("volume")),
            "last_trade_timestamp_raw":
                b.get("lastTradeTimestamp"),
            "is_realtime": bool(b.get("isRealTime")),
        }

    primary, secondary = block(p), block(s)
    spot = secondary["last"] if secondary["last"] is not None \
        else primary["last"]
    out = _stock_stamp("realtime-claimed")
    out.update({
        "symbol": sym,
        "company_name": data.get("companyName"),
        "exchange": data.get("exchange"),
        "market_status": data.get("marketStatus"),
        "primary": primary,
        "secondary": secondary,
        "spot_reference": spot,
        "spot_reference_basis": "secondary (regular close)"
        if secondary["last"] is not None
        else "primary (last sale)",
    })
    return out


def parse_nasdaq_history(raw, sym):
    """Raw historical JSON -> ascending daily OHLCV bars.
    [main.py]"""
    data = (raw or {}).get("data") or {}
    tt = data.get("tradesTable") or {}
    bars = []
    for r in tt.get("rows") or []:
        try:
            iso = datetime.strptime(
                r["date"], "%m/%d/%Y").date().isoformat()
        except (KeyError, ValueError):
            continue
        bars.append({
            "date": iso,
            "open": _nasdaq_num(r.get("open")),
            "high": _nasdaq_num(r.get("high")),
            "low": _nasdaq_num(r.get("low")),
            "close": _nasdaq_num(r.get("close")),
            "volume": _nasdaq_int(r.get("volume")),
        })
    bars.sort(key=lambda b: b["date"])
    out = _stock_stamp("eod")
    out.update({
        "symbol": sym,
        "total_records_reported": data.get("totalRecords"),
        "asof_raw": tt.get("asOf"),
        "n_bars": len(bars),
        "first_date": bars[0]["date"] if bars else None,
        "last_date": bars[-1]["date"] if bars else None,
        "bars": bars,
    })
    return out


def nasdaq_chain_buckets(raw):
    """Phase 1 of the chain pull: the bare response's month
    buckets spanning every listed expiry. [main.py]"""
    bdata = (raw or {}).get("data") or {}
    buckets = []
    for e in ((bdata.get("filterlist") or {}).get("fromdate")
              or {}).get("filter") or []:
        val = e.get("value") or ""
        if "|" in val:
            lo, hi = val.split("|", 1)
            buckets.append({"label": e.get("label"),
                            "from": lo, "to": hi})
    return buckets


def parse_nasdaq_chain(raw, sym):
    """Phase 2: the ranged response -> expiries with contracts.
    [main.py]"""
    fdata = (raw or {}).get("data") or {}
    rows = ((fdata.get("table") or {}).get("rows")) or []

    def side(row, prefix):
        return {
            "last": _nasdaq_num(row.get(f"{prefix}_Last")),
            "change": _nasdaq_num(row.get(f"{prefix}_Change")),
            "bid": _nasdaq_num(row.get(f"{prefix}_Bid")),
            "ask": _nasdaq_num(row.get(f"{prefix}_Ask")),
            "volume": _nasdaq_int(row.get(f"{prefix}_Volume")),
            "open_interest": _nasdaq_int(
                row.get(f"{prefix}_Openinterest")),
        }

    expiries = []
    current = None
    for r in rows:
        if r.get("strike") is None:
            label = r.get("expirygroup")
            if not label:
                continue
            iso = datetime.strptime(
                label, "%B %d, %Y").date().isoformat()
            current = {"expiry": iso, "expiry_label": label,
                       "contracts": []}
            expiries.append(current)
            continue
        if current is None:
            continue
        current["contracts"].append({
            "strike": _nasdaq_num(r.get("strike")),
            "expiry_label_short": r.get("expiryDate"),
            "occ_ref": (r.get("drillDownURL") or "")
                .rsplit("/", 1)[-1] or None,
            "call": side(r, "c"),
            "put": side(r, "p"),
        })
    for e in expiries:
        e["contracts"].sort(key=lambda c: c["strike"])
        e["n_strikes"] = len(e["contracts"])
    out = _stock_stamp("delayed")
    out.update({
        "symbol": sym,
        "last_trade_raw_STALE": fdata.get("lastTrade"),
        "n_expiries": len(expiries),
        "n_contract_rows": sum(e["n_strikes"] for e in expiries),
        "expiries": expiries,
    })
    return out


def stock_history_fromdate():
    """One year of daily bars. [main.py]"""
    return (datetime.now().astimezone().date()
            - timedelta(days=365)).isoformat()


def fetch_stock_bundle(sym, fromdate):
    """fetch -> raw dicts -> parsed bundle {quote, history,
    chain} for one name. Raises on any leg's failure; the
    caller keeps the last good bundle and stamps it STALE.
    [main.py]"""
    quote = parse_nasdaq_quote(
        _nasdaq_get(f"{NASDAQ_BASE}/{sym}/info"
                    f"?assetclass=stocks"), sym)
    history = parse_nasdaq_history(
        _nasdaq_get(f"{NASDAQ_BASE}/{sym}/historical"
                    f"?assetclass=stocks&fromdate={fromdate}"
                    f"&limit=9999"), sym)
    bare = _nasdaq_get(
        f"{NASDAQ_BASE}/{sym}/option-chain?assetclass=stocks")
    buckets = nasdaq_chain_buckets(bare)
    if not buckets:
        raise RuntimeError(f"{sym}: no expiry buckets in chain "
                           f"response")
    lo = min(b["from"] for b in buckets)
    hi = max(b["to"] for b in buckets)
    chain = parse_nasdaq_chain(
        _nasdaq_get(f"{NASDAQ_BASE}/{sym}/option-chain"
                    f"?assetclass=stocks&fromdate={lo}"
                    f"&todate={hi}"), sym)
    chain["expiry_buckets_listed"] = buckets
    chain["enumeration"] = {
        "method": "filterlist.fromdate buckets -> single "
                  "ranged call",
        "fromdate": lo, "todate": hi}
    return {"quote": quote, "history": history, "chain": chain}


def _stocks_asof(bundle):
    raw = ((bundle or {}).get("quote") or {}).get("pulled_at")
    try:
        return datetime.fromisoformat(raw).date()
    except Exception:
        return datetime.now().astimezone().date()


def _stocks_default_expiry(bundle):
    chain = (bundle or {}).get("chain") or {}
    exps = [e["expiry"] for e in chain.get("expiries") or []]
    if not exps:
        return None
    asof = _stocks_asof(bundle)
    for ex in exps:
        try:
            dte = (datetime.strptime(
                ex, "%Y-%m-%d").date() - asof).days
        except ValueError:
            continue
        if dte >= 5:
            return ex
    return exps[0]


def stocks_pull_json():
    """Pull every name in the universe (the Flet worker's
    pattern): a failed name keeps its last good bundle, stamped
    STALE — data is never invented to fill the gap, and the
    failure names itself in the note. Returns the note + the
    tape views."""
    old = _stocks_state.get("names") or {}
    names, failed, fresh = {}, [], 0
    for sym in STOCK_UNIVERSE:
        try:
            names[sym] = fetch_stock_bundle(
                sym, stock_history_fromdate())
            fresh += 1
        except Exception:
            failed.append(sym)
            if sym in old:
                kept = dict(old[sym])
                kept["stale"] = True
                names[sym] = kept
    _stocks_state["names"] = names
    _save_flagged("stocks-snapshot.json", names)
    note = (f"Nasdaq pull landed: {fresh} of "
            f"{len(STOCK_UNIVERSE)} names fresh")
    if failed:
        note += (f" · failed: {', '.join(failed)} — "
                 f"last good data kept, stamped STALE")
    _stocks_state["note"] = note + "."
    return json.dumps({"note": _stocks_state["note"],
                       "fresh": fresh, "failed": failed,
                       "tape": _stocks_views()})


def _stocks_views():
    b5 = _load_engine()
    out = []
    names = _stocks_state.get("names") or {}
    for sym in STOCK_UNIVERSE:
        bundle = names.get(sym)
        if not bundle:
            continue
        view = b5.stock_quote_view(bundle)
        out.append({"symbol": sym, "view": view})
    return out


def stocks_tape_json():
    """TAPE + MATRIX share the engine's quote view (spot,
    realized vol, lane stamps, WATCH action + reason)."""
    return json.dumps({"note": _stocks_state.get("note") or "",
                       "names": _stocks_views()})


def stocks_options_json(sym, expiry=None):
    """The options grid for one name/expiry, shaped by the
    engine's option_grid_view: computed IV + implied P(above
    strike) per strike; expiries under 5 DTE come back with
    the probabilities suppressed by the engine view itself
    (short_dated) — the shell only prints the stamp."""
    b5 = _load_engine()
    names = _stocks_state.get("names") or {}
    if sym not in names:
        return json.dumps({"error": "no_such_name", "symbol": sym})
    bundle = names[sym]
    quote = bundle.get("quote") or {}
    chain = bundle.get("chain") or {}
    spot = quote.get("spot_reference")
    asof = _stocks_asof(bundle)
    expiries = [e["expiry"] for e in chain.get("expiries") or []]
    if not expiries or spot is None:
        return json.dumps({"error": "no_chain", "symbol": sym,
                           "spot": spot})
    if expiry not in expiries:
        expiry = _stocks_default_expiry(bundle)

    def _dte(ex):
        return (datetime.strptime(ex, "%Y-%m-%d").date()
                - asof).days

    block = next(e for e in chain["expiries"]
                 if e["expiry"] == expiry)
    grid = b5.option_grid_view(block, spot,
                               asof=asof.isoformat())
    return json.dumps({
        "symbol": sym, "spot": spot,
        "spot_basis": quote.get("spot_reference_basis"),
        "expiries": [{"expiry": ex, "dte": _dte(ex)}
                     for ex in expiries],
        "expiry": expiry, "dte": _dte(expiry),
        "grid": grid,
        "model_stamp": b5.STOCK_MODEL_STAMP,
        "lane_stamps": {lane: b5.STOCK_LANES[lane]["stamp"]
                        for lane in ("S2", "S3", "S4")},
        "chain": {"source": chain.get("source"),
                  "pulled_at": chain.get("pulled_at"),
                  "delay_class": chain.get("delay_class")}})


def holdings_json():
    """Every universe row with the user's on-device position:
    value and P/L computed from the pulled spot only — never
    estimated — and the SELL line staying WATCH with its
    reason. [main.py render_stocks_holdings, as data]"""
    names = _stocks_state.get("names") or {}
    out = []
    for sym in STOCK_UNIVERSE:
        held = _holdings.get(sym) or {}
        bundle = names.get(sym) or {}
        spot = (bundle.get("quote") or {}).get("spot_reference")
        shares = held.get("shares") or 0
        cost = held.get("avg_cost") or 0
        row = {"symbol": sym, "shares": shares, "avg_cost": cost,
               "spot": spot, "value": None, "pl": None,
               "pl_pct": None,
               "sell": "WATCH (no examined lane)"}
        if shares and spot is not None:
            row["value"] = shares * spot
            if cost:
                row["pl"] = shares * (spot - cost)
                row["pl_pct"] = (spot / cost - 1.0) * 100.0
        out.append(row)
    return json.dumps({"holdings": out})


def set_holding_json(sym, shares, cost):
    """Save or clear one holding, with the Flet validation:
    both fields or neither — a half entry changes nothing.
    [main.py _save_holding]"""
    if sym not in STOCK_UNIVERSE:
        return json.dumps({"ok": False,
                           "note": f"{sym}: not in the universe."})
    if shares is None and cost is None:
        _holdings.pop(sym, None)
        note = f"{sym}: holding cleared."
    elif shares is None or cost is None:
        return json.dumps({
            "ok": False,
            "note": f"{sym}: enter both shares and average "
                    f"cost, or clear both — holding unchanged."})
    else:
        _holdings[sym] = {"shares": float(shares),
                          "avg_cost": float(cost)}
        note = f"{sym}: holding saved on this device."
    _save_json_file("holdings.json", _holdings)
    return json.dumps({"ok": True, "note": note})



# ==================================================================
# Spatial payload for the native TRUE-3D destination (GL).
#
# AXIS MAPPING (also stated in native/PROGRAM.md — the renderer's
# scene is built from exactly these numbers, nothing else):
#   x = implied probability from the quoted price (0..1)
#   y = edge, as a probability fraction (model p - implied p)
#   z = time, in hours (terrain: hours since the window's first
#       point; slate cloud: hours from the pull stamp to the
#       market's own start time, 0 when unparseable — the payload
#       counts those, never hides them)
#
# Terrain: the history store's G1 edge-terrain paths (points
# [t_epoch, p_model, p_implied]) binned onto a regular x/z grid;
# a cell's height is the MEAN edge of the points landing in it.
# Cells with no points are null — the renderer leaves a hole;
# no height is ever interpolated or invented.
# ==================================================================

def spatial_json(window="season"):
    hs = _load_history()
    b5 = _load_engine()
    win = hs.load_window(_store_dir, window,
                         datetime.now(hs.DETROIT))
    records = win["records"]
    terrain = hs.shape_edge_terrain(records)
    pts = []
    for path in terrain["paths"]:
        for t, p_model, p_imp in path["points"]:
            pts.append((t, p_model, p_imp))
    grid = None
    raw_points = []
    if pts:
        t0 = min(p[0] for p in pts)
        t1 = max(p[0] for p in pts)
        span_h = max((t1 - t0) / 3600.0, 1e-9)
        nx, nz = 24, 24
        sums = [[0.0] * nx for _ in range(nz)]
        counts = [[0] * nx for _ in range(nz)]
        for t, p_model, p_imp in pts:
            xi = min(nx - 1, max(0, int(p_imp * nx)))
            zi = min(nz - 1, max(0, int(((t - t0) / 3600.0)
                                         / span_h * nz)))
            sums[zi][xi] += (p_model - p_imp)
            counts[zi][xi] += 1
        heights = [[(sums[z][x] / counts[z][x]
                     if counts[z][x] else None)
                    for x in range(nx)] for z in range(nz)]
        grid = {"nx": nx, "nz": nz, "x_min": 0.0, "x_max": 1.0,
                "z_min_hours": 0.0, "z_max_hours": span_h,
                "heights": heights,
                "cells_filled": sum(1 for z in range(nz)
                                    for x in range(nx)
                                    if counts[z][x]),
                "cells_total": nx * nz}
        raw_points = [[p_imp, p_model - p_imp, (t - t0) / 3600.0]
                      for t, p_model, p_imp in pts[:4000]]
    cloud = []
    z_unknown = 0
    rec = _standing.get("slate")
    if rec:
        verdicts = _ensure_verdicts() or []
        try:
            pulled = datetime.fromisoformat(rec.get("pulled_at"))
        except Exception:
            pulled = None
        for m, v in zip(rec.get("markets") or [], verdicts):
            p = v.get("p")
            price = m.get("price")
            q = b5.implied_prob(price) if price is not None \
                else None
            if p is None or q is None:
                continue
            z = 0.0
            mt = m.get("market_time")
            if pulled is not None and mt:
                try:
                    start = datetime.fromisoformat(
                        str(mt).replace("Z", "+00:00"))
                    if start.tzinfo is None:
                        start = start.replace(
                            tzinfo=pulled.tzinfo)
                    z = (start - pulled).total_seconds() / 3600.0
                except Exception:
                    z_unknown += 1
            else:
                z_unknown += 1
            cloud.append({
                "xyz": [q, p - q, z],
                "golden": card_verdict(v)[0] == "GOLDEN BET",
                "bet_now": bet_now(v),
                "label": (_label_for_cloud(m))})
    return json.dumps({
        "window": window,
        "history_begins": win["history_begins"],
        "axes": {"x": "implied probability (0..1)",
                 "y": "edge (model p - implied p)",
                 "z": "time (hours)"},
        "terrain": {"grid": grid, "points": raw_points,
                    "paths_total": terrain["paths_total"],
                    "paths_returned": terrain["paths_returned"],
                    "cap": terrain["cap"]},
        "slate_cloud": cloud,
        "slate_cloud_z_unknown": z_unknown})


def _label_for_cloud(m):
    name = bet_name(m, None)
    return name.get("slip_label") or name.get("selection") or ""


def _parse_bankroll(raw):
    """The app's bankroll text -> float or None. [main.py,
    verbatim]"""
    try:
        return float(raw or "") or None
    except (TypeError, ValueError):
        return None


# ==================================================================
# Text-arg wrappers for the Kotlin shell (Chaquopy passes
# strings cleanly; bankroll / holding fields are user text in
# every shell this app has ever had — parsed with main.py's own
# _parse_bankroll rule: blank or invalid -> None).
# ==================================================================

def slip_json_text(bankroll_text=None):
    return protected_slip_json(_parse_bankroll(bankroll_text))


def depth_json_text(idx, bankroll_text=None):
    return depth_json(idx, _parse_bankroll(bankroll_text))


def mark_placed_text(bankroll_text=None):
    return mark_placed_json(_parse_bankroll(bankroll_text))


def set_holding_text_json(sym, shares_text, cost_text):
    return set_holding_json(sym, _parse_bankroll(shares_text),
                            _parse_bankroll(cost_text))
