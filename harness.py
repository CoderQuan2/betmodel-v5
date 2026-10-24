#!/usr/bin/env python3
"""BetFi Xii harness — headless checks for the shell (main.py)
against the shipped engine + evidence pack.

Fresh for v11 (the 10.4.1 harness was builder-ephemeral and is
not on disk; this file replaces it, it does not extend it).
Covers: module import + version strings, F1 bet naming (unit +
rendered card order), F2 ledger structure on the shipped pack,
F3 switcher/skeleton/animate wiring, F4 in-place toggles, the
Room Rule states (populated + not-bundled), F5 engine fixtures
(golden boundary is asserted in the engine's own ADDENDUM
v5.3; here: threshold constant, CLV/Kelly spot values), parse
and parlay math, solver math, finds distillation, navigation
to all five destinations, and the golden panel's honesty on a
slate with no golden bet.

Run:  python harness.py            (exit 0 = all checks pass)
"""
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

STORAGE = tempfile.mkdtemp(prefix="betfixii-harness-")
os.environ["FLET_APP_STORAGE_DATA"] = STORAGE
MENU = os.path.join(HERE, "data", "menu-fanduel-20261019-1232.json")
with open(MENU) as f:
    _rec = json.load(f)
with open(os.path.join(STORAGE, "Bet_Finder-last-pull.json"),
          "w") as f:
    json.dump(_rec, f)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not ok else ""))


