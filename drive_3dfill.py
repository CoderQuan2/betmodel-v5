"""Offline drives for the 3D-fulfillment build (xii-3dfill).

Part A–C port the scaffold's drive patterns against the
APP's bundled history_store; part D checks the new graph
shapes' purity; part E drives the recorder entry points
(record_pull / has_pull / history_begins) including the
convergent re-fold case from the DATA-CONTRACT amendments.

Fixtures note: verdicts synthesized here are TEST FIXTURES
only (p from a fixed formula) — they drive plumbing offline
and never touch real data.

Run: python3 drive_3dfill.py   (exit 0 only if all pass)
"""

import copy
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
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


def drive_a(tmp):
    slate = json.load(open(SLATE_PATH))
    now = datetime.now(DETROIT)
    stamps = [(now - timedelta(days=d)).isoformat(
        timespec="seconds") for d in (2, 1, 0)]
    store = os.path.join(tmp, "store_a")
    n_markets = len(slate["markets"])
    for j, stamp in enumerate(stamps):
        rec = copy.deepcopy(slate)
        rec["pulled_at"] = stamp
        rec["markets"] = jittered(slate["markets"], j)
        shaped = hs.shape_record(
            rec, fixture_verdicts(rec["markets"], j))
        hs.append_pull(store, shaped)
    live = hs.load_window(store, "live", now)
    month = hs.load_window(store, "month", now)
    season = hs.load_window(store, "season", now)
    check("a: window record counts live/month/season",
          (len(live["records"]), len(month["records"]),
           len(season["records"])) == (1, 3, 3),
          "live={} month={} season={}".format(
              len(live["records"]), len(month["records"]),
              len(season["records"])))
    check("a: history_begins is the oldest stamp",
          season["history_begins"] == stamps[0]
          and month["history_begins"] == stamps[0])
    check("a: from/to span the window",
          season["from"] == stamps[0]
          and season["to"] == stamps[2]
          and live["from"] == stamps[2])
    rec0 = season["records"][0]
    check("a: record shape (grain, market count)",
          rec0["grain"] == "pull"
          and len(rec0["markets"]) == n_markets
          and season["grain"] == "pull")
    sports_present = sorted({m["sport"]
                             for m in slate["markets"]})
    check("a: scopes = sorted sports present",
          rec0["scopes"] == sports_present)
    keys_ok = all(
        e["key"] == hs.market_key(
            {"sport": e["sport"], "fd_event_id": e["fd_event_id"],
             "market": e["market"], "side": e["side"],
             "line": e["line"]})
        for e in rec0["markets"])
    check("a: every entry key matches market_key()", keys_ok)
    e0 = next(e for e in rec0["markets"]
              if e["p"] is not None and e["price"] is not None)
    expect = round((e0["p"] - hs.implied_prob(e0["price"]))
                   * 100.0, 3)
    check("a: edge_pts = (p - implied) * 100",
          e0["edge_pts"] == expect,
          "edge={} expected={}".format(e0["edge_pts"], expect))
    return store, now, stamps


def mini(stamp, markets, p=0.6):
    return hs.shape_record(
        {"pulled_at": stamp, "markets": markets, "sports": {}},
        [{"p": p, "verdict": "BET HERE", "grade": "B",
          "metal": "SILVER"}] * len(markets))


