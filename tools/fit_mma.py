#!/usr/bin/env python3
"""fit_mma.py — BetFi Xii (fix-guy R3; attempt 2, pricing Build E):
the MMA fit builder.

TWO SOURCES, one decided-fight sequence:
  (a) raw_total_fight_data.csv — the ufcstats.com scrape published
      as the Kaggle dataset rajeevratan84/ufcdata, mirrored on
      GitHub at pantazos/kaggle-UFC-data-CSV (semicolon-delimited;
      R_fighter / B_fighter / Winner / date / Fight_type / win_by
      per fight). This snapshot actually spans 1994-03-11 ..
      2021-03-20 (the R3 docstring said 1993..2021 — the file's
      own dates say otherwise).
  (b) the ESPN MMA scoreboard API (site.api.espn.com
      /apis/site/v2/sports/mma/ufc/scoreboard, monthly date-range
      queries, cached under data/cache/espn-ufc/): every UFC
      bout 2021-03-06 .. 2026-10-24 at build time — winner flag,
      weight class per bout; NO win_by (the scoreboard carries
      no method). ufcstats.com itself is behind a JavaScript
      browser-check from this machine (verified 2026-10-27:
      plain fetch returns the challenge page, not data), so the
      ESPN route is the verified post-2021 source.
  Seam: the sources overlap 2021-03-06..2021-03-20; a bout with
  the same (winner, loser) pair dated within 4 days in both is
  one fight — the CSV copy (with method) is kept.

ATTEMPT 1 (shipped 2026-10-24, FAILED-EXAM): sequential fighter
Elo, K=32, start 1500. Walk-forward Brier 0.2454 vs the
career-win-rate naive 0.2451, n=5,902 — a loss by 0.0003.

ATTEMPT 2 — PRE-REGISTERED (fixed before the exam ran; the
lista_m discipline: features and model form stated up front,
ONE attempt, bar unmoved). A walk-forward logistic
Bradley-Terry index over per-fighter state built ONLY from
prior fights. For fighter f at prediction time:
  f1 = elo/100 (sequential Elo, K=32, start 1500, updated with
       the standard Elo expectation — independent of this layer)
  f2 = shrunk career win rate (w+2)/(games+4)  [the naive itself]
  f3 = finish rate among wins with KNOWN method:
       (fin_wins+1)/(known_wins+3); finish = win_by in
       {KO/TKO, TKO - Doctor's Stoppage, Could Not Continue,
        Submission}
  f4 = stoppage-loss rate among losses with KNOWN method:
       (fin_losses+1)/(known_losses+3)
  f5 = log1p(career fights)/2
  f6 = current streak/3 (signed, capped +-5)
  f7 = -log1p(days since last fight)/5 (debutant: days = 365)
  Method-unknown (ESPN-era) fights update f1/f2/f5/f6/f7, the
  record and the last-seen class, but never the f3/f4 counters
  (neither numerator nor denominator).
  logit P(A beats B) = sum_k beta_k * (f_k(A) - f_k(B)); no
  intercept (the corner is arbitrary). beta by penalized
  logistic regression (Newton/IRLS, L2 lambda=1.0), refit
  walk-forward: first fit once >= 750 decided fights of history
  exist, then every Jan 1, always on fights strictly before
  the refit date with fight-time features; between refits beta
  is frozen. Before the first beta, predictions are the plain
  Elo sigmoid (the attempt-1 form).

EXAM — the lane's own protocol: over ALL decided fights in the
combined window, Brier of the probability assigned to the
actual winner vs the attempt-1 naive, p = wr(winner) /
(wr(winner) + wr(loser)) from the same running shrunk rates.
PASS iff the model Brier is strictly below the naive Brier.
Draws / no-contests are excluded from ratings and the exam,
counted (110 in the CSV snapshot; the ESPN side's no-winner
bouts likewise).

SHIPPED ARTIFACT: beta_final = the same IRLS spec refit on all
fights; each fighter's engine rating is the scalar
s = (400/ln 10) * sum_k beta_k * f_k(final state), so the
engine's unchanged math — p = 1/(1 + 10**(-(sA - sB)/400)) —
reproduces the model's logit at final state exactly. If the
exam fails, the artifact still ships (the engine's exam gate
keeps the lane dark) with attempt 2 recorded in the history.

Usage: fit_mma.py [out_path]  (default ../data/v5-mma.json)
CSV cached under data/cache/ (MMA_SRC_DIR overrides); ESPN
monthly payloads cached under data/cache/espn-ufc/.
"""
import csv
import io
import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

