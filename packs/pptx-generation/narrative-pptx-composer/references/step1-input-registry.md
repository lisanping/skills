# Step 1 — Input Registry

Full procedural detail for Step 1. See [SKILL.md](../SKILL.md) for
the mandatory rules summary.

Four sub-tasks, dependency-driven:

1. **1a — Session directory.** Must exist before any artifact is written.
2. **1b — Input classification + query normalization** →
   `s01b-query-intent.json`. Records `inputMode`, explicit signals,
   aesthetic signals, and `rawQuery` (verbatim). 1b reads only the user's
   chat text + filenames — it does not open content documents or call a
   VLM.
3. **1c — Content extraction** → `s01c-content-digest.json` (content layer).
4. **1d — Design input registration** → `s01d-design-config.json`
   (style layer).

**1c and 1d co-execute in a single pass.** Every input modality
(documents, PPTX, images, query-only) yields content signals and style
signals together, and a single parsing/VLM call services both — but
each writes its own artifact so downstream steps can consume them
independently. Splitting the artifacts (rather than the execution)
avoided the reverse dependencies that an earlier two-pass design had.

`s01b.rawQuery` is the canonical record of the user's brief.
Query-only inputs are handled by 1c reading directly from `s01b.rawQuery`.

---

## Step 1 Scope

- Parse inputs into structured data. Do not analyze content.
- Allowed inferences: `language` (script detection) and `inputMode` (modality dispatch) only.
- Do not infer audience, purpose, formality (Step 2), core argument (Step 3), imageryDemand (Step 3a), or palette/typography/motif (Step 5b).
- Do not reorder, merge, or drop content sections — Step 3 owns structure.

---

## 1a — Set Up Session Directory

```bash
# Skill path variables — every checkpoint and Step 8a render needs these
export SKILLS_ROOT=".claude/skills"
export COMPOSER_SKILL="$SKILLS_ROOT/narrative-pptx-composer"
export PROFILER_SKILL="$SKILLS_ROOT/pptx-profiler"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BRIEF_INTRO="<topic slug from user's initial request — filename or 2-4 word topic; rough is fine, this is just a folder label>"
SESSION="sessions/${TIMESTAMP}_narrative_${BRIEF_INTRO}"

mkdir -p "$SESSION"
cd "$SESSION"
```

All subsequent commands run from `$SESSION`. Content documents are
copied into `$SESSION` in step 1c, after `CONTENT_DOCS` is defined.
The three `export` lines are mandatory — validators and renderers
in later steps depend on them.

`BRIEF_INTRO` is a directory label only — derive it from the user's
initial request topic or the primary document filename. It is not a
structural commitment and does not require any analysis step. Use
`untitled` if the request is too vague to extract a topic.

**Query-only input (no content documents):** Nothing extra to do here.
The user's verbatim brief is captured by `s01b-query-intent.json.rawQuery`
in step 1b, and step 1c reads `rawQuery` as its synthetic content source.

---

## 1b — Classify Input + Normalize the User Query

Before content ingestion, parse the original user request (chat
message + filenames + any inline brief) into a structured intent
artifact. This makes user signals — especially aesthetic ones —
first-class inputs to Steps 2 and 5 instead of leaving them buried
in free-text.

Write `s01b-query-intent.json`. The schema has the **input mode**
classifier, two signal groups — **explicit signals** (what the user
literally said) and **aesthetic signals** (visual/style language) —
plus a single **`inferences`** array (LLM guesses, each entry tagged
with `confidence: high | low`), the raw query, and a
free-form notes field. The example below shows the **post-fill
shape**:

```json
{
  "rawQuery": "<full text of user's request>",
  "inputMode": "generate",
  "inputSources": {
    "documents": ["path/to/doc1.md"],
    "images": [],
    "queryOnly": false
  },
  "explicitSignals": {
    "topic": "...",
    "audience": { "who": null, "priorKnowledge": null, "role": null },
    "purpose": null,
    "slideCountConstraint": null,
    "formality": null,
    "language": null
  },
  "aestheticSignals": {
    "designAmbition": null,
    "visualReferences": [],
    "moodKeywords": [],
    "avoidKeywords": [],
    "diversityPreference": null,
    "imageryHint": null
  },
  "inferences": [],
  "notes": ""
}
```

