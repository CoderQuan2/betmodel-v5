#!/usr/bin/env python3
"""fit_cricket.py — BetFi Xii (fix-guy R4): the cricket fits.

Source: Cricsheet (cricsheet.org) — the public ball-by-ball
archive. This builder uses only each match's *_info.csv from
all_csv2.zip (23,132 matches at build time) and classifies every
match into exactly one lane by the archive's OWN fields
(team_type / match_type / event / gender):

  t20i_m / t20i_f   team_type=international, match_type IT20/T20
  odi_m / odi_f     team_type=international, match_type ODI
                    (ICC CWC League 2 matches are ODI-status and
                    land here through the same fields)
  test_m            team_type=international, match_type Test
  lista_m           event = ICC Cricket World Cup Challenge
                    League (List A, NOT ODI status — its own
                    lane, never borrowed ODI ratings)
  ipl               event = Indian Premier League
  bbl               event = Big Bash League
  wbbl              event = Women's Big Bash League
  csa_t20           event = CSA T20 Challenge (incl. its
                    predecessor name, Ram Slam T20 Challenge)

Model per lane: sequential Elo, K=20, start 1500, no home edge
(Cricsheet's team1/team2 is not a reliable home designation and
internationals are frequently neutral-venue). Walk-forward:
every match predicted from ratings built ONLY on prior matches.
Naive baseline: running win rates with a 4-match 0.5 prior
(p = wrA/(wrA+wrB)), the tennis builder's baseline.

Limited-overs lanes: tied matches count 0.5/0.5 for the update
and are excluded from the Brier (the market has no tie leg);
no-result matches are excluded entirely.
Test lane: THREE-WAY. p_decisive from Elo; p_draw = the lane's
running draw rate (prior 0.30, weight 20 matches); exam =
3-way Brier vs a naive 3-way built the same way from running
win rates. The engine prices the FanDuel Draw runner from
p_draw and the side runners from (1 - p_draw) * p_decisive.

Usage: fit_cricket.py [out_path] (default ../data/v5-cricket.json)
The zip is cached under /tmp/guy4 (re-runs offline); set
CRICSHEET_ZIP to a local all_csv2.zip to skip the download.
"""
import csv
import io
import json
import os
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone

K = 20.0
START = 1500.0
ZIP_URL = "https://cricsheet.org/downloads/all_csv2.zip"
UA = {"User-Agent": "Mozilla/5.0"}
SRC = os.environ.get("CRICSHEET_ZIP", "/tmp/guy4/all_csv2.zip")


def load_matches():
    if not os.path.exists(SRC):
        os.makedirs(os.path.dirname(SRC), exist_ok=True)
        req = urllib.request.Request(ZIP_URL, headers=UA)
        with urllib.request.urlopen(req, timeout=600) as resp:
            with open(SRC, "wb") as f:
                f.write(resp.read())
    matches = []
    with zipfile.ZipFile(SRC) as z:
        for name in z.namelist():
            if not name.endswith("_info.csv"):
                continue
            info = {}
            teams = []
            dates = []
            text = z.read(name).decode("utf-8")
            for row in csv.reader(io.StringIO(text)):
                if len(row) < 3 or row[0] != "info":
                    continue
                if row[1] == "team":
                    teams.append(row[2])
                elif row[1] == "date":
                    dates.append(row[2])
                else:
                    info[row[1]] = row[2]
            if len(teams) != 2 or not dates:
                continue
            matches.append({
                "date": min(dates), "teams": teams,
                "winner": info.get("winner"),
                "match_type": info.get("match_type"),
                "team_type": info.get("team_type"),
                "event": info.get("event") or "",
                "gender": info.get("gender")})
    matches.sort(key=lambda m: m["date"])
    return matches


def lane_of(m):
    ev = m["event"]
    g = "f" if m["gender"] == "female" else "m"
    if "Challenge League" in ev:
        return "lista_m"
    if m["team_type"] == "international":
        if m["match_type"] in ("IT20", "T20"):
            return f"t20i_{g}"
        if m["match_type"] == "ODI":
            return f"odi_{g}"
        if m["match_type"] == "Test":
            return f"test_{g}"
        return None
    if ev == "Indian Premier League":
        return "ipl"
    if ev == "Big Bash League":
        return "bbl"
    if ev == "Women's Big Bash League":
        return "wbbl"
    if ev in ("CSA T20 Challenge", "Ram Slam T20 Challenge"):
        return "csa_t20"
    return None


def elo_p(ra, rb):
    return 1 / (1 + 10 ** (-(ra - rb) / 400))


