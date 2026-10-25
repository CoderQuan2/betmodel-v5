#!/usr/bin/env python3
"""BetFi Xii — props coverage builder (CODER GLOW, Round 2).

Closes player-prop cells player by player:

  1. HARVEST the player props actually on the board: the slate
     pull (SPORT pages) carries no props — props live on per-game
     event pages, behind tab SLUGS (the frontend moved from tab
     ids to slugs; tab=<id> is silently ignored tonight, evidence
     in the run log). Probe slugs on one game per sport, then
     harvest every game on the pull with the slugs that answer.
  2. PARSE main-line player markets ("<Player> - <Stat>", two
     runners, MOVING_HANDICAP) into checker-format markets.
     Alt lines, quarter/half segments and "To Score X+"
     milestones are different families — counted, not parsed.
  3. RESOLVE each player to an ESPN athlete id via ESPN search
     v2 (exact displayName + league matching the market's sport;
     ambiguity stays unresolved, named).
  4. FETCH the player's game log (ESPN common/v3, the house
     method) into data/cache/gamelog_<id>.json — the exact files
     prop_band() prices from — and record the mapping in
     data/cache/athlete_index.json. Season rule (disclosed):
     first season (current, then previous) carrying >= 8 event
     rows; if none does, the deepest log wins and is flagged
     thin. Nothing is fetched twice; everything fetched is
     cached.

Usage:
  fetch_gamelogs.py harvest <pull.json> <out.json>
  fetch_gamelogs.py fetch <harvest.json> [--max-players N]
  fetch_gamelogs.py strip

Round 3: fetch attempts EVERY player on the harvest by default
(MAX_PLAYERS env caps it only when set). Name resolution tries
documented name-FORM variants (suffix Jr/Sr/II/III/IV stripped or
re-attached, periods in initials) \u2014 every variant still has to
match an ESPN displayName EXACTLY and survive the league filter;
ambiguity stays unresolved, named. Fetched logs are written
STRIPPED (stat rows only: names/labels/displayNames/seasonTypes
+ a compact event_dates map; the raw ESPN envelope \u2014 links,
filters, glossary, per-event metadata \u2014 is dropped). `strip`
converts an existing cache in place. `harvest` ends with a
STALENESS report: per cached player, the last game date in
their log and its age against a 10-day line (report only \u2014
no auto-refetch; refresh by re-running fetch, whose existing
path re-fetches any player whose file is deleted).

Round 4 \u2014 RESOLVER TRUTH FIX (the namesake trap): an exact
displayName match can be the WRONG PERSON. "Aaron Jones"
exact-matches an Indianapolis Colts namesake (ESPN 17766)
whose gamelog is empty for every probed season, while the
board player is "Aaron Jones Sr." (Minnesota Vikings,
3042519). Round 3 accepted the empty log as NO-GAMELOG and
never tried the suffix form. The law now: when the resolved
player's gamelog is EMPTY across all probed seasons, try
suffix-form variants (Sr./Jr./II/III) of the same name in the
same league family BEFORE declaring NO-GAMELOG; a variant
that carries a log wins, and the disambiguation is recorded
in athlete_index.json (board name, resolved name, id,
reason). If MORE THAN ONE variant carries a log, that is
ambiguity \u2014 unresolved, never a guess. An index entry
whose cached log is empty is likewise never trusted: it
falls back through the same path instead of short-cutting
to CACHED. Whenever another same-name athlete exists in
the family, the index entry carries the namesake-collision
risk explicitly.

Round 5 — SURNAME-FALLBACK GUARD (Praxis ruling): the
surname-unique fallback (legal name on the board, common
form at ESPN) may fire ONLY when the first names are
COMPATIBLE — identical, a curated nickname pair, or one is
the other's initial. A unique surname alone is NOT identity:
Round 3's unguarded fallback matched Tiffany Hayes to
Jaxson Hayes and Veronica Burton to Tyler Burton (both
entries removed in Round 4). Under the guard those matches
are rejected with the reason recorded, while
Kenneth -> Kenny Gainwell still resolves. The guard lives
ONLY here, in resolve_player: the engine-side athlete_info()
does no name matching at all (exact index/ATHLETES lookup),
so there is no second fallback to align.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(DATA, "cache")
sys.path.insert(0, os.path.abspath(ROOT))

UA = {"User-Agent": "betfi-xii-props"}

SLUG_CANDIDATES = {
    "nba": ["player-points", "player-assists", "player-rebounds",
            "player-threes", "player-combos", "player-defense",
            "team-props"],
    "nfl": ["passing-props", "rushing-props", "receiving-props",
            "td-scorer-props", "scoring", "team-props",
            "game-specials"],
    "ncaaf": ["passing-props", "rushing-props", "receiving-props",
              "td-scorer-props", "scoring", "team-props",
              "player-props"],
}

STAT_TABS = {
    "nba": {"player-points": "Points", "player-assists": "Assists",
            "player-rebounds": "Rebounds"},
    "nfl": {"passing-props": None, "rushing-props": None,
            "receiving-props": None},
    "ncaaf": {"passing-props": None, "rushing-props": None,
              "receiving-props": None},
}

STAT_MAP = {
    "Points": "points", "Assists": "assists",
    "Rebounds": "totalRebounds",
    "Passing Yards": "passingYards",
    "Rushing Yards": "rushingYards",
    "Receiving Yards": "receivingYards",
    "Passing Touchdowns": "passingTouchdowns",
    "Rushing Touchdowns": "rushingTouchdowns",
    "Receiving Touchdowns": "receivingTouchdowns",
    "Completions": "completions",
    "Pass Attempts": "passingAttempts",
    "Interceptions": "interceptions",
    "Receptions": "receptions",
    "Rushing Attempts": "rushingAttempts",
    "Receiving + Rushing Yards": None,
    "Passing + Rushing Yards": None,
    "Passing Yds": "passingYards",
    "Rushing Yds": "rushingYards",
    "Receiving Yds": "receivingYards",
    "Passing TDs": "passingTouchdowns",
    "Rushing TDs": "rushingTouchdowns",
    "Receiving TDs": "receivingTouchdowns",
    "Total Receptions": "receptions",
    "Total Rushing Yards": "rushingYards",
    "Total Passing Yards": "passingYards",
    "Total Receiving Yards": "receivingYards",
}

LEAGUES = {  # market sport -> (gamelog path, [seasons], search tag)
    "nfl": ("football/nfl", [2026, 2025], "NFL"),
    "ncaaf": ("football/college-football", [2026, 2025], None),
    "nba": ("basketball/nba", [2027, 2026], "NBA"),
    "nhl": ("hockey/nhl", [2026, 2025], "NHL"),
}


def http_json(url, timeout=25, retries=2):
    """GET JSON with short backoff retries \u2014 a 440-player
    harvest run leans on ESPN search hard enough that single
    transient failures were masquerading as unresolved players
    (Klay Thompson 'not found' in pass 1 was a dropped request,
    proven on the re-pass)."""
    import time
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            last = e
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise last


# ---------------------------------------------------------------- harvest

def _odds(runner):
    try:
        return runner["winRunnerOdds"]["americanDisplayOdds"][
            "americanOddsInt"]
    except Exception:
        return None


def parse_player_market(mk, sport, game):
    """Checker-format markets for a main-line player market, or
    None (with a family tag) when it is not one."""
    name = mk.get("marketName") or ""
    m = re.match(r"^(.+?) - (.+)$", name)
    if not m:
        return None, "no-dash"
    player, label = m.group(1).strip(), m.group(2).strip()
    if (label.startswith("Alt") or "Qtr" in label
            or "Quarter" in label or "Half" in label
            or "To Score" in name or "1st" in label
            or "2nd" in label):
        return None, "segment-or-alt"
    if mk.get("bettingType") != "MOVING_HANDICAP":
        return None, "not-main-line"
    runners = [r for r in mk.get("runners", [])
               if r.get("runnerStatus") == "ACTIVE"]
    if len(runners) != 2:
        return None, "not-two-runner"
    stat = STAT_MAP.get(label, "__UNMAPPED__")
    if stat == "__UNMAPPED__":
        return None, f"unmapped-stat:{label}"
    if stat is None:
        return None, f"combo-stat:{label}"
    out = []
    for r in runners:
        side = (r.get("result") or {}).get("type", "").lower()
        if side not in ("over", "under"):
            return None, "no-over-under"
        out.append({
            "sport": sport, "market": "player-props",
            "player": player, "stat": stat,
            "line": float(r.get("handicap")),
            "side": side, "price": _odds(r),
            "home": game["home"], "away": game["away"],
            "fd_market_id": mk.get("marketId"),
            "fd_event_id": mk.get("eventId"),
            "market_time": mk.get("marketTime")})
    return out, "main-line"


def parse_team_market(mk, sport, game):
    """Main-line team totals off the team-props tab. The
    marketType is the reliable key (HOME_/AWAY_TEAM_TOTAL_*);
    runners are Over/Under with the line as the handicap. Alt
    markets (one runner per line) are counted by the caller,
    not converted."""
    mtype = mk.get("marketType") or ""
    if "TEAM_TOTAL" not in mtype and "TEAM_ALTERNATE_TOTAL" \
            not in mtype:
        return None
    if "ALTERNATE" in mtype:
        return None
    team = "home" if mtype.startswith("HOME") else "away"
    if mk.get("bettingType") != "MOVING_HANDICAP":
        return None
    runners = [r for r in mk.get("runners", [])
               if r.get("runnerStatus") == "ACTIVE"]
    if len(runners) != 2:
        return None
    out = []
    for r in runners:
        side = (r.get("result") or {}).get("type", "").lower()
        if side not in ("over", "under"):
            return None
        out.append({
            "sport": sport, "market": "team-props",
            "team": team, "line": float(r.get("handicap")),
            "side": side, "price": _odds(r),
            "home": game["home"], "away": game["away"],
            "fd_market_id": mk.get("marketId"),
            "fd_event_id": mk.get("eventId"),
            "market_time": mk.get("marketTime")})
    return out


def harvest(pull_path, out_path, max_games=None):
    import betmodel5 as b5
    with open(pull_path) as f:
        pull = json.load(f)
    games = {}
    for m in pull["markets"]:
        if m["sport"] in SLUG_CANDIDATES and m.get("fd_event_id"):
            games.setdefault((m["sport"], m["fd_event_id"]),
                             {"sport": m["sport"],
                              "event_id": m["fd_event_id"],
                              "home": m.get("home"),
                              "away": m.get("away")})
    games = list(games.values())
    if max_games:
        by_sport = {}
        for g in games:
            by_sport.setdefault(g["sport"], []).append(g)
        games = []
        for s, gs in by_sport.items():
            games.extend(sorted(gs, key=lambda g: g["event_id"])
                         [:max_games])
    print(f"games to harvest: {len(games)} "
          f"({ {s: sum(1 for g in games if g['sport'] == s) for s in SLUG_CANDIDATES} })")

    def base_markets(g):
        r = b5.fd_get(b5.FANDUEL_EVENT_ENDPOINT, {
            "eventId": g["event_id"],
            "useCombinedTouchdownsVirtualMarket": "true",
            "useQuickBets": "true"})
        mk = (r.get("attachments") or {}).get("markets") or {}
        return {k: v for k, v in mk.items()}

    def tab_markets(g, slug):
        r = b5.fd_get(b5.FANDUEL_EVENT_ENDPOINT, {
            "eventId": g["event_id"],
            "useCombinedTouchdownsVirtualMarket": "true",
            "useQuickBets": "true", "tab": slug})
        return (r.get("attachments") or {}).get("markets") or {}

    # probe slugs PER GAME — tab sets vary game by game (a
    # featured NCAAF game carries passing props, a minor one may
    # carry only rushing). One sport-level probe undercounts.
    live_slugs = {}

    def probe(g):
        base = base_markets(g)
        live = []
        for slug in SLUG_CANDIDATES[g["sport"]]:
            try:
                mk = tab_markets(g, slug)
            except Exception:
                continue
            if set(mk) - set(base):
                live.append((slug, mk))
        return live

    parsed, team_parsed, skipped = [], [], {}
    raw_team_names = []

    def work(g):
        out_p, out_t, skip, raw = [], [], {}, []
        seen_mids = set()
        for slug, mk in probe(g):
            live_slugs.setdefault(g["sport"], set()).add(slug)
            for mid, m in mk.items():
                if mid in seen_mids:
                    continue
                seen_mids.add(mid)
                if slug == "team-props":
                    tp = parse_team_market(m, g["sport"], g)
                    if tp:
                        out_t.extend(tp)
                    else:
                        raw.append(m.get("marketName"))
                    continue
                if slug not in STAT_TABS.get(g["sport"], {}):
                    continue
                res, why = parse_player_market(m, g["sport"], g)
                if res:
                    out_p.extend(res)
                else:
                    skip[why] = skip.get(why, 0) + 1
        return out_p, out_t, skip, raw

    with ThreadPoolExecutor(max_workers=6) as ex:
        for out_p, out_t, skip, raw in ex.map(work, games):
            parsed.extend(out_p)
            team_parsed.extend(out_t)
            for k, v in skip.items():
                skipped[k] = skipped.get(k, 0) + v
            raw_team_names.extend(raw)
    # dedupe parsed by (fd_market_id, side)
    seen = set()
    ded = []
    for m in parsed:
        k = (m["fd_market_id"], m["side"])
        if k not in seen:
            seen.add(k)
            ded.append(m)
    seen = set()
    dedt = []
    for m in team_parsed:
        k = (m["fd_market_id"], m["side"])
        if k not in seen:
            seen.add(k)
            dedt.append(m)
    players = sorted({m["player"] for m in ded})
    print(f"parsed player-prop markets: {len(ded)} "
          f"({len(players)} players); team-prop markets: "
          f"{len(dedt)}; skipped: {skipped}")
    print(f"team-props raw names sample: "
          f"{sorted(set(raw_team_names))[:12]}")
    staleness_report()
    with open(out_path, "w") as f:
        json.dump({"pulled_at": pull.get("pulled_at"),
                   "live_slugs": {k: sorted(v) for k, v
                                  in live_slugs.items()},
                   "player_markets": ded,
                   "team_markets": dedt,
                   "skipped": skipped,
                   "team_raw_names": sorted(set(raw_team_names))},
                  f, indent=1)
    return ded, dedt


# ---------------------------------------------------------------- fetch

SUFFIXES = ("Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV")


def name_variants(name):
    """Documented name-FORM variants of the SAME person: the
    FanDuel string, generational suffix stripped, suffix
    re-attached in the common ESPN spellings. Resolution still
    requires an EXACT ESPN displayName match to one variant \u2014
    variants widen the forms tried, never the match standard."""
    out = [name]
    base = name
    for suf in SUFFIXES:
        if base.endswith(" " + suf):
            base = base[:-(len(suf) + 1)].strip()
            break
    if base != name:
        out.append(base)
    for suf in ("Jr.", "Sr.", "II", "III"):
        cand = f"{base} {suf}"
        if cand not in out:
            out.append(cand)
    # initials with/without periods: "J.J. McCarthy" <-> "JJ McCarthy"
    if "." in base:
        out.append(base.replace(".", ""))
    # diacritics folded: "Moussa Diabaté" <-> ESPN "Moussa Diabate"
    import unicodedata
    folded = "".join(ch for ch in unicodedata.normalize(
        "NFKD", base) if not unicodedata.combining(ch))
    if folded != base and folded not in out:
        out.append(folded)
    # FanDuel drops the trailing period on initials ("J.J McCarthy"
    # for ESPN's "J.J. McCarthy"): re-dot a leading initials token.
    parts = base.split(" ", 1)
    tok = parts[0].replace(".", "")
    if len(parts) == 2 and tok.isalpha() and 1 < len(tok) <= 3 \
            and all(c.isupper() for c in tok):
        dotted = ".".join(tok) + "."
        cand = f"{dotted} {parts[1]}"
        if cand not in out:
            out.append(cand)
    return out


def _search_contents(query):
    """Raw ESPN search v2 player contents for a query."""
    try:
        r = http_json("https://site.api.espn.com/apis/search/v2"
                      "?query=" + urllib.parse.quote(query))
    except Exception:
        return []
    out = []
    for res in r.get("results", []):
        if res.get("type") != "player":
            continue
        out.extend(res.get("contents", []))
    return out


def _family_filter(hits, sport):
    fam = {"nfl": ("20", "NFL"), "ncaaf": ("20", None),
           "nba": ("40", "NBA"), "nhl": ("70", "NHL")}[sport]
    hits = [h for h in hits if str(h["sport_id"]) == fam[0]
            and (fam[1] is None or h["desc"] == fam[1])]
    if sport == "ncaaf":
        hits = [h for h in hits
                if h["desc"] not in ("NFL", "NBA", "NHL")]
    return hits


def _search_hits(name, sport):
    """ESPN search v2 hits for one exact name form, league-family
    filtered. Returns hit dicts (possibly empty)."""
    path, _seasons, _tag = LEAGUES[sport]
    hits = []
    for c in _search_contents(name):
            if c.get("displayName") != name:
                continue
            uid = c.get("uid", "")
            mm = re.match(r"s:(\d+)~l:(\d+)~a:(\d+)$", uid)
            if not mm:
                continue
            hits.append({"id": int(mm.group(3)),
                         "league_id": int(mm.group(2)),
                         "sport_id": int(mm.group(1)),
                         "desc": c.get("description", ""),
                         "team": c.get("subtitle", "")})
    return _family_filter(hits, sport)


def _norm_team(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def _team_matches(team_norm, want):
    """Normalized team-name match in EITHER containment
    direction: the board prints 'North Dakota State' where
    ESPN subtitles 'North Dakota State Bison', and prints
    codes ('MIN') that fetch_all expands to full names via
    the engine's FD code maps before calling resolve."""
    if not team_norm:
        return False
    return any(team_norm == w or team_norm in w or w in team_norm
               for w in want if w)


