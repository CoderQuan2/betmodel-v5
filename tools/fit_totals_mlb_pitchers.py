#!/usr/bin/env python3
"""fit_totals_mlb_pitchers.py — BetFi Xii pricing Build N,
closer 2: MLB totals refit, attempt 2.

Attempt 1 (tools/fit_totals.py, shipped 2026-10-24) is
FAILED-EXAM on file: walk-forward Brier 0.2533 vs the
total-blind naive 0.2511, MAE 3.641 vs 3.622, n=2,233 —
the team off/def TotalsModel did not beat the expanding
league-average total on either metric.

ATTEMPT 2 — PRE-REGISTERED DESIGN (declared here BEFORE
the exam ran; nothing below was tuned against the
outcome, and there is no attempt 3 in this build):

  * Everything from attempt 1 is unchanged: the same game
    stream (ESPN MLB scoreboard day pulls, 2025 regular
    season, data/cache/mlb_games_2025.json, 2,433 games),
    the same TotalsModel (prior=10, Normal), the same
    walk-forward scoring (burn-in 200; naive = expanding
    league-average total with expanding SD; Brier on
    P(over L*), L* = the .5 line at the naive mean; PASS
    requires MAE AND Brier both better than naive).
  * The ONE added layer: a starting-pitcher adjustment
    to the totals mean. Each game's two probable
    starters (MLB Stats API schedule,
    hydrate=probablePitcher — announced before the game,
    so using them is not look-ahead) carry a walk-forward
    run-prevention rating built from PRIOR games in the
    stream only: in each of his starts, the runs his team
    allowed (the opposing team's score — starter and
    bullpen together; the declared, self-contained
    measure this data supports).
        sp_factor(p) = (opp_runs(p) + 5 * m)
                       / ((starts(p) + 5) * m)
    with m the TotalsModel's expanding league mean team
    score and 5 the declared shrinkage in pseudo-starts.
    A pitcher with no prior starts has factor exactly
    1.0; a game whose probable is missing from the source
    gets factor 1.0 for that side.
        lam_home *= sp_factor(away SP)
        lam_away *= sp_factor(home SP)
  * Integrity gate: this builder first re-scores
    attempt 1 through its own loop on the same stream.
    If it does not reproduce attempt 1's shipped numbers
    (Brier 0.2533 vs 0.2511, MAE 3.641 vs 3.622,
    n=2,233), the loop is wrong, not the lane — the
    builder stops and reports instead of scoring
    attempt 2.
  * Pitcher matching: Stats API games are matched to
    the ESPN stream on (date, home, away) with the
    final score as the disambiguator where needed; the
    match rate is reported in the artifact. Attempt 2 is
    scored on the SAME stream and the SAME scored set
    as attempt 1 (probables only modulate the mean), so
    the comparison is apples-to-apples.

Writes the outcome into data/v5-totals-mlb.json as
"refit_attempt_2" (attempt 1's backtest block is
preserved untouched; the engine's _latest_exam reads
the newest attempt).

Usage: fit_totals_mlb_pitchers.py
"""
import json
import math
import os
import sys
import urllib.request
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
from fit_totals import TotalsModel, p_over, games_mlb  # noqa: E402

STATSAPI = ("https://statsapi.mlb.com/api/v1/schedule?"
            "sportId=1&startDate={}&endDate={}"
            "&hydrate=probablePitcher")
CACHE_PATH = os.path.join(DATA, "cache",
                          "mlb_probables_2025.json")
