---
name: narrative-pptx-composer
description: >
  Compose a narrative-driven .pptx from content documents (.md, .txt,
  .docx, .pdf, .pptx), a chat brief, or reference images (slide screenshots,
  sketches, wireframes, mood references). Content strategy first
  (audience, narrative, messaging), then design.
  USE WHEN the user asks to: "turn this report into a presentation", "make a deck that
  persuades the board", "present these findings", "create a pitch",
  "turn this image/sketch/screenshot into a PPT", "beautify this PPT",
  "turn this deck into a new presentation", "re-narrate this PPT".
  DO NOT USE for pixel-perfect replication of an existing slide image
  (edit the source file instead), template profiling (pptx-profiler),
  reading existing decks (pptx), or brand-compliance-first generation
  (branded-pptx-generator).
compatibility: Requires Python 3.10+ with python-pptx, Pillow. PowerPoint COM or LibreOffice for rendering.
---

# Narrative PPTX Composer

## Purpose

Turn content into a finished `.pptx` that tells a compelling,
audience-aware story. Content first, design second.

## Global Rules

These apply across all steps. Do not repeat-check per step.

**Priority order:** Content → Narrative → Design; higher pillar wins. See [design-principles.md](references/design-principles.md).

**Workflow invariants:**
- All nine steps run in order for every input modality. **No skip-paths, no merged-step shortcuts.**
- **Completion gate:** the workflow is **incomplete** until `s09-session-retrospective.json` exists. Step 7's `output.pptx` is a **draft** — it is not reviewed, not delivered, and not announced to the user. Stopping after Step 7 is a workflow violation.
- Large decks: when a step's total output would exceed what fits in a single coherent pass, split by acts per [references/batching-strategy.md](references/batching-strategy.md). Each step self-assesses whether to batch.
- Agenda page numbers use the em-dash placeholder `"—"` (never `"TBD"`) in Steps 4/5/6; patched in Step 7c.
- Cross-slide consistency: numbers match `s04a-terminology-registry.json`; only `canonical` forms; low-confidence data points (`confidence < 0.7`) use `qualitativeForm`.

---

## Tools

| Tool | Purpose |
|------|---------|
| `markitdown` | Text extraction from `.pptx`, `.docx`, `.pdf` (`python -m markitdown <file>`) |
| `$PROFILER_SKILL/scripts/render_samples.py` | Renders `.pptx` slides to JPEG. **Mandatory for Step 8a.** |
| `$IMAGE_SKILL/scripts/generate_images.py` | Batch image generation from JSON request. See `$IMAGE_SKILL/SKILL.md`. |

Skill-internal scripts live in `$COMPOSER_SKILL/scripts/`. Each step section below invokes the relevant ones with full commands.

---

## Workflow

```
Step 1: Input Registry
Step 2: Communication Brief
Step 3: Narrative Blueprint
Step 4: Content Draft & Form Specification
Step 5: Slide Visual Design
Step 6: Content–Zone Fitting & Speaker Notes
Step 7: Build PPTX              ← output.pptx is DRAFT, not deliverable
Step 8: QA, Fix & Deliver       ← first deliverable copy to outputs/
Step 9: Session Retrospective   ← workflow complete only after this step
```

---

### Step 1 — Input Registry

> Full procedure: [references/step1-input-registry.md](references/step1-input-registry.md)

**Session initialization (1a, before any other command):**

```bash
export SKILLS_ROOT=".claude/skills"
export COMPOSER_SKILL="$SKILLS_ROOT/narrative-pptx-composer"
export PROFILER_SKILL="$SKILLS_ROOT/pptx-profiler"
export IMAGE_SKILL="$SKILLS_ROOT/image-generator"
```

If unset, validators and rendering fail silently.

