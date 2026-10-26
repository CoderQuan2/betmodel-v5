"""BetFi 11 card reference — DO NOT EDIT, DO NOT IMPORT.

Extracted verbatim from commit 68854ee (BetFi 11.0.2, build 15)
main.py by the v12.8 port: build_market_card, its _tile helper,
and the SPORT_LABELS it reads. The harness's v12.8 fixture pin
AST-compares the shipped card code in main.py against this
file (normalizing only the shipped card's _v11_SPORT_LABELS
name back to SPORT_LABELS) — any logic drift in the shipped
card fails the gate forever. This file is a reference text for
that comparison; nothing imports or executes it.
"""

SPORT_LABELS = {"nfl": "NFL", "ncaaf": "NCAAF", "nba": "NBA",
                "nhl": "NHL", "mlb": "MLB", "soccer": "Soccer"}


def _tile(title: str, gloss: str, body_lines: list) -> ft.ExpansionTile:
    """A depth tile: the engine's section name, a one-line plain
    gloss under it (language report S4 — gloss, don't rename), then
    the engine's lines."""
    controls = [_line(gloss, 11, DIM)]
    controls += [_line(t) for t in body_lines]
    return ft.ExpansionTile(
        title=ft.Text(title, size=12, color=ACCENT,
                      weight=ft.FontWeight.BOLD),
        controls=[ft.Container(
            padding=8,
            content=ft.Column(spacing=2, controls=controls))])


