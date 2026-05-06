# Layout Design Principles

Reference rules for Step 5d (Slide Visual Design). The LLM designs
each slide's layout from scratch, guided by these principles and
the slide's actual content from `s04-content-draft.json`.

**Design from content, then name.** Every `layoutSpec` is
composed directly by the LLM — zone positions, sizes, background
treatments, and decorative shapes are all reasoned from content
structure, narrative role, and visual rhythm. There is no
pre-existing layout library to select from; the tables below
describe a *design vocabulary*, not a catalog. After designing
a layout, the LLM assigns a descriptive `layoutPattern` name
for traceability (e.g. `"asymmetric-stat-hero-band"`). Slides
with similar content structure may intentionally share a
`layoutPattern` name — this is legitimate when the similarity
is content-driven and noted in `designRationale`.

---

## Coordinate System

> **Canonical convention:** see SKILL.md § Step 5 — Visual planning.
> This file's examples follow that contract; do not duplicate the
> rule definition here.

All zone coordinates are written in **inches** (matching the
`add_textbox` / `add_picture` API in `python-pptx`). Bare numeric
values (`"w": 8.0`) are inches. The optional string suffix
`"<N>%"` (e.g. `"w": "44%"`) is resolved against the slide
canvas at render time — use it only when a value is genuinely
proportional (full-bleed bands, edge-anchored decoration).

Reference canvas: `s01d-design-config.json → dimensions` (default
**13.333" × 7.5"** for 16:9). All inch values below assume this
canvas; scale proportionally if the deck uses a different size.

Thin decorative elements (accent bars, divider lines) should use
absolute inches (e.g. `"h": 0.06`) so their visual weight stays
constant regardless of canvas size.

---

## Grid System

All values below are **inches** on the default 13.333" × 7.5"
canvas. Parenthetical percentages are proportional hints for
scaling to other canvas sizes.

### Margins

| Edge   | Minimum    | Recommended       |
| ------ | ---------- | ----------------- |
| Left   | 0.5" (≈4%) | 0.7–0.8" (≈5–6%)  |
| Right  | 0.5" (≈4%) | 0.7–0.8" (≈5–6%)  |
| Top    | 0.3" (≈4%) | 0.4–0.6" (≈5–8%)  |
| Bottom | 0.3" (≈4%) | 0.45–0.6" (≈6–8%) |

Content zones must not bleed into margins. Decorative shapes
(accent bars, side stripes, full-bleed images) may extend to the
edge (`x: 0`).

### Gutters (inter-zone spacing)

| Context          | Minimum     | Recommended       |
| ---------------- | ----------- | ----------------- |
| Between columns  | 0.4" (≈3%)  | 0.5–0.8" (≈4–6%)  |
| Between rows     | 0.15" (≈2%) | 0.25–0.4" (≈3–5%) |
| Title to body    | 0.15" (≈2%) | 0.25–0.4" (≈3–5%) |
| Body to footnote | 0.15" (≈2%) | 0.15–0.3" (≈2–4%) |

### Column Templates (guidance, not requirements)

These are common column splits the LLM may use (inch widths on
the default canvas). Custom splits are equally valid when content
demands them.

| Layout        | Left widths | Right width | Notes                        |
| ------------- | ----------- | ----------- | ---------------------------- |
| Symmetric     | 5.87"       | 5.87"       | Equal weight, ~0.5" gutter   |
| Asymmetric 60 | 7.2"        | 4.5"        | Primary left, support right  |
| Asymmetric 70 | 8.27"       | 3.47"       | Dominant left, sidebar right |
| Thirds        | 3.73" × 3   | —           | Equal three-column           |
| Golden ratio  | 7.47"       | 4.53"       | Pleasing asymmetry           |
| Sidebar       | 9.6"        | 2.4"        | Main content + narrow accent |

### Vertical Regions

| Region       | y range (inches) | Purpose                     |
| ------------ | ---------------- | --------------------------- |
| Title band   | 0.3"–1.35"       | Slide title, accent bar     |
| Content area | 1.35"–6.6"       | Body content zones          |
| Footer area  | 6.6"–7.2"        | Footnotes, source citations |

