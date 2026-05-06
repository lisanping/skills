---
name: pptx-profiler
description: >
  Analyze .pptx/.potx template files to produce template-profile.json.
  Structural extraction (colors, fonts, layouts, placeholders, shapes),
  layout/sample rendering, and VLM semantic analysis.
  USE WHEN the user asks to "analyze this template", "what layouts", "extract
  brand profile", or when a downstream skill needs a template profile.
  DO NOT USE for generating slides, or reading/editing existing decks.
compatibility: Requires Python 3.10+ with python-pptx. PowerPoint COM or LibreOffice for layout/sample rendering.
---

# Template Profiling

## Purpose

Analyze a `.potx` / `.pptx` template and produce a complete
`template-profile.json` enriched with visual semantic data. This
profile is the foundational artifact consumed by `branded-pptx-generator`
and any other skill that needs to understand a template's structure
and design language.

## Architecture

This skill combines programmatic extraction with VLM-driven analysis:

**This skill's tools** (template analysis operations):

Located in this skill's `scripts/` directory.

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| `extract_template.py` | Structural extraction | `.potx`/`.pptx` | `template-profile.json` (partial) |
| `render_layouts.py` | Render slideLayouts as images | `.potx`/`.pptx` | `layout-previews/*.jpg` |
| `render_samples.py` | Render sample slides as images | `.potx`/`.pptx` | `sample-slides/*.jpg` |
| `extract_guide_rules.py` | Extract raw text from guide slides | `.potx`/`.pptx` + profile | `guide-rules-raw.json` |
| `generate_composer_digest.py` | Generate downstream decision digest | `template-profile.json` | `composer-digest.json` |

**Claude's own capabilities** (judgment):
- Visual semantic classification of layouts (roles, capacity)
- Decorative shape role identification
- Cross-layout design language extraction
- Sample slide content pattern and reusability analysis
- Guide slide identification (role classification within sample analysis)
- Guide slide rule extraction (structured rules from instructional text)
- Cross-sample aesthetic principle synthesis (actionable design guidance)

## When to Use

| Scenario | Skill |
|----------|-------|
| "Analyze this template" / "What layouts does it have?" | **This skill** |
| "Extract the brand profile" / "Profile this .potx" | **This skill** |
| Downstream skill needs `template-profile.json` | **This skill** |

---

## Workflow

Six core steps.

- **Step 1–4:** Profile extraction, rendering, semantic analysis (VLM),
  and aesthetic principle synthesis
- **Step 5:** Generate downstream-facing composer digest
- **Step 6:** Deliver profile and digest

### Step 1 — Set Up Working Directory

```bash
TEMPLATE="templates/<Brand>.potx"                      # user-provided path
TEMPLATE_FOLDER=$(dirname "$TEMPLATE")                 # e.g. templates/
TEMPLATE_FILE=$(basename "$TEMPLATE")                  # e.g. Accenture.potx
BRAND=$(basename "$TEMPLATE" | sed 's/\.\(potx\|pptx\)$//')
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SESSION="sessions/${TIMESTAMP}_${BRAND}_extract"
PROFILE_DIR="$(pwd)/${TEMPLATE_FOLDER}/${BRAND}.profile"  # all reusable analysis artifacts
PROFILE="${PROFILE_DIR}/template-profile.json"
LAYOUT_PREVIEWS="${PROFILE_DIR}/layout-previews"         # deterministic renders, reused across sessions
SAMPLE_SLIDES="${PROFILE_DIR}/sample-slides"             # deterministic renders, reused across sessions

mkdir -p "$SESSION"
mkdir -p "$PROFILE_DIR"
cp "$TEMPLATE" "$SESSION/"
cd "$SESSION"
```

All subsequent commands run from `$SESSION`. The profile, preview
renders, and slide design specs are saved to `$PROFILE_DIR` so they
are reusable across sessions. Layout and sample slide renders are
deterministic — identical template produces identical images — so they
live in `$PROFILE_DIR` rather than `$SESSION`.

**Checkpoint:** `$SESSION/<Brand>.potx` (or `.pptx`) exists.

### Step 2 — Extract Template Structure

Extract structural data from the template programmatically.

```bash
python $SKILL/scripts/extract_template.py $TEMPLATE_FILE -o $PROFILE
```

Multi-master templates are handled automatically: the parser identifies the
brand master (skips the default Office Theme master) and extracts only the
brand master's layouts.

This produces `$PROFILE` with all programmatically extractable
data. Fields requiring visual judgment (`inferred_type`, `content_capacity`,
`visual_weight`, `shapes[].role`, `design_language`) are left as `null`.

**Checkpoint:** `$PROFILE` exists with structural data populated.

### Step 3 — Layout Semantic Analysis

#### 3a — Render Layout Previews

**Skip if `$LAYOUT_PREVIEWS/` already contains `.jpg` files** (renders
are deterministic for a given template — no need to re-render).

