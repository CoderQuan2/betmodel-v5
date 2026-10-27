#!/usr/bin/env python3
"""fit_lacrosse.py — BetFi Xii pricing Build N, closer 3:
the NLL season-simulator outright model.

The arriving lacrosse markets are season outrights (the
NLL Cup winner future, 12 runners on the saved slate; the
NCAA championship future rides the same sport key and
stays separately stamped — no fitted source). A team
rating alone does not price a championship outright; the
census's named closer is a Monte Carlo season simulator,
examined against historical Cup outcomes. This builder
builds it, in the soccer outright protocol's shape
(tools/fit_outrights.py), with every choice declared
here BEFORE the exam ran:

SOURCE (verified by fetch, 2026-10-27): ESPN's NLL
scoreboard (site.api.espn.com lacrosse/nll) — real finals
with FanDuel-matching club names. The feed labels every
game regular-season (even Finals games), so the RS /
playoff split is by date, declared: regular season =
November-April games; playoffs = May-June. The split
is checked against the league's known shape (14 clubs
x 18 games = 126 RS games a season, every club at
exactly 18) in the run log. RETENTION: the feed serves
nothing before the 2024-25 season (every 2023-24 date
probed returns zero events — a verified negative), so
the examined era is the two completed seasons the
route serves, springs 2025 and 2026.

MODEL: per-season att/def strengths fit on that season's
regular-season goals (fit_outrights.fit_strengths — the
shipped fitter's shrinkage recipe, verbatim). A game's
win probability comes from independent Poisson scoring
rates lam = LH/LA * att * def; a tied regulation score
is split in proportion to the scoring rates (NLL
overtime is sudden-death; the declared approximation).
Playoffs, the league's format: 8 qualifiers seeded by
RS wins (ties: goal differential, then goals for);
quarterfinals single games at the higher seed;
semifinals best-of-3 (higher seed hosts games 1 and 3);
finals best-of-3 (higher seed hosts games 1 and 3);
fixed bracket (1/8 winner vs 4/5 winner, 2/7 vs 3/6).

EXAM (fit_outrights' bar, adapted only where the
verified route forces it — declared here, before the
exam ran): for each completed season the route serves
(springs 2025 and 2026), strengths are fit on the
regular season, the playoffs are simulated 20,000
times (fixed seed), and the champion shares are
scored against the actual Cup winner — Brier and
log-loss vs the naive baseline p_i = RS wins share
(the standings-share naive). fit_outrights requires
beating the naive on BOTH metrics in at least 2 of 3
seasons AND on both means; with two seasons in
existence on this route, the bar here is a clean
sweep — BOTH metrics in BOTH seasons, AND both
2-season means. No season may be lost.

LIVE ARTIFACT (written only with the exam, whatever its
verdict — the engine's gate decides what prices): the
2026-27 NLL Cup shares: strengths from the spring-2026
season (the most recent completed), a full-season
simulation over that season's actual fixture pairings
as the schedule template (18 games a club, home/away
as played), RS simulated game by game, then the same
playoff format. The FireWolves' relocation is applied
to the live artifact only: ESPN's "Albany FireWolves"
(the 2025-26 club) is FanDuel's "Oshawa FireWolves" on
the 2026-27 future.

Writes data/v5-lacrosse.json. A re-run with the games
cache present (data/cache/nll_games_2024-26.json)
refits without re-pulling.

Usage: fit_lacrosse.py
"""
import json
import math
import os
import random
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
CACHE_PATH = os.path.join(DATA, "cache",
                          "nll_games_2024-26.json")
ESPN_NLL = ("https://site.api.espn.com/apis/site/v2/"
            "sports/lacrosse/nll/scoreboard")
SPRINGS = (2025, 2026)
SIMS = 20000
SEED = 20261027
PRIOR_GAMES = 4
PRIOR_LH = 11.9
PRIOR_LA = 11.0
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
LIVE_NAME_MAP = {"Albany FireWolves": "Oshawa FireWolves"}


def now():
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds")


def fetch_day(d):
    url = f"{ESPN_NLL}?dates={d.strftime('%Y%m%d')}&limit=200"
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return d, json.loads(r.read().decode("utf-8"))
    except Exception:
        return d, None