Four sub-tasks: (1a) session directory; (1b) classification → `s01b-query-intent.json`; (1c) content extraction → `s01c-content-digest.json`; (1d) design registration → `s01d-design-config.json`. **1c and 1d co-execute in one pass.** Optional: `1c-pptx` for `.pptx` docs, `1c-image` for image inputs (three-track VLM).

**Guard rules:**

- **Registry only, not analysis.** No audience/purpose/formality inference (→ Step 2), no `imageryDemand` (→ Step 3a), no palette/typography/style (→ Step 5b). Only infer `language` and `inputMode`.
- **`inputMode`** set in 1b, locked. One of `generate`/`beautify`/`reproduce`/`expand`.
- **`s01b.inferences[]`** whitelisted to `language` + `inputMode` only — validator hard-fails others.
- **`s01d` resolution:** user-explicit → reference-image (VLM) → deferred. Non-supplied design fields → `null` + `deferred-step5b`. Only `dimensions` (16:9) and `monoFont` (`JetBrains Mono`) get `system-default`.
- **`sourceProvenance`** (origin tag) mandatory per leaf: `user-explicit` / `reference-image` / `system-default` / `deferred-step5b`. Null↔deferred coupling enforced.
- **Media:** extract images/diagrams into `mediaAssets`; log conflicts in `mergedSections.conflicts[]` — never block.

**Outputs:** `s01b-query-intent.json`, `s01c-content-digest.json`, `s01d-design-config.json`; optionally `s01c-image-style-extraction.json`.

```bash
python $COMPOSER_SKILL/scripts/s01_validate_inputs.py "$SESSION"
```

---

### Step 2 — Communication Brief

> Full procedure: [references/step2-comm-brief.md](references/step2-comm-brief.md)

Pure LLM reasoning — **no design knowledge**. Always runs (mandatory for every modality). Sparse signals → thin brief with `inferences` + `confidence`.

**Guard rules:**

- Consume `s01b.explicitSignals` verbatim. **Step 2 owns all audience/purpose inference.**
- Single-pass: `presentationPurpose` (∈ inform/persuade/report/propose/inspire) + `purposeStatement`; `audience`; `communicationObjectives` (think/feel/do); `keyMessages` (1–5); `constraints` (language, formalityLevel, optional timeMinutes).
- **Out of scope:** `slideCountConstraint` (→ Step 3c), `imageryDemand` (→ Step 3a).
- `audience.decisionPower` required when purpose ∈ {persuade, propose, report}.
- Brief-only mode: infer all unsupported fields; record in `inferences` with `confidence`. **Never block to ask.**

**Outputs:** `s02-communication-brief.json`

```bash
python $COMPOSER_SKILL/scripts/s02_validate_brief.py "$SESSION"
```

---

### Step 3 — Narrative Blueprint

> Full procedure: [references/step3-narrative-blueprint.md](references/step3-narrative-blueprint.md) | Patterns: [references/storytelling-patterns.md](references/storytelling-patterns.md)

Pure LLM reasoning — **no design knowledge**. Three sub-phases: (3a) narrative architecture, (3b) structural scaffolding, (3c) per-slide blueprint.

**Guard rules — 3a:**

- Five sub-tasks: core argument, pattern & acts, act transitions, opening hook & closing takeaway, information hierarchy.
- Pattern paths: reuse / compose / nest / design new. Record `origin`. Justify from content+audience, not the pattern table.
- **Core argument:** falsifiable claim (not vague topic). Derive from `s02.keyMessages[rank=1]`; log any departure in `inferences[]`.
- Every `cut` item needs `reason`.

**Guard rules — 3b:**

- Decide structural slides (executive summary, agenda, dividers, recap, appendix). Executive summary ↔ opening hook mutually exclusive. Appendix excluded from `totalSlides`.
- **Section dividers:** include only when (a) each act has enough body slides to justify a structural marker (minimum depth ≥ 2 — a single-slide act makes its divider feel hollow), AND (b) the total divider count stays well below ~25 % of body slides (avoids over-scaffolding). Never asymmetric — all acts or none.

