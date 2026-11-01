"""Pull-history store for BetFi's 3D fulfillment (app module).

Design law: the 3D-fulfillment scaffold folder in the lab
(README.md, SPEC.md, DATA-CONTRACT.md) — DATA-CONTRACT.md is
canonical for shapes, including its 2026-10-31 amendments
(convergent compaction; one single-market daily record per
(day, key); load_window returns header + "records").

This is the scaffold's history_store.py ported into the app
as a bundled module, extended with the remaining graph shapes
(G2/G3/G5/G6/G7/G8 + the G4 gate) and the recorder entry
points main.py calls (record_pull / has_pull /
history_begins). The scaffold core — shape_record,
shape_edge_terrain, append_pull, compact, load_window — is
carried over unchanged in behaviour.

Stdlib only, and deliberately STANDALONE: no import of the
app engine (betmodel5). The implied-probability math is
duplicated locally on purpose — this module must be
unit-drivable offline and shippable as a bundled module
without dragging the engine behind it.

Store layout under `store_dir`:
    pull-history/YYYY-MM.jsonl   one JSON object per record,
                                 the file named by the record's
                                 own pulled_at month (Detroit).

Record (one landed pull, grain "pull"):
    {"pulled_at": iso-with-offset, "scopes": [sport, ...],
     "grain": "pull",
     "markets": [{"key", "sport", "fd_event_id", "fd_market_id",
                  "fd_selection_id", "market", "side", "line",
                  "price", "p", "edge_pts", "rung", "grade",
                  "metal"}, ...]}
Priced AND unpriced markets are recorded (the unpriced
denominator feeds coverage-over-time); unpriced entries carry
their price and null p/edge_pts/rung/grade/metal.

Compaction (daily grain): records OLDER than 30 days fold per
(calendar day America/Detroit, market key): the day's LAST
pull containing that key survives as one record per market —
{"pulled_at": that pull's stamp, "scopes": [the entry's
sport], "grain": "day", "markets": [the winning entry]}.
Raw records <= 30 days old are never compacted. Compaction
is idempotent and convergent: existing daily records re-enter
the per-(day, key) winner selection, so the day's true last
pull survives any number of folds.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DETROIT = ZoneInfo("America/Detroit")
HISTORY_DIRNAME = "pull-history"
COMPACT_AGE_DAYS = 30
EDGE_TERRAIN_CAP = 200
RIVERS_CAP = 24
RIVER_EVENTS_CAP = 50
DRIFT_CAP = 1500
CORRELATION_CAP = 60
WINDOWS = ("live", "month", "season")

# Season table (DATA-CONTRACT, stamped 2026-10-31; an edit is
# a code change with a dated note, never a silent drift).
# Month/day each sport's season starts. Sports absent here
# have no season — their ALL SEASON window reads calendar
# year to date and labels itself that way.
SEASON_STARTS = {
    "nfl": (9, 1), "ncaaf": (8, 20), "nba": (10, 1),
    "nhl": (10, 1), "mlb": (3, 20), "soccer": (8, 1),
    "wnba": (5, 1),
}


# ------------------------------------------------------------------
# primitives
# ------------------------------------------------------------------

def implied_prob(price):
    """American odds -> implied probability (the market's own
    number, vig included — the same primitive the app uses,
    duplicated here so this module stands alone). None when
    the price is missing or 0 (no such American price)."""
    if price is None:
        return None
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None
    if price == 0:
        return None
    if price < 0:
        return -price / (-price + 100.0)
    return 100.0 / (price + 100.0)


def _parse_ts(stamp):
    """ISO stamp -> aware datetime. Naive stamps are read as
    Detroit local (the contract's stamps always carry an
    offset; this is only a defensive read)."""
    dt = datetime.fromisoformat(stamp)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=DETROIT)
    return dt


def market_key(mkt):
    """The contract key: sport|fd_event_id|market|side|line.
    Line rides in the key (a moved spread is a different bet);
    a missing line renders as the empty final field, exactly
    as the contract's example ("nfl|36236119|moneyline|home|").
    """
    line = mkt.get("line")
    line_s = "" if line is None else str(line)
    return "|".join([str(mkt.get("sport")),
                     str(mkt.get("fd_event_id")),
                     str(mkt.get("market")),
                     str(mkt.get("side")),
                     line_s])


def _label(e):
    return "{} {} {}".format(e.get("sport"), e.get("market"),
                             e.get("side"))


# ------------------------------------------------------------------
# shaping (pure)
# ------------------------------------------------------------------

def shape_record(rec, verdicts):
    """One landed pull -> one contract pull record. PURE.

    rec: the app's snapshot shape — {pulled_at, markets,
    sports, ...}; each market carries fd_event_id /
    fd_market_id / fd_selection_id / market / side / line /
    price and its sport. verdicts: the verdict list aligned
    BY INDEX with rec["markets"] (the app's convention); an
    entry may be None (no verdict computed for that market)
    and the list may be short/absent — verdict fields then
    ride as nulls. Verdict fields read: p, verdict (-> rung),
    grade, metal.

    edge_pts is computed HERE, never copied from the verdict:
    (p - implied_prob(price)) * 100 when both exist, rounded
    to 3 decimals (the contract's printed precision).

    scopes = the sorted sports present among the markets;
    with no markets at all, the rec's own sports table keys.
    """
    markets_in = rec.get("markets") or []
    verdicts = verdicts or []
    out_markets = []
    sports_present = set()
    for i, m in enumerate(markets_in):
        v = verdicts[i] if i < len(verdicts) else None
        p = v.get("p") if isinstance(v, dict) else None
        price = m.get("price")
        q = implied_prob(price)
        edge = None
        if p is not None and q is not None:
            edge = round((p - q) * 100.0, 3)
        sport = m.get("sport")
        if sport:
            sports_present.add(sport)
        out_markets.append({
            "key": market_key(m),
            "sport": sport,
            "fd_event_id": m.get("fd_event_id"),
            "fd_market_id": m.get("fd_market_id"),
            "fd_selection_id": m.get("fd_selection_id"),
            "market": m.get("market"),
            "side": m.get("side"),
            "line": m.get("line"),
            "price": price,
            "p": p,
            "edge_pts": edge,
            "rung": (v.get("verdict") if isinstance(v, dict)
                     else None),
            "grade": (v.get("grade") if isinstance(v, dict)
                      else None),
            "metal": (v.get("metal") if isinstance(v, dict)
                      else None),
        })
    if sports_present:
        scopes = sorted(sports_present)
    else:
        scopes = sorted((rec.get("sports") or {}).keys())
    return {"pulled_at": rec.get("pulled_at"),
            "scopes": scopes,
            "grain": "pull",
            "markets": out_markets}


def shape_edge_terrain(records):
    """G1 EDGE TERRAIN payload. PURE: records in, payload out.

    One path per market key with >= 2 PRICED points across the
    records (priced = the entry carries both a model p and a
    quoted price, so p_implied exists). Points are
    [t_epoch, p_model, p_implied], sorted by time. Label is
    "<sport> <market> <side>" from the key's latest entry.
    Paths are capped at the EDGE_TERRAIN_CAP longest (ties
    broken by key, so the cut is deterministic); the payload
    states the cap and both counts — a cut is never silent.
    """
    by_key = {}
    for rec in records or []:
        stamp = rec.get("pulled_at")
        if not stamp:
            continue
        t = _parse_ts(stamp).timestamp()
        for e in rec.get("markets") or []:
            p = e.get("p")
            q = implied_prob(e.get("price"))
            if p is None or q is None:
                continue
            slot = by_key.setdefault(
                e.get("key"),
                {"key": e.get("key"), "points": [],
                 "label": None})
            slot["points"].append([t, p, q])
            slot["label"] = _label(e)
    paths = []
    for slot in by_key.values():
        if len(slot["points"]) >= 2:
            slot["points"].sort(key=lambda pt: pt[0])
            paths.append(slot)
    total = len(paths)
    paths.sort(key=lambda s: (-len(s["points"]), s["key"] or ""))
    paths = paths[:EDGE_TERRAIN_CAP]
    return {"paths": paths,
            "diagonal": True,
            "cap": EDGE_TERRAIN_CAP,
            "paths_total": total,
            "paths_returned": len(paths)}


def shape_price_rivers(records, event_id=None):
    """G2 PRICE RIVERS payload. PURE.

    One game's market complex breathing together: a ribbon
    per market key of ONE event, points [t_epoch, price,
    edge_pts] (edge null where the market was unpriced on
    that pull — the ribbon is the PRICE's path; the edge
    rides where it exists). The event is chosen by the
    caller (fd_event_id, compared as a string) or defaults
    to the event with the most priced points in the window
    (ties: smallest event id — deterministic). The payload
    carries an "events" index (capped, stated) so the page
    can offer the other games. Ribbons are capped at the
    RIVERS_CAP longest, stated both ways like G1.
    """
    events = {}
    for rec in records or []:
        stamp = rec.get("pulled_at")
        if not stamp:
            continue
        t = _parse_ts(stamp).timestamp()
        for e in rec.get("markets") or []:
            eid = e.get("fd_event_id")
            if eid is None:
                continue
            slot = events.setdefault(
                str(eid),
                {"fd_event_id": eid, "sport": e.get("sport"),
                 "priced_points": 0, "pulls": set(),
                 "ribbons": {}})
            rk = e.get("key")
            rib = slot["ribbons"].setdefault(
                rk, {"key": rk, "label": _label(e),
                     "market": e.get("market"),
                     "side": e.get("side"),
                     "line": e.get("line"), "points": []})
            if e.get("price") is not None:
                rib["points"].append(
                    [t, e.get("price"), e.get("edge_pts")])
                slot["pulls"].add(stamp)
                if e.get("p") is not None:
                    slot["priced_points"] += 1
    summaries = []
    for slot in events.values():
        summaries.append({
            "fd_event_id": slot["fd_event_id"],
            "sport": slot["sport"],
            "priced_points": slot["priced_points"],
            "pulls": len(slot["pulls"]),
            "ribbons": len(slot["ribbons"])})
    summaries.sort(key=lambda s: (-s["priced_points"],
                                  str(s["fd_event_id"])))
    chosen = None
    if event_id is not None:
        # an explicit ask is honoured exactly or not at all —
        # an event outside the window yields no ribbons and a
        # null event, never a silent substitute game
        chosen = events.get(str(event_id))
    elif summaries:
        chosen = events[str(summaries[0]["fd_event_id"])]
    ribbons = []
    if chosen is not None:
        for rib in chosen["ribbons"].values():
            if len(rib["points"]) >= 2:
                rib["points"].sort(key=lambda pt: pt[0])
                ribbons.append(rib)
    total_r = len(ribbons)
    ribbons.sort(key=lambda r: (-len(r["points"]),
                                r["key"] or ""))
    ribbons = ribbons[:RIVERS_CAP]
    chosen_sum = None
    if chosen is not None:
        chosen_sum = next(
            s for s in summaries
            if str(s["fd_event_id"]) == str(chosen["fd_event_id"]))
    return {"event": chosen_sum,
            "events": summaries[:RIVER_EVENTS_CAP],
            "events_total": len(summaries),
            "events_cap": RIVER_EVENTS_CAP,
            "ribbons": ribbons,
            "cap": RIVERS_CAP,
            "ribbons_total": total_r,
            "ribbons_returned": len(ribbons)}


def shape_drift_field(records):
    """G3 DRIFT FIELD payload. PURE.

    Consecutive record pairs per market key: one point per
    step, x = the price's move in implied points, y = the
    model p's move in points, z = the later record's index
    in the window (pull index). Coloured by lane (sport) on
    the page — where the book systematically re-prices
    toward a lane's model (points along +x/+y together) or
    fades it. Only steps where both records priced the key
    with a quoted price count. Over the cap, the LARGEST
    moves are kept (ties by key then z — deterministic);
    the payload states the rule and both counts.
    """
    seqs = {}
    for idx, rec in enumerate(records or []):
        for e in rec.get("markets") or []:
            p = e.get("p")
            q = implied_prob(e.get("price"))
            if p is None or q is None:
                continue
            seqs.setdefault(e.get("key"), []).append(
                (idx, p, q, e.get("sport"), e.get("market")))
    points = []
    for key, seq in seqs.items():
        for a, b in zip(seq, seq[1:]):
            points.append({
                "key": key,
                "x": round((b[2] - a[2]) * 100.0, 3),
                "y": round((b[1] - a[1]) * 100.0, 3),
                "z": b[0],
                "sport": b[3], "market": b[4]})
    total = len(points)
    if total > DRIFT_CAP:
        points.sort(key=lambda pt: (-(abs(pt["x"])
                                      + abs(pt["y"])),
                                    pt["key"] or "", pt["z"]))
        points = points[:DRIFT_CAP]
    lanes = sorted({pt["sport"] for pt in points if pt["sport"]})
    return {"points": points,
            "lanes": lanes,
            "cap": DRIFT_CAP,
            "cap_rule": "largest moves kept",
            "points_total": total,
            "points_returned": len(points),
            "pulls": len(records or [])}


def shape_coverage_topography(records):
    """G6 COVERAGE TOPOGRAPHY payload. PURE.

    One cell per (sport, record): x sport, y time, z priced
    share (height), mean priced edge rides for colour. The
    unpriced denominator is why records keep unpriced
    markets. Sports are ordered by their best share (the
    pricing frontier first), ties by name — deterministic.
    """
    cells = []
    sports_best = {}
    for rec in records or []:
        stamp = rec.get("pulled_at")
        if not stamp:
            continue
        t = _parse_ts(stamp).timestamp()
        by_sport = {}
        for e in rec.get("markets") or []:
            s = e.get("sport")
            if not s:
                continue
            slot = by_sport.setdefault(
                s, {"n": 0, "priced": 0, "edges": []})
            slot["n"] += 1
            if e.get("p") is not None:
                slot["priced"] += 1
                if e.get("edge_pts") is not None:
                    slot["edges"].append(e["edge_pts"])
        for s, slot in by_sport.items():
            share = (slot["priced"] / slot["n"]
                     if slot["n"] else 0.0)
            mean_edge = (round(sum(slot["edges"])
                               / len(slot["edges"]), 3)
                         if slot["edges"] else None)
            cells.append({"sport": s, "t": t, "stamp": stamp,
                          "share": round(share, 4),
                          "mean_edge": mean_edge,
                          "n": slot["n"],
                          "priced": slot["priced"]})
            if share > sports_best.get(s, -1.0):
                sports_best[s] = share
    sports = sorted(sports_best,
                    key=lambda s: (-sports_best[s], s))
    cells.sort(key=lambda c: (c["t"], c["sport"]))
    return {"sports": sports, "cells": cells,
            "cells_total": len(cells)}


def shape_correlation_space(records):
    """G5 CORRELATION SPACE (live) payload. PURE.

    Same-game clusters across today's pulls: one trail per
    event with >= 2 pulls carrying >= 2 priced markets.
    A trail point is [t_epoch, mean |edge| of the game's
    priced markets, edge dispersion (max - min edge)] —
    clusters tightening as kickoff approaches show as the
    dispersion falling along the trail. Event labels (team
    names) live in the current slate, not the record; the
    page joins them from /api/slate.json. Trails capped at
    the CORRELATION_CAP richest (most points, then most
    markets), stated both ways.
    """
    per_event = {}
    for rec in records or []:
        stamp = rec.get("pulled_at")
        if not stamp:
            continue
        t = _parse_ts(stamp).timestamp()
        by_event = {}
        for e in rec.get("markets") or []:
            eid = e.get("fd_event_id")
            if eid is None or e.get("edge_pts") is None:
                continue
            by_event.setdefault(eid, []).append(e["edge_pts"])
        for eid, edges in by_event.items():
            if len(edges) < 2:
                continue
            slot = per_event.setdefault(
                str(eid), {"fd_event_id": eid, "sport": None,
                           "points": [], "n_max": 0})
            slot["sport"] = next(
                (e.get("sport") for e in rec.get("markets") or []
                 if e.get("fd_event_id") == eid), slot["sport"])
            slot["points"].append([
                t,
                round(sum(abs(x) for x in edges) / len(edges), 3),
                round(max(edges) - min(edges), 3),
                len(edges)])
            slot["n_max"] = max(slot["n_max"], len(edges))
    trails = []
    for slot in per_event.values():
        if len(slot["points"]) >= 2:
            slot["points"].sort(key=lambda pt: pt[0])
            trails.append(slot)
    total = len(trails)
    trails.sort(key=lambda s: (-len(s["points"]), -s["n_max"],
                               str(s["fd_event_id"])))
    trails = trails[:CORRELATION_CAP]
    return {"trails": trails,
            "cap": CORRELATION_CAP,
            "trails_total": total,
            "trails_returned": len(trails)}


def shape_clv_surface(records):
    """G8 CLV SURFACE — price side. PURE.

    Per lane (sport + market) per ISO week (Detroit): the
    mean closing-line movement of the lane's markets, in
    implied points — for each key, implied(last sighting)
    minus implied(first sighting) inside the window, grouped
    by the week of the last sighting. Positive ground is
    prices that shortened into their last sighting. This is
    the price-side surface only: settled CLV (the model's
    picks against the close, graded on outcomes) needs the
    settled-results join and ships in the payload as its
    named gate, never as a series.
    """
    seqs = {}
    for rec in records or []:
        stamp = rec.get("pulled_at")
        if not stamp:
            continue
        t = _parse_ts(stamp).timestamp()
        for e in rec.get("markets") or []:
            q = implied_prob(e.get("price"))
            if q is None:
                continue
            seqs.setdefault(e.get("key"), []).append(
                (t, q, e.get("sport"), e.get("market")))
    groups = {}
    for key, seq in seqs.items():
        if len(seq) < 2:
            continue
        seq.sort(key=lambda pt: pt[0])
        first, last = seq[0], seq[-1]
        if last[0] <= first[0]:
            continue
        day = datetime.fromtimestamp(last[0],
                                     tz=DETROIT).date()
        iso = day.isocalendar()
        week = "{}-W{:02d}".format(iso[0], iso[1])
        lane = "{} {}".format(last[2], last[3])
        move = round((last[1] - first[1]) * 100.0, 3)
        groups.setdefault((lane, week), []).append(move)
    cells = []
    for (lane, week), moves in groups.items():
        cells.append({"lane": lane, "week": week,
                      "mean_move_pts": round(
                          sum(moves) / len(moves), 3),
                      "n": len(moves)})
    cells.sort(key=lambda c: (c["lane"], c["week"]))
    return {"cells": cells,
            "lanes": sorted({c["lane"] for c in cells}),
            "weeks": sorted({c["week"] for c in cells}),
            "settled": {
                "gate": "UNBUILT-DATA",
                "missing": "settled CLV needs outcomes joined "
                           "per market (the settled-results "
                           "join) — the same missing join as "
                           "G4. Price-side movement above is "
                           "all that is drawn until it exists."}}


def shape_calibration_volume(records):
    """G4 CALIBRATION VOLUME — the gate. PURE.

    Pull records carry no outcomes, so no calibration
    surface can be drawn from them — by law this shape
    returns the UNBUILT-DATA gate naming the missing join
    instead of a series. When a results join lands (settled
    outcomes per market key riding the record), this is the
    function that grows the real surface.
    """
    return {"gate": "UNBUILT-DATA",
            "missing": "settled outcomes joined per market "
                       "key — a results join. The engine's "
                       "scored lane records cover lanes, not "
                       "every market; until outcomes join the "
                       "pull record, predicted-vs-realized has "
                       "no realized side to draw.",
            "records_seen": len(records or [])}


def shape_team_trajectories(records):
    """G7 TEAM-STRENGTH TRAJECTORIES. PURE.

    Feed: per-pull pool snapshots (attack / defense /
    rating per team) — the surface reads a record's "pools"
    block ({"<sport>": {"<team>": {"attack": x, "defense":
    y, "rating": z}}}) when records carry one. The pull
    record as contracted (DATA-CONTRACT) carries neither
    team identity nor pool stamps, so until pool stamps
    join the record this shape returns the gate naming the
    missing input; with pools present it draws the paths
    and says plainly when the pool history is still thin.
    """
    paths = {}
    pools_seen = 0
    for rec in records or []:
        pools = rec.get("pools")
        if not isinstance(pools, dict) or not pools:
            continue
        pools_seen += 1
        stamp = rec.get("pulled_at")
        if not stamp:
            continue
        t = _parse_ts(stamp).timestamp()
        for sport, teams in pools.items():
            if not isinstance(teams, dict):
                continue
            for team, vals in teams.items():
                if not isinstance(vals, dict):
                    continue
                a, d, r = (vals.get("attack"),
                           vals.get("defense"),
                           vals.get("rating"))
                if a is None or d is None or r is None:
                    continue
                slot = paths.setdefault(
                    "{}|{}".format(sport, team),
                    {"sport": sport, "team": team, "points": []})
                slot["points"].append([t, a, d, r])
    out = []
    for slot in paths.values():
        if len(slot["points"]) >= 2:
            slot["points"].sort(key=lambda pt: pt[0])
            out.append(slot)
    out.sort(key=lambda s: (s["sport"], s["team"]))
    if not out:
        return {"gate": "UNBUILT-DATA",
                "missing": "team identity and pool snapshots "
                           "(attack / defense / rating per "
                           "team per pull) — the pull record "
                           "carries neither team names nor "
                           "pool stamps, so no team path can "
                           "be drawn from the archive yet. "
                           "When pool stamps join the record, "
                           "this surface draws from them.",
                "records_seen": len(records or []),
                "pools_seen": pools_seen}
    return {"paths": out,
            "pools_seen": pools_seen,
            "thin": pools_seen < 10,
            "thin_note": ("pool history is young — {} pooled "
                          "pull(s) on file; paths lengthen "
                          "with every pooled pull."
                          .format(pools_seen))
            if pools_seen < 10 else ""}


GRAPH_SHAPES = {
    "g1-edge-terrain": shape_edge_terrain,
    "g2-price-rivers": shape_price_rivers,
    "g3-drift-field": shape_drift_field,
    "g4-calibration-volume": shape_calibration_volume,
    "g5-correlation-space": shape_correlation_space,
    "g6-coverage-topography": shape_coverage_topography,
    "g7-team-trajectories": shape_team_trajectories,
    "g8-clv-surface": shape_clv_surface,
}


def shape_for(graph, records, event_id=None):
    """Dispatch one graph id to its pure shape function.
    Raises ValueError("unknown_graph") for an unlisted id —
    the server turns it into the named JSON error."""
    fn = GRAPH_SHAPES.get(graph)
    if fn is None:
        raise ValueError("unknown_graph")
    if graph == "g2-price-rivers":
        return fn(records, event_id)
    return fn(records)


# ------------------------------------------------------------------
# store I/O
# ------------------------------------------------------------------

def _history_dir(store_dir):
    return os.path.join(store_dir, HISTORY_DIRNAME)


def _month_name(dt):
    return dt.strftime("%Y-%m")


def _month_files(store_dir):
    hdir = _history_dir(store_dir)
    if not os.path.isdir(hdir):
        return []
    return sorted(os.path.join(hdir, f)
                  for f in os.listdir(hdir)
                  if f.endswith(".jsonl"))


def _read_records(store_dir):
    """Every record on file, sorted by pulled_at. Malformed
    lines are skipped (a torn final write must not poison the
    whole archive); records without a pulled_at are dropped
    for the same reason."""
    out = []
    for path in _month_files(store_dir):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("pulled_at"):
                    out.append(rec)
    out.sort(key=lambda r: _parse_ts(r["pulled_at"]))
    return out


def _write_month_file(store_dir, month, records):
    hdir = _history_dir(store_dir)
    os.makedirs(hdir, exist_ok=True)
    path = os.path.join(hdir, month + ".jsonl")
    records = sorted(records,
                     key=lambda r: _parse_ts(r["pulled_at"]))
    if not records:
        if os.path.exists(path):
            os.remove(path)
        return
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, separators=(",", ":")))
            fh.write("\n")


def append_pull(store_dir, record):
    """Append one pull record to its month file, then run the
    compaction check (SPEC: compaction runs on append — here
    concretely: if any grain-"pull" record on file is older
    than the compaction age, fold it). Returns the path
    written. The record is stored as given — shape_record is
    the caller's step (build plan step 1)."""
    stamp = _parse_ts(record["pulled_at"])
    hdir = _history_dir(store_dir)
    os.makedirs(hdir, exist_ok=True)
    path = os.path.join(hdir, _month_name(stamp) + ".jsonl")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, separators=(",", ":")))
        fh.write("\n")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=COMPACT_AGE_DAYS)
    for rec in _read_records(store_dir):
        if rec.get("grain") == "pull" and \
                _parse_ts(rec["pulled_at"]) < cutoff:
            compact(store_dir, now)
            break
    return path


