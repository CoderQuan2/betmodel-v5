#!/usr/bin/env python3
"""
BetFi 11 — the betmodel v5.3 mobile shell (public name: BetFi;
internal id: Bet_Finder).

The ENTIRE app in one file, per the Pilot's 1-script preference:
this shell plus the engine (betmodel5.py, one self-contained
script, byte-identical to the lab's) are the only two Python files
in the repo. Flet requires the entry point to be named main.py —
that is the only reason there are two.

Screens (bottom nav, five destinations — permanently capped):
  * Board — every checked market from the current pull as a card
    (face: matchup / record / odds / hero probability + edge /
    grade + calibration chip / verdict pill + stance pill; depth
    folded in as PRICE ANATOMY / SCALE / COHERENCE / PROVENANCE
    tiles), with the finds feed merged in behind an
    All cards | Finds segment. Toggles (priced only / golden
    only / hide DO NOT BET / per-sport / quick bets) and eight
    sorts re-render the cached checker pass — they never
    re-price.
  * Slip  — the ticket tools as one segmented screen:
    Parse (paste slip text — "Lions -3.5 (-110)" — read against
    the pull; a bet it can't match gets stamped, not guessed),
    Parlay (up to four PRICED legs; combined odds, combined
    model probability — independence assumed, printed on the
    page — EV per unit, ladder verdict, slip stance; same-game
    slips stamp UNPRICED under engine law), and Solver (stake
    for a target profit, Kelly sizing with the warning printed,
    equal-return hedge).
  * Lab   — the record wing: latest-pull summary, lane ledger,
    the Lab Card and the Pilot Book (two books, separate totals,
    never merged), the kill ledger, and the grading rubric —
    all read from the bundled evidence pack (see below).
  * 3D    — the instruments shelf: the lab's 11 instruments in
    three families (Stocks / Win Probability / NFL), served from
    the bundled instruments/ folder over a loopback page and
    opened full-screen, each with its honest label.
  * More  — Terms, Equations, and Dev (version, engine
    fingerprint, evidence-pack stamp, credit). Closed to new
    tiles in 10.4.x.

v10 (2026-10-20): engine v5.2 — grades computed from the edge
math on every lane (no calibration cap; bands widened), the
calibration state rides on every card as a tag (CALIBRATED /
PROVISIONAL / UNCALIBRATED / UNTESTED), and every priced bet
carries a stance (BULLISH / CONSERVATIVE / LONGSHOT) computed by
the engine from the bet's own probability, edge and price.

v10.4.1 (2026-10-21) — the combination (super-team spec):
one engine (v5.2 in the lab and the app alike), the lab and the
3D instruments folded into the same app. The Lab wing reads a
bundled EVIDENCE PACK (data/lab_export.json: scorecard, lane
history, phi registry, lane fits — exported by the lab, stamped
with its export time); at startup the pack seeds the engine's
storage so the record on the phone is the lab's record, not an
empty fallback (the Room Rule: no pack ⇒ the Lab prints
"record not bundled", never a 0-0 dressed as a record).
Prices come only from the live FanDuel menu pull — never
invented; UNPRICED markets print DO NOT BET with the named
reason; the golden panel is never backfilled. Analysis only:
the app never places a bet and never touches a sportsbook
account.

v11.0 (2026-10-22) — "The Feel Build" (Pilot order, from the
beta reviews of v10): F1 bet identity first — every card leads
with the FanDuel market name and the selection in plain words,
carries a "Find it on FanDuel" path and a one-tap copy of the
exact slip label, and the same bet_name() names the bet on the
Board, in the Slip, in the finds and in the Lab ledger. F2 the
Lab record rebuilt as a columnar ledger (Date · Bet · Odds ·
Grade · Result · P/L) under per-book summary headers. F3
motion + depth: AnimatedSwitcher view changes, cards animate
in once per pull, skeleton placeholders during pulls, layered
surfaces on the standing palette — no verdict, stance, tag or
rubric wording changed. F4 speed: the shell paints first and
the pricing pass runs on a worker; toggles and sorts update in
place. F5 (engine v5.3): the GOLDEN bar at +2.0, the CLV &
drift ledger on the Lab face (measurement only), and the
Kelly staking advisory on the Slip (advice only — it never
places or queues a bet).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
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
APP_VERSION = "11.0.1"
BUILD_NUMBER = 14
DISPLAY_NAME = "BetFi 11"
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
# The evidence pack (v10.4.1) — the lab's record, exported by the
# lab into data/lab_export.json + the engine's own data files, and
# bundled beside this shell. At startup the pack seeds the
# engine's data dir so the phone's record is the lab's record
# (scorecard, lane history, phi registry, lane fits) instead of
# the engine's silent empty fallback. The Room Rule rides on it:
# no pack anywhere => the Lab prints "record not bundled", never
# a 0-0 dressed as a record. Seeding never overwrites a NEWER
# device pack: lab_export.json's exported_at decides, and the
# pack's engine files travel with their export as one unit.

BUNDLED_DATA_DIR = os.path.join(APP_DIR, "data")
INSTRUMENTS_DIR = os.path.join(APP_DIR, "instruments")


def _exported_at_of(path: str):
    """The exported_at stamp of a lab_export.json, parsed aware;
    None when absent or unreadable."""
    try:
        with open(path) as f:
            stamp = json.load(f).get("exported_at")
        dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def seed_evidence_pack() -> dict:
    """Copy the bundled evidence pack into the engine's data dir.

    Missing files are copied. When the bundled export is fresher
    than the device's, the pack's own engine files refresh with
    it (a pack is one unit — a fresher scorecard never travels
    with staler fits). Files the pack does not own (the engine's
    caches, the NFL pricing file) are never touched. A device
    pack with an equal or newer exported_at is left alone.
    Returns a status dict for the Dev screen and the Lab stamp.
    """
    status = {"bundled": False, "seeded": False, "files": 0,
              "exported_at": None}
    src = BUNDLED_DATA_DIR
    dst = b5.DATA
    try:
        bundled_export = os.path.join(src, "lab_export.json")
        if not os.path.isfile(bundled_export):
            return status
        status["bundled"] = True
        with open(bundled_export) as f:
            pack = json.load(f)
        status["exported_at"] = pack.get("exported_at")
        if os.path.abspath(src) == os.path.abspath(dst):
            status["seeded"] = True  # already in place (dev layout)
            status["files"] = sum(
                1 for fn in os.listdir(src)
                if os.path.isfile(os.path.join(src, fn)))
            return status
        os.makedirs(dst, exist_ok=True)
        bundled_at = _exported_at_of(bundled_export)
        device_at = _exported_at_of(os.path.join(dst,
                                                 "lab_export.json"))
        fresher = device_at is None or (
            bundled_at is not None and bundled_at > device_at)
        pack_files = set(pack.get("engine_data_files") or [])
        pack_files.add("lab_export.json")
        copied = 0
        for fn in sorted(os.listdir(src)):
            sp = os.path.join(src, fn)
            if not os.path.isfile(sp):
                continue
            dp = os.path.join(dst, fn)
            if not os.path.exists(dp) or (fresher
                                          and fn in pack_files):
                with open(sp, "rb") as f:
                    blob = f.read()
                with open(dp, "wb") as f:
                    f.write(blob)
                copied += 1
        status["seeded"] = True
        status["files"] = copied
        return status
    except Exception:
        return status  # the shell must never die over the pack


PACK_STATUS = seed_evidence_pack()


def load_lab_pack() -> dict | None:
    """The evidence pack as the Lab face reads it: the seeded copy
    in the engine's data dir first (that is the device's record),
    the bundled copy as fallback. None when no pack exists —
    the Room Rule's named failure state."""
    for path in (os.path.join(b5.DATA, "lab_export.json"),
                 os.path.join(BUNDLED_DATA_DIR, "lab_export.json")):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            continue
    return None


