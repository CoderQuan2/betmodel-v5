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
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

K = 20.0
START = 1500.0
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


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "data", "v5-rugby.json")
    fit = {"fitted_at": datetime.now(timezone.utc).isoformat(),
           "model": (f"sequential Elo K={K:g}, start {START:g}, "
                     "no home edge (NPC home edge sits in the "
                     "margin map's intercept)"),
           "league": {}, "union": {}}
    men = rl_matches("senior-international-matches", RL_YEARS)
    women = rl_matches("women-s-internationals", RL_YEARS)
    fit["league"]["intl_m"] = run_elo(men)
    fit["league"]["intl_m"]["n_matches"] = len(men)
    fit["league"]["intl_m"]["source"] = (
        "Rugby League Project (rugbyleagueproject.org) "
        "senior-international-matches-<year> summary pages, "
        "2016-2026")
    fit["league"]["intl_f"] = run_elo(women)
    fit["league"]["intl_f"]["n_matches"] = len(women)
    fit["league"]["intl_f"]["source"] = (
        "Rugby League Project (rugbyleagueproject.org) "
        "women-s-internationals-<year> summary pages, 2016-2026")
    npc = npc_matches(NPC_YEARS)
    fit["union"]["npc"] = run_elo(npc, with_margin=True)
    fit["union"]["npc"]["n_matches"] = len(npc)
    fit["union"]["npc"]["source"] = (
        "Wikipedia 'YYYY Bunnings NPC' season articles "
        "(rugbybox templates), 2021-2026, via the Wikipedia API")
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