PRIOR_STARTS = 5
BURN_IN = 200
UA = {"User-Agent": "betfi-xii-fit-totals-mlb-pitchers"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def collect_probables():
    """(date, home, away) -> game dict with probable
    starters, from the MLB Stats API."""
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            blob = json.load(f)
        return {(g["date"], g["home"], g["away"]): g
                for g in blob["games"]}
    out = {}
    d = date(2025, 3, 1)
    end = date(2025, 10, 1)
    while d < end:
        nxt = min(d + timedelta(days=31), end)
        last = (nxt - timedelta(days=1)).isoformat()
        j = fetch(STATSAPI.format(d.isoformat(), last))
        for day in j.get("dates", []):
            for g in day.get("games", []):
                if g.get("gameType") != "R":
                    continue
                if (g.get("status") or {}).get(
                        "abstractGameState") != "Final":
                    continue
                t = g["teams"]
                hn = t["home"]["team"]["name"]
                an = t["away"]["team"]["name"]
                out[(day["date"], hn, an)] = {
                    "date": day["date"], "home": hn,
                    "away": an,
                    "hs": t["home"].get("score"),
                    "as": t["away"].get("score"),
                    "home_sp": (t["home"].get(
                        "probablePitcher") or {}).get(
                        "fullName"),
                    "away_sp": (t["away"].get(
                        "probablePitcher") or {}).get(
                        "fullName")}
        d = nxt
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"games": sorted(
            out.values(), key=lambda g: g["date"])}, f)
    return out


def lams(model, home, away, neutral=False):
    """TotalsModel.predict's two components, recomputed
    from the model's state with its own formulas (predict
    returns only the sum; attempt 2 needs the split)."""
    lh = model.sum_h / model.n
    la = model.sum_a / model.n
    m = (lh + la) / 2.0
    off_h = model._shrunk(model.pf.get(home, 0.0),
                          model.gp.get(home, 0), m)
    def_a = model._shrunk(model.pa.get(away, 0.0),
                          model.gp.get(away, 0), m)
    off_a = model._shrunk(model.pf.get(away, 0.0),
                          model.gp.get(away, 0), m)
    def_h = model._shrunk(model.pa.get(home, 0.0),
                          model.gp.get(home, 0), m)
    if neutral:
        return m * off_h * def_a, m * off_a * def_h, m
    return lh * off_h * def_a, la * off_a * def_h, m


def walk_forward_sp(games, probables, adjust):
    """fit_totals.walk_forward's loop and scoring, in the
    same structure; with adjust=True the mean is the
    pitcher-adjusted one. Returns the exam dict."""
    model = TotalsModel(10, "normal")
    sp = {}                     # name -> [starts, opp runs]
    resid_all = []
    totals_prior = []
    mae_m = mae_n = br_m = br_n = ll_m = ll_n = 0.0
    n_scored = 0
    resid = []

    def sp_factor(name, m):
        if not name or name not in sp:
            return 1.0
        starts, opp = sp[name]
        return (opp + PRIOR_STARTS * m) / (
            (starts + PRIOR_STARTS) * m)

    for g in games:
        total = g["hs"] + g["as"]
        if model.n >= 10:
            lam_h, lam_a, m = lams(
                model, g["home"], g["away"],
                g.get("neutral", False))
            mu = lam_h + lam_a
            pr = probables.get(
                (g["date"], g["home"], g["away"])) or {}
            if adjust:
                mu = (lam_h * sp_factor(pr.get("away_sp"), m)
                      + lam_a * sp_factor(
                          pr.get("home_sp"), m))
            if len(resid_all) >= 25:
                mean_r = sum(resid_all) / len(resid_all)
                sig = math.sqrt(
                    sum((r - mean_r) ** 2 for r in resid_all)
                    / (len(resid_all) - 1))
            elif len(totals_prior) >= 25:
                mt = sum(totals_prior) / len(totals_prior)
                sig = math.sqrt(
                    sum((t - mt) ** 2 for t in totals_prior)
                    / (len(totals_prior) - 1))
            else:
                sig = 0.15 * (
                    sum(totals_prior) / len(totals_prior)
                    if totals_prior else 45.0)
            resid_all.append(total - mu)
            if model.n >= BURN_IN:
                mu_n = sum(totals_prior) / len(totals_prior)
                sig_n = math.sqrt(
                    sum((t - mu_n) ** 2 for t in totals_prior)
                    / (len(totals_prior) - 1))
                line_star = math.floor(mu_n) + 0.5
                pm, _ = p_over(mu, sig, "normal", line_star)
                pn, _ = p_over(mu_n, sig_n, "normal",
                               line_star)
                y = 1.0 if total > line_star else 0.0
                mae_m += abs(total - mu)
                mae_n += abs(total - mu_n)
                br_m += (pm - y) ** 2
                br_n += (pn - y) ** 2
                ll_m += -0.5 * ((total - mu) / sig) ** 2 \
                    - math.log(sig)
                ll_n += -0.5 * ((total - mu_n) / sig_n) ** 2 \
                    - math.log(sig_n)
                resid.append(total - mu)
                n_scored += 1
        totals_prior.append(total)
        model.update(g)
        pr = probables.get((g["date"], g["home"], g["away"]))
        if pr:
            if pr.get("away_sp"):
                e = sp.setdefault(pr["away_sp"], [0, 0])
                e[0] += 1
                e[1] += g["hs"]     # runs the away SP's
                                    # team allowed
            if pr.get("home_sp"):
                e = sp.setdefault(pr["home_sp"], [0, 0])
                e[0] += 1
                e[1] += g["as"]
    out = {"n": n_scored}
    if n_scored:
        out["mae_model"] = round(mae_m / n_scored, 3)
        out["mae_naive"] = round(mae_n / n_scored, 3)
        out["brier_model"] = round(br_m / n_scored, 4)
        out["brier_naive"] = round(br_n / n_scored, 4)
        out["logscore_model"] = round(ll_m / n_scored, 4)
        out["logscore_naive"] = round(ll_n / n_scored, 4)
        mean_r = sum(resid) / len(resid)
        out["sigma_resid"] = round(math.sqrt(
            sum((r - mean_r) ** 2 for r in resid)
            / (len(resid) - 1)), 3)
        out["verdict"] = (
            "PASS" if (out["mae_model"] < out["mae_naive"]
                       and out["brier_model"]
                       < out["brier_naive"])
            else "FAILED-EXAM")
    return out


