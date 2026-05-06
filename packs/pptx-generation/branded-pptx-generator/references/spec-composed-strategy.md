# Spec-Composed Strategy (Step 7c)

Use only when neither a layout nor a sample slide demonstrates the
required pattern. Typical cases: charts, timelines, Gantt diagrams,
custom infographics.

Before making design choices, consult
[generation-modes.md](generation-modes.md) for mode-dependent design
boundaries (what each mode allows for typography, color, shapes,
density, and layout invention).

## Sub-steps

### 1. Build the style spec for this slide

- **Case A — A sample slide is *almost* the right pattern:**
  1. Check `$PROFILE_DIR/slide-design-{slide_file}.json` first — if it
     exists, skip extraction. Otherwise, run the
     [slide visual design analysis](slide-design-analysis.md)
     (Phase 1 extraction + Phase 2 VLM subagent) to produce the file.
  2. **Adapt the spec to the target content.** The `slide-design-*.json`
     describes the *sample* slide's layout (e.g., 5 agenda rows, 6
     timeline nodes), not the target slide. Create an adapted spec:
     - Compare the target content's data items against
       `patternStructure.nodes` — add or remove node groups as needed.
     - Recompute `elements[]` positions using `spacingPattern` values
       (pitch, gap) and the new item count. Keep positions within the
       slide bounds (`$PROFILE → slideSize`).
     - Preserve `colorMapping`, fixed-chrome elements
       (`designIntent: "fixed"`), and `patternStructure.axis` /
       `connectors` — adjust their extents if the node count changed.
     - Retain `typographyMapping` and all theme color references as-is.
     Save the adapted spec as
     `$SESSION_DIR/slide-spec-{taskId}.json`.

