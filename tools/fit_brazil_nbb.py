#!/usr/bin/env python3
"""fit_brazil_nbb.py — BetFi Xii pricing Build O: the
Brazil NBB fit builder.

Fits the Brazil NBB lane (FanDuel files its fixtures
under the "nba" page, competition "Brazilian NBB" — 8
markets on the saved slate) from REAL results: RealGM's
international league schedule pages
(basketball.realgm.com, league 59, "Brazilian NBB"),
team-by-team over the 2023-24 .. 2026-27 regular
seasons. Source hunt, in the house order: RealGM —
VERIFIED by fetch 2026-10-27: the league 59 home page
lists the NBB's clubs (Mogi das Cruzes id 1288 —
a slate club — Basquete Cearense, Botafogo FR, ...),
and Mogi's 2025-26 schedule page carries 46 real
results under the "Brazilian NBB" venue label (e.g.
2025-10-25 Mogi 103 - 84 at Cruzeiro). Writes
data/v5-brazil-nbb.json in the exact v5-nba.json shape
(plus the Greece A1 "teams" gloss), via the shared
machinery in tools/realgm_harvest.py (sequential Elo
K=20, HFA=100, un-tuned; regular season only via the
declared first-two-meetings rule; walk-forward Brier
exam vs the naive home-rate baseline scored BEFORE any
engine wiring).

Cache: data/cache/brazil_nbb_games_2023-27.json.
Usage: fit_brazil_nbb.py [out_path]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realgm_harvest

CFG = {"sport": "brazil-nbb",
       "label": "Brazilian NBB",
       "league_id": 59, "league_slug": "Brazilian-NBB",
       "cache": "brazil_nbb_games_2023-27.json",
       "fit_file": "v5-brazil-nbb.json"}

if __name__ == "__main__":
    realgm_harvest.main(CFG)
