#!/usr/bin/env python3
"""fit_tennis.py — BetFi Xii (fix-guy R3): the tennis fit builder.

Fits the head-to-head tennis lane from REAL results, one Elo
model per tour:

  * ATP — Jeff Sackmann's match CSVs (atp_matches_<year>.csv,
    2015..2024). Sackmann deleted the original
    JeffSackmann/tennis_atp + tennis_wta repos from GitHub
    (verified 2026-10-24: the account lists only
    tennis_MatchChartingProject; the raw URLs 404). The CSVs
    survive in the public mirror bornamilkovic/ATP-Matches
    (data/atp_matches_<year>.csv, Sackmann schema verbatim —
    header verified against the documented schema).
  * WTA — the tennis-data.co.uk archive format
    (Date/Surface/Player_1/Player_2/Winner), mirrored at
    fmmarino1/wta-tennis (wta.csv). Player keys keep the
    archive's own form ("Swiatek I.") — the engine's WTA
    resolver maps FanDuel's full names onto them.

Model (per tour): sequential Elo, K=32, start 1500, NO home
edge (neutral venues). Walk-forward: every match is predicted
from ratings built ONLY on prior matches, then updated.
Backtest = Brier of those predictions vs a naive baseline
that predicts from the players' running career win rates
(p_A = wrA / (wrA + wrB), win rates shrunk with a 4-match
0.5 prior). Walkovers (score "W/O") are not contests and are
excluded; retirements count (the match was decided).

Surface ratings ride along: a parallel Elo per surface
(Hard/Clay/Grass/Carpet), updated only by matches on that
surface, with its own walk-forward block (predicting with the
surface rating when both players have >= 5 matches on the
surface, else the overall rating). The PRICED model is the
overall Elo: a FanDuel slate entry carries no surface, so
pricing off a surface rating would require guessing the
surface — the surface block is reported, never priced from.

Usage: fit_tennis.py [out_path]  (default ../data/v5-tennis.json)
Downloads are cached under /tmp/guy3 by default (re-runs are
offline); set TENNIS_SRC_DIR to a folder holding the CSVs.
"""
import csv
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

K = 32.0
START = 1500.0
ATP_YEARS = list(range(2015, 2025))
ATP_URL = ("https://raw.githubusercontent.com/bornamilkovic/"
           "ATP-Matches/main/data/atp_matches_{y}.csv")
WTA_URL = ("https://raw.githubusercontent.com/fmmarino1/"
           "wta-tennis/main/wta.csv")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
SRC_DIR = os.environ.get("TENNIS_SRC_DIR", "/tmp/guy3")