# ------------------------------------------------ surname guard
# Round 5 (Praxis ruling): the surname-unique fallback may fire
# ONLY when the first names are compatible — (a) identical,
# (b) a diminutive/nickname pair from this curated map, or
# (c) one first name is the other's initial. The map is
# EXPLICIT by design: canonical first name -> its nicknames.
# Compatibility is symmetric and group-wise (two nicknames of
# the same canonical name are compatible with each other).
NICKNAME_GROUPS = {
    "kenneth": {"kenny", "ken"},
    "william": {"bill", "billy", "will", "willie", "liam"},
    "robert": {"bob", "bobby", "rob", "robbie", "bert"},
    "james": {"jim", "jimmy", "jamie"},
    "john": {"jack", "johnny", "jon", "jonny"},
    "michael": {"mike", "mick", "mickey"},
    "richard": {"rick", "ricky", "rich", "dick"},
    "joseph": {"joe", "joey"},
    "thomas": {"tom", "tommy"},
    "charles": {"chuck", "charlie", "charley"},
    "edward": {"ed", "eddie", "ted", "ned"},
    "daniel": {"dan", "danny"},
    "matthew": {"matt", "matty"},
    "andrew": {"andy", "drew"},
    "christopher": {"chris", "topher"},
    "jonathan": {"jon", "jonny", "jonathan"},
    "nicholas": {"nick", "nicky"},
    "samuel": {"sam", "sammy"},
    "benjamin": {"ben", "benny", "benji"},
    "zachary": {"zach", "zack", "zac"},
    # sensible extensions (same standard: established
    # English diminutives, never invented pairings)
    "david": {"dave", "davey"},
    "stephen": {"steve", "steven"},
    "steven": {"steve", "stephen"},
    "anthony": {"tony", "ant"},
    "patrick": {"pat", "paddy"},
    "timothy": {"tim", "timmy"},
    "joshua": {"josh"},
    "jacob": {"jake"},
    "alexander": {"alex", "al", "xander"},
    "frederick": {"fred", "freddie"},
    "gregory": {"greg"},
    "jeffrey": {"jeff"},
    "donald": {"don", "donnie", "donny"},
    "ronald": {"ron", "ronnie", "ronny"},
    "gerald": {"jerry", "gerry"},
    "walter": {"walt", "wally"},
    "henry": {"hank", "harry"},
    "albert": {"al", "bert", "albie"},
    "raymond": {"ray"},
    "eugene": {"gene"},
    "lawrence": {"larry", "law"},
    "francis": {"frank", "fran"},
    "peter": {"pete"},
    "paul": set(),
    "george": {"georgie"},
    "harold": {"harry", "hal"},
    "arthur": {"art", "artie"},
    "vincent": {"vince", "vinny", "vin"},
    "nathaniel": {"nathan", "nate", "nat"},
    "nathan": {"nate", "nat"},
    "gabriel": {"gabe"},
    "isaac": {"ike", "zac"},
    "zachariah": {"zach", "zack"},
    "theodore": {"ted", "teddy", "theo"},
    "leonard": {"leo", "len", "lenny"},
    "bernard": {"bernie"},
    "stanley": {"stan"},
    "sidney": {"sid"},
    "sydney": {"syd", "sid"},
    "cameron": {"cam"},
    "brandon": {"brand"},
    "bradley": {"brad"},
    "mitchell": {"mitch"},
    "terrence": {"terry"},
    "terence": {"terry"},
    "jerome": {"jerry"},
    "calvin": {"cal"},
    "reginald": {"reggie", "reg"},
    "russell": {"russ", "rusty"},
    "tobias": {"toby"},
    "sebastian": {"seb"},
    "dominic": {"dom", "nick"},
    "maximilian": {"max"},
    "maxwell": {"max"},
    "oliver": {"ollie"},
    "samson": {"sam"},
    "solomon": {"sol"},
    "emmanuel": {"manny"},
    "manuel": {"manny"},
    "raphael": {"ralph"},
    "xavier": {"x"},
    "josiah": {"jo"},
    "jeremiah": {"jerry", "jeremy"},
    "jeremy": {"jeremiah"},
    "isaiah": {"zay"},
    "elijah": {"eli"},
    "elias": {"eli"},
    "silas": {"si"},
    "tobiah": {"toby"},
}