**Guard rules — 3c:**

- Per-slide fields: `slideId`, `headlineMessage`, `narrativeRole` (story function), `slideType`, `narrativeIntent` (delivery mode), `transitionIn`/`Out`, `informationDensity`, `contentSource`, `sourceRef`.
- **Slide count is bottom-up.** `slideCountConstraint` clamped here (single decision point). Exactly one `cover` + one `closing`. Step 5 may not insert/remove slides.
- **Pacing rule:** every 6–8 body slides ≥ 1 with `informationDensity: "minimal"`.
- Every body slide MUST have `headlineMessage`. Structural slides may leave null.
- Adjacent `transitionOut[N]` / `transitionIn[N+1]` must be logically coherent. If incoherent: revise N+1's `transitionIn` to align.
- **Media:** assign `mediaAttachments` from `s01c.mediaAssets`; each on ≤ 1 slide.
- **Illustration intent:** single decision point for the illustration roster. Run minimum imagery check. Step 5 may not back-fill or demote. Field shape: [step3-narrative-blueprint.md § illustrationIntent](references/step3-narrative-blueprint.md).
- Document mode: `supportingPoints` need `sourceRef`; numbers match `preGlossary` (initial term list from content extraction).

**Outputs:** `s03-presentation-blueprint.json` (embeds `architecture`: core argument, pattern, acts, hooks, hierarchy, scaffold, `contentDomain`, `imageryDemand` (deck-level imagery budget), `imageryDemandRationale`).

```bash
python $COMPOSER_SKILL/scripts/s03_validate_blueprint.py "$SESSION"
```

---

### Step 4 — Content Draft & Form Specification

> Full procedure: [references/step4-content-draft.md](references/step4-content-draft.md)

Write per-slide content (4b) and choose `contentForm` per slide (4c). Form is a **content decision**, not visual design.

**Guard rules:**

- **4a — Terminology registry.** Seed from `s01c.preGlossary` (initial term list) before 4b; finalize after. Every `dataPoints` entry: `verificationTier` (verified/common-knowledge/unverified) + `confidence` (0.0–1.0). Low-confidence precise numbers also get `qualitativeForm`.
- **Source rules:** `document` → no fabrication; `generated`/`hybrid` → numbers from registry.
- **Headlines** faithfully render blueprint's `headlineMessage`.
- **4c — `contentForm`** (`{type, ...counts}`). No spatial structure → `text-narrative` / `bullet-list`. Do not pre-name a layout.
- **`blocks[]`** for multi-zone types (`card-grid`, `comparison-matrix`, `timeline`, `step-flow`, `stat-callout`, `architecture-layers`, `before-after`, `diagram-callouts`, `icon-list`): one entry per zone with `role`, `headline`, `body`. Single-zone → empty.
- **Content metrics** auto-derived by validator. Do not hand-fill.
- **4c-illust:** refine `illustrationIntent` → `illustrationSpec` with `source: "to-generate"`, `subject`, `perImageSubject`, `compositionNote`, `contentInteraction`.
- **4d — Speaker-note cues only.** Brief transition cue per slide (tone from `formalityLevel` + `audience`). Full talk track → Step 6c. Required: non-empty `speakerNotes` for every slide.

**Outputs:** `s04-content-draft.json`, `s04a-terminology-registry.json`.

```bash
python $COMPOSER_SKILL/scripts/s04_validate_content.py "$SESSION"
```

---

### Step 5 — Slide Visual Design

> Full procedure: [references/step5-visual-design.md](references/step5-visual-design.md) | Layout: [references/layout-principles.md](references/layout-principles.md) | Tone: [references/visual-tone-mapping.md](references/visual-tone-mapping.md)

Read before this step: [design-principles.md](references/design-principles.md), [design-guardrails.md](references/design-guardrails.md).

**Execution flow:**

