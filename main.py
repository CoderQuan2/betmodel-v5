#!/usr/bin/env python3
"""
BetFi Xii — the betmodel v5.4 mobile shell (public name:
BetFi_Xii; display name: BetFi Xii; internal id: Bet_Finder —
UNCHANGED from BetFi 11, so on-device storage, snapshots and
the evidence pack carry over; a rename must never orphan the
record).

The ENTIRE app in one file, per the Pilot's 1-script preference:
this shell plus the engine (betmodel5.py, one self-contained
script, byte-identical to the lab's) are the only two Python files
in the repo. Flet requires the entry point to be named main.py —
that is the only reason there are two.

Screens (bottom nav — five destinations through v12; v13.0 adds a sixth, Stocks):
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

v12.0 (2026-10-24) — BetFi Xii (engine v5.4): the app is
renamed (PUBLIC_NAME BetFi_Xii, display "BetFi Xii";
INTERNAL_ID and the storage path are unchanged on purpose).
(1) The Universal Model (engine Organ 8): a registry over
every fit on the device plus per-pull coverage reporting, and
multi-league soccer — Serie A, La Liga, Bundesliga and Ligue 1
fits built from real results (tools/fit_soccer_leagues.py)
price alongside the shipped EPL fit, which keeps first
precedence and its exact numbers. (2) Auto-pull: the menu
pulls itself on start and every 4 minutes while the app is
open (never overlapping a running pull); a failed pull keeps
the last good pull and its STALE / UNVERIFIED stamp — prices
are never invented to fill a gap. (3) Copy mechanic: team and
player NAMES copy individually (a name is what searches);
the slip-label copy stays. (4) Xii Charts on the 3D
destination, above the snapshot instruments: edge distribution,
PRICED vs UNPRICED by sport, and model-vs-implied for the top
priced markets — built from the current pull on every pull,
zoom via + / − / reset buttons (no sliders), tap a bar for
its detail line. (5) The Protected Slip: GOLDEN BET / BET
HERE markets auto-populate a slip panel with engine Kelly
stakes (quarter-Kelly, 5% hard cap, damping printed), total
stake and max loss = total stake printed; the user places it
on FanDuel themselves and marks it placed here — the app
never places a bet and never touches a sportsbook account.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
import sys
import threading
import traceback
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import betmodel5 as b5  # the engine — one script, imported, never copied
import flet as ft

# ------------------------------------------------------------------
# Light sound + haptics (v12.1) — the app's first sense beyond the
# screen, kept LIGHT by law: four tiny stdlib-generated WAVs
# (tools/make_sounds.py), one volume cap for every playback, and
# silence as the only failure mode — every call in this layer is
# wrapped so a missing extension, a dead service or a headless
# harness degrades to nothing happening, never to an error.
#
# Sound route: Flet 1.0.4 core has NO Audio control; the official
# flet-audio extension (pinned in requirements.txt) provides it as
# a Service. The import is defensive — on a build without the
# extension the whole layer disables itself silently.
try:
    import flet_audio as _flet_audio
except Exception:  # extension absent -> sound layer off, silently
    _flet_audio = None

# v12.11: the ImageBoard's drawing engine. Pillow is pinned in
# requirements.txt; the import is still guarded — if it is
# somehow absent on a device build, build_card_safe degrades
# to a minimal text control instead of crashing the board.
try:
    from PIL import Image as _PILImage
    from PIL import ImageDraw as _PILDraw
    from PIL import ImageFont as _PILFont
    _PIL_OK = True
except Exception:  # pragma: no cover - device-build guard
    _PILImage = _PILDraw = _PILFont = None
    _PIL_OK = False

SOUND_VOLUME = 0.30   # hard cap: no Audio control ever sits above
SOUND_FILES = {"tick": "assets/sounds/tick.wav",
               "confirm": "assets/sounds/confirm.wav",
               "golden": "assets/sounds/golden.wav",
               "startup": "assets/sounds/startup.wav"}
_SOUND = {"enabled": True, "controls": {}, "page": None}
_HAPTIC = {"ctrl": None, "page": None}


def _sound_settings_path() -> str:
    return os.path.join(storage_dir(), f"{INTERNAL_ID}-sound.json")


def load_sound_enabled() -> bool:
    """The persisted sound toggle; default ON (a missing or
    unreadable settings file is the default, never an error)."""
    try:
        with open(_sound_settings_path()) as f:
            return bool(json.load(f).get("enabled", True))
    except Exception:
        return True


def set_sound_enabled(on: bool) -> None:
    """Flip the toggle in memory and persist it (same on-device
    JSON pattern as the marked slips). Failures stay silent."""
    _SOUND["enabled"] = bool(on)
    try:
        with open(_sound_settings_path(), "w") as f:
            json.dump({"enabled": bool(on)}, f)
    except Exception:
        pass


def _chosen_sport_path() -> str:
    return os.path.join(storage_dir(),
                        f"{INTERNAL_ID}-sport.json")


def load_chosen_sport() -> str:
    """The persisted scoped-pull sport (v12.3); default SOCCER
    since v12.4 (the Pilot's first-pull default). A missing,
    unreadable or unknown value is the default, never an
    error — the chooser's options are exactly the engine's
    static event types. A sport the user actually picked and
    persisted still wins over the default."""
    try:
        with open(_chosen_sport_path()) as f:
            sport = json.load(f).get("sport")
        if sport in b5.FANDUEL_EVENT_TYPES:
            return sport
    except Exception:
        pass
    return "soccer"


def set_chosen_sport(sport: str) -> str:
    """Persist the chooser's sport (same on-device JSON pattern
    as the sound toggle). Unknown sports normalize to soccer
    (the v12.4 default). Returns the sport actually stored."""
    if sport not in b5.FANDUEL_EVENT_TYPES:
        sport = "soccer"
    try:
        with open(_chosen_sport_path(), "w") as f:
            json.dump({"sport": sport}, f)
    except Exception:
        pass
    return sport


def register_sounds(page) -> None:
    """Register the four Audio services + the haptic service on
    the page (same page.services pattern as UrlLauncher/Clipboard
    below). Called once from main(); any failure leaves the layer
    dark and the app untouched."""
    _SOUND["enabled"] = load_sound_enabled()
    _SOUND["page"] = page
    _HAPTIC["page"] = page
    if _flet_audio is not None:
        for name, src in SOUND_FILES.items():
            try:
                ctrl = _flet_audio.Audio(
                    src=src, autoplay=False, volume=SOUND_VOLUME)
                page.services.append(ctrl)
                _SOUND["controls"][name] = ctrl
            except Exception:
                pass
    try:
        _HAPTIC["ctrl"] = ft.HapticFeedback()
        page.services.append(_HAPTIC["ctrl"])
    except Exception:
        _HAPTIC["ctrl"] = None


def _fire(page, method) -> None:
    """Schedule a Flet service call on the page's task loop.

    Audio.play() and HapticFeedback.light_impact() are COROUTINES
    in Flet 1.0.4: calling them bare builds a coroutine that is
    never awaited, _invoke_method never runs, and the command
    never reaches the device — the layer looks wired and stays
    silent (found 2026-10-25; the 12.1 sound/haptic calls all
    fired this way). page.run_task is the codebase's established
    route for service coroutines (cf. UrlLauncher). With no page
    (headless probes), the coroutine is closed, not leaked."""
    try:
        if page is not None:
            page.run_task(method)
            return
        out = method()
        if asyncio.iscoroutine(out):
            out.close()
    except Exception:
        pass


def play_sound(name: str) -> None:
    """Play one named sound ('tick' / 'confirm' / 'golden' /
    'startup').
    No-ops when the toggle is off, the extension is absent, or
    anything at all goes wrong — silence, never a crash."""
    try:
        if not _SOUND.get("enabled"):
            return
        ctrl = _SOUND["controls"].get(name)
        if ctrl is None:
            return
        _fire(_SOUND.get("page"), ctrl.play)
    except Exception:
        pass


def tap_haptic() -> None:
    """One light haptic tick (Flet 1.0.4's HapticFeedback service,
    light_impact). Guarded like everything in this layer."""
    try:
        ctrl = _HAPTIC.get("ctrl")
        if ctrl is not None:
            _fire(_HAPTIC.get("page"), ctrl.light_impact)
    except Exception:
        pass


def pressify(btn, sound=None, haptic=True):
    """Weighted press for a button (v12.1): Flet 1.0.4 buttons
    expose no press-down/up events, so the weight is a click pulse
    — scale to 0.97 over 110 ms on an ease-out-back settle, then
    restore — plus the layer's tick + haptic. The wrapped handler
    keeps the button's original on_click semantics exactly."""
    inner = btn.on_click

    def _click(e):
        if sound:
            play_sound(sound)
        if haptic:
            tap_haptic()
        try:
            btn.scale = 0.97
            btn.update()
        except Exception:
            pass

        def _restore():
            try:
                btn.scale = 1.0
                btn.update()
            except Exception:
                pass
        try:
            threading.Timer(0.11, _restore).start()
        except Exception:
            _restore()
        if inner is not None:
            inner(e)

    btn.on_click = _click
    try:
        btn.animate_scale = ft.Animation(
            110, ft.AnimationCurve.EASE_OUT_BACK)
    except Exception:
        pass
    return btn

# ------------------------------------------------------------------
# Bet_Finder identity + storage

PUBLIC_NAME = "BetFi_Xii"
INTERNAL_ID = "Bet_Finder"   # BetFi Xii rename law: the
# internal id (and therefore the on-device storage path,
# snapshot filename and engine-data folder) is UNCHANGED from
# BetFi 11 — renaming the app must not orphan the user's data.
APP_VERSION = "13.0.0"
BUILD_NUMBER = 53
DISPLAY_NAME = "BetFi Xii"
# Auto-pull (v12): every 4 minutes while the app is open —
# but ONLY once armed (v12.4): the Pilot's rule is that the
# user starts the first pull, so the loop idles until the
# session's first user-initiated pull action (scoped Pull,
# Pull all, or Price Slate) arms it; see auto_pull_should_tick.
# The loop only starts inside the real ft.run entry path
# (AUTO_PULL_ENABLED is set by the __main__ block), so
# headless harnesses that build the control tree never fire a
# network pull.
AUTO_PULL_INTERVAL_S = 4 * 60
AUTO_PULL_ENABLED = False


def auto_pull_should_tick(armed, busy, last_pull_at, now,
                          interval=AUTO_PULL_INTERVAL_S):
    """The auto-pull gate (v12.4), pure so the harness can pin
    it: a tick is due only when the session has been armed by
    a user-initiated pull, no pull is running, and a full
    interval has passed since the last pull landed."""
    if not armed or busy:
        return False
    return (now - (last_pull_at or 0.0)) >= interval


# Sports whose markets arrive on another sport's FanDuel page
# (the parser's own stamps): loading the host page alone is
# what refreshes them — the only routed pair on the menu.
_ROUTED_SPORT_HOST = {"ncaaf": "nfl"}


def auto_pull_sport(sport_view, chosen):
    """Which sport an AUTO tick loads alone (v12.28, the
    Pilot's 'sport load alone' rule): the sport in front of
    the user when the board is showing one sport alone — a
    routed sport loads its host page, the only page that
    carries it — else the chooser's sport. The full menu is
    never an auto load; it stays the manual Pull all. A
    MANUAL scoped pull always loads the chooser's sport: the
    chooser sits next to the Pull button and names its
    target, while the loop has no button, so it follows the
    user's eyes instead."""
    host = _ROUTED_SPORT_HOST.get(sport_view, sport_view)
    if host in b5.FANDUEL_EVENT_TYPES:
        return host
    return chosen or "nfl"

# ------------------------------------------------------------------
# BetFi Xii ICE design system (v12, from the artist's
# DESIGN-RESCUE.md — "an X-ray of a bet": dark film field, bone
# linework, one cyan glow wherever the model sees something
# real). Glow is a SIGNAL, never decoration: cyan glow only on
# priced/live elements, gold glow only on GOLDEN surfaces, and
# NO glow on UNPRICED or empty states.

BONE = "#EAF8FF"          # primary linework / text (artist: bone)
BONE_DIM = "#CDE8F8"      # secondary linework, axis labels
INK_DIM = "#8FA8C8"       # secondary text (contrast floor)
CYAN_HI = "#7DE0FF"       # glow core highlights
CYAN_DEEP = "#0E3C60"     # keylines under bone strokes
HAIRLINE = "#1E3A5F"      # 1dp borders / chart grid (artist)
PANEL_RAISED_C = "#101E3D"  # elevated surface (artist panelRaised)
XRAY_FILL = "#8C0D2B45"   # panelXray: #0D2B45 @ ~55% alpha
GOLD = "#F5C451"          # GOLDEN only — nowhere else (artist)
GOLD_DEEP = "#2A1F06"     # GOLDEN surface base
ICE = "#38BDF8"           # the X-ray cyan (== ACCENT, named here
#                           for the pulse system)
NUM_FONT = "Roboto Mono"  # tabular figures for new surfaces
#                           (Flet 1.0.4 has no tabular-numerals
#                           toggle; a mono font is the honest
#                           mechanism — 11.0's finding stands)

# Elevation tokens (artist depth law: surface colour + hairline
# first, shadow second; three layers, no more)
ELEV_L0 = None
ELEV_L1 = ft.BoxShadow(blur_radius=12, spread_radius=0,
                       color="#00000059", offset=ft.Offset(0, 4))
ELEV_L2 = [ft.BoxShadow(blur_radius=18, spread_radius=0,
                        color="#00000073", offset=ft.Offset(0, 6)),
           ft.BoxShadow(blur_radius=6, spread_radius=0,
                        color="#1F38BDF8", offset=ft.Offset(0, 1))]
GOLD_GLOW = [ft.BoxShadow(blur_radius=16, spread_radius=0,
                          color="#73F5C451",
                          offset=ft.Offset(0, 4)),
             ft.BoxShadow(blur_radius=6, spread_radius=0,
                          color="#00000059",
                          offset=ft.Offset(0, 2))]
ICE_GLOW = [ft.BoxShadow(blur_radius=14, spread_radius=0,
                         color="#6638BDF8",
                         offset=ft.Offset(0, 3)),
            ft.BoxShadow(blur_radius=5, spread_radius=0,
                         color="#00000059",
                         offset=ft.Offset(0, 2))]

# Gradient washes (Flet 1.0.4 has no backdrop blur; the frosted
# "ice" header is layered translucent gradients instead — real
# mechanism, no invented API)
FIELD_GRADIENT = ft.LinearGradient(
    begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
    colors=["#0A1730", "#060B1A"])
PANEL_GRADIENT = ft.LinearGradient(
    begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
    colors=["#0D1834", "#0B1329"])
FROST_GRADIENT = ft.LinearGradient(
    begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
    colors=["#2938BDF8", "#0D1834", "#2938BDF8"])
GOLD_GRADIENT = ft.LinearGradient(
    begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
    colors=["#3A2A08", GOLD_DEEP])
# v12.1 header texture: the standing palette as a two-stop wash
# (deep field -> panel), for section headers, view titles and
# the 3D panel's segment bar — one family treatment.
HEADER_GRADIENT = ft.LinearGradient(
    begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
    colors=["#060B1A", "#0B1329"])
# The board header band is the one header allowed a breath of
# accent: the cyan at ~12% alpha washing into the panel stop.
BOARD_HEADER_GRADIENT = ft.LinearGradient(
    begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
    colors=["#1F38BDF8", "#0B1329"])
# Market-card shadow (v12.1): one soft layer per card — y2,
# blur 12, black at 25%. GOLDEN cards keep GOLD_GLOW instead;
# the two never stack.
CARD_SHADOW = ft.BoxShadow(blur_radius=12, spread_radius=0,
                           color="#00000040",
                           offset=ft.Offset(0, 2))

# ------------------------------------------------------------------
# Button weights (9c) — a real weight system, named once:
#   PRIMARY   heavy: filled, 48dp+, bold w700, layered shadow —
#             the actions that move the app (Pull, Protected
#             Slip confirm/mark, chart zoom).
#   SECONDARY tonal mid-weight: raised surface fill, 44dp.
#   TERTIARY  text-only, light: navigation-grade actions.

BTN_PRIMARY_HEIGHT = 52    # artist §2: primary 52dp / w700
BTN_SECONDARY_HEIGHT = 48  # secondary 48dp / w600, hairline side


def primary_button(text, on_click, icon=None):
    # Two-layer shadow per artist §2 (black y2/blur6 + cyan glow
    # blur12 @25%): ButtonStyle carries ONE shadow_color, so the
    # cyan glow rides the shadow_color and the black layer rides
    # the material elevation — the closest honest expression in
    # Flet 1.0.4 (no per-button shadow lists exist).
    # v12.1: pressified — every primary action carries the
    # weighted press (scale pulse + tick + light haptic).
    return pressify(ft.Button(
        text, icon=icon, on_click=on_click, height=BTN_PRIMARY_HEIGHT,
        style=ft.ButtonStyle(
            bgcolor=ICE, color="#060B1A", elevation=4,
            shadow_color="#4038BDF8",
            text_style=ft.TextStyle(weight=ft.FontWeight.W_700,
                                    size=15),
            shape=ft.RoundedRectangleBorder(radius=14),
            padding=ft.Padding(left=24, right=24, top=14,
                               bottom=14))),
        sound="tick")


def secondary_button(text, on_click, icon=None):
    return ft.Button(
        text, icon=icon, on_click=on_click,
        height=BTN_SECONDARY_HEIGHT,
        style=ft.ButtonStyle(
            bgcolor=CARD_BG, color=BONE, elevation=1,
            shadow_color="#40000000",
            side=ft.BorderSide(1.5, HAIRLINE),
            text_style=ft.TextStyle(weight=ft.FontWeight.W_600,
                                    size=14),
            shape=ft.RoundedRectangleBorder(radius=14),
            padding=ft.Padding(left=18, right=18, top=12,
                               bottom=12)))


def tertiary_button(text, on_click):
    return ft.TextButton(
        text, on_click=on_click,
        style=ft.ButtonStyle(
            color=ICE,
            text_style=ft.TextStyle(weight=ft.FontWeight.W_600,
                                    size=14)))


# ------------------------------------------------------------------
# Ice pulse machinery (9a/9b) — ONE daemon loop shape for every
# pulse in the app. A loop breathes its targets' opacity on a
# ~1.8 s ease cycle (sinusoidal), touches AT MOST 3 controls,
# and stops permanently when its stop event is set. Loops start
# only in the real entry path (AUTO_PULL_ENABLED); headless
# harnesses never start one.

PULSE_PERIOD_S = 2.0      # the live dot's period (artist §1.2)
PULSE_PERIODS = {"splash": 3.2, "dot": 2.0, "golden": 2.8,
                 "shimmer": 1.5}
_PULSE_TARGETS = {"splash": [], "dot": [], "golden": [],
                  "shimmer": []}
_PULSE_STOPS = {}
_DOT_FRESH = {"fresh": False}   # the live dot's freshness gate
# (artist §1.2): the dot loop runs, but writes nothing while the
# displayed pull is stale — the dot sits frozen at 60% instead.
# v12.7.1 ONE LOCK: every screen mutation + page.update() runs
# inside this single RLock — the daemon pulse ticks, every
# list-mutating render, the nav swap, the workers' trailing
# updates. On device, concurrent updates from pulse threads
# interleaved with a render's bulk child-adds and the client
# dropped the card patches ("client out of sync"); serializing
# every update through one lock makes a torn patch impossible.
# RLock, so a locked render may call locked helpers freely.
_UPDATE_LOCK = threading.RLock()
# v12.10 EVENT-LOOP BATCHED APPLIER. Device evidence
# (build 30's ladder): the one card that paints on the
# Pilot's phone is TEST B — appended alone, after boot, by
# a tap: a single small patch, delivered on the event
# loop. Everything the old render shape shipped (one bulk
# patch from a worker thread, plus a deferred Timer re-ship
# of that same patch) arrives as full-height empty
# containers, while worker value-writes (counts, stamps)
# have always displayed. So the board and the finds now
# render the tap's way: the render computes everything up
# front, then a job — reset, batches of at most 3 controls,
# finish — is applied by the coroutine below, scheduled
# with page.run_task (the event loop), one page.update()
# per step, yielding between batches. A job superseded by
# a newer render (its sequence stamp no longer current)
# aborts before its next step and never touches the
# screen again.


def _chunk3(controls):
    """Chunk an ordered control list into batches of <= 3 —
    the applier's patch size (the tap-sized patch)."""
    return [controls[i:i + 3]
            for i in range(0, len(controls), 3)]


async def _run_apply(job):
    """Apply one render job on the event loop.

    Job keys: page; reset (fn: clear the target list + the
    render's value writes); batches (list of control lists);
    extend (fn(batch): append one batch to the target list);
    finish (fn or None: closing writes — the receipt, pulse
    targets); is_current (fn: False once a newer render has
    been dispatched); status (a Text or None, for error
    surfacing). Every step runs inside _UPDATE_LOCK and
    ships its own page.update(); the sleep(0) between
    batches lets each patch flush before the next is built.
    A failure is printed and written to the status line —
    never swallowed silently, never fatal to the loop."""
    page = job["page"]
    try:
        if not job["is_current"]():
            return
        with _UPDATE_LOCK:
            job["reset"]()
            page.update()
        for batch in job["batches"]:
            with _UPDATE_LOCK:
                if not job["is_current"]():
                    return
                job["extend"](batch)
                page.update()
            await asyncio.sleep(0)
        with _UPDATE_LOCK:
            if not job["is_current"]():
                return
            if job.get("finish") is not None:
                job["finish"]()
            page.update()
    except Exception as ex:  # noqa: BLE001 - surfaced below
        print(f"BetFi Xii: render apply failed: "
              f"{type(ex).__name__}: {ex}")
        try:
            _status = job.get("status")
            if _status is not None:
                with _UPDATE_LOCK:
                    _status.value = (
                        "That render hit a snag "
                        f"({type(ex).__name__}) — the pull "
                        "itself is fine; tap Pull to redraw.")
                    page.update()
        except Exception:
            pass
# Performance budget (artist §5): at most 3 looping animations
# stand at once in this app (dot + golden + splash-or-shimmer —
# splash and shimmer never coexist), under the hard cap of 6.
# Every pulse writes OPACITY ONLY, on a pre-rendered glow layer
# (Flet cannot animate shadow blur), ticking at 120 ms (>= the
# artist's 100 ms floor). Flet 1.0.4 exposes no app-lifecycle
# or battery API, so background/battery pausing cannot be
# wired in this build — the loops are daemon, opacity-only and
# stop the moment their surface leaves the tree.


def _pulse_value(key, elapsed):
    """The opacity a pulse key wants at `elapsed` seconds.
    splash: the §1.1 keyframe envelope for the first 2.4 s
    (ignition .0->.55, swell .55->.35, swell .35->.60, hold .60),
    then the idle breath (period 3.2 s, alpha .25<->.40).
    dot: period 2.0 s, alpha 1.0<->.45. golden: period 2.8 s,
    alpha .35<->.50. shimmer: 1.2 s sweep + 0.3 s flat, peak
    alpha .12 (the sheen layer's own opacity)."""
    import math
    if key == "splash":
        if elapsed < 0.6:
            return 0.55 * (elapsed / 0.6)
        if elapsed < 1.2:
            return 0.55 - 0.20 * ((elapsed - 0.6) / 0.6)
        if elapsed < 1.8:
            return 0.35 + 0.25 * ((elapsed - 1.2) / 0.6)
        if elapsed < 2.4:
            return 0.60
        ph = ((elapsed - 2.4) % 3.2) / 3.2
        return 0.325 + 0.075 * math.sin(ph * 2 * math.pi)
    if key == "dot":
        ph = (elapsed % 2.0) / 2.0
        return 0.725 + 0.275 * math.sin(ph * 2 * math.pi)
    if key == "golden":
        ph = (elapsed % 2.8) / 2.8
        return 0.425 + 0.075 * math.sin(ph * 2 * math.pi)
    if key == "shimmer":
        ph = elapsed % 1.5
        if ph >= 1.2:
            return 0.0
        return 0.12 * math.sin((ph / 1.2) * math.pi)
    return 1.0


def ice_pulse_loop(key):
    """Daemon body: breathe the registered glow-layer targets
    for `key` until its stop event is set. Touches at most 3
    controls per tick (golden: top 3 surfaces; shimmer: the
    registered sheen layers, capped at registration)."""
    import time as _time
    stop = _PULSE_STOPS.setdefault(key, threading.Event())
    t0 = _time.monotonic()
    while not stop.is_set():
        if key == "dot" and not _DOT_FRESH["fresh"]:
            stop.wait(0.25)
            continue
        value = _pulse_value(key, _time.monotonic() - t0)
        limit = 4 if key == "shimmer" else 3
        # v12.7.1 one-lock: the whole tick (every ctrl write +
        # update) runs inside the update lock, so a pulse tick
        # can never interleave with a render's patch.
        with _UPDATE_LOCK:
            for ctrl in list(_PULSE_TARGETS.get(key) or [])[:limit]:
                try:
                    ctrl.opacity = value
                    ctrl.update()
                except Exception:
                    pass
        stop.wait(0.12)


def start_pulse(key):
    if key in _PULSE_STOPS and not _PULSE_STOPS[key].is_set():
        return
    _PULSE_STOPS[key] = threading.Event()
    threading.Thread(target=ice_pulse_loop, args=(key,),
                     daemon=True).start()


def stop_pulse(key):
    ev = _PULSE_STOPS.get(key)
    if ev is not None:
        ev.set()
    _PULSE_TARGETS[key] = []


_SPLASH_PARTS = {}


def build_splash():
    """The startup splash (9a; artist MOTION §1.1, staged up in
    v12.4 — "more pop"): the app emblem (assets/icon.png) at a
    generous size over a PRE-RENDERED glow layer (a
    shadow-carrying container whose OPACITY the standing splash
    pulse breathes — Flet cannot animate shadow blur), the
    "BetFi Xii" wordmark and one soft gold sweep line under it.
    VIEWABILITY CONTRACT (v12.4.1, Pilot order): every element
    is built at its final visible state — the splash is properly
    rendered and viewable from its first painted frame, and no
    element's visibility waits on a staging thread (the pattern
    that hid board cards on device). The only staged motion is
    the emblem's synchronous settle and the breathing glow.
    Pure builder — main() wires it into page.overlay in the
    real entry path only; the splash OVERLAYS the
    already-painted board (it never gates first paint),
    self-resolves within ~1.4 s, resolves early when the first
    pull lands (or on tap), and the pulse stops with it."""
    glow = ft.Container(
        width=170, height=170, border_radius=85,
        shadow=ICE_GLOW, opacity=0.0,
        animate_opacity=ft.Animation(
            120, ft.AnimationCurve.EASE_IN_OUT))
    emblem = ft.Container(
        width=150, height=150, left=10, top=10,
        border_radius=34,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        scale=ft.Scale(scale=0.90),
        animate_scale=ft.Animation(500,
                                   ft.AnimationCurve.EASE_OUT),
        alignment=ft.Alignment(0, 0),
        content=ft.Image(src="assets/icon.png",
                         width=150, height=150,
                         fit=ft.BoxFit.COVER))
    ring = ft.Container(
        width=150, height=150, left=10, top=10,
        border_radius=34,
        border=_border_all(1, CYAN_DEEP))
    wordmark = ft.Row(
        spacing=0, tight=True, opacity=1.0,
        scale=ft.Scale(scale=1.0),
        controls=[
            ft.Text("BetFi ", size=30, color=BONE,
                    weight=ft.FontWeight.W_700),
            ft.Text("Xii", size=30, color=ICE,
                    weight=ft.FontWeight.W_700)])
    sweep = ft.Container(
        width=120, height=3, border_radius=2,
        gradient=GOLD_GRADIENT, opacity=1.0,
        scale=ft.Scale(scale=1.0))
    _PULSE_TARGETS["splash"] = [glow]
    _SPLASH_PARTS["glow"] = glow
    _SPLASH_PARTS["ring"] = ring
    _SPLASH_PARTS["emblem"] = emblem
    _SPLASH_PARTS["wordmark"] = wordmark
    _SPLASH_PARTS["sweep"] = sweep
    return ft.Container(
        bgcolor="#F2060B1A", alignment=ft.Alignment(0, 0),
        animate_opacity=ft.Animation(
            240, ft.AnimationCurve.EASE_IN_OUT),
        content=ft.Column(
            spacing=14, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Stack(width=170, height=170,
                         controls=[glow, emblem, ring]),
                wordmark,
                sweep,
                ft.Text("Pick a sport — your first pull is "
                        "one tap.", size=13, color=INK_DIM),
                ft.Text("Analysis only — never places a bet.",
                        size=11, color=FAINT)]))
ENGINE_VERSION = f"betmodel v{b5.ENGINE_VERSION}"
MENU_SOURCE = "FanDuel sbapi (Michigan) live pull"
# Per pull cycle, the soonest this many slate games also get
# their full per-game menu (all tabs) refreshed from the event
# page into rec["event_menus"] — capped so a cycle stays a
# pull, not a crawl (Pilot addition, R2). The full pull
# harvests synchronously; a scoped (one-sport) pull defers its
# harvest to a background follow-up so the pull itself lands
# on the sport page alone (v12.3 amendment).
EVENT_MENU_CAP = 8
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

SPORT_LABELS = {"nfl": "American football",
                "ncaaf": "College football", "nba": "Basketball",
                "nhl": "Hockey", "mlb": "Baseball", "soccer": "Soccer",
                # Category names are the SPORT's name, not a
                # league's (Pilot order 2026-10-27): the NFL is a
                # league; the sport is American football. League
                # and competition names keep their own names in
                # the league surfaces (league_label, _LEAGUE_TITLES).
                # R2: the rest of FanDuel's menu tree, pulled
                # since engine v5.4 (fix-guy) — labels only;
                # these stamp UNPRICED until fitted.
                "tennis": "Tennis", "mma": "MMA", "golf": "Golf",
                "boxing": "Boxing", "cricket": "Cricket",
                "darts": "Darts", "motorsport": "Motorsport",
                "rugby-union": "Rugby union",
                "rugby-league": "Rugby league",
                "lacrosse": "Lacrosse", "snooker": "Snooker",
                "table-tennis": "Table tennis"}