def _fold_token(tok):
    """Fold a name token for comparison: lowercase, strip
    punctuation, fold diacritics."""
    import unicodedata
    tok = unicodedata.normalize("NFKD", tok or "")
    tok = "".join(ch for ch in tok if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]", "", tok.lower())


def _first_name(full):
    """First-name token of a full display/board name, with a
    trailing generational suffix removed first."""
    parts = (full or "").strip().split()
    if len(parts) > 2 and parts[-1].strip(".,") in (
            "Jr", "Sr", "II", "III", "IV"):
        parts = parts[:-1]
    return _fold_token(parts[0]) if parts else ""


def first_names_compatible(board_first, espn_first):
    """The Round-5 guard predicate. Inputs are RAW first-name
    strings (folded here). Compatible iff (a) identical,
    (b) a nickname pair in NICKNAME_GROUPS (same group), or
    (c) one is the other's initial (a single letter equal to
    the other's first letter)."""
    a, b = _fold_token(board_first), _fold_token(espn_first)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) == 1 and b.startswith(a):
        return True
    if len(b) == 1 and a.startswith(b):
        return True
    for canon, nicks in NICKNAME_GROUPS.items():
        group = {canon} | set(nicks)
        if a in group and b in group:
            return True
    return False


def _surname_guard(board_name, espn_display):
    """(ok, reason) for a surname-unique candidate."""
    bf, ef = _first_name(board_name), _first_name(espn_display)
    if first_names_compatible(bf, ef):
        return True, (f"first names {bf!r} vs {ef!r} compatible")
    return False, (f"surname match rejected: first names "
                   f"{bf!r} vs {ef!r} incompatible")