These are defaults. The LLM may adjust when content demands it
(e.g. a hero stat-callout may push the title higher and use a
full-height accent band).

---

## Zone Design Rules

### Required zones

Every non-divider slide must have a `title` zone. Body slides
must have at least one content zone.

### Zone types

| `type`  | python-pptx API                      | When to use                       |
| ------- | ------------------------------------ | --------------------------------- |
| `text`  | `add_textbox()`                      | Title, body, caption, label, code |
| `shape` | `add_shape()`                        | Decorative: accent bars, card bgs |
| `chart` | `add_chart()`                        | Data visualizations               |
| `image` | `add_picture()` / `add_image_safe()` | Photos, diagrams                  |
| `icon`  | `add_textbox()` + icon font          | Icon + label pairs                |

### Zone attributes

Every zone must declare:

```json
{
  "role": "left-body",          // unique name, used as slot key in s06-slide-content.json
  "type": "text",               // determines python-pptx API
  "x": 0.7, "y": 1.5, "w": 5.6, "h": 5.1,  // inches (see Coordinate System)
  "font": "body",              // "heading", "body", or "mono" — resolved from style-policy
  "size": "body",              // size token or raw point value
  "color": "text",             // palette key from style-policy
  "align": "left",             // horizontal: "left", "center", "right"
  "valign": "top"              // vertical: "top", "middle", "bottom"
}
```

For shape zones, add: `shape`, `fill`, optionally `rectRadius`,
`transparency`.

For image zones, omit font/size/color; add `alt` if known.

### Role naming conventions

Use descriptive, content-oriented names:

| Good role names               | Bad role names     |
| ----------------------------- | ------------------ |
| `title`, `subtitle`           | `zone-1`, `zone-2` |
| `left-body`, `right-body`     | `text-a`, `text-b` |
| `stat-1`, `stat-2`, `stat-3`  | `number-zone`      |
| `code`, `explain-list`        | `content-left`     |
| `card-1`, `card-2`, `card-3`  | `box-1`, `box-2`   |
| `diagram`, `callout-1`        | `image-zone`       |
| `step-1`, `step-2`, `arrow-1` | `flow-part`        |

---

## Typography Scale

The LLM references tokens from `s05b-style-policy.json → typography.scale`:

| Token      | Typical size | Usage                        |
| ---------- | ------------ | ---------------------------- |
| `display`  | 44–54pt      | Cover titles, hero numbers   |
| `heading1` | 28–36pt      | Slide titles                 |
| `heading2` | 20–26pt      | Section titles, card headers |
| `body`     | 14–16pt      | Body text, lists             |
| `caption`  | 10–12pt      | Footnotes, source citations  |

Raw point sizes may be used when tokens don't fit. Minimum text
size: **10pt** (below this, text becomes unreadable in projection).

> **Quota 4 enforcement (mandatory).** The Universal Design Floor's
> typographic-punch quota counts ONLY zones whose `size` field is
> the literal string `"display"`. Numeric values (e.g. `"size": 54`)
> are visually equivalent but **do not count toward the quota** —
> the validator checks `z.get("size") == "display"` literally.
> Always use the token form on cover / climax / hero titles:
>
> ```json
> { "role": "title", "size": "display", ... }   // counts ✓
> { "role": "title", "size": 54,        ... }   // does NOT count ✗
> ```
>
> Same rule applies to `heading1` / `heading2` / `body` / `caption`
> when downstream telemetry or future quotas key off the token name.

### Font tokens

- `heading` → `s05b-style-policy.json → typography.headingFont`
- `body` → `s05b-style-policy.json → typography.bodyFont`
- `mono` → `s05b-style-policy.json → typography.monoFont`

---

## Background Treatments

Each slide specifies a `background` in its `layoutSpec`:

### Solid
```json
{ "type": "solid", "color": "background" }
```
Palette key from `s05b-style-policy.json → palette`.