# BetFi 11's SPORT_LABELS, kept for the card's event line.
# The standing SPORT_LABELS above grew extra sports in v12
# (R2 labels for the wider menu tree) and other surfaces
# read it; the card (11's, now the ImageBoard's row) keeps
# 11's exact lookup for its league label, so its one labels
# read goes through this private copy instead.
_v11_SPORT_LABELS = {"nfl": "American football",
                     "ncaaf": "College football", "nba": "Basketball",
                     "nhl": "Hockey", "mlb": "Baseball",
                     "soccer": "Soccer"}
SPORT_ICONS = {"nfl": ft.Icons.SPORTS_FOOTBALL,
               "ncaaf": ft.Icons.SPORTS_FOOTBALL,
               "nba": ft.Icons.SPORTS_BASKETBALL,
               "nhl": ft.Icons.SPORTS_HOCKEY,
               "mlb": ft.Icons.SPORTS_BASEBALL,
               "soccer": ft.Icons.SPORTS_SOCCER,
               "tennis": ft.Icons.SPORTS_TENNIS,
               "mma": ft.Icons.SPORTS_MMA,
               "golf": ft.Icons.SPORTS_GOLF,
               "cricket": ft.Icons.SPORTS_CRICKET,
               "motorsport": ft.Icons.SPORTS_MOTORSPORTS,
               "rugby-union": ft.Icons.SPORTS_RUGBY,
               "rugby-league": ft.Icons.SPORTS_RUGBY}

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

# Board view filters (v12.4): the old switch wall is gone — the
# board filters through two dropdowns. "Show" is single-select;
# each value maps to exactly the predicate the matching v12
# switch implemented (priced_only / golden_only / quick_only /
# hide_dnb) — combos went away by the Pilot's design call.
SHOW_MODES = [("all", "All markets"),
              ("priced", "Priced only"),
              ("golden", "Golden bets"),
              ("silver", "Silver bets"),
              ("steel", "Steel bets"),
              ("quick", "Quick bets (≤2h)"),
              ("nodnb", "No do-not-bets")]
# The startup defaults (v12.4; Show amended v12.12): nothing
# toggled on, ever — the board opens on All sports with
# Show = All markets, and the scoped-pull chooser opens on
# soccer. (v12.4–v12.11 opened on Show = Golden bets; that
# front door hid every lane without a scored record — the
# record-less soft caps soccer/NBA below GOLDEN BET, so the
# default board showed NFL only. Diagnosis:
# SPORTS-DIAGNOSIS-2026-10-27. Golden bets remains a Show
# filter; the ladder sort still leads with it when a lane
# mints one.)
DEFAULT_SHOW = "all"
DEFAULT_SPORT_VIEW = "all"

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
    """Short hash + size of the running engine, computed from the
    imported module itself. The packaged Android build does not keep
    betmodel5.py beside main.py on disk (the APP_DIR open raised
    FileNotFoundError on-device), so resolve the engine through the
    import system — module file, then spec origin, then source —
    and hash what is actually running. A stale build shows a
    different fingerprint on the Dev screen."""
    try:
        blob = None
        path = getattr(b5, "__file__", None)
        if path and os.path.isfile(path):
            with open(path, "rb") as f:
                blob = f.read()
        if blob is None:
            import importlib.util
            spec = importlib.util.find_spec("betmodel5")
            if (spec is not None and spec.origin
                    and os.path.isfile(spec.origin)):
                with open(spec.origin, "rb") as f:
                    blob = f.read()
        if blob is None:
            import inspect
            blob = inspect.getsource(b5).encode("utf-8")
        return f"sha256 {hashlib.sha256(blob).hexdigest()[:12]}" \
               f" · {len(blob)} bytes"
    except Exception as e:
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
        b5.MLB_FIT_PATH = os.path.join(data, "v5-mlb.json")
        b5.TENNIS_FIT_PATH = os.path.join(data, "v5-tennis.json")
        b5.MMA_FIT_PATH = os.path.join(data, "v5-mma.json")
        b5.CRICKET_FIT_PATH = os.path.join(data, "v5-cricket.json")
        b5.RUGBY_FIT_PATH = os.path.join(data, "v5-rugby.json")
        b5.F1_FIT_PATH = os.path.join(data, "v5-f1.json")
        b5.SOCCER_FIT_PATH = os.path.join(data, "v5-soccer.json")
        b5.SOCCER_LEAGUES_PATH = os.path.join(
            data, "v5-soccer-leagues.json")
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
        # R4 (fix-guy): recurse into the bundled cache — the
        # stripped gamelog cache + athlete index are what let
        # on-device props price beyond the legacy players.
        # Same ownership rule as the top level, one level down:
        # missing files copy; a fresher pack refreshes the
        # cache files it owns (listed as "cache/<fn>" in
        # engine_data_files); cache files the pack does not
        # carry are never touched or deleted.
        cache_src = os.path.join(src, "cache")
        cache_copied = 0
        if os.path.isdir(cache_src):
            cache_dst = os.path.join(dst, "cache")
            os.makedirs(cache_dst, exist_ok=True)
            for fn in sorted(os.listdir(cache_src)):
                if not (fn == "athlete_index.json"
                        or (fn.startswith("gamelog_")
                            and fn.endswith(".json"))):
                    continue
                sp = os.path.join(cache_src, fn)
                if not os.path.isfile(sp):
                    continue
                dp = os.path.join(cache_dst, fn)
                if not os.path.exists(dp) or (
                        fresher
                        and f"cache/{fn}" in pack_files):
                    with open(sp, "rb") as f:
                        blob = f.read()
                    with open(dp, "wb") as f:
                        f.write(blob)
                    cache_copied += 1
        status["cache_files"] = cache_copied
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
            # v12.30: a cached server whose socket no longer
            # answers is not a server — clear it and rebind
            # below instead of handing out a dead port forever
            try:
                import socket
                with socket.create_connection(
                        ("127.0.0.1", _instrument_server["port"]),
                        timeout=0.25):
                    return _instrument_server["port"]
            except OSError:
                try:
                    _instrument_server["httpd"].shutdown()
                except Exception:
                    pass
                _instrument_server["httpd"] = None
                _instrument_server["port"] = None
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


def _fetch_sport_page(sport):
    """Fetch (only) one sport page, with its custom-page merge.

    Network work belongs here so the pages can be fetched in
    parallel; parsing and slate assembly stay in canonical
    order, making the merged market order identical to the
    historical sequential pull. Shared by the full pull and
    the scoped (one-sport) pull — one fetch block, two callers.
    Returns (sport, page, error): page XOR error."""
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
        return sport, page, None
    except Exception as e:
        return sport, None, f"{type(e).__name__}: {e}"


def _sport_entry(sport, page, pulled_at):
    """Parse one fetched sport page into (stats entry, slate).
    The entry carries the pull's own stamp — v12.3 per-sport
    pulled_at, so an accumulated slate can say when EACH sport
    was last pulled. Raises whatever the parser raises; the
    callers stamp the error exactly as the full pull has."""
    slate, inventory, n_games, routed = \
        b5.fd_parse_sport_page(page, sport)
    entry = {"games": n_games, "markets_on_page":
             sum(inventory.values()), "slate_markets": len(slate),
             "routed": routed, "pulled_at": pulled_at}
    return entry, slate


def _soonest_events(markets):
    """The soonest EVENT_MENU_CAP distinct events on a market
    list, as (event_id, market_time) pairs, soonest first —
    the harvest's target selection, shared by the synchronous
    full-pull harvest, the background scoped-pull harvest, and
    the scoped pull's menus_pending marker, so all three name
    exactly the same games."""
    seen = {}
    for m in markets:
        eid = m.get("fd_event_id")
        if eid is not None and eid not in seen:
            seen[eid] = m.get("market_time") or "9999"
    return sorted(seen.items(),
                  key=lambda kv: kv[1])[:EVENT_MENU_CAP]


def _fetch_event_menus(markets, pulled_at):
    """The per-game full-menu harvest over one market list:
    the soonest EVENT_MENU_CAP games, fetched in parallel,
    each stamped with the pull's time; a failed event stamps
    itself, never the pull. Shared by the full pull (over the
    whole slate, synchronously) and the scoped pull's
    BACKGROUND harvest (over one sport's games, after the pull
    itself has landed). The harvest is an inventory (every
    market name on every tab) — Pricing still rides the slate
    + checkers."""
    soonest = _soonest_events(markets)

    def _fetch_one(item):
        eid, _t = item
        try:
            menu = b5.fd_event_menu(eid)
            menu["fetched_at"] = pulled_at
            return eid, menu
        except Exception as e:
            return eid, {"event_id": eid,
                         "error": f"{type(e).__name__}: {e}",
                         "fetched_at": pulled_at}

    menus = {}
    if soonest:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for eid, menu in pool.map(_fetch_one, soonest):
                menus[str(eid)] = menu
    return menus


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
    sports_in_order = list(b5.FANDUEL_EVENT_TYPES)
    with ThreadPoolExecutor(max_workers=8) as pool:
        fetched_pages = list(pool.map(_fetch_sport_page,
                                      sports_in_order))
    for sport, page, fetch_error in fetched_pages:
        if fetch_error is not None:
            rec["sports"][sport] = {
                "error": fetch_error,
                "attempted_at": rec["pulled_at"]}
            continue
        try:
            entry, slate = _sport_entry(sport, page,
                                        rec["pulled_at"])
            rec["sports"][sport] = entry
            markets += slate
        except Exception as e:
            rec["sports"][sport] = {
                "error": f"{type(e).__name__}: {e}",
                "attempted_at": rec["pulled_at"]}
    rec["markets"] = markets
    rec["verified"] = bool(markets)
    # ---- per-game full menus (Pilot addition, R2): the sport
    # pages above carry each game's PRIMARY markets; the full
    # per-game menu (all tabs) lives on the event page. Refresh
    # it here for the soonest games on this slate — capped, so
    # a pull stays a pull: EVENT_MENU_CAP games, soonest first,
    # each stamped with this pull's time.
    rec["event_menus"] = {}
    try:
        rec["event_menus"] = _fetch_event_menus(
            markets, rec["pulled_at"])
    except Exception as e:
        rec["event_menus_error"] = f"{type(e).__name__}: {e}"
    return rec


def pull_menu_sport(sport: str) -> dict:
    """The scoped pull (v12.3, the Pilot's design): fetch ONLY
    one sport's page (+ its custom page where the full pull
    fetches one) and parse it. No app-context tree (the event
    types are static in b5.FANDUEL_EVENT_TYPES), no other
    sport's page — and NO event-menu harvest: the menu fetch
    was ~90% of a scoped pull's wall time, so it runs as a
    background follow-up after the pull lands (see
    merge_menu_harvest and the sport pull worker). The partial
    carries an empty event_menus plus a menus_pending marker
    naming the soonest games whose menus are still to come —
    on the record and on the sport's own stats entry, so a
    snapshot can say the menus are pending, never pretend
    they are here. Returns a partial record for
    merge_sport_pull(); the record's own pulled_at stamps
    this sport alone (and is the token a later harvest must
    match). verified means the page landed and parsed — a
    sport with zero games on the page is a truthful empty,
    verified all the same; a failed fetch stamps
    sports[sport] with the error and verified stays False."""
    if sport not in b5.FANDUEL_EVENT_TYPES:
        raise ValueError(f"unknown sport: {sport!r}")
    ts = datetime.now().astimezone()
    stamp = ts.isoformat(timespec="seconds")
    partial = {"pulled_at": stamp, "source": MENU_SOURCE,
               "verified": False, "sport": sport, "markets": [],
               "sports": {}, "event_menus": {},
               "menus_pending": []}
    _sport, page, fetch_error = _fetch_sport_page(sport)
    if fetch_error is not None:
        partial["sports"][sport] = {"error": fetch_error,
                                    "attempted_at": stamp}
        return partial
    try:
        entry, slate = _sport_entry(sport, page, stamp)
    except Exception as e:
        partial["sports"][sport] = {
            "error": f"{type(e).__name__}: {e}",
            "attempted_at": stamp}
        return partial
    pending = [str(eid) for eid, _t in _soonest_events(slate)]
    entry["menus_pending"] = pending
    partial["sports"][sport] = entry
    partial["markets"] = slate
    partial["verified"] = True
    partial["menus_pending"] = pending
    return partial


def merge_menu_harvest(slate: dict | None, sport: str,
                       menus: dict, token: str) -> dict | None:
    """Merge a BACKGROUND menu harvest into the standing slate
    (v12.3 amendment): the scoped pull lands fast on the sport
    page alone; this follow-up folds in ONLY the per-game
    menus, once they arrive.

    The guard is the token: the harvest was scheduled by the
    pull whose pulled_at is `token`, and it may merge only
    while the sport's slate entry still carries that stamp.
    A newer pull of the same sport supersedes it — the stale
    harvest is dropped whole (returns None) and can never
    overwrite the fresher pull's menus or clear its pending
    marker. Menus for events no longer on the slate are
    dropped too; every other sport's menus and markets are
    untouched, and the sport's pulled_at is NOT freshened —
    each menu carries its own fetched_at."""
    if not slate:
        return None
    sports = slate.get("sports") or {}
    entry = sports.get(sport) or {}
    if entry.get("pulled_at") != token:
        return None
    on_slate = {str(m.get("fd_event_id"))
                for m in slate.get("markets") or []
                if m.get("fd_event_id") is not None}
    fresh = {k: v for k, v in (menus or {}).items()
             if k in on_slate}
    merged = dict(slate)
    all_menus = dict(slate.get("event_menus") or {})
    all_menus.update(fresh)
    merged["event_menus"] = all_menus
    new_entry = dict(entry)
    remaining = [eid for eid in new_entry.get("menus_pending")
                 or [] if eid not in fresh]
    if remaining:
        new_entry["menus_pending"] = remaining
    else:
        new_entry.pop("menus_pending", None)
    new_sports = dict(sports)
    new_sports[sport] = new_entry
    merged["sports"] = new_sports
    return merged


def merge_sport_pull(slate: dict | None, partial: dict) -> dict:
    """Accumulate one sport's partial pull into the standing
    slate (v12.3): the pulled sport's slice is REPLACED, every
    other sport's markets keep their objects and their order,
    and each sport's stats entry keeps its own pulled_at — the
    board never loses a sport it already had, and no sport's
    stamp is ever freshened by another sport's pull.

    The dropped slice is the pulled sport plus whatever the
    page routes to (the parser's own sport stamps: the NFL
    page's markets arrive stamped nfl AND ncaaf) — taken from
    the old entry's routing, the new entry's routing, and the
    partial's market stamps, so a re-pull can never strand a
    stale cross-filed market next to its fresh copy. The new
    markets take the dropped slice's place in the list (the
    board re-sorts for display anyway; Pull order stays
    canonical). A FAILED scoped pull (error entry) destroys
    nothing: the last-good slice and stats stand, with the
    error recorded on the entry as last_error."""
    sport = partial["sport"]
    entry = (partial.get("sports") or {}).get(sport) or {}
    old = slate or {}
    old_sports = old.get("sports") or {}
    if "error" in entry:
        if not old.get("markets") and not old_sports:
            return {"pulled_at": partial["pulled_at"],
                    "source": old.get("source") or MENU_SOURCE,
                    "verified": False, "markets": [],
                    "sports": {sport: dict(entry)},
                    "event_menus": {}}
        sports = dict(old_sports)
        prev = dict(sports.get(sport) or {})
        prev["last_error"] = entry["error"]
        prev["last_attempt_at"] = partial["pulled_at"]
        sports[sport] = prev
        merged = dict(old)
        merged["sports"] = sports
        return merged
    drop = {sport}
    for src_entry in (old_sports.get(sport) or {}, entry):
        routed = src_entry.get("routed") or {}
        if isinstance(routed, dict):
            drop.update(routed.keys())
    drop.update(m.get("sport")
                for m in partial.get("markets") or [])
    drop.discard(None)
    old_markets = old.get("markets") or []
    kept = []
    insert_at = None
    dropped_ids = set()
    for m in old_markets:
        if m.get("sport") in drop:
            if insert_at is None:
                insert_at = len(kept)
            eid = m.get("fd_event_id")
            if eid is not None:
                dropped_ids.add(str(eid))
        else:
            kept.append(m)
    if insert_at is None:
        insert_at = len(kept)
    new_markets = (kept[:insert_at]
                   + list(partial.get("markets") or [])
                   + kept[insert_at:])
    new_ids = {str(m.get("fd_event_id"))
               for m in partial.get("markets") or []
               if m.get("fd_event_id") is not None}
    menus = {k: v for k, v in (old.get("event_menus") or {}).items()
             if k not in dropped_ids | new_ids}
    menus.update(partial.get("event_menus") or {})
    sports = dict(old_sports)
    sports[sport] = entry
    merged = dict(old)
    merged.update({
        "pulled_at": partial["pulled_at"],
        "source": old.get("source") or MENU_SOURCE,
        "verified": bool(new_markets),
        "markets": new_markets,
        "sports": sports,
        "event_menus": menus})
    merged.pop("event_menus_error", None)
    if partial.get("event_menus_error"):
        merged["event_menus_error"] = partial["event_menus_error"]
    return merged


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
# Stocks pull (v13.0) — Nasdaq API, stdlib urllib, the same
# fetch -> raw dict -> pure parse structure as the menu pull.
# Route verified by probe 2026-10-30 (the v13-stocks fill):
# quote/info, historical, and the two-phase option-chain (the
# bare call returns only the nearest expiry group; the
# response's filterlist month buckets give the fromdate/todate
# span whose ranged call returns every expiry group at once).
# Every parsed block carries {source, pulled_at, delay_class}.
# The chain's own embedded lastTrade stamp was observed one
# session stale at probe time — it is kept raw for audit and
# NEVER used as spot; spot is the quote's regular close.

STOCK_UNIVERSE = ["MSTR", "CRM", "META", "AVGO", "SMCI", "BAC"]
NASDAQ_BASE = "https://api.nasdaq.com/api/quote"
NASDAQ_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
NASDAQ_SOURCE = "Nasdaq API"
NASDAQ_MIN_INTERVAL_S = 0.5

_nasdaq_last_call = [0.0]
_nasdaq_lock = threading.Lock()


def _stock_stamp(delay_class: str) -> dict:
    return {"source": NASDAQ_SOURCE,
            "pulled_at": datetime.now().astimezone().isoformat(
                timespec="seconds"),
            "delay_class": delay_class}


