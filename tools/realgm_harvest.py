#!/usr/bin/env python3
"""realgm_harvest.py — shared harvest + fit machinery for the
BetFi Xii RealGM lanes (Build L: Spanish ACB, Italian Lega
Basket Serie A, Turkish BSL, German BBL — the small foreign
leagues FanDuel files under the "nba" page).

Each lane's builder (tools/fit_<league>.py) declares its
league config and calls main() here; the math body is
fit_eurocup.fit_nba's, verbatim:

  * sequential Elo, K=20, HFA=100 Elo points (the NBA lane's
    ENGINE PARAMS, carried over un-tuned — no parameter was
    searched for these lanes), the NBA lane's margin-of-
    victory multiplier, ratings carried across seasons in
    date order (no per-season reset).
  * walk-forward exam, scored BEFORE any engine wiring:
    every game's prediction is made from ratings built ONLY
    on prior games; backtest = Brier of those walk-forward
    probabilities vs the naive baseline that predicts the
    overall home-win rate for every game (fit_nba's exact
    baseline). The lane prices only if Brier < naive.
  * margin map: OLS with intercept of margin on the
    walk-forward Elo diff, residual SD — fit_nba's map,
    verbatim (cover prices inherit its in-sample caveat and
    ride FRAGILE, exactly like the NBA lane's spreads).

SOURCE (verified by fetch 2026-10-27 for all four leagues):
basketball.realgm.com team schedule pages,
  /international/league/{id}/{slug}/team/{tid}/{tslug}/
  schedule/{season_end_year}
ESPN's basketball league stubs for these competitions are
empty shells (the acb / lba slugs resolve to league names
with empty calendars and zero events on every date probed,
the EuroLeague pattern; ger/tur slug guesses 400), the
leagues' own sites expose no reachable results API from
this machine (legabasket.it embeds championship metadata
but its /api/v1 origin is not public; acb.com is a JS shell;
tbf.org.tr does not answer), Sofascore/TheSportsDB 403 —
RealGM is the maintained public mirror that serves real
game-level results for all four, quoted in each builder's
report. Each schedule row carries the date, the opponent
(with its RealGM team id), the result from the page team's
perspective ("W, 85 - 78", scores always home-away), the
venue, and the competition label in the venue cell.

REGULAR SEASON ONLY, declared rule: keep rows whose
competition label is the league's own, then per season keep
the FIRST TWO games of each unordered pair. These leagues
play a double round-robin regular season — each pair meets
exactly twice — so playoff meetings (a pair's 3rd+) are
excluded mechanically, and mid-season cups carry their own
labels (Spanish Cup, German Cup, ...) and never reach the
filter. The two-meeting form (rather than one per ordered
pair) is deliberate: a return fixture occasionally flips
its home designation when an arena is unavailable —
Bahcesehir–Buyukcekmece in the 2024-25 TBSL was played
twice at Buyukcekmece's Gazanfer Bilge — and the ordered-
pair form would silently drop that genuine RS game.

Discovery: seed clubs from the league home page, then BFS —
every league-labelled row names its opponent's team id, and
in a round-robin every club plays every club, so the closure
covers every club that played in a pulled season. Games are
keyed by RealGM box-score id; the two mirrored rows (one per
club's page) must agree exactly or the game is dropped and
counted. Ratings key on the RealGM team id (the Greece A1
ESAKE-id pattern), glossed by the fit file's "teams" map.

Cache: data/cache/<slug>_games_2023-27.json stores every
league-labelled game (pre-RS-filter, so the RS rule can be
re-decided without re-pulling) — a re-run with the cache
present refits without re-fetching.
"""
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

BASE = "https://basketball.realgm.com"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36"}
K = 20                  # the NBA lane's ENGINE PARAMS, un-tuned
HFA_ELO = 100
SEASON_ENDS = (2024, 2025, 2026, 2027)   # 2023-24 .. 2026-27

ROW_RE = re.compile(r"<tr[^>]*>(?:(?!</tr>).)*?/international/"
                    r"boxscore/(?:(?!</tr>).)*?</tr>", re.S)
BOX_RE = re.compile(r"/international/boxscore/(\d{4}-\d{2}-\d{2})/"
                    r"[^\"/]+/(\d+)")
OPP_RE = re.compile(r"data-th=\"Opponent\">\s*(v\.|@)\s*"
                    r"<a href=\"/international/league/\d+/[^/]+/"
                    r"team/(\d+)/([^\"/]+)/rosters\">([^<]+)</a>")
RES_RE = re.compile(r"data-th=\"Result\"[^>]*>.*?([WL]), "
                    r"(\d+) - (\d+)", re.S)
VENUE_RE = re.compile(r"data-th=\"Venue\">(.*?)</td>", re.S)
TITLE_RE = re.compile(r"<title>([^<]+?) Schedule - RealGM</title>")
TEAM_LINK_RE = None     # built per league in harvest()


