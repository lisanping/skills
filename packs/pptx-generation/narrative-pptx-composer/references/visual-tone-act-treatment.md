# Visual Tone — Dimension 2: Per-Act Visual Treatment

How accent intensity, background atmosphere, and decoration
vocabulary vary across the narrative arc. Single decision
pipeline: **pattern → intensity → coupling → atmosphere**.

---

## 2a — Color Temperature Strategy

Derived from `storytellingPattern` and `transitionStrategy`.

### Pattern → Strategy mapping

| Storytelling pattern family                | Color strategy          | Rationale                                                    |
| ------------------------------------------ | ----------------------- | ------------------------------------------------------------ |
| Evidence → Opportunity → Ask               | `restrained-to-bold`    | Build credibility quietly, then accent the ask               |
| Situation → Complication → Resolution      | `neutral-spike-resolve` | Neutral setup, high-contrast complication, resolution calm   |
| Problem → Evidence → Solution → Impact     | `cool-to-warm`          | Analytical opening, progressively warmer as solution emerges |
| Before/After                               | `split-contrast`        | Muted palette for "before", vibrant for "after"              |
| Context → Performance → Strategy → Roadmap | `steady-accent`         | Consistent accent usage — periodic updates not dramatic      |
| Vision → Proof → Call to Action            | `bold-validate-bold`    | Open bold, pull back for proof, bold close                   |
| What → So What → Now What                  | `flat-accent`           | Short deck, uniform intensity — no arc needed                |

### Accent intensity levels

| Level    | Meaning                                                            | Production guidance                                    |
| -------- | ------------------------------------------------------------------ | ------------------------------------------------------ |
| `low`    | Accent colors used sparingly — headers, single highlight per slide | ≤ 1 accent-colored element per slide body              |
| `medium` | Accent used for emphasis and grouping — charts, callout boxes      | 2–3 accent elements per slide                          |
| `high`   | Accent dominates visual attention — bold backgrounds, large areas  | Accent may fill shape backgrounds; full accent headers |

---

## 2b — Visual Rhythm Arc (Coupling Table)

The rhythm arc couples three visual dimensions to each act's
`accentIntensity` from § 2a.

### The Coupling Table

| `accentIntensity`          | Accent area                                                                 | Background type                                            | Decoration vocabulary                                                                             | Title scale                                         |
| -------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `low`                      | `accent-bar` only                                                           | `solid`                                                    | accent-bar, emphasis-line                                                                         | `heading1`                                          |
| `medium`                   | `accent-bar` + `surface-card` + `corner-accent`                             | `tinted` (0.03–0.05) or `solid backgroundAlt`              | accent-bar, surface-card, corner-accent, background-circle, step-connector                        | `heading1`                                          |
| `high`                     | `accent-band` or large accent shapes                                        | `tinted` (0.08) or `gradient`                              | accent-band, gradient-band, corner-accent, inset-card                                             | `display` for climax, `heading1` otherwise          |
| `instructional-rich` (any) | accent-bar on concept; accent-band on hero diagrams; per-layer color blocks | `solid` on code/diagram; `tinted` on architecture overview | + code-frame, terminal-chrome, diagram-frame, leader-line, layer-band, step-connector, badge-pill | `display` for chapter-opening, `heading1` otherwise |

### How to apply

For each act in `accentProgression`:

1. Look up the act's `accentIntensity` in the table above
2. Use **Accent area** column to size and place decorative
   shape zones for slides in that act
3. Use **Background type** column as the default background for
   content slides in that act — structural slides may override
   per `impactLevels` rules
4. Use **Title scale** column for title zone `size` token.
   Default: cover/closing/climax → `display`,
   `slideType: divider` → `heading2`, others → `heading1`

### Structural slide overrides

Cover and closing follow `impactLevels`, not the act's
`accentIntensity`:

| `impactLevel` | Background                    | Title scale | Decoration                    |
| ------------- | ----------------------------- | ----------- | ----------------------------- |
| `understated` | `solid` (primary)             | `display`   | Minimal — accent-bar only     |
| `standard`    | `solid` (primary)             | `display`   | accent-bar + one accent shape |
| `high-impact` | `gradient` (primary → accent) | `display`   | accent-bar + bold composition |

### Output format

Write into `s05b-style-policy.json → visualTone.rhythmArc`:

```json
"rhythmArc": {
  "perAct": [
    { "act": 1, "accentArea": "accent-bar only", "backgroundType": "solid", "titleScale": "heading1" },
    { "act": 2, "accentArea": "accent-bar + surface cards", "backgroundType": "tinted", "titleScale": "heading1" },
    { "act": 3, "accentArea": "accent-band or large shapes", "backgroundType": "tinted", "titleScale": "display for climax" }
  ]
}
```

---

## 2c — Background Atmosphere Selection

Background type adds visual temperature variation across the deck.
Selection is driven by narrative signals, not aesthetic preference.

### Selection rules (first match wins)

| Condition                                          | Background type                          | Layout guidance                                     |
| -------------------------------------------------- | ---------------------------------------- | --------------------------------------------------- |
| Structural slide + `impactLevel === "high-impact"` | `gradient`                               | centered-title-gradient                             |
| Structural slide + `impactLevel !== "high-impact"` | `solid` (primary)                        | centered-title-dark                                 |
| `narrativeRole === "pivot"`                        | `tinted` (0.08) or `gradient`            | diagonal-split, split-panel-left/right              |
| `narrativeRole === "climax"`                       | `tinted` (0.08)                          | hero-number, top-image-bottom-text with accent-band |
| `narrativeRole === "callback"`                     | `tinted` (0.03)                          | split-panel-left/right or sidebar-accent            |
| Act-level `accentIntensity === "high"`             | `tinted` (0.05)                          | Unlock all compositions                             |
| Act-level `accentIntensity === "medium"`           | `tinted` (0.03) or `solid backgroundAlt` | Standard + split-panels + sidebar-accent            |
| Act-level `accentIntensity === "low"`              | `solid`                                  | Standard compositions only                          |
| Default                                            | `solid`                                  | any composition matching semanticFit                |

**Layout family alternation rule:** Within any act containing ≥ 3
body slides, no layout composition may repeat more than twice
consecutively.

### Tinted background specification

```json
{ "type": "tinted", "base": "background", "tint": "accent", "tintOpacity": 0.05 }
```

Rendered in s07-build.py as: computed hex overlay → solid fill via
`RGBColor`.

### Gradient background specification

```json
{ "type": "gradient", "colors": ["primary", "accent"], "direction": "to-bottom-right" }
```

Use python-pptx gradient fill with resolved hex colors.