def has_pull(store_dir, pulled_at):
    """The market count of the record already on file for
    `pulled_at`, or None when that stamp was never recorded.
    Reads only the stamp's own month file (the recorder's
    cheap dedupe probe)."""
    try:
        stamp = _parse_ts(pulled_at)
    except Exception:
        return None
    path = os.path.join(_history_dir(store_dir),
                        _month_name(stamp) + ".jsonl")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) \
                    and rec.get("pulled_at") == pulled_at:
                return len(rec.get("markets") or [])
    return None


def record_pull(store_dir, rec, verdicts):
    """Shape one landed pull and append it — the recorder's
    entry point (build plan step 1). A pull records ONCE:
    when a record with the same pulled_at and the same
    market count is already on file, this is a duplicate
    (a merge re-saving an already-recorded slate) and
    nothing is appended — history is never rewritten by a
    later save of the same pull. Returns {"status":
    "recorded", "path", "markets"} or {"status":
    "duplicate"}. Raises on a stamp-less rec — the caller
    (main.py) catches and stamps the Lab health line."""
    shaped = shape_record(rec, verdicts)
    stamp = shaped.get("pulled_at")
    if not stamp:
        raise ValueError("pull record carries no pulled_at")
    existing = has_pull(store_dir, stamp)
    if existing is not None \
            and existing == len(shaped["markets"]):
        return {"status": "duplicate", "markets": existing}
    path = append_pull(store_dir, shaped)
    return {"status": "recorded", "path": path,
            "markets": len(shaped["markets"])}


