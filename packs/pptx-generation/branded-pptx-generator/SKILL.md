---
name: branded-pptx-generator
description: >
  Generate a brand-compliant .pptx from an enterprise template plus a
  user content brief. Operates in three modes — strict, balanced, creative —
  that govern design authority over template layers (brand identity, design
  system, demonstration). Consumes the template-profile.json produced by
  the pptx-profiler skill, plans a deck with a shared style policy, then
  generates slides via four strategies: clone-sample, clone-layout,
  augmented-clone, or spec-composed.
  USE WHEN a user uploads a .potx/.pptx template alongside content or asks
  to "make slides like this", "match our brand", "use this template",
  "corporate deck", or "follow this style". Also use when a user uploads an
  existing branded deck and wants a new deck in the same style.
  DO NOT USE for: profiling a template (use pptx-profiler), reading content from
  existing decks (use pptx), or creating slides without a template (use pptx).
compatibility: Requires Python 3.10+ with python-pptx and lxml. PowerPoint COM or LibreOffice for rendering.
---

# Branded PPTX Generation

## Purpose

Turn `(template + content brief)` into a finished, brand-compliant `.pptx`.

## Architecture

### Guiding Posture (summary)

The template is the law. Claude is the steward, not the author. The
three modes (strict / balanced / creative) are three distinct working
postures that govern how much design authority Claude exercises over
the template's three pillars (brand identity, design system,
demonstration).

For the full posture, the three personas, the mode manifesto, and how
to handle mode conflicts, see
[references/mode-philosophy.md](references/mode-philosophy.md). Read
it at the start of every session.

**Dependency: `pptx-profiler` skill** (template analysis)

Located at `$PROFILER_SKILL` = `$SKILLS_ROOT/pptx-profiler`.
Produces `$PROFILE` (`{Brand}.profile/template-profile.json`) and
`composer-digest.json`.

**Tools from the `pptx` skill** (deterministic PPTX operations)

Located at `$PPTX_SKILL/scripts/` where `$PPTX_SKILL` = `$SKILLS_ROOT/pptx`.

| Tool | Purpose |
|------|---------|
| `office/unpack.py` | Unpack `.pptx` → XML directory |
| `office/pack.py` | Pack XML directory → `.pptx` (with validation) |
| `add_slide.py` | Clone an existing slide or create one from a layout |
| `clean.py` | Remove orphaned slides and resources |
| `office/soffice.py` | Render `.pptx` → PDF via LibreOffice |
| `office/validate.py` | OOXML schema validation + auto-repair |
| `office/potx2pptx.py` | Convert `.potx` → `.pptx` (patch ContentType) |
| `markitdown` | Quick text extraction (`python -m markitdown`) |

**This skill's tools** (final compliance check)

Located at `$SKILL/scripts/` where `$SKILL` = `$SKILLS_ROOT/branded-pptx-generator`.

| Tool | Purpose | Status |
|------|---------|--------|
| `validate_plan.py` | Step 5 checkpoint — JSON Schema + business rules (taskId uniqueness, bookends, divider consistency, mode×strategy, layoutRef existence, theme-slot palette, plan/policy mode alignment) | ✅ Available |
| `compliance_checker.py` | Locked-tier compliance check on final `.pptx` | ✅ Available |
| `extract_slide_elements.py` | Raw structural extraction of a sample slide for on-demand design analysis | ✅ Available |

**This skill's reference artifacts** (schemas and prompts)

| Artifact | Purpose |
|----------|---------|
| `schemas/content_outline_schema.json` | JSON Schema for `content-outline.json` (Step 4) |
| `schemas/slide_plan_schema.json` | JSON Schema for `slide-plan.json` (Step 5a) |
| `schemas/style_policy_schema.json` | JSON Schema for `style-policy.json` (Step 5b, incl. aestheticGuidance) |
| `schemas/slide_design_schema.json` | Output schema for slide visual design analysis (Phase 1+2) |
| `schemas/*.example.json` | Filled-in examples: content_outline, slide_plan, style_policy, slide_content, generation_report |
| `prompts/annotate-slide-design.md` | VLM subagent prompt for Phase 2 semantic annotation |

**Claude's own capabilities** (judgment and generation)

