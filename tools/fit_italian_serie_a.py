#!/usr/bin/env python3
"""fit_italian_serie_a.py — BetFi Xii pricing Build L: the
Italian Serie A fit builder.

Fits the Italian Serie A lane (FanDuel files its fixtures
under the "nba" page, competition "Italian Serie A BB" —
12 markets on the saved slate) from REAL results: RealGM's
international league schedule pages (basketball.realgm.com,
league 6, "Italian Lega Basket Serie A"), team-by-team over
the 2023-24 .. 2026-27 regular seasons. Source hunt, in the
house order: the league's own site (legabasket.it embeds
championship metadata — Serie A RS championship ids 530 /
567 / 596 / 602 — but its /api/v1 origin is not publicly
reachable: direct calls return the JS shell or 404), ESPN
(the "lba" slug resolves to a "Lega Basket Serie A" stub
with an empty calendar and zero events on every date
probed), then the maintained public mirror — RealGM,
verified by fetch. Writes data/v5-italian-serie-a.json in
the exact v5-nba.json shape (plus the Greece A1 "teams"
gloss), via the shared machinery in
tools/realgm_harvest.py (sequential Elo K=20, HFA=100,
un-tuned; regular season only via the declared
ordered-pair rule; walk-forward Brier exam vs the naive
home-rate baseline scored BEFORE any engine wiring).

SOURCE IDENTITY NOTE (verified by fetch 2026-10-27):
RealGM's team registry hangs two wrong names on Serie A
ids — id 675 is glossed "Roma SPQR" and id 809 "Maxima
Roma" (both are 2025-26 EuroCup entrants), but each id's
schedule history under the Serie A label is one real
club's, every pulled season: id 675 plays at the Palasport
Ca' de Somenzi with Vanoli Cremona's rosters (Lacey /
Denegri / Pecchia in 2023-24, Booth / Owens / Davis in
2024-25, Durham in 2025-26) and id 809 at Brescia's Centro
Sportivo San Filippo with Germani Brescia's (Della Valle
across 2023-24 and 2025-26). The games and the id stream
are faithful — every season reconstructs as a complete
double round-robin — so the fit keys on the ids and the
gloss names the real clubs via NAME_OVERRIDES below.

Cache: data/cache/italian_serie_a_games_2023-27.json.
Usage: fit_italian_serie_a.py [out_path]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realgm_harvest

CFG = {"sport": "italian-serie-a",
       "label": "Italian Lega Basket Serie A",
       "league_id": 6, "league_slug": "Italian-Lega-Basket-Serie-A",
       "cache": "italian_serie_a_games_2023-27.json",
       "fit_file": "v5-italian-serie-a.json",
       "name_overrides": {"675": "Vanoli Cremona",
                          "809": "Germani Brescia"}}

if __name__ == "__main__":
    realgm_harvest.main(CFG)
