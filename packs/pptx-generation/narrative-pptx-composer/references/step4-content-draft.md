# Step 4 — Content Draft & Form Specification

Full procedural detail for Step 4. See [SKILL.md](../SKILL.md)
for the mandatory rules summary.

Produce per-slide content and determine the precise content
presentation form for each slide. This step sees the actual
content before any visual design decisions, enabling form choices
(e.g. "3-milestone timeline", "4×2 comparison matrix",
"5-step horizontal flow") that are grounded in real data.

---

## 4a — Build the Terminology & Data Registry

Construct `s04a-terminology-registry.json` — the single source of truth
for all named entities, data points, and abbreviations
(see [../schemas/s04a-terminology-registry.example.json](../schemas/s04a-terminology-registry.example.json)).

**Two-phase execution.** Registry construction wraps Step 4b:

- **4a-seed (before 4b):** initialize the registry from
  `s01c-content-digest.json → preGlossary`. This is the working
  registry that 4b reads while drafting.
- **4a-finalize (after 4b):** merge any new canonical terms / data
  points coined by 4b (across all batches if batching) into the
  registry. This is the final artifact `s04_validate_content.py`
  validates against.

No separate file is written for the seed phase — the same
`s04a-terminology-registry.json` is appended-to and finalized in place.

**Structural reminder (load-bearing):** `namedEntities` is a **dict
keyed by stable id**, with each value an object `{canonical, rejected}`.
It is *not* `{namedEntities: {canonical: [...], rejected: [...]}}`. The
flat shape will be rejected by `s06_validate_content.py` with a pointer
back to the example file.

### Content Grounding Fields (mandatory on every `dataPoints` entry)

Every data point **must** carry two grounding fields:

| Field              | Type   | Values / range                                       | Required |
| ------------------ | ------ | ---------------------------------------------------- | -------- |
| `verificationTier` | string | `"verified"` · `"common-knowledge"` · `"unverified"` | Yes      |
| `confidence`       | float  | 0.0 – 1.0                                            | Yes      |

**Tier definitions:**

| Tier               | When to use                                                                                        | Typical `confidence` |
| ------------------ | -------------------------------------------------------------------------------------------------- | -------------------- |
| `verified`         | Value is extracted verbatim from a user-supplied document (`contentSource: "document"`)            | 0.95 – 1.0           |
| `common-knowledge` | Widely accepted fact that the LLM can state with high certainty (e.g. "the Eiffel Tower is 324 m") | 0.8 – 0.95           |
| `unverified`       | LLM-generated number, statistic, or claim with no document backing and no universal consensus      | 0.3 – 0.7            |

**`qualitativeForm` (conditional).** When `confidence < 0.7` **and**
the `value` is a precise number (no approximation marker like `~`,
`≈`, `about`), the entry **must** include a `qualitativeForm` string
— a hedged or approximate alternative (e.g. `"nearly 40%"`,
`"approximately 300 m"`). `s04_validate_content.py` checks field
presence.

**Brief-only mode:** when no content documents are provided, most
data points will be `common-knowledge` or `unverified`. The LLM
should prefer `common-knowledge` only for facts it can state with
genuine confidence. When uncertain, use `unverified` + provide
`qualitativeForm`.

---

## 4b — Author Content Draft

For each slide in `s03-presentation-blueprint.json`, write the actual
content: headline text, supporting body text, data points, and
evidence.

### Batching (large decks)

Follow [batching-strategy.md](batching-strategy.md). Post-merge:
verify slide id coverage, canonical terminology, no duplicate
headline openers across boundaries.

### Terminology consistency

Use `canonical` forms from `s04a-terminology-registry.json`
throughout all Step 4 output — body text, supporting points, and
slide titles. If a `rejected` variant appears in a headline from
`s03-presentation-blueprint.json`, replace it with the `canonical`
form when writing the slide title in `s04-content-draft.json`.
Never modify `s03-presentation-blueprint.json` itself.

