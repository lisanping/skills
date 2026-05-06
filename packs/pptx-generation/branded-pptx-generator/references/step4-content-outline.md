# Step 4 — Create Content Outline

Analyze the user's request and produce `content-outline.json` — the
content-side plan that Step 5 will map onto template layouts. This is
pure LLM reasoning: no tools, no template knowledge needed yet.

Three sub-tasks in one pass:

1. **Intent analysis** — Extract the topic, audience, tone, explicit
   slide-count constraint (if any), and key messages or data points
   the user expects to see.

2. **Narrative arc** — Decide the storytelling structure. Common arcs:
   `situation → analysis → recommendation → next steps`,
   `problem → evidence → solution → impact`,
   `context → performance → strategy → roadmap`.
   Pick the one that best fits the intent.

3. **Section & role allocation** — Break the narrative into sections,
   assign a slide count per section (must sum to the user's requested
   total or a sensible default), and pre-assign a `semanticRole` to
   each slide slot. Valid roles: `cover`, `divider`, `content_text`,
   `content_data`, `content_mixed`, `closing`.

Write `content-outline.json`:

```json
{
  "intent": {
    "topic": "Q2 2026 strategy review",
    "audience": "executive leadership team",
    "tone": "formal, data-driven",
    "slideCount": 10,
    "keyMessages": [
      "Q2 financial performance vs targets",
      "Progress on three strategic pillars",
      "H2 roadmap and resource asks"
    ]
  },
  "narrativeArc": "context → performance → strategy → roadmap",
  "sections": [
    {
      "title": "Opening",
      "slideCount": 1,
      "roles": ["cover"]
    },
    {
      "title": "Q2 Performance",
      "slideCount": 2,
      "roles": ["divider", "content_data"]
    },
    {
      "title": "Strategic Pillars",
      "slideCount": 4,
      "roles": ["divider", "content_text", "content_text", "content_mixed"]
    },
    {
      "title": "Roadmap & Next Steps",
      "slideCount": 2,
      "roles": ["divider", "content_data"]
    },
    {
      "title": "Closing",
      "slideCount": 1,
      "roles": ["closing"]
    }
  ]
}
```

**Rules:**

- Every deck starts with exactly one `cover` and ends with one `closing`.
- Sections with ≥ 2 body slides get a `divider` as their first slide.
- Respect the user's slide count if specified; otherwise default to
  8–12 slides depending on content density.
- `keyMessages` should be concrete and traceable — avoid vague labels
  like "overview" or "summary" unless the user literally said that.

**Checkpoint:** `content-outline.json` exists in `$SESSION`; slide
counts sum to the requested total; every slide slot has a
`semanticRole`; `narrativeArc` is a coherent storytelling structure.
