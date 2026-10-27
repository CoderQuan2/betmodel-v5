#!/usr/bin/env python3
"""fit_turkish_bsl.py — BetFi Xii pricing Build L: the
Turkish BSL fit builder.

Fits the Turkish BSL lane (FanDuel files its fixtures under
the "nba" page, competition "Turkish TBSL" — 2 markets on
the saved slate) from REAL results: RealGM's international
league schedule pages (basketball.realgm.com, league 7,
"Turkish BSL"), team-by-team over the 2023-24 .. 2026-27
regular seasons. Source hunt, in the house order: the
federation's own site (tbf.org.tr does not answer from this
machine — connection fails outright), ESPN (no Turkish
basketball league resolves: every slug probed 400s), then
the maintained public mirror — RealGM, verified by fetch.
Writes data/v5-turkish-bsl.json in the exact v5-nba.json
shape (plus the Greece A1 "teams" gloss), via the shared
machinery in tools/realgm_harvest.py (sequential Elo K=20,
HFA=100, un-tuned; regular season only via the declared
ordered-pair rule; walk-forward Brier exam vs the naive
home-rate baseline scored BEFORE any engine wiring).

Cache: data/cache/turkish_bsl_games_2023-27.json.
Usage: fit_turkish_bsl.py [out_path]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realgm_harvest

CFG = {"sport": "turkish-bsl", "label": "Turkish BSL",
       "league_id": 7, "league_slug": "Turkish-BSL",
       "cache": "turkish_bsl_games_2023-27.json",
       "fit_file": "v5-turkish-bsl.json"}

if __name__ == "__main__":
    realgm_harvest.main(CFG)