def run_lane(matches, three_way=False):
    elo, wins, games = {}, {}, {}
    draws = decided = 0
    brier = naive_brier = 0.0
    n = correct = 0

    def wr(t):
        return (wins.get(t, 0) + 2.0) / (games.get(t, 0) + 4.0)

    def draw_rate():
        return (draws + 0.30 * 20) / (decided + draws + 20)

    for m in matches:
        a, b = m["teams"]
        w = m["winner"]
        if w in (None, "", "no result"):
            # Cricsheet records a DRAWN Test with no winner
            # field at all (verified across the archive: 179
            # winner-less Tests, zero literal 'draw' winners).
            # In the three-way lane that IS the draw outcome;
            # in limited-overs lanes a winner-less match is a
            # no-result and stays excluded.
            if three_way:
                w = "draw"
            else:
                continue
        ra, rb = elo.get(a, START), elo.get(b, START)
        p_a = elo_p(ra, rb)
        pn_a = wr(a) / (wr(a) + wr(b))
        if three_way:
            pd = draw_rate()
            pred = {a: (1 - pd) * p_a, b: (1 - pd) * (1 - p_a),
                    "draw": pd}
            predn = {a: (1 - pd) * pn_a, b: (1 - pd) * (1 - pn_a),
                     "draw": pd}
            out = w if w in (a, b) else "draw"
            brier += sum((pred[k] - (1.0 if k == out else 0.0)) ** 2
                         for k in pred)
            naive_brier += sum(
                (predn[k] - (1.0 if k == out else 0.0)) ** 2
                for k in predn)
            n += 1
            if max(pred, key=pred.get) == out:
                correct += 1
            if out == "draw":
                draws += 1
            else:
                decided += 1
                elo[w] = elo.get(w, START) + K * (
                    1 - (p_a if w == a else 1 - p_a))
                loser = b if w == a else a
                elo[loser] = elo.get(loser, START) + K * (
                    0 - (p_a if loser == a else 1 - p_a))
                wins[w] = wins.get(w, 0) + 1
                games[a] = games.get(a, 0) + 1
                games[b] = games.get(b, 0) + 1
            continue
        if w == "tie":
            elo[a] = ra + K * (0.5 - p_a)
            elo[b] = rb + K * (0.5 - (1 - p_a))
            games[a] = games.get(a, 0) + 1
            games[b] = games.get(b, 0) + 1
            continue
        if w not in (a, b):
            continue
        y = 1.0 if w == a else 0.0
        brier += (p_a - y) ** 2
        naive_brier += (pn_a - y) ** 2
        n += 1
        if (p_a >= 0.5) == (y == 1.0):
            correct += 1
        elo[a] = ra + K * (y - p_a)
        elo[b] = rb + K * ((1 - y) - (1 - p_a))
        wins[w] = wins.get(w, 0) + 1
        games[a] = games.get(a, 0) + 1
        games[b] = games.get(b, 0) + 1
    out = {"ratings": {t: round(r, 2) for t, r in elo.items()},
           "games": games,
           "backtest": {
               "n": n,
               "brier": round(brier / n, 4) if n else None,
               "naive_brier": round(naive_brier / n, 4) if n else None,
               "accuracy": round(correct / n, 4) if n else None}}
    if three_way:
        out["draw_rate"] = round(draw_rate(), 4)
        out["draws"] = draws
        out["decided"] = decided
    return out


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "data", "v5-cricket.json")
    matches = load_matches()
    lanes = {}
    for m in matches:
        lane = lane_of(m)
        if lane:
            lanes.setdefault(lane, []).append(m)
    fit = {"fitted_at": datetime.now(timezone.utc).isoformat(),
           "source": ("Cricsheet (cricsheet.org) all_csv2.zip "
                      "match info files — public ball-by-ball "
                      "archive; lanes classified by the archive's "
                      "own team_type/match_type/event fields"),
           "model": (f"sequential Elo K={K:g}, start {START:g}, "
                     "no home edge; test lane three-way with a "
                     "running draw rate"),
           "lanes": {}}
    for lane, ms in sorted(lanes.items()):
        blk = run_lane(ms, three_way=lane.startswith("test"))
        blk["n_matches"] = len(ms)
        fit["lanes"][lane] = blk
        bt = blk["backtest"]
        print(f"{lane}: n={bt['n']} brier={bt['brier']} "
              f"naive={bt['naive_brier']} acc={bt['accuracy']} "
              f"teams={len(blk['ratings'])}")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fit, f, indent=1)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
