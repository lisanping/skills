# Visual Tone — Dimensions 5 & 6: Impact Levels and Imagery Guidance

---

## Dimension 5 — Impact Levels

Visual weight for the cover and closing slides.

### Assessing hook/anchor intensity

Read `openingHook` and `closingAnchor` from the narrative
architecture and classify:

| Signal               | `understated`              | `standard`             | `high-impact`                         |
| -------------------- | -------------------------- | ---------------------- | ------------------------------------- |
| Emotional charge     | Factual, neutral           | Moderate engagement    | Provocative, urgent, aspirational     |
| Specificity          | General context            | Specific claim or data | Bold quantified statement or question |
| Audience familiarity | Audience knows the context | Mixed awareness        | Cold audience or high-stakes decision |

### Impact → Visual treatment

| Level         | Cover treatment                                                       | Closing treatment                                                 |
| ------------- | --------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `understated` | Clean title + subtitle, standard layout, minimal accent               | Simple summary layout, standard styling                           |
| `standard`    | Title with one accent element, balanced composition                   | Key takeaway + CTA, moderate accent use                           |
| `high-impact` | Full visual treatment — large type, accent background or bold imagery | Strong visual CTA — accent background, isolated ask, max contrast |

---

## Dimension 6 — Imagery Guidance

When and how to use visual elements beyond text and data.

| Register             | Default imagery approach                                                                         |
| -------------------- | ------------------------------------------------------------------------------------------------ |
| `authoritative`      | `data-forward` — charts, tables, KPIs dominate. No decorative imagery.                           |
| `analytical`         | `data-forward with selective icon accents` — data primary; icons for categorization.             |
| `conversational`     | `icon-rich` — icons and simple illustrations to support each point.                              |
| `inspirational`      | `imagery-led` — large photographs or conceptual visuals; data as single hero numbers.            |
| `instructional-rich` | `diagram-led` — architecture diagrams, sequence flows, code blocks, annotated callouts dominate. |

**Override signals:**

- ≥ 3 `content_data` sections → bias toward `data-forward`.
- ≥ 2 `narrativeIntent: "metaphor"` slides → bias toward `imagery-led`.
- `formalityLevel: "regulatory"` → force `data-forward`.
- `contentDomain = "technical-instructional"` → force `diagram-led`.
- `contentDomain = "data-analytical"` → force `data-forward`.
- `contentDomain = "creative-portfolio"` → force `imagery-led`;
  ≥ 50% body slides should include image zones.

---

## Imagery Floor (binding minimums per `imageryDemand`)

The floor wins when stricter than register default. Read
`s05b-style-policy.json → visualTone.imageryDemand` (mirrored
from `s03-presentation-blueprint.json → architecture.imageryDemand`).

| Register                               | Demand `high`                                                              | Demand `medium`                                                                            | Demand `low`                 | Demand `none`            |
| -------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ---------------------------- | ------------------------ |
| `inspirational` / `creative-portfolio` | Cover **and** closing bg = `image-generated`; ≥ 50% body have `image` zone | Cover **and** closing bg ∈ {`image-generated`, `gradient`}; ≥ 30% body have `image` zone   | ≥ 20% body have `image` zone | No imagery required      |
| `conversational`                       | Cover bg = `image-generated`; ≥ 30% body have `image`/`icon` zone          | Cover **and** closing bg ∈ {`image-generated`, `gradient`}; ≥ 20% body have `image`/`icon` | Optional                     | No imagery required      |
| `authoritative` / `analytical`         | Cover bg = `image-generated`; body remains data-forward                    | Cover **and** closing bg ∈ {`image-generated`, `gradient`}; body data-forward              | None required                | No imagery required      |
| `instructional-rich`                   | Diagram-led body; cover/closing may use `image-generated`                  | Cover **or** closing bg ∈ {`image-generated`, `gradient`}                                  | None required                | No imagery required      |
| **Dividers** (any register)            | All = `image-generated`                                                    | All ∈ {`image-generated`, `motif-shape`}                                                   | `motif-shape` acceptable     | `motif-shape` or `solid` |

**`designAmbition: restrained` override:** caps bookend imagery at
one slide (cover OR closing, not both). Body-slide quotas drop one tier.

---

## Structural-slide imagery uplift

For `technical-instructional`, `data-analytical`, and `general`
domain decks at `medium` demand — body slides yield imagery to
diagrams/charts, but structural slides (cover/closing/dividers)
become the deck's aesthetic moments.

**Trigger conditions** (all must hold):
- `imageryDemand` ∈ {`low`, `medium`}
- `contentDomain` ∈ {`technical-instructional`, `data-analytical`, `general`}
- `formalityLevel` ≠ `regulatory`
- `imageryHint` ≠ `avoid-imagery`

**At `medium` (required):**
- Cover AND closing: bg ∈ {`image-generated`, `gradient`}
- Every recap: bg = `image-generated` (abstract/geometric)
- ≥ 1 divider: bg = `image-generated` (abstract/geometric)
- Every agenda: ≥ 1 motif-derived `shape` zone

**At `low` (recommended, validator warns):**
- Cover or closing: bg ∈ {`image-generated`, `gradient`}
- Dividers/recap may use `image-generated` when ≥ 3 such slides

**Simplicity constraints** (when uplift is taken):
- `imageRequest.prompt` MUST contain ≥ 1 constraint keyword:
  `abstract`, `geometric`, `grid`, `mesh`, `topographic`, `circuit`,
  `schematic`, `isometric pattern`, `gradient`, `monochrome`,
  `wireframe`, `contour`, `low-poly`, `noise field`, `dot matrix`,
  `line art`, `blueprint`.
- `negative_prompt` MUST contain: `no people, no logos, no scenes,
  no text, no realistic objects, no faces, no recognizable brands`.

---

## Accent imagery (permissive allowance, any register/demand)

Every deck may carry up to **two** small decorative `imageRole:
"accent"` zones for visual texture without committing to full
imagery. This is a **permission**, not a quota.

Constraints (enforced by validator):
- Area ≤ 30% of canvas.
- Must NOT overlap title/headline zones.
- Prompt MUST contain: `abstract`, `texture`, `wash`, `gradient`,
  `motif`, `organic`, `pattern`, `non-representational`, or
  `color field`.
- Negative-prompt: `no people, no logos, no text, no recognizable objects`.
