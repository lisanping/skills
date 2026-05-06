---
output_schema: $SKILL/schemas/profile_schema.json#aesthetic_principles
sync_with: SKILL.md ## Step 4c merge instructions
variables: [SAMPLE_SLIDES, PROFILE, SKILL]
enums: $SKILL/schemas/enums.json
enum_rule: All enum-typed fields MUST use values from enums.json. Read it first.
---

Synthesize aesthetic design principles from this template's sample
slides. Your job is CROSS-SAMPLE SYNTHESIS — identify patterns,
proportions, and conventions that hold across multiple slides and
generalize them into actionable principles for generating brand-new
slide designs.

Read the output schema first:
`$SKILL/schemas/profile_schema.json` → definitions for
AestheticPrinciples, CompositionSystem, ColorSemantics,
TypographicSystem, ShapeGrammar, PatternRecipe. Every property has
a `description` that defines what to populate — follow those
definitions exactly. Do not invent fields beyond what the schema
specifies.

Inputs:
1. Sample slide images: `$SAMPLE_SLIDES/slide{N}.jpg` for ALL
   sample/hybrid slides
2. `$PROFILE` → sample_slide_catalog (per-slide classifications from
   Step 4b: role, contentPattern, complexElements, patternDescription)
3. `$PROFILE` → identity (colors.scheme, fonts, slide_size)

De-duplication note: design_language (from Step 3b) already covers
style_tone, component_style_pattern, visual_motifs, and
vlm_guardrails. Do NOT re-derive those. Focus on PRESCRIPTIVE
principles that go beyond description.

Populate all five dimensions defined in the schema:
compositionSystem, colorSemantics, typographicSystem, shapeGrammar,
patternRecipes. For each dimension, the schema's property
descriptions tell you WHAT to extract. The guidance below tells you
HOW to approach the analysis.

**Analytical guidance:**

- Analyze ACROSS slides, not per-slide. Per-slide work is done in
  Step 4b — this step synthesizes.
- Output must be PRESCRIPTIVE and ACTIONABLE: "when building X, do Y"
  not "X is observed". The downstream generator will use this to make
  design decisions for content the template never showed.
- Use theme color slot names (accent1, dk1, etc.), NEVER hex values.
- Express spatial measurements as % of slide dimensions, not absolute
  values, so they scale correctly.
- patternRecipes must include scaling rules — the generator will need
  to adapt patterns to different item counts.
- Do NOT duplicate what design_language already captures. Focus on
  actionable prescriptions, not descriptions.
- For colorSemantics.roleAssignment, map each semantic role to the
  theme color slot that serves it, including tintShade modifier and
  WHEN it is used.
- For shapeGrammar.primitiveVocabulary, this is the ALLOWED shape
  list — new designs must choose from this vocabulary only.

**Priority guidance:**

Not all fields carry equal weight for downstream generation. Spend
analytical effort proportionally.

- HIGH priority (consumed by composer-digest, drives generation):
  alignmentAnchors, marginStrategy, symmetryPreference,
  roleAssignment, colorEmphasisProgression, paletteBalance,
  scaleStops, emphasisMechanism, textDensityGuideline,
  primitiveVocabulary, compositionRules, scalingBehavior,
  patternRecipes (all fields)
- LOW priority (archival — preserved in profile, not in digest):
  zoneAllocation, densitySpectrum, scaleRatio, spacingConvention,
  connectorStyle, decorationPlacement

HIGH fields must be thorough and precise. LOW fields: populate if
clearly observable, set null if uncertain rather than guessing.

Return JSON conforming to the AestheticPrinciples schema:
```json
{
  "provenance": "vlm_cross_sample_synthesis",
  "compositionSystem": { ... },
  "colorSemantics": { ... },
  "typographicSystem": { ... },
  "shapeGrammar": { ... },
  "patternRecipes": [ ... ]
}
```

Read ALL images and $PROFILE — do NOT fabricate data.
