# Step 8 — QA, Fix & Deliver

Full procedural detail for Step 8. See [SKILL.md](../SKILL.md)
for the mandatory rules summary.

Step 8 has seven sub-tracks:

| Sub-track                              | Scope                                                                                                               | Owner doc         |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ----------------- |
| **8a · Render + Anchor Pack**          | Render every slide to JPEG and precompute the deterministic data both QA tracks consume.                            | This file (§ 8a). |
| **8b · Per-slide QA**                  | Each slide inspected for defects → flat findings list. Modifies single-slide `build_sXX()` only.                    | This file (§ 8b). |
| **8c · Per-cohort QA**                 | Structurally-similar slide groups inspected for cross-member inconsistencies. Modifies via `COHORT_OVERRIDES` dict. | This file (§ 8c). |
| **8d · Per-deck Input**                | Generate contact sheet + select high-res sample slides for per-deck evaluation.                                     | This file (§ 8d). |
| **8e · Per-deck Aesthetic Evaluation** | VLM holistic aesthetic assessment of the full deck as a unit.                                                       | This file (§ 8e). |
| **8f · Per-deck Fix**                  | Designer applies per-deck recommendations → archive → rebuild → re-render.                                          | This file (§ 8f). |
| **8g · Deliver**                       | Copy artifacts + finalize qa-log + write generation report.                                                         | This file (§ 8g). |

> **Track ordering: 8a → 8b → 8c → 8d → 8e → 8f → 8g.**
> Per-slide first to flush hard defects, per-cohort next for family
> consistency, per-deck for holistic aesthetics, then deliver.
> If 8e produces zero recommendations, skip 8f.

---

## Findings System (shared by 8b and 8c)

Both QA tracks produce a **flat `findings[]` array** — one entry
per detected problem. Each finding is independently triaged,
remediated, and tracked through the fix pipeline.

### Finding schema

| Field             | Required | Description                                                                |
| ----------------- | -------- | -------------------------------------------------------------------------- |
| `dimension`       | yes      | Classification axis (open string — recommended values or VLM-created new). |
| `what`            | yes      | Concrete description of the problem.                                       |
| `severity`        | yes      | `"critical"` or `"minor"`.                                                 |
| `confidence`      | yes      | `"high"` / `"medium"` / `"low"`.                                           |
| `evidence`        | yes      | Location + measurement / visual feature (anti-hallucination).              |
| `fixDirection`    | yes      | Concise, clear, directional, no parameters; use OR for alternatives.       |
| `affectedMembers` | 8c only  | Array of slide ids affected (per-cohort findings only).                    |

### Dimension field

`dimension` is an **open enumeration**: the prompt provides
recommended scan axes that the VLM MUST check, but the VLM may
create new dimension names (camelCase, descriptive) for problems
that don't fit any recommended axis. Schema validates `dimension`
as `string` with no enum constraint.

### Priority mapping (deterministic)

Priority is determined purely by `severity × confidence`:

| Condition                                | Priority | Downstream action                   |
| ---------------------------------------- | -------- | ----------------------------------- |
| `severity=critical` AND `confidence≠low` | **P0**   | Must fix + gets remediation         |
| `severity=critical` AND `confidence=low` | **P1**   | Gets remediation; designer decides  |
| `severity=minor` AND `confidence=high`   | **P2**   | Designer discretion, no remediation |
| `severity=minor` AND `confidence≠high`   | **P3**   | Usually dropped                     |

### Evidence contract

- Every finding MUST carry at least one of: precise location, a
  measurement from metrics, or a specific visual feature visible
  in the JPEG.
- Findings with `evidence` < 30 chars AND `confidence=low` are
  dropped during post-processing.
- If evidence is weak, the VLM should assign `confidence=low`
  rather than inflating severity.

---

## 8a — Render + Anchor Pack

Both 8b (per-slide) and 8c (per-cohort) consume the same anchor
pack. Generate it once at the start of Step 8.

```bash
# Render
python $PROFILER_SKILL/scripts/render_samples.py output.pptx \
  -o slide-previews/per-slide/ --width 1920
ls slide-previews/per-slide/*.jpg | wc -l   # must equal slide count

# Precompute zone metrics (raw measurements, no judgments)
python $COMPOSER_SKILL/scripts/s08_precompute_metrics.py .

# Compute cohort definitions (deterministic grouping + comparison tables)
python $COMPOSER_SKILL/scripts/s08_cohort_definitions.py .

# Build the unified anchor pack (per-slide + per-cohort entries)
python $COMPOSER_SKILL/scripts/s08_anchor_pack.py .
```