> `imageryDemand` is decided in Step 3a, not here. 1b only records
> what the user said about imagery (`avoidKeywords`, `imageryHint`).

### Field semantics

**`inputMode`** — coarse classification of what the user is asking the
skill to do. Decided from the chat text + the kinds of files attached
alone (no document parse, no VLM call). One of:

| `inputMode` | When                                                                                                                                                                   |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `generate`  | Default. Documents and/or chat brief, no image input — the skill authors a new deck from scratch.                                                                      |
| `beautify`  | Default when image input is present. The user wants a *good* slide built from the same content, not a pixel copy.                                                      |
| `reproduce` | Image input AND user explicitly asked to "复刻 / 还原 / preserve / replicate / match exactly" the source layout. Multi-page same-template sequences also suggest this. |
| `expand`    | Image input is one of several inputs (docs + brief + image), used as a mood/style reference rather than the structural seed.                                           |

Decision rule: `generate` when no image; `reproduce` only when user
explicitly asks for fidelity; `beautify` for image-only; `expand`
when image + other content without fidelity request. `generate` +
images is invalid (hard-fail). VLM may refine topology/style but
**never overwrites** `inputMode`.

**`inputSources`** — what the user actually attached. Used by 1c to
decide which extraction sub-paths to invoke (text/PPTX/image) and by
the Step 1 checkpoint to verify all sources were processed.

**`explicitSignals`** — only populated when the user *explicitly*
states the value. Leave `null` if not stated; **never write
inferred values into this block**. All audience/purpose inference
is deferred to Step 2 — s01b only extracts, it does not infer.

- `purpose` ∈ {`inform`, `persuade`, `report`, `propose`, `inspire`}
- `formality` ∈ {`executive-formal`, `business-standard`, `casual`,
  `regulatory`}
- `audience.priorKnowledge` ∈ {`novice`, `familiar`, `expert`}
- `slideCountConstraint` — user-stated quantity constraint; one of
  `null` (not stated), `{ "type": "exact", "value": <int> }`,
  `{ "type": "range", "min": <int>, "max": <int> }`, or
  `{ "type": "duration", "minutes": <number> }`. Step 3c is the
  sole arbitration point; Step 2 does not consume this field.

**`aestheticSignals`** — captured from any aesthetic language in
the query. Same fact-vs-inference rule as `explicitSignals`: only
fill a field when the user's language directly supports it; leave
`null` / `[]` otherwise. **Do not pre-fill defaults here** — Step 5b
applies defaults for any field left `null`.

- `designAmbition` ∈ {`restrained`, `expressive`} — derive from
  words like "minimal/clean/restrained" → `restrained`;
  "modern/polished/expressive/bold/dramatic/cinematic/keynote"
  → `expressive`. (Bolder mood is captured in `moodKeywords`,
  not as a third ambition tier.)
- `visualReferences` — explicit comparisons like "Apple keynote",
  "McKinsey style", "Stripe-like".
- `moodKeywords` — atmospheric adjectives: "bold", "modern",
  "editorial", "keynote", "warm", "futuristic", "playful",
  "serious".
- `avoidKeywords` — negative constraints: "no stock photos", "not
  too corporate", "avoid clip-art".
- `diversityPreference` ∈ {`low`, `standard`, `high`} — set to
  `high` when the user mentions variety, energy, range, or
  references a keynote-style talk; set to `low` only when the
  user said "keep it consistent" or "uniform". Otherwise leave
  `null` (Step 5b defaults to `standard`).
- `imageryHint` ∈ {`favor-imagery`, `avoid-imagery`, `null`} —
  **only set when the user's text directly addresses imagery**:
  "keep it visual / image-heavy / cinematic" → `favor-imagery`;
  "no images / minimal imagery / text-only" → `avoid-imagery`.
  Otherwise leave `null`. Step 3a sub-task 6 reads this hint as one
  input to the `imageryDemand` cascade; the final demand value is
  decided there, not here. Negative constraints like "no stock photos"
  remain in `avoidKeywords` (they constrain *style*, not *demand*).

