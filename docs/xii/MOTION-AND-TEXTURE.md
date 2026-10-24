# BetFi Xii — Motion & Texture Spec

Artist entity, follow-up commission (Pilot order 2026-10-24: "a nice glowing
pulsation for the ice … give buttons weights, give surfaces texture, give the
app big-budget style"). Companion to `DESIGN-RESCUE.md` — same tokens, same
law: **glow = signal only**, GOLDEN is the only warm surface, **no sliders
anywhere**, tabular figures everywhere, transitions 180–240 ms unless a
section below says otherwise. Anything not specified here defers to the
rescue spec. All numbers are implement-as-written.

Flet reality note (applies to §1–§3): Flet animates opacity, scale, offset,
rotation and position natively (`ft.Animation`); it does **not** animate
shadow blur. Every "glow pulse" below is therefore implemented as a
**pre-rendered glow layer** (a container carrying the full `BoxShadow`)
stacked behind the element, whose **opacity** is animated. Never animate a
shadow property per frame.

---

## 1. Ice pulsation system

Shared glow mechanics (from rescue §3): blurred copy of the stroke/shape,
cyan at 40–60% alpha under a bone-white core. Ice pulse colour is `cyan`
#38BDF8 with `cyanHi` #7DE0FF at the core; the only warm pulse in the app is
the GOLDEN pulse (§1.3), gold #F5C451.

### 1.1 Startup splash pulse

The ice forming, then cracking open into the board. One sequence, never a
loop that outlives its welcome.

| Phase | Time | Icon scale | Glow layer radius* | Glow alpha | Notes |
|---|---|---|---|---|---|
| Ignition | 0–600 ms | 0.94 → 1.00 | 8 → 22 dp | 0% → 55% | Ease-out cubic; icon fades in 0 → 100% over the first 300 ms |
| First swell | 600–1200 ms | 1.00 | 22 → 12 dp | 55% → 35% | Ease-in-out; the breath out |
| Second swell | 1200–1800 ms | 1.00 → 1.01 | 12 → 26 dp | 35% → 60% | Ease-in-out; peak brightness of the whole splash, `cyanHi` core at full |
| Hold | 1800–2400 ms | 1.01 → 1.00 | 26 dp | 60% | Wordmark `BetFi Xii` (rescue §1 lockup) fades/slides in: opacity 0 → 100%, y-offset +6 → 0 dp, 240 ms, starting at 1900 ms |

\* "Radius" = the blur of the pre-rendered glow layer that is cross-faded in;
switch layers at the keyframe boundaries, animate only opacity between them.

- Easing: `ft.AnimationCurve.EASE_OUT` for Ignition, `EASE_IN_OUT` for both
  swells. No bounce, no overshoot anywhere.
- **Resolve — first pull lands before 2400 ms:** cut the sequence at
  whatever phase it is in. Glow decays over 240 ms to the static signal
  state (radius 10 dp, alpha 40%), splash cross-fades out 240 ms, and the
  board paints under it with the standing card entrance (opacity + 6 dp
  offset, 40 ms stagger, max 8 cards animated, the rest instant).
- **Resolve — pull lands after 2400 ms:** splash ends into the idle state
  below; the same 240 ms resolve runs whenever the pull does land.
- **Idle (no data yet):** one slow breath — period 3200 ms, glow radius
  fixed 14 dp, alpha oscillating 25% ↔ 40% only (a ±15-point band, visibly
  calmer than the swells), icon at scale 1.00. Status line under the
  wordmark in `inkDim` ("Pulling the board…"). Idle breathing is the
  splash's only permitted loop.
- **Pull failed / empty:** pulse stops dead. Splash resolves to the honest
  empty state (rescue §7 skeletal frame) — flat, no glow, no pulse.

### 1.2 Live-pull dot (in-app)

The heartbeat of the board. Sits left of the pull timestamp in the board
header and the chart header (rescue §7).

- Dot: 8 dp circle, solid `cyan`, bone-white 1 dp ring.
- Halo: pre-rendered glow layer behind it, radius animating by opacity
  cross-fade between a 4 dp / 50% alpha layer and a 10 dp / 20% alpha layer.
- **Period 2000 ms**, ease-in-out, symmetric: dot alpha 100% → 45% → 100%,
  halo inverse (bright when halo is tight, soft when halo is wide).
- **Freshness gate:** pulses only while the displayed pull is fresh
  (< 4 min old, the auto-pull cadence). At ≥ 4 min the dot freezes at
  60% alpha, halo off, and the timestamp gets the rescue §7 stale
  treatment ("Stale — tap to refresh" in `gold`). A stale app never
  throbs like a live one.
- On each new pull landing: one 240 ms timestamp fade (rescue §7) plus a
  single dot flash to 100% / halo 12 dp, then the 2000 ms cycle restarts.

### 1.3 GOLDEN warm pulse (in-app)

The only warm pulse, on GOLDEN surfaces only (rescue §6 — gold, never cyan,
no cyan anywhere inside).

- Target: the GOLDEN card's border glow layer only — never its text,
  figures, or pill.
- **Period 2800 ms** (deliberately slower than the ice dot — gold is calm,
  ice is alive), ease-in-out, symmetric.
- Glow layer: gold #F5C451, blur cross-fading 14 dp ↔ 22 dp, alpha
  35% ↔ 50%. Surface gradient (`goldDeep` #2A1F06 → #3A2A08) does not move.
- Applies to the GOLDEN panel header surface when ≥ 1 bet qualifies, and
  to at most the **top 3 GOLDEN cards** by grade; any further GOLDEN cards
  carry the static glow (blur 14 dp, alpha 40%).
- A newly qualifying GOLDEN bet gets one entrance bloom before joining
  the cycle: glow 0 → 22 dp / 55% alpha over 600 ms ease-out, settle to
  the 2800 ms cycle.
- **Empty GOLDEN panel: no pulse, no glow** (rescue §6) — 40% alpha border,
  centred `inkDim` text. Nothing about an empty panel may move.

### 1.4 One-shot pulses (fire once, never loop)

- **Newly priced card** (a market flips UNPRICED → priced on a new pull):
  its verdict pill glow blooms in once, 400 ms ease-out, 0 → static
  signal glow (radius 10 dp, alpha 40–60% per rescue §3). Cards that were
  already priced do not re-bloom.
- **Copy confirmation:** the copied name's underline (rescue §5) flashes
  `cyanHi` once, 160 ms in / 160 ms out. The toast does not pulse.
- **Pull timestamp tick:** 240 ms fade only (rescue §7). Fading is not
  pulsing — do not add a glow flash to routine ticks beyond §1.2's dot.

### 1.5 Where NOT to pulse — hard list

- UNPRICED anything: cards, pills, reasons, borders (flat dashed hairline
  only, rescue §5).
- Empty states of every kind, including the GOLDEN empty state (§1.3).
- Skeleton placeholders — they shimmer (§3.4); shimmer and pulse never
  combine on the same element.
- Text, figures, odds, edge, EV — numbers never breathe; legibility first.
- Navigation: the selected destination carries a *static* glow (rescue
  §3). Selection changes are a 180 ms cross-fade, not a pulse.
- Result pills (WON / LOST / PENDING / VOID) — static colour **and** text.
- Error / failed-pull states — static; alarm is shown by wording, not
  motion.
- Backgrounds: the film grid, vignette and grain (§3.1) are frozen.
- The wordmark and the XII badge — static after the splash resolves.
- Any off-screen element (see §5 viewport rule).

---

## 2. Button weight scale

Weight is communicated by height + font weight + shadow, in that order.
All buttons: minimum touch target 48 dp tall regardless of visual height
(tertiary excepted at 44 dp with 48 dp hit area via padding), label in
tabular figures when it contains numbers, pressed state = scale 0.98 +
shadow collapse (below) over 100 ms ease-out, release over 160 ms.
Focus/pressed wash: `cyanHi` at 12% alpha (rescue §8) under the label.

| | Primary | Secondary | Tertiary |
|---|---|---|---|
| Role | The one action per surface (Pull, Place-ready slip CTA, Refresh) | Paired actions (Parse, Copy slip, Filters) | Inline/text actions (Clear, View all, Dismiss) |
| Height | 52 dp | 48 dp | 44 dp hit area (36 dp visual) |
| Horizontal padding | 24 dp | 18 dp | 10 dp |
| Corner radius | 14 dp | 14 dp | 10 dp |
| Label | 15 sp, weight 700, letter-spacing 0.02 em | 14 sp, weight 600 | 14 sp, weight 600 |
| Fill / text | `cyan` #38BDF8 fill, #060B1A text | Transparent over `panel`; 1.5 dp border `hairline` #1E3A5F brightened on the label side to `cyan` at 60% alpha; `bone` text | No fill, no border; `cyan` text |
| Shadow | Two layers: black 30%, y 2 dp, blur 6 dp **+** cyan glow, y 0, blur 12 dp, alpha 25% (the only decorative-adjacent glow permitted — it marks the primary action, i.e. signal) | One layer: black 25%, y 2 dp, blur 4 dp | None |
| Icon (if any) | 20 dp, left of label, 8 dp gap, same colour as text | 18 dp, `boneDim` | 16 dp, `cyan` |

States:

- **Pressed (all tiers):** scale 0.98; primary loses its cyan glow layer
  and its black shadow drops to y 1 dp / blur 3 dp; secondary border goes
  full `cyan`; tertiary wash deepens to `cyanHi` 18% alpha.
- **Disabled:** fill `panelRaised` #101E3D (primary/secondary), text
  `inkDim` #8FA8C8, border `hairline`, **no shadow, no glow, no pulse**,
  opacity 100% (grey it by colour, never by fading the label below the
  contrast floor).
- **Loading (primary only, e.g. Pull in flight):** label swaps to the
  action's progress wording ("Pulling…"), a 16 dp spinner ring in
  #060B1A replaces the icon; the button does **not** pulse — the §1.2 dot
  in the header carries the liveness.
- Exactly **one primary per visible surface**. If two actions feel
  primary, one of them is secondary — demote it, don't promote both.

---

## 3. Surface texture system

### 3.1 Elevation tokens

Three layers, per rescue §4 — texture lives *inside* each layer's recipe,
never as extra floating decoration.

| Token | Background | Border | Shadow | Extra texture |
|---|---|---|---|---|
| **L0 — field** | Solid `bg` #060B1A, with a radial vignette: gradient from #060B1A (centre, 0%) to #040814 (edge, 100%) | — | — | Film grid on top-level screens only: 64 dp squares, `cyan` at 4% alpha, 1 dp lines; plus static grain (§3.5) |
| **L1 — card** (`panel`) | Vertical gradient: #0B1329 at 0% → #0A1122 at 100% | 1 dp `hairline` #1E3A5F, radius 14 dp | Black 35%, blur 12 dp, y-offset 4 dp | Top inner highlight: 1 dp line across the top inner edge, `bone` at 6% alpha (the lightbox edge-catch) |
| **L2 — raised** (`panelRaised`: chart viewer, sheets, dialogs, GOLDEN card) | Vertical gradient: #101E3D at 0% → #0D1830 at 100% | 1.5 dp `hairline` #1E3A5F, radius 18 dp | Black 40%, blur 20 dp, y-offset 8 dp | Top inner highlight as L1 but `bone` at 8% alpha; GOLDEN variant swaps the base to the rescue §6 gold gradient and border to `gold` 1.5 dp |

Rules: elevation reads colour + hairline first, shadow second (rescue §4).
No nested cards. Grey shadows are a defect — shadows are black-alpha only.
An element carries **at most 3 shadow layers** (primary button = 2, L2
surface = 1, glow layer counts as its element's own, not the surface's).

### 3.2 X-ray film-strip card header

Every market card's 22 dp header band (rescue §5), textured as film stock:

- Base: `panelXray` #0D2B45 at 55% alpha composited over the card's L1
  gradient; bottom edge closed by the 1 dp `hairline`.
- Sprocket texture: a row of perforation marks along the band's top edge —
  rounded rectangles 8 × 4 dp, radius 2 dp, `bone` at 8% alpha, spaced
  18 dp apart, first mark inset 10 dp from the left. They sit *behind*
  the content at texture alpha; the league chip (left) and pull timestamp
  (right, tabular, `boneDim`) render over them at full strength.
- Scan sheen: a single diagonal band (45°, width 28 dp, `cyan` at 3%
  alpha) fixed at the band's left third — static, position never animates
  (this is texture, not the §3.4 shimmer).
- On priced cards only, the band's right end carries a 14 dp registration
  corner mark in `cyan` at 50% alpha (⌐ rotated to the corner). UNPRICED
  cards: same band, dashed bottom hairline, no registration mark, no sheen.

### 3.3 Frosted ice header (app header + chart header)

- Base: `panelRaised` gradient (§3.1 L2 stops) at **82% opacity** over
  the L0 field, bottom 1 dp `hairline`, top inner highlight `bone` 8%.
- Flet has no backdrop blur — do **not** fake it with a blur filter over
  content (costly, §5). The frost is the 82% opacity + a fine ice-crystal
  grain: 2 dp dots, `cyanHi` at 2% alpha, on a 14 dp staggered grid,
  clipped to the header only. Reads as frost at arm's length, costs one
  static pattern layer.
- The header never pulses. Its only motion is the §1.2 live dot it hosts
  and the 240 ms timestamp fade.

### 3.4 Skeleton shimmer sweep

The "film developing" state (rescue §8), tightened to numbers:

- Blocks: `panelXray` fill, radius matching the element they stand in for
  (text line 6 dp, card 14 dp), static base alpha 100% of the token.
- Sweep: a gradient band 35% of the block's width, `cyanHi` peaking at
  **12% alpha** at band centre, falling to 0% at both edges, translating
  from −100% to +200% of block width over **1200 ms**, ease-in-out.
- Between sweeps: **300 ms** of flat block (full cycle 1500 ms). All
  blocks on a screen sweep **in phase** (one clock, staggered 0 ms) —
  a screen of skeletons breathes together or it looks broken.
- Max 4 shimmering blocks animate concurrently per screen (§5); further
  skeleton blocks render flat.
- Shimmer stops the moment real content lands in that block — content
  cross-fades in over 180 ms, never waits for the sweep to finish.

### 3.5 Static grain (whole-app)

- One repeating noise pattern over L0/L1/L2 alike: 1 dp dots at 2% alpha
  `bone`, pseudo-random per 128 × 128 dp tile, rendered as a single
  pre-generated background image per surface size class — never a
  per-element filter, never animated. If the pattern can't be pre-rendered
  in a given surface, omit grain there rather than generating it live.

---

## 4. Micro-touches — big-budget details

Each is one line, Flet-implementable, and none may add a slider.

1. **Copy toast:** `panelRaised` chip (radius 10 dp) with a 14 dp cyan
   check icon + "Copied: {name}" in `bone`, slides up 8 dp / fades in
   180 ms, auto-dismisses at 1600 ms — confirming exactly what was copied.
2. **Card entrance:** cards fade/slide in once per pull (opacity 0 → 100%,
   y-offset +6 → 0 dp, 200 ms, 40 ms stagger, capped at 8 cards; the rest
   appear instantly) — re-pulls re-animate only cards whose data changed.
3. **Changed-figure tick:** when a pull updates a figure on a visible card,
   the number cross-fades 180 ms and its column never shifts width
   (tabular figures, fixed column widths).
4. **Relative pull age:** the header timestamp gains a quiet suffix —
   "· 12 s ago" / "· 3 min ago" in `inkDim` — recomputed every 30 s,
   swapped without animation except the standing 240 ms fade.
5. **Section divider motif:** section headers sit on a `hairline` rule
   split by a 7 dp centre diamond in `cyan` at 60% alpha — the icon's
   XII rule, echoed at UI scale.
6. **Chart chrome:** chart header shows pull timestamp + a legend chip
   row (model = chip with glowing cyan dot, market = chip with bone
   dashed swatch); on pinch, a tabular zoom readout ("2.5×") appears
   top-right and fades 1200 ms after the gesture ends.
7. **Verdict edge flash:** a card's 3 dp verdict side-border (rescue §5)
   animates colour over 200 ms when a new pull changes its grade — the
   only colour transition on the card, everything else swaps instantly.
8. **Empty-state corners:** every empty/insufficient panel gets the four
   registration corner marks (14 dp, `hairline` full strength) around its
   skeletal frame — an empty film frame looks intentional, not broken.
9. **GOLDEN arrival order:** when the GOLDEN panel gains its first bet it
   plays the §1.3 entrance bloom, then the panel header's count figure
   ("1") ticks in with the §4.3 cross-fade — arrival feels like an event,
   emptiness never does.

---

## 5. Performance budget

Pulse and shimmer are spent like money — this budget is a hard cap, not a
guideline. When the cap and a spec item conflict, the cap wins and the
lowest-priority animation (order: §3.4 shimmer → §1.3 GOLDEN cards beyond
the first → §1.2 halo) degrades to its static state first.

- **Looping animations, total on screen: ≤ 6.** The standing load is 3:
  live-pull dot (1) + GOLDEN pulse (1 surface, or top card) + splash idle
  *or* skeleton shimmer phase-clock (1, and they never coexist). Headroom
  of 3 is reserved, not spent by default.
- **Pulse implementation rate:** all pulses run as declarative
  `ft.Animation` opacity cross-fades (GPU/compositor side). Any manual
  timer fallback ticks at **≥ 100 ms intervals (≤ 10 fps)** and only ever
  writes opacity — no layout, no shadow, no text changes per tick.
- **Frame budget:** no animation may trigger a control-tree rebuild;
  animating properties are opacity / scale / offset only. Shadow layers
  ≤ 3 per element (§3.1), pre-rendered glow blur ≤ 26 dp (the §1.1 peak).
- **Viewport rule:** only elements in the visible viewport animate;
  scrolled-off cards hold their static state and resume (not restart)
  their cycle when visible again.
- **Lifecycle:** every looping animation pauses when the app is
  backgrounded or the screen is off, and resumes on return — a board
  nobody is looking at does not throb.
- **Battery rule:** at battery ≤ 20% or with OS battery-saver on, all
  pulses and shimmer switch to their static states (dot solid at 80%
  alpha, GOLDEN glow static at 14 dp / 40%, skeletons flat) and the
  splash plays the sequence once with the idle breath disabled. Motion
  returns automatically when charge/saver clears.
- **Splash discipline:** the §1.1 sequence plays once per cold start,
  never on pull, navigation, or return-from-background (warm returns get
  at most the 240 ms timestamp fade).

---

## Acceptance checks for the coder

1. Splash: keyframe table §1.1 reproduced (scale, radii, alphas, timings);
   resolves in 240 ms whenever the first pull lands, early or late.
2. Live dot: 2000 ms period, freezes stale at ≥ 4 min with the gold stale
   treatment — verify by ageing a pull.
3. GOLDEN pulse: 2800 ms, gold only, ≤ top 3 cards; empty panel provably
   motionless.
4. §1.5 grep-by-eye pass: no pulse/shimmer/glow on any UNPRICED, empty,
   disabled, or error surface in the build.
5. Buttons: exactly one primary per surface; pressed/disabled/loading
   states match §2 values; every target ≥ 48 dp.
6. Simultaneously looping animations counted on the busiest screen ≤ 6;
   battery-saver state kills all loops to static.

[END OF FILE]
