# BetFi Xii — Design Rescue Spec

Artist entity deliverable for the Xii build. This is the visual law for the
rescue; the coder implements against these numbers exactly. Anything not
specified here keeps the standing 11.0 rules (warm verdicts, cool stances,
UNPRICED outlined, verdict wording unchanged).

Identity in one line: **an X-ray of a bet.** Every surface looks like film on
a lightbox — dark navy field, translucent density, bone-white skeletal
linework, one cyan glow wherever the model sees something real.

---

## 1. App name & lockup

- Launcher / home-screen label: **`BetFi Xii`** (exactly that casing and
  space — this is the name under the icon on the phone).
- In-app wordmark (header, About): `BetFi` in Bone White, weight 700,
  followed by a space, then `Xii` in X-Ray Cyan (#38BDF8), weight 700.
  Same baseline, same size, no separator, no underline, no extra words.
- Roman numerals are all-caps `XII` **only** inside the icon and in the
  small header badge (see §4). Never write "XII" in running UI text and
  never write "Xii" in the icon.
- Wordmark sizes: header 22 sp; About screen 34 sp. Clearspace around the
  wordmark = height of the "B" on all sides. Minimum wordmark width 96 dp —
  below that, show the icon alone.
- Don'ts: no gradient text, no drop shadow on the wordmark, no re-casing
  ("BETFI XII", "Betfi Xii", "BetFi_Xii" are all wrong in visible UI;
  `BetFi_Xii` is only the project/repo identifier).

## 2. Icon

Files delivered in `xii-artist/`:

| File | Size | Use |
|---|---|---|
| `icon.png` | 1024×1024 | Master / store / release asset |
| `icon-512.png` | 512×512 | Store listing |
| `icon-192.png` | 192×192 | Launcher density fallback |

Construction (what's drawn, so it is never redrawn differently):

- Full-bleed film field #060B1A, faint 64 px grid at 6% cyan, thin film
  frame inset 34 px, cyan registration corner marks.
- Three faint halo scan-rings centred on the ball.
- The ball: double rim (13 px bone-white outer, faint inner), central
  pentagon in translucent cyan density with a bone-white outline, skeletal
  seam spokes to the rim, two faint internal panel arcs. It is a *skeleton*
  of a ball on film, never a filled/photoreal ball.
- The chart: one rising polyline entering lower-left, exiting upper-right
  as an arrowhead, drawn as a cyan tube (26 px) with a bone-white core
  (9 px) and a blurred cyan glow pass; hollow node rings with cyan centres
  at each data point.
- `XII` in DejaVu Serif Bold, 196 px, bone white with a deep-cyan
  (#0E3C60) keyline, under a cyan hairline rule split by a centre diamond.
- Only text in the icon: `XII`. Nothing else, ever.
- Safe zone: all meaningful content lives inside the central 78% — Android
  adaptive masks (circle / squircle) must never clip the arrowhead
  (top-right) or the XII baseline. For the adaptive icon: background layer
  = solid #060B1A; foreground layer = ball + chart + XII group, scaled to
  78% and centred.
- Legibility gate (already passed, must keep passing after any edit):
  downscale to 96×96 — ball, arrow, and XII must each still read.

## 3. Palette — tokens

Standing base is unchanged. Xii adds the X-ray accents marked ★.

| Token | Hex | Use |
|---|---|---|
| `bg` | #060B1A | App background, icon field |
| `panel` | #0B1329 | Card / sheet surface |
| `panelRaised` ★ | #101E3D | Elevated card, chart viewer, dialogs |
| `panelXray` ★ | #0D2B45 @ 55% alpha over `panel` | "Density" fill inside X-ray treatments (ball, chart area, detail hero) |
| `hairline` | #1E3A5F | 1 dp borders, dividers, chart grid |
| `bone` ★ | #EAF8FF | Primary linework, primary text, icon core strokes |
| `boneDim` ★ | #CDE8F8 | Secondary linework, panel seams, axis labels |
| `inkDim` | #8FA8C8 | Secondary text (never below this on `bg` — contrast floor) |
| `cyan` | #38BDF8 | X-ray glow, links, selected state, "Xii" in the lockup |
| `cyanHi` ★ | #7DE0FF | Glow core highlights, chart node centres, active crosshair |
| `cyanDeep` ★ | #0E3C60 | Keylines under bone-white strokes (icon XII, chart line casing) |
| `gold` | #F5C451 | GOLDEN only — see §6. Nowhere else. |
| `goldDeep` | #2A1F06 | GOLDEN surface base |
| `won` / `lost` / `pending` | #34D399 / #F87171 / #9CA3AF | Result pills — always colour **and** text |

Glow rule: glow is a signal, not decoration. A cyan glow (blurred copy of
the stroke, Android: shadow / layered draw, radius 8–18 dp, cyan at
40–60% alpha under a bone-white core) appears only on: priced verdict
elements, the selected nav destination, chart data lines, and GOLDEN
surfaces (gold glow there, never cyan). UNPRICED, disabled, and empty
states get **no glow** — flat hairline only. If everything glows, nothing
is on the film.

## 4. Depth, spacing, typography

Depth — three layers, no more:
1. `bg` field (with the §5 film grid at 4–6% alpha on top-level screens only)
2. `panel` cards, 1 dp `hairline` border, radius 14 dp, shadow: black 35%,
   blur 12 dp, y-offset 4 dp
3. `panelRaised` for the chart viewer, sheets, and the GOLDEN card,
   radius 18 dp, border 1.5 dp

No nested cards inside cards. No grey drop shadows. Elevation is shown by
surface colour + hairline first, shadow second.

Spacing — 4 dp grid: screen padding 16 dp; card padding 14 dp; gap between
cards 10 dp; section gap 24 dp; touch targets ≥ 48 dp.

Typography:
- UI font: system sans (Roboto on Android). Serif is reserved for the icon
  XII and the header badge — nowhere else.
- Scale: screen title 22 sp / 700; card headline (the FanDuel market name)
  16 sp / 700 `bone`; selection line 15 sp / 600; body 14 sp; meta/labels
  12 sp / 600, uppercase, letter-spacing 0.08 em, `inkDim`.
- **All numbers tabular** (monospaced figures), right-aligned in columns.
  Odds, edge, EV, and prices never use proportional figures.
- Header badge: a 26×26 dp rounded square (radius 7 dp) in `panelRaised`
  with a `cyanDeep` keyline, containing `XII` in serif bold 11 sp `bone`,
  placed left of the wordmark, 8 dp gap.

## 5. How the X-ray identity carries into cards

- Every market card keeps the 11.0 identity order: line 1 = exact FanDuel
  market name, line 2 = selection in plain words, line 3 = matchup · time ·
  league chip. The rescue changes the *treatment*, not the order or wording.
- Card top edge carries a 22 dp "film strip": a `panelXray` band with the
  league chip left and the pull timestamp right, separated from the body by
  a `hairline`. This is the card's radiograph header.
- Priced cards: the verdict pill gets the glow treatment (§3) and the
  edge figure is set in `cyanHi`. The card border on the verdict side
  (left, 3 dp) takes the verdict colour at full strength.
- UNPRICED cards: flat, border dashed `hairline`, reason printed in
  `inkDim` italic — visibly "not on the film yet." No glow, no colour fill.
- Detail view hero: the matchup rendered as the icon is — a `panelXray`
  density panel, bone-white skeletal divider lines between the two sides,
  model-vs-market figures as two glowing traces (model = cyan, market =
  bone). Corner registration marks (like the icon frame) on this panel only.
- Copy mechanic (from the Pilot's tasking): tapping a *name* — a team,
  player, or market name — copies **that name only**, never the whole card
  title. Affordance: name text underlines in `cyanHi` while pressed, and a
  toast/snackbar confirms exactly what was copied ("Copied: Inter"). Names
  that copy get a small copy glyph (10 dp, `inkDim`) after the text on
  detail views only — board cards stay clean.

## 6. GOLDEN surfaces

- GOLDEN is the only warm thing in the app. Surface: `goldDeep` base with
  a restrained vertical gradient to #3A2A08, 1.5 dp `gold` border, gold
  glow (same mechanics as §3, gold at 45% alpha).
- Inside GOLDEN: text `bone`, figures `gold`, verdict pill solid `gold`
  with #060B1A text. No cyan anywhere inside a GOLDEN surface.
- The GOLDEN panel stays honestly empty when nothing qualifies: empty
  state is the same surface at 40% alpha border, no glow, centred text
  "No GOLDEN bets on this pull" in `inkDim`. An empty GOLDEN panel is a
  correct result, not an error screen — never fill it with near-misses.

## 7. In-app charts — zoomable, in-app, no sliders

- Charts open **inside the app** in a full-screen chart viewer
  (`panelRaised` sheet, §4 layer 3). Never kick the user to a browser or
  an external image. The existing 3D instruments follow the same rule:
  rendered in-app, full-screen on tap.
- Zoom is gesture-only: **pinch to zoom (1×–6×), drag to pan, double-tap
  toggles 1× ↔ 2.5×** centred on the tap. **No sliders anywhere in the
  app** — not for zoom, not for stake, not for thresholds. Anywhere a
  slider exists today, replace it with: preset chips (for ranges),
  a stepper (for single values), or direct numeric entry.
- Depth in charts: `hairline` grid both axes (dotted verticals), axis
  labels in `boneDim` 11 sp tabular, data line 2.5 dp as a glow trace
  (cyan body, bone-white 1 dp core), area under the model line filled
  `panelXray` gradient to transparent. Model vs market = two traces
  (model cyan glow, market bone, dashed). Never more than 3 traces.
- Inspection: tap-and-hold shows a crosshair — vertical `cyanHi` hairline,
  node dot, and a readout chip (`panelRaised`, radius 10 dp) with the
  timestamp, model value, and market value in tabular figures. Releasing
  dismisses it; nothing about inspection uses a slider or a scrub bar.
- **Charts update on pull:** when a new pull lands, open charts re-render
  with the new data in place — same chart, same zoom/pan state if the
  series still exists — and the pull timestamp in the chart header ticks
  to the new time with a single 240 ms fade (the standing motion spec:
  180–240 ms, no bounce). A chart must never silently show a stale pull:
  if the displayed data is older than the latest pull, the header shows
  "Stale — tap to refresh" in `gold`.
- Empty/insufficient data: the chart area shows the skeletal frame
  (border, grid, corner marks) with the honest state text centred, e.g.
  "Insufficient snapshots". No fake flat lines, no invented series.

## 8. Motion & states (carried, restated so the rescue doesn't regress it)

- Transitions: fade/slide 180–240 ms, no bounce, no gimmicks. Cards
  animate in once (opacity + small offset, staggered, capped).
- Skeleton placeholders use `panelXray` blocks with a slow cyan sheen
  sweep (1.2 s, alpha ≤ 12%) — the "film developing" state — instead of
  bare spinners.
- Result pills: colour **and** text, always (WON / LOST / PENDING / VOID).
- Focus/pressed states: `cyanHi` at 12% alpha wash; never a colour change
  alone for meaning.

## 9. Acceptance checks for the coder

1. Launcher label reads `BetFi Xii`; icon is the delivered `icon.png`
   lineage (or the adaptive pair built per §2) — XII legible at 96 px.
2. No hex value in the UI outside the §3 token table (gold outside GOLDEN
   is a defect).
3. Zero slider controls in the app (grep the widget tree).
4. Every chart: pinch-zoom works, opens in-app full-screen, header shows
   the pull timestamp, re-renders on a new pull without losing zoom.
5. GOLDEN empty on a non-qualifying pull renders the §6 empty state.
6. Tapping any team/player/market name copies that name alone, with the
   confirmation naming what was copied.
