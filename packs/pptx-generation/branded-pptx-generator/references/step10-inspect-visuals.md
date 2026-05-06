# Step 10 — Inspect Visuals

**⚠️ USE SUBAGENT** — even for 2–3 slides; never self-inspect.

First, run schema validation — cheap and deterministic, catches
structural errors before spending tokens on visual QA:

```bash
python $PPTX_SKILL/scripts/office/validate.py output.pptx \
  --original $TEMPLATE_FILE --auto-repair
```

`--original` baselines against the template so only **new** schema
errors are reported. `--auto-repair` only fixes trivial issues
(e.g. missing `xml:space="preserve"`); structural errors (broken
refs, duplicate IDs, missing Content_Types entries) must be fixed
manually in `unpacked/`, re-packed, and re-validated before
proceeding. Do not run visual inspection on a structurally invalid
file.

Then render the deck — one full-resolution JPEG per slide for the
subagent:

```bash
mkdir -p slide-previews
python $PROFILER_SKILL/scripts/render_samples.py output.pptx \
  -o slide-previews/ --width 1920
```

The subagent inspects individual `slide-previews/slide{N}.jpg` images.

Launch a subagent with this prompt (substitute slide expectations from
`slide-plan.json`):

```
Visually inspect these slides. Assume there are issues — find them.

Look for:
- Overlapping elements (text through shapes, lines through words)
- Text overflow / cut off at slide or box edges
- Decorative lines positioned for single-line titles but title wrapped
- Footer/citation collisions with content above
- Elements too close (< 0.3" gaps) or unevenly spaced
- Insufficient slide-edge margins (< 0.5")
- Columns or repeated elements not consistently aligned
- Low-contrast text (title < 3:1, body < 4.5:1)
- Style drift: dividers, covers, or repeated layouts that don't match
  each other across the deck (this is the #1 thing to flag)
- Leftover placeholder content
- Colors or fonts inconsistent with the template brand
- Logo missing, moved, or resized vs template (locked element)
- Footer/disclaimer/copyright text missing or altered (locked element)
- Aesthetic principle violations (when aestheticGuidance is provided):
  * Shapes that don't match shapeVocabulary (wrong corner style, fill
    treatment, or stroke conventions for the brand)
  * Colors assigned to wrong semantic roles per colorRoleMap (e.g.
    accent color used for background where structural color expected)
  * Margins or element spacing inconsistent with compositionRules
  * Font sizes that don't correspond to any typeScale stop
  * Recipe deviation (balanced/strict modes): if a slide was planned
    with a patternRecipe, verify the skeleton structure and color
    assignment logic are faithfully applied

Read and analyze:
1. slide1.jpg — Expected: <brief from slide-plan.json>
2. slide2.jpg — Expected: ...
...

Report ALL issues found, including minor ones, grouped by slide.
```

**Checkpoint:** Issue list collected from the validator + subagent.