**`imageryDemand` is NOT a 1b field** — decided in Step 3a sub-task 6.

**`inferences`** — whitelist: `language` and `inputMode` only. The
validator hard-fails any other `field` value. Each entry records
`field`, `value`, `basis`, `confidence ∈ {high, low}`.

### Downstream consumers

| 1b field                                                          | Consumed by  |
| ----------------------------------------------------------------- | ------------ |
| `explicitSignals.audience` / `purpose` / `formality` / `language` | Step 2       |
| `explicitSignals.slideCountConstraint`                            | Step 3c      |
| `aestheticSignals.*`                                              | Steps 5b, 5d |

---

## 1c — Content Extraction

Content-track output of the 1c/1d co-execution pass. Produces
`s01c-content-digest.json`. The companion style-track output
(`s01d-design-config.json`) is described in
[**§ 1d — Register Design Inputs**](#1d--register-design-inputs) below;
both run from the same modality dispatch so each input is parsed once.

| Modality                 | Content extraction                           | Style extraction (see § 1d)                                                |
| ------------------------ | -------------------------------------------- | -------------------------------------------------------------------------- |
| Text docs (.md/.txt/...) | LLM read or `markitdown`                     | None — `s01d` resolves via path 3 (`source: "deferred"`)                   |
| `.pptx`                  | `s01c_ingest_pptx.py` (§ 1c-pptx)            | None — `.pptx` source visuals are out of scope; `s01d` resolves via path 3 |
| Images                   | VLM content track (§ 1c-image)               | VLM style track → `s01d` path 2 (reference image)                          |
| Query only               | LLM read of `s01b.rawQuery` as synthetic doc | `s01d` resolves via path 1 (user explicit) or path 3 (`deferred`) per § 1d |

The full design-config resolution paths and field semantics are in
[**§ 1d — Register Design Inputs**](#1d--register-design-inputs)
below. The remainder of this section covers the content extraction.

```bash
# Content documents (user-provided)
# Supported formats: .md, .txt, .docx, .pdf, .pptx
# Query-only inputs: skip this — 1c reads s01b.rawQuery directly.
CONTENT_DOCS=("path/to/doc1.md" "path/to/doc2.pdf")

# Copy them into the session directory for provenance
for doc in "${CONTENT_DOCS[@]}"; do
  cp "$doc" "$SESSION/"
done
```

Parse every document into a structured intermediate format.

**Parsing:**

| Format           | Method                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------ |
| `.md` / `.txt`   | Read file directly                                                                         |
| `.docx` / `.pdf` | `python -m markitdown <file>`                                                              |
| `.pptx`          | `python $COMPOSER_SKILL/scripts/s01c_ingest_pptx.py <file> $SESSION` (see § 1c-pptx below) |

**Extraction:** Analyze the parsed text and produce
`s01c-content-digest.json`
(see [../schemas/s01c-content-digest.example.json](../schemas/s01c-content-digest.example.json)).

**Rules:**

- **Media asset extraction (mandatory).** Scan each document for
  embedded media (images, diagrams, quotes, links, code blocks).
  Record in section-level and top-level `mediaAssets` arrays.
  Copy referenced image files into `$SESSION/images/`.
  Initialize `usedInSlides: []` on each top-level entry.
- Preserve document section structure as initial scaffold only —
  Steps 2–3 may reorder, merge, split, or drop.
- Every section keeps a stable `anchor` for downstream `sourceRef`.
- Extract all data points, named entities, figures into `preGlossary`.
- Assign `suggestedRole`: `content_data` | `content_text` | `content_mixed`.
- **Multi-document:** merge by topic into `mergedSections`. Record
  conflicts; pick most recent/cited value; log in `conflicts[].resolution`.

**Query-only inputs:** `CONTENT_DOCS` is empty. Read `s01b-query-intent.json.rawQuery`
as the sole synthetic content source and produce a thin
`s01c-content-digest.json` from it (one section, `sourceDoc: "chat-brief"`).
The schema is identical — downstream Steps 2–3 cannot tell the
difference between a chat-derived digest and a document-derived one.

---

## 1c-pptx — PPTX Input (optional)

When one or more of the `CONTENT_DOCS` are `.pptx` files, run this
sub-step **as part of** 1c (not a separate pass). The extraction
script replaces the manual LLM parse for the `.pptx` source and
produces the same `s01c-content-digest.json` schema that downstream
steps consume.

### What gets extracted

| Content           | Where it goes                                                    |
| ----------------- | ---------------------------------------------------------------- |
| Per-slide title   | `sections[].heading`                                             |
| Body text         | `sections[].content` (text-frames, grouped shapes)               |
| Tables            | `sections[].content` (rendered as markdown tables)               |
| Speaker notes     | `sections[].speakerNotes`                                        |
| Embedded images   | Copied to `$SESSION/images/`, listed in `sections[].mediaAssets` |
| Slide layout name | `sections[].layoutName` (advisory — not a design commitment)     |
| Data points       | `sections[].dataPoints` + top-level `preGlossary`                |
| Slide dimensions  | `sources[].dimensions` (EMU + inches)                            |

Linked (non-embedded) images are skipped — only images stored inside
the `.pptx` package are extracted. Duplicate image blobs (same image
on multiple slides) are written once and referenced multiple times.

### Procedure

```bash
# For each .pptx in CONTENT_DOCS, run the extraction script:
python $COMPOSER_SKILL/scripts/s01c_ingest_pptx.py "$PPTX_FILE" "$SESSION"
```

The script writes `$SESSION/s01c-content-digest.json` and copies
embedded images into `$SESSION/images/`.

**When `.pptx` is the sole content source,** the script output is
the complete `s01c-content-digest.json`. No further LLM parsing
needed for 1c.

**When `.pptx` is mixed with other formats** (e.g. `.pptx` +
`.md`), run the script first, then merge its output with the
LLM-parsed sections from the other documents following the standard
multi-document merge rules (topic-based `mergedSections`, conflict
resolution, combined `preGlossary`).

### PPTX-specific content-digest fields

The script adds one field beyond the base schema:

- `sections[].layoutName` — the slide layout name from the source
  deck (e.g. `"Title + Content_2"`, `"Section Divider"`). This is
  advisory metadata only — Steps 2–3 are free to re-structure.

Slide order is recorded in the section's `anchor` (`pptx-slide-N`).
The `sources[].format` value is `"pptx"` and includes a
`slideCount` and `dimensions` object.

### Structural notes

- Each slide becomes one section in the content digest. The slide's
  title placeholder (idx 0 or `shapes.title`) maps to `heading`;
  all other text-bearing shapes are concatenated into `content`.
- The source deck's slide order is preserved as the initial section
  order, but this is **not a structural commitment** — Steps 2–3
  may reorder, merge, or drop slides entirely.
- Template/sample slides with only placeholder text (e.g. "Click to
  add title", "Lorem ipsum") will appear in the digest. The LLM
  should recognize these as non-content in Step 2 and mark them for
  exclusion via `informationHierarchy.cut`.
- `.potx` template files are **not supported** for content ingestion.
  Use the `pptx-profiler` skill for template analysis instead.

---

## 1c-image — Image Input (optional)

When images are provided, launch a **single subagent** with
[image-extraction-prompt.md](image-extraction-prompt.md). Pass
`$SESSION` and the full `IMAGE_PATHS` list in one call.

### Outputs (produced by the subagent)

- `s01c-image-style-extraction.json` (style + topology track, one
  entry in `images[]` per source image)
- `images/<basename>` (copies of source images)
- updates to `s01c-content-digest.json` (synthetic content sections
  + `mediaAssets` for non-text groups)
- updates to `s01b-query-intent.json` (intent track merged into
  `aestheticSignals` + `inferences[]`; `notes` may record a divergent
  intent observation)
- updates to `s01d-design-config.json` (`source: "reference-image"`,
  palette/paletteRole/typography.fontHint, `sourceProvenance`)

### Checkpoint additions

- `s01c-image-style-extraction.json` exists with one entry per source image
- `s01b-query-intent.json.inputMode` is one of `beautify` / `reproduce` / `expand` (set in 1b, not here)
- `s01c-content-digest.json` contains synthetic sections for the image-derived text content
- `s01d-design-config.json.source` is `"reference-image"`

---

## 1d — Register Design Inputs

Produces `s01d-design-config.json`. Records what the user or
reference image explicitly gave — does not infer design fields
from content or mood.

Only two system defaults are allowed:

| Field                 | Default              | Provenance       |
| --------------------- | -------------------- | ---------------- |
| `dimensions`          | 13.333×7.5 in (16:9) | `system-default` |
| `typography.monoFont` | `"JetBrains Mono"`   | `system-default` |

All other fields (`palette`, `style.*`, `typography.headingFont`,
`typography.bodyFont`, `typography.secondaryFont`): write as `null`
with provenance `deferred-step5b` unless user or reference image
supplies them.

### Three resolution paths (priority order)

1. **User explicit** → `source: "user-explicit"`.
2. **Reference image** → VLM extract palette/typography/dimensions → `source: "reference-image"`.
3. **No design signals** → all non-default fields `null` + `deferred-step5b` → `source: "deferred"`.

When user provides both explicit params AND image, merge
field-by-field: path 1 wins per-field.

### `sourceProvenance` (mandatory, field-grain)

Every leaf in `dimensions`, `palette`, `typography`, `style` must
appear in `sourceProvenance` with one of:
`user-explicit` | `reference-image` | `system-default` | `deferred-step5b`.

`content-inferred` is no longer valid. A `null` leaf whose
provenance is not `deferred-step5b` is a hard error. A non-`null`
leaf with `deferred-step5b` is a hard error.

Required keys: `dimensions`, `palette`, `typography.headingFont`,
`typography.bodyFont`, `typography.monoFont`,
`typography.secondaryFont`, `style.contrast`, `style.motif`,
`style.iconStyle`.

### Multi-image style merging

When multiple images: intersect colors appearing in ≥2 images (if
<3 colors, take union of highest-confidence). Cap palette at 6.
Take typography from `imageRole: "single-slide"` image (or first).

### Dimensions

1. User explicit → honor it.
2. Reference image → snap to nearest standard (16:9, 4:3, 3:2).
3. Default: **16:9 widescreen 13.333×7.5**.

`dimensions` is locked at Step 1. Step 5 may not change it.
If 4:3 is needed, user must declare at brief stage.

### Language default

`s01b.explicitSignals.language` is set by 1b when the user names a
language (e.g. "用英文写" / "make it in Chinese"). Otherwise 1d
infers language from the detected primary script of content sources
and `rawQuery`, with the following priority:

1. **User explicit** → honor verbatim.
2. **Document language** → primary script of content documents
   (`s01c` sources). This wins even when `rawQuery` is written in a
   different language (the user's chat language is conversational;
   the document language is the presentation's target language).
3. **`rawQuery` language** → fallback when no content documents exist
   (query-only input).

Write the result as a high-confidence `inferences[]` entry on
`s01b`. Language is on the inference whitelist (see § 1b). **Never
leave language unset** when content text is available.

### Typography fields

- `monoFont` — default `"JetBrains Mono"` (`system-default`).
- `headingFont` / `bodyFont` — user or image, else `null` + `deferred-step5b`.
- `secondaryFont` — user or image, else `null` + `deferred-step5b`.
  (Escalation logic now runs in Step 5b, not here.)

All fields must be present in JSON, even when `null`.

Schema: [../schemas/s01d-design-config.example.json](../schemas/s01d-design-config.example.json).

---

**Checkpoint:** session directory exists and contains content document
copies (or none, for query-only input — `s01b.rawQuery` carries the
brief); `s01b-query-intent.json` exists with `inputMode` set;
`s01c-content-digest.json` exists;
`s01d-design-config.json` exists (at least partial). Run the
validator:

```bash
python $COMPOSER_SKILL/scripts/s01_validate_inputs.py "$SESSION"
```

The validator enforces: `inputMode` ∈ enum,
`s01d.source` ∈ {`user-explicit`, `reference-image`, `deferred`},
`dimensions` complete, all `sourceProvenance` keys present and valid
(no `content-inferred`; `null` leaves require `deferred-step5b`),
`secondaryFont` field present, image-style-extraction parity, and
`inferences[]` whitelist (`language` and `inputMode` only).
