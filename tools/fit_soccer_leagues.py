#!/usr/bin/env python3
"""
fit_soccer_leagues.py — BetFi Xii (v12) multi-league soccer fits.

Pulls REAL completed-season results CSVs from football-data.co.uk
and fits each league with the SAME protocol the engine's own
fit_soccer() used for the EPL fit in data/v5-soccer.json:

  * league home/away scoring rates with the engine's priors
    (LH 1.40 / LA 1.15, 10-game prior weight),
  * attack/defence strengths per team (prior shrinkage of
    SOC_PRIOR_GAMES = 8 games at the league scoring rate),
  * sequential Elo (K = 20, HFA = 65 Elo points, score 1 / 0.5 / 0),
  * a WALK-FORWARD backtest: every game is predicted from the
    strengths/Elo accumulated from PRIOR games only, then graded
    (3-way Brier, argmax accuracy, n) — updates land AFTER the
    prediction, exactly as in fit_soccer.

The Poisson grid and lambda construction are the engine's own
(betmodel5.soccer_grid / betmodel5.soccer_lambdas, imported —
never re-implemented), so a league fit here prices identically to
how the engine prices the EPL fit.

Leagues (football-data.co.uk mmz4281, season 2425 = 2024-25):
  I1  Serie A        SP1 La Liga       D1  Bundesliga
  F1  Ligue 1        E0  Premier League — the CONTROL: fitted by
      the same code and stored under "control", NOT under
      "leagues", so it can be compared against the shipped
      v5-soccer.json without ever shadowing it in the checker
      (EPL grading stays byte-for-byte the shipped fit's).

  "Fix the laziness" extension (CODER X): every other league
  that actually shows up on FanDuel pulls got the same fit —
    E1 Championship      I2 Serie B        SP2 La Liga 2
    F2 Ligue 2           D2 Bundesliga 2   N1 Eredivisie
    P1 Primeira Liga     T1 Super Lig      G1 Super League (GR)
    B1 Jupiler Pro       SC0 Scottish Premiership
  plus MLS (usa.1) from ESPN scoreboard DAY PULLS — the same
  source family the original EPL fit used — over the full 2025
  regular season (2025-02-22 .. 2025-10-18, Decision Day;
  playoffs excluded: knockout games are not league fixtures).
  A league whose source fails is OMITTED and printed, never
  fabricated (the law above is unchanged).

Output: data/v5-soccer-leagues.json, same schema family as
v5-soccer.json per league (league rates / elo / strengths /
backtest / params / source / fitted_at).

Honesty law: a league whose download or parse fails is OMITTED
and its failure printed — a league is never fabricated, padded,
or borrowed from another league's numbers.

Run:  python3 tools/fit_soccer_leagues.py [--out PATH]
"""
import csv
import io
import json
import os
import statistics
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CLONE = os.path.dirname(HERE)
sys.path.insert(0, CLONE)

import betmodel5 as b5  # the engine — grid/lambda math imported

BASE = "https://www.football-data.co.uk/mmz4281/2425"
LEAGUES = {
    "serie-a":    ("I1", "Serie A (Italy)"),
    "la-liga":    ("SP1", "La Liga (Spain)"),
    "bundesliga": ("D1", "Bundesliga (Germany)"),
    "ligue-1":    ("F1", "Ligue 1 (France)"),
    # --- "fix the laziness" extension: the other leagues that
    # appear on FanDuel pulls, same source, same protocol ---
    "championship":         ("E1", "Championship (England)"),
    "serie-b":              ("I2", "Serie B (Italy)"),
    "la-liga-2":            ("SP2", "La Liga 2 (Spain)"),
    "ligue-2":              ("F2", "Ligue 2 (France)"),
    "bundesliga-2":         ("D2", "Bundesliga 2 (Germany)"),
    "eredivisie":           ("N1", "Eredivisie (Netherlands)"),
    "primeira-liga":        ("P1", "Primeira Liga (Portugal)"),
    "super-lig":            ("T1", "Super Lig (Turkey)"),
    "super-league-greece":  ("G1", "Super League (Greece)"),
    "jupiler-pro":          ("B1", "Jupiler Pro League (Belgium)"),
    "scottish-premiership": ("SC0", "Scottish Premiership"),
}