# ------------------------------------------------------------------
# The instruments (v10.4.1) — the lab's 11 self-contained HTML
# instruments, bundled in instruments/ beside this shell and
# served over a loopback page (stdlib http.server, lazy start,
# idempotent): Android browsers do not reliably render file://
# paths into app-private storage, and Flet 1.0.4 has no WebView —
# so each instrument opens full-screen through the UrlLauncher
# service at its loopback URL (verified in the pinned venv:
# ft.UrlLauncher exists, page.launch_url does not).

INSTRUMENTS = [
    # Stocks — one sample, 6 names, 44 sessions (Aug 17–Oct 16 2026)
    {"file": "stock-vol4d.html", "family": "Stocks",
     "name": "Volatility Space 4D",
     "note": "Six names: return vs realized volatility. Ribbon "
             "width is volume share; the particle cloud is "
             "indecision (J).",
     "chip": "SNAPSHOT · AUG 17 – OCT 16, 2026"},
    {"file": "stock-vol-webgl2.html", "family": "Stocks",
     "name": "Volatility Space — WebGL2",
     "note": "The current edition: the same vol4d data on a raw "
             "WebGL2 GPU pipeline — same encodings, same J.",
     "chip": "SNAPSHOT · AUG 17 – OCT 16, 2026 · CURRENT EDITION"},
    {"file": "stock-vol-3d.html", "family": "Stocks",
     "name": "Volatility Space 3D",
     "note": "The trajectories with volatility as a true third "
             "spatial axis.",
     "chip": "SNAPSHOT · AUG 17 – OCT 16, 2026"},
    {"file": "stock-3d-map.html", "family": "Stocks",
     "name": "Stock 3D Map",
     "note": "The first 3D pass over the six trajectories.",
     "chip": "SNAPSHOT · AUG 17 – OCT 16, 2026"},
    {"file": "crm-3d.html", "family": "Stocks",
     "name": "CRM Terrain",
     "note": "Single-name 3D terrain of the CRM series.",
     "chip": "SNAPSHOT · AUG 17 – OCT 16, 2026"},
    {"file": "crm-path.html", "family": "Stocks",
     "name": "CRM Path",
     "note": "Single-name study: CRM's cumulative path, "
             "Jun 15 – Oct 16, 2026.",
     "chip": "SNAPSHOT · AUG 17 – OCT 16, 2026"},
    # Win Probability — the lab's closed-form WP model, computed live
    {"file": "wp-surface-webgl2.html", "family": "Win Probability",
     "name": "WP Surface — WebGL2",
     "note": "The current edition: the win-probability surface "
             "as a lit mesh, computed live from the model; the "
             "probe prices any state; journeys are recorded "
             "priced states.",
     "chip": "MODEL — COMPUTED LIVE · JOURNEYS RECORDED · "
             "CURRENT EDITION"},
    {"file": "wp-surface-3d-interactive.html",
     "family": "Win Probability",
     "name": "WP Surface — Interactive",
     "note": "The same live model in lightweight canvas, with "
             "the draggable probe.",
     "chip": "MODEL — COMPUTED LIVE · JOURNEYS RECORDED"},
    {"file": "wp-surface-3d.html", "family": "Win Probability",
     "name": "WP Surface — Static",
     "note": "The print render of the surface, both journeys "
             "drawn.",
     "chip": "FROZEN RENDER"},
    # NFL Week 6 — frozen weekend artifacts
    {"file": "nfl-week6-trajectories-model-vs-market.html",
     "family": "NFL",
     "name": "Model vs Market Trajectories",
     "note": "Per-game probability trajectories, model vs "
             "market, NFL Week 6.",
     "chip": "FROZEN · WEEK 6, 2026"},
    {"file": "nfl-week6-command-board.html", "family": "NFL",
     "name": "Command Board",
     "note": "The weekend command board for the Week 6 slate.",
     "chip": "FROZEN · WEEK 6, 2026 · CONTAINS AN AUDIT FLAG"},
]
INSTRUMENT_FAMILIES = ["Stocks", "Win Probability", "NFL"]
STOCKS_SAMPLE_NOTE = (
    "One sample — 6 names, 44 sessions, chosen from a 42-name "
    "universe. Patterns and J are observations about this sample, "
    "not laws.")

_instrument_server = {"httpd": None, "port": None}
_instrument_lock = threading.Lock()


def ensure_instrument_server() -> int | None:
    """Start (once, under a lock — the shelf warms it on a worker
    thread via page.run_thread and a tap may ask at the same
    moment) the loopback server for instruments/ and return its
    port; None when the folder is absent (single-file editions)
    or no port in 8791–8800 binds."""
    with _instrument_lock:
        if _instrument_server["httpd"] is not None:
            return _instrument_server["port"]
        if not os.path.isdir(INSTRUMENTS_DIR):
            return None
        try:
            import functools
            import http.server

            class _Quiet(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *args):
                    pass

            handler = functools.partial(_Quiet,
                                        directory=INSTRUMENTS_DIR)
            httpd = None
            port = None
            for candidate in range(8791, 8801):
                try:
                    httpd = http.server.ThreadingHTTPServer(
                        ("127.0.0.1", candidate), handler)
                    port = candidate
                    break
                except OSError:
                    continue
            if httpd is None:
                return None
            threading.Thread(target=httpd.serve_forever,
                             daemon=True).start()
            _instrument_server["httpd"] = httpd
            _instrument_server["port"] = port
            return port
        except Exception:
            return None


def instruments_bundled() -> tuple[int, int]:
    """(files present, total bytes) of the bundled instruments —
    the Dev screen's count, read fresh at render."""
    n = 0
    total = 0
    for inst in INSTRUMENTS:
        p = os.path.join(INSTRUMENTS_DIR, inst["file"])
        if os.path.isfile(p):
            n += 1
            total += os.path.getsize(p)
    return n, total


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
# BetFi 11 (F1) — bet identity. One bet, one name, everywhere: the
# card face, the slip, the finds feed and the Lab ledger all read
# a bet through bet_name(). The hierarchy follows FanDuel's own
# order — MARKET first, then the selection in plain words, then
# the game — because that is the order a bettor matches against
# the FanDuel app in their other hand. Market names are the ones
# FanDuel prints (verified against the live pull in the engine's
# fd_parse_sport_page: "Moneyline", "Point Spread", "Total
# Points", soccer "Moneyline (3-way)").

_NFL_FULL_NAMES = {code: name for name, code
                   in b5.FD_NFL_TEAM_CODES.items()}

_STAT_WORDS = {"td": "TDs", "yds": "yards", "att": "attempts",
               "rec": "receptions", "fg": "field goals"}


def team_name(mkt: dict, side: str) -> str:
    """The team's name as a bettor reads it. NFL slate entries
    carry team codes (the engine routes by code); the full name
    is restored from the engine's own code table. Every other
    sport already carries full names as pulled."""
    raw = mkt.get(side) or "?"
    if mkt.get("sport") == "nfl":
        return _NFL_FULL_NAMES.get(raw, raw)
    return raw


def _stat_words(stat: str | None) -> str:
    """camelCase engine stat key -> plain words ('passingYards'
    -> 'passing yards', 'passingTouchdowns' -> 'passing TDs')."""
    if not stat:
        return ""
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", str(stat)).split()
    return " ".join(_STAT_WORDS.get(w.lower(), w.lower())
                    for w in words)


def _fmt_line(line) -> str:
    """A line with its sign, in the app's minus: -3.5 -> '−3.5',
    47.5 -> '+47.5' is NOT implied — callers pass signed lines."""
    s = f"{float(line):+g}"
    return s.replace("-", "−")


def fd_market_name(mkt: dict) -> str:
    """Line 1 of the card: the market's name as FanDuel prints
    it — NOT the shell's display name and NOT the engine's key."""
    market = mkt.get("market") or ""
    if mkt.get("player") and mkt.get("stat"):
        return f"{_stat_words(mkt['stat']).title()} — player prop"
    if mkt.get("sport") == "soccer":
        return {"moneyline": "Moneyline (3-way)",
                "spread": "Handicap (spread)",
                "alt-spread": "Handicap (spread)",
                "totals": "Total goals (over/under)",
                "alt-total": "Total goals (over/under)",
                "btts": "Both Teams To Score"}.get(
                    market, market)
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


