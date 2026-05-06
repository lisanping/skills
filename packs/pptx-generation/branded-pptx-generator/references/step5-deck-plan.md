# Step 5 — Plan the Deck

Produce two artifacts in one pass: a slide plan and a shared style
policy. The style policy is the **single source of consistency** across
the deck — every slide later references it instead of re-deciding.

Inputs: `content-outline.json` (Step 4) + `$DIGEST` (Step 1).

## 5a — Build the slide plan

Map each slide slot from `content-outline.json` to a template layout
using `$DIGEST → preferredLayoutHints` and `layoutBehaviorSummary`.

Write `slide-plan.json`:

```json
{
  "mode": "balanced",
  "outline": "Q2 strategy review for execs",
  "slides": [
    {
      "taskId": "s01",
      "title": "Q2 Strategy Overview",
      "semanticRole": "cover",
      "layoutRef": "slideLayout2.xml",
      "strategy": "clone-layout",
      "cloneSource": null,
      "contentBrief": "Deck title + subtitle + date"
    },
    {
      "taskId": "s05",
      "title": "Pillar 2: Customer",
      "semanticRole": "divider",
      "layoutRef": "slideLayout7.xml",
      "strategy": "clone-sample",
      "cloneSource": "slide4.xml",
      "contentBrief": "Section divider for pillar 2"
    },
    {
      "taskId": "s07",
      "title": "Revenue by Region",
      "semanticRole": "content_data",
      "layoutRef": "slideLayout4.xml",
      "strategy": "augmented-clone",
      "cloneSource": "slide6.xml",
      "contentBrief": "KPI layout + added bar chart for regional breakdown"
    },
    {
      "taskId": "s09",
      "title": "Project Timeline",
      "semanticRole": "content_data",
      "layoutRef": "slideLayout4.xml",
      "strategy": "spec-composed",
      "cloneSource": null,
      "styleRef": "slide-design-slide6.json",
      "contentBrief": "6-month Gantt with 4 workstreams"
    }
  ]
}
```

**Strategy rules (pick the lightest that works):**

| Strategy | Starting point | When to use |
|---|---|---|
| `clone-sample` | Sample slide | A sample demonstrates the exact pattern (cards, divider, KPI row). Always use for section dividers, cover, closing |
| `clone-layout` | Layout definition | Standard placeholder slide; layout already fits the content |
| `augmented-clone` | Sample or layout | Layout/sample provides the base, but content needs additions (extra chart, modified card count, added shapes). Clone first, then modify structure |
| `spec-composed` | Layout ref + blank | No layout or sample fits — charts, timelines, infographics built entirely by code |

See [generation-modes.md](generation-modes.md) for the per-dimension
decision matrix (what each mode allows for typography, color, shapes,
density, etc.).

**Mode × strategy availability:**

| Strategy | Strict | Balanced | Creative |
|---|---|---|---|
| `clone-sample` | Preferred for all slides with a matching sample | Preferred for recurring elements (dividers, covers, closings) | Optional; use when a sample genuinely fits |
| `clone-layout` | For slides without a matching sample | Default for body content slides | Starting point, may be heavily customized |
| `augmented-clone` | Forbidden | Allowed (conservative additions only) | Allowed (structural modifications permitted) |
| `spec-composed` | Forbidden unless no layout fits at all | Allowed for data visualizations and complex layouts | Freely available for any slide |

**Consistency rules enforced inside the plan:**

- All section dividers MUST share the same `cloneSource` (or, if none
  exists, the same `layoutRef` + same style policy entry).
- Cover and closing slides should come from the same visual family.
- Slides of the same `semanticRole` use the same `layoutRef` unless the
  user explicitly asked for variation.
- Prefer layout variety over reusing the same content layout for every
  body slide — but never trade variety for inconsistent dividers/covers.

## 5b — Freeze the shared style policy

Write `style-policy.json` once for the whole deck:

```json
{
  "mode": "balanced",
  "palette": {
    "background": "lt1",
    "headingText": "dk1",
    "accent": "accent1",
    "muted": "lt2"
  },
  "typography": {
    "titleSize": 36,
    "bodySize": 14,
    "captionSize": 10,
    "emphasisStyle": "bold"
  },
  "spacing": {
    "marginEMU": 457200,
    "rowGapEMU": 91440
  },
  "dividerSource": "slide4.xml",
  "coverSource": "slide1.xml",
  "closingSource": "slide12.xml",
  "guardrails": {
    "fontSizeTolerance": 0.15,
    "augmentationAllowed": true,
    "augmentationConservative": true
  },
  "designLanguageNotes": "Generous whitespace, left-aligned headings, accent1 used sparingly for emphasis",
  "aestheticGuidance": null
}
```

