# Visual Tone — Dimensions 3 & 4: Whitespace Rhythm and Visual Contrast

---

## Dimension 3 — Whitespace Rhythm

Per-act minimum whitespace percentage, derived from
`informationDensity` in the narrative architecture.

### Density → Whitespace floor mapping

| `informationDensity` | `minWhitespacePct` | Max body elements | Notes                                                  |
| -------------------- | ------------------ | ----------------- | ------------------------------------------------------ |
| `minimal`            | 55%                | 3                 | Dividers, title cards. Breathing room is the content   |
| `light`              | 40%                | 5                 | Setup slides. Space for the audience to absorb context |
| `medium`             | 30%                | 7                 | Standard content slides. Balanced density              |
| `dense`              | 20%                | 10                | Data-heavy slides. Minimum viable whitespace           |

When an act specifies a density **gradient** (e.g. `"light → dense"`),
interpolate for slides between the first and last.

**Whitespace includes:** empty areas, margins, inter-element gaps,
and non-content placeholder regions. Does **not** include interior
of content shapes.

### Proximity — the spatial logic of grouping

The **proximity principle**: elements that are logically related
should sit close together; elements that are logically separate
should sit far apart.

**Authoring rule** — when designing `layoutSpec.zones[]`, decide
gaps in two tiers:

- **Intra-group gap** — between zones that belong together (figure +
  caption, KPI numbers + labels). Use `spacing.rowGapInches` or smaller.
- **Inter-group gap** — between distinct logical groups. Use **at least
  1.5×** the intra-group gap, often 2×.

Failure mode to avoid: distributing all elements with **uniform**
spacing for "balance". Uniform spacing flattens hierarchy.

---

## Dimension 4 — Visual Contrast Strategy

How visually different adjacent sections or acts should look.
Derived from `transitionStrategy` in the narrative architecture.

### Default strategy table

| `transitionStrategy`     | Default visual contrast                                                   | Production guidance                                                        |
| ------------------------ | ------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `progressive-disclosure` | Gradual intensification — layout stays consistent; color/density increase | Same layout family across acts; accent and density ramp up                 |
| `contrast`               | Sharp visual differentiation — adjacent acts look noticeably different    | Different layout families per act; color shifts at act boundaries          |
| `callback`               | Motif recurrence — later sections visually echo earlier ones              | Reuse specific layouts or color treatments from Act 1 in later acts        |
| `parallel`               | Symmetric structure — parallel threads share a visual pattern             | Identical layout for parallel sections; differentiate only by accent color |

### Earned exceptions

A slide may deviate from its strategy's default when **all** hold:

1. **Local scope** — at most 1 deviating slide per act, or 2 in a
   deck of > 12 body slides.
2. **Narrative justification** — the deviation reinforces a specific
   `narrativeRole` or storytelling beat. "To add variety" is not
   sufficient.
3. **Recorded** — logged as `transitionDeviation` inside
   `designRationale`:

```json
"transitionDeviation": {
  "from": "parallel",
  "appliedInstead": "asymmetric-callback",
  "narrativeJustification": "Slide echoes Act 1's pivot moment; symmetric layout would mute the recognition"
}
```

### When deviation is encouraged

- A `callback` slide inside a `parallel` set (recognition needs
  visual difference from parallel siblings).
- Closing of a `progressive-disclosure` deck snapping to `contrast`
  (closing must register as a *turn*, not as next step).
- A `pivot` slide inside `callback` strategy breaking the motif
  (the narrative refuses the past).
