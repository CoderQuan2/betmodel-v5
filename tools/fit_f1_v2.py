#!/usr/bin/env python3
"""fit_f1_v2.py — BetFi Xii (fix-guy R5): the ONE F1 refit the
R4 FAILED-EXAM named as its closer — driver + constructor.

Attempt 1 (R4, tools/fit_f1.py) was a pure driver Elo and it
was not close: walk-forward log-loss 2.5036 vs the win-share
naive 2.0574, Brier 0.8878 vs 0.8122 (n=234 races, 2015-2025).
In a constructor-dominated sport a driver-only rating cannot
see the car. This refit adds exactly that one piece of new
information and nothing else:

  score(driver) = driver_rating + constructor_effect

  * driver_rating: Elo updated ONLY from teammate
    head-to-heads (same car, same race — the one comparison
    that isolates the driver). Pairwise, K=8, start 1500,
    persistent across seasons and team changes.
  * constructor_effect: per constructor, updated after each
    race from its cars' pairwise results against OTHER
    constructors' cars (actual vs expected from the combined
    scores), K=6 on the mean residual; at each season's
    first race every effect is shrunk x0.6 (new cars are
    redesigns, not continuations).
  * winner probability over an entered field: softmax
    10^(beta * score / 400). beta is chosen BEFORE each
    season from the grid {0.6, 0.85, 1.0, 1.2, 1.45, 1.75,
    2.1} by log-loss over all prior races only (2015 runs
    at beta=1.0) — walk-forward, no peeking.

Exam (PRE-STATED, identical protocol and naive to R4):
every race 2015-2025 predicted pre-race; log-loss and
one-hot Brier vs the Laplace win-share naive over the
entered field (p_i ∝ prior wins_i + 1). PASS iff model
log-loss < naive AND model Brier < naive. A fail here is
TERMINAL for the lane: the fit file keeps both attempts'
numbers and the checker stamps the chain.

Usage: fit_f1_v2.py [out_path] (default ../data/v5-f1.json)
Season JSON reads the R4 cache under /tmp/guy4 (offline).
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

K_DRIVER = 8.0
K_CONSTR = 6.0
SEASON_SHRINK = 0.6
START = 1500.0
BETA_GRID = (0.6, 0.85, 1.0, 1.2, 1.45, 1.75, 2.1)
YEARS = list(range(2015, 2026))
CACHE = "/tmp/guy4"


def load_races():
    races = []
    for y in YEARS:
        path = os.path.join(CACHE, f"f1_{y}.json")
        with open(path, encoding="utf-8") as f:
            season = json.load(f)
        for race in season:
            res = race.get("Results") or []
            classified = [r for r in res
                          if (r.get("positionText") or "").isdigit()]
            classified.sort(key=lambda r: int(r["position"]))
            nc = [r for r in res
                  if not (r.get("positionText") or "").isdigit()]
            entries = [{
                "driver": r["Driver"]["driverId"],
                "constructor":
                    (r.get("Constructor") or {}).get(
                        "constructorId", "?"),
            } for r in classified + nc]
            if len(entries) >= 10:
                races.append({"date": race["date"], "year": y,
                              "name": race["raceName"],
                              "entries": entries})
    races.sort(key=lambda r: r["date"])
    return races


def elo_exp(a, b):
    return 1 / (1 + 10 ** (-(a - b) / 400))


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "data", "v5-f1.json")
    races = load_races()
    ratings = {}          # driver -> rating
    effects = {}          # constructor -> effect (current season)
    wins = {}             # driver -> career wins (naive)
    # per-race record for beta selection + scoring:
    # (year, [(driver, pre-race score)], winner)
    recorded = []
    cur_year = None
    for race in races:
        if race["year"] != cur_year:
            cur_year = race["year"]
            for c in effects:
                effects[c] *= SEASON_SHRINK
        entries = race["entries"]
        field = [e["driver"] for e in entries]
        cons = {e["driver"]: e["constructor"] for e in entries}
        pre_r = {d: ratings.get(d, START) for d in field}
        pre_e = {c: effects.get(c, 0.0) for c in set(cons.values())}
        scores = {d: pre_r[d] + pre_e[cons[d]] for d in field}
        recorded.append((cur_year, scores, field[0]))
        # ---- updates (all from PRE-race state) ----
        pos = {d: i for i, d in enumerate(field)}
        # driver: teammate head-to-heads only
        by_team = {}
        for d in field:
            by_team.setdefault(cons[d], []).append(d)
        d_delta = {d: 0.0 for d in field}
        for team, ds in by_team.items():
            for i in range(len(ds)):
                for j in range(i + 1, len(ds)):
                    a, b = ds[i], ds[j]  # a finished ahead
                    exp_a = elo_exp(pre_r[a], pre_r[b])
                    d_delta[a] += K_DRIVER * (1.0 - exp_a)
                    d_delta[b] -= K_DRIVER * (1.0 - exp_a)
        for d in field:
            if d_delta[d]:
                ratings[d] = pre_r[d] + d_delta[d]
        # constructor: cars vs other constructors' cars
        c_resid, c_cnt = {}, {}
        for d in field:
            others = [o for o in field if cons[o] != cons[d]]
            if not others:
                continue
            exp_sum = sum(elo_exp(scores[d], scores[o])
                          for o in others)
            act_sum = sum(1.0 if pos[d] < pos[o] else 0.0
                          for o in others)
            c = cons[d]
            c_resid[c] = c_resid.get(c, 0.0) + (act_sum - exp_sum)
            c_cnt[c] = c_cnt.get(c, 0) + len(others)
        for c, tot in c_resid.items():
            effects[c] = pre_e[c] + K_CONSTR * tot / c_cnt[c]
        wins[field[0]] = wins.get(field[0], 0) + 1
        # naive state must lag the race: wins updated after
        # recording — but the naive needs PRE-race wins; the
        # recorded tuple stores scores only; naive is rebuilt
        # in the scoring pass from a second walk (see below).
    # ---- scoring pass: replay wins for the naive, choose
    # beta per season from prior races, score walk-forward.
    wins = {}
    ll = ll_n = br = br_n = 0.0
    hits = hits_n = n = 0
    beta_by_year = {}
    prior = []   # (scores, winner) of races before this season
    idx = 0
    for year in YEARS:
        season_recs = [r for r in recorded if r[0] == year]
        if prior:
            best_beta, best_ll = 1.0, None
            for beta in BETA_GRID:
                tot = 0.0
                for scores, winner in prior:
                    w = {d: 10 ** (beta * s / 400)
                         for d, s in scores.items()}
                    p = w[winner] / sum(w.values())
                    tot += -math.log(max(p, 1e-12))
                if best_ll is None or tot < best_ll:
                    best_ll, best_beta = tot, beta
            beta_by_year[year] = best_beta
        else:
            beta_by_year[year] = 1.0
        beta = beta_by_year[year]
        for _y, scores, winner in season_recs:
            field = list(scores)
            w = {d: 10 ** (beta * scores[d] / 400) for d in field}
            tot_w = sum(w.values())
            probs = {d: w[d] / tot_w for d in field}
            naive = {d: wins.get(d, 0) + 1 for d in field}
            tot_nv = sum(naive.values())
            probs_n = {d: naive[d] / tot_nv for d in field}
            ll += -math.log(max(probs[winner], 1e-12))
            ll_n += -math.log(max(probs_n[winner], 1e-12))
            br += sum((probs[d] - (1.0 if d == winner else 0.0)) ** 2
                      for d in field)
            br_n += sum((probs_n[d]
                         - (1.0 if d == winner else 0.0)) ** 2
                        for d in field)
            n += 1
            if max(probs, key=probs.get) == winner:
                hits += 1
            if max(probs_n, key=probs_n.get) == winner:
                hits_n += 1
            wins[winner] = wins.get(winner, 0) + 1
            prior.append((scores, winner))
            idx += 1
    bt = {"n": n, "log_loss": round(ll / n, 4),
          "naive_log_loss": round(ll_n / n, 4),
          "brier": round(br / n, 4),
          "naive_brier": round(br_n / n, 4),
          "top1": round(hits / n, 4),
          "naive_top1": round(hits_n / n, 4),
          "beta_by_year": {str(y): b for y, b in beta_by_year.items()},
          "verdict": "PASS" if (ll / n < ll_n / n
                                and br / n < br_n / n)
          else "FAILED-EXAM"}
    # attempt 1's numbers come from the fit file at the
    # DEFAULT path (the shipped artifact), never from the
    # (possibly scratch) output path.
    old = {}
    default_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "data", "v5-f1.json")
    if os.path.exists(default_path):
        with open(default_path, encoding="utf-8") as f:
            old = json.load(f)
    if old.get("attempt_1"):
        # a re-run must not promote attempt 2 into the
        # attempt-1 slot
        attempt_1 = old["attempt_1"]
    else:
        attempt_1 = old.get("backtest")
    fit = {"fitted_at": datetime.now(timezone.utc).isoformat(),
           "source": ("Ergast via Jolpica (api.jolpi.ca/ergast) "
                      "full race classifications, 2015-2025"),
           "model": ("driver Elo (teammate head-to-heads only, "
                     f"K={K_DRIVER:g}) + constructor effect "
                     f"(cross-team pairwise residuals, "
                     f"K={K_CONSTR:g}, season shrink "
                     f"x{SEASON_SHRINK}); winner = softmax "
                     "10^(beta*score/400) over the entered "
                     "field, beta chosen per season from prior "
                     "races only"),
           "ratings": {d: round(r, 2)
                       for d, r in sorted(ratings.items())},
           "constructor_effects": {c: round(e, 2) for c, e
                                   in sorted(effects.items())},
           "wins": wins,
           "backtest": bt,
           "attempt_1": attempt_1,
           "refit_attempt_2": bt}
    print(f"f1 v2: races={bt['n']} logloss={bt['log_loss']} "
          f"naive={bt['naive_log_loss']} brier={bt['brier']} "
          f"naive_brier={bt['naive_brier']} top1={bt['top1']} "
          f"naive_top1={bt['naive_top1']} verdict={bt['verdict']}")
    print(f"  beta by year: {beta_by_year}")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fit, f, indent=1)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