Pull values from `$DIGEST → designDirectives`, `guardrails`, and
`preferredLayoutHints`. All later steps consult `style-policy.json`
when filling content or writing code.

**Aesthetic guidance enrichment:** When `$DIGEST → aestheticPrinciples`
exists, populate `aestheticGuidance` from it. This becomes the
**single reference** for aesthetic design decisions during generation —
subagents read it instead of the raw digest.

```json
{
  "aestheticGuidance": {
    "compositionRules": "left-aligned titles, centered process rows; 5% edge margins, 2% inter-element gaps",
    "colorRoleMap": [
      { "role": "emphasis_primary", "themeSlot": "accent1", "useWhen": "focal points, CTA, active step" },
      { "role": "structural", "themeSlot": "dk1", "useWhen": "body text, table borders" },
      { "role": "background_primary", "themeSlot": "dk1", "useWhen": "slide backgrounds" }
    ],
    "colorEmphasisProgression": "neutral dk1 → accent1 text → accent1 fill → full-bleed accent1 bg",
    "typeScale": [
      { "role": "display", "sizePt": 96, "weight": "heavy condensed", "font": "Trade Gothic Next HvyCd", "useWhen": "cover/divider hero" },
      { "role": "title", "sizePt": 40, "weight": "bold", "font": "Trade Gothic Next HvyCd", "useWhen": "content slide titles" },
      { "role": "body", "sizePt": 18, "weight": "regular", "font": "Avenir Next LT Pro", "useWhen": "body text and bullets" }
    ],
    "shapeVocabulary": [
      { "shape": "rectangle", "treatment": "sharp corners, flat fill", "primaryUse": "content cards" },
      { "shape": "hexagon", "treatment": "thin accent1 outline, transparent", "primaryUse": "icon containers" }
    ],
    "applicableRecipes": [
      { "patternFamily": "horizontal_process", "description": "N equal-width cards in row...", "...": "..." }
    ]
  }
}
```

Data source mapping:
- `compositionRules` ← `aestheticPrinciples.compositionSummary.alignmentAnchors`
  + `marginStrategy` formatted as prose
- `colorRoleMap` ← `aestheticPrinciples.colorSummary.roleAssignment`
- `colorEmphasisProgression` ← `aestheticPrinciples.colorSummary.colorEmphasisProgression`
- `typeScale` ← `aestheticPrinciples.typographySummary.scaleStops`
- `shapeVocabulary` ← `aestheticPrinciples.shapeSummary.primitiveVocabulary`
- `applicableRecipes` ← `aestheticPrinciples.patternRecipes`, **filtered**:
  include only recipes whose `patternFamily` is relevant to at least one
  slide in `slide-plan.json` (match by `semanticRole` and `strategy`).
  For example, include `horizontal_process` if any slide has
  `semanticRole: "content_data"` with `strategy: "spec-composed"`.

When `$DIGEST → aestheticPrinciples` is absent, set
`aestheticGuidance: null` — the generator falls back to
`designLanguageNotes` and `designDirectives` (existing behavior).

**Mode-dependent guardrails lookup** (set in `guardrails` based on mode):

| Guardrail | Strict | Balanced | Creative |
|---|---|---|---|
| `colorRoleBinding` | `locked` | `reassignable-within-theme` | `free-within-theme` |
| `typographicScale` | `locked` | `use-existing-set` | `font-families-locked` |
| `shapeVocabulary` | `locked` | `template-shapes-only` | `match-visual-weight` |
| `augmentation` | `disabled` | `conservative` | `exploratory` |
| `layoutInvention` | `disabled` | `disabled` | `enabled` |
| `aestheticAdherence` | `recipes-as-law` | `recipes-as-guidance` | `recipes-as-inspiration` |

`aestheticAdherence` governs how strictly `patternRecipes` from
`aestheticGuidance` are followed:
- **`recipes-as-law`**: When a matching recipe exists, the generated
  slide must follow its skeleton, colorAssignment, and spacingSpec
  exactly. No deviation from the recipe structure.
- **`recipes-as-guidance`**: Recipes are the preferred starting point.
  May adapt item counts via `scalingRules`, adjust proportions to fit
  content, or combine elements from multiple recipes — but the overall
  pattern structure and color logic should remain recognizable.
- **`recipes-as-inspiration`**: Recipes inform the design direction but
  do not constrain it. May invent new patterns that follow the
  `shapeGrammar` and `colorSemantics` principles.

**Checkpoint:** `slide-plan.json` and `style-policy.json` exist;
each slide in the plan traces back to a slot in `content-outline.json`;
plan respects the consistency rules above.

## 5c — Generate slide content

Produce `slide-content.json` — the full text content for every slide,
sized to fit within each layout's placeholder capacity.