def collect():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            blob = json.load(f)
        print(f"cache: {len(blob['games'])} games "
              f"({blob['fetched_at']})", file=sys.stderr)
        return blob["games"], blob["fetched_at"]
    days = []
    for y in SPRINGS:
        d = date(y - 1, 12, 1)
        end = date(y, 6, 15)
        while d <= end:
            days.append(d)
            d += timedelta(days=1)
    raw = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        for d, j in ex.map(fetch_day, days):
            if j:
                raw[d] = j
    games = []
    for d in sorted(raw):
        for ev in raw[d].get("events", []):
            if not ev["status"]["type"]["completed"]:
                continue
            comp = ev["competitions"][0]
            cs = comp["competitors"]
            home = next(c for c in cs
                        if c["homeAway"] == "home")
            away = next(c for c in cs
                        if c["homeAway"] == "away")
            if home.get("score") in (None, "") or \
                    away.get("score") in (None, ""):
                continue
            dt = (ev.get("date") or "")[:10]
            spring = int(dt[:4]) + (1 if int(dt[5:7]) >= 7
                                    else 0)
            if spring not in SPRINGS:
                continue
            games.append({
                "date": dt, "spring": spring,
                "phase": ("po" if int(dt[5:7]) in (5, 6)
                          else "rs"),
                "home": home["team"]["displayName"],
                "away": away["team"]["displayName"],
                "hs": int(home["score"]),
                "as": int(away["score"])})
    games.sort(key=lambda g: (g["date"], g["home"]))
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"fetched_at": now(), "games": games}, f)
    return games, now()


# ------------------------------------------------ strengths

def fit_strengths(games):
    """fit_outrights.fit_strengths, verbatim in recipe
    (goal-based att/def with the shipped shrinkage)."""
    gp, gf, ga = {}, {}, {}
    hg = ag = hgames = 0
    for g in games:
        for t in (g["home"], g["away"]):
            gp.setdefault(t, 0)
            gf.setdefault(t, 0)
            ga.setdefault(t, 0)
        gp[g["home"]] += 1
        gp[g["away"]] += 1
        gf[g["home"]] += g["hs"]
        ga[g["home"]] += g["as"]
        gf[g["away"]] += g["as"]
        ga[g["away"]] += g["hs"]
        hg += g["hs"]
        ag += g["as"]
        hgames += 1
    total_gp = sum(gp.values())
    L = sum(gf.values()) / total_gp if total_gp else 12.0
    LH = (hg + 10 * PRIOR_LH) / (hgames + 10) if hgames \
        else PRIOR_LH
    LA = (ag + 10 * PRIOR_LA) / (hgames + 10) if hgames \
        else PRIOR_LA
    st = {}
    for t in gp:
        st[t] = {
            "att": ((gf[t] + PRIOR_GAMES * L)
                    / (gp[t] + PRIOR_GAMES)) / L,
            "def": ((ga[t] + PRIOR_GAMES * L)
                    / (gp[t] + PRIOR_GAMES)) / L,
            "gp": gp[t]}
    return st, {"LH": LH, "LA": LA, "L": L}


def pois(rng, lam):
    """Knuth sampler (lam ~ 12: fine at this size)."""
    if lam > 60:
        return int(rng.gauss(lam, math.sqrt(lam)) + 0.5)
    l_ = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        p *= rng.random()
        if p <= l_:
            return k
        k += 1


def game_win_prob(st, lg, home, away):
    """P(home wins) under independent Poissons, by exact
    summation to 45 goals; ties split by scoring rate."""
    lh = lg["LH"] * st[home]["att"] * st[away]["def"]
    la = lg["LA"] * st[away]["att"] * st[home]["def"]

    def pmf(lam, k):
        return math.exp(-lam) * lam ** k / math.factorial(k)
    p = 0.0
    for h in range(46):
        ph = pmf(lh, h)
        if ph < 1e-12:
            continue
        cdf_a = sum(pmf(la, a) for a in range(h))
        tie = pmf(la, h)
        p += ph * (cdf_a + tie * lh / (lh + la))
    return p