def resolve_player(name, sport, teams=None):
    """Resolve a board name to (athlete_id, league_path, team,
    seasons) or (None, reason). Tries the documented name-form
    variants; a variant wins only when it yields exactly one
    athlete id after the league filter. Ambiguity across ALL
    variants stays unresolved \u2014 never a guess."""
    path, seasons, _tag = LEAGUES[sport]
    # Fast path = the Round-2 standard: the board string itself,
    # exact. Variants are searched only when the board form does
    # not resolve cleanly, and then ALL variants must agree on
    # one athlete id.
    direct = _search_hits(name, sport)
    direct_ids = {h["id"] for h in direct}
    if len(direct_ids) == 1:
        h = direct[0]
        return (h["id"], path, h["team"], seasons), \
            f"exact match on board form {name!r}"
    by_id = {h["id"]: h for h in direct}
    tried = [name] if direct else []
    for variant in name_variants(name):
        if variant == name:
            continue
        hits = _search_hits(variant, sport)
        if hits:
            tried.append(variant)
        for h in hits:
            by_id.setdefault(h["id"], h)
    if len(by_id) == 1:
        h = next(iter(by_id.values()))
        return (h["id"], path, h["team"], seasons), \
            f"exact match on form(s) {tried}"
    if len(by_id) > 1:
        # Team evidence: the market's own game names the two
        # teams. If exactly one candidate's ESPN team matches a
        # side, that is evidence, not a guess. If none match,
        # the board player is none of them \u2014 stay unresolved.
        if teams:
            want = {_norm_team(t) for t in teams}
            match = [h for h in by_id.values()
                     if _team_matches(_norm_team(h["team"]), want)]
            if len(match) == 1:
                h = match[0]
                return (h["id"], path, h["team"], seasons), \
                    (f"exact name ambiguous across "
                     f"{len(by_id)} athletes; team evidence "
                     f"({h['team']}) matches this market's game")
            return None, (f"ambiguous: {len(by_id)} distinct "
                          f"athlete ids across forms {tried}; "
                          f"team evidence matched "
                          f"{len(match)} of them "
                          f"(candidates: "
                          f"{[(h['id'], h['team'], h['desc']) for h in by_id.values()]}) "
                          f"\u2014 not guessed")
        return None, (f"ambiguous: {len(by_id)} distinct athlete "
                      f"ids across forms {tried} \u2014 not guessed")
    # Surname-unique fallback: FanDuel prints legal names where
    # ESPN lists the common form (Kenneth vs Kenny Gainwell).
    # Evidence standard: exactly ONE athlete in the league
    # family carries the surname — AND, since Round 5, the
    # first names must be COMPATIBLE (identical / curated
    # nickname pair / initial). A unique surname with an
    # incompatible first name is a different person who happens
    # to share a surname (Tiffany Hayes is not Jaxson Hayes;
    # Veronica Burton is not Tyler Burton): REJECTED, reason
    # recorded.
    surname = name.split()[-1].strip(".,")
    if len(surname) >= 4:
        cands = {}
        for c in _search_contents(surname):
            dn = c.get("displayName") or ""
            if dn.split()[-1].strip(".,") != surname:
                continue
            uid = c.get("uid", "")
            mm = re.match(r"s:(\d+)~l:(\d+)~a:(\d+)$", uid)
            if not mm:
                continue
            cands.setdefault(int(mm.group(3)), {
                "id": int(mm.group(3)),
                "league_id": int(mm.group(2)),
                "sport_id": int(mm.group(1)),
                "desc": c.get("description", ""),
                "team": c.get("subtitle", ""),
                "displayName": dn})
        cands = _family_filter(list(cands.values()), sport)
        if len(cands) == 1:
            h = cands[0]
            ok, why = _surname_guard(name, h["displayName"])
            if not ok:
                return None, (f"{why} — surname-unique "
                              f"candidate was ESPN "
                              f"{h['displayName']!r} (id "
                              f"{h['id']}, {h['team']}); board "
                              f"player {name!r} stays unresolved")
            return (h["id"], path, h["team"], seasons), \
                (f"surname-unique: ESPN lists "
                 f"{h['displayName']!r} \u2014 the only {surname} "
                 f"in the {sport} family; {why}")
    return None, (f"no exact ESPN displayName match in the "
                  f"{sport} family for any form of {name!r} "
                  f"(tried {name_variants(name)}); surname "
                  f"{surname!r} not unique in family either")


