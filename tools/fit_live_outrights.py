"""Build the LIVE EPL outright artifact for the current
season: played fixtures from ESPN day pulls, strengths
re-fitted in-season under the SAME protocol as the pilot
(shrinkage toward the league mean with the league's own
lambda), the remaining 380-fixture schedule simulated
20,000 times, title shares written into
data/v5-outrights.json's live block.

The shipped league fit is last season's full-season fit;
a mid-season outright must be simulated from CURRENT
strengths, so strengths are estimated from played games
only (same estimator, same shrinkage per goal count).
Nothing about the pilot's backtest changes.

Usage: fit_live_outrights.py [espn_league=eng.1] [season_year=2026]
"""
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fit_outrights import (fit_strengths, play_match,  # noqa: E402
                           champion_probs, fetch_day)

CACHE = "/tmp/guy5/livefix"


def main():
    league = sys.argv[1] if len(sys.argv) > 1 else "eng.1"
    year = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    # ESPN season window: Aug (year) .. May (year+1)
    days = []
    y, mo = year, 8
    while (y, mo) <= (year + 1, 5):
        days.append((y, mo))
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1
    played, remaining = {}, {}
    import datetime
    for (yy, mm) in days:
        ndays = [31, 29 if yy % 4 == 0 else 28, 31, 30, 31, 30,
                 31, 31, 30, 31, 30, 31][mm - 1]
        for dd in range(1, ndays + 1):
            d = f"{yy}{mm:02d}{dd:02d}"
            data = fetch_day(league, d, CACHE)
            for ev in (data or {}).get("events") or []:
                comp = (ev.get("competitions") or [{}])[0]
                cs = comp.get("competitors") or []
                if len(cs) != 2:
                    continue
                home = next((c for c in cs
                             if c.get("homeAway") == "home"),
                            None)
                away = next((c for c in cs
                             if c.get("homeAway") == "away"),
                            None)
                if not home or not away:
                    continue
                hc = (home.get("team") or {}).get(
                    "abbreviation")
                ac = (away.get("team") or {}).get(
                    "abbreviation")
                if not hc or not ac:
                    continue
                st = ((ev.get("status") or {}).get("type")
                      or {}).get("name", "")
                try:
                    hs = int(home.get("score"))
                    as_ = int(away.get("score"))
                except (TypeError, ValueError):
                    hs = as_ = None
                key = (hc, ac)
                if st == "STATUS_FULL_TIME" and hs is not None:
                    played[key] = (hs, as_)
                elif hs is None:
                    remaining[key] = True
    fx = [(h, a, g[0], g[1]) for (h, a), g in played.items()]
    teams = sorted({t for f in fx for t in f[:2]}
                   | {t for k in remaining for t in k})
    lh, la, att, dfn = fit_strengths(fx, teams)
    base = {t: [0, 0, 0] for t in teams}
    for h, a, hg, ag in fx:
        if hg > ag:
            base[h][0] += 3
        elif hg < ag:
            base[a][0] += 3
        else:
            base[h][0] += 1
            base[a][0] += 1
        base[h][1] += hg - ag
        base[a][1] += ag - hg
        base[h][2] += hg
        base[a][2] += ag
    rem = [(h, a) for (h, a) in remaining]
    probs = champion_probs(base, rem, lh, la, att, dfn,
                           sims=20000, seed=99)
    out_path = os.path.join(HERE, "..", "data",
                            "v5-outrights.json")
    with open(out_path, encoding="utf-8") as f:
        doc = json.load(f)
    doc["leagues"]["epl"].update({
        "status": "FITTED",
        "shares": probs,
        "played": len(fx),
        "remaining": len(rem),
        "sims": 20000,
        "source": f"ESPN {league} 2026-27 day pulls "
                  f"({len(fx)} played, {len(rem)} "
                  "remaining); strengths refit in-season "
                  "on played games with the pilot's "
                  "shrinkage protocol; shipped fit "
                  "untouched"})
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print(f"played={len(fx)} remaining={len(rem)} "
          f"teams={len(teams)}")
    print({k: round(v, 4) for k, v in
           sorted(probs.items(), key=lambda kv: -kv[1])
           if v > 0})


if __name__ == "__main__":
    main()