def build_market_card(mkt: dict, verdict: dict, rec: dict,
                      quotes_by_game: dict, rank: int | None = None,
                      edge_pts: float | None = None,
                      lane_ctx: dict | None = None) -> ft.Container:
    lane = market_lane(mkt)
    if lane_ctx is not None and lane in lane_ctx:
        (w, l, rec_src, phi, phi_state, uncal, cal_tag) = \
            lane_ctx[lane]
    else:
        w, l, rec_src = b5.lane_record(lane)
        phi, phi_state, _detail = b5.lane_phi(lane)
        uncal = b5.lane_uncalibrated(lane)
        cal_tag = verdict.get("cal_tag") or \
            b5.calibration_tag(lane, b5.load_scorecard())
    p = verdict.get("p")
    grade = verdict.get("grade")
    term, vreason = card_verdict(verdict)
    state = verdict.get("state") or ""
    stance = verdict.get("stance")
    if verdict.get("cal_tag"):
        cal_tag = verdict["cal_tag"]
    key = (mkt.get("sport"), mkt.get("away"), mkt.get("home"))
    quote = quotes_by_game.get(key)
    if quote and any(quote.get(k) is not None for k in
                     ("spread_home", "total", "ml_p_home")):
        flags = b5.coherence_check([quote])
        coh_lines = flags or ["coherent at quoted prices"]
    else:
        coh_lines = ["insufficient quotes in this pull to audit"]

    face = []
    if rank is not None:
        face.append(_line(
            f"FIND #{rank}"
            + (f" · edge {edge_pts:+.1f} pts"
               if edge_pts is not None else ""),
            12, ACCENT, True))
    # F1 identity block — the bet leads, the game follows:
    # line 1 the FanDuel market name (the player on props),
    # line 2 the selection in plain words with its price,
    # line 3 the matchup + start time + league, then the
    # FanDuel navigation path and the slip-label copy button.
    name = bet_name(mkt, verdict)
    face.append(ft.Text(name["headline"], size=17, color=INK,
                        weight=ft.FontWeight.BOLD))
    sel_row = [ft.Text(name["selection"], size=15, color=INK,
                       weight=ft.FontWeight.BOLD)]
    if mkt.get("price") is not None:
        price = int(mkt["price"])
        if mkt.get("sport") == "soccer":
            # world readers price in decimal: decimal first,
            # American in parentheses (language report W4)
            price_txt = (f"odds "
                         f"{b5.american_to_decimal(price):.2f} "
                         f"({price:+d})")
        else:
            price_txt = f"odds {price:+d}"
        sel_row.append(ft.Text(price_txt, size=12, color=DIM))
    face.append(ft.Row(spacing=8, controls=sel_row))
    meta_bits = [name["matchup"]]
    _dt = _market_dt(mkt)
    if _dt is not None:
        meta_bits.append(_dt.strftime("%a %b %d · %I:%M %p")
                         .replace(" 0", " "))
    meta_bits.append(SPORT_LABELS.get(
        mkt.get("sport"), (mkt.get("sport") or "?").upper()))
    face.append(_line(" · ".join(meta_bits), 11, DIM))
    face.append(ft.Row(
        spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text("Find it: ", size=11, color=FAINT,
                    weight=ft.FontWeight.BOLD),
            ft.Text(name["fd_path"], size=11, color=DIM),
            ft.IconButton(
                icon=ft.Icons.CONTENT_COPY, icon_size=15,
                icon_color=ACCENT, width=34, height=34,
                tooltip="Copy the exact slip label",
                on_click=lambda e, lbl=name["slip_label"]:
                _copy_label(e, lbl))]))
    face.append(_line(f"Win {w} · Lose {l}   ({lane} lane record)",
                      11, DIM))
    # hero row: probability left (promoted), edge right, colored
    hero = [ft.Text(
        "Probability UNPRICED" if p is None else
        f"Probability {p * 100:.1f}%",
        size=20, color=WARN if p is None else INK,
        weight=ft.FontWeight.BOLD)]
    if p is not None and edge_pts is not None:
        hero.append(ft.Text(
            f"{edge_pts:+.1f} pts", size=14,
            color=EDGE_POS if edge_pts > 0 else
            EDGE_NEG if edge_pts < 0 else DIM,
            weight=ft.FontWeight.BOLD))
    face.append(ft.Row(spacing=8,
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                       controls=hero))
    # grade row: grade stays colored TEXT (never a pill), the
    # state beside it, the calibration chip right-aligned
    grade_row = [
        ft.Text(f"Grade {grade}" if grade else "Grade —",
                size=16, color=GRADE_COLORS.get(grade or "", FAINT),
                weight=ft.FontWeight.BOLD),
        ft.Text(state, size=12,
                color=DIM if state == "PRICED" else WARN,
                weight=ft.FontWeight.BOLD)]
    chip = cal_chip(cal_tag)
    if chip is not None:
        grade_row.append(ft.Container(expand=True))
        grade_row.append(chip)
    face.append(ft.Row(spacing=8, controls=grade_row))
    # pill row: verdict first, stance beside it — never a stance
    # without a verdict
    pills = [verdict_pill(term, unpriced=(state == "UNPRICED"))]
    sp = stance_pill(stance)
    if sp is not None:
        pills.append(sp)
    face.append(ft.Row(spacing=8, controls=pills))
    if uncal:
        # the engine's stamp, verbatim on the face
        face.append(_line(uncal, 11, WARN, True))
    if verdict.get("note"):
        face.append(_line(verdict["note"], 10, FAINT))

    # the engine's verdict + its named reason lead the collapsible
    # depth — first line, verbatim
    anatomy = []
    if vreason:
        anatomy.append(f"{term} — {vreason}")
    elif term:
        anatomy.append(f"verdict: {term}")
    anatomy.append(f"state: {state}")
    if stance:
        anatomy.append(f"stance: {stance} — the shape of the bet "
                       f"(Terms); the verdict above decides")
    anatomy.append(f"calibration tag: {cal_tag or '—'}")
    if p is not None:
        anatomy.append(f"model probability (after calibration — "
                       f"see Terms: phi): {p * 100:.1f}%")
    if mkt.get("price") is not None:
        anatomy.append(f"pulled price: {int(mkt['price']):+d} "
                       f"(implied "
                       f"{b5.implied_prob(mkt['price']) * 100:.1f}%)"
                       f" · decimal odds "
                       f"{b5.american_to_decimal(int(mkt['price'])):.2f}")
    if edge_pts is not None:
        anatomy.append(f"edge: {edge_pts:+.1f} pts (model P - "
                       f"implied P at the pulled price)")
    if mkt.get("line") is not None:
        anatomy.append(f"line: {mkt['line']} · side: "
                       f"{side_label(mkt)}")
    if verdict.get("detail"):
        anatomy.append(f"checker detail: {verdict['detail']}")
    if verdict.get("note"):
        anatomy.append(f"checker note: {verdict['note']}")

    phi_params = ({k: v for k, v in phi.items() if k != "kind"}
                  if isinstance(phi, dict) else {})
    scale = [f"phi: {phi.get('kind', '?') if isinstance(phi, dict) else '?'}"
             f" [{phi_state}]"
             + (f" params {phi_params}" if phi_params else ""),
             f"lane record: {w}-{l} ({rec_src})",
             f"calibration tag: {cal_tag or '—'}"
             + (f" — {uncal}" if uncal else "")]

    stamp_text, _degraded = stamp_of(rec)
    provenance = [f"menu: {stamp_text}",
                  f"source: {rec.get('source')}",
                  f"pulled at: {rec.get('pulled_at')}"]
    if mkt.get("market_time"):
        provenance.append(f"kickoff: {mkt['market_time']} (local)")
    if mkt.get("fd_event_id"):
        provenance.append(f"FanDuel event id: "
                          f"{mkt['fd_event_id']}")
    if mkt.get("fd_market_id"):
        provenance.append(f"FanDuel market id: "
                            f"{mkt['fd_market_id']}")
    provenance.append(f"card rendered: "
                      f"{datetime.now().astimezone().isoformat(timespec='seconds')}")

    stripe_color = UNPRICED_BORDER if state == "UNPRICED" else \
        VERDICT_BG.get(term, BORDER)
    gradient = None
    if term == "GOLDEN BET":
        # the only gradient on a card: a restrained gold wash
        # over the standing card surface (F3 depth pass)
        gradient = ft.LinearGradient(
            begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
            colors=["#191405", CARD_BG])
    return ft.Container(
        bgcolor=CARD_BG, gradient=gradient, border_radius=10,
        padding=12,
        shadow=ft.BoxShadow(blur_radius=14, spread_radius=0,
                            color="#00000066",
                            offset=ft.Offset(0, 4)),
        border=ft.Border(
            left=ft.BorderSide(3, stripe_color),
            top=ft.BorderSide(1, BORDER),
            right=ft.BorderSide(1, BORDER),
            bottom=ft.BorderSide(1, BORDER)),
        content=ft.Column(spacing=6, controls=face + [
            _tile("PRICE ANATOMY", "where the probability came from",
                  anatomy),
            _tile("SCALE",
                  "phi — the fitted map that adjusts this lane's "
                  "raw probabilities toward what its record has "
                  "earned", scale),
            _tile("COHERENCE",
                  "do this game's prices agree with each other?"
                  if mkt.get("sport") != "soccer" else
                  "do this match's prices agree with each other?",
                  coh_lines),
            _tile("PROVENANCE",
                  "where every number came from, and when",
                  provenance),
        ]))
