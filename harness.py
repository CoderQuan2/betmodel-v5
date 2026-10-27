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
import io
import json
import os
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

from PIL import Image as _PIL_Image

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
    complete synchronously), run_task EXECUTES coroutines to
    completion (build 31 — the board/finds renders are
    dispatched as coroutines; a fake that merely closes them
    would test nothing)."""

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
        # Execute the coroutine to completion on a fresh
        # loop. Exceptions inside a driven coroutine are
        # recorded in task_errors, never raised at the call
        # site — a real run_task schedules the task; the
        # scheduler never sees the task's exception.
        out = fn(*args, **kwargs)
        if asyncio.iscoroutine(out):
            errs = self.__dict__.setdefault("task_errors", [])
            try:
                asyncio.get_running_loop()
                nested = True
            except RuntimeError:
                nested = False
            if nested:
                # A loop is already running on this thread
                # (a driven coroutine dispatched again):
                # drive this one on a helper thread's loop
                # and wait — still completion-before-return.
                def _drive():
                    lp = asyncio.new_event_loop()
                    try:
                        lp.run_until_complete(out)
                    except Exception as ex:  # noqa: BLE001
                        errs.append(ex)
                    finally:
                        lp.close()
                _t = threading.Thread(target=_drive)
                _t.start()
                _t.join()
            else:
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


def _span_text(span):
    """A span's full text: its own text plus every nested
    span's, in order (spans can nest)."""
    t = getattr(span, "text", None) or ""
    for sub in getattr(span, "spans", None) or []:
        t += _span_text(sub)
    return t


def texts(ctrl):
    """Visible text of a subtree. For an ft.Text, ONE string
    is yielded — its value plus the concatenation of all its
    span texts in order (span-awareness added in v12.7 for
    the typographic card, kept in v12.8: it is purely
    additive — value-only Texts, including every row of
    BetFi 11's card, yield exactly their value)."""
    out = []
    for c in walk(ctrl):
        if type(c).__name__ == "Text":
            s = getattr(c, "value", None) or ""
            for span in getattr(c, "spans", None) or []:
                s += _span_text(span)
            if s:
                out.append(s)
            continue
        v = getattr(c, "value", None)
        if isinstance(v, str) and v:
            out.append(v)
    return out