K = 32.0
START = 1500.0
URL = ("https://raw.githubusercontent.com/pantazos/"
       "kaggle-UFC-data-CSV/master/raw_total_fight_data.csv")
ESPN_URL = ("https://site.api.espn.com/apis/site/v2/sports/mma/"
            "ufc/scoreboard?dates={}-{}&limit=200")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
TREE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.environ.get("MMA_SRC_DIR",
                         os.path.join(TREE, "data", "cache"))
ESPN_DIR = os.path.join(TREE, "data", "cache", "espn-ufc")
FINISHES = {"KO/TKO", "TKO - Doctor's Stoppage",
            "Could Not Continue", "Submission"}
L2 = 1.0
FIRST_FIT_N = 750
FEATURE_NAMES = ["elo_per100", "career_win_rate_shrunk",
                 "finish_rate_known_wins",
                 "stoppage_loss_rate_known_losses",
                 "log1p_fights_over2", "streak_over3",
                 "neg_log1p_days_since_over5"]


def weight_class(fight_type):
    t = (fight_type or "").strip()
    for pre in ("UFC ", "WSOF ", "Strikeforce "):
        if t.startswith(pre):
            t = t[len(pre):]
    for suf in (" Title Bout", " Bout", " Championship"):
        if t.endswith(suf):
            t = t[:-len(suf)]
    return t.strip() or "Unknown"


def collect_csv():
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
        fights.append({"date": d.strftime("%Y-%m-%d"), "winner": w,
                       "loser": loser,
                       "weight_class": weight_class(
                           r.get("Fight_type")),
                       "win_by": (r.get("win_by") or "").strip(),
                       "source": "csv"})
    return fights, skipped


def collect_espn():
    """Every UFC bout from 2021-03 onward, monthly scoreboard
    queries, cached. Returns (decided fights, no-winner count)."""
    os.makedirs(ESPN_DIR, exist_ok=True)
    now = datetime.now(timezone.utc)
    months = []
    y, m = 2021, 3
    while (y, m) <= (now.year, now.month):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    events, skipped = {}, 0
    for (y, m) in months:
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        start, end = f"{y}{m:02d}01", f"{ny}{nm:02d}01"
        path = os.path.join(ESPN_DIR, f"{start}-{end}.json")
        if os.path.exists(path):
            with open(path) as f:
                d = json.load(f)
        else:
            req = urllib.request.Request(
                ESPN_URL.format(start, end), headers=UA)
            with urllib.request.urlopen(req, timeout=60) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            with open(path, "w") as f:
                json.dump(d, f)
            time.sleep(0.3)
        for e in d.get("events", []):
            events[e["id"]] = e
    fights = []
    for e in events.values():
        edate = (e.get("date") or "")[:10]
        for c in e.get("competitions", []):
            cs = c.get("competitors", [])
            if len(cs) != 2:
                continue
            winners = [x for x in cs if x.get("winner")]
            if len(winners) != 1:
                skipped += 1
                continue
            w = winners[0]["athlete"]["fullName"].strip()
            l = [x for x in cs if not x.get("winner")][0]
            l = l["athlete"]["fullName"].strip()
            wc = ((c.get("type") or {}).get("abbreviation")
                  or "").strip() or "Unknown"
            fights.append({"date": edate, "winner": w,
                           "loser": l, "weight_class": wc,
                           "win_by": "", "source": "espn"})
    return fights, skipped


def merge_fights(csv_fights, espn_fights):
    """CSV first (it carries method); drop an ESPN bout whose
    (winner, loser) pair matches a CSV bout within 4 days."""
    def key(f):
        return (f["winner"], f["loser"])
    csv_keys = {}
    for f in csv_fights:
        csv_keys.setdefault(key(f), []).append(
            datetime.strptime(f["date"], "%Y-%m-%d"))
    merged, dropped = list(csv_fights), 0
    for f in espn_fights:
        d = datetime.strptime(f["date"], "%Y-%m-%d")
        if any(abs((d - cd).days) <= 4
               for cd in csv_keys.get(key(f), [])):
            dropped += 1
            continue
        merged.append(f)
    merged.sort(key=lambda f: f["date"])
    return merged, dropped


class State:
    __slots__ = ("elo", "games", "wins", "known_wins", "fin_wins",
                 "known_losses", "fin_losses", "streak", "last_date",
                 "last_class", "rec_w", "rec_l")

    def __init__(self):
        self.elo = START
        self.games = 0
        self.wins = 0
        self.known_wins = 0
        self.fin_wins = 0
        self.known_losses = 0
        self.fin_losses = 0
        self.streak = 0
        self.last_date = None
        self.last_class = "Unknown"
        self.rec_w = 0
        self.rec_l = 0


