# Image Extraction — VLM Subagent Contract

Self-contained subagent specification for [step1-input-registry.md § 1c-image](step1-input-registry.md). The subagent receives a session directory and **a batch of images** (1–N), runs VLM analysis on each, and writes back to the standard Step 1 artifacts in a single session. Calling agent does not need any post-processing.

Output schema reference: [../schemas/s01c-image-style-extraction.example.json](../schemas/s01c-image-style-extraction.example.json).

---

## Subagent inputs

The calling agent passes these in the subagent prompt:

| Input         | Description                                                                                                           |
| ------------- | --------------------------------------------------------------------------------------------------------------------- |
| `$SESSION`    | Absolute path to the session directory. All write-backs are relative to here.                                         |
| `IMAGE_PATHS` | Ordered list (1–N) of absolute paths to the user's source images. Subagent processes the entire batch in one session. |

The subagent reads existing artifacts in `$SESSION` (`s01b-query-intent.json`, `s01c-content-digest.json`, `s01d-design-config.json`) before writing. There is no concurrent subagent — a single batch call owns all image-derived writes.

---

## Subagent responsibilities

Execute these in order. The whole batch is processed in one session, so all writes happen after all images have been analyzed — this is what enables high-quality cross-image palette / style decisions.

1. **Copy every source image first.** `mkdir -p "$SESSION/images/"`, then copy each path in `IMAGE_PATHS` to `$SESSION/images/<basename>` (overwrite ok; deduplicate by basename). **All subsequent steps — including VLM analysis — reference the session-local copies, never the originals.** This guarantees the session directory is self-contained and re-runnable.
2. **Analyze each session-local image with VLM.** Produce one JSON object per image matching the five-section schema below (overallForm / visualGroups / relations / extractedStyle / designMoves + top-level metadata). Use `imageId: "img-<i>"` for the i-th image (1-based) when the VLM does not provide one. Write `sourceImage` as the basename only (path-free).
3. **Write all style+topology entries** to `$SESSION/s01c-image-style-extraction.json` as `{"images": [...]}` (one entry per image, in the order of `IMAGE_PATHS`). Create the file if absent.
4. **Append all content-track sections** to `$SESSION/s01c-content-digest.json` (one synthetic section per `visualGroups[]` entry with non-null `textContent`; non-text leaf groups become `mediaAssets` entries). See "Write-back rules" below.
5. **Merge intent-track signals from all images** into `$SESSION/s01b-query-intent.json → aestheticSignals` (as `inferences` entries — never as `explicitSignals`). Cross-image signals are unioned/deduplicated.
6. **Update `$SESSION/s01d-design-config.json`** to `source: "reference-image"`. Run the cross-image palette / typography merge (see "Multi-image aggregation" below). For a single-image batch, the merge degenerates to a direct copy.
7. **Never overwrite `s01b.inputMode`.** It is locked from step 1b. If the VLM understanding suggests a different intent, append a one-line observation to `s01b-query-intent.json.notes` — do not flip the mode.

Return a short summary: number of images processed, artifacts touched, palette decision (direct vs intersect vs union), any divergent intent observations recorded.

---

## Three-track output model

The VLM emits one JSON object containing five sections (`overallForm`, `visualGroups`, `relations`, `extractedStyle`, `designMoves`) plus top-level metadata. The calling code splits the result into three destinations:

| Track                | Source fields                                                                                                                    | Destination file                                                                                                                      |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **Content**          | `visualGroups[].textContent` (verbatim text inside any group)                                                                    | append synthetic sections to `s01c-content-digest.json`                                                                               |
| **Style + topology** | `overallForm`, `visualGroups[]` (whole tree, including bbox), `relations[]`, `extractedStyle`, `designMoves`, top-level metadata | write to `s01c-image-style-extraction.json`                                                                                           |
| **Intent**           | `intentInference` + derived `aestheticSignals` updates                                                                           | merge into `s01b-query-intent.json` (set `inputMode`; merge `extractedStyle` / `designMoves` into `aestheticSignals` as `inferences`) |

---

## Prompt

