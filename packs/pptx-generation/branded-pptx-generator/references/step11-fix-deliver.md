# Step 11 — Fix, Verify & Deliver

1. List every issue from Steps 9–10.
2. Fix each one at the source (XML edit or regenerate the slide).
3. If fixes added or removed slides (changing total count or order),
   recompute agenda page numbers from the updated `<p:sldIdLst>`
   (same procedure as Step 8 sub-step 6), patch the agenda slide's
   XML, and include it in the re-inspection set.
4. Re-pack, re-render the affected slides, re-inspect with the subagent.
5. Repeat until a full pass surfaces no new issues.

**Maximum 1 fix-and-verify cycle.** If issues persist, deliver the
current output with a written summary of remaining issues.

```bash
# Naming: {Brand}_{mode}_{timestamp}_{topic_slug}.pptx
# topic_slug: 2-4 words from content-outline intent.topic, underscored
TOPIC_SLUG=$(echo "<topic>" | tr ' ' '_' | head -c 40)
cp output.pptx "outputs/${BRAND}_${MODE}_${TIMESTAMP}_${TOPIC_SLUG}.pptx"
```

Report to the user:

- Number of slides generated and the mode used
- Layouts used (confirm variety)
- Any unresolved issues or `accepted_best` compromises
- Any guide-rule overrides that influenced decisions

Write `generation-report.json` in `$SESSION`:

```json
{
  "mode": "balanced",
  "slideCount": 10,
  "layoutsUsed": ["slideLayout2.xml", "slideLayout4.xml", "slideLayout7.xml"],
  "strategies": {"clone-sample": 4, "clone-layout": 3, "augmented-clone": 2, "spec-composed": 1},
  "compliance": {
    "lockedViolations": 0,
    "wcagIssues": 0,
    "leftoverPlaceholders": false
  },
  "schemaValidation": "pass",
  "visualIssuesFound": 2,
  "visualIssuesFixed": 2,
  "unresolvedIssues": [],
  "outputFile": "outputs/Accenture_balanced_20260413_Q2_strategy_review.pptx"
}
```
