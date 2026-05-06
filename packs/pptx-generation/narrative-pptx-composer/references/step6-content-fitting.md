# Step 6 — Content–Zone Fitting & Speaker Notes

Adapt content draft to fit zones from Step 5. Step 6 is the
only step holding both content and zone geometry — no escape
hatch back to Step 4.

Inputs: `s04-content-draft.json` + `s05-slide-visual-design.json` +
`s05b-style-policy.json` + `s04a-terminology-registry.json`.
Output: `s06-slide-content.json`.

### Batching

Follow [batching-strategy.md](batching-strategy.md). No
prior-batch context needed (fitting is per-slide). Post-merge:
run cross-slide consistency pass + `s06_validate_content.py`.

---

## 6a — Map Content to Zones

For each slide, assign text from `s04-content-draft.json` to the
specific zone roles defined in
`s05-slide-visual-design.json → layoutSpec.zones[]`.

### Slot Naming

`s06-slide-content.json` slots use zone `role` names
from `layoutSpec.zones[]` (not placeholder names):

```json
{
  "taskId": "s05",
  "slots": [
    { "zone": "title", "text": "Live Repo Context" },
    { "zone": "left-body", "text": "The agent collects..." },
    { "zone": "right-body", "text": "What gets collected..." }
  ],
  "speakerNotes": "..."
}
```

### Mapping Rules

1. **Title zone** ← `headlineMessage` from content draft. Use
   verbatim when it fits the title-zone width. When it does not
   fit, compress within Step 6 — there is no escape hatch back
   to Step 3. Compression follows the same self-contained
   discipline as body content (§ 6b):
   - **Stage 1 — syntactic compression.** Drop modifiers,
     subordinate clauses, hedges; tighten phrasing. Preserve
     every claim, entity, and number.
   - **Stage 2 — semantic compression.** When syntactic
     compression isn't enough, distill the headline to its
     core claim. The on-slide title carries the irreducible
     statement; the dropped framing / qualifiers move into
     `speakerNotes` so no information is lost.
   - **Always forbidden** (regardless of fit pressure): merging
     two distinct claims into one, replacing a specific number
     with a vaguer one (use the registry's `qualitativeForm`
     only when the registry itself provides one), adding any
     wording not implied by the blueprint headline, or
     truncating mid-thought (the on-slide title must always be
     a complete, well-formed statement).

   No special record is needed. The validator's
   `check_headline_alignment` reports a warning when the
   compressed title shares < 40% token overlap with the
   blueprint headline — this is an informational audit signal
   for traceability, not a failure to escalate.
2. **Body zones** — distribute content across available text zones,
   respecting the composition's spatial intent. Two paths:
   - **`s04-content-draft.json` provides `blocks[]`** (multi-zone
     layouts authored upfront — see step4-content-draft.md § When to
     author `blocks[]`): map each block directly to the zone whose
     `role` matches `block.role` (e.g. `block.role: "card-1"` →
     zone `card-1-title` + zone `card-1-body`). No string splitting
     by Step 6 — this is pure mapping.
   - **`blocks[]` is absent**: split `contentBody` heuristically to
     populate the multiple body zones (use textual cues — "Force 1
     / 2 / 3", numbered lists, paragraph breaks, or semantic
     boundaries). The validator records this slide in its
     informational "self-split" log for traceability; this is **not**
     a warning. Authoring `blocks[]` upfront in Step 4 is preferred
     because it makes the split explicit and reproducible, but
     ad-hoc splitting in Step 6 is a supported fallback.
3. **Caption/label zones** ← auxiliary text (data labels,
   category names, footnotes).
4. **Image zones** ← media from `s04-content-draft.json →
   mediaAttachments` first; if the slide has both
   `mediaAttachments` and `illustrationSpec`, **mediaAttachments
   wins** for any zone where they would compete (illustrations
   demote to a secondary/atmospheric role or are dropped — see
   step4-content-draft.md § Illustration Spec for precedence rules).

---

## 6b — Size Content to Fit

Two-stage strategy. No escape hatch to Step 4.

### Stage 1 — Syntactic compression (try first)

Tighten prose without dropping facts: drop filler, collapse
redundant phrasing, convert prose to tight phrases for labels,
tighten punctuation. If content fits, stop.

### Stage 2 — Lossy distillation

On-slide = distilled view (strongest support for headline).
`speakerNotes` = full evidence. Together they preserve every
Step 4 fact.

Demotion order: caveats → secondary points → repeated framings
→ auxiliary numbers. Always keep: headline-dependent claims,
credibility numbers, named entities.

### Always forbidden

- Merging two distinct claims into one.
- Replacing a specific number with a vaguer one (use registry's
  `qualitativeForm` only when the registry provides one).
- Adding facts not in `s04-content-draft.json`.
- Changing the headline's core claim.

### Other notes

- Zone sizes in the layout spec are suggestions, not hard
  constraints; `s07-build.py` can adjust font size or zone dimensions
  for minor overflow (≤ ~10% over capacity).
- For `dense` slides, permit tighter on-slide text; for `minimal`
  slides, syntactic compression should already leave whitespace
  without any need to enter Stage 2.

### Image / Media Slots

When Step 5 allocates an image zone, include an image slot in
`s06-slide-content.json`:

```json
{
  "zone": "visual",
  "type": "image",
  "path": "images/fig03-coding-harness-layers.png",
  "alt": "Three layers of a coding harness"
}
```

