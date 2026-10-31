"""Headless drive of the app's instrument server (fulfillment
step 2): static files byte-exact, /api/slate.json, and
/api/history.json for every window x every graph, plus the
named-JSON error paths. Storage is redirected to a temp dir
before the app module is imported, so the drive never
touches real app storage.

Run: python3 drive_3dfill_server.py  (exit 0 iff all pass)
"""

import copy
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta

TMP = tempfile.mkdtemp(prefix="betfi3d-server-drive-")
os.environ["FLET_APP_STORAGE_DATA"] = TMP

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import main as app  # noqa: E402
import history_store as hs  # noqa: E402

SLATE_PATH = ("/home/hatch/workspace/bets-analyst/mobile/"
              "perf-ab/slate.json")
DETROIT = hs.DETROIT
FAILURES = []


def check(name, cond, detail=""):
    print("[{}] {}{}".format("PASS" if cond else "FAIL", name,
                             " — " + detail if detail else ""))
    if not cond:
        FAILURES.append(name)


def fixture_verdicts(markets, pull_idx):
    out = []
    for i, m in enumerate(markets):
        q = hs.implied_prob(m.get("price"))
        if q is None:
            out.append(None)
            continue
        off = (((i * 7 + pull_idx * 3) % 9) - 4) * 0.008
        p = min(0.99, max(0.01, q + off))
        out.append({"p": p, "verdict": "BET HERE",
                    "grade": "B", "metal": "SILVER"})
    return out


def jittered(markets, pull_idx):
    ms = copy.deepcopy(markets)
    if pull_idx:
        for i, m in enumerate(ms):
            if i % 7 == 0 and m.get("price") is not None:
                m["price"] = (m["price"] + 10 if m["price"] > 0
                              else m["price"] - 10)
    return ms


def main_drive():
    slate = json.load(open(SLATE_PATH))
    now = datetime.now(DETROIT)
    stamps = [(now - timedelta(hours=h)).isoformat(
        timespec="seconds") for h in (5, 2, 0)]
    store_dir = app.history_store_dir()
    for j, stamp in enumerate(stamps):
        rec = copy.deepcopy(slate)
        rec["pulled_at"] = stamp
        rec["markets"] = jittered(slate["markets"], j)
        res = hs.record_pull(store_dir, rec,
                             fixture_verdicts(rec["markets"], j))
        assert res["status"] == "recorded", res
    app._CURRENT_SLATE["rec"] = slate

    port = app.ensure_instrument_server()
    check("server binds a port", port is not None,
          "port={}".format(port))
    if port is None:
        return 1
    base = "http://127.0.0.1:{}".format(port)

    def fetch(path):
        try:
            with urllib.request.urlopen(base + path,
                                        timeout=15) as r:
                return r.status, r.headers.get_content_type(), \
                    r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get_content_type(), e.read()

    try:
        # static: byte-exact instrument file
        st, ct, body = fetch("/g1-edge-terrain.html")
        disk = open(os.path.join(
            app.INSTRUMENTS_DIR, "g1-edge-terrain.html"),
            "rb").read()
        check("static instrument served byte-exact",
              st == 200 and body == disk,
              "status={} bytes={}".format(st, len(body)))

        # slate API
        st, ct, body = fetch("/api/slate.json")
        payload = json.loads(body)
        check("slate.json 200 with the current pull's events",
              st == 200 and ct == "application/json"
              and payload["markets"] == len(slate["markets"])
              and len(payload["events"]) > 0
              and payload["events"][0]["label"],
              "events={}".format(len(payload["events"])))

        graphs = sorted(hs.GRAPH_SHAPES)
        ok_all = True
        g1_month = None
        for window in ("live", "month", "season"):
            for graph in graphs:
                st, ct, body = fetch(
                    "/api/history.json?window={}&graph={}"
                    .format(window, graph))
                p = json.loads(body)
                good = (st == 200
                        and p["window"] == window
                        and p["graph"] == graph
                        and "grain" in p and "from" in p
                        and "to" in p
                        and p["history_begins"] == stamps[0]
                        and isinstance(p["series"], dict))
                if not good:
                    ok_all = False
                    print("  bad payload: {} {} -> {}".format(
                        window, graph, st))
                if window == "month" and graph == "g1-edge-terrain":
                    g1_month = p
        check("history.json: every window x graph answers "
              "the contract shape", ok_all)
        check("g1 month series carries capped real paths",
              g1_month is not None
              and g1_month["series"]["paths_returned"]
              == hs.EDGE_TERRAIN_CAP
              and g1_month["series"]["paths_total"]
              > hs.EDGE_TERRAIN_CAP,
              "paths={}".format((g1_month or {}).get(
                  "series", {}).get("paths_returned")))

        st, ct, body = fetch("/api/history.json?window=month"
                             "&graph=g4-calibration-volume")
        p = json.loads(body)
        check("g4 answers its UNBUILT-DATA gate, not a series",
              st == 200
              and p["series"].get("gate") == "UNBUILT-DATA"
              and "results join" in p["series"]["missing"])
        st, ct, body = fetch("/api/history.json?window=season"
                             "&graph=g7-team-trajectories")
        p = json.loads(body)
        check("g7 answers its gate (no pool stamps on file)",
              st == 200
              and p["series"].get("gate") == "UNBUILT-DATA")

        st, ct, body = fetch(
            "/api/history.json?window=live"
            "&graph=g2-price-rivers")
        p = json.loads(body)
        ev = p["series"]["event"]["fd_event_id"]
        st2, ct2, body2 = fetch(
            "/api/history.json?window=live"
            "&graph=g2-price-rivers&event={}".format(ev))
        p2 = json.loads(body2)
        check("g2 event parameter selects the asked game",
              st2 == 200
              and p2["series"]["event"]["fd_event_id"] == ev
              and p2["series"]["ribbons_returned"] > 0,
              "event={}".format(ev))

        st, ct, body = fetch("/api/history.json?graph=nope")
        err = json.loads(body)
        check("unknown graph -> 400 named JSON",
              st == 400 and err.get("error") == "unknown_graph",
              "status={} error={}".format(st, err.get("error")))
        st, ct, body = fetch("/api/history.json?window=nope")
        err = json.loads(body)
        check("unknown window -> 400 named JSON",
              st == 400 and err.get("error") == "unknown_window",
              "status={} error={}".format(st, err.get("error")))
        st, ct, body = fetch("/api/nope.json")
        err = json.loads(body)
        check("unknown api path -> 404 named JSON",
              st == 404
              and err.get("error") == "unknown_api_path",
              "status={} error={}".format(st, err.get("error")))
        st, ct, body = fetch("/no-such-instrument.html")
        err = json.loads(body)
        check("missing static file -> named JSON, no HTML "
              "traceback page",
              st == 404 and ct == "application/json"
              and err.get("error") == "http_404",
              "status={} ct={}".format(st, ct))
    finally:
        httpd = app._instrument_server.get("httpd")
        if httpd is not None:
            try:
                httpd.shutdown()
            except Exception:
                pass
    if FAILURES:
        print("FAILED: {}".format(", ".join(FAILURES)))
        return 1
    print("ALL SERVER DRIVES PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main_drive())
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