```text
You are a slide-design analyst. Examine the attached image and produce a
structured description in strict JSON.

Do NOT try to fit the image into preset categories like "chart" or
"diagram". Describe what is actually there using the five sections below.

Your output drives THREE downstream tracks: any text you transcribe
becomes content for the deck; the structure / palette / mood you
describe drives layout and styling decisions; the inferred mode and
mood feed the user-intent record. Be precise in all three.

==============================
1. overallForm — holistic identity            [→ style track]
==============================
Name the image's overall form AS A WHOLE, in your own words. This is
the one-sentence anchor a designer would use to describe "what shape
this image is" before zooming into parts.

  - name           : free text. Name the form concretely. If it
                     matches a conventional form (pyramid, Gantt,
                     funnel, Sankey, radial concept map, timeline,
                     org chart, matrix, quadrant, ...), use that
                     name AND include structural detail (number of
                     layers, axes, branches, columns).
                     Good: "5-layer pyramid, wide base to narrow top".
                     Good: "horizontal Gantt, 12-week axis, 4 parallel
                            swim lanes with dependency arrows".
                     Good: "no single overall form — page is 4
                            independent cards tiled in a 2x2 grid".
                     Bad:  "diagram" / "chart" / "layout".
  - communicates   : free text. What this form COMMUNICATES — the
                     relationship or message the shape conveys.
                     Examples: "hierarchy / containment",
                     "parallel progress with dependencies",
                     "center-and-satellite primacy", "single data
                     point dramatized at scale".
  - confidence     : high | low
  - isConventional : boolean. true if this matches a named convention
                     (pyramid, Gantt, funnel, ...); false for novel
                     or free compositions. Informational only.

Hard rules for this field:
  - `name` must NOT be a bare type word. Always include structural
    detail (layer count, axis, branch count, column count, etc.).
  - When no single form dominates, say so explicitly — do not force
    one.

==============================
2. visualGroups — recursive tree              [→ content + style tracks]
==============================
Decompose the image into nested visual groups. A group is any region
that reads as one unit: a title block, a stack of boxes, an arrow, a
footnote strip, a single icon. Groups can contain child groups.

For each group output:
  - id           : short stable string ("g-title", "g-stack-1", ...)
  - bbox         : normalized [x1, y1, x2, y2] in 0..1
  - whatItIs     : one or two sentences in your own words. Describe
                   STRUCTURE not category. Bad: "diagram". Good: "3
                   horizontally aligned boxes connected by arrows; the
                   middle box is larger and warmer-colored."
  - textContent  : verbatim transcription of any text in the group
                   (null if none). Do NOT paraphrase. THIS FIELD IS
                   THE SOLE CONTENT-TRACK SOURCE — every word that
                   ends up on the deck flows from here. Transcribe
                   every readable character; never summarize.
  - childGroups  : array of child group ids (empty for leaves)

Always include a single "g-root" group covering the whole image, with
top-level groups as its children. Depth is up to you — go as deep as
the structure warrants, but don't split a single visual unit just to
add nesting.

==============================
3. relations — 7 primitives                   [→ style track]
==============================
Use ONLY these seven relation kinds to describe how groups relate.
Any content form (flow, architecture, comparison, hero, novel layout)
is a combination of these.

  - contains  : { kind, from, to[] }
                Group `from` visually contains the listed children.

  - sequence  : { kind, ordered[], via[?], direction, note }
                Ordered chain. `ordered` lists group ids in order.
                `via` lists arrow/connector group ids if present.
                `direction` ∈ {left-to-right, right-to-left,
                top-to-bottom, bottom-to-top, radial-out, radial-in,
                circular, other}. Use for flows, timelines, pipelines.

  - align     : { kind, members[], axis, rhythm, note }
                Members share an alignment / repetition.
                `axis` ∈ {horizontal, vertical, grid, radial}.
                `rhythm` is free text ("equal-width 3-column", "uneven
                staggered", "tight rows of 4"). Use for grids, card
                rows, repeated icons.

  - group     : { kind, members[], by, note }
                Members read as one cluster. `by` describes what
                bonds them: "shared color", "enclosing frame", "tight
                proximity", "shared background tint".

  - emphasize : { kind, focus, by, note }
                One group is visually elevated above its peers.
                `by` describes the mechanism: "larger", "warmer
                color", "heavier weight", "isolated by whitespace",
                "surrounded by accent halo".

  - annotate  : { kind, from, target, note }
                `from` group labels, captions, or comments on
                `target`. Use for callouts, footnotes-to-diagram,
                axis labels, leader lines.

  - overlay   : { kind, top, bottom, coverage, note }
                `top` is z-order above `bottom` and partially or
                fully covers it. `coverage` ∈ {full, partial,
                corner, band}. Use for hero-image-with-text,
                title-on-photo, overlapping cards, modal-style
                callouts. Distinct from `contains` (containment is
                geometric nesting without z-order intent) and
                `emphasize` (which describes hierarchy, not stacking).

You may emit multiple relations of the same kind. Aim for the
relations a designer would need to recreate the topology — not an
exhaustive enumeration of every adjacency.

==============================
4. extractedStyle                              [→ style + intent tracks]
==============================
  - palette             : 3–6 hex colors sampled from the image
  - paletteRole         : { background, primary, secondary?, accent?, text? }
  - fontHint            : free text, e.g. "humanist sans, bold for title"
  - registerImpression  : executive-formal | business-standard |
                           casual | editorial | technical
  - moodKeywords        : 2–5 atmospheric adjectives ("confident",
                           "warm", "editorial", "futuristic", "serious")
  - designAmbitionGuess : restrained | expressive

  (registerImpression, moodKeywords, designAmbitionGuess feed the
  intent track's write-back to `s01b-query-intent.json → aestheticSignals`.
  palette, paletteRole, fontHint feed the style track and `s01d-design-config.json`.)

==============================
5. designMoves — open-vocabulary               [→ style track]
==============================
Describe the design system as observed moves, not labels.

  - whatDrivesContrast : the primary mechanism producing visual
                          hierarchy. Free text. Examples: "scale only",
                          "color-temperature shift", "weight + color
                          combined", "isolation in whitespace".
  - firstFixation      : { bbox, reason } — where the eye lands first
                          and why.
  - rhythm             : free text describing the overall composition
                          rhythm: "regular 3-col grid", "free-form
                          collage", "central-axis symmetry", "stepped
                          diagonal".
  - signatureMoves     : 1–3 short phrases capturing what is
                          DISTINCTIVE about this image's design — the
                          moves another designer would need to copy
                          to make a slide feel like it belongs to the
                          same family. Concrete, not generic. Bad:
                          "uses color well". Good: "warm focal column
                          flanked by cool bookends", "thin horizontal
                          rule splits data zone into 3 bands".

==============================
Top-level fields
==============================
Also include:
  - sourceImage      : filename
  - imageRole        : single-slide | deck-page-of-many |
                        layout-reference | mood-reference | data-source
  - intentInference  : { mode, rationale, modeAlternatives[],
                          suggestedSlideCount, openQuestions[] }
                        mode ∈ {reproduce, beautify, expand};
                        default beautify when ambiguous.
                        THIS DRIVES THE INTENT TRACK only — it is a
                        Step-5 design-strategy hint, NOT a workflow
                        switch. Steps 2–3 always run regardless.

==============================
Hard rules
==============================
  - Never fabricate text that isn't visibly present.
  - For low-resolution or ambiguous regions, prefer fewer groups
    over guessing — note uncertainty in `whatItIs`.
  - Coordinates are best-effort; do not pretend to pixel precision.
  - Output strict JSON matching s01c-image-style-extraction.example.json.
    No prose, no markdown fences.
```

