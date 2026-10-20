#!/usr/bin/env python3
"""
BetFi 10 — the betmodel v5.2 mobile shell (public name: BetFi;
internal id: Bet_Finder).

The ENTIRE app in one file, per the Pilot's 1-script preference:
this shell plus the engine (betmodel5.py, one self-contained
script, byte-identical to the lab's) are the only two Python files
in the repo. Flet requires the entry point to be named main.py —
that is the only reason there are two.

Screens (bottom nav, five destinations):
  * Cards  — every checked market from the current pull as a card
    (face: matchup / record / odds / hero probability + edge /
    grade + calibration chip / verdict pill + stance pill; depth
    folded in as PRICE ANATOMY / SCALE / COHERENCE / PROVENANCE
    tiles). Toggles (priced only / golden only / hide DO NOT BET /
    per-sport) and eight sorts re-render the cached checker pass —
    they never re-price.
  * Parse  — paste slip text ("Lions -3.5 (-110)"); the app reads
    the selection, market, line, odds and implied probability,
    and matches it against the last pull when it can. A bet it
    can't match gets stamped, not guessed.
  * Parlay — build a slip of up to four PRICED legs from the last
    pull; combined odds, combined model probability (product —
    independence assumed, printed on the page), EV per unit, a
    ladder-language verdict and the slip's stance.
  * Solver — stake for a target profit, Kelly sizing (full /
    half / quarter, with the warning printed), and an
    equal-return hedge solver.
  * More   — links to BetFi (the finds feed), Record (the lane
    ledger + latest-pull summary), Terms, Equations, and Dev
    (version, engine fingerprint, credit).

v10 (2026-10-20): engine v5.2 — grades computed from the edge
math on every lane (no calibration cap; bands widened), the
calibration state rides on every card as a tag (CALIBRATED /
PROVISIONAL / UNCALIBRATED / UNTESTED), and every priced bet
carries a stance (BULLISH / CONSERVATIVE / LONGSHOT) computed by
the engine from the bet's own probability, edge and price.
Prices come only from the live FanDuel menu pull — never
invented; UNPRICED markets print DO NOT BET with the named
reason; the golden panel is never backfilled. Analysis only:
the app never places a bet and never touches a sportsbook
account.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import betmodel5 as b5  # the engine — one script, imported, never copied
import flet as ft

# ------------------------------------------------------------------
# Bet_Finder identity + storage

PUBLIC_NAME = "BetFi"
INTERNAL_ID = "Bet_Finder"
APP_VERSION = "10.1.0"
BUILD_NUMBER = 10
DISPLAY_NAME = "BetFi 10"
ENGINE_VERSION = f"betmodel v{b5.ENGINE_VERSION}"
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
# dark tints behind the verdict pill text — the WARM family
VERDICT_BG = {"GOLDEN BET": "#574A00", "BET HERE": "#065F46",
              "RISK BET (BET)": "#713F12",
              "RISK BET (DO NOT BET)": "#7C2D12",
              "DO NOT BET": "#7F1D1D",
              "Bet": "#065F46", "No Bet": "#7F1D1D"}
# stance tints — the COOL family, deliberately unlike the warm
# verdict tints so a stance never reads as a verdict
STANCE_BG = {"BULLISH": "#155E75", "CONSERVATIVE": "#3730A3",
             "LONGSHOT": "#6B21A8"}
STANCE_LABELS = {"BULLISH": "BULLISH", "CONSERVATIVE": "CONSERVATIVE",
                 "LONGSHOT": "LONGSHOT"}
# calibration chip status dots
CAL_DOT = {"CALIBRATED": "#34D399", "PROVISIONAL": "#FBBF24",
           "UNCALIBRATED": "#F59E0B", "UNTESTED": "#64748B"}
# UNPRICED is the only outlined pill: flat fill, grey text, grey
# border — no signal must never read as the DO NOT BET red
UNPRICED_BG = "#1F2937"
UNPRICED_FG = "#9CA3AF"
UNPRICED_BORDER = "#4B5563"

SPORT_LABELS = {"nfl": "NFL", "ncaaf": "NCAAF", "nba": "NBA",
                "nhl": "NHL", "mlb": "MLB", "soccer": "Soccer"}
SPORT_ICONS = {"nfl": ft.Icons.SPORTS_FOOTBALL,
               "ncaaf": ft.Icons.SPORTS_FOOTBALL,
               "nba": ft.Icons.SPORTS_BASKETBALL,
               "nhl": ft.Icons.SPORTS_HOCKEY,
               "mlb": ft.Icons.SPORTS_BASEBALL,
               "soccer": ft.Icons.SPORTS_SOCCER}

# Card screen paging + sorts (v7.1's six, labels corrected —
# edge is points, not percent — plus grade order in v10). Paging,
# filtering and sorting are display only, over the cached pass.
CARD_PAGE = 40
SORT_MODES = [("verdict", "Bets first — verdict ladder"),
              ("edge", "Top gain — edge (pts)"),
              ("no-bet-first", "Do not bets first"),
              ("grade", "Grade — A to F"),
              ("probability", "Highest probability"),
              ("time", "Kickoff time"),
              ("resolve", "Resolve date"),
              ("pull", "Pull order")]

GRADE_COLORS = {
    "A+": "#10B981", "A": "#10B981", "A-": "#34D399",
    "B+": "#60A5FA", "B": "#3B82F6", "B-": "#93C5FD",
    "C+": "#FBBF24", "C": "#F59E0B", "C-": "#D97706",
    "D+": "#F87171", "D": "#EF4444", "D-": "#DC2626", "F": "#991B1B",
}
# the v10 palette (design report): deep-navy page, card and raised
# surfaces, one border tone, three ink tones, one accent
PAGE_BG = "#060B1A"
INK = "#E2E8F0"
DIM = "#94A3B8"
FAINT = "#64748B"
CARD_BG = "#0B1329"
RAISED = "#111C38"
BORDER = "#1E293B"
CHIP_BORDER = "#334155"
ACCENT = "#38BDF8"
WARN = "#F59E0B"
BAD = "#EF4444"
EDGE_POS = "#10B981"
EDGE_NEG = "#EF4444"


def storage_dir() -> str:
    """Writable per-app storage (Flet/Android), else the app dir."""
    return (os.environ.get("FLET_APP_STORAGE_DATA")
            or os.environ.get("ANDROID_PRIVATE") or APP_DIR)


def snapshot_path() -> str:
    return os.path.join(storage_dir(), f"{INTERNAL_ID}-last-pull.json")


def engine_fingerprint() -> str:
    """Short hash + size of the bundled engine file — a stale build
    shows a different fingerprint on the Dev screen."""
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
    """(term, reason) exactly as the engine issued them. The app
    prints whichever the bundled engine issued — it never
    translates, shortens, or re-derives a verdict."""
    term = verdict.get("verdict") or verdict.get("decision") \
        or verdict.get("state") or ""
    reason = verdict.get("verdict_reason")
    if not reason and verdict.get("blocked_by"):
        reason = "blocked by: " + "; ".join(verdict["blocked_by"])
    return term, reason


def verdict_rank(term: str) -> int:
    """Ladder position for ordering only."""
    if term in VERDICT_LADDER:
        return VERDICT_LADDER.index(term)
    if term == "Bet":
        return VERDICT_LADDER.index("BET HERE")
    if term == "No Bet":
        return VERDICT_LADDER.index("DO NOT BET")
    return len(VERDICT_LADDER)


def grade_rank(grade: str | None) -> int:
    """Position on the engine's grade ladder (A+ best) for the
    grade sort; ungraded markets sort last."""
    if grade in b5.LADDER:
        return b5.LADDER.index(grade)
    return len(b5.LADDER)


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
# Display rules (language report §5: US surfaces keep US language;
# soccer surfaces use world language — display copy only, the
# engine's internal market keys never change)


def market_display_name(mkt: dict) -> str:
    """The market's name as the card face prints it."""
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


def matchup_title(mkt: dict, verdict: dict) -> str:
    """Soccer lists the home team first ('Inter vs Fiorentina');
    US sports keep '{away} @ {home}' via the engine's desc."""
    if mkt.get("sport") == "soccer":
        return f"{mkt.get('home', '?')} vs {mkt.get('away', '?')}"
    return verdict.get("desc") or \
        f"{mkt.get('away', '?')} @ {mkt.get('home', '?')}"


def side_label(mkt: dict) -> str:
    side = mkt.get("side") or ""
    if mkt.get("sport") == "soccer" and side == "draw":
        return "Draw"
    return side


# ------------------------------------------------------------------
# Shared display pieces: lines, tiles, pills, chips, skeletons


def _line(text: str, size: int = 11, color: str = DIM,
          bold: bool = False) -> ft.Text:
    return ft.Text(text, size=size, color=color,
                   weight=ft.FontWeight.BOLD if bold else None)


def _border_all(width: float, color: str) -> ft.Border:
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


def _tile(title: str, gloss: str, body_lines: list) -> ft.ExpansionTile:
    """A depth tile: the engine's section name, a one-line plain
    gloss under it (language report S4 — gloss, don't rename), then
    the engine's lines."""
    controls = [_line(gloss, 11, DIM)]
    controls += [_line(t) for t in body_lines]
    return ft.ExpansionTile(
        title=ft.Text(title, size=12, color=ACCENT,
                      weight=ft.FontWeight.BOLD),
        controls=[ft.Container(
            padding=8,
            content=ft.Column(spacing=2, controls=controls))])


def verdict_pill(term: str, unpriced: bool = False) -> ft.Container:
    """The verdict pill. GOLDEN BET is the only gold text; every
    other verdict is white on its warm tint — except UNPRICED,
    which gets the app's only OUTLINED pill so no-signal never
    reads as the DO NOT BET red."""
    if unpriced:
        return ft.Container(
            bgcolor=UNPRICED_BG, border_radius=10,
            border=_border_all(1, UNPRICED_BORDER),
            padding=ft.Padding(left=10, right=10, top=5, bottom=5),
            content=ft.Text(term, size=13, color=UNPRICED_FG,
                            weight=ft.FontWeight.BOLD))
    return ft.Container(
        bgcolor=VERDICT_BG.get(term, "#374151"), border_radius=10,
        padding=ft.Padding(left=10, right=10, top=5, bottom=5),
        content=ft.Text(
            term, size=13,
            color="#FFD700" if term == "GOLDEN BET" else "#FFFFFF",
            weight=ft.FontWeight.BOLD))


def stance_pill(stance: str | None) -> ft.Container | None:
    """The stance pill — cool family, smaller than the verdict
    pill, never printed without one. None when the bet carries no
    stance (UNPRICED bets get none)."""
    if not stance or stance not in STANCE_BG:
        return None
    return ft.Container(
        bgcolor=STANCE_BG[stance], border_radius=8,
        padding=ft.Padding(left=8, right=8, top=3, bottom=3),
        content=ft.Text(STANCE_LABELS[stance], size=11,
                        color="#FFFFFF", weight=ft.FontWeight.BOLD))