def standings(rs_games):
    """seed order: wins, then goal diff, then goals for."""
    w, gf, ga = {}, {}, {}
    for g in rs_games:
        for t in (g["home"], g["away"]):
            w.setdefault(t, 0)
            gf.setdefault(t, 0)
            ga.setdefault(t, 0)
        gf[g["home"]] += g["hs"]
        ga[g["home"]] += g["as"]
        gf[g["away"]] += g["as"]
        ga[g["away"]] += g["hs"]
        if g["hs"] > g["as"]:
            w[g["home"]] += 1
        elif g["as"] > g["hs"]:
            w[g["away"]] += 1
    order = sorted(w, key=lambda t: (-w[t],
                                     -(gf[t] - ga[t]),
                                     -gf[t], t))
    return order, w


def sim_playoffs(rng, probs, seeds):
    """One playoff run. probs[(h, a)] = P(h beats a) at
    h's venue. Bracket: QF 1v8 4v5 2v7 3v6 (single game
    at the higher seed); SF best-of-3 (1/8 winner vs 4/5
    winner, 2/7 vs 3/6), Finals best-of-3; in a series
    the higher seed hosts games 1 and 3."""

    def game(h, a):
        return h if rng.random() < probs[(h, a)] else a

    def series(hi, lo):
        wins = {hi: 0, lo: 0}
        for host, guest in ((hi, lo), (lo, hi), (hi, lo)):
            w = game(host, guest)
            wins[w] += 1
            if wins[w] == 2:
                return w
        return hi if wins[hi] > wins[lo] else lo

    s = seeds
    qf = [game(s[0], s[7]), game(s[3], s[4]),
          game(s[1], s[6]), game(s[2], s[5])]
    sf1 = series(*sorted((qf[0], qf[1]),
                         key=lambda t: s.index(t)))
    sf2 = series(*sorted((qf[2], qf[3]),
                         key=lambda t: s.index(t)))
    hi, lo = sorted((sf1, sf2), key=lambda t: s.index(t))
    return series(hi, lo)


def playoff_probs(st, lg, seeds):
    teams = list(st)
    return {(h, a): game_win_prob(st, lg, h, a)
            for h in teams for a in teams if h != a}


def champion_shares(st, lg, seeds, sims, seed):
    rng = random.Random(seed)
    probs = playoff_probs(st, lg, seeds)
    counts = {t: 0 for t in st}
    for _ in range(sims):
        counts[sim_playoffs(rng, probs, seeds)] += 1
    return {t: counts[t] / sims for t in st}


def score(probs, champ):
    brier = sum((p - (1.0 if t == champ else 0.0)) ** 2
                for t, p in probs.items())
    return brier, -math.log(max(probs.get(champ, 0.0),
                                1e-9))


