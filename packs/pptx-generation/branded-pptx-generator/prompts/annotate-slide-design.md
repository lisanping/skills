---
output_schema: $SKILL/schemas/slide_design_schema.json
sync_with: references/slide-design-analysis.md ## Phase 2
variables: [SLIDE_FILE, PROFILE_DIR, PROFILE, SKILL]
enums: $PROFILER_SKILL/schemas/enums.json
enum_rule: patternType MUST use values from enums.json#pattern_type. Read it first.
---

Analyze this sample slide's visual design. Annotate the raw element
extraction with semantic roles and design intent so that a downstream
generator can recreate this pattern programmatically.

Read the output schema first:
`$SKILL/schemas/slide_design_schema.json` — property descriptions
define what each field means and what values are expected.

Inputs:
1. Preview image: `$PROFILE_DIR/sample-slides/slide{N}.jpg`
2. Raw element extraction: `slide-elements-${SLIDE_FILE%.xml}.json`
   (every element with full xfrm, fill, line, geometry, textBody,
   effects, z-order, group hierarchies)
3. Template profile: `$PROFILE` (theme colors and fonts)

**Slide-level analysis:**
Determine `patternDescription`, `patternStructure` (type, direction,
axis, nodes, connectors, hierarchy), `spacingPattern` (consistent EMU
gaps only), and `colorMapping` (semantic role to theme color key).

**Per-element annotation:**
For each element in the extraction, add `role`, `structuralRole`,
`relatedTo`, `designIntent`, and `group` as defined in the schema's
`AnnotatedElement` definition.

**Critical rules:**
- Preserve ALL structural fields from Phase 1 extraction (xfrm, fill,
  line, geometry, textBody, effects, zIndex, etc.) — add annotations
  alongside them, never replace or omit originals
- Keep color references as-is from Phase 1 (scheme/srgb/sys with mods)
- For group shapes (grpSp), annotate both the group and its children
- Use theme color keys from `$PROFILE`, not hex values, in colorMapping
- Read the image and JSON files — do NOT fabricate data

Return JSON conforming to the schema.
