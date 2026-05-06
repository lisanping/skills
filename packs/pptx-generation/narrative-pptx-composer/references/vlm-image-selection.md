# VLM-Based Image Variation Selection

Reference for Step 5f-3. Step 5f points here for the VLM
subagent prompt template, evaluation criteria, output schema,
and fallback behavior. The workflow runbook only states
*when* to invoke this; the *how* lives here.

Background images (`variations: 1`) skip selection entirely —
they are patched directly from `s05f-image_generation_output.json`.
This document is only relevant for illustration groups
(`variations: 3`).

---

## 3a — Assemble evaluation context per image group

For each original request `id`, gather:

- The 3 candidate images (`images/<id>_v1.png`, `<id>_v2.png`,
  `<id>_v3.png`).
- The slide's design context from `s05-slide-visual-design.json`:
  zone role (`background` / `hero-illustration` / `decoration`),
  zone dimensions, other zone positions (where text will overlap).
- The slide's content context from `s04-content-draft.json`:
  `headlineMessage`, body text summary, `contentForm`.
- The deck's palette from `s05b-style-policy.json`: primary, accent,
  surface, background colors as named colors (not hex).
- The deck's `visualRegister` (e.g. `authoritative`, `instructional`).

---

## 3b — Invoke VLM subagent

Prompt structure:

```
You are a senior presentation designer selecting the best image
variation for a slide. You will see 3 candidate images generated
from the same prompt. Choose the ONE best candidate.

## Slide context
- Slide: {slideId} — "{headlineMessage}"
- Image role: {zone role — background / hero-illustration / etc.}
- Zone position: {x}%, {y}%, {w}%×{h}% of slide
- Text overlay zones: {list of text zone positions that overlap}
- Deck palette: {primary}, {accent}, {surface} colors
- Visual register: {visualRegister}

## Evaluation criteria (score 1–5 each, weight in parentheses)

1. **Palette harmony** (×3) — Does the image's dominant color
   palette complement the deck's palette? Clashing hues score 1;
   natural extension of the palette scores 5.
2. **Composition fit** (×3) — For backgrounds: are the quiet /
   low-contrast regions where text zones will be placed? For
   hero illustrations: does the subject sit within the image zone
   without important content bleeding into text zones? Score 1
   if text zones overlap busy/high-contrast regions.
3. **Style coherence** (×2) — Does the image style match the
   deck's visual register? (authoritative → clean/editorial;
   instructional → technical/diagram; inspirational → cinematic)
4. **Narrative support** (×2) — Does the image reinforce the
   slide's headline message? Score on metaphorical or literal fit.
5. **Technical quality** (×1) — Sharpness, absence of artifacts,
   no hallucinated text, no unnatural elements.

## Output format
For each candidate, provide:
- Scores per criterion (1–5)
- Weighted total
- One-line rationale

Then state the winner: {"selected": "<id>_v{N}",
"filename": "<filename>", "rationale": "..."}
```

Feed all 3 images to the VLM in a single call per group for
fair comparison. If the deck has multiple image groups,
batch them into one subagent call when feasible (reduces
overhead); otherwise run sequentially.

---

## 3c — Record selections in `s05f-image-selection.json`

Only illustration groups (those with `variations > 1`) appear in
the `selections` array. Background images (`variations: 1`) are
patched directly from `s05f-image_generation_output.json` by
`s05f_patch_image_paths.py` — they do not need VLM evaluation.

```json
{
  "selections": [
    {
      "originalId": "s03-illustration",
      "slideId": "s03",
      "candidates": [
        { "file": "images/s03-illustration_v1.png", "weightedScore": 44, "rationale": "Subject centered, good narrative fit" },
        { "file": "images/s03-illustration_v2.png", "weightedScore": 38, "rationale": "Off-center composition, busy background" },
        { "file": "images/s03-illustration_v3.png", "weightedScore": 41, "rationale": "Nice style but subject partially cropped" }
      ],
      "selected": "images/s03-illustration_v1.png",
      "selectedVariation": 1
    }
  ],
  "directUse": [
    { "originalId": "cover-bg", "slideId": "s01", "file": "images/cover-bg.png", "note": "single variation, no selection needed" }
  ],
  "selectionMethod": "vlm-comparative",
  "totalGroups": 1,
  "totalDirectUse": 1,
  "timestamp": "2026-04-22T12:00:00+00:00"
}
```

---

## Fallback when VLM is unavailable

If the VLM subagent cannot be invoked (e.g. no vision model
configured), fall back to selecting variation 1 for illustration
groups and record `"selectionMethod": "fallback-first"` in the log.

`s05f_patch_image_paths.py` will detect this case automatically
when no `s05f-image-selection.json` exists, write
`"vlmSelectionApplied": false` on every affected zone/background,
and emit a stderr WARN. `s05_validate_plan.py` then surfaces those
zones in its `Image resources` section so Step 8 QA knows exactly
which slides need a human visual check.

---

## Partial variation failures

When a 3-variation request returns fewer than 3 images (e.g. 2
of 3 succeed because of a content-filter rejection on one prompt
permutation), select among the surviving candidates rather than
re-generating to refill:

- **2 of 3 succeeded** \u2192 run the rubric against the 2
  surviving candidates and record `"candidates": [...]` with the
  2 entries; mark the missing slot in `imageGenerationLog.failures`.
  Do NOT auto-regenerate \u2014 the prompt that failed will likely
  fail again, and the surviving pair is usually adequate.
- **1 of 3 succeeded** \u2192 use the survivor directly with
  `"selectionMethod": "single-survivor"`; record both failures in
  `imageGenerationLog.failures`.
- **0 of 3 succeeded** \u2192 the zone falls through to its declared
  `fallback`; `s05f_patch_image_paths.py` sets `path: null` +
  `fallbackApplied: true`. No selection entry is written.

Re-generation is a manual loop \u2014 the operator may edit the
prompt in `s05f-image-requests.json` and re-run
`generate_images.py` (idempotent: only missing
`output_filename`s are re-requested).
