#!/usr/bin/env python3
"""fit_mma.py — BetFi Xii (fix-guy R3): the MMA fit builder.

Fits the UFC moneyline lane from REAL completed-fight records:
raw_total_fight_data.csv — the ufcstats.com scrape published
as the Kaggle dataset rajeevratan84/ufcdata, mirrored on
GitHub at pantazos/kaggle-UFC-data-CSV (semicolon-delimited;
R_fighter / B_fighter / Winner / date / Fight_type / win_by
per fight, 1993..2021 in this snapshot).

Model: sequential fighter Elo, K=32, start 1500, NO home
edge (neutral cage; the slate's "home" slot is just the
first-named fighter). Walk-forward by event date: every
fight is predicted from ratings built ONLY on prior fights,
then updated. Backtest = Brier of those predictions vs a
naive baseline from the fighters' running career win rates
(p_A = wrA / (wrA + wrB), 4-fight 0.5 prior). Rows with no
recorded winner (draws / no-contests — 110 in the snapshot)
are not decided contests and are excluded from both the
ratings and the backtest, counted here.

Each fighter's last-seen weight class (parsed from
Fight_type) and career W/L in the snapshot ride along for
the registry/report — the priced math is the single Elo
(weight-class context was considered; with ~2 fights per
fighter-year a per-class split starves the ratings, so the
class is carried as context, not a second rating).

Freshness, stated plainly: the mirror's snapshot ends in
2021. Fighters who debuted after it are not in this fit
and will stamp player-not-in-fit until a fresher source is
wired — the ratings are real, the gap is named.

Usage: fit_mma.py [out_path]  (default ../data/v5-mma.json)
Download cached under /tmp/guy3 (MMA_SRC_DIR to override).
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
URL = ("https://raw.githubusercontent.com/pantazos/"
       "kaggle-UFC-data-CSV/master/raw_total_fight_data.csv")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
SRC_DIR = os.environ.get("MMA_SRC_DIR", "/tmp/guy3")


def weight_class(fight_type):
    t = (fight_type or "").strip()
    for pre in ("UFC ", "WSOF ", "Strikeforce "):
        if t.startswith(pre):
            t = t[len(pre):]
    for suf in (" Title Bout", " Bout", " Championship"):
        if t.endswith(suf):
            t = t[:-len(suf)]
    return t.strip() or "Unknown"


def collect():
    path = os.path.join(SRC_DIR, "raw_total_fight_data.csv")
    if os.path.exists(path) and os.path.getsize(path) > 100000:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    else:
        req = urllib.request.Request(URL, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8")
        os.makedirs(SRC_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    fights, skipped = [], 0
    for r in csv.DictReader(io.StringIO(text), delimiter=";"):
        w = (r.get("Winner") or "").strip()
        rf, bf = (r.get("R_fighter") or "").strip(), \
            (r.get("B_fighter") or "").strip()
        if w not in (rf, bf) or not rf or not bf:
            skipped += 1
            continue
        try:
            d = datetime.strptime((r.get("date") or "").strip(),
                                  "%B %d, %Y")
        except ValueError:
            skipped += 1
            continue
        loser = bf if w == rf else rf
        fights.append((d.strftime("%Y%m%d"), w, loser,
                       weight_class(r.get("Fight_type")),
                       (r.get("win_by") or "").strip()))
    fights.sort(key=lambda f: f[0])
    return fights, skipped


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data",
        "v5-mma.json")
    fights, skipped = collect()
    print(f"[fit-mma] decided fights: {len(fights)} "
          f"(skipped undecided/unparseable: {skipped})")
    if len(fights) < 3000:
        raise SystemExit("[fit-mma] too few fights — refusing "
                         "to fit on a partial pull")
    elo, wins, games = {}, {}, {}
    last_class, record = {}, {}
    brier = naive_brier = 0.0
    n = correct = 0

    def wr(p):
        return (wins.get(p, 0) + 2.0) / (games.get(p, 0) + 4.0)

    def elo_p(a, b):
        return 1 / (1 + 10 ** (-(a - b) / 400))

    for _d, w, l, wc, _method in fights:
        rw, rl = elo.get(w, START), elo.get(l, START)
        p = elo_p(rw, rl)
        brier += (p - 1.0) ** 2
        pn = wr(w) / (wr(w) + wr(l))
        naive_brier += (pn - 1.0) ** 2
        n += 1
        if p >= 0.5:
            correct += 1
        elo[w] = rw + K * (1 - p)
        elo[l] = rl + K * (0 - (1 - p))
        for f, won in ((w, 1), (l, 0)):
            games[f] = games.get(f, 0) + 1
            wins[f] = wins.get(f, 0) + won
            rec = record.setdefault(f, {"w": 0, "l": 0})
            rec["w" if won else "l"] += 1
            last_class[f] = wc
    blob = {
        "sport": "mma", "league": "ufc",
        "fitted_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "source": ("ufcstats.com scrape via Kaggle "
                   "rajeevratan84/ufcdata, GitHub mirror "
                   "pantazos/kaggle-UFC-data-CSV "
                   "(raw_total_fight_data.csv); snapshot covers "
                   "1993..2021 — fighters debuting after the "
                   "snapshot are not in this fit"),
        "params": {"K": K, "start_elo": START, "home_edge": 0.0},
        "elo": {f: round(elo[f], 1) for f in sorted(elo)},
        "fights": {f: games[f] for f in sorted(games)},
        "weight_class": {f: last_class[f] for f in sorted(games)},
        "record": {f: record[f] for f in sorted(record)},
        "backtest": {
            "brier": round(brier / n, 4),
            "naive_brier": round(naive_brier / n, 4),
            "accuracy": round(correct / n, 4), "n": n,
            "skipped_undecided": skipped,
            "protocol": "walk-forward by event date (Elo from "
                        "prior fights only; naive = relative "
                        "running career win rate, 4-fight 0.5 "
                        "prior); draws/no-contests excluded"},
    }
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=1)
    bt = blob["backtest"]
    print(f"[fit-mma] fighters={len(elo)} n={bt['n']} "
          f"brier={bt['brier']} naive={bt['naive_brier']} "
          f"acc={bt['accuracy']}")
    print(f"[fit-mma] wrote {out_path}")


if __name__ == "__main__":
    main()
