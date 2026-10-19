#!/usr/bin/env python3
"""
BetFi — the betmodel v5 mobile shell (public name: BetFi; internal
id: Bet_Finder).

The ENTIRE app in one file, per the Pilot's 1-script preference: this
shell plus the engine (betmodel5.py, one self-contained script,
byte-identical to the lab's) are the only two Python files in the
repo. Flet requires the entry point to be named main.py — that is
the only reason there are two.

Screens:
  * Card  — the Level-3 card screen: every checked market from the
    current pull as a card (face: matchup #:# / Win # / Lose # /
    Probability # / Grade / the engine's verdict term, verbatim;
    depth folded in as collapsible PRICE ANATOMY / SCALE /
    COHERENCE / PROVENANCE sections, exactly the engine's named
    sections, with the engine's verdict_reason as the first line
    of the depth).
  * BetFi — the finds feed (internal: Bet_Finder feed): a GOLDEN
    BETS panel at the top (every card whose engine verdict is
    GOLDEN BET; "No golden bets on this pull" when there are
    none — never backfilled), then the finds: verdict-bearing
    PRICED cards ranked by the verdict ladder first (GOLDEN BET >
    BET HERE > RISK BET (BET) > RISK BET (DO NOT BET) > DO NOT
    BET), then by reparametrized edge descending.
    COHERENCE-FLAGGED markets in their own group, and everything
    else collapsed into one "Checked — no edge" counter. BetFi
    finds and ranks — it never upgrades a verdict: the engine's
    verdict term and every stamp (UNCALIBRATED, UNPRICED,
    UNVERIFIED) print exactly as the engine issued them.
  * Record — lane Win/Lose records + the engine version string and
    a fingerprint of the bundled engine file, so a stale build is
    visible at a glance.

Every number on every screen comes from an imported betmodel5
function — the shell computes nothing of its own except the BetFi
ranking, which applies the engine's own phi-edge formula
(edge = P - implied_prob(price), the formula _grade_and_gate uses
inside the engine) to the engine's returned probability and the
pulled price. Analysis only: the app never places a bet, never
touches or stores FanDuel credentials; the menu pull reads the
public board via the engine's read-only sbapi route.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import betmodel5 as b5  # the engine — one script, imported, never copied
import flet as ft

# ------------------------------------------------------------------
# Bet_Finder identity + storage

PUBLIC_NAME = "BetFi"
INTERNAL_ID = "Bet_Finder"
ENGINE_VERSION = "betmodel v5"
MENU_SOURCE = "FanDuel sbapi (Michigan) live pull"
# lanes shown on the Record screen (engine lane_record is safe for
# any lane name: an unknown lane reports 0-0, "no scored record")
RECORD_LANES = ["nfl-ml", "ml", "cover", "live", "nba-ml", "props",
                "soccer"]

# The verdict ladder (MODEL-V5.md) — rank order for the BetFi
# feed. The terms themselves are the engine's; the app only orders
# by them, verbatim, and never re-derives or renames one.
VERDICT_LADDER = ["GOLDEN BET", "BET HERE", "RISK BET (BET)",
                  "RISK BET (DO NOT BET)", "DO NOT BET"]
VERDICT_COLORS = {"GOLDEN BET": "#FFD700", "BET HERE": "#10B981",
                  "RISK BET (BET)": "#FBBF24",
                  "RISK BET (DO NOT BET)": "#F97316",
                  "DO NOT BET": "#EF4444",
                  "Bet": "#10B981", "No Bet": "#EF4444"}

GRADE_COLORS = {
    "A+": "#10B981", "A": "#10B981", "A-": "#34D399",
    "B+": "#60A5FA", "B": "#3B82F6", "B-": "#93C5FD",
    "C+": "#FBBF24", "C": "#F59E0B", "C-": "#D97706",
    "D+": "#F87171", "D": "#EF4444", "D-": "#DC2626", "F": "#991B1B",
}
INK = "#E2E8F0"
DIM = "#94A3B8"
FAINT = "#64748B"
CARD_BG = "#0B1329"
ACCENT = "#38BDF8"
WARN = "#F59E0B"
BAD = "#EF4444"


def storage_dir() -> str:
    """Writable per-app storage (Flet/Android), else the app dir."""
    return (os.environ.get("FLET_APP_STORAGE_DATA")
            or os.environ.get("ANDROID_PRIVATE") or APP_DIR)


def snapshot_path() -> str:
    return os.path.join(storage_dir(), f"{INTERNAL_ID}-last-pull.json")


def engine_fingerprint() -> str:
    """Short hash + size of the bundled engine file — a stale build
    shows a different fingerprint on the Record screen."""
    try:
        path = os.path.join(APP_DIR, "betmodel5.py")
        with open(path, "rb") as f:
            blob = f.read()
        return f"sha256 {hashlib.sha256(blob).hexdigest()[:12]}" \
               f" · {len(blob)} bytes"
    except OSError as e:
        return f"unreadable ({type(e).__name__})"


def repoint_engine_storage() -> None:
    """The v4 shell's pattern: on-device, the engine's data paths
    (DATA = engine_dir/../data) may be read-only or absent, so point
    the engine's module-level path globals at writable app storage.
    Every engine loader tolerates missing files (empty scorecard,
    no phi registry, no lane history) and reports that honestly;
    this only gives it somewhere writable to keep what it saves."""
    base = (os.environ.get("FLET_APP_STORAGE_DATA")
            or os.environ.get("ANDROID_PRIVATE"))
    if not base:
        return
    try:
        data = os.path.join(base, f"{INTERNAL_ID}-engine-data")
        os.makedirs(os.path.join(data, "cache"), exist_ok=True)
        b5.DATA = data
        b5.RESULTS = data
        b5.CACHE = os.path.join(data, "cache")
        b5.SCORECARD_PATH = os.path.join(data, "scorecard.json")
        b5.PHI_PATH = os.path.join(data, "v5-phi.json")
        b5.HISTORY_PATH = os.path.join(data, "v5-lane-history.json")
        b5.NFL_PRICING_PATH = os.path.join(data,
                                           "nfl-week6-pricing.json")
        b5.NBA_FIT_PATH = os.path.join(data, "v5-nba.json")
        b5.SOCCER_FIT_PATH = os.path.join(data, "v5-soccer.json")
    except Exception:
        pass  # the shell must never die over storage bookkeeping


repoint_engine_storage()

# ------------------------------------------------------------------
# The menu pull — composed from the engine's own functions, the
# same composition the engine's `menu` command performs:
# application-context (tree) -> per-sport SPORT page (+ CUSTOM
# league page merged for nfl/nba/nhl) -> fd_parse_sport_page ->
# checker slate. Any failed scope stamps itself UNVERIFIED in the
# returned record; nothing is ever replaced with an assumed menu.


def pull_menu() -> dict:
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
    for sport in b5.FANDUEL_EVENT_TYPES:
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
            slate, inventory, n_games, routed = \
                b5.fd_parse_sport_page(page, sport)
            rec["sports"][sport] = {
                "games": n_games, "markets_on_page":
                sum(inventory.values()), "slate_markets": len(slate),
                "routed": routed}
            markets += slate
        except Exception as e:
            rec["sports"][sport] = {"error":
                                    f"{type(e).__name__}: {e}"}
    rec["markets"] = markets
    rec["verified"] = bool(markets)
    return rec


def save_snapshot(rec: dict) -> None:
    try:
        with open(snapshot_path(), "w") as f:
            json.dump(rec, f)
    except Exception:
        pass


def load_snapshot() -> dict | None:
    try:
        with open(snapshot_path()) as f:
            rec = json.load(f)
        if isinstance(rec, dict) and "markets" in rec:
            return rec
    except Exception:
        pass
    return None


# ------------------------------------------------------------------
# Engine-derived per-market facts (all engine functions; the shell
# adds no model math of its own)


def market_lane(mkt: dict) -> str:
    return b5._lane_for(mkt)


def market_edge_pts(mkt: dict, verdict: dict) -> float | None:
    """The reparametrized (phi) edge in points — the engine's own
    formula from _grade_and_gate: (P - implied_prob(price)) * 100,
    applied to the probability the engine returned for this market.
    None when the market carries no priced probability."""
    p = verdict.get("p")
    price = mkt.get("price")
    if p is None or price is None:
        return None
    return (p - b5.implied_prob(price)) * 100


def card_verdict(verdict: dict) -> tuple[str, str | None]:
    """(term, reason) exactly as the engine issued them. Engine
    v5.1+ emits `verdict` + `verdict_reason` on every card; the
    v5.0 engine's own issued field is `decision` (Bet / No Bet)
    with its reasons in `blocked_by` / the checker note. The app
    prints whichever the bundled engine issued — it never
    translates, shortens, or re-derives a verdict."""
    term = verdict.get("verdict") or verdict.get("decision") \
        or verdict.get("state") or ""
    reason = verdict.get("verdict_reason")
    if not reason and verdict.get("blocked_by"):
        reason = "blocked by: " + "; ".join(verdict["blocked_by"])
    return term, reason


def verdict_rank(term: str) -> int:
    """Ladder position for ordering only. The pre-ladder engine's
    own terms sort at their natural rungs (its affirmative with
    BET HERE, its negative with DO NOT BET); unknown terms last."""
    if term in VERDICT_LADDER:
        return VERDICT_LADDER.index(term)
    if term == "Bet":
        return VERDICT_LADDER.index("BET HERE")
    if term == "No Bet":
        return VERDICT_LADDER.index("DO NOT BET")
    return len(VERDICT_LADDER)


def game_quotes(markets: list) -> dict:
    """Per-game quote dicts in the engine coherence_check's own
    shape: {source, spread_home, total, ml_p_home} — ml_p_home is
    the no-vig home probability from the pull's two moneyline
    prices (engine implied_prob on both sides, normalised)."""
    games = {}
    for m in markets:
        key = (m.get("sport"), m.get("away"), m.get("home"))
        g = games.setdefault(key, {"spread_home": None, "total": None,
                                   "_ml": {}})
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
                       "total": g["total"], "ml_p_home": ml_p_home}
    return quotes


def stamp_of(rec: dict | None) -> tuple[str, bool]:
    """The engine's menu stamp (menu_stamp) for a pull record."""
    if not rec:
        return "UNVERIFIED (no successful live pull)", True
    ctx = {"pulled_at": rec.get("pulled_at"),
           "source": rec.get("source"),
           "verified": rec.get("verified", False)}
    return b5.menu_stamp(ctx)


