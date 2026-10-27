#!/usr/bin/env python3
"""fit_rugby.py — BetFi Xii (fix-guy R4): the rugby fits.

RUGBY LEAGUE — internationals only (the FanDuel board's league
fixtures are World Cup internationals, not club games).
Source: Rugby League Project (rugbyleagueproject.org), the
volunteer-curated results archive — the per-year competition
summary pages senior-international-matches-<year> (men) and
women-s-internationals-<year> (women), 2016..build-date. Rows
carry team names and scores in a regular table; parsed
structurally, blank-score fixtures skipped. Lanes intl_m /
intl_f are rated SEPARATELY (never pooled).

RUGBY UNION — New Zealand NPC only (the board's union fixture
is the NPC final; the Six Nations entry is an outright).
Source: Wikipedia season articles "YYYY Bunnings NPC"
(2021..current season), whose {{rugbybox}} templates carry
date / home / away / score for every match — parsed from
wikitext via the Wikipedia API. Lane npc: sequential Elo PLUS
an expanding-window margin map (margin ~ a + b * Elo-diff,
re-fit on prior matches only) and residual SD, so the lane can
price the spread FanDuel actually posts; the margin map's
walk-forward MAE is reported next to the winner exam.

Model: sequential Elo K=20, start 1500, no home edge (RLP rows
do not reliably designate a home side; NPC home designation in
the templates IS reliable, so the NPC margin map absorbs home
advantage in its intercept instead of a guessed constant).
Walk-forward throughout; naive baseline = running win rates
with a 4-match 0.5 prior (the house baseline). Drawn matches:
0.5/0.5 update, excluded from the Brier (no draw leg is priced
in either code's head-to-head markets here).

Usage: fit_rugby.py [out_path] (default ../data/v5-rugby.json)
Pages are cached under /tmp/guy4 (re-runs offline).

BUILD G (2026-10-27) — rugby-league attempt 2, PRE-REGISTERED in
priceg-preregistration.md before the exam ran. The league lanes'
attempt 1 (the model above) FAILED-EXAM in both sexes (intl_m
0.2392 vs naive 0.2308, n=189; intl_f 0.2377 vs 0.2354, n=110).
Attempt 2 is SPORT_CLOSERS' named closer — recency/squad
weighting — and nothing else: the base learner is unchanged
(sequential Elo, start 1500, no home edge, same naive, same
walk-forward protocol, bar unmoved), with exactly two declared
mechanisms:
  (R) recency decay: before each match, each team's stored
      rating regresses toward 1500 by 0.85^(years since that
      team's previous pool match), persistently;
  (S) squad-establishedness K: a team updates with K=40 while
      it has played fewer than 10 prior pool matches, else
      K=20 (expected scores from pre-match ratings, as before).
One attempt per lane; the fit file records both attempts.
The union NPC lane is NOT refit by this build: main() carries
its block verbatim from the existing output file, so a passing
lane cannot be moved by a same-week Wikipedia edit.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

K = 20.0
START = 1500.0
# Build G attempt-2 constants (pre-registered; see the module
# docstring and priceg-preregistration.md).
DECAY = 0.85        # (R) rating retention per year of absence
PROV_K = 40.0       # (S) K while a squad is unestablished
PROV_GAMES = 10     # (S) matches before a squad is established
UA = {"User-Agent": "Mozilla/5.0 (BetFi research)"}
CACHE = "/tmp/guy4"
CUTOFF = datetime.now(timezone.utc).strftime("%Y-%m-%d")
RL_YEARS = list(range(2016, 2027))
NPC_YEARS = list(range(2021, 2027))


def fetch(url, name):
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and os.path.getsize(path) > 5000:
        with open(path, encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8")
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------- rugby league (RLP) ----------------

RL_ROW = re.compile(
    r'<td class="team"><a href="/teams/\d+">([^<]+)</a></td>'
    r'<td class="n">(\d*)</td>'
    r'<td class="team"><a href="/teams/\d+">([^<]+)</a></td>'
    r'<td class="n">(\d*)</td>')
MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
     "Sep", "Oct", "Nov", "Dec"])}


def rl_matches(slug, years):
    out = []
    for y in years:
        try:
            html = fetch(
                f"https://www.rugbyleagueproject.org/competitions/"
                f"{slug}-{y}/summary.html", f"rlp_{slug}_{y}.html")
        except Exception:
            continue
        # rows sit under month headings; the summary lists them
        # chronologically within the year, which is all the
        # walk-forward needs (same-month order preserved).
        for team_a, sa, team_b, sb in RL_ROW.findall(html):
            if sa == "" or sb == "":
                continue
            out.append({"date": f"{y}-06-15", "seq_year": y,
                        "home": team_a.strip(), "away": team_b.strip(),
                        "hs": int(sa), "as": int(sb)})
    return out


# ---------------- rugby union (NPC wikitext) ----------------

def npc_matches(years):
    out = []
    for y in years:
        url = ("https://en.wikipedia.org/w/api.php?action=parse"
               f"&page={y}%20Bunnings%20NPC&prop=wikitext"
               "&format=json&formatversion=2")
        try:
            raw = fetch(url, f"npc_{y}.json")
            wt = json.loads(raw)["parse"]["wikitext"]
        except Exception:
            continue
        for block in re.findall(r"\{\{rugbybox(.*?)\}\}",
                                wt, re.S):
            def field(name):
                m = re.search(rf"\|\s*{name}\s*=\s*(.+)", block)
                return m.group(1).strip() if m else ""

            def team_name(raw):
                # {{Rut|X}} templates in most boxes; Ranfurly
                # Shield boxes use raw wikilinks with bold
                # markers ("'''RS –''' [[X (National Provincial
                # Championship)|X]]"). Normalize both to the
                # union's plain name.
                m = re.search(r"\{\{Rut\|([^}]+)\}\}", raw)
                if m:
                    return m.group(1).strip()
                links = re.findall(r"\[\[([^\]]+)\]\]", raw)
                if links:
                    last = links[-1]
                    if "|" in last:
                        return last.split("|")[-1].strip()
                    name = last.strip()
                    for suffix in (
                            " (National Provincial Championship)",
                            " Rugby Football Union"):
                        if name.endswith(suffix):
                            name = name[: -len(suffix)]
                    return name.strip()
                return raw.strip().strip("'")

            score = field("score").replace("–", "-")
            sm = re.match(r"^(\d+)\s*-\s*(\d+)$", score)
            home = team_name(field("home"))
            away = team_name(field("away"))
            dm = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
                           field("date"))
            if not sm or not home or not away or not dm:
                continue
            date = (f"{int(dm.group(3)):04d}-"
                    f"{MONTHS.get(dm.group(2)[:3], 1):02d}-"
                    f"{int(dm.group(1)):02d}")
            out.append({"date": date, "home": home, "away": away,
                        "hs": int(sm.group(1)),
                        "as": int(sm.group(2))})
    out.sort(key=lambda m: m["date"])
    return out


# ---------------- shared Elo walk-forward ----------------

def elo_p(ra, rb):
    return 1 / (1 + 10 ** (-(ra - rb) / 400))


def run_elo(matches, with_margin=False):
    elo, wins, games = {}, {}, {}
    brier = naive_brier = 0.0
    n = correct = 0
    # expanding margin map: margin = a + b * elo_diff, fit on
    # prior matches only (running sufficient statistics)
    sx = sy = sxx = sxy = 0.0
    cnt = 0
    resid = []
    mae = naive_mae = 0.0

    def wr(t):
        return (wins.get(t, 0) + 2.0) / (games.get(t, 0) + 4.0)

    for m in matches:
        h, a = m["home"], m["away"]
        margin = m["hs"] - m["as"]
        rh, ra = elo.get(h, START), elo.get(a, START)
        p = elo_p(rh, ra)
        pn = wr(h) / (wr(h) + wr(a))
        if margin != 0:
            y = 1.0 if margin > 0 else 0.0
            brier += (p - y) ** 2
            naive_brier += (pn - y) ** 2
            n += 1
            if (p >= 0.5) == (y == 1.0):
                correct += 1
        if with_margin and cnt >= 30:
            b = ((sxy - sx * sy / cnt)
                 / (sxx - sx * sx / cnt)) if (
                     sxx - sx * sx / cnt) > 0 else 0.0
            aint = (sy - b * sx) / cnt
            pred_margin = aint + b * (rh - ra)
            mae += abs(pred_margin - margin)
            naive_mae += abs(0 - margin)
            resid.append(margin - pred_margin)
        # updates
        y01 = 1.0 if margin > 0 else (0.0 if margin < 0 else 0.5)
        elo[h] = rh + K * (y01 - p)
        elo[a] = ra + K * ((1 - y01) - (1 - p))
        if margin > 0:
            wins[h] = wins.get(h, 0) + 1
        elif margin < 0:
            wins[a] = wins.get(a, 0) + 1
        games[h] = games.get(h, 0) + 1
        games[a] = games.get(a, 0) + 1
        if with_margin:
            d = rh - ra
            sx += d
            sy += margin
            sxx += d * d
            sxy += d * margin
            cnt += 1
    out = {"ratings": {t: round(r, 2) for t, r in elo.items()},
           "games": games,
           "backtest": {
               "n": n,
               "brier": round(brier / n, 4) if n else None,
               "naive_brier": round(naive_brier / n, 4) if n
               else None,
               "accuracy": round(correct / n, 4) if n else None}}
    if with_margin and cnt >= 30:
        b = ((sxy - sx * sy / cnt) / (sxx - sx * sx / cnt)) if (
            sxx - sx * sx / cnt) > 0 else 0.0
        aint = (sy - b * sx) / cnt
        sd = (sum(r * r for r in resid) / len(resid)) ** 0.5 \
            if resid else None
        out["margin_map"] = {"a": round(aint, 4), "b": round(b, 4),
                             "sd": round(sd, 3) if sd else None,
                             "n": cnt}
        out["backtest"]["margin_mae"] = round(
            mae / len(resid), 3) if resid else None
        out["backtest"]["margin_naive_mae"] = round(
            naive_mae / len(resid), 3) if resid else None
    return out


# ---------------- attempt 2 (Build G, pre-registered) ----------

def run_elo_attempt2(matches):
    """Attempt-2 league model: attempt 1's sequential Elo plus
    (R) per-team recency decay toward START between a team's
    matches and (S) per-team provisional K while a squad has
    played < PROV_GAMES pool matches. Naive baseline and the
    Brier accounting are attempt 1's, verbatim."""
    elo, wins, games, last_year = {}, {}, {}, {}
    brier = naive_brier = 0.0
    n = correct = 0

    def wr(t):
        return (wins.get(t, 0) + 2.0) / (games.get(t, 0) + 4.0)

    for m in matches:
        h, a = m["home"], m["away"]
        year = m["seq_year"]
        margin = m["hs"] - m["as"]
        # (R) decay each side's stored rating for its absence
        for t in (h, a):
            if t in last_year and year > last_year[t]:
                elo[t] = START + (elo.get(t, START) - START) \
                    * DECAY ** (year - last_year[t])
        rh, ra = elo.get(h, START), elo.get(a, START)
        p = elo_p(rh, ra)
        pn = wr(h) / (wr(h) + wr(a))
        if margin != 0:
            y = 1.0 if margin > 0 else 0.0
            brier += (p - y) ** 2
            naive_brier += (pn - y) ** 2
            n += 1
            if (p >= 0.5) == (y == 1.0):
                correct += 1
        # (S) each team updates with its own establishedness K
        y01 = 1.0 if margin > 0 else (0.0 if margin < 0 else 0.5)
        kh = PROV_K if games.get(h, 0) < PROV_GAMES else K
        ka = PROV_K if games.get(a, 0) < PROV_GAMES else K
        elo[h] = rh + kh * (y01 - p)
        elo[a] = ra + ka * ((1 - y01) - (1 - p))
        if margin > 0:
            wins[h] = wins.get(h, 0) + 1
        elif margin < 0:
            wins[a] = wins.get(a, 0) + 1
        games[h] = games.get(h, 0) + 1
        games[a] = games.get(a, 0) + 1
        last_year[h] = year
        last_year[a] = year
    return {"ratings": {t: round(r, 2) for t, r in elo.items()},
            "games": games,
            "backtest": {
                "n": n,
                "brier": round(brier / n, 4) if n else None,
                "naive_brier": round(naive_brier / n, 4) if n
                else None,
                "accuracy": round(correct / n, 4) if n else None}}


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "data", "v5-rugby.json")
    # The prior fit file is the record of attempt 1 (and the
    # carrier for the union block — see the docstring).
    prior = {}
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            prior = json.load(f)
    fit = {"fitted_at": datetime.now(timezone.utc).isoformat(),
           "model": (
               "league lanes: attempt 2 (Build G, pre-registered) "
               f"— sequential Elo start {START:g}, base "
               f"K={K:g}, recency decay {DECAY:g}^years-absent "
               f"toward {START:g}, provisional K={PROV_K:g} "
               f"while a squad has < {PROV_GAMES} pool matches, "
               "no home edge; union npc: attempt 1 — sequential "
               f"Elo K={K:g}, start {START:g}, no home edge (NPC "
               "home edge sits in the margin map's intercept), "
               "carried unchanged from the prior fit"),
           "league": {}, "union": {}}
    men = rl_matches("senior-international-matches", RL_YEARS)
    women = rl_matches("women-s-internationals", RL_YEARS)
    a2_model = (
        "sequential Elo, start 1500; recency decay 0.85^years "
        "since the team's previous pool match toward 1500; "
        "provisional K=40 while a squad has <10 prior pool "
        "matches, else K=20")
    for lane, matches in (("intl_m", men), ("intl_f", women)):
        blk = run_elo_attempt2(matches)
        blk["n_matches"] = len(matches)
        blk["source"] = ((prior.get("league") or {})
                         .get(lane) or {}).get("source")
        a1 = (((prior.get("league") or {}).get(lane) or {})
              .get("backtest")) or {}
        bt = blk["backtest"]
        blk["attempts"] = [
            {"attempt": 1,
             "model": (f"sequential Elo, K={K:g}, start "
                       f"{START:g}, no home edge"),
             "window": "RLP pull 2026-10-24 (2020-2026 "
                       "effective)",
             "brier": a1.get("brier"),
             "naive_brier": a1.get("naive_brier"),
             "n": a1.get("n"),
             "result": ("PASSED" if a1.get("brier") is not None
                        and a1.get("naive_brier") is not None
                        and a1["brier"] < a1["naive_brier"]
                        else "FAILED-EXAM")},
            {"attempt": 2, "model": a2_model,
             "window": "RLP pull 2026-10-27, refreshed "
                       "(2020-2026 effective)",
             "brier": bt.get("brier"),
             "naive_brier": bt.get("naive_brier"),
             "n": bt.get("n"),
             "result": ("PASSED" if bt.get("brier") is not None
                        and bt.get("naive_brier") is not None
                        and bt["brier"] < bt["naive_brier"]
                        else "FAILED-EXAM")}]
        fit["league"][lane] = blk
    fit["league"]["intl_m"]["source"] = (
        "Rugby League Project (rugbyleagueproject.org) "
        "senior-international-matches-<year> summary pages, "
        "2016-2026")
    fit["league"]["intl_f"]["source"] = (
        "Rugby League Project (rugbyleagueproject.org) "
        "women-s-internationals-<year> summary pages, 2016-2026")
    # Union NPC: carried verbatim from the prior fit (Build G
    # scope is the league lanes; a passing lane is not refit
    # from a live page inside another lane's build).
    fit["union"] = prior.get("union") or {}
    if not fit["union"]:
        raise SystemExit("no union block in the prior fit to "
                         "carry — refusing to drop the NPC lane")
    for code, lanes in (("league", fit["league"]),
                        ("union", fit["union"])):
        for name, blk in lanes.items():
            bt = blk["backtest"]
            print(f"{code}/{name}: matches={blk['n_matches']} "
                  f"n={bt['n']} brier={bt['brier']} "
                  f"naive={bt['naive_brier']} acc={bt['accuracy']} "
                  f"teams={len(blk['ratings'])} "
                  f"margin={blk.get('margin_map')}")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fit, f, indent=1)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