def history_begins(store_dir):
    """The archive's birth stamp, read cheaply: the earliest
    pulled_at in the earliest month file. None when the
    store is empty. Every history surface prints this —
    on-device history begins the recorder's ship date and
    says so."""
    files = _month_files(store_dir)
    if not files:
        return None
    best = None
    with open(files[0], encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            stamp = rec.get("pulled_at") if isinstance(
                rec, dict) else None
            if stamp and (best is None or stamp < best):
                best = stamp
    return best


def compact(store_dir, now):
    """Fold records older than COMPACT_AGE_DAYS (vs `now`)
    into daily grain, per (Detroit day, market key): the
    day's last pull containing the key survives as a
    single-market grain-"day" record stamped with that pull's
    own pulled_at — the contract's wording is literal here,
    so a folded market keeps its true last-seen time, never
    the day's end. Fresh records pass through untouched.
    Existing grain-"day" records RE-ENTER the winner
    selection for their (day, key): compaction is convergent,
    so a fold triggered between two same-day appends can
    never leave an earlier pull of that day standing beside
    the later one — the day's true last pull wins no matter
    how many times compaction runs. Month files are
    rewritten (a daily record stays in its pulled_at month).
    Idempotent. Returns {"folded_records": grain-"pull"
    records consumed, "daily_records": daily records
    emitted} for the folded scope (zeros when nothing old)."""
    if isinstance(now, str):
        now = _parse_ts(now)
    cutoff = now - timedelta(days=COMPACT_AGE_DAYS)
    records = _read_records(store_dir)
    fresh, old = [], []
    for rec in records:
        if _parse_ts(rec["pulled_at"]) < cutoff:
            old.append(rec)
        else:
            fresh.append(rec)
    folded_in = 0
    winners = {}  # (day, key) -> (pulled_dt, record, entry)
    for rec in old:
        if rec.get("grain") == "pull":
            folded_in += 1
        dt = _parse_ts(rec["pulled_at"])
        day = dt.astimezone(DETROIT).date().isoformat()
        for e in rec.get("markets") or []:
            k = (day, e.get("key"))
            # records arrive sorted by pulled_at; the >= also
            # lets an existing daily record defend its win
            # against an earlier same-day pull folded later.
            cur = winners.get(k)
            if cur is None or dt >= cur[0]:
                winners[k] = (dt, rec, e)
    daily = []
    for (day, _key), (_dt, rec, e) in winners.items():
        daily.append({"pulled_at": rec["pulled_at"],
                      "scopes": [e.get("sport")],
                      "grain": "day",
                      "markets": [e]})
    keep = fresh + daily
    by_month = {}
    for rec in keep:
        month = _month_name(_parse_ts(rec["pulled_at"]))
        by_month.setdefault(month, []).append(rec)
    for path in _month_files(store_dir):
        month = os.path.basename(path)[:-len(".jsonl")]
        _write_month_file(store_dir, month,
                          by_month.pop(month, []))
    for month, recs in by_month.items():
        _write_month_file(store_dir, month, recs)
    return {"folded_records": folded_in,
            "daily_records": len(daily)}


def load_window(store_dir, window, now):
    """Records for one window + the payload header.

    window: "live" (today, America/Detroit), "month" (rolling
    30 days back from `now`), "season" (everything on file —
    daily grain and raw alike; season-table filtering is the
    caller's concern per the contract). `now` is an aware
    datetime (or ISO string).

    Returns {"window", "grain", "from", "to",
    "history_begins", "records"}: grain is "pull"/"day" when
    the returned records are uniform, "mixed" when both ride
    (the DATA-CONTRACT payload spelling), "pull" when empty.
    from/to span the RETURNED records; history_begins spans
    the WHOLE store — it is the archive's birth date, not the
    window's edge, and every history surface prints it.
    An empty store yields records [] and null stamps.
    """
    if window not in WINDOWS:
        raise ValueError("unknown window: {!r} (want one of {})"
                         .format(window, ", ".join(WINDOWS)))
    if isinstance(now, str):
        now = _parse_ts(now)
    all_records = _read_records(store_dir)
    history_begins = (all_records[0]["pulled_at"]
                      if all_records else None)
    if window == "live":
        today = now.astimezone(DETROIT).date()
        sel = [r for r in all_records
               if _parse_ts(r["pulled_at"])
               .astimezone(DETROIT).date() == today]
    elif window == "month":
        cutoff = now - timedelta(days=30)
        sel = [r for r in all_records
               if _parse_ts(r["pulled_at"]) >= cutoff]
    else:  # season
        sel = list(all_records)
    grains = {r.get("grain") for r in sel}
    if len(grains) > 1:
        grain = "mixed"
    elif grains:
        grain = next(iter(grains))
    else:
        grain = "pull"
    return {"window": window,
            "grain": grain,
            "from": sel[0]["pulled_at"] if sel else None,
            "to": sel[-1]["pulled_at"] if sel else None,
            "history_begins": history_begins,
            "records": sel}