def features(st, fight_date):
    if st.last_date is None:
        days = 365.0
    else:
        days = max(0.0, (fight_date - st.last_date).days)
    return [
        st.elo / 100.0,
        (st.wins + 2.0) / (st.games + 4.0),
        (st.fin_wins + 1.0) / (st.known_wins + 3.0),
        (st.fin_losses + 1.0) / (st.known_losses + 3.0),
        math.log1p(st.games) / 2.0,
        max(-5, min(5, st.streak)) / 3.0,
        -math.log1p(days) / 5.0,
    ]


def irls(rows, dim=7, lam=L2, iters=100):
    """Penalized logistic regression on winner-oriented diff
    rows (y == 1 for every row): Bradley-Terry maximum
    likelihood by Newton-Raphson."""
    beta = [0.0] * dim
    beta[0] = math.log(10) / 4.0  # start at the attempt-1 form
    for _ in range(iters):
        grad = [-2 * lam * b for b in beta]
        hess = [[2 * lam if i == j else 0.0 for j in range(dim)]
                for i in range(dim)]
        for x in rows:
            z = sum(b * xi for b, xi in zip(beta, x))
            p = 1 / (1 + math.exp(-z)) if z > -35 else 0.0
            r = 1.0 - p
            w = p * r
            for i in range(dim):
                grad[i] += r * x[i]
                for j in range(dim):
                    hess[i][j] += w * x[i] * x[j]
        # solve hess * step = grad (Gaussian elimination)
        a = [row[:] + [grad[i]] for i, row in enumerate(hess)]
        for col in range(dim):
            piv = max(range(col, dim), key=lambda rr: abs(a[rr][col]))
            a[col], a[piv] = a[piv], a[col]
            pv = a[col][col]
            if abs(pv) < 1e-12:
                continue
            for rr in range(dim):
                if rr != col and a[rr][col] != 0.0:
                    fac = a[rr][col] / pv
                    for cc in range(col, dim + 1):
                        a[rr][cc] -= fac * a[col][cc]
        step = [a[i][dim] / a[i][i] if abs(a[i][i]) > 1e-12 else 0.0
                for i in range(dim)]
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-9:
            break
    return beta


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        TREE, "data", "v5-mma.json")
    csv_fights, csv_skipped = collect_csv()
    espn_fights, espn_skipped = collect_espn()
    fights, seam_dropped = merge_fights(csv_fights, espn_fights)
    print(f"[fit-mma] csv fights: {len(csv_fights)} "
          f"(skipped undecided: {csv_skipped}); espn fights: "
          f"{len(espn_fights)} (no-winner: {espn_skipped}); "
          f"seam duplicates dropped: {seam_dropped}; "
          f"combined decided: {len(fights)}")
    if len(fights) < 6000:
        raise SystemExit("[fit-mma] too few fights — refusing "
                         "to fit on a partial pull")
    states = {}

    def st(name):
        s = states.get(name)
        if s is None:
            s = states[name] = State()
        return s

    rows = []           # fight-time feature diffs (winner - loser)
    beta = None
    next_jan = None
    brier = naive_brier = 0.0
    n = correct = 0
    for f in fights:
        fdate = datetime.strptime(f["date"], "%Y-%m-%d")
        if beta is None and len(rows) >= FIRST_FIT_N:
            beta = irls(rows)
            next_jan = fdate.year + 1
            print(f"[fit-mma] first beta fitted on {len(rows)} "
                  f"fights at {f['date']}")
        elif beta is not None and fdate.year >= next_jan:
            beta = irls(rows)
            next_jan = fdate.year + 1
        sw, sl = st(f["winner"]), st(f["loser"])
        fw, fl = features(sw, fdate), features(sl, fdate)
        diff = [a - b for a, b in zip(fw, fl)]
        rows.append(diff)
        if beta is None:
            p = 1 / (1 + 10 ** (-(sw.elo - sl.elo) / 400))
        else:
            z = sum(b * x for b, x in zip(beta, diff))
            p = 1 / (1 + math.exp(-z)) if z > -35 else 0.0
        pn = fw[1] / (fw[1] + fl[1]) if (fw[1] + fl[1]) > 0 else 0.5
        brier += (p - 1.0) ** 2
        naive_brier += (pn - 1.0) ** 2
        n += 1
        if p >= 0.5:
            correct += 1
        # state updates — Elo first (standard expectation), then
        # the bookkeeping. Method counters only when known.
        ew = 1 / (1 + 10 ** (-(sw.elo - sl.elo) / 400))
        sw.elo += K * (1 - ew)
        sl.elo += K * (0 - (1 - ew))
        method = f.get("win_by") or ""
        for s, won in ((sw, True), (sl, False)):
            s.games += 1
            if won:
                s.wins += 1
                s.rec_w += 1
                s.streak = s.streak + 1 if s.streak > 0 else 1
                if method:
                    s.known_wins += 1
                    if method in FINISHES:
                        s.fin_wins += 1
            else:
                s.rec_l += 1
                s.streak = s.streak - 1 if s.streak < 0 else -1
                if method:
                    s.known_losses += 1
                    if method in FINISHES:
                        s.fin_losses += 1
            s.last_date = fdate
            s.last_class = f["weight_class"]
    beta_final = irls(rows)
    scale = 400.0 / math.log(10)
    end_date = fights[-1]["date"]
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    elo_out = {}
    for name, s in states.items():
        fv = features(s, end_dt)
        elo_out[name] = round(scale * sum(
            b * x for b, x in zip(beta_final, fv)), 1)
    bt = {"brier": round(brier / n, 4),
          "naive_brier": round(naive_brier / n, 4),
          "accuracy": round(correct / n, 4), "n": n,
          "skipped_undecided": csv_skipped + espn_skipped,
          "protocol": "walk-forward by event date over the "
                      "combined 1994-03-11..2026-10-24 window "
                      "(features and Elo from prior fights "
                      "only; beta refit every Jan 1 on prior "
                      "fights, frozen between refits; naive = "
                      "relative running career win rate, "
                      "4-fight 0.5 prior); draws/no-contests "
                      "excluded"}
    passed = bt["brier"] < bt["naive_brier"]
    blob = {
        "sport": "mma", "league": "ufc",
        "fitted_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "source": ("ufcstats.com scrape via Kaggle "
                   "rajeevratan84/ufcdata, GitHub mirror "
                   "pantazos/kaggle-UFC-data-CSV "
                   "(raw_total_fight_data.csv; 1994-03-11.."
                   "2021-03-20, with win_by) EXTENDED by the "
                   "ESPN MMA scoreboard API (site.api.espn.com, "
                   "monthly scoreboard queries cached in "
                   "data/cache/espn-ufc; 2021-03-06..2026-10-24, "
                   "winner + weight class, no method); seam "
                   "bouts deduplicated (same winner/loser pair "
                   "within 4 days, CSV copy kept). ufcstats.com "
                   "direct is behind a JavaScript browser-check "
                   "from this machine (verified 2026-10-27)"),
        "params": {"K": K, "start_elo": START, "home_edge": 0.0,
                   "model": "logistic Bradley-Terry index over "
                            "7 per-fighter walk-forward "
                            "features; engine rating = "
                            "(400/ln10) * beta . features(final "
                            "state)",
                   "features": FEATURE_NAMES,
                   "beta": [round(b, 6) for b in beta_final],
                   "l2": L2},
        "elo": dict(sorted(elo_out.items())),
        "fights": {name: states[name].games
                   for name in sorted(states)},
        "weight_class": {name: states[name].last_class
                         for name in sorted(states)},
        "record": {name: {"w": states[name].rec_w,
                          "l": states[name].rec_l}
                   for name in sorted(states)},
        "backtest": bt,
        "attempts": [
            {"attempt": 1, "model": "sequential fighter Elo, "
                                    "K=32, start 1500",
             "window": "1994-03-11..2021-03-20 (CSV snapshot)",
             "brier": 0.2454, "naive_brier": 0.2451, "n": 5902,
             "result": "FAILED-EXAM (lost by 0.0003)"},
            {"attempt": 2,
             "model": "logistic Bradley-Terry index, 7 "
                      "walk-forward features (elo, shrunk "
                      "career win rate, finish rate, stoppage-"
                      "loss rate, log experience, streak, "
                      "recency), L2=1.0, beta refit annually "
                      "walk-forward",
             "window": f"1994-03-11..{end_date} (CSV + ESPN)",
             "brier": bt["brier"], "naive_brier": bt["naive_brier"],
             "n": n,
             "result": "PASSED" if passed else "FAILED-EXAM"}],
    }
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=1)
    print(f"[fit-mma] fighters={len(elo_out)} n={n} "
          f"brier={bt['brier']} naive={bt['naive_brier']} "
          f"acc={bt['accuracy']} -> "
          f"{'PASSED' if passed else 'FAILED-EXAM'}")
    print(f"[fit-mma] beta_final="
          f"{[round(b, 4) for b in beta_final]}")
    print(f"[fit-mma] wrote {out_path}")


if __name__ == "__main__":
    main()