class FakePage:
    """The probe-page convention: run_thread inline (workers
    complete synchronously), run_task closes coroutines."""

    def __init__(self):
        self.controls = []
        self.navigation_bar = None
        self.services = []
        self.title = None
        self.bgcolor = None
        self.theme_mode = None
        self.padding = None
        self.spacing = None
        self.scroll = None
        self.updates = 0

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self, *args, **kwargs):
        self.updates += 1

    def run_thread(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def run_task(self, fn, *args, **kwargs):
        out = fn(*args, **kwargs)
        if asyncio.iscoroutine(out):
            out.close()
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


def texts(ctrl):
    out = []
    for c in walk(ctrl):
        v = getattr(c, "value", None)
        if isinstance(v, str) and v:
            out.append(v)
        for span in getattr(c, "spans", None) or []:
            t = getattr(span, "text", None)
            if t:
                out.append(t)
    return out


def main():
    import flet as ft
    import main as app
    import betmodel5 as b5

    # ---------- identity ----------
    check("APP_VERSION is 12.0.0", app.APP_VERSION == "12.0.0")
    check("BUILD_NUMBER is 16", app.BUILD_NUMBER == 16)
    check("DISPLAY_NAME is BetFi Xii",
          app.DISPLAY_NAME == "BetFi Xii")
    check("PUBLIC_NAME is BetFi_Xii",
          app.PUBLIC_NAME == "BetFi_Xii")
    check("INTERNAL_ID unchanged (storage carries over)",
          app.INTERNAL_ID == "Bet_Finder")
    check("engine is v5.4", b5.ENGINE_VERSION == "5.4")
    check("GOLDEN threshold constant is +2.0 (F5a)",
          b5.GOLDEN_THRESHOLD_PTS == 2.0)
    lab_engine = os.path.join(HERE, "..", "..", "scripts",
                              "betmodel5.py")
    if os.path.exists(lab_engine):
        h = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()
        check("one-engine law: clone engine == lab engine",
              h(os.path.join(HERE, "betmodel5.py")) == h(lab_engine))

    # ---------- F1 naming (unit) ----------
    ml = {"sport": "nfl", "market": "moneyline", "side": "home",
          "home": "DET", "away": "GB", "price": -150}
    check("fd name: NFL moneyline is 'Moneyline'",
          app.fd_market_name(ml) == "Moneyline")
    check("fd name: NFL spread is 'Point Spread'",
          app.fd_market_name({**ml, "market": "spread"})
          == "Point Spread")
    check("fd name: NFL total is 'Total Points'",
          app.fd_market_name({**ml, "market": "totals"})
          == "Total Points")
    soc = {"sport": "soccer", "market": "moneyline",
           "side": "draw", "home": "Arsenal", "away": "Chelsea",
           "price": 240}
    check("fd name: soccer moneyline is 'Moneyline (3-way)'",
          app.fd_market_name(soc) == "Moneyline (3-way)")
    check("selection: soccer draw reads 'Draw'",
          app.selection_words(soc) == "Draw")
    tot = {"sport": "nfl", "market": "totals", "side": "over",
           "line": 47.5, "home": "DET", "away": "GB",
           "price": -110}
    check("selection: total reads 'Over 47.5 total points'",
          app.selection_words(tot) == "Over 47.5 total points")
    spr = {"sport": "nfl", "market": "spread", "side": "home",
           "line": -3.5, "home": "DET", "away": "GB",
           "price": -110}
    check("selection: spread names the full team + signed line",
          app.selection_words(spr) == "Detroit Lions −3.5")
    prop = {"sport": "nfl", "market": "player-props",
            "player": "Jared Goff", "stat": "passingYards",
            "side": "over", "line": 249.5, "home": "DET",
            "away": "GB", "price": -114}
    nm = app.bet_name(prop)
    check("F1: a prop leads with the player",
          nm["headline"] == "Jared Goff")
    check("F1: prop selection is plain words",
          nm["selection"] == "Over 249.5 passing yards")
    check("F1: slip label carries selection + price + market",
          nm["slip_label"].startswith("Over 249.5 passing yards")
          and "(-114)" in nm["slip_label"])
    check("F1: FanDuel path is a navigation path",
          nm["fd_path"].startswith("FanDuel → NFL")
          and "Player Props" in nm["fd_path"])
    nm_ml = app.bet_name(ml)
    check("F1: a moneyline leads with the market name",
          nm_ml["headline"] == "Moneyline"
          and nm_ml["selection"] == "Detroit Lions")
    check("skeletons render (F3)", len(app.skeleton_cards()) == 3)

    # clipboard copy must never raise (F1)
    try:
        app.bind_clipboard(None)
        ev = SimpleNamespace(
            page=FakePage(),
            control=SimpleNamespace(icon=None, update=lambda: None))
        app._copy_label(ev, "Detroit Lions (-150) · Moneyline")
        clip_ok = True
    except Exception:
        clip_ok = False
    check("copy-label handler is safe without a service", clip_ok)

    # ---------- F5 engine spot fixtures ----------
    check("CLV fixture: -110 into -130 close = +4.14 pts",
          abs(b5.clv_points(-110, -130) - 4.14) < 0.01)
    k = b5.kelly_advice(0.60, -110, bankroll=1000)
    check("Kelly fixture: p .60 @ -110 advises 2.0u / $20",
          k["state"] == "ADVISORY"
          and abs(k["stake_units"] - 2.0) < 1e-6
          and abs(k["stake_dollars"] - 20.0) < 1e-6)
    rep = b5.clv_report([_rec])
    check("CLV on the shipped pull: insufficient snapshots, "
          "honestly", rep["drift"]["markets_tracked"] == 0
          and rep["drift"]["markets_seen"] > 300)

    # ---------- parse / parlay / solver math ----------
    p1 = app.parse_slip_text("Lions -3.5 (-110)")
    check("parse: spread line reads",
          p1 and p1["market"] == "spread" and p1["line"] == -3.5)
    p2 = app.parse_slip_text("garbage text with no bet")
    check("parse: garbage is refused, not guessed", p2 is None)
    leg_a = ({"sport": "nfl", "market": "moneyline",
              "side": "home", "home": "DET", "away": "GB",
              "price": -110},
             {"state": "PRICED", "p": 0.6, "grade": "B"})
    leg_b = ({"sport": "nfl", "market": "moneyline",
              "side": "home", "home": "KC", "away": "BUF",
              "price": -110},
             {"state": "PRICED", "p": 0.6, "grade": "A"})
    comb = app.parlay_combine([leg_a, leg_b])
    check("parlay: two -110 legs combine to +264",
          comb["american"] == 264
          and abs(comb["model_p"] - 0.36) < 1e-9)
    check("parlay: combined grade caps at the weakest leg",
          comb["grade"] == "B")
    comb_sg = app.parlay_combine([leg_a, leg_a])
    check("parlay: same-game is stamped, not priced",
          comb_sg["same_game"] is True)
    check("solver: profit target sizes the stake",
          abs(app.solver_stake_for_profit(100, -110) - 110.0)
          < 1e-6)
    hg = app.solver_hedge(100, -110, 120)
    check("solver: hedge math returns the other side",
          abs(hg["hedge_stake"] - 86.78) < 0.01
          and "guaranteed" in hg)

    # ---------- boot the app on the shipped pull ----------
    page = FakePage()
    app.main(page)
    check("app boots headless", len(page.controls) >= 2)
    check("a clipboard service is registered (F1)",
          any(type(s).__name__ == "Clipboard"
              for s in page.services))
    switcher = page.controls[1]
    check("top-level view host is an AnimatedSwitcher (F3)",
          type(switcher).__name__ == "AnimatedSwitcher"
          and switcher.duration == 220)
    board = switcher.content
    board_sw = [c for c in walk(board)
                if type(c).__name__ == "AnimatedSwitcher"]
    check("board segment host is an AnimatedSwitcher (F3)",
          len(board_sw) == 1)
    cards_view = board_sw[0].content
    all_texts = texts(cards_view)
    check("board renders market cards",
          any("Find it:" in t for t in all_texts))
    card = next(c for c in walk(cards_view)
                if any("Find it:" in t for t in texts(c))
                and type(c).__name__ == "Container")
    ct = texts(card)
    i_path = next(i for i, t in enumerate(ct) if "Find it:" in t)
    check("F1 order: market/selection print above the FD path",
          i_path >= 3 and any(t in ("Moneyline", "Point Spread",
                                    "Total Points")
                              for t in ct[:i_path]))
    check("F1: card carries a FanDuel navigation path",
          any(t.startswith("FanDuel → ") for t in ct))
    check("F3: cards cast the depth shadow",
          getattr(card, "shadow", None) is not None)
    check("F3: first render animated in (opacity restored)",
          getattr(card, "opacity", 1) == 1
          and getattr(card, "animate_opacity", None) is not None)

    # finds segment: the golden panel is honest on this slate
    seg = next(c for c in walk(board)
               if type(c).__name__ == "SegmentedButton")
    seg.on_change(SimpleNamespace(
        control=SimpleNamespace(selected={"finds"})))
    finds_texts = texts(board_sw[0].content)
    check("golden panel honest: no GOLDEN on this pull, "
          "printed as such",
          any("No golden bets on this pull" in t
              for t in finds_texts))
    seg.on_change(SimpleNamespace(
        control=SimpleNamespace(selected={"all"})))

    # toggles are NOT rebuilt across re-renders (F4 in-place)
    tog_row = next(c for c in walk(cards_view)
                   if type(c).__name__ == "Row"
                   and any(type(x).__name__ == "Switch"
                           for x in getattr(c, "controls", [])))
    page.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=2)))   # Lab
    page.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=0)))   # Board
    tog_row2 = next(c for c in walk(cards_view)
                    if type(c).__name__ == "Row"
                    and any(type(x).__name__ == "Switch"
                            for x in getattr(c, "controls", [])))
    check("F4: toggle row survives re-renders (same object)",
          tog_row is tog_row2)

    # ---------- Lab: ledger structure on the shipped pack ----
    page.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=2)))
    lab = switcher.content
    lt = texts(lab)
    check("Lab is populated from the bundled pack (Room Rule)",
          any("LAB CARD" in t for t in lt)
          and not any("record not bundled" in t for t in lt))
    check("F2: ledger column header prints",
          all(any(t == h for t in lt)
              for h in ("DATE", "BET", "ODDS", "GRADE",
                        "RESULT", "P/L")))
    check("F2: Pilot Book header carries its own totals",
          any("PILOT BOOK" in t for t in lt)
          and any("Closed line" in t for t in lt))
    check("F2: books are never merged (the sentence stands)",
          any("never added together" in t for t in lt))
    check("F2: pilot tickets render as ledger rows",
          any("Florida" in t for t in lt)
          and any(t == "WON" for t in lt)
          and any(t == "PENDING" for t in lt))
    check("F2: Lab Card aggregate row is not pill-washed",
          any("Clean Saturday Slate" in t for t in lt)
          and any(t == "3-3" for t in lt))
    check("F2: result pills exist for settled states",
          any(type(c).__name__ == "Container"
              and getattr(c, "bgcolor", None) == "#065F46"
              for c in walk(lab)))
    check("F5b: CLV section prints its honest state",
          any("CLV & DRIFT" in t for t in lt)
          and any("insufficient snapshots" in t for t in lt))
    check("lane ledger renders zebra rows",
          any("nfl-ml" in t for t in lt))

    # ---------- Slip / Stage / More destinations ----------
    page.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=1)))
    slip = switcher.content
    slip_sw = [c for c in walk(slip)
               if type(c).__name__ == "AnimatedSwitcher"]
    check("slip tool host is an AnimatedSwitcher (F3)",
          len(slip_sw) == 1)
    seg2 = next(c for c in walk(slip)
                if type(c).__name__ == "SegmentedButton")
    seg2.on_change(SimpleNamespace(
        control=SimpleNamespace(selected={"parlay"})))
    pt = texts(slip_sw[0].content)
    check("parlay face carries the bankroll field (F5b)",
          any("Bankroll" in t for t in pt)
          or any("Bankroll" in (getattr(c, "label", "") or "")
                 for c in walk(slip_sw[0].content)))
    check("parlay empty state is honest",
          any("No legs yet" in t for t in pt))
    page.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=3)))
    stage_texts = texts(switcher.content)
    check("3D stage renders the instrument library",
          any("instrument" in t.lower() for t in stage_texts))
    page.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=4)))
    more_texts = texts(switcher.content)
    check("More renders; the header carries BetFi Xii / v5.4",
          len(switcher.content.controls) >= 5
          and any("BetFi Xii" in t
                  for t in texts(page.controls[0]))
          and any("v5.4" in t
                  for t in texts(page.controls[0])))

    # Room Rule strings in the source (all three UI surfaces)
    src = open(os.path.join(HERE, "main.py")).read()
    check("Room Rule phrase present in source",
          src.count("record not bundled") >= 3,
          f"count={src.count('record not bundled')}")

    # ---------- the not-bundled state (Room Rule failure) ----
    import shutil
    empty_dir = tempfile.mkdtemp(prefix="betfi11-nopack-")
    # warm engine caches, but NO lab_export.json anywhere:
    # the Room Rule's failure state, reached honestly
    shutil.copytree(os.path.join(HERE, "data"), empty_dir,
                    dirs_exist_ok=True)
    os.remove(os.path.join(empty_dir, "lab_export.json"))
    saved = (app.BUNDLED_DATA_DIR, b5.DATA)
    app.BUNDLED_DATA_DIR = empty_dir
    b5.DATA = empty_dir
    try:
        page2 = FakePage()
        app.main(page2)
        sw2 = page2.controls[1]
        page2.navigation_bar.on_change(SimpleNamespace(
            control=SimpleNamespace(selected_index=2)))
        lt2 = texts(sw2.content)
        check("no pack anywhere: Lab prints 'record not "
              "bundled', never a 0-0",
              any("not bundled" in t.lower() for t in lt2)
              and not any("LAB CARD" in t for t in lt2))
    finally:
        app.BUNDLED_DATA_DIR, b5.DATA = saved

    # ---------- v12 / BetFi Xii ----------
    reg = b5.universal_registry()
    leagues = {(e["sport"], e["league"]) for e in reg}
    check("Xii registry: soccer/epl registered",
          ("soccer", "epl") in leagues)
    check("Xii registry: serie a registered (leagues file)",
          ("soccer", "serie-a") in leagues,
          f"leagues={sorted(leagues)}")
    check("Xii registry: backtest carried verbatim",
          any(e["league"] == "epl"
              and (e["backtest"] or {}).get("brier3") == 0.6302
              for e in reg))
    cov = b5.universal_coverage([
        {"sport": "soccer", "home": "Inter", "away": "Fiorentina",
         "market": "moneyline", "side": "home", "price": -145},
        {"sport": "soccer", "home": "Inter", "away": "FC Nowhere",
         "market": "moneyline", "side": "home", "price": -145},
        {"sport": "nfl", "home": "DET", "away": "GB",
         "market": "moneyline", "side": "home", "price": -150},
        {"sport": "nfl", "home": "DET", "away": "GB",
         "market": "totals", "side": "over", "line": 47.5,
         "price": -110},
        {"sport": "mlb", "home": "DET", "away": "NYY",
         "market": "moneyline", "side": "home", "price": -110}])
    soc_cov = next(c for c in cov if c["sport"] == "soccer"
                   and c["bet_type"] == "moneyline")
    mlb_cov = next(c for c in cov if c["sport"] == "mlb")
    nfl_ml = next(c for c in cov if c["sport"] == "nfl"
                  and c["bet_type"] == "moneyline")
    nfl_tot = next(c for c in cov if c["sport"] == "nfl"
                   and c["bet_type"] == "totals")
    check("Xii coverage: Serie A fixture is PRICED-capable",
          soc_cov["priced_capable"] == 1
          and soc_cov["league"] == "serie-a")
    check("Xii coverage: missing fit is named per bet type",
          any("team not in the soccer fit: FC Nowhere" in m
              for m in soc_cov["missing"])
          and any("no fit registered for league mlb" in m
                  for m in mlb_cov["missing"]))
    check("Xii coverage: bet-type grain — NFL moneyline capable "
          "while NFL totals stamps its missing distribution",
          nfl_ml["priced_capable"] == 1
          and nfl_tot["unpriced"] == 1
          and any("no totals distribution" in m
                  for m in nfl_tot["missing"]))
    _fams = {(e["sport"]) for e in reg}
    check("Xii registry: every lane family present with its "
          "specialized math + bet types",
          {"nfl", "ncaaf", "nba", "nhl", "soccer", "props",
           "live"} <= _fams
          and all(any(e.get("bet_types") for e in reg
                      if e["sport"] == s)
                  for s in ("nfl", "nba", "nhl", "soccer")))
    check("Xii copy mechanic: a name copies alone",
          app.copy_name("  Inter ") == "Inter"
          and app.copy_name("Josh Allen") == "Josh Allen")
    check("Xii auto-pull: interval constant is 4 minutes",
          app.AUTO_PULL_INTERVAL_S == 4 * 60)
    check("Xii charts: empty pull builds honest controls",
          len(app.build_xii_charts([])) >= 2
          and any("No pull yet" in t
                  for t in texts(app.build_xii_charts([])[-1])))
    _entries = [
        ({"sport": "nfl", "market": "moneyline", "side": "home",
          "home": "DET", "away": "GB", "price": -110},
         {"state": "PRICED", "p": 0.62, "grade": "A"}, 6.0),
        ({"sport": "soccer", "market": "moneyline", "side": "home",
          "home": "Inter", "away": "Fiorentina", "price": -145},
         {"state": "UNPRICED", "p": None, "grade": None}, None)]
    _charts = app.build_xii_charts(_entries, on_tap=lambda d: None,
                                   on_zoom=lambda f: None)
    _ct = []
    for _c in _charts:
        _ct += texts(_c)
    check("Xii charts: priced + unpriced render from a pull",
          any("EDGE DISTRIBUTION" in t for t in _ct)
          and any("PRICED vs UNPRICED" in t for t in _ct))
    check("Xii ICE: splash + pulse + button-weight constants",
          app.PULSE_PERIODS["dot"] == 2.0
          and app.PULSE_PERIODS["golden"] == 2.8
          and app.BTN_PRIMARY_HEIGHT == 52
          and callable(app.build_splash)
          and callable(app.ice_pulse_loop)
          and app.primary_button("x", lambda e: None).height == 52)
    _src = open(os.path.join(HERE, "main.py")).read()
    check("Xii law: no ft.Slider anywhere in main.py",
          "ft.Slider" not in _src and "Slider(" not in _src)
    check("Xii fit cache: load_soccer returns the cached object",
          b5.load_soccer() is b5.load_soccer())
    check("Xii: EPL spot price unchanged (LIV v ARS home)",
          abs(b5.engine_price("soccer", "moneyline", "LIV", "ARS",
                              side="home")[0]
              - 0.2538531567386233) < 1e-12)
    check("Xii: Serie A prices off the leagues fit",
          b5.engine_price("soccer", "moneyline", "Inter",
                          "Fiorentina", side="home")[0] is not None)

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks "
          f"passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