- **Case B — No similar sample exists (design from scratch):**

  First, check `style-policy.json → aestheticGuidance`. If non-null,
  aesthetic principles are available and Case B splits into two
  sub-cases based on whether a matching pattern recipe exists:

  **Case B-guided** — `aestheticGuidance.applicableRecipes` contains a
  recipe whose `patternFamily` matches the target slide's content
  pattern (e.g., `horizontal_process` for a process flow,
  `comparison_columns` for a feature comparison). The recipe provides
  a complete structural blueprint:

  1. **Start from the recipe.** Read the matching recipe's `skeleton`,
     `scalingRules`, `colorAssignment`, and `spacingSpec`.
  2. **Adapt item count.** Compare the target content's data items
     against `skeleton.elementsPerUnit`. Use `scalingRules.method` to
     compute positions:
     - `equal_distribute`: `unitWidth = (contentZone - (N-1)*gap) / N`
     - `fixed_width_wrap`: fixed unit width, wrap to next row at
       `maxItems`
     - `proportional`: allocate width proportional to content length
     - `overflow_paginate`: split across slides if > `maxItems`
  3. **Apply color assignment.** Follow `colorAssignment.method`:
     - `tintProgression`: interpolate from start tint to full
       saturation across N items
     - `uniform`: same color for all units
     - `alternating`: cycle between specified colors
     - `semanticByRole`: map each element role to
       `aestheticGuidance.colorRoleMap`
     - `seriesColors`: use data_series_1, data_series_2, etc.
  4. **Compute spacing.** Use `spacingSpec.interElementGapPct` and
     `spacingSpec.contentZoneUsagePct` with the slide dimensions
     (`$PROFILE → slideSize`) to derive EMU values.
  5. **Build the spec.** Produce `patternDescription`,
     `patternStructure`, `spacingPattern`, `colorMapping`, and
     `elements[]` following the recipe's structure. Use shapes from
     `aestheticGuidance.shapeVocabulary` and font sizes from
     `aestheticGuidance.typeScale`.
  6. **Respect `aestheticAdherence` guardrail:**
     - `recipes-as-law`: skeleton and colorAssignment must be followed
       exactly; only item count may change.
     - `recipes-as-guidance`: may adjust proportions, combine recipe
       elements, or modify wrapper treatment to fit content.
     - `recipes-as-inspiration`: recipe informs direction but does not
       constrain structure.

  **Case B-principled** — no matching recipe exists in
  `applicableRecipes` (or `aestheticGuidance` is null). Author a new
  design spec from scratch, but draw constraints from aesthetic
  principles when available:

  1. **`patternDescription`** — one-line summary of the visual pattern
     you are designing (e.g., "3-column KPI cards with icons and
     sparklines").
  2. **`patternStructure`** — compositional structure: `patternType`
     (from `enums.json`), `direction`, `axis`/`nodes`/`connectors` if
     applicable.
  3. **`spacingPattern`** — compute gap values (EMU) using the slide
     dimensions (`$PROFILE → slideSize`) and the number of elements.
     When `aestheticGuidance` is available, use
     `compositionRules` margins as the baseline; otherwise fall back
     to `designDirectives.margins` and `style-policy.json → spacing`.
  4. **`colorMapping`** — assign theme color keys (`accent1`, `dk1`,
     etc.) to each semantic role. When `aestheticGuidance` is
     available, look up each element's semantic role in
     `colorRoleMap` to find the correct theme slot. Otherwise fall
     back to `style-policy.json → palette`. Must pass WCAG contrast
     checks against the actual background.
  5. **Shape choices** — when `aestheticGuidance.shapeVocabulary` is
     available, choose ONLY shapes listed there. This ensures new
     elements use the same corner style, fill treatment, and stroke
     conventions as the rest of the template. When unavailable, follow
     `designDirectives.componentStylePattern`.
  6. **Typography** — when `aestheticGuidance.typeScale` is available,
     pick the appropriate scale stop for each text element's role
     (title → `title` stop, body → `body` stop, etc.). When
     unavailable, use `style-policy.json → typography`.
  7. **`elements[]`** — define every element with:
     - `xfrm` (x, y, cx, cy) — compute positions from the spacing
       pattern and slide dimensions
     - `role`, `structuralRole`, `group`, `designIntent`
     - `textBody` with font from the type scale or `style-policy.json`
     - No `fill`/`line` needed if using theme defaults

  Save as `$SESSION_DIR/slide-spec-{taskId}.json` (session-scoped,
  not cached at template level since this design is task-specific).

### 2. Write `generate_{taskId}.py`

Write a Python script that reads the slide spec and target content,
then builds a `<p:spTree>` XML fragment using **lxml**.

Use `$SESSION_DIR/slide-spec-{taskId}.json` from Step 1 (produced by
either Case A adaptation or Case B from-scratch design). The fields
below drive code generation:
- **`patternStructure`** → drives the generation loop (element count,
  flow direction, node/connector topology)
- **`spacingPattern`** → exact gap values (EMU) between repeated elements
- **`colorMapping`** → semantic role → theme color key for `<a:schemeClr>`
- **`elements[].xfrm`** → reference positions and sizes for the spatial
  arrangement
- **`elements[].group` + `role`** → identify repeatable units vs fixed chrome
- **`elements[].designIntent`** → `"fixed"` elements copy verbatim;
  `"flexible"` elements parameterize for new content

**Script output:** The script must produce a `<p:spTree>` XML file at
`$SESSION_DIR/generated-spTree-{taskId}.xml`. This file contains only
the shape tree — title placeholder(s), footer placeholders, and all
custom shapes (diagrams, cards, charts, etc.). It does **not** include
the `<p:sld>` or `<p:cSld>` wrapper; Step 3 handles merging the
`<p:spTree>` into the slide skeleton created by `add_slide.py`.

Critical rules:

- Pull every color and font name from `$PROFILE` / `style-policy.json`
- **Never** put `#` in a hex color (corrupts the file)
- **Never use `xml.etree.ElementTree`** to read/write OOXML XML — it
  rewrites namespace prefixes to `ns0:`, `ns1:`, etc. PowerPoint COM
  will refuse to open the file. Always use `lxml.etree` instead
- **Never use `<p:cxnSp>` (connector shapes)** — always use `<p:sp>`
  with `<a:prstGeom prst="line"/>` for lines and arrows. Add
  `<a:tailEnd type="triangle"/>` inside `<a:ln>` for arrowheads.
  Connector shapes generated by python-pptx lose their implicit
  context (stCxn/endCxn shape references) during the spTree extraction
  and merge pipeline, producing XML that passes lxml/python-pptx
  validation but causes PowerPoint COM to reject the entire file.
  This is a silent, undetectable corruption — binary-search slide
  removal is the only reliable diagnostic.
- Set `margin: 0` on text frames when aligning precisely with shapes
- Use `charSpacing`, not `letterSpacing` (silently ignored)
- Verify WCAG contrast against the actual background
- **Never use hardcoded `<a:srgbClr>`** for branded colors — it fails
  locked-tier compliance. Always use `<a:schemeClr val="accent1"/>`
  etc. (see theme color patterns below)

#### Theme color patterns (lxml)

**Shape fill:**

```python
from pptx.oxml.ns import qn
from lxml import etree

solid = etree.SubElement(spPr, qn('a:solidFill'))
clr = etree.SubElement(solid, qn('a:schemeClr'))
clr.set('val', 'accent1')
# Optional luminance modifiers for tints/shades:
# mod = etree.SubElement(clr, qn('a:lumMod')); mod.set('val', '95000')
```

**Text color:**

```python
rPr = run._r.find(qn('a:rPr'))
solid = etree.SubElement(rPr, qn('a:solidFill'))
clr = etree.SubElement(solid, qn('a:schemeClr'))
clr.set('val', 'dk1')
```

### 3. Execute and merge into `unpacked/`

1. **Run the script** to produce the shape tree:
   ```bash
   python $SESSION_DIR/generate_{taskId}.py \
     --spec $SESSION_DIR/slide-spec-{taskId}.json \
     -o $SESSION_DIR/generated-spTree-{taskId}.xml
   ```
2. **Create the slide slot** using `add_slide.py` with the target layout
   (from `slide-plan.json → layoutRef`):
   ```bash
   python $PPTX_SKILL/scripts/add_slide.py unpacked/ slideLayoutNN.xml
   ```
   This creates the slide XML with proper `.rels` pointing to the
   slideLayout.
3. **Merge the shape tree** — replace the new slide's `<p:spTree>` with
   the content from `generated-spTree-{taskId}.xml`. Use lxml (not
   `xml.etree`) to parse and patch.

**Critical: use layout placeholders, not standalone textboxes.** The
generated slide XML **must** include `<p:ph type="title"/>` (and
`<p:ph type="sldNum"/>` etc.) in `<p:nvPr>` so that it inherits the
layout's title font, size, position, and colors. Add custom shapes
(charts, diagrams, cards) as additional `<p:sp>` elements alongside
the placeholders — never replace them with textboxes.

Pattern for the title placeholder (copy from any clone-layout slide):

```xml
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="2" name="Title 1"/>
    <p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
    <p:nvPr><p:ph type="title"/></p:nvPr>
  </p:nvSpPr>
  <p:spPr/>
  <p:txBody>
    <a:bodyPr/><a:lstStyle/>
    <a:p><a:r><a:rPr lang="en-US"/><a:t>Your Title</a:t></a:r></a:p>
  </p:txBody>
</p:sp>
```

Ensure the slide's `.rels` points to a slideLayout that exists in this
template (the one specified in `slide-plan.json → layoutRef`).

### 4. Validate the merged slide

Spec-composed slides bypass template placeholders more than other
strategies, so they need explicit validation before proceeding.

1. **OOXML structural validation:**
   ```bash
   python $PPTX_SKILL/scripts/office/validate.py unpacked/ \
     --original $TEMPLATE_FILE --auto-repair
   ```
   Fixes trivial issues (hex ID overflow, missing `xml:space`). Fail
   the step if unfixable schema errors remain.

2. **Layout linkage check** — verify the new slide's `.rels` references
   the correct `slideLayoutNN.xml` and that the layout exists in the
   template's slide master.

3. **Brand compliance:**
   ```bash
   python $SKILL/scripts/compliance_checker.py unpacked/ \
     --profile $PROFILE --strict
   ```
   Must pass with `locked_violations: 0`. Common issues to watch:
   - Hardcoded `<a:srgbClr>` instead of `<a:schemeClr>` → fix in
     `generate_{taskId}.py` and re-run Steps 2–3
   - Font family not in template theme → use `style-policy.json →
     fontMapping` values only
   - WCAG contrast failure → adjust `colorMapping` luminance modifiers

4. **Placeholder inheritance check** — confirm the slide XML contains
   `<p:ph type="title"/>` (and `<p:ph type="sldNum"/>`, `<p:ph
   type="ftr"/>`, `<p:ph type="dt"/>` if required by the layout) so
   that fonts, sizes, and positions are inherited from the slideLayout
   rather than hardcoded.

If any check fails, fix at the source (Step 1 spec or Step 2 script)
and re-run. Do **not** patch the merged XML by hand — regenerate to
keep the pipeline reproducible.