# The non-football-data leagues come from ESPN scoreboard day
# pulls (the source family the original EPL fit used): one
# scoreboard call per day over each regular-season window,
# completed events only, deduped by ESPN event id, fitted with
# the identical walk-forward code. Windows cover the last
# completed seasons; playoff / liguilla phases are excluded
# (knockout games are not league fixtures).
ESPN_SOCCER = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_LEAGUES = [
    {"key": "mls", "slug": "usa.1", "name": "MLS (USA)",
     "season": "2025", "label": "2025 MLS regular season",
     "windows": [(date(2025, 2, 22), date(2025, 10, 18))]},
    {"key": "brasileirao", "slug": "bra.1",
     "name": "Serie A (Brazil)", "season": "2025",
     "label": "2025 Brazilian Serie A",
     "windows": [(date(2025, 3, 29), date(2025, 12, 7))]},
    {"key": "liga-mx", "slug": "mex.1", "name": "Liga MX (Mexico)",
     "season": "2025",
     "label": "2025 Liga MX regular seasons (Clausura + "
              "Apertura; liguilla excluded)",
     "windows": [(date(2025, 1, 10), date(2025, 4, 21)),
                 (date(2025, 7, 11), date(2025, 11, 10))]},
    {"key": "liga-profesional", "slug": "arg.1",
     "name": "Liga Profesional (Argentina)", "season": "2025",
     "label": "2025 Liga Profesional regular phases (Apertura "
              "+ Clausura; playoffs excluded)",
     "windows": [(date(2025, 1, 23), date(2025, 5, 5)),
                 (date(2025, 7, 11), date(2025, 11, 17))]},
    {"key": "brasileirao-b", "slug": "bra.2",
     "name": "Serie B (Brazil)", "season": "2025",
     "label": "2025 Brazilian Serie B",
     "windows": [(date(2025, 4, 5), date(2025, 11, 23))]},
    {"key": "nacional-b", "slug": "arg.2",
     "name": "Primera Nacional (Argentina)", "season": "2025",
     "label": "2025 Primera Nacional regular phase (reducido "
              "playoffs excluded)",
     "windows": [(date(2025, 2, 7), date(2025, 10, 5))]},
]
CONTROL = ("epl", "E0", "Premier League (England) — control")

# the engine's fit_soccer protocol constants, named once here
SOC_K, SOC_HFA = b5.SOC_K, b5.SOC_HFA
SOC_PRIOR_GAMES = b5.SOC_PRIOR_GAMES
SOC_PRIOR_LH, SOC_PRIOR_LA = b5.SOC_PRIOR_LH, b5.SOC_PRIOR_LA


