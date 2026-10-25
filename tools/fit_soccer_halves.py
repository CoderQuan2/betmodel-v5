#!/usr/bin/env python3
"""fit_soccer_halves.py — BetFi Xii (fix-guy R5): soccer
first-half distributions via a fitted half-share on the
shipped Poisson grid.

The full-game grid gives fixture lambdas (lam_h, lam_a).
First-half goals are modeled as Poisson with the SAME
strengths and league rates scaled by a fitted half-share:
lam1_h = lam_h * share_h, lam1_a = lam_a * share_a, where
share_h = HTHG/FTHG and share_a = HTAG/FTAG for the league.

Exam (PRE-STATED, walk-forward per league, seasons
2024-25 + 2025-26 pooled in date order, burn-in 80 games):
strengths update game-by-game with the shipped fitter's
shrinkage; shares are the expanding HTHG/FTHG means. Two
scores per game, both against the a-priori naive (FIXED
universal shares 0.44/0.44 on the same strengths, and
full-game grid probabilities for the half result):
  * Brier for 1H total over 1.5 (Poisson tail);
  * Brier3 for the 1H result (H/D/A from the 1H grid).
R5 ran a JOINT bar (both Briers had to beat naive); it
failed 12 of 16 leagues while the 1H-result cell beat its
naive in all 16 — the joint bar graded a passing form
down with a failing one.
R6 bar (PRE-STATED in the R6 assignment, before this
builder re-ran): the exam splits PER FORM.
  * 1H result passes iff its walk-forward Brier3 beats
    the fixed-share naive's Brier3;
  * 1H total passes iff its Brier (over 1.5) beats the
    0.44-share naive's.
The checker prices each (league, form) exactly on its own
pass; the four R5 joint-passed leagues keep both forms.
"status" stays the joint summary (FITTED iff both forms
pass) and "forms" carries the per-form verdicts the
checker and coverage read. Final shares (all games) ship
into data/v5-segments.json under "soccer-1h" either way,
so a stamp can quote both forms' numbers.

Usage: fit_soccer_halves.py [segments_path]
CSVs cache under /tmp/guy5/fd (shared with fit_outrights).
"""
import json
import math
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fit_outrights import fetch_csv, parse_games, PRIOR_GAMES  # noqa: E402

LEAGUES = {  # league key (v5-soccer-leagues) -> football-data code
    "epl": "E0", "championship": "E1", "serie-a": "I1",
    "serie-b": "I2", "la-liga": "SP1", "la-liga-2": "SP2",
    "bundesliga": "D1", "bundesliga-2": "D2", "ligue-1": "F1",
    "ligue-2": "F2", "eredivisie": "N1", "primeira-liga": "P1",
    "super-lig": "T1", "super-league-greece": "G1",
    "jupiler-pro": "B1", "scottish-premiership": "SC0",
}
SEASONS = ("2425", "2526")
NAIVE_SHARE = 0.44
BURN_IN = 80


def _pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def grid_probs(lh, la, maxg=10):
    ph = [_pois(i, lh) for i in range(maxg + 1)]
    pa = [_pois(i, la) for i in range(maxg + 1)]
    p_home = p_draw = p_away = p_over15 = 0.0
    for i in range(maxg + 1):
        for j in range(maxg + 1):
            p = ph[i] * pa[j]
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p
            if i + j > 1.5:
                p_over15 += p
    return p_home, p_draw, p_away, p_over15


