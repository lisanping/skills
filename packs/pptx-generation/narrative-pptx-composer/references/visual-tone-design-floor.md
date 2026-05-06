# Visual Tone — Universal Design Floor

Applies to every deck, every register. These are quotas enforced
by `s05_validate_plan.py` and Step 8 QA. A deck that fails them
is unfinished, not just modest.

---

## Design Ambition

Passthrough parameter from `s01b-query-intent.json →
aestheticSignals.designAmbition`. **Default: `expressive`.**

| Value        | When to use                                                                          | What it means                                                         |
| ------------ | ------------------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| `expressive` | Almost every deck                                                                    | Deliberate variety within the register's idiom                        |
| `restrained` | Only when user explicitly requests minimalism, or `regulatory` + internal-compliance | Quotas relax by 50% but never to zero. Smaller moves, still mandatory |

`restrained` is **never** auto-selected by purpose × formality alone.

---

## Register-appropriate Expressive Vocabulary

| Register             | Expressive vocabulary                                                                      |
| -------------------- | ------------------------------------------------------------------------------------------ |
| `authoritative`      | Extreme asymmetry, single oversized typographic moment, large dark color blocks            |
| `analytical`         | Data-rhythm contrast (dense → sparse), KPI hero treatments, structured grids + accent      |
| `conversational`     | Saturated color blocks, rounded geometry, icon systems, playful typographic scale jumps    |
| `inspirational`      | Full-bleed imagery, display-scale typography, single-element compositions, max whitespace  |
| `instructional-rich` | Diagrams as heroes, code framed as visual artifacts, layered stacks, semantic color coding |

---

## Quotas (exact thresholds enforced by validator)

### Quota 1 — Layout variety (deck-wide)

For decks > 6 body slides: distinct `layoutPattern` count ≥ 60%
of body count; no single composition > 30%. Structural slides
excluded.

`restrained`: thresholds become 40% / 50%.

### Quota 2 — Hero cadence

Every 5 consecutive body slides must contain ≥ 1 hero slide
(display-scale title ≥ 30% area, OR non-white body background,
OR asymmetric split with zone ≥ 60% filled primary/accent,
OR full-bleed image with overlay).

`restrained`: every 8 consecutive → ≥ 1 hero.

### Quota 3 — Color-area floor

At least 30% of body slides must have non-white background OR a
shape filled with a color-weight token (`primary*`, `accent*`,
`secondary*`) occupying ≥ 15% of slide area.

`restrained`: floor drops to 15%.

### Quota 4 — Typographic punch

- ≥ 2 occurrences of `display`-scale title (only the literal
  token `"display"` counts — numeric sizes ≥ 44pt do not).
- ≥ 1 slide with title color ∈ {`primary`, `accent`,
  `background` (on dark)}.

`restrained`: ≥ 1 `display` title; title color quota dropped.

---

## Failure mode taxonomy

When a quota fails:

1. **Promote organically.** Identify candidate slides that can be
   upgraded — swap a `two-column` body into a `split-panel-left`
   to add color, or upgrade a climax title to `display`.
2. **Auto-relax if no organic option exists.** Record as
   `quotaWaiver` in `designRationale`:

```json
"quotaWaiver": {
  "quota": "hero-cadence",
  "slideId": "s07",
  "reason": "Single-line takeaway with no quantitative anchor; hero treatment would feel forced",
  "compensation": "adjacent slide s06 escalated to hero-number"
}
```

3. Compensation is encouraged but not required.

**Never block to ask the user. The deck is always delivered.**