```bash
python $SKILL/scripts/render_layouts.py $TEMPLATE_FILE -o $LAYOUT_PREVIEWS/
```

Produces `$LAYOUT_PREVIEWS/slideLayout{N}.jpg` (clean) and
`$LAYOUT_PREVIEWS/slideLayout{N}_annotated.jpg` (with placeholder bounding
boxes and property labels) — one pair per slideLayout.

**Checkpoint:** `$LAYOUT_PREVIEWS/*.jpg` exist.

#### 3b — Classify Layouts and Extract Design Language

**⚠️ USE SUBAGENT** with prompt: `$SKILL/prompts/classify-layouts.md`

Substitute variables: `$LAYOUT_PREVIEWS`, `$PROFILE`, `$SKILL` before passing to subagent.

**Merge** the subagent's response into `$PROFILE`:
- Set `inferred_type`, `inferred_type_confidence`, `content_capacity`,
  `visual_weight` on each `layouts[]` entry
- Set `shapes[i].role` for each shape using the `shape_roles` map
- Set top-level `design_language`

**Checkpoint:** `$PROFILE` has layout semantics and `design_language`.

### Step 4 — Analyze Sample Slides

Check `$PROFILE → sample_slide_catalog`: any entry with `has_content: true`
is a sample slide (contains real text or visual elements, not just
placeholder markers like "Click to add title").
**If no entries have `has_content: true`, skip this step entirely.**

#### 4a — Render Sample Slide Previews

**Skip if `$SAMPLE_SLIDES/` already contains `.jpg` files** (renders
are deterministic for a given template — no need to re-render).

```bash
python $SKILL/scripts/render_samples.py $TEMPLATE_FILE -o $SAMPLE_SLIDES/
```

Produces `$SAMPLE_SLIDES/slide{N}.jpg` — one full-resolution image per
slide, suitable for detailed visual analysis.

#### 4b — Classify Sample Slides and Identify Guide Slides

**⚠️ USE SUBAGENT** with prompt: `$SKILL/prompts/classify-samples.md`

One VLM pass handles both slide classification and guide detection —
seeing all slides together makes the contrast between guide pages and
content samples obvious.

Substitute variables: `$SAMPLE_SLIDES`, `$LAYOUT_PREVIEWS`, `$PROFILE`, `$SKILL` before passing to subagent.

**Merge** the subagent's response into `$PROFILE`:
- Set `role` (and `guideType` if applicable) on every catalog entry
- Set Task B fields on sample/hybrid entries only
- Append `design_language_supplements` to `design_language.visual_motifs`
- Set `design_language.vlm_guardrails` from Task C output

**Checkpoint:** `$PROFILE → sample_slide_catalog[]` has role, guideType,
and classification fields for all content-bearing slides.

#### 4c — Synthesize Aesthetic Design Principles

**Only run if Step 4b classified at least 3 sample or hybrid slides.**
If fewer than 3 content-bearing samples exist, set
`aesthetic_principles: null` and skip to Step 4d.

This step performs **cross-sample synthesis** — analyzing ALL sample
slides together to extract generalizable, actionable design principles
that the generator can apply to novel slide designs. Unlike Step 3b's
`design_language` (which describes WHAT the template looks like) and
Step 4b's per-slide classification (which characterizes individual
slides), this step produces prescriptive guidance: HOW to design new
things that look like they belong.

The output covers five dimensions:
1. **compositionSystem** — spatial organization rules
2. **colorSemantics** — semantic color-role mapping
3. **typographicSystem** — the full type scale with usage contexts
4. **shapeGrammar** — shape vocabulary and composition rules
5. **patternRecipes** — reusable structural templates with scaling logic

**⚠️ USE SUBAGENT** with prompt: `$SKILL/prompts/synthesize-aesthetics.md`

Substitute variables: `$SAMPLE_SLIDES`, `$PROFILE`, `$SKILL` before passing to subagent.

**Merge** the subagent's response into `$PROFILE`:
- Set top-level `aesthetic_principles` field

**Checkpoint:** `$PROFILE → aesthetic_principles` is populated with all
five dimensions; `patternRecipes` has at least one entry for each
distinct visual pattern observed across samples; `colorSemantics
.roleAssignment` maps at least `emphasis_primary`, `structural`, and
`background_primary`.

#### 4d — Extract Guide Rules

**Only run if Step 4b identified at least one guide or hybrid slide.**

```bash
python $SKILL/scripts/extract_guide_rules.py $TEMPLATE_FILE $PROFILE -o guide-rules-raw.json
```

**⚠️ USE SUBAGENT** with prompt: `$SKILL/prompts/extract-guide-rules.md`

Substitute variables: `$SAMPLE_SLIDES`, `$PROFILE`, `$SKILL` before passing to subagent.
The subagent also needs access to `guide-rules-raw.json` in the session directory.

**Merge** into `$PROFILE`: group rules by `ruleKind` into
`template_guide.byType`, set `template_guide.slides` and
`template_guide.rulesExtracted`.

