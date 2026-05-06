# Step 5d — Design Each Slide's Layout

The LLM designs each slide's `layoutSpec` directly, guided by
[layout-principles.md](layout-principles.md) and the slide's
`contentForm` from Step 4. Every layout is reasoned from the
specific content, narrative role, and audience — never selected
from a pre-existing catalog. After designing, the LLM assigns
a descriptive `layoutPattern` name for traceability.

---

## Batching (large decks)

5d is the heaviest per-slide output in the workflow.

**When to batch.** Default to single-pass. Only split when the
combined `layoutSpec` output for all slides would exceed one
coherent response or quality visibly degrades. Estimate total
output volume before starting — do not pre-emptively batch on
slide count alone.

**Split boundaries.** Split along act boundaries — one batch
per act (plus its divider). Cover → first batch; closing → last
batch. If a single act is still too large, split at a sub-topic
boundary within the act.

**Global precondition.** Steps 5a–5c run **once** before any
batch. The frozen `s05b-style-policy.json` is shared read-only
across all batches — it is the single source of truth for
palette, typography, compositionPalette budgets, and visual tone.

**First-batch scope.** The first batch also produces `deckMeta`,
`structuralFamily`, cover, and the canonical divider. These are
deck-level; subsequent batches reuse them without modification.

**Cross-batch continuity context.** Each batch receives:

- `s05b-style-policy.json` (full, read-only).
- `s04-content-draft.json` + `s03-presentation-blueprint.json`
  (full, read-only — upstream artifacts shared across batches).
- `tailSlides` from the prior batch: the **last 2 body slides**
  designed in the previous batch. Include per slide:
  `slideId`, `layoutPattern`, `compositionFamily`,
  `designRationale.aestheticMove`, `background.type`, and
  `emphasis`. This is enough to enforce adjacent-pair contrast
  (Rule 2) and avoid aesthetic-move repetition at the boundary.
- `paletteBudgetSnapshot`: a copy of the current
  `compositionPalette` with remaining `usesLeft` per family,
  computed after the prior batch. This lets the new batch
  continue decrementing accurately.

Do not replay entire prior-batch outputs — carry only the
fields listed above.

**Palette budget tracking across batches.** Before each batch,
compute `usesLeft = maxUses − usesInPriorBatches` for every
`compositionPalette` family. Pass this snapshot to the batch.
Within the batch, decrement locally. If all families reach zero
mid-batch, the single permitted post-freeze mutation applies:
append one new family with `addedAt` + `rationale` to
`s05b-style-policy.json`, then continue.

**Execution order.** Batches execute **sequentially** — each
batch depends on the prior batch's tail slides and budget
snapshot. Do not run 5d batches in parallel.

**Validator cadence.**

- Run `s05_validate_plan.py` **once per batch** (after the
  batch is written, before starting the next).
- Run once more **after all batches are merged** — this is the
  only run that can check cross-batch design floor quotas
  and adjacent-slide contrast at act boundaries.
- Do not run the validator more than once within a single batch.

---

## Design approach

For every slide:

1. Read `contentForm`, `contentMetrics`, `narrativeRole`, `emphasis`,
   and rhythm arc position from upstream artifacts.
2. Review prior slides' `aestheticMove` and `layoutPattern` to
   ensure variety.
3. **Commit a slide concept** before drawing zones: dominant
   gesture, focal element, contrast with neighbors. Choose
   `compositionPalette` family and `aestheticMove` now.
4. Execute layout: choose grid, size zones to content, add
   decorations, set background.
5. Verify: geometry within margins, no overlaps, concept delivery
   matches rationale.

Consult [layout-principles.md](layout-principles.md) for grid
system, margin rules, and geometric constraints.

---

## Coordinate system