def main():
    games, fetched_at = collect()
    by_spring = {}
    for g in games:
        by_spring.setdefault(g["spring"], []).append(g)
    rows = []
    for y in SPRINGS:
        rs = [g for g in by_spring[y] if g["phase"] == "rs"]
        po = [g for g in by_spring[y] if g["phase"] == "po"]
        _gp = {}
        for g in rs:
            _gp[g["home"]] = _gp.get(g["home"], 0) + 1
            _gp[g["away"]] = _gp.get(g["away"], 0) + 1
        print(f"  spring {y}: RS {len(rs)} games, clubs "
              f"{len(_gp)}, per-club RS games "
              f"{sorted(set(_gp.values()))}, PO {len(po)}",
              file=sys.stderr)
        champ = po[-1]["home"] if po[-1]["hs"] > po[-1]["as"] \
            else po[-1]["away"]
        st, lg = fit_strengths(rs)
        seeds, wins = standings(rs)
        shares = champion_shares(st, lg, seeds[:8], SIMS,
                                 SEED + y)
        # non-qualifiers hold a zero share in the model
        full = {t: shares.get(t, 0.0) for t in st}
        tot_w = sum(wins.values())
        naive = {t: wins[t] / tot_w for t in st}
        b, ll = score(full, champ)
        bn, lln = score(naive, champ)
        rows.append({
            "season": f"{y - 1}-{str(y)[2:]}",
            "champion": champ,
            "rs_games": len(rs), "po_games": len(po),
            "p_champion_model": round(full[champ], 4),
            "p_champion_naive": round(naive[champ], 4),
            "brier_model": round(b, 4),
            "brier_naive": round(bn, 4),
            "logloss_model": round(ll, 4),
            "logloss_naive": round(lln, 4)})
        r = rows[-1]
        print(f"  {r['season']}: RS {len(rs)} PO "
              f"{len(po)}; champ {champ} — model p "
              f"{r['p_champion_model']} (Brier {b:.4f}, "
              f"LL {ll:.4f}) vs naive "
              f"{r['p_champion_naive']} (Brier {bn:.4f}, "
              f"LL {lln:.4f})", file=sys.stderr)
    wins_n = sum(1 for r in rows
                 if r["brier_model"] < r["brier_naive"]
                 and r["logloss_model"] < r["logloss_naive"])
    mean = lambda k: round(sum(r[k] for r in rows)
                           / len(rows), 4)  # noqa: E731
    passed = (wins_n == len(rows)
              and mean("brier_model") < mean("brier_naive")
              and mean("logloss_model")
              < mean("logloss_naive"))
    exam = {"seasons": rows, "seasons_won": wins_n,
            "mean_brier_model": mean("brier_model"),
            "mean_brier_naive": mean("brier_naive"),
            "mean_logloss_model": mean("logloss_model"),
            "mean_logloss_naive": mean("logloss_naive"),
            "verdict": "PASS" if passed else "FAILED-EXAM",
            "bar": ("model beats naive on Brier AND "
                    "log-loss in BOTH examined seasons "
                    "and on both means (the fit_outrights "
                    ">= 2-of-3 bar as a clean sweep — only "
                    "two completed seasons exist on the "
                    "verified ESPN route)"),
            "sims_per_season": SIMS}
    print(f"EXAM: {exam['verdict']} (won {wins_n}/"
          f"{len(rows)}; "
          f"mean Brier {exam['mean_brier_model']} vs "
          f"{exam['mean_brier_naive']}; mean LL "
          f"{exam['mean_logloss_model']} vs "
          f"{exam['mean_logloss_naive']})",
          file=sys.stderr)

    # live artifact: 2026-27 shares from spring-2026
    rs26 = [g for g in by_spring[2026] if g["phase"] == "rs"]
    st, lg = fit_strengths(rs26)
    fixtures = [(g["home"], g["away"]) for g in rs26]
    rng = random.Random(SEED)
    teams = list(st)
    probs = playoff_probs(st, lg, teams)
    counts = {t: 0 for t in teams}
    for _ in range(SIMS):
        pts = {t: 0 for t in teams}
        gf = {t: 0 for t in teams}
        ga = {t: 0 for t in teams}
        for h, a in fixtures:
            hg = pois(rng, lg["LH"] * st[h]["att"]
                      * st[a]["def"])
            ag = pois(rng, lg["LA"] * st[a]["att"]
                      * st[h]["def"])
            gf[h] += hg
            ga[h] += ag
            gf[a] += ag
            ga[a] += hg
            if hg > ag:
                pts[h] += 1
            elif ag > hg:
                pts[a] += 1
            else:  # OT: split by scoring rates
                lh = lg["LH"] * st[h]["att"] * st[a]["def"]
                la = lg["LA"] * st[a]["att"] * st[h]["def"]
                if rng.random() < lh / (lh + la):
                    pts[h] += 1
                else:
                    pts[a] += 1
        seeds = sorted(teams, key=lambda t: (-pts[t],
                                             -(gf[t] - ga[t]),
                                             -gf[t], t))
        counts[sim_playoffs(rng, probs, seeds[:8])] += 1
    shares = {}
    for t in teams:
        name = LIVE_NAME_MAP.get(t, t)
        shares[name] = round(counts[t] / SIMS, 4)
    art = {
        "sport": "lacrosse", "league": "nll",
        "fitted_at": now(),
        "source": ("ESPN NLL scoreboard day pulls "
                   "(site.api.espn.com lacrosse/nll), "
                   "seasons 2024-25 .. 2025-26 (the "
                   "route serves nothing earlier); "
                   f"fetched {fetched_at}"),
        "exam": exam,
        "live": {"season": "2026-27",
                 "basis": ("spring-2026 strengths; that "
                           "season's fixture pairings as "
                           "the schedule template"),
                 "played": 0, "remaining": len(fixtures),
                 "sims": SIMS, "shares": shares},
        "status": "FITTED" if passed else "FAILED-EXAM"}
    out = os.path.join(DATA, "v5-lacrosse.json")
    with open(out, "w") as f:
        json.dump(art, f, indent=1)
    print(f"wrote {out} (status {art['status']})",
          file=sys.stderr)


if __name__ == "__main__":
    main()