# ------------------------------------------------------------------
# Card rendering — one builder shared by the Card screen and the
# BetFi finds feed (a find IS a card, face + collapsible depth).


def _line(text: str, size: int = 11, color: str = DIM,
          bold: bool = False) -> ft.Text:
    return ft.Text(text, size=size, color=color,
                   weight=ft.FontWeight.BOLD if bold else None)


def _tile(title: str, body_lines: list) -> ft.ExpansionTile:
    return ft.ExpansionTile(
        title=ft.Text(title, size=12, color=ACCENT,
                      weight=ft.FontWeight.BOLD),
        controls=[ft.Container(
            padding=8,
            content=ft.Column(spacing=2, controls=[
                _line(t) for t in body_lines]))])


def build_market_card(mkt: dict, verdict: dict, rec: dict,
                      quotes_by_game: dict, rank: int | None = None,
                      edge_pts: float | None = None) -> ft.Container:
    lane = market_lane(mkt)
    w, l, rec_src = b5.lane_record(lane)
    phi, phi_state, _detail = b5.lane_phi(lane)
    uncal = b5.lane_uncalibrated(lane)
    p = verdict.get("p")
    grade = verdict.get("grade")
    term, vreason = card_verdict(verdict)
    state = verdict.get("state") or ""
    key = (mkt.get("sport"), mkt.get("away"), mkt.get("home"))
    quote = quotes_by_game.get(key)
    if quote and any(quote.get(k) is not None for k in
                     ("spread_home", "total", "ml_p_home")):
        flags = b5.coherence_check([quote])
        coh_lines = flags or ["coherent at quoted prices"]
    else:
        coh_lines = ["insufficient quotes in this pull to audit"]

    face = []
    if rank is not None:
        face.append(_line(
            f"FIND #{rank}"
            + (f" · edge {edge_pts:+.1f} pts"
               if edge_pts is not None else ""),
            12, ACCENT, True))
    face.append(ft.Text(verdict.get("desc") or
                        f"{mkt.get('away', '?')} @ "
                        f"{mkt.get('home', '?')}",
                        size=16, color=INK, weight=ft.FontWeight.BOLD))
    face.append(_line(f"#:{mkt.get('fd_event_id') or '—'} · "
                      f"{mkt.get('market', '?')} · "
                      f"{mkt.get('sport', '?')}", 10, FAINT))
    face.append(_line(f"Win {w} · Lose {l}   ({lane} lane record)",
                      12, DIM))
    face.append(ft.Text(
        "Probability UNPRICED" if p is None else
        f"Probability {p * 100:.1f}%",
        size=20, color=INK, weight=ft.FontWeight.BOLD))
    grade_color = GRADE_COLORS.get(grade or "", FAINT)
    face.append(ft.Row(spacing=8, controls=[
        ft.Text(f"Grade {grade}" if grade else "Grade —",
                size=16, color=grade_color,
                weight=ft.FontWeight.BOLD),
        ft.Text(state, size=12,
                color=WARN if state != "PRICED" else DIM,
                weight=ft.FontWeight.BOLD),
    ]))
    face.append(ft.Text(
        term, size=16,
        color=VERDICT_COLORS.get(term, BAD),
        weight=ft.FontWeight.BOLD))
    if uncal:
        # the engine's stamp, verbatim on the face
        face.append(_line(f"UNCALIBRATED — {uncal}", 11, WARN, True))
    if verdict.get("note"):
        face.append(_line(verdict["note"], 10, FAINT))

    # the engine's verdict + its named reason lead the collapsible
    # depth — first line, verbatim
    anatomy = []
    if vreason:
        anatomy.append(f"{term} — {vreason}")
    elif term:
        anatomy.append(f"verdict: {term}")
    anatomy.append(f"state: {state}")
    if p is not None:
        anatomy.append(f"engine probability (post-phi): "
                       f"{p * 100:.1f}%")
    if mkt.get("price") is not None:
        anatomy.append(f"pulled price: {int(mkt['price']):+d} "
                       f"(implied "
                       f"{b5.implied_prob(mkt['price']) * 100:.1f}%)")
    if edge_pts is not None:
        anatomy.append(f"phi edge: {edge_pts:+.1f} pts "
                       f"(engine formula: P - implied at price)")
    if mkt.get("line") is not None:
        anatomy.append(f"line: {mkt['line']} · side: "
                       f"{mkt.get('side')}")
    if verdict.get("detail"):
        anatomy.append(f"checker detail: {verdict['detail']}")
    if verdict.get("note"):
        anatomy.append(f"checker note: {verdict['note']}")

    phi_params = ({k: v for k, v in phi.items() if k != "kind"}
                  if isinstance(phi, dict) else {})
    scale = [f"phi: {phi.get('kind', '?') if isinstance(phi, dict) else '?'}"
             f" [{phi_state}]"
             + (f" params {phi_params}" if phi_params else ""),
             f"lane record: {w}-{l} ({rec_src})",
             f"calibration: {uncal or phi_state}"]

    stamp_text, _degraded = stamp_of(rec)
    provenance = [f"menu: {stamp_text}",
                  f"source: {rec.get('source')}",
                  f"pulled at: {rec.get('pulled_at')}"]
    if mkt.get("market_time"):
        provenance.append(f"market time (FanDuel): "
                            f"{mkt['market_time']}")
    if mkt.get("fd_market_id"):
        provenance.append(f"FanDuel market id: "
                            f"{mkt['fd_market_id']}")
    provenance.append(f"card rendered: "
                      f"{datetime.now().astimezone().isoformat(timespec='seconds')}")

    return ft.Container(
        bgcolor=CARD_BG, border_radius=8, padding=10,
        content=ft.Column(spacing=4, controls=face + [
            _tile("PRICE ANATOMY", anatomy),
            _tile("SCALE", scale),
            _tile("COHERENCE", coh_lines),
            _tile("PROVENANCE", provenance),
        ]))


