---
output_schema: $SKILL/schemas/profile_schema.json#sample_slide_catalog, #design_language
sync_with: SKILL.md ## Step 4b merge instructions
variables: [SAMPLE_SLIDES, LAYOUT_PREVIEWS, PROFILE, SKILL]
enums: $SKILL/schemas/enums.json
enum_rule: All enum-typed fields MUST use values from enums.json. Read it first.
---

Analyze ALL sample slides in this template. For each slide where
has_content is true, perform THREE tasks in order:
first complete Task A + B for ALL slides, then do Task C.

Read the output schema first:
`$SKILL/schemas/profile_schema.json` → sample_slide_catalog item
properties and design_language definition. Property descriptions
define what each field means.

**Task A — Role classification:**
Assign role (enum: slide_role):
- "sample": normal content slide demonstrating a layout/style
- "guide": template usage guide (color palettes, typography specs,
  do's/don'ts, layout conventions)
- "hybrid": both instructional AND a useful style reference

If guide, assign guideType (enum: guide_type).
Err conservative: only mark guide when clearly instructional.

**Task B — Style classification (sample/hybrid only):**

Compare each slide against its mapped layout:
- View slide preview: `$SAMPLE_SLIDES/slide{N}.jpg`
- View layout preview: `$LAYOUT_PREVIEWS/slideLayout{M}.jpg` + annotated
- Read layout attributes from `$PROFILE` → layouts[]

Populate the VLM-assigned fields defined in the schema:
contentPattern, patternDescription, complexElements, cloneCandidate,
layoutRelationship (enum), styleSourceType (enum),
styleRefSuitability (enum), layoutMismatchSummary.

Skip Task B for role="guide".

Inputs:
1. `$SAMPLE_SLIDES/slide{N}.jpg`
2. `$LAYOUT_PREVIEWS/slideLayout{M}.jpg` + annotated
3. `$PROFILE` → sample_slide_catalog, layouts, identity

Also list any design_language_supplements not captured in design_language.
Sample slides often reveal design elements invisible in layout previews.
Specifically look for component styling that only appears in samples:
- corner style, fill style, shadow/effects, line/border treatment
If these contradict or extend what Step 3b found in layouts, include
them in design_language_supplements with a note that sample slides
take precedence over layout-only observations.

**Task C — Brand guardrails (once, after reviewing all slides):**

Emit 3–7 brand-specific guardrails the composer should respect.
Each guardrail: { rule: concise imperative sentence, severity: "soft" }

Focus on constraints that are template-specific and observable (whitespace
density, color emphasis patterns, visual grammar conventions, content
density limits). Do NOT emit generic advice.

Return JSON:

```json
{
  "slideAnalysis": [
    {
      "slide_file": "slideN.xml",
      "role": "sample | guide | hybrid",
      "guideType": "... | null",
      "contentPattern": "...",
      "patternDescription": "... | null",
      "complexElements": [],
      "cloneCandidate": true,
      "layoutRelationship": "...",
      "styleSourceType": "...",
      "styleRefSuitability": "...",
      "layoutMismatchSummary": "..."
    }
  ],
  "design_language_supplements": [],
  "vlm_guardrails": [
    { "rule": "...", "severity": "soft" }
  ]
}
```

(Set Task B fields to null for guide slides.)
Read the images and $PROFILE — do NOT fabricate data.
