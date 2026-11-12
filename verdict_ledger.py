"""Verdict-and-outcome ledger for Scare Bets (app module).

Pilot directive 2026-11-12: "The app from now on logs and
keep record of its bets and outcomes to build a dynamic
mathematical foundation."

What this module is: the app's own permanent book of every
bet it issued a verdict on, and what happened to that bet
afterwards. Every pull that prices the board appends one
entry per market the checker issued a verdict for — the
engine's rung exactly as issued, the shell's BET NOW /
DO NOT BET layer (the shell computes the layer with its own
bet_now(); this module never re-derives a verdict), the
price, the model probability, the edge. When an outcome for
a market becomes known, settle_outcomes() joins it onto the
bet by the market's contract key — the same join the 3D
panel's calibration instrument has always named as its
gate ("settled outcomes joined per market"). foundation()
then computes the running performance mathematics from the
settled side of the book: hit rates per verdict layer,
calibration of the model's own probabilities against
realized frequencies, Brier score, per-sport records. The
math is recomputed from the ledger on every read, so it is
dynamic by construction — it moves the moment an outcome
lands, and it never prints a settled statistic over an
empty settled set: counts of issued / settled / open ride
alongside every figure.

The 4D verdict layer in The Web of Everything
(instruments/web-of-everything.html) reads its history from
verdict_web_payload(): each pick's verdict timeline, so
flying through time shows the verdict the app actually held
at that moment, and its outcome once settled.

Design law mirrors history_store.py: stdlib only, and
deliberately standalone — no import of the app engine. The
market key is the history contract's key
(sport|fd_event_id|market|side|line), imported from the
sibling history_store module so the two stores can never
disagree about a market's identity, with a local copy as
fallback. The implied-probability math is duplicated
locally for the same reason history_store duplicates it.

Store layout under `store_dir`:
    verdict-ledger/YYYY-MM.jsonl — one JSON object per
    line, the file named by the record's own month
    (America/Detroit). Two record kinds share the file:
      {"kind": "verdict", "key", "logged_at", "sport",
       "fd_event_id", "fd_market_id", "fd_selection_id",
       "market", "side", "line", "price", "p", "edge_pts",
       "rung", "grade", "metal", "cal_tag", "stance",
       "layer", "event_time", "home", "away"}
      {"kind": "outcome", "key", "settled_at", "outcome"}
    Outcome is one of "won" / "lost" / "push" / "void".
    The first outcome recorded for a key wins; later outcome
    records for the same key are counted as duplicates and
    change nothing (a settled bet's result is a fact, not a
    dial). Verdict records are deduplicated on
    (key, logged_at): re-recording the same pull writes
    nothing twice.

A "bet" in the foundation math is one market key. Its
standing verdict is the LAST verdict the app issued for it
while it was open — the app's final word on that bet — and
its outcome is the joined outcome. Every issuance still
rides in the entry's timeline (the 4D layer reads the
timeline, not just the final word).

The app is an analyst: this ledger records verdicts and
outcomes. It places no bet, moves no money, and its BET NOW
layer is a signal the shell already computes — the ledger
only remembers it.
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

DETROIT = ZoneInfo("America/Detroit")
LEDGER_DIRNAME = "verdict-ledger"
LAYERS = ("BET NOW", "DO NOT BET")
OUTCOMES = ("won", "lost", "push", "void")
WEB_PICKS_CAP = 140

try:
    from history_store import market_key as _contract_key
except Exception:  # pragma: no cover - sibling always ships
    _contract_key = None


# ------------------------------------------------------------------
# primitives
# ------------------------------------------------------------------

def implied_prob(price):
    """American odds -> implied probability (the history
    contract's math, duplicated locally on purpose)."""
    if price is None:
        return None
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None
    if price == 0:
        return None
    if price > 0:
        return 100.0 / (price + 100.0)
    return (-price) / ((-price) + 100.0)


def market_key(mkt):
    """The contract key: sport|fd_event_id|market|side|line
    (see history_store.market_key — one identity per market,
    shared by both stores)."""
    if _contract_key is not None:
        return _contract_key(mkt)
    line = mkt.get("line")
    line_s = "" if line is None else str(line)
    return "|".join([str(mkt.get("sport")),
                     str(mkt.get("fd_event_id")),
                     str(mkt.get("market")),
                     str(mkt.get("side")),
                     line_s])


def _parse_ts(stamp):
    dt = datetime.fromisoformat(stamp)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=DETROIT)
    return dt