```
5a  Fill deferred design fields (palette, fonts, contrast)
     ↓
5b  Derive visual tone from content strategy:
     - resolve register (authoritative/analytical/conversational/inspirational/instructional-rich)
     - set color temperature, whitespace rhythm, imagery guidance per act
     - write designThesis (one-sentence design concept + 2–4 mechanisms)
     - plan compositionPalette (layout vocabulary) and titleChoreography (title treatments)
     ↓
5c  Freeze s05b-style-policy.json — read-only from here on
     ↓
5d  Design each slide's layoutSpec (three phases per slide):
     Phase 1 — Concept: read context + review prior slides' moves →
               commit aestheticMove, palette family, and focal idea
               BEFORE drawing zones (→ designRationale)
     Phase 2 — Execute: choose grid → size zones → add decorations → set background
     Phase 3 — Verify: check geometry + confirm layout delivers the Phase 1 concept
     ↓
5f  Generate images (if needed):
     - collect all source:"generated" zones → image request file
     - run generate_images.py (backgrounds: 1 variant; illustrations: 3 variants)
     - VLM selects best illustration variant (best-of-3)
     - patch file paths back into the plan
```

**Guard rules:**

- **`designThesis` (mandatory, frozen at 5c).** Single sentence: what the design is *about* + 2–4 visible `mechanisms`. Verified in Step 8, compared in Step 9.
- **`aestheticSignals` (style preferences):** `designAmbition` (style intensity) overrides default (default: `"expressive"`; `restrained` only for explicit minimalism); `moodKeywords` bias 5d; `avoidKeywords` are hard exclusions; `diversityPreference: "high"` tightens quotas.
- **5d — Layout from `contentForm`.** Design from first principles per layout-principles.md. Preserve content's spatial structure. Generic layout for structured content → justify in `designRationale.aesthetic`.
- **Zone types:** `text`, `shape`, `chart`, `image`, `icon`, `formula`. Unknown type → validator hard-fails. Formula zones: `notation: "mathtext"`, `source: "authored"`, `fallback` block required.
- **Formula-zone mandate:** when content contains math equations or symbolic expressions, create `type: "formula"` zones — **never** embed formulas as Unicode text in `type: "text"` zones. Short inline symbols (σ, θ) are acceptable in prose; standalone equations must be formula zones.
- **Coordinate units:** inches by default (bare numbers). `"<N>%"` for percent. No mixing.
- **Design minimums** (4 quotas: layout variety, hero cadence, color-area, typographic punch): [visual-tone-design-floor.md](references/visual-tone-design-floor.md). Auto-relax with `quotaWaiver`; never block.
- **Minimum imagery requirements:** apply row for resolved `imageryDemand`. Step 3 owns the illustration roster; Step 5 may not add or remove illustration slots. Waiver needs reason ≥ 20 chars.
- **Cover–closing consistency (recommended):** cover ↔ closing share ≥ 1 decorative element in common. [step5d-slide-layout.md § Bookend](references/step5d-slide-layout.md).
- **Deck-wide decorative motifs** (`motifPalette`, recommended): 2–5 shape/pattern variations; slides classified as motif-bearing / decoration-free / non-motif. [step5d-slide-layout.md § motifPalette](references/step5d-slide-layout.md).
- **Illustration zones:** match `illustrationSpec` for `imageCount`, `placement`. Step 5 decides `imageShape` based on layout and available space. Every generated zone MUST have `fallback`.

**Outputs:** `s05-slide-visual-design.json` ([schema](schemas/s05-slide-visual-design.schema.json)), `s05b-style-policy.json`. If 5f: `s05f-image-requests.json`, `images/`, `s05f-image_generation_output.json`, `s05f-image-selection.json`.

```bash
python $COMPOSER_SKILL/scripts/s05_validate_plan.py "$SESSION"
```

---

### Step 6 — Content–Zone Fitting & Speaker Notes

> Full procedure: [references/step6-content-fitting.md](references/step6-content-fitting.md)