- `path` is relative to the session directory (images are copied
  there during Step 1c).
- `alt` is used as the image's alt-text attribute in the PPTX.
- `type: "image"` tells `s07-build.py` to call `add_image_safe()`
  instead of `add_textbox()`.
- **Aspect ratio (mandatory):** `s07-build.py` must always use
  `add_image_safe()` which computes display dimensions that
  preserve the image's original width:height ratio and fit
  within the zone. Never stretch or squash an image to fill
  the zone — distorted images are a critical defect.
- If the image file is missing at build time, fall back to a
  text-only layout — never break the build.

### Formula Slots

When Step 5 allocates a `type: "formula"` zone, include a formula
slot in `s06-slide-content.json` keyed by the zone `role`:

```json
{
  "zone": "formula-attention",
  "formulaSource": "\\mathrm{Attention}(Q,K,V) = \\mathrm{softmax}\\!\\left(\\frac{QK^{\\top}}{\\sqrt{d_k}}\\right)V",
  "alt": "Attention of Q, K, V equals softmax of Q-K-transpose over square-root of d_k, applied to V."
}
```

- `formulaSource` is the **mathtext expression body**, **without**
  `$…$` / `\(…\)` / `\[…\]` delimiters. The Step 7 renderer wraps
  with `$…$` itself; doubled delimiters silently produce empty
  artifacts (`s06_validate_content.py` hard-fails on outer delimiters).
- `alt` is **mandatory** (≥ 10 chars, plain language, no LaTeX
  commands). Used both for the inserted picture's alt-text and for
  Step 8 QA review of equation slides.
- **No `path` field.** Step 7's `render_formulas()` pre-pass writes
  the artifact to `<session>/formulas/<taskId>-<role>.png`
  deterministically; the per-slide builder looks it up from a cache
  map. (See [build-script-template.md § Formula zones](build-script-template.md).)
- Mathtext supports fractions, roots, sub/sup, Greek, sums,
  integrals, common operators. **Not supported:** `\begin{matrix}`,
  custom packages (`amsmath`, `bm`). Use stacked sup or
  `\\substack` as a compact alternative when matrices are needed.
  Full Phase 1 contract:
  [sessions/formula-svg-design-2026-05-01.md](../../../../sessions/formula-svg-design-2026-05-01.md).

---

## 6c — Author Speaker Notes

Full talk track authored now that on-slide text is final. Integrate
any 6b Stage 2 demoted content — do not re-author from scratch.

Rules:
- Every slide gets notes (including structural slides). Validator
  enforces non-empty.
- Tone matches deck register (`s02.constraints.formalityLevel`,
  audience profile, narrative pattern).
- Length is content-driven, not fixed. Dense slides with demoted
  content need longer notes; simple dividers need one sentence.
- No redundancy with on-slide text.
- Open with transition cue from Step 4d.
- Use only `canonical` forms from terminology registry.
- Numbers must match `s04a-terminology-registry.json`.

---

## Cross-slide Consistency (authoritative pass)

This is the **single authoritative cross-deck consistency pass**
for the whole pipeline. Step 4 only runs cheap batch-internal
smoke checks (see step4-content-draft.md § Batch Strategy); Step 6
owns the deck-level verification because all upstream artifacts
are now finalized and content has been mapped to real zones:

1. **Numbers match registry.** Every numeric token in any slot
   text or speaker note appears in
   `s04a-terminology-registry.json → dataPoints` (or is justified
   as a slide id / page number).
2. **Terminology stable.** Only `canonical` forms used; no
   `rejected` variants in slot text or notes.
3. **Headlines preserved.** Each title-zone string carries the
   blueprint `headlineMessage`'s core claim — verbatim when it
   fits, compressed within Step 6 (per § 6a Mapping Rule 1) when
   it does not. The validator's `check_headline_alignment` reports
   an informational warning when token overlap with the blueprint
   headline drops below 40%, which is a traceability signal that
   semantic compression occurred — not an error to escalate.
4. **Narrative coherence.** Read all title-zone strings
   top-to-bottom — no repeated openers, logical progression
   intact, act transitions smooth.

`s06_validate_content.py` automates checks 1–3; check 4 remains
a manual LLM review of the printed headline sequence.

### Agenda Slide Content (page numbers deferred)

Agenda page-number slots use the em-dash sentinel `"—"` (e.g.
`"Act 1 · pp. —   Act 2 · pp. —"`) until Step 7c patches them with
actual slide numbers — see
[step7-build-pptx.md § Agenda numbering](step7-build-pptx.md). Do **not**
use the literal string `"TBD"`: `s06_validate_content.py`'s
placeholder check hard-fails on it.

Write `s06-slide-content.json`
(see [../schemas/s06-slide-content.example.json](../schemas/s06-slide-content.example.json)).

---

**Checkpoint:** `s06-slide-content.json` exists; every `taskId` in
`s05-slide-visual-design.json` has a matching entry; all data points
match `s04a-terminology-registry.json`; no `rejected` terminology
variants appear in any slot text; every slide has a non-empty
`speakerNotes` field (no exemption for dividers / structural
slides); slot zone names match plan `layoutSpec` zone roles.

```bash
python $COMPOSER_SKILL/scripts/s06_validate_content.py "$SESSION"
```

The validator also prints the headline sequence for manual narrative
coherence review.
