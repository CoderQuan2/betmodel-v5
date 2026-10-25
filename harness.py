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
    check("APP_VERSION is 12.1.0", app.APP_VERSION == "12.1.0")
    check("BUILD_NUMBER is 17", app.BUILD_NUMBER == 17)
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
          and switcher.duration == 260)
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
        {"sport": "nhl", "home": "Boston Bruins",
         "away": "Toronto Maple Leafs", "market": "totals",
         "side": "over", "line": 5.5, "price": -110},
        {"sport": "mlb", "home": "DET", "away": "NYY",
         "market": "moneyline", "side": "home", "price": -110}])
    soc_cov = next(c for c in cov if c["sport"] == "soccer"
                   and c["bet_type"] == "moneyline")
    mlb_cov = next(c for c in cov if c["sport"] == "mlb")
    nfl_ml = next(c for c in cov if c["sport"] == "nfl"
                  and c["bet_type"] == "moneyline")
    nfl_tot = next(c for c in cov if c["sport"] == "nfl"
                   and c["bet_type"] == "totals")
    nhl_tot = next(c for c in cov if c["sport"] == "nhl"
                   and c["bet_type"] == "totals")
    check("Xii coverage: Serie A fixture is PRICED-capable",
          soc_cov["priced_capable"] == 1
          and soc_cov["league"] == "serie-a")
    check("Xii coverage: missing fit is named per bet type",
          any("team not in the soccer fit: FC Nowhere" in m
              for m in soc_cov["missing"]))
    check("R2 coverage: MLB moneyline is PRICED-capable off "
          "the fitted lane (v5-mlb.json, walk-forward passed)",
          mlb_cov["priced_capable"] == 1
          and ("mlb", "mlb") in leagues,
          f"mlb_cov={mlb_cov}")
    # R5 DISCLOSURE: this check asserted NFL totals stamps
    # "no totals distribution". R5 wired the totals lanes
    # (the fitted distributions, Glow's fits) into this tree
    # for straight AND alt totals, so the truth flipped:
    # NFL totals is now PRICED-capable in coverage too, and
    # the check asserts the new truth.
    check("R5 coverage: bet-type grain — NFL moneyline AND "
          "NFL totals both PRICED-capable (totals lane wired)",
          nfl_ml["priced_capable"] == 1
          and nfl_tot["priced_capable"] == 1,
          f"nfl_tot={nfl_tot}")
    # ---------- R2 (fix-guy): pull expansion + NFL spreads ----------
    inv = b5.sport_inventory()
    check("R2 inventory: all 17 tree sports pulled (NOT-PULLED "
          "bucket closed)",
          len(inv) == 17 and all(r["pulled"] for r in inv),
          f"unpulled={[r['name'] for r in inv if not r['pulled']]}")
    cov2 = b5.universal_coverage([
        {"sport": "golf", "home": "A Player", "away": "B Player",
         "market": "moneyline", "side": "home", "price": -110},
        {"sport": "boxing", "home": "Fighter A", "away": "Fighter B",
         "market": "moneyline", "side": "home", "price": -110}])
    # R5 DISCLOSURE: the R2 wording expected the bare
    # "no checker registered for" reason. R4 deliberately
    # replaced that bare reason for golf/boxing with NAMED
    # source terminals in both layers (BoxRec/DataGolf
    # gated), so the stale expectation failed on R4's own
    # design; the check now asserts the current truth —
    # named terminals, never NOT-PULLED rows.
    check("R2/R4 coverage: pulled-but-unchecked sports stamp "
          "their named source terminals, never NOT-PULLED rows",
          all(c["unpriced"] == 1 and any(
              "source" in m for m in c["missing"]) for c in cov2
              if c["bet_type"] == "moneyline")
          and not any(c.get("not_pulled") for c in cov2))
    # ---------- R3 (fix-guy): head-to-head lanes ----------
    check("R3 registry: tennis tours + mma registered",
          ("tennis", "atp") in leagues
          and ("tennis", "wta") in leagues
          and ("mma", "ufc") in leagues,
          f"leagues={sorted(leagues)}")
    _tp, _ti = b5.engine_price("tennis", "moneyline",
                               "Novak Djokovic", "Carlos Alcaraz",
                               side="home")
    check("R3 tennis: ATP moneyline prices off the fitted Elo",
          _tp is not None and 0 < _tp < 1
          and "Tennis Elo lane (ATP" in _ti.get("detail", ""),
          f"p={_tp} info={_ti}")
    _wp, _wi = b5.engine_price("tennis", "moneyline",
                               "Iga Swiatek", "Aryna Sabalenka",
                               side="home")
    check("R3 tennis: WTA moneyline prices (archive name form "
          "resolved)", _wp is not None and 0 < _wp < 1
          and "WTA" in _wi.get("detail", ""), f"p={_wp}")
    _np, _ni = b5.engine_price("tennis", "moneyline",
                               "A Player", "B Player", side="home")
    check("R3 tennis: unknown player names themselves",
          _np is None and "player not in the tennis fit" in _ni,
          f"{_np} {_ni}")
    _mp, _mi = b5.engine_price("mma", "moneyline",
                               "Charles Oliveira", "Diego Lopes",
                               side="home")
    check("R3 mma: lane ships FAILED-EXAM with its numbers "
          "(walk-forward did not beat naive — does not price)",
          _mp is None and "FAILED-EXAM" in _mi
          and "0.2454" in _mi and "0.2451" in _mi,
          f"{_mp} {_mi}")
    cov3 = b5.universal_coverage([
        {"sport": "tennis", "home": "Novak Djokovic",
         "away": "Carlos Alcaraz", "market": "moneyline",
         "side": "home", "price": -110},
        {"sport": "mma", "home": "Charles Oliveira",
         "away": "Diego Lopes", "market": "moneyline",
         "side": "home", "price": -110},
        {"sport": "table-tennis", "home": "A B", "away": "C D",
         "market": "moneyline", "side": "home", "price": -110}])
    _tc = next(c for c in cov3 if c["sport"] == "tennis")
    _mc = next(c for c in cov3 if c["sport"] == "mma")
    _ttc = next(c for c in cov3 if c["sport"] == "table-tennis")
    check("R3 coverage: tennis capable, mma FAILED-EXAM, table "
          "tennis still named-unchecked (checker == coverage)",
          _tc["priced_capable"] == 1
          and _mc["unpriced"] == 1
          and any("FAILED-EXAM" in m for m in _mc["missing"])
          and any("no checker registered for table-tennis" in m
                  for m in _ttc["missing"]),
          f"ten={_tc} mma={_mc} tt={_ttc}")
    check("R3 preservation: R1 CFB spread value byte-identical "
          "(Georgia -6.5 home)",
          abs(b5.engine_price("ncaaf", "spread", "Georgia",
                              "Alabama", side="home", line=-6.5)[0]
              - 0.5456033345497181) < 1e-12)
    check("R3 preservation: R2 MLB price byte-identical "
          "(Dodgers v Jays home)",
          abs(b5.engine_price("mlb", "moneyline",
                              "Los Angeles Dodgers",
                              "Toronto Blue Jays", side="home")[0]
              - 0.5215733330511455) < 1e-12)
    # ---------- R4 (fix-guy): team-sport remainder ----------
    check("R4 registry: cricket lanes + rugby + f1 registered",
          ("cricket", "t20i_m") in leagues
          and ("cricket", "test_m") in leagues
          and ("rugby-union", "npc") in leagues
          and ("rugby-league", "intl_m") in leagues
          and ("motorsport", "f1") in leagues,
          f"leagues={sorted(leagues)}")
    _cp, _ci = b5.engine_price(
        "cricket", "moneyline", "New Zealand", "India",
        side="home", competition="International Twenty20 Matches")
    check("R4 cricket: T20I moneyline prices off the fitted Elo",
          _cp is not None and 0 < _cp < 1
          and "t20i_m" in _ci.get("detail", ""), f"p={_cp}")
    _dp, _di = b5.engine_price(
        "cricket", "moneyline", "South Africa", "Australia",
        side="draw", competition="Test Matches")
    _test_blk = (b5.load_cricket().get("lanes") or {})["test_m"]
    check("R4 cricket: the Test Draw runner prices from the "
          "lane's fitted draw rate",
          _dp is not None
          and abs(_dp - _test_blk["draw_rate"]) < 1e-9,
          f"p={_dp} rate={_test_blk.get('draw_rate')}")
    _lp, _li = b5.engine_price(
        "cricket", "moneyline", "Denmark", "Papua New Guinea",
        side="home",
        competition="ICC Cricket World Cup Challenge League")
    check("R4 cricket: Challenge League lane ships FAILED-EXAM "
          "with its numbers (does not price)",
          _lp is None and "FAILED-EXAM" in _li
          and "0.2253" in _li and "0.2234" in _li, f"{_li}")
    _rp, _ri = b5.engine_price(
        "rugby-union", "spread", "Canterbury", "Northland",
        side="home", line=-6.5, competition="New Zealand - NPC")
    check("R4 rugby union: NPC spread prices off the margin map",
          _rp is not None and 0 < _rp < 1
          and "margin map" in _ri.get("detail", ""), f"p={_rp}")
    _gp, _gi = b5.engine_price(
        "rugby-league", "moneyline", "Australia", "Fiji",
        side="home", competition="World Cup - Men")
    check("R4 rugby league: international lane ships "
          "FAILED-EXAM with its numbers (does not price)",
          _gp is None and "FAILED-EXAM" in _gi
          and "0.2392" in _gi and "0.2308" in _gi, f"{_gi}")
    _bp, _bi = b5.engine_price("boxing", "moneyline", "Alvarez",
                               "Mbilli", side="home")
    check("R4 boxing: named source terminal (BoxRec gated), "
          "no toy-data Elo",
          _bp is None and "BoxRec" in _bi and "403" in _bi,
          f"{_bi}")
    # R4 competition truth: checker and coverage print the SAME
    # competition stamp for WNBA/NBL markets filed under "nba".
    _ctxv = {"verified": True}
    _wn = {"sport": "nba", "home": "Golden State Valkyries",
           "away": "Atlanta Dream", "market": "moneyline",
           "side": "home", "price": 120}
    _wn_chk = b5.run_checker(_wn, _ctxv)
    _wn_cov = next(c for c in b5.universal_coverage([_wn])
                   if c["sport"] == "nba")
    _wp_chk = b5.run_checker(
        {**_wn, "market": "player-props",
         "player": "Kayla Thornton", "stat": "points",
         "side": "over", "line": 12.5}, _ctxv)
    _nbl = {"sport": "nba", "home": "Cairns Taipans",
            "away": "New Zealand Breakers",
            "market": "team-props", "team": "home",
            "side": "over", "line": 85.5, "price": -110}
    _nbl_chk = b5.run_checker(_nbl, _ctxv)
    _nbl_cov = next(c for c in b5.universal_coverage([_nbl])
                    if c["sport"] == "nba")
    check("R4 competition truth: WNBA moneyline + WNBA prop + "
          "NBL team total name their real competitions in BOTH "
          "layers",
          "WNBA" in _wn_chk["note"]
          and any("WNBA" in m for m in _wn_cov["missing"])
          and "WNBA" in _wp_chk["note"]
          and "NBL (Australia)" in _nbl_chk["note"]
          and any("NBL (Australia)" in m
                  for m in _nbl_cov["missing"]),
          f"{_wn_chk['note']} || {_nbl_chk['note']}")
    # R4 MLB alignment: checker state == coverage priced_capable
    # on codes, full names, a spread, and an NPB fixture — the
    # shared mlb_lane_gate/mlb_membership make them agree.
    _mlb_cases = [
        {"sport": "mlb", "home": "DET", "away": "NYY",
         "market": "moneyline", "side": "home", "price": 120},
        {"sport": "mlb", "home": "Detroit Tigers",
         "away": "New York Yankees", "market": "moneyline",
         "side": "home", "price": 120},
        {"sport": "mlb", "home": "Detroit Tigers",
         "away": "New York Yankees", "market": "spread",
         "side": "home", "line": 1.5, "price": 120},
        {"sport": "mlb", "home": "Yokohama Dena Baystars",
         "away": "Fukuoka Hawks", "market": "moneyline",
         "side": "home", "price": 152}]
    _agree = True
    _npb_named = True
    for _m in _mlb_cases:
        _st = b5.run_checker(_m, _ctxv)["state"]
        _cell = next(c for c in b5.universal_coverage([_m])
                     if c["sport"] == "mlb")
        if (_st == "PRICED") != (_cell["priced_capable"] == 1):
            _agree = False
    _npb_chk = b5.run_checker(_mlb_cases[3], _ctxv)
    _npb_cov = next(c for c in b5.universal_coverage(
        [_mlb_cases[3]]) if c["sport"] == "mlb")
    _npb_named = ("NPB (Japan)" in _npb_chk["note"]
                  and any("NPB (Japan)" in m
                          for m in _npb_cov["missing"]))
    check("R4 MLB alignment: checker and coverage agree on "
          "every case (shared resolver), NPB named in both",
          _agree and _npb_named, f"agree={_agree}")
    # R4 athlete index: a non-legacy player resolves + prices
    # from the bundled cache layout (the pack the seeder ships).
    _old_cache = b5.CACHE
    b5.CACHE = os.path.join(HERE, "data", "cache")
    b5._FIT_CACHE.clear()
    try:
        _series = b5.gamelog_series_cached("Jalen Green",
                                           "points")
        _band = b5.prop_band("Jalen Green", "points", 19.5,
                             "over")
        _idx_ok = len(_series) >= 10 and _band is not None
    except Exception as _e:  # noqa: BLE001
        _idx_ok = False
        _series, _band = [], str(_e)
    finally:
        b5.CACHE = _old_cache
        b5._FIT_CACHE.clear()
    check("R4 props: non-legacy player (Jalen Green) resolves "
          "via the athlete index and prices from the cache",
          _idx_ok, f"series={len(_series) if isinstance(_series, list) else _series}")
    _fut = b5.run_checker(
        {"sport": "golf", "home": "Butterfield Bermuda "
         "Championship", "away": "Group A", "market": "futures",
         "side": "home", "price": None}, _ctxv)
    _f1f = b5.run_checker(
        {"sport": "motorsport", "home": "United States Grand "
         "Prix", "away": "Race Winner", "market": "futures",
         "side": "home", "price": None}, _ctxv)
    check("R4 futures terminals: golf names the gated source, "
          "F1 names its FAILED-EXAM",
          "DataGolf" in _fut["note"]
          and "FAILED-EXAM" in _f1f["note"]
          and "2.5036" in _f1f["note"],
          f"{_fut['note'][:60]} || {_f1f['note'][:60]}")
    # ---------- R5 (fix-guy): alt lines, segments, F1 refit,
    # soccer outrights ----------
    _alt_a = b5.run_checker(
        {"sport": "nfl", "home": "GB", "away": "DAL",
         "market": "spread", "side": "home", "line": -3.5,
         "price": -110}, _ctxv)
    _alt_b = b5.run_checker(
        {"sport": "nfl", "home": "GB", "away": "DAL",
         "market": "alt-spread", "side": "home", "line": -3.5,
         "price": -110}, _ctxv)
    _alt_c = b5.run_checker(
        {"sport": "nfl", "home": "GB", "away": "DAL",
         "market": "totals", "side": "over", "line": 47.5,
         "price": -110}, _ctxv)
    _alt_d = b5.run_checker(
        {"sport": "nfl", "home": "GB", "away": "DAL",
         "market": "alt-total", "side": "over", "line": 47.5,
         "price": -110}, _ctxv)
    check("R5 alt parity: at the main line the alt form's "
          "price equals the straight form's exactly (spread "
          "and total)",
          _alt_a["state"] == _alt_b["state"] == "PRICED"
          and abs(_alt_a["p"] - _alt_b["p"]) <= 1e-9
          and _alt_c["state"] == _alt_d["state"] == "PRICED"
          and abs(_alt_c["p"] - _alt_d["p"]) <= 1e-9,
          f"{_alt_a['p']} vs {_alt_b['p']}; "
          f"{_alt_c['p']} vs {_alt_d['p']}")
    _nhl_alt = b5.run_checker(
        {"sport": "nhl", "home": "EDM", "away": "COL",
         "market": "alt-total", "side": "over", "line": 6.5,
         "price": -110}, _ctxv)
    check("R5 totals: NHL alt-total stamps the lane's "
          "FAILED-EXAM with its numbers (never prices)",
          _nhl_alt["state"] == "UNPRICED"
          and "FAILED-EXAM" in _nhl_alt["note"]
          and "0.2626" in _nhl_alt["note"],
          f"{_nhl_alt['note'][:80]}")
    _seg_nfl = b5.run_checker(
        {"sport": "nfl", "home": "GB", "away": "DAL",
         "market": "segment", "segment": "1st half"}, _ctxv)
    _seg_ll = b5.run_checker(
        {"sport": "soccer", "home": "Real Madrid",
         "away": "Getafe", "market": "segment",
         "segment": "1st half", "side": "over", "line": 1.5,
         "price": -110}, _ctxv)
    _seg_epl = b5.run_checker(
        {"sport": "soccer", "home": "LIV", "away": "ARS",
         "market": "segment", "segment": "1st half",
         "side": "over", "line": 1.5, "price": -110}, _ctxv)
    check("R5 segments: NFL 1H stamps FAILED-EXAM with its "
          "numbers; La Liga 1H prices off the half-share "
          "grid; EPL 1H total stamps FAILED-EXAM",
          _seg_nfl["state"] == "UNPRICED"
          and "FAILED-EXAM" in _seg_nfl["note"]
          and "7.461" in _seg_nfl["note"]
          and _seg_ll["state"] == "PRICED"
          and _seg_epl["state"] == "UNPRICED"
          and "FAILED-EXAM" in _seg_epl["note"],
          f"{_seg_nfl['note'][:60]} || {_seg_ll['state']} || "
          f"{_seg_epl['note'][:60]}")
    _out = b5.run_checker(
        {"sport": "soccer", "home": "Arsenal", "away": "x",
         "market": "futures", "competition": "Premier League",
         "runner": "Arsenal", "price": 250}, _ctxv)
    _out_doc = b5.load_outrights() or {}
    _ars = ((_out_doc.get("leagues") or {}).get("epl")
            or {}).get("shares", {}).get("ARS")
    check("R5 futures: an EPL outright selection prices at "
          "the simulated title share on file",
          _out["state"] == "PRICED" and _ars is not None
          and abs(_out["p"] - _ars) < 1e-9,
          f"{_out['state']} p={_out['p']} file={_ars}")
    check("R5 futures: the F1 stamp chain carries BOTH "
          "attempts' numbers (terminal FAILED-EXAM)",
          "2.5036" in _f1f["note"] and "2.2126" in _f1f["note"]
          and "TERMINAL" in _f1f["note"],
          f"{_f1f['note'][:100]}")
    _epl_reg = next(e for e in reg if e["sport"] == "soccer"
                    and e["league"] == "epl")
    _nba_reg = next(e for e in reg if e["sport"] == "nba")
    check("R5 registry: EPL futures PRICED-capable (pilot "
          "PASS), NBA segment FAILED-EXAM with numbers",
          "PRICED-capable" in _epl_reg["bet_types"].get(
              "futures", "")
          and "FAILED-EXAM" in _nba_reg["bet_types"].get(
              "segment", ""),
          f"{_epl_reg['bet_types'].get('futures')}")
    # ---------- R6 (fix-guy): per-form soccer 1H, NCAAF +
    # quarter segment exams, per-league outrights, tennis
    # futures FORM TERMINAL ----------
    _seg_epl_res = b5.run_checker(
        {"sport": "soccer", "home": "LIV", "away": "ARS",
         "market": "segment", "segment": "1st half",
         "side": "home", "price": -110}, _ctxv)
    _seg_sa_res = b5.run_checker(
        {"sport": "soccer", "home": "Inter",
         "away": "Fiorentina", "market": "segment",
         "segment": "1st half", "side": "home",
         "price": -110}, _ctxv)
    check("R6 segments: soccer 1H prices PER FORM — EPL + "
          "Serie A 1H results price (their results passed), "
          "EPL 1H total still stamps FAILED-EXAM quoting "
          "both forms' numbers",
          _seg_epl_res["state"] == "PRICED"
          and _seg_sa_res["state"] == "PRICED"
          and _seg_epl["state"] == "UNPRICED"
          and "per-form" in _seg_epl["note"]
          and "0.2302" in _seg_epl["note"]
          and "0.6378" in _seg_epl["note"],
          f"{_seg_epl_res['state']} / {_seg_sa_res['state']} "
          f"|| {_seg_epl['note'][:80]}")
    _seg_q = {}
    for _sp, _sg, _nn in (("nba", "1st quarter", "n=2519"),
                          ("nfl", "1st quarter", "n=512")):
        _seg_q[_sp] = b5.run_checker(
            {"sport": _sp,
             "home": "GB" if _sp == "nfl" else "Boston Celtics",
             "away": "DAL" if _sp == "nfl" else "New York Knicks",
             "market": "segment", "segment": _sg,
             "side": "home", "price": -110}, _ctxv)
    _seg_cfb = b5.run_checker(
        {"sport": "ncaaf", "home": "Georgia", "away": "Alabama",
         "market": "segment", "segment": "1st half",
         "side": "home", "price": -110}, _ctxv)
    check("R6 segments: NBA/NFL 1Q + NCAAF 1H are EXAMINED "
          "cells (FAILED-EXAM with walk-forward numbers, "
          "never 'not fitted')",
          all(v["state"] == "UNPRICED"
              and "FAILED-EXAM" in v["note"]
              for v in _seg_q.values())
          and "n=2519" in _seg_q["nba"]["note"]
          and "n=512" in _seg_q["nfl"]["note"]
          and _seg_cfb["state"] == "UNPRICED"
          and "FAILED-EXAM" in _seg_cfb["note"]
          and "n=1778" in _seg_cfb["note"]
          and "1878" in _seg_cfb["note"],
          f"{_seg_q['nba']['note'][:60]} || "
          f"{_seg_cfb['note'][:60]}")
    _tf = b5.run_checker(
        {"sport": "tennis", "home": "ATP Finals 2026",
         "away": "Tournament Winner", "market": "futures",
         "price": None}, _ctxv)
    check("R6 futures: tennis tournament winners are FORM "
          "TERMINAL (draw-dependent; no raw-Elo shortcut)",
          _tf["state"] == "UNPRICED"
          and "FORM TERMINAL" in _tf["note"]
          and "draw-aware tournament simulator" in _tf["note"],
          f"{_tf['note'][:80]}")
    _out6 = b5.load_outrights() or {}
    _lg6 = _out6.get("leagues") or {}
    _ok6, _det6 = True, []
    for _key, _lg in sorted(_lg6.items()):
        _ex = _lg.get("exam") or {}
        _shares = _lg.get("shares") or {}
        if _ex.get("verdict") == "PASS" and _shares:
            _code = max(_shares, key=_shares.get)
            _nm = (_lg.get("names") or {}).get(_code, _code)
            _comp = {"epl": "Premier League",
                     "la-liga": "La Liga",
                     "bundesliga": "Bundesliga",
                     "serie-a": "Serie A",
                     "ligue-1": "Ligue 1",
                     "mls": "Major League Soccer",
                     "championship": "EFL Championship",
                     "serie-b": "Serie B",
                     "la-liga-2": "La Liga 2",
                     "bundesliga-2": "2. Bundesliga",
                     "ligue-2": "Ligue 2"}[_key]
            _v = b5.run_checker(
                {"sport": "soccer", "home": _nm, "away": "x",
                 "market": "futures", "competition": _comp,
                 "runner": _nm, "price": 500}, _ctxv)
            _good = (_v["state"] == "PRICED"
                     and abs(_v["p"] - _shares[_code]) < 1e-9)
            _det6.append(f"{_key}:{'P' if _good else 'X'}")
            _ok6 = _ok6 and _good
        elif _ex:
            _comp = {"epl": "Premier League",
                     "la-liga": "La Liga",
                     "bundesliga": "Bundesliga",
                     "serie-a": "Serie A",
                     "ligue-1": "Ligue 1",
                     "mls": "Major League Soccer",
                     "championship": "EFL Championship",
                     "serie-b": "Serie B",
                     "la-liga-2": "La Liga 2",
                     "bundesliga-2": "2. Bundesliga",
                     "ligue-2": "Ligue 2"}[_key]
            _v = b5.run_checker(
                {"sport": "soccer", "home": "x", "away": "x",
                 "market": "futures", "competition": _comp,
                 "runner": "x", "price": 500}, _ctxv)
            _good = (_v["state"] == "UNPRICED"
                     and "FAILED-EXAM" in _v["note"]
                     and str(_ex.get("mean_brier_model"))
                     in _v["note"])
            _det6.append(f"{_key}:{'F' if _good else 'X'}")
            _ok6 = _ok6 and _good
    check("R6 futures: per-league outright exams — every "
          "passing league prices its runners at the file "
          "shares, every failing league stamps its own "
          "numbers", _ok6 and len(_det6) >= 5,
          " ".join(_det6))
    _cfb_reg = next(e for e in reg if e["sport"] == "ncaaf")
    check("R6 registry: NCAAF segment reads its exam; EPL "
          "segment reads per-form",
          "FAILED-EXAM" in _cfb_reg["bet_types"].get(
              "segment", "")
          and "1H RESULT" in _epl_reg["bet_types"].get(
              "segment", ""),
          f"{_cfb_reg['bet_types'].get('segment')}")
    _p, _info = b5.engine_price("nfl", "spread", "MIN", "SF",
                                side="home", line=-3.5)
    check("R2 NFL spreads: an off-slate fixture prices from the "
          "ratings-derived fair (validated map)",
          _p is not None and "derived" in _info.get("detail", ""),
          f"p={_p} info={_info}")
    check("R2 menus: per-game menu refresh is wired into the "
          "pull (cap constant + engine harvester)",
          app.EVENT_MENU_CAP > 0 and hasattr(b5, "fd_event_menu"))
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
    # ---------- R7 (fix-guy): ESPN soccer 1H, NCAAF
    # quarters, NHL period forms, second-tier outrights —
    # the R6 remainder, closed ----------
    _seg_doc7 = b5.load_segments() or {}
    _soc7 = _seg_doc7.get("soccer-1h") or {}
    _espn7 = ("mls", "brasileirao", "liga-mx",
              "liga-profesional", "brasileirao-b", "nacional-b",
              "usl-championship", "usl-league-one", "peru-liga-1",
              "colombia-primera", "ecuador-ligapro",
              "uruguay-primera", "paraguay-primera",
              "bolivia-profesional", "venezuela-primera",
              "costa-rica-primera", "guatemala-liga",
              "chile-primera", "nwsl", "liga-mx-femenil",
              "wsl", "a-league-women", "a-league",
              "brasileirao-c", "primera-b-ar", "liga-expansion")
    check("R7 segments: every ESPN-sourced soccer league "
          "carries a terminal 1H block (examined per form "
          "or NO-DATA with evidence)",
          all(_soc7.get(k, {}).get("status") in
              ("FITTED", "FAILED-EXAM", "NO-DATA")
              for k in _espn7)
          and all(k in _soc7 for k in _espn7),
          ", ".join(f"{k}:{_soc7.get(k, {}).get('status')}"
                    for k in _espn7[:6]) + " ...")
    _seg_mls_res = b5.run_checker(
        {"sport": "soccer", "home": "Inter Miami CF",
         "away": "LA Galaxy", "market": "segment",
         "segment": "1st half", "side": "home",
         "price": -110}, _ctxv)
    _seg_mls_tot = b5.run_checker(
        {"sport": "soccer", "home": "Inter Miami CF",
         "away": "LA Galaxy", "market": "segment",
         "segment": "1st half", "side": "over", "line": 1.5,
         "price": -110}, _ctxv)
    _seg_bra_res = b5.run_checker(
        {"sport": "soccer", "home": "Flamengo",
         "away": "Botafogo", "market": "segment",
         "segment": "1st half", "side": "home",
         "price": -110}, _ctxv)
    _seg_bra_tot = b5.run_checker(
        {"sport": "soccer", "home": "Flamengo",
         "away": "Botafogo", "market": "segment",
         "segment": "1st half", "side": "over", "line": 1.5,
         "price": -110}, _ctxv)
    check("R7 segments: ESPN soccer 1H prices PER FORM — "
          "MLS result + total price (both passed), "
          "Brasileirao result prices while its total stamps "
          "FAILED-EXAM with its numbers",
          _seg_mls_res["state"] == "PRICED"
          and _seg_mls_tot["state"] == "PRICED"
          and "ESPN" in _seg_mls_res["note"]
          and _seg_bra_res["state"] == "PRICED"
          and _seg_bra_tot["state"] == "UNPRICED"
          and "FAILED-EXAM" in _seg_bra_tot["note"]
          and "0.2135" in _seg_bra_tot["note"],
          f"{_seg_mls_res['state']}/{_seg_mls_tot['state']}/"
          f"{_seg_bra_res['state']} || "
          f"{_seg_bra_tot['note'][:80]}")
    _nodata7 = [k for k in _espn7
                if _soc7.get(k, {}).get("status") == "NO-DATA"]
    check("R7 segments: NO-DATA leagues (if any) carry "
          "their evidence in the artifact",
          all((_soc7[k].get("evidence") and
               (_soc7[k].get("coverage") or {})
               .get("games_completed") is not None)
              for k in _nodata7),
          f"NO-DATA leagues: {_nodata7}")
    _seg_cfb_q = {}
    for _sg in ("1st quarter", "2nd quarter"):
        _seg_cfb_q[_sg] = b5.run_checker(
            {"sport": "ncaaf", "home": "Georgia",
             "away": "Alabama", "market": "segment",
             "segment": _sg, "side": "home", "price": -110},
            _ctxv)
    check("R7 segments: NCAAF 1Q + 2Q are EXAMINED cells "
          "(FAILED-EXAM with walk-forward numbers on the "
          "rebuilt linescore pull, n=1822 each)",
          all(v["state"] == "UNPRICED"
              and "FAILED-EXAM" in v["note"]
              and "n=1822" in v["note"]
              for v in _seg_cfb_q.values()),
          " || ".join(v["note"][:60]
                      for v in _seg_cfb_q.values()))
    _seg_nhl_2p_t = b5.run_checker(
        {"sport": "nhl", "home": "BOS", "away": "NYR",
         "market": "segment", "segment": "2nd period",
         "side": "over", "line": 1.5, "price": -110}, _ctxv)
    _seg_nhl_2p_m = b5.run_checker(
        {"sport": "nhl", "home": "BOS", "away": "NYR",
         "market": "segment", "segment": "2nd period",
         "side": "home", "price": -110}, _ctxv)
    _seg_nhl_1p_m = b5.run_checker(
        {"sport": "nhl", "home": "BOS", "away": "NYR",
         "market": "segment", "segment": "1st period",
         "side": "home", "price": -110}, _ctxv)
    _seg_nhl_3p_t = b5.run_checker(
        {"sport": "nhl", "home": "BOS", "away": "NYR",
         "market": "segment", "segment": "3rd period",
         "side": "over", "line": 1.5, "price": -110}, _ctxv)
    check("R7 segments: NHL period forms are EXAMINED per "
          "period per form (2P/3P totals + period moneylines "
          "stamp FAILED-EXAM with their own numbers)",
          _seg_nhl_2p_t["state"] == "UNPRICED"
          and "FAILED-EXAM" in _seg_nhl_2p_t["note"]
          and "0.2399" in _seg_nhl_2p_t["note"]
          and _seg_nhl_2p_m["state"] == "UNPRICED"
          and "FAILED-EXAM" in _seg_nhl_2p_m["note"]
          and "0.6686" in _seg_nhl_2p_m["note"]
          and _seg_nhl_1p_m["state"] == "UNPRICED"
          and "0.6759" in _seg_nhl_1p_m["note"]
          and _seg_nhl_3p_t["state"] == "UNPRICED"
          and "0.2309" in _seg_nhl_3p_t["note"],
          f"{_seg_nhl_2p_t['note'][:70]} || "
          f"{_seg_nhl_2p_m['note'][:70]}")
    _out7 = b5.load_outrights() or {}
    _lg7 = _out7.get("leagues") or {}
    _t2 = ("championship", "serie-b", "la-liga-2",
           "bundesliga-2", "ligue-2")
    check("R7 futures: second-tier title outrights are "
          "EXAMINED per league (Monte Carlo protocol, same "
          "bar — an exam block with a verdict for each)",
          all((_lg7.get(k, {}).get("exam") or {})
              .get("verdict") in ("PASS", "FAILED-EXAM")
              for k in _t2),
          ", ".join(f"{k}:"
                    f"{(_lg7.get(k, {}).get('exam') or {}).get('verdict')}"
                    for k in _t2))
    _nhl_reg7 = next(e for e in reg if e["sport"] == "nhl")
    _cfb_reg7 = next(e for e in reg if e["sport"] == "ncaaf")
    check("R7 registry: NHL segment line reads all three "
          "periods per form; NCAAF line reads 1Q + 2Q exams",
          "2P:" in _nhl_reg7["bet_types"].get("segment", "")
          and "3P:" in _nhl_reg7["bet_types"].get("segment", "")
          and "2Q:" in _cfb_reg7["bet_types"].get(
              "segment", ""),
          f"{_nhl_reg7['bet_types'].get('segment', '')[:90]} "
          f"|| {_cfb_reg7['bet_types'].get('segment', '')[:90]}")

    # ---------- v12 panel update: segments, Coverage,
    # Registry, Edge Landscape, slip correlation, viewer,
    # cross-nav ----------
    _panel_sample = [
        {"sport": "soccer", "home": "Inter", "away": "Fiorentina",
         "market": "moneyline", "side": "home", "price": -145},
        {"sport": "soccer", "home": "Inter", "away": "FC Nowhere",
         "market": "moneyline", "side": "home", "price": -145},
        {"sport": "nfl", "home": "DET", "away": "GB",
         "market": "moneyline", "side": "home", "price": -150}]
    _cov_rows = app.coverage_rows(_panel_sample)
    _serie = next((r for r in _cov_rows
                   if r["league"] == "serie-a"), None)
    check("panel coverage: per-league rows, priced share "
          "strictly between 0 and 1",
          _serie is not None and _serie["markets"] == 2
          and _serie["priced"] == 1
          and 0.0 < _serie["share"] < 1.0,
          f"rows={_cov_rows}")
    _cov_txt = texts(ft.Column(controls=app.build_coverage_section(
        _panel_sample, stamp="Pull: test · VERIFIED")))
    check("panel coverage: section renders share, pull stamp "
          "and the named gap",
          any("1/2 priced" in t for t in _cov_txt)
          and any("Pull: test" in t for t in _cov_txt)
          and any("FC Nowhere" in t for t in _cov_txt),
          f"texts={_cov_txt[:6]}")
    _tiles = app.registry_tiles()
    check("panel registry: tiles carry kind, covered count, "
          "backtest text, unified status",
          len(_tiles) >= 50
          and all(t["backtest_text"] for t in _tiles)
          and all(t["status"] for t in _tiles)
          and any("Brier" in t["backtest_text"] for t in _tiles),
          f"n={len(_tiles)}")
    _reg_txt = texts(ft.Column(
        controls=app.build_registry_section()))
    check("panel registry: tiles speak the purged language "
          "(no raw FAILED-EXAM, no fit file names)",
          any("Registry" in t for t in _reg_txt)
          and not any("FAILED-EXAM" in t for t in _reg_txt)
          and not any(".json" in t for t in _reg_txt))
    _mk_entries = []
    for i in range(80):
        _mk_entries.append((
            {"sport": "nfl", "home": f"H{i}", "away": f"A{i}",
             "market": "moneyline", "side": "home",
             "price": -110},
            {"state": "PRICED", "p": 0.40 + (i % 40) / 100.0,
             "grade": "—"},
            float(i % 17) - 8.0))
    _land = app.edge_landscape_data(_mk_entries)
    check("panel landscape: points capped at the stated budget; "
          "tap detail names the market + the value diagonal",
          len(_land["points"]) == app.EDGE_LANDSCAPE_CAP
          and _land["total"] == 80 and _land["capped"]
          and "diagonal" in _land["points"][0]["detail"],
          f"land={ {k: _land[k] for k in ('total', 'capped')} }")
    _land_txt = texts(ft.Column(
        controls=app.build_edge_landscape(_mk_entries)))
    check("panel landscape: plotting area + axis labels + the "
          "cap stated on the surface",
          any("EDGE LANDSCAPE" in t for t in _land_txt)
          and any("implied" in t for t in _land_txt)
          and any("largest" in t for t in _land_txt))
    _slip_legs = [
        {"sport": "nfl", "home": "DET", "away": "GB",
         "market": "moneyline", "side": "home", "price": -150},
        {"sport": "nfl", "home": "DET", "away": "GB",
         "market": "totals", "side": "over", "line": 47.5,
         "price": -110},
        {"sport": "nfl", "home": "KC", "away": "BUF",
         "market": "moneyline", "side": "home", "price": -120}]
    _corr = app.slip_correlation(_slip_legs)
    check("panel slip correlation: same-game legs cluster, the "
          "spread leg stands alone",
          _corr["n_clustered"] == 2
          and any(c["kind"] == "same game"
                  for c in _corr["clusters"])
          and len(_corr["singles"]) == 1,
          f"corr={_corr}")
    _corr_txt = texts(ft.Column(controls=app.build_slip_correlation(
        [(m, {}) for m in _slip_legs])))
    check("panel slip correlation: the warning is printed in "
          "plain words",
          any("one bet in costumes" in t for t in _corr_txt))
    check("panel viewer: zoom clamps to [1, 6]",
          app.viewer_zoom_clamp(0.2) == 1.0
          and app.viewer_zoom_clamp(9) == 6.0
          and app.viewer_zoom_clamp(2.5) == 2.5
          and app.viewer_zoom_clamp("x") == 1.0)
    _sheet = app.build_viewer_sheet(
        "T", "Pull: test", 2.0, [ft.Text("body")],
        on_zoom=lambda f: None, on_close=lambda e: None)
    _ivs = [c for c in walk(_sheet)
            if type(c).__name__ == "InteractiveViewer"]
    check("panel viewer: sheet carries a pinch/pan "
          "InteractiveViewer clamped to [1, 6]",
          len(_ivs) == 1 and _ivs[0].min_scale == 1.0
          and _ivs[0].max_scale == 6.0)

    # live drive: the panel segments on the real page
    page.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=3)))
    stage = switcher.content
    pseg = next(c for c in walk(stage)
                if type(c).__name__ == "SegmentedButton")
    check("panel: segmented control carries Charts | Coverage "
          "| Instruments | Registry",
          {s.value for s in pseg.segments}
          == {"charts", "coverage", "instruments", "registry"})
    pseg.on_change(SimpleNamespace(
        control=SimpleNamespace(selected={"coverage"})))
    cov_live = texts(switcher.content)
    check("panel: Coverage segment renders priced share + pull "
          "stamp on the live pull",
          any("Coverage" in t for t in cov_live)
          and any("priced" in t for t in cov_live)
          and any("Pull:" in t for t in cov_live))
    pseg.on_change(SimpleNamespace(
        control=SimpleNamespace(selected={"registry"})))
    check("panel: Registry segment renders league tiles",
          any("Registry" in t for t in texts(switcher.content)))
    pseg.on_change(SimpleNamespace(
        control=SimpleNamespace(selected={"instruments"})))
    inst_live = texts(switcher.content)
    check("panel: Instruments segment keeps the snapshot shelf "
          "and prints the current pull time beside it",
          any("SNAPSHOT INSTRUMENTS" in t for t in inst_live)
          and any("Current pull:" in t for t in inst_live))
    pseg.on_change(SimpleNamespace(
        control=SimpleNamespace(selected={"coverage"})))
    league_row = next(
        c for c in walk(switcher.content)
        if type(c).__name__ == "Container"
        and getattr(c, "on_click", None) is not None
        and (getattr(c, "tooltip", "") or "").startswith("Open "))
    league_row.on_click(SimpleNamespace())
    board_txt = texts(switcher.content)
    check("panel cross-nav: league tap lands on the Board with "
          "the league filter named",
          any("League:" in t for t in board_txt)
          and any(getattr(c, "content", "") == "Back to 3D panel"
                  for c in walk(switcher.content)),
          f"board={board_txt[:4]}")
    back_btn = next(
        c for c in walk(switcher.content)
        if type(c).__name__ == "TextButton"
        and getattr(c, "content", "") == "Back to 3D panel")
    back_btn.on_click(SimpleNamespace())
    check("panel cross-nav: back returns to the panel segment "
          "it came from",
          any("Coverage" in t for t in texts(switcher.content)))
    page.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=0)))
    chart_btn = next(
        c for c in walk(switcher.content)
        if type(c).__name__ == "TextButton"
        and getattr(c, "content", "")
        == "Chart — see this market in the 3D panel")
    chart_btn.on_click(SimpleNamespace())
    check("panel cross-nav: a card's Chart affordance opens the "
          "Charts segment",
          any("Xii Charts" in t for t in texts(switcher.content)))

    # ---------- v12.1 feel / QoL ----------
    import inspect as _inspect
    import wave as _wave
    _src = open(os.path.join(HERE, "main.py")).read()
    _readme = open(os.path.join(HERE, "README.md")).read()
    _wf = open(os.path.join(
        HERE, ".github", "workflows", "build-apk.yml")).read()
    _req = open(os.path.join(HERE, "requirements.txt")).read()
    check("v12.1 version unified: README release line",
          "12.1.0 (build 17)" in _readme)
    check("v12.1 version unified: workflow build args",
          '--build-version "12.1.0"' in _wf
          and '--build-number "17"' in _wf)
    check("v12.1: requirements pin the flet-audio extension",
          "flet-audio==1.0.4" in _req)
    for _nm, _lo, _hi in (("tick", 0.03, 0.08),
                          ("confirm", 0.09, 0.16),
                          ("golden", 0.20, 0.32)):
        _p = os.path.join(HERE, "assets", "sounds", f"{_nm}.wav")
        _ok = os.path.exists(_p) and os.path.getsize(_p) < 25000
        if _ok:
            try:
                with _wave.open(_p) as _w:
                    _dur = _w.getnframes() / _w.getframerate()
                _ok = _lo <= _dur <= _hi
            except Exception:
                _ok = False
        check(f"v12.1 sound asset: {_nm}.wav exists, <25KB, "
              f"valid WAV of the right length", _ok)
    check("v12.1: play_sound + tap_haptic never raise (wrapped)",
          "except" in _inspect.getsource(app.play_sound)
          and "except" in _inspect.getsource(app.tap_haptic))
    check("v12.1: sound volume is capped at 0.35",
          app.SOUND_VOLUME <= 0.35)
    _audios = [s for s in page.services
               if type(s).__name__ == "Audio"]
    check("v12.1: three Audio services registered, capped + "
          "autoplay off",
          len(_audios) == 3
          and all(a.volume <= 0.35 and a.autoplay is False
                  for a in _audios))
    check("v12.1: a HapticFeedback service is registered",
          any(type(s).__name__ == "HapticFeedback"
              for s in page.services))
    check("v12.1: sound play points wired (tick/confirm/golden)",
          'play_sound("tick")' in _src
          and 'play_sound("confirm")' in _src
          and 'play_sound("golden")' in _src)
    check("v12.1: no new standing loops (pulse keys <= 6)",
          len(app.PULSE_PERIODS) <= 6)
    _pb = app.primary_button("Probe", lambda e: None)
    check("v12.1: primary buttons are pressified (110 ms scale "
          "animation)",
          _pb.animate_scale is not None
          and _pb.animate_scale.duration == 110)
    check("v12.1: protected slip carries the pinned summary "
          "line (source)",
          "combined odds" in _src and "max loss" in _src)

    # a fresh boot for the board-level QoL probes
    page3 = FakePage()
    app.main(page3)
    sw3 = page3.controls[1]
    board3 = sw3.content
    bsw3 = [c for c in walk(board3)
            if type(c).__name__ == "AnimatedSwitcher"]
    cards3 = bsw3[0].content
    check("v12.1: pull-age line renders on the board",
          any("pulled" in t and "ago" in t
              for t in texts(cards3)))
    _lists = [c for c in walk(cards3)
              if type(c).__name__ == "Column"]
    cards_list3 = max(_lists, key=lambda c: sum(
        1 for x in getattr(c, "controls", [])
        if type(x).__name__ == "Container"))
    _cards3 = [x for x in cards_list3.controls
               if type(x).__name__ == "Container"]
    check("v12.1: entrance animation gates at the first 8 "
          "cards (180 ms), the rest static",
          len(_cards3) > 8
          and all(c.animate_opacity is not None
                  and c.animate_opacity.duration == 180
                  for c in _cards3[:8])
          and all(c.animate_opacity is None
                  for c in _cards3[8:]))
    _golden_exp = len(app.distill_finds(
        _rec["markets"],
        b5.run_slate(_rec, print_out=False))[0])
    _badge = page3.navigation_bar.destinations[1].badge
    check("v12.1: Slip badge shows the GOLDEN count (hidden "
          "at zero)",
          (_badge is not None) == (_golden_exp > 0)
          and (_golden_exp == 0
               or _badge.label == str(_golden_exp)),
          f"golden={_golden_exp} badge={_badge}")
    _sf = next(c for c in walk(cards3)
               if type(c).__name__ == "TextField")
    _sf.on_change(SimpleNamespace(
        control=SimpleNamespace(value="Lions")))
    _chip = [c for c in walk(cards3)
             if type(c).__name__ == "TextButton"
             and getattr(c, "content", "") == "Clear filters"]
    check("v12.1: Clear filters chip appears when a filter is "
          "non-default", len(_chip) == 1)
    if _chip:
        _chip[0].on_click(SimpleNamespace())
    check("v12.1: one tap on Clear filters resets the search",
          _sf.value == ""
          and not any(
              getattr(c, "content", "") == "Clear filters"
              for c in walk(cards3)
              if type(c).__name__ == "TextButton"))
    # the sound toggle in More: default ON, flips + persists
    page3.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=4)))
    _snd = [c for c in walk(sw3.content)
            if type(c).__name__ == "Switch"
            and "Sound" in (getattr(c, "label", "") or "")]
    check("v12.1: More carries the Sound toggle, default ON",
          len(_snd) == 1 and _snd[0].value is True
          and app._SOUND["enabled"] is True)
    if _snd:
        _snd[0].on_change(SimpleNamespace(
            control=SimpleNamespace(value=False)))
    _setfile = os.path.join(STORAGE, "Bet_Finder-sound.json")
    check("v12.1: muting persists on-device and play_sound "
          "no-ops",
          app._SOUND["enabled"] is False
          and os.path.exists(_setfile)
          and app.play_sound("tick") is None)
    app.set_sound_enabled(True)

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks "
          f"passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