The **only step holding both content draft and real zone geometry** — owns fit end-to-end (no escape hatch to Step 4).

**Guard rules:**

- **6a — Map content to zones** by zone `role` names (not placeholders). `blocks[]` present → map by matching `role` (no splitting). `blocks[]` absent on multi-zone → heuristic split (informational log, not error).
- **Title compression (within Step 6 only):** Stage 1 syntactic (drop modifiers), then Stage 2 semantic (core claim stays; dropped framing → `speakerNotes`). Must always be complete statement. Validator warns at <40% token overlap (traceability signal, not escalation).
- **6b — Fit (two-stage).** Stage 1: syntactic compression (1:1 info). Stage 2: distilled view — demote secondary points to `speakerNotes`. Forbidden: merging claims, vaguer numbers, new facts, changing headline's core claim.
- **6c — Speaker notes** (full talk track, every slide, no exemptions). Tone from `formalityLevel` + `audience`. Integrate Stage 2 demoted material. Never repeat slide text verbatim.
- **Image slots:** `type: "image"`, `path`, `alt`. Source: `user-media` or `generated` (already patched in 5f).
- **Formula slots:** keyed by zone `role`; carry `formulaSource` (no `$…$` delimiters) + `alt` (≥10 chars, plain language). No `path`. See [build-script-template.md § Formula zones](references/build-script-template.md).

**Outputs:** `s06-slide-content.json`

```bash
python $COMPOSER_SKILL/scripts/s06_validate_content.py "$SESSION"
```

---

### Step 7 — Build PPTX

> Full procedure: [references/step7-build-pptx.md](references/step7-build-pptx.md) | Template: [references/build-script-template.md](references/build-script-template.md)

Write and execute `s07-build.py` using python-pptx. Import helpers from `$COMPOSER_SKILL/scripts/s07_slide_helpers.py`.

**Guard rules:**

- **7a — Per-`taskId` builder functions.** One `build_<taskId>` per slide (promote to shared `build_<composition>` only when ≥ 2 slides share identical pattern). **Disallowed:** single generic `build_slide(tid)` branching internally. Helpers: `add_textbox`, `add_card`, `add_accent_bar`, `add_rounded_rect`, `add_outline_capsule`, `add_outline_circle`, `add_image_safe`, `set_slide_bg`, `set_slide_bg_image`, `add_image_with_overlay`, `resolve_image_path`, `add_formula`, `render_formulas`.
- **Images:** insert ONLY via `add_image_safe()` / `add_image_with_overlay()` / `set_slide_bg_image()` (aspect-ratio preserving). Never use `slide.shapes.add_picture()` directly.
- **Formulas:** call `render_formulas()` once at top of `main()` (renders to `<session>/formulas/<taskId>-<role>.png`). Builders call `add_formula()` with cached path. No `$…$` in `formulaSource`; no SVG via `add_picture()`.
- **Illustration zones in every builder:** every builder function whose slide has an `illustration` zone in the plan MUST resolve and insert it via `resolve_image_path(plan_zone, slot)` + `add_image_safe()`. Omitting the illustration call silently drops the image — invisible until Step 8 visual QA. Audit: grep shared builders for illustration handling before dispatch.- **7c — `patch_agenda_pages()`** inline at end of `s07-build.py` before `prs.save()`. Not a separate file.

**Outputs:** `output.pptx`

```bash
python $COMPOSER_SKILL/scripts/s07_validate_build.py "$SESSION"
```

Checks: slide count matches s06; zone `path` files exist; no em-dash placeholder in labels (confirms 7c ran).

> **⛔ STOP — DO NOT announce completion or deliver to the user.** The `output.pptx` produced here is an **unreviewed draft**. Proceed immediately to Step 8.

---

### Step 8 — QA, Fix & Deliver

> Full procedure: [references/step8-qa-deliver.md](references/step8-qa-deliver.md)