### Content Sources (per slide)

| `contentSource` | Behavior                                                                                                                                                        |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `document`      | Extract and restructure text from `s01c-content-digest.json → mergedSections`. All facts must be traceable to source. Summarization allowed; fabrication is not |
| `generated`     | LLM generates content (cover, closing, dividers, executive summary). Must be consistent with document data via `s04a-terminology-registry.json`                 |
| `hybrid`        | Document provides data/facts, LLM provides framing and narrative. All numbers from registry                                                                     |

### Content Density Guidance

The blueprint's `informationDensity` field is the primary guide for
how much content each slide should carry. Content drives layout,
not the other way around.

| `informationDensity` | Body text guidance                                    | Max body points | Whitespace |
| -------------------- | ----------------------------------------------------- | --------------- | ---------- |
| `minimal`            | Title + one sentence or tagline                       | 1–2             | > 55%      |
| `light`              | 2–3 short points or a brief paragraph                 | 3–4             | ~40%       |
| `medium`             | 4–6 points, standard paragraphs, or a structured list | 5–7             | ~30%       |
| `dense`              | Data-heavy, multi-column, compact text                | 8–10            | ~20%       |

If content significantly exceeds what `informationDensity` allows,
summarize or split across slides — do not pack a slide beyond its
density tier.

#### Headline message — verbatim from blueprint

Carry `headlineMessage` from `s03-presentation-blueprint.json`
verbatim. Do not shorten or adapt based on assumed zone size —
that belongs to Step 6a.

### When to author `blocks[]`

Author `blocks[]` when `contentForm.type` is multi-zone:
`card-grid`, `comparison-matrix`, `timeline`, `step-flow`,
`stat-callout`, `architecture-layers`, `before-after`,
`diagram-callouts`, `icon-list`. Use role conventions:
`card-N`, `cell-rNcN`, `phase-N`, `step-N`, `stat-N`,
`layer-N`, `before`/`after`, `callout-N`, `item-N`.

Single-zone layouts (`text-narrative`, `bullet-list`, `quote`,
etc.) leave `blocks` empty.

### Cross-slide Consistency

- Numbers must match `s04a-terminology-registry.json → dataPoints`.
- Use only `canonical` forms; no `rejected` variants.
- Executive summary must preview body slides. Closing must
  reflect actual asks.
- Each slide's title must faithfully render `headlineMessage`.

### Agenda Slide Content (page numbers deferred)

Agenda page-number slots use the em-dash sentinel `"—"`. Do **not**
use the literal string `"TBD"` — `s06_validate_content.py` hard-fails
on it.

### Image / Media Content

When the blueprint assigns `mediaAttachments` to a slide, include
them in the content draft:

```json
{
  "ref": "images/fig03-coding-harness-layers.png",
  "type": "image",
  "alt": "Three layers of a coding harness",
  "placement": "primary-visual"
}
```

- `placement: "primary-visual"` tells Step 5 to select a
  composition with an image zone.
- **Step 4 only declares** the attachment. Missing-image fallback
  is handled downstream; Step 4 does not need to plan for it.

---

## 4c — Determine Content Form (mandatory)

For each slide, analyze the **actual content structure** and specify
a `contentForm` — a structured description of the optimal
visualization or layout form. This is a **content decision**, not a
design decision: the content's inherent structure determines the form.

### Content Form Schema

```json
{
  "type": "<form-type>",
  ...type-specific fields...
}
```

### Form Type Catalog