def fetch_csv(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "BetFi-Xii fit builder "
                                   "(stdlib urllib)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def parse_games(text):
    """football-data rows -> [{home, away, hs, as}] in date order.
    Rows without a full-time score are skipped (postponed /
    unplayed fixtures carry no result to fit on)."""
    games = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            hs = int(float(row["FTHG"]))
            hs_as = int(float(row["FTAG"]))
        except (KeyError, TypeError, ValueError):
            continue
        home = (row.get("HomeTeam") or "").strip()
        away = (row.get("AwayTeam") or "").strip()
        if not home or not away:
            continue
        games.append({"date": row.get("Date") or "",
                      "home": home, "away": away,
                      "hs": hs, "as": hs_as})
    return games


def fit_league(games, source):
    """fit_soccer's walk-forward construction, verbatim in
    structure: strengths() snapshot -> grid prediction -> grade
    the record -> THEN update gp/gf/ga, league totals and Elo."""
    elo, gp, gf, ga = {}, {}, {}, {}
    hg = ag = hgames = 0
    recs = []

    def strengths():
        total_gp = sum(gp.values())
        L = ((sum(gf.values()) / total_gp) if total_gp else 1.35)
        if L <= 0:
            # A season whose opening games are all goalless (the
            # Scottish Premiership 2024-25 file opens 0-0, 0-0)
            # makes the raw rate 0 and the att/def map divide by
            # it. Fall back to the prior scoring rate until the
            # season has a goal — the prior is what a zero-game
            # snapshot already uses, so no fitted league whose
            # early games had goals changes at all.
            L = (SOC_PRIOR_LH + SOC_PRIOR_LA) / 2
        LH = (hg + 10 * SOC_PRIOR_LH) / (hgames + 10) if hgames \
            else SOC_PRIOR_LH
        LA = (ag + 10 * SOC_PRIOR_LA) / (hgames + 10) if hgames \
            else SOC_PRIOR_LA
        st = {}
        for t in gp:
            st[t] = {
                "att": ((gf[t] + SOC_PRIOR_GAMES * L)
                        / (gp[t] + SOC_PRIOR_GAMES)) / L,
                "def": ((ga[t] + SOC_PRIOR_GAMES * L)
                        / (gp[t] + SOC_PRIOR_GAMES)) / L,
                "gp": gp[t]}
        return st, {"LH": LH, "LA": LA, "L": L}

    for g in games:
        for t in (g["home"], g["away"]):
            gp.setdefault(t, 0)
            gf.setdefault(t, 0)
            ga.setdefault(t, 0)
            elo.setdefault(t, 1500.0)
        st, lg = strengths()
        lh, la = b5.soccer_lambdas(st, lg, g["home"], g["away"])
        grid = b5.soccer_grid(lh, la)
        y = (1 if g["hs"] > g["as"] else 0 if g["hs"] == g["as"]
             else -1)
        recs.append({"p_home": grid["p_home"],
                     "p_draw": grid["p_draw"],
                     "p_away": grid["p_away"], "y": y,
                     "pick": max((("home", grid["p_home"]),
                                  ("draw", grid["p_draw"]),
                                  ("away", grid["p_away"])),
                                 key=lambda kv: kv[1])[0]})
        gp[g["home"]] += 1
        gp[g["away"]] += 1
        gf[g["home"]] += g["hs"]
        ga[g["home"]] += g["as"]
        gf[g["away"]] += g["as"]
        ga[g["away"]] += g["hs"]
        hg += g["hs"]
        ag += g["as"]
        hgames += 1
        d = elo[g["home"]] + SOC_HFA - elo[g["away"]]
        exp_h = 1 / (1 + 10 ** (-d / 400))
        score_h = 1.0 if y == 1 else 0.5 if y == 0 else 0.0
        elo[g["home"]] += SOC_K * (score_h - exp_h)
        elo[g["away"]] -= SOC_K * (score_h - exp_h)
    brier3 = statistics.mean([
        (x["p_home"] - (1 if x["y"] == 1 else 0)) ** 2
        + (x["p_draw"] - (1 if x["y"] == 0 else 0)) ** 2
        + (x["p_away"] - (1 if x["y"] == -1 else 0)) ** 2
        for x in recs])
    acc = statistics.mean([
        1.0 if (x["pick"] == "home" and x["y"] == 1)
        or (x["pick"] == "draw" and x["y"] == 0)
        or (x["pick"] == "away" and x["y"] == -1) else 0.0
        for x in recs])
    st, lg = strengths()
    return {
        "params": {"K": SOC_K, "hfa_elo": SOC_HFA,
                   "prior_games": SOC_PRIOR_GAMES},
        "source": source,
        "elo": {k: round(v, 1) for k, v in elo.items()},
        "strengths": {k: {"att": round(v["att"], 3),
                          "def": round(v["def"], 3),
                          "gp": v["gp"]}
                      for k, v in st.items()},
        "league": {"LH": round(lg["LH"], 3),
                   "LA": round(lg["LA"], 3),
                   "L": round(lg["L"], 3)},
        "backtest": {"brier3": round(brier3, 4),
                     "accuracy": round(acc, 4),
                     "n": len(recs),
                     "protocol": "walk-forward (strengths/Elo "
                                 "from prior games only)"}}


def fetch_espn_day(slug, day):
    """One ESPN scoreboard day pull -> completed games only, as
    [{date, id, home, away, hs, as}]. Raises on HTTP/parse
    failure so the caller can omit the league honestly."""
    url = (f"{ESPN_SOCCER}/{slug}/scoreboard"
           f"?dates={day.strftime('%Y%m%d')}")
    req = urllib.request.Request(
        url, headers={"User-Agent": "BetFi-Xii fit builder "
                                   "(stdlib urllib)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        blob = json.loads(r.read().decode("utf-8", "replace"))
    games = []
    for ev in blob.get("events") or []:
        try:
            if not (ev.get("status", {}).get("type", {})
                    .get("completed")):
                continue
            comp = (ev.get("competitions") or [{}])[0]
            cs = {c["homeAway"]: c
                  for c in comp.get("competitors") or []}
            home, away = cs["home"], cs["away"]
            games.append({
                "date": day.isoformat(), "id": str(ev.get("id")),
                "home": home["team"]["displayName"],
                "away": away["team"]["displayName"],
                "hs": int(float(home["score"])),
                "as": int(float(away["score"]))})
        except (KeyError, TypeError, ValueError):
            continue
    return games


def fetch_espn_season(slug, windows):
    """Day pulls across every (start, end) window, deduped by
    event id and ordered by (date, id) so the walk-forward is
    deterministic regardless of fetch order."""
    days = []
    for start, end in windows:
        d = start
        while d <= end:
            days.append(d)
            d += timedelta(days=1)
    by_id = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for games in pool.map(
                lambda day: fetch_espn_day(slug, day), days):
            for g in games:
                by_id[g["id"]] = g
    return sorted(by_id.values(),
                  key=lambda g: (g["date"], g["id"]))


def main(argv):
    out_path = os.path.join(CLONE, "data", "v5-soccer-leagues.json")
    if "--out" in argv:
        out_path = argv[argv.index("--out") + 1]
    fitted_at = datetime.now().astimezone().isoformat(
        timespec="seconds")
    blob = {"sport": "soccer", "fitted_at": fitted_at,
            "leagues": {}, "control": {},
            "note": "Per-league fits (football-data.co.uk, season "
                    "2024-25; MLS from ESPN usa.1 day pulls, 2025 "
                    "regular season). 'control' is the EPL fitted "
                    "by this "
                    "same code for comparison against the shipped "
                    "v5-soccer.json; the checker never prices "
                    "from control — EPL prices from v5-soccer.json "
                    "exactly as before."}
    jobs = [(key, code, name, False)
            for key, (code, name) in LEAGUES.items()]
    jobs.append((CONTROL[0], CONTROL[1], CONTROL[2], True))
    for key, code, name, is_control in jobs:
        url = f"{BASE}/{code}.csv"
        try:
            games = parse_games(fetch_csv(url))
            if len(games) < 50:
                raise ValueError(
                    f"only {len(games)} scored games parsed — "
                    f"too few to fit honestly")
            fit = fit_league(
                games, f"football-data.co.uk results CSV {url}")
            fit["league_name"] = name
            fit["fitted_at"] = fitted_at
            fit["season"] = "2024-25"
        except Exception as e:
            print(f"[FAIL] {name} ({code}): "
                  f"{type(e).__name__}: {e} — league OMITTED, "
                  f"never fabricated")
            continue
        (blob["control"] if is_control else blob["leagues"])[key] \
            = fit
        bt = fit["backtest"]
        print(f"[OK] {name} ({code}): n={bt['n']} games · "
              f"brier3={bt['brier3']} · accuracy={bt['accuracy']} "
              f"· LH={fit['league']['LH']} LA={fit['league']['LA']} "
              f"· teams={len(fit['strengths'])}")
    # ESPN day-pull leagues — MLS was the biggest named bucket
    # on the live coverage queue; Brazil / Liga MX / Argentina
    # are the next ones. All fitted by the identical code.
    for job in ESPN_LEAGUES:
        source = (f"ESPN scoreboard day pulls ({job['slug']}, "
                  f"{job['label']})")
        try:
            games = fetch_espn_season(job["slug"], job["windows"])
            # Exhibition all-star events sit inside season
            # windows as league-slug events (MLS All-Stars vs
            # Liga MX All-Stars, 2025-07-23). They are not
            # league fixtures — excluding them leaves exactly
            # the regular-season games of the member clubs.
            games = [g for g in games
                     if "All-Stars" not in g["home"]
                     and "All-Stars" not in g["away"]]
            if len(games) < 50:
                raise ValueError(
                    f"only {len(games)} completed games pulled "
                    f"— too few to fit honestly")
            fit = fit_league(games, source)
            fit["league_name"] = job["name"]
            fit["fitted_at"] = fitted_at
            fit["season"] = job["season"]
            blob["leagues"][job["key"]] = fit
            bt = fit["backtest"]
            print(f"[OK] {job['name']} (ESPN {job['slug']}): "
                  f"n={bt['n']} games · brier3={bt['brier3']} · "
                  f"accuracy={bt['accuracy']} "
                  f"· LH={fit['league']['LH']} "
                  f"LA={fit['league']['LA']} "
                  f"· teams={len(fit['strengths'])}")
        except Exception as e:
            print(f"[FAIL] {job['name']} (ESPN {job['slug']}): "
                  f"{type(e).__name__}: {e} — league OMITTED, "
                  f"never fabricated")
    if not blob["leagues"]:
        print("No league fitted — file NOT written.")
        return 1
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=1)
    print(f"Wrote {out_path}: leagues="
          f"{sorted(blob['leagues'])} control="
          f"{sorted(blob['control'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
