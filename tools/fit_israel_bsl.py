#!/usr/bin/env python3
"""fit_israel_bsl.py — BetFi Xii pricing Build O: the
Israel BSL fit builder.

Fits the Israel BSL lane (FanDuel files its fixtures
under the "nba" page, competition "Israel - BSL" — 16
markets on the saved slate) from REAL results: RealGM's
international league schedule pages
(basketball.realgm.com, league 11, "Israeli BSL"),
team-by-team over the 2023-24 .. 2026-27 regular
seasons. Source hunt, in the house order: RealGM —
VERIFIED by fetch 2026-10-27: the league 11 home page
lists the BSL's clubs (Maccabi FOX Tel Aviv id 4,
Hapoel Bank Yahav Jerusalem, Ironi Nes Ziona, Elitzur
Kiryat Ata, ...), and Maccabi's 2025-26 schedule page
carries its games under three distinct venue labels —
"Israeli BSL" (the league), "Euroleague" and "Israel
BSL Winner Cup" — so the declared label filter keeps
league fixtures only (2025-09-26 Winner Cup: Maccabi
69 - 79 Hapoel Jerusalem, excluded by label). Writes
data/v5-israel-bsl.json in the exact v5-nba.json shape
(plus the Greece A1 "teams" gloss), via the shared
machinery in tools/realgm_harvest.py (sequential Elo
K=20, HFA=100, un-tuned; regular season only via the
declared first-two-meetings rule; walk-forward Brier
exam vs the naive home-rate baseline scored BEFORE any
engine wiring).

Cache: data/cache/israel_bsl_games_2023-27.json.
Usage: fit_israel_bsl.py [out_path]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realgm_harvest

CFG = {"sport": "israel-bsl",
       "label": "Israeli BSL",
       "league_id": 11, "league_slug": "Israeli-BSL",
       "cache": "israel_bsl_games_2023-27.json",
       "fit_file": "v5-israel-bsl.json"}

if __name__ == "__main__":
    realgm_harvest.main(CFG)