**Track order: 8a → 8b → 8c → 8d → 8e → 8f → 8g.** Dimension-grading system (8b/8c): 4-level scale (pass/acceptable/marginal/fail) + open `anomalies[]`. Per-deck (8e): holistic aesthetic recommendations (no grading).

**Guard rules:**

- **8a — Render + QA baseline.** Render to `slide-previews/per-slide/` (JPEG count == slide count), then `s08_precompute_metrics.py` → `s08_cohort_definitions.py` → `s08_anchor_pack.py`. Generate once; both tracks consume it.
- **Dimensions.** Per-slide (8b): 7 (spatialContainment, textRendering, imageIntegrity, contentCompleteness, visualHierarchy, spatialOrganization, intentAlignment). Per-cohort (8c): 5 (typographicConsistency, proportionalConsistency, paletteConsistency, motifIntegrity, bookendSymmetry).
- **Pipeline (8b & 8c):** detect (subagent) → triage (deterministic `s08_triage.py`) → remediate (subagent, for `fail` + P1 anomalies) → designer applies (`s07-build.py` + `*-fix-decisions.json`) → verify (rebuild + re-detect). Per-slide detection batched 5/call; per-cohort one subagent per cohort.
- **Subagent mandatory** for detect + remediate (self-inspection is delivery blocker). Validate against schema before merge.
- **Fix scope:** 8b → single `build_sXX()` + `PERSLIDE_*_OVERRIDES`; 8c → `COHORT_OVERRIDES` + `COHORT_TO_MEMBERS`. Neither touches `s05`/`s06`/global constants.
- **Archive before edit:** rename `s07-build.py` → `s07-build.pre-perslide-fix.py` (8b) or `s07-build.pre-cohort-fix.py` (8c), and `output.pptx` → matching `pre-*-fix.pptx`.
- **Fix-decision completeness:** every `fail`/`marginal` dimension + P1+ anomaly appears exactly once in `decisions[]` (action: applied/dropped/deferred).
- **QA log:** append rounds with `roundType` ∈ {per-slide, per-slide-verify, per-cohort, per-cohort-verify, per-deck, per-deck-fix}. Each: `gradeSummary` + `anomalySummary`.
- **Budget:** 1 fix cycle each for 8b/8c (second allowed with `-2` suffix). Unresolved `fail` → `unresolvedItems[]`.
- **8d/8e/8f — Per-deck aesthetic evaluation:** contact sheet + samples → VLM holistic assessment → single fix pass. Skip 8f if zero recommendations.
- **8g — Delivery precondition:** latest preview dir has one JPEG per slide. Then `cp` to `outputs/`.

**Outputs:** `s08-zone-metrics.json`, `s08-cohort-definitions.json`, `s08-anchor-pack.json`, `s08-perslide-grades.json`, `s08-perslide-triaged.json`, `s08-perslide-remediations.json`, `s08-perslide-fix-decisions.json`, `s08-cohort-grades.json`, `s08-cohort-triaged.json`, `s08-cohort-remediations.json`, `s08-cohort-fix-decisions.json`, `s08e-perdeck-evaluation.json`, `s08f-perdeck-fix-decisions.json`, `s08-qa-log.json`, `s08g-generation-report.json` (includes `contentGrounding` — fact attribution), final `.pptx` in `outputs/`.

---

### Step 9 — Session Retrospective

> Full procedure: [references/step9-retrospective.md](references/step9-retrospective.md)

Structured analysis: problems, root causes, recommendations.

**Guard rules:**