def gamelog_events(d):
    n = 0
    for st in d.get("seasonTypes", []):
        for cat in st.get("categories", []):
            if cat.get("type") == "event":
                n += len(cat.get("events", []))
    return n


def _fetch_log(aid, path, seasons):
    """Probe a gamelog across the lane's seasons. Returns
    (payload, events, season) for the best season found —
    the first season carrying >= 8 event rows, else the
    deepest log — or (None, 0, None) when every probed
    season is empty/unreachable. The house season rule,
    shared by the primary path and the Round-4 fallback so
    both judge 'empty' identically."""
    best = None
    for season in seasons:
        url = ("https://site.api.espn.com/apis/common/v3/sports/"
               f"{path}/athletes/{aid}/gamelog?season={season}")
        try:
            d = http_json(url)
        except Exception:
            continue
        nev = gamelog_events(d)
        if best is None or nev > best[1]:
            best = (d, nev, season)
        if nev >= 8:
            best = (d, nev, season)
            break
    if best is None:
        return None, 0, None
    return best


FALLBACK_SUFFIXES = ("Sr.", "Jr.", "II", "III")


def _suffix_forms(name):
    """Suffix-form variants of a board name: the base name
    (board suffix stripped, if any) re-attached with each
    generational suffix. The board form itself is excluded —
    the fallback exists for the forms NOT yet tried as the
    resolution."""
    base = name
    for suf in SUFFIXES:
        if base.endswith(" " + suf):
            base = base[:-(len(suf) + 1)].strip()
            break
    return base, [f"{base} {s}" for s in FALLBACK_SUFFIXES
                  if f"{base} {s}" != name]


