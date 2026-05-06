# Slide Visual Design Analysis

On-demand deep analysis of a sample slide's visual design, producing a
full element-level spec with semantic annotations. Used when a sample
slide is selected as `styleRef` for `spec-composed` strategy.

## When to Trigger

- A slide task uses `strategy: "spec-composed"` and identifies
  a sample slide as the style source
- `complexElements` is non-empty on the selected sample slide
- A user explicitly asks "analyze the detailed style of slide X"

## Input

- `$SLIDE_FILE`: sample slide XML filename (e.g. `slide3.xml`)
- `$TEMPLATE_FILE`: the template .pptx/.potx file
- `$PROFILE`: completed template-profile.json
- `$PROFILE_DIR/sample-slides/slide{N}.jpg`: preview image of the slide

## Phase 1 — Slide Element Extraction

**Caching:** If `$PROFILE_DIR/slide-elements-${SLIDE_FILE%.xml}.json`
already exists, skip extraction and reuse the cached file.

```bash
python $SKILL/scripts/extract_slide_elements.py $TEMPLATE_FILE $SLIDE_FILE \
  -o $PROFILE_DIR/slide-elements-${SLIDE_FILE%.xml}.json
```

This produces a raw structural extraction:
- Every shape with position (`x`, `y`, `cx`, `cy`), fill, line, font
- Text content and paragraph properties
- Group shape hierarchies
- Z-order (layer sequence)

## Phase 2 — VLM Semantic Interpretation

**⚠️ USE SUBAGENT** for this phase.

Launch a subagent using the prompt at
`$SKILL/prompts/annotate-slide-design.md`. Substitute variables:

| Variable          | Value                                             |
| ----------------- | ------------------------------------------------- |
| `$SLIDE_FILE`     | The sample slide XML filename (e.g. `slide3.xml`) |
| `$PROFILE_DIR`    | Path to the `{Brand}.profile/` directory          |
| `$PROFILE`        | Path to `template-profile.json`                   |
| `$SKILL`          | `$SKILLS_ROOT/branded-pptx-generator`             |
| `$PROFILER_SKILL` | `$SKILLS_ROOT/pptx-profiler`                      |

The prompt references `$SKILL/schemas/slide_design_schema.json` for
output structure and field definitions. The subagent reads the schema,
the raw extraction JSON, and the slide preview image to produce the
annotated result.

## Phase 3 — Output

Save the result as `$PROFILE_DIR/slide-design-{slide_file}.json`
(e.g., `templates/Accenture.profile/slide-design-slide3.json`).

**Cleanup:** The final `slide-design-*.json` is a strict superset of
`slide-elements-*.json` — it contains every original structural field
(xfrm, fill, line, geometry, textBody, effects, zIndex, etc.) plus the
semantic annotations added in Phase 2. Once `slide-design-*.json` is
successfully written, delete the intermediate `slide-elements-*.json`
to avoid redundant storage:

```bash
rm $PROFILE_DIR/slide-elements-${SLIDE_FILE%.xml}.json
```

**Caching:** Only `slide-design-*.json` (the final output) is cached
in `$PROFILE_DIR`. If `slide-design-{slide_file}.json` already exists,
skip all phases and return the cached version. If only a
`slide-elements-*.json` exists (e.g. from a prior interrupted run),
skip Phase 1 extraction and run Phase 2 only, then delete the
intermediate file after completion. This cache is template-level —
shared across all sessions using the same template.

## Downstream Usage

The `slide-design-{slide_file}.json` is consumed by
[spec-composed-strategy.md](spec-composed-strategy.md) Step 2 when writing
`generate_{taskId}.py`. The downstream code generation uses these fields:

| Field                       | How it drives code generation                                                                   |
| --------------------------- | ----------------------------------------------------------------------------------------------- |
| `patternStructure`          | Determines the overall layout algorithm — loop structure, element count, flow direction         |
| `spacingPattern`            | Provides exact gap values (EMU) between repeated elements instead of guessing                   |
| `colorMapping`              | Maps semantic roles → theme color keys; used in `<a:schemeClr>` via lxml                        |
| `elements[].xfrm`           | Supplies reference positions/sizes for recreating the spatial arrangement                       |
| `elements[].role` / `group` | Identifies which elements to replicate per data point and which are fixed chrome                |
| `elements[].designIntent`   | `"fixed"` elements are copied verbatim; `"flexible"` elements are parameterized for new content |