Produces (overwritten on every fix cycle):

- `s08-zone-metrics.json` — raw per-zone measurements including
  `roleHint`, `estimatedRenderedLines`, `estimatedWidthIn`.
- `s08-cohort-definitions.json` — discovered cohorts with per-role
  cross-member comparison tables.
- `s08-anchor-pack.json` — unified detection-evidence file. Holds
  `perSlide.<slideId>` subsets and `perCohort.<cohortId>` entries;
  both detection and remediation prompts pull their evidence from
  this file.

---

## 8b — Per-Slide QA (mandatory)

### Recommended Per-Slide Scan Axes

The VLM MUST scan every recommended axis. Problems found are
emitted as individual findings. If no problem exists for an axis,
nothing is emitted. The VLM may also create new dimension names
for problems outside these axes.

| #   | Recommended dimension   | What to check                                                | Critical-severity triggers                                                                         |
| --- | ----------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| 1   | **spatialContainment**  | All elements within canvas safe area                         | bbox exceeds slide edge; element < 0.2 in from edge.                                               |
| 2   | **textRendering**       | Text renders as readable, correct form                       | text clipped; unintended wrap; body < 9pt; contrast < WCAG AA; code in proportional font.          |
| 3   | **imageIntegrity**      | Images preserve aspect ratio and subject visibility          | visibly stretched > 15%; subject face or text critically clipped.                                  |
| 4   | **contentCompleteness** | No placeholder residue or unintended occlusion               | 'lorem', 'TBD', 'placeholder' visible; core content covered ≥ 30%.                                 |
| 5   | **visualHierarchy**     | Clear focal point, discriminable levels, logical entry point | multiple competing focal points; title-body indistinguishable; entry point misaligned with intent. |
| 6   | **spatialOrganization** | Grouping and reading path match content logic                | reading path contradicts content sequence; unrelated items visually grouped.                       |
| 7   | **intentAlignment**     | Design serves this specific content's purpose                | design contradicts narrative intent (somber palette on celebratory content).                       |

**Prompt protocol by axis group:**

| Axes 1–4 (spatialContainment, textRendering, imageIntegrity, contentCompleteness)                                                                                                                    | Axes 5–7 (visualHierarchy, spatialOrganization, intentAlignment)                                                                                                                                |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Consult `metricsSubset` + JPEG. Cross-check metrics fields (`outOfCanvas`, `marginsIn`, `fontPt`, `wcagContrast`, `aspectDelta`, `placeholderHits`). Use thresholds in the table above for severity. | Consult JPEG + `narrativeIntent`. Use "describe-then-judge" protocol: first describe what the eye sees, then compare with `narrativeIntent` to judge. Do not consult `narrativeIntent` for 1–4. |

### Pipeline

```
8b-1 detect + prioritize (per batch) → s08-perslide-findings.json
8b-2 remediate (P0 + P1)             → s08-perslide-remediations.json
8b-3 designer LLM applies            → new s07-build.py + s08-perslide-fix-decisions.json
8b-4 rebuild · re-render · verify    → re-detect → records to s08-qa-log.json
```

**Subagent enforcement checkpoint:** the per-slide entry in
`s08-qa-log.json` MUST identify the VLM subagent invocation
(batch ids + timestamps). Self-inspection is a delivery blocker.

### 8b-1: VLM detection + prioritize (per batch)

**Prompt:** [qa-reviewer-perslide-prompt.md](qa-reviewer-perslide-prompt.md).

**Batch size: 5 slides per call** (default). Do not branch on
slide count.

For each batch:

1. Substitute placeholders: batch id, slide ids, slide
   dimensions, the **anchor bundle** for this batch's slides from
   `s08-anchor-pack.json`, JPEG paths, output path. The anchor
   bundle includes `metricsSubset`, `narrativeIntent`, and
   `contentText`.
2. Launch a fresh subagent with the substituted prompt.
3. The subagent **returns the JSON in its response**. The
   orchestrator extracts the JSON and writes it to disk.
4. **Validate** the written file against
   [`schemas/s08-perslide-findings.schema.json`](../schemas/s08-perslide-findings.schema.json)
   before merging. On schema-validation failure, re-prompt with
   the error.
