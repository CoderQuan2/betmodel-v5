#!/usr/bin/env python3
"""fit_outrights.py — BetFi Xii (fix-guy R5): the soccer
futures PILOT — title outrights by Monte Carlo season
simulation from the fitted league strengths.

Method: a league's fitted att/def strengths + league
LH/LA (the shipped v5-soccer / v5-soccer-leagues fits)
give a Poisson goal grid for any fixture. A title price
is the simulated champion share over the REMAINING
fixtures, starting from the CURRENT points/GD/GF table:
simulate every remaining fixture off its grid, add the
points, rank by points, then goal difference, then goals
for (the EPL tiebreak order), count champions.

Backtest exam (PRE-STATED bar): three completed EPL
seasons (football-data.co.uk E0 archives 2023-24,
2024-25, 2025-26). For each: fit strengths on the first
half of the season ONLY (every team has played 19 games —
190 fixtures), take the table at that point, simulate the
remaining 190 fixtures 20,000 times from those strengths,
and score the title probabilities:
  Brier  = sum over teams (p_i - y_i)^2   (y = champion)
  log-loss = -log(p_champion)
against the naive standings baseline p_i = points_i /
sum(points) at the same point (the leader-heavy share a
table-reader would quote). PASS iff the model beats the
naive on BOTH metrics in at least 2 of the 3 seasons AND
on the 3-season mean of both metrics.

If the pilot passes, the same tool writes the LIVE
artifact data/v5-outrights.json for the current EPL
season: strengths = the shipped EPL fit, table +
remaining fixtures from ESPN day pulls (2026-27 to date),
20,000 simulations. (Other leagues join when their
current-season fixture lists are pulled the same way;
the exam is EPL because the archives are complete.)

R6 EXTENSION (same simulation, same shrinkage, same
standings-share naive, same bar — champion Brier +
log-loss, >= 2/3 seasons and both means): the protocol
now runs PER LEAGUE — La Liga (SP1), Bundesliga (D1),
Serie A (I1), Ligue 1 (F1) on football-data archives
2023-24/2024-25/2025-26, and MLS on ESPN usa.1 day
pulls 2023/2024/2025. MLS's champion is the MLS Cup
winner, so its simulation adds the 2023-25 playoff
bracket (wild card, best-of-3 first round, single-game
semis/finals; drawn playoff games to a shootout modeled
as renormalized regulation win shares — stated in the
artifact). Every league ships its own exam block in
data/v5-outrights.json; a league's title outrights price
only when ITS exam passed and its live artifact built.
Title winner only — relegation / top-4 / golden boot
stay named, unexamined forms.

R7 EXTENSION (identical protocol, identical bar): the
second tiers with complete football-data fixture
archives — Championship (E1), Serie B (I2), La Liga 2
(SP2), Bundesliga 2 (D2), Ligue 2 (F2) — on the same
2023-24/2024-25/2025-26 archives. The champion is the
regular-season table top in all five (their playoffs
decide a promotion place, not the title), so the plain
table simulation is the pilot protocol unchanged. Run
alone with --tiers2 (merges into the existing artifact;
the R5/R6 leagues are not re-run).

Usage: fit_outrights.py [--no-live] [--tiers2] [out_path]
CSVs cache under /tmp/guy5/fd; MLS pulls under /tmp/guy6.
"""
import csv
import io
import json
import math
import os
import random
import sys
import urllib.request
from datetime import datetime, timezone

FD = "/tmp/guy5/fd"
SEASONS = ("2324", "2425", "2526")
SIMS = 20000
SEED = 20261024
PRIOR_GAMES = 4.0     # the engine's SOC_PRIOR_GAMES family
PRIOR_LH, PRIOR_LA = 1.35, 1.15   # placeholders, replaced by
# the engine constants at runtime (imported below)


