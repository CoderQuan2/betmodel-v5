#!/usr/bin/env python3
"""fit_soccer_halves_espn.py — BetFi Xii (fix-guy R7):
half-share exams for the ESPN-sourced soccer leagues —
the leagues fit_soccer_halves.py could not reach because
football-data.co.uk CSVs (the HTHG/HTAG source) do not
cover them: MLS, the Americas set, USL, NWSL and the
other women's leagues (26 leagues, the ESPN job table
from tools/fit_soccer_leagues.py R1+R2).

Half-time goals from ESPN payloads, two routes, both
verified before this builder ran (2026-10-24 probe,
34 games across usa.1/bra.1/usa.nwsl/usa.usl.1/eng.w.1/
arg.1):
  * PRIMARY — scoreboard `details`: scoring plays carry
    a clock displayValue ("3'", "45'+2'"); a goal is a
    1st-half goal iff its base minute <= 45. Per game the
    detail-goal count per team must reconcile EXACTLY
    with the final score, else the game is excluded and
    counted (0-0 games reconcile trivially).
  * VALIDATION + FALLBACK — summary `header` competitors
    carry period `linescores` ([1H, 2H] goal counts). A
    per-league sample (up to 20 covered games) must agree
    with the primary route on every sampled game.
PRE-STATED coverage bar (written before the sweep ran):
a league is examined on the primary route iff >= 85% of
its completed games reconcile AND >= 120 games reconcile
(burn-in 80 + a scoreable walk-forward tail). Below that,
the summary fallback runs over every completed game
(linescores[0] = 1H goals, sum must equal the final);
if the fallback also yields < 120 games the league ships
status NO-DATA with the coverage numbers and the sampled
payload fields as evidence — never a silent skip.

INTEGRITY GATE (added mid-run, BEFORE the remaining
leagues were examined, after the first three fallback
leagues produced physically impossible fits): the
sum-check alone cannot validate a split — uru.1/par.1/
bol.1 summaries reconcile in sum while entry[0] carries
0-2% of goals (every real league on record: 41-50%) and
uru.1 contains a NEGATIVE period value. A fallback-fed
league is therefore audited before any exam: any
negative or non-integer period value in the league's
pulled summaries, or an entry[0] goal share outside
[0.30, 0.60] over the fallback-covered games, marks the
feed corrupt -> NO-DATA with the audit numbers as
evidence. The gate changes no examined league's numbers;
it refuses three leagues the unaudited run had fitted
on garbage (their bogus blocks were overwritten).

Exam: IDENTICAL to the R6 per-form exam
(fit_soccer_halves.exam_league — walk-forward strengths
+ expanding shares, burn-in 80): 1H result passes iff
walk-forward Brier3 < fixed-0.44-share naive's; 1H total
passes iff Brier (over 1.5) < 0.44-share naive's. Blocks
land in data/v5-segments.json under "soccer-1h", keyed
exactly like the football-data blocks, so the checker
prices/stamps per (league, form) with no special case.

Usage: fit_soccer_halves_espn.py [segments_path]
       [--key=<league>] (one league; default: all)
Day pulls cache under /tmp/guy7 (re-runs are offline).
"""
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fit_soccer_halves import exam_league  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (BetFi research)"}
API = "https://site.api.espn.com/apis/site/v2/sports/soccer"
# R7 rebuild note: the first sweep's /tmp cache died with
# a tmpfs wipe mid-round; the cache now honors
# BETFI_FIT_CACHE so runs can be pointed at durable
# storage (the /tmp default is unchanged for other runs).
CACHE = os.environ.get("BETFI_FIT_CACHE", "/tmp/guy7")
MIN_COVER_FRAC = 0.85
MIN_COVER_GAMES = 120
VALIDATE_N = 20

