"""End-to-end recorder drive (fulfillment step 1): boot the
real app on the harness's FakePage pattern, stub the engine's
FanDuel seams exactly as harness.py does, land two scoped
soccer pulls through the actual UI handlers, and verify:

  * each landed pull appends exactly one record, holding
    ONLY the pulled sport's slice under its own stamp;
  * the recorder health counters move and no error stamps;
  * the merged save_snapshot moments in between (the menu
    harvest) do NOT double-record;
  * the recorded store reads back through the app's own
    /api/history.json (G6 coverage sees the soccer cells,
    history_begins is the first pull's stamp).

Storage is a temp dir set before import. Fixture markets are
the harness's own stub shape — plumbing only, never data.

Run: ~/workspace/.venvs/fletcheck/bin/python \
    drive_3dfill_recorder.py   (exit 0 iff all pass)
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request
from types import SimpleNamespace

TMP = tempfile.mkdtemp(prefix="betfi3d-recorder-drive-")
os.environ["FLET_APP_STORAGE_DATA"] = TMP

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import betmodel5 as b5  # noqa: E402
import main as app  # noqa: E402
import history_store as hs  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print("[{}] {}{}".format("PASS" if cond else "FAIL", name,
                             " — " + detail if detail else ""))
    if not cond:
        FAILURES.append(name)


class FakePage:
    """The harness probe-page convention: run_thread inline,
    run_task executes coroutines to completion."""

    def __init__(self):
        self.controls = []
        self.overlay = []
        self.navigation_bar = None
        self.services = []
        self.title = None
        self.bgcolor = None
        self.theme_mode = None
        self.padding = None
        self.spacing = None
        self.scroll = None
        self.updates = 0
        self.task_errors = []

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self, *args, **kwargs):
        self.updates += 1

    def run_thread(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def run_task(self, fn, *args, **kwargs):
        out = fn(*args, **kwargs)
        if asyncio.iscoroutine(out):
            errs = self.__dict__.setdefault("task_errors", [])
            lp = asyncio.new_event_loop()
            try:
                lp.run_until_complete(out)
            except Exception as ex:  # noqa: BLE001
                errs.append(ex)
            finally:
                lp.close()
        return None


def walk(ctrl, depth=0):
    yield ctrl
    if depth > 14:
        return
    for attr in ("controls", "content"):
        v = getattr(ctrl, attr, None)
        if isinstance(v, (list, tuple)):
            for c in v:
                yield from walk(c, depth + 1)
        elif v is not None and not isinstance(
                v, (str, int, float, bool)):
            yield from walk(v, depth + 1)


def _stub_get(endpoint, params):
    return {"attachments": {}}


def _stub_parse(page, sport):
    mkts = [
        {"sport": sport, "market": "moneyline",
         "side": "home", "home": "AAA", "away": "BBB",
         "price": -150, "fd_event_id": f"stub-{sport}-1",
         "market_time": "2026-10-26T17:00:00"},
        {"sport": sport, "market": "totals",
         "side": "over", "home": "AAA", "away": "BBB",
         "line": 44.5, "price": -110,
         "fd_event_id": f"stub-{sport}-1",
         "market_time": "2026-10-26T17:00:00"},
        {"sport": sport, "market": "moneyline",
         "side": "away", "home": "CCC", "away": "DDD",
         "price": 130, "fd_event_id": f"stub-{sport}-2",
         "market_time": "2026-10-26T20:00:00"}]
    return mkts, {"moneyline": 2, "totals": 1}, 2, {sport: 2}


def _stub_event_menu(eid):
    return {"event_id": eid, "markets": []}


def main_drive():
    orig = (b5.fd_get, b5.fd_parse_sport_page,
            b5.fd_event_menu, b5.build_menu_tree)
    b5.fd_get = _stub_get
    b5.fd_parse_sport_page = _stub_parse
    b5.fd_event_menu = _stub_event_menu
    b5.build_menu_tree = lambda ctx: {"event_types": {},
                                      "az_order": []}
    try:
        page = FakePage()
        app.main(page)
        board = page.controls[1].content
        chooser = next(
            d for d in walk(board)
            if type(d).__name__ == "Dropdown"
            and len(getattr(d, "options", None) or []) == 17)
        chooser.on_select(SimpleNamespace(
            control=SimpleNamespace(value="soccer")))

        def btn_label(c):
            t = getattr(c, "text", None)
            if t:
                return t
            ct = getattr(c, "content", None)
            if isinstance(ct, str):
                return ct
            return getattr(ct, "value", None)

        pulls = [c for c in walk(board)
                 if type(c).__name__ == "Button"
                 and btn_label(c) == "Pull"]
        check("scoped Pull button found", len(pulls) == 1)
        if not pulls:
            return 1
        pulls[0].on_click(SimpleNamespace())

        store = app.history_store_dir()
        from datetime import datetime as _dt
        season = hs.load_window(store, "season",
                                _dt.now(hs.DETROIT))
        recs = season["records"]
        check("one scoped pull -> exactly one record",
              len(recs) == 1, "records={}".format(len(recs)))
        if recs:
            r0 = recs[0]
            check("record holds only the pulled slice",
                  r0["scopes"] == ["soccer"]
                  and len(r0["markets"]) == 3
                  and all(m["sport"] == "soccer"
                          for m in r0["markets"]),
                  "scopes={} markets={}".format(
                      r0["scopes"], len(r0["markets"])))
            snap = json.load(open(os.path.join(
                TMP, "Bet_Finder-last-pull.json")))
            check("record stamp == the slate's pulled_at",
                  r0["pulled_at"] == snap["pulled_at"],
                  "rec={} snap={}".format(
                      r0["pulled_at"], snap["pulled_at"]))
            check("record keys follow the contract",
                  all(m["key"] == hs.market_key(m)
                      for m in r0["markets"]))
        health = app._RECORDER_HEALTH
        check("health: one recorded, no error stamped",
              health["recorded"] == 1
              and health["last_error"] is None,
              "health={}".format(health))

        time.sleep(1.1)  # cross a stamp-second boundary
        pulls[0].on_click(SimpleNamespace())
        season = hs.load_window(store, "season",
                                _dt.now(hs.DETROIT))
        recs = season["records"]
        check("second pull appends (harvest saves in between "
              "did not double-record)",
              len(recs) == 2, "records={}".format(len(recs)))
        check("health: two recorded, still no error",
              app._RECORDER_HEALTH["recorded"] == 2
              and app._RECORDER_HEALTH["last_error"] is None)
        check("history_begins is the first pull's stamp",
              season["history_begins"] == recs[0]["pulled_at"]
              and app.history_health_line().startswith(
                  "Pull-history recorder: recording"),
              app.history_health_line()[:60])

        # the full-pull moment: one record, the whole slate
        time.sleep(1.1)
        pull_alls = [c for c in walk(board)
                     if type(c).__name__ == "Button"
                     and btn_label(c) == "Pull all"]
        check("Pull all button found", len(pull_alls) == 1)
        if pull_alls:
            pull_alls[0].on_click(SimpleNamespace())
            season = hs.load_window(store, "season",
                                    _dt.now(hs.DETROIT))
            recs = season["records"]
            full = recs[-1] if recs else {}
            check("full pull appends one whole-slate record",
                  len(recs) == 3
                  and len(full.get("markets") or [])
                  == 3 * len(b5.FANDUEL_EVENT_TYPES)
                  and len(full.get("scopes") or [])
                  == len(b5.FANDUEL_EVENT_TYPES),
                  "records={} markets={} scopes={}".format(
                      len(recs),
                      len(full.get("markets") or []),
                      len(full.get("scopes") or [])))
            check("health: three recorded, no error",
                  app._RECORDER_HEALTH["recorded"] == 3
                  and app._RECORDER_HEALTH["last_error"] is None)

        # read it back through the app's own API
        port = app.ensure_instrument_server()
        with urllib.request.urlopen(
                "http://127.0.0.1:{}/api/history.json"
                "?window=live&graph=g6-coverage-topography"
                .format(port), timeout=15) as r:
            payload = json.loads(r.read())
        cells = [c for c in payload["series"]["cells"]
                 if c["sport"] == "soccer"]
        check("API reads the recorded store (G6 soccer cells)",
              len(cells) == 3
              and all(c["n"] == 3 for c in cells)
              and payload["history_begins"]
              == recs[0]["pulled_at"],
              "cells={}".format(len(cells)))
        httpd = app._instrument_server.get("httpd")
        if httpd is not None:
            httpd.shutdown()
    finally:
        (b5.fd_get, b5.fd_parse_sport_page,
         b5.fd_event_menu, b5.build_menu_tree) = orig
    if FAILURES:
        print("FAILED: {}".format(", ".join(FAILURES)))
        return 1
    print("ALL RECORDER DRIVES PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_drive())