def suffix_fallback(name, sport, exclude_ids=()):
    """Round 4: the exact match's log is empty — try the
    suffix forms of the same name in the same family.
    Returns one of:
      ("OK", hit, form, (payload, events, season)) —
        exactly one suffix variant carries a log;
      ("AMBIGUOUS", [(hit, form, events), ...]) — more
        than one variant carries a log: never guessed;
      (None, tried) — no variant carries a log."""
    path, seasons, _tag = LEAGUES[sport]
    _base, forms = _suffix_forms(name)
    tried, with_log = [], []
    seen_ids = set(exclude_ids)
    for form in forms:
        for h in _search_hits(form, sport):
            if h["id"] in seen_ids:
                continue
            seen_ids.add(h["id"])
            tried.append((form, h["id"]))
            d, nev, season = _fetch_log(h["id"], path, seasons)
            if nev > 0:
                with_log.append((h, form, (d, nev, season)))
    if len(with_log) == 1:
        h, form, best = with_log[0]
        return "OK", h, form, best
    if len(with_log) > 1:
        return "AMBIGUOUS", [(h, form, best[1])
                             for h, form, best in with_log]
    return None, tried


def _namesake_collisions(name, sport, resolved_id):
    """Other athletes in the same league family who share
    this player's base name — the exact displayName, or a
    suffix form of it (or the name is a suffix form of
    theirs). These are the collisions that make an exact
    match dangerous; the caller records them on the index
    entry. One surname-scoped search, family-filtered."""
    base, forms = _suffix_forms(name)
    kin = {base} | set(forms) | {name}
    out = []
    seen = {resolved_id}
    for c in _search_contents(base):
        dn = c.get("displayName") or ""
        if dn not in kin:
            continue
        uid = c.get("uid", "")
        mm = re.match(r"s:(\d+)~l:(\d+)~a:(\d+)$", uid)
        if not mm:
            continue
        hit = {"id": int(mm.group(3)),
               "league_id": int(mm.group(2)),
               "sport_id": int(mm.group(1)),
               "desc": c.get("description", ""),
               "team": c.get("subtitle", ""),
               "displayName": dn}
        if hit["id"] in seen:
            continue
        if _family_filter([hit], sport):
            seen.add(hit["id"])
            out.append(hit)
    return out


def strip_gamelog(d):
    """Stat rows only: the fields prop pricing reads (names +
    seasonTypes) plus display helpers and a compact
    eventId -> gameDate map (for the staleness report). The raw
    envelope (per-event links/metadata, filters, glossary,
    categories) is dropped. Pricing reads nothing else."""
    dates = {}
    for eid, ev in (d.get("events") or {}).items():
        if isinstance(ev, dict) and ev.get("gameDate"):
            dates[str(eid)] = ev["gameDate"]
    if not dates and d.get("event_dates"):
        dates = dict(d["event_dates"])
    return {"names": d.get("names") or [],
            "labels": d.get("labels") or [],
            "displayNames": d.get("displayNames") or [],
            "seasonTypes": d.get("seasonTypes") or [],
            "event_dates": dates,
            "stripped": "stat-rows-only (Round 3 cache weight)"}


def last_game_date(d):
    """Latest game date in a gamelog, stripped or full form."""
    dates = []
    if d.get("event_dates"):
        dates.extend(d["event_dates"].values())
    for ev in (d.get("events") or {}).values():
        if isinstance(ev, dict) and ev.get("gameDate"):
            dates.append(ev["gameDate"])
    return max(dates) if dates else None


STALE_DAYS = 10


