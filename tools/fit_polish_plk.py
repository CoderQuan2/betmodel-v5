#!/usr/bin/env python3
"""fit_polish_plk.py — BetFi Xii pricing Build O: the
Polish PLK fit builder.

Fits the Polish PLK lane (FanDuel files its fixtures
under the "nba" page, competition "Polish PLK" — 4
markets on the saved slate) from REAL results:
RealGM's international league schedule pages
(basketball.realgm.com, league 21, "Polish OBL" — the
Orlen Basket Liga, the PLK under its sponsored name),
team-by-team over the 2023-24 .. 2026-27 regular
seasons. Source hunt, in the house order: RealGM —
VERIFIED by fetch 2026-10-27: the league 21 home page
lists the league's clubs (Legia Warszawa id 1858,
Dziki Warszawa, Start Lublin, ...), and Legia's
2025-26 schedule page carries its games under distinct
venue labels — "Polish OBL" (the league), "Basketball
Champions League Europe" and "Polish Mens Cup" — so
the declared label filter keeps league fixtures only
(2025-10-03 Legia 90 - 68 Start Lublin, Polish OBL).
Writes data/v5-polish-plk.json in the exact v5-nba.json
shape (plus the Greece A1 "teams" gloss), via the
shared machinery in tools/realgm_harvest.py
(sequential Elo K=20, HFA=100, un-tuned; regular
season only via the declared first-two-meetings rule;
walk-forward Brier exam vs the naive home-rate
baseline scored BEFORE any engine wiring).

Cache: data/cache/polish_plk_games_2023-27.json.
Usage: fit_polish_plk.py [out_path]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realgm_harvest

CFG = {"sport": "polish-plk",
       "label": "Polish OBL",
       "league_id": 21, "league_slug": "Polish-OBL",
       "cache": "polish_plk_games_2023-27.json",
       "fit_file": "v5-polish-plk.json"}

if __name__ == "__main__":
    realgm_harvest.main(CFG)