### Gradient
```json
{
  "type": "gradient",
  "colors": ["primary", "accent"],
  "direction": "to-bottom-right"
}
```
Direction options: `to-bottom`, `to-right`, `to-bottom-right`,
`to-bottom-left`.

### Tinted
```json
{
  "type": "tinted",
  "base": "background",
  "tint": "primary",
  "tintOpacity": 0.08
}
```
`tintOpacity` must be ≤ 0.20 (higher values compete with content).

### Background rhythm

Vary backgrounds across the deck to create visual rhythm:
- **Act openings** (section breaks, dividers) → gradient or
  solid-dark for dramatic contrast
- **Evidence/analysis slides** → light/tinted backgrounds that
  don't compete with data
- **Climax slides** → bold background (gradient, accent solid)
  to signal importance
- **Adjacent slides** should rarely share the same background
  treatment

> **Text-color rule for image backgrounds:** any text zone overlaying
> an `image-generated` background (full-bleed or partial-with-scrim)
> MUST use a light palette token (`background` / `backgroundAlt` /
> `surface`). Dark semantic tokens (`secondary`, `accent2`, `text`,
> `textMuted`, `primary`) render invisible on typical dark/atmospheric
> images regardless of scrim opacity. Full rule and rationale:
> [design-guardrails.md § Text-on-image colors](design-guardrails.md#text-on-image-colors-mandatory).

---

## Decoration Vocabulary

Decorations are shape zones that add visual structure without
carrying content. The LLM composes them freely. Common patterns:

| Decoration       | Implementation                                       | When to use                         |
| ---------------- | ---------------------------------------------------- | ----------------------------------- |
| Accent bar       | Thin rectangle (h: `"0.04in"`) under title           | Title emphasis, visual anchor       |
| Side stripe      | Narrow vertical rectangle (w: 0.3–0.6") at left edge | Framing, structural slides          |
| Card background  | Rounded rectangle behind content groups              | Grouping related items              |
| Surface card     | Subtle tinted rectangle behind content               | Elevating content sections          |
| Number highlight | Colored circle/oval with centered number             | Stat callouts, step indicators      |
| Divider line     | Thin horizontal line between sections                | Visual separation                   |
| Top gradient bar | Gradient-filled rectangle across top                 | Visual weight, branding             |
| Accent band      | Full-width colored rectangle                         | High-impact moments (use sparingly) |
| Corner accent    | Small geometric shape at corner                      | Subtle visual interest              |
| Footer band      | Thin rectangle at bottom                             | Source attribution, page numbers    |

The decorations above are design vocabulary, not a catalog to
select from. The LLM designs each decorative shape inline as a
`zone` with `type: "shape"`, explicit `x/y/w/h`, a `shape`
(rectangle, ellipse, roundedRectangle, etc.), and a `fill`
palette key — composed directly in the slide's
`layoutSpec.zones` array.

### Decoration intensity rules

- **`accent-band`** (full-width color block): reserve for 1–2
  highest-impact slides per deck. Overuse dilutes impact.
- Match decoration weight to the act's `accentIntensity`:
  low → subtle (accent bar, divider line);
  medium → moderate (card bg, side stripe);
  high → bold (accent band, gradient bar).
- Within any 3 consecutive body slides, avoid repeating the
  exact same decoration composition.

### Decoration cadence — the cap is on *identical* compositions

The cap that follows is **not** a ceiling on decoration presence.
A polished deck *should* carry decoration on every body slide;
what it must avoid is the same decoration composition repeating
until it reads as visual noise. The rule:

- **≤ 40% of body slides may share the same decoration
  composition.** A composition is the same when (a) the shape
  primitive (e.g. accent-bar, side-stripe), (b) the position
  (top vs bottom, left vs right edge, etc.), AND (c) the fill
  token all match. Two `accent-bar` zones — one under the title
  and one along the bottom edge — count as **different**
  compositions.
- **Identical-composition span cap.** Within any 3 consecutive
  body slides, the same composition may not appear in all 3.
  Two-in-three is fine; three-in-three is a quota failure.
- **Body-slide decoration coverage floor.** When the deck's
  `motifPalette` (Rule 5) declares one or more motifs, **every**
  body slide should carry at least one decoration zone
  (shape / accent / motif) drawn from the palette. Bare
  title-and-text slides are permitted only as breathing slides
  (Rule 3) or when explicitly justified in `designRationale`.

### Accent-bar specifics

The accent bar is the most-overused decoration in default
PowerPoint output. The cadence rule above already governs
*identical* accent-bar usage; the points below are accent-bar–
specific guidance for picking it as the right tool:

- **Preferred placement:** high-impact moments (act openers,
  key argument slides, hero slides). Omit on quieter slides
  (supporting evidence, transitional, data-dense).
- **Alternatives for title emphasis:** bold color on the title
  text itself, a side stripe, a subtle top gradient bar, or
  simply generous whitespace above the title.
- **Vary position when reusing the form.** When the bar primitive
  appears on more than one slide, vary its anchor (under-title,
  bottom-edge, left-stripe) and width so adjacent slides do not
  read as carbon copies.

### Accent-bar color context

Accent-bar fill must harmonize with the slide's own background
and palette context — **not default to a single palette token
across the entire deck.**

- **Dark / image backgrounds:** use `text-on-primary`, `accent`,
  or a light contrasting tone that reads against the background.
- **Light backgrounds:** use `accent` or `primary` — whichever
  provides sufficient contrast (WCAG ≥ 3:1 against bg).
- **Tinted / surface backgrounds:** derive from the tint's
  complementary or from `secondary` to avoid blending in.
- **Per-act color variation:** when the color temperature
  strategy shifts across acts (e.g. `cool-to-warm`), accent-bar
  color may shift in tandem — use `accent` in early acts,
  `primary` or a warmer palette token in later acts.

### Generated imagery as a design tool

Decoration is normally composed from shape primitives (`accent-bar`,
`surface-card`, `gradient-band`). When primitives genuinely cannot
serve — a metaphor, a hero photograph, an abstract atmospheric
backdrop for cover/closing — reach for **LLM-generated imagery**
via Step 5f. There is no cap on image count; generate as many as
the narrative demands. The decision to illustrate is made upstream
(Step 3 `illustrationIntent`, Step 4 `illustrationSpec`), not at
layout time — Step 5d reads the spec and designs zones accordingly.

> **Quotas — how many slides MUST carry imagery** are governed by
> the Imagery Floor in
> [visual-tone-impact-imagery.md § Imagery Floor](visual-tone-impact-imagery.md).
> This section covers *when* to choose generated imagery as a
> design move; that file covers *how much* is mandatory per
> declared `imageryDemand`.

**Two image pathways into body slides:**

1. **`illustrationSpec` from Step 4** (primary pathway). The
   spec declares `imageCount`, `placement`, and
   `contentInteraction`. Step 5d decides `imageShape` and designs
   image zones to match.
   This covers hero panels, comparison diptychs, portrait grids,
   banner strips, and all other body-slide illustration needs.
2. **Designer judgment in Step 5d** (secondary). The LLM may add
   an image zone even when Step 3/5 didn't flag one — e.g. when
   the visual rhythm arc needs a hero moment and no nearby slide
   carries imagery. Record the reason in `designRationale`.

**Backgrounds** (cover, closing, divider) are handled separately
by `structuralFamily.*BackgroundType` — not by `illustrationSpec`.

**Use generated imagery when:**

- The slide has `illustrationSpec.source: "to-generate"`.
- Cover / closing needs photographic or illustrative atmosphere.
- A `full-bleed-image` or `top-image-bottom-text` content form has
  no user-provided media to fill it.
- Narrative requires a metaphor that abstract shapes cannot carry.

**Skip generation when:**

- A user-provided image in `mediaAttachments` already covers the
  slot — always prefer real media.
- The slide's purpose is data / instruction / code (charts,
  diagrams, code blocks are clearer than illustration).
- A shape primitive (gradient-band, surface-card, accent-band)
  would communicate the same intent at zero cost.

Every generated image zone or background MUST declare a
`fallback` (alternate background type, or text-zone reflow) so the
build degrades gracefully on generation failure. Full procedure,
schema, and prompt-authoring rules:
[step5f-image-generation.md](step5f-image-generation.md).

---

## Content-Form-Driven Design

Step 4's `contentForm` is the **primary input** for layout design.
The LLM reads the content's inherent structure and designs zones
to match:

### Design heuristics by content form

| `contentForm.type`    | Design approach                                                                                                                     |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `text-narrative`      | 1–2 text zones; consider asymmetric split if long, single wide zone if short                                                        |
| `bullet-list`         | Single column for ≤4 items; two columns for 5–8; icon+text rows for visual interest                                                 |
| `stat-callout`        | Large number zones with display font; accent band or card backgrounds; 2–4 stats across                                             |
| `comparison-matrix`   | Grid of zones matching rows×columns; header row + data cells; card backgrounds for grouping                                         |
| `timeline`            | Horizontal step zones with connector arrows; milestone count determines zone count                                                  |
| `step-flow`           | Horizontal or vertical flow with numbered badges and arrow connectors                                                               |
| `architecture-layers` | Stacked zones top-to-bottom; labeled layers with different tints; arrows between layers                                             |
| `code-walkthrough`    | Dark code frame (~7.3–8" wide) + light explanation panel; monospace font for code zone                                              |
| `diagram-callouts`    | Image zone (~6.7–8" wide) + numbered callout badges with text                                                                       |
| `before-after`        | Two equal panels side-by-side with labels; divider line or contrasting backgrounds                                                  |
| `card-grid`           | Equal-sized card zones in grid; 2×1, 3×1, 2×2, or 3×2 depending on card count                                                       |
| `quote`               | Large centered text zone with display font; attribution below; generous whitespace                                                  |
| `data-visualization`  | Chart zone (~8–9.3" wide, large area) + insight text zone + optional data source caption                                            |
| `icon-list`           | Icon circles + label+description text pairs in rows; 2–3 columns for many items                                                     |
| `full-bleed-image`    | Image zone covering the full canvas (`x: 0, y: 0, w: 13.333, h: 7.5`) with optional text overlay zone (semi-transparent background) |

These are starting points. The LLM should adapt based on actual
content volume (`contentMetrics.wordCount`), emphasis level, and
the slide's position in the visual rhythm arc.

### Item count → zone count mapping

| Content items | Zone strategy                                            |
| ------------- | -------------------------------------------------------- |
| 1             | Single wide zone or hero treatment                       |
| 2             | Two-column or before-after                               |
| 3             | Three-column, card trio, or triangular arrangement       |
| 4             | 2×2 grid or four-card row                                |
| 5–6           | 2×3 grid, 3×2 grid, or 2-column stacked                  |
| 7+            | Consider icon-list compact layout or split across slides |

---

## Geometric Safety Rules (enforced by s05_validate_plan.py)

These are **hard constraints** that the validator checks:

1. **Bounds:** every zone must fit within the slide canvas.
   `x + w ≤ slideWidth`, `y + h ≤ slideHeight` (13.333" × 7.5"
   on the default canvas).
2. **No text-zone overlap:** text zones must not intersect.
   Shape zones may overlap text zones (they're background
   decorations rendered first via z-order).
3. **Minimum zone size:** text zones should be at least 1" wide
   and 0.4" tall to be readable.
4. **Margin respect:** text zone edges should maintain ≥ 0.5"
   from slide edges (decorative shapes exempt).

### Avoiding common geometric mistakes

- **Don't exceed canvas width.** On the 13.333" canvas, if the
  left column is `x=0.7, w=5.87`, it ends at 6.57"; with a 0.5"
  gutter the right column starts at 7.07" and `w` should be
  ≤ 5.6" (7.07 + 5.6 = 12.67, leaving 0.66" right margin).
- **Verify row stacking.** Title at `y=0.4, h=0.9` → body starts
  at `y ≥ 1.3`. Don't start body at `y=1.2` (overlap).
- **Account for decorations.** An accent bar at `y=1.25, h=0.06`
  occupies negligible height but still exists. Start the next
  zone 0.1–0.15" below.

