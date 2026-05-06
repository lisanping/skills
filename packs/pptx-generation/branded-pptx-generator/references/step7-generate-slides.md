# Step 7 — Generate Slides

Process `slide-plan.json` **grouped by strategy** (not strictly
sequential), since same-strategy work shares the same context.
Within each group, follow `slide-plan.json` order so the final
`<p:sldIdLst>` ends up correct.

For every new slide produced by `add_slide.py`, append the printed
`<p:sldId>` element to `<p:sldIdLst>` in
`unpacked/ppt/presentation.xml` immediately.

All XML edits in this step (and Steps 8, 11) must follow the
[XML Editing Rules](xml-editing-rules.md).

## Subagent Delegation

Each slide's XML editing is independent — different files, no shared
state except `presentation.xml`. **Always** delegate per-slide content
filling to a subagent to keep the main context clean:

1. Main agent runs `add_slide.py` for **all** slides first, collecting
   the new slide filenames and `<p:sldId>` entries.
2. Main agent updates `presentation.xml` `<p:sldIdLst>` in one pass.
3. For each slide, launch a subagent with this prompt:

   ```
   Edit the slide XML at `unpacked/ppt/slides/{new_slide}.xml`.

   Source slide XML (for reference patterns): {read the cloneSource XML}
   Slide content: {slots from slide-content.json for this taskId}
   Style policy: {style-policy.json contents}
   Aesthetic guidance: {style-policy.json → aestheticGuidance, or "N/A"}

   Apply the XML Editing Rules section.

   Map each slot to the corresponding placeholder and replace text.
   Do NOT invent or modify content — use the exact text from
   slide-content.json.

   If aestheticGuidance is available:
   - Use colorRoleMap to choose theme colors for any new or modified
     elements (do not hardcode hex).
   - Use typeScale to verify font sizes match the expected role
     (title, body, caption).
   - Use shapeVocabulary to verify any shapes you add or modify use
     allowed shape types and treatments.

   Report what you changed.
   ```

4. Main agent reviews subagent results, then proceeds to Step 8.

If subagents are unavailable, the main agent handles all editing
inline.

## 7a — `clone-sample` and `clone-layout`

```bash
# From a layout
python $PPTX_SKILL/scripts/add_slide.py unpacked/ slideLayout2.xml

# From a sample slide
python $PPTX_SKILL/scripts/add_slide.py unpacked/ slide3.xml
```

Then edit the new slide's XML directly (`str_replace`), following the
[XML Editing Rules](xml-editing-rules.md).

## 7b — `augmented-clone`

Clone a sample or layout (same as 7a), then structurally modify the
resulting slide: add shapes, insert charts, change card counts, etc.
Two approaches:

- **XML editing** — for simple additions (extra text box, shape).
  Clone first, then `str_replace` to insert new XML elements.
- **lxml scripting** — for complex additions (charts, tables).
  Write a Python script that builds a `<p:spTree>` XML fragment via
  **lxml**, then merge it into the cloned slide in `unpacked/`.
  Follow the same spec → code → merge → validate procedure as Step 7c
  (see [spec-composed-strategy.md](spec-composed-strategy.md)),
  but skip the full style-spec step — use `style-policy.json` and the
  cloned slide's existing structure as the design baseline.

The cloned base inherits theme styling automatically; added elements
must reference `style-policy.json` for colors, fonts, and spacing.
Consult [generation-modes.md](generation-modes.md) for mode-dependent
design boundaries (what shapes, colors, and density changes are
permitted).

**Aesthetic guidance for additions:** When `style-policy.json →
aestheticGuidance` is non-null, all added elements must comply:
- **Shapes**: choose only from `shapeVocabulary` (same corner style,
  fill treatment, stroke conventions as existing template elements).
- **Colors**: look up each new element's semantic role in `colorRoleMap`
  to pick the correct theme color slot. Follow
  `colorEmphasisProgression` for emphasis decisions.
- **Spacing**: respect `compositionRules` margin and gap values when
  positioning new elements relative to existing ones.
- **Typography**: use `typeScale` stops for any new text elements.

## 7c — `spec-composed`

Use only when neither a layout nor a sample slide demonstrates the
required pattern (charts, timelines, custom infographics). Consult
[generation-modes.md](generation-modes.md) for mode-dependent design
boundaries before making design choices.

See [spec-composed-strategy.md](spec-composed-strategy.md) for the
full four-step procedure (style spec → code generation → merge →
validation) and critical coding rules.

**Checkpoint:** Every task in `slide-plan.json` has a corresponding
`<p:sldId>` entry in `presentation.xml`; the spec-composed slide passes
all validation checks defined in the reference doc.
