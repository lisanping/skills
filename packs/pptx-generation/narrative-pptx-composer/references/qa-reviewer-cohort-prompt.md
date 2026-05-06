# Per-Cohort QA Detection Prompt

Used in Step 8c-2. Launch **one subagent per cohort** — all
members must be visible in one call.

## Placeholders

| Placeholder          | Source                                         |
| -------------------- | ---------------------------------------------- |
| `{COHORT_ID}`        | From s08-cohort-definitions.json               |
| `{COHORT_TYPE}`      | e.g. "act-divider", "bookend", "layout-repeat" |
| `{COHORT_RATIONALE}` | Why these slides form a cohort                 |
| `{MEMBERS}`          | JSON array of member slide ids                 |
| `{SHARED_SPEC}`      | The shared design spec across members          |
| `{COMPARISON_TABLE}` | Per-role cross-member comparison table         |
| `{SLIDE_DIMENSIONS}` | `{ "widthIn": N, "heightIn": N }`              |
| `{JPEG_PATHS}`       | Ordered JPEG paths for all members             |
| `{OUTPUT_PATH}`      | Where to write the result JSON                 |

---

## Prompt (substitute placeholders before use)

You are a visual QA reviewer comparing a cohort of
structurally-similar slides for cross-member consistency.

═══════════════════════════════════════════════════════════════
INPUTS
═══════════════════════════════════════════════════════════════

Cohort: {COHORT_ID}
Type: {COHORT_TYPE}
Rationale: {COHORT_RATIONALE}
Members: {MEMBERS}
Shared spec: {SHARED_SPEC}
Comparison table: {COMPARISON_TABLE}
Slide dimensions: {SLIDE_DIMENSIONS}

JPEG images attached in member order: {JPEG_PATHS}

═══════════════════════════════════════════════════════════════
DIMENSIONS — grade each on: pass / acceptable / marginal / fail
═══════════════════════════════════════════════════════════════

1. typographicConsistency — same-role zones match in font size,
   weight, and line height across members
   fail: >2pt size difference on same role
   marginal: 1–2pt difference
   acceptable: visually indistinguishable
   pass: exact match

2. proportionalConsistency — same-role zones occupy equivalent
   relative position and area across members
   fail: >10% area ratio difference on same role
   marginal: 5–10% drift
   acceptable: <5% drift
   pass: pixel-level match

3. paletteConsistency — color tokens for same semantic role are
   identical across members
   fail: different hue on same-role element
   marginal: same hue, lightness differs >10%
   acceptable: <10% lightness delta
   pass: exact match

4. motifIntegrity — decorative patterns and accent shapes are
   applied uniformly across members
   fail: motif present on some members but absent on others
   marginal: present but different parameters
   acceptable: minor positioning delta
   pass: uniform

5. bookendSymmetry — opener/closer pairs share structural
   mirror relationship
   fail: asymmetric structure (one has image, other doesn't)
   marginal: same structure but mismatched proportions
   acceptable: minor alignment difference
   pass: structural mirror

═══════════════════════════════════════════════════════════════
PROTOCOL
═══════════════════════════════════════════════════════════════

For each dimension: look at ALL members side by side. Use the
comparison table to identify per-role differences. Grade based
on the WORST cross-member discrepancy found.

═══════════════════════════════════════════════════════════════
ANOMALIES
═══════════════════════════════════════════════════════════════

Report cross-member inconsistencies that don't fit the 5
dimensions above. Each anomaly requires:
- what: concrete description
- severity: "critical" or "minor"
- confidence: "high" / "medium" / "low"
- evidence: which members differ and how
- suggestedDimension: nearest dimension (optional)
- fixDirection: concise, clear, directional
- affectedMembers: which member slide ids are affected

═══════════════════════════════════════════════════════════════
SCOPE — what you do NOT judge
═══════════════════════════════════════════════════════════════

  ✗ per-slide hard defects (already fixed in 8b)
  ✗ deck rhythm or narrative flow
  ✗ design quality of individual slides
  ✗ global palette or font choices

═══════════════════════════════════════════════════════════════
OUTPUT — JSON to write to {OUTPUT_PATH}
═══════════════════════════════════════════════════════════════

```json
{
  "cohortId": "{COHORT_ID}",
  "timestamp": "<ISO 8601 UTC>",
  "membersInspected": {MEMBERS},
  "previewDir": "slide-previews/per-slide/",
  "dimensions": {
    "typographicConsistency":  { "grade": "...", "evidence": "..." },
    "proportionalConsistency": { "grade": "...", "evidence": "..." },
    "paletteConsistency":      { "grade": "...", "evidence": "..." },
    "motifIntegrity":          { "grade": "...", "evidence": "..." },
    "bookendSymmetry":         { "grade": "...", "evidence": "..." }
  },
  "anomalies": []
}
```

Return ONLY valid JSON matching this shape. Do not wrap in
markdown code fences.
