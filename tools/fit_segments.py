#!/usr/bin/env python3
"""fit_segments.py — BetFi Xii (fix-guy R5): segment (half /
quarter / period) distributions from real ESPN linescore
history.

Sources (all ESPN scoreboard routes, linescores included):
  NBA  basketball/nba  day-range pulls, completed seasons
       2024-25 + 2025-26 — 1H = Q1+Q2 linescores.
  NFL  football/nfl    week pulls, seasons 2024 + 2025 —
       1H = Q1+Q2 linescores.
  NHL  hockey/nhl      day-range pulls, completed seasons
       2024-25 + 2025-26 — 1P = first linescore.

Model (NBA/NFL first half): team 1H scoring rates fitted
exactly like the totals lanes fit full-game rates —
lam_h = LH1*off1[h]*def1[a], lam_a = LA1*off1[a]*def1[h],
rates shrunk to the league mean with prior_games=4 — the
predicted 1H total is Normal(mu, sigma) and the 1H margin
is Normal(lam_h - lam_a, sigma_m), sigmas from walk-forward
residuals.

Exam (PRE-STATED, walk-forward — every game predicted from
prior games only, burn-in excluded from scoring):
  totals: MAE of the 1H total and Brier for over/under at
    L* (the expanding train median 1H total, rounded to .5).
  spreads: MAE of the 1H margin and Brier for home cover at
    -L*m (L*m = expanding train median home 1H margin, .5).
  naive (the bar, not a strawman): the SCALED FULL-GAME
    baseline — full-game rates fitted the same way on full
    scores; naive 1H total mu = s * mu_full with s the
    expanding mean 1H/full total share, sigma = s * sigma_full;
    naive 1H margin mu = 0.5 * mu_full_margin, sigma =
    sqrt(0.5) * sigma_full_margin.
  PASS (per lane) iff model MAE < naive MAE AND model Brier
  < naive Brier for BOTH the total and the margin.
NHL 1P totals: Poisson from team 1P rates; naive = expanding
league-mean 1P total (Poisson); Brier on over 1.5; PASS iff
model MAE < naive MAE AND model Brier < naive Brier.

The shipped ratings are the final walk-forward state (all
history), in data/v5-segments.json. A lane whose exam fails
ships with status FAILED-EXAM and its numbers — the checker
stamps it and never prices.

R6 additions (same machinery, same scaled-naive bar):
  NBA/NFL FIRST QUARTERS (seg_fn = Q1 linescores; the
  naive's margin share is the expanding segment share
  instead of the halves' fixed 1/2) and NCAAF FIRST HALVES
  from ESPN FBS (groups=80) day pulls, seasons 2024+2025,
  pulled by /tmp/guy6/fetch_ncaaf.py — the lane records
  its linescore coverage (events seen vs usable games)
  verbatim, so a thin pull would say so on the stamp.

R7 additions (the closer round's remainder):
  NCAAF QUARTERS — ncaaf-1q / ncaaf-2q through exam_us
  with the R6 share-scaled naive, same coverage record as
  the 1H lane. Terminal with numbers, pass or fail.
  NHL PERIODS — exam_nhl_periods: one walk-forward pass
  over the same day-pull linescores scoring EVERY period
  (1P/2P/3P) on TWO forms, per-form verdicts:
    total form: Poisson period totals from team period
      rates; MAE + Brier (over 1.5) vs the expanding
      league-mean period total (the R5 1P naive, per
      period). Pass iff both beat naive.
    moneyline form: the period result (H/D/A) off the
      independent-Poisson grid of the same rates; Brier3
      + period-margin MAE vs the naive grid built on the
      expanding league-mean home/away period rates. Pass
      iff both beat naive.
  The R5 nhl-1p lane keeps its shipped totals exam
  verbatim; R7 adds its moneyline form and the full
  nhl-2p / nhl-3p lanes.

Usage: fit_segments.py [out_path] [--lane=nba|nfl|nhl|
       nba1q|nfl1q|ncaaf|ncaaf1q|ncaaf2q|nhlperiods]
Raw pulls cache under /tmp/guy5 (re-runs are offline);
NCAAF pulls live under /tmp/guy6.
"""
import json
import math
import os
import statistics
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

