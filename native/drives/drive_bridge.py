"""Desktop drives for the Grand BetFi bridge (Tier 1).

Run from anywhere:  python3 native/drives/drive_bridge.py
Exits non-zero if any check fails. Network drives (FanDuel pull,
Nasdaq stocks) are best-effort: they report REACHABLE + results or
the exact blocker, and never fail the run on a network block.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PYDIR = os.path.join(HERE, "..", "app", "src", "main", "python")
ASSETS = os.path.join(HERE, "..", "app", "src", "main", "assets")
sys.path.insert(0, os.path.abspath(PYDIR))

import bridge  # noqa: E402
import history_store as hs  # noqa: E402 (resolves via bridge's path)

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))


def canon(o):
    if isinstance(o, dict):
        return {k: canon(o[k]) for k in sorted(o)}
    if isinstance(o, list):
        return [canon(x) for x in o]
    return o


sample = open(os.path.join(ASSETS, "sample_slate.json")).read()
reference = json.load(open(os.path.join(ASSETS,
                                        "reference_verdicts.json")))

# ---- 1. parity, bundled defaults (no init) ----
got = json.loads(bridge.run_slate_json(sample))
check("parity: bridge.run_slate_json(sample) == reference (exact)",
      canon(got) == canon(reference),
      f"{len(got)} verdicts")

# ---- 2. init drive (fake filesDir) ----
tmp = tempfile.mkdtemp(prefix="grandbetfi-drive-")
bridge.init(tmp)
st = json.loads(bridge.init_status())
check("init: ok, data dir under filesDir",
      st["ok"] is True and st["data_dir"].startswith(tmp))
marker = os.path.join(tmp, "history-store", "device-marker.txt")
with open(marker, "w") as f:
    f.write("mine")
bridge.init(tmp)  # re-init must not clobber device state
check("init: idempotent, device files survive re-init",
      open(marker).read() == "mine")
got2 = json.loads(bridge.run_slate_json(sample))
check("parity after init (repointed data): still exact",
      canon(got2) == canon(reference))

# ---- 3. fixture history store -> history_json, 8 graphs x 3 windows ----
now = datetime.now(hs.DETROIT)
stamps = [(now - timedelta(hours=h)).isoformat(timespec="seconds")
          for h in (5, 3, 0)]


def synth_rec(pull):
    base = [
        {"sport": "nfl", "fd_event_id": 111, "fd_market_id": "1.1",
         "fd_selection_id": 11, "market": "moneyline", "side": "home",
         "line": None, "price": -140 - pull * 10},
        {"sport": "nfl", "fd_event_id": 111, "fd_market_id": "1.2",
         "fd_selection_id": 12, "market": "moneyline", "side": "away",
         "line": None, "price": 120 + pull * 5},
        {"sport": "nfl", "fd_event_id": 111, "fd_market_id": "1.3",
         "fd_selection_id": 13, "market": "totals", "side": "over",
         "line": 44.5, "price": -110},
        {"sport": "nba", "fd_event_id": 222, "fd_market_id": "2.1",
         "fd_selection_id": 21, "market": "spread", "side": "away",
         "line": -3.5, "price": -105 - pull * 5},
        {"sport": "nba", "fd_event_id": 222, "fd_market_id": "2.2",
         "fd_selection_id": 22, "market": "moneyline", "side": "home",
         "line": None, "price": None},
    ]
    vs = []
    for m in base:
        q = hs.implied_prob(m["price"])
        vs.append(None if q is None else
                  {"p": min(0.99, max(0.01, q + 0.02)),
                   "verdict": "BET HERE", "grade": "B",
                   "metal": "SILVER"})
    return {"pulled_at": stamps[pull], "markets": base,
            "sports": {}}, vs


for j in range(3):
    rec, vs = synth_rec(j)
    res = hs.record_pull(bridge._store_dir, rec, vs)
    assert res["status"] == "recorded", res

graphs = sorted(hs.GRAPH_SHAPES)
ok_all, detail = True, ""
for window in ("live", "month", "season"):
    for g in graphs:
        p = json.loads(bridge.history_json(window, g))
        if not (p.get("window") == window and p.get("graph") == g
                and "grain" in p and "from" in p and "to" in p
                and p.get("history_begins") == stamps[0]
                and "series" in p):
            ok_all, detail = False, f"{window}/{g}: {list(p)}"
check("history_json: 8 graphs x 3 windows, contract shape + "
      "history_begins", ok_all, detail)
g4 = json.loads(bridge.history_json("live", "g4-calibration-volume"))
g7 = json.loads(bridge.history_json("season", "g7-team-trajectories"))
g8 = json.loads(bridge.history_json("live", "g8-clv-surface"))
check("history_json: G4 + G7 gates ride the payload; G8 settled gate",
      g4["series"].get("gate") == "UNBUILT-DATA"
      and g7["series"].get("gate") == "UNBUILT-DATA"
      and g8["series"]["settled"]["gate"] == "UNBUILT-DATA")
e1 = json.loads(bridge.history_json("live", "nope"))
e2 = json.loads(bridge.history_json("nope", "g1-edge-terrain"))
check("history_json: named errors (unknown_graph / unknown_window)",
      e1.get("error") == "unknown_graph"
      and e2.get("error") == "unknown_window")
riv = json.loads(bridge.history_json(
    "live", "g2-price-rivers", event_id="111"))
check("history_json: G2 event param honoured",
      riv["series"]["event"] is not None
      and riv["series"]["event"]["fd_event_id"] == 111)

# ---- 4. board payload over the sample slate ----
bridge._standing["slate"] = json.loads(sample)
bridge._standing["verdicts"] = None
board = json.loads(bridge.current_board_json())
cards = board["cards"]
check("board: 25 cards, receipt matches the census sample "
      "(18 priced / 8 bet_now)",
      len(cards) == 25 and board["receipt"]["priced"] == 18
      and board["receipt"]["bet_now"] == 8,
      f"receipt={board['receipt']}")
def url_shape_ok(c):
    return c["bet_url"].startswith(
        "https://sportsbook.fanduel.com/addToBetslip?marketId=") \
        and "&selectionId=" in c["bet_url"]


armed = [c for c in cards if c["link_state"] == "armed"]
check("board: link_state is consistent with the ids each market "
      "carries (the sample predates selection ids -> all unarmed, "
      "the honest state)",
      all((c["bet_url"] is not None) == (
          c["market"].get("fd_market_id") is not None
          and c["market"].get("fd_selection_id") is not None)
          for c in cards)
      and all(url_shape_ok(c) for c in armed),
      f"armed={len(armed)} of {len(cards)}")
check("board: every card carries name + row blocks",
      all(c["name"]["slip_label"] and c["row"]["headline"]
          and c["row"]["event"] for c in cards))

# ---- 5. depth ----
priced_idx = next(c["idx"] for c in cards
                  if c["state"] == "PRICED")
depth = json.loads(bridge.depth_json(priced_idx))
titles = [s["title"] for s in depth["sections"]]
check("depth: five sections in the Flet order",
      titles == ["PRICE ANATOMY", "THE MATHEMATICS", "SCALE",
                 "COHERENCE", "PROVENANCE"], str(titles))
prov = " ".join(depth["sections"][4]["lines"])
check("depth: PROVENANCE carries the FanDuel ids",
      "FanDuel event id:" in prov and "menu:" in prov)
bad = json.loads(bridge.depth_json(9999))
check("depth: out-of-range idx -> named error",
      bad.get("error") == "no_such_card")

# ---- 6. finds ----
finds = json.loads(bridge.finds_json())
total = (len(finds["golden"]) + len(finds["finds"])
         + len(finds["flagged"]) + len(finds["counter"]))
check("finds: golden+finds+flagged+counter partition the slate",
      total == 25, f"total={total} golden={len(finds['golden'])}")

# ---- 7. protected slip + mark ----
slip = json.loads(bridge.protected_slip_json())
if slip["legs"]:
    ssum = sum(l["stake_units"] for l in slip["legs"])
    check("slip: legs sized by kelly_advice; totals consistent",
          abs(ssum - slip["total_units"]) < 1e-9
          and slip["combined_decimal"] is not None
          and slip["combined_model_p"] is not None,
          f"legs={len(slip['legs'])} total={slip['total_units']:.1f}u")
    marked = json.loads(bridge.mark_placed_json())
    slips = json.loads(bridge.marked_slips_json())
    check("slip: mark-placed persists exactly one user-marked slip",
          marked.get("marked", {}).get("status")
          == "PLACED (user-marked)" and len(slips) == 1)
else:
    check("slip: no GOLDEN BET / BET HERE on the sample (honest "
          "empty)", slip["candidates"] == 0)

# ---- 8. lab ----
lab = json.loads(bridge.lab_json())
check("lab: engine 5.4 + recorder health + slate stats",
      lab["engine"]["engine_version"] == "5.4"
      and lab["recorder"]["history_begins"] == stamps[0]
      and lab["slate"]["priced"] == 18
      and "recording" in lab["recorder"]["health_line"])

# ---- 9. slate_json (the G5 label join source) ----
sj = json.loads(bridge.slate_json())
check("slate_json: events carry labels + market keys",
      sj["markets"] == 25 and len(sj["events"]) > 0
      and all("label" in e and "keys" in e for e in sj["events"]))

# ---- 10. network drives (best-effort; blockers recorded) ----
print("\n--- network drives (best-effort) ---")
try:
    t0 = datetime.now()
    payload = json.loads(bridge.build_and_run("[]"))
    dt = (datetime.now() - t0).total_seconds()
    check("NET pull: full FanDuel pull via build_and_run",
          payload["receipt"] is not None,
          f"{payload['receipt']} in {dt:.0f}s, "
          f"recorder={payload['recorder']}")
except Exception as e:
    print(f"[BLOCKED] NET pull: FanDuel not completable from this "
          f"VM — {type(e).__name__}: {e}")

try:
    live = json.loads(bridge.current_board_json())
    live_armed = [c for c in live["cards"]
                  if c["link_state"] == "armed"]
    check("NET board: fresh pull arms exact QuickSlip URLs",
          len(live_armed) > 0
          and all(url_shape_ok(c) for c in live_armed),
          f"armed={len(live_armed)} of {len(live['cards'])}")
    live_slip = json.loads(bridge.protected_slip_json())
    ssum = sum(l["stake_units"] for l in live_slip["legs"])
    check("NET slip: live GOLDEN/BET HERE legs sized + consistent",
          len(live_slip["legs"]) > 0
          and abs(ssum - live_slip["total_units"]) < 1e-9,
          f"legs={len(live_slip['legs'])} "
          f"total={live_slip['total_units']:.1f}u "
          f"golden={live_slip['any_golden']}")
    marked = json.loads(bridge.mark_placed_json())
    check("NET slip: mark-placed writes the user-marked slip",
          marked.get("marked", {}).get("status")
          == "PLACED (user-marked)")
    scoped = json.loads(bridge.build_and_run('["soccer"]'))
    season = hs.load_window(bridge._store_dir, "season",
                            datetime.now(hs.DETROIT))
    last = season["records"][-1]
    check("NET pull: scoped soccer pull merges + records ONLY "
          "its slice under its own stamp",
          scoped["scope"] == "sport:soccer"
          and last["pulled_at"] == scoped["pulled_at"]
          and len(last["markets"]) > 0
          and all(e["sport"] == "soccer"
                  for e in last["markets"]),
          f"records={len(season['records'])} "
          f"slice={len(last['markets'])} markets")
except Exception as e:
    print(f"[BLOCKED] NET board/slip/scoped: {type(e).__name__}: {e}")

try:
    bundle = bridge.fetch_stock_bundle(
        "MSTR", bridge.stock_history_fromdate())
    b5 = bridge._load_engine()
    view = b5.stock_quote_view(bundle)
    expiries = bundle["chain"]["expiries"]
    grid = b5.option_grid_view(
        expiries[0], view["spot_reference"],
        asof=bridge._stocks_asof(bundle).isoformat())
    check("NET stocks: Nasdaq bundle + engine views (MSTR)",
          view["spot_reference"] is not None
          and len(grid["rows"]) > 0,
          f"spot={view['spot_reference']} "
          f"expiries={len(expiries)} rows={len(grid['rows'])} "
          f"short_dated={grid['short_dated']}")
except Exception as e:
    print(f"[BLOCKED] NET stocks: Nasdaq not completable from "
          f"this VM — {type(e).__name__}: {e}")

failed = [n for n, ok in RESULTS if not ok]
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
sys.exit(1 if failed else 0)