def fetch_csv(code_season):
    season, code = code_season
    path = os.path.join(FD, f"{code}_{season}.csv")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        with open(path, encoding="utf-8-sig") as f:
            return f.read()
    url = f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
    req = urllib.request.Request(
        url, headers={"User-Agent": "BetFi-Xii fit builder "
                                   "(stdlib urllib)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8-sig", errors="replace")
    os.makedirs(FD, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def parse_games(text, with_ht=False):
    games = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            hs = int(float(row["FTHG"]))
            as_ = int(float(row["FTAG"]))
        except (KeyError, TypeError, ValueError):
            continue
        home = (row.get("HomeTeam") or "").strip()
        away = (row.get("AwayTeam") or "").strip()
        if not home or not away:
            continue
        g = {"date": row.get("Date") or "", "home": home,
             "away": away, "hs": hs, "as": as_}
        if with_ht:
            try:
                g["hth"] = int(float(row["HTHG"]))
                g["hta"] = int(float(row["HTAG"]))
            except (KeyError, TypeError, ValueError):
                g["hth"] = g["hta"] = None
        games.append(g)
    return games


def fit_strengths(games):
    """The shipped fitter's strengths snapshot (att/def with
    the engine's shrinkage), on the given games only."""
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
    L = sum(gf.values()) / total_gp if total_gp else 1.35
    LH = (hg + 10 * PRIOR_LH) / (hgames + 10) if hgames else PRIOR_LH
    LA = (ag + 10 * PRIOR_LA) / (hgames + 10) if hgames else PRIOR_LA
    st = {}
    for t in gp:
        st[t] = {
            "att": ((gf[t] + PRIOR_GAMES * L)
                    / (gp[t] + PRIOR_GAMES)) / L,
            "def": ((ga[t] + PRIOR_GAMES * L)
                    / (gp[t] + PRIOR_GAMES)) / L,
            "gp": gp[t]}
    return st, {"LH": LH, "LA": LA, "L": L}


def table_after(games):
    pts, gf, ga, played = {}, {}, {}, {}
    for g in games:
        for t in (g["home"], g["away"]):
            pts.setdefault(t, 0)
            gf.setdefault(t, 0)
            ga.setdefault(t, 0)
            played.setdefault(t, 0)
        played[g["home"]] += 1
        played[g["away"]] += 1
        gf[g["home"]] += g["hs"]
        ga[g["home"]] += g["as"]
        gf[g["away"]] += g["as"]
        ga[g["away"]] += g["hs"]
        if g["hs"] > g["as"]:
            pts[g["home"]] += 3
        elif g["hs"] < g["as"]:
            pts[g["away"]] += 3
        else:
            pts[g["home"]] += 1
            pts[g["away"]] += 1
    return pts, gf, ga, played


def pois(rng, lam):
    # Knuth for small lam (soccer goals)
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def simulate(st, lg, table, fixtures, sims=SIMS, seed=SEED):
    """table: (pts, gf, ga) dicts. fixtures: [(home, away)].
    Returns {team: champion share}."""
    pts0, gf0, ga0, _pl = table
    teams = sorted(pts0)
    lam = {}
    for h, a in fixtures:
        lh = lg["LH"] * st[h]["att"] * st[a]["def"]
        la = lg["LA"] * st[a]["att"] * st[h]["def"]
        lam[(h, a)] = (lh, la)
    wins = {t: 0 for t in teams}
    rng = random.Random(seed)
    for _ in range(sims):
        pts = dict(pts0)
        gf = dict(gf0)
        ga = dict(ga0)
        for (h, a), (lh, la) in lam.items():
            gh, ga_ = pois(rng, lh), pois(rng, la)
            gf[h] += gh
            ga[h] += ga_
            gf[a] += ga_
            ga[a] += gh
            if gh > ga_:
                pts[h] += 3
            elif gh < ga_:
                pts[a] += 3
            else:
                pts[h] += 1
                pts[a] += 1
        champ = max(teams, key=lambda t: (pts[t], gf[t] - ga[t],
                                          gf[t]))
        wins[champ] += 1
    return {t: wins[t] / sims for t in teams}


def score(probs, champ):
    brier = sum((p - (1.0 if t == champ else 0.0)) ** 2
                for t, p in probs.items())
    return brier, -math.log(max(probs.get(champ, 0.0), 1e-9))


def backtest(code="E0", seasons=SEASONS):
    rows = []
    for season in seasons:
        games = parse_games(fetch_csv((season, code)))
        teams = sorted({g["home"] for g in games}
                       | {g["away"] for g in games})
        n_teams = len(teams)
        half = n_teams * (n_teams - 1) // 2   # 190 for 20 teams
        played, remaining = games[:half], games[half:]
        st, lg = fit_strengths(played)
        table = table_after(played)
        fixtures = [(g["home"], g["away"]) for g in remaining]
        probs = simulate(st, lg, table, fixtures)
        final = table_after(games)
        champ = max(final[0], key=lambda t: (final[0][t],
                                             final[1][t]
                                             - final[2][t],
                                             final[1][t]))
        tot_pts = sum(table[0].values())
        naive = {t: table[0][t] / tot_pts for t in teams}
        b, ll = score(probs, champ)
        bn, lln = score(naive, champ)
        rows.append({"season": f"20{season[:2]}-{season[2:]}",
                     "champion": champ,
                     "p_champion_model": round(probs[champ], 4),
                     "p_champion_naive": round(naive[champ], 4),
                     "brier_model": round(b, 4),
                     "brier_naive": round(bn, 4),
                     "logloss_model": round(ll, 4),
                     "logloss_naive": round(lln, 4),
                     "sim_from": f"matchweek {n_teams - 1} "
                                 f"({half} played, {len(fixtures)} "
                                 f"simulated)",
                     "top3_model": sorted(
                         probs.items(), key=lambda kv: -kv[1])[:3]})
        r = rows[-1]
        print(f"  {r['season']}: champ {champ} — model p "
              f"{r['p_champion_model']} (Brier {b:.4f}, LL "
              f"{ll:.4f}) vs naive p {r['p_champion_naive']} "
              f"(Brier {bn:.4f}, LL {lln:.4f})")
    wins = sum(1 for r in rows
               if r["brier_model"] < r["brier_naive"]
               and r["logloss_model"] < r["logloss_naive"])
    mean_b = statistics_mean([r["brier_model"] for r in rows])
    mean_bn = statistics_mean([r["brier_naive"] for r in rows])
    mean_l = statistics_mean([r["logloss_model"] for r in rows])
    mean_ln = statistics_mean([r["logloss_naive"] for r in rows])
    passed = wins >= 2 and mean_b < mean_bn and mean_l < mean_ln
    return {"seasons": rows, "seasons_won": wins,
            "mean_brier_model": round(mean_b, 4),
            "mean_brier_naive": round(mean_bn, 4),
            "mean_logloss_model": round(mean_l, 4),
            "mean_logloss_naive": round(mean_ln, 4),
            "verdict": "PASS" if passed else "FAILED-EXAM",
            "bar": "model beats naive on Brier AND log-loss "
                   "in >= 2 of 3 seasons and on both 3-season "
                   "means",
            "sims_per_season": SIMS}


def statistics_mean(xs):
    return sum(xs) / len(xs)


def live_artifact(slug="eng.1", key="epl"):
    """Current-season outrights from ESPN fixtures/results
    (2026-27 for the European leagues): strengths refit
    in-season on the played games with the exam's shrinkage
    protocol, remaining fixtures simulated. Parameterized
    in R6 from the R5 EPL-only version — same method."""
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".."))
    import betmodel5 as b5
    fit = b5.load_soccer()
    if fit is None:
        return None, "shipped EPL fit not found"
    url = ("https://site.api.espn.com/apis/site/v2/sports/"
           f"soccer/{slug}/scoreboard?dates={{}}")
    from datetime import datetime as _dt
    games, errors = b5._fetch_days(url, _dt(2026, 8, 1),
                                   _dt(2027, 5, 31), "soccer")
    if not games:
        return None, (f"ESPN {slug} day pulls returned no "
                      "fixtures for the 2026-27 window — live "
                      "artifact cannot be built")
    # The eng.1 scoreboard window is the league season
    # itself (380 fixtures): membership = every team in the
    # fixture list. The SHIPPED fit carries last season's
    # team set (promoted sides have no strengths in it and
    # relegated sides linger), so live strengths are refit
    # on THIS season's played games with the identical
    # shrinkage protocol the backtest exam validated — the
    # artifact says so and prints n. (The shipped fit is
    # not edited; this is a simulation input, not a lane
    # fit.)
    members = sorted({g["home"] for g in games}
                     | {g["away"] for g in games})
    played = [g for g in games
              if g["final"] and g["hs"] is not None]
    fixtures = [(g["home"], g["away"]) for g in games
                if not g["final"]]
    st, lg = fit_strengths([{"home": g["home"],
                              "away": g["away"], "hs": g["hs"],
                              "as": g["as"]} for g in played])
    if set(st) != set(members):
        return None, ("strength refit does not cover the "
                      f"league: {sorted(set(members) - set(st))}")
    table = table_after([{"home": g["home"], "away": g["away"],
                          "hs": g["hs"], "as": g["as"]}
                         for g in played])
    for t in st:
        for d in table[:3]:
            d.setdefault(t, 0)
    probs = simulate(st, lg, table, fixtures)
    names = {}
    for g in games:
        names[g["home"]] = g.get("home_name") or g["home"]
        names[g["away"]] = g.get("away_name") or g["away"]
    return {"league": key,
            "fitted_at": datetime.now(timezone.utc).isoformat(),
            "source": f"ESPN {slug} day pulls 2026-27 (played "
                      "table + remaining fixtures); strengths "
                      "refit in-season on the played games "
                      "with the shipped shrinkage protocol "
                      "(the backtest exam's method); the "
                      "shipped v5-soccer.json fit is NOT the "
                      "input — it carries last season's teams",
            "played": len(played), "remaining": len(fixtures),
            "sims": SIMS,
            "names": names,
            "shares": {t: round(p, 4) for t, p in
                       sorted(probs.items(), key=lambda kv: -kv[1])
                       if p > 0}}, None


