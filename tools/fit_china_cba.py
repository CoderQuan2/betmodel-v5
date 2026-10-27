#!/usr/bin/env python3
"""fit_china_cba.py — BetFi Xii pricing Build O: the China
CBA fit builder.

Fits the China CBA lane (FanDuel files its fixtures under
the "nba" page, competition "China - CBA" — 8 markets on
the saved slate; the checker today stamps them through
OTHER_COMPETITION_TEAMS, "competition not in this app:
CBA (China)") from REAL results: RealGM's international
league schedule pages (basketball.realgm.com, league 40,
"Chinese CBA"), team-by-team over the 2023-24 .. 2026-27
regular seasons. Source hunt, in the house order: RealGM
covers China (the brief's named lead for this league) —
VERIFIED by fetch 2026-10-27: the league 40 home page
lists the CBA's clubs (Guangdong Dongguan id 14, Sichuan
Blue Whales, Nanjing Tongxi Monkey King, Beijing
BeiKong, ...), and Guangdong's schedule pages carry real
results under the "Chinese CBA" venue label (2025-26:
48 rows, e.g. 2025-12-14 Guangdong 107 - 102 Nanjing
Tongxi; 2024-25: 52 rows). Writes
data/v5-china-cba.json in the exact v5-nba.json shape
(plus the Greece A1 "teams" gloss), via the shared
machinery in tools/realgm_harvest.py (sequential Elo
K=20, HFA=100, un-tuned; regular season only via the
declared first-two-meetings rule — the CBA regular season
adds intra-group return fixtures beyond the double
round-robin, and the rule keeps the chronological first
two meetings of each pair, all of which are regular-
season games because the playoffs start only after the
regular season ends; walk-forward Brier exam vs the
naive home-rate baseline scored BEFORE any engine
wiring).

Cache: data/cache/china_cba_games_2023-27.json.
Usage: fit_china_cba.py [out_path]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realgm_harvest

CFG = {"sport": "china-cba",
       "label": "Chinese CBA",
       "league_id": 40, "league_slug": "Chinese-CBA",
       "cache": "china_cba_games_2023-27.json",
       "fit_file": "v5-china-cba.json"}

if __name__ == "__main__":
    realgm_harvest.main(CFG)