def _nasdaq_get(url: str):
    """One paced GET -> parsed JSON. Raises on HTTP/JSON failure."""
    with _nasdaq_lock:
        wait = NASDAQ_MIN_INTERVAL_S - (
            time.monotonic() - _nasdaq_last_call[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={
            "User-Agent": NASDAQ_UA,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
        finally:
            _nasdaq_last_call[0] = time.monotonic()
    return json.loads(body)


def _nasdaq_num(raw):
    """Nasdaq display numbers: '$132.20', '+1.29%', '33,997,225'
    -> float; '--', '', None -> None."""
    if raw is None:
        return None
    s = str(raw).strip().replace("$", "").replace(",", "") \
        .replace("%", "")
    if s in ("", "--", "N/A", "NA", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _nasdaq_int(raw):
    v = _nasdaq_num(raw)
    return None if v is None else int(v)


def parse_nasdaq_quote(raw: dict, sym: str) -> dict:
    """Raw quote/info JSON -> the quote block. Primary (live /
    after-hours) and secondary (regular close) are kept
    separate — they routinely disagree after hours.
    spot_reference is the regular close when present (that is
    the session the option chain's quotes belong to), else the
    primary last sale; the stale chain lastTrade is never spot.
    """
    data = (raw or {}).get("data") or {}
    p = data.get("primaryData") or {}
    s = data.get("secondaryData") or {}

    def block(b):
        return {
            "last": _nasdaq_num(b.get("lastSalePrice")),
            "net_change": _nasdaq_num(b.get("netChange")),
            "pct_change": _nasdaq_num(b.get("percentageChange")),
            "bid": _nasdaq_num(b.get("bidPrice")),
            "ask": _nasdaq_num(b.get("askPrice")),
            "bid_size": _nasdaq_int(b.get("bidSize")),
            "ask_size": _nasdaq_int(b.get("askSize")),
            "volume": _nasdaq_num(b.get("volume")),
            "last_trade_timestamp_raw": b.get("lastTradeTimestamp"),
            "is_realtime": bool(b.get("isRealTime")),
        }

    primary, secondary = block(p), block(s)
    spot = secondary["last"] if secondary["last"] is not None \
        else primary["last"]
    out = _stock_stamp("realtime-claimed")
    out.update({
        "symbol": sym,
        "company_name": data.get("companyName"),
        "exchange": data.get("exchange"),
        "market_status": data.get("marketStatus"),
        "primary": primary,
        "secondary": secondary,
        "spot_reference": spot,
        "spot_reference_basis": "secondary (regular close)"
        if secondary["last"] is not None
        else "primary (last sale)",
    })
    return out


def parse_nasdaq_history(raw: dict, sym: str) -> dict:
    """Raw historical JSON -> ascending daily OHLCV bars."""
    data = (raw or {}).get("data") or {}
    tt = data.get("tradesTable") or {}
    bars = []
    for r in tt.get("rows") or []:
        try:
            iso = datetime.strptime(
                r["date"], "%m/%d/%Y").date().isoformat()
        except (KeyError, ValueError):
            continue
        bars.append({
            "date": iso,
            "open": _nasdaq_num(r.get("open")),
            "high": _nasdaq_num(r.get("high")),
            "low": _nasdaq_num(r.get("low")),
            "close": _nasdaq_num(r.get("close")),
            "volume": _nasdaq_int(r.get("volume")),
        })
    bars.sort(key=lambda b: b["date"])
    out = _stock_stamp("eod")
    out.update({
        "symbol": sym,
        "total_records_reported": data.get("totalRecords"),
        "asof_raw": tt.get("asOf"),
        "n_bars": len(bars),
        "first_date": bars[0]["date"] if bars else None,
        "last_date": bars[-1]["date"] if bars else None,
        "bars": bars,
    })
    return out


def nasdaq_chain_buckets(raw: dict) -> list:
    """Phase 1 of the chain pull: the bare response's month
    buckets ([{label, from, to}]) spanning every listed expiry."""
    bdata = (raw or {}).get("data") or {}
    buckets = []
    for e in ((bdata.get("filterlist") or {}).get("fromdate")
              or {}).get("filter") or []:
        val = e.get("value") or ""
        if "|" in val:
            lo, hi = val.split("|", 1)
            buckets.append({"label": e.get("label"),
                            "from": lo, "to": hi})
    return buckets


def parse_nasdaq_chain(raw: dict, sym: str) -> dict:
    """Phase 2: the ranged response -> expiries with contracts.

    Rows alternate group-header rows (strike null, expirygroup
    'November 6, 2026') and strike rows whose own expiryDate is
    only a short label, so each strike row inherits its ISO
    expiry from the preceding group header.
    """
    fdata = (raw or {}).get("data") or {}
    rows = ((fdata.get("table") or {}).get("rows")) or []

    def side(row, prefix):
        return {
            "last": _nasdaq_num(row.get(f"{prefix}_Last")),
            "change": _nasdaq_num(row.get(f"{prefix}_Change")),
            "bid": _nasdaq_num(row.get(f"{prefix}_Bid")),
            "ask": _nasdaq_num(row.get(f"{prefix}_Ask")),
            "volume": _nasdaq_int(row.get(f"{prefix}_Volume")),
            "open_interest": _nasdaq_int(
                row.get(f"{prefix}_Openinterest")),
        }

    expiries = []
    current = None
    for r in rows:
        if r.get("strike") is None:
            label = r.get("expirygroup")
            if not label:
                continue
            iso = datetime.strptime(
                label, "%B %d, %Y").date().isoformat()
            current = {"expiry": iso, "expiry_label": label,
                       "contracts": []}
            expiries.append(current)
            continue
        if current is None:
            continue
        current["contracts"].append({
            "strike": _nasdaq_num(r.get("strike")),
            "expiry_label_short": r.get("expiryDate"),
            "occ_ref": (r.get("drillDownURL") or "").rsplit("/", 1)[-1]
            or None,
            "call": side(r, "c"),
            "put": side(r, "p"),
        })
    for e in expiries:
        e["contracts"].sort(key=lambda c: c["strike"])
        e["n_strikes"] = len(e["contracts"])
    out = _stock_stamp("delayed")
    out.update({
        "symbol": sym,
        # WART (kept raw for audit, never used as spot): this
        # stamp was one full session stale at probe time.
        "last_trade_raw_STALE": fdata.get("lastTrade"),
        "n_expiries": len(expiries),
        "n_contract_rows": sum(e["n_strikes"] for e in expiries),
        "expiries": expiries,
    })
    return out


def stock_history_fromdate() -> str:
    """One year of daily bars — enough for the RV estimators
    on-device (the exam archive keeps the full history)."""
    return (datetime.now().astimezone().date()
            - timedelta(days=365)).isoformat()


def fetch_stock_bundle(sym: str, fromdate: str) -> dict:
    """fetch -> raw dicts -> parsed bundle {quote, history,
    chain} for one name. Raises on any leg's failure; the
    caller keeps the last good bundle and stamps it STALE."""
    quote = parse_nasdaq_quote(
        _nasdaq_get(f"{NASDAQ_BASE}/{sym}/info?assetclass=stocks"),
        sym)
    history = parse_nasdaq_history(
        _nasdaq_get(f"{NASDAQ_BASE}/{sym}/historical"
                    f"?assetclass=stocks&fromdate={fromdate}"
                    f"&limit=9999"), sym)
    bare = _nasdaq_get(
        f"{NASDAQ_BASE}/{sym}/option-chain?assetclass=stocks")
    buckets = nasdaq_chain_buckets(bare)
    if not buckets:
        raise RuntimeError(f"{sym}: no expiry buckets in chain "
                           f"response")
    lo = min(b["from"] for b in buckets)
    hi = max(b["to"] for b in buckets)
    chain = parse_nasdaq_chain(
        _nasdaq_get(f"{NASDAQ_BASE}/{sym}/option-chain"
                    f"?assetclass=stocks&fromdate={lo}&todate={hi}"),
        sym)
    chain["expiry_buckets_listed"] = buckets
    chain["enumeration"] = {
        "method": "filterlist.fromdate buckets -> single "
                  "ranged call",
        "fromdate": lo, "todate": hi}
    return {"quote": quote, "history": history, "chain": chain}


def stocks_snapshot_path() -> str:
    return os.path.join(storage_dir(), f"{INTERNAL_ID}-stocks.json")


def save_stocks_snapshot(names: dict) -> None:
    try:
        with open(stocks_snapshot_path(), "w") as f:
            json.dump(names, f)
    except Exception:
        pass


def load_stocks_snapshot() -> dict | None:
    try:
        with open(stocks_snapshot_path()) as f:
            names = json.load(f)
        if isinstance(names, dict) and names:
            return names
    except Exception:
        pass
    return None


def _holdings_path() -> str:
    return os.path.join(storage_dir(),
                        f"{INTERNAL_ID}-holdings.json")


def load_holdings() -> dict:
    """User-entered stock positions {sym: {shares, avg_cost}},
    persisted on-device (the chosen-sport JSON pattern). A
    missing or unreadable file is no positions, never an
    error."""
    try:
        with open(_holdings_path()) as f:
            h = json.load(f)
        if isinstance(h, dict):
            return {s: {"shares": float(v.get("shares") or 0),
                        "avg_cost": float(v.get("avg_cost") or 0)}
                    for s, v in h.items()
                    if isinstance(v, dict)}
    except Exception:
        pass
    return {}


def save_holdings(holdings: dict) -> None:
    try:
        with open(_holdings_path(), "w") as f:
            json.dump(holdings, f)
    except Exception:
        pass


# ------------------------------------------------------------------
# Verdict fingerprint cache (v12.2) — a market is repriced only
# when the market itself, the slate context that can affect a
# checker, or a fit/record file changes. This is deliberately
# conservative: the market fingerprint covers the complete market
# record, not a hand-picked subset of fields, so no checker input
# can drift underneath a reused verdict.


def _fit_files_stamp() -> str:
    """A hash of (path, mtime_ns, size) for the engine's fit and
    record files. Explicit *_PATH globals are included as well as
    every JSON file under the engine DATA/CACHE roots, covering
    lane fits, game pools, scorecard/history/phi state, outrights
    and the gamelog cache. A missing path is part of the stamp, so
    a file appearing later invalidates just as a rewrite does."""
    entries = {}

    def add_file(path):
        try:
            st = os.stat(path)
            entries[path] = (st.st_mtime_ns, st.st_size)
        except OSError:
            entries[path] = None

    def walk(root):
        if not root or not os.path.isdir(root):
            return
        for base, _dirs, files in os.walk(root):
            for fn in files:
                if fn.endswith(".json"):
                    add_file(os.path.join(base, fn))

    roots = set()
    for name, value in vars(b5).items():
        if not isinstance(value, str):
            continue
        if name.endswith("_PATH"):
            if os.path.isdir(value):
                roots.add(value)
            else:
                add_file(value)
    for root in (getattr(b5, "DATA", None),
                 getattr(b5, "CACHE", None)):
        if isinstance(root, str):
            roots.add(root)
    for root in sorted(roots):
        walk(root)
    blob = repr(sorted(entries.items())).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _verdict_context_key(slate: dict) -> tuple:
    """The slate-level checker context, reduced to what can alter
    a verdict. A verified pull reuses across pull timestamps (the
    engine only consumes source/degraded state for a verified
    context); an unverified slate keys on its full stamp because
    that stamp is printed into its verdict reasons."""
    ctx = {"pulled_at": slate.get("pulled_at"),
           "source": slate.get("source"),
           "verified": slate.get("verified", True)}
    stamp, degraded = b5.menu_stamp(ctx)
    if ctx.get("verified"):
        return ("verified", ctx.get("source"), bool(degraded))
    return ("unverified", stamp)


def _market_fingerprint(mkt: dict, fit_stamp: str,
                        context_key: tuple) -> str:
    blob = json.dumps(
        {"market": mkt, "fit_stamp": fit_stamp,
         "context": context_key},
        sort_keys=True, separators=(",", ":"), default=repr)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _price_markets_cached(markets: list, slate: dict,
                          previous_cache: dict | None):
    """(verdicts, current_cache) for `markets`, reusing exact
    verdict objects for unchanged fingerprints and applying the
    engine's run_slate central stamping to newly checked markets.
    The returned cache contains only this slate's entries."""
    ctx = {"pulled_at": slate.get("pulled_at"),
           "source": slate.get("source"),
           "verified": slate.get("verified", True)}
    fit_stamp = _fit_files_stamp()
    context_key = _verdict_context_key(slate)
    card = b5.load_scorecard()
    previous_cache = previous_cache or {}
    verdicts = []
    current_cache = {}
    for mkt in markets:
        key = _market_fingerprint(mkt, fit_stamp, context_key)
        v = previous_cache.get(key)
        if v is None:
            v = b5.run_checker(mkt, ctx)
            if v["state"] == "PRICED" and v["p"] is not None:
                lane = b5._lane_for(mkt)
                v["cal_tag"] = b5.calibration_tag(lane, card)
                if mkt.get("price") is not None:
                    v["stance"] = b5.bet_stance(
                        v["p"],
                        (v["p"] - b5.implied_prob(mkt["price"]))
                        * 100,
                        mkt["price"])
        current_cache[key] = v
        verdicts.append(v)
    return verdicts, current_cache


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


# ------------------------------------------------------------------
# Build-52 display mathematics (the BET NOW indicator + THE
# MATHEMATICS depth section). The locked formula sheet is the
# task-force audit's FORMULAS.md; every displayed number
# recomputes from two primitives — the verdict's p and the
# FanDuel price. The verdict's p is the engine's FINAL
# probability: the raw model probability run through the lane's
# fitted calibration map (phi), then ensemble-blended toward the
# market's own implied/no-vig number (FORMULAS §7). It is never
# the raw model probability, and the percentages inside the
# verdict's detail text name the phi-stage number — a different
# number whenever the blend is active — so nothing here reads
# them. Implied probability and decimal odds reuse the engine's
# own functions (§§1-2, identical to the sheet); fair odds (§3)
# and EV per unit (§5) use the sheet's formulas exactly.


def _fair_american(p):
    """Fair ("true") American odds for probability p
    (FORMULAS §3): p >= 0.5 -> -100p/(1-p) (favourite);
    p < 0.5 -> +100(1-p)/p (underdog). None at the degenerate
    ends (p <= 0 or p >= 1), where no finite fair price
    exists."""
    if p is None or p <= 0.0 or p >= 1.0:
        return None
    if p >= 0.5:
        return -100.0 * p / (1.0 - p)
    return 100.0 * (1.0 - p) / p


def _fair_text(p) -> str:
    """The fair price as printed American odds (nearest
    point — the engine's own decimal_to_american rounds the
    same way), or the honest dash at a degenerate end."""
    f = _fair_american(p)
    return f"{f:+.0f}" if f is not None else "—"


def _parse_bankroll(raw):
    """The app's bankroll text -> float or None: the same
    parse the Slip's Kelly block uses (blank or invalid ->
    None, and stakes then print as fractions only)."""
    try:
        return float(raw or "") or None
    except (TypeError, ValueError):
        return None


_AFFIRMATIVE_RUNGS = ("GOLDEN BET", "BET HERE",
                      "RISK BET (BET)")


def bet_now(verdict) -> bool:
    """The BET NOW condition: this bet survives the verdict
    ladder's OWN pessimistic-end test — the ladder basis
    (FORMULAS §8): pess edge = (p_pess - q) * 100 on the
    band's low end, NOT the Kelly advisory's half-edge basis
    (q + half the headline edge), which is positive for every
    positive-headline-edge market including the ladder's own
    do-not-bets (on the reference slate, all 491 of them).

    The engine stamps the basis onto the verdict when it can
    (bet_now / pess_edge_pts) — the stamps win when present.
    On this engine build the stamps are absent and the
    ladder's low end is not recoverable from (p, price) alone
    (§8), so the fallback reads the ladder's own outcome: an
    affirmative rung (GOLDEN BET / BET HERE / RISK BET (BET))
    is reachable only with the pessimistic edge > 0 and no
    hard condition standing (verdict_ladder), and every
    do-not-bet rung stays dark."""
    bn = verdict.get("bet_now")
    if bn is not None:
        return bool(bn)
    pe = verdict.get("pess_edge_pts")
    if pe is not None:
        return pe > 0
    term, _reason = card_verdict(verdict)
    return term in _AFFIRMATIVE_RUNGS


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


def copy_name(name: str) -> str:
    """The v12 copy mechanic: a team or player NAME, alone —
    exactly what a FanDuel (or any) search box wants. Copying
    the whole slip label into a search yields nothing; the name
    is the search key. Returns the string that goes on the
    clipboard (the name, stripped, nothing added)."""
    return (name or "").strip()


def _copy_name(e, name: str):
    _copy_label(e, copy_name(name))


def name_chip(name: str) -> ft.Row:
    """One copyable name: the name itself (tap it or its copy
    icon and JUST the name lands on the clipboard)."""
    return ft.Row(
        spacing=2, tight=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text(name, size=12, color=INK,
                    weight=ft.FontWeight.BOLD),
            ft.IconButton(
                icon=ft.Icons.CONTENT_COPY, icon_size=13,
                icon_color=ACCENT, width=30, height=30,
                tooltip=f"Copy the name '{name}'",
                on_click=lambda e, n=name: _copy_name(e, n))])


def market_names(mkt: dict) -> list:
    """The copyable names a market carries: the player on a
    prop, else both teams (full names as a bettor reads them)."""
    if mkt.get("player"):
        return [mkt["player"]]
    names = []
    for side in ("home", "away"):
        if mkt.get(side):
            names.append(team_name(mkt, side))
    return names


# ------------------------------------------------------------------
# Skeletons (F3/F4): the shell paints these while a pull or the
# first pricing pass is in flight — a shaped placeholder in the
# card's own silhouette instead of a bare spinner or a dead
# screen.


def skeleton_card(shape="C"):
    # v12.11: drawn, like every card surface now — gray bars
    # on CARD_BG at the surface's own ImageBoard geometry
    # (shape "C": the board row; shape "B": the finds
    # ticket), no text. The old widget skeleton's ICE-shimmer
    # sheen layer was a card-internal pulse target; it is
    # gone with the widget card system (the shimmer pulse
    # now has no targets and start_pulse degrades to a
    # no-op, as designed).
    h_dp = _TICKET_DP_H if shape == "B" else _CARD_DP_H
    if not _PIL_OK:
        return ft.Container(bgcolor=CARD_BG, border_radius=14,
                            height=h_dp)
    return ft.Image(src=_skeleton_png(shape), width=_CARD_DP_W,
                    height=h_dp, fit=ft.BoxFit.FILL)


def skeleton_cards(n: int = 3, shape: str = "C") -> list:
    return [skeleton_card(shape) for _ in range(n)]

# ------------------------------------------------------------------
# Shared display pieces: lines, tiles, pills, chips, skeletons


def _line(text: str, size: int = 11, color: str = DIM,
          bold: bool = False) -> ft.Text:
    return ft.Text(text, size=size, color=color,
                   weight=ft.FontWeight.BOLD if bold else None)


def plain_note(text):
    """Engine text, in the app's own words, for user surfaces
    (label standard, 2026-10-24): one status vocabulary, no
    developer language. The engine's own strings stay precise in
    the record; what the phone SHOWS is plain: FAILED-EXAM reads
    as benched on its backtest, file names and tool paths never
    print, and 'checker' is the app's model, not a part name."""
    if not text:
        return text
    t = str(text)
    t = t.replace("FAILED-EXAM",
                  "benched — failed its backtest")
    t = t.replace("no checker registered for",
                  "no model on file for")
    t = t.replace(" — see coverage queue", "")
    t = re.sub(r"\(tools/[^)]*\)", "", t)
    t = re.sub(r"\(betmodel5\.py[^)]*\)", "", t)
    t = re.sub(r"\bv5-[\w.-]+\.json\b", "the fit file", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _border_all(width: float, color: str) -> ft.Border:
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


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


def screen_title(title: str, subtitle: str = "") -> ft.Container:
    # v12.1 texture: the title sits in a thin gradient band
    # (HEADER_GRADIENT + a hairline base) — same family as the
    # section headers and the panel segment bar.
    controls = [ft.Text(title, size=18, color=INK,
                        weight=ft.FontWeight.BOLD)]
    if subtitle:
        controls.append(ft.Text(subtitle, size=11, color=FAINT))
    return ft.Container(
        gradient=HEADER_GRADIENT, border_radius=10,
        border=ft.Border(bottom=ft.BorderSide(1, HAIRLINE)),
        padding=ft.Padding(left=10, right=10, top=8, bottom=8),
        content=ft.Column(spacing=2, tight=True,
                          controls=controls))


def section_header(text: str, color: str = INK) -> ft.Container:
    # v12.1 texture: a banded header — gradient wash, a 3dp
    # accent rule on the left, the label riding on top.
    return ft.Container(
        gradient=HEADER_GRADIENT, border_radius=8,
        padding=ft.Padding(left=8, right=8, top=5, bottom=5),
        content=ft.Row(spacing=8, tight=True, controls=[
            ft.Container(width=3, height=14, bgcolor=color,
                         border_radius=2),
            ft.Text(text, size=14, color=color,
                    weight=ft.FontWeight.BOLD)]))


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
# Shared display pieces + the card-expansion state.

# Which cards currently show their depth: the ImageBoard's
# expansion state (born as Card v2's details toggle in
# v12.5, dormant under the v11 port, live again in v12.11).
# Keyed by FanDuel market id when the menu carried one,
# else (sport, away, home, market, side, player, line) —
# the state survives re-renders because it lives here, not
# on the (rebuilt) controls.
_CARD_DETAILS_OPEN = set()


def _settle_in(page, ctrl, scale_from=0.99, dur=220,
               dy=0.01):
    """The two-update settle (v12.6): the ONLY sanctioned
    entrance motion besides the card rise — set the
    from-state (scale / offset), ship it, set the identity
    state, ship that, both updates synchronous inside the
    calling render/navigation function. The client animates
    between the two shipped states via the animate_scale /
    animate_offset properties; if it doesn't, the control is
    simply AT its identity state. This helper never touches
    a control's opacity and never starts a thread or timer:
    content visibility never depends on it."""
    with _UPDATE_LOCK:
        try:
            ctrl.animate_scale = ft.Animation(
                dur, ft.AnimationCurve.EASE_OUT_CUBIC)
            ctrl.animate_offset = ft.Animation(
                dur, ft.AnimationCurve.EASE_OUT_CUBIC)
            ctrl.scale = ft.Scale(scale_from)
            ctrl.offset = ft.Offset(0, dy)
        except Exception:
            return
        page.update()
        try:
            ctrl.scale = ft.Scale(1.0)
            ctrl.offset = ft.Offset(0, 0)
        except Exception:
            pass
        page.update()


# ------------------------------------------------------------------
# v12.11: THE IMAGEBOARD — cards are drawn pictures. The widget
# card system (BetFi 11's card builder + its depth tiles, ported
# verbatim in v12.8) is DELETED: across builds 20–31 its content
# never painted on the Pilot's phone — containers and gradients
# rendered at full height, children never did, in every design,
# thread and packaging tried. A card is now ONE PNG drawn with
# Pillow, in the two designs the Pilot picked from the rendered
# demos (the mix): Design C odds-board rows on the Board,
# Design B tickets on the finds feed and the Slip parse
# result. Stripe/headline/columns (C) or event/selection/odds
# box (B) and the depth all reach the phone as a single image,
# the one content type with no descendant tree for the client
# to drop. Tapping a card swaps in its expanded drawing (the
# depth sections as drawn text + an action bar); tap position
# comes from the GestureDetector TapEvent's local_position
# (verified in the installed flet 1.0.4 package), so one
# detector carries every action as a zone.
#
# The depth strings are the deleted tiles' strings, factored
# into _depth_sections BEFORE the builder was removed — the
# words did not change, only their medium.

_CARD_W = 1170          # canvas px — 390 dp at the 3x draw scale
_CARD_H = 177           # Design C collapsed row px — 59 dp
_TICKET_H = 408         # Design B collapsed ticket px — 136 dp
_CARD_DP_W = 390
_CARD_DP_H = 59
_TICKET_DP_H = 136
_CARD_FONT_FILES = {
    "regular": "DejaVuSans.ttf",
    "bold": "DejaVuSans-Bold.ttf",
    "mono": "DejaVuSansMono.ttf",
    "mono_bold": "DejaVuSansMono-Bold.ttf"}
_CARD_FONT_FALLBACKS = {
    "regular": "/system/fonts/Roboto-Regular.ttf",
    "bold": "/system/fonts/Roboto-Bold.ttf",
    "mono": "/system/fonts/RobotoMono-Regular.ttf",
    "mono_bold": "/system/fonts/RobotoMono-Bold.ttf"}
_FONT_CACHE = {}
_CARD_ACTION_LABELS = ("COPY LABEL", "SLIP", "COLLAPSE")
_ACTION_BAR_PX = 84     # the expanded action bar's height, px
_CARD_HOOKS = {"refresh": None, "slip": None}
_RENDER_STAMPS = {}     # per-card "card rendered" stamp, cached
                        # so a card's provenance line — and its
                        # PNG bytes — are stable across draws


def bind_card_hooks(refresh=None, slip=None):
    """main() binds the app's own navigation here (the
    bind_clipboard pattern): refresh re-shows the current
    view (a card tap toggles expansion by re-rendering
    through the normal path); slip opens the Slip view,
    whose Protected Slip panel is the app's slip surface."""
    if refresh is not None:
        _CARD_HOOKS["refresh"] = refresh
    if slip is not None:
        _CARD_HOOKS["slip"] = slip


def _card_key(mkt):
    mid = mkt.get("fd_market_id")
    if mid:
        return (mkt.get("sport"), mid)
    return (mkt.get("sport"), mkt.get("away"), mkt.get("home"),
            mkt.get("market"), mkt.get("side"),
            mkt.get("player"), mkt.get("line"))


def _render_stamp(key):
    stamp = _RENDER_STAMPS.get(key)
    if stamp is None:
        stamp = datetime.now().astimezone().isoformat(
            timespec="seconds")
        _RENDER_STAMPS[key] = stamp
    return stamp


def _rgb(hex_color):
    h = (hex_color or "#000000").lstrip("#")
    if len(h) == 8:            # AARRGGBB — alpha dropped
        h = h[2:]
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


_CARD_BG_RGB = _rgb(CARD_BG)
_GOLD_RGB = _rgb(GOLD)
_INK_RGB = _rgb(INK)
_DIM_RGB = _rgb(DIM)
_FAINT_RGB = _rgb(FAINT)
_BORDER_RGB = _rgb(BORDER)
_ACCENT_RGB = _rgb(ACCENT)
_WARN_RGB = _rgb(WARN)
_BAD_RGB = _rgb(BAD)


def _font(kind, size):
    """Font ladder: the bundled DejaVu faces (assets/fonts)
    first, then Android's Roboto, then Pillow's built-in
    default — a card must draw on any device. Cached per
    (kind, size)."""
    key = (kind, size)
    fnt = _FONT_CACHE.get(key)
    if fnt is not None:
        return fnt
    fnt = None
    path = os.path.join(APP_DIR, "assets", "fonts",
                        _CARD_FONT_FILES[kind])
    if not os.path.exists(path):
        path = _CARD_FONT_FALLBACKS.get(kind, "")
    if path and os.path.exists(path):
        try:
            fnt = _PILFont.truetype(path, size)
        except Exception:
            fnt = None
    if fnt is None:
        try:
            fnt = _PILFont.load_default(size)
        except Exception:
            fnt = _PILFont.load_default()
    _FONT_CACHE[key] = fnt
    return fnt


def _textw(d, text, fnt):
    return d.textlength(text, font=fnt)


def _trunc(d, text, fnt, maxw):
    if _textw(d, text, fnt) <= maxw:
        return text
    while text and _textw(d, text + "…", fnt) > maxw:
        text = text[:-1]
    return text.rstrip() + "…"


def _fit(d, text, kind, size, maxw, floor=22):
    """Shrink-to-fit (the demo's fit): step the size down
    until the text fits its pixel budget."""
    while size > floor and \
            _textw(d, text, _font(kind, size)) > maxw:
        size -= 2
    return _font(kind, size)


def _wrap_text(d, text, fnt, maxw):
    words = str(text).split()
    lines, cur = [], ""
    for wd in words:
        nxt = f"{cur} {wd}".strip()
        if cur and _textw(d, nxt, fnt) > maxw:
            lines.append(cur)
            cur = wd
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines or [""]


def _png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _card_facts(mkt, verdict, lane_ctx=None):
    """The card's shared inputs — the deleted builder's head,
    factored once: lane record / phi / calibration from the
    render's precomputed lane context when present, else
    straight from the engine."""
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
    if verdict.get("cal_tag"):
        cal_tag = verdict["cal_tag"]
    term, vreason = card_verdict(verdict)
    return {"lane": lane, "w": w, "l": l, "rec_src": rec_src,
            "phi": phi, "phi_state": phi_state, "uncal": uncal,
            "cal_tag": cal_tag, "p": verdict.get("p"),
            "grade": verdict.get("grade"), "term": term,
            "vreason": vreason,
            "state": verdict.get("state") or "",
            "stance": verdict.get("stance")}


def _mathematics_lines(mkt, verdict, f, edge_pts, bankroll):
    """THE MATHEMATICS (build 52): one card's proof chain, as
    printed depth lines — the engine's final probability
    against FanDuel's price, the ladder-basis pessimistic end,
    and the position (the engine's Kelly advisory, shown
    as-is). Bases are named on the lines themselves: the
    pessimistic end here is the VERDICT LADDER's (§8), the
    stake's sizing basis is kelly_advice's own (§9) and its
    reason lines print verbatim. No defended probability at
    a pulled price -> one honest line, never invented
    numbers."""
    p, price = f["p"], mkt.get("price")
    if p is None:
        return ["no mathematics to show — this market carries "
                "no probability the system can defend "
                f"({f['state'] or 'UNPRICED'}), so there is no "
                "projection to prove and no position to size."]
    if price is None:
        return ["no mathematics to show — the engine priced a "
                "probability for this market, but no FanDuel "
                "price rides with it, so there is no price to "
                "prove the projection against and no position "
                "to size."]
    price = int(price)
    q = b5.implied_prob(price)
    dec = b5.american_to_decimal(price)
    edge = edge_pts if edge_pts is not None else (p - q) * 100
    lines = [
        f"win probability (engine final): {p * 100:.1f}%",
        "the engine's final probability — calibration-mapped "
        "(phi) and blended toward the market's own number; "
        "not the raw model probability",
        f"FanDuel odds: {price:+d} — implied probability "
        f"{q * 100:.1f}% (decimal {dec:.2f})",
        f"true odds at the engine's number: {_fair_text(p)} "
        f"— the fair price, where this bet breaks even"]
    pe = verdict.get("pess_edge_pts")
    if pe is not None:
        p_pess = q + pe / 100.0
        lines += [
            f"pessimistic probability (verdict ladder's "
            f"basis): {p_pess * 100:.1f}% — the band's low "
            f"end the ladder grades survival on",
            f"pessimistic edge: {pe:+.1f} pts · true odds "
            f"at the pessimistic end: {_fair_text(p_pess)} · "
            f"EV at the pessimistic end: "
            f"{p_pess * dec - 1.0:+.3f} per unit"]
    else:
        lines.append(
            "pessimistic end (verdict ladder's basis): the "
            "ladder's low-end number is not carried on this "
            "verdict — the ladder applied it itself, and its "
            "outcome is the rung in the proof below")
    lines.append(
        f"proof: engine {p * 100:.1f}% vs implied "
        f"{q * 100:.1f}% → edge {edge:+.1f} pts → EV "
        f"{p * dec - 1.0:+.3f} per unit → verdict {f['term']}"
        + (f" · grade {f['grade']}" if f["grade"] else ""))
    adv = b5.kelly_advice(p, price, bankroll=bankroll,
                          cal_tag=f["cal_tag"])
    lines.append("position — Kelly advisory (the engine's "
                 "kelly_advice: quarter-Kelly range under a "
                 "5% hard cap; advice only — the app never "
                 "places a bet)")
    if adv["state"] == "UNPRICED":
        lines.append(adv["reasons"][0])
    else:
        stake = (f"advised stake: "
                 f"{adv['stake_frac'] * 100:.2f}%–"
                 f"{adv['stake_frac_hi'] * 100:.2f}% of "
                 f"bankroll ({adv['stake_units']:.1f}u–"
                 f"{adv['stake_units_hi']:.1f}u)")
        if adv["stake_dollars"] is not None:
            stake += (f" = ${adv['stake_dollars']:,.0f}–"
                      f"${adv['stake_dollars_hi']:,.0f} on a "
                      f"${bankroll:,.0f} bankroll")
        else:
            stake += (" — no bankroll set in the app, so "
                      "the stake prints as a fraction of "
                      "bankroll only")
        lines.append(stake)
        lines.extend(adv["reasons"])
    return lines


def _depth_sections(mkt, verdict, rec, quotes_by_game,
                    lane_ctx=None, edge_pts=None, bankroll=None):
    """The card's depth, as data: [(title, [gloss, *lines])]
    — the exact strings the deleted widget tiles carried
    (PRICE ANATOMY / SCALE / COHERENCE / PROVENANCE), gloss
    first in each list, factored out of the old builder
    before it was removed. Build 52 adds THE MATHEMATICS
    (the projection's proof chain + the Kelly-advisory
    position) after PRICE ANATOMY. The expanded drawing
    prints these; nothing else invents card depth text."""
    f = _card_facts(mkt, verdict, lane_ctx)
    w, l = f["w"], f["l"]
    rec_src, phi, phi_state = f["rec_src"], f["phi"], \
        f["phi_state"]
    uncal, cal_tag = f["uncal"], f["cal_tag"]
    p, state, stance = f["p"], f["state"], f["stance"]
    term, vreason = f["term"], f["vreason"]

    key = (mkt.get("sport"), mkt.get("away"), mkt.get("home"))
    quote = quotes_by_game.get(key)
    if quote and any(quote.get(k) is not None for k in
                     ("spread_home", "total", "ml_p_home")):
        flags = b5.coherence_check([quote])
        coh_lines = flags or ["coherent at quoted prices"]
    else:
        coh_lines = ["insufficient quotes in this pull to audit"]

    anatomy = []
    if vreason:
        anatomy.append(f"{term} — {vreason}")
    elif term:
        anatomy.append(f"verdict: {term}")
    if verdict.get("metal"):
        anatomy.append(f"metal tier: {verdict['metal']}")
    anatomy.append(f"state: {state}")
    if stance:
        anatomy.append(f"stance: {stance} — the shape of the "
                       f"bet (Terms); the verdict above decides")
    anatomy.append(f"calibration tag: {cal_tag or '—'}")
    if p is not None:
        anatomy.append(f"model probability (after calibration "
                       f"— see Terms: phi): {p * 100:.1f}%")
    if mkt.get("price") is not None:
        anatomy.append(
            f"pulled price: {int(mkt['price']):+d} "
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
    scale = [
        f"phi: "
        f"{phi.get('kind', '?') if isinstance(phi, dict) else '?'}"
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
                      f"{_render_stamp(_card_key(mkt))}")

    return [
        ("PRICE ANATOMY", ["where the probability came from"]
         + anatomy),
        ("THE MATHEMATICS",
         ["the projection proved with its own numbers — "
          "probability against price, the ladder's "
          "pessimistic end, the position"]
         + _mathematics_lines(mkt, verdict, f, edge_pts,
                              bankroll)),
        ("SCALE",
         ["phi — the fitted map that adjusts this lane's raw "
          "probabilities toward what its record has earned"]
         + scale),
        ("COHERENCE",
         ["do this game's prices agree with each other?"
          if mkt.get("sport") != "soccer" else
          "do this match's prices agree with each other?"]
         + coh_lines),
        ("PROVENANCE",
         ["where every number came from, and when"]
         + provenance)]


def _card_accent_rgb(verdict):
    term, _r = card_verdict(verdict)
    if (verdict.get("state") or "") == "UNPRICED":
        return _rgb(UNPRICED_BORDER)
    if term == "GOLDEN BET":
        return _GOLD_RGB
    return _rgb(VERDICT_COLORS.get(term or "", DIM))


def _row_texts(mkt, verdict, edge_pts=None):
    """The collapsed row's strings (Design C): the headline
    is the SELECTION — what you'd tap on FanDuel — with the
    market title after the em dash (bet_name's fields, the
    names the widget face led with); the event line is
    matchup · start · league, the same meta the face built;
    the ODDS column is the face's price logic shortened to
    its column (soccer: decimal first; else American)."""
    name = bet_name(mkt, verdict)
    bits = [name["matchup"]]
    _dt = _market_dt(mkt)
    if _dt is not None:
        bits.append(_dt.strftime("%a %b %d · %I:%M %p")
                    .replace(" 0", " "))
    bits.append(_v11_SPORT_LABELS.get(
        mkt.get("sport"), (mkt.get("sport") or "?").upper()))
    p = verdict.get("p")
    if mkt.get("price") is None:
        odds = "—"
    elif mkt.get("sport") == "soccer":
        odds = f"{b5.american_to_decimal(int(mkt['price'])):.2f}"
    else:
        odds = f"{int(mkt['price']):+d}"
    return {"name": name,
            "headline": f"{name['selection']} — "
                        f"{name['market']}",
            "event": " · ".join(bits),
            "model": f"{p * 100:.0f}%" if p is not None else "—",
            "odds": odds,
            "edge": (f"{edge_pts:+.1f}"
                     if edge_pts is not None else "—"),
            "grade": verdict.get("grade") or "—"}


def _paint_row(img, mkt, verdict, edge_pts, y0=0):
    """Paint the Design C collapsed row onto img at vertical
    offset y0 (the expanded image reuses it verbatim on top).
    Geometry is the demo's card_c (780x118 at 2x) at 3x."""
    d = _PILDraw.Draw(img)
    term, _vreason = card_verdict(verdict)
    accent = _card_accent_rgb(verdict)
    if term == "GOLDEN BET":
        # design A's golden treatment: a faint gold wash
        # fading down from the row's top edge
        for i in range(60):
            a = int(36 * (1 - i / 60)) / 255.0
            blended = tuple(
                int(_CARD_BG_RGB[c] * (1 - a) + _GOLD_RGB[c] * a)
                for c in range(3))
            d.line([(0, y0 + i), (_CARD_W, y0 + i)], fill=blended)
    d.rounded_rectangle([0, y0, _CARD_W - 1, y0 + _CARD_H - 1],
                        radius=24, outline=_BORDER_RGB, width=3)
    d.rounded_rectangle([0, y0 + 27, 12, y0 + _CARD_H - 27],
                        radius=6, fill=accent)
    texts = _row_texts(mkt, verdict, edge_pts)
    hf = _fit(d, texts["headline"], "bold", 40, 495)
    d.text((42, y0 + 24), _trunc(d, texts["headline"], hf, 495),
           font=hf, fill=_INK_RGB)
    d.text((42, y0 + 84),
           _trunc(d, texts["event"], _font("regular", 28), 495),
           font=_font("regular", 28), fill=_FAINT_RGB)
    d.text((42, y0 + 126),
           _trunc(d, term or "", _font("bold", 28), 400),
           font=_font("bold", 28), fill=accent)
    edge_col = _DIM_RGB
    if edge_pts is not None and edge_pts > 0:
        edge_col = _rgb(EDGE_POS)
    elif edge_pts is not None and edge_pts < 0:
        edge_col = _rgb(EDGE_NEG)
    vf = _font("mono_bold", 39)
    lf = _font("regular", 22)
    for x, lab, val, col in (
            (702, "MODEL", texts["model"], _INK_RGB),
            (876, "ODDS", texts["odds"], _INK_RGB),
            (1035, "EDGE", texts["edge"], edge_col),
            (1134, "GRADE", texts["grade"], accent)):
        d.text((x - _textw(d, val, vf), y0 + 33), val,
               font=vf, fill=col)
        d.text((x - _textw(d, lab, lf), y0 + 87), lab,
               font=lf, fill=_FAINT_RGB)


def _card_png_collapsed(mkt, verdict, edge_pts=None):
    img = _PILImage.new("RGB", (_CARD_W, _CARD_H), _CARD_BG_RGB)
    _paint_row(img, mkt, verdict, edge_pts)
    return _png_bytes(img)


# The two collapsed drawers, named as the Pilot picked them:
# draw_row_c feeds the Board, draw_ticket_b the finds feed
# and the Slip parse result.
draw_row_c = _card_png_collapsed


def _ticket_texts(mkt, verdict, edge_pts=None):
    """The ticket's strings (Design B): the event line is
    matchup · league · start; the huge line is the SELECTION
    (bet_name semantics — what you'd tap on FanDuel); the
    market title + stance sit under it; the odds box value
    is the row's price logic (soccer: decimal first; else
    American); the tag is the verdict term; the bottom
    strip carries MODEL / EDGE / GRADE."""
    name = bet_name(mkt, verdict)
    row = _row_texts(mkt, verdict, edge_pts)
    bits = [name["matchup"],
            _v11_SPORT_LABELS.get(
                mkt.get("sport"),
                (mkt.get("sport") or "?").upper())]
    _dt = _market_dt(mkt)
    if _dt is not None:
        bits.append(_dt.strftime("%a %b %d · %I:%M %p")
                    .replace(" 0", " "))
    stance = verdict.get("stance")
    p = verdict.get("p")
    strip = (f"MODEL {p * 100:.1f}%" if p is not None
             else "MODEL —")
    strip += (f" · EDGE {edge_pts:+.1f} PTS"
              if edge_pts is not None else " · EDGE —")
    strip += f" · GRADE {verdict.get('grade') or '—'}"
    return {"name": name, "event": " · ".join(bits),
            "selection": name["selection"],
            "market_line": name["market"] + (
                f"  ·  {stance}" if stance else ""),
            "odds": row["odds"],
            "tag": card_verdict(verdict)[0] or "",
            "strip": strip}


def _paint_ticket(img, mkt, verdict, edge_pts, y0=0):
    """Paint the Design B ticket onto img at vertical
    offset y0 (the expanded ticket reuses it verbatim on
    top). Geometry is the demo's card_b (780x272 at 2x)
    at 3x. GOLDEN tickets get the gold wash + gold border
    treatment (design A's golden grammar, as on the row)."""
    d = _PILDraw.Draw(img)
    term, _vreason = card_verdict(verdict)
    accent = _card_accent_rgb(verdict)
    golden = term == "GOLDEN BET"
    if golden:
        for i in range(90):
            a = int(36 * (1 - i / 90)) / 255.0
            blended = tuple(
                int(_CARD_BG_RGB[c] * (1 - a) + _GOLD_RGB[c] * a)
                for c in range(3))
            d.line([(0, y0 + i), (_CARD_W, y0 + i)], fill=blended)
    d.rounded_rectangle(
        [2, y0 + 2, _CARD_W - 3, y0 + _TICKET_H - 3], radius=36,
        outline=_GOLD_RGB if golden else _BORDER_RGB, width=3)
    texts = _ticket_texts(mkt, verdict, edge_pts)
    x = 51
    ef = _fit(d, texts["event"], "regular", 32, 1074)
    d.text((x, y0 + 33), _trunc(d, texts["event"], ef, 1074),
           font=ef, fill=_DIM_RGB)
    sf = _fit(d, texts["selection"], "bold", 60, 705)
    d.text((x, y0 + 84), _trunc(d, texts["selection"], sf, 705),
           font=sf, fill=_INK_RGB)
    d.text((x, y0 + 162),
           _trunc(d, texts["market_line"],
                  _font("regular", 34), 705),
           font=_font("regular", 34), fill=_DIM_RGB)
    # the FanDuel odds box, right: raised surface, the price
    # huge, the book's name under it
    bx0, by0, bx1, by1 = 813, y0 + 78, 1125, y0 + 237
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=24,
                        fill=_rgb(RAISED), outline=_BORDER_RGB,
                        width=3)
    of = _font("mono_bold", 69)
    d.text((bx0 + (312 - _textw(d, texts["odds"], of)) / 2,
            by0 + 21), texts["odds"], font=of, fill=_INK_RGB)
    lf2 = _font("regular", 26)
    d.text((bx0 + (312 - _textw(d, "FANDUEL", lf2)) / 2,
            by0 + 108), "FANDUEL", font=lf2, fill=_FAINT_RGB)
    d.line([(x, y0 + 264), (_CARD_W - 45, y0 + 264)],
           fill=_BORDER_RGB, width=3)
    # the verdict tag: a filled pill in the verdict color —
    # accent text on the accent tinted over the card surface
    tf = _font("bold", 33)
    tw = _textw(d, texts["tag"], tf)
    tag_fill = tuple(
        int(_CARD_BG_RGB[c] * (1 - 40 / 255.0)
            + accent[c] * (40 / 255.0)) for c in range(3))
    d.rounded_rectangle([x, y0 + 288, x + tw + 39, y0 + 345],
                        radius=15, fill=tag_fill,
                        outline=accent, width=3)
    d.text((x + 20, y0 + 298), texts["tag"], font=tf,
           fill=accent)
    nf = _fit(d, texts["strip"], "mono_bold", 32, 1074)
    d.text((x, y0 + 360), texts["strip"], font=nf,
           fill=_INK_RGB)


def draw_ticket_b(mkt, verdict, edge_pts=None):
    """Design B collapsed: one ticket PNG (1170x408)."""
    img = _PILImage.new("RGB", (_CARD_W, _TICKET_H),
                        _CARD_BG_RGB)
    _paint_ticket(img, mkt, verdict, edge_pts)
    return _png_bytes(img)


def _expanded_items(mkt, verdict, rec, quotes_by_game,
                    rank=None, edge_pts=None, lane_ctx=None,
                    bankroll=None):
    """The expanded card's text plan, in draw order:
    [(kind, text)] — the face lines the collapsed row
    compresses (find rank, lane record, the engine's
    uncalibrated stamp and note, the FanDuel path), then the
    four depth sections, then the action bar marker. The
    drawer and the line plan both read this list, so what
    the harness reads is what the phone shows."""
    f = _card_facts(mkt, verdict, lane_ctx)
    name = bet_name(mkt, verdict)
    items = []
    if rank is not None:
        items.append(("extra",
                      f"FIND #{rank}"
                      + (f" · edge {edge_pts:+.1f} pts"
                         if edge_pts is not None else "")))
    items.append(("line",
                  f"Win {f['w']} · Lose {f['l']}   "
                  f"({f['lane']} lane record)"))
    if f["uncal"]:
        items.append(("warn", f["uncal"]))
    if verdict.get("note"):
        items.append(("note", verdict["note"]))
    items.append(("fd", f"Find it: {name['fd_path']}"))
    for title, lines in _depth_sections(
            mkt, verdict, rec, quotes_by_game,
            lane_ctx=lane_ctx, edge_pts=edge_pts,
            bankroll=bankroll):
        items.append(("title", title))
        items.append(("gloss", lines[0]))
        for ln in lines[1:]:
            items.append(("body", ln))
    items.append(("actions", ""))
    return items


# expanded text styles: kind -> (font kind, size, color, line px)
_EXP_STYLE = {
    "extra": ("bold", 30, _ACCENT_RGB, 44),
    "line": ("regular", 30, _DIM_RGB, 42),
    "warn": ("bold", 28, _WARN_RGB, 40),
    "note": ("regular", 26, _FAINT_RGB, 38),
    "fd": ("regular", 28, _DIM_RGB, 40),
    "title": ("bold", 36, _ACCENT_RGB, 54),
    "gloss": ("regular", 28, _FAINT_RGB, 40),
    "body": ("regular", 30, _DIM_RGB, 42)}


def _card_png_expanded(mkt, verdict, rec, quotes_by_game,
                       rank=None, edge_pts=None, lane_ctx=None,
                       design="C", bankroll=None):
    """The expanded drawing: the collapsed face on top
    (the Design C row or the Design B ticket, per surface),
    the depth below as drawn text, the action bar last.
    Returns (png_bytes, height_px)."""
    items = _expanded_items(mkt, verdict, rec, quotes_by_game,
                            rank=rank, edge_pts=edge_pts,
                            lane_ctx=lane_ctx, bankroll=bankroll)
    face_h = _TICKET_H if design == "B" else _CARD_H
    scratch = _PILDraw.Draw(_PILImage.new("RGB", (8, 8)))
    height = face_h + 18
    for kind, text in items:
        if kind == "actions":
            height += 20 + _ACTION_BAR_PX + 24
            break
        fk, size, _c, lh = _EXP_STYLE[kind]
        height += lh * len(_wrap_text(
            scratch, text, _font(fk, size), _CARD_W - 84))
        if kind == "title":
            height += 16
    img = _PILImage.new("RGB", (_CARD_W, height), _CARD_BG_RGB)
    # the expanded frame first — the face paints over its
    # top segment with its own border (gold on GOLDEN), so
    # the face's border treatment stays clean
    _PILDraw.Draw(img).rounded_rectangle(
        [0, 0, _CARD_W - 1, height - 1], radius=24,
        outline=_BORDER_RGB, width=3)
    if design == "B":
        _paint_ticket(img, mkt, verdict, edge_pts)
    else:
        _paint_row(img, mkt, verdict, edge_pts)
    d = _PILDraw.Draw(img)
    y = face_h + 18
    for kind, text in items:
        if kind == "actions":
            y += 20
            d.rounded_rectangle(
                [0, y, _CARD_W - 1, y + _ACTION_BAR_PX],
                radius=16, fill=_rgb(RAISED))
            lf = _font("bold", 30)
            third = _CARD_W // 3
            for i, lab in enumerate(_CARD_ACTION_LABELS):
                d.text((third * i
                        + (third - _textw(d, lab, lf)) / 2,
                        y + (_ACTION_BAR_PX - 30) / 2), lab,
                       font=lf, fill=_INK_RGB)
            y += _ACTION_BAR_PX + 24
            break
        fk, size, color, lh = _EXP_STYLE[kind]
        fnt = _font(fk, size)
        for ln in _wrap_text(d, text, fnt, _CARD_W - 84):
            d.text((42, y), ln, font=fnt, fill=color)
            y += lh
        if kind == "title":
            y += 16
    return _png_bytes(img), height


def _card_line_plan(mkt, verdict, rec, quotes_by_game,
                    rank=None, edge_pts=None, lane_ctx=None,
                    design="C", bankroll=None):
    """The expanded card's text lines in draw order (the
    face's lines first, the action labels last) — the
    readable form of the drawing; the harness pins card
    content against this now that no widget tree exists."""
    if design == "B":
        tt = _ticket_texts(mkt, verdict, edge_pts)
        plan = [tt["event"], tt["selection"],
                tt["market_line"], tt["tag"]]
    else:
        texts = _row_texts(mkt, verdict, edge_pts)
        plan = [texts["headline"], texts["event"],
                card_verdict(verdict)[0] or ""]
    plan += [text for kind, text in _expanded_items(
        mkt, verdict, rec, quotes_by_game, rank=rank,
        edge_pts=edge_pts, lane_ctx=lane_ctx, bankroll=bankroll)
        if kind != "actions"]
    plan += list(_CARD_ACTION_LABELS)
    return plan


def _skeleton_png(shape="C"):
    """A drawn skeleton in the surface's own silhouette:
    shape "C" is the board's row (1170x177), shape "B" the
    finds ticket block (1170x408) — gray bars on CARD_BG,
    no text."""
    xray = _rgb(XRAY_FILL)
    if shape == "B":
        img = _PILImage.new("RGB", (_CARD_W, _TICKET_H),
                            _CARD_BG_RGB)
        d = _PILDraw.Draw(img)
        d.rounded_rectangle([2, 2, _CARD_W - 3, _TICKET_H - 3],
                            radius=36, outline=_BORDER_RGB,
                            width=3)
        for (x, y, w, h) in ((51, 33, 600, 36),
                             (51, 90, 660, 64),
                             (51, 168, 420, 30),
                             (51, 288, 240, 57),
                             (51, 360, 800, 32)):
            d.rounded_rectangle([x, y, x + w, y + h], radius=8,
                                fill=xray)
        d.rounded_rectangle([813, 78, 1125, 237], radius=24,
                            fill=xray)
        return _png_bytes(img)
    img = _PILImage.new("RGB", (_CARD_W, _CARD_H), _CARD_BG_RGB)
    d = _PILDraw.Draw(img)
    d.rounded_rectangle([0, 0, _CARD_W - 1, _CARD_H - 1],
                        radius=24, outline=_BORDER_RGB, width=3)
    for (x, y, w, h) in ((42, 28, 540, 44), (42, 88, 780, 34),
                         (900, 28, 228, 44), (42, 134, 330, 24)):
        d.rounded_rectangle([x, y, x + w, y + h], radius=8,
                            fill=xray)
    return _png_bytes(img)


def _header_image(text, color_hex):
    """A group header inside a dynamic list (the board's
    league/date groups, the finds sections), drawn like the
    cards: a short wide PNG — the section title (count
    included by the caller) in the section's color on the
    raised surface, accent rule at the left, no tap. Headers
    outside the dynamic lists stay widgets."""
    if not _PIL_OK:
        return section_header(text, color_hex)
    img = _PILImage.new("RGB", (_CARD_W, 87), _rgb(PAGE_BG))
    d = _PILDraw.Draw(img)
    d.rounded_rectangle([0, 0, _CARD_W - 1, 86], radius=18,
                        fill=_rgb(RAISED))
    d.rounded_rectangle([24, 18, 33, 69], radius=4,
                        fill=_rgb(color_hex))
    fnt = _font("bold", 42)
    d.text((57, 22), _trunc(d, text, fnt, _CARD_W - 99),
           font=fnt, fill=_rgb(color_hex))
    return ft.Image(src=_png_bytes(img), width=_CARD_DP_W,
                    height=29, fit=ft.BoxFit.FILL)


def _card_fallback_png(mkt, verdict, err, design="C"):
    """The drawn fallback (armor kept from v12.4.3): the
    bet's identity + the failure itself, drawn on the
    surface's own silhouette (the row on the Board, the
    ticket block on finds/parse) — a screenshot of a
    failure stays a complete bug report. Deterministic in
    (market, verdict, error type/message, design) so the
    harness can byte-match it."""
    h = _TICKET_H if design == "B" else _CARD_H
    img = _PILImage.new("RGB", (_CARD_W, h), _CARD_BG_RGB)
    d = _PILDraw.Draw(img)
    d.rounded_rectangle([0, 0, _CARD_W - 1, h - 1],
                        radius=24, outline=_WARN_RGB, width=3)
    d.rounded_rectangle([0, 27, 12, h - 27], radius=6,
                        fill=_BAD_RGB)
    try:
        nm = bet_name(mkt, verdict)
        head = f"{nm['selection']} — {nm['market']}"
        match = nm["matchup"]
    except Exception:
        head = (f"{mkt.get('away') or '?'} @ "
                f"{mkt.get('home') or '?'}")
        match = str(mkt.get("name") or mkt.get("market")
                    or "market")
    hf = _font("bold", 36)
    d.text((42, 22), _trunc(d, head, hf, _CARD_W - 84),
           font=hf, fill=_INK_RGB)
    d.text((42, 74),
           _trunc(d, match, _font("regular", 28), _CARD_W - 84),
           font=_font("regular", 28), fill=_DIM_RGB)
    msg = f"card failed to draw — {type(err).__name__}: {err}"
    y = 116
    for ln in _wrap_text(d, msg, _font("regular", 26),
                         _CARD_W - 84)[:2]:
        d.text((42, y), ln, font=_font("regular", 26),
               fill=_WARN_RGB)
        y += 34
    return _png_bytes(img)


def _bet_now_chip():
    """The BET NOW indicator (build 52): a native control
    mounted at the TOP of an expanded card whose bet survives
    the verdict ladder's pessimistic-end test (bet_now()) —
    the render loops place it directly above the card (see
    bet_now_chip_for); the card control itself stays the
    bare GestureDetector every surface enumerates.

    STATIC glow, deliberately: the pulse keys are owned —
    the golden key's target list is assigned wholesale by
    its two owners' render finishes (the Finds glow bar and
    the Protected Slip glow bar), and no registration
    lifecycle exists that an expansion chip could join
    without racing those assignments or the 3-target tick
    cap — so the chip carries the standing static ICE_GLOW
    and no new timer or thread exists for it.

    Accent (cyan) treatment, not gold: the design law
    reserves gold to GOLDEN surfaces (GOLD is "GOLDEN only —
    nowhere else"), while cyan is the glow "wherever the
    model sees something real" — a priced bet the ladder's
    own test survives."""
    return ft.Container(
        width=_CARD_DP_W, padding=10, bgcolor=CYAN_DEEP,
        border=_border_all(1.5, ACCENT), border_radius=10,
        shadow=ICE_GLOW,
        content=ft.Text(
            "● BET NOW — model projects this bet to beat "
            "its price", size=13, color=ACCENT,
            weight=ft.FontWeight.BOLD))


def bet_now_chip_for(mkt, verdict):
    """The BET NOW indicator control for one card, or None:
    it mounts only while the card is expanded (its key sits
    in _CARD_DETAILS_OPEN) and its bet survives the ladder's
    pessimistic-end test. Render loops append it directly
    before the card control, so it rides at the top of the
    expansion and leaves the tree with the collapse
    re-render — no registration, no lifecycle of its own."""
    if _card_key(mkt) in _CARD_DETAILS_OPEN \
            and bet_now(verdict):
        return _bet_now_chip()
    return None


def _card_control(mkt, verdict, rec, quotes_by_game,
                  rank=None, edge_pts=None, lane_ctx=None,
                  design="C", bankroll=None):
    """One card = one drawn image in a GestureDetector.
    Collapsed: the surface's face (the Design C row on the
    Board; the Design B ticket on finds/parse). Expanded
    (the market's key sits in _CARD_DETAILS_OPEN — one
    state shared by both designs; each surface draws its
    own face on top): face + depth + action bar.

    Tap zones read the TapEvent's local_position (dp, origin
    at the control's top-left — flet 1.0.4's TapEvent):
    a collapsed card expands anywhere; an expanded card
    collapses on a body tap, and its action bar's thirds are
    COPY LABEL / SLIP / COLLAPSE — the deleted card's
    affordances in drawn form: the slip-label copy button;
    the Protected Slip (which lives on the Slip view and
    builds itself there — the zone routes through the app's
    own navigation, the same path the bottom nav takes);
    the depth tiles' open state, now the COLLAPSE zone."""
    key = _card_key(mkt)
    name = bet_name(mkt, verdict)
    expanded = key in _CARD_DETAILS_OPEN
    if expanded:
        png, height_px = _card_png_expanded(
            mkt, verdict, rec, quotes_by_game, rank=rank,
            edge_pts=edge_pts, lane_ctx=lane_ctx, design=design,
            bankroll=bankroll)
    elif design == "B":
        png = draw_ticket_b(mkt, verdict, edge_pts)
        height_px = _TICKET_H
    else:
        png = _card_png_collapsed(mkt, verdict, edge_pts)
        height_px = _CARD_H
    height_dp = height_px / 3
    bar_top_dp = (height_px - 24 - _ACTION_BAR_PX) / 3 \
        if expanded else None

    def _on_tap(e, _key=key, _expanded=expanded,
                _bar_top=bar_top_dp,
                _label=name["slip_label"]):
        pos = getattr(e, "local_position", None)
        x = getattr(pos, "x", None)
        y = getattr(pos, "y", None)
        if _expanded:
            if y is not None and _bar_top is not None \
                    and y >= _bar_top:
                if x is not None and x < _CARD_DP_W / 3:
                    _copy_label(e, _label)
                    return
                if x is not None and x < 2 * _CARD_DP_W / 3:
                    hook = _CARD_HOOKS.get("slip")
                    if hook is not None:
                        hook()
                    return
            _CARD_DETAILS_OPEN.discard(_key)
        else:
            _CARD_DETAILS_OPEN.add(_key)
        hook = _CARD_HOOKS.get("refresh")
        if hook is not None:
            hook()

    return ft.GestureDetector(
        content=ft.Image(src=png, width=_CARD_DP_W,
                         height=height_dp, fit=ft.BoxFit.FILL),
        on_tap=_on_tap)


def build_card_safe(mkt: dict, verdict: dict, rec: dict,
                    quotes_by_game: dict, **kw):
    """The render loops' only door to a card (armor kept
    from v12.4.3: one market's failure can never empty the
    board — the count is set from the slate, and a card that
    fails to draw lands as the drawn fallback row carrying
    the error on its face).

    v12.11: the card behind the door is a drawn image (see
    _card_control). The surface picks the design: design="B"
    (the ticket) on the finds feed and the Slip parse
    result, Design C (the odds-board row) everywhere else —
    the default. on_chart / on_toggle are still accepted
    and intentionally ignored, as they were under the old
    adapter — the drawn card's depth is its expansion and
    it carries no Chart affordance. With Pillow itself
    absent the card degrades to a minimal text control —
    build_card_safe never raises."""
    design = kw.get("design", "C")
    if not _PIL_OK:
        try:
            nm = bet_name(mkt, verdict)
            label = f"{nm['selection']} — {nm['market']}"
        except Exception:
            label = "market card"
        return ft.Text(
            f"{label} — image renderer unavailable "
            f"(Pillow missing)", size=12, color=WARN)
    try:
        return _card_control(
            mkt, verdict, rec, quotes_by_game,
            rank=kw.get("rank"), edge_pts=kw.get("edge_pts"),
            lane_ctx=kw.get("lane_ctx"), design=design,
            bankroll=kw.get("bankroll"))
    except Exception as err:
        try:
            return ft.Image(
                src=_card_fallback_png(mkt, verdict, err,
                                       design=design),
                width=_CARD_DP_W,
                height=(_TICKET_DP_H if design == "B"
                        else _CARD_DP_H),
                fit=ft.BoxFit.FILL)
        except Exception:
            return ft.Text(
                f"card failed to draw — "
                f"{type(err).__name__}: {err}",
                size=11, color=WARN)


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
# Xii Charts (v12) — charts built from native Flet controls
# (containers — pinned Flet 1.0.4 core has no chart control and
# flet-charts is not a dependency of this app) from the CURRENT
# pull's
# verdicts, rebuilt on every pull: (a) the edge distribution of
# priced markets, (b) PRICED vs UNPRICED by sport, (c) model
# probability vs implied probability for the top priced markets
# by |edge|. Zoom is a factor the + / − / reset buttons adjust
# (the shell owns the factor; these builders take it as data) —
# no sliders anywhere in this app. Every bar carries its detail
# as a tooltip AND as a labelled tap target under the chart;
# either tap writes the detail line. Zero priced markets render
# an honest empty state — never a fake bar.

EDGE_BUCKETS = [("< −5", None, -5.0), ("−5…−2", -5.0, -2.0),
                ("−2…0", -2.0, 0.0), ("0…+2", 0.0, 2.0),
                ("+2…+5", 2.0, 5.0), ("+5…+8", 5.0, 8.0),
                ("> +8", 8.0, None)]


def chart_market_key(m: dict) -> str:
    """Stable identity for one market in the current pull — used
    by the Charts highlight and the card -> chart cross-link."""
    return "|".join(str(m.get(k) or "") for k in
                    ("sport", "home", "away", "market", "side"))


def xii_chart_data(entries: list) -> dict:
    """The chart facts, computed once from (market, verdict,
    edge) triples — the same triples the Board renders, so the
    charts can never disagree with the cards."""
    priced = [(m, v, e) for m, v, e in entries
              if v.get("state") == "PRICED" and e is not None]
    buckets = []
    for label, lo, hi in EDGE_BUCKETS:
        n = sum(1 for _m, _v, e in priced
                if (lo is None or e >= lo)
                and (hi is None or e < hi))
        buckets.append({"label": label, "count": n})
    by_sport = {}
    for m, v, _e in entries:
        s = m.get("sport") or "?"
        slot = by_sport.setdefault(
            s, {"sport": s, "priced": 0, "unpriced": 0})
        slot["priced" if v.get("state") == "PRICED"
             else "unpriced"] += 1
    top = sorted(priced, key=lambda t: -abs(t[2]))[:40]
    pairs = []
    for m, v, e in top:
        nm = bet_name(m, v)
        pairs.append({
            "label": nm["selection"],
            "key": chart_market_key(m), "sport": m.get("sport"),
            "home": m.get("home"), "away": m.get("away"),
            "model": (v.get("p") or 0) * 100,
            "implied": b5.implied_prob(m["price"]) * 100
            if m.get("price") is not None else 0.0,
            "edge": e, "grade": v.get("grade"),
            "detail": f"{nm['selection']} · {nm['market']} · "
                      f"model {(v.get('p') or 0) * 100:.1f}% vs "
                      f"implied "
                      f"{b5.implied_prob(m['price']) * 100:.1f}% "
                      f"at {int(m['price']):+d} · edge {e:+.1f} "
                      f"pts · grade {v.get('grade') or '—'}"
            if m.get("price") is not None else
            f"{nm['selection']} · edge {e:+.1f} pts"})
    return {"buckets": buckets,
            "by_sport": [by_sport[k] for k in sorted(by_sport)],
            "pairs": pairs, "n_priced": len(priced),
            "n_total": len(entries)}


def _bar_chart(groups, zoom, color, max_v=None, on_tap=None):
    """One bar chart drawn from native Flet containers (the
    pinned Flet 1.0.4 core ships NO chart control — charts moved
    to the separate flet-charts package, which is not in this
    app's requirements; a bar here is a sized Container, which
    keeps the charts dependency-free, serializable and tappable
    on-device). groups: list of {label, rods:[(value, color,
    tooltip)]}. Bars scale with the zoom factor; tapping a bar
    (or its label chip below) writes the detail line."""
    top = max_v or max((r[0] for g in groups for r in g["rods"]),
                       default=0) or 1
    plot_h = 120 * zoom
    cols = []
    for g in groups:
        rods = []
        for val, c, tt in g["rods"]:
            h = max(2.0, (float(val) / float(top)) * plot_h) \
                if val else 2.0
            rods.append(ft.Container(
                width=max(8.0, 14 * zoom), height=h, bgcolor=c,
                border_radius=ft.BorderRadius(
                    top_left=3, top_right=3, bottom_left=0,
                    bottom_right=0),
                tooltip=tt,
                on_click=(lambda e, d=tt: on_tap(d))
                if on_tap is not None else None))
        plot = ft.Container(
            height=plot_h,
            alignment=ft.Alignment(0, 1),
            content=ft.Row(spacing=2, tight=True,
                           vertical_alignment=
                           ft.CrossAxisAlignment.END,
                           controls=rods))
        if g.get("mark"):
            # the highlighted market (card -> chart cross-link):
            # an accent frame around its bars, drawn, not said
            plot = ft.Container(
                content=plot, padding=3, border_radius=6,
                border=_border_all(2, ACCENT))
        cols.append(ft.Column(
            spacing=3, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                plot,
                ft.Text(g["label"], size=9,
                        color=ACCENT if g.get("mark") else DIM,
                        weight=ft.FontWeight.BOLD
                        if g.get("mark") else None)]))
    return ft.Row(spacing=8, tight=False,
                  vertical_alignment=ft.CrossAxisAlignment.END,
                  controls=cols)


def _tap_chips(items, on_tap):
    """Labelled tap targets, one per bar — tapping writes the
    detail line under the chart (the bars carry the same detail
    as tooltips)."""
    if on_tap is None:
        return []
    return [ft.Row(spacing=6, wrap=True, controls=[
        ft.TextButton(
            it["chip"], style=ft.ButtonStyle(color=ACCENT),
            on_click=lambda e, d=it["detail"]: on_tap(d))
        for it in items])]


def build_xii_charts(entries: list, zoom: float = 1.0,
                     on_tap=None, on_zoom=None,
                     detail: str = "", on_point=None,
                     highlight: str = "") -> list:
    """The Xii Charts section controls for one pull's entries.
    Empty pull -> one honest line; a pull with no priced markets
    still draws PRICED vs UNPRICED and prints the empty state
    for the priced-only charts."""
    data = xii_chart_data(entries or [])
    out = [section_header("Xii Charts — this pull, live", ACCENT),
           ft.Text("Built from the current pull's verdicts on "
                   "every pull — the same numbers the cards "
                   "carry. Zoom with the buttons; tap a bar's "
                   "label for its detail.", size=11, color=DIM,
                   height=1.3)]
    if on_zoom is not None:
        # chart zoom is a PRIMARY-weight action (Pilot 9c)
        out.append(ft.Row(spacing=6, controls=[
            primary_button("− Zoom",
                           lambda e: on_zoom(1 / 1.25)),
            secondary_button("Reset", lambda e: on_zoom(0)),
            primary_button("+ Zoom",
                           lambda e: on_zoom(1.25)),
            ft.Text(f"zoom ×{zoom:.2f}", size=11, color=FAINT,
                    font_family=NUM_FONT)]))
    if not entries:
        out.append(ft.Text(
            "No pull yet — pull the menu and the charts build "
            "from it. Nothing is drawn from nothing.",
            size=12, color=DIM, height=1.35))
        return out
    if detail:
        out.append(ft.Text(detail, size=12, color=INK,
                           height=1.35))
    # (a) edge distribution
    out.append(ft.Text("EDGE DISTRIBUTION — priced markets by "
                       "edge (points)", size=12, color=INK,
                       weight=ft.FontWeight.BOLD))
    if data["n_priced"]:
        groups = [{"label": b["label"], "rods": [(
            b["count"],
            EDGE_POS if not b["label"].startswith(("<", "−"))
            else EDGE_NEG,
            f"{b['label']} pts: {b['count']} priced markets")]}
            for b in data["buckets"]]
        out.append(ft.Row(scroll=ft.ScrollMode.AUTO,
                          controls=[_bar_chart(groups, zoom,
                                               EDGE_POS,
                                               on_tap=on_tap)]))
        out += _tap_chips(
            [{"chip": f"{b['label']}: {b['count']}",
              "detail": f"Edge bucket {b['label']} pts — "
                        f"{b['count']} priced markets on this "
                        f"pull"} for b in data["buckets"]],
            on_tap)
    else:
        out.append(ft.Text("No priced markets on this pull — "
                           "no distribution to draw.",
                           size=12, color=DIM))
    # (b) priced vs unpriced by sport
    out.append(ft.Text("PRICED vs UNPRICED — by sport",
                       size=12, color=INK,
                       weight=ft.FontWeight.BOLD))
    groups = [{"label": SPORT_LABELS.get(s["sport"], s["sport"]),
               "rods": [(s["priced"], EDGE_POS,
                         f"{s['sport']}: {s['priced']} priced"),
                        (s["unpriced"], UNPRICED_FG,
                         f"{s['sport']}: {s['unpriced']} "
                         f"unpriced")]}
              for s in data["by_sport"]]
    out.append(ft.Row(scroll=ft.ScrollMode.AUTO,
                      controls=[_bar_chart(groups, zoom,
                                           EDGE_POS,
                                           on_tap=on_tap)]))
    out += _tap_chips(
        [{"chip": f"{SPORT_LABELS.get(s['sport'], s['sport'])} "
                  f"{s['priced']}/{s['priced'] + s['unpriced']}",
          "detail": f"{SPORT_LABELS.get(s['sport'], s['sport'])}"
                    f" — {s['priced']} PRICED · {s['unpriced']} "
                    f"UNPRICED on this pull"}
         for s in data["by_sport"]], on_tap)
    # (c) model vs implied, top priced by |edge|
    out.append(ft.Text("MODEL vs IMPLIED — top priced markets "
                       "by |edge| (model in blue, implied in grey)",
                       size=12, color=INK,
                       weight=ft.FontWeight.BOLD))
    if data["pairs"]:
        groups = [{"label": str(i + 1),
                   "mark": bool(highlight)
                   and p["key"] == highlight,
                   "rods": [
                       (p["model"], ACCENT, p["detail"]),
                       (p["implied"], UNPRICED_FG, p["detail"])]}
                  for i, p in enumerate(data["pairs"])]
        out.append(ft.Row(scroll=ft.ScrollMode.AUTO,
                          controls=[_bar_chart(groups, zoom,
                                               ACCENT,
                                               on_tap=on_tap)]))
        if on_point is not None:
            out.append(ft.Row(spacing=6, wrap=True, controls=[
                ft.TextButton(
                    f"{i + 1}. {p['label']}",
                    style=ft.ButtonStyle(color=ACCENT),
                    on_click=lambda e, pt=p: on_point(pt))
                for i, p in enumerate(data["pairs"])]))
        else:
            out += _tap_chips(
                [{"chip": f"{i + 1}. {p['label']}",
                  "detail": p["detail"]}
                 for i, p in enumerate(data["pairs"])], on_tap)
    else:
        out.append(ft.Text("No priced markets on this pull — "
                           "nothing to compare against the "
                           "market's implied numbers.",
                           size=12, color=DIM))
    # (d) edge landscape — the correlation surface: every priced
    # market as a point in model x implied space (see below)
    out += build_edge_landscape(entries, zoom=zoom,
                                on_tap=on_tap, on_point=on_point)
    return out


# ------------------------------------------------------------------
# Xii panel (v12 panel update) — Coverage, Registry, Edge
# Landscape, slip correlation and the full-screen viewer. All
# builders are pure functions of the current pull / the fitted
# registry, so the harness can drive them without a page; the
# stage closures below only wire taps and state.


_LEAGUE_TITLES = {"epl": "EPL", "nfl": "NFL", "ncaaf": "NCAAF",
                  "nba": "NBA", "nhl": "NHL", "mlb": "MLB",
                  "atp": "ATP", "wta": "WTA", "ufc": "UFC",
                  "f1": "F1", "npc": "NPC", "bbl": "BBL",
                  "wbbl": "WBBL", "ipl": "IPL"}


def league_label(sport, league) -> str:
    """Display name for one (sport, league) pair — the same name
    on Coverage rows, Registry tiles and the Board filter."""
    s = SPORT_LABELS.get(sport, (sport or "?").upper())
    lg = str(league or "")
    if not lg or lg == sport:
        return s
    name = _LEAGUE_TITLES.get(lg) or lg.replace("_", " ").title()
    return f"{s} · {name}"


def board_league_of(mkt: dict):
    """The league a market belongs to, resolved exactly the way
    the engine's coverage resolves it — so a Coverage row, its
    count and the Board filter it opens can never disagree."""
    sport = mkt.get("sport")
    if sport == "cricket":
        lane, _r = b5.cricket_lane_for(
            b5.load_cricket(), mkt.get("competition"),
            mkt.get("home"), mkt.get("away"))
        return lane or "cricket"
    if sport == "rugby-league":
        return b5.rugby_league_lane(mkt.get("competition"),
                                    mkt.get("home"),
                                    mkt.get("away"))
    if sport == "rugby-union":
        return "npc"
    if sport == "soccer":
        _fit, key = b5.soccer_fit_for(mkt.get("home"),
                                      mkt.get("away"))
        if key:
            return key
        blob = b5.load_soccer_leagues()
        hits = set()
        for k, lg in (blob or {}).get("leagues", {}).items():
            st = lg.get("strengths") or {}
            if mkt.get("home") in st or mkt.get("away") in st:
                hits.add(k)
        if len(hits) == 1:
            return hits.pop()
        soc = b5.load_soccer()
        if soc and (mkt.get("home") in soc["strengths"]
                    or mkt.get("away") in soc["strengths"]):
            return "epl"
        return "unresolved"
    return mkt.get("league") or sport or "?"


def market_in_league(mkt: dict, sport, league) -> bool:
    if mkt.get("sport") != sport:
        return False
    if not league or league == sport:
        return True
    return board_league_of(mkt) == league


def coverage_rows(markets) -> list:
    """universal_coverage cells aggregated to (sport, league)
    rows with a priced share — the Coverage graph's data."""
    cells = b5.universal_coverage(markets or [])
    agg, order = {}, []
    for c in cells:
        key = (c.get("sport") or "?", c.get("league") or "?")
        row = agg.get(key)
        if row is None:
            row = agg[key] = {
                "sport": key[0], "league": key[1],
                "label": league_label(*key), "markets": 0,
                "priced": 0, "unpriced": 0, "missing": [],
                "not_pulled": False}
            order.append(key)
        row["markets"] += c.get("markets", 0) or 0
        row["priced"] += c.get("priced_capable", 0) or 0
        row["unpriced"] += c.get("unpriced", 0) or 0
        if c.get("not_pulled"):
            row["not_pulled"] = True
        for txt in c.get("missing") or []:
            p = plain_note(txt)
            if p and p not in row["missing"]:
                row["missing"].append(p)
    rows = [agg[k] for k in order]
    for r in rows:
        r["share"] = (r["priced"] / r["markets"]) \
            if r["markets"] else 0.0
    rows.sort(key=lambda r: (-r["markets"], r["label"]))
    return rows


def build_coverage_section(markets, on_league=None, stamp="",
                           stale=False, on_expand=None) -> list:
    """Priced share per league on the current pull — native
    container bars like the Xii Charts, one tappable row per
    league. The header carries the pull stamp + stale state."""
    out = [section_header("Coverage — priced share by league",
                          ACCENT),
           ft.Text("Every league on this pull, and how much of "
                   "it the model prices. The rest is never "
                   "silent — each unpriced cell names what is "
                   "missing. Tap a league to open its markets "
                   "on the Board.", size=11, color=DIM,
                   height=1.3)]
    if stamp:
        out.append(ft.Text(stamp, size=11,
                           color=GOLD if stale else FAINT,
                           height=1.3))
    if on_expand is not None:
        out.append(ft.Row(spacing=6, controls=[
            secondary_button("Full screen",
                             lambda e: on_expand())]))
    if not markets:
        out.append(ft.Text(
            "No pull yet — pull the menu and coverage builds "
            "from it. Nothing is drawn from nothing.",
            size=12, color=DIM, height=1.35))
        return out
    for r in coverage_rows(markets):
        pct = r["share"] * 100
        body = [ft.Row(spacing=8, wrap=True, controls=[
            ft.Text(r["label"], size=12, color=INK,
                    weight=ft.FontWeight.BOLD),
            ft.Text(f"{r['priced']}/{r['markets']} priced · "
                    f"{pct:.0f}%", size=11, color=DIM,
                    font_family=NUM_FONT)]),
            ft.Container(width=240, height=10, bgcolor=BORDER,
                         border_radius=5, content=ft.Container(
                             width=max(4.0, 240 * r["share"]),
                             height=10, bgcolor=EDGE_POS,
                             border_radius=5))]
        if r["not_pulled"]:
            body.append(ft.Text(
                "Not on the board yet — this league is in the "
                "registry but no pull has carried its markets.",
                size=10, color=FAINT, height=1.3))
        for miss in r["missing"][:2]:
            body.append(ft.Text(miss, size=10, color=FAINT,
                                height=1.3))
        out.append(ft.Container(
            bgcolor=CARD_BG, border=_border_all(1, HAIRLINE),
            border_radius=10, padding=10, margin=ft.Margin(
                left=0, top=0, right=0, bottom=6),
            tooltip=f"Open {r['label']} on the Board",
            on_click=(lambda e, s=r["sport"], l=r["league"]:
                      on_league(s, l))
            if on_league is not None else None,
            content=ft.Column(spacing=5, controls=body)))
    return out


def _backtest_headline(bt) -> str:
    """One honest line from a registry backtest block — Brier
    vs its naive baseline when the block carries one; never an
    invented comparison."""
    if not isinstance(bt, dict) or not bt:
        return ("No backtest block on file — reported as "
                "none, never filled in.")
    n = bt.get("n")
    tail = f" · n={n:,}" if isinstance(n, int) else ""
    if bt.get("brier3") is not None:
        return (f"Walk-forward 3-way Brier "
                f"{bt['brier3']:.4f}{tail}")
    if bt.get("brier") is not None:
        naive = bt.get("naive_brier",
                       bt.get("naive_home_brier"))
        if naive is not None:
            return (f"Walk-forward Brier {bt['brier']:.4f} "
                    f"vs naive {naive:.4f}{tail}")
        return f"Walk-forward Brier {bt['brier']:.4f}{tail}"
    if bt.get("log_loss") is not None:
        naive = bt.get("naive_log_loss")
        if naive is not None:
            return (f"Walk-forward log loss "
                    f"{bt['log_loss']:.4f} vs naive "
                    f"{naive:.4f}{tail}")
        return f"Walk-forward log loss {bt['log_loss']:.4f}{tail}"
    return "Backtest on file (walk-forward)"


def registry_tiles() -> list:
    """One tile per fitted league in the universal registry —
    kind, teams covered, backtest headline, and a status in the
    unified vocabulary (priced / benched / named gap)."""
    tiles = []
    for e in b5.universal_registry():
        vals = [str(v) for v in (e.get("bet_types") or {})
                .values()]
        priced = any(v.startswith("PRICED-capable")
                     for v in vals)
        failed = any("FAILED-EXAM" in v for v in vals)
        if priced and failed:
            status = ("Priced in part — the rest is benched "
                      "or named on Coverage")
        elif priced:
            status = "Priced — markets price off this fit"
        elif failed:
            status = ("Benched — failed its backtest; it does "
                      "not price")
        else:
            status = "Unpriced — named gap (see Coverage)"
        tiles.append({
            "sport": e.get("sport"), "league": e.get("league"),
            "label": league_label(e.get("sport"),
                                  e.get("league")),
            "kind": e.get("kind") or "",
            "covered": e.get("covered"),
            "backtest_text": _backtest_headline(
                e.get("backtest")),
            "status": status,
            "gaps": [plain_note(v) for v in vals
                     if v.startswith("UNPRICED")][:2]})
    return tiles


def build_registry_section(on_league=None, stamp="") -> list:
    """The Registry map: every fitted league as a tile. Tap a
    tile to open that league on the Board."""
    out = [section_header("Registry — every fitted league",
                          ACCENT),
           ft.Text("The fits behind the prices: what kind of "
                   "model each league runs on, how many teams "
                   "it covers, and its walk-forward backtest "
                   "against the naive baseline where one is on "
                   "file. Tap a tile to open the league on the "
                   "Board.", size=11, color=DIM, height=1.3)]
    if stamp:
        out.append(ft.Text(stamp, size=11, color=FAINT,
                           height=1.3))
    for t in registry_tiles():
        body = [ft.Text(t["label"], size=13, color=INK,
                        weight=ft.FontWeight.BOLD),
                ft.Text(f"Fit: {t['kind'] or '—'} · teams "
                        f"covered: {t['covered']}",
                        size=11, color=DIM, height=1.3),
                ft.Text(t["backtest_text"], size=11, color=DIM,
                        height=1.3),
                ft.Text(t["status"], size=11, color=ACCENT,
                        height=1.3)]
        for g in t["gaps"]:
            body.append(ft.Text(g, size=10, color=FAINT,
                                height=1.3))
        out.append(ft.Container(
            bgcolor=CARD_BG, border=_border_all(1, HAIRLINE),
            border_radius=10, padding=10, margin=ft.Margin(
                left=0, top=0, right=0, bottom=6),
            tooltip=f"Open {t['label']} on the Board",
            on_click=(lambda e, s=t["sport"], l=t["league"]:
                      on_league(s, l))
            if on_league is not None else None,
            content=ft.Column(spacing=3, controls=body)))
    return out


EDGE_LANDSCAPE_CAP = 60


def edge_landscape_data(entries, cap=EDGE_LANDSCAPE_CAP) -> dict:
    """Priced markets as points in model x implied space,
    largest |edge| first, capped for the on-device budget —
    the cap is stated, never silent."""
    pts = []
    for m, v, e in entries or []:
        if v.get("state") != "PRICED" or e is None \
                or m.get("price") is None or v.get("p") is None:
            continue
        nm = bet_name(m, v)
        model = v["p"] * 100
        implied = b5.implied_prob(m["price"]) * 100
        where = ("above" if e > 0.05 else "below"
                 if e < -0.05 else "on")
        pts.append({
            "key": chart_market_key(m), "label": nm["selection"],
            "sport": m.get("sport"), "home": m.get("home"),
            "away": m.get("away"), "model": model,
            "implied": implied, "edge": e,
            "grade": v.get("grade"),
            "detail": (f"{nm['selection']} · {nm['market']} · "
                       f"model {model:.1f}% vs implied "
                       f"{implied:.1f}% at {int(m['price']):+d} "
                       f"· edge {e:+.1f} pts — {where} the value "
                       f"diagonal (model = implied)")})
    pts.sort(key=lambda p: -abs(p["edge"]))
    return {"points": pts[:cap], "total": len(pts),
            "capped": len(pts) > cap, "cap": cap}


def build_edge_landscape(entries, zoom: float = 1.0, on_tap=None,
                         on_point=None) -> list:
    """The Edge Landscape: one point per priced market, x =
    the market's implied probability, y = the model's. Points
    above the dotted diagonal are where the model sees more
    than the price implies — the correlation a flat list
    hides. Native containers in a Stack; tap a point (or its
    numbered chip) for the market."""
    out = [ft.Text("EDGE LANDSCAPE — model probability against "
                   "the market's implied probability", size=12,
                   color=INK, weight=ft.FontWeight.BOLD),
           ft.Text("One point per priced market. Above the "
                   "dotted diagonal the model rates the side "
                   "better than its price does; below it, worse. "
                   "Point size grows with |edge|. Tap a point "
                   "for its market.", size=11, color=DIM,
                   height=1.3)]
    data = edge_landscape_data(entries)
    if not data["points"]:
        out.append(ft.Text("No priced markets on this pull — "
                           "no landscape to draw.", size=12,
                           color=DIM))
        return out
    W, H = 330 * zoom, 230 * zoom
    dots = [ft.Container(width=W, height=H,
                         bgcolor=PANEL_RAISED_C,
                         border=_border_all(1, HAIRLINE),
                         border_radius=8)]
    for i in range(21):
        x = i / 20
        dots.append(ft.Container(
            width=3, height=3, bgcolor=FAINT, border_radius=1.5,
            left=x * W - 1, top=(1 - x) * H - 1))
    for p in data["points"]:
        size = 8 + min(6.0, abs(p["edge"]))
        color = EDGE_POS if p["edge"] > 0.5 else EDGE_NEG \
            if p["edge"] < -0.5 else ACCENT
        dots.append(ft.Container(
            width=size, height=size, border_radius=size / 2,
            bgcolor=color, tooltip=p["label"],
            left=p["implied"] / 100 * W - size / 2,
            top=(1 - p["model"] / 100) * H - size / 2,
            on_click=(lambda e, pt=p: on_point(pt))
            if on_point is not None else
            (lambda e, d=p["detail"]: on_tap(d))
            if on_tap is not None else None))
    out.append(ft.Row(scroll=ft.ScrollMode.AUTO, controls=[
        ft.Stack(width=W, height=H, controls=dots)]))
    out.append(ft.Row(spacing=8, controls=[
        ft.Text("model ↑", size=10, color=FAINT),
        ft.Container(expand=True),
        ft.Text("implied →  0% … 100%", size=10, color=FAINT)]))
    if data["capped"]:
        out.append(ft.Text(
            f"Showing the {data['cap']} largest |edge| of "
            f"{data['total']} priced markets (on-device budget "
            f"— the Board carries them all).", size=10,
            color=FAINT, height=1.3))
    if on_point is not None or on_tap is not None:
        out.append(ft.Row(spacing=6, wrap=True, controls=[
            ft.TextButton(
                f"{i + 1}. {p['label']}",
                style=ft.ButtonStyle(color=ACCENT),
                on_click=(lambda e, pt=p: on_point(pt))
                if on_point is not None else
                (lambda e, d=p["detail"]: on_tap(d)))
            for i, p in enumerate(data["points"])]))
    return out


def slip_correlation(legs) -> dict:
    """Group a Protected Slip's legs by what they share: the
    same game first, then a shared team, then the same league.
    What shares nothing stands alone — real diversification."""
    legs = list(legs or [])

    def label(m):
        return bet_name(m)["selection"]

    clusters, used = [], set()
    by_game = {}
    for m in legs:
        by_game.setdefault((m.get("sport"), m.get("home"),
                            m.get("away")), []).append(m)
    for _g, ms in by_game.items():
        if len(ms) >= 2:
            clusters.append({
                "kind": "same game",
                "title": f"Same game — {ms[0].get('away')} at "
                         f"{ms[0].get('home')}",
                "legs": [label(m) for m in ms]})
            used.update(id(m) for m in ms)
    rest = [m for m in legs if id(m) not in used]
    by_team = {}
    for m in rest:
        for t in {m.get("home"), m.get("away")}:
            if t:
                by_team.setdefault((m.get("sport"), t),
                                   []).append(m)
    used2 = set()
    for (_s, t), ms in by_team.items():
        ms = [m for m in ms if id(m) not in used2]
        if len(ms) >= 2:
            clusters.append({"kind": "shared team",
                             "title": f"Shared team — {t}",
                             "legs": [label(m) for m in ms]})
            used2.update(id(m) for m in ms)
    singles = []
    by_sport = {}
    for m in rest:
        if id(m) not in used2:
            by_sport.setdefault(m.get("sport"), []).append(m)
    for s, ms in by_sport.items():
        if len(ms) >= 2:
            clusters.append({
                "kind": "same league",
                "title": f"Same league — "
                         f"{SPORT_LABELS.get(s, (s or '?').upper())}",
                "legs": [label(m) for m in ms]})
        else:
            singles += [label(m) for m in ms]
    return {"clusters": clusters, "singles": singles,
            "n_legs": len(legs),
            "n_clustered": sum(len(c["legs"])
                               for c in clusters)}


_SLIP_CLUSTER_NOTES = {
    "same game": ("Legs that share a game are one bet in "
                  "costumes — a single game can sink every leg "
                  "in this group at once."),
    "shared team": ("The same team carries more than one leg "
                    "— its day decides all of them together."),
    "same league": ("Same league — one slate, one set of "
                    "conditions; results can move together.")}


def build_slip_correlation(cands) -> list:
    """The Protected Slip's correlation view: clustered legs
    as proximity groups with the warning in plain words, and
    the legs that share nothing named as the diversification."""
    legs = [m for m, _v in cands or []]
    out = [section_header(
        "Protected Slip — how the legs hold together", ACCENT),
        ft.Text("Legs that share a game, a team or a league "
                "rise and fall together — correlation the flat "
                "slip list hides. Spread legs are the "
                "diversification.", size=11, color=DIM,
                height=1.3)]
    if not legs:
        return out
    corr = slip_correlation(legs)
    if corr["n_legs"] < 2:
        out.append(ft.Text("One leg — no correlation to draw.",
                           size=12, color=DIM))
        return out
    for c in corr["clusters"]:
        out.append(ft.Container(
            bgcolor=CARD_BG, border=_border_all(1, HAIRLINE),
            border_radius=10, padding=10, margin=ft.Margin(
                left=0, top=0, right=0, bottom=6),
            content=ft.Column(spacing=3, controls=[
                ft.Text(c["title"], size=12, color=INK,
                        weight=ft.FontWeight.BOLD),
                ft.Text(" · ".join(c["legs"]), size=11,
                        color=DIM, height=1.3),
                ft.Text(_SLIP_CLUSTER_NOTES[c["kind"]],
                        size=11, color=WARN, height=1.3)])))
    if corr["singles"]:
        out.append(ft.Text(
            "Standing alone — real diversification: "
            + ", ".join(corr["singles"]), size=11, color=DIM,
            height=1.3))
    if not corr["clusters"]:
        out.append(ft.Text(
            "No two legs share a game, a team or a league — "
            "this slip is spread as wide as this pull allows.",
            size=12, color=DIM, height=1.35))
    return out


def viewer_zoom_clamp(z) -> float:
    """The full-screen viewer's zoom law: 1x to 6x, always."""
    try:
        z = float(z)
    except (TypeError, ValueError):
        return 1.0
    return min(6.0, max(1.0, z))


def build_viewer_sheet(title, stamp, zoom, body, on_zoom=None,
                       on_close=None, detail="") -> ft.Container:
    """The full-screen graph viewer: a sheet whose plotting
    area sits in an InteractiveViewer (native pinch + pan on
    Flet 1.0.4) with button zoom rebuilding the body at the
    shell zoom factor — buttons and pinch agree through the
    same clamp. The detail line is the crosshair readout."""
    controls = [ft.Row(spacing=8, wrap=True,
                       vertical_alignment=
                       ft.CrossAxisAlignment.CENTER, controls=[
                           ft.Text(title, size=14, color=INK,
                                   weight=ft.FontWeight.BOLD),
                           ft.Text(stamp, size=11, color=FAINT),
                           ft.IconButton(
                               ft.Icons.CLOSE,
                               icon_color=DIM,
                               tooltip="Close the viewer",
                               on_click=on_close)])]
    if on_zoom is not None:
        controls.append(ft.Row(spacing=6, controls=[
            secondary_button("− Zoom",
                             lambda e: on_zoom(1 / 1.25)),
            secondary_button("Reset",
                             lambda e: on_zoom(0)),
            secondary_button("+ Zoom",
                             lambda e: on_zoom(1.25)),
            ft.Text(f"zoom ×{zoom:.2f}", size=11, color=FAINT,
                    font_family=NUM_FONT)]))
    if detail:
        controls.append(ft.Text(detail, size=12, color=INK,
                                height=1.35))
    controls.append(ft.InteractiveViewer(
        content=ft.Column(spacing=8, controls=list(body)),
        min_scale=1.0, max_scale=6.0, pan_enabled=True,
        scale_enabled=True, height=520))
    return ft.Container(
        bgcolor=CARD_BG, border=_border_all(1, HAIRLINE),
        border_radius=12, padding=12, margin=8,
        content=ft.Column(spacing=8, controls=controls))


# ------------------------------------------------------------------
# Marked slips (v12) — the user's own placement marks for the
# Protected Slip. Device-local JSON beside the snapshot; a slip
# is written ONLY when the user taps "Mark placed on FanDuel"
# (after the confirm step) — never before, never by the app on
# its own. The app places nothing; this file is the user's
# record of what THEY placed.

def marked_slips_path() -> str:
    return os.path.join(storage_dir(),
                        f"{INTERNAL_ID}-marked-slips.json")


def load_marked_slips() -> list:
    try:
        with open(marked_slips_path()) as f:
            slips = json.load(f)
        return slips if isinstance(slips, list) else []
    except Exception:
        return []


def append_marked_slip(slip: dict) -> list:
    slips = load_marked_slips()
    slips.append(slip)
    try:
        with open(marked_slips_path(), "w") as f:
            json.dump(slips, f, indent=1)
    except Exception:
        pass
    return slips


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
    page.padding = 16   # artist spacing grid: screen padding 16dp
    page.spacing = 8
    page.scroll = ft.ScrollMode.AUTO
    # v12.1 feel layer: sound + haptic services register first,
    # so every handler below can fire them from the first tap.
    register_sounds(page)

    state = {"slate": load_snapshot(), "verdicts": None,
             "verdict_cache": {},
             "sort": "verdict", "card_limit": CARD_PAGE, "search": "",
             # v12.4 board filters: two dropdown values, no
             # switches. Startup is the clean state — sport
             # view on All sports, Show on All markets (the
             # v12.12 front door: the whole slate; Golden
             # bets is a filter, not the entrance).
             "sport_view": DEFAULT_SPORT_VIEW,
             "show": DEFAULT_SHOW,
             "pull_armed": False,
             "parlay_legs": [], "view": "board",
             "board_seg": "all", "slip_seg": "parse",
             "instrument_url": None, "animate_next": False,
             "apply_seq": 0,
             "bankroll": "",
             "chart_zoom": 1.0, "chart_detail": "",
             "pull_busy": False, "last_pull_at": 0.0,
             "chosen_sport": load_chosen_sport(),
             "golden_count": 0,
             "protected_confirm": False,
             # Xii panel state (v12 panel update): the active
             # segment, the highlighted market, the pending
             # "show on Board" point, the Board league filter,
             # the one-level return, and the full-screen viewer
             # — segment, zoom and detail all survive pulls.
             "panel_segment": "charts", "chart_highlight": "",
             "chart_board": None, "league_filter": None,
             "nav_return": None, "viewer_kind": None,
             "viewer_zoom": 1.0, "viewer_detail": "",
             # v13.0 Stocks destination: the pulled name
             # bundles ({sym: {quote, history, chain}}), the
             # active segment / name / expiry, the pull flag
             # and note, and the user-entered holdings
             # (persisted on-device; see load_holdings).
             "stocks": load_stocks_snapshot(),
             "stocks_seg": "tape", "stocks_sym": "MSTR",
             "stocks_expiry": None, "stocks_busy": False,
             "stocks_note": "",
             "holdings": load_holdings()}
    stamp_text, degraded = stamp_of(state["slate"])
    stamp_ctrl = ft.Text(f"Menu: {stamp_text}", size=12,
                         color=WARN if degraded else DIM,
                         expand=True,
                         overflow=ft.TextOverflow.ELLIPSIS)
    status = ft.Text("", size=12, color=ACCENT)
    # the live-pull dot (9b; artist §1.2): 8dp cyan circle with
    # a bone ring and a static pre-rendered ice halo; the dot
    # pulse breathes its OPACITY on a 2000 ms cycle — and only
    # while the displayed pull is fresh (< 4 min, the auto-pull
    # cadence). Stale: frozen at 60%, halo off, gold suffix.
    pull_dot = ft.Container(
        width=8, height=8, border_radius=4, bgcolor=ICE,
        border=_border_all(1, BONE), shadow=ICE_GLOW,
        opacity=1.0, animate_opacity=ft.Animation(
            120, ft.AnimationCurve.EASE_IN_OUT))
    _PULSE_TARGETS["dot"] = [pull_dot]
    stale_ctrl = ft.Text("", size=11, color=GOLD,
                         weight=ft.FontWeight.BOLD)

    # view containers — the destinations (v10.4.1 nav; Stocks added v13.0):
    # Board (cards + finds behind a segment), Slip (Parse /
    # Parlay / Solver behind a segment), Lab, the 3D shelf,
    # More — plus the More sub-views (Terms / Equations / Dev).
    cards_view = ft.Column(spacing=8)
    betfi_view = ft.Column(spacing=8)
    board_view = ft.Column(spacing=8)
    parse_view = ft.Column(spacing=8)
    parlay_view = ft.Column(spacing=8)
    solver_view = ft.Column(spacing=8)
    protected_view = ft.Column(spacing=8)
    slip_view = ft.Column(spacing=8)
    record_view = ft.Column(spacing=8)
    stage_view = ft.Column(spacing=8)
    more_view = ft.Column(spacing=8)
    terms_view = ft.Column(spacing=8)
    equations_view = ft.Column(spacing=8)
    dev_view = ft.Column(spacing=8)
    stocks_view = ft.Column(spacing=8)
    views = {"board": board_view, "slip": slip_view,
             "lab": record_view, "stage": stage_view,
             "more": more_view, "terms": terms_view,
             "equations": equations_view, "dev": dev_view,
             "stocks": stocks_view}
    # v13.0: Stocks joins as a sixth destination, appended so
    # the five standing indices (0-4) never move.
    TOP_VIEWS = ["board", "slip", "lab", "stage", "more",
                 "stocks"]

    def _switcher(content):
        # v12.1 weighted switch: 260 ms ease-in-out-cubic both
        # ways — a view change you can feel arrive, not a cut.
        return ft.AnimatedSwitcher(
            content=content, duration=260,
            transition=ft.AnimatedSwitcherTransition.FADE,
            switch_in_curve=ft.AnimationCurve.EASE_IN_OUT_CUBIC,
            switch_out_curve=ft.AnimationCurve.EASE_IN_OUT_CUBIC)

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
        with _UPDATE_LOCK:
            state["board_seg"] = seg
            board_seg_ctrl.selected = [seg]
            finds = seg == "finds"
            board_switcher.content = betfi_view if finds \
                else cards_view
            if finds:
                render_betfi()
            else:
                render_cards()
            # v12.6 segment transition: the incoming segment
            # settles in (two-update, scale/offset only).
            _settle_in(page, board_switcher.content)
            page.update()

    def on_board_seg(e):
        sel = e.control.selected or []
        show_board_segment(next(iter(sel)) if sel else "all")

    board_seg_ctrl = _segmented(
        [("all", "All cards"), ("finds", "Finds")], "all",
        on_board_seg)

    def show_slip_tool(tool: str):
        with _UPDATE_LOCK:
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
            render_protected()
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
        # freshness gate for the live dot (artist §1.2): fresh
        # (< 4 min since the pull) pulses; stale freezes.
        rec = state["slate"] or {}
        fresh = False
        raw = rec.get("pulled_at")
        if raw:
            try:
                dt = datetime.fromisoformat(
                    str(raw).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age = (datetime.now().astimezone()
                       - dt).total_seconds()
                fresh = age < AUTO_PULL_INTERVAL_S
            except ValueError:
                fresh = False
        _DOT_FRESH["fresh"] = fresh
        pull_age_ctrl.value = _pull_age_text()
        if fresh:
            stale_ctrl.value = ""
            pull_dot.shadow = ICE_GLOW
            if AUTO_PULL_ENABLED:
                start_pulse("dot")
        else:
            pull_dot.opacity = 0.6
            pull_dot.shadow = None
            if rec.get("verified"):
                stale_ctrl.value = "Stale — tap Pull to refresh"

    def ensure_verdicts():
        rec = state["slate"]
        if not rec:
            return None
        if state["verdicts"] is None:
            verdicts, cache = _price_markets_cached(
                rec.get("markets", []), rec,
                state.get("verdict_cache"))
            state["verdicts"] = verdicts
            state["verdict_cache"] = cache
        return state["verdicts"]

    # ---------------- Cards ----------------

    cards_count = ft.Text("", size=11, color=FAINT)
    # v12.7.1 render receipt: the board band states how many
    # cards the last render_cards actually appended — the
    # server-side truth, readable in any Pilot screenshot.
    cards_receipt = ft.Text("", size=10, color=FAINT)
    cards_list = ft.Column(spacing=8)
    # v12.1 QoL: the board header band's pull-age line and the
    # clear-filters chip row — both live in the band (assembly
    # below) and are refreshed by render_cards / refresh_stamp.
    pull_age_ctrl = ft.Text("", size=11, color=DIM,
                            font_family=NUM_FONT)
    filter_chip_row = ft.Row(spacing=8, wrap=True, controls=[])

    # v12.4: the board's two filter dropdowns — the switch
    # wall's replacements. Built once here and seated in the
    # board band at assembly (same styling family as the sort
    # and sport-chooser dropdowns); render_cards keeps the
    # sport dropdown's options synced to the slate's sports.
    def on_sport_view(e):
        state["sport_view"] = e.control.value or "all"
        state["card_limit"] = CARD_PAGE
        render_cards()

    def on_show(e):
        state["show"] = e.control.value or state["show"]
        state["card_limit"] = CARD_PAGE
        render_cards()

    sport_view_dd = ft.Dropdown(
        value=state["sport_view"], width=190,
        options=[ft.DropdownOption(key="all",
                                   text="All sports")],
        on_select=on_sport_view)
    show_dd = ft.Dropdown(
        value=state["show"], width=200,
        options=[ft.DropdownOption(key=k, text=t)
                 for k, t in SHOW_MODES],
        on_select=on_show)

    def _slate_sports():
        """Sports present on the accumulated slate, in the
        board's standing display order (the old switch row's
        order), then any others in pull order."""
        present = []
        for m in (state["slate"] or {}).get("markets", []):
            s = m.get("sport")
            if s is not None and s not in present:
                present.append(s)
        order = ["nfl", "ncaaf", "nba", "nhl", "mlb", "soccer"]
        present.sort(key=lambda s: order.index(s)
                     if s in order else 99)
        return present

    def _sync_sport_view_dd():
        """Keep the 'Board shows' dropdown honest: options are
        All sports + the slate's sports, and a selection whose
        sport has left the slate falls back to All sports."""
        present = _slate_sports()
        sport_view_dd.options = (
            [ft.DropdownOption(key="all", text="All sports")]
            + [ft.DropdownOption(
                key=s, text=SPORT_LABELS.get(s, (s or "?").upper()))
               for s in present])
        if state["sport_view"] != "all" \
                and state["sport_view"] not in present:
            state["sport_view"] = "all"
        sport_view_dd.value = state["sport_view"]
        show_dd.value = state["show"]

    def _pull_age_text():
        """Per-sport pull age (v12.3): the CHOSEN sport's own
        stamp from the accumulated slate ('NFL pulled 2m ago'),
        'not pulled yet' when that sport has no entry in the
        record at all — a sport is never shown with another
        sport's freshness. Legacy entries without their own
        pulled_at fall back to the slate's stamp. Refreshed on
        renders and pulls — no extra clock loop for a label."""
        rec = state["slate"]
        if not rec:
            return ""
        sport = state.get("chosen_sport")
        label = SPORT_LABELS.get(sport, (sport or "").upper())
        sports = rec.get("sports") or {}
        if sport and sport not in sports:
            return f"{label} not pulled yet"
        entry = sports.get(sport) or {}
        raw = entry.get("pulled_at") or rec.get("pulled_at")
        age_txt = None
        if raw:
            try:
                dt = datetime.fromisoformat(
                    str(raw).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                secs = (datetime.now().astimezone()
                        - dt).total_seconds()
                mins = int(secs // 60)
                if secs < 60:
                    age_txt = "just now"
                elif mins < 60:
                    age_txt = f"{mins}m ago"
                elif mins < 1440:
                    age_txt = f"{mins // 60}h ago"
                else:
                    age_txt = f"{mins // 1440}d ago"
            except ValueError:
                age_txt = None
        if age_txt is None:
            return ""
        base = f"{label} pulled {age_txt}" if sport \
            else f"pulled {age_txt}"
        if AUTO_PULL_ENABLED and state.get("last_pull_at"):
            rem = AUTO_PULL_INTERVAL_S - (
                time.monotonic() - state["last_pull_at"])
            if rem > 0:
                return (f"{base} — next auto-pull "
                        f"in ~{max(1, round(rem / 60))}m")
            return f"{base} — auto-pull due"
        return base

    def _filters_nondefault():
        """Non-default is measured against the startup
        state: sport view off All sports, Show off the All
        markets default, a search typed, or a panel league
        filter riding."""
        if state.get("search"):
            return True
        if state.get("league_filter"):
            return True
        if state.get("sport_view") not in (None, "all"):
            return True
        return state.get("show") != DEFAULT_SHOW

    def clear_all_filters():
        """One tap back to the startup view: search emptied,
        both filter dropdowns at their startup defaults, the
        panel league filter cleared."""
        state["search"] = ""
        try:
            search_field.value = ""
        except Exception:
            pass
        state["sport_view"] = DEFAULT_SPORT_VIEW
        state["show"] = DEFAULT_SHOW
        state["card_limit"] = CARD_PAGE
        if state.get("league_filter"):
            clear_league_filter()      # clears + re-renders
        else:
            render_cards()

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
        """The board's view filters (v12.4: the two dropdowns —
        'Board shows' sport + 'Show'), over the cached verdicts
        — display only, never a re-price. Each Show value is
        exactly the predicate the v12 switch of the same name
        implemented; the sport dropdown is the old per-sport
        switches as a single choice (All sports = no filter)."""
        sv = state.get("sport_view") or "all"
        show = state.get("show") or "all"
        out = []
        for m, v, e in entries:
            if show == "priced" and v.get("state") != "PRICED":
                continue
            if show == "golden" and \
                    card_verdict(v)[0] != "GOLDEN BET":
                continue
            if show == "silver" and v.get("metal") != "SILVER":
                continue
            if show == "steel" and v.get("metal") != "STEEL":
                continue
            if show == "nodnb" and \
                    card_verdict(v)[0] == "DO NOT BET":
                continue
            if sv != "all" and m.get("sport") != sv:
                continue
            lf = state.get("league_filter")
            if lf and not market_in_league(
                    m, lf.get("sport"), lf.get("league")):
                continue
            if show == "quick" and not is_quick(m, _anchor()):
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
        # Settings switches only (v12.4): the Board's switch
        # wall is gone — this helper survives solely for the
        # More view's settings (the Sound toggle).
        return ft.Switch(label=label, value=value,
                         active_color=ACCENT, on_change=handler,
                         label_text_style=ft.TextStyle(size=11,
                                                       color=DIM))

    def _animate_cards(cards):
        # F3 entrance, MADE LOAD-BEARING-SAFE in v12.4.1: the
        # first eight cards of a fresh slate rise in (offset
        # only, 180 ms ease-out-cubic) — and a card's OPACITY IS
        # NEVER TOUCHED. The v12.1 pattern set opacity=0, shipped
        # that state, and relied on a worker thread (_flip) to
        # restore visibility; on device the flip's updates never
        # landed and the board rendered its count ("4 of 705")
        # over an invisible list (Pilot screenshot, 2026-10-25).
        # Content visibility must never depend on a follow-up
        # async step: here both offset states ship synchronously
        # inside render_cards (two page.update() calls back to
        # back) — if the client animates between them, the rise
        # plays; if it doesn't, the cards are simply THERE.
        with _UPDATE_LOCK:
            cards = [c for c in cards
                     if isinstance(c, ft.Container)][:8]
            if not cards:
                return
            for c in cards:
                c.offset = ft.Offset(0, 0.03)
                c.animate_offset = ft.Animation(
                    180, ft.AnimationCurve.EASE_OUT_CUBIC)
                if getattr(c, "data", None) == "golden":
                    # v12.6 golden entrance: golden cards also
                    # settle in scale (0.97 -> 1.0, 220 ms)
                    # through the same two shipped states —
                    # scale and offset only, like everything
                    # in this entrance.
                    c.scale = ft.Scale(0.97)
                    c.animate_scale = ft.Animation(
                        220, ft.AnimationCurve.EASE_OUT_CUBIC)
            page.update()
            for c in cards:
                c.offset = ft.Offset(0, 0)
                if getattr(c, "data", None) == "golden":
                    c.scale = ft.Scale(1.0)
            page.update()

    def _dispatch_apply(job):
        # v12.10: stamp the job with the next apply sequence
        # and schedule it on the event loop (page.run_task is
        # this codebase's established thread-to-loop bridge).
        # A job whose stamp is no longer current when the
        # applier reaches it — a newer render was dispatched
        # behind it — aborts without touching the screen:
        # supersession replaces pile-ups.
        state["apply_seq"] = state.get("apply_seq", 0) + 1
        _seq = state["apply_seq"]
        job["seq"] = _seq
        job["is_current"] = (
            lambda s=_seq: state.get("apply_seq") == s)
        job["page"] = page
        job["status"] = status
        page.run_task(_run_apply, job)

    def render_cards():
        # v12.10: the computation is the build-29 render
        # unchanged — same filters, same verdicts, every card
        # built by build_card_safe, same league/date grouping,
        # same count and receipt strings. What changed is the
        # APPLY: nothing in this function mutates the screen
        # anymore. It builds a job (reset / batches of <= 3 /
        # finish) and the event-loop applier (_run_apply)
        # streams it on in small patches — the shape of the
        # one add-path that has always painted on device: a
        # tap's single small patch, delivered on the event
        # loop. The old shape (a worker thread shipping one
        # bulk patch, then a deferred Timer re-ship of the
        # same patch a beat later) is retired with it.
        with _UPDATE_LOCK:
            rec = state["slate"]
            _sync_sport_view_dd()
            if not rec:
                def _reset_empty():
                    cards_list.controls = []
                    pull_age_ctrl.value = ""
                    filter_chip_row.controls = []
                    cards_count.value = ""
                    cards_list.controls.append(empty_full(
                        ft.Icons.CLOUD_OFF, "No pull yet",
                        "Tap Pull — until a live pull lands, "
                        "every market is UNVERIFIED, never "
                        "assumed."))

                def _finish_empty():
                    cards_receipt.value = (
                        "Rendered: 0 cards on this board")

                _dispatch_apply({
                    "reset": _reset_empty,
                    "batches": [],
                    "extend":
                        lambda b: cards_list.controls.extend(b),
                    "finish": _finish_empty})
                return
            entries = sorted_entries()
            # v12.1 QoL header state: pull age + the
            # clear-filters chip (present only while
            # something is non-default). Computed here;
            # the job's reset applies them — value writes,
            # the class that has always displayed.
            _age_text = _pull_age_text()
            _chip_row = (
                [ft.TextButton(
                    "Clear filters",
                    icon=ft.Icons.FILTER_ALT_OFF,
                    style=ft.ButtonStyle(color=ACCENT),
                    on_click=lambda _e: clear_all_filters())]
                if _filters_nondefault() else [])
            # v12.4 render diet: the filter dropdowns are
            # static controls built once in the band — a
            # render only syncs the sport dropdown's options
            # to the slate (above) and rebuilds the card
            # list. There is no per-slate switch row to
            # rebuild at all anymore.
            shown = apply_toggles(entries)
            if len(shown) != len(entries):
                _count_text = (f"{len(shown)} of "
                               f"{len(entries)} markets")
            else:
                _count_text = f"{len(entries)} markets"
            ordered = []
            if state.get("league_filter"):
                # arrived from the 3D panel (Coverage /
                # Registry): the filter is named, and one
                # tap returns
                lf = state["league_filter"]
                ordered.append(ft.Row(
                    spacing=8, wrap=True,
                    vertical_alignment=
                    ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.FILTER_ALT, size=16,
                                color=ACCENT),
                        ft.Text(f"League: {lf['label']} — "
                                f"{len(shown)} markets on "
                                f"this pull",
                                size=12, color=INK,
                                weight=ft.FontWeight.BOLD),
                        ft.TextButton(
                            "Back to 3D panel",
                            on_click=lambda _e: nav_back()),
                        ft.TextButton(
                            "Clear filter",
                            on_click=lambda _e:
                            clear_league_filter())]))
            markets = rec.get("markets", [])
            quotes = game_quotes(markets)
            ctx = lane_contexts(markets)
            limit = state["card_limit"]
            grouped = state["sort"] in ("pull", "time")
            by_date = state["sort"] == "resolve"
            last_sport = None
            last_date = None
            _n_rendered = 0
            for mkt, verdict, edge in shown[:limit]:
                if by_date:
                    label = resolve_date_label(mkt)
                    if label != last_date:
                        last_date = label
                        n_day = sum(
                            1 for e in shown
                            if resolve_date_label(e[0])
                            == label)
                        ordered.append(_header_image(
                            f"{label} · {n_day} markets", INK))
                elif grouped and mkt.get("sport") != last_sport:
                    last_sport = mkt.get("sport")
                    n_sport = sum(
                        1 for e in shown
                        if e[0].get("sport") == last_sport)
                    ordered.append(_header_image(
                        f"{SPORT_LABELS.get(last_sport, (last_sport or '—').upper())}"
                        f" · {n_sport} markets", INK))
                _card = build_card_safe(
                    mkt, verdict, rec, quotes, edge_pts=edge,
                    lane_ctx=ctx, on_chart=_card_chart,
                    on_toggle=render_cards,
                    bankroll=_parse_bankroll(
                        state.get("bankroll")))
                _chip = bet_now_chip_for(mkt, verdict)
                if _chip is not None:
                    ordered.append(_chip)
                ordered.append(_card)
                _n_rendered += 1
            if not shown:
                ordered.append(empty_inline(
                    ft.Icons.SEARCH_OFF,
                    "No markets in this view",
                    "Widen the Show or Board shows dropdown "
                    "— the pull itself is unchanged."))
            elif len(shown) > limit:
                ordered.append(ft.Button(
                    f"Show more ({len(shown) - limit} more)",
                    on_click=on_show_more))
                ordered.append(ft.Text(
                    "Paging is display only — every market "
                    "was priced by the same pricing pass.",
                    size=10, color=FAINT))
            # v12.11: cards are placed as drawn images —
            # no card entrance exists to replay, so
            # _animate_cards stays gated OFF for card
            # children (the flag is still popped so it
            # cannot pile up). View-level settles
            # (_settle_in) are untouched: they move whole
            # views, never cards.
            state.pop("animate_next", False)
            _receipt_text = (
                f"Rendered: {_n_rendered} cards on this "
                f"board")

            def _reset():
                cards_list.controls = []
                pull_age_ctrl.value = _age_text
                filter_chip_row.controls = _chip_row
                cards_count.value = _count_text
                stop_pulse("shimmer")   # real content landed
                # (artist §3.4: shimmer stops the moment
                # content lands)

            def _finish():
                cards_receipt.value = _receipt_text

            _dispatch_apply({
                "reset": _reset,
                "batches": _chunk3(ordered),
                "extend":
                    lambda b: cards_list.controls.extend(b),
                "finish": _finish})

    # ---------------- pull / price workers ----------------

    def on_pull(_e):
        # A manual tap resets the auto-pull clock (v12) and —
        # v12.4 — ARMS the auto-pull loop: the user starts the
        # first pull, and only then may the loop tick.
        with _UPDATE_LOCK:
            state["pull_armed"] = True
            state["last_pull_at"] = time.monotonic()
            status.value = "Pulling the live FanDuel menu…"
            cards_list.controls = skeleton_cards()
            if AUTO_PULL_ENABLED:
                start_pulse("shimmer")
            page.update()
            page.run_thread(_pull_worker)

    def _pull_worker(auto=False):
        # Off the event-handler thread (page.run_thread): the pull
        # plus the first render's pricing pass can take a minute or
        # more, and doing it inside the click handler froze the app
        # on-device behind Dart null-check error banners (v7.0,
        # 2026-10-20). A failure now lands in the status line as
        # the actual Python error — visible, never silent.
        # v12 auto-pull law: a FAILED auto-pull keeps the last
        # good pull and its stamp (the engine calls an old pull
        # STALE, and an unverified one UNVERIFIED — both print);
        # a failed MANUAL pull keeps its v11 behaviour of
        # recording the unverified attempt. Prices are never
        # invented to fill either gap.
        if state["pull_busy"]:
            return
        state["pull_busy"] = True
        try:
            rec = pull_menu()
            state["last_pull_at"] = time.monotonic()
            if auto and not rec.get("verified") \
                    and state["slate"] is not None \
                    and state["slate"].get("verified"):
                status.value = (
                    "Auto-pull didn't land — keeping the last "
                    "good pull; its stamp stands (STALE past the "
                    "engine's window). Nothing was assumed in "
                    "its place.")
                with _UPDATE_LOCK:
                    page.update()
                return
            state["slate"] = rec
            state["verdicts"] = None
            state["card_limit"] = CARD_PAGE
            state["parlay_legs"] = []
            state["protected_confirm"] = False
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
            if state["view"] == "stage":
                render_stage()
            if state["view"] == "slip":
                render_protected()
            # v12.1 feel: the badge follows the new slate, and
            # a pull that lands the slate's FIRST golden bet
            # chimes — once per pull event, only on the 0 -> n
            # crossing (a pull that merely keeps gold is silent).
            _prev_golden = state.get("golden_count", 0)
            state["golden_count"] = _golden_count()
            refresh_slip_badge()
            if _prev_golden == 0 and state["golden_count"] > 0:
                play_sound("golden")
            if state.get("dismiss_splash"):
                state["dismiss_splash"]()
            with _UPDATE_LOCK:
                page.update()
        except Exception as e:
            status.value = (f"Pull failed on this device: "
                            f"{type(e).__name__}: {e}")
            try:
                with _UPDATE_LOCK:
                    page.update()
            except Exception:
                pass
        finally:
            state["pull_busy"] = False

    def _show_only_sport(sport, partial):
        """After a manual scoped pull, the board's 'Board
        shows' dropdown points at what was just pulled (v12.4:
        the dropdown is single-select, so the pulled sport
        itself is the view; its routed sports stay one dropdown
        change away under their own names). The clear-filters
        chip this summons restores the startup view in one
        tap."""
        state["sport_view"] = sport

    def on_sport_select(e):
        sport = e.control.value
        if sport not in b5.FANDUEL_EVENT_TYPES:
            return
        state["chosen_sport"] = set_chosen_sport(sport)
        refresh_stamp()
        page.update()

    def on_pull_sport(_e):
        # A manual tap resets the auto-pull clock (v12), same
        # as Pull all — and (v12.4) ARMS the auto-pull loop:
        # the user starts the first pull.
        with _UPDATE_LOCK:
            state["pull_armed"] = True
            state["last_pull_at"] = time.monotonic()
            label = SPORT_LABELS.get(state["chosen_sport"],
                                      state["chosen_sport"])
            status.value = f"Pulling {label}\u2026"
            cards_list.controls = skeleton_cards()
            if AUTO_PULL_ENABLED:
                start_pulse("shimmer")
            page.update()
            page.run_thread(_sport_pull_worker)

    def _menu_harvest_worker(sport, markets, token):
        # The scoped pull's background follow-up (v12.3
        # amendment): the pull itself lands on the sport page
        # alone — the per-game menu harvest was ~90% of its
        # wall time — so the menus arrive here, off the pull's
        # critical path, and merge as menus only. Guarded by
        # the scheduling pull's pulled_at token: if a newer
        # pull of the same sport has landed since, this
        # harvest is stale and drops itself whole. A failure
        # here never surfaces as a pull failure — each failed
        # menu stamps itself inside the harvest, and the
        # sport's menus_pending marker simply stands until a
        # later pull's harvest clears it.
        try:
            stamp = datetime.now().astimezone().isoformat(
                timespec="seconds")
            menus = _fetch_event_menus(markets, stamp)
            if not menus:
                return
            merged = merge_menu_harvest(state["slate"], sport,
                                        menus, token)
            if merged is None:
                return  # superseded by a fresher pull
            state["slate"] = merged
            save_snapshot(state["slate"])
            # v12.4 render diet: NO surface in the app displays
            # event_menus content (cards, stage and slip all
            # render off markets + verdicts — verified by grep:
            # event_menus is read only by the pull/merge code),
            # so a landed harvest re-renders NOTHING. It saves
            # the snapshot and stands down; the menus are on
            # disk for whatever reads the record next.
        except Exception:
            pass

    def _sport_pull_worker(auto=False):
        # The scoped pull's worker (v12.3): fetches ONLY the
        # chosen sport and MERGES it into the standing slate —
        # the rest of the board keeps its markets and its own
        # stamp. Same off-thread rule and failure honesty as
        # _pull_worker: a failed scoped pull (auto or manual)
        # keeps the last good slice, its error recorded on the
        # sport's entry; prices are never invented to fill it.
        # On success it schedules the background menu harvest
        # (_menu_harvest_worker) as its last act — the pull is
        # complete before the first menu fetch starts.
        if state["pull_busy"]:
            return
        state["pull_busy"] = True
        # v12.28: an auto tick loads the sport in front of the
        # user alone (auto_pull_sport); a manual pull loads
        # the chooser's sport, as its button promises.
        sport = (auto_pull_sport(state.get("sport_view"),
                                 state.get("chosen_sport"))
                 if auto else
                 state.get("chosen_sport") or "nfl")
        label = SPORT_LABELS.get(sport, sport.upper())
        try:
            partial = pull_menu_sport(sport)
            state["last_pull_at"] = time.monotonic()
            entry = (partial.get("sports") or {}).get(sport) or {}
            if "error" in entry:
                if state["slate"] is not None:
                    state["slate"] = merge_sport_pull(
                        state["slate"], partial)
                    save_snapshot(state["slate"])
                status.value = (
                    f"{label} pull didn't land — "
                    f"{entry['error']}. Keeping the last good "
                    f"{label} markets; nothing was assumed in "
                    f"their place.")
                refresh_stamp()
                with _UPDATE_LOCK:
                    page.update()
                return
            state["slate"] = merge_sport_pull(state["slate"],
                                               partial)
            state["verdicts"] = None
            state["card_limit"] = CARD_PAGE
            state["parlay_legs"] = []
            state["protected_confirm"] = False
            if not auto:
                _show_only_sport(sport, partial)
            save_snapshot(state["slate"])
            refresh_stamp()
            status.value = (
                f"Pulled {label}: {entry.get('games', 0)} games "
                f"\u00b7 {len(partial.get('markets') or [])} "
                f"markets — the rest of the board kept its own "
                f"pull.")
            state["animate_next"] = True
            render_cards()
            if state["view"] == "stage":
                render_stage()
            if state["view"] == "slip":
                render_protected()
            _prev_golden = state.get("golden_count", 0)
            state["golden_count"] = _golden_count()
            refresh_slip_badge()
            if _prev_golden == 0 and state["golden_count"] > 0:
                play_sound("golden")
            if state.get("dismiss_splash"):
                state["dismiss_splash"]()
            with _UPDATE_LOCK:
                page.update()
            # The per-game menus follow in the background
            # (v12.3 amendment) — scheduled LAST, after the
            # pull's own merge, save, pricing and render are
            # all done, so the harvest can never delay or gate
            # any of them. The pull's pulled_at rides along as
            # the token: a newer pull of this sport makes this
            # harvest drop itself.
            if partial.get("menus_pending"):
                page.run_thread(
                    _menu_harvest_worker, sport,
                    list(partial.get("markets") or []),
                    partial["pulled_at"])
        except Exception as e:
            status.value = (f"{label} pull failed on this "
                            f"device: {type(e).__name__}: {e}")
            try:
                with _UPDATE_LOCK:
                    page.update()
            except Exception:
                pass
        finally:
            state["pull_busy"] = False

    def _auto_pull_loop():
        # v12 auto-pull: a daemon loop while the app is open.
        # v12.4 arming law (the Pilot's rule): the user starts
        # the first pull — the loop NEVER ticks until the
        # session's first user-initiated pull action (scoped
        # Pull, Pull all, or Price Slate) sets pull_armed; from
        # then on a tick is due every AUTO_PULL_INTERVAL_S since
        # the last pull (the gate is auto_pull_should_tick, pure
        # and harness-pinned). v12.3 re-scope stands, sharpened
        # v12.28: a tick loads ONE sport alone — the sport the
        # board is showing when it shows one (auto_pull_sport),
        # else the chosen sport (the scoped worker + merge) —
        # the full pull is manual, via Pull all. Never
        # overlaps a running pull (the gate and the worker both
        # refuse). Started ONLY from the real entry path — see
        # the __main__ block and AUTO_PULL_ENABLED; the harness
        # never starts it. The 1 s poll is a flag check only —
        # no renders, no fetches while idle.
        while True:
            try:
                if auto_pull_should_tick(
                        state.get("pull_armed"),
                        state["pull_busy"],
                        state.get("last_pull_at"),
                        time.monotonic()):
                    page.run_thread(_sport_pull_worker, True)
            except Exception:
                pass
            time.sleep(1)

    def _boot_worker():
        # The first pricing pass, off the paint path (F4).
        try:
            ensure_verdicts()
            state["golden_count"] = _golden_count()
            refresh_slip_badge()
            state["animate_next"] = True
            if status.value == "Pricing the last pull…":
                status.value = ""
            if state["view"] == "board":
                show_board_segment(state["board_seg"])
            refresh_stamp()
            if state.get("dismiss_splash"):
                state["dismiss_splash"]()
            with _UPDATE_LOCK:
                page.update()
        except Exception as e:
            status.value = (f"Pricing the last pull failed on "
                            f"this device: {type(e).__name__}: {e}")
            try:
                with _UPDATE_LOCK:
                    page.update()
            except Exception:
                pass

    def on_price(_e):
        # Price Slate is a user-initiated pull action — it arms
        # the auto-pull loop too (v12.4), even on the empty
        # path: the user has started the session's pulling.
        with _UPDATE_LOCK:
            state["pull_armed"] = True
            if not state["slate"]:
                status.value = "Nothing to price yet — Pull first."
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
            state["golden_count"] = _golden_count()
            refresh_slip_badge()
            state["animate_next"] = True
            render_cards()
            with _UPDATE_LOCK:
                page.update()
        except Exception as e:
            status.value = (f"Pricing failed on this device: "
                            f"{type(e).__name__}: {e}")
            try:
                with _UPDATE_LOCK:
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
        with _UPDATE_LOCK:
            parse_view.controls = [screen_title(
                "Parse", "Read a pasted bet against the current pull.")]
            rec = state["slate"]
            if not rec:
                parse_view.controls.append(empty_full(
                    ft.Icons.CLOUD_OFF, "No pull yet",
                    "Tap Pull — until a live pull lands, every "
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
        with _UPDATE_LOCK:
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
                _chip = bet_now_chip_for(mkt, verdict)
                if _chip is not None:
                    parse_result.controls.append(_chip)
                parse_result.controls.append(build_card_safe(
                    mkt, verdict, rec, game_quotes(markets),
                    edge_pts=market_edge_pts(mkt, verdict),
                    lane_ctx=lane_contexts(markets), design="B",
                    on_chart=_card_chart,
                    on_toggle=lambda: on_parse(None),
                    bankroll=_parse_bankroll(
                        state.get("bankroll"))))
                parse_result.controls.append(_kelly_block(
                    verdict.get("p"), mkt.get("price"),
                    lane=market_lane(mkt),
                    cal_tag=verdict.get("cal_tag"),
                    priced=verdict.get("state") == "PRICED"))
            page.update()

    # ---------------- Protected Slip (v12) ----------------
    # GOLDEN BET / BET HERE markets auto-populate this panel.
    # Protection is arithmetic printed in the open: every leg
    # sized by the engine's Kelly organ (quarter-Kelly, 5% hard
    # cap, UNCALIBRATED damping in its reasons), total stake,
    # max loss = total stake (every leg can lose — that IS the
    # max loss, printed, not hidden), and the warnings. The app
    # NEVER places anything: the user places the slip on
    # FanDuel themselves, then marks it here; only the mark is
    # written, to the Pilot Book view, as PLACED (user-marked).

    # v12.1: the Slip destination's GOLDEN badge + the golden
    # chime share one count — GOLDEN BET verdicts on the priced
    # slate, read off the cached verdicts (never a re-price).
    _SLIP_DEST = {"dest": None,
                  "badge": ft.Badge(label="", bgcolor=GOLD,
                                    text_color="#060B1A")}

    def _golden_count():
        try:
            return sum(1 for v in (state.get("verdicts") or [])
                       if card_verdict(v)[0] == "GOLDEN BET")
        except Exception:
            return 0

    def refresh_slip_badge():
        try:
            n = _golden_count()
            dest = _SLIP_DEST.get("dest")
            if dest is not None:
                if n > 0:
                    _SLIP_DEST["badge"].label = str(n)
                    dest.badge = _SLIP_DEST["badge"]
                else:
                    dest.badge = None
        except Exception:
            pass

    def protected_candidates():
        rec = state["slate"]
        if not rec:
            return []
        verdicts = ensure_verdicts() or []
        out = []
        for m, v in zip(rec.get("markets", []), verdicts):
            term, _r = card_verdict(v)
            if v.get("state") == "PRICED" \
                    and term in ("GOLDEN BET", "BET HERE") \
                    and v.get("p") is not None \
                    and m.get("price") is not None:
                out.append((m, v))
        out.sort(key=lambda t: (
            verdict_rank(card_verdict(t[1])[0]),
            -(market_edge_pts(t[0], t[1]) or 0)))
        return out

    def render_protected():
        with _UPDATE_LOCK:
            protected_view.controls = []
            cands = protected_candidates()
            bankroll = None
            try:
                bankroll = float(state.get("bankroll") or "") or None
            except (TypeError, ValueError):
                bankroll = None
            rows = [ft.Text("PROTECTED SLIP — PLACEMENT-READY",
                            size=13, color=ACCENT,
                            weight=ft.FontWeight.BOLD),
                    ft.Text("Auto-built from this pull's GOLDEN BET / "
                            "BET HERE markets, sized by the engine's "
                            "Kelly organ. You place it on FanDuel "
                            "yourself — the app never places a bet "
                            "and never touches a sportsbook account.",
                            size=11, color=DIM, height=1.35)]
            if not cands:
                rows.append(ft.Text(
                    "No GOLDEN BET or BET HERE markets on this pull "
                    "— the slip stays empty rather than promote a "
                    "market the engine did not bless.",
                    size=12, color=DIM, height=1.35))
                protected_view.controls = [ft.Container(
                    bgcolor=CARD_BG, border=_border_all(1, HAIRLINE),
                    border_radius=14, padding=12, shadow=ELEV_L1,
                    content=ft.Column(spacing=6, controls=rows))]
                page.update()
                return
            total_units = 0.0
            total_dollars = 0.0 if bankroll else None
            warnings = []
            legs = []
            seen_games = {}
            any_golden = False
            for m, v in cands:
                term, _r = card_verdict(v)
                any_golden = any_golden or term == "GOLDEN BET"
                adv = b5.kelly_advice(
                    v["p"], m["price"], bankroll=bankroll,
                    cal_tag=v.get("cal_tag"), priced=True)
                nm = bet_name(m, v)
                stake_txt = f"{adv['stake_units']:.1f}u"
                if adv["stake_dollars"] is not None:
                    stake_txt += f" (${adv['stake_dollars']:,.0f})"
                    total_dollars += adv["stake_dollars"]
                total_units += adv["stake_units"]
                legs.append({"name": nm["slip_label"], "term": term,
                             "price": int(m["price"]),
                             "stake_units": adv["stake_units"],
                             "stake_dollars": adv["stake_dollars"]})
                rows.append(ft.Row(
                    spacing=8, vertical_alignment=
                    ft.CrossAxisAlignment.START, controls=[
                        verdict_pill(term),
                        ft.Column(spacing=2, tight=True, expand=True,
                                  controls=[
                                      ft.Text(nm["selection"],
                                              size=13, color=INK,
                                              weight=ft.FontWeight
                                              .BOLD),
                                      ft.Text(
                                          f"{nm['market']} · "
                                          f"{int(m['price']):+d} · "
                                          f"Kelly stake {stake_txt}",
                                          size=11, color=DIM,
                                          font_family=NUM_FONT)])]))
                for reason in adv["reasons"]:
                    if "UNCALIBRATED" in reason or "hard cap" in reason:
                        warnings.append(f"{nm['selection']}: {reason}")
                if v.get("note"):
                    warnings.append(
                        f"{nm['selection']}: {plain_note(v['note'])}")
                gkey = (m.get("sport"), m.get("home"), m.get("away"))
                if gkey in seen_games:
                    warnings.append(
                        "Multiple legs from the same game "
                        f"({nm['matchup']}) — they are not "
                        "independent; one game can sink several "
                        "legs at once.")
                seen_games[gkey] = True
            total_txt = f"Total stake {total_units:.1f}u"
            if total_dollars is not None:
                total_txt += f" (${total_dollars:,.0f})"
            # v12.1 QoL: the pinned summary line, directly under the
            # panel header — legs, combined odds + combined model
            # probability (the legs' own prices and probabilities,
            # combined with the app's standing independence product,
            # the same formula the Parlay tool prints), and max loss
            # = the total stake computed above. Nothing recomputed
            # on a second basis.
            if legs:
                _dec = 1.0
                _mp = 1.0
                for (_m, _v), _leg in zip(cands, legs):
                    _pr = int(_leg["price"])
                    _dec *= 1.0 + (_pr / 100.0 if _pr > 0
                                   else 100.0 / abs(_pr))
                    _mp *= float(_v.get("p") or 0.0)
                _amer = (int(round((_dec - 1) * 100)) if _dec >= 2
                         else int(round(-100.0 / (_dec - 1))))
                _loss = f"{total_units:.1f}u"
                if total_dollars is not None:
                    _loss += f" / ${total_dollars:,.0f}"
                rows.insert(2, ft.Container(
                    gradient=PANEL_GRADIENT,
                    border=_border_all(1, HAIRLINE), border_radius=10,
                    padding=ft.Padding(left=10, right=10, top=7,
                                       bottom=7),
                    content=ft.Text(
                        f"{len(legs)} legs · combined odds "
                        f"{_dec:.2f} ({_amer:+d}) · model {_mp:.1%} "
                        f"· max loss {_loss}",
                        size=12, color=INK,
                        weight=ft.FontWeight.BOLD,
                        font_family=NUM_FONT)))
            rows.append(ft.Text(total_txt, size=15, color=INK,
                                weight=ft.FontWeight.BOLD,
                                font_family=NUM_FONT))
            rows.append(ft.Text(
                f"Max loss = the total stake above "
                f"({total_units:.1f}u"
                + (f" / ${total_dollars:,.0f}" if total_dollars
                   is not None else "")
                + ") — every leg can lose, and the slip loses no "
                  "more than what is staked. There is no scenario "
                  "worse than that printed here.",
                size=12, color=WARN, height=1.35))
            if warnings:
                rows.append(ft.Text("WARNINGS — READ BEFORE PLACING",
                                    size=11, color=WARN,
                                    weight=ft.FontWeight.BOLD))
                for w in dict.fromkeys(warnings):
                    rows.append(ft.Row(spacing=6, controls=[
                        ft.Icon(ft.Icons.WARNING_AMBER, size=14,
                                color=WARN),
                        ft.Text(w, size=11, color=WARN, height=1.3,
                                expand=True)]))
            if not state["protected_confirm"]:
                rows.append(primary_button(
                    "Mark placed on FanDuel",
                    lambda _e: _protected_confirm(cands, legs,
                                                  total_units,
                                                  total_dollars)))
                rows.append(ft.Text(
                    "Tapping asks you to confirm the legs + total "
                    "first. Nothing is written until you confirm — "
                    "and what is written is YOUR mark, in the Pilot "
                    "Book, as PLACED (user-marked).",
                    size=10, color=FAINT, height=1.3))
            else:
                rows.append(ft.Text(
                    "Confirm: you placed exactly these legs on "
                    "FanDuel at the prices above?",
                    size=12, color=INK, weight=ft.FontWeight.BOLD))
                rows.append(ft.Row(spacing=8, controls=[
                    primary_button(
                        "Yes — mark it placed",
                        lambda _e: _protected_mark(legs, total_units,
                                                   total_dollars)),
                    secondary_button(
                        "Not yet",
                        lambda _e: _protected_unconfirm())]))
            panel_controls = []
            if any_golden:
                # the GOLDEN warm pulse lives on this glow bar: a
                # pre-rendered gold glow layer whose opacity the
                # golden pulse breathes (2800 ms) — the only warm
                # pulse in the app, on a GOLDEN surface only.
                glow_bar = ft.Container(
                    height=6, border_radius=3, bgcolor=GOLD,
                    shadow=GOLD_GLOW, opacity=0.425,
                    animate_opacity=ft.Animation(
                        120, ft.AnimationCurve.EASE_IN_OUT))
                _PULSE_TARGETS["golden"] = [glow_bar]
                panel_controls.append(glow_bar)
            panel_controls.append(ft.Container(
                bgcolor=CARD_BG,
                gradient=GOLD_GRADIENT if any_golden else PANEL_GRADIENT,
                border=_border_all(1.5 if any_golden else 1,
                                   GOLD if any_golden else HAIRLINE),
                border_radius=14, padding=12, shadow=ELEV_L2,
                content=ft.Column(spacing=6, controls=rows)))
            protected_view.controls = panel_controls
            page.update()

    def _protected_confirm(cands, legs, total_units, total_dollars):
        state["protected_confirm"] = True
        render_protected()

    def _protected_unconfirm():
        state["protected_confirm"] = False
        render_protected()

    def _protected_mark(legs, total_units, total_dollars):
        slip = {"marked_at": datetime.now().astimezone()
                .isoformat(timespec="seconds"),
                "status": "PLACED (user-marked)",
                "legs": legs, "total_units": total_units,
                "total_dollars": total_dollars,
                "pull": (state["slate"] or {}).get("pulled_at")}
        append_marked_slip(slip)
        play_sound("confirm")   # v12.1: the slip is built + marked
        state["protected_confirm"] = False
        status.value = ("Marked as placed — written to the "
                        "Pilot Book view as PLACED (user-marked). "
                        "The app placed nothing.")
        render_protected()
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
        with _UPDATE_LOCK:
            parlay_view.controls = [screen_title(
                "Parlay", "Priced legs only — built from the last pull.")]
            rec = state["slate"]
            if not rec:
                parlay_view.controls.append(empty_full(
                    ft.Icons.CLOUD_OFF, "No pull yet",
                    "Tap Pull — until a live pull lands, every "
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
                                    tooltip="Remove leg",
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
        with _UPDATE_LOCK:
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
                          tooltip="Go back",
                          on_click=lambda _e: show("more")),
            screen_title(title, subtitle)])

    def render_more():
        # More is closed to new tiles in 10.4.x (UX nav law):
        # the finds feed moved to the Board and the Record grew
        # into the Lab destination — what remains is reference.
        with _UPDATE_LOCK:
            tiles = [
                (ft.Icons.MENU_BOOK, "Terms",
                 "What every word on a card means", "terms"),
                (ft.Icons.FUNCTIONS, "Equations",
                 "The math, in the open", "equations"),
                (ft.Icons.CODE, "Dev",
                 "Version, fingerprint, credit", "dev")]
            controls = [screen_title("More", "Everything else in BetFi.")]
            # v12.1: the sound toggle — persisted on-device, default
            # ON. Off means play_sound no-ops everywhere at once.
            controls.append(_switch(
                "Sound — tap ticks, slip confirm, golden chime",
                bool(_SOUND.get("enabled", True)),
                lambda e: set_sound_enabled(bool(e.control.value))))
            controls.append(ft.Text(
                "Three quiet sounds, volume-capped, off means off — "
                "the setting is saved on this device.",
                size=10, color=FAINT, height=1.3))
            controls.append(ft.Divider(color=BORDER))
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
        # v12.10: the finds computation and its ordering are
        # unchanged — applied by the event-loop batched
        # applier like the board (see render_cards). The
        # section chrome (the intro line) seats in the job's
        # reset; every section after it streams on in
        # batches of <= 3; the finish registers the golden
        # glow layer with the pulse, once its surface is on
        # screen.
        with _UPDATE_LOCK:
            _intro = ft.Text(
                "Finds — golden bets first, then the ranked "
                "finds. Same pull, same prices as All cards; "
                "the feed only re-ranks.",
                size=12, color=DIM, height=1.35)
            rec = state["slate"]
            if not rec:
                def _reset_empty():
                    betfi_view.controls = [
                        _intro,
                        empty_full(
                            ft.Icons.CLOUD_OFF,
                            "Nothing to distill",
                            "The feed distills the current "
                            "pull — pull the menu on the Board "
                            "first.")]

                _dispatch_apply({
                    "reset": _reset_empty,
                    "batches": [],
                    "extend":
                        lambda b: betfi_view.controls.extend(b),
                    "finish": None})
                return
            verdicts = ensure_verdicts()
            markets = rec.get("markets", [])
            quotes = game_quotes(markets)
            ctx = lane_contexts(markets)
            golden, finds, flagged, counter = distill_finds(
                markets, verdicts)
            ordered = []
            ordered.append(_header_image("GOLDEN BETS", GOLD))
            _glow = None
            if golden:
                # the GOLDEN warm pulse (2800 ms) breathes
                # this pre-rendered glow layer's opacity —
                # gold only, GOLDEN surface only; the empty
                # panel below gets NO glow and NO pulse
                # (artist §1.3 / rescue §6).
                _glow = ft.Container(
                    height=6, border_radius=3, bgcolor=GOLD,
                    shadow=GOLD_GLOW, opacity=0.425,
                    animate_opacity=ft.Animation(
                        120, ft.AnimationCurve.EASE_IN_OUT))
                ordered.append(_glow)
            if not golden:
                ordered.append(empty_inline(
                    ft.Icons.STAR_OUTLINE,
                    "No golden bets on this pull"))
                ordered.append(ft.Text(
                    "Nothing golden on this pull. The standard "
                    "don't drop just 'cause the panel empty.",
                    size=11, color=DIM))
            for mkt, verdict, edge in golden:
                _chip = bet_now_chip_for(mkt, verdict)
                if _chip is not None:
                    ordered.append(_chip)
                ordered.append(build_card_safe(
                    mkt, verdict, rec, quotes, edge_pts=edge,
                    lane_ctx=ctx, design="B",
                    on_chart=_card_chart,
                    on_toggle=render_betfi,
                    bankroll=_parse_bankroll(
                        state.get("bankroll"))))
            ordered.append(_header_image(
                f"FINDS — verdict ladder, then edge "
                f"({len(finds)})", ACCENT))
            if not finds:
                ordered.append(ft.Text(
                    "No priced, verdict-bearing market on this "
                    "pull. The feed stays empty rather than "
                    "promote a market the engine did not price.",
                    size=12, color=DIM, height=1.35))
            for i, (mkt, verdict, edge) in enumerate(
                    finds[:CARD_PAGE], start=1):
                _chip = bet_now_chip_for(mkt, verdict)
                if _chip is not None:
                    ordered.append(_chip)
                ordered.append(build_card_safe(
                    mkt, verdict, rec, quotes, rank=i,
                    edge_pts=edge, lane_ctx=ctx, design="B",
                    on_chart=_card_chart,
                    on_toggle=render_betfi,
                    bankroll=_parse_bankroll(
                        state.get("bankroll"))))
            if len(finds) > CARD_PAGE:
                ordered.append(ft.Text(
                    f"+{len(finds) - CARD_PAGE} more finds past "
                    f"the page cap — All cards on the Board "
                    f"holds the full list.",
                    size=11, color=FAINT))
            if flagged:
                ordered.append(_header_image(
                    f"PRICE CONFLICT — two prices for the same "
                    f"event disagree inside this pull "
                    f"({len(flagged)})", WARN))
                for mkt, verdict, edge in flagged:
                    _chip = bet_now_chip_for(mkt, verdict)
                    if _chip is not None:
                        ordered.append(_chip)
                    ordered.append(build_card_safe(
                        mkt, verdict, rec, quotes,
                        edge_pts=edge, lane_ctx=ctx, design="B",
                        on_chart=_card_chart,
                        on_toggle=render_betfi,
                        bankroll=_parse_bankroll(
                            state.get("bankroll"))))
            counter_lines = []
            for _m, v, e in counter:
                _nm = bet_name(_m, v)
                counter_lines.append(
                    f"{_nm['selection']} · {_nm['market']} — "
                    f"{v.get('state')}"
                    + (f" · edge {e:+.1f} pts"
                       if e is not None else ""))
            ordered.append(ft.ExpansionTile(
                title=ft.Text(
                    f"Checked — no edge ({len(counter)})",
                    size=12, color=FAINT,
                    weight=ft.FontWeight.BOLD),
                controls=[ft.Container(
                    padding=8, content=ft.Column(
                        spacing=2,
                        controls=[_line(t, 10, FAINT)
                                  for t in counter_lines]))]))

            def _reset():
                betfi_view.controls = [_intro]

            def _finish():
                # the golden pulse key belongs to this
                # surface's glow bar alone (v12.7: cards no
                # longer carry bars; render_protected's glow
                # bar is the other owner)
                _PULSE_TARGETS["golden"] = (
                    [_glow] if golden else [])

            _dispatch_apply({
                "reset": _reset,
                "batches": _chunk3(ordered),
                "extend":
                    lambda b: betfi_view.controls.extend(b),
                "finish": _finish})

    # ---------------- Lab (the record wing) ----------------

    def _money(v) -> str:
        return f"${abs(v):,.0f}" if float(v) == int(v) \
            else f"${abs(v):,.2f}"

    def _signed_money(v) -> str:
        return ("+" if v > 0 else "−" if v < 0 else "") \
            + _money(v)

    def render_lab():
        with _UPDATE_LOCK:
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
                    "Xii build carries the pack."))
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
            _marked = load_marked_slips()
            if _marked:
                record_view.controls.append(ft.Text(
                    "PLACED (user-marked) — slips you marked placed "
                    "from the Protected Slip. Your marks, on this "
                    "device; the app placed none of them.",
                    size=11, color=WARN, height=1.35))
                for _ms in _marked:
                    _legs_txt = "; ".join(
                        f"{lg['name']} · {lg['stake_units']:.1f}u"
                        for lg in _ms.get("legs") or [])
                    record_view.controls.append(ledger_row(
                        str(_ms.get("marked_at") or "")[:10],
                        _legs_txt, "—", "—", "PLACED",
                        f"{float(_ms.get('total_units') or 0):.1f}u",
                        zebra=False,
                        bet_note="PLACED (user-marked) · "
                                 f"{_ms.get('marked_at')}"))
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
                    f"(engine v{b5.ENGINE_VERSION}, display only).", size=11,
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
             "the pull — the Quick bets view in the Board's Show "
             "dropdown. The "
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
        with _UPDATE_LOCK:
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
        with _UPDATE_LOCK:
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
        with _UPDATE_LOCK:
            identity = ft.Container(
                bgcolor=CARD_BG, border_radius=10, padding=12,
                content=ft.Column(spacing=6, controls=[
                    ft.Text(DISPLAY_NAME, size=16, color=INK,
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
                    ft.Text("BetFi Xii — by T. Abram.", size=13,
                            color=INK, weight=ft.FontWeight.BOLD),
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
    # v12.11: the ImageBoard's tap routing — expansion
    # re-renders through the current view's normal path; the
    # SLIP zone opens the Slip view (whose Protected Slip
    # panel builds itself on arrival, exactly as a bottom-nav
    # tap there does). The lambdas resolve show/state at call
    # time; both are live before any tap can land.
    bind_card_hooks(
        refresh=lambda: show(state["view"]),
        slip=lambda: show("slip"))
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

    def _chart_tap(detail):
        state["chart_detail"] = detail
        render_stage()

    def _chart_zoom(factor):
        if factor == 0:
            state["chart_zoom"] = 1.0
        else:
            state["chart_zoom"] = min(
                6.0, max(0.5, state["chart_zoom"] * factor))
        render_stage()

    # ---- Xii panel: four segments, one switcher (v12) ----
    # Charts | Coverage | Instruments | Registry — only the
    # active segment is built per render, and the segment, the
    # chart zoom and the tapped detail all live in state, so a
    # pull re-renders the open segment in place with them kept.

    panel_charts_col = ft.Column(spacing=8)
    panel_coverage_col = ft.Column(spacing=8)
    panel_instruments_col = ft.Column(spacing=8)
    panel_registry_col = ft.Column(spacing=8)
    _PANEL_COLS = {"charts": panel_charts_col,
                   "coverage": panel_coverage_col,
                   "instruments": panel_instruments_col,
                   "registry": panel_registry_col}
    panel_switcher = _switcher(panel_charts_col)

    def show_panel_segment(seg: str):
        with _UPDATE_LOCK:
            state["panel_segment"] = seg
            panel_seg_ctrl.selected = [seg]
            render_stage()
            # v12.6 graph navigation: the incoming panel segment
            # settles in (two-update, scale/offset only).
            _settle_in(page, panel_switcher.content)

    def on_panel_seg(e):
        sel = e.control.selected or []
        show_panel_segment(next(iter(sel)) if sel else "charts")

    panel_seg_ctrl = _segmented(
        [("charts", "Charts"), ("coverage", "Coverage"),
         ("instruments", "Instruments"), ("registry", "Registry")],
        "charts", on_panel_seg)

    # ---- Stocks destination (v13.0): four segments, one
    # switcher — Tape | Matrix | Options | Holdings, on the Xii
    # panel pattern (only the active segment is built per
    # render; segment, name and expiry live in state and
    # survive pulls). The section prints the market's own
    # numbers — quotes, realized vol, the options-implied
    # distribution — and the lane truth beside them: S1/S5
    # FAILED-EXAM, S2/S3/S4 NOT-BUILT, so every action here is
    # WATCH and no model probability or edge exists to print.

    stocks_tape_col = ft.Column(spacing=8)
    stocks_matrix_col = ft.Column(spacing=8)
    stocks_options_col = ft.Column(spacing=8)
    stocks_holdings_col = ft.Column(spacing=8)
    _STOCKS_COLS = {"tape": stocks_tape_col,
                    "matrix": stocks_matrix_col,
                    "options": stocks_options_col,
                    "holdings": stocks_holdings_col}
    stocks_switcher = _switcher(stocks_tape_col)

    def show_stocks_segment(seg: str):
        with _UPDATE_LOCK:
            state["stocks_seg"] = seg
            stocks_seg_ctrl.selected = [seg]
            render_stocks()
            _settle_in(page, stocks_switcher.content)

    def on_stocks_seg(e):
        sel = e.control.selected or []
        show_stocks_segment(next(iter(sel)) if sel else "tape")

    stocks_seg_ctrl = _segmented(
        [("tape", "Tape"), ("matrix", "Matrix"),
         ("options", "Options"), ("holdings", "Holdings")],
        "tape", on_stocks_seg)

    def _stocks_names() -> dict:
        return state.get("stocks") or {}

    def _stocks_asof(bundle):
        # the pull's own date (ET-stamped at pull time) — DTE
        # and the implied extraction both key off it, so an
        # archived pull shapes the same grid it shaped live
        raw = ((bundle or {}).get("quote") or {}).get("pulled_at")
        try:
            return datetime.fromisoformat(raw).date()
        except Exception:
            return datetime.now().astimezone().date()

    def _stocks_default_expiry(bundle):
        chain = (bundle or {}).get("chain") or {}
        exps = [e["expiry"] for e in chain.get("expiries") or []]
        if not exps:
            return None
        asof = _stocks_asof(bundle)
        for ex in exps:
            try:
                dte = (datetime.strptime(
                    ex, "%Y-%m-%d").date() - asof).days
            except ValueError:
                continue
            if dte >= 5:
                return ex
        return exps[0]

    def _fmt_money(v):
        return "—" if v is None else f"${v:,.2f}"

    def _fmt_pct(v, digits=2):
        return "—" if v is None else f"{v:+.{digits}f}%"

    def _stocks_empty(col, title, line):
        col.controls = [
            ft.Text(title, size=13, color=INK,
                    weight=ft.FontWeight.BOLD),
            ft.Text(line, size=12, color=DIM, height=1.35)]

    # ---------------- stocks pull ----------------

    def on_stocks_pull(_e):
        with _UPDATE_LOCK:
            if state["stocks_busy"]:
                return
            state["stocks_note"] = "Pulling stocks — Nasdaq API…"
            render_stocks()
            page.run_thread(_stocks_pull_worker)

    def _stocks_pull_worker():
        # Off the event-handler thread (page.run_thread), the
        # _pull_worker pattern: a failed name keeps its last
        # good bundle, stamped STALE — data is never invented
        # to fill the gap, and the failure names itself in the
        # note line.
        if state["stocks_busy"]:
            return
        state["stocks_busy"] = True
        try:
            old = state.get("stocks") or {}
            names, failed, fresh = {}, [], 0
            for sym in STOCK_UNIVERSE:
                try:
                    names[sym] = fetch_stock_bundle(
                        sym, stock_history_fromdate())
                    fresh += 1
                except Exception:
                    failed.append(sym)
                    if sym in old:
                        kept = dict(old[sym])
                        kept["stale"] = True
                        names[sym] = kept
            state["stocks"] = names
            save_stocks_snapshot(names)
            note = (f"Nasdaq pull landed: {fresh} of "
                    f"{len(STOCK_UNIVERSE)} names fresh")
            if failed:
                note += (f" · failed: {', '.join(failed)} — "
                         f"last good data kept, stamped STALE")
            state["stocks_note"] = note + "."
            if state["view"] == "stocks":
                render_stocks()
            with _UPDATE_LOCK:
                page.update()
        except Exception as e:
            state["stocks_note"] = (
                f"Stocks pull failed on this device: "
                f"{type(e).__name__}: {e}")
            try:
                with _UPDATE_LOCK:
                    page.update()
            except Exception:
                pass
        finally:
            state["stocks_busy"] = False

    # ---------------- tape ----------------

    def render_stocks_tape(col):
        names = _stocks_names()
        if not names:
            _stocks_empty(
                col, "No stock pull yet",
                "Pull stocks and the tape fills from the "
                "Nasdaq API — quotes, chains and a year of "
                "daily history per name. Nothing is drawn "
                "from nothing.")
            return
        out = [ft.Text(
            "Quotes are the market's own numbers (Nasdaq "
            "API). Delay classes: quotes realtime-claimed, "
            "chains delayed, history end-of-day — every row "
            "carries its own pull stamp.", size=11, color=DIM,
            height=1.35)]
        for sym in STOCK_UNIVERSE:
            bundle = names.get(sym)
            if not bundle:
                continue
            v = b5.stock_quote_view(bundle)
            pct = v["pct_change"]
            out.append(ft.Row(spacing=8, vertical_alignment=
                              ft.CrossAxisAlignment.CENTER,
                              controls=[
                ft.Text(sym, size=14, color=INK,
                        weight=ft.FontWeight.BOLD, width=58),
                ft.Text(v["company_name"] or "", size=11,
                        color=DIM, width=170,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(_fmt_money(v["last"]), size=14,
                        color=INK, width=86,
                        text_align=ft.TextAlign.RIGHT),
                ft.Text(_fmt_pct(pct), size=13, width=76,
                        text_align=ft.TextAlign.RIGHT,
                        color=EDGE_POS if (pct or 0) >= 0
                        else EDGE_NEG)]))
            stamp = (f"{v['source']} · pulled {v['pulled_at']} "
                     f"· {v['delay_class']}")
            if v["stale"]:
                stamp += " · STALE — last good pull kept"
            out.append(ft.Text(stamp, size=10, color=FAINT))
        col.controls = out

    # ---------------- matrix ----------------

    def render_stocks_matrix(col):
        names = _stocks_names()
        if not names:
            _stocks_empty(
                col, "No stock pull yet",
                "The matrix prices each name's realized vol "
                "and prints its lane truth. Pull stocks first "
                "— nothing is drawn from nothing.")
            return
        out = [ft.Text(
            "One row per name: the market's spot, realized "
            "vol from the pulled history, and the examined "
            "lanes' verdicts. The model-probability columns "
            "of the v13.0 design stay stamped, not numbered — "
            "both matrix lanes failed their exams.",
            size=11, color=DIM, height=1.35)]
        for sym in STOCK_UNIVERSE:
            bundle = names.get(sym)
            if not bundle:
                continue
            v = b5.stock_quote_view(bundle)
            rows = [
                ft.Row(spacing=8, controls=[
                    ft.Text(sym, size=14, color=INK,
                            weight=ft.FontWeight.BOLD),
                    ft.Text(v["company_name"] or "", size=11,
                            color=DIM)]),
                ft.Text(
                    f"Spot (regular close): "
                    f"{_fmt_money(v['spot_reference'])} — "
                    f"{v['spot_reference_basis'] or ''}",
                    size=12, color=INK)]
            rv = v["rv"]
            if rv and rv.get("cc20_pct") is not None:
                rows.append(ft.Text(
                    f"Realized vol (annualized, pulled "
                    f"history): cc20 {rv['cc20_pct']:.1f}% · "
                    f"cc60 {rv['cc60_pct']:.1f}% · "
                    f"EWMA(λ=0.94) {rv['ewma94_pct']:.1f}%",
                    size=12, color=INK))
            else:
                rows.append(ft.Text(
                    "Realized vol unavailable — no usable "
                    "history in this pull.", size=12,
                    color=DIM))
            for stamp in v["lanes"]:
                rows.append(ft.Text(stamp, size=10,
                                    color=FAINT, height=1.3))
            rows.append(ft.Row(spacing=6, controls=[
                ft.Text("ACTION:", size=12, color=DIM),
                ft.Text("WATCH", size=12, color=ACCENT,
                        weight=ft.FontWeight.BOLD),
                ft.Text("— " + v["action_reason"], size=11,
                        color=DIM)]))
            out.append(ft.Container(
                bgcolor=CARD_BG, border=_border_all(1, HAIRLINE),
                border_radius=10, padding=10,
                content=ft.Column(spacing=3, controls=rows)))
        col.controls = out

    # ---------------- options ----------------

    def _on_stocks_sym(e):
        sym = e.control.value
        if sym in _stocks_names():
            state["stocks_sym"] = sym
            state["stocks_expiry"] = None
            render_stocks()

    def _on_stocks_expiry(e):
        state["stocks_expiry"] = e.control.value
        render_stocks()

    def render_stocks_options(col):
        names = _stocks_names()
        if not names:
            _stocks_empty(
                col, "No stock pull yet",
                "The options grid is built from the pulled "
                "chain — the market's own implied probability "
                "book. Pull stocks first; nothing is drawn "
                "from nothing.")
            return
        sym = state.get("stocks_sym")
        if sym not in names:
            sym = next(s for s in STOCK_UNIVERSE if s in names)
            state["stocks_sym"] = sym
        bundle = names[sym]
        quote = bundle.get("quote") or {}
        chain = bundle.get("chain") or {}
        spot = quote.get("spot_reference")
        asof = _stocks_asof(bundle)
        expiries = [e["expiry"]
                    for e in chain.get("expiries") or []]
        out = [ft.Row(spacing=8, controls=[
            ft.Dropdown(
                value=sym, width=130,
                options=[ft.DropdownOption(key=s, text=s)
                         for s in STOCK_UNIVERSE if s in names],
                on_select=_on_stocks_sym),
            ft.Text(f"spot (regular close): {_fmt_money(spot)}",
                    size=12, color=DIM)])]
        if not expiries or spot is None:
            out.append(ft.Text(
                "No chain in this pull for " + sym + " — the "
                "grid has nothing to extract from.",
                size=12, color=DIM, height=1.35))
            col.controls = out
            return
        expiry = state.get("stocks_expiry")
        if expiry not in expiries:
            expiry = _stocks_default_expiry(bundle)
            state["stocks_expiry"] = expiry

        def _exp_label(ex):
            dte = (datetime.strptime(
                ex, "%Y-%m-%d").date() - asof).days
            return f"{ex} · {dte} DTE"

        out.append(ft.Dropdown(
            value=expiry, width=210,
            options=[ft.DropdownOption(key=ex,
                                       text=_exp_label(ex))
                     for ex in expiries],
            on_select=_on_stocks_expiry))
        block = next(e for e in chain["expiries"]
                     if e["expiry"] == expiry)
        grid = b5.option_grid_view(block, spot,
                                   asof=asof.isoformat())
        out.append(ft.Text(b5.STOCK_MODEL_STAMP, size=11,
                           color=WARN, height=1.35))
        if grid["short_dated"]:
            out.append(ft.Text(
                f"SHORT-DATED — IMPLIED UNRELIABLE "
                f"({grid['dte_calendar']} DTE): implied "
                f"probabilities suppressed on this expiry.",
                size=12, color=WARN,
                weight=ft.FontWeight.BOLD, height=1.35))

        def _cell(txt, w, color=INK, bold=False, align=None):
            return ft.Text(txt, size=11, color=color, width=w,
                           weight=ft.FontWeight.BOLD if bold
                           else None, text_align=align)

        R = ft.TextAlign.RIGHT
        out.append(ft.Row(spacing=6, controls=[
            _cell("Strike", 62, DIM, True),
            _cell("Call bid", 58, DIM, True, R),
            _cell("Call ask", 58, DIM, True, R),
            _cell("IV", 56, DIM, True, R),
            _cell("P(above)", 66, DIM, True, R),
            _cell("Model", 74, DIM, True),
            _cell("Action", 52, DIM, True)]))
        for r in grid["rows"]:
            iv = (f"{r['iv'] * 100:.1f}%" if r["iv"] is not None
                  else "—")
            p = (f"{r['p_above'] * 100:.1f}%"
                 if r["p_above"] is not None else "—")
            out.append(ft.Row(spacing=6, controls=[
                _cell(f"{r['strike']:,.0f}", 62),
                _cell(_fmt_money(r["call_bid"]), 58, INK,
                      False, R),
                _cell(_fmt_money(r["call_ask"]), 58, INK,
                      False, R),
                _cell(iv, 56, INK, False, R),
                _cell(p, 66, ACCENT if r["p_above"] is not None
                      else FAINT, False, R),
                _cell("NOT-BUILT", 74, FAINT),
                _cell("WATCH", 52, ACCENT, True)]))
        diag = grid["diagnostics"]
        em, sm = grid["expected_move_pct"], \
            grid["straddle_move_pct"]
        if em is not None and not grid["short_dated"]:
            line = (f"Implied expected move (density): "
                    f"{em * 100:.1f}% of spot")
            if sm is not None:
                line += (f" · ATM straddle cross-check: "
                         f"{sm * 100:.1f}%")
            out.append(ft.Text(line, size=11, color=DIM,
                               height=1.35))
            out.append(ft.Text(
                f"Extraction diagnostics: mass before "
                f"renormalization "
                f"{diag.get('mass_before_renorm', 0):.3f} · "
                f"clipped negative mass "
                f"{diag.get('clipped_negative_mass', 0):.3f} · "
                f"implied mean vs forward "
                f"{diag.get('mean_minus_forward', 0):+.2f} · "
                f"strikes used {diag.get('n_strikes_used')} "
                f"of {diag.get('n_strikes_listed')}",
                size=10, color=FAINT, height=1.35))
        for lane in ("S2", "S3", "S4"):
            out.append(ft.Text(b5.STOCK_LANES[lane]["stamp"],
                               size=10, color=FAINT, height=1.3))
        for note in grid["notes"]:
            out.append(ft.Text(note, size=10, color=FAINT,
                               height=1.3))
        out.append(ft.Text(
            f"Chain: {chain.get('source')} · pulled "
            f"{chain.get('pulled_at')} · delayed composite; "
            f"spot is the quote's regular close, never the "
            f"chain's embedded last-trade stamp.",
            size=10, color=FAINT, height=1.3))
        col.controls = out

    # ---------------- holdings ----------------

    def _save_holding(sym, shares_field, cost_field):
        def _h(_e):
            sh = _parse_bankroll(shares_field.value)
            co = _parse_bankroll(cost_field.value)
            h = dict(state["holdings"])
            if sh is None and co is None:
                h.pop(sym, None)
                state["stocks_note"] = (
                    f"{sym}: holding cleared.")
            elif sh is None or co is None:
                state["stocks_note"] = (
                    f"{sym}: enter both shares and average "
                    f"cost, or clear both — holding unchanged.")
                render_stocks()
                return
            else:
                h[sym] = {"shares": sh, "avg_cost": co}
                state["stocks_note"] = (
                    f"{sym}: holding saved on this device.")
            state["holdings"] = h
            save_holdings(h)
            render_stocks()
        return _h

    def render_stocks_holdings(col):
        names = _stocks_names()
        out = [ft.Text(
            "Your positions, entered by you and stored only "
            "on this device. Values and P/L are computed from "
            "the pulled spot — never estimated. SELL stays "
            "WATCH for every name: no stock lane has passed "
            "its exam (S1/S5 FAILED-EXAM · S2/S3/S4 "
            "NOT-BUILT), so BetFi prints no sell signal and "
            "sizes no exit.", size=11, color=DIM, height=1.35)]
        for sym in STOCK_UNIVERSE:
            held = state["holdings"].get(sym) or {}
            bundle = names.get(sym) or {}
            spot = (bundle.get("quote") or {}).get(
                "spot_reference")
            sh_field = ft.TextField(
                label="Shares", width=110, text_size=13,
                value=(f"{held['shares']:g}"
                       if held.get("shares") else ""))
            cost_field = ft.TextField(
                label="Avg cost", width=110, text_size=13,
                value=(f"{held['avg_cost']:g}"
                       if held.get("avg_cost") else ""))
            rows = [ft.Row(spacing=8, vertical_alignment=
                           ft.CrossAxisAlignment.CENTER,
                           controls=[
                ft.Text(sym, size=14, color=INK,
                        weight=ft.FontWeight.BOLD, width=58),
                sh_field, cost_field,
                secondary_button(
                    "Save", _save_holding(sym, sh_field,
                                          cost_field))])]
            shares = held.get("shares") or 0
            cost = held.get("avg_cost") or 0
            if shares:
                if spot is not None and cost:
                    value = shares * spot
                    pl = shares * (spot - cost)
                    plpct = (spot / cost - 1.0) * 100.0
                    rows.append(ft.Text(
                        f"{shares:g} sh × {_fmt_money(spot)} "
                        f"= {_fmt_money(value)} · P/L "
                        f"{pl:+,.2f} ({plpct:+.1f}%) vs avg "
                        f"cost {_fmt_money(cost)} · SELL: "
                        f"WATCH (no examined lane)",
                        size=12,
                        color=EDGE_POS if pl >= 0 else EDGE_NEG))
                elif spot is not None:
                    rows.append(ft.Text(
                        f"{shares:g} sh × {_fmt_money(spot)} "
                        f"= {_fmt_money(shares * spot)} · "
                        f"enter an average cost to see P/L · "
                        f"SELL: WATCH (no examined lane)",
                        size=12, color=INK))
                else:
                    rows.append(ft.Text(
                        f"{shares:g} sh held · no stock pull "
                        f"yet — position value unknown, never "
                        f"estimated · SELL: WATCH (no examined "
                        f"lane)", size=12, color=DIM))
            out.append(ft.Container(
                bgcolor=CARD_BG, border=_border_all(1, HAIRLINE),
                border_radius=10, padding=10,
                content=ft.Column(spacing=4, controls=rows)))
        col.controls = out

    def render_stocks():
        with _UPDATE_LOCK:
            seg = state.get("stocks_seg") or "tape"
            if seg not in _STOCKS_COLS:
                seg = "tape"
            state["stocks_seg"] = seg
            stocks_seg_ctrl.selected = [seg]
            stocks_view.controls = [
                screen_title(
                    "Stocks",
                    "The market's own numbers — quotes, "
                    "realized vol, and the options-implied "
                    "distribution. No stock lane has passed "
                    "its exam, so every action is WATCH."),
                ft.Container(
                    gradient=HEADER_GRADIENT, border_radius=10,
                    padding=ft.Padding(
                        left=6, right=6, top=6, bottom=6),
                    content=stocks_seg_ctrl),
                ft.Row(spacing=8, vertical_alignment=
                       ft.CrossAxisAlignment.CENTER, controls=[
                           primary_button("Pull stocks",
                                          on_stocks_pull),
                           ft.Text(state.get("stocks_note")
                                   or "", size=11, color=DIM)]),
                stocks_switcher]
            stocks_switcher.content = _STOCKS_COLS[seg]
            {"tape": render_stocks_tape,
             "matrix": render_stocks_matrix,
             "options": render_stocks_options,
             "holdings": render_stocks_holdings}[seg](
                _STOCKS_COLS[seg])
            page.update()


    def _panel_entries():
        if not state["slate"]:
            return []
        _vs = ensure_verdicts() or []
        return [(m, v, market_edge_pts(m, v))
                for m, v in zip(state["slate"].get("markets", []),
                                _vs)]

    def _pull_stamp_line():
        rec = state["slate"] or {}
        text, _deg = stamp_of(state["slate"])
        pulled = rec.get("pulled_at") or "no pull yet"
        return f"Pull: {pulled} · {text}"

    def _chart_point(point):
        # a tapped landscape point / pairs chip: the detail line
        # names the market, and the pending Board jump is armed
        state["chart_detail"] = point["detail"]
        state["chart_board"] = point
        render_stage()

    def _card_chart(mkt):
        # card depth -> Charts: highlight this market's bar in
        # the model-vs-implied chart when it is in the top 40,
        # and say so honestly when it is not
        data = xii_chart_data(_panel_entries())
        key = chart_market_key(mkt)
        hit = next((p for p in data["pairs"]
                    if p["key"] == key), None)
        if hit is not None:
            state["chart_highlight"] = key
            state["chart_detail"] = hit["detail"]
            state["chart_board"] = hit
        else:
            state["chart_highlight"] = ""
            nm = bet_name(mkt)
            state["chart_detail"] = (
                f"{nm['selection']} · {nm['market']} — no bar to "
                f"highlight: the model-vs-implied chart draws "
                f"this pull's top 40 priced markets by edge, "
                f"and this market is not in it.")
            state["chart_board"] = None
        state["panel_segment"] = "charts"
        show("stage")

    # ---- cross-navigation (panel <-> Board, one level) ----

    def cross_nav_league(sport, league):
        state["nav_return"] = {
            "view": "stage",
            "segment": state.get("panel_segment") or "charts"}
        mkts = (state["slate"] or {}).get("markets", [])
        eff = league
        if league != sport and not any(
                m.get("sport") == sport
                and board_league_of(m) == league for m in mkts):
            # the fitted league key does not occur on this
            # pull (e.g. a season-named fit) — fall back to the
            # whole sport lane; the banner names the league
            # either way, and the count says what matched
            eff = sport
        state["league_filter"] = {
            "sport": sport, "league": eff,
            "label": league_label(sport, league)}
        # v12.4: the league's sport is also the board's sport
        # view (the dropdown replaced the per-sport switches).
        state["sport_view"] = sport
        state["search"] = ""
        search_field.value = ""
        state["card_limit"] = CARD_PAGE
        state["board_seg"] = "all"
        board_seg_ctrl.selected = ["all"]
        show("board")

    def cross_nav_market(point):
        state["nav_return"] = {"view": "stage",
                               "segment": "charts"}
        state["league_filter"] = None
        q = " ".join(x for x in (point.get("home"),
                                 point.get("away")) if x)
        state["search"] = q
        search_field.value = q
        # v12.4: point the board's sport view at the market's
        # sport (the dropdown replaced the per-sport switches).
        if point.get("sport"):
            state["sport_view"] = point.get("sport")
        state["card_limit"] = CARD_PAGE
        state["board_seg"] = "all"
        board_seg_ctrl.selected = ["all"]
        state["chart_board"] = None
        show("board")

    def nav_back():
        ret = state.pop("nav_return", None) or {}
        state["league_filter"] = None
        state["search"] = ""
        search_field.value = ""
        state["sport_view"] = DEFAULT_SPORT_VIEW
        if ret.get("view") == "stage":
            state["panel_segment"] = ret.get("segment") \
                or "charts"
            show("stage")
        else:
            show(ret.get("view") or "stage")

    def clear_league_filter():
        state["league_filter"] = None
        state["nav_return"] = None
        state["sport_view"] = DEFAULT_SPORT_VIEW
        render_cards()

    # ---- full-screen graph viewer ----
    # The sheet lives on page.overlay; its plotting area is an
    # InteractiveViewer (native pinch + pan in Flet 1.0.4) and
    # the zoom buttons rebuild the body at the shell factor —
    # both routes pass through viewer_zoom_clamp, so pinch and
    # buttons can never leave [1, 6].

    _viewer = {"ctrl": None}

    def _viewer_tap(detail):
        state["viewer_detail"] = detail
        _refresh_viewer()

    def _viewer_zoom(factor):
        if factor == 0:
            state["viewer_zoom"] = 1.0
        else:
            state["viewer_zoom"] = viewer_zoom_clamp(
                state["viewer_zoom"] * factor)
        _refresh_viewer()

    def _viewer_body(kind):
        entries = _panel_entries()
        if kind == "coverage":
            rec = state["slate"] or {}
            _txt, deg = stamp_of(state["slate"])
            return build_coverage_section(
                rec.get("markets", []), stamp=_pull_stamp_line(),
                stale=bool(deg and rec))
        if kind == "landscape":
            return build_edge_landscape(
                entries, zoom=state["viewer_zoom"],
                on_tap=_viewer_tap)
        return build_xii_charts(
            entries, zoom=state["viewer_zoom"], on_tap=_viewer_tap,
            detail=state["viewer_detail"],
            highlight=state["chart_highlight"])

    def _refresh_viewer():
        with _UPDATE_LOCK:
            kind = state.get("viewer_kind")
            ov = getattr(page, "overlay", None)
            if kind is None or ov is None:
                return
            title = {"charts": "Xii Charts — full screen",
                     "coverage": "Coverage — full screen",
                     "landscape": "Edge Landscape — full screen"}[kind]
            sheet = build_viewer_sheet(
                title, _pull_stamp_line(), state["viewer_zoom"],
                _viewer_body(kind), on_zoom=_viewer_zoom,
                on_close=lambda e: close_viewer(),
                detail=state["viewer_detail"]
                if kind == "landscape" else "")
            if _viewer["ctrl"] is not None and _viewer["ctrl"] in ov:
                ov[ov.index(_viewer["ctrl"])] = sheet
            else:
                ov.append(sheet)
            _viewer["ctrl"] = sheet
            page.update()

    def open_viewer(kind):
        state["viewer_kind"] = kind
        state["viewer_zoom"] = 1.0
        state["viewer_detail"] = ""
        _refresh_viewer()
        # v12.6: the viewer sheet settles open (scale
        # 0.96 -> 1.0, two-update) — zoom/tap refreshes
        # through _refresh_viewer never re-settle.
        if _viewer["ctrl"] is not None:
            _settle_in(page, _viewer["ctrl"],
                       scale_from=0.96, dur=240, dy=0.0)

    def close_viewer():
        with _UPDATE_LOCK:
            state["viewer_kind"] = None
            ov = getattr(page, "overlay", None)
            if ov is not None and _viewer["ctrl"] in ov:
                ov.remove(_viewer["ctrl"])
            _viewer["ctrl"] = None
            page.update()

    # ---- the four segment renderers ----

    def render_panel_charts(col):
        with _UPDATE_LOCK:
            col.controls = []
            col.controls.append(ft.Row(spacing=6, wrap=True, controls=[
                secondary_button(
                    "Full screen — charts",
                    lambda _e: open_viewer("charts")),
                secondary_button(
                    "Full screen — edge landscape",
                    lambda _e: open_viewer("landscape"))]))
            entries = _panel_entries()
            col.controls += build_xii_charts(
                entries, zoom=state["chart_zoom"], on_tap=_chart_tap,
                on_zoom=_chart_zoom, detail=state["chart_detail"],
                on_point=_chart_point,
                highlight=state["chart_highlight"])
            if state.get("chart_board"):
                p = state["chart_board"]
                col.controls.append(ft.Row(
                    spacing=8, wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(f"Selected: {p['label']}", size=12,
                                color=INK),
                        primary_button(
                            "Show on Board",
                            lambda _e: cross_nav_market(p))]))
            cands = protected_candidates()
            if cands:
                col.controls.append(ft.Divider(color=HAIRLINE))
                col.controls += build_slip_correlation(cands)

    def render_panel_coverage(col):
        with _UPDATE_LOCK:
            col.controls = []
            rec = state["slate"] or {}
            _txt, deg = stamp_of(state["slate"])
            col.controls += build_coverage_section(
                rec.get("markets", []),
                on_league=lambda s, l: cross_nav_league(s, l),
                stamp=_pull_stamp_line(), stale=bool(deg and rec),
                on_expand=lambda: open_viewer("coverage"))

    def render_panel_registry(col):
        with _UPDATE_LOCK:
            col.controls = build_registry_section(
                on_league=lambda s, l: cross_nav_league(s, l),
                stamp=_pull_stamp_line())

    def render_panel_instruments(col):
        with _UPDATE_LOCK:
            col.controls = []
            col.controls.append(section_header(
                "SNAPSHOT INSTRUMENTS — OPEN IN BROWSER", ACCENT))
            col.controls.append(ft.Text(
                f"Current pull: {_pull_stamp_line()}", size=11,
                color=FAINT, height=1.3))
            col.controls.append(ft.Text(
                "The lab's instruments below are SNAPSHOTS (each "
                "carries its label) and open full-screen via the "
                "browser route — they are not live charts and never "
                "pretend to be.", size=11, color=DIM, height=1.3))
            n, _total = instruments_bundled()
            if n == 0:
                col.controls.append(empty_full(
                    ft.Icons.VIEW_IN_AR,
                    "Instruments not bundled in this edition",
                    "This build shipped without the instruments "
                    "folder, so the shelf prints its state instead "
                    "of a dead list. The full BetFi Xii build "
                    "carries all 11."))
                return
            col.controls.append(stage_status)
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
                col.controls.append(section_header(
                    family.upper(), ACCENT))
                for inst in members:
                    col.controls.append(ft.Container(
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
                    col.controls.append(ft.Text(
                        STOCKS_SAMPLE_NOTE, size=10, color=FAINT,
                        height=1.35))

    def render_stage():
        with _UPDATE_LOCK:
            seg = state.get("panel_segment") or "charts"
            if seg not in _PANEL_COLS:
                seg = "charts"
            state["panel_segment"] = seg
            panel_seg_ctrl.selected = [seg]
            stage_view.controls = [screen_title(
                "Instruments",
                "One panel, four views of the same pull and the "
                "same fits: live charts, priced coverage, the "
                "snapshot instruments and the registry map."),
                # v12.1 texture: the segment bar wears the header
                # band, same family as the view titles.
                ft.Container(gradient=HEADER_GRADIENT,
                             border_radius=10,
                             padding=ft.Padding(
                                 left=6, right=6, top=6, bottom=6),
                             content=panel_seg_ctrl),
                panel_switcher]
            panel_switcher.content = _PANEL_COLS[seg]
            {"charts": render_panel_charts,
             "coverage": render_panel_coverage,
             "instruments": render_panel_instruments,
             "registry": render_panel_registry}[seg](
                _PANEL_COLS[seg])
            page.update()

    # ---------------- navigation ----------------

    def show(name: str):
        with _UPDATE_LOCK:
            state["view"] = name
            view_switcher.content = views[name]
            # v12.1: the back-to-top button belongs to the Board
            # only (see the assembly note — Flet 1.0.4's page-level
            # scroll exposes no position event to gate it on).
            try:
                if page.floating_action_button is not None:
                    page.floating_action_button.visible = (
                        name == "board")
            except Exception:
                pass
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
            elif name == "stocks":
                render_stocks()
            elif name == "more":
                render_more()
            elif name == "terms":
                render_terms()
            elif name == "equations":
                render_equations()
            elif name == "dev":
                render_dev()
            # v12.6 page transition: on top of the switcher's
            # fade, the incoming view settles in (two-update,
            # scale/offset only) — a view change you can feel
            # land, and the view is fully present either way.
            _settle_in(page, views[name])
            page.update()

    def on_nav(e):
        # v12.1 feel: a destination switch ticks + taps back.
        play_sound("tick")
        tap_haptic()
        show(TOP_VIEWS[e.control.selected_index])

    # ---------------- assembly ----------------

    # Frosted ice header (9d; artist §3.3): L2 gradient at
    # translucent stops over the field (Flet has no backdrop
    # blur — the frost is layered translucency, not a filter),
    # the XII badge (serif, keylined) + the two-tone lockup
    # (BetFi in bone, Xii in cyan, both w700 — artist §1), and
    # the live dot left of the pull stamp.
    header = ft.Container(
        gradient=FROST_GRADIENT,
        border=ft.Border(
            bottom=ft.BorderSide(1, HAIRLINE)),
        padding=ft.Padding(left=2, right=2, top=2, bottom=8),
        content=ft.Column(spacing=4, controls=[
            ft.Row(spacing=8, vertical_alignment=
                   ft.CrossAxisAlignment.CENTER, controls=[
                       ft.Container(
                           width=26, height=26, border_radius=7,
                           bgcolor=PANEL_RAISED_C,
                           border=_border_all(1, CYAN_DEEP),
                           alignment=ft.Alignment(0, 0),
                           content=ft.Text(
                               "XII", size=11, color=BONE,
                               weight=ft.FontWeight.BOLD,
                               font_family="Georgia")),
                       ft.Text("BetFi", size=22, color=BONE,
                               weight=ft.FontWeight.W_700),
                       ft.Text("Xii", size=22, color=ICE,
                               weight=ft.FontWeight.W_700)]),
            ft.Text(f"{DISPLAY_NAME} · engine {ENGINE_VERSION} · "
                    f"analysis only — never places a bet",
                    size=11, color=FAINT),
            ft.Row(spacing=6, vertical_alignment=
                   ft.CrossAxisAlignment.CENTER,
                   controls=[pull_dot, stamp_ctrl, stale_ctrl]),
        ]))
    search_field = ft.TextField(
        hint_text="Search teams, markets, leagues\u2026",
        prefix_icon=ft.Icons.SEARCH, text_size=13,
        on_change=on_search)
    # v12.1 texture: the board's working header rides in one
    # band (BOARD_HEADER_GRADIENT — the one header with accent
    # in the wash): the v12.3 sport chooser + scoped Pull /
    # Pull all actions, pull age, status, sort, search and
    # the clear-filters chip row.
    _board_controls = [
        ft.Container(
            gradient=BOARD_HEADER_GRADIENT, border_radius=12,
            border=ft.Border(bottom=ft.BorderSide(1, HAIRLINE)),
            padding=10,
            content=ft.Column(spacing=8, tight=True, controls=[
                ft.Row(spacing=8, controls=[
                    ft.Dropdown(
                        value=state["chosen_sport"], width=210,
                        options=[ft.DropdownOption(
                            key=k,
                            text=SPORT_LABELS.get(k, k.upper()))
                            for k in b5.FANDUEL_EVENT_TYPES],
                        on_select=on_sport_select),
                    primary_button("Pull", on_pull_sport)]),
                ft.Row(spacing=8, controls=[
                    secondary_button("Pull all", on_pull),
                    secondary_button("Price Slate", on_price)]),
                pull_age_ctrl,
                status,
                ft.Row(spacing=8, controls=[
                    ft.Icon(ft.Icons.SORT, size=18, color=ACCENT),
                    ft.Dropdown(
                        value=state["sort"], width=230,
                        options=[ft.DropdownOption(key=k, text=t)
                                 for k, t in SORT_MODES],
                        on_select=on_sort),
                    cards_count, cards_receipt]),
                # v12.4: the filter dropdowns — "Board shows"
                # (which sport of the accumulated board is on
                # screen) and "Show" (which markets pass),
                # where the switch wall used to live.
                ft.Row(spacing=8, controls=[
                    ft.Icon(ft.Icons.TUNE, size=18, color=ACCENT),
                    sport_view_dd,
                    show_dd]),
                search_field,
                filter_chip_row])),
        cards_list]
    cards_view.controls = _board_controls
    board_view.controls = [
        screen_title("Board",
                     "Every checked market on the current pull."),
        board_seg_ctrl,
        board_switcher]
    slip_view.controls = [
        screen_title("Slip", "The ticket tools — read a slip, "
                             "build a parlay, size a stake."),
        slip_seg_ctrl,
        slip_switcher,
        protected_view]
    page.add(header, view_switcher)

    nav_bar_cls = getattr(ft, "NavigationBar", None)
    nav_dest_cls = (getattr(ft, "NavigationDestination", None)
                    or getattr(ft, "NavigationBarDestination", None))
    if nav_bar_cls is not None and nav_dest_cls is not None:
        _dests = [
            nav_dest_cls(icon=ft.Icons.VIEW_AGENDA,
                         label="Board"),
            nav_dest_cls(icon=ft.Icons.RECEIPT_LONG,
                         label="Slip"),
            nav_dest_cls(icon=ft.Icons.LIST, label="Lab"),
            nav_dest_cls(icon=ft.Icons.VIEW_IN_AR,
                         label="3D"),
            nav_dest_cls(icon=ft.Icons.MORE_HORIZ,
                         label="More"),
            nav_dest_cls(icon=ft.Icons.SHOW_CHART,
                         label="Stocks"),
        ]
        page.navigation_bar = nav_bar_cls(
            selected_index=0, on_change=on_nav,
            destinations=_dests)
        # v12.1: the Slip destination carries the GOLDEN badge.
        _SLIP_DEST["dest"] = _dests[1]
        refresh_slip_badge()
    else:  # equivalent switch: a labelled button row
        page.add(ft.Row(spacing=8, wrap=True, controls=[
            pressify(ft.OutlinedButton(
                "Board",
                on_click=lambda _e: show("board")), sound="tick"),
            pressify(ft.OutlinedButton(
                "Slip",
                on_click=lambda _e: show("slip")), sound="tick"),
            pressify(ft.OutlinedButton(
                "Lab",
                on_click=lambda _e: show("lab")), sound="tick"),
            pressify(ft.OutlinedButton(
                "3D",
                on_click=lambda _e: show("stage")), sound="tick"),
            pressify(ft.OutlinedButton(
                "More",
                on_click=lambda _e: show("more")), sound="tick"),
            pressify(ft.OutlinedButton(
                "Stocks",
                on_click=lambda _e: show("stocks")), sound="tick"),
        ]))

    # v12.1 QoL: back-to-top on the Board. Flet 1.0.4's board is
    # a page-level scroll (no ListView, and Page exposes no
    # scroll-position event), so the button cannot honestly be
    # scroll-triggered: it lives on the Board view only, shown
    # by show(), and rides page.scroll_to home.
    try:
        page.floating_action_button = ft.FloatingActionButton(
            icon=ft.Icons.ARROW_UPWARD, mini=True,
            bgcolor=PANEL_RAISED_C, foreground_color=BONE,
            tooltip="Back to top",
            on_click=lambda _e: _scroll_top())
    except Exception:
        pass

    def _scroll_top():
        try:
            page.scroll_to(offset=0, duration=400,
                           curve=ft.AnimationCurve.EASE_OUT_CUBIC)
        except Exception:
            pass

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

    # ---- v12 startup: splash + auto-pull (real entry only) --
    # Everything in this block is gated on AUTO_PULL_ENABLED,
    # which only the __main__ entry sets: headless harnesses
    # build the same tree with no overlay, no pulse threads and
    # no network. The splash OVERLAYS the async load above — it
    # never gates first paint (the board is already painted
    # under it) and adds no second control tree (one overlay
    # container, ~8 controls).
    splash = {"ctrl": None}

    def dismiss_splash():
        ctrl = splash["ctrl"]
        if ctrl is None:
            return
        splash["ctrl"] = None
        stop_pulse("splash")

        def _remove():
            # v12.7.1: overlay removal + update ride the lock.
            with _UPDATE_LOCK:
                try:
                    page.overlay.remove(ctrl)
                except Exception:
                    pass
                try:
                    page.update()
                except Exception:
                    pass

        def _fade_out():
            # v12.7.1: the fade is an update like any other —
            # serialized through the one lock.
            with _UPDATE_LOCK:
                try:
                    ctrl.opacity = 0
                    ctrl.update()
                except Exception:
                    pass
        page.run_thread(_fade_out)
        # v12.4.1 hardening: removal is scheduled on a plain
        # Timer, NOT nested inside the fade — if the fade's
        # run_thread ever fails to land on device, the splash
        # still leaves the board. It can never sit on the app.
        threading.Timer(0.35, _remove).start()

    state["dismiss_splash"] = dismiss_splash
    if AUTO_PULL_ENABLED:
        try:
            splash["ctrl"] = build_splash()
            splash["ctrl"].on_click = lambda _e: dismiss_splash()
            page.overlay.append(splash["ctrl"])
            page.update()
            # v12.4 staging, hardened in v12.4.1: the emblem
            # settles in synchronously; the wordmark and the
            # gold sweep are BORN VISIBLE (final opacity/scale
            # at build) — an earlier design staged them from
            # opacity 0 via Timer threads, the same
            # invisible-until-async-restored pattern that hid
            # the board's cards on device. The splash reads
            # complete from its first painted frame; the whole
            # sequence self-resolves at ~1.4 s even if no pull
            # lands (a landed pull or a tap resolves it early).
            def _stage(part, **props):
                ctrl = _SPLASH_PARTS.get(part)
                if ctrl is None:
                    return
                for k, v in props.items():
                    setattr(ctrl, k, v)
                try:
                    ctrl.update()
                except Exception:
                    pass
            _stage("emblem", scale=ft.Scale(scale=1.0))
            threading.Timer(1.4, dismiss_splash).start()
            start_pulse("splash")
            start_pulse("shimmer")
            start_pulse("golden")
        except Exception:
            splash["ctrl"] = None
        threading.Thread(target=_auto_pull_loop, daemon=True).start()
    # v12.4: the startup sound — once per cold start, through
    # the same mute-respected, failure-silent play_sound as
    # every other sound in the app.
    play_sound("startup")
    refresh_stamp()


if __name__ == "__main__":
    AUTO_PULL_ENABLED = True
    ft.run(main)
