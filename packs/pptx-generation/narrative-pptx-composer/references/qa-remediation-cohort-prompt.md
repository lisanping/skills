# Per-Cohort Remediation Prompt

Used in Step 8c-4. Launch **one subagent per trigger** (each
`fail` dimension or P1 anomaly gets its own call).

## Placeholders

| Placeholder              | Source                                             |
| ------------------------ | -------------------------------------------------- |
| `{TRIGGER_JSON}`         | The dimension grade or anomaly JSON being remedied |
| `{COHORT_ENTRY}`         | Full cohort entry from s08-cohort-definitions.json |
| `{JPEG_PATHS}`           | Paths to all member JPEGs                          |
| `{DECK_VISUAL_LANGUAGE}` | One-sentence summary of deck's design language     |
| `{KNOWN_LAYOUTS}`        | List of layoutPattern strings in the deck          |

---

## Prompt (substitute placeholders before use)

You are a remediation specialist. Given a consistency deficiency
across a cohort of slides, propose 1–3 fixes that bring members
into alignment.

═══════════════════════════════════════════════════════════════
INPUTS
═══════════════════════════════════════════════════════════════

Deficiency: {TRIGGER_JSON}
Cohort: {COHORT_ENTRY}
Member JPEGs attached: {JPEG_PATHS}
Deck visual language: {DECK_VISUAL_LANGUAGE}
Layout patterns in deck: {KNOWN_LAYOUTS}

═══════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════

Propose 1–3 mutually-exclusive fix proposals. Each must be:

Form A: parameter_change (preferred)
  Specific change applied uniformly to affected members.
  Must include: role, parameter, target value, which members.

Form B: directional (fallback)
  Plain-language guidance for the designer.

═══════════════════════════════════════════════════════════════
CONSTRAINTS
═══════════════════════════════════════════════════════════════

- Fixes go through COHORT_OVERRIDES (applied to all members
  of the same role). Do not propose per-slide exceptions.
- Do not propose global palette/font changes.
- Prefer aligning TO the majority pattern (change the outlier,
  not the majority).
- Each proposal must be independently viable.

═══════════════════════════════════════════════════════════════
OUTPUT — return as JSON
═══════════════════════════════════════════════════════════════

```json
{
  "cohortId": "cohort-act-dividers",
  "trigger": "<dimension name or 'anomaly'>",
  "proposals": [
    {
      "form": "parameter_change",
      "role": "title",
      "parameter": "fontPt",
      "targetValue": "28",
      "affectedMembers": ["s06"],
      "rationale": "s06 title is 24pt vs 28pt on s03/s09"
    }
  ]
}
```

Return ONLY valid JSON. Do not wrap in markdown code fences.