def drive_b(tmp, now):
    store = os.path.join(tmp, "store_b")
    day = (now - timedelta(days=40)).date()
    t1 = datetime(day.year, day.month, day.day, 9, 0,
                  tzinfo=DETROIT).isoformat(timespec="seconds")
    t2 = datetime(day.year, day.month, day.day, 18, 0,
                  tzinfo=DETROIT).isoformat(timespec="seconds")

    def mk(stamp, k1_price, with_k2=True):
        markets = [
            {"sport": "nfl", "fd_event_id": 111,
             "fd_market_id": "1.1", "fd_selection_id": 11,
             "market": "moneyline", "side": "home",
             "line": None, "price": k1_price},
            {"sport": "nfl", "fd_event_id": 111,
             "fd_market_id": "1.2", "fd_selection_id": 12,
             "market": "totals", "side": "over",
             "line": 44.5, "price": -110}]
        if with_k2:
            markets.append(
                {"sport": "nba", "fd_event_id": 222,
                 "fd_market_id": "2.1", "fd_selection_id": 21,
                 "market": "spread", "side": "away",
                 "line": -3.5, "price": -105})
        return mini(stamp, markets)

    hs.append_pull(store, mk(t1, -140))
    hs.append_pull(store, mk(t2, -150, with_k2=False))
    hs.append_pull(store, mk(
        now.isoformat(timespec="seconds"), -160))
    res = hs.compact(store, now)
    season = hs.load_window(store, "season", now)
    daily = [r for r in season["records"] if r["grain"] == "day"]
    pulls = [r for r in season["records"]
             if r["grain"] == "pull"]
    check("b: old day folded to one daily record per key",
          len(daily) == 3 and len(pulls) == 1,
          "daily={} pulls={} compact={}".format(
              len(daily), len(pulls), res))
    by_key = {r["markets"][0]["key"]: r for r in daily}
    k1key = hs.market_key(
        {"sport": "nfl", "fd_event_id": 111,
         "market": "moneyline", "side": "home", "line": None})
    k1 = by_key.get(k1key)
    check("b: last pull wins (price + stamp)",
          k1 is not None
          and k1["markets"][0]["price"] == -150
          and k1["pulled_at"] == t2)
    k2 = by_key.get(hs.market_key(
        {"sport": "nba", "fd_event_id": 222,
         "market": "spread", "side": "away", "line": -3.5}))
    check("b: key seen only in pull 1 keeps pull 1's stamp",
          k2 is not None and k2["pulled_at"] == t1)
    check("b: season grain reads mixed after folding",
          season["grain"] == "mixed")

    def store_bytes():
        out = {}
        hdir = os.path.join(store, hs.HISTORY_DIRNAME)
        for f in sorted(os.listdir(hdir)):
            out[f] = open(os.path.join(hdir, f), "rb").read()
        return out

    before = store_bytes()
    hs.compact(store, now)
    check("b: compaction is idempotent",
          store_bytes() == before)

    # convergent re-fold: a LATER same-day pull appended after
    # the fold must win the day; an EARLIER one must not
    # displace the standing daily record.
    t3 = datetime(day.year, day.month, day.day, 21, 0,
                  tzinfo=DETROIT).isoformat(timespec="seconds")
    t0 = datetime(day.year, day.month, day.day, 7, 0,
                  tzinfo=DETROIT).isoformat(timespec="seconds")
    hs.append_pull(store, mk(t3, -170, with_k2=False))
    hs.compact(store, now)
    season = hs.load_window(store, "season", now)
    daily = {r["markets"][0]["key"]: r
             for r in season["records"] if r["grain"] == "day"}
    k1 = daily.get(k1key)
    check("b2: re-fold — later same-day pull wins the day",
          k1 is not None
          and k1["markets"][0]["price"] == -170
          and k1["pulled_at"] == t3,
          "price={} stamp={}".format(
              k1["markets"][0]["price"] if k1 else None,
              k1["pulled_at"] if k1 else None))
    hs.append_pull(store, mk(t0, -120, with_k2=False))
    hs.compact(store, now)
    season = hs.load_window(store, "season", now)
    daily = {r["markets"][0]["key"]: r
             for r in season["records"] if r["grain"] == "day"}
    k1 = daily.get(k1key)
    check("b2: re-fold — earlier pull cannot displace the win",
          k1 is not None
          and k1["markets"][0]["price"] == -170
          and k1["pulled_at"] == t3)
    check("b2: still exactly one daily record per key",
          len([r for r in season["records"]
               if r["grain"] == "day"]) == 3)


def drive_c(store, now):
    month = hs.load_window(store, "month", now)
    payload = hs.shape_edge_terrain(month["records"])
    paths = payload["paths"]
    ok_sorted = all(
        all(p["points"][i][0] <= p["points"][i + 1][0]
            for i in range(len(p["points"]) - 1))
        for p in paths)
    ok_range = all(0.0 <= pt[1] <= 1.0 and 0.0 <= pt[2] <= 1.0
                   for p in paths for pt in p["points"])
    ok_len = all(len(p["points"]) >= 2 for p in paths)
    check("c: terrain paths present and capped",
          len(paths) == hs.EDGE_TERRAIN_CAP
          and payload["paths_total"] > hs.EDGE_TERRAIN_CAP,
          "returned={} total={}".format(
              len(paths), payload["paths_total"]))
    check("c: points sorted, >= 2 per path, probs in [0,1]",
          ok_sorted and ok_range and ok_len
          and payload["diagonal"] is True)


