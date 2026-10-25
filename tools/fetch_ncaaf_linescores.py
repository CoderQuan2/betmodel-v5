#!/usr/bin/env python3
"""fetch_ncaaf_linescores.py — BetFi Xii (fix-guy R7
rebuild): ESPN FBS (groups=80) scoreboard day pulls for
the NCAAF segment exams.

The R6 original (/tmp/guy6/fetch_ncaaf.py) died with a
/tmp wipe during R7; this is its reconstruction from
the spec the R6 addendum + fit_segments.fetch_ncaaf
record: day pulls over the 2024 + 2025 seasons, every
event seen counted, games kept when completed with a
complete linescore (>= 4 periods for both sides), team
names recorded (abbrev -> ESPN displayName).

Outputs (into $BETFI_GUY6 or /tmp/guy6):
  ncaaf_games.json    [{id, date, home, away, h_ls,
                        a_ls, hs, as}]  (abbreviations)
  ncaaf_names.json    {abbrev: displayName}
  ncaaf_coverage.json {events, games_with_linescores,
                        pull_days, seasons}
"""
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

UA = {"User-Agent": "Mozilla/5.0 (BetFi research)"}
API = ("https://site.api.espn.com/apis/site/v2/sports/"
       "football/college-football/scoreboard")
OUT = os.environ.get("BETFI_GUY6", "/tmp/guy6")
WINDOWS = [(date(2024, 8, 24), date(2025, 1, 21)),
           (date(2025, 8, 23), date(2026, 1, 20))]


def _get(day):
    url = f"{API}?dates={day:%Y%m%d}&groups=80&limit=300"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    days = []
    for start, end in WINDOWS:
        d = start
        while d <= end:
            days.append(d)
            d += timedelta(days=1)
    print(f"pull days: {len(days)}", flush=True)
    events_seen = 0
    games, names, seen = [], {}, set()
    with ThreadPoolExecutor(max_workers=12) as ex:
        for blob in ex.map(_get, days):
            for ev in blob.get("events") or []:
                events_seen += 1
                if ev.get("id") in seen:
                    continue
                seen.add(ev.get("id"))
                st = ((ev.get("status") or {}).get("type")
                      or {})
                if not st.get("completed"):
                    continue
                comp = (ev.get("competitions") or [{}])[0]
                sides, ok = {}, True
                for c in comp.get("competitors") or []:
                    ls = [x.get("value")
                          for x in c.get("linescores") or []]
                    if len(ls) < 4 or any(v is None for v in ls):
                        ok = False
                        break
                    team = c.get("team") or {}
                    ab = team.get("abbreviation")
                    if not ab:
                        ok = False
                        break
                    names[ab] = team.get("displayName") or ab
                    sides[c["homeAway"]] = {
                        "team": ab, "ls": ls}
                if not ok or set(sides) != {"home", "away"}:
                    continue
                h, a = sides["home"], sides["away"]
                games.append({
                    "id": ev["id"], "date": ev["date"],
                    "home": h["team"], "away": a["team"],
                    "h_ls": h["ls"], "a_ls": a["ls"],
                    "hs": sum(h["ls"]), "as": sum(a["ls"])})
    games.sort(key=lambda g: g["date"])
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "ncaaf_games.json"), "w",
              encoding="utf-8") as f:
        json.dump(games, f)
    with open(os.path.join(OUT, "ncaaf_names.json"), "w",
              encoding="utf-8") as f:
        json.dump(names, f, indent=1)
    cov = {"events": events_seen,
           "games_with_linescores": len(games),
           "pull_days": len(days),
           "seasons": "2024+2025 (ESPN FBS groups=80)"}
    with open(os.path.join(OUT, "ncaaf_coverage.json"), "w",
              encoding="utf-8") as f:
        json.dump(cov, f, indent=1)
    print(f"events seen {events_seen}, games with complete "
          f"linescores {len(games)}, teams {len(names)}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
