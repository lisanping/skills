# Step 5 — Slide Visual Design

Routing index for Step 5 sub-steps. Read only the sub-step you
are currently executing — not the entire set.

See [SKILL.md](../SKILL.md) § Step 5 for the mandatory rules summary.

Bound by [design-principles.md](design-principles.md) and
[design-guardrails.md](design-guardrails.md). Every body slide
answers: narrative, narrativeLink, focalPoint + eyePath, aestheticMove.
Every layout is designed from content, not selected from a catalog.

---

## Global context (applies to all sub-steps)

Honor `s01b.aestheticSignals` throughout Step 5:
- `designAmbition` overrides default `expressive` in 5b.
- `moodKeywords` bias toward expressive compositions.
- `avoidKeywords` are hard exclusions for imagery/decoration.
- `diversityPreference: "high"` tightens variety quotas.

Honor `s01b.inputMode` — it sets the overall design strategy:

| `inputMode` | Design strategy                                                                                              |
| ----------- | ------------------------------------------------------------------------------------------------------------ |
| `generate`  | Standard layout authoring from narrative; no source layout to reference.                                     |
| `beautify`  | Treat source image style + topology as strong inspiration; design `layoutSpec` from scratch.                 |
| `reproduce` | Honor source topology; lower `designAmbition` toward fidelity. Suspends some variety rules (see Rules 1, 5). |
| `expand`    | Image style feeds `aestheticSignals` only; layout authored from narrative as in `generate`.                  |

---

## Sub-step routing

| Sub-step | What it does                                             | Read                                                       |
| -------- | -------------------------------------------------------- | ---------------------------------------------------------- |
| **5a**   | Fill deferred design fields (palette, fonts, contrast)   | [step5a-design-config.md](step5a-design-config.md)         |
| **5b**   | Derive visual tone from content strategy                 | [step5b-visual-tone.md](step5b-visual-tone.md)             |
| **5c**   | Freeze `s05b-style-policy.json` — read-only from here on | [step5c-freeze-checkpoint.md](step5c-freeze-checkpoint.md) |
| **5d**   | Design each slide's `layoutSpec` (3 phases × N slides)   | [step5d-slide-layout.md](step5d-slide-layout.md)           |
| **5f**   | Generate images (if needed)                              | [step5f-image-generation.md](step5f-image-generation.md)   |

Supporting references (read on demand, not pre-loaded):

| Reference                                        | When to consult                                        |
| ------------------------------------------------ | ------------------------------------------------------ |
| [visual-tone-mapping.md](visual-tone-mapping.md) | During 5b: dimension derivation framework              |
| [layout-principles.md](layout-principles.md)     | During 5d: grid, margins, zone vocabulary, decorations |
| [image-prompt-guide.md](image-prompt-guide.md)   | During 5f: prompt authoring                            |
| [vlm-image-selection.md](vlm-image-selection.md) | During 5f: variation selection                         |

---

## Checkpoint

`s01d-design-config.json` fully resolved;
`s05-slide-visual-design.json` with `layoutSpec` for every slide;
`s05b-style-policy.json` with complete palette and visual tone.
Every zone in every `layoutSpec` has valid coordinates within
slide dimensions.

```bash
python $COMPOSER_SKILL/scripts/s05_validate_plan.py "$SESSION"
```

The validator checks blueprint coverage, layout spec validity,
geometric constraints (overlap, bounds), and style policy structure.