def synth_records(now):
    """Three pulls today, two events, mixed priced/unpriced."""
    stamps = [(now - timedelta(hours=h)).isoformat(
        timespec="seconds") for h in (5, 3, 0)]

    def mkts(pull):
        base = [
            {"sport": "nfl", "fd_event_id": 111,
             "fd_market_id": "1.1", "fd_selection_id": 11,
             "market": "moneyline", "side": "home",
             "line": None, "price": -140 - pull * 10},
            {"sport": "nfl", "fd_event_id": 111,
             "fd_market_id": "1.2", "fd_selection_id": 12,
             "market": "moneyline", "side": "away",
             "line": None, "price": 120 + pull * 5},
            {"sport": "nfl", "fd_event_id": 111,
             "fd_market_id": "1.3", "fd_selection_id": 13,
             "market": "totals", "side": "over",
             "line": 44.5, "price": -110},
            {"sport": "nba", "fd_event_id": 222,
             "fd_market_id": "2.1", "fd_selection_id": 21,
             "market": "spread", "side": "away",
             "line": -3.5, "price": -105 - pull * 5},
            {"sport": "nba", "fd_event_id": 222,
             "fd_market_id": "2.2", "fd_selection_id": 22,
             "market": "moneyline", "side": "home",
             "line": None, "price": None},
        ]
        vs = []
        for m in base:
            q = hs.implied_prob(m["price"])
            if q is None:
                vs.append(None)
            else:
                vs.append({"p": min(0.99, max(
                    0.01, q + 0.02 - pull * 0.005)),
                    "verdict": "BET HERE", "grade": "B",
                    "metal": "SILVER"})
        return hs.shape_record(
            {"pulled_at": stamps[pull], "markets": base,
             "sports": {}}, vs)

    return [mkts(j) for j in range(3)]


def drive_d(now):
    records = synth_records(now)
    riv = hs.shape_price_rivers(records)
    check("d: rivers default event is the richest priced",
          riv["event"] is not None
          and riv["event"]["fd_event_id"] == 111
          and riv["ribbons_returned"] >= 2,
          "event={} ribbons={}".format(
              (riv["event"] or {}).get("fd_event_id"),
              riv["ribbons_returned"]))
    ok = all(all(pt[1] is not None for pt in r["points"])
             and all(r["points"][i][0] <= r["points"][i + 1][0]
                     for i in range(len(r["points"]) - 1))
             for r in riv["ribbons"])
    check("d: river points time-sorted with prices", ok)
    riv2 = hs.shape_price_rivers(records, event_id=222)
    check("d: rivers honour an explicit event",
          riv2["event"] is not None
          and riv2["event"]["fd_event_id"] == 222)
    riv3 = hs.shape_price_rivers(records, event_id=999)
    check("d: rivers unknown event -> no ribbons, no fake pick",
          riv3["event"] is None and riv3["ribbons"] == [])

    drift = hs.shape_drift_field(records)
    check("d: drift points in range, lanes named",
          drift["points_total"] > 0
          and all(-100.0 <= p["x"] <= 100.0
                  and -100.0 <= p["y"] <= 100.0
                  and 0 <= p["z"] < 3
                  for p in drift["points"])
          and drift["lanes"] == sorted(drift["lanes"]),
          "points={} lanes={}".format(
              drift["points_total"], drift["lanes"]))

    cov = hs.shape_coverage_topography(records)
    check("d: coverage shares in [0,1], cells time-sorted",
          cov["cells_total"] == 6
          and all(0.0 <= c["share"] <= 1.0 for c in cov["cells"])
          and all(cov["cells"][i]["t"]
                  <= cov["cells"][i + 1]["t"]
                  for i in range(len(cov["cells"]) - 1))
          and set(cov["sports"]) == {"nfl", "nba"},
          "cells={} sports={}".format(
              cov["cells_total"], cov["sports"]))
    nba_cells = [c for c in cov["cells"] if c["sport"] == "nba"]
    check("d: coverage counts the unpriced denominator",
          all(c["n"] == 2 and c["priced"] == 1
              and abs(c["share"] - 0.5) < 1e-9
              for c in nba_cells))

    corr = hs.shape_correlation_space(records)
    check("d: correlation trails sorted, non-negative spread",
          corr["trails_returned"] == 1
          and corr["trails"][0]["fd_event_id"] == 111
          and all(pt[1] >= 0.0 and pt[2] >= 0.0
                  for pt in corr["trails"][0]["points"])
          and all(corr["trails"][0]["points"][i][0]
                  <= corr["trails"][0]["points"][i + 1][0]
                  for i in range(2)),
          "trails={}".format(corr["trails_returned"]))

    clv = hs.shape_clv_surface(records)
    check("d: clv cells sane + settled gate rides the payload",
          len(clv["cells"]) > 0
          and all(-100.0 <= c["mean_move_pts"] <= 100.0
                  for c in clv["cells"])
          and clv["settled"]["gate"] == "UNBUILT-DATA"
          and "results join" in clv["settled"]["missing"],
          "cells={}".format(len(clv["cells"])))

    g4 = hs.shape_calibration_volume(records)
    check("d: g4 is a gate, never a series",
          g4["gate"] == "UNBUILT-DATA"
          and "results join" in g4["missing"]
          and "series" not in g4
          and g4["records_seen"] == 3)

    g7 = hs.shape_team_trajectories(records)
    check("d: g7 gates without pool stamps in the record",
          g7["gate"] == "UNBUILT-DATA"
          and "pool" in g7["missing"])
    pooled = copy.deepcopy(records)
    for j, r in enumerate(pooled):
        r["pools"] = {"nfl": {"KC": {
            "attack": 1.1 + j * 0.1, "defense": 0.9,
            "rating": 0.2 + j * 0.05}}}
    g7b = hs.shape_team_trajectories(pooled)
    check("d: g7 draws paths when pools ride, and says thin",
          "paths" in g7b and len(g7b["paths"]) == 1
          and len(g7b["paths"][0]["points"]) == 3
          and g7b["thin"] is True and g7b["thin_note"])

    try:
        hs.shape_for("nope", records)
        check("d: shape_for unknown graph raises", False)
    except ValueError as e:
        check("d: shape_for unknown graph raises",
              str(e) == "unknown_graph")