- Mode inference from the user's request
- Outline + slide plan + shared style policy authoring
- Per-slide content fitting, placeholder filling, XML edits
- python-pptx code generation for complex visuals
- Visual QA via subagents and fix-and-verify reasoning

---

## Workflow

**Skill path variables (initialization before any other command):**

```bash
export SKILLS_ROOT=".claude/skills"
export SKILL="$SKILLS_ROOT/branded-pptx-generator"
export PROFILER_SKILL="$SKILLS_ROOT/pptx-profiler"
export PPTX_SKILL="$SKILLS_ROOT/pptx"
```

Eleven core steps. Execute in order. Each step ends with a checkpoint.
Each step below lists the critical rules inline; for full procedural
detail, JSON examples, and edge cases, read the linked per-step
reference before executing that step.

### Step 1 — Obtain Template Profile

```bash
TEMPLATE="templates/<Brand>.potx"                       # user-provided
TEMPLATE_FOLDER=$(dirname "$TEMPLATE")
TEMPLATE_FILE=$(basename "$TEMPLATE")
BRAND=$(basename "$TEMPLATE" | sed 's/\.\(potx\|pptx\)$//')

PROFILE_DIR="$(pwd)/${TEMPLATE_FOLDER}/${BRAND}.profile"
PROFILE="${PROFILE_DIR}/template-profile.json"
DIGEST="${PROFILE_DIR}/composer-digest.json"
```

- **If both files already exist** and the template hasn't changed,
  reuse them.
- **Otherwise**, run the `pptx-profiler` skill end-to-end:

  ```
  Read $SKILLS_ROOT/pptx-profiler/SKILL.md and execute its workflow
  on $TEMPLATE. Produce $PROFILE and $DIGEST (preview renders are
  cached in $PROFILE_DIR).
  ```

`composer-digest.json` is the smaller, decision-ready summary —
prefer reading it during planning. Its structure is defined by
`$SKILLS_ROOT/pptx-profiler/schemas/composer_digest_schema.json`.
Fall back to the full `$PROFILE`
only when you need raw structural details (placeholder idx, exact
positions, etc.).

**Checkpoint:** `$PROFILE` and `$DIGEST` exist. Layouts have
`inferred_type`, `content_capacity`; `design_language` is populated;
sample slides (if any) have `role` and clone-suitability fields
(`cloneCandidate`, `layoutRelationship`, `styleSourceType`,
`styleRefSuitability`, `layoutMismatchSummary`).

### Step 2 — Determine Mode

Three modes governing design authority over template layers. Each mode
is a distinct working persona — see
[references/mode-philosophy.md](references/mode-philosophy.md) for the
full persona descriptions, when each fits, and the mode manifesto.

| Mode | Brand Identity | Design System | Demonstration |
|---|---|---|---|
| `strict` | **Rule** | **Rule** | **Rule** |
| `balanced` | **Rule** | **Rule** | Reference |
| `creative` | **Rule** | Reference | Reference |

- **Strict** — Content-filling machine. No design decisions.
- **Balanced** — Follows the style guide, interprets examples.
- **Creative** — Creates within the brand; template is inspiration.

Read the user's request **and** `$DIGEST`. Two signal sources:

1. **Content purpose** (from the user's request) — the primary signal.
   Formal/regulated → strict. Standard business → balanced.
   Expressive/audience-facing → creative.
2. **Template richness** (from `$DIGEST → template`) — a secondary nudge.
   Layout-rich templates (>10 layouts + multiple samples) lean strict;
   minimal templates (3–5 layouts, few/no samples) lean creative.

When the two signals conflict, content purpose wins.
Default to `balanced` when unclear.

**Checkpoint:** A single mode chosen. If the request was ambiguous,
note your reasoning (including template richness factor) briefly to
the user.

### Step 3 — Set Up Session Directory

```bash
MODE="<mode>"                                           # from Step 2
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SESSION="sessions/${TIMESTAMP}_${BRAND}_${MODE}"

mkdir -p "$SESSION"
cp "$TEMPLATE" "$SESSION/"
cd "$SESSION"
```

All subsequent commands run from `$SESSION`.

**Checkpoint:** `$SESSION/<Brand>.potx` (or `.pptx`) exists.

### Step 4 — Create Content Outline

Analyze the user's request → `content-outline.json` with intent, narrative
arc, and per-slide semantic role allocation. Pure LLM reasoning.

- **Outputs:** `content-outline.json` (schema:
  [schemas/content_outline_schema.json](schemas/content_outline_schema.json)).
- **Key rules:** One `cover` + one `closing`; sections with ≥ 2 body slides
  get a `divider`; respect user's slide count or default 8–12.
- **Checkpoint:** Slide counts sum to total; every slot has a `semanticRole`.

> Full procedure: [references/step4-content-outline.md](references/step4-content-outline.md)

### Step 5 — Plan the Deck

Two artifacts in one pass: `slide-plan.json` (layout mapping) +
`style-policy.json` (shared style), plus `slide-content.json` (full text).

#### 5a — Build the slide plan

Map each slide slot to a template layout using `$DIGEST`. Select strategy
per slide: `clone-sample` > `clone-layout` > `augmented-clone` > `spec-composed`
(lightest that works). See
[references/generation-modes.md](references/generation-modes.md) for
mode-dependent strategy availability.

#### 5b — Freeze the shared style policy

One `style-policy.json` for the whole deck. Pull values from `$DIGEST →
designDirectives`. Populate `aestheticGuidance` from `$DIGEST →
aestheticPrinciples` when available.

#### 5c — Generate slide content

Produce `slide-content.json` with capacity-aware text sizing per layout
placeholder. All content authored in a single pass for cross-slide
consistency. Agenda page numbers deferred as `"TBD"`.

- **Checkpoint:** `slide-plan.json`, `style-policy.json`, and
  `slide-content.json` exist; plan respects consistency rules. Schemas:
  [slide_plan_schema.json](schemas/slide_plan_schema.json),
  [style_policy_schema.json](schemas/style_policy_schema.json).

```bash
python $SKILL/scripts/validate_plan.py "$SESSION" --profile $PROFILE
```

> Full procedure (5a–5c, including aestheticGuidance enrichment and
> capacity-aware sizing): [references/step5-deck-plan.md](references/step5-deck-plan.md)

### Step 6 — Initialize the Working PPTX

Convert `.potx` → `.pptx` if needed, then unpack for XML editing.

```bash
python $PPTX_SKILL/scripts/office/potx2pptx.py "$TEMPLATE_FILE" -o "$PPTX_FILE"  # if .potx
python $PPTX_SKILL/scripts/office/unpack.py "$PPTX_FILE" unpacked/
```

- **Checkpoint:** `unpacked/ppt/presentation.xml` exists.

> Full procedure: [references/step6-init-pptx.md](references/step6-init-pptx.md)

### Step 7 — Generate Slides

Process slides grouped by strategy. Delegate per-slide XML editing to
subagents. All XML edits follow the
[XML Editing Rules](references/xml-editing-rules.md).

**Critical rules:**

- **Always delegate** per-slide editing to subagents — keeps the main
  context clean. Run `add_slide.py` for all slides first, update
  `<p:sldIdLst>` in one pass, then dispatch one subagent per slide.
- **Use exact text** from `slide-content.json` — subagents must not
  invent or modify content.
- **Theme references over hex** for any added/modified elements.
- **Mode boundaries hold:** `augmented-clone` is forbidden in `strict`;
  `spec-composed` is forbidden in `strict` unless no layout fits at all.

| Strategy | Approach |
|---|---|
| `clone-sample` / `clone-layout` | `add_slide.py` then edit XML |
| `augmented-clone` | Clone + structural modifications |
| `spec-composed` | See [references/spec-composed-strategy.md](references/spec-composed-strategy.md) |

- **Checkpoint:** Every task in `slide-plan.json` has a `<p:sldId>` entry.

> Full procedure (subagent prompt template, per-strategy details):
> [references/step7-generate-slides.md](references/step7-generate-slides.md)

### Step 8 — Assemble & Pack

Drop template sample slides, reorder to match plan, rebuild sections,
clean orphans, patch agenda page numbers, detach stale chart data,
verify chart cache integrity, reject `<p:cxnSp>` connectors, then pack.

**Critical rules (each is a confirmed PowerPoint repair trigger if skipped):**

- **Rebuild `<p14:sectionLst>`** — template's section list still
  references old sample slide IDs; replace entirely with new sections
  from `content-outline.json`.
- **Clean `[Content_Types].xml`** — `clean.py` does NOT remove `<Override>`
  entries for deleted files; orphans cause repair prompts.
- **Detach stale chart `<c:externalData>`** — any edited chart's
  embedded `.xlsx` is stale; remove the ref + delete the xlsx.
- **Verify chart `<c:ptCount>` matches `<c:pt>` count** — subagents
  often change data points without updating the count.
- **Reject `<p:cxnSp>` connectors before packing** — they pass all
  automated checks but cause PowerPoint COM to refuse the file.

```bash
python $PPTX_SKILL/scripts/clean.py unpacked/
python $PPTX_SKILL/scripts/office/pack.py unpacked/ output.pptx --original $TEMPLATE_FILE
```

- **Checkpoint:** `output.pptx` is valid OOXML; no `<p:cxnSp>` elements;
  no orphaned `[Content_Types].xml` entries.

> Full procedure (10 sub-steps with snippets):
> [references/step8-assemble-pack.md](references/step8-assemble-pack.md)

### Step 9 — Check Compliance

```bash
python -m markitdown output.pptx | grep -iE "xxxx|lorem|ipsum|click to|insert"
python $SKILL/scripts/compliance_checker.py output.pptx --profile $PROFILE --output compliance-report.json
```

- **Checkpoint:** No leftover placeholders; zero locked violations.

> Full procedure: [references/step9-compliance.md](references/step9-compliance.md)

### Step 10 — Inspect Visuals

Run schema validation, render slide previews, and launch a visual QA
subagent. See [references/brand-compliance.md](references/brand-compliance.md)
for what to check.

**Critical rules:**

- **Validate before rendering.** Run `validate.py --original $TEMPLATE_FILE
  --auto-repair` first; do not spend tokens on visual QA if the file is
  structurally invalid.
- **Always use a subagent** for visual inspection — never self-inspect,
  even for 2–3 slides. The #1 thing to flag is style drift across
  recurring elements (dividers, covers).
- **Render at `--width 1920`** so the subagent can read fine details.
- **Locked elements are visual-only:** logo positions, footer structure,
  disclaimer/copyright are not covered by `compliance_checker.py` —
  the subagent must verify them.

```bash
python $PPTX_SKILL/scripts/office/validate.py output.pptx --original $TEMPLATE_FILE --auto-repair
python $PROFILER_SKILL/scripts/render_samples.py output.pptx -o slide-previews/ --width 1920
```

- **Checkpoint:** Issue list collected from validator + subagent.

> Full procedure (full subagent prompt template):
> [references/step10-inspect-visuals.md](references/step10-inspect-visuals.md)

### Step 11 — Fix, Verify & Deliver

Fix issues at source → re-pack → re-render → re-inspect. Maximum 1
fix-and-verify cycle.

**Critical rules:**

- **Fix at source**, not in the packed `.pptx`. Edit `unpacked/` then
  re-pack.
- **Recompute agenda page numbers** if fixes added/removed slides
  (same procedure as Step 8 sub-step 6).
- **Maximum 1 cycle.** If issues persist after one fix pass, deliver
  with a written summary of remaining issues — don't loop.
- **Write `generation-report.json`** capturing mode, slide count,
  layouts used, strategy mix, compliance result, unresolved issues.

```bash
cp output.pptx "outputs/${BRAND}_${MODE}_${TIMESTAMP}_${TOPIC_SLUG}.pptx"
```

- **Outputs:** `generation-report.json`, final `.pptx` in `outputs/`.

> Full procedure (report schema, naming convention):
> [references/step11-fix-deliver.md](references/step11-fix-deliver.md)

---
## Output Artifacts

```
$TEMPLATE_FOLDER/
└── {Brand}.profile/                  # produced by pptx-profiler, reused here
    ├── template-profile.json
    ├── composer-digest.json
    ├── slide-elements-slide{N}.json  # Phase 1 extraction cache (on demand)
    └── slide-design-slide{N}.json    # Phase 1+2 full analysis cache (on demand)

$SESSION/
├── {Brand}.potx                      # copy of source template
├── content-outline.json              # Step 4
├── slide-plan.json                   # Step 5a
├── style-policy.json                 # Step 5b
├── slide-content.json                # Step 5c
├── unpacked/                         # editable XML (Step 6–8)
├── output.pptx                       # final deck (Step 8, working name)
├── compliance-report.json            # compliance checker output (Step 9)
├── generation-report.json            # final summary report (Step 11)
├── slide-previews/                   # rendered previews (Step 10)
│   └── slide{N}.jpg
└── generate_{taskId}.py              # only for spec-composed / augmented-clone slides

outputs/
└── {Brand}_{mode}_{timestamp}_{topic_slug}.pptx   # delivered deck (Step 11)
```

---

## XML Editing Rules

See [references/xml-editing-rules.md](references/xml-editing-rules.md)
for the full list. Key rules: use `lxml.etree` (never stdlib ET),
never use `<p:cxnSp>` connectors, reference theme color slots over hex.

---

## Style Consistency Principles

These are the failure modes that distinguish a "branded" deck from a
generic one. Internalize them:

1. **One source per recurring slide kind.** Every section divider
   clones the same source slide. Cover and closing come from the same
   family. Decided once in `style-policy.json`, not per slide.
2. **Theme references over hex.** Always reference theme color slots
   (`accent1`, `dk1`, …) so the deck recolors correctly if the template
   is updated.
3. **Same `semanticRole` → same `layoutRef`.** Don't randomize layout
   choice for similar content unless the user asked for variation.
4. **Variety across body slides, not within recurring elements.**
   Avoid using the same body layout for every content slide, but never
   sacrifice divider/cover consistency for variety.
5. **WCAG always.** Title ≥ 3:1, body ≥ 4.5:1, regardless of mode.

---

## Troubleshooting

| Problem | What to check |
|---|---|
| Locked violation: off-theme color | A slide has hardcoded `<a:srgbClr>`. Replace with `<a:schemeClr val="accent1"/>` etc. Re-run Step 9 |
| Text overflows or wraps unexpectedly | Inspect `<a:ext>` on the shape's `<a:xfrm>`; either shorten content or split slides |
| Section dividers look different from each other | Step 5a violation — they must share `cloneSource`. Regenerate the affected slides |
| Merged spec-composed slide loses theme | The new slide's `.rels` references a slideLayout that doesn't exist in this PPTX. Fix the rels target |
| `pack.py` validation fails | Run `validate.py --auto-repair` first; if still failing, inspect for malformed XML from `str_replace` edits |
| Subagent reports style drift | Check that all affected slides reference the same `style-policy.json` entries; common cause is a forgotten hardcoded font in a `spec-composed` slide |
| Template has no sample slides | Step 5a must use `clone-layout` (or `spec-composed`) for every slide. Style policy still applies |
| Stale section grouping in output | Template's `<p14:sectionLst>` still references old sample slides. Step 8 sub-step 2 was skipped — replace the entire section list with new sections from `content-outline.json` |
| Profile missing semantic fields | Re-run `pptx-profiler` Steps 3–4; do not proceed without `inferred_type` and `content_capacity` |
| PowerPoint repair prompt on open | Most common causes: (1) chart XML data edited but embedded `.xlsx` is stale — remove `<c:externalData>` refs; (2) `<c:ptCount>` doesn't match actual `<c:pt>` count in chart cache — fix the count; (3) `[Content_Types].xml` has `<Override>` entries pointing to deleted files — clean orphans after `clean.py` |
| Spec-composed slide ignores template styling | The generated slide's `.rels` references a slideLayout but the slide XML has no `<p:ph>` placeholders — it's all standalone textboxes. Rebuild with `<p:ph type="title"/>` etc. so the layout's fonts/positions/colors are inherited |
| Chart "Edit Data" doesn't work | Expected if `<c:externalData>` was removed (Step 8 sub-step 6). Charts render from cache. Re-link an xlsx only if the user needs to edit chart data in PowerPoint |
| Cloned slide renders blank | The slide's `.rels` points to a non-existent slideLayout. Check `unpacked/ppt/slides/_rels/slide{N}.xml.rels` — the `rId1` target must match an existing `slideLayouts/slideLayout{M}.xml` |
| PowerPoint COM won't open file at all | **CRITICAL:** `xmlns:ns0`/`ns1` namespace prefix corruption from `xml.etree.ElementTree`. Run `grep -rl "xmlns:ns[0-9]" unpacked/` — any hit outside `customXml/` is corrupted. Restore from template and re-apply edits using `lxml.etree` |
| PowerPoint COM won't open file but lxml/python-pptx/validate.py all pass | **CRITICAL:** A spec-composed slide likely contains `<p:cxnSp>` connector shapes. Run `grep -rl "cxnSp" unpacked/ppt/slides/` to find the offending slide. Replace all `<p:cxnSp>` with `<p:sp>` using `prstGeom prst="line"` and `<a:tailEnd type="triangle"/>` for arrows. If conversion fails, regenerate the slide from scratch using pure lxml.etree with only `<p:sp>` shapes. Binary-search by removing slides from `<p:sldIdLst>` to isolate which slide is the culprit |

> **⚠ MANDATORY RULE: Never use `xml.etree.ElementTree` to read/write OOXML files.**
> Always use `lxml.etree` — stdlib ET rewrites namespace prefixes, causing
> PowerPoint to refuse to open the file.

---

## Reference Docs

Read these when designing complex slides or debugging compliance issues —
not needed for normal operation.

| Reference | Covers |
|---|---|
| [mode-philosophy.md](references/mode-philosophy.md) | Core posture, three pillars of brand authority, three modes as personas, mode manifesto |
| [step4-content-outline.md](references/step4-content-outline.md) | Step 4 — content outline (intent, narrative arc, section/role allocation) |
| [step5-deck-plan.md](references/step5-deck-plan.md) | Step 5 — slide plan, style policy (incl. aestheticGuidance enrichment), capacity-aware content sizing |
| [step6-init-pptx.md](references/step6-init-pptx.md) | Step 6 — potx→pptx conversion, unpack |
| [step7-generate-slides.md](references/step7-generate-slides.md) | Step 7 — subagent delegation, per-strategy generation (clone-sample/layout, augmented-clone, spec-composed) |
| [step8-assemble-pack.md](references/step8-assemble-pack.md) | Step 8 — 10 sub-steps for assembly: sldIdLst, sectionLst, Content_Types, app.xml, agenda numbers, chart cleanup, cxnSp gate, pack |
| [step9-compliance.md](references/step9-compliance.md) | Step 9 — leftover-text grep + locked-tier compliance check |
| [step10-inspect-visuals.md](references/step10-inspect-visuals.md) | Step 10 — schema validation, render, full visual-QA subagent prompt |
| [step11-fix-deliver.md](references/step11-fix-deliver.md) | Step 11 — fix-and-verify cycle, delivery, generation-report.json schema |
| [xml-editing-rules.md](references/xml-editing-rules.md) | Mandatory XML editing rules for all direct OOXML edits |
| [generation-modes.md](references/generation-modes.md) | Per-dimension decision matrix (layout, typography, color, shapes, density, placeholders) and absolute invariants |
| [slide-design-analysis.md](references/slide-design-analysis.md) | On-demand VLM analysis of a sample slide for `spec-composed` strategy — full subagent prompt and output schema |
| [brand-compliance.md](references/brand-compliance.md) | Three-tier compliance model (Locked/Guided/Flexible), WCAG rules, augmentation constraints, per-step checklist |
| [spec-composed-strategy.md](references/spec-composed-strategy.md) | Step 7c full procedure — style spec, python-pptx coding rules, merge into `unpacked/` |
| [content_outline_schema.json](schemas/content_outline_schema.json) | JSON Schema for `content-outline.json` |
| [slide_plan_schema.json](schemas/slide_plan_schema.json) | JSON Schema for `slide-plan.json` |
| [style_policy_schema.json](schemas/style_policy_schema.json) | JSON Schema for `style-policy.json` (incl. aestheticGuidance) |
| [*.example.json](schemas/) | Filled-in examples: content_outline, slide_plan, style_policy, slide_content, generation_report |
