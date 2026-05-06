# Mode Philosophy

The philosophical foundation of this skill: the three-mode design
authority spectrum, the persona behind each mode, and the core
posture that distinguishes a "branded" deck from a generic one.
Consulted at Step 2 (mode determination) and whenever a design
trade-off arises.

---

## Core Posture: the template is the law

This skill exists because someone — a brand team, a design system
owner, a client — invested in a template that encodes how the
organization wants to look. Our job is to **honor that investment**,
not to override it with our own taste.

Three consequences:

1. **The template is upstream of the content.** When the user's
   request and the template's design language conflict, the template
   wins inside its locked dimensions. (The user can override by
   choosing a more permissive mode — but the choice must be explicit.)
2. **Claude is the steward, not the author.** The aesthetic decisions
   were already made; Claude's job is to apply them faithfully across
   new content. "Improving on" the template's color or typography is a
   failure mode, not creativity.
3. **Consistency outranks local optimization.** A divider that looks
   slightly worse but matches every other divider is correct. A
   divider that looks slightly better in isolation but breaks the
   recurring pattern is wrong.

---

## Three Pillars of Brand Authority

Every template encodes three layers, with descending strictness:

| Pillar | Examples | Default authority |
|---|---|---|
| **Brand Identity** | Theme colors, primary fonts, logo placement, slide size, locked footer/disclaimer | **Rule** — never overridden, regardless of mode |
| **Design System** | Layout grid, placeholder positions, typographic scale, spacing tokens, shape vocabulary | **Rule or Reference** depending on mode |
| **Demonstration** | Sample slides showing how the template is used in practice | **Rule, Reference, or Inspiration** depending on mode |

The three modes are exactly the three valid combinations of authority
across these pillars (see Step 2 in SKILL.md).

---

## Three Modes as Personas

Each mode is a **distinct working posture**. When choosing a mode,
ask which persona fits the request.

### Strict — *the content-filling machine*

> "This template was designed by people more qualified than me. My
> job is to put the right words in the right boxes and get out of
> the way."

- **Whose authority:** brand team, regulatory/legal, design system owner.
- **Use when:** regulated content (legal, compliance, financial
  reporting); externally-facing materials where any brand drift is a
  risk; templates with rich sample slides demonstrating every
  intended use.
- **Decisions Claude makes:** which layout to use for each slide; how
  to summarize content to fit existing placeholders.
- **Decisions Claude does NOT make:** colors, fonts, shape choices,
  density, layout invention, augmentation. **No design decisions.**
- **Failure mode:** picking `spec-composed` for anything that could
  fit an existing layout. In strict mode, "no layout fits" is almost
  always wrong — re-examine the layouts first.

### Balanced — *the brand-respecting designer*

> "I follow the style guide, and I interpret the examples. When the
> examples don't quite fit my content, I extend within the rules."

- **Whose authority:** house style guide, with the working designer
  applying judgment.
- **Use when:** standard internal business presentations (strategy
  reviews, project updates, sales materials); the default for
  ambiguous requests.
- **Decisions Claude makes:** layout selection, conservative
  augmentation (extra chart, modified card count), content density,
  spec-composed slides for data visualizations the template doesn't
  cover.
- **Decisions Claude does NOT make:** new colors outside the theme,
  new fonts outside the established scale, new shape vocabulary,
  layout invention.
- **Failure mode:** treating `style-policy.json → aestheticGuidance`
  as suggestion when it should be guidance. In balanced mode, recipes
  may adapt counts and proportions but the **structure and color
  logic must remain recognizable**.

### Creative — *the in-house designer working within brand*

> "The brand identity is sacred — colors and logos and the visual
> tone. Everything else is craft I can practice within those limits."

- **Whose authority:** brand identity (locked); everything else is
  designer-led.
- **Use when:** expressive audience-facing materials (keynotes,
  marketing decks, recruiting); minimal templates (3–5 layouts, no
  sample slides) where the template can only set tone, not pattern.
- **Decisions Claude makes:** layout invention, custom shape
  compositions, color emphasis within the theme, typography
  treatment within the established families, structural augmentation.
- **Decisions Claude does NOT make:** off-theme colors, off-family
  fonts, anything that violates `brand-compliance.md` locked tier.
- **Failure mode:** drifting away from the template's visual family
  while the brand colors and fonts technically match. A "creative"
  slide must still feel like it belongs in the same deck as a
  template sample.

---

## Mode Manifesto

Read at the start of every session. These are absolute, regardless
of mode.

1. **Locked-tier compliance is not negotiable.** Theme colors, fonts,
   slide size, logo placement, footer/disclaimer — these are rules in
   every mode. Creative ≠ permission to break these.
2. **WCAG always.** Title contrast ≥ 3:1, body ≥ 4.5:1, regardless
   of mode. The brand team did not authorize unreadable slides.
3. **One source per recurring slide kind.** Every divider clones the
   same source slide. Cover and closing come from the same family.
   Decided once in `style-policy.json`, not per slide.
4. **Theme references, never hex.** Always reference theme color
   slots (`accent1`, `dk1`, …) so the deck recolors correctly when
   the template is updated. Hex codes are a code smell at best and a
   compliance violation at worst.
5. **Variety across body slides, not within recurring elements.**
   Avoid using the same body layout for every content slide, but
   never sacrifice divider/cover consistency for variety.
6. **When in doubt, downshift.** Creative → balanced → strict.
   Picking a mode more permissive than warranted produces brand
   drift; picking a mode stricter than warranted produces a slightly
   plain deck. The first is a failure; the second is a recoverable
   compromise.

---

## When Modes Conflict with the Request

The user's content purpose is the **primary** signal for mode
selection. The template's richness is a **secondary nudge**.

When they conflict:

- **Content purpose wins.** A regulatory disclosure deck is `strict`
  even if the template has only 4 layouts. A marketing keynote is
  `creative` even if the template has 30 layouts.
- **Surface the trade-off to the user when the conflict is sharp.**
  E.g., "Your template only has 4 layouts and no sample slides, so
  strict mode would produce a very plain deck. Recommend balanced
  unless you have a compliance reason for strict."
- **Default to balanced when unclear.** Balanced is the only mode
  that preserves both brand authority and content adaptability — the
  least-bad choice when the signal is weak.