5. Concatenate all batches, then **post-process** (deterministic,
   no LLM):
   - Compute `priority` on each finding from `severity × confidence`.
   - Drop findings with `confidence=low` AND `evidence` < 30 chars.
   - Mark `conflict: true` on findings targeting the same zone
     with contradictory `fixDirection`.
6. Write the final `s08-perslide-findings.json` (includes
   `priority` field on every surviving finding).

**VLM output shape (per slide):**

```jsonc
{
  "slideId": "s03",
  "findings": [
    {
      "dimension": "spatialContainment",
      "what": "title text frame exceeds right slide edge by 0.3in",
      "severity": "critical",
      "confidence": "high",
      "evidence": "metrics show right margin = -0.3in on zone title-1",
      "fixDirection": "shrink text frame width OR move left by 0.3in"
    },
    {
      "dimension": "textRendering",
      "what": "body text 8pt, below 9pt threshold",
      "severity": "critical",
      "confidence": "high",
      "evidence": "metrics fontPt=8 on zone body-1",
      "fixDirection": "increase to 10pt OR reduce content to fit at 10pt"
    },
    {
      "dimension": "textRendering",
      "what": "emoji '🔥' renders as tofu □",
      "severity": "critical",
      "confidence": "high",
      "evidence": "JPEG row 2 col 1 shows replacement glyph □",
      "fixDirection": "replace emoji with text OR use a font supporting this codepoint"
    },
    {
      "dimension": "intentAlignment",
      "what": "generic template look with no content-specific design choices",
      "severity": "minor",
      "confidence": "medium",
      "evidence": "slide uses default blue gradient unrelated to topic (nature photography)",
      "fixDirection": "adjust palette toward earth tones OR add a nature-themed accent"
    }
  ]
}
```

**Key rules:**
- One finding per distinct problem (never bundle multiple issues).
- A slide with no problems produces `"findings": []`.
- Same `dimension` may appear multiple times (each for a separate
  problem).
- Use recommended dimension names when applicable; create new
  camelCase names only when no recommended axis fits.

### 8b-2: Remediation pass

Triggers for P0/P1 findings only. Per trigger:
launch subagent with
[qa-remediation-perslide-prompt.md](qa-remediation-perslide-prompt.md).
Each remediation: 1–3 mutually-exclusive proposals as
`parameter_change` (preferred) or `directional` (fallback).
Write `s08-perslide-remediations.json`.

### 8b-3: Designer applies fixes

Reads findings + remediations, produces:

**(a) New `s07-build.py`** — modify only affected `build_sXX()`
functions + `PERSLIDE_*_OVERRIDES` dicts.

| Priority | Action                                 |
| -------- | -------------------------------------- |
| P0       | Must fix                               |
| P1       | Pick proposal or reject with rationale |
| P2       | Designer discretion                    |
| P3       | Usually dropped                        |

**Whitelisted:** zone coordinates, font sizes, text strings,
image paths within single `build_sXX()`; override dict entries.
**Forbidden:** global constants, style policy, cross-slide helpers,
plan files, `COHORT_OVERRIDES`.

**Archive before edit:**
```bash
mv s07-build.py s07-build.pre-perslide-fix.py
mv output.pptx output.pre-perslide-fix.pptx
```

**(b) `s08-perslide-fix-decisions.json`** — every P0/P1 finding
must appear. Schema: [../schemas/s08-perslide-fix-decisions.schema.json](../schemas/s08-perslide-fix-decisions.schema.json).

### 8b-4: Rebuild, verify

```bash
python s07-build.py
python $COMPOSER_SKILL/scripts/s08_precompute_metrics.py .
python $COMPOSER_SKILL/scripts/s08_cohort_definitions.py .
python $COMPOSER_SKILL/scripts/s08_anchor_pack.py .
python $PROFILER_SKILL/scripts/render_samples.py output.pptx \
  -o slide-previews/per-slide-verify/ --width 1920
```

Re-run VLM detection on new JPEGs + anchor pack. Verify: every
fixed P0/P1 finding must no longer appear. If original batch had
≥3 P0s, verify at 1 slide/call.

### 8b-5: Record in `s08-qa-log.json`

Append initial + verify `rounds[]` entries. Schema:
[`schemas/s08-qa-log.schema.json`](../schemas/s08-qa-log.schema.json).