# ----------------------------------------------------------------
# R6: the pilot's protocol applied per league.
FD_LEAGUES = {"la-liga": "SP1", "bundesliga": "D1",
              "serie-a": "I1", "ligue-1": "F1"}
ESPN_SLUGS = {"la-liga": "esp.1", "bundesliga": "ger.1",
              "serie-a": "ita.1", "ligue-1": "fra.1"}
# R7: second tiers (same archives, same seasons, same
# ESPN live route family).
FD_LEAGUES2 = {"championship": "E1", "serie-b": "I2",
               "la-liga-2": "SP2", "bundesliga-2": "D2",
               "ligue-2": "F2"}
ESPN_SLUGS2 = {"championship": "eng.2", "serie-b": "ita.2",
               "la-liga-2": "esp.2", "bundesliga-2": "ger.2",
               "ligue-2": "fra.2"}
GUY6 = "/tmp/guy6"
REG_GAMES = 34          # MLS regular-season games per team
MLS_SEASONS = (2023, 2024, 2025)


def _mls_conferences(year):
    """{abbrev: 'east'|'west'} from the ESPN standings file
    fetched alongside the fixtures."""
    path = os.path.join(GUY6, f"mls_standings_{year}.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for child in data.get("children") or []:
        name = (child.get("name") or "").lower()
        conf = "east" if "east" in name else \
            "west" if "west" in name else None
        if conf is None:
            continue
        entries = ((child.get("standings") or {})
                   .get("entries") or [])
        for e in entries:
            ab = ((e.get("team") or {}).get("abbreviation"))
            if ab:
                out[ab] = conf
    return out


def _mls_split(games, members):
    """Final games between league members, in date order,
    split into (regular, playoffs): a game is regular iff
    neither side has already played REG_GAMES regular
    games when it is reached (playoffs begin once the
    regular count is exhausted — Decision Day precedes
    the wild-card round every season on file)."""
    gs = [g for g in games if g["final"]
          and g["home"] in members and g["away"] in members]
    gs.sort(key=lambda g: g["date"])
    counts, regular, playoffs = {}, [], []
    for g in gs:
        if counts.get(g["home"], 0) >= REG_GAMES or \
                counts.get(g["away"], 0) >= REG_GAMES:
            playoffs.append(g)
        else:
            regular.append(g)
            counts[g["home"]] = counts.get(g["home"], 0) + 1
            counts[g["away"]] = counts.get(g["away"], 0) + 1
    return regular, playoffs


def _playoff_game_probs(lh, la, maxg=14):
    """(p_home_win, p_draw, p_away_win) on the Poisson grid
    + the single-game advancement probability for the home
    side: a draw goes to a shootout, modeled as the
    regulation win shares renormalized (stated
    simplification, fixed before any MLS exam ran)."""
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
    adv = hw + (dr * hw / (hw + aw) if hw + aw > 0 else dr / 2)
    return hw, dr, aw, adv


def _mls_playoff_champion(rng, st, lg, pts, gf, ga, confs):
    """One simulated playoff bracket (2023-25 format) from
    a simulated final table. Returns the champion."""

    def lam(h, a):
        return (lg["LH"] * st[h]["att"] * st[a]["def"],
                lg["LA"] * st[a]["att"] * st[h]["def"])

    def game_winner(h, a):
        lh, la = lam(h, a)
        _hw, _dr, _aw, adv = _playoff_game_probs(lh, la)
        return h if rng.random() < adv else a

    def series_winner(high, low):
        # best-of-3, games at high, low, high (if needed)
        w = {high: 0, low: 0}
        for host, guest in ((high, low), (low, high),
                            (high, low)):
            w[game_winner(host, guest)] += 1
            if w[high] == 2 or w[low] == 2:
                break
        return high if w[high] == 2 else low

    def seeded(conf):
        teams = [t for t in pts if confs.get(t) == conf]
        return sorted(teams,
                      key=lambda t: (pts[t], gf[t] - ga[t],
                                     gf[t]),
                      reverse=True)

    champs = {}
    for conf in ("east", "west"):
        sd = seeded(conf)
        top = sd[:9]
        wc = game_winner(top[7], top[8])       # 8 v 9 wild card
        r1 = {1: series_winner(top[0], wc),
              2: series_winner(top[1], top[6]),
              3: series_winner(top[2], top[5]),
              4: series_winner(top[3], top[4])}

        def host(x, y):
            return x if sd.index(x) < sd.index(y) else y

        def single(x, y):
            h = host(x, y)
            return game_winner(h, y if h == x else x)

        sf1 = single(r1[1], r1[4])
        sf2 = single(r1[2], r1[3])
        champs[conf] = single(sf1, sf2)
    e, w = champs["east"], champs["west"]
    host = e if (pts[e], gf[e] - ga[e], gf[e]) >= \
        (pts[w], gf[w] - ga[w], gf[w]) else w
    return game_winner(host, w if host == e else e)


def _mls_simulate(st, lg, table, fixtures, confs, sims=SIMS,
                  seed=SEED):
    """Regular-season remainder on the Poisson grid, then
    the playoff bracket per sim. {team: champion share}."""
    pts0, gf0, ga0, _pl = table
    lam = {}
    for h, a in fixtures:
        lam[(h, a)] = (lg["LH"] * st[h]["att"] * st[a]["def"],
                       lg["LA"] * st[a]["att"] * st[h]["def"])
    wins = {t: 0 for t in pts0}
    rng = random.Random(seed)
    for _ in range(sims):
        pts = dict(pts0)
        gf = dict(gf0)
        ga = dict(ga0)
        for (h, a), (lh, la) in lam.items():
            gh, ga_ = pois(rng, lh), pois(rng, la)
            gf[h] += gh
            ga[h] += ga_
            gf[a] += ga_
            ga[a] += gh
            if gh > ga_:
                pts[h] += 3
            elif gh < ga_:
                pts[a] += 3
            else:
                pts[h] += 1
                pts[a] += 1
        champ = _mls_playoff_champion(rng, st, lg, pts, gf,
                                      ga, confs)
        wins[champ] += 1
    return {t: wins[t] / sims for t in wins}


def mls_backtest():
    """The pilot protocol on MLS: 3 completed seasons
    (2023-2025), snapshot when every club has >= 17
    regular games, remaining regular fixtures + the
    playoff bracket simulated 20,000x, champion = MLS
    Cup winner, naive = snapshot standings-points share.
    Same bar as the pilot."""
    rows = []
    for year in MLS_SEASONS:
        confs = _mls_conferences(year)
        members = set(confs)
        with open(os.path.join(GUY6, f"mls_{year}.json"),
                  encoding="utf-8") as f:
            games = json.load(f)
        regular, playoffs = _mls_split(games, members)
        counts, snap = {}, 0
        for i, g in enumerate(regular):
            counts[g["home"]] = counts.get(g["home"], 0) + 1
            counts[g["away"]] = counts.get(g["away"], 0) + 1
            if len(counts) >= len(members) and \
                    min(counts.values()) >= 17:
                snap = i + 1
                break
        played, remaining = regular[:snap], regular[snap:]
        st, lg = fit_strengths(played)
        table = table_after(played)
        for t in members:
            for d in table[:3]:
                d.setdefault(t, 0)
        probs = _mls_simulate(
            st, lg, table,
            [(g["home"], g["away"]) for g in remaining],
            confs)
        last = playoffs[-1]
        champ = last["home"] if last["hs"] > last["as"] \
            else last["away"]
        tot_pts = sum(table[0].values())
        naive = {t: table[0][t] / tot_pts for t in members}
        b, ll = score(probs, champ)
        bn, lln = score(naive, champ)
        rows.append({"season": str(year), "champion": champ,
                     "p_champion_model": round(probs[champ], 4),
                     "p_champion_naive": round(naive[champ], 4),
                     "brier_model": round(b, 4),
                     "brier_naive": round(bn, 4),
                     "logloss_model": round(ll, 4),
                     "logloss_naive": round(lln, 4),
                     "sim_from": f"snapshot at {snap} regular "
                                 f"games (every club >= 17 "
                                 f"played); {len(remaining)} "
                                 "regular + playoff bracket "
                                 "simulated",
                     "top3_model": sorted(
                         probs.items(),
                         key=lambda kv: -kv[1])[:3]})
        r = rows[-1]
        print(f"  MLS {year}: champ {champ} — model p "
              f"{r['p_champion_model']} (Brier {b:.4f}, LL "
              f"{ll:.4f}) vs naive p {r['p_champion_naive']} "
              f"(Brier {bn:.4f}, LL {lln:.4f})", flush=True)
    wins = sum(1 for r in rows
               if r["brier_model"] < r["brier_naive"]
               and r["logloss_model"] < r["logloss_naive"])
    mean_b = statistics_mean([r["brier_model"] for r in rows])
    mean_bn = statistics_mean([r["brier_naive"] for r in rows])
    mean_l = statistics_mean([r["logloss_model"] for r in rows])
    mean_ln = statistics_mean([r["logloss_naive"]
                               for r in rows])
    passed = wins >= 2 and mean_b < mean_bn and mean_l < mean_ln
    return {"seasons": rows, "seasons_won": wins,
            "mean_brier_model": round(mean_b, 4),
            "mean_brier_naive": round(mean_bn, 4),
            "mean_logloss_model": round(mean_l, 4),
            "mean_logloss_naive": round(mean_ln, 4),
            "verdict": "PASS" if passed else "FAILED-EXAM",
            "bar": "model beats naive on Brier AND log-loss "
                   "in >= 2 of 3 seasons and on both 3-season "
                   "means",
            "sims_per_season": SIMS,
            "protocol_note": "MLS champion is the MLS Cup "
                             "winner: the simulation adds "
                             "the 2023-25 playoff bracket "
                             "(wild card, best-of-3 first "
                             "round, single-game semis/finals, "
                             "shootouts on drawn playoff "
                             "games) to the pilot's "
                             "regular-season simulation"}


def mls_live_artifact():
    """Current MLS season (2026): played table from the
    ESPN day pulls, remaining regular fixtures + playoff
    bracket simulated 20,000x, strengths refit in-season
    (the exam's method)."""
    year = 2026
    confs = _mls_conferences(year)
    members = set(confs)
    with open(os.path.join(GUY6, f"mls_{year}.json"),
              encoding="utf-8") as f:
        games = json.load(f)
    regular, _po = _mls_split(games, members)
    # remaining REGULAR fixtures: scheduled (non-final)
    # member games that arrive before the regular count
    # would be exhausted, in date order interleaved with
    # the played ones — recovered by replaying the season
    # in date order over both final and scheduled games.
    allg = [g for g in games if g["home"] in members
            and g["away"] in members]
    allg.sort(key=lambda g: g["date"])
    counts, remaining = {}, []
    played = []
    for g in allg:
        if counts.get(g["home"], 0) >= REG_GAMES or \
                counts.get(g["away"], 0) >= REG_GAMES:
            continue            # playoff portion — simulated
        counts[g["home"]] = counts.get(g["home"], 0) + 1
        counts[g["away"]] = counts.get(g["away"], 0) + 1
        if g["final"]:
            played.append(g)
        else:
            remaining.append((g["home"], g["away"]))
    st, lg = fit_strengths(played)
    if set(st) != members:
        return None, ("strength refit does not cover the "
                      f"league: {sorted(members - set(st))}")
    table = table_after(played)
    for t in members:
        for d in table[:3]:
            d.setdefault(t, 0)
    probs = _mls_simulate(st, lg, table, remaining, confs)
    names = {}
    for g in allg:
        names[g["home"]] = g.get("home_name") or g["home"]
        names[g["away"]] = g.get("away_name") or g["away"]
    return {"league": "mls",
            "fitted_at": datetime.now(timezone.utc).isoformat(),
            "source": "ESPN usa.1 day pulls 2026 (played "
                      "table + remaining regular fixtures, "
                      "playoff bracket simulated); strengths "
                      "refit in-season on the played games "
                      "with the shipped shrinkage protocol "
                      "(the backtest exam's method)",
            "played": len(played), "remaining": len(remaining),
            "sims": SIMS, "names": names,
            "shares": {t: round(p, 4) for t, p in
                       sorted(probs.items(), key=lambda kv: -kv[1])
                       if p > 0}}, None


def main():
    global PRIOR_LH, PRIOR_LA
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".."))
    import betmodel5 as b5
    PRIOR_LH, PRIOR_LA = b5.SOC_PRIOR_LH, b5.SOC_PRIOR_LA
    out_path = None
    no_live = "--no-live" in sys.argv
    tiers2 = "--tiers2" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        out_path = args[0]
    else:
        out_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..",
            "data", "v5-outrights.json")
    if tiers2:
        # R7: second tiers only, merged into the shipped
        # artifact — the R5/R6 exams are not re-run.
        doc = {}
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as f:
                doc = json.load(f)
        doc.setdefault("pilot", "soccer title outrights "
                                "(Monte Carlo season simulation "
                                "from fitted league strengths)")
        doc.setdefault("leagues", {})
        bt = None
    else:
        print("futures pilot backtest (EPL x3, mid-season sim):")
        bt = backtest()
        print(f"  VERDICT: {bt['verdict']} (seasons won "
              f"{bt['seasons_won']}/3; mean Brier "
              f"{bt['mean_brier_model']} vs "
              f"{bt['mean_brier_naive']}; mean LL "
              f"{bt['mean_logloss_model']} vs "
              f"{bt['mean_logloss_naive']})")
        doc = {"pilot": "soccer title outrights (Monte Carlo "
                        "season simulation from fitted league "
                        "strengths)",
               "backtest": bt,
               "leagues": {}}

    def add_league(key, exam, live_fn):
        entry = {"league": key, "exam": exam}
        print(f"  {key}: exam {exam['verdict']} (seasons won "
              f"{exam['seasons_won']}/3; mean Brier "
              f"{exam['mean_brier_model']} vs "
              f"{exam['mean_brier_naive']}; mean LL "
              f"{exam['mean_logloss_model']} vs "
              f"{exam['mean_logloss_naive']})", flush=True)
        if exam["verdict"] == "PASS" and not no_live:
            live, err = live_fn()
            if live is None:
                print(f"  live {key} NOT built: {err}")
                entry["live_error"] = err
            else:
                entry.update(live)
                print(f"  live {key}: played {live['played']}, "
                      f"remaining {live['remaining']}, top: "
                      f"{list(live['shares'].items())[:3]}",
                      flush=True)
        elif exam["verdict"] == "PASS":
            # keep a previous live block when re-running exams
            prev = {}
            if os.path.exists(out_path):
                with open(out_path, encoding="utf-8") as f:
                    prev = (json.load(f).get("leagues") or {}) \
                        .get(key) or {}
            for k in ("fitted_at", "source", "played",
                      "remaining", "sims", "names", "shares"):
                if k in prev:
                    entry[k] = prev[k]
        doc["leagues"][key] = entry
        # checkpoint after every league: the full run is
        # long (15 season sims + 5 live builds) and a lost
        # process must not lose finished leagues.
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1)
        print(f"  checkpoint: {key} written", flush=True)

    if tiers2:
        for key, code in FD_LEAGUES2.items():
            print(f"backtest {key} ({code} x3, R7 second "
                  f"tier):", flush=True)
            add_league(key, backtest(code),
                       lambda k=key: live_artifact(
                           ESPN_SLUGS2[k], k))
    else:
        add_league("epl", bt,
                   lambda: live_artifact("eng.1", "epl"))
        # R6: same protocol, same bar, per league.
        for key, code in FD_LEAGUES.items():
            print(f"backtest {key} ({code} x3):", flush=True)
            add_league(key, backtest(code),
                       lambda k=key: live_artifact(ESPN_SLUGS[k],
                                                   k))
        print("backtest mls (ESPN usa.1 x3, playoff bracket):",
              flush=True)
        add_league("mls", mls_backtest(), mls_live_artifact)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