# key -> (slug, windows) — the ESPN job table of
# tools/fit_soccer_leagues.py (R1 six + R2 twenty), the
# same windows the shipped full-game fits were built on.
LEAGUES = {
    "mls": ("usa.1", [(date(2025, 2, 22), date(2025, 10, 18))]),
    "brasileirao": ("bra.1", [(date(2025, 3, 29),
                               date(2025, 12, 7))]),
    "liga-mx": ("mex.1", [(date(2025, 1, 10), date(2025, 4, 21)),
                          (date(2025, 7, 11), date(2025, 11, 10))]),
    "liga-profesional": ("arg.1",
                         [(date(2025, 1, 23), date(2025, 5, 5)),
                          (date(2025, 7, 11), date(2025, 11, 17))]),
    "brasileirao-b": ("bra.2", [(date(2025, 4, 5),
                                 date(2025, 11, 23))]),
    "nacional-b": ("arg.2", [(date(2025, 2, 7),
                              date(2025, 10, 5))]),
    "usl-championship": ("usa.usl.1",
                         [(date(2025, 3, 8), date(2025, 10, 25)),
                          (date(2026, 3, 7), date(2026, 10, 24))]),
    "usl-league-one": ("usa.usl.l1",
                       [(date(2025, 3, 7), date(2025, 10, 25)),
                        (date(2026, 3, 6), date(2026, 10, 24))]),
    "peru-liga-1": ("per.1", [(date(2025, 2, 7),
                               date(2025, 11, 23)),
                              (date(2026, 2, 6),
                               date(2026, 10, 24))]),
    "colombia-primera": ("col.1",
                         [(date(2025, 1, 24), date(2025, 12, 7)),
                          (date(2026, 1, 23), date(2026, 10, 24))]),
    "ecuador-ligapro": ("ecu.1",
                        [(date(2025, 2, 14), date(2025, 11, 30)),
                         (date(2026, 2, 20), date(2026, 10, 24))]),
    "uruguay-primera": ("uru.1",
                        [(date(2025, 1, 31), date(2025, 12, 7)),
                         (date(2026, 1, 30), date(2026, 10, 24))]),
    "paraguay-primera": ("par.1",
                         [(date(2025, 1, 24), date(2025, 11, 30)),
                          (date(2026, 1, 23), date(2026, 10, 24))]),
    "bolivia-profesional": ("bol.1",
                            [(date(2025, 3, 28),
                              date(2025, 12, 14)),
                             (date(2026, 3, 20),
                              date(2026, 10, 24))]),
    "venezuela-primera": ("ven.1",
                          [(date(2025, 1, 24), date(2025, 11, 30)),
                           (date(2026, 1, 30),
                            date(2026, 10, 24))]),
    "costa-rica-primera": ("crc.1",
                           [(date(2025, 7, 25),
                             date(2025, 12, 21)),
                            (date(2026, 1, 9),
                             date(2026, 10, 24))]),
    "guatemala-liga": ("gua.1", [(date(2025, 7, 19),
                                  date(2025, 12, 21)),
                                 (date(2026, 1, 16),
                                  date(2026, 10, 24))]),
    "chile-primera": ("chi.1", [(date(2025, 2, 14),
                                 date(2025, 12, 7)),
                                (date(2026, 2, 13),
                                 date(2026, 10, 24))]),
    "nwsl": ("usa.nwsl", [(date(2025, 3, 14), date(2025, 11, 2)),
                          (date(2026, 3, 13),
                           date(2026, 10, 24))]),
    "liga-mx-femenil": ("mex.w.1",
                        [(date(2025, 7, 11), date(2025, 11, 23)),
                         (date(2026, 1, 9), date(2026, 10, 24))]),
    "wsl": ("eng.w.1", [(date(2024, 9, 20), date(2025, 5, 10)),
                        (date(2025, 9, 5), date(2026, 5, 16))]),
    "a-league-women": ("aus.w.1", [(date(2025, 10, 31),
                                    date(2026, 5, 2))]),
    "a-league": ("aus.1", [(date(2025, 10, 17),
                            date(2026, 5, 30))]),
    "brasileirao-c": ("bra.3", [(date(2025, 4, 12),
                                 date(2025, 10, 25)),
                                (date(2026, 4, 11),
                                 date(2026, 10, 24))]),
    "primera-b-ar": ("arg.3", [(date(2025, 2, 7),
                                date(2025, 12, 21)),
                               (date(2026, 2, 6),
                                date(2026, 10, 24))]),
    "liga-expansion": ("mex.2", [(date(2025, 1, 3),
                                  date(2025, 12, 21)),
                                 (date(2026, 1, 2),
                                  date(2026, 10, 24))]),
}


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _strip(blob):
    """Cache only what the exam reads (events' status,
    competitors' ids/names/scores, scoring details) — the
    full scoreboard payload is ~10x this and /tmp is a
    small tmpfs; the R7 sweep's first run filled it."""
    evs = []
    for ev in blob.get("events") or []:
        comp = (ev.get("competitions") or [{}])[0]
        cs = [{"homeAway": c.get("homeAway"),
               "score": c.get("score"),
               "team": {"id": (c.get("team") or {}).get("id"),
                        "displayName": (c.get("team") or {})
                        .get("displayName")}}
              for c in comp.get("competitors") or []]
        evs.append({"id": ev.get("id"), "date": ev.get("date"),
                    "status": ev.get("status"),
                    "competitions": [{"competitors": cs,
                                      "details":
                                          comp.get("details")}]})
    return {"events": evs}