def drive_e(tmp, now, stamps):
    store = os.path.join(tmp, "store_e")
    slate = json.load(open(SLATE_PATH))
    rec = copy.deepcopy(slate)
    rec["pulled_at"] = stamps[2]
    vs = fixture_verdicts(rec["markets"], 0)
    r1 = hs.record_pull(store, rec, vs)
    r2 = hs.record_pull(store, rec, vs)
    check("e: record_pull records once, then dedupes",
          r1["status"] == "recorded"
          and r2["status"] == "duplicate",
          "r1={} r2={}".format(r1["status"], r2["status"]))
    check("e: has_pull reports the recorded market count",
          hs.has_pull(store, stamps[2]) == len(rec["markets"])
          and hs.has_pull(store, stamps[0]) is None)
    season = hs.load_window(store, "season", now)
    check("e: store holds exactly the one record",
          len(season["records"]) == 1)
    check("e: history_begins helper finds the birth stamp",
          hs.history_begins(store) == stamps[2]
          and hs.history_begins(
              os.path.join(tmp, "no-such-store")) is None)
    rec2 = copy.deepcopy(slate)
    rec2["pulled_at"] = (now - timedelta(hours=1)).isoformat(
        timespec="seconds")
    r3 = hs.record_pull(store, rec2,
                        fixture_verdicts(rec2["markets"], 1))
    season = hs.load_window(store, "season", now)
    check("e: a second, distinct pull appends",
          r3["status"] == "recorded"
          and len(season["records"]) == 2)
    try:
        hs.record_pull(store, {"markets": []}, [])
        check("e: stamp-less rec raises (caller stamps Lab)",
              False)
    except ValueError:
        check("e: stamp-less rec raises (caller stamps Lab)",
              True)


def main():
    tmp = tempfile.mkdtemp(prefix="betfi3d-app-drive-")
    try:
        store, now, stamps = drive_a(tmp)
        drive_b(tmp, now)
        drive_c(store, now)
        drive_d(now)
        drive_e(tmp, now, stamps)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if FAILURES:
        print("FAILED: {}".format(", ".join(FAILURES)))
        return 1
    print("ALL DRIVES PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