Coordinates are **inches** on the `s01d-design-config.json → dimensions`
canvas. Full rule (suffix syntax, validator behavior, grid/margin
values): see SKILL.md § Step 5 — Visual planning and
[layout-principles.md § Coordinate System](layout-principles.md#coordinate-system).

---

## Bookend slides

Cover, closing, and dividers are LLM-designed with full
`layoutSpec`. All bookends share a visual language via the
`structuralFamily` block (designed once in 5d-bookend):

- `sharedMotif`, `coverTreatment`, `closingTreatment`,
  `dividerPattern`, `motifRationale`
- `*BackgroundType` fields for cover/closing/divider/recap
- `agendaDecorationFromMotif` (when structural-slide uplift triggers)
- `bookendSignature` (recommended): `rhyme`, `coverExpression`,
  `closingExpression`, `designIntent` — how cover and closing
  visually answer each other. Validator warns when absent.

**Bookend backgrounds:** apply
[visual-tone-impact-imagery.md § Imagery Floor](visual-tone-impact-imagery.md).
`designAmbition: "restrained"` caps bookend imagery at one slide;
dividers drop to `motif-shape`.

Design cover, closing, and one canonical divider in 5d-bookend.
Reuse divider composition for every divider. Validator enforces
divider-name consistency.

---

## Body slides

**Phase 1 — Concept commitment.**

1. **Read context.** Gather the slide's `contentForm`, `contentMetrics`,
   `narrativeRole`, `emphasis`, and position in the visual rhythm arc.
   Also read `illustrationSpec` (if any) for image constraints.
2. **Review prior slides.** Scan the `designRationale.aestheticMove`
   and `layoutPattern` of **all slides already designed in this batch**
   (and `tailSlides` from prior batches). Identify:
   - Which `compositionPalette` families are already spent or near cap.
   - Which `aestheticMove.axes` were used on the previous 2 slides.
   - Whether the previous slide shares a similar `contentForm.type`
     (if so, this slide **must** take a visually distinct approach).
3. **Commit a slide concept.** In one sentence, state: what is this
   slide's visual idea — its dominant gesture, its focal element, and
   how it contrasts with its neighbors? Write this into
   `designRationale.narrative`. Choose the `compositionPalette` family
   and the `aestheticMove` (move + axes + reason) **now**, before
   drawing any zones.

**Phase 2 — Layout execution (draw the concept).**

4. **Choose a grid** from the concept. Select column splits, vertical
   regions, and gutters. Use asymmetric splits for visual interest;
   symmetric for equal-weight content. When illustration zones
   exist, the grid must accommodate them — `placement:
   "primary-visual"` images get ≥ 40% of slide area;
   `"supporting-visual"` gets 20–35%; `"background"` gets
   10–20% (often as a strip, scrim, or full-bleed backdrop).
5. **Size zones to content.** Use `contentMetrics.wordCount` to
   estimate text volume. Dense slides need more zone area; light
   slides need more whitespace.
6. **Add decorations.** Card backgrounds, side
   stripes — encoded inline as shape zones (`type: "shape"` with
   explicit `x/y/w/h`, `shape`, `fill`). Match intensity to the
   act's `accentIntensity`. Never place a centered/short horizontal
   dash directly beneath a title. If title separation is needed, use
   whitespace, a full-width hairline tied to the grid, or a left-side
   vertical accent bar. Compose each shape directly from
   the design vocabulary in
   [layout-principles.md](layout-principles.md).
7. **Set background.** Solid, gradient, or tinted per the visual
   rhythm arc from Step 5b.

**Phase 3 — Verification (check against intent).**

8. **Verify geometry.** All zones fit within margins, no text-zone
   overlaps, minimum size rules met. Image zones must not overlap
   text zones (except for `placement: "background"` where a
   semi-transparent scrim is applied).
9. **Verify concept delivery.** Re-read the `designRationale` written
   in Phase 1. Does the layout actually deliver the stated concept?
   Does `focalPoint` match the largest/most prominent zone? Does
   `eyePath` trace a plausible reading order through the real zones?
   If not, adjust the layout — do not adjust the rationale to match
   a drifted layout.

**Verification cadence.** Run `s05_validate_plan.py` once per
5d batch and once at the end of 5d. Trust the validator, not the
eye — mental zone arithmetic on the 13.333" × 7.5" canvas is
unreliable.

---

## Image zone shape & dimensions

Step 5 owns the image zone shape decision. Choose the zone aspect
ratio based on the slide layout, available space, `imageCount`,
`placement`, and the visual subject described in
`illustrationSpec.subject`. Use this guide:

| Shape       | Zone aspect ratio | When to use                                                  |
| ----------- | ----------------- | ------------------------------------------------------------ |
| `landscape` | 3:2, 16:9, or 2:1 | Wide panel; hero scenes, panoramic comparisons, before/after |
| `portrait`  | 2:3 or 3:4        | Tall composition; character portraits, vertical architecture |
| `square`    | 1:1               | Grid items, icon-illustrations, card visuals, avatar source  |
| `strip`     | 4:1+ or 1:4+      | Banner or sidebar; orientation based on layout direction     |

Record the chosen shape as `imageShape` on the image zone.

**Mask styling.** Set `clipShape` on the image zone when the
visual language calls for it:

| `clipShape`      | Effect                                                                 |
| ---------------- | ---------------------------------------------------------------------- |
| `none` (default) | Rectangular zone — no clipping                                         |
| `circle`         | Oval clip via `MSO_AUTO_SHAPE_TYPE.OVAL` picture fill (avatars, icons) |
| `hexagon`        | Hexagonal clip (tech/science grids, honeycomb layouts)                 |

When `imageCount > 1`, distribute zones evenly using the grid
system. **Canonical multi-image arrangement examples:** see
[step3-narrative-blueprint.md § Multi-image examples](step3-narrative-blueprint.md).
All images in a multi-image set share the same zone dimensions.

---

## Naming the layout

After designing the layout, set `layoutPattern` to a descriptive
name that summarizes the composition (e.g.
`"asymmetric-stat-hero-band"`, `"five-step-flow-icons"`). The
name serves cross-slide consistency checks (dividers must share
a name) and human readability.

Write `s05-slide-visual-design.json`
(schema: [../schemas/s05-slide-visual-design.schema.json](../schemas/s05-slide-visual-design.schema.json),
example: [../schemas/s05-slide-visual-design.example.json](../schemas/s05-slide-visual-design.example.json)).

---

## Design Rationale (mandatory)

Written in Phase 1 (concept), verified in Phase 3 (check). If
layout drifts from intent, fix the layout, not the rationale.

Four required fields per body slide:

1. `narrative` — what about the content drove this layout.
2. `narrativeLink` — must reference the slide's `narrativeRole`
   token or a content word from `headlineMessage`. Generic
   phrasing is rejected by validator.
3. `focalPoint` + `eyePath` — concrete element name (not
   adjectives) + 2–4 ordered visual stops. `emphasis: "low"`
   slides may simplify to slot name + single-stop eyePath.
4. `aestheticMove` — structured triple:
   - `move` — concrete gesture description.
   - `axes` — 1–3 of `layout`/`color`/`form`/`scale`/`contrast`/
     `type`/`motion-implied`.
   - `reason` — why this move serves the headlineMessage.

---

## Reasoning Axes

Three vocabularies:

| Vocabulary           | Members                                                          | Use when                            |
| -------------------- | ---------------------------------------------------------------- | ----------------------------------- |
| Four static axes     | Form / Color / Type / Layout                                     | Reasoning about what kind of design |
| `aestheticMove.axes` | layout / color / form / type / scale / contrast / motion-implied | Filling the schema field            |
| Hierarchy levers     | Size / Contrast / Position                                       | Composing focal element priority    |

---

## Variety construction — five rules

The validator (`s05_validate_plan.py`) enforces all numeric
thresholds. The rules below describe the *intent*; exact numbers
are in the validator.

### Rule 1 — `compositionPalette` (designed in 5b, spent in 5d)

Design an explicit composition palette in
`s05b-style-policy.json → visualTone.compositionPalette`:
distinct families with per-family `maxUses` budget.

**Sizing:** families ≥ `ceil(bodySlideCount / 1.5)`. Sum of
`maxUses` must equal or slightly exceed `bodySlideCount`.

Every slide in 5d declares its `family`. Each declaration
decrements the budget. When spent, pick another family or
extend the palette with rationale.

`reproduce` mode suspends palette sizing. `beautify` raises
every `maxUses` by 1.

### Rule 2 — Adjacent-pair contrast (hard rule)

Any two adjacent body slides must differ on ≥1 of:
- **Background** — type or palette token.
- **Composition family** — different `compositionPalette` family.
- **Dominant type scale** — different tier (display/heading1/heading2/body).

All three matching = hard fail. Dividers between body slides
do not break adjacency.

### Rule 3 — Breathing slide (hard rule)

Every 6–8 consecutive body slides must contain ≥1 with
`informationDensity: "minimal"` AND `wordCount ≤ 25`.
Breathing slides are declared by Step 3. Step 5d does not
insert slides.

### Rule 4 — Title choreography (mandatory)

Declare in `s05b-style-policy.json → visualTone.titleChoreography`:
`movesAvailable`, `perSlidePlan`, `deckWideMoves`.

Nine moves: `mixed-weight-run`, `oversized-numeral`,
`multi-line-break`, `display-color-shift`, `dual-typeface`,
`vertical-act-label`, `wide-tracking`, `drop-cap`,
`split-highlight`.

Validator enforces: `perSlidePlan` length, no move > twice,
`dual-typeface` requires `typography.secondaryFont`.

### Rule 5 — `motifPalette` (recommended)

Declare in `s05b-style-policy.json → visualTone.motifPalette`:
`primaryMotif` (required when present) with 2–5 `vocabulary`
instances, optional `secondaryMotif`, `perSlidePlan`,
and `budget` (`ambientMaxFraction: 0.6`, `decorationFreeMin: 2`).

Validator warns when absent; enforces all rules when present.
`reproduce` mode suspends Rule 5.

> Rules 1–4 are mandatory; Rule 5 is recommended.

---

## Per-slide Emphasis

Each slide must have an `emphasis` field
(`high` / `standard` / `low`). Defaults: cover/closing/climax →
`high`, `slideType: divider` → `low`, all others → `standard`.
The designer may override when the narrative warrants it.

---

## Background Type

Choose background per the visual rhythm arc (Step 5b):
`solid` / `gradient` / `tinted`. See
[visual-tone-act-treatment.md § 2c](visual-tone-act-treatment.md)
for act-level selection rules.

---

## Zone Types

Every zone declares a `type` that determines which
python-pptx API is called:

| `type`    | python-pptx API                      | Notes                                                      |
| --------- | ------------------------------------ | ---------------------------------------------------------- |
| `text`    | `add_textbox()`                      | Default. Title, body, caption, label zones                 |
| `shape`   | `add_shape()`                        | Decorative: accent bars, dividers, card bgs                |
| `chart`   | `add_chart()`                        | Data visualization; data series in content                 |
| `image`   | `add_picture()` / `add_image_safe()` | Photos, diagrams; path in content                          |
| `icon`    | `add_textbox()` + icon font          | Icon + label pairs                                         |
| `formula` | `add_formula()`                      | Mathtext expression rendered to PNG @ 300dpi at build time |

Formula zones: `notation: "mathtext"` + `source: "authored"` +
`fallback`. See [build-script-template.md § Formula zones](build-script-template.md).

---

## Decoration Design Rules

Decorations are inline `type: "shape"` zones inside each slide's
`layoutSpec` — there is no separate decoration pass and no
`decorations` field. Compose each shape from the canonical
vocabulary in [layout-principles.md § Decoration Vocabulary](layout-principles.md).

1. **Accent intensity matching.** Bold decorations
   (`accent-band`, full-width color blocks) must match the act's
   `accentIntensity`. Reserve `accent-band` for 1–2 highest-impact
   moments per deck.
2. **Decoration cadence — cap is on *identical* compositions.**
   A polished deck should carry decoration on every body slide.
   What it must avoid is the same composition (same primitive +
   same position + same fill token) repeating. Cap and span rules
   live in [layout-principles.md § Decoration cadence](layout-principles.md).
3. **Variety across the act.** For 8+ body slides, use ≥ 4
   distinct decoration *treatments*. When the deck declares a
   `motifPalette` (Rule 5), spend across motif families instead
   of one family with N positions.
4. **avoidKeywords exclusion.** When
   `aestheticSignals.avoidKeywords` semantically rejects a
   decoration family, exclude matching patterns entirely.
5. **Under-title short-rule ban (hard).** Do not draw a
   centered/short horizontal rule directly beneath title text.
   Allowed alternatives: full-width hairline aligned to the layout
   grid, or a left-side vertical accent bar.