def _ledger_dir(store_dir):
    return os.path.join(store_dir, LEDGER_DIRNAME)


def _month_name(dt):
    return dt.strftime("%Y-%m")


def _month_files(store_dir):
    d = _ledger_dir(store_dir)
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if f.endswith(".jsonl"))


def _read_records(store_dir):
    out = []
    d = _ledger_dir(store_dir)
    for name in _month_files(store_dir):
        path = os.path.join(d, name)
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue  # a torn final line never
                        # poisons the book
        except OSError:
            continue
    return out


def _append_records(store_dir, month, records):
    d = _ledger_dir(store_dir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{month}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, sort_keys=True) + "\n")


# ------------------------------------------------------------------
# writing
# ------------------------------------------------------------------

def log_verdicts(store_dir, pulled_at, markets, verdicts, layers):
    """Append one verdict record per market the checker
    issued a verdict for. `verdicts` and `layers` align BY
    INDEX with `markets` (the app's convention); a None
    verdict or a None layer means no verdict was issued for
    that market and nothing is written for it. The rung is
    the engine's term exactly as issued; the layer is the
    shell's own BET NOW / DO NOT BET call. Returns
    {"logged": n, "skipped": n} — skipped counts deduped
    (key, logged_at) pairs already on file."""
    if not pulled_at:
        return {"logged": 0, "skipped": 0}
    existing = {(r.get("key"), r.get("logged_at"))
                for r in _read_records(store_dir)
                if r.get("kind") == "verdict"}
    month = _month_name(_parse_ts(pulled_at))
    rows = []
    skipped = 0
    for i, m in enumerate(markets or []):
        v = verdicts[i] if i < len(verdicts) else None
        layer = layers[i] if i < len(layers) else None
        if not isinstance(v, dict) or layer not in LAYERS:
            continue
        key = market_key(m)
        if (key, pulled_at) in existing:
            skipped += 1
            continue
        existing.add((key, pulled_at))
        p = v.get("p")
        price = m.get("price")
        q = implied_prob(price)
        edge = None
        if p is not None and q is not None:
            edge = round((p - q) * 100.0, 3)
        rows.append({
            "kind": "verdict",
            "key": key,
            "logged_at": pulled_at,
            "sport": m.get("sport"),
            "fd_event_id": m.get("fd_event_id"),
            "fd_market_id": m.get("fd_market_id"),
            "fd_selection_id": m.get("fd_selection_id"),
            "market": m.get("market"),
            "side": m.get("side"),
            "line": m.get("line"),
            "price": price,
            "p": p,
            "edge_pts": edge,
            "rung": v.get("verdict") or v.get("state"),
            "grade": v.get("grade"),
            "metal": v.get("metal"),
            "cal_tag": v.get("cal_tag"),
            "stance": v.get("stance"),
            "layer": layer,
            "event_time": m.get("market_time"),
            "home": m.get("home"),
            "away": m.get("away"),
        })
    if rows:
        _append_records(store_dir, month, rows)
    return {"logged": len(rows), "skipped": skipped}


def settle_outcomes(store_dir, results, settled_at):
    """Join outcomes onto open bets. Each result names its
    market by "key" or by the fd id triple
    (fd_event_id / fd_market_id / fd_selection_id) and
    carries "outcome" in won/lost/push/void. The first
    outcome for a key wins. Returns {"settled": n,
    "duplicates": n, "unknown": n} — unknown counts results
    naming a market the ledger holds no verdict for; they
    are never written (the ledger only settles its own
    bets)."""
    if not settled_at:
        return {"settled": 0, "duplicates": 0, "unknown": 0}
    entries = _fold(_read_records(store_dir))
    by_ids = {}
    for key, e in entries.items():
        triple = (e.get("fd_event_id"), e.get("fd_market_id"),
                  e.get("fd_selection_id"))
        if triple[0] is not None:
            by_ids.setdefault(triple, key)
    month = _month_name(_parse_ts(settled_at))
    rows = []
    settled = duplicates = unknown = 0
    for r in results or []:
        outcome = (r or {}).get("outcome")
        if outcome not in OUTCOMES:
            continue
        key = r.get("key")
        if key is None:
            key = by_ids.get((r.get("fd_event_id"),
                              r.get("fd_market_id"),
                              r.get("fd_selection_id")))
        if key is None or key not in entries:
            unknown += 1
            continue
        if entries[key].get("outcome") is not None:
            duplicates += 1
            continue
        entries[key]["outcome"] = outcome  # first wins, also
        # within this call
        rows.append({"kind": "outcome", "key": key,
                     "settled_at": settled_at,
                     "outcome": outcome})
        settled += 1
    if rows:
        _append_records(store_dir, month, rows)
    return {"settled": settled, "duplicates": duplicates,
            "unknown": unknown}