def main():
    import flet as ft
    import main as app
    import betmodel5 as b5

    # ---------- identity ----------
    check("APP_VERSION is 12.12.0", app.APP_VERSION == "12.19.0")
    check("BUILD_NUMBER is 33", app.BUILD_NUMBER == 40)
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
    # startup state, asserted BEFORE anything drives it:
    # Show opens on All markets (v12.12 — v12.4–v12.11 opened
    # on Golden bets), the sport view on All sports, the pull
    # chooser on the persisted sport — and the board carries
    # NO switches at all (the switch wall is gone).
    _dds0 = [c for c in walk(cards_view)
             if type(c).__name__ == "Dropdown"]
    _show_dd0 = next(
        d for d in _dds0
        if [o.key for o in d.options]
        == [k for k, _t in app.SHOW_MODES])
    _sv_dd0 = next(
        d for d in _dds0
        if [o.key for o in d.options]
        == ["all", "nfl", "ncaaf"])
    check("v12.12 re-pin (was v12.4): startup state — Show = "
          "All markets, Board shows = All sports, nothing "
          "toggled on",
          _show_dd0.value == "all"
          and _sv_dd0.value == "all")
    check("v12.4: the board renders zero switches (the switch "
          "wall is gone)",
          not any(type(c).__name__ == "Switch"
                  for c in walk(board)))
    # The card assertions below were written against the
    # Golden-bets startup view (v12.4): they drive Show to
    # All markets through the dropdown. Under the v12.12
    # default the board already opens there — the drive is
    # now a no-op safeguard; the dropdown IS the filter.
    _show_dd0.on_select(SimpleNamespace(
        control=SimpleNamespace(value="all")))
    all_texts = texts(cards_view)
    # v12.11 re-home: cards are drawn images now — the board
    # renders market cards when its list holds
    # GestureDetectors whose images decode at the ImageBoard
    # row geometry.
    _dets0 = [c for c in walk(cards_view)
              if type(c).__name__ == "GestureDetector"]
    check("board renders market cards",
          bool(_dets0) and all(
              _PIL_Image.open(io.BytesIO(
                  c.content.src)).size == (1170, 177)
              for c in _dets0))
    card = _dets0[0]
    # F1 order is measured on the card's line plan (the
    # readable form of the expanded drawing): the market /
    # selection headline prints above the FanDuel path, and
    # the path itself is carried. The plan's market is
    # identified by byte-matching the collapsed draw.
    _m0 = _v0 = None
    for _mm, _vv in zip(_rec["markets"], b5.run_slate(_rec)):
        if app._card_png_collapsed(
                _mm, _vv, app.market_edge_pts(_mm, _vv)
                ) == card.content.src:
            _m0, _v0 = _mm, _vv
            break
    _plan0 = app._card_line_plan(
        _m0, _v0, _rec, app.game_quotes(_rec["markets"]),
        edge_pts=app.market_edge_pts(_m0, _v0),
        lane_ctx=app.lane_contexts(_rec["markets"]))
    _i_path = next(i for i, t in enumerate(_plan0)
                   if t.startswith("Find it:"))
    check("F1 order: market/selection print above the FD path",
          _i_path > 0 and any(
              h in _plan0[i]
              for i in range(_i_path)
              for h in ("Moneyline", "Point Spread",
                        "Total Points")))
    check("F1: card carries a FanDuel navigation path",
          any("FanDuel \u2192 " in t for t in _plan0))
    check("v12.4 re-pin (was F3 first-render animation): a "
          "filter re-render does not replay entrances \u2014 cards "
          "arrive static; the animated first render is pinned "
          "on the fresh-boot Price Slate path in v12.1 below",
          getattr(card, "opacity", 1) == 1
          and getattr(card, "animate_opacity", None) is None)

    # v12.11 re-home (the v12.8 widget-construction pins are
    # retired with the widget card system): the card's
    # structure is the drawing itself, and its depth is the
    # four sections in order, whose anatomy leads with the
    # verdict line and carries state + calibration tag.
    _secs0 = app._depth_sections(
        _m0, _v0, _rec, app.game_quotes(_rec["markets"]),
        edge_pts=app.market_edge_pts(_m0, _v0),
        lane_ctx=app.lane_contexts(_rec["markets"]))
    check("v12.11: card depth is the four sections "
          "(PRICE ANATOMY / SCALE / COHERENCE / PROVENANCE)",
          [t for t, _ls in _secs0]
          == ["PRICE ANATOMY", "SCALE", "COHERENCE",
              "PROVENANCE"],
          f"sections={[t for t, _ls in _secs0]}")
    check("v12.8: 11's anatomy leads with the verdict line "
          "and carries state + calibration tag",
          any(ln.startswith("state:")
              for ln in _secs0[0][1])
          and any(ln.startswith("calibration tag:")
                  for ln in _secs0[0][1]))

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

    # v12.4 re-pin (was F4: the toggle row survives
    # re-renders): there is no toggle row anymore — the two
    # filter dropdowns are static band controls that survive
    # re-renders as the same objects, and still no switch
    # appears anywhere on the board.
    page.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=2)))   # Lab
    page.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=0)))   # Board
    _dds0b = [c for c in walk(cards_view)
              if type(c).__name__ == "Dropdown"]
    _show_dd0b = next(
        d for d in _dds0b
        if [o.key for o in d.options]
        == [k for k, _t in app.SHOW_MODES])
    _sv_dd0b = next(
        d for d in _dds0b
        if [o.key for o in d.options]
        == ["all", "nfl", "ncaaf"])
    check("v12.4: filter dropdowns survive re-renders (same "
          "objects), board still switch-free",
          _show_dd0b is _show_dd0 and _sv_dd0b is _sv_dd0
          and not any(type(c).__name__ == "Switch"
                      for c in walk(board)))

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
    check("R3 mma: lane prices off the passed refit "
          "(attempt 2: Brier 0.2438 vs naive 0.2441, n=9091; "
          "attempt 1's 0.2454 vs 0.2451 failure is history)",
          _mp is not None and 0 < _mp < 1
          and "0.2438" in _mi.get("detail", "")
          and "0.2441" in _mi.get("detail", ""),
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
    check("R3 coverage: tennis capable, mma capable (refit "
          "passed), table tennis still named-unchecked "
          "(checker == coverage)",
          _tc["priced_capable"] == 1
          and _mc["priced_capable"] == 1
          and _mc["unpriced"] == 0
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
    _lista_blk = (b5.load_cricket().get("lanes") or {})["lista_m"]
    check("R4 cricket: Challenge League lane prices off the "
          "passed refit (attempt 2: Brier 0.1903 vs naive "
          "0.2253, n=127; the FAILED-EXAM stamp is retired)",
          _lp is not None and 0 < _lp < 1
          and _lista_blk["backtest"]["brier"] < _lista_blk[
              "backtest"]["naive_brier"], f"p={_lp}")
    _rp, _ri = b5.engine_price(
        "rugby-union", "spread", "Canterbury", "Northland",
        side="home", line=-6.5, competition="New Zealand - NPC")
    check("R4 rugby union: NPC spread prices off the margin map",
          _rp is not None and 0 < _rp < 1
          and "margin map" in _ri.get("detail", ""), f"p={_rp}")
    _gp, _gi = b5.engine_price(
        "rugby-league", "moneyline", "Australia", "Fiji",
        side="home", competition="World Cup - Men")
    check("R4 rugby league: international men's lane ships "
          "FAILED-EXAM with attempt 2's numbers (does not "
          "price)",
          _gp is None and "FAILED-EXAM" in _gi
          and "0.2332" in _gi and "192" in _gi, f"{_gi}")
    _fp, _fi = b5.engine_price(
        "rugby-league", "moneyline", "Australia", "New Zealand",
        side="home", competition="World Cup - Women")
    check("R4 rugby league: international women's lane prices "
          "off the passed refit (attempt 2: Brier 0.2327 vs "
          "naive 0.2363, n=111)",
          _fp is not None and 0 < _fp < 1
          and "intl_f" in _fi.get("detail", ""), f"p={_fp}")
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
    # v12.11 re-home (was the v12.8 no-Chart-TextButton pin):
    # the drawn card's affordances ARE its action zones —
    # the exposed zone labels are the whole inventory, and
    # no Chart action is among them (on_chart is still
    # dropped at the build_card_safe adapter, as in 11).
    check("v12.8: cards carry no Chart affordance (11 had "
          "none \u2014 on_chart is dropped at the adapter)",
          list(app._CARD_ACTION_LABELS)
          == ["COPY LABEL", "SLIP", "COLLAPSE"]
          and not any(type(c).__name__ == "TextButton"
                      and "Chart" in str(
                          getattr(c, "content", ""))
                      for c in walk(switcher.content)))

    # ---------- v12.1 feel / QoL ----------
    import inspect as _inspect
    import wave as _wave
    _src = open(os.path.join(HERE, "main.py")).read()
    _readme = open(os.path.join(HERE, "README.md")).read()
    _wf = open(os.path.join(
        HERE, ".github", "workflows", "build-apk.yml")).read()
    _req = open(os.path.join(HERE, "requirements.txt")).read()
    check("v12.12 version unified: README release line",
          "12.19.0 (build 40)" in _readme)
    check("v12.12 version unified: workflow build args",
          '--build-version "12.19.0"' in _wf
          and '--build-number "40"' in _wf)
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
    check("v12.4 re-pin (was v12.1 three services): four "
          "Audio services registered, capped + autoplay off",
          len(_audios) == 4
          and all(a.volume <= 0.35 and a.autoplay is False
                  for a in _audios))
    check("v12.1: a HapticFeedback service is registered",
          any(type(s).__name__ == "HapticFeedback"
              for s in page.services))
    check("v12.1: sound play points wired (tick/confirm/golden)",
          'play_sound("tick")' in _src
          and 'play_sound("confirm")' in _src
          and 'play_sound("golden")' in _src)
    check("v12.4: the startup sound's play point is wired",
          'play_sound("startup")' in _src)
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
    check("v12.4 re-pin (was v12.1 pull-age): the pull-age "
          "line renders — under the soccer first-pull default "
          "the fixture slate has no soccer entry, so the "
          "truthful line is 'not pulled yet'",
          any(("pulled" in t and "ago" in t)
              or "not pulled yet" in t
              for t in texts(cards3)))
    # v12.12 re-pin (was v12.4): this fresh boot opened on
    # the All markets startup view — under the old Golden
    # bets default this fixture pull (no GOLDEN BETs on it)
    # rendered no cards at all. Drive Show to All markets
    # anyway (a no-op under the new default), then land a
    # fresh pricing pass through the band's own Price Slate
    # action — the path that used to set the entrance flag —
    # before measuring the board (v12.8: cards get NO
    # entrance; they are placed exactly as 11 built them).
    _show3 = next(c for c in walk(cards3)
                  if type(c).__name__ == "Dropdown"
                  and [o.key for o in c.options]
                  == [k for k, _t in app.SHOW_MODES])
    _show3.on_select(SimpleNamespace(
        control=SimpleNamespace(value="all")))

    def _btn_label3(c):
        ct = getattr(c, "content", None)
        if isinstance(ct, str):
            return ct
        return getattr(ct, "value", None)
    _price_btn = next(c for c in walk(cards3)
                      if type(c).__name__ == "Button"
                      and _btn_label3(c) == "Price Slate")
    _price_btn.on_click(SimpleNamespace())
    _lists = [c for c in walk(cards3)
              if type(c).__name__ == "Column"]
    cards_list3 = max(_lists, key=lambda c: sum(
        1 for x in getattr(c, "controls", [])
        if type(x).__name__ == "GestureDetector"))
    _cards3 = [x for x in cards_list3.controls
               if type(x).__name__ == "GestureDetector"]
    # v12.8 RETIRED: "v12.4.1 re-pin (was v12.1 entrance
    # gates): the first-8 entrance is OFFSET-ONLY..." — 11's
    # cards had no entrance at all, and the port gates
    # _animate_cards OFF for card children. The replacement
    # assertion is stronger: after the full Price Slate path,
    # NO card carries any entrance state at all.
    check("v12.8: cards are placed exactly as 11 built them "
          "— no entrance (no offset/scale animation, no "
          "staged opacity) on any card after a fresh render",
          len(_cards3) > 8
          and all(c.animate_offset is None for c in _cards3)
          and all(c.animate_scale is None for c in _cards3)
          and all(c.animate_opacity is None for c in _cards3)
          and all(getattr(c, "opacity", 1) == 1
                  for c in _cards3)
          and all(getattr(c, "offset", None) is None
                  for c in _cards3))
    # v12.7.1: the render receipt seated beside cards_count is
    # written by that very render — it must name exactly the
    # cards the drive appended (the GestureDetector children
    # of the board's card list; headers are Images, empties
    # are Rows).
    _receipt3 = next(
        (c for c in walk(cards3)
         if type(c).__name__ == "Text"
         and (getattr(c, "value", "") or "")
         .startswith("Rendered:")),
        None)
    check("v12.7.1: the board render receipt reports exactly "
          "the cards the drive appended",
          _receipt3 is not None
          and _receipt3.value
          == f"Rendered: {len(_cards3)} cards on this board",
          f"receipt={getattr(_receipt3, 'value', None)} "
          f"cards={len(_cards3)}")
    _ac = _src[_src.index("def _animate_cards"):
               _src.index("def render_cards")]
    check("v12.4.1: _animate_cards never touches opacity "
          "(source pin — the load-bearing-visibility rule)",
          ".opacity" not in _ac)
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
    # back to the startup defaults before the chip flow, so
    # the chip's appearance is the search's doing alone
    # (v12.12: the startup Show default is All markets —
    # driving to "golden" here would itself be a non-default
    # filter and summon the chip on its own)
    _show3.on_select(SimpleNamespace(
        control=SimpleNamespace(value="all")))
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

    # ---------- v12.2 performance ----------
    _norm_battery = ["San José", "Hawai'i", "  Ångström O’Neil ",
                     "Jannik Sinner", "Świątek", "FC Porto"]
    b5._norm_name_cached.cache_clear()
    _norm_out = [b5._norm_name(_n) for _n in _norm_battery]
    _norm_expected = [b5._norm_name_uncached(_n)
                      for _n in _norm_battery]
    b5._norm_name(_norm_battery[0])
    check("v12.2: _norm_name memoization is output-identical",
          _norm_out == _norm_expected
          and _norm_out[:3] == ["san jose", "hawaii",
                                "angstrom oneil"]
          and b5._norm_name_cached.cache_info().hits >= 1)

    _tennis_fit = b5.load_tennis()
    _atp_blk = _tennis_fit["tours"]["atp"]
    _wta_blk = _tennis_fit["tours"]["wta"]
    _atp_synth = {"elo": {"Smith John": 1500.0,
                          "Smith Jane": 1490.0}}
    _wta_synth = {"elo": {"Lee C.": 1500.0,
                          "Smith Jones A.": 1490.0,
                          "Jones A.": 1480.0}}
    check("v12.2: tennis indexed resolution matches known "
          "exact/token/surname outcomes",
          b5.resolve_tennis_player(
              "Jannik Sinner", _atp_blk, "atp") == "Jannik Sinner"
          and b5.resolve_tennis_player(
              "Sinner Jannik", _atp_blk, "atp") == "Jannik Sinner"
          and b5.resolve_tennis_player(
              "John Smith", _atp_synth, "atp") == "Smith John"
          and b5.resolve_tennis_player(
              "Iga Swiatek", _wta_blk, "wta") == "Swiatek I."
          and b5.resolve_tennis_player(
              "Carol Young Suh Lee", _wta_synth, "wta") == "Lee C.")
    check("v12.2: tennis indexed resolution keeps ambiguity "
          "ambiguous (never guesses)",
          b5.resolve_tennis_player(
              "J Smith", _atp_synth, "atp") is None
          and b5.resolve_tennis_player(
              "Alice Smith Jones", _wta_synth, "wta") is None)

    _sample = [dict(m) for m in _rec["markets"][:16]]
    _orig_run_checker = b5.run_checker
    _checker_calls = []

    def _counting_checker(mkt, ctx=None):
        _checker_calls.append(mkt)
        return _orig_run_checker(mkt, ctx)

    b5.run_checker = _counting_checker
    try:
        _first_v, _fp_cache = app._price_markets_cached(
            _sample, _rec, {})
        _first_calls = len(_checker_calls)
        _checker_calls.clear()
        _second_v, _fp_cache = app._price_markets_cached(
            _sample, _rec, _fp_cache)
        _second_calls = len(_checker_calls)
        _changed = [dict(m) for m in _sample]
        _price_idx = [i for i, m in enumerate(_changed)
                      if m.get("price") is not None][:2]
        for _i in _price_idx:
            _changed[_i]["price"] = -105 \
                if _changed[_i]["price"] >= 0 else 125
        _checker_calls.clear()
        _third_v, _fp_cache = app._price_markets_cached(
            _changed, _rec, _fp_cache)
        _changed_calls = len(_checker_calls)
    finally:
        b5.run_checker = _orig_run_checker
    _fresh_changed = b5.run_slate(
        {**_rec, "markets": _changed}, print_out=False)
    check("v12.2: fingerprint cache prices a sample slate once, "
          "then reuses every unchanged verdict",
          _first_calls == len(_sample)
          and _second_calls == 0
          and _second_v == _first_v)
    check("v12.2: fingerprint cache reprices only odds-changed "
          "markets and matches a full fresh pass",
          len(_price_idx) == 2
          and _changed_calls == 2
          and _third_v == _fresh_changed)

    # ---------- v12.3 scoped pull ----------
    # Stub the engine's fetch/parse seams and record every
    # call: the scoped pull must touch ONLY its own sport.
    _fetch_calls = []
    _menu_calls = []
    _orig_fd_get = b5.fd_get
    _orig_parse = b5.fd_parse_sport_page
    _orig_event_menu = b5.fd_event_menu
    _orig_tree = b5.build_menu_tree

    def _stub_get(endpoint, params):
        _fetch_calls.append((endpoint, dict(params or {})))
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
        _menu_calls.append(eid)
        return {"event_id": eid, "markets": []}

    b5.fd_get = _stub_get
    b5.fd_parse_sport_page = _stub_parse
    b5.fd_event_menu = _stub_event_menu
    b5.build_menu_tree = lambda ctx: {"event_types": {},
                                      "az_order": []}
    try:
        _partial = app.pull_menu_sport("nba")
        _sport_params = [p for _e, p in _fetch_calls]
        check("v12.3: scoped pull fetches only its sport's "
              "page (+ its custom page), never the tree",
              _partial["sport"] == "nba"
              and _partial["verified"] is True
              and len(_sport_params) == 2
              and all(p.get("eventTypeId")
                      == b5.FANDUEL_EVENT_TYPES["nba"]
                      or p.get("customPageId") == "nba"
                      for p in _sport_params)
              and not any("dataEntries" in p
                          for p in _sport_params)
              and all(m["sport"] == "nba"
                      for m in _partial["markets"])
              and list(_partial["sports"]) == ["nba"]
              and _partial["sports"]["nba"].get("pulled_at")
              == _partial["pulled_at"])
        check("v12.3: scoped pull makes NO menu fetches — "
              "its partial carries empty menus + a pending "
              "marker naming its own soonest games",
              _menu_calls == []
              and _partial["event_menus"] == {}
              and _partial["menus_pending"]
              == ["stub-nba-1", "stub-nba-2"]
              and _partial["sports"]["nba"].get(
                  "menus_pending")
              == ["stub-nba-1", "stub-nba-2"])
        _fetch_calls.clear()
        _menu_calls.clear()
        _golf = app.pull_menu_sport("golf")
        check("v12.3: a sport with no custom page makes "
              "exactly one fetch",
              len(_fetch_calls) == 1
              and _golf["verified"] is True)

        def _boom(endpoint, params):
            raise RuntimeError("stub offline")
        b5.fd_get = _boom
        _bad = app.pull_menu_sport("nba")
        check("v12.3: a failed scoped pull stamps its error "
              "and prices nothing",
              _bad["verified"] is False
              and "error" in _bad["sports"]["nba"]
              and _bad["markets"] == [])
        b5.fd_get = _stub_get
        _fetch_calls.clear()
        _full = app.pull_menu()
        check("v12.3: full pull unchanged in shape — tree, "
              "all 17 sports, per-sport pulled_at",
              "tree" in _full
              and set(_full["sports"])
              == set(b5.FANDUEL_EVENT_TYPES)
              and all(e.get("pulled_at") == _full["pulled_at"]
                      for e in _full["sports"].values())
              and len(_full["markets"])
              == 3 * len(b5.FANDUEL_EVENT_TYPES))
    finally:
        b5.fd_get = _orig_fd_get
        b5.fd_parse_sport_page = _orig_parse
        b5.fd_event_menu = _orig_event_menu
        b5.build_menu_tree = _orig_tree

    # merge semantics, on synthetic slates
    _t0 = "2026-10-25T10:00:00-04:00"
    _t1 = "2026-10-25T12:00:00-04:00"
    _nfl_m = {"sport": "nfl", "id": "nfl1",
              "fd_event_id": "ev-nfl"}
    _nba_o1 = {"sport": "nba", "id": "nba-old1",
               "fd_event_id": "ev-nba-old"}
    _nba_o2 = {"sport": "nba", "id": "nba-old2",
               "fd_event_id": "ev-nba-old"}
    _soc_m = {"sport": "soccer", "id": "soc1",
              "fd_event_id": "ev-soc"}
    _base_slate = {
        "pulled_at": _t0, "source": app.MENU_SOURCE,
        "verified": True,
        "markets": [_nfl_m, _nba_o1, _nba_o2, _soc_m],
        "sports": {"nfl": {"games": 5, "pulled_at": _t0},
                   "nba": {"games": 4, "pulled_at": _t0}},
        "event_menus": {"ev-nfl": {"event_id": "ev-nfl"},
                        "ev-nba-old": {"event_id": "ev-nba-old"}}}
    _nba_new = {"sport": "nba", "id": "nba-new1",
                "fd_event_id": "ev-nba-new"}
    _partial_nba = {
        "pulled_at": _t1, "source": app.MENU_SOURCE,
        "verified": True, "sport": "nba", "markets": [_nba_new],
        "sports": {"nba": {"games": 3, "pulled_at": _t1}},
        "event_menus": {"ev-nba-new": {"event_id": "ev-nba-new"}}}
    _merged = app.merge_sport_pull(_base_slate, _partial_nba)
    check("v12.3: merge replaces only the pulled sport's "
          "slice (identity + order of the rest untouched)",
          [m["id"] for m in _merged["markets"]]
          == ["nfl1", "nba-new1", "soc1"]
          and _merged["markets"][0] is _nfl_m
          and _merged["markets"][2] is _soc_m)
    check("v12.3: merge keeps each sport's own stamp — the "
          "unpulled sport is not freshened",
          _merged["sports"]["nfl"]["pulled_at"] == _t0
          and _merged["sports"]["nba"]["pulled_at"] == _t1
          and _merged["pulled_at"] == _t1
          and _merged["verified"] is True)
    check("v12.3: merge swaps event menus for the pulled "
          "sport's games only",
          set(_merged["event_menus"])
          == {"ev-nfl", "ev-nba-new"})
    _bad_partial = {
        "pulled_at": _t1, "source": app.MENU_SOURCE,
        "verified": False, "sport": "nba", "markets": [],
        "sports": {"nba": {"error": "RuntimeError: stub offline",
                           "attempted_at": _t1}},
        "event_menus": {}}
    _kept = app.merge_sport_pull(_base_slate, _bad_partial)
    check("v12.3: a failed scoped pull keeps the last-good "
          "slice, stamps untouched, error recorded",
          [m["id"] for m in _kept["markets"]]
          == ["nfl1", "nba-old1", "nba-old2", "soc1"]
          and _kept["sports"]["nba"].get("last_error")
          == "RuntimeError: stub offline"
          and _kept["sports"]["nba"]["pulled_at"] == _t0
          and _kept["pulled_at"] == _t0)
    _empty_partial = {
        "pulled_at": _t1, "source": app.MENU_SOURCE,
        "verified": True, "sport": "nba", "markets": [],
        "sports": {"nba": {"games": 0, "pulled_at": _t1}},
        "event_menus": {}}
    _emptied = app.merge_sport_pull(_base_slate, _empty_partial)
    check("v12.3: a landed pull with zero games truthfully "
          "empties the sport's slice",
          [m["id"] for m in _emptied["markets"]]
          == ["nfl1", "soc1"]
          and _emptied["sports"]["nba"]["games"] == 0)

    # the background menu harvest: menus only, token-guarded
    _pend_partial = {
        "pulled_at": _t1, "source": app.MENU_SOURCE,
        "verified": True, "sport": "nba", "markets": [_nba_new],
        "sports": {"nba": {"games": 3, "pulled_at": _t1,
                           "menus_pending": ["ev-nba-new"]}},
        "event_menus": {}}
    _pend = app.merge_sport_pull(_base_slate, _pend_partial)
    _harv = app.merge_menu_harvest(
        _pend, "nba",
        {"ev-nba-new": {"event_id": "ev-nba-new",
                         "markets": []},
         "ev-not-on-slate": {"event_id": "ev-not-on-slate"}},
        _t1)
    check("v12.3: background harvest merges only the pulled "
          "sport's on-slate menus, clears its pending marker, "
          "and freshens no stamp",
          _harv is not None
          and set(_harv["event_menus"])
          == {"ev-nfl", "ev-nba-new"}
          and "menus_pending" not in _harv["sports"]["nba"]
          and _harv["sports"]["nba"]["pulled_at"] == _t1
          and _harv["pulled_at"] == _t1
          and [m["id"] for m in _harv["markets"]]
          == ["nfl1", "nba-new1", "soc1"])
    _stale = app.merge_menu_harvest(
        _pend, "nba",
        {"ev-nba-new": {"event_id": "ev-nba-new"}}, _t0)
    check("v12.3: a stale-token harvest is dropped whole — "
          "it cannot overwrite a fresher pull's menus or "
          "clear its pending marker",
          _stale is None
          and _pend["sports"]["nba"].get("menus_pending")
          == ["ev-nba-new"]
          and set(_pend["event_menus"]) == {"ev-nfl"})

    # verdicts on an accumulated slate == fresh per-sport
    _nf = [dict(m) for m in _rec["markets"]
           if m.get("sport") == "nfl"][:3]
    _nb = [dict(m) for m in _rec["markets"]
           if m.get("sport") == "ncaaf"][:3]

    def _part(sport, mkts):
        return {"pulled_at": _rec["pulled_at"],
                "source": app.MENU_SOURCE, "verified": True,
                "sport": sport, "markets": mkts,
                "sports": {sport: {"games": 1,
                                   "pulled_at":
                                   _rec["pulled_at"]}},
                "event_menus": {}}
    _acc = app.merge_sport_pull(
        app.merge_sport_pull(None, _part("nfl", _nf)),
        _part("ncaaf", _nb))
    _acc_v, _acc_c = app._price_markets_cached(
        _acc["markets"], _acc, {})
    _fresh_v = []
    for _mm in (_nf, _nb):
        _v, _c = app._price_markets_cached(
            _mm, {**_acc, "markets": _mm}, {})
        _fresh_v += _v
    check("v12.3: verdicts on an accumulated slate equal "
          "fresh per-sport pricing",
          len(_nf) == 3 and len(_nb) == 3
          and _acc["markets"] == _nf + _nb
          and _acc_v == _fresh_v)

    # the chooser on a fresh boot + the auto-pull's target
    page4 = FakePage()
    app.main(page4)
    sw4 = page4.controls[1]
    board4 = sw4.content
    _dds = [c for c in walk(board4)
            if type(c).__name__ == "Dropdown"]
    _chooser = [d for d in _dds
                if len(getattr(d, "options", None) or []) == 17]
    check("v12.3: the board band carries a sport chooser "
          "listing all 17 event types, defaulting to the "
          "persisted sport",
          len(_chooser) == 1
          and [o.key for o in _chooser[0].options]
          == list(b5.FANDUEL_EVENT_TYPES)
          and _chooser[0].value == app.load_chosen_sport())
    check("v12.3: the auto-pull loop ticks the scoped "
          "worker, not the full pull",
          "run_thread(_sport_pull_worker, True)" in _src
          and "run_thread(_pull_worker, True)" not in _src)

    # drive the chooser + Pull end to end on stubs: the
    # saved snapshot must show ONLY nba refreshed.
    _fetch_calls.clear()
    _menu_calls.clear()
    b5.fd_get = _stub_get
    b5.fd_parse_sport_page = _stub_parse
    b5.fd_event_menu = _stub_event_menu
    try:
        _chooser[0].on_select(SimpleNamespace(
            control=SimpleNamespace(value="nba")))

        def _btn_label(c):
            t = getattr(c, "text", None)
            if t:
                return t
            ct = getattr(c, "content", None)
            if isinstance(ct, str):
                return ct
            return getattr(ct, "value", None)
        _pull_btns = [c for c in walk(board4)
                      if type(c).__name__ == "Button"
                      and _btn_label(c) == "Pull"]
        check("v12.3: the band's Pull action is present",
              len(_pull_btns) == 1)
        if _pull_btns:
            _pull_btns[0].on_click(SimpleNamespace())
        _snap = json.load(open(os.path.join(
            STORAGE, "Bet_Finder-last-pull.json")))
        _snap_nba = [m for m in _snap["markets"]
                     if m.get("sport") == "nba"]
        check("v12.3: choosing + pulling a sport refreshes "
              "only that sport in the saved slate",
              len(_pull_btns) == 1
              and len(_snap_nba) == 3
              and all(m.get("home") in ("AAA", "CCC")
                      for m in _snap_nba)
              and any(m.get("sport") == "nfl"
                      for m in _snap["markets"])
              and _snap["sports"]["nba"].get("slate_markets")
              == 3
              and "pulled_at" in _snap["sports"]["nba"]
              and "pulled_at" not in _snap["sports"]["nfl"]
              and len(_fetch_calls) == 2
              and not any("dataEntries" in (p or {})
                          for _e, p in _fetch_calls)
              and app.load_chosen_sport() == "nba"
              and any("Pulled NBA" in t
                      for t in texts(board4)))
        check("v12.3: the background harvest follows the "
              "scoped pull — the saved slate carries the "
              "sport's menus, its pending marker cleared",
              {"stub-nba-1", "stub-nba-2"}
              <= set(_snap["event_menus"])
              and "menus_pending" not in
              _snap["sports"]["nba"])
    finally:
        b5.fd_get = _orig_fd_get
        b5.fd_parse_sport_page = _orig_parse
        b5.fd_event_menu = _orig_event_menu
        app.set_chosen_sport("nfl")

    # ---------- v12.4 startup / dropdowns / diet ----------
    # startup.wav: exists, <25KB, valid WAV, ~700 ms
    _sp = os.path.join(HERE, "assets", "sounds", "startup.wav")
    _sok = os.path.exists(_sp) and os.path.getsize(_sp) < 25000
    if _sok:
        try:
            with _wave.open(_sp) as _w:
                _sdur = _w.getnframes() / _w.getframerate()
            _sok = 0.6 <= _sdur <= 0.8
        except Exception:
            _sok = False
    check("v12.4: startup.wav exists, <25KB, valid WAV of "
          "~700 ms", _sok)
    check("v12.4: the sound registry carries exactly the "
          "four sounds",
          set(app.SOUND_FILES)
          == {"tick", "confirm", "golden", "startup"})

    # the auto-pull gate: never before the first user pull,
    # never while busy, only on a full interval
    _now = 10000.0
    check("v12.4: auto-pull gate — unarmed never ticks, "
          "armed ticks only on a full quiet interval",
          app.auto_pull_should_tick(False, False, 0.0, _now)
          is False
          and app.auto_pull_should_tick(True, True, 0.0, _now)
          is False
          and app.auto_pull_should_tick(
              True, False, _now - 60, _now) is False
          and app.auto_pull_should_tick(
              True, False, _now - app.AUTO_PULL_INTERVAL_S,
              _now) is True
          and app.auto_pull_should_tick(
              True, False, _now - 10, _now, interval=5) is True)
    check("v12.4: the loop consults the gate, and exactly the "
          "three user pull actions arm it",
          "auto_pull_should_tick(" in _src
          and _src.count('state["pull_armed"] = True') == 3)

    # the chooser's cold default is soccer; a persisted pick
    # still wins; unknown values normalize to soccer
    _sport_file = os.path.join(STORAGE,
                               "Bet_Finder-sport.json")
    _prev_sport = app.load_chosen_sport()
    try:
        if os.path.exists(_sport_file):
            os.remove(_sport_file)
        _cold = app.load_chosen_sport()
        _norm = app.set_chosen_sport("not-a-sport")
    finally:
        app.set_chosen_sport(_prev_sport)
    check("v12.4: first-pull chooser default is soccer "
          "(persisted picks still win)",
          _cold == "soccer" and _norm == "soccer"
          and app.load_chosen_sport() == _prev_sport)

    # the startup sound fires exactly once per cold boot
    _played = []
    _orig_play = app.play_sound
    app.play_sound = lambda name: _played.append(name)
    try:
        page5 = FakePage()
        app.main(page5)
    finally:
        app.play_sound = _orig_play
    check("v12.4: play_sound('startup') is invoked exactly "
          "once on a cold boot",
          _played == ["startup"], f"played={_played}")
    # ...and it no-ops when muted (a fake control counts plays)
    _plays = {"n": 0}
    _real_ctrl = app._SOUND["controls"].get("startup")
    app._SOUND["controls"]["startup"] = SimpleNamespace(
        play=lambda: _plays.__setitem__("n", _plays["n"] + 1))
    try:
        app.set_sound_enabled(False)
        app.play_sound("startup")
        _muted_plays = _plays["n"]
        app.set_sound_enabled(True)
        app.play_sound("startup")
    finally:
        if _real_ctrl is not None:
            app._SOUND["controls"]["startup"] = _real_ctrl
        app.set_sound_enabled(True)
    check("v12.4: the startup sound no-ops when muted, "
          "plays when on",
          _muted_plays == 0 and _plays["n"] == 1)

    # the two board dropdowns on a fresh boot: exact option
    # sets, startup values, zero board switches; driving the
    # sport view filters the cards to that sport alone
    sw5 = page5.controls[1]
    board5 = sw5.content
    bsw5 = [c for c in walk(board5)
            if type(c).__name__ == "AnimatedSwitcher"]
    cards5 = bsw5[0].content
    # page5 restores the accumulated snapshot the v12.3 drive
    # left on disk (fixture sports + the stub NBA slice) — the
    # sport-view options must mirror THAT slate's sports.
    _snap5 = json.load(open(os.path.join(
        STORAGE, "Bet_Finder-last-pull.json")))
    _pres5 = []
    for _m5 in _snap5["markets"]:
        _s5 = _m5.get("sport")
        if _s5 is not None and _s5 not in _pres5:
            _pres5.append(_s5)
    _ord5 = ["nfl", "ncaaf", "nba", "nhl", "mlb", "soccer"]
    _pres5.sort(key=lambda s: _ord5.index(s)
                if s in _ord5 else 99)
    _exp5 = ["all"] + _pres5
    _dds5 = [c for c in walk(cards5)
             if type(c).__name__ == "Dropdown"]
    _show5 = next(d for d in _dds5
                  if [o.key for o in d.options]
                  == [k for k, _t in app.SHOW_MODES])
    _sv5 = next(d for d in _dds5
                if [o.key for o in d.options] == _exp5)
    check("v12.4: the board's Show dropdown carries exactly "
          "the five views, in order, with their labels",
          [o.key for o in _show5.options]
          == ["all", "priced", "golden", "quick", "nodnb"]
          and [o.text for o in _show5.options]
          == [t for _k, t in app.SHOW_MODES])
    check("v12.4: the Board shows dropdown is All sports + "
          "the slate's sports, at its startup values",
          [o.key for o in _sv5.options] == _exp5
          and _sv5.value == "all" and _show5.value == "all"
          and not any(type(c).__name__ == "Switch"
                      for c in walk(board5)))
    _show5.on_select(SimpleNamespace(
        control=SimpleNamespace(value="all")))
    _sv5.on_select(SimpleNamespace(
        control=SimpleNamespace(value="nfl")))
    _n_nfl = sum(1 for m in _snap5["markets"]
                 if m.get("sport") == "nfl")
    _find_ct = sum(1 for c in walk(cards5)
                   if type(c).__name__ == "GestureDetector")
    check("v12.4: sport-view drive shows only NFL cards",
          _find_ct == min(_n_nfl, app.CARD_PAGE),
          f"cards={_find_ct} nfl={_n_nfl}")
    # v12.4.3 armor: poison ONE sport's builds — the board
    # must keep the other sport's real cards AND land the
    # drawn fallback row for the poisoned sport (the device
    # blank-board failure mode, made impossible and
    # self-reporting). v12.11 re-home: the poison seam is
    # the internal builder (_card_control); the fallback is
    # asserted as a drawn image — a bare Image child of the
    # card list whose bytes equal a direct fallback draw
    # for some poisoned-sport market, decoding at row
    # geometry — and real detector cards survive beside it.
    _orig_bmc = app._card_control

    def _poison(mkt, verdict, rec, quotes, **kw):
        if mkt.get("sport") == "ncaaf":
            raise RuntimeError("probe-boom")
        return _orig_bmc(mkt, verdict, rec, quotes, **kw)
    app._card_control = _poison
    try:
        _sv5.on_select(SimpleNamespace(
            control=SimpleNamespace(value="all")))
    finally:
        app._card_control = _orig_bmc
    _lists5b = [c for c in walk(cards5)
                if type(c).__name__ == "Column"]
    _clist5b = max(_lists5b, key=lambda c: sum(
        1 for x in getattr(c, "controls", [])
        if type(x).__name__ == "GestureDetector"))
    _fb_expect = {
        app._card_fallback_png(_m, _v,
                               RuntimeError("probe-boom"))
        for _m, _v in zip(_snap5["markets"],
                          b5.run_slate(_snap5,
                                       print_out=False))
        if _m.get("sport") == "ncaaf"}
    _fb_landed = [x for x in _clist5b.controls
                  if type(x).__name__ == "Image"
                  and getattr(x, "src", None) in _fb_expect]
    check("v12.4.3 armor: a raising card build cannot empty "
          "the board — fallback card prints the error, real "
          "cards survive",
          bool(_fb_landed)
          and _PIL_Image.open(io.BytesIO(
              _fb_landed[0].src)).size == (1170, 177)
          and any(type(x).__name__ == "GestureDetector"
                  for x in _clist5b.controls))

    # the serialization smoke gate's coverage, kept: scan
    # THIS fully-driven board tree for set-valued control
    # fields — the 11.0.1 crash class. (The comment this
    # replaces credited the old golden startup view for the
    # small boot tree; the scan never depended on it.)
    import dataclasses as _dc

    def _set_hits(_v, _depth=0):
        if _depth > 12:
            return 0
        if isinstance(_v, (set, frozenset)):
            return 1
        if isinstance(_v, dict):
            return sum(_set_hits(x, _depth + 1)
                       for x in _v.values())
        if isinstance(_v, (list, tuple)):
            return sum(_set_hits(x, _depth + 1) for x in _v)
        if _dc.is_dataclass(_v) and not isinstance(_v, type):
            _n = 0
            for _f in _dc.fields(_v):
                try:
                    _n += _set_hits(getattr(_v, _f.name),
                                    _depth + 1)
                except Exception:
                    pass
            return _n
        return 0
    _hits5 = 0
    _seen5 = 0
    _roots5 = list(page5.controls)
    if page5.navigation_bar is not None:
        _roots5.append(page5.navigation_bar)
    for _r5 in _roots5:
        for _c5 in walk(_r5):
            _seen5 += 1
            if _dc.is_dataclass(_c5) \
                    and not isinstance(_c5, type):
                for _f5 in _dc.fields(_c5):
                    try:
                        _hits5 += _set_hits(getattr(_c5, _f5.name))
                    except Exception:
                        pass
    check("v12.11 re-pin (was v12.4, floor re-pinned in "
          "v12.7 and kept in v12.8): the full board tree "
          "carries no set-valued control fields (smoke-gate "
          "coverage, kept) — the seen floor is re-pinned "
          "to 80 in v12.11: an image card is two controls "
          "(detector + image) where 11's widget card was "
          "dozens, so the same fully-driven tree now walks "
          "at 95; the gate's substance (zero set-valued "
          "fields) is unchanged",
          _seen5 > 80 and _hits5 == 0,
          f"seen={_seen5} hits={_hits5}")

    # the splash builder: emblem + wordmark + gold sweep, and
    # the loop budget stands (splash pulse is the same key)
    _splash = app.build_splash()
    _imgs = [c for c in walk(_splash)
             if type(c).__name__ == "Image"]
    check("v12.4: the splash centers the new emblem, the "
          "BetFi Xii wordmark and one gold sweep line",
          len(_imgs) == 1
          and _imgs[0].src == "assets/icon.png"
          and any(t == "BetFi " for t in texts(_splash))
          and any(t == "Xii" for t in texts(_splash))
          and any(getattr(c, "gradient", None)
                  is app.GOLD_GRADIENT
                  for c in walk(_splash))
          and len(app._PULSE_TARGETS.get("splash") or []) == 1
          and len(app.PULSE_PERIODS) <= 6)
    _glow1 = (app._PULSE_TARGETS.get("splash") or [None])[0]
    check("v12.4.1: the splash is BORN VIEWABLE — every "
          "element at its final opacity from the first frame "
          "(only the breathing glow layer starts dark)",
          all(getattr(c, "opacity", 1) in (None, 1, 1.0)
              for c in walk(_splash) if c is not _glow1))
    _stamp5 = next(
        (c for c in walk(page5)
         if type(c).__name__ == "Text"
         and str(getattr(c, "value", "")).startswith("Menu:")),
        None)
    check("v12.4.2: the header menu stamp ellipsizes inside "
          "its row — no Flutter overflow at phone width (the "
          "error stripe on the Pilot's 17:43 screenshot)",
          _stamp5 is not None
          and _stamp5.expand
          and str(_stamp5.overflow) == "TextOverflow.ELLIPSIS")

    # render diet: the harvest worker saves and renders
    # nothing (source-pinned — the worker is a closure, so
    # its body is sliced from the shell source)
    _hw = _src[_src.index("def _menu_harvest_worker"):
               _src.index("def _sport_pull_worker")]
    check("v12.4: harvest completion renders nothing — it "
          "merges menus and saves the snapshot only",
          "save_snapshot" in _hw and "render_" not in _hw
          and "page.update" not in _hw)

    # ---------- v12.6 motion (gold checks re-pinned in
    # v12.11: cards are drawn pictures — the gold lives in
    # the drawing (stripe + wash on Board rows, border +
    # wash on Finds tickets); view-level settles and the
    # glow-owned pulse key stand) ----------
    # Fabricate GOLDEN BET cards on page5's board: the first
    # two markets the patched builder sees get an injected
    # GOLDEN BET verdict (the fixture pull has none). The
    # board is at Show=all / sport=all from the v12.4 drives.
    _orig_bmc6 = app._card_control
    _orig_distill6 = app.distill_finds
    _gold_keys6 = []
    _gold_set6 = set()

    def _mkey6(mkt):
        return mkt.get("fd_market_id") or (
            mkt.get("sport"), mkt.get("away"),
            mkt.get("home"), mkt.get("name"))

    def _gold_bmc(mkt, verdict, rec, quotes, **kw):
        _k6 = _mkey6(mkt)
        if _k6 not in _gold_set6 and len(_gold_keys6) < 2:
            _gold_keys6.append(_k6)
            _gold_set6.add(_k6)
        if _k6 in _gold_set6:
            verdict = dict(verdict)
            verdict["verdict"] = "GOLDEN BET"
        return _orig_bmc6(mkt, verdict, rec, quotes, **kw)

    def _gold_distill(markets, verdicts):
        _g, _f, _fl, _c = _orig_distill6(markets, verdicts)
        _moved = [t for t in _f if _mkey6(t[0]) in _gold_set6]
        _rest = [t for t in _f if _mkey6(t[0]) not in _gold_set6]
        return _moved + _g, _rest, _fl, _c

    app._card_control = _gold_bmc
    try:
        # pull-order sort for this drive: the accumulated
        # slate prices to many real goldens and the verdict
        # sort would fill the whole first page with them —
        # pull order mixes the two injected goldens (the
        # first two built) with plain cards in the animated
        # first eight.
        _sort6 = next(c for c in walk(cards5)
                      if type(c).__name__ == "Dropdown"
                      and [o.key for o in c.options]
                      == [k for k, _t in app.SORT_MODES])
        _sort6.on_select(SimpleNamespace(
            control=SimpleNamespace(value="pull")))
        _price6 = next(c for c in walk(cards5)
                       if type(c).__name__ == "Button"
                       and getattr(c, "content", None)
                       == "Price Slate")
        _price6.on_click(SimpleNamespace())
    finally:
        app._card_control = _orig_bmc6
    _lists6 = [c for c in walk(cards5)
               if type(c).__name__ == "Column"]
    _clist6 = max(_lists6, key=lambda c: sum(
        1 for x in getattr(c, "controls", [])
        if type(x).__name__ == "GestureDetector"))
    _cards6 = [x for x in _clist6.controls
               if type(x).__name__ == "GestureDetector"]
    _gcard6 = _cards6[0] if _cards6 else None

    def _stripe6(c):
        return _PIL_Image.open(io.BytesIO(
            c.content.src)).getpixel((4, 88))
    _gold6 = next((c for c in _cards6
                   if _stripe6(c) == (245, 196, 81)), None)
    _gim6 = _PIL_Image.open(io.BytesIO(
        _gold6.content.src)) if _gold6 is not None else None
    _wash6 = _gim6.getpixel((600, 6)) if _gim6 else None
    check("v12.11: a golden card is a drawn row \u2014 gold "
          "stripe, gold wash across the top rows, no data "
          "tag, no entrance/bloom state (re-homes the "
          "v12.8 construction pin)",
          _gold6 is not None
          and _wash6 is not None
          and _wash6 != app._rgb(app.CARD_BG)
          and _wash6[0] > 30
          and getattr(_gold6, "data", None) is None
          and _gold6.animate_scale is None
          and _gold6.animate_offset is None
          and getattr(_gold6, "opacity", 1) == 1)
    _plain6 = next((c for c in _cards6
                    if _stripe6(c) != (245, 196, 81)), None)
    check("v12.8: non-golden cards carry no entrance state "
          "either (no scale, no offset animation)",
          _plain6 is not None
          and _plain6.animate_scale is None
          and _plain6.animate_offset is None)
    _tg6 = app._PULSE_TARGETS.get("golden") or []
    check("v12.7 re-pin (was v12.6 board gold bars): the "
          "board render publishes NO card bars to the golden "
          "pulse — the key stays empty or glow-only (no "
          "height-3 bar targets)",
          all(getattr(t, "height", None) != 3 for t in _tg6),
          f"targets={len(_tg6)}")

    # Finds: route the same two markets into the golden
    # loop — the pulse set must lead with the glow bar.
    app._card_control = _gold_bmc
    app.distill_finds = _gold_distill
    try:
        _seg6 = next(c for c in walk(board5)
                     if type(c).__name__ == "SegmentedButton")
        _seg6.on_change(SimpleNamespace(
            control=SimpleNamespace(selected={"finds"})))
    finally:
        app._card_control = _orig_bmc6
        app.distill_finds = _orig_distill6
    _betfi6 = bsw5[0].content
    _tg6f = app._PULSE_TARGETS.get("golden") or []
    check("v12.7 re-pin (was v12.6 Finds pulse set): the "
          "Finds golden pulse is the glow bar ALONE — no "
          "card bars ride it anymore",
          len(_tg6f) == 1
          and _tg6f[0].height == 6
          and _tg6f[0].bgcolor == app.GOLD,
          f"targets={len(_tg6f)}")
    def _gold_ticket6(c):
        _im = _PIL_Image.open(io.BytesIO(c.content.src))
        return _im.size == (1170, 408) \
            and _im.getpixel((2, 204)) == (245, 196, 81) \
            and _im.getpixel((600, 6)) != app._rgb(app.CARD_BG)
    _fcards6 = [c for c in walk(_betfi6)
                if type(c).__name__ == "GestureDetector"
                and _gold_ticket6(c)]
    check("v12.11: a Finds golden card is a drawn ticket "
          "\u2014 gold border + gold wash on the ticket "
          "(re-homes the v12.8 construction pin)",
          len(_fcards6) >= 1)
    check("v12.6: the board segment switch settles the "
          "incoming segment view (scale + offset animations "
          "armed, two-update)",
          _betfi6.animate_scale is not None
          and _betfi6.animate_offset is not None
          and _betfi6.scale is not None
          and _betfi6.scale.scale == 1.0)
    _seg6.on_change(SimpleNamespace(
        control=SimpleNamespace(selected={"all"})))

    # page transition: nav to Lab settles the incoming view
    page5.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=2)))
    _lab6 = sw5.content
    check("v12.6: show() settles the incoming view on a "
          "page transition",
          _lab6.animate_scale is not None
          and _lab6.animate_offset is not None
          and _lab6.scale is not None
          and _lab6.scale.scale == 1.0)
    page5.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=3)))
    _stage6 = sw5.content
    _pseg6 = next(c for c in walk(_stage6)
                  if type(c).__name__ == "SegmentedButton")
    _pseg6.on_change(SimpleNamespace(
        control=SimpleNamespace(selected={"coverage"})))
    _psw6 = next(c for c in walk(_stage6)
                 if type(c).__name__ == "AnimatedSwitcher")
    check("v12.6: the panel segment switch settles the "
          "incoming segment container",
          _psw6.content.animate_scale is not None
          and _psw6.content.animate_offset is not None
          and _psw6.content.scale is not None
          and _psw6.content.scale.scale == 1.0)
    _pseg6.on_change(SimpleNamespace(
        control=SimpleNamespace(selected={"charts"})))
    _vbtn6 = next(c for c in walk(_stage6)
                  if type(c).__name__ == "Button"
                  and getattr(c, "content", None)
                  == "Full screen — charts")
    _vbtn6.on_click(SimpleNamespace())
    _sheet6 = page5.overlay[-1] if page5.overlay else None
    check("v12.6: the full-screen viewer opens with a "
          "0.96 -> 1.0 settle (240 ms), ending at identity",
          _sheet6 is not None
          and _sheet6.animate_scale is not None
          and _sheet6.animate_scale.duration == 240
          and _sheet6.scale is not None
          and _sheet6.scale.scale == 1.0)

    # the settle helper obeys the same visibility law as
    # the card entrance: no opacity assignment anywhere in
    # its body (source pin)
    _si = _src[_src.index("def _settle_in"):
               _src.index("def build_card_safe")]
    check("v12.6: _settle_in never touches opacity "
          "(source pin — the load-bearing-visibility rule)",
          ".opacity" not in _si)

    # ---------- v12.7.1 one lock ----------
    # Every screen update is serialized through ONE module
    # RLock: the pulse ticks, every list-mutating render, the
    # nav swap, the workers' trailing updates — so a pulse
    # tick can never interleave with a render's bulk patch
    # (the on-device torn-patch / blank-board failure).
    import threading as _threading
    _lk = app._UPDATE_LOCK
    _lk_acq = _lk.acquire(timeout=2)
    _lk_re = _lk.acquire(timeout=2) if _lk_acq else False
    if _lk_re:
        _lk.release()
    if _lk_acq:
        _lk.release()
    check("v12.7.1: _UPDATE_LOCK is a module-level RLock "
          "(re-acquirable by its holder)",
          _lk_acq and _lk_re)

    def _fn_slice7(name):
        i = _src.index(f"def {name}")
        j = _src.index("\n    def ", i + 1)
        return _src[i:j]

    _pulse_src = _src[_src.index("def ice_pulse_loop"):
                      _src.index("def start_pulse")]
    check("v12.7.1: ice_pulse_loop wraps its tick in "
          "_UPDATE_LOCK (inside the while — never held "
          "across a wait)",
          "with _UPDATE_LOCK:" in _pulse_src
          and _pulse_src.index("with _UPDATE_LOCK:")
          > _pulse_src.index("while not stop.is_set():"))
    check("v12.7.1: render_cards runs inside _UPDATE_LOCK "
          "(source pin)",
          "_UPDATE_LOCK" in _fn_slice7("render_cards"))
    check("v12.7.1: render_betfi runs inside _UPDATE_LOCK "
          "(source pin)",
          "_UPDATE_LOCK" in _fn_slice7("render_betfi"))
    check("v12.7.1: render_protected runs inside "
          "_UPDATE_LOCK (source pin)",
          "_UPDATE_LOCK" in _fn_slice7("render_protected"))
    _rc_src = _fn_slice7("render_cards")
    check("v12.7.1: render_cards writes the render receipt "
          "(source pin — the one-pending 0.35s re-assert it "
          "once scheduled was retired by 12.10's batched "
          "applier and exists nowhere in the app anymore)",
          "cards_receipt" in _rc_src
          and "Rendered:" in _rc_src
          and "_reassert_board" not in _src
          and "_REASSERT_PENDING" not in _src)

    # Concurrency guard: hammer pulse-style locked updates
    # from several threads WHILE repeatedly re-rendering the
    # board through its own Price Slate path. This guards OUR
    # lock discipline / deadlock-freedom — it does not claim
    # to reproduce the client's dropped patch.
    page7 = FakePage()
    app.main(page7)
    sw7 = page7.controls[1]
    board7 = sw7.content
    bsw7 = [c for c in walk(board7)
            if type(c).__name__ == "AnimatedSwitcher"]
    cards7 = bsw7[0].content
    _show7 = next(c for c in walk(cards7)
                  if type(c).__name__ == "Dropdown"
                  and [o.key for o in c.options]
                  == [k for k, _t in app.SHOW_MODES])
    _show7.on_select(SimpleNamespace(
        control=SimpleNamespace(value="all")))

    def _btn_label7(c):
        ct = getattr(c, "content", None)
        if isinstance(ct, str):
            return ct
        return getattr(ct, "value", None)
    _price7 = next(c for c in walk(cards7)
                   if type(c).__name__ == "Button"
                   and _btn_label7(c) == "Price Slate")
    _price7.on_click(SimpleNamespace())
    _lists7 = [c for c in walk(cards7)
               if type(c).__name__ == "Column"]
    _clist7 = max(_lists7, key=lambda c: sum(
        1 for x in getattr(c, "controls", [])
        if type(x).__name__ == "GestureDetector"))

    def _card_count7():
        return sum(1 for x in _clist7.controls
                   if type(x).__name__ == "GestureDetector")
    _expected7 = _card_count7()

    class _HammerCtrl:
        """A pulse-style target: opacity writes + update(),
        the update a no-op counter (the FakePage convention)."""

        def __init__(self):
            self.opacity = 1.0
            self.updates = 0

        def update(self):
            self.updates += 1

    _hammer = _HammerCtrl()
    _saved_golden7 = app._PULSE_TARGETS.get("golden")
    app._PULSE_TARGETS["golden"] = [_hammer]
    _errors7 = []
    _stop7 = _threading.Event()

    def _pulse_hammer():
        try:
            while not _stop7.is_set():
                # the pulse tick's exact shape: the whole
                # tick inside the one lock
                with app._UPDATE_LOCK:
                    for ctrl in list(
                            app._PULSE_TARGETS.get("golden")
                            or [])[:3]:
                        ctrl.opacity = 0.4
                        ctrl.update()
        except Exception as e:  # noqa: BLE001 - recorded
            _errors7.append(e)

    def _render_hammer():
        try:
            for _ in range(6):
                _price7.on_click(SimpleNamespace())
        except Exception as e:  # noqa: BLE001 - recorded
            _errors7.append(e)

    _ths7 = [_threading.Thread(target=_pulse_hammer)
             for _ in range(3)]
    _ths7 += [_threading.Thread(target=_render_hammer)
              for _ in range(3)]
    for _t in _ths7:
        _t.start()
    for _t in _ths7[3:]:
        _t.join()
    _stop7.set()
    for _t in _ths7[:3]:
        _t.join()
    app._PULSE_TARGETS["golden"] = _saved_golden7 or []
    check("v12.7.1: pulse-style locked updates hammered "
          "during repeated board renders — no exception "
          "escapes, no deadlock, and the board still holds "
          "exactly the expected cards",
          not _errors7 and _expected7 > 0
          and _card_count7() == _expected7
          and _hammer.updates > 0,
          f"errors={_errors7!r} final={_card_count7()} "
          f"expected={_expected7}")

    # ---------- v12.10 event-loop batched applier ----------
    check("v12.10: batched applier present — _run_apply + "
          "_dispatch_apply exist, jobs are dispatched via "
          "page.run_task, and the deferred re-ship exists "
          "nowhere in the app (source pins)",
          "async def _run_apply(" in _src
          and "def _dispatch_apply(" in _src
          and "page.run_task(_run_apply" in _src
          and "def _chunk3(" in _src
          and "_reassert_board" not in _src
          and "_REASSERT_PENDING" not in _src)
    check("v12.10: render_cards and render_betfi both "
          "dispatch apply jobs (source pins)",
          "_dispatch_apply(" in _fn_slice7("render_cards")
          and "_dispatch_apply(" in _fn_slice7("render_betfi"))

    # Functional: a fresh boot + the standard Price Slate
    # drive. The fake's run_task now executes dispatched
    # coroutines to completion, so when the drive returns
    # the applier must have run to completion: the board
    # holds the full card count, the receipt names it, and
    # the render arrived as a stream of updates (reset +
    # batches + finish), not one bulk patch.
    page10 = FakePage()
    app.main(page10)
    sw10 = page10.controls[1]
    board10 = sw10.content
    bsw10 = [c for c in walk(board10)
             if type(c).__name__ == "AnimatedSwitcher"]
    cards10 = bsw10[0].content
    _show10 = next(c for c in walk(cards10)
                   if type(c).__name__ == "Dropdown"
                   and [o.key for o in c.options]
                   == [k for k, _t in app.SHOW_MODES])
    _show10.on_select(SimpleNamespace(
        control=SimpleNamespace(value="all")))

    def _btn_label10(c):
        ct = getattr(c, "content", None)
        if isinstance(ct, str):
            return ct
        return getattr(ct, "value", None)
    _price10 = next(c for c in walk(cards10)
                    if type(c).__name__ == "Button"
                    and _btn_label10(c) == "Price Slate")
    _lists10 = [c for c in walk(cards10)
                if type(c).__name__ == "Column"]
    _clist10 = max(_lists10, key=lambda c: sum(
        1 for x in getattr(c, "controls", [])
        if type(x).__name__ == "GestureDetector"))

    def _card_count10():
        return sum(1 for x in _clist10.controls
                   if type(x).__name__ == "GestureDetector")
    _before10 = page10.updates
    _price10.on_click(SimpleNamespace())
    _delta10 = page10.updates - _before10
    _n10 = _card_count10()
    _receipt10 = next(
        (c for c in walk(cards10)
         if type(c).__name__ == "Text"
         and (getattr(c, "value", "") or "")
         .startswith("Rendered:")), None)
    check("v12.10: the applier runs to completion under "
          "the fake — after the Price Slate drive the board "
          "holds the full expected card count and the "
          "receipt names it",
          _n10 >= 10
          and _receipt10 is not None
          and _receipt10.value
          == f"Rendered: {_n10} cards on this board",
          f"cards={_n10} receipt="
          f"{getattr(_receipt10, 'value', None)}")
    check("v12.10: a board apply streams — reset + batches "
          "of <=3 + finish produce at least 4 page updates "
          "for one render (never one bulk patch)",
          _n10 >= 10 and _delta10 >= 4,
          f"updates during one render={_delta10} "
          f"cards={_n10}")

    # Supersession, driven directly against the applier: a
    # job whose stamp is already stale lands nothing (its
    # reset never runs); the current job lands fully; a job
    # superseded mid-stream stops before its next batch.
    _fp10 = FakePage()
    _cell10 = {"n": 2}
    _landed10 = []
    _resets10 = []

    def _job10(seq, tag, batches):
        return {"page": _fp10,
                "reset": lambda t=tag: _resets10.append(t),
                "batches": batches,
                "extend": lambda b: _landed10.extend(b),
                "finish": None,
                "is_current":
                    lambda s=seq: _cell10["n"] == s,
                "status": None}
    _lp10 = asyncio.new_event_loop()
    try:
        _lp10.run_until_complete(
            app._run_apply(_job10(1, "stale", [["x"]])))
        _lp10.run_until_complete(app._run_apply(
            _job10(2, "fresh", [["y1"], ["y2"]])))
        _flip10 = {"n": 0}

        def _flaky10():
            _flip10["n"] += 1
            return _flip10["n"] <= 2
        _landed10b = []
        _job10b = {"page": _fp10,
                   "reset": lambda: None,
                   "batches": [[1], [2], [3]],
                   "extend": lambda b: _landed10b.extend(b),
                   "finish": None,
                   "is_current": _flaky10,
                   "status": None}
        _lp10.run_until_complete(app._run_apply(_job10b))
    finally:
        _lp10.close()
    check("v12.10: supersession — a stale job lands "
          "nothing, the current job lands fully, and a job "
          "superseded mid-stream stops before its next "
          "batch",
          _landed10 == ["y1", "y2"]
          and _resets10 == ["fresh"]
          and _landed10b == [1],
          f"landed={_landed10} resets={_resets10} "
          f"mid-stream={_landed10b}")

    # ---------- v12.11: the ImageBoard (the mix) ----------
    # Board = Design C rows; Finds + Parse = Design B
    # tickets. (f) armor is covered above by the re-homed
    # v12.4.3 check (poisoned _card_control -> drawn
    # fallback row, byte-matched, real cards survive).
    # (a) the widget card system is gone from the source,
    # pillow is pinned, the bundled fonts exist.
    check("v12.11: widget card system deleted from source "
          "(no card builder, no depth-tile helper, no "
          "diagnostic ladder)",
          "def build_market_card" not in _src
          and "def _tile(" not in _src
          and "DIAGNOSTIC_LADDER" not in _src
          and "def _diag_" not in _src)
    check("v12.11: pillow pinned in requirements and the "
          "bundled DejaVu faces exist in assets/fonts",
          "pillow==12.3.0" in _req
          and all(os.path.exists(os.path.join(
              HERE, "assets", "fonts", _ff)) for _ff in (
                  "DejaVuSans.ttf", "DejaVuSans-Bold.ttf",
                  "DejaVuSansMono.ttf",
                  "DejaVuSansMono-Bold.ttf")))

    # (b) renderer determinism + geometry + pixels, BOTH
    # drawers, on one fixture market/verdict.
    _pairs11 = [(m, v) for m, v in zip(
        _rec["markets"], b5.run_slate(_rec, print_out=False))
        if v.get("p") is not None
        and m.get("price") is not None]
    _m11, _v11 = _pairs11[0]
    _e11 = app.market_edge_pts(_m11, _v11)
    _c11a = app.draw_row_c(_m11, _v11, _e11)
    _c11b = app.draw_row_c(_m11, _v11, _e11)
    _cim11 = _PIL_Image.open(io.BytesIO(_c11a))
    _b11a = app.draw_ticket_b(_m11, _v11, _e11)
    _b11b = app.draw_ticket_b(_m11, _v11, _e11)
    _bim11 = _PIL_Image.open(io.BytesIO(_b11a))
    check("v12.11: Design C row is deterministic, exactly "
          "1170x177, stripe pixel is the verdict color, "
          "headline zone carries ink-bright pixels",
          _c11a == _c11b and _cim11.size == (1170, 177)
          and _cim11.getpixel((4, 88))
          == app._card_accent_rgb(_v11)
          and any(max(_px) > 200 for _px in
                  _cim11.crop((42, 24, 540, 66)).getdata()))
    check("v12.11: Design B ticket is deterministic, "
          "exactly 1170x408, selection zone carries "
          "ink-bright pixels",
          _b11a == _b11b and _bim11.size == (1170, 408)
          and any(max(_px) > 200 for _px in
                  _bim11.crop((51, 84, 750, 150)).getdata()))
    _gv11 = dict(_v11)
    _gv11.update(verdict="GOLDEN BET", state="PRICED",
                 p=0.62, grade="A")
    _gc11 = _PIL_Image.open(io.BytesIO(
        app.draw_row_c(_m11, _gv11, 5.0)))
    _gb11 = _PIL_Image.open(io.BytesIO(
        app.draw_ticket_b(_m11, _gv11, 5.0)))
    _bg_rgb11 = app._rgb(app.CARD_BG)
    check("v12.11: GOLDEN draws carry the gold — C: gold "
          "stripe + wash; B: gold border + wash",
          _gc11.getpixel((4, 88)) == (245, 196, 81)
          and _gc11.getpixel((600, 6)) != _bg_rgb11
          and _gc11.getpixel((600, 6))[0] > 30
          and _gb11.getpixel((2, 204)) == (245, 196, 81)
          and _gb11.getpixel((600, 6)) != _bg_rgb11
          and _gb11.getpixel((600, 6))[0] > 30)
    check("v12.11: skeletons draw in both silhouettes "
          "(C row 1170x177, B ticket block 1170x408)",
          _PIL_Image.open(io.BytesIO(
              app.skeleton_cards()[0].src)).size
          == (1170, 177)
          and _PIL_Image.open(io.BytesIO(
              app.skeleton_cards(2, "B")[0].src)).size
          == (1170, 408))

    # (c)+(d)+(e): one fresh boot drives the standard
    # Price Slate path; every card on the Board byte-matches
    # a direct Design C draw, every card on Finds a direct
    # Design B draw; taps expand (byte-equal to direct
    # expanded draws) and the SLIP zone routes to the
    # Protected Slip panel.
    app._CARD_DETAILS_OPEN.clear()
    page11 = FakePage()
    app.main(page11)
    sw11 = page11.controls[1]
    board11 = sw11.content
    bsw11 = [c for c in walk(board11)
             if type(c).__name__ == "AnimatedSwitcher"]
    cards11 = bsw11[0].content
    _show11 = next(c for c in walk(cards11)
                   if type(c).__name__ == "Dropdown"
                   and [o.key for o in c.options]
                   == [k for k, _t in app.SHOW_MODES])
    _show11.on_select(SimpleNamespace(
        control=SimpleNamespace(value="all")))

    def _btn_label11(c):
        ct = getattr(c, "content", None)
        if isinstance(ct, str):
            return ct
        return getattr(ct, "value", None)
    _price11 = next(c for c in walk(cards11)
                    if type(c).__name__ == "Button"
                    and _btn_label11(c) == "Price Slate")
    _price11.on_click(SimpleNamespace())
    # The app's slate at this point in the run is the
    # CURRENT last-pull file (earlier drives grow the
    # accumulated snapshot) — the integration maps are
    # built from the very record the app just priced.
    _fresh11 = json.load(open(os.path.join(
        STORAGE, "Bet_Finder-last-pull.json")))
    _mkts11 = _fresh11["markets"]
    _vrd11 = b5.run_slate(_fresh11, print_out=False)
    _q11 = app.game_quotes(_mkts11)
    _ctx11 = app.lane_contexts(_mkts11)
    _cmap11 = {}
    for _m, _v in zip(_mkts11, _vrd11):
        _cmap11[app.draw_row_c(
            _m, _v, app.market_edge_pts(_m, _v))] = (_m, _v)

    def _board_dets11():
        _ls = [c for c in walk(cards11)
               if type(c).__name__ == "Column"]
        _cl = max(_ls, key=lambda c: sum(
            1 for x in getattr(c, "controls", [])
            if type(x).__name__ == "GestureDetector"))
        return [x for x in _cl.controls
                if type(x).__name__ == "GestureDetector"]
    _dets11 = _board_dets11()
    _receipt11 = next(
        (c for c in walk(cards11)
         if type(c).__name__ == "Text"
         and (getattr(c, "value", "") or "")
         .startswith("Rendered:")), None)
    check("v12.11: board integration — every Board card is "
          "a GestureDetector whose image byte-matches a "
          "direct Design C draw of the same inputs, and "
          "the receipt names the count",
          bool(_dets11)
          and all(c.content.src in _cmap11 for c in _dets11)
          and all(_PIL_Image.open(io.BytesIO(
              c.content.src)).size == (1170, 177)
              for c in _dets11)
          and _receipt11 is not None
          and _receipt11.value
          == f"Rendered: {len(_dets11)} cards on this board",
          f"dets={len(_dets11)} receipt="
          f"{getattr(_receipt11, 'value', None)}")

    def _tap11(det, x, y):
        det.on_tap(SimpleNamespace(
            control=det,
            local_position=SimpleNamespace(x=x, y=y)))
    # (d) C expansion: byte-equal to a direct expanded draw.
    _det11 = _dets11[0]
    _m11b, _v11b = _cmap11[_det11.content.src]
    _tap11(_det11, 100, 10)
    _dets11x = _board_dets11()
    _exp_c11 = app._card_png_expanded(
        _m11b, _v11b, _fresh11, _q11,
        edge_pts=app.market_edge_pts(_m11b, _v11b),
        lane_ctx=_ctx11)[0]
    _xdet11 = next((c for c in _dets11x
                    if c.content.src == _exp_c11), None)
    check("v12.11: tapping a Board row expands it — the "
          "replacement image byte-matches a direct expanded "
          "draw and is taller than the row",
          _xdet11 is not None
          and app._card_key(_m11b) in app._CARD_DETAILS_OPEN
          and _PIL_Image.open(io.BytesIO(
              _xdet11.content.src)).size[1] > 177)
    _tap11(_xdet11, 100, 10)
    check("v12.11: tapping the expanded row's body "
          "collapses it back to the collapsed draw",
          app._card_key(_m11b) not in app._CARD_DETAILS_OPEN
          and any(c.content.src == _det11.content.src
                  for c in _board_dets11()))
    app._CARD_DETAILS_OPEN.clear()

    # Finds: segment over, then the same integration on B.
    _seg11 = next(c for c in walk(board11)
                  if type(c).__name__ == "SegmentedButton")
    _seg11.on_change(SimpleNamespace(
        control=SimpleNamespace(selected={"finds"})))
    _betfi11 = bsw11[0].content
    _g11, _f11, _fl11, _c11 = app.distill_finds(
        _mkts11, _vrd11)
    _bmap11 = {}
    for _m, _v, _e in _g11:
        _bmap11[app.draw_ticket_b(_m, _v, _e)] = (_m, _v, _e, None)
    for _i, (_m, _v, _e) in enumerate(_f11[:app.CARD_PAGE], start=1):
        _bmap11[app.draw_ticket_b(_m, _v, _e)] = (_m, _v, _e, _i)
    for _m, _v, _e in _fl11:
        _bmap11[app.draw_ticket_b(_m, _v, _e)] = (_m, _v, _e, None)

    def _finds_dets11():
        return [c for c in walk(_betfi11)
                if type(c).__name__ == "GestureDetector"]
    _fdets11 = _finds_dets11()
    check("v12.11: finds integration — every Finds card "
          "byte-matches a direct Design B draw and decodes "
          "at ticket geometry",
          bool(_fdets11)
          and all(c.content.src in _bmap11 for c in _fdets11)
          and all(_PIL_Image.open(io.BytesIO(
              c.content.src)).size == (1170, 408)
              for c in _fdets11),
          f"finds dets={len(_fdets11)}")
    # (d) B expansion: byte-equal to a direct expanded
    # ticket draw, taller than the ticket.
    _fdet11 = _fdets11[0]
    _fm11, _fv11, _fe11, _fr11 = _bmap11[_fdet11.content.src]
    _tap11(_fdet11, 100, 10)
    _exp_b11 = app._card_png_expanded(
        _fm11, _fv11, _fresh11, _q11, rank=_fr11,
        edge_pts=_fe11, lane_ctx=_ctx11, design="B")[0]
    _fxdet11 = next((c for c in _finds_dets11()
                     if c.content.src == _exp_b11), None)
    check("v12.11: tapping a Finds ticket expands it — "
          "the replacement image byte-matches a direct "
          "expanded ticket draw and is taller than the "
          "ticket",
          _fxdet11 is not None
          and app._card_key(_fm11) in app._CARD_DETAILS_OPEN
          and _PIL_Image.open(io.BytesIO(
              _fxdet11.content.src)).size[1] > 408)
    # (e) the SLIP zone on the expanded ticket routes to
    # the Slip view, whose Protected Slip panel populates
    # through the app's own path; the card stays expanded.
    _tap11(_fxdet11, 195, _fxdet11.content.height - 10)
    _all11 = []
    for _r in page11.controls:
        _all11 += texts(_r)
    check("v12.11: the expanded ticket's SLIP zone opens "
          "the Slip view and the Protected Slip panel "
          "populates (its header prints); the card itself "
          "stays expanded",
          any("PROTECTED SLIP — PLACEMENT-READY" in t
              for t in _all11)
          and app._card_key(_fm11) in app._CARD_DETAILS_OPEN)
    app._CARD_DETAILS_OPEN.clear()
    page11.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=0)))

    # Parse surface: a pasted bet that matches the pull
    # lands as a Design B ticket.
    page11.navigation_bar.on_change(SimpleNamespace(
        control=SimpleNamespace(selected_index=1)))
    _slip11 = sw11.content
    _pf11 = next(c for c in walk(_slip11)
                 if type(c).__name__ == "TextField")
    _pb11 = next(c for c in walk(_slip11)
                 if type(c).__name__ == "Button"
                 and _btn_label11(c) == "Parse")
    _pdet11 = None
    for _m, _v in zip(_mkts11, _vrd11):
        if _m.get("sport") != "nfl" \
                or _m.get("market") != "spread" \
                or _m.get("line") is None \
                or float(_m["line"]) >= 0 \
                or _m.get("price") is None:
            continue
        _pf11.value = (
            f"{app.team_name(_m, _m.get('side') or 'home')} "
            f"{float(_m['line']):+g} "
            f"({int(_m['price']):+d})")
        _pb11.on_click(SimpleNamespace())
        _pd = [c for c in walk(_slip11)
               if type(c).__name__ == "GestureDetector"]
        if _pd:
            _pdet11 = _pd[0]
            break
    check("v12.11: the Parse match card is a Design B "
          "ticket (1170x408 draw)",
          _pdet11 is not None
          and _PIL_Image.open(io.BytesIO(
              _pdet11.content.src)).size == (1170, 408)
          and _pdet11.content.src in {
              app.draw_ticket_b(_m, _v,
                                app.market_edge_pts(_m, _v))
              for _m, _v in zip(_mkts11, _vrd11)},
          f"parse det={_pdet11 is not None}")

    # ---------- v12.12: the Show-default fix ----------
    # Diagnosis (SPORTS-DIAGNOSIS-2026-10-27): the board
    # booted on Show = Golden bets, and GOLDEN BET requires
    # zero soft conditions in the engine's verdict ladder —
    # a record-less lane IS a soft, the shipped scorecard
    # carries no soccer or nba-ml record, and NFL's lane
    # alone has one (3-8). So the boot filter passed NFL
    # and silently excluded every soccer/NBA market, and a
    # manual scoped pull (which pins Board shows to the
    # pulled sport but never touched Show) landed on the
    # empty board. The fix is the front door only:
    # DEFAULT_SHOW "golden" -> "all". The ladder, the
    # golden gate and the Show filter itself are untouched
    # — (b) below proves the filter still filters.
    from datetime import datetime as _dt12
    check("v12.12: DEFAULT_SHOW is All markets",
          app.DEFAULT_SHOW == "all")

    # (a) + (b): a fresh boot over a mixed REAL slate in a
    # fresh storage dir. Markets are real (the saga's saved
    # slate, mobile/perf-ab/slate.json), priced by the real
    # engine through the app's own cached pass. The record
    # is stamped FRESH: the engine degrades every grade on
    # a stale pull (betmodel5.menu_stamp, STALE_AFTER_H) —
    # that honesty is not what is on trial here. One NFL
    # moneyline is repriced (+300) so the engine mints a
    # genuine GOLDEN BET through its own checker, making
    # (b) non-vacuous; its untainted twin is excluded from
    # the NFL sample so no fixture appears twice.
    _perf12 = json.load(open(os.path.join(
        HERE, os.pardir, "perf-ab", "slate.json")))
    _gold_src12 = next(
        m for m in _perf12["markets"]
        if m.get("sport") == "nfl"
        and m.get("market") == "moneyline")
    _gold12 = dict(_gold_src12)
    _gold12["price"] = 300
    _nfl12 = [m for m in _perf12["markets"]
              if m.get("sport") == "nfl"
              and not (m.get("fd_market_id")
                       == _gold_src12.get("fd_market_id")
                       and m.get("side")
                       == _gold_src12.get("side"))][:6]
    _soc12 = [m for m in _perf12["markets"]
              if m.get("sport") == "soccer"][:6]
    _nba12 = [m for m in _perf12["markets"]
              if m.get("sport") == "nba"][:6]
    _mkts12 = _nfl12 + [_gold12] + _soc12 + _nba12
    _rec12 = {"pulled_at": _dt12.now().astimezone().isoformat(
                  timespec="seconds"),
              "source": _perf12.get("source"),
              "verified": True,
              "markets": _mkts12,
              "sports": {s: (_perf12.get("sports") or {}).get(
                             s, {})
                         for s in ("nfl", "soccer", "nba")},
              "tree": {}, "event_menus": {}}
    _vs12, _cache12 = app._price_markets_cached(
        _mkts12, _rec12, {})
    _png12 = {}
    for _m12, _v12 in zip(_mkts12, _vs12):
        _png12[app._card_png_collapsed(
            _m12, _v12, app.market_edge_pts(_m12, _v12))] = (
            _m12.get("sport"),
            app.card_verdict(_v12)[0] == "GOLDEN BET")
    _golden12 = {p for p, (_s12, _g12) in _png12.items()
                 if _g12}
    _gold_png12 = app._card_png_collapsed(
        _gold12, _vs12[_mkts12.index(_gold12)],
        app.market_edge_pts(
            _gold12, _vs12[_mkts12.index(_gold12)]))
    _dir12 = tempfile.mkdtemp(prefix="betfixii-v1212-")
    _env12 = os.environ.get("FLET_APP_STORAGE_DATA")
    try:
        os.environ["FLET_APP_STORAGE_DATA"] = _dir12
        with open(os.path.join(
                _dir12, "Bet_Finder-last-pull.json"),
                "w") as _f12:
            json.dump(_rec12, _f12)
        page12 = FakePage()
        app.main(page12)
        _board12 = page12.controls[1].content
        _bsw12 = [c for c in walk(_board12)
                  if type(c).__name__ == "AnimatedSwitcher"]
        _cards12 = _bsw12[0].content
        _show12 = next(
            c for c in walk(_cards12)
            if type(c).__name__ == "Dropdown"
            and [o.key for o in c.options]
            == [k for k, _t in app.SHOW_MODES])

        def _dets12():
            _lists = [c for c in walk(_cards12)
                      if type(c).__name__ == "Column"]
            _cl = max(_lists, key=lambda c: sum(
                1 for x in getattr(c, "controls", [])
                if type(x).__name__ == "GestureDetector"))
            return [x for x in _cl.controls
                    if type(x).__name__ == "GestureDetector"]

        def _per12(dets):
            _per = {}
            for _d in dets:
                _hit = _png12.get(_d.content.src)
                if _hit:
                    _per[_hit[0]] = _per.get(_hit[0], 0) + 1
            return _per

        _boot_dets12 = _dets12()
        _boot_per12 = _per12(_boot_dets12)
        check("v12.12 (a): a fresh boot over a mixed slate "
              "renders rows for NFL, soccer AND NBA under "
              "the boot-default view",
              _show12.value == "all"
              and len(_boot_dets12) == len(_mkts12)
              and _boot_per12.get("nfl", 0) > 0
              and _boot_per12.get("soccer", 0) > 0
              and _boot_per12.get("nba", 0) > 0,
              f"show={_show12.value} per-sport={_boot_per12} "
              f"dets={len(_boot_dets12)}/{len(_mkts12)}")
        _show12.on_select(SimpleNamespace(
            control=SimpleNamespace(value="golden")))
        _g_dets12 = _dets12()
        _g_srcs12 = {d.content.src for d in _g_dets12}
        check("v12.12 (b): Show = Golden bets still filters "
              "to GOLDEN BET verdicts only — every golden on "
              "this slate is NFL, the record lanes' privilege "
              "exactly as diagnosed",
              len(_golden12) >= 1
              and _gold_png12 in _golden12
              and _g_srcs12 == _golden12
              and all(_png12[p][0] == "nfl" for p in _golden12),
              f"golden={len(_golden12)} rendered="
              f"{len(_g_dets12)} per-sport="
              f"{_per12(_g_dets12)}")
    finally:
        os.environ["FLET_APP_STORAGE_DATA"] = _env12

    # (c): a MANUAL scoped soccer pull lands on its rows.
    # Same end-to-end machinery as the v12.3 drive (chooser
    # + the band's Pull button, engine fetch/parse seams
    # stubbed): the worker pins Board shows to soccer, and
    # under the v12.12 default the pulled sport's rows are
    # what the board shows — the receipt names them. Under
    # the old golden default this exact drive rendered 0.
    page13 = FakePage()
    app.main(page13)
    _board13 = page13.controls[1].content
    _bsw13 = [c for c in walk(_board13)
              if type(c).__name__ == "AnimatedSwitcher"]
    _cards13 = _bsw13[0].content
    _chooser13 = next(
        d for d in walk(_board13)
        if type(d).__name__ == "Dropdown"
        and len(getattr(d, "options", None) or []) == 17)
    _fetch_calls.clear()
    _menu_calls.clear()
    b5.fd_get = _stub_get
    b5.fd_parse_sport_page = _stub_parse
    b5.fd_event_menu = _stub_event_menu
    try:
        _chooser13.on_select(SimpleNamespace(
            control=SimpleNamespace(value="soccer")))

        def _btn_label13(c):
            t = getattr(c, "text", None)
            if t:
                return t
            ct = getattr(c, "content", None)
            if isinstance(ct, str):
                return ct
            return getattr(ct, "value", None)
        _pull13 = [c for c in walk(_board13)
                   if type(c).__name__ == "Button"
                   and _btn_label13(c) == "Pull"]
        if _pull13:
            _pull13[0].on_click(SimpleNamespace())
        _receipt13 = next(
            (c for c in walk(_cards13)
             if type(c).__name__ == "Text"
             and (getattr(c, "value", "") or "")
             .startswith("Rendered:")),
            None)
        _n13 = int(_receipt13.value.split()[1]) \
            if _receipt13 else -1
        _snap13 = json.load(open(os.path.join(
            STORAGE, "Bet_Finder-last-pull.json")))
        _soc13 = [m for m in _snap13["markets"]
                  if m.get("sport") == "soccer"]
        _vs13, _c13 = app._price_markets_cached(
            _snap13["markets"], _snap13, {})
        _soc_pngs13 = {
            app._card_png_collapsed(
                m, v, app.market_edge_pts(m, v))
            for m, v in zip(_snap13["markets"], _vs13)
            if m.get("sport") == "soccer"}
        _lists13 = [c for c in walk(_cards13)
                    if type(c).__name__ == "Column"]
        _cl13 = max(_lists13, key=lambda c: sum(
            1 for x in getattr(c, "controls", [])
            if type(x).__name__ == "GestureDetector"))
        _dets13 = [x for x in _cl13.controls
                   if type(x).__name__ == "GestureDetector"]
        _sv_cands13 = [
            d for d in walk(_cards13)
            if type(d).__name__ == "Dropdown"
            and [o.key for o in d.options]
            != [k for k, _t in app.SHOW_MODES]
            and len(d.options) != 17
            and [o.key for o in d.options][:1] == ["all"]
            and "soccer" in [o.key for o in d.options]]
        _sv13 = _sv_cands13[0] if _sv_cands13 else None
        check("v12.12 (c): a manual scoped soccer pull lands "
              "on a board showing the pulled sport's rows "
              "(receipt > 0, every row a soccer card)",
              len(_pull13) == 1
              and _n13 > 0
              and _n13 == len(_dets13)
              and len(_soc13) == 3
              and len(_dets13) == len(_soc13)
              and all(d.content.src in _soc_pngs13
                      for d in _dets13)
              and _sv13 is not None
              and _sv13.value == "soccer",
              f"receipt={getattr(_receipt13, 'value', None)} "
              f"dets={len(_dets13)} soccer={len(_soc13)} "
              f"sv={getattr(_sv13, 'value', None)} "
              f"sv-cands="
              f"{[getattr(d, 'value', None) for d in _sv_cands13]}")
    finally:
        b5.fd_get = _orig_fd_get
        b5.fd_parse_sport_page = _orig_parse
        b5.fd_event_menu = _orig_event_menu
        app.set_chosen_sport("nfl")

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks "
          f"passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
