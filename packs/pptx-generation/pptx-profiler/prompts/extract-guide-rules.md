---
output_schema: $SKILL/schemas/profile_schema.json#template_guide
sync_with: SKILL.md ## Step 4d merge instructions
variables: [SAMPLE_SLIDES, PROFILE, SKILL]
enums: $SKILL/schemas/enums.json
enum_rule: All enum-typed fields MUST use values from enums.json. Read it first.
---

Extract structured design rules from guide slides.

Inputs:
1. Read guide-rules-raw.json (text blocks, rule kinds, color swatches)
2. Preview images: $SAMPLE_SLIDES/slide{N}.jpg for each guide slide
3. $PROFILE → identity (colors, fonts)

For each guide slide, extract rules with these fields:
- ruleKind (enum: rule_kind)
- applies_to: natural language (e.g., "headline", "pie chart component")
- constraint: structured object when possible, null for donts
- rawQuote: original text from the slide
- sourceSlide: slide_file
- confidence: 0-1

Notes:
- donts: constraint=null, keep rawQuote + applies_to only
- typography/color: extract specific values into constraint
- elementUsage: capture reusable component instructions (editable
  charts, icon libraries, shape groups) and usage caveats

Return JSON:

```json
{
  "extractedRules": [
    {
      "ruleKind": "...",
      "applies_to": "...",
      "constraint": { } | null,
      "rawQuote": "...",
      "sourceSlide": "slideN.xml",
      "confidence": 0.0
    }
  ]
}
```

Read guide-rules-raw.json, images, and $PROFILE — do NOT fabricate data.
