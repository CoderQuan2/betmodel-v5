#!/usr/bin/env python3
"""fit_f1.py — BetFi Xii (fix-guy R4): the Formula 1 fit.

Source: the Ergast database via its community successor
Jolpica (api.jolpi.ca/ergast) — full official race
classifications, seasons 2015-2025 (Ergast itself shut down
after 2024; Jolpica serves the same schema and data).

Model: one rating per driver (Elo scale, start 1500). After
each race, every driver's rating moves by the pairwise Elo
decomposition of the classification: against each other
classified driver, finishing ahead scores 1, behind scores 0,
expected from the PRE-race rating difference; the per-race
delta is K=8 times the mean (score - expected) over the field.
Non-classified drivers (positionText R/D/W) rank behind all
classified finishers in listed order. Winner probability over
an entered field is the parameter-free multinomial extension
of Elo: p_i ∝ 10^(r_i/400).

Exam (walk-forward, every race predicted from prior races
only): winner log-loss and one-hot Brier vs the naive
favorite-baseline — Laplace win shares over the entered field,
p_i ∝ (prior wins_i + 1), i.e. the baseline's favorite is the
field's most decorated prior winner. Top-1 accuracy reported
for both.

Usage: fit_f1.py [out_path] (default ../data/v5-f1.json)
Season JSON is cached under /tmp/guy4 (re-runs offline).
"""
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

K = 8.0
START = 1500.0
YEARS = list(range(2015, 2026))
UA = {"User-Agent": "Mozilla/5.0 (BetFi research)"}
CACHE = "/tmp/guy4"
API = "https://api.jolpi.ca/ergast/f1/{y}/results.json"


def fetch_season(y):
    path = os.path.join(CACHE, f"f1_{y}.json")
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    races = []
    offset = 0
    while True:
        url = API.format(y=y) + f"?limit=100&offset={offset}"
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        page = data["MRData"]["RaceTable"]["Races"]
        for race in page:
            races.append(race)
        total = int(data["MRData"]["total"])
        offset += 100
        if offset >= total:
            break
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(races, f)
    return races


def race_order(race):
    """Classified order: numeric positions first (in order),
    then non-classified in listed order."""
    res = race.get("Results") or []
    classified = [r for r in res
                  if (r.get("positionText") or "").isdigit()]
    classified.sort(key=lambda r: int(r["position"]))
    nc = [r for r in res
          if not (r.get("positionText") or "").isdigit()]
    return [r["Driver"]["driverId"] for r in classified + nc]


def softmax_probs(ratings, field):
    w = {d: 10 ** (ratings.get(d, START) / 400) for d in field}
    tot = sum(w.values())
    return {d: w[d] / tot for d in field}


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "data", "v5-f1.json")
    races = []
    for y in YEARS:
        for race in fetch_season(y):
            order = race_order(race)
            if len(order) >= 10:
                races.append({"date": race["date"],
                              "name": race["raceName"],
                              "order": order})
    races.sort(key=lambda r: r["date"])
    ratings, wins, starts = {}, {}, {}
    ll = ll_n = brier = brier_n = 0.0
    n = hits = hits_n = 0
    names = {}
    for race in races:
        field = race["order"]
        winner = field[0]
        probs = softmax_probs(ratings, field)
        naive = {d: (wins.get(d, 0) + 1) for d in field}
        tot = sum(naive.values())
        probs_n = {d: naive[d] / tot for d in field}
        p = max(probs[winner], 1e-12)
        pn = max(probs_n[winner], 1e-12)
        ll += -math.log(p)
        ll_n += -math.log(pn)
        brier += sum((probs[d] - (1.0 if d == winner else 0.0)) ** 2
                     for d in field)
        brier_n += sum(
            (probs_n[d] - (1.0 if d == winner else 0.0)) ** 2
            for d in field)
        n += 1
        if max(probs, key=probs.get) == winner:
            hits += 1
        if max(probs_n, key=probs_n.get) == winner:
            hits_n += 1
        # pairwise Elo update on pre-race ratings
        pre = {d: ratings.get(d, START) for d in field}
        pos = {d: i for i, d in enumerate(field)}
        for d in field:
            others = [o for o in field if o != d]
            exp_sum = sum(
                1 / (1 + 10 ** (-(pre[d] - pre[o]) / 400))
                for o in others)
            act_sum = sum(1.0 if pos[d] < pos[o] else 0.0
                          for o in others)
            ratings[d] = pre[d] + K * (act_sum - exp_sum) / len(others)
            starts[d] = starts.get(d, 0) + 1
        wins[winner] = wins.get(winner, 0) + 1
    fit = {"fitted_at": datetime.now(timezone.utc).isoformat(),
           "source": ("Ergast via Jolpica (api.jolpi.ca/ergast) "
                      "full race classifications, 2015-2025"),
           "model": (f"driver Elo (pairwise decomposition, "
                     f"K={K:g}, start {START:g}); winner = "
                     "softmax 10^(r/400) over the entered field"),
           "ratings": {d: round(r, 2) for d, r in ratings.items()},
           "starts": starts, "wins": wins,
           "backtest": {
               "n": n,
               "log_loss": round(ll / n, 4),
               "naive_log_loss": round(ll_n / n, 4),
               "brier": round(brier / n, 4),
               "naive_brier": round(brier_n / n, 4),
               "top1": round(hits / n, 4),
               "naive_top1": round(hits_n / n, 4)}}
    bt = fit["backtest"]
    print(f"f1: races={bt['n']} logloss={bt['log_loss']} "
          f"naive={bt['naive_log_loss']} brier={bt['brier']} "
          f"naive_brier={bt['naive_brier']} top1={bt['top1']} "
          f"naive_top1={bt['naive_top1']} drivers={len(ratings)}")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fit, f, indent=1)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