def fetch(url, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.5)


def parse_schedule(html, league_label):
    """One team schedule page -> (page_team_name, rows).
    Each row: boxscore id, iso date, marker (v./@), opponent
    id + name, home/away scores, competition label. Only
    played games (a W/L result) parse at all."""
    tm = TITLE_RE.search(html)
    page_name = tm.group(1) if tm else None
    rows = []
    for m in ROW_RE.finditer(html):
        tr = m.group(0)
        box = BOX_RE.search(tr)
        opp = OPP_RE.search(tr)
        res = RES_RE.search(tr)
        ven = VENUE_RE.search(tr)
        if not (box and opp and res and ven):
            continue
        vtxt = re.sub(r"<[^>]+>", " ", ven.group(1))
        vtxt = " ".join(vtxt.split())
        # the competition label is the venue cell's trailing
        # text after the venue anchor (or the whole cell when
        # no venue is linked): recover it as the known-label
        # suffix, else keep the raw tail for diagnostics
        label = None
        for cand in KNOWN_LABELS:
            if vtxt.endswith(cand):
                label = cand
                break
        if label is None:
            label = vtxt[-32:]
        rows.append({
            "box": int(box.group(2)), "date": box.group(1),
            "marker": opp.group(1), "opp_id": int(opp.group(2)),
            "opp_slug": opp.group(3),
            "opp_name": opp.group(4).strip(),
            "hs": int(res.group(2)), "as": int(res.group(3)),
            "label": label})
    return page_name, rows


KNOWN_LABELS = ("Spanish ACB", "Italian Lega Basket Serie A",
                "Turkish BSL", "German BBL", "Spanish Cup",
                "Spanish ACB SuperCup", "German Cup",
                "Italian Cup", "Turkish Cup", "Euroleague",
                "Eurocup", "Basketball Champions League Europe",
                "Basketball Champions League",
                "FIBA Europe Cup", "EuroCup",
                # Build O additions (labels verified by fetch
                # on each league's schedule pages 2026-10-27)
                "Chinese CBA", "Israeli BSL", "Brazilian NBB",
                "Argentinian Liga A", "Polish OBL",
                "Super League Basketball")


def harvest(cfg):
    """cfg: league_id, league_slug, label, cache name.
    Returns (games, fetched_at, stats) — games reconstructed
    once per box-score id, RS-filtered, date-sorted, with
    home/away as RealGM team ids (strings) + name glosses."""
    lid, lslug, label = cfg["league_id"], cfg["league_slug"], \
        cfg["label"]
    team_link_re = re.compile(
        rf"/international/league/{lid}/{re.escape(lslug)}/"
        rf"team/(\d+)/([^/\"']+)")
    home_html = fetch(f"{BASE}/international/league/{lid}/"
                      f"{lslug}")
    seeds, names = {}, {}
    for tid, tslug in team_link_re.findall(home_html):
        seeds[int(tid)] = tslug
    slugs = dict(seeds)         # team id -> URL slug, learned
    # from the home page and from opponent anchors on every
    # page pulled (an empty slug is a RealGM soft-404 — the
    # "Page Not Found" shell parses to zero rows, so a page
    # whose title does not resolve is an ERROR, never a
    # silent empty schedule)
    print(f"seeds: {len(seeds)} clubs from the league home "
          f"page", file=sys.stderr)
    seen_pages = set()          # (team_id, season_end)
    queue = [(t, s) for t in seeds for s in SEASON_ENDS]
    raw_rows = []               # (page_team_id, season_end, row)
    errors = 0
    failed = []

    def pull(tid, send):
        url = (f"{BASE}/international/league/{lid}/{lslug}/"
               f"team/{tid}/{slugs.get(tid, '')}/"
               f"schedule/{send}")
        html = fetch(url)
        pname, rows = parse_schedule(html, label)
        if pname is None:
            return None
        return pname, rows

    while queue:
        batch, queue = queue, []
        todo = []
        for tid, send in batch:
            if (tid, send) in seen_pages:
                continue
            seen_pages.add((tid, send))
            todo.append((tid, send))
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(pull, tid, send): (tid, send)
                    for tid, send in todo}
            for fut, (tid, send) in futs.items():
                try:
                    got = fut.result()
                except Exception:
                    got = None
                if got is None:
                    errors += 1
                    failed.append((tid, send))
                    continue
                pname, rows = got
                names.setdefault(tid, pname)
                for row in rows:
                    raw_rows.append((tid, send, row))
                    oid = row["opp_id"]
                    slugs.setdefault(oid, row["opp_slug"])
                    if row["label"] == label:
                        names.setdefault(oid, row["opp_name"])
                        if oid not in seeds:
                            seeds[oid] = row["opp_slug"]
                            for s2 in SEASON_ENDS:
                                if (oid, s2) not in seen_pages:
                                    queue.append((oid, s2))
    # one serial retry for failed pages, now that opponent
    # anchors have taught us every club's real slug
    still_failed = []
    for tid, send in failed:
        try:
            got = pull(tid, send)
        except Exception:
            got = None
        if got is None:
            still_failed.append((tid, send))
            continue
        pname, rows = got
        names.setdefault(tid, pname)
        for row in rows:
            raw_rows.append((tid, send, row))
            slugs.setdefault(row["opp_id"], row["opp_slug"])
            if row["label"] == label:
                names.setdefault(row["opp_id"], row["opp_name"])
    if still_failed:
        print(f"WARNING: {len(still_failed)} schedule pages "
              f"unreachable after retry: {still_failed}",
              file=sys.stderr)
    print(f"pages: {len(seen_pages)} pulled, {errors} errors; "
          f"clubs discovered: {len(seeds)}", file=sys.stderr)
    # reconstruct games by box-score id; mirrored rows must
    # agree exactly
    games_by_box, conflicts = {}, 0
    for tid, send, row in raw_rows:
        if row["label"] != label:
            continue
        if row["marker"] == "v.":
            home, away = tid, row["opp_id"]
        else:
            home, away = row["opp_id"], tid
        g = {"box": row["box"], "season_end": send,
             "date": row["date"], "home": str(home),
             "away": str(away), "home_name": names.get(home, ""),
             "away_name": names.get(away, ""),
             "hs": row["hs"], "as": row["as"], "final": True}
        prev = games_by_box.get(row["box"])
        if prev is not None:
            same = all(prev[k] == g[k] for k in
                       ("date", "home", "away", "hs", "as"))
            if not same:
                conflicts += 1
                games_by_box[row["box"]] = None
            continue
        games_by_box[row["box"]] = g
    games = [g for g in games_by_box.values() if g]
    print(f"league games reconstructed: {len(games)} "
          f"({conflicts} mirror conflicts dropped)",
          file=sys.stderr)
    fetched_at = datetime.now().astimezone().isoformat(
        timespec="seconds")
    stats = {"pages": len(seen_pages), "errors": errors,
             "failed_pages": [list(f) for f in still_failed],
             "conflicts": conflicts, "clubs": len(seeds),
             "all_games": len(games)}
    return games, names, fetched_at, stats