**Checkpoint:** `$PROFILE → template_guide` has extracted rules by type.

**Checkpoint after Step 4:** Profile is complete with layout semantics,
slide classifications, aesthetic design principles (if sufficient
samples), guide rules (if any), and designLanguage.

### Step 5 — Generate Composer Digest

Export a downstream-facing decision digest for `branded-pptx-generator`.

```bash
python $SKILL/scripts/generate_composer_digest.py $PROFILE -o $PROFILE_DIR/composer-digest.json
```

Produces `composer-digest.json` conforming to
`$SKILL/schemas/composer_digest_schema.json`. Contains: `meta`,
`template`, `profileHealth`, `designDirectives`,
`layoutBehaviorSummary`, `preferredLayoutHints`,
`styleRefCandidates`, `strategyPolicy`, `guardrails`, and (when
`aesthetic_principles` is non-null) `aestheticPrinciples`.

Guide slide rules are merged into `guardrails` and
`designDirectives` with `provenance: "guide_slide_explicit"`.

**Checkpoint:** `$PROFILE_DIR/composer-digest.json` exists.

### Step 6 — Deliver

Report to the user:

1. **Template info** — brand name, layout count, sample slide count
2. **Key findings** — design language summary (style tone, whitespace
   rhythm, visual motifs), number of guide rules extracted, number of
   aesthetic pattern recipes identified
3. **Gaps** — which semantic fields remain `null`, which layouts could
   not be confidently classified, any rendering failures, whether
   `aesthetic_principles` was populated or skipped (and why)
4. **Downstream readiness** — `$PROFILE_DIR/composer-digest.json` path,
   confirmation it is ready for consumption

---

## Output Artifacts

After a complete profiling run:

```
$TEMPLATE_FOLDER/
└── {Brand}.profile/                  # All reusable analysis artifacts
    ├── template-profile.json         # Template structure + semantics
    ├── composer-digest.json          # Downstream decision digest
    ├── layout-previews/              # Deterministic renders, reused across sessions
    │   ├── slideLayout1.jpg          # Clean render
    │   ├── slideLayout1_annotated.jpg # With placeholder overlays
    │   └── ...
    └── sample-slides/                # (if template has samples)
        ├── slide1.jpg
        └── ...

$SESSION/
├── {Brand}.potx                     # Copy of source template
└── guide-rules-raw.json             # Intermediate — raw guide text (if applicable)
```

## Profile Schema

The full JSON Schema is at `$SKILL/schemas/profile_schema.json`.
Top-level structure:

| Key | Type | Description |
|-----|------|-------------|
| `meta` | object | Source file, extraction date, extractor version |
| `identity` | object | Theme colors, fonts, brand identity |
| `compliance` | object | Color/font compliance checks |
| `masters` | array | Slide master metadata |
| `layouts` | array | Per-layout structure + VLM semantics (`inferred_type`, `content_capacity`, `visual_weight`, `shapes[].role`) |
| `design_language` | object | Cross-layout style tone, whitespace rhythm, visual motifs, VLM guardrails |
| `aesthetic_principles` | object/null | Actionable design principles synthesized from cross-sample VLM analysis: composition system, color semantics, typographic system, shape grammar, pattern recipes. `null` if fewer than 3 content-bearing samples |
| `sample_slide_catalog` | array/null | Per-slide classification (`role`, `guideType`, `cloneCandidate`, style fields) |
| `template_guide` | object/null | Structured rules extracted from guide slides, grouped by `ruleKind` |
| `extended` | object | Additional extracted data (table styles, etc.) |
| `gaps` | object | Fields that could not be populated |

## Composer Digest Schema

The composer digest JSON schema is defined at `$SKILL/schemas/composer_digest_schema.json`.
This schema governs the output of `generate_composer_digest.py` (Step 5)
and is the contract consumed by `branded-pptx-generator` and other
downstream skills.

---

## Troubleshooting

| Problem | What to check |
|---------|---------------|
| Extraction fails | Verify template is valid `.potx`/`.pptx`. Try `python -m markitdown` first |
| Multi-master confusion | Check `extract_template.py` output — it skips "Office Theme" masters and picks the non-Office-Theme master with the most layouts. If the wrong master is selected (too few layouts listed), inspect the "Masters" summary line and verify layout counts match expectations |
| Layout renders are blank | Ensure LibreOffice or PowerPoint COM is available for rendering |
| VLM subagent returns bad data | Review preview images manually — they may be low quality or blank |
| Profile missing semantic fields | Re-run Steps 3-4 (VLM analysis). Delete cached profile to force refresh |
| Template has no sample slides | Normal — Step 4 is skipped, profile will have empty `sample_slide_catalog` |
| `aesthetic_principles` is null | Fewer than 3 content-bearing sample slides — expected behavior, not an error. `design_language` and per-slide classifications are still available |