# ------------------------------------------------------------------
# Bet_Finder — the finds feed distillation


def distill_finds(markets: list, verdicts: list):
    """(golden, finds, flagged, checked_no_edge) from a priced
    slate. golden: every card whose engine verdict is GOLDEN BET
    (the golden panel's only residents). finds: verdict-bearing
    PRICED cards, ranked by verdict ladder first, then by
    reparametrized edge descending. flagged: COHERENCE-FLAGGED
    markets, in pull order. checked_no_edge: everything else the
    engine checked — kept off the feed, counted, not hidden."""
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


# ------------------------------------------------------------------
# The app


def main(page: ft.Page):
    page.title = PUBLIC_NAME
    page.scroll = ft.ScrollMode.AUTO

    state = {"slate": load_snapshot(), "verdicts": None}
    stamp_text, degraded = stamp_of(state["slate"])
    stamp_ctrl = ft.Text(f"Menu: {stamp_text}", size=12,
                         color=WARN if degraded else DIM)
    status = ft.Text("", size=12, color=ACCENT)
    card_view = ft.Column(spacing=8)
    betfi_view = ft.Column(spacing=8, visible=False)
    record_view = ft.Column(spacing=8, visible=False)

    def current_ctx():
        rec = state["slate"] or {}
        return {"pulled_at": rec.get("pulled_at"),
                "source": rec.get("source"),
                "verified": rec.get("verified", False)}

    def refresh_stamp():
        text, deg = stamp_of(state["slate"])
        stamp_ctrl.value = f"Menu: {text}"
        stamp_ctrl.color = WARN if deg else DIM

    def ensure_verdicts():
        rec = state["slate"]
        if not rec:
            return None
        if state["verdicts"] is None:
            state["verdicts"] = b5.run_slate(rec, print_out=False)
        return state["verdicts"]

    def render_cards():
        card_view.controls = []
        rec = state["slate"]
        if not rec:
            card_view.controls = [ft.Text(
                "No pull yet. Tap Pull Menu — until a live pull "
                "lands, every market is UNVERIFIED, never assumed.",
                size=13, color=DIM)]
            page.update()
            return
        verdicts = ensure_verdicts()
        quotes = game_quotes(rec.get("markets", []))
        for mkt, verdict in zip(rec.get("markets", []), verdicts):
            card_view.controls.append(build_market_card(
                mkt, verdict, rec, quotes,
                edge_pts=market_edge_pts(mkt, verdict)))
        if not card_view.controls:
            card_view.controls = [ft.Text(
                "The pull returned no primary markets.",
                size=13, color=DIM)]
        page.update()

    def render_betfi():
        betfi_view.controls = []
        rec = state["slate"]
        header = ft.Text(f"{PUBLIC_NAME} — finds feed", size=18,
                         color=INK, weight=ft.FontWeight.BOLD)
        betfi_view.controls.append(header)
        if not rec:
            betfi_view.controls.append(ft.Text(
                "No pull yet — the feed distills the current pull. "
                "Pull Menu on the Card screen first.",
                size=13, color=DIM))
            page.update()
            return
        verdicts = ensure_verdicts()
        markets = rec.get("markets", [])
        quotes = game_quotes(markets)
        golden, finds, flagged, counter = distill_finds(markets,
                                                         verdicts)
        # the golden panel — top of the screen, GOLDEN BET cards
        # only, honest empty state, never backfilled
        betfi_view.controls.append(ft.Text(
            "GOLDEN BETS", size=15, color="#FFD700",
            weight=ft.FontWeight.BOLD))
        if not golden:
            betfi_view.controls.append(ft.Text(
                "No golden bets on this pull", size=12, color=DIM))
        for mkt, verdict, edge in golden:
            betfi_view.controls.append(build_market_card(
                mkt, verdict, rec, quotes, edge_pts=edge))
        betfi_view.controls.append(ft.Text(
            f"FINDS — verdict ladder, then edge ({len(finds)})",
            size=14, color=ACCENT, weight=ft.FontWeight.BOLD))
        if not finds:
            betfi_view.controls.append(ft.Text(
                "No priced, verdict-bearing market on this pull. "
                "The feed stays empty rather than promote a "
                "market the engine did not price.",
                size=12, color=DIM))
        for i, (mkt, verdict, edge) in enumerate(finds, start=1):
            betfi_view.controls.append(build_market_card(
                mkt, verdict, rec, quotes, rank=i, edge_pts=edge))
        if flagged:
            betfi_view.controls.append(ft.Text(
                f"COHERENCE-FLAGGED — somebody's price is wrong "
                f"({len(flagged)})", size=14, color=WARN,
                weight=ft.FontWeight.BOLD))
            for mkt, verdict, edge in flagged:
                betfi_view.controls.append(build_market_card(
                    mkt, verdict, rec, quotes, edge_pts=edge))
        counter_lines = [
            f"{v.get('desc')} — {v.get('state')}"
            + (f" · edge {e:+.1f} pts" if e is not None else "")
            for _m, v, e in counter]
        betfi_view.controls.append(ft.ExpansionTile(
            title=ft.Text(f"Checked — no edge ({len(counter)})",
                          size=12, color=FAINT,
                          weight=ft.FontWeight.BOLD),
            controls=[ft.Container(padding=8, content=ft.Column(
                spacing=2, controls=[_line(t, 10, FAINT)
                                     for t in counter_lines]))]))
        page.update()

    def render_record():
        record_view.controls = [ft.Text(
            "Record — lane Win / Lose", size=18, color=INK,
            weight=ft.FontWeight.BOLD)]
        card = b5.load_scorecard()
        for lane in RECORD_LANES:
            w, l, src = b5.lane_record(lane)
            status_line = ""
            if lane not in ("nfl-ml", "nfl"):
                try:
                    status_line = " · governor: " + \
                        b5.lane_status(card, lane)["status"]
                except Exception as e:
                    status_line = f" · governor: {type(e).__name__}"
            uncal = b5.lane_uncalibrated(lane)
            record_view.controls.append(ft.Text(
                f"{lane}: Win {w} · Lose {l} ({src}){status_line}"
                + (f" · UNCALIBRATED — {uncal}" if uncal else ""),
                size=13, color=DIM))
        entries = card.get("entries") or []
        record_view.controls.append(ft.Divider())
        record_view.controls.append(ft.Text(
            f"Engine: {ENGINE_VERSION} · {engine_fingerprint()}",
            size=12, color=ACCENT))
        record_view.controls.append(ft.Text(
            f"Scorecard entries on device: {len(entries)} · "
            f"internal id {INTERNAL_ID} · analysis only — "
            f"{PUBLIC_NAME} never places a bet.",
            size=11, color=FAINT))
        page.update()

    # ---- actions (the engine's menu command / slate pricing,
    # imported — never a network copy of the engine)

    def on_pull(_e):
        status.value = "Pulling the live FanDuel menu…"
        page.update()
        rec = pull_menu()
        state["slate"] = rec
        state["verdicts"] = None
        save_snapshot(rec)
        refresh_stamp()
        if rec.get("verified"):
            per = ", ".join(
                f"{s}: {v.get('slate_markets', 0)} markets"
                for s, v in rec["sports"].items() if "error" not in v)
            failed = ", ".join(
                s for s, v in rec["sports"].items() if "error" in v)
            status.value = (f"Pulled {len(rec['markets'])} primary "
                            f"markets ({per})"
                            + (f" · UNVERIFIED scopes: {failed}"
                               if failed else ""))
        else:
            err = rec.get("tree_error") or "no markets returned"
            status.value = (f"Menu UNVERIFIED — {err}. Nothing was "
                            f"assumed; every market stamps UNPRICED.")
        render_cards()
        render_betfi()
        page.update()

    def on_price(_e):
        if not state["slate"]:
            status.value = "Nothing to price yet — Pull Menu first."
            page.update()
            return
        state["verdicts"] = None  # re-run the checkers on the pull
        verdicts = ensure_verdicts()
        priced = sum(1 for v in verdicts
                     if v.get("state") == "PRICED")
        status.value = (f"Priced slate: {len(verdicts)} markets "
                        f"checked · {priced} PRICED · the rest "
                        f"stamped, never guessed.")
        render_cards()
        render_betfi()
        page.update()

    def show(idx: int):
        card_view.visible = idx == 0
        betfi_view.visible = idx == 1
        record_view.visible = idx == 2
        if idx == 1:
            render_betfi()
        if idx == 2:
            render_record()
        page.update()

    def on_nav(e):
        show(e.control.selected_index)

    header = ft.Column(spacing=4, controls=[
        ft.Text(PUBLIC_NAME, size=22, color=INK,
                weight=ft.FontWeight.BOLD),
        ft.Text(f"{ENGINE_VERSION} · {INTERNAL_ID} · analysis only",
                size=11, color=FAINT),
        stamp_ctrl,
        ft.Row(spacing=8, controls=[
            ft.ElevatedButton("Pull Menu", on_click=on_pull),
            ft.ElevatedButton("Price Slate", on_click=on_price),
        ]),
        status,
        ft.Divider(),
    ])
    page.add(header, card_view, betfi_view, record_view)

    nav_bar_cls = getattr(ft, "NavigationBar", None)
    nav_dest_cls = (getattr(ft, "NavigationDestination", None)
                    or getattr(ft, "NavigationBarDestination", None))
    if nav_bar_cls is not None and nav_dest_cls is not None:
        page.navigation_bar = nav_bar_cls(
            selected_index=0, on_change=on_nav,
            destinations=[
                nav_dest_cls(icon="sports", label="Card"),
                nav_dest_cls(icon="search", label=PUBLIC_NAME),
                nav_dest_cls(icon="list", label="Record"),
            ])
    else:  # equivalent switch: a labelled button row
        page.add(ft.Row(spacing=8, controls=[
            ft.OutlinedButton("Card", on_click=lambda _e: show(0)),
            ft.OutlinedButton(PUBLIC_NAME,
                              on_click=lambda _e: show(1)),
            ft.OutlinedButton("Record", on_click=lambda _e: show(2)),
        ]))

    # offline behaviour: open on the last pull, stamped with its
    # original pull time (the engine's stamp calls it STALE past
    # its own window) — stale is labelled stale, never freshened.
    if state["slate"]:
        render_cards()
        render_betfi()
    else:
        render_cards()
    page.update()


if __name__ == "__main__":
    ft.app(target=main)