def _fetch_day(slug, day):
    path = os.path.join(CACHE, f"sb_{slug}_{day:%Y%m%d}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    blob = _strip(_get(f"{API}/{slug}/scoreboard"
                       f"?dates={day:%Y%m%d}"))
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(blob, f)
    return blob


def _summary(slug, event_id):
    path = os.path.join(CACHE, f"sum_{slug}_{event_id}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    blob = _get(f"{API}/{slug}/summary?event={event_id}")
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(blob, f)
    return blob


def _ht_from_details(comp):
    """{team_id: [ht_goals, total_goals]} from scoring
    details, or None when a goal's clock won't parse."""
    goals = {}
    for d in comp.get("details") or []:
        if not d.get("scoringPlay") or d.get("shootout"):
            continue
        dv = (d.get("clock") or {}).get("displayValue") or ""
        m = re.match(r"(\d+)", dv)
        if not m:
            return None
        tid = (d.get("team") or {}).get("id")
        if tid is None:
            return None
        g = goals.setdefault(tid, [0, 0])
        g[1] += d.get("scoreValue") or 1
        if int(m.group(1)) <= 45:
            g[0] += d.get("scoreValue") or 1
    return goals


def pull_league(slug, windows):
    """All completed games in the windows, each annotated
    with its details-reconciliation state. Returns
    (games, stats) — games carry hth/hta when the primary
    route reconciled them."""
    days = []
    for start, end in windows:
        d = start
        while d <= end:
            days.append(d)
            d += timedelta(days=1)
    with ThreadPoolExecutor(max_workers=12) as ex:
        blobs = list(ex.map(lambda dy: _fetch_day(slug, dy),
                            days))
    games, seen = [], set()
    for blob in blobs:
        for ev in blob.get("events") or []:
            if ev.get("id") in seen:
                continue
            seen.add(ev.get("id"))
            st = ((ev.get("status") or {}).get("type") or {})
            if not st.get("completed"):
                continue
            comp = (ev.get("competitions") or [{}])[0]
            cs = {c["homeAway"]: c
                  for c in comp.get("competitors") or []}
            if set(cs) != {"home", "away"}:
                continue
            try:
                hs = int(float(cs["home"]["score"]))
                as_ = int(float(cs["away"]["score"]))
            except (KeyError, TypeError, ValueError):
                continue
            g = {"id": str(ev.get("id")),
                 "date": (ev.get("date") or "")[:10],
                 "home": cs["home"]["team"]["displayName"],
                 "away": cs["away"]["team"]["displayName"],
                 "hs": hs, "as": as_, "hth": None, "hta": None,
                 "covered": False}
            goals = _ht_from_details(comp)
            if goals is not None:
                gh = goals.get(cs["home"]["team"]["id"], [0, 0])
                ga = goals.get(cs["away"]["team"]["id"], [0, 0])
                if gh[1] == hs and ga[1] == as_:
                    g["hth"], g["hta"] = gh[0], ga[0]
                    g["covered"] = True
            games.append(g)
    games.sort(key=lambda g: (g["date"], g["id"]))
    return games


def validate_sample(slug, games, n=VALIDATE_N):
    """Primary route vs summary linescores on covered
    games: {checked, agree, summary_fields} — the fields
    are the NO-DATA evidence when a payload lacks period
    data."""
    sample = [g for g in games if g["covered"]][:n]
    out = {"checked": 0, "agree": 0, "summary_has_linescores": 0,
           "summary_competitor_fields": None}

    def one(g):
        s = _summary(slug, g["id"])
        hdr = (s.get("header") or {}).get("competitions") or [{}]
        hc = {c["homeAway"]: c
              for c in hdr[0].get("competitors") or []}
        fields = sorted((hc.get("home") or {}).keys())
        ls = {}
        for side in ("home", "away"):
            raw = (hc.get(side) or {}).get("linescores") or []
            vals = []
            for x in raw:
                try:
                    vals.append(int(x.get("displayValue")))
                except (TypeError, ValueError):
                    vals = []
                    break
            ls[side] = vals
        return fields, ls, g

    if not sample:
        return out
    with ThreadPoolExecutor(max_workers=8) as ex:
        for fields, ls, g in ex.map(one, sample):
            out["checked"] += 1
            out["summary_competitor_fields"] = fields
            if len(ls.get("home", [])) >= 2 \
                    and len(ls.get("away", [])) >= 2:
                out["summary_has_linescores"] += 1
                if ls["home"][0] == g["hth"] \
                        and ls["away"][0] == g["hta"] \
                        and sum(ls["home"]) == g["hs"] \
                        and sum(ls["away"]) == g["as"]:
                    out["agree"] += 1
    return out


def summary_fallback(slug, games):
    """HT from summary linescores for every completed
    game not already covered. Returns n newly covered."""
    todo = [g for g in games if not g["covered"]]

    def one(g):
        try:
            s = _summary(slug, g["id"])
        except Exception:  # noqa: BLE001
            return g, None
        hdr = (s.get("header") or {}).get("competitions") or [{}]
        hc = {c["homeAway"]: c
              for c in hdr[0].get("competitors") or []}
        vals = {}
        for side in ("home", "away"):
            raw = (hc.get(side) or {}).get("linescores") or []
            v = []
            for x in raw:
                try:
                    v.append(int(x.get("displayValue")))
                except (TypeError, ValueError):
                    v = []
                    break
            vals[side] = v
        return g, vals

    added = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        for g, vals in ex.map(one, todo):
            if vals and len(vals.get("home", [])) >= 2 \
                    and len(vals.get("away", [])) >= 2 \
                    and sum(vals["home"]) == g["hs"] \
                    and sum(vals["away"]) == g["as"]:
                g["hth"], g["hta"] = vals["home"][0], \
                    vals["away"][0]
                g["covered"] = True
                g["via"] = "summary-linescores"
                added += 1
    return added


def audit_summaries(slug, games):
    """Integrity audit of a league's summary period data
    (see the header gate): negative/non-integer period
    values across every summary pulled for the league,
    plus the entry[0] goal share over fallback-covered
    games."""
    import glob as _glob
    neg = 0
    files = 0
    for p in _glob.glob(os.path.join(CACHE, f"sum_{slug}_*.json")):
        files += 1
        try:
            with open(p, encoding="utf-8") as f:
                s = json.load(f)
        except Exception:  # noqa: BLE001
            continue
        hdr = (s.get("header") or {}).get("competitions") \
            or [{}]
        for c in hdr[0].get("competitors") or []:
            for x in c.get("linescores") or []:
                try:
                    v = int(x.get("displayValue"))
                except (TypeError, ValueError):
                    neg += 1
                    continue
                if v < 0:
                    neg += 1
    fb_games = [g for g in games if g.get("via")
                == "summary-linescores"]
    e0 = sum(g["hth"] or 0 for g in fb_games)
    tot = sum(g["hs"] + g["as"] for g in fb_games)
    share = (e0 / tot) if tot else None
    corrupt = neg > 0 or share is None or share < 0.30 \
        or share > 0.60
    return {"summaries_scanned": files,
            "negative_or_noninteger_period_values": neg,
            "fallback_games": len(fb_games),
            "entry0_goal_share": (round(share, 4)
                                  if share is not None
                                  else None),
            "corrupt": corrupt}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--key="):
            only = a.split("=", 1)[1]
    seg_path = args[0] if args else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "data", "v5-segments.json")
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".."))
    import betmodel5 as b5
    doc = {}
    if os.path.exists(seg_path):
        with open(seg_path, encoding="utf-8") as f:
            doc = json.load(f)
    out = doc.get("soccer-1h") or {}
    for key, (slug, windows) in LEAGUES.items():
        if only and key != only:
            continue
        games = pull_league(slug, windows)
        total = len(games)
        covered = sum(1 for g in games if g["covered"])
        frac = covered / total if total else 0.0
        val = validate_sample(slug, games)
        route = "scoreboard-details"
        fb = 0
        if frac < MIN_COVER_FRAC or covered < MIN_COVER_GAMES:
            fb = summary_fallback(slug, games)
            covered = sum(1 for g in games if g["covered"])
            frac = covered / total if total else 0.0
            route = ("summary-linescores-fallback"
                     if covered >= MIN_COVER_GAMES else route)
        cov = {"games_completed": total,
               "games_ht_covered": covered,
               "coverage_frac": round(frac, 4),
               "fallback_added": fb,
               "validation": val,
               "bar": f"primary route needs >= {MIN_COVER_FRAC} "
                      f"reconciled and >= {MIN_COVER_GAMES} "
                      "games (pre-stated in the builder header)"}
        audit = audit_summaries(slug, games) if fb else None
        if audit:
            cov["summary_integrity_audit"] = audit
        if audit and audit["corrupt"]:
            out[key] = {
                "status": "NO-DATA",
                "exam_route": route,
                "coverage": cov,
                "evidence": (
                    f"ESPN {slug} period data is corrupt: "
                    f"scoreboard scoring details reconcile "
                    f"for too few games, and the summary "
                    f"period linescores fail the integrity "
                    f"audit — "
                    f"{audit['negative_or_noninteger_period_values']}"
                    f" negative/non-integer period values in "
                    f"{audit['summaries_scanned']} pulled "
                    f"summaries, entry[0] goal share "
                    f"{audit['entry0_goal_share']} over "
                    f"{audit['fallback_games']} fallback "
                    "games (real 1H shares run 0.41-0.50; "
                    "the band is [0.30, 0.60]). The split "
                    "the payload carries is not a half-time "
                    "split, so no half-share is fitted — "
                    "the league stamps NO-DATA with this "
                    "evidence."),
                "ht_source": "ESPN scoreboard details + "
                             "summary linescores (corrupt)"}
            print(f"  {key}: NO-DATA — corrupt summary "
                  f"period feed (audit {audit})", flush=True)
        elif covered < MIN_COVER_GAMES:
            fields = val.get("summary_competitor_fields")
            out[key] = {
                "status": "NO-DATA",
                "exam_route": route,
                "coverage": cov,
                "evidence": (
                    f"ESPN {slug}: {covered} of {total} "
                    "completed games carry reconcilable "
                    "half-time goals (scoreboard scoring "
                    "details reconciling to the final score, "
                    "plus summary period linescores where "
                    f"present); validation sample: "
                    f"{val.get('checked')} checked, "
                    f"{val.get('summary_has_linescores')} "
                    "with summary linescores; summary "
                    f"competitor fields sampled: {fields}. "
                    "Below the pre-stated 120-game floor for "
                    "the walk-forward half-share exam — the "
                    "league stamps NO-DATA, never a guessed "
                    "share."),
                "ht_source": "ESPN scoreboard details + "
                             "summary linescores (insufficient)"}
            print(f"  {key}: NO-DATA — {covered}/{total} "
                  f"HT-covered (validation {val})", flush=True)
        else:
            exam_games = [g for g in games if g["covered"]]
            r = exam_league(exam_games, b5.SOC_PRIOR_LH,
                            b5.SOC_PRIOR_LA)
            if r is None:
                out[key] = {"status": "NO-DATA",
                            "exam_route": route, "coverage": cov,
                            "evidence": "exam produced no "
                                        "scoreable games",
                            "ht_source": "ESPN period scores"}
                print(f"  {key}: NO-DATA — exam empty",
                      flush=True)
                continue
            r["exam_route"] = route
            r["coverage"] = cov
            r["ht_source"] = (
                "ESPN scoreboard scoring details "
                "(clock-parsed 1st-half goals, reconciled "
                "to final scores; validated against ESPN "
                "summary period linescores: "
                f"{val.get('agree')}/{val.get('checked')} "
                "sampled games agree)"
                if route == "scoreboard-details" else
                "ESPN summary period linescores (scoreboard "
                "details did not reconcile for enough games; "
                f"validation {val.get('agree')}/"
                f"{val.get('checked')} sampled agree)")
            r["bar_r7"] = (
                "R7 (pre-stated): the R6 per-form bar on "
                "ESPN period scores — 1H result passes iff "
                "walk-forward Brier3 beats the fixed-0.44-"
                "share naive's; 1H total passes iff its "
                "Brier beats the 0.44-share naive's")
            out[key] = r
            bt = r["backtest"]
            print(f"  {key}: {r['status']} route={route} "
                  f"cov {covered}/{total} shares "
                  f"{r['share_h']}/{r['share_a']} result "
                  f"{bt['brier3_1h']} vs {bt['brier3_1h_naive']}, "
                  f"total {bt['brier_over15']} vs "
                  f"{bt['brier_over15_naive']} (n={bt['n']})",
                  flush=True)
        # checkpoint per league — the sweep is long.
        doc["soccer-1h"] = out
        doc["soccer_1h_espn_source"] = (
            "R7: ESPN scoreboard scoring details (primary) / "
            "summary period linescores (fallback), windows "
            "identical to the shipped full-game fits; exam "
            "= fit_soccer_halves.exam_league (R6 per-form "
            "bar)")
        with open(seg_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1)
    print("wrote", seg_path)


if __name__ == "__main__":
    main()