| `type`                | When to use                                           | Type-specific fields                               |
| --------------------- | ----------------------------------------------------- | -------------------------------------------------- |
| `cover`               | Title slide / opening                                 | _(no count fields)_                                |
| `divider`             | Act / section divider                                 | _(no count fields)_                                |
| `closing`             | Closing slide / call-to-action                        | _(no count fields)_                                |
| `agenda`              | Agenda / table of contents                            | _(no count fields)_                                |
| `text-narrative`      | Prose content, no inherent spatial structure          | `paragraphs` (int)                                 |
| `bullet-list`         | Discrete points without relational structure          | `items` (int), `hasIcons` (bool)                   |
| `stat-callout`        | Key numbers/metrics as hero elements                  | `stats` (int)                                      |
| `comparison-matrix`   | Side-by-side comparison of items on shared dimensions | `rows` (int), `columns` (int), `hasHeaders` (bool) |
| `timeline`            | Sequential events over time                           | `milestones` (int), `hasDescriptions` (bool)       |
| `step-flow`           | Sequential process steps                              | `steps` (int), `hasIcons` (bool)                   |
| `architecture-layers` | Stacked/nested system components                      | `layers` (int), `hasLabels` (bool)                 |
| `code-walkthrough`    | Code + explanation                                    | `codeBlocks` (int), `explanationPoints` (int)      |
| `diagram-callouts`    | Visual diagram with annotation points                 | `calloutCount` (int)                               |
| `before-after`        | Two-state comparison                                  | `hasLabels` (bool)                                 |
| `card-grid`           | Multiple items of equal weight                        | `cards` (int), `hasIcons` (bool)                   |
| `quote`               | Featured quotation                                    | `hasAttribution` (bool)                            |
| `data-visualization`  | Chart or data graphic                                 | `chartType` (str), `dataPoints` (int)              |
| `icon-list`           | Icon + label pairs                                    | `items` (int)                                      |
| `full-bleed-image`    | Image as primary visual                               | `hasOverlayText` (bool)                            |

Structural slides (cover / divider / closing / agenda) carry their
own form id with no count fields — the visual treatment is decided
in Step 5 from `slideType` + bookend rules, not from `contentForm`.

When body content has no inherent spatial structure, use
`"type": "text-narrative"` or `"type": "bullet-list"`.

### Content Metrics (auto-derived — do not hand-fill)

`contentMetrics` (`wordCount`, `dataPointCount`, `bulletCount`,
`hasImage`) are computed by `s04_validate_content.py` and written
back automatically. Leave the field absent or empty.

### Illustration Spec (when `illustrationIntent.needed` is true)

Refine Step 3's `illustrationIntent` into an actionable
`illustrationSpec` using the actual written content.

**Precedence:** `mediaAttachments` > `illustrationSpec`. If slide
has `mediaAttachments` with `primary-visual`/`supporting-visual`,
drop or demote illustration to `background`.

Refinement: read `illustrationIntent`, refine `subject` with
content details, add `compositionNote` (spatial guidance) and
`contentInteraction` (text-to-image spatial relationship).
Schema example: [../schemas/s04-content-draft.example.json](../schemas/s04-content-draft.example.json).

---

## 4d — Sketch Speaker-Note Cues

For every slide, write a short transition cue (opening/closing
handoff) plus non-obvious context. Full talk track is authored
in Step 6c when on-slide text is final.

Rules:
- Short: transition + one anchor thought.
- Tone matches `s02.constraints.formalityLevel`.
- Use only `canonical` forms.
- Numbers match `s04a-terminology-registry.json`.
- Every slide gets a cue, including structural slides.

---

Write `s04-content-draft.json`
(schema: [../schemas/s04-content-draft.schema.json](../schemas/s04-content-draft.schema.json);
example: [../schemas/s04-content-draft.example.json](../schemas/s04-content-draft.example.json)).

**Checkpoint:**

```bash
python $COMPOSER_SKILL/scripts/s04_validate_content.py "$SESSION"
```

Validates: slide coverage (blueprint ↔ s04), headline verbatim,
`contentForm.type` in catalog with required count fields,
speaker-notes presence, source traceability for `document` slides,
`s04a` registry shape (dict-of-objects), data-point grounding
(`verificationTier` + `confidence`, `qualitativeForm` for
low-confidence precise numbers), and illustration-spec consistency.