def exam_league(games, prior_lh, prior_la):
    games = [g for g in games if g.get("hth") is not None]
    def key(g):
        try:
            return datetime.strptime(g["date"], "%d/%m/%Y")
        except ValueError:
            return datetime.min
    games.sort(key=key)
    gp, gf, ga = {}, {}, {}
    hg = ag = hgames = 0
    hth = hta = 0
    n = 0
    br_o = br_on = br3 = br3n = 0.0
    for g in games:
        for t in (g["home"], g["away"]):
            gp.setdefault(t, 0)
            gf.setdefault(t, 0)
            ga.setdefault(t, 0)
        if hgames >= BURN_IN and hg > 0:
            total_gp = sum(gp.values())
            L = sum(gf.values()) / total_gp
            LH = (hg + 10 * prior_lh) / (hgames + 10)
            LA = (ag + 10 * prior_la) / (hgames + 10)
            st = {}
            for t in gp:
                st[t] = {
                    "att": ((gf[t] + PRIOR_GAMES * L)
                            / (gp[t] + PRIOR_GAMES)) / L,
                    "def": ((ga[t] + PRIOR_GAMES * L)
                            / (gp[t] + PRIOR_GAMES)) / L}
            lh = LH * st[g["home"]]["att"] * st[g["away"]]["def"]
            la = LA * st[g["away"]]["att"] * st[g["home"]]["def"]
            sh, sa = hth / hg, hta / ag
            ph, pd_, pa, po = grid_probs(lh * sh, la * sa)
            nh, nd, na, no = grid_probs(lh * NAIVE_SHARE,
                                        la * NAIVE_SHARE)
            y_over = 1.0 if g["hth"] + g["hta"] > 1.5 else 0.0
            br_o += (po - y_over) ** 2
            br_on += (no - y_over) ** 2
            yh = 1.0 if g["hth"] > g["hta"] else 0.0
            yd = 1.0 if g["hth"] == g["hta"] else 0.0
            ya = 1.0 - yh - yd
            br3 += (ph - yh) ** 2 + (pd_ - yd) ** 2 + (pa - ya) ** 2
            fh, fd, fa, _ = grid_probs(lh, la)
            br3n += (fh - yh) ** 2 + (fd - yd) ** 2 + (fa - ya) ** 2
            n += 1
        gp[g["home"]] += 1
        gp[g["away"]] += 1
        gf[g["home"]] += g["hs"]
        ga[g["home"]] += g["as"]
        gf[g["away"]] += g["as"]
        ga[g["away"]] += g["hs"]
        hg += g["hs"]
        ag += g["as"]
        hth += g["hth"]
        hta += g["hta"]
        hgames += 1
    if n == 0 or hg == 0:
        return None
    bt = {"n": n, "brier_over15": round(br_o / n, 4),
          "brier_over15_naive": round(br_on / n, 4),
          "brier3_1h": round(br3 / n, 4),
          "brier3_1h_naive": round(br3n / n, 4),
          "protocol": "walk-forward (strengths + shares from "
                      "prior games only); naive = fixed 0.44 "
                      "shares + full-game grid for the 1H result"}
    passed = bt["brier_over15"] < bt["brier_over15_naive"] \
        and bt["brier3_1h"] < bt["brier3_1h_naive"]
    # R6 per-form verdicts (the governing bar now — see the
    # header). "status" remains the joint summary so every
    # R5 reader keeps its meaning.
    res_ok = bt["brier3_1h"] < bt["brier3_1h_naive"]
    tot_ok = bt["brier_over15"] < bt["brier_over15_naive"]
    return {"status": "FITTED" if passed else "FAILED-EXAM",
            "share_h": round(hth / hg, 4),
            "share_a": round(hta / ag, 4),
            "forms": {
                "result": {
                    "status": "FITTED" if res_ok
                              else "FAILED-EXAM",
                    "brier3_1h": bt["brier3_1h"],
                    "brier3_1h_naive": bt["brier3_1h_naive"]},
                "total": {
                    "status": "FITTED" if tot_ok
                              else "FAILED-EXAM",
                    "brier_over15": bt["brier_over15"],
                    "brier_over15_naive":
                        bt["brier_over15_naive"]}},
            "bar_r6": "per-form: 1H result passes iff its "
                      "walk-forward Brier3 beats the "
                      "fixed-share naive's; 1H total passes "
                      "iff its Brier beats the 0.44-share "
                      "naive's (pre-stated in the R6 "
                      "assignment, before this builder ran)",
            # R5-era per-form facts, kept verbatim.
            "form_facts": {
                "result_beats_naive": res_ok,
                "total_beats_naive": tot_ok},
            "backtest": bt, "n_history": hgames}


def main():
    seg_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "data", "v5-segments.json")
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".."))
    import betmodel5 as b5
    out = {}
    for key, code in LEAGUES.items():
        games = []
        for s in SEASONS:
            try:
                games += parse_games(fetch_csv((s, code)),
                                     with_ht=True)
            except Exception as e:  # noqa: BLE001
                print(f"  !! {key} {s}: {e}")
        if not games:
            print(f"  {key}: no games — skipped (named)")
            continue
        r = exam_league(games, b5.SOC_PRIOR_LH, b5.SOC_PRIOR_LA)
        if r is None:
            print(f"  {key}: no HT data — skipped (named)")
            continue
        out[key] = r
        print(f"  {key}: {r['status']} shares "
              f"{r['share_h']}/{r['share_a']} "
              f"over15 {r['backtest']['brier_over15']} vs "
              f"{r['backtest']['brier_over15_naive']}, 1H Brier3 "
              f"{r['backtest']['brier3_1h']} vs "
              f"{r['backtest']['brier3_1h_naive']} (n={r['backtest']['n']})")
    doc = {}
    if os.path.exists(seg_path):
        with open(seg_path, encoding="utf-8") as f:
            doc = json.load(f)
    doc["soccer-1h"] = out
    doc["soccer_1h_source"] = ("football-data.co.uk CSVs "
                               "(HTHG/HTAG), seasons 2024-25 + "
                               "2025-26, walk-forward exam per "
                               "league")
    with open(seg_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print("wrote", seg_path)


if __name__ == "__main__":
    main()