---

## Write-back rules (executed once after all images are analyzed)

These rules turn the VLM JSON outputs into in-place updates of the four Step 1 artifacts. Apply per-image where noted; final cross-image consolidation is in "Multi-image aggregation".

### A. `s01c-image-style-extraction.json` (style + topology)

- If the file does not exist, create with `{"images": []}`.
- Append one entry per image (in `IMAGE_PATHS` order): the full VLM JSON (overallForm, visualGroups, relations, extractedStyle, designMoves, top-level metadata).
- Set `sourceImage` to the basename of each image; set `imageId` to `"img-<i>"` (1-based) if absent.

### B. `s01c-content-digest.json` (content track)

For every image, walk its `visualGroups[]` (recurse into `childGroups`):

- **If `textContent` is non-null and non-empty:** append a synthetic section with:
  - `anchor`: `"img-<i>-<groupId>"` (i = 1-based image index)
  - `sourceDoc`: `"image:<basename>"`
  - `heading`: derive from group context (parent's `whatItIs` or short slug of `textContent`)
  - `content`: verbatim `textContent`
  - `suggestedRole`: `"content_data"` if the group's `whatItIs` mentions chart / table / data / metric / number / axis; otherwise `"content_text"`
  - `dataPoints`: extract any numbers/percentages present in `textContent` and add to top-level `preGlossary` as well
- **If `textContent` is null AND the group is a leaf:** add an entry to the section's `mediaAssets[]` (and the top-level `mediaAssets[]`) with `type: "image"`, `ref: "images/<basename>"`, `description: <whatItIs>`, `sourceAnchor: "img-<i>"`.
- **`g-root` and intermediate non-leaf groups** without `textContent` are skipped (they are structural, not content).

If `s01c-content-digest.json` does not yet exist, create a minimal scaffold with `sources: []`, `sections: []`, `mediaAssets: []`, `preGlossary: []`, then append. For each image, add one entry to `sources[]` with `format: "image"` and `path: "images/<basename>"`.

### C. `s01b-query-intent.json` (intent track + aesthetic merge)

- **Do NOT touch `inputMode`.** It is locked from 1b.
- **Do NOT write to `explicitSignals`** unless the user's text query verbatim endorsed the image's aesthetic.
- Cross-image merge into `aestheticSignals`:
  - `extractedStyle.moodKeywords` (union across all images) → union into existing `moodKeywords` (deduplicate)
  - `designMoves.signatureMoves` (union across all images) → append each as a phrase to `moodKeywords`
  - `extractedStyle.designAmbitionGuess` → write to `designAmbition` **only if currently `null`**; when images disagree, prefer `expressive` (bias toward openness)
  - `extractedStyle.palette` per image → record one structured entry per image in `visualReferences` (e.g. `{"source": "image:<basename>", "palette": [...]}`)
- Append to `inferences[]` for each merged value: `{field, value, basis: "image batch VLM extraction (N images)", confidence: <high|low based on majority overallForm.confidence>}`.
- For each image whose `intentInference` suggests a different `inputMode` than is already set, append one line to `notes`: `"image:<basename> VLM suggests inputMode=<X> because <rationale> — kept original <Y>"`. Do not flip.

### D. `s01d-design-config.json` (style track)

- Set `source: "reference-image"` (overwriting `"deferred"` is fine; do **not** overwrite `"user-explicit"`).
- Per-field merge with the user-explicit-wins rule (each field already supplied by the user is kept):
  - `palette`: see "Multi-image aggregation" below.
  - `paletteRole`: see "Multi-image aggregation" below.
  - `typography.fontHint`: see "Multi-image aggregation" below.
- Update `sourceProvenance` to record per-field provenance (e.g. `{"palette": "reference-image", "typography.fontHint": "reference-image"}`).

(Image copy is performed in subagent responsibility #1, before VLM analysis — not here.)

---

## Multi-image aggregation

Run once after all per-image writes (A–C) are done. Writes the final consolidated values into `s01d-design-config.json`.

- **Palette merge:** collect all `extractedStyle.palette` arrays across the batch.
  - **Single image:** take the palette directly.
  - **Multiple images:** compute the intersection (colors appearing in ≥ 2 images, normalized by hex equality). If the intersection has ≥ 3 colors, use it. Otherwise take the union of palettes from the images with the highest `overallForm.confidence` (ties: earliest first).
  - **Cap final palette at 6 colors.** Write to `s01d-design-config.json.palette`.
- **paletteRole / typography.fontHint:** take from the image whose `imageRole == "single-slide"`, or failing that, the first image. Record losers under `s01d.sourceProvenance.alternates`.
- **Mood / designAmbition:** already merged across images in step C; no further action.

---

## Pre-write read order

Before writing any artifact, read these once at the start of the batch:

1. `s01b-query-intent.json` — to know `inputMode` (locked) and the existing `aestheticSignals` shape
2. `s01c-content-digest.json` — to know existing `sections`, `sources`, `mediaAssets`, `preGlossary`
3. `s01d-design-config.json` — to know `sourceProvenance` and any `user-explicit` fields not to be overwritten

There is no prior `s01c-image-style-extraction.json` to read — the batch owns this file end-to-end. If any read yields a JSON parse error, return a clear error to the calling agent — do not attempt repair.

---

## Rerun & failure semantics

The subagent is **all-or-nothing per batch**. The four target artifacts are the system of record; the batch must leave them in a consistent state or fail loudly.

- **Rerun (calling the subagent twice on the same `$SESSION`):** the subagent **must overwrite** `s01c-image-style-extraction.json` end-to-end (do not append on top of a prior batch). Before writing back to the other three artifacts, it **rolls back** any entries the previous batch had injected:
  - `s01c-content-digest.json` — drop `sections[]` whose `anchor` matches `^img-\d+-`; drop `mediaAssets[]` whose `sourceAnchor` matches `^img-\d+`; drop `sources[]` entries with `format == "image"`.
  - `s01b-query-intent.json` — drop `inferences[]` entries whose `basis` starts with `image batch VLM extraction`; remove `visualReferences[]` entries whose `source` starts with `image:`; do not touch `moodKeywords` (they may have been edited by the user — additive merges are kept).
  - `s01d-design-config.json` — only revert fields whose `sourceProvenance.<field> == "reference-image"`; leave `user-explicit` fields untouched. After rollback, run the full write-back again from the new VLM output.
- **Partial VLM failure (some images fail to analyze):** the entire batch fails. Do not write any of the four artifacts. Return an error naming the failing image(s) so the caller can drop or replace them and rerun. There is no partial-batch state.
- **Idempotence guarantee:** under these rules, running the subagent N times with the same inputs produces byte-identical outputs (modulo VLM nondeterminism on individual extractions).

---

## Design rationale (notes for skill maintainers, not the VLM)

- **`inputMode` is a Step-5 strategy hint, not a workflow switch.** `reproduce` biases Step 5 toward fidelity (preserve `relations.sequence`/`align`, copy bbox positions, lower designAmbition); `beautify` lets Step 5 redesign freely while honoring `extractedStyle` + `designMoves`; `expand` treats the image as one of several inputs to a normal narrative. Never promote `inputMode` into a control-flow branch in Steps 2–3.
- **Recursive groups + 6 relation primitives** are a closed grammar over an open vocabulary — any composition (flow, architecture, comparison, novel layout) decomposes without schema changes. Resist adding a 7th relation kind; if a new pattern doesn't fit, it usually decomposes into a combination of existing kinds.
- **`whatItIs` is open vocabulary** but constrained to "describe structure, not category" — this is the key prompt move that keeps the VLM from collapsing back into preset labels.

## Downstream consumers

- **Step 2 (Communication Brief)** treats image-derived content (synthetic sections in `s01c-content-digest.json`) the same as document-derived content. When signals are sparse, Step 2 produces a thin brief — see [step2-comm-brief.md § Thin-brief adaptation](step2-comm-brief.md).
- **Step 3 (Narrative Blueprint)** synthesizes a normal blueprint from the now-populated `s02-communication-brief.json` + `s01c-content-digest.json`. For `reproduce`-mode multi-image inputs, the per-image content forms a natural per-slide content basis that Step 3c can merge or split bottom-up.
- **Step 5d (layoutSpec)** reads `s01c-image-style-extraction.json → overallForm.communicates` first to pick the layout family (pyramid → stacked-bands, Gantt → timeline-grid, etc.), then uses `visualGroups` topology and `relations` (especially `sequence`, `align`, `emphasize`) to preserve structural intent — most strongly in `reproduce` mode, as inspiration in `beautify` mode.
- **Step 5b/6c** reads `designMoves.signatureMoves` and `whatDrivesContrast` to bias decoration and structural-family choices, beyond just palette transfer.
- **Step 1d (design config)** reads `extractedStyle.palette` / `paletteRole` / `fontHint` and writes them into `s01d-design-config.json` with `source: "reference-image"`.