def main():
    games, _src = games_mlb()
    games.sort(key=lambda g: g["date"])
    probables = collect_probables()
    matched = 0
    both_named = 0
    for g in games:
        pr = probables.get((g["date"], g["home"], g["away"]))
        if pr is None:
            continue
        matched += 1
        if pr.get("home_sp") and pr.get("away_sp"):
            both_named += 1
    print(f"stream {len(games)} games; probables matched "
          f"{matched}; both starters named {both_named}",
          file=sys.stderr)
    a1 = walk_forward_sp(games, probables, adjust=False)
    print(f"attempt-1 reproduction: {a1}", file=sys.stderr)
    if not (a1["n"] == 2233 and a1["brier_model"] == 0.2533
            and a1["brier_naive"] == 0.2511
            and a1["mae_model"] == 3.641
            and a1["mae_naive"] == 3.622):
        print("INTEGRITY GATE FAILED - this loop does not "
              "reproduce attempt 1's shipped numbers; "
              "attempt 2 NOT scored.", file=sys.stderr)
        sys.exit(1)
    a2 = walk_forward_sp(games, probables, adjust=True)
    print(f"ATTEMPT 2: MAE {a2['mae_model']} vs naive "
          f"{a2['mae_naive']}, Brier {a2['brier_model']} "
          f"vs {a2['brier_naive']}, n={a2['n']} -> "
          f"{a2['verdict']}", file=sys.stderr)
    a2["protocol"] = (
        "walk-forward, attempt 1's protocol unchanged "
        "(burn-in 200; naive = expanding league-average "
        "total; Brier on P(over L*), L* = .5 line at the "
        "naive mean; PASS requires MAE and Brier both "
        "better than naive); attempt 2 adds the "
        "pre-registered starting-pitcher adjustment "
        "(probable starters, MLB Stats API; per-start "
        "team runs allowed, shrunk 5 pseudo-starts at "
        "the expanding league mean team score)")
    a2["pitcher_matching"] = {
        "stream_games": len(games), "matched": matched,
        "both_starters_named": both_named,
        "source": ("MLB Stats API schedule "
                   "(statsapi.mlb.com), "
                   "hydrate=probablePitcher, 2025 "
                   "regular season")}
    path = os.path.join(DATA, "v5-totals-mlb.json")
    with open(path) as f:
        fit = json.load(f)
    fit["refit_attempt_2"] = a2
    if a2["verdict"] == "PASS":
        fit["status"] = "FITTED"
    with open(path, "w") as f:
        json.dump(fit, f, indent=1)
    print(f"wrote {path} (status {fit['status']})",
          file=sys.stderr)


if __name__ == "__main__":
    main()
