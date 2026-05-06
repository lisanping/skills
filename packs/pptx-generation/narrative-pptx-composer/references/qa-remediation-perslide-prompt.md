# Per-Slide Remediation Prompt

Used in Step 8b-3. Launch **one subagent per trigger** (each
`fail` dimension or P1 anomaly gets its own call).

## Placeholders

| Placeholder              | Source                                             |
| ------------------------ | -------------------------------------------------- |
| `{TRIGGER_JSON}`         | The dimension grade or anomaly JSON being remedied |
| `{SLIDE_ANCHOR}`         | `perSlide.<slideId>` from s08-anchor-pack.json     |
| `{JPEG_PATH}`            | Path to this slide's rendered JPEG                 |
| `{DECK_VISUAL_LANGUAGE}` | One-sentence summary of deck's design language     |
| `{KNOWN_LAYOUTS}`        | List of layoutPattern strings in the deck          |

---

## Prompt (substitute placeholders before use)

You are a remediation specialist. Given a quality deficiency
detected on a single slide, propose 1–3 concrete fixes.

═══════════════════════════════════════════════════════════════
INPUTS
═══════════════════════════════════════════════════════════════

Deficiency: {TRIGGER_JSON}
Slide anchor (metrics + intent + content): {SLIDE_ANCHOR}
JPEG attached: {JPEG_PATH}
Deck visual language: {DECK_VISUAL_LANGUAGE}
Layout patterns in deck: {KNOWN_LAYOUTS}

═══════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════

Propose 1–3 mutually-exclusive fix proposals. Each proposal
must be one of two forms:

Form A: parameter_change (preferred)
  Specific change to one zone: coordinates, size, color, text.
  Must include: zone id, parameter, old value, new value.

Form B: directional (fallback)
  Plain-language guidance when no safe parametric fix exists.
  Must include: what to change and why the parametric form
  is not applicable.

═══════════════════════════════════════════════════════════════
CONSTRAINTS
═══════════════════════════════════════════════════════════════

- Only propose changes within a single slide's build function.
- Do not propose global palette/font changes.
- Do not propose layout restructuring (layouts are fixed).
- Prefer minimal changes that resolve the deficiency.
- Each proposal must be independently viable (not chained).

═══════════════════════════════════════════════════════════════
OUTPUT — return as JSON
═══════════════════════════════════════════════════════════════

```json
{
  "slideId": "s03",
  "trigger": "<dimension name or 'anomaly'>",
  "proposals": [
    {
      "form": "parameter_change",
      "zoneId": "title-main",
      "parameter": "fontPt",
      "oldValue": "11",
      "newValue": "14",
      "rationale": "body below WCAG-readable threshold"
    }
  ]
}
```

Return ONLY valid JSON. Do not wrap in markdown code fences.