def staleness_report(cache=CACHE, index_name="athlete_index.json"):
    """Per cached player: last game date in their log + age vs
    the 10-day line. Report only \u2014 no refetch machinery."""
    import datetime
    idx_path = os.path.join(cache, index_name)
    index = {}
    if os.path.exists(idx_path):
        with open(idx_path) as f:
            index = json.load(f)
    now = datetime.datetime.now(datetime.timezone.utc)
    rows, stale, nodate = [], 0, 0
    for name, ent in sorted(index.items()):
        path = os.path.join(cache, f"gamelog_{ent['id']}.json")
        if not os.path.exists(path):
            rows.append((name, None, None, "NO-FILE"))
            stale += 1
            continue
        with open(path) as f:
            d = json.load(f)
        last = last_game_date(d)
        if not last:
            rows.append((name, None, None, "NO-DATE"))
            nodate += 1
            continue
        try:
            dt = datetime.datetime.fromisoformat(
                last.replace("Z", "+00:00"))
        except ValueError:
            rows.append((name, last, None, "BAD-DATE"))
            nodate += 1
            continue
        age = (now - dt).days
        flag = "STALE" if age > STALE_DAYS else "fresh"
        if age > STALE_DAYS:
            stale += 1
        rows.append((name, last[:10], age, flag))
    print(f"STALENESS ({len(rows)} cached players, line = "
          f"{STALE_DAYS} days): {stale} stale, {nodate} no-date")
    for name, last, age, flag in rows:
        print(f"  {flag:7s} {name:28s} last game {last} "
              f"age {age if age is not None else '-'}d")
    return rows


def strip_cache(cache=CACHE):
    """Strip every gamelog_*.json in place; returns
    (n_files, bytes_before, bytes_after)."""
    import glob as _glob
    tot_b = tot_a = 0
    files = sorted(_glob.glob(os.path.join(cache, "gamelog_*.json")))
    for path in files:
        with open(path) as f:
            d = json.load(f)
        if d.get("stripped"):
            tot_b += os.path.getsize(path)
            tot_a += os.path.getsize(path)
            continue
        s = strip_gamelog(d)
        before = os.path.getsize(path)
        with open(path, "w") as f:
            json.dump(s, f)
        tot_b += before
        tot_a += os.path.getsize(path)
    return len(files), tot_b, tot_a


def fetch_one(name, sport, teams=None, known=None):
    """Resolve + fetch + cache one player. Returns a record.
    `known` = a prior athlete_index entry for this exact name:
    that entry IS a past exact resolution, so with a NON-EMPTY
    cache file present the player is CACHED without a new
    search. Round 4: an EMPTY cached log is never trusted —
    it is the namesake trap's fingerprint, so the player
    falls through to full resolution + the suffix fallback."""
    rec = {"player": name, "sport": sport}
    if known:
        cache_path = os.path.join(
            CACHE, f"gamelog_{known['id']}.json")
        if os.path.exists(cache_path):
            with open(cache_path) as f:
                d = json.load(f)
            if gamelog_events(d) > 0:
                rec.update({"id": known["id"],
                            "league_path":
                                known.get("league_path"),
                            "team_search": known.get("team"),
                            "season": known.get("season"),
                            "status": "CACHED",
                            "events": gamelog_events(d),
                            "resolve_note":
                                "athlete_index entry "
                                "(past exact resolution)"})
                if known.get("resolved_name"):
                    rec["resolved_name"] = \
                        known["resolved_name"]
                    rec["disambiguation"] = \
                        known.get("disambiguation")
                return rec
            rec["resolve_note"] = (
                "index entry's cached log is EMPTY "
                f"(id {known['id']}) — namesake-trap "
                "suspect; re-resolving with suffix fallback")
    got, why = resolve_player(name, sport, teams=teams)
    rec["resolve_note"] = (rec.get("resolve_note") + "; "
                          if rec.get("resolve_note") else "") \
        + why
    if got is None:
        rec["status"] = "UNRESOLVED"
        return rec
    aid, path, team, seasons = got
    rec.update({"id": aid, "team_search": team,
                "league_path": path})
    cache_path = os.path.join(CACHE, f"gamelog_{aid}.json")
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            d = json.load(f)
        if gamelog_events(d) > 0:
            rec.update({"status": "CACHED",
                        "events": gamelog_events(d)})
            rec["namesakes"] = _namesake_collisions(
                name, sport, aid)
            return rec
        # a zero-event cache file proves nothing — re-probe
    d, nev, season = _fetch_log(aid, path, seasons)
    if nev == 0:
        # ROUND 4 FALLBACK: the exact match may be a namesake
        # with no log while the board player carries a
        # suffix form. Try those forms before NO-GAMELOG.
        fb = suffix_fallback(name, sport, exclude_ids=(aid,))
        if fb[0] == "OK":
            _tag, h, form, (d2, nev2, season2) = fb
            rec["disambiguation"] = (
                "exact namesake empty-log; suffix variant "
                f"with log — board form {name!r} resolved to "
                f"id {aid} ({team}), empty across seasons "
                f"{seasons}; variant {form!r} is id {h['id']} "
                f"({h['team']}) with {nev2} events in "
                f"season {season2}")
            rec["resolved_name"] = form
            rec.update({"id": h["id"],
                        "team_search": h["team"]})
            cache_path = os.path.join(
                CACHE, f"gamelog_{h['id']}.json")
            if os.path.exists(cache_path):
                with open(cache_path) as f:
                    dc = json.load(f)
                if gamelog_events(dc) > 0:
                    rec.update({"status": "CACHED",
                                "events": gamelog_events(dc)})
                    rec["namesakes"] = \
                        _namesake_collisions(name, sport,
                                             h["id"])
                    return rec
            with open(cache_path, "w") as f:
                json.dump(strip_gamelog(d2), f)
            rec.update({"status": "FETCHED" if nev2 >= 8
                        else "THIN",
                        "events": nev2, "season": season2})
            rec["namesakes"] = _namesake_collisions(
                name, sport, h["id"])
            return rec
        if fb[0] == "AMBIGUOUS":
            rec["status"] = "UNRESOLVED"
            rec["resolve_note"] += (
                "; suffix fallback AMBIGUOUS — more than one "
                "suffix variant carries a log: "
                f"{[(h['id'], h['team'], ev) for h, _f, ev in fb[1]]}"
                " — not guessed")
            return rec
        rec["status"] = "NO-GAMELOG"
        rec["resolve_note"] += (
            f"; suffix fallback tried {fb[1]} — no variant "
            "carries a log either")
        return rec
    with open(cache_path, "w") as f:
        json.dump(strip_gamelog(d), f)
    rec.update({"status": "FETCHED" if nev >= 8 else "THIN",
                "events": nev, "season": season})
    rec["namesakes"] = _namesake_collisions(name, sport, aid)
    return rec