# ------------------------------------------------------------------
# reading / folding
# ------------------------------------------------------------------

def _fold(records):
    """All records -> one entry per market key: the full
    verdict timeline (chronological), the standing (last)
    verdict's fields, and the joined outcome."""
    entries = {}
    outcomes = {}
    for r in records:
        if r.get("kind") == "outcome":
            outcomes.setdefault(r.get("key"), r)
    for r in records:
        if r.get("kind") != "verdict":
            continue
        key = r.get("key")
        e = entries.get(key)
        if e is None:
            e = {"key": key,
                 "sport": r.get("sport"),
                 "fd_event_id": r.get("fd_event_id"),
                 "fd_market_id": r.get("fd_market_id"),
                 "fd_selection_id": r.get("fd_selection_id"),
                 "market": r.get("market"),
                 "side": r.get("side"),
                 "line": r.get("line"),
                 "event_time": r.get("event_time"),
                 "home": r.get("home"),
                 "away": r.get("away"),
                 "timeline": [],
                 "outcome": None,
                 "settled_at": None}
            entries[key] = e
        e["timeline"].append({
            "at": r.get("logged_at"),
            "layer": r.get("layer"),
            "rung": r.get("rung"),
            "p": r.get("p"),
            "price": r.get("price"),
            "edge_pts": r.get("edge_pts"),
        })
    for key, e in entries.items():
        e["timeline"].sort(key=lambda t: t.get("at") or "")
        last = e["timeline"][-1] if e["timeline"] else {}
        e["first_at"] = (e["timeline"][0].get("at")
                         if e["timeline"] else None)
        e["last_at"] = last.get("at")
        e["layer"] = last.get("layer")
        e["rung"] = last.get("rung")
        e["p"] = last.get("p")
        e["price"] = last.get("price")
        e["edge_pts"] = last.get("edge_pts")
        o = outcomes.get(key)
        if o is not None:
            e["outcome"] = o.get("outcome")
            e["settled_at"] = o.get("settled_at")
    return entries


def read_ledger(store_dir):
    """The folded book: {key: entry} — see _fold."""
    return _fold(_read_records(store_dir))


def ledger_begins(store_dir):
    """The earliest verdict stamp on file, or None."""
    stamps = [r.get("logged_at") for r in _read_records(store_dir)
              if r.get("kind") == "verdict" and r.get("logged_at")]
    return min(stamps) if stamps else None


# ------------------------------------------------------------------
# the dynamic foundation
# ------------------------------------------------------------------

def _layer_math(bets):
    """Performance math over one layer's settled bets.
    won/lost count only decisive outcomes (push and void
    settle without judging the call). hit_rate is the
    layer's own success measure: for BET NOW, the share of
    decisive settled bets the selection won; for DO NOT
    BET, the share it lost (the call was to stay off).
    realized is always the selection's raw win frequency,
    printed beside mean_p for calibration honesty."""
    decided = [b for b in bets if b.get("outcome") in ("won", "lost")]
    won = sum(1 for b in decided if b["outcome"] == "won")
    lost = len(decided) - won
    layer = bets[0].get("layer") if bets else None
    hit = None
    if decided:
        hit = (won if layer == "BET NOW" else lost) / len(decided)
    ps = [b["p"] for b in decided if b.get("p") is not None]
    brier = None
    if decided and ps:
        pairs = [(b["p"], 1.0 if b["outcome"] == "won" else 0.0)
                 for b in decided if b.get("p") is not None]
        brier = round(sum((p - y) ** 2 for p, y in pairs)
                      / len(pairs), 4)
    return {
        "issued": len(bets),
        "settled": len(bets),
        "decided": len(decided),
        "won": won,
        "lost": lost,
        "push": sum(1 for b in bets if b.get("outcome") == "push"),
        "void": sum(1 for b in bets if b.get("outcome") == "void"),
        "hit_rate": (round(hit, 4) if hit is not None else None),
        "realized": (round(won / len(decided), 4)
                     if decided else None),
        "mean_p": (round(sum(ps) / len(ps), 4) if ps else None),
        "brier": brier,
    }


