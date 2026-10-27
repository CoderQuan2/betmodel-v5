#!/usr/bin/env python3
"""fit_argentina_lnb.py — BetFi Xii pricing Build O: the
Argentina LNB fit builder.

Fits the Argentina LNB lane (FanDuel files its fixtures
under the "nba" page, competition "Argentina - LNB" —
8 markets on the saved slate) from REAL results:
RealGM's international league schedule pages
(basketball.realgm.com, league 58, "Argentinian
Liga A" — the LNB's top division), team-by-team over
the 2023-24 .. 2026-27 regular seasons. Source hunt,
in the house order: RealGM — VERIFIED by fetch
2026-10-27: the league 58 home page lists the Liga A's
clubs (Quimsa id 1004 — a slate club — La Union de
Formosa, Ciclista Olimpico, Gimnasia Indalo, ...), and
Quimsa's 2025-26 schedule page carries 51 real results
under the "Argentinian Liga A" venue label (e.g.
2025-09-28 Quimsa 99 - 71 Atletico Argentino de
Junin). Writes data/v5-argentina-lnb.json in the exact
v5-nba.json shape (plus the Greece A1 "teams" gloss),
via the shared machinery in tools/realgm_harvest.py
(sequential Elo K=20, HFA=100, un-tuned; regular
season only via the declared first-two-meetings rule;
walk-forward Brier exam vs the naive home-rate
baseline scored BEFORE any engine wiring).

Cache: data/cache/argentina_lnb_games_2023-27.json.
Usage: fit_argentina_lnb.py [out_path]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realgm_harvest

CFG = {"sport": "argentina-lnb",
       "label": "Argentinian Liga A",
       "league_id": 58, "league_slug": "Argentinian-Liga-A",
       "cache": "argentina_lnb_games_2023-27.json",
       "fit_file": "v5-argentina-lnb.json"}

if __name__ == "__main__":
    realgm_harvest.main(CFG)