- **9a — Evidence** from 5 categories (workflow, content/narrative, design/layout, QA/fix, environment/tooling). Sweep all artifacts, not memory alone.
- **9b — Root cause** per issue (one from: `workflow-gap`, `spec-ambiguity`, `code-quality`, `design-judgment`, `content-judgment`, `validation-miss`, `tooling-limitation`, `resource-constraint`). Pick most upstream.
- **9c — Recommendations** evidence-linked (≥ 1 issue ID + `estimatedPayoff: {timeSavedMinutes, affectedSessions, confidence}`). Priority: high/medium/low.
- **9d — `sessionInsights`:** `workedWell[]`, `worthSurprise[]`, `wouldChange[]` (≥ 1 entry combined).
- **`stepMetrics[]`:** one per step with `minutesSpent`, `retryCount`, (optional) `rootCauseCategory`.
- **`preventable` flag** per issue. When true: include `preventionMethod`.

**Outputs:** `s09-session-retrospective.json`

> **✅ Workflow complete.** Only now may the final `.pptx` (already in `outputs/` from Step 8g) be announced to the user.

---

## Session Artifact Layout

> Full directory tree, naming convention, routing rules: [references/session-layout.md](references/session-layout.md)

- **Naming:** `sN-{name}.json` = step's main output. `sN[letter]-{name}.json` = sub-task artifact (e.g. `s04a` = step 4, artifact a).
- **Schema contract:** Three artifacts have formal JSON Schema (blueprint, visual-design, qa-log). Others use `*.example.json` as spec.
- `sessions/` and `outputs/` are siblings at repo root — `outputs/` is NEVER a child of `sessions/`.
- Delivery is `cp` (session keeps its copy).

---

## Troubleshooting

| Problem | Check |
|---|---|
| Brief too vague | Infer in `s01b.inferences` with `confidence`. Never block. |
| Headlines lack narrative arc | Read all `headlineMessage` top-to-bottom; revise architecture |
| Content too dense | Check `informationDensity`; split or downgrade |
| Terminology drift | Scan s06 for `rejected` variants from registry |
| Zone overlap | Check `s05 → layoutSpec` coords; run `s05_validate_plan.py` |
| Visually plain | Add decorative shape zones; check `imageryDemand` resolved to `high` |
| python-pptx error | Check imports, `RGBColor`, `Inches`/`Pt` units |
| Unverified data | Check registry `verificationTier`; add `qualitativeForm` for low-confidence |

---

## Reference Docs

- **Design:** [design-principles.md](references/design-principles.md), [design-guardrails.md](references/design-guardrails.md), [visual-tone-mapping.md](references/visual-tone-mapping.md), [layout-principles.md](references/layout-principles.md)
- **Narrative:** [storytelling-patterns.md](references/storytelling-patterns.md)
- **Build:** [build-script-template.md](references/build-script-template.md), [python-pptx-guide.md](references/python-pptx-guide.md)
- **QA prompts:** [qa-reviewer-perslide-prompt.md](references/qa-reviewer-perslide-prompt.md), [qa-reviewer-cohort-prompt.md](references/qa-reviewer-cohort-prompt.md), [qa-reviewer-perdeck-prompt.md](references/qa-reviewer-perdeck-prompt.md), [qa-remediation-perslide-prompt.md](references/qa-remediation-perslide-prompt.md), [qa-remediation-cohort-prompt.md](references/qa-remediation-cohort-prompt.md)
- **Other:** [batching-strategy.md](references/batching-strategy.md), [image-extraction-prompt.md](references/image-extraction-prompt.md), [image-prompt-guide.md](references/image-prompt-guide.md), [vlm-image-selection.md](references/vlm-image-selection.md)
- **Per-step procedures:** [step1-input-registry.md](references/step1-input-registry.md) — [step9-retrospective.md](references/step9-retrospective.md)
- **Schemas:** [s03-presentation-blueprint.schema.json](schemas/s03-presentation-blueprint.schema.json), [s05-slide-visual-design.schema.json](schemas/s05-slide-visual-design.schema.json), [s08-qa-log.schema.json](schemas/s08-qa-log.schema.json), [s08e-perdeck-evaluation.schema.json](schemas/s08e-perdeck-evaluation.schema.json), [*.example.json](schemas/)