def foundation(store_dir):
    """The dynamic mathematical foundation, recomputed from
    the ledger on every call: totals, per-layer records,
    per-sport records (BET NOW layer), and the calibration
    table — the model's stated probability against the
    realized win frequency in tenth-wide buckets, over all
    settled decisive bets with a stated p. Settled figures
    describe settled bets only; open counts ride beside
    them so an empty settled set can never pose as a
    record."""
    entries = read_ledger(store_dir)
    bets = list(entries.values())
    settled = [b for b in bets if b.get("outcome") is not None]
    by_layer = {}
    for layer in LAYERS:
        lb = [b for b in settled if b.get("layer") == layer]
        by_layer[layer] = _layer_math(lb)
        by_layer[layer]["issued"] = sum(
            1 for b in bets if b.get("layer") == layer)
    by_sport = {}
    for b in settled:
        if b.get("layer") != "BET NOW":
            continue
        by_sport.setdefault(b.get("sport"), []).append(b)
    by_sport = {s: _layer_math(v) for s, v in sorted(
        by_sport.items(), key=lambda kv: str(kv[0]))}
    buckets = []
    decided = [b for b in settled
               if b.get("outcome") in ("won", "lost")
               and b.get("p") is not None]
    for i in range(10):
        lo, hi = i / 10.0, (i + 1) / 10.0
        cell = [b for b in decided
                if lo <= b["p"] < hi or (i == 9 and b["p"] == 1.0)]
        if not cell:
            buckets.append({"lo": lo, "hi": hi, "n": 0,
                            "mean_p": None, "realized": None})
            continue
        won = sum(1 for b in cell if b["outcome"] == "won")
        buckets.append({
            "lo": lo, "hi": hi, "n": len(cell),
            "mean_p": round(sum(b["p"] for b in cell)
                            / len(cell), 4),
            "realized": round(won / len(cell), 4),
        })
    issuances = sum(len(b["timeline"]) for b in bets)
    return {
        "issued": len(bets),
        "issuances": issuances,
        "settled": len(settled),
        "open": len(bets) - len(settled),
        "begins": ledger_begins(store_dir),
        "by_layer": by_layer,
        "by_sport": by_sport,
        "calibration": buckets,
    }


# ------------------------------------------------------------------
# the 4D verdict layer's feed
# ------------------------------------------------------------------

def _pick_label(e):
    who = ""
    if e.get("away") and e.get("home"):
        who = f"{e['away']} @ {e['home']} — "
    line = e.get("line")
    line_s = "" if line is None else f" {line}"
    return (f"{who}{e.get('market')} {e.get('side')}{line_s}"
            .strip())


def verdict_web_payload(store_dir, cap=WEB_PICKS_CAP):
    """What /api/verdict-web.json serves: the foundation
    plus the pick nodes for the web's 4D verdict layer —
    most recently verdicted markets first, each with its
    full verdict timeline (the layer the app held at each
    stamp) and its outcome once settled."""
    entries = read_ledger(store_dir)
    bets = sorted(entries.values(),
                  key=lambda b: b.get("last_at") or "",
                  reverse=True)[:cap]
    picks = [{
        "key": b["key"],
        "label": _pick_label(b),
        "sport": b.get("sport"),
        "market": b.get("market"),
        "side": b.get("side"),
        "line": b.get("line"),
        "event_time": b.get("event_time"),
        "first_at": b.get("first_at"),
        "timeline": [{"at": t.get("at"), "layer": t.get("layer"),
                      "rung": t.get("rung"), "p": t.get("p"),
                      "price": t.get("price")}
                     for t in b["timeline"]],
        "outcome": b.get("outcome"),
        "settled_at": b.get("settled_at"),
    } for b in bets]
    return {"foundation": foundation(store_dir), "picks": picks}
