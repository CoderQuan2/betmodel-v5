#!/usr/bin/env python3
"""fit_british_slb.py — BetFi Xii pricing Build O: the
British SLB fit builder.

Fits the British SLB lane (FanDuel files its fixtures
under the "nba" page, competition "British SLB" — 2
markets on the saved slate; the checker today stamps
them through OTHER_COMPETITION_TEAMS, "competition not
in this app: British Basketball League") from REAL
results: RealGM's international league schedule pages
(basketball.realgm.com, league 161, "Super League
Basketball" — the British top flight since 2024-25,
when it succeeded the BBL), team-by-team over the
2024-25 .. 2026-27 regular seasons. Source hunt, in
the house order: RealGM — VERIFIED by fetch
2026-10-27: the league 161 home page lists the SLB's
clubs (Surrey 89ers id 2787 — a slate club — Bristol
Flyers, Manchester Basketball, ...), and Surrey's
schedule pages carry 34 real results per season under
the "Super League Basketball" venue label (2025-26:
e.g. 2025-09-27 Surrey 94 - 80 Manchester). RealGM
files the SLB's Championship, Trophy and Cup under
the one league label, so the declared
first-two-meetings rule is the regular-season proxy
here (the Build L declared rule, unmodified): the
chronological first two meetings of each pair are
kept, later cup/playoff return meetings excluded.
The league did not exist in 2023-24 (the BBL's last
season, filed under RealGM league 69), so the fit's
window starts 2024-25 and season_label says so.
Writes data/v5-british-slb.json in the exact
v5-nba.json shape (plus the Greece A1 "teams" gloss),
via the shared machinery in tools/realgm_harvest.py
(sequential Elo K=20, HFA=100, un-tuned; walk-forward
Brier exam vs the naive home-rate baseline scored
BEFORE any engine wiring).

Cache: data/cache/british_slb_games_2023-27.json.
Usage: fit_british_slb.py [out_path]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realgm_harvest

CFG = {"sport": "british-slb",
       "label": "Super League Basketball",
       "league_id": 161,
       "league_slug": "Super-League-Basketball",
       "cache": "british_slb_games_2023-27.json",
       "fit_file": "v5-british-slb.json",
       "season_label": "2024-25 to 2026-27 regular seasons"}

if __name__ == "__main__":
    realgm_harvest.main(CFG)
