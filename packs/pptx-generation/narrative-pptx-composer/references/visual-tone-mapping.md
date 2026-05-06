# Visual Tone Mapping — Content-Driven Design Language

Routing index. Read only the dimension file you need for the
current sub-step — not all files at once.

Primary consumer: Step 5b (visual tone derivation). Also
referenced by 6a (palette tokens), 6c (emphasis/background),
and 6d (style policy freeze).

---

## Overview

Steps 2–3 define *what* to communicate and *how* the story unfolds.
This reference translates those content decisions into visual
design parameters that guide downstream production (Steps 5–8).

```text
Steps 2–3 artifacts   →  Visual Tone (this index)  →  s05b-style-policy.json
(content strategy)       (design intent)              (direct to production)
```

---

## Dimension routing

| When                                              | Read                                                                                     |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Determining the deck's overall design posture     | [visual-tone-register.md](visual-tone-register.md)                                       |
| Per-act accent, background, decoration decisions  | [visual-tone-act-treatment.md](visual-tone-act-treatment.md)                             |
| Whitespace floors / proximity gaps                | [visual-tone-rhythm-contrast.md](visual-tone-rhythm-contrast.md) § Dimension 3           |
| How different adjacent acts should look           | [visual-tone-rhythm-contrast.md](visual-tone-rhythm-contrast.md) § Dimension 4           |
| Cover / closing visual weight                     | [visual-tone-impact-imagery.md](visual-tone-impact-imagery.md) § Dimension 5             |
| When / how to use images, icons, diagrams         | [visual-tone-impact-imagery.md](visual-tone-impact-imagery.md) § Dimension 6             |
| Minimum image quotas per register × demand        | [visual-tone-impact-imagery.md](visual-tone-impact-imagery.md) § Imagery Floor           |
| Bookend/divider imagery for tech/analytical decks | [visual-tone-impact-imagery.md](visual-tone-impact-imagery.md) § Structural-slide uplift |
| Expanding 4-color palette to 10 tokens            | [visual-tone-palette-rules.md](visual-tone-palette-rules.md)                             |
| Mandatory design minimums (4 quotas)              | [visual-tone-design-floor.md](visual-tone-design-floor.md)                               |
| Resolving `imageryDemand` (Step 3a sub-task 6)    | [step3-narrative-blueprint.md § Imagery Demand cascade](step3-narrative-blueprint.md)    |

---

## Input Signals

All inputs come from Steps 2–3 artifacts.

| Signal                      | Source                                                                                          | Drives                           |
| --------------------------- | ----------------------------------------------------------------------------------------------- | -------------------------------- |
| `contentDomain`             | `s01c-content-digest.json` + `s03-presentation-blueprint.json` + `s02-communication-brief.json` | Visual register (domain axis)    |
| `presentationPurpose`       | `s02-communication-brief.json`                                                                  | Visual register (purpose axis)   |
| `formalityLevel`            | `s02-communication-brief.json → constraints`                                                    | Visual register (formality axis) |
| `storytellingPattern.name`  | `s03-presentation-blueprint.json → architecture`                                                | Visual contrast strategy         |
| `transitionStrategy`        | `s03-presentation-blueprint.json → architecture`                                                | Visual contrast strategy         |
| `acts[].emotionalArc`       | `s03-presentation-blueprint.json → architecture`                                                | Color temperature per act        |
| `acts[].informationDensity` | `s03-presentation-blueprint.json → architecture`                                                | Whitespace rhythm per act        |
| `openingHook` intensity     | `s03-presentation-blueprint.json → architecture`                                                | Cover impact level               |
| `closingAnchor` intensity   | `s03-presentation-blueprint.json → architecture`                                                | Closing impact level             |

---

## Downstream Consumption

Steps 6-9 read `visualTone` from `s05b-style-policy.json`:
`whitespaceRhythm.perAct` shapes Step 6 text length;
`accentProgression`, `contrastStrategy`, and `rhythmArc.perAct`
drive Step 7 background, accent, and decoration choices; Step 8
QA checks that visual rhythm matches `visualTone`.
