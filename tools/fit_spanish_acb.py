#!/usr/bin/env python3
"""fit_spanish_acb.py — BetFi Xii pricing Build L: the
Spanish ACB fit builder.

Fits the Spanish ACB lane (FanDuel files its fixtures under
the "nba" page, competition "Spanish ACB" — 4 markets on the
saved slate) from REAL results: RealGM's international
league schedule pages (basketball.realgm.com, league 4),
team-by-team over the 2023-24 .. 2026-27 regular seasons.
Source hunt, in the house order: the league's own site
(acb.com is a JS shell with no reachable results API from
this machine), ESPN (the "acb" slug resolves to an
"ACB Copa del Rey" stub with an empty calendar and zero
events on every date probed — the EuroLeague empty-shell
pattern), then the maintained public mirror — RealGM,
verified by fetch (e.g. the league home page on 2026-10-27
lists Real Madrid at Forca Lleida CE, played 2026-10-25 —
the slate's own fixture). Writes data/v5-spanish-acb.json
in the exact v5-nba.json shape (plus the Greece A1 "teams"
gloss), via the shared machinery in tools/realgm_harvest.py:

  * sequential Elo, K=20, HFA=100 (the NBA lane's ENGINE
    PARAMS, un-tuned), NBA MOV multiplier, ratings carried
    across seasons; REGULAR SEASON only via the declared
    ordered-pair rule (see realgm_harvest.py).
  * walk-forward exam scored BEFORE any engine wiring:
    Brier vs the naive home-rate baseline; the lane prices
    only if Brier < naive.

Cache: data/cache/spanish_acb_games_2023-27.json.
Usage: fit_spanish_acb.py [out_path]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realgm_harvest

CFG = {"sport": "spanish-acb", "label": "Spanish ACB",
       "league_id": 4, "league_slug": "Spanish-ACB",
       "cache": "spanish_acb_games_2023-27.json",
       "fit_file": "v5-spanish-acb.json"}

if __name__ == "__main__":
    realgm_harvest.main(CFG)