### 8b-6: Fix budget

Default: 1 fix cycle. Unresolved P0s → `unresolvedItems[]`.
Second cycle at designer discretion (suffix `-2`).

---

## 8c — Per-Cohort QA (when ≥1 cohort exists)

Runs after 8b.

### Cohort Scan Axes

| #   | Dimension               | Critical trigger                                    |
| --- | ----------------------- | --------------------------------------------------- |
| 1   | typographicConsistency  | >2pt size diff on same role                         |
| 2   | proportionalConsistency | >10% area diff on same role                         |
| 3   | paletteConsistency      | Different hue on same-role element                  |
| 4   | motifIntegrity          | Motif present on some members but not others        |
| 5   | bookendSymmetry         | Asymmetric structure (one has image, other doesn't) |

### Pipeline

```
8c-1 cohort definitions (already produced in 8a) → s08-cohort-definitions.json
8c-2 detect + prioritize (one subagent per cohort) → s08-cohort-findings.json
8c-3 remediate (P0 + P1)                           → s08-cohort-remediations.json
8c-4 designer LLM applies COHORT_OVERRIDES         → new s07-build.py + s08-cohort-fix-decisions.json
8c-5 rebuild · re-render · verify                  → re-detect → records to s08-qa-log.json
```

If `s08-cohort-definitions.json` contains **zero cohorts** (only
when every layoutPattern is unique and there are no
opener/closer endpoints), skip 8c entirely and record a single
qa-log entry with `roundType: "per-cohort"` and empty findings
documenting the skip reason.

### 8c-2: VLM detection (one call per cohort)

**Prompt:** [qa-reviewer-cohort-prompt.md](qa-reviewer-cohort-prompt.md).
One subagent per cohort (must see all members). Substitute
placeholders: cohort entry, dimensions, member JPEGs.
Validate against schema. Post-process same as 8b-1.
Cohort findings MUST include `affectedMembers`.

### 8c-3: Remediation

Same as 8b-2 but uses
[qa-remediation-cohort-prompt.md](qa-remediation-cohort-prompt.md).
Write `s08-cohort-remediations.json`.

### 8c-4: Designer applies via `COHORT_OVERRIDES`

Extend `COHORT_TO_MEMBERS` and `COHORT_OVERRIDES` dicts in
`s07-build.py`. Per-slide overrides take precedence over cohort.
See [`build-script-template.md`](build-script-template.md).

```bash
mv s07-build.py s07-build.pre-cohort-fix.py
mv output.pptx output.pre-cohort-fix.pptx
```

Write `s08-cohort-fix-decisions.json`.

### 8c-5/6: Verify + fix budget

Same as 8b-4/6 but with per-cohort subagent. Append
`per-cohort` and `per-cohort-verify` qa-log entries.

---

## 8d — Per-Deck Input

Generate visual inputs for 8e. Runs on post-8c state.

```bash
python $COMPOSER_SKILL/scripts/s08_contact_sheet.py . \
  --input-dir slide-previews/per-slide-verify/ \
  --fallback-dir slide-previews/per-slide/ \
  -o slide-previews/contact-sheet.jpg

python $COMPOSER_SKILL/scripts/s08_select_samples.py . \
  -o slide-previews/per-deck-samples/
```

Contact sheet: thumbnail grid (~200x120px cells), annotated with
slide numbers. Sample selection: cover, first content, mid-point,
highest density, lowest density, final (4–6 slides).
If deck ≤6 slides, use all as samples.

---

## 8e — Per-Deck Aesthetic Evaluation

Single VLM call. Holistic aesthetic assessment — no metrics,
no per-slide defects, no cohort inconsistencies. Images only.

**Prompt:** [qa-reviewer-perdeck-prompt.md](qa-reviewer-perdeck-prompt.md).
Protocol: describe → identify strengths → recommend (with
concrete `whatISee` observations ≥30 chars each).

Output: `s08e-perdeck-evaluation.json`. Schema:
[`schemas/s08e-perdeck-evaluation.schema.json`](../schemas/s08e-perdeck-evaluation.schema.json).

If `recommendations` is empty → skip 8f.

Append `per-deck` qa-log entry.

---

## 8f — Per-Deck Fix

Executes only when 8e has ≥1 recommendation. Single pass, no verify.

All modifications in `s07-build.py` only. Plans are frozen.
Scope: `specific_pages` → affected `build_sXX()` zones;
`section` → multiple builders; `global` → top-level constants.

```bash
mv s07-build.py s07-build.pre-perdeck-fix.py
mv output.pptx output.pre-perdeck-fix.pptx
python s07-build.py
python $PROFILER_SKILL/scripts/render_samples.py output.pptx \
  -o slide-previews/per-deck-verify/ --width 1920
```

Write `s08f-perdeck-fix-decisions.json`. Every recommendation
must appear with `action: applied | dropped` + rationale.
Append `per-deck-fix` qa-log entry.

---

## 8g — Deliver

- Copy (do not move) `$SESSION/output.pptx` to
  `$OUTPUTS_DIR/{topic_slug}_{YYYYMMDD_HHMMSS}.pptx`
  (`$OUTPUTS_DIR` is the repo-root `outputs/` directory; absolute
  path required).
- Write `s08g-generation-report.json` per
  [`schemas/s08g-generation-report.example.json`](../schemas/s08g-generation-report.example.json),
  including the `contentGrounding` block from
  `s04a-terminology-registry.json`.
- Finalize `s08-qa-log.json` with `finalStatus` /
  `totalRounds` / `totalFindingsCritical` / `totalFindingsFixed` /
  `unresolvedItems[]`.
- **Delivery precondition:** the latest preview directory must
  contain one JPEG per slide in `output.pptx`.

---

## Appendix A — Files this step produces

| File                                    | Source                                | Lifecycle                    |
| --------------------------------------- | ------------------------------------- | ---------------------------- |
| `slide-previews/per-slide/*.jpg`        | 8a                                    | Kept                         |
| `slide-previews/per-slide-verify/*.jpg` | 8b-4 / 8c-5                           | Kept (only when verify ran)  |
| `s08-zone-metrics.json`                 | 8a, recomputed in 8b-4/8c-5           | **Overwritten** each cycle   |
| `s08-cohort-definitions.json`           | 8a, recomputed in 8b-4/8c-5           | **Overwritten** each cycle   |
| `s08-anchor-pack.json`                  | 8a, recomputed in 8b-4/8c-5           | **Overwritten** each cycle   |
| `s08-perslide-findings.json`            | 8b-1 (merged from per-batch outputs)  | Kept                         |
| `s08-perslide-findings-verify.json`     | 8b-4                                  | Kept (only when verify ran)  |
| `s08-perslide-remediations.json`        | 8b-2                                  | Kept (only when P0/P1 fired) |
| `s08-perslide-fix-decisions.json`       | 8b-3                                  | Kept                         |
| `s07-build.pre-perslide-fix.py`         | 8b-3 archival                         | Kept                         |
| `output.pre-perslide-fix.pptx`          | 8b-3 archival                         | Kept                         |
| `s08-cohort-findings.json`              | 8c-2 (merged from per-cohort outputs) | Kept                         |
| `s08-cohort-findings-verify.json`       | 8c-5                                  | Kept (only when verify ran)  |
| `s08-cohort-remediations.json`          | 8c-3                                  | Kept (only when P0/P1 fired) |
| `s08-cohort-fix-decisions.json`         | 8c-4                                  | Kept                         |
| `s07-build.pre-cohort-fix.py`           | 8c-4 archival                         | Kept                         |
| `output.pre-cohort-fix.pptx`            | 8c-4 archival                         | Kept                         |
| `slide-previews/contact-sheet.jpg`      | 8d                                    | Kept                         |
| `slide-previews/per-deck-samples/*.jpg` | 8d                                    | Kept                         |
| `s08e-perdeck-evaluation.json`          | 8e                                    | Kept                         |
| `s08f-perdeck-fix-decisions.json`       | 8f                                    | Kept (only when 8f ran)      |
| `s07-build.pre-perdeck-fix.py`          | 8f archival                           | Kept (only when 8f ran)      |
| `output.pre-perdeck-fix.pptx`           | 8f archival                           | Kept (only when 8f ran)      |
| `slide-previews/per-deck-verify/*.jpg`  | 8f                                    | Kept (only when 8f ran)      |
| `s08-qa-log.json`                       | 8b-5 / 8c-5 / 8e / 8f (appends)       | Finalized at 8g              |
| `s08g-generation-report.json`           | 8g                                    | Final                        |