def rs_filter(games, names):
    """Regular season only, per the declared rule in the
    module docstring: per season, the first two meetings of
    each unordered pair. Applied AFTER the cache load as
    well as on a fresh harvest — the cache stores every
    league-labelled game, so the rule can be re-decided
    without re-pulling. Runs the completeness audit."""
    games = sorted(games, key=lambda g: (g["date"], g["box"]))
    pair_count, rs = {}, []
    for g in games:
        key = (g["season_end"],
               frozenset((g["home"], g["away"])))
        if pair_count.get(key, 0) >= 2:
            continue
        pair_count[key] = pair_count.get(key, 0) + 1
        rs.append(g)
    print(f"regular-season games: {len(rs)}", file=sys.stderr)
    # completeness audit: in a FULL season of a double
    # round-robin, every club plays 2*(clubs-1) RS games —
    # any shortfall is printed, never silently absorbed (a
    # soft-404'd schedule page once cost exactly the
    # fixtures among the affected clubs; the audit is the
    # tripwire). Home/away splits are NOT asserted: venue
    # flips make them non-structural (module docstring).
    for send in sorted({g["season_end"] for g in rs}):
        if send == max(SEASON_ENDS):
            continue                    # current, partial
        gs = [g for g in rs if g["season_end"] == send]
        clubs = {g["home"] for g in gs} | {g["away"] for g in gs}
        exp = 2 * (len(clubs) - 1)
        short = []
        for c in sorted(clubs, key=int):
            n = sum(1 for g in gs
                    if g["home"] == c or g["away"] == c)
            if n != exp:
                short.append(f"{names.get(int(c), c)}: "
                             f"{n} games (exp {exp})")
        print(f"audit season_end {send}: {len(gs)} games, "
              f"{len(clubs)} clubs, shortfalls: "
              f"{short or 'none'}", file=sys.stderr)
    return rs