def fetch(url, name):
    path = os.path.join(SRC_DIR, name)
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        with open(path, encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8")
    os.makedirs(SRC_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def elo_p(ra, rb):
    return 1 / (1 + 10 ** (-(ra - rb) / 400))


def run_tour(matches):
    """matches: [(date_key, winner, loser, surface)] in
    chronological order. Returns the tour block."""
    elo, surf_elo, played, surf_played = {}, {}, {}, {}
    wins, games = {}, {}
    brier = naive_brier = 0.0
    s_brier = s_naive = 0.0
    n = s_n = correct = 0
    skipped_surface = {"Greenset": "Hard"}

    def wr(p):
        return (wins.get(p, 0) + 2.0) / (games.get(p, 0) + 4.0)

    for _d, w, l, surface in matches:
        surface = skipped_surface.get(surface, surface)
        rw, rl = elo.get(w, START), elo.get(l, START)
        p = elo_p(rw, rl)
        y = 1.0
        brier += (p - y) ** 2
        pn = wr(w) / (wr(w) + wr(l))
        naive_brier += (pn - y) ** 2
        n += 1
        if p >= 0.5:
            correct += 1
        # surface walk-forward (diagnostic block)
        sw = (surf_elo.get(surface) or {}).get(w)
        sl = (surf_elo.get(surface) or {}).get(l)
        pw = (surf_played.get(surface) or {}).get(w, 0)
        pl = (surf_played.get(surface) or {}).get(l, 0)
        ps = elo_p(sw, sl) if (sw is not None and sl is not None
                               and pw >= 5 and pl >= 5) else p
        s_brier += (ps - y) ** 2
        s_naive += (pn - y) ** 2
        s_n += 1
        # updates
        elo[w] = rw + K * (1 - p)
        elo[l] = rl + K * (0 - (1 - p))
        srat = surf_elo.setdefault(surface, {})
        sp = surf_played.setdefault(surface, {})
        sw2, sl2 = srat.get(w, START), srat.get(l, START)
        psurf = elo_p(sw2, sl2)
        srat[w] = sw2 + K * (1 - psurf)
        srat[l] = sl2 + K * (0 - (1 - psurf))
        sp[w] = sp.get(w, 0) + 1
        sp[l] = sp.get(l, 0) + 1
        for p_, won in ((w, 1), (l, 0)):
            played[p_] = played.get(p_, 0) + 1
            games[p_] = games.get(p_, 0) + 1
            wins[p_] = wins.get(p_, 0) + won
    bt = {"brier": round(brier / n, 4),
          "naive_brier": round(naive_brier / n, 4),
          "accuracy": round(correct / n, 4), "n": n,
          "protocol": "walk-forward (Elo from prior matches "
                      "only; naive = relative running career "
                      "win rate, 4-match 0.5 prior)"}
    sbt = {"brier": round(s_brier / s_n, 4),
           "naive_brier": round(s_naive / s_n, 4), "n": s_n,
           "protocol": "walk-forward; surface rating when both "
                       "players have >=5 matches on the surface, "
                       "else the overall rating. DIAGNOSTIC — "
                       "the priced model is the overall Elo "
                       "(a slate entry carries no surface)"}
    return {
        "elo": {p: round(elo[p], 1) for p in sorted(elo)},
        "surface_elo": {
            s: {p: round(r[p], 1) for p in sorted(r)}
            for s, r in sorted(surf_elo.items())},
        "matches": {p: played[p] for p in sorted(played)},
        "backtest": bt, "surface_backtest": sbt}


def collect_atp():
    out = []
    for y in ATP_YEARS:
        text = fetch(ATP_URL.format(y=y), f"atp_{y}.csv")
        for r in csv.DictReader(io.StringIO(text)):
            score = r.get("score") or ""
            if "W/O" in score:
                continue
            w, l = r.get("winner_name"), r.get("loser_name")
            if not w or not l:
                continue
            out.append(((r.get("tourney_date") or "",
                         int(r.get("match_num") or 0)),
                        w.strip(), l.strip(),
                        (r.get("surface") or "").strip()))
    out.sort(key=lambda m: m[0])
    return [(d, w, l, s) for (d, _mn), w, l, s in
            [(m[0], m[1], m[2], m[3]) for m in out]]


def collect_wta():
    text = fetch(WTA_URL, "wta.csv")
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            d = datetime.strptime((r.get("Date") or "")[:10],
                                  "%Y-%m-%d")
        except ValueError:
            continue
        if d.year < 2015:
            continue
        p1, p2, w = (r.get("Player_1") or "").strip(), \
            (r.get("Player_2") or "").strip(), \
            (r.get("Winner") or "").strip()
        if not p1 or not p2 or w not in (p1, p2):
            continue
        l = p2 if w == p1 else p1
        out.append((d.strftime("%Y%m%d"), w, l,
                    (r.get("Surface") or "").strip()))
    out.sort(key=lambda m: m[0])
    return out


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data",
        "v5-tennis.json")
    atp_matches = collect_atp()
    wta_matches = collect_wta()
    print(f"[fit-tennis] ATP matches: {len(atp_matches)} "
          f"WTA matches: {len(wta_matches)}")
    if len(atp_matches) < 10000 or len(wta_matches) < 10000:
        raise SystemExit("[fit-tennis] too few matches — "
                         "refusing to fit on partial pulls")
    blob = {
        "sport": "tennis",
        "fitted_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "source": ("ATP: Jeff Sackmann match CSVs via the "
                   "public mirror bornamilkovic/ATP-Matches "
                   "(data/atp_matches_2015..2024.csv — the "
                   "original JeffSackmann/tennis_atp repo was "
                   "deleted by its owner; mirror schema verified "
                   "Sackmann-verbatim). WTA: tennis-data.co.uk "
                   "archive format via fmmarino1/wta-tennis "
                   "(wta.csv, 2015+)"),
        "params": {"K": K, "start_elo": START,
                   "home_edge": 0.0,
                   "note": "priced model = overall Elo per "
                           "tour; surface ratings carried for "
                           "reporting (a slate entry carries "
                           "no surface)"},
        "tours": {
            "atp": dict(run_tour(atp_matches),
                        window="2015-2024 (mirror's last year)"),
            "wta": dict(run_tour(wta_matches),
                        window="2015+ (archive runs current)"),
        },
    }
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=1)
    for tour, blk in blob["tours"].items():
        bt = blk["backtest"]
        print(f"[fit-tennis] {tour}: players={len(blk['elo'])} "
              f"n={bt['n']} brier={bt['brier']} "
              f"naive={bt['naive_brier']} acc={bt['accuracy']} "
              f"surface_brier={blk['surface_backtest']['brier']}")
    print(f"[fit-tennis] wrote {out_path}")


if __name__ == "__main__":
    main()
