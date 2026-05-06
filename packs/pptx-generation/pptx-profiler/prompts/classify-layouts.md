---
output_schema: $SKILL/schemas/profile_schema.json#layouts, #design_language
sync_with: SKILL.md ## Step 3b merge instructions
variables: [LAYOUT_PREVIEWS, PROFILE, SKILL]
enums: $SKILL/schemas/enums.json
enum_rule: All enum-typed fields MUST use values from enums.json. Read it first.
---

Analyze the slide layouts in this template.

Read the output schema first:
`$SKILL/schemas/profile_schema.json` → layout item properties and
design_language definition. Property descriptions define what to
populate.

Inputs:
1. Layout preview images: `$LAYOUT_PREVIEWS/slideLayout{N}.jpg` (clean)
   and `$LAYOUT_PREVIEWS/slideLayout{N}_annotated.jpg` (annotated)
2. Profile metadata: read `$PROFILE` → layouts array

For each layout, determine (enum fields — values from enums.json):
- inferred_type (enum: layout_inferred_type)
- inferred_type_confidence (enum: confidence_level)
- content_capacity (enum: content_capacity)
- visual_weight (enum: visual_weight)
- For each non-placeholder shape (by index in shapes[]), assign a role
  (enum: shape_role)

Then extract cross-template design_language from ALL layouts together.
Populate all fields defined in the schema's design_language object.

**Analytical guidance for component_style_pattern:**
Specifically identify and report:
- corner style: rounded or sharp (and approximate radius if rounded)
- fill style: flat solid, gradient, or transparent
- shadow/effects: drop shadow, glow, reflection, bevel, or none
- line/border treatment: visible outlines, no outlines, accent-colored
- overall aesthetic: flat/modern, skeuomorphic, glassmorphism, etc.
Report what IS used, and also what is notably ABSENT (e.g.,
"no shadows or gradients anywhere — strictly flat design").

Return JSON:

```json
{
  "layouts": [
    {
      "layout_file": "slideLayoutN.xml",
      "inferred_type": "...",
      "inferred_type_confidence": "...",
      "content_capacity": "...",
      "visual_weight": "...",
      "shape_roles": { "<shapeIndex>": "<role>" }
    }
  ],
  "design_language": {
    "style_tone": "...",
    "whitespace_rhythm": "...",
    "visual_hierarchy_method": "...",
    "component_style_pattern": "...",
    "cover_vs_content_contrast": "...",
    "visual_motifs": [{ "type": "...", "description": "...", "frequency": "..." }]
  }
}
```

Read the images and $PROFILE — do NOT fabricate data.