def cal_chip(tag: str | None) -> ft.Container | None:
    """The calibration chip: an outlined tag with a status dot —
    information, never a gate (v5.2)."""
    if not tag:
        return None
    return ft.Container(
        border=_border_all(1, CHIP_BORDER), border_radius=8,
        padding=ft.Padding(left=6, right=6, top=2, bottom=2),
        content=ft.Row(spacing=4, tight=True, controls=[
            ft.Container(width=8, height=8, border_radius=4,
                         bgcolor=CAL_DOT.get(tag, FAINT)),
            ft.Text(tag, size=10, color=DIM,
                    weight=ft.FontWeight.BOLD)]))


def empty_full(icon, headline: str, body: str,
               action: ft.Control = None) -> ft.Container:
    """The full empty/error skeleton — ONE pattern, every screen:
    icon, headline, body, optional action, centered."""
    controls = [ft.Icon(icon, size=40, color=FAINT),
                ft.Text(headline, size=14, color=INK,
                        weight=ft.FontWeight.BOLD),
                ft.Text(body, size=12, color=DIM, height=1.35,
                        text_align=ft.TextAlign.CENTER)]
    if action is not None:
        controls.append(action)
    return ft.Container(
        padding=ft.Padding(left=16, right=16, top=32, bottom=16),
        content=ft.Column(spacing=8, horizontal_alignment=
                          ft.CrossAxisAlignment.CENTER,
                          controls=controls))


def empty_inline(icon, headline: str, body: str = "") -> ft.Row:
    """The inline empty state: icon + headline (+ body) on one or
    two lines, for empty panels inside a populated screen."""
    texts = [ft.Text(headline, size=12, color=DIM,
                     weight=ft.FontWeight.BOLD)]
    if body:
        texts.append(ft.Text(body, size=12, color=DIM, height=1.35))
    return ft.Row(spacing=8, vertical_alignment=
                  ft.CrossAxisAlignment.START,
                  controls=[ft.Icon(icon, size=16, color=FAINT),
                            ft.Column(spacing=2, tight=True,
                                      controls=texts)])


def screen_title(title: str, subtitle: str = "") -> ft.Column:
    controls = [ft.Text(title, size=18, color=INK,
                        weight=ft.FontWeight.BOLD)]
    if subtitle:
        controls.append(ft.Text(subtitle, size=11, color=FAINT))
    return ft.Column(spacing=2, tight=True, controls=controls)


def section_header(text: str, color: str = INK) -> ft.Text:
    return ft.Text(text, size=14, color=color,
                   weight=ft.FontWeight.BOLD)


def sport_header(sport: str, count: int) -> ft.Column:
    icon = SPORT_ICONS.get(sport, ft.Icons.SPORTS_FOOTBALL)
    return ft.Column(spacing=4, tight=True, controls=[
        ft.Container(padding=6, content=ft.Row(spacing=8, controls=[
            ft.Icon(icon, size=16, color=ACCENT),
            ft.Text(
                f"{SPORT_LABELS.get(sport, (sport or '—').upper())}"
                f" · {count} markets",
                size=13, color=INK, weight=ft.FontWeight.BOLD)])),
        ft.Divider(color=BORDER)])


def _market_dt(mkt):
    """The market's resolve datetime — the event's scheduled start
    (FanDuel marketTime) parsed to an aware datetime; None when the
    menu carried no usable time. Naive stamps are read as UTC."""
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


def resolve_date_label(mkt) -> str:
    """The calendar date a market resolves on, for headers and the
    Resolve-date sort — the event date in the viewer's timezone."""
    dt = _market_dt(mkt)
    if dt is None:
        return "Date not on the menu"
    return dt.astimezone().strftime("%a %b %d")


def is_quick(mkt, anchor) -> bool:
    """Quick bet: the market resolves within 0–2 hours of the
    anchor (the pull's own clock). Started-but-open events whose
    start sits inside the window's first hour also count — they
    resolve soonest of all."""
    dt = _market_dt(mkt)
    if dt is None or anchor is None:
        return False
    delta = (dt - anchor).total_seconds()
    return -3600 <= delta <= 2 * 3600


def search_hit(mkt, query: str) -> bool:
    """Cards search: the query against every text field the menu
    gave this market (matchup, market name, description, sport)."""
    if not query:
        return True
    hay = " ".join(str(v) for v in (mkt or {}).values()
                   if isinstance(v, str)).lower()
    return all(word in hay for word in query.lower().split())


def date_header(label: str, count: int) -> ft.Column:
    return ft.Column(spacing=4, tight=True, controls=[
        ft.Container(padding=6, content=ft.Row(spacing=8, controls=[
            ft.Icon(ft.Icons.CALENDAR_MONTH, size=16, color=ACCENT),
            ft.Text(f"{label} · {count} markets",
                    size=13, color=INK, weight=ft.FontWeight.BOLD)])),
        ft.Divider(color=BORDER)])


def lane_contexts(markets: list) -> dict:
    """Per-lane engine lookups (record / phi / calibration stamp /
    v5.2 tag) computed ONCE per render and shared by every card on
    it — before v7.1 each card re-ran all three lookups for its
    lane, hundreds of redundant passes on a full slate."""
    ctx = {}
    card = b5.load_scorecard()
    for m in markets:
        lane = market_lane(m)
        if lane not in ctx:
            w, l, src = b5.lane_record(lane)
            phi, phi_state, _d = b5.lane_phi(lane)
            ctx[lane] = (w, l, src, phi, phi_state,
                         b5.lane_uncalibrated(lane),
                         b5.calibration_tag(lane, card))
    return ctx


# ------------------------------------------------------------------
# Card rendering — one builder shared by the Cards screen, the
# BetFi finds feed and the Parse match block (a find IS a card,
# face + collapsible depth). Anatomy order is fixed (design
# report §2): matchup → meta → record → odds → hero probability
# row → grade row + calibration chip → verdict + stance pills →
# stamp / note → depth tiles.