def selection_words(mkt: dict) -> str:
    """Line 2 of the card: the selection in plain words, with
    the line — the words on the FanDuel slip itself. Player
    props are 'Over 249.5 passing yards' (the player leads on
    line 1); a spread is the team with its signed line."""
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


def bet_name(mkt: dict, verdict: dict | None = None) -> dict:
    """The bet's one name, in every surface's shape:
      headline   — card line 1 (the player on props, else the
                   FanDuel market name)
      selection  — card line 2, plain words with the line
      matchup    — the game, as matchup_title prints it
      slip_label — the exact label the COPY button puts on the
                   clipboard: selection, price, market, matchup
      fd_path    — the 'Find it on FanDuel' navigation path:
                   league -> game -> market tab, in FanDuel's
                   own words."""
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


# ------------------------------------------------------------------
# The clipboard (F1): ft.Clipboard is the Flet 1.0.4 service for
# this (page.set_clipboard does not exist in the pinned build —
# verified). main() registers its service here so the module-
# level card builder can offer the copy button; a tap copies the
# exact slip label for FanDuel search or a notes app.

_CLIPBOARD = {"svc": None}


def bind_clipboard(svc) -> None:
    _CLIPBOARD["svc"] = svc


def _copy_label(e, label: str):
    svc = _CLIPBOARD["svc"]
    page = getattr(e, "page", None)
    if svc is None or page is None:
        return
    try:
        page.run_task(svc.set, label)
    except Exception:
        return
    try:
        e.control.icon = ft.Icons.CHECK
        e.control.update()
    except Exception:
        pass


# ------------------------------------------------------------------
# Skeletons (F3/F4): the shell paints these while a pull or the
# first pricing pass is in flight — a shaped placeholder in the
# card's own silhouette instead of a bare spinner or a dead
# screen.


def skeleton_card() -> ft.Container:
    bar = lambda w, h, c=RAISED: ft.Container(  # noqa: E731
        width=w, height=h, bgcolor=c, border_radius=4)
    return ft.Container(
        bgcolor=CARD_BG, border_radius=10, padding=12,
        border=_border_all(1, BORDER),
        content=ft.Column(spacing=8, controls=[
            bar(150, 16), bar(230, 20), bar(190, 12, DIM),
            bar(120, 26), bar(260, 12)]))


def skeleton_cards(n: int = 3) -> list:
    return [skeleton_card() for _ in range(n)]

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
    # F1 identity block — the bet leads, the game follows:
    # line 1 the FanDuel market name (the player on props),
    # line 2 the selection in plain words with its price,
    # line 3 the matchup + start time + league, then the
    # FanDuel navigation path and the slip-label copy button.
    name = bet_name(mkt, verdict)
    face.append(ft.Text(name["headline"], size=17, color=INK,
                        weight=ft.FontWeight.BOLD))
    sel_row = [ft.Text(name["selection"], size=15, color=INK,
                       weight=ft.FontWeight.BOLD)]
    if mkt.get("price") is not None:
        price = int(mkt["price"])
        if mkt.get("sport") == "soccer":
            # world readers price in decimal: decimal first,
            # American in parentheses (language report W4)
            price_txt = (f"odds "
                         f"{b5.american_to_decimal(price):.2f} "
                         f"({price:+d})")
        else:
            price_txt = f"odds {price:+d}"
        sel_row.append(ft.Text(price_txt, size=12, color=DIM))
    face.append(ft.Row(spacing=8, controls=sel_row))
    meta_bits = [name["matchup"]]
    _dt = _market_dt(mkt)
    if _dt is not None:
        meta_bits.append(_dt.strftime("%a %b %d · %I:%M %p")
                         .replace(" 0", " "))
    meta_bits.append(SPORT_LABELS.get(
        mkt.get("sport"), (mkt.get("sport") or "?").upper()))
    face.append(_line(" · ".join(meta_bits), 11, DIM))
    face.append(ft.Row(
        spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text("Find it: ", size=11, color=FAINT,
                    weight=ft.FontWeight.BOLD),
            ft.Text(name["fd_path"], size=11, color=DIM),
            ft.IconButton(
                icon=ft.Icons.CONTENT_COPY, icon_size=15,
                icon_color=ACCENT, width=34, height=34,
                tooltip="Copy the exact slip label",
                on_click=lambda e, lbl=name["slip_label"]:
                _copy_label(e, lbl))]))
    face.append(_line(f"Win {w} · Lose {l}   ({lane} lane record)",
                      11, DIM))
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
    if mkt.get("fd_event_id"):
        provenance.append(f"FanDuel event id: "
                          f"{mkt['fd_event_id']}")
    if mkt.get("fd_market_id"):
        provenance.append(f"FanDuel market id: "
                            f"{mkt['fd_market_id']}")
    provenance.append(f"card rendered: "
                      f"{datetime.now().astimezone().isoformat(timespec='seconds')}")

    stripe_color = UNPRICED_BORDER if state == "UNPRICED" else \
        VERDICT_BG.get(term, BORDER)
    gradient = None
    if term == "GOLDEN BET":
        # the only gradient on a card: a restrained gold wash
        # over the standing card surface (F3 depth pass)
        gradient = ft.LinearGradient(
            begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
            colors=["#191405", CARD_BG])
    return ft.Container(
        bgcolor=CARD_BG, gradient=gradient, border_radius=10,
        padding=12,
        shadow=ft.BoxShadow(blur_radius=14, spread_radius=0,
                            color="#00000066",
                            offset=ft.Offset(0, 4)),
        border=ft.Border(
            left=ft.BorderSide(3, stripe_color),
            top=ft.BorderSide(1, BORDER),
            right=ft.BorderSide(1, BORDER),
            bottom=ft.BorderSide(1, BORDER)),
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
    # F3 — the parlay law (engine law wins, v10.4.1):
    # * same game: two or more legs on one game (same FanDuel
    #   event id, or the same sport + away + home key) make the
    #   slip a same-game parlay. No correlation engine prices it,
    #   so NO combined figure is issued — the block renders the
    #   UNPRICED stamp with its reason instead.
    # * cross-game: the independence math stands, and the
    #   combined grade is capped at the weakest leg's grade —
    #   the engine's grouping law (a basket is graded by its
    #   basket, never by its best part).
    def _game_key(mkt):
        if mkt.get("fd_event_id") is not None:
            return ("fd", mkt["fd_event_id"])
        return ("teams", mkt.get("sport"), mkt.get("away"),
                mkt.get("home"))

    keys = [_game_key(m) for m, _v in legs]
    same_game = len(set(keys)) != len(keys)
    grade = b5.base_grade(edge_pts)
    leg_grades = [v.get("grade") for _m, v in legs
                  if v.get("grade")]
    grade_capped = False
    if leg_grades:
        weakest = max(leg_grades, key=grade_rank)
        if grade_rank(weakest) > grade_rank(grade):
            grade = weakest
            grade_capped = True
    return {"decimal": dec, "american": b5.decimal_to_american(dec),
            "model_p": p, "implied": implied, "ev": ev,
            "edge_pts": edge_pts, "verdict": verdict,
            "grade": grade, "grade_capped": grade_capped,
            "same_game": same_game,
            "stance": b5.parlay_stance(
                [v.get("stance") for _m, v in legs]),
            "conflicts": conflicts}


SAME_GAME_REASON = ("Same-game parlay — no correlation engine "
                    "prices this; an independence product would "
                    "be a lie of precision.")



# ------------------------------------------------------------------
# The Lab ledger (F2). Columnar rows under per-book summary
# headers; result pills always carry text AND colour (colour is
# never the only signal). The two books render through the same
# row builder but keep separate headers and separate totals —
# they are never merged (lab law I-L2, the Room Rule).
# Tabular numerals: Flet 1.0.4 exposes no font-feature switch,
# so columns are fixed-width and right-aligned and every number
# is formatted to a consistent shape — the columns line up by
# construction.

_RESULT_PILL = {
    "WON": ("#065F46", "#34D399"),
    "LOST": ("#7F1D1D", "#F87171"),
    "PENDING": ("#1F2937", "#9CA3AF"),
    "VOID": ("#334155", "#CBD5E1"),
}

_ODDS_RE = re.compile(r"[+-]\d{2,5}(?!\d)")


def result_pill(result):
    """The Result cell: a pill for the four settled states, a
    plain cell for anything else (an aggregate record like
    '3-3' is not a single bet's result and is never pill-washed
    into one)."""
    key = (result or "").strip().upper()
    if key in _RESULT_PILL:
        bg, fg = _RESULT_PILL[key]
        return ft.Container(
            bgcolor=bg, border_radius=20,
            padding=ft.Padding(left=8, right=8, top=3, bottom=3),
            content=ft.Text(key, size=11, color=fg,
                            weight=ft.FontWeight.BOLD))
    return ft.Text(result or "—", size=12, color=INK)


def ticket_odds(ticket):
    """The first American price printed in a recorded ticket
    string — read off the record, never reconstructed."""
    m = _ODDS_RE.search(ticket or "")
    return m.group(0) if m else "—"


def ledger_header():
    return ft.Container(
        padding=ft.Padding(left=8, right=8, top=4, bottom=4),
        border=ft.Border(bottom=ft.BorderSide(1, BORDER)),
        content=ft.Row(spacing=6, controls=[
            ft.Text("DATE", size=10, color=FAINT, width=64,
                    weight=ft.FontWeight.BOLD),
            ft.Text("BET", size=10, color=FAINT, expand=True,
                    weight=ft.FontWeight.BOLD),
            ft.Text("ODDS", size=10, color=FAINT, width=48,
                    text_align=ft.TextAlign.RIGHT,
                    weight=ft.FontWeight.BOLD),
            ft.Text("GRADE", size=10, color=FAINT, width=42,
                    text_align=ft.TextAlign.CENTER,
                    weight=ft.FontWeight.BOLD),
            ft.Text("RESULT", size=10, color=FAINT, width=78,
                    text_align=ft.TextAlign.CENTER,
                    weight=ft.FontWeight.BOLD),
            ft.Text("P/L", size=10, color=FAINT, width=58,
                    text_align=ft.TextAlign.RIGHT,
                    weight=ft.FontWeight.BOLD)]))


def ledger_row(date, bet, odds, grade, result, pl, zebra=False,
               bet_note=None, pl_color=None):
    bet_cell = [ft.Text(bet, size=12, color=INK, height=1.3)]
    if bet_note:
        bet_cell.append(ft.Text(bet_note, size=10, color=FAINT))
    return ft.Container(
        bgcolor=RAISED if zebra else CARD_BG, border_radius=6,
        padding=ft.Padding(left=8, right=8, top=7, bottom=7),
        content=ft.Row(
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Text(date or "—", size=11, color=DIM,
                        width=64),
                ft.Column(spacing=1, expand=True,
                          controls=bet_cell),
                ft.Text(odds or "—", size=12, color=INK,
                        width=48,
                        text_align=ft.TextAlign.RIGHT),
                ft.Text(grade or "—", size=12, color=DIM,
                        width=42,
                        text_align=ft.TextAlign.CENTER),
                ft.Container(width=78,
                             alignment=ft.Alignment(0, 0),
                             content=result_pill(result)),
                ft.Text(pl or "—", size=12,
                        color=pl_color or INK, width=58,
                        text_align=ft.TextAlign.RIGHT)]))


