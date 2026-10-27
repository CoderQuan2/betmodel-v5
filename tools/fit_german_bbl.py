#!/usr/bin/env python3
"""fit_german_bbl.py — BetFi Xii pricing Build L: the
German BBL fit builder.

Fits the German BBL lane (FanDuel files its fixtures under
the "nba" page, competition "German BBL" — 6 markets on the
saved slate) from REAL results: RealGM's international
league schedule pages (basketball.realgm.com, league 15,
"German BBL"), team-by-team over the 2023-24 .. 2026-27
regular seasons. Source hunt, in the house order: the
league's own site (easycredit-bbl.de — the schedule path
404s and no public results API is exposed), ESPN (no German
basketball league resolves: every slug probed 400s), then
the maintained public mirror — RealGM, verified by fetch.
Writes data/v5-german-bbl.json in the exact v5-nba.json
shape (plus the Greece A1 "teams" gloss), via the shared
machinery in tools/realgm_harvest.py (sequential Elo K=20,
HFA=100, un-tuned; regular season only via the declared
ordered-pair rule; walk-forward Brier exam vs the naive
home-rate baseline scored BEFORE any engine wiring).

Cache: data/cache/german_bbl_games_2023-27.json.
Usage: fit_german_bbl.py [out_path]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realgm_harvest

CFG = {"sport": "german-bbl", "label": "German BBL",
       "league_id": 15, "league_slug": "German-BBL",
       "cache": "german_bbl_games_2023-27.json",
       "fit_file": "v5-german-bbl.json"}

if __name__ == "__main__":
    realgm_harvest.main(CFG)