def fit(games, cfg, fetched_at):
    """fit_eurocup's body, verbatim math, on id-keyed teams."""
    R, recs = {}, []

    def r(t):
        return R.get(t, 1500.0)

    for g in games:
        d = r(g["home"]) + HFA_ELO - r(g["away"])
        p = 1 / (1 + 10 ** (-d / 400))
        mov = g["hs"] - g["as"]
        y = 1.0 if mov > 0 else 0.0
        recs.append({"diff": d, "p": p, "margin": mov, "y": y})
        mult = (math.log(abs(mov) + 1)
                * (2.2 / ((r(g["home"]) - r(g["away"]))
                          * 0.001 + 2.2))
                if mov != 0 else 1.0)
        delta = K * mult * (y - p)
        R[g["home"]] = r(g["home"]) + delta
        R[g["away"]] = r(g["away"]) - delta
    brier = statistics.mean([(x["p"] - x["y"]) ** 2
                             for x in recs])
    home_rate = statistics.mean([x["y"] for x in recs])
    naive = statistics.mean([(home_rate - x["y"]) ** 2
                             for x in recs])
    n = len(recs)
    mx = statistics.mean([x["diff"] for x in recs])
    my = statistics.mean([x["margin"] for x in recs])
    b = (sum((x["diff"] - mx) * (x["margin"] - my) for x in recs)
         / sum((x["diff"] - mx) ** 2 for x in recs))
    a = my - b * mx
    sd = statistics.pstdev([x["margin"] - (a + b * x["diff"])
                            for x in recs])
    return {"sport": cfg["sport"],
            "season": cfg.get(
                "season_label",
                "2023-24 to 2026-27 regular seasons"),
            "fitted_at": datetime.now().astimezone().isoformat(
                timespec="seconds"),
            "source": f"RealGM international league schedule "
                      f"pages ({cfg['label']}; basketball."
                      f"realgm.com league {cfg['league_id']}; "
                      f"cached {fetched_at}; "
                      f"data/cache/{cfg['cache']})",
            "params": {"K": K, "hfa_elo": HFA_ELO},
            "ratings": {k: round(v, 1)
                        for k, v in sorted(R.items())},
            "margin_map": {"a": round(a, 3), "b": round(b, 4),
                           "sd": round(sd, 2), "n": n},
            "backtest": {"brier": round(brier, 4),
                         "naive_brier": round(naive, 4),
                         "naive_home_brier": round(naive, 4),
                         "n": n,
                         "protocol": "walk-forward (pre-game "
                                     "ratings, sequential Elo)"}}


def main(cfg):
    root = os.path.dirname(os.path.dirname(os.path.abspath(
        __file__)))
    cache_path = os.path.join(root, "data", "cache",
                              cfg["cache"])
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        root, "data", cfg["fit_file"])
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            blob = json.load(f)
        games, names = blob["games"], blob["teams"]
        fetched_at = blob["fetched_at"]
        print(f"cache: {len(games)} games ({fetched_at})",
              file=sys.stderr)
    else:
        games, names, fetched_at, stats = harvest(cfg)
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump({"fetched_at": fetched_at,
                       "source": "RealGM team schedule pages "
                                 f"({cfg['label']})",
                       "stats": stats, "teams": names,
                       "games": games}, f, indent=1)
    # the cache holds every league-labelled game; the RS
    # rule is applied here so it can be re-decided without
    # re-pulling
    games = rs_filter(games, names)
    blob = fit(games, cfg, fetched_at)
    blob["teams"] = {str(k): v for k, v in sorted(
        names.items(), key=lambda kv: int(kv[0]))}
    # a league may pin a club's identity against a source
    # mislabel (declared in the lane's builder with its
    # evidence); the override rewrites the gloss, never the
    # games or the ratings
    overrides = cfg.get("name_overrides") or {}
    for tid, real_name in overrides.items():
        blob["teams"][str(tid)] = real_name
    if overrides:
        blob["teams_note"] = (
            "RealGM hangs a wrong club name on team id(s) "
            + ", ".join(sorted(overrides, key=int))
            + " — the id's schedule history is one real club's, "
              "pinned by home venue + rosters in the lane "
              "builder's docstring; the gloss here names the "
              "real club.")
    bt = blob["backtest"]
    passed = bt["brier"] < bt["naive_home_brier"]
    per_season = {}
    for g in games:
        per_season[g["season_end"]] = per_season.get(
            g["season_end"], 0) + 1
    print(f"games by season_end: {per_season}")
    print(f"teams ({len(blob['teams'])}): "
          + ", ".join(f"{i}={n}" for i, n in
                      blob["teams"].items()))
    print(f"exam: walk-forward Brier {bt['brier']} vs naive "
          f"{bt['naive_home_brier']}, n={bt['n']} -> "
          f"{'PASSED' if passed else 'FAILED-EXAM'}")
    print(f"margin map: a={blob['margin_map']['a']} "
          f"b={blob['margin_map']['b']} sd={blob['margin_map']['sd']}")
    print(f"ratings: {blob['ratings']}")
    if games:
        g = games[len(games) // 2]
        print(f"sample: {g['date']} {g['away_name']} @ "
              f"{g['home_name']} {g['hs']}-{g['as']}")
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=1)
    print(f"wrote {out_path}")