def fetch_all(harvest_path, max_players=None):
    with open(harvest_path) as f:
        hv = json.load(f)
    by_player = {}
    teams_of = {}
    for m in hv["player_markets"]:
        by_player.setdefault((m["player"], m["sport"]), 0)
        by_player[(m["player"], m["sport"])] += 1
        teams_of.setdefault((m["player"], m["sport"]), set()).update(
            t for t in (m.get("home"), m.get("away")) if t)
    ranked = sorted(by_player.items(), key=lambda kv: -kv[1])
    cap = len(ranked) if max_players is None else max_players
    print(f"unique players on the board: {len(ranked)}; "
          f"attempting {min(cap, len(ranked))}")
    idx_path = os.path.join(CACHE, "athlete_index.json")
    index = {}
    if os.path.exists(idx_path):
        with open(idx_path) as f:
            index = json.load(f)
    # Board team strings arrive as codes in the NFL/NBA pulls
    # ('MIN', 'IND'). Expand each code to its full name via the
    # engine's own FD maps so team-evidence matching compares
    # like with like.
    try:
        import betmodel5 as _b5
        _code2name = {}
        for _mp in (getattr(_b5, "FD_NFL_TEAM_CODES", {}),
                    getattr(_b5, "FD_NBA_TEAM_CODES", {})):
            for _full, _code in _mp.items():
                _code2name[_code] = _full
    except Exception:
        _code2name = {}

    def expand_teams(ts):
        out = set(ts)
        for t in ts:
            if t in _code2name:
                out.add(_code2name[t])
        return sorted(out)

    results = []
    for (name, sport), n_mk in ranked[:cap]:
        rec = fetch_one(name, sport,
                        teams=expand_teams(
                            teams_of.get((name, sport), ())),
                        known=index.get(name))
        rec["markets"] = n_mk
        results.append(rec)
        if rec.get("status") in ("FETCHED", "CACHED", "THIN"):
            entry = {"id": rec["id"],
                     "league_path": rec["league_path"],
                     "season": rec.get("season"),
                     "team": rec.get("team_search"),
                     "sport": sport,
                     "events": rec.get("events"),
                     "status": rec["status"]}
            # Round 4 audit fields: a disambiguated or
            # collision-prone resolution is recorded ON THE
            # ENTRY, never left in a log line. Cached re-runs
            # carry prior fields forward.
            prior = index.get(name) or {}
            if rec.get("resolved_name"):
                entry["board_name"] = name
                entry["resolved_name"] = rec["resolved_name"]
                entry["disambiguation"] = \
                    rec.get("disambiguation")
            elif prior.get("resolved_name"):
                entry["board_name"] = prior.get("board_name",
                                                name)
                entry["resolved_name"] = \
                    prior["resolved_name"]
                entry["disambiguation"] = \
                    prior.get("disambiguation")
            namesakes = rec.get("namesakes")
            if namesakes:
                entry["namesake_collision_risk"] = True
                entry["namesakes"] = [
                    {"id": h["id"],
                     "displayName": h["displayName"],
                     "team": h["team"]} for h in namesakes]
            elif prior.get("namesake_collision_risk"):
                entry["namesake_collision_risk"] = True
                entry["namesakes"] = prior.get("namesakes")
            index[name] = entry
        print(f"  {name} ({sport}, {n_mk} mkts): "
              f"{rec['status']}"
              + (f" id={rec.get('id')} events={rec.get('events')}"
                 f" season={rec.get('season')}"
                 if "id" in rec else
                 f" \u2014 {rec.get('resolve_note', '')}")
              + (f" [DISAMBIGUATED: {rec['disambiguation']}]"
                 if rec.get("disambiguation") else ""))
    with open(idx_path, "w") as f:
        json.dump(index, f, indent=1)
    got = [r for r in results
           if r["status"] in ("FETCHED", "CACHED", "THIN")]
    bad = [r for r in results
           if r["status"] not in ("FETCHED", "CACHED", "THIN")]
    print(f"resolved+cached: {len(got)}; unresolved/failed: "
          f"{len(bad)} -> {[r['player'] for r in bad[:15]]}")
    return results


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "harvest":
        mg = int(os.environ.get("MAX_GAMES", "0")) or None
        harvest(sys.argv[2], sys.argv[3], max_games=mg)
    elif cmd == "fetch":
        mp_env = os.environ.get("MAX_PLAYERS")
        mp = int(mp_env) if mp_env else None
        fetch_all(sys.argv[2], max_players=mp)
    elif cmd == "strip":
        n, b, a = strip_cache()
        print(f"stripped {n} gamelog files: {b} -> {a} bytes "
              f"({b - a} saved)")
    elif cmd == "staleness":
        staleness_report()