Inputs: `slide-plan.json` (Step 5a) + `$PROFILE` (placeholder dimensions
and slot counts per layout) + user-supplied materials (if any).

**Content sources (choose per slide):**

| Source | When |
|---|---|
| **User-provided** | User uploaded documents, data, or detailed text — extract, restructure, and map to slide slots |
| **Generated** | User gave only a topic/brief — LLM generates content that matches the intent and tone |
| **Hybrid** | Some data from user, remaining narrative generated to fill the structure |

**Capacity-aware sizing:**

For each slide, read the target layout's placeholders from `$PROFILE`
(`w_pct`, `h_pct`, `font_size_pt`) and convert to absolute dimensions
using `$PROFILE → identity.slide_size`. Then compute `charBudget`:

```
charBudget = floor(chars_per_line × lines × 0.85)

where:
  width_pt       = w_pct × slide_width_pt
  height_pt      = h_pct × slide_height_pt
  eff_w          = width_pt  − (leftInset_pt + rightInset_pt)   # default inset ≈ 7.2 pt
  eff_h          = height_pt − (topInset_pt  + bottomInset_pt)
  chars_per_line = eff_w / (fontSize_pt × charWidthFactor)
  lines          = eff_h / (fontSize_pt × lineSpacing)
```

| Parameter | Latin | CJK | Mixed (e.g. 70% CJK) |
|---|---|---|---|
| `charWidthFactor` | 0.55 | 1.0 | weighted avg (0.865) |
| `lineSpacing` | 1.2 default; read `<a:lnSpc>` if set | | |

All text must stay within its `charBudget`. If content is too long,
summarize or split across slides — never rely on auto-shrink.

**Cross-slide consistency (critical):**

All content is authored in a single pass so that facts, figures, and
terminology stay consistent across the entire deck:

- **Numbers must match.** If slide 4 says revenue is "$16.2B", then
  slide 2's executive summary must reference the same figure.
- **Terminology must be stable.** If one slide calls it "Digital
  Transformation", every other slide uses the same label — not
  "DX", "Digitization", or "Digital Strategy" interchangeably.
- **Narrative coherence.** The executive summary must accurately
  preview what the body slides will say. The closing must reflect
  the actual asks presented in the body.
- **KPI consistency.** Each metric appears with the same value,
  unit, and comparison basis everywhere it's referenced.

Write `slide-content.json`:

```json
{
  "slides": [
    {
      "taskId": "s04",
      "title": "Financial Highlights",
      "contentSource": "generated",
      "slots": [
        {
          "placeholder": "title",
          "text": "Financial Highlights",
          "charBudget": 40
        },
        {
          "placeholder": "cell1_number",
          "text": "$16.2B",
          "charBudget": 8
        },
        {
          "placeholder": "cell1_label",
          "text": "Revenue",
          "charBudget": 20
        },
        {
          "placeholder": "cell1_detail",
          "text": "+3% vs target | YoY: +8.4%",
          "charBudget": 40
        }
      ]
    }
  ],
  "glossary": {
    "revenue_q2": "$16.2B",
    "ebitda_q2": "$2.8B",
    "pillar1_name": "Digital Transformation",
    "pillar2_name": "Market Expansion",
    "pillar3_name": "Operational Excellence"
  }
}
```

The `glossary` is a flat key-value map of every named entity and
number used across the deck. Before finalizing, scan all `slots[].text`
values against the glossary to verify no contradictions.

**Agenda slide content (page numbers deferred):**

If the deck includes an agenda slide whose template layout shows
per-section page numbers, generate the section name slots here but
**leave page-number slots as `"TBD"`**. Actual page numbers depend on
the final slide order after Step 8 assembly (sample slide removal +
reorder). They will be computed and patched in Step 8 sub-step 6.

```json
{
  "taskId": "s02",
  "title": "Agenda",
  "contentSource": "generated",
  "slots": [
    { "placeholder": "agenda_item_1", "text": "Q2 Performance", "charBudget": 30 },
    { "placeholder": "agenda_page_1", "text": "TBD", "charBudget": 4 },
    { "placeholder": "agenda_item_2", "text": "Strategic Pillars", "charBudget": 30 },
    { "placeholder": "agenda_page_2", "text": "TBD", "charBudget": 4 }
  ]
}
```

**Checkpoint:** `slide-content.json` exists; every `taskId` in
`slide-plan.json` has a matching entry; all `slots[].text` values
fit within their `charBudget`; glossary terms are consistent
across all slides.

Run the Step 5 validator:

```bash
python $SKILL/scripts/validate_plan.py "$SESSION" --profile $PROFILE
```

Checks JSON Schema, taskId uniqueness, bookends, divider consistency,
mode×strategy legality, layoutRef existence in the profile, palette
theme-slot usage, and plan/policy mode alignment.