UA = {"User-Agent": "Mozilla/5.0 (BetFi research)"}
CACHE = os.environ.get("BETFI_FIT_CACHE", "/tmp/guy5")
PRIOR = 4.0
API = "https://site.api.espn.com/apis/site/v2/sports"


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_cached(name, builder):
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    out = builder()
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    return out


def _parse_events(data, sport):
    games = []
    for ev in data.get("events") or []:
        comp = (ev.get("competitions") or [{}])[0]
        sides = {}
        ok = True
        for c in comp.get("competitors") or []:
            ls = [x.get("value") for x in c.get("linescores") or []]
            if len(ls) < 2 or any(v is None for v in ls):
                ok = False
                break
            sides[c["homeAway"]] = {
                "team": c["team"]["abbreviation"], "ls": ls}
        if not ok or set(sides) != {"home", "away"}:
            continue
        st = ((ev.get("status") or {}).get("type") or {})
        if not st.get("completed"):
            continue
        h, a = sides["home"], sides["away"]
        games.append({"id": ev["id"], "date": ev["date"],
                      "home": h["team"], "away": a["team"],
                      "h_ls": h["ls"], "a_ls": a["ls"],
                      "hs": sum(h["ls"]), "as": sum(a["ls"])})
    return games


def fetch_day_ranges(sport_path, start, end, tag):
    """Single-day scoreboard pulls (the range form of the
    dates parameter 400s through this route; day pulls are
    the route every other fit in the lab uses). Each day is
    cached separately under /tmp/guy5 so a re-run is offline
    and a partial fetch keeps its progress."""
    from concurrent.futures import ThreadPoolExecutor
    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)

    def one(day):
        path = os.path.join(CACHE, f"seg_{tag}_{day:%Y%m%d}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        url = (f"{API}/{sport_path}/scoreboard?"
               f"dates={day:%Y%m%d}")
        try:
            games = _parse_events(_get(url), sport_path)
        except Exception as e:  # noqa: BLE001
            print(f"  !! {tag} {day:%Y%m%d}: {e}")
            return []
        os.makedirs(CACHE, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(games, f)
        return games

    games, seen = [], set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for day_games in ex.map(one, days):
            for g in day_games:
                if g["id"] not in seen:
                    seen.add(g["id"])
                    games.append(g)
    games.sort(key=lambda g: g["date"])
    return games


def fetch_nfl():
    """Day pulls over the two season windows — the week form
    of the scoreboard route currently returns no linescores,
    the date form does (verified 2026-10-24)."""
    games = fetch_day_ranges("football/nfl",
                             datetime(2024, 9, 5),
                             datetime(2025, 1, 5), "nfl24")
    games += fetch_day_ranges("football/nfl",
                              datetime(2025, 9, 4),
                              datetime(2026, 1, 4), "nfl25")
    games.sort(key=lambda g: g["date"])
    return games


def norm_sf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def rates_from(gf, ga, gp, league_mean):
    """totals-lane shrinkage: off/def multipliers per team."""
    out = {}
    for t in gp:
        off = ((gf[t] + PRIOR * league_mean)
               / (gp[t] + PRIOR)) / league_mean
        deff = ((ga[t] + PRIOR * league_mean)
                / (gp[t] + PRIOR)) / league_mean
        out[t] = {"off": off, "def": deff, "gp": gp[t]}
    return out


def exam_us(games, seg_fn, burn_in, label, naive_margin="half"):
    """Walk-forward exam for a US segment lane. seg_fn(game)
    -> (home_seg_pts, away_seg_pts). naive_margin="half" is
    the R5 protocol (naive margin = half the full-game
    margin, sigma sqrt(1/2) x) used for the half lanes;
    "share" (R6 quarter lanes) scales the naive margin by
    the expanding segment/full total share s and its sigma
    by sqrt(s) — the same scaled-naive bar, with the share
    the segment actually occupies."""
    gp, gf_s, ga_s = {}, {}, {}          # segment scores
    gf_f, ga_f = {}, {}                  # full scores
    seg_tot_hist, seg_mgn_hist = [], []
    res_t, res_m = [], []                # segment residuals
    res_ft, res_fm = [], []              # full-game residuals
    shares = []
    seg_h_sum = seg_a_sum = full_h_sum = full_a_sum = 0
    seg_h_n = 0
    n = 0
    mae_t = mae_tn = mae_m = mae_mn = 0.0
    br_t = br_tn = br_m = br_mn = 0.0
    for g in games:
        hs, as_ = seg_fn(g)
        seg_tot, seg_mgn = hs + as_, hs - as_
        full_tot, full_mgn = g["hs"] + g["as"], g["hs"] - g["as"]
        for t in (g["home"], g["away"]):
            gp.setdefault(t, 0)
            gf_s.setdefault(t, 0)
            ga_s.setdefault(t, 0)
            gf_f.setdefault(t, 0)
            ga_f.setdefault(t, 0)
        if len(seg_tot_hist) >= burn_in:
            lm_s = statistics.mean(seg_tot_hist[-400:])
            # home/away segment league rates from running sums
            lh_s = seg_h_sum / max(seg_h_n, 1)
            la_s = seg_a_sum / max(seg_h_n, 1)
            r_s = rates_from(gf_s, ga_s, gp, (lh_s + la_s) / 2)
            lh = lh_s * r_s[g["home"]]["off"] * r_s[g["away"]]["def"]
            la = la_s * r_s[g["away"]]["off"] * r_s[g["home"]]["def"]
            mu_t, mu_m = lh + la, lh - la
            sig_t = statistics.pstdev(res_t) if len(res_t) > 30 \
                else lm_s * 0.24
            sig_m = statistics.pstdev(res_m) if len(res_m) > 30 \
                else lm_s * 0.30
            # naive: scaled full-game baseline
            lh_f = full_h_sum / max(seg_h_n, 1)
            la_f = full_a_sum / max(seg_h_n, 1)
            r_f = rates_from(gf_f, ga_f, gp, (lh_f + la_f) / 2)
            lf_h = lh_f * r_f[g["home"]]["off"] * r_f[g["away"]]["def"]
            lf_a = la_f * r_f[g["away"]]["off"] * r_f[g["home"]]["def"]
            mu_ft = lf_h + lf_a
            s = statistics.mean(shares) if shares else 0.5
            sig_ft = statistics.pstdev(res_ft) if len(res_ft) > 30 \
                else mu_ft * 0.24
            mu_tn = s * mu_ft
            sig_tn = s * sig_ft
            # variance scales with the time share: the naive
            # margin sigma is sqrt(share) x the full-game
            # margin sigma (tracked from the full model's own
            # walk-forward residuals). For halves the share
            # is fixed at 1/2 (the R5 protocol); for quarters
            # it is the expanding segment share s.
            sig_fm = statistics.pstdev(res_fm) if len(res_fm) > 30 \
                else sig_ft
            if naive_margin == "share":
                mu_mn = s * (lf_h - lf_a)
                sig_mn = math.sqrt(s) * sig_fm
            else:
                mu_mn = 0.5 * (lf_h - lf_a)
                sig_mn = math.sqrt(0.5) * sig_fm
            # reference lines from expanding medians
            l_star = round(statistics.median(seg_tot_hist) - 0.5) + 0.5
            l_marg = round(statistics.median(seg_mgn_hist) - 0.5) + 0.5
            mae_t += abs(mu_t - seg_tot)
            mae_tn += abs(mu_tn - seg_tot)
            mae_m += abs(mu_m - seg_mgn)
            mae_mn += abs(mu_mn - seg_mgn)
            y_over = 1.0 if seg_tot > l_star else 0.0
            br_t += (1 - norm_sf((l_star - mu_t) / sig_t)
                     - y_over) ** 2
            br_tn += (1 - norm_sf((l_star - mu_tn) / sig_tn)
                      - y_over) ** 2
            y_cov = 1.0 if seg_mgn > l_marg else 0.0
            br_m += (1 - norm_sf((l_marg - mu_m) / sig_m)
                     - y_cov) ** 2
            br_mn += (1 - norm_sf((l_marg - mu_mn) / sig_mn)
                      - y_cov) ** 2
            n += 1
            res_t.append(seg_tot - mu_t)
            res_m.append(seg_mgn - mu_m)
            res_ft.append(full_tot - mu_ft)
            res_fm.append(full_mgn - (lf_h - lf_a))
        # update with the actual game (segment + full)
        seg_tot_hist.append(seg_tot)
        seg_mgn_hist.append(seg_mgn)
        if full_tot:
            shares.append(seg_tot / full_tot)
        seg_h_sum += hs
        seg_a_sum += as_
        seg_h_n += 1
        full_h_sum += g["hs"]
        full_a_sum += g["as"]
        gf_s[g["home"]] += hs
        ga_s[g["home"]] += as_
        gf_s[g["away"]] += as_
        ga_s[g["away"]] += hs
        gf_f[g["home"]] += g["hs"]
        ga_f[g["home"]] += g["as"]
        gf_f[g["away"]] += g["as"]
        ga_f[g["away"]] += g["hs"]
        gp[g["home"]] += 1
        gp[g["away"]] += 1
    # final shipped state
    lh_s = seg_h_sum / seg_h_n
    la_s = seg_a_sum / seg_h_n
    teams = rates_from(gf_s, ga_s, gp, (lh_s + la_s) / 2)
    proto = ("walk-forward (rates from prior games only); "
             "naive = scaled full-game baseline (expanding "
             "segment/full share for totals, "
             + ("half the full-game margin for spreads)"
                if naive_margin == "half" else
                "the segment share of the full-game margin "
                "for spreads, sigma scaled by sqrt(share))"))
    bt = {"n": n,
          "mae_total": round(mae_t / n, 3),
          "mae_total_naive": round(mae_tn / n, 3),
          "brier_total": round(br_t / n, 4),
          "brier_total_naive": round(br_tn / n, 4),
          "mae_margin": round(mae_m / n, 3),
          "mae_margin_naive": round(mae_mn / n, 3),
          "brier_margin": round(br_m / n, 4),
          "brier_margin_naive": round(br_mn / n, 4),
          "protocol": proto}
    passed = (bt["mae_total"] < bt["mae_total_naive"]
              and bt["brier_total"] < bt["brier_total_naive"]
              and bt["mae_margin"] < bt["mae_margin_naive"]
              and bt["brier_margin"] < bt["brier_margin_naive"])
    return {"status": "FITTED" if passed else "FAILED-EXAM",
            "league": {"LH1": round(lh_s, 3), "LA1": round(la_s, 3),
                       "share": round(statistics.mean(shares), 4)},
            "sigma_total": round(statistics.pstdev(res_t), 3),
            "sigma_margin": round(statistics.pstdev(res_m), 3),
            "teams": {t: {"off": round(v["off"], 4),
                          "def": round(v["def"], 4), "gp": v["gp"]}
                      for t, v in sorted(teams.items())},
            "backtest": bt, "n_history": len(games)}


def exam_nhl_1p(games):
    """Poisson first-period totals vs league-mean naive."""
    gp, gf, ga = {}, {}, {}
    hist = []
    res = []
    n = 0
    mae = mae_n = br = br_n = 0.0
    h_sum = a_sum = cnt = 0

    def pois_pmf(k, lam):
        return math.exp(-lam) * lam ** k / math.factorial(k)

    def p_over_15(mu):
        return 1.0 - sum(pois_pmf(k, mu) for k in range(2))

    for g in games:
        hp, ap = g["h_ls"][0], g["a_ls"][0]
        tot = hp + ap
        for t in (g["home"], g["away"]):
            gp.setdefault(t, 0)
            gf.setdefault(t, 0)
            ga.setdefault(t, 0)
        if len(hist) >= 100:
            lm = (h_sum + a_sum) / (2 * cnt)
            lh_m, la_m = h_sum / cnt, a_sum / cnt
            r = rates_from(gf, ga, gp, lm)
            mu = (lh_m * r[g["home"]]["off"] * r[g["away"]]["def"]
                  + la_m * r[g["away"]]["off"]
                  * r[g["home"]]["def"])
            mu_n = statistics.mean(hist)
            mae += abs(mu - tot)
            mae_n += abs(mu_n - tot)
            y = 1.0 if tot > 1.5 else 0.0
            br += (p_over_15(mu) - y) ** 2
            br_n += (p_over_15(mu_n) - y) ** 2
            n += 1
            res.append(tot - mu)
        hist.append(tot)
        h_sum += hp
        a_sum += ap
        cnt += 1
        gf[g["home"]] += hp
        ga[g["home"]] += ap
        gf[g["away"]] += ap
        ga[g["away"]] += hp
        gp[g["home"]] += 1
        gp[g["away"]] += 1
    lm = (h_sum + a_sum) / (2 * cnt)
    teams = rates_from(gf, ga, gp, lm)
    bt = {"n": n, "mae_model": round(mae / n, 3),
          "mae_naive": round(mae_n / n, 3),
          "brier_model": round(br / n, 4),
          "brier_naive": round(br_n / n, 4),
          "protocol": "walk-forward (rates from prior games "
                      "only); Brier on over 1.5; naive = "
                      "expanding league-mean 1P total (Poisson)"}
    passed = bt["mae_model"] < bt["mae_naive"] \
        and bt["brier_model"] < bt["brier_naive"]
    return {"status": "FITTED" if passed else "FAILED-EXAM",
            "league": {"LH1P": round(h_sum / cnt, 3),
                       "LA1P": round(a_sum / cnt, 3),
                       "mean_total": round(statistics.mean(hist), 3)},
            "teams": {t: {"off": round(v["off"], 4),
                          "def": round(v["def"], 4), "gp": v["gp"]}
                      for t, v in sorted(teams.items())},
            "backtest": bt, "n_history": len(games)}


def _pois_grid(lh, la, maxg=12):
    """(p_home, p_draw, p_away) for independent Poissons."""
    ph = [math.exp(-lh) * lh ** k / math.factorial(k)
          for k in range(maxg + 1)]
    pa = [math.exp(-la) * la ** k / math.factorial(k)
          for k in range(maxg + 1)]
    hw = dr = aw = 0.0
    for i in range(maxg + 1):
        for j in range(maxg + 1):
            p = ph[i] * pa[j]
            if i > j:
                hw += p
            elif i == j:
                dr += p
            else:
                aw += p
    return hw, dr, aw


def _p_over_15(mu):
    return 1.0 - sum(math.exp(-mu) * mu ** k
                     / math.factorial(k) for k in range(2))


def exam_nhl_periods(games):
    """R7: walk-forward exam of every NHL period on the
    total and moneyline forms (see the module header for
    the pre-stated bars). One pass; state tracked per
    period. The 1P totals numbers this produces are a
    cross-check on the shipped R5 nhl-1p exam (same
    protocol), NOT a replacement for it — the shipped
    lane's totals block stays verbatim in main(); this
    exam's 1P contribution is its moneyline form."""
    periods = (0, 1, 2)
    gp = {}
    gf = {p: {} for p in periods}
    ga = {p: {} for p in periods}
    h_sum = {p: 0 for p in periods}
    a_sum = {p: 0 for p in periods}
    hist = {p: [] for p in periods}
    acc = {p: {"n": 0, "mae_t": 0.0, "mae_tn": 0.0,
               "br_t": 0.0, "br_tn": 0.0, "br3": 0.0,
               "br3n": 0.0, "mae_m": 0.0, "mae_mn": 0.0}
           for p in periods}
    cnt = 0
    for g in games:
        if len(g["h_ls"]) < 3 or len(g["a_ls"]) < 3:
            continue
        for t in (g["home"], g["away"]):
            gp.setdefault(t, 0)
            for p in periods:
                gf[p].setdefault(t, 0)
                ga[p].setdefault(t, 0)
        if cnt >= 100:
            for p in periods:
                hp, ap = g["h_ls"][p], g["a_ls"][p]
                tot, mgn = hp + ap, hp - ap
                lm = (h_sum[p] + a_sum[p]) / (2 * cnt)
                lh_m, la_m = h_sum[p] / cnt, a_sum[p] / cnt
                r = rates_from(gf[p], ga[p], gp, lm)
                lam_h = lh_m * r[g["home"]]["off"] \
                    * r[g["away"]]["def"]
                lam_a = la_m * r[g["away"]]["off"] \
                    * r[g["home"]]["def"]
                mu = lam_h + lam_a
                mu_n = statistics.mean(hist[p])
                a_ = acc[p]
                a_["mae_t"] += abs(mu - tot)
                a_["mae_tn"] += abs(mu_n - tot)
                y = 1.0 if tot > 1.5 else 0.0
                a_["br_t"] += (_p_over_15(mu) - y) ** 2
                a_["br_tn"] += (_p_over_15(mu_n) - y) ** 2
                ph, pd_, pa = _pois_grid(lam_h, lam_a)
                nh, nd, na = _pois_grid(lh_m, la_m)
                yh = 1.0 if hp > ap else 0.0
                yd = 1.0 if hp == ap else 0.0
                ya = 1.0 - yh - yd
                a_["br3"] += (ph - yh) ** 2 + (pd_ - yd) ** 2 \
                    + (pa - ya) ** 2
                a_["br3n"] += (nh - yh) ** 2 + (nd - yd) ** 2 \
                    + (na - ya) ** 2
                a_["mae_m"] += abs((lam_h - lam_a) - mgn)
                a_["mae_mn"] += abs((lh_m - la_m) - mgn)
                a_["n"] += 1
        for p in periods:
            hp, ap = g["h_ls"][p], g["a_ls"][p]
            hist[p].append(hp + ap)
            h_sum[p] += hp
            a_sum[p] += ap
            gf[p][g["home"]] += hp
            ga[p][g["home"]] += ap
            gf[p][g["away"]] += ap
            ga[p][g["away"]] += hp
        gp[g["home"]] += 1
        gp[g["away"]] += 1
        cnt += 1
    out = {}
    for p in periods:
        lm = (h_sum[p] + a_sum[p]) / (2 * cnt)
        teams = rates_from(gf[p], ga[p], gp, lm)
        a_ = acc[p]
        n = a_["n"]
        tot_bt = {"n": n,
                  "mae_model": round(a_["mae_t"] / n, 3),
                  "mae_naive": round(a_["mae_tn"] / n, 3),
                  "brier_model": round(a_["br_t"] / n, 4),
                  "brier_naive": round(a_["br_tn"] / n, 4),
                  "protocol": "walk-forward (period rates "
                              "from prior games only); Brier "
                              "on over 1.5; naive = expanding "
                              "league-mean period total "
                              "(Poisson) — the R5 1P protocol "
                              "per period"}
        ml_bt = {"n": n,
                 "brier3_model": round(a_["br3"] / n, 4),
                 "brier3_naive": round(a_["br3n"] / n, 4),
                 "mae_margin_model": round(a_["mae_m"] / n, 3),
                 "mae_margin_naive": round(a_["mae_mn"] / n, 3),
                 "protocol": "walk-forward (period rates "
                             "from prior games only); period "
                             "result H/D/A off the independent-"
                             "Poisson grid; naive = the same "
                             "grid on expanding league-mean "
                             "home/away period rates; margin "
                             "MAE on lam_h - lam_a vs the "
                             "league-mean margin"}
        tot_ok = tot_bt["mae_model"] < tot_bt["mae_naive"] \
            and tot_bt["brier_model"] < tot_bt["brier_naive"]
        ml_ok = ml_bt["brier3_model"] < ml_bt["brier3_naive"] \
            and ml_bt["mae_margin_model"] \
            < ml_bt["mae_margin_naive"]
        out[p + 1] = {
            "league": {"LH": round(h_sum[p] / cnt, 3),
                       "LA": round(a_sum[p] / cnt, 3),
                       "mean_total":
                           round(statistics.mean(hist[p]), 3)},
            "teams": {t: {"off": round(v["off"], 4),
                          "def": round(v["def"], 4),
                          "gp": v["gp"]}
                      for t, v in sorted(teams.items())},
            "forms": {
                "total": dict(tot_bt,
                              status="FITTED" if tot_ok
                              else "FAILED-EXAM"),
                "moneyline": dict(ml_bt,
                                  status="FITTED" if ml_ok
                                  else "FAILED-EXAM")},
            "backtest": tot_bt,
            "n_history": cnt}
    return out


GUY6 = os.environ.get("BETFI_GUY6", "/tmp/guy6")


def fetch_ncaaf():
    """R6: NCAAF (FBS, ESPN groups=80) day pulls, fetched by
    /tmp/guy6/fetch_ncaaf.py into per-day files + a combined
    games file + a coverage manifest (events seen vs games
    with complete linescores). Returns (games, coverage,
    names) or (None, None, None) when the pull is absent."""
    gp = os.path.join(GUY6, "ncaaf_games.json")
    if not os.path.exists(gp):
        return None, None, None
    with open(gp, encoding="utf-8") as f:
        games = json.load(f)
    cov = None
    cp = os.path.join(GUY6, "ncaaf_coverage.json")
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as f:
            cov = json.load(f)
    names = {}
    np_ = os.path.join(GUY6, "ncaaf_names.json")
    if os.path.exists(np_):
        with open(np_, encoding="utf-8") as f:
            names = json.load(f)
    return games, cov, names


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--lane="):
            only = a.split("=", 1)[1]
    out_path = args[0] if args else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "data", "v5-segments.json")
    doc = {}
    lanes = {}
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            doc = json.load(f)
        lanes = (doc.get("lanes") or {})
    half = lambda g: (g["h_ls"][0] + g["h_ls"][1],
                      g["a_ls"][0] + g["a_ls"][1])  # noqa: E731
    q1 = lambda g: (g["h_ls"][0], g["a_ls"][0])  # noqa: E731
    q2 = lambda g: (g["h_ls"][1], g["a_ls"][1])  # noqa: E731
    if only in (None, "nba"):
        print("fetching NBA day ranges (2024-25 + 2025-26)...",
              flush=True)
        nba = fetch_day_ranges("basketball/nba",
                               datetime(2024, 10, 22),
                               datetime(2026, 4, 13), "nba")
        print(f"  nba games with linescores: {len(nba)}")
        lanes["nba-1h"] = exam_us(nba, half, 100, "nba-1h")
        print(f"  nba-1h: {lanes['nba-1h']['status']} "
              f"{lanes['nba-1h']['backtest']}")
    if only in (None, "nfl"):
        print("fetching NFL weeks (2024 + 2025)...", flush=True)
        nfl = fetch_nfl()
        print(f"  nfl games with linescores: {len(nfl)}")
        lanes["nfl-1h"] = exam_us(nfl, half, 32, "nfl-1h")
        print(f"  nfl-1h: {lanes['nfl-1h']['status']} "
              f"{lanes['nfl-1h']['backtest']}")
    if only in (None, "nhl"):
        print("fetching NHL day ranges (2024-25 + 2025-26)...",
              flush=True)
        nhl = fetch_day_ranges("hockey/nhl",
                               datetime(2024, 10, 4),
                               datetime(2026, 4, 17), "nhl")
        print(f"  nhl games with linescores: {len(nhl)}")
        lanes["nhl-1p"] = exam_nhl_1p(nhl)
        print(f"  nhl-1p: {lanes['nhl-1p']['status']} "
              f"{lanes['nhl-1p']['backtest']}")
    if only in (None, "nba1q"):
        # R6 quarter forms: same cached linescores, Q1 only,
        # same machinery, share-scaled naive (see exam_us).
        nba = fetch_day_ranges("basketball/nba",
                               datetime(2024, 10, 22),
                               datetime(2026, 4, 13), "nba")
        lanes["nba-1q"] = exam_us(nba, q1, 100, "nba-1q",
                                  naive_margin="share")
        lanes["nba-1q"]["form"] = "1st quarter"
        print(f"  nba-1q: {lanes['nba-1q']['status']} "
              f"{lanes['nba-1q']['backtest']}")
    if only in (None, "nfl1q"):
        nfl = fetch_nfl()
        lanes["nfl-1q"] = exam_us(nfl, q1, 32, "nfl-1q",
                                  naive_margin="share")
        lanes["nfl-1q"]["form"] = "1st quarter"
        print(f"  nfl-1q: {lanes['nfl-1q']['status']} "
              f"{lanes['nfl-1q']['backtest']}")
    if only in (None, "ncaaf"):
        games, cov, names = fetch_ncaaf()
        if games is None:
            print("  ncaaf: /tmp/guy6 pull absent — lane NOT "
                  "examined (named, not assumed)")
        else:
            print(f"  ncaaf games with linescores: {len(games)}"
                  f" (coverage: {cov})")
            lane = exam_us(games, half, 100, "ncaaf-1h")
            lane["coverage"] = cov
            lane["team_names"] = names
            lanes["ncaaf-1h"] = lane
            print(f"  ncaaf-1h: {lane['status']} "
                  f"{lane['backtest']}")
    if only in (None, "ncaaf1q", "ncaaf2q"):
        # R7: NCAAF quarters — the R6 remainder's unexamined
        # form. Same linescores (100% complete per the R6
        # coverage manifest), same exam_us machinery, the
        # R6 share-scaled naive.
        games, cov, names = fetch_ncaaf()
        if games is None:
            print("  ncaaf quarters: /tmp/guy6 pull absent — "
                  "lanes NOT examined (named, not assumed)")
        else:
            for lane_key, fn, form in (
                    ("ncaaf-1q", q1, "1st quarter"),
                    ("ncaaf-2q", q2, "2nd quarter")):
                if only not in (None, "ncaaf1q", "ncaaf2q"):
                    continue
                if only == "ncaaf1q" and lane_key != "ncaaf-1q":
                    continue
                if only == "ncaaf2q" and lane_key != "ncaaf-2q":
                    continue
                lane = exam_us(games, fn, 100, lane_key,
                               naive_margin="share")
                lane["coverage"] = cov
                lane["team_names"] = names
                lane["form"] = form
                lanes[lane_key] = lane
                print(f"  {lane_key}: {lane['status']} "
                      f"{lane['backtest']}")
    if only in (None, "nhlperiods"):
        # R7: NHL period forms. nhl-1p keeps its shipped R5
        # totals block verbatim and gains the moneyline
        # form; nhl-2p / nhl-3p ship whole.
        print("fetching NHL day ranges (periods)...",
              flush=True)
        nhl = fetch_day_ranges("hockey/nhl",
                               datetime(2024, 10, 4),
                               datetime(2026, 4, 17), "nhl")
        print(f"  nhl games with linescores: {len(nhl)}")
        per = exam_nhl_periods(nhl)
        for pnum in (2, 3):
            blk = per[pnum]
            forms = blk["forms"]
            blk["status"] = "FITTED" if any(
                f["status"] == "FITTED"
                for f in forms.values()) else "FAILED-EXAM"
            blk["form"] = f"{pnum}nd period" if pnum == 2 \
                else "3rd period"
            lanes[f"nhl-{pnum}p"] = blk
            print(f"  nhl-{pnum}p: total "
                  f"{forms['total']['status']} "
                  f"{forms['total']['mae_model']} vs "
                  f"{forms['total']['mae_naive']} / "
                  f"{forms['total']['brier_model']} vs "
                  f"{forms['total']['brier_naive']}; moneyline "
                  f"{forms['moneyline']['status']} brier3 "
                  f"{forms['moneyline']['brier3_model']} vs "
                  f"{forms['moneyline']['brier3_naive']} "
                  f"(n={forms['total']['n']})")
        one = lanes.get("nhl-1p")
        if one is not None:
            bt1 = one.get("backtest") or {}
            one["forms"] = {
                "total": {"status": one.get("status"),
                          "mae_model": bt1.get("mae_model"),
                          "mae_naive": bt1.get("mae_naive"),
                          "brier_model": bt1.get("brier_model"),
                          "brier_naive": bt1.get("brier_naive"),
                          "n": bt1.get("n"),
                          "protocol": bt1.get("protocol"),
                          "note": "the shipped R5 totals exam, "
                                  "verbatim"},
                "moneyline": per[1]["forms"]["moneyline"]}
            one["period_forms_exam"] = (
                "R7: moneyline form examined in "
                "exam_nhl_periods (same walk-forward pass "
                "as 2P/3P); the totals form is the shipped "
                "R5 exam")
            print(f"  nhl-1p moneyline form: "
                  f"{per[1]['forms']['moneyline']['status']} "
                  f"brier3 "
                  f"{per[1]['forms']['moneyline']['brier3_model']}"
                  f" vs "
                  f"{per[1]['forms']['moneyline']['brier3_naive']}"
                  f"; 1P totals cross-check from the R7 pass: "
                  f"MAE {per[1]['forms']['total']['mae_model']} "
                  f"vs shipped "
                  f"{bt1.get('mae_model')}, Brier "
                  f"{per[1]['forms']['total']['brier_model']} "
                  f"vs shipped {bt1.get('brier_model')}")
    # Preserve the rest of the doc (soccer-1h lives here too;
    # fit_soccer_halves.py owns that block).
    doc["fitted_at"] = datetime.now(timezone.utc).isoformat()
    doc["source"] = ("ESPN scoreboard linescores (NBA/NHL day "
                     "ranges, NFL day pulls, NCAAF FBS day "
                     "pulls R6); completed seasons 2024-25+"
                     "2025-26 (NBA/NHL), 2024+2025 (NFL/NCAAF)")
    doc["params"] = {"prior_games": PRIOR}
    doc["lanes"] = lanes
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