def build_market_card(mkt: dict, verdict: dict, rec: dict,
                      quotes_by_game: dict, rank: int | None = None,
                      edge_pts: float | None = None,
                      lane_ctx: dict | None = None) -> ft.Container:
    lane = market_lane(mkt)
    if lane_ctx is not None and lane in lane_ctx:
        (w, l, rec_src, phi, phi_state, uncal, cal_tag) = \
            lane_ctx[lane]
    else:
        w, l, rec_src = b5.lane_record(lane)
        phi, phi_state, _detail = b5.lane_phi(lane)
        uncal = b5.lane_uncalibrated(lane)
        cal_tag = verdict.get("cal_tag") or \
            b5.calibration_tag(lane, b5.load_scorecard())
    p = verdict.get("p")
    grade = verdict.get("grade")
    term, vreason = card_verdict(verdict)
    state = verdict.get("state") or ""
    stance = verdict.get("stance")
    if verdict.get("cal_tag"):
        cal_tag = verdict["cal_tag"]
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
    face.append(ft.Text(matchup_title(mkt, verdict),
                        size=16, color=INK, weight=ft.FontWeight.BOLD))
    face.append(_line(f"#:{mkt.get('fd_event_id') or '—'} · "
                      f"{market_display_name(mkt)} · "
                      f"{SPORT_LABELS.get(mkt.get('sport'), mkt.get('sport', '?'))}",
                      10, FAINT))
    face.append(_line(f"Win {w} · Lose {l}   ({lane} lane record)",
                      11, DIM))
    _bits = []
    if mkt.get("price") is not None:
        price = int(mkt["price"])
        if mkt.get("sport") == "soccer":
            # world readers price in decimal: decimal first,
            # American in parentheses (language report W4)
            _bits.append(f"odds "
                         f"{b5.american_to_decimal(price):.2f} "
                         f"({price:+d})")
        else:
            _bits.append(f"odds {price:+d}")
    if mkt.get("line") is not None:
        _bits.append(f"line {mkt['line']} · {side_label(mkt)}")
    elif mkt.get("side"):
        _bits.append(side_label(mkt))
    if _bits:
        face.append(_line(" · ".join(_bits), 12, INK))
    # hero row: probability left (promoted), edge right, colored
    hero = [ft.Text(
        "Probability UNPRICED" if p is None else
        f"Probability {p * 100:.1f}%",
        size=20, color=WARN if p is None else INK,
        weight=ft.FontWeight.BOLD)]
    if p is not None and edge_pts is not None:
        hero.append(ft.Text(
            f"{edge_pts:+.1f} pts", size=14,
            color=EDGE_POS if edge_pts > 0 else
            EDGE_NEG if edge_pts < 0 else DIM,
            weight=ft.FontWeight.BOLD))
    face.append(ft.Row(spacing=8,
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                       controls=hero))
    # grade row: grade stays colored TEXT (never a pill), the
    # state beside it, the calibration chip right-aligned
    grade_row = [
        ft.Text(f"Grade {grade}" if grade else "Grade —",
                size=16, color=GRADE_COLORS.get(grade or "", FAINT),
                weight=ft.FontWeight.BOLD),
        ft.Text(state, size=12,
                color=DIM if state == "PRICED" else WARN,
                weight=ft.FontWeight.BOLD)]
    chip = cal_chip(cal_tag)
    if chip is not None:
        grade_row.append(ft.Container(expand=True))
        grade_row.append(chip)
    face.append(ft.Row(spacing=8, controls=grade_row))
    # pill row: verdict first, stance beside it — never a stance
    # without a verdict
    pills = [verdict_pill(term, unpriced=(state == "UNPRICED"))]
    sp = stance_pill(stance)
    if sp is not None:
        pills.append(sp)
    face.append(ft.Row(spacing=8, controls=pills))
    if uncal:
        # the engine's stamp, verbatim on the face
        face.append(_line(uncal, 11, WARN, True))
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
    if stance:
        anatomy.append(f"stance: {stance} — the shape of the bet "
                       f"(Terms); the verdict above decides")
    anatomy.append(f"calibration tag: {cal_tag or '—'}")
    if p is not None:
        anatomy.append(f"model probability (after calibration — "
                       f"see Terms: phi): {p * 100:.1f}%")
    if mkt.get("price") is not None:
        anatomy.append(f"pulled price: {int(mkt['price']):+d} "
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
    scale = [f"phi: {phi.get('kind', '?') if isinstance(phi, dict) else '?'}"
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
    if mkt.get("fd_market_id"):
        provenance.append(f"FanDuel market id: "
                            f"{mkt['fd_market_id']}")
    provenance.append(f"card rendered: "
                      f"{datetime.now().astimezone().isoformat(timespec='seconds')}")

    stripe_color = UNPRICED_BORDER if state == "UNPRICED" else \
        VERDICT_BG.get(term, BORDER)
    return ft.Container(
        bgcolor=CARD_BG, border_radius=10, padding=12,
        border=ft.Border(left=ft.BorderSide(3, stripe_color)),
        content=ft.Column(spacing=6, controls=face + [
            _tile("PRICE ANATOMY", "where the probability came from",
                  anatomy),
            _tile("SCALE",
                  "phi — the fitted map that adjusts this lane's "
                  "raw probabilities toward what its record has "
                  "earned", scale),
            _tile("COHERENCE",
                  "do this game's prices agree with each other?"
                  if mkt.get("sport") != "soccer" else
                  "do this match's prices agree with each other?",
                  coh_lines),
            _tile("PROVENANCE",
                  "where every number came from, and when",
                  provenance),
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
# Parse / Parlay / Solver math — module-level so the harness can
# test them without a page. All odds math goes through the
# engine's converters; the shell adds no pricing of its own.


def parse_slip_text(text: str) -> dict | None:
    """Read one pasted bet line. Handles the common slip shapes:
    "Team -3.5 (-110)", "Team +7", "Team ML +150",
    "Team moneyline -130", "Over 47.5 (-110)", "Under 41".
    Returns {selection, market, side, line, odds, implied} —
    or {"partial": True, "odds": ...} when a price was read but
    no market was — or None when nothing could be read."""
    raw = (text or "").strip()
    if not raw:
        return None
    t = " ".join(raw.split()).rstrip(",")
    odds = None
    m = re.search(r"\(\s*([+-]?\d{2,5})\s*\)\s*$", t)
    if m:
        odds = int(m.group(1))
        t = t[:m.start()].strip()
    low = t.lower()

    def done(selection, market, side, line, o):
        return {"selection": selection, "market": market,
                "side": side, "line": line, "odds": o,
                "implied": (b5.implied_prob(o) if o is not None
                            else None)}

    m = re.match(r"^(over|under)\s+(\d+(?:\.\d+)?)"
                 r"(?:\s+([+-]\d{2,5}))?$", low)
    if m:
        o = odds if odds is not None else \
            (int(m.group(3)) if m.group(3) else None)
        return done(m.group(1).capitalize(), "totals",
                    m.group(1), float(m.group(2)), o)
    m = re.match(r"^(.*?)\s+(?:ml|moneyline)"
                 r"(?:\s+([+-]\d{2,5}))?$", t, re.IGNORECASE)
    if m and m.group(1).strip():
        o = odds if odds is not None else \
            (int(m.group(2)) if m.group(2) else None)
        return done(m.group(1).strip(), "moneyline", None, None, o)
    m = re.match(r"^(.*?)\s+([+-]\d+(?:\.\d+)?)"
                 r"(?:\s+([+-]\d{2,5}))?$", t)
    if m and m.group(1).strip():
        num = m.group(2)
        val = float(num)
        if "." not in num and abs(val) >= 100:
            # a bare price with no line and no market word:
            # the price was read, the market was not
            return {"partial": True, "odds": int(val),
                    "selection": m.group(1).strip()}
        o = odds if odds is not None else \
            (int(m.group(3)) if m.group(3) else None)
        return done(m.group(1).strip(), "spread", None, val, o)
    if odds is not None:
        return {"partial": True, "odds": odds, "selection": t}
    return None


def _nfl_code_for(selection: str) -> str | None:
    """Map a typed NFL team reference (city, nickname or full
    name) to the engine's team code, via the engine's own table."""
    sel = (selection or "").strip().lower()
    if not sel:
        return None
    for full, code in b5.FD_NFL_TEAM_CODES.items():
        fl = full.lower()
        if sel == fl or sel == code.lower() or fl.endswith(sel) \
                or sel in fl:
            return code
    return None


def find_parsed_match(parsed: dict, markets: list,
                      verdicts: list):
    """The (market, verdict) from the last pull that a parsed bet
    refers to — matched on market, side/team and line when the
    slip named one. None when the pull holds no such market:
    nothing is assumed."""
    if not parsed or parsed.get("partial"):
        return None
    market = parsed.get("market")
    for mkt, verdict in zip(markets, verdicts):
        if mkt.get("market") != market:
            continue
        if market == "totals":
            if mkt.get("side") != parsed.get("side"):
                continue
            if parsed.get("line") is not None and \
                    mkt.get("line") != parsed["line"]:
                continue
            return mkt, verdict
        sel = (parsed.get("selection") or "").lower()
        side_team = (mkt.get(mkt.get("side") or "") or "").lower()
        hit = bool(sel) and (sel in side_team or side_team in sel)
        if not hit and mkt.get("sport") == "nfl":
            code = _nfl_code_for(parsed.get("selection") or "")
            hit = bool(code) and side_team == code.lower()
        if not hit:
            continue
        if market == "spread" and parsed.get("line") is not None \
                and mkt.get("line") != parsed["line"]:
            continue
        return mkt, verdict
    return None


def solver_stake_for_profit(target_profit: float,
                            american: int) -> float:
    """Stake whose WIN returns exactly target_profit at the given
    American odds: stake = profit / (decimal - 1)."""
    dec = b5.american_to_decimal(american)
    return target_profit / (dec - 1)


def solver_kelly(bankroll: float, american: int,
                 model_p: float) -> dict:
    """Full Kelly fraction f = (b*p - q) / b with b = decimal - 1,
    and the full / half / quarter stakes on the bankroll."""
    dec = b5.american_to_decimal(american)
    b = dec - 1
    f = (b * model_p - (1 - model_p)) / b if b > 0 else 0.0
    return {"f": f, "full": bankroll * f,
            "half": bankroll * f / 2, "quarter": bankroll * f / 4}


def solver_hedge(stake1: float, odds1: int, odds2: int) -> dict:
    """Equal-return hedge: hedge stake h = stake1 * dec1 / dec2
    makes both outcomes pay stake1 * dec1 total; the guaranteed
    figure is that payout minus both stakes (negative = the
    hedge locks a loss, printed as one)."""
    dec1 = b5.american_to_decimal(odds1)
    dec2 = b5.american_to_decimal(odds2)
    h = stake1 * dec1 / dec2
    return {"hedge_stake": h, "payout": stake1 * dec1,
            "guaranteed": stake1 * dec1 - stake1 - h}


def parlay_combine(legs: list) -> dict:
    """Combined figures for a slip of (market, verdict) legs, all
    PRICED. Combined odds are the product of the legs' decimal
    odds; the combined model probability is the product of the
    legs' probabilities — which assumes the legs are independent
    (the Parlay page prints that assumption; same-game legs
    rarely satisfy it). The verdict uses the ladder's language;
    the stance is the engine's parlay_stance."""
    dec = 1.0
    p = 1.0
    for mkt, v in legs:
        dec *= b5.american_to_decimal(int(mkt["price"]))
        p *= v["p"]
    implied = 1.0 / dec
    ev = p * (dec - 1) - (1 - p)
    edge_pts = (p - implied) * 100
    conflicts = []
    by_game = {}
    for mkt, _v in legs:
        by_game.setdefault(
            (mkt.get("sport"), mkt.get("away"), mkt.get("home")),
            []).append(mkt)
    for _game, ms in by_game.items():
        tots = {m.get("side") for m in ms
                if m.get("market") == "totals"}
        if "over" in tots and "under" in tots:
            conflicts.append("over and under on the same game — "
                             "the legs fight each other")
        mls = {m.get("side") for m in ms
               if m.get("market") == "moneyline"}
        if "home" in mls and "away" in mls:
            conflicts.append("both sides of the same moneyline — "
                             "the legs fight each other")
        sps = {m.get("side") for m in ms
               if m.get("market") in ("spread", "alt-spread")}
        if "home" in sps and "away" in sps:
            conflicts.append("both sides of the same spread — the "
                             "legs fight each other")
    terms = [card_verdict(v)[0] for _m, v in legs]
    if any(t == "DO NOT BET" for t in terms):
        verdict = "DO NOT BET"
    elif conflicts:
        verdict = "RISK BET (DO NOT BET)"
    elif edge_pts <= 0:
        verdict = "DO NOT BET"
    elif edge_pts >= 3 and all(t in ("BET HERE", "GOLDEN BET")
                               for t in terms):
        verdict = "BET HERE"
    else:
        verdict = "RISK BET (BET)"
    return {"decimal": dec, "american": b5.decimal_to_american(dec),
            "model_p": p, "implied": implied, "ev": ev,
            "edge_pts": edge_pts, "verdict": verdict,
            "stance": b5.parlay_stance(
                [v.get("stance") for _m, v in legs]),
            "conflicts": conflicts}


# ------------------------------------------------------------------
# The app


def main(page: ft.Page):
    page.title = DISPLAY_NAME
    page.bgcolor = PAGE_BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 12
    page.spacing = 8
    page.scroll = ft.ScrollMode.AUTO

    state = {"slate": load_snapshot(), "verdicts": None,
             "sort": "verdict", "card_limit": CARD_PAGE, "search": "",
             "toggles": {"priced_only": False, "golden_only": False,
                         "hide_dnb": False, "quick_only": False,
                         "sports": {}},
             "parlay_legs": [], "view": "cards"}
    stamp_text, degraded = stamp_of(state["slate"])
    stamp_ctrl = ft.Text(f"Menu: {stamp_text}", size=12,
                         color=WARN if degraded else DIM)
    status = ft.Text("", size=12, color=ACCENT)

    # view containers — top-level five plus the More sub-views
    cards_view = ft.Column(spacing=8)
    parse_view = ft.Column(spacing=8, visible=False)
    parlay_view = ft.Column(spacing=8, visible=False)
    solver_view = ft.Column(spacing=8, visible=False)
    more_view = ft.Column(spacing=8, visible=False)
    betfi_view = ft.Column(spacing=8, visible=False)
    record_view = ft.Column(spacing=8, visible=False)
    terms_view = ft.Column(spacing=8, visible=False)
    equations_view = ft.Column(spacing=8, visible=False)
    dev_view = ft.Column(spacing=8, visible=False)
    views = {"cards": cards_view, "parse": parse_view,
             "parlay": parlay_view, "solver": solver_view,
             "more": more_view, "betfi": betfi_view,
             "record": record_view, "terms": terms_view,
             "equations": equations_view, "dev": dev_view}
    TOP_VIEWS = ["cards", "parse", "parlay", "solver", "more"]

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

    # ---------------- Cards ----------------

    cards_toggles = ft.Column(spacing=2, tight=True)
    cards_count = ft.Text("", size=11, color=FAINT)
    cards_list = ft.Column(spacing=8)

    def sorted_entries():
        """(market, verdict, edge) triples in the Card screen's
        current sort. Verdicts come from the cached checker pass —
        sorting never re-prices."""
        rec = state["slate"]
        verdicts = ensure_verdicts() or []
        markets = rec.get("markets", [])
        entries = [(m, v, market_edge_pts(m, v))
                   for m, v in zip(markets, verdicts)]
        mode = state["sort"]

        def edge_key(t):
            return -(t[2] if t[2] is not None else -1e9)

        if mode == "verdict":
            entries.sort(key=lambda t: (
                verdict_rank(card_verdict(t[1])[0]), edge_key(t)))
        elif mode == "no-bet-first":
            entries.sort(key=lambda t: (
                -verdict_rank(card_verdict(t[1])[0]), edge_key(t)))
        elif mode == "edge":
            entries.sort(key=edge_key)
        elif mode == "grade":
            entries.sort(key=lambda t: (
                grade_rank(t[1].get("grade")), edge_key(t)))
        elif mode == "probability":
            entries.sort(key=lambda t: -(
                t[1].get("p") if t[1].get("p") is not None
                else -1.0))
        elif mode == "time":
            entries.sort(key=lambda t: (
                t[0].get("market_time") or "9999",
                t[0].get("desc") or ""))
        elif mode == "resolve":
            far = datetime.max.replace(tzinfo=timezone.utc)
            entries.sort(key=lambda t: (
                _market_dt(t[0]) or far,
                t[0].get("desc") or ""))
        return entries

    def _anchor():
        """The Quick-bets clock: the pull's own timestamp, parsed;
        now() when the slate carries no readable stamp."""
        rec = state.get("slate") or {}
        raw = rec.get("pulled_at")
        if raw:
            try:
                dt = datetime.fromisoformat(
                    str(raw).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.astimezone()
                return dt
            except ValueError:
                pass
        return datetime.now().astimezone()

    def apply_toggles(entries):
        """The Cards toggles, over the cached verdicts — display
        only, never a re-price."""
        t = state["toggles"]
        out = []
        for m, v, e in entries:
            if t["priced_only"] and v.get("state") != "PRICED":
                continue
            if t["golden_only"] and \
                    card_verdict(v)[0] != "GOLDEN BET":
                continue
            if t["hide_dnb"] and \
                    card_verdict(v)[0] == "DO NOT BET":
                continue
            if not t["sports"].get(m.get("sport"), True):
                continue
            if t.get("quick_only") and not is_quick(m, _anchor()):
                continue
            if not search_hit(m, state.get("search") or ""):
                continue
            out.append((m, v, e))
        return out

    def on_sort(e):
        state["sort"] = e.control.value or "verdict"
        state["card_limit"] = CARD_PAGE
        render_cards()

    def on_search(e):
        state["search"] = e.control.value or ""
        state["card_limit"] = CARD_PAGE
        render_cards()

    def on_show_more(_e):
        state["card_limit"] += CARD_PAGE
        render_cards()

    def _switch(label, value, handler):
        return ft.Switch(label=label, value=value,
                         active_color=ACCENT, on_change=handler,
                         label_text_style=ft.TextStyle(size=11,
                                                       color=DIM))

    def render_cards():
        cards_list.controls = []
        cards_toggles.controls = []
        rec = state["slate"]
        if not rec:
            cards_count.value = ""
            cards_list.controls = [empty_full(
                ft.Icons.CLOUD_OFF, "No pull yet",
                "Tap Pull Menu — until a live pull lands, every "
                "market is UNVERIFIED, never assumed.")]
            page.update()
            return
        entries = sorted_entries()
        # toggle rows: the three view toggles + one switch per
        # sport actually present in this pull
        t = state["toggles"]
        present = []
        for m, _v, _e in entries:
            s = m.get("sport")
            if s not in present:
                present.append(s)
            t["sports"].setdefault(s, True)
        order = ["nfl", "ncaaf", "nba", "nhl", "mlb", "soccer"]
        present.sort(key=lambda s: order.index(s)
                     if s in order else 99)
        rows = [
            _switch("Priced only", t["priced_only"],
                    lambda e: _toggle("priced_only", e)),
            _switch("Golden only", t["golden_only"],
                    lambda e: _toggle("golden_only", e)),
            _switch("Hide DO NOT BET", t["hide_dnb"],
                    lambda e: _toggle("hide_dnb", e)),
            _switch("Quick bets (\u22642h)", t["quick_only"],
                    lambda e: _toggle("quick_only", e))]
        for s in present:
            rows.append(_switch(
                SPORT_LABELS.get(s, (s or "?").upper()),
                t["sports"].get(s, True),
                lambda e, s=s: _toggle_sport(s, e)))
        cards_toggles.controls = [ft.Row(spacing=12, wrap=True,
                                         controls=rows)]
        shown = apply_toggles(entries)
        if len(shown) != len(entries):
            cards_count.value = f"{len(shown)} of {len(entries)} markets"
        else:
            cards_count.value = f"{len(entries)} markets"
        markets = rec.get("markets", [])
        quotes = game_quotes(markets)
        ctx = lane_contexts(markets)
        limit = state["card_limit"]
        grouped = state["sort"] in ("pull", "time")
        by_date = state["sort"] == "resolve"
        last_sport = None
        last_date = None
        for mkt, verdict, edge in shown[:limit]:
            if by_date:
                label = resolve_date_label(mkt)
                if label != last_date:
                    last_date = label
                    n_day = sum(1 for e in shown
                                if resolve_date_label(e[0]) == label)
                    cards_list.controls.append(
                        date_header(label, n_day))
            elif grouped and mkt.get("sport") != last_sport:
                last_sport = mkt.get("sport")
                n_sport = sum(1 for e in shown
                              if e[0].get("sport") == last_sport)
                cards_list.controls.append(
                    sport_header(last_sport, n_sport))
            cards_list.controls.append(build_market_card(
                mkt, verdict, rec, quotes, edge_pts=edge,
                lane_ctx=ctx))
        if not shown:
            cards_list.controls.append(empty_inline(
                ft.Icons.SEARCH_OFF, "No markets pass the toggles",
                "Loosen a toggle — the pull itself is unchanged."))
        elif len(shown) > limit:
            cards_list.controls.append(ft.Button(
                f"Show more ({len(shown) - limit} more)",
                on_click=on_show_more))
            cards_list.controls.append(ft.Text(
                "Paging is display only — every market was priced "
                "by the same checker pass.", size=10, color=FAINT))
        page.update()

    def _toggle(key, e):
        state["toggles"][key] = bool(e.control.value)
        state["card_limit"] = CARD_PAGE
        render_cards()

    def _toggle_sport(sport, e):
        state["toggles"]["sports"][sport] = bool(e.control.value)
        state["card_limit"] = CARD_PAGE
        render_cards()

    # ---------------- pull / price workers ----------------

    def on_pull(_e):
        status.value = "Pulling the live FanDuel menu…"
        page.update()
        page.run_thread(_pull_worker)

    def _pull_worker():
        # Off the event-handler thread (page.run_thread): the pull
        # plus the first render's pricing pass can take a minute or
        # more, and doing it inside the click handler froze the app
        # on-device behind Dart null-check error banners (v7.0,
        # 2026-10-20). A failure now lands in the status line as
        # the actual Python error — visible, never silent.
        try:
            rec = pull_menu()
            state["slate"] = rec
            state["verdicts"] = None
            state["card_limit"] = CARD_PAGE
            state["parlay_legs"] = []
            save_snapshot(rec)
            refresh_stamp()
            if rec.get("verified"):
                per = ", ".join(
                    f"{s}: {v.get('slate_markets', 0)} markets"
                    for s, v in rec["sports"].items()
                    if "error" not in v)
                failed = ", ".join(
                    s for s, v in rec["sports"].items()
                    if "error" in v)
                status.value = (f"Pulled {len(rec['markets'])} "
                                f"primary markets ({per})"
                                + (f" · UNVERIFIED scopes: {failed}"
                                   if failed else ""))
            else:
                err = rec.get("tree_error") or "no markets returned"
                status.value = (f"Pull didn't land — {err}. Wasn't "
                                f"nothing assumed in its place; "
                                f"every market stamps UNPRICED.")
            render_cards()
            page.update()
        except Exception as e:
            status.value = (f"Pull failed on this device: "
                            f"{type(e).__name__}: {e}")
            try:
                page.update()
            except Exception:
                pass

    def on_price(_e):
        if not state["slate"]:
            status.value = "Nothing to price yet — Pull Menu first."
            page.update()
            return
        status.value = "Pricing the slate…"
        page.update()
        page.run_thread(_price_worker)

    def _price_worker():
        # Same off-thread rule as _pull_worker.
        try:
            state["verdicts"] = None  # re-run checkers on the pull
            state["parlay_legs"] = []
            verdicts = ensure_verdicts()
            priced = sum(1 for v in verdicts
                         if v.get("state") == "PRICED")
            status.value = (f"Priced slate: {len(verdicts)} markets "
                            f"checked · {priced} PRICED · the rest "
                            f"stamped, never guessed.")
            render_cards()
            page.update()
        except Exception as e:
            status.value = (f"Pricing failed on this device: "
                            f"{type(e).__name__}: {e}")
            try:
                page.update()
            except Exception:
                pass


    # ---------------- Parse ----------------

    parse_field = ft.TextField(
        multiline=True, min_lines=3, max_lines=5, text_size=13,
        border_color=CHIP_BORDER, focused_border_color=ACCENT,
        hint_text="Lions -3.5 (-110)")
    parse_result = ft.Column(spacing=8)

    def _kv_row(label, value, label_color=FAINT, value_size=12):
        return ft.Row(spacing=8, controls=[
            ft.Container(width=110, content=ft.Text(
                label, size=11, color=label_color)),
            ft.Text(value, size=value_size, color=INK)])

    def render_parse():
        parse_view.controls = [screen_title(
            "Parse", "Read a pasted bet against the current pull.")]
        rec = state["slate"]
        if not rec:
            parse_view.controls.append(empty_full(
                ft.Icons.CLOUD_OFF, "No pull yet",
                "Tap Pull Menu — until a live pull lands, every "
                "market is UNVERIFIED, never assumed."))
            page.update()
            return
        parse_view.controls.append(ft.Container(
            bgcolor=CARD_BG, border_radius=10, padding=12,
            content=ft.Column(spacing=8, controls=[
                parse_field,
                ft.Button("Parse", on_click=on_parse,
                          width=float("inf"))])))
        if not parse_result.controls:
            parse_result.controls = [ft.Text(
                "Nothing parsed yet. Paste a bet — teams, market, "
                "line, price — and the app will price it against "
                "the current pull. A bet it can't match to the "
                "pull gets stamped, not guessed.",
                size=12, color=DIM, height=1.35)]
        parse_view.controls.append(parse_result)
        page.update()

    def on_parse(_e):
        parse_result.controls = []
        parsed = parse_slip_text(parse_field.value or "")
        if parsed is None:
            parse_result.controls.append(ft.Row(
                spacing=8, vertical_alignment=
                ft.CrossAxisAlignment.START, controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=16,
                            color=BAD),
                    ft.Column(spacing=2, tight=True, controls=[
                        ft.Text("Couldn't read that", size=12,
                                color=BAD, weight=ft.FontWeight.BOLD),
                        ft.Text("Try one line per bet, like: "
                                "Lions -3.5 (-110)", size=12,
                                color=DIM, height=1.35)])]))
            page.update()
            return
        rows = []
        if parsed.get("selection"):
            rows.append(_kv_row("Selection", parsed["selection"]))
        if parsed.get("partial"):
            if parsed.get("odds") is not None:
                rows.append(_kv_row("Odds",
                                    f"{parsed['odds']:+d}"))
                rows.append(_kv_row(
                    "Implied %",
                    f"{b5.implied_prob(parsed['odds']) * 100:.1f}%"))
            parse_result.controls.append(ft.Container(
                bgcolor=RAISED, border_radius=8, padding=12,
                content=ft.Column(spacing=4, controls=rows)))
            parse_result.controls.append(ft.Text(
                "Parsed the price but not the market. Name the "
                "market (moneyline / spread / total) and parse "
                "again.", size=12, color=DIM, height=1.35))
            page.update()
            return
        disp = market_display_name(
            {"market": parsed["market"], "sport": None})
        rows.append(_kv_row("Market", disp))
        if parsed.get("line") is not None:
            rows.append(_kv_row("Line", f"{parsed['line']:+g}"))
        if parsed.get("odds") is not None:
            rows.append(_kv_row("Odds", f"{parsed['odds']:+d}"))
            rows.append(_kv_row(
                "Implied %", f"{parsed['implied'] * 100:.1f}%"))
        parse_result.controls.append(ft.Container(
            bgcolor=RAISED, border_radius=8, padding=12,
            content=ft.Column(spacing=4, controls=rows)))
        rec = state["slate"]
        verdicts = ensure_verdicts() or []
        markets = rec.get("markets", [])
        found = find_parsed_match(parsed, markets, verdicts)
        if found is None:
            parse_result.controls.append(empty_inline(
                ft.Icons.SEARCH_OFF, "No matching market",
                "No match in the current pull for that bet. Pull "
                "the menu, or check the teams and market — nothing "
                "was assumed."))
        else:
            mkt, verdict = found
            parse_result.controls.append(section_header(
                "MATCH IN THE LAST PULL", ACCENT))
            parse_result.controls.append(build_market_card(
                mkt, verdict, rec, game_quotes(markets),
                edge_pts=market_edge_pts(mkt, verdict),
                lane_ctx=lane_contexts(markets)))
        page.update()

    # ---------------- Parlay ----------------

    parlay_msg = ft.Text("", size=11, color=WARN)

    def priced_options():
        """The last pull's PRICED legs, in pull order."""
        rec = state["slate"]
        if not rec:
            return []
        verdicts = ensure_verdicts() or []
        return [(m, v) for m, v in zip(rec.get("markets", []),
                                       verdicts)
                if v.get("state") == "PRICED"
                and m.get("price") is not None
                and v.get("p") is not None]

    def render_parlay():
        parlay_view.controls = [screen_title(
            "Parlay", "Priced legs only — built from the last pull.")]
        rec = state["slate"]
        if not rec:
            parlay_view.controls.append(empty_full(
                ft.Icons.CLOUD_OFF, "No pull yet",
                "Tap Pull Menu — until a live pull lands, every "
                "market is UNVERIFIED, never assumed."))
            page.update()
            return
        options = priced_options()
        state["priced_options"] = options
        legs = state["parlay_legs"]
        if legs:
            for i, (mkt, verdict) in enumerate(legs):
                edge = market_edge_pts(mkt, verdict)
                meta = (f"{int(mkt['price']):+d} · model "
                        f"{verdict['p'] * 100:.1f}% · edge "
                        f"{edge:+.1f} pts" if edge is not None
                        else f"{int(mkt['price']):+d}")
                parlay_view.controls.append(ft.Container(
                    bgcolor=RAISED, border_radius=8, padding=8,
                    content=ft.Row(
                        spacing=8, alignment=
                        ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(spacing=2, tight=True,
                                      controls=[
                                          ft.Text(
                                              verdict.get("desc")
                                              or matchup_title(
                                                  mkt, verdict),
                                              size=13, color=INK,
                                              weight=ft.FontWeight
                                              .BOLD),
                                          ft.Text(meta, size=11,
                                                  color=DIM)]),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE, icon_size=16,
                                icon_color=FAINT, width=40,
                                height=40,
                                on_click=lambda _e, i=i:
                                on_remove_leg(i))])))
        else:
            parlay_view.controls.append(empty_inline(
                ft.Icons.RECEIPT_LONG, "No legs yet",
                "Add priced legs from the last pull and the "
                "combined price builds here."))
        if not options:
            parlay_view.controls.append(empty_inline(
                ft.Icons.SEARCH_OFF, "No priced legs on this pull",
                "Every market on this pull is UNPRICED — there is "
                "nothing honest to combine."))
        else:
            in_legs = {id(m) for m, _v in legs}
            avail = [(i, m, v) for i, (m, v) in enumerate(options)
                     if id(m) not in in_legs]
            dd = ft.Dropdown(
                value=None, width=float("inf"),
                options=[ft.DropdownOption(
                    key=str(i),
                    text=f"{v.get('desc') or matchup_title(m, v)}"
                         f" · {int(m['price']):+d}")
                    for i, m, v in avail],
                on_select=lambda e: state.update(
                    {"parlay_pick": e.control.value}))
            parlay_view.controls.append(ft.Row(spacing=8, controls=[
                dd, ft.Button("Add leg", on_click=on_add_leg)]))
            parlay_view.controls.append(parlay_msg)
        if legs:
            parlay_view.controls.append(_combined_block(legs))
        page.update()

    def _combined_block(legs):
        c = parlay_combine(legs)
        rows = [_kv_row("Legs", str(len(legs))),
                ft.Row(spacing=8, controls=[
                    ft.Container(width=110, content=ft.Text(
                        "Combined odds", size=11, color=FAINT)),
                    ft.Text(f"{c['american']:+d}", size=20,
                            color=INK, weight=ft.FontWeight.BOLD)]),
                _kv_row("Decimal odds", f"{c['decimal']:.2f}"),
                _kv_row("Implied %", f"{c['implied'] * 100:.1f}%"),
                _kv_row("Model %", f"{c['model_p'] * 100:.1f}%"),
                ft.Row(spacing=8, controls=[
                    ft.Container(width=110, content=ft.Text(
                        "Edge", size=11, color=FAINT)),
                    ft.Text(f"{c['edge_pts']:+.1f} pts", size=12,
                            color=EDGE_POS if c["edge_pts"] > 0
                            else EDGE_NEG if c["edge_pts"] < 0
                            else DIM,
                            weight=ft.FontWeight.BOLD)]),
                _kv_row("EV per $1",
                        f"{'+' if c['ev'] >= 0 else '-'}"
                        f"${abs(c['ev']):.2f}")]
        pills = [verdict_pill(c["verdict"])]
        sp = stance_pill(c["stance"])
        if sp is not None:
            pills.append(sp)
        rows.append(ft.Row(spacing=8, controls=pills))
        if c["stance"]:
            rows.append(ft.Text(
                f"Slip stance: {c['stance']} — the longest shot "
                f"on the slip sets it.", size=11, color=DIM))
        for note in c["conflicts"]:
            rows.append(ft.Row(spacing=6, controls=[
                ft.Icon(ft.Icons.WARNING_AMBER, size=14, color=WARN),
                ft.Text(note, size=11, color=WARN)]))
        rows.append(ft.Text(
            "Combined probability = product of the legs' "
            "probabilities. That assumes the legs are independent "
            "— treat it as a ceiling, and expect same-game legs "
            "to break the assumption.", size=10, color=FAINT,
            height=1.35))
        return ft.Container(
            bgcolor=RAISED, border=_border_all(1, CHIP_BORDER),
            border_radius=10, padding=12,
            content=ft.Column(spacing=6, controls=rows))

    def on_add_leg(_e):
        pick = state.get("parlay_pick")
        options = state.get("priced_options") or []
        if pick is None:
            parlay_msg.value = "Pick a leg from the list first."
            page.update()
            return
        if len(state["parlay_legs"]) >= 4:
            parlay_msg.value = "A slip holds at most 4 legs here."
            page.update()
            return
        mkt, verdict = options[int(pick)]
        if any(m is mkt for m, _v in state["parlay_legs"]):
            parlay_msg.value = "That leg is already on the slip."
            page.update()
            return
        parlay_msg.value = ""
        state["parlay_legs"].append((mkt, verdict))
        render_parlay()

    def on_remove_leg(i):
        if 0 <= i < len(state["parlay_legs"]):
            state["parlay_legs"].pop(i)
        render_parlay()

    # ---------------- Solver ----------------

    def _num_field(label):
        return ft.Column(spacing=2, tight=True, controls=[
            ft.Text(label, size=11, color=FAINT),
            ft.TextField(width=170, text_size=13,
                         border_color=CHIP_BORDER,
                         focused_border_color=ACCENT,
                         keyboard_type=ft.KeyboardType.NUMBER)])

    def _num(field):
        try:
            return float((field.value or "").strip()
                         .replace("$", "").replace("%", "")
                         .replace(",", ""))
        except (ValueError, AttributeError):
            return None

    def _odds(field):
        v = _num(field)
        if v is None or abs(v) < 100:
            return None
        return int(v)

    tp_profit = _num_field("Target profit ($)")
    tp_odds = _num_field("Book odds (American)")
    tp_err = ft.Text("", size=11, color=BAD)
    tp_result = ft.Column(spacing=2)
    k_bank = _num_field("Bankroll ($)")
    k_odds = _num_field("Book odds (American)")
    k_prob = _num_field("Your model probability (%)")
    k_err = ft.Text("", size=11, color=BAD)
    k_result = ft.Column(spacing=2)
    h_stake = _num_field("Original stake ($)")
    h_odds1 = _num_field("Original odds (American)")
    h_odds2 = _num_field("Hedge odds (American)")
    h_err = ft.Text("", size=11, color=BAD)
    h_result = ft.Column(spacing=2)

    def _solver_block(title, desc, fields, on_solve, err, result,
                      extra=None):
        controls = [ft.Text(title, size=14, color=ACCENT,
                            weight=ft.FontWeight.BOLD),
                    ft.Text(desc, size=11, color=DIM)]
        controls.append(ft.Row(spacing=12, wrap=True,
                               controls=fields))
        controls.append(ft.Button("Solve", on_click=on_solve))
        controls.append(err)
        controls.append(result)
        if extra is not None:
            controls.append(extra)
        return ft.Container(bgcolor=RAISED, border_radius=10,
                            padding=12,
                            content=ft.Column(spacing=8,
                                              controls=controls))

    def on_solve_profit(_e):
        tp_result.controls = []
        target = _num(tp_profit.controls[1])
        odds = _odds(tp_odds.controls[1])
        if target is None or odds is None or target <= 0:
            tp_err.value = "Enter a number for every field."
            page.update()
            return
        tp_err.value = ""
        stake = solver_stake_for_profit(target, odds)
        dec = b5.american_to_decimal(odds)
        tp_result.controls = [
            ft.Text(f"Stake ${stake:,.2f}", size=18, color=INK,
                    weight=ft.FontWeight.BOLD),
            ft.Text(f"at {odds:+d} (decimal {dec:.2f}) — a win "
                    f"pays ${stake * dec:,.2f} total, "
                    f"${target:,.2f} of it profit; a loss loses "
                    f"the stake.", size=12, color=DIM)]
        page.update()

    def on_solve_kelly(_e):
        k_result.controls = []
        bank = _num(k_bank.controls[1])
        odds = _odds(k_odds.controls[1])
        pct = _num(k_prob.controls[1])
        if bank is None or odds is None or pct is None \
                or bank <= 0 or not (0 < pct < 100):
            k_err.value = "Enter a number for every field."
            page.update()
            return
        k_err.value = ""
        r = solver_kelly(bank, odds, pct / 100)
        if r["f"] <= 0:
            k_result.controls = [ft.Text(
                f"No Kelly stake — at this price the model "
                f"probability gives no edge (Kelly fraction "
                f"{r['f']:.3f}).", size=12, color=DIM)]
        else:
            k_result.controls = [
                ft.Text(f"Full Kelly stake ${r['full']:,.2f}",
                        size=18, color=INK,
                        weight=ft.FontWeight.BOLD),
                ft.Text(f"Half Kelly stake ${r['half']:,.2f} · "
                        f"Quarter Kelly stake "
                        f"${r['quarter']:,.2f} (what this app "
                        f"uses) · fraction {r['f']:.3f}",
                        size=12, color=DIM)]
        page.update()

    def on_solve_hedge(_e):
        h_result.controls = []
        s1 = _num(h_stake.controls[1])
        o1 = _odds(h_odds1.controls[1])
        o2 = _odds(h_odds2.controls[1])
        if s1 is None or o1 is None or o2 is None or s1 <= 0:
            h_err.value = "Enter a number for every field."
            page.update()
            return
        h_err.value = ""
        r = solver_hedge(s1, o1, o2)
        g = r["guaranteed"]
        if g >= 0:
            support = (f"Guaranteed profit ${g:,.2f} — both "
                       f"outcomes pay ${r['payout']:,.2f} total.")
        else:
            support = (f"locks a loss of ${-g:,.2f} — both "
                       f"outcomes pay ${r['payout']:,.2f}, less "
                       f"than the ${s1 + r['hedge_stake']:,.2f} "
                       f"staked across both sides.")
        h_result.controls = [
            ft.Text(f"Hedge stake ${r['hedge_stake']:,.2f}",
                    size=18, color=INK, weight=ft.FontWeight.BOLD),
            ft.Text(support, size=12, color=DIM)]
        page.update()

    KELLY_WARNING = (
        "Read this before the number. Full Kelly assumes your "
        "probability is exactly right. It never is. If your true "
        "chance is even a few points below the number you typed, "
        "full-Kelly sizing stops being aggressive and starts "
        "being a fast way to shrink a bankroll — the losses "
        "compound before the edge can average out. That is why "
        "BetFi sizes at quarter-Kelly and treats the full-Kelly "
        "figure as a ceiling, not a target. If you don't have a "
        "model probability you can defend, you don't have a "
        "Kelly stake — you have a guess with a formula on it.")

    def render_solver():
        solver_view.controls = [
            screen_title("Solver",
                         "The arithmetic, in the open."),
            _solver_block(
                "STAKE FOR TARGET PROFIT",
                "How much to stake so a win returns the profit "
                "you name.",
                [tp_profit, tp_odds], on_solve_profit, tp_err,
                tp_result),
            _solver_block(
                "KELLY SIZING",
                "The stake a probability earns, at full, half "
                "and quarter Kelly.",
                [k_bank, k_odds, k_prob], on_solve_kelly, k_err,
                k_result,
                extra=ft.Text(KELLY_WARNING, size=11, color=WARN,
                              height=1.35)),
            _solver_block(
                "HEDGE — EQUAL RETURN",
                "The hedge stake that pays the same total "
                "whichever side wins.",
                [h_stake, h_odds1, h_odds2], on_solve_hedge,
                h_err, h_result)]
        page.update()


    # ---------------- More + sub-views ----------------

    def _sub_header(title, subtitle=""):
        return ft.Row(spacing=8, controls=[
            ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=ACCENT,
                          on_click=lambda _e: show("more")),
            screen_title(title, subtitle)])

    def render_more():
        tiles = [
            (ft.Icons.SEARCH, "BetFi finds",
             "Golden bets and the ranked finds feed", "betfi"),
            (ft.Icons.LIST, "Record",
             "Lane ledger and the latest pull", "record"),
            (ft.Icons.MENU_BOOK, "Terms",
             "What every word on a card means", "terms"),
            (ft.Icons.FUNCTIONS, "Equations",
             "The math, in the open", "equations"),
            (ft.Icons.CODE, "Dev",
             "Version, fingerprint, credit", "dev")]
        controls = [screen_title("More", "Everything else in BetFi.")]
        for icon, title, sub, target in tiles:
            controls.append(ft.ListTile(
                leading=ft.Icon(icon, color=ACCENT),
                title=ft.Text(title, size=14, color=INK),
                subtitle=ft.Text(sub, size=11, color=FAINT),
                trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT,
                                 color=FAINT),
                on_click=lambda _e, t=target: show(t)))
            controls.append(ft.Divider(color=BORDER))
        more_view.controls = controls
        page.update()

    # ---------------- BetFi finds ----------------

    def render_betfi():
        betfi_view.controls = [_sub_header(
            "BetFi — finds feed",
            "Golden bets first, then the ranked finds.")]
        rec = state["slate"]
        if not rec:
            betfi_view.controls.append(empty_full(
                ft.Icons.CLOUD_OFF, "Nothing to distill",
                "The feed distills the current pull — pull the "
                "menu on the Cards screen first."))
            page.update()
            return
        verdicts = ensure_verdicts()
        markets = rec.get("markets", [])
        quotes = game_quotes(markets)
        ctx = lane_contexts(markets)
        golden, finds, flagged, counter = distill_finds(markets,
                                                         verdicts)
        betfi_view.controls.append(section_header("GOLDEN BETS",
                                                  "#FFD700"))
        if not golden:
            betfi_view.controls.append(empty_inline(
                ft.Icons.STAR_OUTLINE, "No golden bets on this pull"))
            betfi_view.controls.append(ft.Text(
                "Nothing golden on this pull. The standard don't "
                "drop just 'cause the panel empty.",
                size=11, color=DIM))
        for mkt, verdict, edge in golden:
            betfi_view.controls.append(build_market_card(
                mkt, verdict, rec, quotes, edge_pts=edge,
                lane_ctx=ctx))
        betfi_view.controls.append(section_header(
            f"FINDS — verdict ladder, then edge ({len(finds)})",
            ACCENT))
        if not finds:
            betfi_view.controls.append(ft.Text(
                "No priced, verdict-bearing market on this pull. "
                "The feed stays empty rather than promote a "
                "market the engine did not price.",
                size=12, color=DIM, height=1.35))
        for i, (mkt, verdict, edge) in enumerate(
                finds[:CARD_PAGE], start=1):
            betfi_view.controls.append(build_market_card(
                mkt, verdict, rec, quotes, rank=i, edge_pts=edge,
                lane_ctx=ctx))
        if len(finds) > CARD_PAGE:
            betfi_view.controls.append(ft.Text(
                f"+{len(finds) - CARD_PAGE} more finds past the "
                f"page cap — the Cards screen holds the full "
                f"list.", size=11, color=FAINT))
        if flagged:
            betfi_view.controls.append(section_header(
                f"COHERENCE-FLAGGED — somebody's price is wrong "
                f"({len(flagged)})", WARN))
            for mkt, verdict, edge in flagged:
                betfi_view.controls.append(build_market_card(
                    mkt, verdict, rec, quotes, edge_pts=edge,
                    lane_ctx=ctx))
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

    # ---------------- Record ----------------

    def render_record():
        record_view.controls = [_sub_header(
            "Record", "Lane ledger and the latest pull.")]
        record_view.controls.append(section_header(
            "LATEST PULL — WHAT THE APP DID", ACCENT))
        rec = state["slate"]
        if rec:
            verdicts = ensure_verdicts() or []
            markets = rec.get("markets", [])
            priced_v = [v for v in verdicts
                        if v.get("state") == "PRICED"]
            golden_n = sum(1 for v in verdicts
                           if card_verdict(v)[0] == "GOLDEN BET")
            flagged_n = sum(1 for v in verdicts
                            if v.get("state")
                            == "COHERENCE-FLAGGED")
            stamp_text2, _d2 = stamp_of(rec)
            record_view.controls.append(ft.Text(
                f"Pulled: {rec.get('pulled_at')} · {stamp_text2}",
                size=12, color=DIM))
            record_view.controls.append(ft.Text(
                f"Markets checked {len(markets)} · PRICED "
                f"{len(priced_v)} · GOLDEN {golden_n} · "
                f"coherence-flagged {flagged_n} · the rest "
                f"stamped, never guessed.", size=12, color=DIM))
            from collections import Counter
            tags = Counter(v.get("cal_tag") for v in priced_v)
            stances = Counter(v.get("stance") for v in priced_v)
            record_view.controls.append(ft.Text(
                "Calibration tags on priced markets: "
                + " · ".join(f"{t} {tags.get(t, 0)}"
                             for t in b5.CALIBRATION_TAGS),
                size=12, color=DIM))
            record_view.controls.append(ft.Text(
                "Stances among priced markets: "
                + " · ".join(
                    f"{s.capitalize()} {stances.get(s, 0)}"
                    for s in b5.STANCES),
                size=12, color=DIM))
        else:
            record_view.controls.append(ft.Text(
                "No pull on this device yet — the ledger fills "
                "with the first pull.", size=12, color=DIM))
        record_view.controls.append(ft.Divider(color=BORDER))
        record_view.controls.append(section_header(
            "LANE LEDGER — WIN / LOSE OF RECORD", ACCENT))
        card = b5.load_scorecard()
        for lane in RECORD_LANES:
            w, l, src = b5.lane_record(lane)
            tag = b5.calibration_tag(lane, card)
            status_line = ""
            if lane not in ("nfl-ml", "nfl"):
                try:
                    st = b5.lane_status(card, lane)["status"]
                    if st == "BENCHED":
                        status_line = (" · governor: BENCHED "
                                       "(lane sat down — its "
                                       "recent record against "
                                       "the market is losing)")
                    else:
                        status_line = f" · governor: {st}"
                except Exception as e:
                    status_line = f" · governor: {type(e).__name__}"
            uncal = b5.lane_uncalibrated(lane)
            record_view.controls.append(ft.Text(
                f"{lane}: Win {w} · Lose {l} ({src}) · tag {tag}"
                f"{status_line}"
                + (f" · {uncal}" if uncal else ""),
                size=13, color=DIM))
        entries = card.get("entries") or []
        record_view.controls.append(ft.Divider(color=BORDER))
        record_view.controls.append(ft.Text(
            f"App: {DISPLAY_NAME} v{APP_VERSION} · Engine: "
            f"{ENGINE_VERSION} · {engine_fingerprint()}",
            size=12, color=ACCENT))
        record_view.controls.append(ft.Text(
            f"Scorecard entries on device: {len(entries)} · "
            f"internal id {INTERNAL_ID} · analysis only — "
            f"{PUBLIC_NAME} never places a bet.",
            size=11, color=FAINT))
        page.update()

    # ---------------- Terms ----------------

    def _term_entry(head, body):
        return ft.Text(
            spans=[ft.TextSpan(head, style=ft.TextStyle(
                       weight=ft.FontWeight.BOLD, color=INK)),
                   ft.TextSpan(f" — {body}", style=ft.TextStyle(
                       color=INK))],
            size=12, height=1.35)

    TERMS = [
        ("THE VERDICT LADDER", [
            ("Verdict", "the app's call on one priced market, "
             "from a five-rung ladder. Verdicts are analysis, not "
             "instructions; the app never places a bet."),
            ("GOLDEN BET", "the strongest signal the app prints: "
             "an A-band grade, an edge still +3.0 pts or better "
             "at the pessimistic end of the model's band, and a "
             "named reason the market may be wrong. The "
             "calibration tag rides on the card but does not "
             "gate it (v5.2). Most pulls have none. The panel is "
             "never backfilled."),
            ("BET HERE", "a clean bet by the ladder's rules: real "
             "edge, no cautions standing."),
            ("RISK BET (BET)", "a real edge with exactly one "
             "caution attached. The caution prints on the card "
             "with the verdict."),
            ("RISK BET (DO NOT BET)", "a signal exists, but a "
             "hard stop or two or more stacked cautions say "
             "pass. It prints so you can see what was refused, "
             "and why."),
            ("DO NOT BET", "no edge, a negative edge, or no "
             "price the app can defend. The app's default "
             "answer."),
            ("UNPRICED", "the app has no probability it can "
             "defend for this market, so it prints none. An "
             "UNPRICED market always carries its reason (engine "
             "not built, team not in the fit, source failed). "
             "It is stamped, never guessed."),
            ("PRICED", "the engine produced a probability for "
             "this market from a fitted source and graded it "
             "against the pulled price."),
            ("COHERENCE-FLAGGED", "this game's prices disagree "
             "with each other beyond the audit thresholds (a "
             "favorite flip, a spread or total far from another "
             "source, a moneyline/spread pair no single margin "
             "distribution can reconcile). Somebody's price is "
             "wrong; the card shows which quotes fight."),
        ]),
        ("GRADES, STANCE, CALIBRATION", [
            ("Grade (A+ to F)", "a score of the edge, not of the "
             "team and not of the chance of winning. A B can be "
             "a 40% shot with a fat edge; an A is not a promise. "
             "Grades come from the band table on the Equations "
             "page, with named modifiers (FRAGILE, grouping cap, "
             "provisional cap) printed as tags when they "
             "apply."),
            ("Stance", "the shape of a priced bet, from its own "
             "probability, edge, and price. Stance describes "
             "the shape of the bet, never whether to take it — "
             "the verdict decides that."),
            ("BULLISH", "a strong position — the model's edge "
             "is strong: edge at the B-band floor (+2.0 pts) or "
             "better, on a side the model genuinely rates "
             "(probability 45%+). Not a prediction that the "
             "price will move; it describes the model's edge, "
             "not market sentiment."),
            ("CONSERVATIVE", "the boring-favorite profile — "
             "probability 65%+ with a thin edge. You are paying "
             "for likelihood, not for edge."),
            ("LONGSHOT", "low probability (implied 35% or "
             "less, or odds of +200 or longer). The return comes "
             "from the payout shape, not from likelihood."),
            ("Stance on a parlay", "the longest shot sets the "
             "slip's stance: any LONGSHOT leg makes the slip "
             "LONGSHOT; any BULLISH leg with no LONGSHOT leg "
             "makes it BULLISH; a slip of only CONSERVATIVE "
             "legs is CONSERVATIVE."),
            ("Calibration tag", "how much testing stands behind "
             "a lane's probability adjustments (its phi map)."),
            ("CALIBRATED", "the map was walk-forward tested and "
             "passed its benchmark."),
            ("PROVISIONAL", "the phi is not yet tested, or the "
             "lane's register is provisional. Untested is not "
             "failed — the tag says which."),
            ("UNCALIBRATED", "the map was tested and failed its "
             "benchmark. The lane still prices and grades; the "
             "tag rides on the card so the failure is visible, "
             "and in v5.2 it no longer caps the grade."),
            ("UNTESTED", "no scored record yet — nothing has "
             "been tested, because there is nothing to test "
             "against. A lane with no record has not failed "
             "anything."),
        ]),
        ("THE MATH WORDS", [
            ("Edge (pts)", "model probability minus the price's "
             "implied probability, in percentage points. "
             "+5.0 pts means the model makes it 60% where the "
             "price implies 55%."),
            ("Implied probability", "the win chance a price "
             "breaks even at. −150 implies 60.0%; +200 implies "
             "33.3%. Implied probabilities from a two-sided "
             "market sum to more than 100% — the extra is the "
             "book's margin."),
            ("No-vig probability", "the market's implied "
             "probabilities rescaled to sum to exactly 100%, "
             "removing the book's margin. The market's fair "
             "price, as the app uses the phrase."),
            ("EV (expected value)", "the average profit or loss "
             "per $1 staked if the model's probability is "
             "right, repeated many times. +$0.08 per $1 is a "
             "good bet by the model's lights; it says nothing "
             "about any single outcome."),
            ("Kelly fraction", "the share of bankroll a bet "
             "\"deserves\" if the model's probability were "
             "exactly right: f = EV per $1 ÷ (decimal odds "
             "− 1). This app sizes at quarter-Kelly, capped — "
             "see the Solver page warning before using the "
             "full number for anything."),
            ("Unit (u)", "1 unit = 1% of bankroll. Printed "
             "sizes run 0.0–2.0u."),
            ("Plus money", "odds longer than even money: "
             "American +100 or more, decimal above 2.00."),
            ("BTTS", "both teams to score — a soccer market: "
             "both teams score at least once in the match."),
            ("CLV (closing line value)", "how a taken price "
             "compares with the price at market close. Defined "
             "here because bettors use the term; this app does "
             "not track CLV."),
        ]),
        ("THE MACHINERY", [
            ("Phi (φ)", "the fitted map that adjusts a lane's "
             "raw model probabilities toward what the lane's "
             "scored record has earned (identity, linear, or "
             "isotonic; fitted walk-forward only — never on "
             "the games it then prices)."),
            ("Shrinkage / reliability", "the model's "
             "probability is pulled toward the market's no-vig "
             "probability before grading: shrunk P = no-vig P "
             "+ reliability × (model P − no-vig P). Reliability "
             "(0 to 1) is how much of the model's disagreement "
             "with the market survives, learned from the lane's "
             "scored record. 0.30 means the app keeps 30% of "
             "the disagreement and concedes the rest to the "
             "market."),
            ("Band", "the range of probabilities the model's "
             "independent families produce for one market. "
             "Verdicts grade the band's pessimistic (low) end, "
             "so a bet must survive the model's own doubt, not "
             "just its headline number."),
            ("Mechanism tag", "the named reason the market may "
             "be wrong, required for GOLDEN BET. One of: "
             "live-repricing-lag (the book is slow to move a "
             "live price), soft-market (a smaller book lags the "
             "sharp market), opener-staleness (the opening "
             "price was never corrected), public-shading (the "
             "price is shaded toward the popular side), "
             "model-structural (the model's structure itself "
             "sees it differently), pilot-read (the Pilot's own "
             "read, entered by hand — the only non-model "
             "mechanism)."),
            ("Governor / BENCHED", "a lane whose recent scored "
             "record against the market is losing gets benched: "
             "it still prints, but its bets cannot pass the "
             "ladder while the bench stands."),
            ("Lane", "one kind of bet in one sport (NFL "
             "moneyline, NBA spread, soccer match result…), "
             "tracked and graded as its own track record. "
             "Grades and records never mix across lanes."),
            ("Brier score", "the accuracy score behind the "
             "records: the mean squared gap between predicted "
             "probabilities and outcomes. Lower is better; "
             "0.25 is coin-flip territory for a 50/50 market."),
        ]),
        ("THE BOARD — SEARCH, QUICK BETS, RESOLVE", [
            ("Search", "the Cards search box. It reads every text "
             "field the menu printed for a market — teams, market "
             "name, league — and every word typed must match. "
             "Search filters the pull on screen; it never pulls, "
             "prices, or guesses."),
            ("Resolve date", "the calendar date a market settles, "
             "taken from the event's scheduled start on the menu. "
             "The Resolve date sort orders the board by that date, "
             "earliest first, grouped under date headers."),
            ("Quick bet", "a market resolving within 0–2 hours of "
             "the pull — the Quick bets toggle on Cards. The clock "
             "is the pull's own timestamp, so a stale pull shows "
             "its quick window as it stood when pulled, stamped "
             "STALE like everything else on it."),
        ]),
    ]

    def render_terms():
        controls = [_sub_header("Terms",
                                "What every word on a card means.")]
        for header, entries in TERMS:
            controls.append(ft.Container(
                padding=ft.Padding(left=0, right=0, top=16,
                                   bottom=0),
                content=ft.Text(header, size=13, color=ACCENT,
                                weight=ft.FontWeight.BOLD)))
            for head, body in entries:
                controls.append(_term_entry(head, body))
                if head == "UNPRICED":
                    controls.append(ft.Text(
                        "Plain talk: if the engine can't stand "
                        "behind a number, it won't print one. No "
                        "guessing, and no dressing the market's "
                        "price up like it's ours.",
                        size=12, color=DIM, height=1.35))
        terms_view.controls = controls
        page.update()

    # ---------------- Equations ----------------

    def _eq_block(equation, gloss):
        return ft.Container(
            bgcolor=RAISED, border_radius=6, padding=8,
            content=ft.Column(spacing=2, tight=True, controls=[
                ft.Text(equation, size=13, color=INK),
                ft.Text(gloss, size=11, color=DIM, height=1.35)]))

    def render_equations():
        controls = [_sub_header("Equations", "The math, in the open.")]
        sections = [
            ("PRICES", [
                ("P = A ÷ (A + 100) for odds −A · "
                 "P = 100 ÷ (B + 100) for odds +B",
                 "Implied probability — the win chance a price "
                 "breaks even at. Worked: −150 → 150/250 = "
                 "60.0%. +200 → 100/300 = 33.3%."),
                ("decimal = 1 + 100/A (odds −A) · "
                 "1 + B/100 (odds +B)",
                 "Decimal odds. −110 = 1.91 · +200 = 3.00 · "
                 "−150 = 1.67."),
                ("no-vig P = a side's implied P ÷ the sum of "
                 "both sides' implied P",
                 "Removes the book's margin, so the market's "
                 "fair prices sum to 100%.")]),
            ("EDGE AND VALUE", [
                ("edge (pts) = (model P − implied P) × 100",
                 "In percentage points of probability. +5.0 pts "
                 "means the model makes it 60% where the price "
                 "implies 55%."),
                ("EV per $1 = P × (decimal − 1) − (1 − P)",
                 "Expected value per $1 staked, if the model's "
                 "probability is right."),
                ("Kelly f = EV per $1 ÷ (decimal − 1)",
                 "The app sizes at one quarter of this, "
                 "hard-capped by the unit classes below.")]),
            ("THE MODEL", [
                ("shrunk P = no-vig P + reliability × "
                 "(model P − no-vig P)",
                 "Shrinkage — the phi edge grades the shrunk "
                 "number, not the raw one. Reliability is "
                 "learned from the lane's scored record.")]),
            ("PARLAYS AND HEDGES", [
                ("combined decimal = product of leg decimals · "
                 "joint P = product of leg probabilities",
                 "Assumes the legs are independent — same-game "
                 "legs rarely are; treat a parlay's joint "
                 "probability as a ceiling."),
                ("hedge stake = original stake × original "
                 "decimal ÷ hedge decimal",
                 "Equal return both ways: both outcomes pay "
                 "original stake × original decimal in total.")]),
        ]
        for header, blocks in sections:
            controls.append(ft.Container(
                padding=ft.Padding(left=0, right=0, top=16,
                                   bottom=0),
                content=ft.Text(header, size=13, color=ACCENT,
                                weight=ft.FontWeight.BOLD)))
            for eq, gloss in blocks:
                controls.append(_eq_block(eq, gloss))
        controls.append(ft.Container(
            padding=ft.Padding(left=0, right=0, top=16, bottom=0),
            content=ft.Text("GRADE BANDS (v5.2)", size=13,
                            color=ACCENT,
                            weight=ft.FontWeight.BOLD)))
        for lo, g in b5.GRADE_BANDS_V52:
            controls.append(_kv_row(
                g, f"phi edge ≥ {lo:+.1f} pts", label_color=FAINT))
        controls.append(_kv_row("F", "phi edge below −5.5 pts",
                                label_color=FAINT))
        controls.append(ft.Text(
            "v5.2 widened every floor about a point from the "
            "frozen v5.1 rubric, by Pilot order — a solid edge "
            "now reaches B at +2.0. Named modifiers (FRAGILE, "
            "grouping cap, provisional cap) print as tags when "
            "they apply.", size=12, color=INK, height=1.35))
        controls.append(ft.Container(
            padding=ft.Padding(left=0, right=0, top=16, bottom=0),
            content=ft.Text("STANCE RULES", size=13, color=ACCENT,
                            weight=ft.FontWeight.BOLD)))
        for line in [
                "BULLISH — phi edge ≥ +2.0 pts, model P ≥ 45%, "
                "implied P above 35%.",
                "CONSERVATIVE — model P ≥ 65% with edge under "
                "+2.0 pts (the fallback at model P ≥ 60%).",
                "LONGSHOT — implied P ≤ 35%, or price +200 or "
                "longer, or model P ≤ 45% without the bullish "
                "shape.",
                "Parlay stance — the longest shot sets the slip: "
                "any LONGSHOT leg ⇒ LONGSHOT; else any BULLISH "
                "leg ⇒ BULLISH; all CONSERVATIVE ⇒ CONSERVATIVE."]:
            controls.append(ft.Text(line, size=12, color=INK,
                                    height=1.35))
        controls.append(ft.Container(
            padding=ft.Padding(left=0, right=0, top=16, bottom=0),
            content=ft.Text("UNIT CLASSES", size=13, color=ACCENT,
                            weight=ft.FontWeight.BOLD)))
        controls.append(ft.Text(
            "edge ≥ 3 pts: up to 1.0u · above 6 pts: up to "
            "2.0u · below 3 pts: 0.0u — before the quarter-Kelly "
            "cap also applies; the smaller of the two sizes "
            "prints.", size=12, color=INK, height=1.35))
        equations_view.controls = controls
        page.update()

    # ---------------- Dev ----------------

    def render_dev():
        identity = ft.Container(
            bgcolor=CARD_BG, border_radius=10, padding=12,
            content=ft.Column(spacing=6, controls=[
                ft.Text("BetFi", size=16, color=INK,
                        weight=ft.FontWeight.BOLD),
                _kv_row("App version", f"{APP_VERSION}"),
                _kv_row("Build", str(BUILD_NUMBER)),
                _kv_row("Engine", ENGINE_VERSION),
                _kv_row("Engine fingerprint",
                        engine_fingerprint()),
                _kv_row("Menu source",
                        "FanDuel (Michigan) public menu — "
                        "read-only, no login"),
                _kv_row("Storage", storage_dir()),
                _kv_row("Internal id", INTERNAL_ID)]))
        credit = ft.Container(
            bgcolor=RAISED, border_radius=10, padding=12,
            content=ft.Column(spacing=6, controls=[
                ft.Text("BetFi — by T. Abram.", size=13, color=INK,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Engine: betmodel. Built with Praxis.",
                        size=12, color=DIM),
                ft.Row(spacing=6, vertical_alignment=
                       ft.CrossAxisAlignment.START, controls=[
                           ft.Icon(ft.Icons.INFO_OUTLINE, size=14,
                                   color=WARN),
                           ft.Text("Analysis only. The app point "
                                   "at the number — you make the "
                                   "call.", size=11, color=WARN,
                                   height=1.35)])]))
        dev_view.controls = [
            _sub_header("Dev", "Build, engine, and credit."),
            identity, credit]
        page.update()

    # ---------------- navigation ----------------

    def show(name: str):
        state["view"] = name
        for key, view in views.items():
            view.visible = key == name
        if page.navigation_bar is not None:
            page.navigation_bar.selected_index = \
                TOP_VIEWS.index(name) if name in TOP_VIEWS else 4
        if name == "cards":
            render_cards()
        elif name == "parse":
            render_parse()
        elif name == "parlay":
            render_parlay()
        elif name == "solver":
            render_solver()
        elif name == "more":
            render_more()
        elif name == "betfi":
            render_betfi()
        elif name == "record":
            render_record()
        elif name == "terms":
            render_terms()
        elif name == "equations":
            render_equations()
        elif name == "dev":
            render_dev()
        page.update()

    def on_nav(e):
        show(TOP_VIEWS[e.control.selected_index])

    # ---------------- assembly ----------------

    header = ft.Column(spacing=4, controls=[
        ft.Text(PUBLIC_NAME, size=22, color=INK,
                weight=ft.FontWeight.BOLD),
        ft.Text(f"{DISPLAY_NAME} · engine {ENGINE_VERSION} · "
                f"analysis only — never places a bet",
                size=11, color=FAINT),
        stamp_ctrl,
    ])
    cards_view.controls = [
        screen_title("Cards",
                     "Every checked market on the current pull."),
        ft.Row(spacing=8, controls=[
            ft.Button("Pull Menu", on_click=on_pull),
            ft.Button("Price Slate", on_click=on_price)]),
        status,
        ft.Row(spacing=8, controls=[
            ft.Icon(ft.Icons.SORT, size=18, color=ACCENT),
            ft.Dropdown(
                value=state["sort"], width=230,
                options=[ft.DropdownOption(key=k, text=t)
                         for k, t in SORT_MODES],
                on_select=on_sort),
            cards_count]),
        ft.TextField(
            hint_text="Search teams, markets, leagues\u2026",
            prefix_icon=ft.Icons.SEARCH, text_size=13,
            on_change=on_search),
        cards_toggles,
        cards_list]
    page.add(header, cards_view, parse_view, parlay_view,
             solver_view, more_view, betfi_view, record_view,
             terms_view, equations_view, dev_view)

    nav_bar_cls = getattr(ft, "NavigationBar", None)
    nav_dest_cls = (getattr(ft, "NavigationDestination", None)
                    or getattr(ft, "NavigationBarDestination", None))
    if nav_bar_cls is not None and nav_dest_cls is not None:
        page.navigation_bar = nav_bar_cls(
            selected_index=0, on_change=on_nav,
            destinations=[
                nav_dest_cls(icon=ft.Icons.VIEW_AGENDA,
                             label="Cards"),
                nav_dest_cls(icon=ft.Icons.SEARCH, label="Parse"),
                nav_dest_cls(icon=ft.Icons.RECEIPT_LONG,
                             label="Parlay"),
                nav_dest_cls(icon=ft.Icons.CALCULATE,
                             label="Solver"),
                nav_dest_cls(icon=ft.Icons.MORE_HORIZ,
                             label="More"),
            ])
    else:  # equivalent switch: a labelled button row
        page.add(ft.Row(spacing=8, wrap=True, controls=[
            ft.OutlinedButton("Cards",
                              on_click=lambda _e: show("cards")),
            ft.OutlinedButton("Parse",
                              on_click=lambda _e: show("parse")),
            ft.OutlinedButton("Parlay",
                              on_click=lambda _e: show("parlay")),
            ft.OutlinedButton("Solver",
                              on_click=lambda _e: show("solver")),
            ft.OutlinedButton("More",
                              on_click=lambda _e: show("more")),
        ]))

    # offline behaviour: open on the last pull, stamped with its
    # original pull time (the engine's stamp calls it STALE past
    # its own window) — stale is labelled stale, never freshened.
    render_cards()
    page.update()


if __name__ == "__main__":
    ft.run(main)