def book_header(title, lines, edge):
    return ft.Container(
        bgcolor=RAISED, border_radius=10, padding=12,
        border=_border_all(1, edge),
        content=ft.Column(spacing=3, controls=(
            [ft.Text(title, size=14, color=INK,
                     weight=ft.FontWeight.BOLD)]
            + [ft.Text(t, size=12, color=DIM, height=1.35)
               for t in lines])))

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
             "parlay_legs": [], "view": "board",
             "board_seg": "all", "slip_seg": "parse",
             "instrument_url": None, "animate_next": False,
             "toggles_for": None, "bankroll": ""}
    stamp_text, degraded = stamp_of(state["slate"])
    stamp_ctrl = ft.Text(f"Menu: {stamp_text}", size=12,
                         color=WARN if degraded else DIM)
    status = ft.Text("", size=12, color=ACCENT)

    # view containers — the five destinations (v10.4.1 nav):
    # Board (cards + finds behind a segment), Slip (Parse /
    # Parlay / Solver behind a segment), Lab, the 3D shelf,
    # More — plus the More sub-views (Terms / Equations / Dev).
    cards_view = ft.Column(spacing=8)
    betfi_view = ft.Column(spacing=8)
    board_view = ft.Column(spacing=8)
    parse_view = ft.Column(spacing=8)
    parlay_view = ft.Column(spacing=8)
    solver_view = ft.Column(spacing=8)
    slip_view = ft.Column(spacing=8)
    record_view = ft.Column(spacing=8)
    stage_view = ft.Column(spacing=8)
    more_view = ft.Column(spacing=8)
    terms_view = ft.Column(spacing=8)
    equations_view = ft.Column(spacing=8)
    dev_view = ft.Column(spacing=8)
    views = {"board": board_view, "slip": slip_view,
             "lab": record_view, "stage": stage_view,
             "more": more_view, "terms": terms_view,
             "equations": equations_view, "dev": dev_view}
    TOP_VIEWS = ["board", "slip", "lab", "stage", "more"]

    def _switcher(content):
        return ft.AnimatedSwitcher(
            content=content, duration=220,
            transition=ft.AnimatedSwitcherTransition.FADE,
            switch_in_curve=ft.AnimationCurve.DECELERATE,
            switch_out_curve=ft.AnimationCurve.EASE_IN)

    board_switcher = _switcher(cards_view)
    slip_switcher = _switcher(parse_view)
    view_switcher = _switcher(board_view)

    # ---- the two segmented controls (stock Flet segments) ----

    def _segmented(options, selected, handler):
        return ft.SegmentedButton(
            segments=[ft.Segment(
                value=v, label=ft.Text(lbl, size=13))
                for v, lbl in options],
            selected=[selected], allow_empty_selection=False,
            on_change=handler)

    def show_board_segment(seg: str):
        state["board_seg"] = seg
        board_seg_ctrl.selected = [seg]
        finds = seg == "finds"
        board_switcher.content = betfi_view if finds \
            else cards_view
        if finds:
            render_betfi()
        else:
            render_cards()
        page.update()

    def on_board_seg(e):
        sel = e.control.selected or []
        show_board_segment(next(iter(sel)) if sel else "all")

    board_seg_ctrl = _segmented(
        [("all", "All cards"), ("finds", "Finds")], "all",
        on_board_seg)

    def show_slip_tool(tool: str):
        state["slip_seg"] = tool
        slip_seg_ctrl.selected = [tool]
        slip_switcher.content = {"parse": parse_view,
                                 "parlay": parlay_view,
                                 "solver": solver_view}[tool]
        if tool == "parse":
            render_parse()
        elif tool == "parlay":
            render_parlay()
        else:
            render_solver()
        page.update()

    def on_slip_seg(e):
        sel = e.control.selected or []
        show_slip_tool(next(iter(sel)) if sel else "parse")

    slip_seg_ctrl = _segmented(
        [("parse", "Parse"), ("parlay", "Parlay"),
         ("solver", "Solver")], "parse", on_slip_seg)

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

    def _animate_cards(cards):
        # F3: cards fade/rise in once per fresh slate (boot,
        # pull, price pass) — toggles, sorts and search never
        # re-run this; render_cards consumes the flag.
        cards = [c for c in cards
                 if isinstance(c, ft.Container)]
        if not cards:
            return
        for c in cards:
            c.opacity = 0
            c.offset = ft.Offset(0, 0.04)
            c.animate_opacity = ft.Animation(
                300, ft.AnimationCurve.DECELERATE)
            c.animate_offset = ft.Animation(
                300, ft.AnimationCurve.DECELERATE)
        page.update()

        def _flip():
            import time as _time
            for k, c in enumerate(cards):
                if 0 < k <= 10:
                    _time.sleep(0.03)   # stagger, capped (F3)
                c.opacity = 1
                c.offset = ft.Offset(0, 0)
                try:
                    c.update()
                except Exception:
                    pass
        page.run_thread(_flip)

    def render_cards():
        cards_list.controls = []
        rec = state["slate"]
        if not rec:
            cards_toggles.controls = []
            state["toggles_for"] = None
            cards_count.value = ""
            cards_list.controls = [empty_full(
                ft.Icons.CLOUD_OFF, "No pull yet",
                "Tap Pull Menu — until a live pull lands, every "
                "market is UNVERIFIED, never assumed.")]
            page.update()
            return
        entries = sorted_entries()
        # F4: the toggle row is rebuilt only when
        # the slate itself changes — sort, search and
        # toggle events update the cards in place.
        if state.get("toggles_for") != id(rec):
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
            state["toggles_for"] = id(rec)
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
        if state.pop("animate_next", False):
            _animate_cards(cards_list.controls)
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
        cards_list.controls = skeleton_cards()
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
            state["animate_next"] = True
            render_cards()
            page.update()
        except Exception as e:
            status.value = (f"Pull failed on this device: "
                            f"{type(e).__name__}: {e}")
            try:
                page.update()
            except Exception:
                pass

    def _boot_worker():
        # The first pricing pass, off the paint path (F4).
        try:
            ensure_verdicts()
            state["animate_next"] = True
            if status.value == "Pricing the last pull…":
                status.value = ""
            if state["view"] == "board":
                show_board_segment(state["board_seg"])
            page.update()
        except Exception as e:
            status.value = (f"Pricing the last pull failed on "
                            f"this device: {type(e).__name__}: {e}")
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
        cards_list.controls = skeleton_cards()
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
            state["animate_next"] = True
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
        disp = fd_market_name({"market": parsed["market"],
                               "sport": None})
        rows.append(_kv_row("Market", disp))
        if parsed.get("selection"):
            rows.append(_kv_row("Bet", parsed["selection"]))
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
            parse_result.controls.append(_kelly_block(
                verdict.get("p"), mkt.get("price"),
                lane=market_lane(mkt),
                cal_tag=verdict.get("cal_tag"),
                priced=verdict.get("state") == "PRICED"))
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

    def _kelly_block(p, price, lane=None, cal_tag=None,
                     priced=True):
        # F5b display: the engine's Kelly organ advises a stake
        # range; it never places or queues anything. Priced off
        # the pessimistic number, quarter-Kelly, 5% hard cap,
        # UNCALIBRATED lanes damped — every adjustment prints
        # its reason (kelly_advice returns them).
        rows = [ft.Text("KELLY SIZING — ADVISORY ONLY", size=11,
                        color=ACCENT, weight=ft.FontWeight.BOLD),
                ft.Text("Advice for your own slip — the app "
                        "never places or queues a bet.",
                        size=10, color=FAINT)]
        bankroll = None
        try:
            bankroll = float(state.get("bankroll") or "") \
                or None
        except (TypeError, ValueError):
            bankroll = None
        adv = b5.kelly_advice(p, price, bankroll=bankroll,
                              cal_tag=cal_tag, priced=priced)
        if adv["state"] == "UNPRICED":
            rows.append(ft.Text(adv["reasons"][0], size=12,
                                color=DIM, height=1.35))
        else:
            stake = (f"Advised stake "
                     f"{adv['stake_units']:.1f}u – "
                     f"{adv['stake_units_hi']:.1f}u")
            if adv["stake_dollars"] is not None:
                stake += (f"  (${adv['stake_dollars']:,.0f} – "
                          f"${adv['stake_dollars_hi']:,.0f} of "
                          f"${bankroll:,.0f})")
            rows.append(ft.Text(
                stake, size=14, color=INK,
                weight=ft.FontWeight.BOLD))
            for reason in adv["reasons"]:
                rows.append(ft.Text(reason, size=11, color=DIM,
                                    height=1.35))
            if lane:
                mc = b5.kelly_mc_bands(p, price,
                                       adv["stake_frac"],
                                       lane=lane)
            else:
                mc = {"state": "insufficient scored history",
                      "note": "no single lane prices this slip "
                              "(mixed lanes) — no Monte Carlo "
                              "bands"}
            if mc.get("state") == "simulated":
                rows.append(ft.Text(mc["basis"], size=11,
                                    color=DIM, height=1.35))
                rows.append(ft.Text(
                    f"If this exact bet repeated "
                    f"{mc['bets_per_path']} times at that "
                    f"stake: median bankroll "
                    f"×{mc['median_final']:.2f} · worst-decile "
                    f"drawdown {mc['p90_max_dd_pct']:.0f}% · "
                    f"ruin (under 10% of start) on "
                    f"{mc['ruin_rate'] * 100:.0f}% of paths.",
                    size=11, color=DIM, height=1.35))
            else:
                rows.append(ft.Text(
                    f"Monte Carlo: {mc.get('note')}",
                    size=11, color=FAINT, height=1.35))
        return ft.Container(
            bgcolor=CARD_BG, border=_border_all(1, BORDER),
            border_radius=10, padding=12,
            content=ft.Column(spacing=5, controls=rows))

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
                _nm = bet_name(mkt, verdict)
                edge = market_edge_pts(mkt, verdict)
                meta = (f"{_nm['market']} · "
                        f"{int(mkt['price']):+d} · model "
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
                                              _nm["selection"],
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
                    text=bet_name(m, v)["slip_label"])
                    for i, m, v in avail],
                on_select=lambda e: state.update(
                    {"parlay_pick": e.control.value}))
            parlay_view.controls.append(ft.Row(spacing=8, controls=[
                dd, ft.Button("Add leg", on_click=on_add_leg)]))
            parlay_view.controls.append(parlay_msg)
        parlay_view.controls.append(ft.Row(spacing=8, controls=[
            ft.TextField(
                label="Bankroll $ — for Kelly $ sizing",
                value=state["bankroll"], width=220,
                keyboard_type=ft.KeyboardType.NUMBER,
                on_change=lambda e: state.update(
                    {"bankroll": e.control.value or ""})),
            ft.Button("Update sizing",
                      on_click=lambda _e: render_parlay())]))
        if legs:
            parlay_view.controls.append(_combined_block(legs))
        page.update()

    def _combined_block(legs):
        c = parlay_combine(legs)
        if c["same_game"]:
            # F3: the combined block is REPLACED by the UNPRICED
            # stamp — no combined odds, probability, EV or grade
            # is printed for a same-game slip, anywhere on the app.
            stamp_rows = [
                _kv_row("Legs", str(len(legs))),
                ft.Row(spacing=8, controls=[
                    verdict_pill("UNPRICED", unpriced=True)]),
                ft.Text(SAME_GAME_REASON, size=12, color=DIM,
                        height=1.35),
                ft.Text("The legs above still price on their own "
                        "cards. What no engine here will print is "
                        "a combined number for them.",
                        size=11, color=FAINT, height=1.35)]
            return ft.Container(
                bgcolor=RAISED, border=_border_all(1, CHIP_BORDER),
                border_radius=10, padding=12,
                content=ft.Column(spacing=6, controls=stamp_rows))
        rows = [_kv_row("Legs", str(len(legs))),
                ft.Row(spacing=8, controls=[
                    ft.Container(width=110, content=ft.Text(
                        "Grade", size=11, color=FAINT)),
                    ft.Text(c["grade"], size=16,
                            color=GRADE_COLORS.get(
                                c["grade"], INK),
                            weight=ft.FontWeight.BOLD)]),
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
        if c["grade_capped"]:
            rows.append(ft.Text(
                f"Combined grade capped at the weakest leg "
                f"({c['grade']}) — the grouping law: a slip is "
                f"graded by its weakest leg, never its best.",
                size=11, color=WARN, height=1.35))
        rows.append(ft.Text(
            "Combined probability = product of the legs' "
            "probabilities. That assumes the legs are independent "
            "— treat it as a ceiling. Same-game legs never get a "
            "combined number at all (see the stamp rule in "
            "Terms).", size=10, color=FAINT, height=1.35))
        _lanes = {market_lane(m) for m, _v in legs}
        _lane = _lanes.pop() if len(_lanes) == 1 else None
        _tag = None
        if _lane:
            try:
                _tag = b5.calibration_tag(
                    _lane, b5.load_scorecard())
            except Exception:
                _tag = None
        rows.append(_kelly_block(c["model_p"], c["american"],
                                 lane=_lane, cal_tag=_tag))
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
        return ft.Container(
            bgcolor=RAISED, border_radius=10, padding=12,
            border=_border_all(1, BORDER),
            shadow=ft.BoxShadow(blur_radius=10, spread_radius=0,
                                color="#00000055",
                                offset=ft.Offset(0, 3)),
            content=ft.Column(spacing=8, controls=controls))

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
        # More is closed to new tiles in 10.4.x (UX nav law):
        # the finds feed moved to the Board and the Record grew
        # into the Lab destination — what remains is reference.
        tiles = [
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
        betfi_view.controls = [ft.Text(
            "Finds — golden bets first, then the ranked finds. "
            "Same pull, same prices as All cards; the feed only "
            "re-ranks.", size=12, color=DIM, height=1.35)]
        rec = state["slate"]
        if not rec:
            betfi_view.controls.append(empty_full(
                ft.Icons.CLOUD_OFF, "Nothing to distill",
                "The feed distills the current pull — pull the "
                "menu on the Board first."))
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
                f"page cap — All cards on the Board holds the "
                f"full list.", size=11, color=FAINT))
        if flagged:
            betfi_view.controls.append(section_header(
                f"PRICE CONFLICT — two prices for the same event "
                f"disagree inside this pull ({len(flagged)})",
                WARN))
            for mkt, verdict, edge in flagged:
                betfi_view.controls.append(build_market_card(
                    mkt, verdict, rec, quotes, edge_pts=edge,
                    lane_ctx=ctx))
        counter_lines = []
        for _m, v, e in counter:
            _nm = bet_name(_m, v)
            counter_lines.append(
                f"{_nm['selection']} · {_nm['market']} — "
                f"{v.get('state')}"
                + (f" · edge {e:+.1f} pts"
                   if e is not None else ""))
        betfi_view.controls.append(ft.ExpansionTile(
            title=ft.Text(f"Checked — no edge ({len(counter)})",
                          size=12, color=FAINT,
                          weight=ft.FontWeight.BOLD),
            controls=[ft.Container(padding=8, content=ft.Column(
                spacing=2, controls=[_line(t, 10, FAINT)
                                     for t in counter_lines]))]))
        page.update()

    # ---------------- Lab (the record wing) ----------------

    def _money(v) -> str:
        return f"${abs(v):,.0f}" if float(v) == int(v) \
            else f"${abs(v):,.2f}"

    def _signed_money(v) -> str:
        return ("+" if v > 0 else "−" if v < 0 else "") \
            + _money(v)

    def render_lab():
        pack = load_lab_pack()
        record_view.controls = [screen_title(
            "Lab",
            "The record wing — the lab's graded history, read "
            "from the bundled evidence pack.")]
        if pack is None:
            # ROOM RULE failure state: a named state, never a
            # ledger — no lane rows, no book sections, no totals.
            record_view.controls.append(empty_full(
                ft.Icons.FOLDER_OFF, "Record not bundled",
                "This build shipped without the lab evidence "
                "pack, so the Lab shows no record at all — never "
                "an empty ledger dressed as 0-0. The full BetFi "
                "build carries the pack."))
            page.update()
            return
        exported = str(pack.get("exported_at") or "")
        record_view.controls.append(ft.Text(
            f"Lab record as of {exported[:10]} · evidence pack "
            f"exported {exported} · the app reads it, only the "
            f"lab writes it.", size=11, color=FAINT, height=1.35))
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
                f"price conflicts {flagged_n} · the rest "
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
                "No pull on this device yet — this section fills "
                "with the first pull. The graded record below is "
                "the pack's, and stands whether or not a pull "
                "has landed.", size=12, color=DIM, height=1.35))
        record_view.controls.append(ft.Divider(color=BORDER))
        record_view.controls.append(section_header(
            "LANE LEDGER — WIN / LOSE OF RECORD", ACCENT))
        card = b5.load_scorecard()
        for _li, lane in enumerate(RECORD_LANES):
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
            record_view.controls.append(ft.Container(
                bgcolor=RAISED if _li % 2 else CARD_BG,
                border_radius=6,
                padding=ft.Padding(left=8, right=8, top=7,
                                   bottom=7),
                content=ft.Column(spacing=2, controls=[
                    ft.Row(spacing=8, controls=[
                        ft.Text(lane, size=13, color=INK,
                                width=110,
                                weight=ft.FontWeight.BOLD),
                        ft.Text(f"W {w} · L {l}", size=13,
                                color=INK, width=92),
                        ft.Text(f"tag {tag}{status_line}"
                                + (f" · {uncal}" if uncal
                                   else ""),
                                size=11, color=DIM,
                                expand=True)]),
                    ft.Text(src, size=10, color=FAINT)])))
        entries = card.get("entries") or []
        record_view.controls.append(ft.Text(
            f"Scorecard entries on device: {len(entries)} · "
            f"graded by the engine's record laws; the full "
            f"entries live in the lab.", size=11, color=FAINT))
        # ---- the two books: separate sections, separate
        # totals, no combined figure anywhere (lab law I-L2) ----
        record_view.controls.append(ft.Divider(color=BORDER))
        sealed = pack.get("sealed_cards") or []
        if sealed:
            tot_net = sum(float(sc.get("net_units") or 0)
                          for sc in sealed)
            last = sealed[-1]
            record_view.controls.append(book_header(
                "LAB CARD — PAPER, SEALED BY THE PIPELINE",
                [f"Sealed cards on file: {len(sealed)} · "
                 f"latest {last.get('date')} · "
                 f"{last.get('name')}",
                 f"Record {last.get('record')} · net "
                 f"{tot_net:+.2f}u · ROI "
                 f"{last.get('roi_pct'):+.1f}% · CLV "
                 f"{last.get('clv')} — paper: no money ever "
                 f"moved on this book. Totals are this book's "
                 f"alone."],
                ACCENT))
            record_view.controls.append(ledger_header())
            for _si, sc in enumerate(sealed):
                _net = float(sc.get("net_units") or 0)
                record_view.controls.append(ledger_row(
                    sc.get("date"), sc.get("name"), "—", "—",
                    sc.get("record"), f"{_net:+.2f}u",
                    zebra=bool(_si % 2),
                    bet_note=f"CLV {sc.get('clv')}",
                    pl_color=("#34D399" if _net > 0 else
                              "#F87171" if _net < 0 else INK)))
        else:
            record_view.controls.append(ft.Text(
                "No sealed card in this pack.", size=12,
                color=DIM))
        screened = pack.get("screened_not_sealed")
        if screened:
            record_view.controls.append(ft.Text(
                f"{screened} packets were screened and held — "
                f"screened is not sealed. They never became "
                f"cards and are not in any total above.",
                size=11, color=FAINT, height=1.35))
        record_view.controls.append(ft.Divider(color=BORDER))
        tickets = pack.get("pilot_book") or []
        closed = pack.get("pilot_book_closed_line") or {}
        pending = [t for t in tickets
                   if (t.get("result") or "PENDING") == "PENDING"]
        header_lines = []
        if closed:
            header_lines.append(
                f"Closed line (as of {closed.get('as_of')}): "
                f"{_money(closed.get('staked') or 0)} staked → "
                f"{_money(closed.get('returned') or 0)} returned "
                f"· net {_signed_money(closed.get('net') or 0)} "
                f"— this book only.")
        if pending:
            _pend_stake = sum(float(t.get("stake") or 0)
                              for t in pending)
            header_lines.append(
                f"{len(pending)} ticket(s) pending — "
                f"{_money(_pend_stake)} staked, in no "
                f"total until they settle.")
        header_lines.append(
            "His plays, graded on their own lines. The two "
            "books are never added together.")
        record_view.controls.append(book_header(
            "PILOT BOOK — HIS PLAYS, THEIR OWN LINES",
            header_lines, "#EAB308"))  # gold edge: the Pilot Book
        record_view.controls.append(ledger_header())
        for _ti, t in enumerate(tickets):
            res = t.get("result") or "PENDING"
            if res == "PENDING":
                pl, plc = "—", None
                note = (f"stake {_money(t.get('stake') or 0)}"
                        f" · result not recorded")
            else:
                net = float(t.get("net") or 0)
                pl = _signed_money(net)
                plc = ("#34D399" if net > 0 else
                       "#F87171" if net < 0 else INK)
                note = (f"stake {_money(t.get('stake') or 0)}"
                        f" → returned "
                        f"{_money(t.get('returned') or 0)}")
            record_view.controls.append(ledger_row(
                t.get("date"), t.get("ticket"),
                ticket_odds(t.get("ticket")), "—", res, pl,
                zebra=bool(_ti % 2), bet_note=note,
                pl_color=plc))
        record_view.controls.append(ft.Divider(color=BORDER))
        record_view.controls.append(section_header(
            "CLV & DRIFT — MEASUREMENT, NOT A GRADE", ACCENT))
        _pulls, _seen_at = [], set()
        for _d in (b5.DATA, BUNDLED_DATA_DIR):
            try:
                _names = sorted(os.listdir(_d))
            except Exception:
                _names = []
            for _fn in _names:
                if (_fn.startswith("menu-fanduel-")
                        and _fn.endswith(".json")):
                    try:
                        with open(os.path.join(_d, _fn)) as _fh:
                            _rec_p = json.load(_fh)
                    except Exception:
                        continue
                    if _rec_p.get("pulled_at") not in _seen_at:
                        _seen_at.add(_rec_p.get("pulled_at"))
                        _pulls.append(_rec_p)
        _bets = [{"lane": e.get("lane") or "?", "price": None,
                  "close_price": None} for e in entries]
        try:
            _clv = b5.clv_report(_pulls, _bets)
        except Exception:
            _clv = None
        if _clv is None:
            record_view.controls.append(ft.Text(
                "The CLV ledger could not run on this device.",
                size=12, color=DIM))
        else:
            _dr = _clv["drift"]
            record_view.controls.append(ft.Text(
                f"Menu pulls on file: {_dr['snapshots']} · "
                f"markets seen {_dr['markets_seen']} · tracked "
                f"across two or more pulls "
                f"{_dr['markets_tracked']}.", size=12, color=DIM,
                height=1.35))
            if _dr["markets_tracked"]:
                record_view.controls.append(ft.Text(
                    f"Median |drift| across tracked markets: "
                    f"{_dr['median_abs_drift_pts']:.2f} pts "
                    f"(implied probability, first pull to last).",
                    size=12, color=DIM, height=1.35))
            else:
                record_view.controls.append(ft.Text(
                    "Drift: insufficient snapshots — one pull "
                    "cannot show a market moving, so no drift "
                    "is printed. Nothing is invented to fill "
                    "this.", size=12, color=DIM, height=1.35))
            for _lr in _clv["lanes"]:
                _mean = (_lr["mean_clv_pts"]
                         if _lr["mean_clv_pts"] is not None
                         else None)
                record_view.controls.append(ft.Text(
                    f"CLV {_lr['lane']}: {_lr['closed']} closed "
                    f"bets · {_lr['unclosed']} without a closing "
                    f"snapshot · mean CLV "
                    + (f"{_mean:+.2f} pts" if _mean is not None
                       else "—")
                    + f" · state: {_lr['state']}",
                    size=12, color=DIM, height=1.35))
            record_view.controls.append(ft.Text(
                "CLV grades the price you got against the "
                "close — it feeds no grade, verdict or tag "
                "(engine v5.3, display only).", size=11,
                color=FAINT, height=1.35))
        record_view.controls.append(ft.Divider(color=BORDER))
        record_view.controls.append(section_header(
            "KILL LEDGER — BARRED, READ-ONLY", ACCENT))
        kills = pack.get("kill_ledger_items")
        record_view.controls.append(ft.Text(
            f"{kills} patterns are barred by the lab's Hard Kill "
            f"Ledger — shapes that failed their sealed tests and "
            f"may not be bet in any form. The full text lives "
            f"in the lab (LAB.md); the app shows the count and "
            f"the rule, and nothing un-bars a pattern from "
            f"here.", size=12, color=DIM, height=1.35))
        gov = pack.get("governor_note")
        if gov:
            record_view.controls.append(ft.Text(
                f"Governor at export: {gov}.",
                size=11, color=FAINT, height=1.35))
        record_view.controls.append(ft.Divider(color=BORDER))
        record_view.controls.append(section_header(
            "THE RUBRIC — HOW A BET IS GRADED", ACCENT))
        bands = " · ".join(
            f"{g} ≥ {floor:+g}" for floor, g
            in b5.GRADE_BANDS_V52)
        record_view.controls.append(ft.Text(
            f"Grade bands (edge, points): {bands} · below the "
            f"last floor: F.", size=12, color=DIM, height=1.35))
        record_view.controls.append(ft.Text(
            "Then the named adjustments: FRAGILE −1 grade when a "
            "thin or single-source price holds half the edge; "
            "PRICE DISCIPLINE −1 when the model asks for a price "
            "the market rarely deals; a parlay's grade capped "
            "at its weakest leg; UNPRICED always capped at "
            "DO NOT BET. Every adjustment prints its reason on "
            "the card or the slip — a grade never moves in "
            "silence.", size=12, color=DIM, height=1.35))
        record_view.controls.append(ft.Divider(color=BORDER))
        record_view.controls.append(ft.Text(
            f"App: {DISPLAY_NAME} v{APP_VERSION} · Engine: "
            f"{ENGINE_VERSION} · {engine_fingerprint()}",
            size=12, color=ACCENT))
        record_view.controls.append(ft.Text(
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
             "an A-band grade, an edge still +2.0 pts or better "
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
             "wrong; the card shows which quotes fight. On the "
             "Board the state prints as PRICE CONFLICT."),
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
             "the pull — the Quick bets toggle on the Board. The "
             "clock is the pull's own timestamp, so a stale pull "
             "shows its quick window as it stood when pulled, "
             "stamped STALE like everything else on it."),
        ]),
        ("THE LAB, THE PACK, AND THE SLIP LAW", [
            ("Evidence pack", "the lab's record, exported from "
             "the lab and bundled with the app: the scorecard, "
             "the lane history, the phi registry and the lane "
             "fits, stamped with the time of its export. The "
             "app reads it and displays it; only the lab writes "
             "it. The Lab face prints the pack's stamp — 'Lab "
             "record as of' that date."),
            ("Room Rule", "the Lab wing ships populated: the "
             "record exists, so the room is never empty. If a "
             "build carries no evidence pack, the Lab prints "
             "'record not bundled' instead of an empty record "
             "dressed as 0-0."),
            ("Sealed card", "a lab card locked before its games "
             "and graded after — paper only. Packets that were "
             "screened and held are not cards and never enter "
             "a total."),
            ("Pilot Book", "the Pilot's own placed plays, graded "
             "on their own lines in their own section. The Lab "
             "Card and the Pilot Book are never added together; "
             "there is no combined record."),
            ("Same-game parlay", "two or more legs on the same "
             "game. The app stamps the slip UNPRICED and prints "
             "no combined number: no correlation engine prices "
             "same-game legs, and an independence product would "
             "be a lie of precision. The legs still price on "
             "their own cards."),
            ("Weakest-leg cap", "a parlay's combined grade can "
             "never beat the grade of its weakest leg — the "
             "grouping law. When the cap binds, the Parlay page "
             "says so in words."),
            ("Closed-form WP", "the Win Probability instruments "
             "compute win probability from score difference and "
             "clock with a closed-form curve — a different, "
             "simpler estimator than the engine's live Monte "
             "Carlo matrix. Both names are printed so the two "
             "are never confused."),
            ("Snapshot", "an instrument labelled SNAPSHOT or "
             "FROZEN shows recorded data from the window on its "
             "label — it does not update. One labelled MODEL — "
             "COMPUTED LIVE evaluates its model as you move."),
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

    def _pack_stamp_line() -> str:
        pack = load_lab_pack()
        if pack is None:
            return "not bundled in this edition"
        return (f"lab-export/1 · exported "
                f"{pack.get('exported_at')} · seeded at startup: "
                f"{'yes' if PACK_STATUS.get('seeded') else 'no'}")

    def _instruments_line() -> str:
        n, total = instruments_bundled()
        if n == 0:
            return "not bundled in this edition"
        return f"{n} of {len(INSTRUMENTS)} bundled · {total} bytes"

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
                _kv_row("Internal id", INTERNAL_ID),
                _kv_row("Evidence pack",
                        _pack_stamp_line()),
                _kv_row("Instruments",
                        _instruments_line())]))
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

    # ---------------- 3D — the instruments shelf ----------------

    # Flet 1.0.4's verified URL route: the UrlLauncher service
    # (page.launch_url does not exist in the pinned version, and
    # there is no WebView) — registered once, used per tap.
    url_launcher = ft.UrlLauncher()
    try:
        page.services.append(url_launcher)
    except Exception:
        pass
    clipboard = ft.Clipboard()
    try:
        page.services.append(clipboard)
    except Exception:
        pass
    bind_clipboard(clipboard)
    stage_status = ft.Text("", size=12, color=DIM)

    def on_open_instrument(inst):
        def _open(_e):
            port = ensure_instrument_server()
            if port is None:
                stage_status.value = (
                    "The instruments folder isn't reachable in "
                    "this edition — nothing to open.")
                page.update()
                return
            url = f"http://127.0.0.1:{port}/{inst['file']}"
            state["instrument_url"] = url
            try:
                page.run_task(url_launcher.launch_url, url)
                stage_status.value = (f"Opening {inst['name']} "
                                      f"full-screen…")
            except Exception as ex:
                stage_status.value = (
                    f"Couldn't open {inst['name']}: "
                    f"{type(ex).__name__}: {ex}")
            page.update()
        return _open

    def render_stage():
        stage_view.controls = [screen_title(
            "Instruments",
            "The lab's instruments — snapshots and live models, "
            "each labelled as what it is.")]
        n, _total = instruments_bundled()
        if n == 0:
            stage_view.controls.append(empty_full(
                ft.Icons.VIEW_IN_AR,
                "Instruments not bundled in this edition",
                "This build shipped without the instruments "
                "folder, so the shelf prints its state instead "
                "of a dead list. The full BetFi build "
                "carries all 11."))
            page.update()
            return
        stage_view.controls.append(stage_status)
        try:
            # lazy warm-up: the loopback server starts on a
            # worker thread the first time the shelf opens, so
            # the first tap finds its port already bound.
            page.run_thread(ensure_instrument_server)
        except Exception:
            pass
        for family in INSTRUMENT_FAMILIES:
            members = [i for i in INSTRUMENTS
                       if i["family"] == family
                       and os.path.isfile(os.path.join(
                           INSTRUMENTS_DIR, i["file"]))]
            if not members:
                continue
            stage_view.controls.append(section_header(
                family.upper(), ACCENT))
            for inst in members:
                stage_view.controls.append(ft.Container(
                    bgcolor=CARD_BG, border_radius=10, padding=10,
                    content=ft.Column(spacing=4, controls=[
                        ft.Row(
                            spacing=8, alignment=ft
                            .MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(inst["name"], size=14,
                                        color=INK, weight=ft
                                        .FontWeight.BOLD),
                                ft.Button(
                                    "Open",
                                    on_click=on_open_instrument(
                                        inst))]),
                        ft.Text(inst["note"], size=11, color=DIM,
                                height=1.3),
                        ft.Text(inst["chip"], size=10,
                                color=FAINT)])))
            if family == "Stocks":
                stage_view.controls.append(ft.Text(
                    STOCKS_SAMPLE_NOTE, size=10, color=FAINT,
                    height=1.35))
        page.update()

    # ---------------- navigation ----------------

    def show(name: str):
        state["view"] = name
        view_switcher.content = views[name]
        if page.navigation_bar is not None:
            page.navigation_bar.selected_index = \
                TOP_VIEWS.index(name) if name in TOP_VIEWS else 4
        if name == "board":
            show_board_segment(state["board_seg"])
        elif name == "slip":
            show_slip_tool(state["slip_seg"])
        elif name == "lab":
            render_lab()
        elif name == "stage":
            render_stage()
        elif name == "more":
            render_more()
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

    header = ft.Container(
        gradient=ft.LinearGradient(
            begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
            colors=["#0D1730", PAGE_BG]),
        border=ft.Border(
            bottom=ft.BorderSide(1, BORDER)),
        padding=ft.Padding(left=2, right=2, top=2, bottom=8),
        content=ft.Column(spacing=4, controls=[
            ft.Text(PUBLIC_NAME, size=22, color=INK,
                    weight=ft.FontWeight.BOLD),
            ft.Text(f"{DISPLAY_NAME} · engine {ENGINE_VERSION} · "
                    f"analysis only — never places a bet",
                    size=11, color=FAINT),
            stamp_ctrl,
        ]))
    cards_view.controls = [
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
    board_view.controls = [
        screen_title("Board",
                     "Every checked market on the current pull."),
        board_seg_ctrl,
        board_switcher]
    slip_view.controls = [
        screen_title("Slip", "The ticket tools — read a slip, "
                             "build a parlay, size a stake."),
        slip_seg_ctrl,
        slip_switcher]
    page.add(header, view_switcher)

    nav_bar_cls = getattr(ft, "NavigationBar", None)
    nav_dest_cls = (getattr(ft, "NavigationDestination", None)
                    or getattr(ft, "NavigationBarDestination", None))
    if nav_bar_cls is not None and nav_dest_cls is not None:
        page.navigation_bar = nav_bar_cls(
            selected_index=0, on_change=on_nav,
            destinations=[
                nav_dest_cls(icon=ft.Icons.VIEW_AGENDA,
                             label="Board"),
                nav_dest_cls(icon=ft.Icons.RECEIPT_LONG,
                             label="Slip"),
                nav_dest_cls(icon=ft.Icons.LIST, label="Lab"),
                nav_dest_cls(icon=ft.Icons.VIEW_IN_AR,
                             label="3D"),
                nav_dest_cls(icon=ft.Icons.MORE_HORIZ,
                             label="More"),
            ])
    else:  # equivalent switch: a labelled button row
        page.add(ft.Row(spacing=8, wrap=True, controls=[
            ft.OutlinedButton("Board",
                              on_click=lambda _e: show("board")),
            ft.OutlinedButton("Slip",
                              on_click=lambda _e: show("slip")),
            ft.OutlinedButton("Lab",
                              on_click=lambda _e: show("lab")),
            ft.OutlinedButton("3D",
                              on_click=lambda _e: show("stage")),
            ft.OutlinedButton("More",
                              on_click=lambda _e: show("more")),
        ]))

    # offline behaviour: open on the Board on the last pull,
    # stamped with its original pull time (the engine's stamp
    # calls it STALE past its own window) — stale is labelled
    # stale, never freshened.
    # F4 async first render: the shell — header, nav, the board
    # frame and skeleton cards — paints immediately; the
    # pricing pass runs on a worker thread and the real cards
    # stream into the built shell when it lands.
    state["view"] = "board"
    if page.navigation_bar is not None:
        page.navigation_bar.selected_index = 0
    cards_list.controls = skeleton_cards()
    if state["slate"]:
        status.value = "Pricing the last pull…"
    page.update()
    page.run_thread(_boot_worker)


if __name__ == "__main__":
    ft.run(main)
