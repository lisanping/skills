# Step 3 — Narrative Blueprint

Full procedural detail for Step 3. See [SKILL.md](../SKILL.md)
for the mandatory rules summary.

This step merges narrative architecture (3a/3b) and per-slide
blueprint (3c) into a single pass. Pure LLM reasoning — **no
design knowledge consulted**.

---

## Inputs

- `s01b-query-intent.json` (consumed for `explicitSignals.slideCountConstraint`
  in slide-count arbitration and `aestheticSignals.imageryHint` for
  illustration-intent decisions)
- `s02-communication-brief.json`
- `s01c-content-digest.json`

## Output

`s03-presentation-blueprint.json` — with embedded `architecture` field.

---

## Phase 3a — Narrative Architecture

Consult [storytelling-patterns.md](storytelling-patterns.md) as
vocabulary and anti-pattern checklist. Six sub-tasks in one pass:

1. **Core argument** — single overarching claim connecting every
   slide. Anchor on `s02.keyMessages[rank=1]` and sharpen into a
   falsifiable sentence. If departing from rank-1, log in
   `architecture.inferences[]`.

2. **Pattern & acts** — choose storytelling pattern AND lay out
   acts in one decision. Record `storytellingPattern.{name, origin,
   rationale}` (`origin` ∈ `reused` | `composed` | `nested` |
   `designed`). Divide into acts under `actStructure[]`, each
   with `goal`, `emotionalArc`, `sections`, `informationDensity`.
   Determine act count from: number of `s02.keyMessages`, number of
   distinct topic clusters in `s01c` sections, natural boundary
   points in the chosen storytelling pattern, and audience
   complexity tolerance (`s02.audience.priorKnowledge`).

3. **Inter-act handoff strategy** — how adjacent acts connect:
   `progressive-disclosure` | `contrast` | `callback` | `parallel`.

4. **Opening hook & closing anchor** —
   - `openingHook` = verbal articulation of cover slide's
     engagement framing. Must align with cover's `headlineMessage`.
   - `closingAnchor` = closing slide's takeaway. Must match the
     closing slide's `headlineMessage`.

5. **Information hierarchy** — triage content into:
   - `essential` — must appear.
   - `supporting` — include if space allows.
   - `cut` — exclude; each entry requires `reason`.

6. **Content domain & imagery demand** —
   - `contentDomain` ∈ {`technical-instructional`,
     `data-analytical`, `creative-portfolio`, `general`} — detect
     per [visual-tone-register.md § Dimension 1](visual-tone-register.md).
   - `imageryDemand` ∈ {`high`, `medium`, `low`, `none`} — apply
     the cascade below using `s01b.aestheticSignals` +
     `s02.constraints` + domain.
   - Both are the **single source of truth** for all downstream
     consumers. Step 5 may not re-derive or override them.

   #### Imagery Demand cascade

   **Designer bias — when in doubt, lean visual.** Visually rich
   decks communicate more effectively — background images and
   illustrations carry most of the deck's "design feel". The cascade is intentionally
   asymmetric: hard suppressors (`none`/`low`) are always honored;
   the soft uplift to `high` triggers liberally.

   Apply the cascade — **first match wins** — and write the result
   to `s03-presentation-blueprint.json → architecture.imageryDemand`.
   Step 5b copies it into `s05b-style-policy.json →
   visualTone.imageryDemand`; both locations carry the same value.

   | Priority | Trigger                                                                                                                                                    | `imageryDemand` |
   | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
   | 1        | User explicitly suppresses imagery (e.g. "no images", "text-only"), or context is regulatory / compliance / audit / legal                                  | `none`          |
   | 2        | User explicitly favors imagery, domain is `creative-portfolio`, or mood is cinematic / editorial / atmospheric / immersive                                 | `high`          |
   | 3        | Internal formal report (not already matched by row 1)                                                                                                      | `low`           |
   | 4        | **Soft uplift** — topic involves concrete visual subjects (people, places, objects), sensory or emotive language, or narrative "show don't tell" character | `high`          |
   | 5        | Default — none of the above triggered                                                                                                                      | `medium`        |

   When the result is `medium` by default (row 5), record
   `imageryDemandRationale` with `confidence: "low"`,
   `basis: "insufficient signals"`. When it is `high` via
   soft uplift (row 4), record `confidence: "medium"`,
   `basis: "soft uplift — visually expressive topic"`.

---

## Phase 3b — Structural Scaffolding

Decide which structural (non-body)
   slides the deck needs. These are narrative-level decisions that
   depend on audience, purpose, and deck complexity — not
   design choices. Phase 3c implements them; Step 5 styles them.

   | Structural element    | Include when                                                                                                                                                                        |
   | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | **Cover**             | Always (mandatory)                                                                                                                                                                  |
   | **Closing**           | Always (mandatory)                                                                                                                                                                  |
   | **Executive summary** | Audience is executive/time-constrained; purpose is `report`, `propose`, or `persuade`; deck has enough body slides that a reader would benefit from conclusion-first framing        |
   | **Agenda**            | Multiple acts with distinct topics; audience is unfamiliar with scope; deck is complex enough that a roadmap aids navigation                                                        |
   | **Section dividers**  | Each act has enough body slides to justify a structural marker AND total dividers do not dominate the deck (avoid over-scaffolding) AND act boundaries are significant topic shifts |
   | **Mid-deck recap**    | Long deck with complex multi-thread argument; audience fatigue risk is high based on `informationDensity` distribution and `audience.priorKnowledge`                                |
   | **Appendix**          | Purpose is `propose` or `report`; detailed backup data exists that executives might ask about in Q&A; regulatory/compliance context                                                 |

   Default to `false` when the Include condition isn't met.
   Section dividers are all-or-nothing: if any gate fails,
   restructure (merge thin acts) rather than ship asymmetric
   dividers.

   Record the decision as `architecture.structuralScaffold` in
   `s03-presentation-blueprint.json`:

   ```json
   "structuralScaffold": {
     "executiveSummary": false,
     "agenda": true,
     "sectionDividers": true,
     "midDeckRecap": false,
     "appendix": false,
     "rationale": "3-act technical explainer for familiar audience; agenda helps navigate 6 sections but exec summary would spoil the build-up narrative; no backup data warrants an appendix"
   }
   ```

   **Rules:**
   - **Divider symmetry (mandatory):** when `sectionDividers` is
     true, **every** act gets a leading divider — including Act 1
     (placed after cover/agenda, before Act 1’s first body slide).
     Asymmetric dividers (some acts have them, others don’t) make
     the deck feel structurally incomplete.
   - Executive summary and opening hook are **mutually exclusive
     strategies** — if you include an exec summary, the hook is
     already the summary itself (conclusion-first). Don't also add
     a dramatic hook slide.
   - Agenda and executive summary can coexist (exec summary = what,
     agenda = how we'll get there), but for short decks, pick
     at most one to avoid scaffolding overhead.
   - Appendix slides are **not counted** in `totalSlides` for the
     main deck. They live after the closing slide and are excluded
     from narrative role sequencing and visual rhythm calculations.

Write the `architecture` block of `s03-presentation-blueprint.json`.
Then proceed to Phase 3c.

---

## Phase 3c — Per-Slide Blueprint

Translate the narrative architecture into per-slide messaging design.
Define what each slide communicates (headline, supporting points,
narrative role, visual intent, transitions, density).

**Per-slide execution order (mandatory).** For each slide, run the
three sub-decisions sequentially — later steps consume earlier ones:

1. **Fill the per-slide field table** below (slideId, headline,
   supportingPoints, narrativeRole, slideType, narrativeIntent,
   transitions, density, contentSource, sourceRef, title).
2. **Decide `mediaAttachments`** — review `s01c.mediaAssets` against
   this slide's headline / supportingPoints (criteria in § Media
   Attachment Decision). Depends on (1)'s headlineMessage and
   sourceRef.
3. **Decide `illustrationIntent`** — run the 7-step decision flow
   (§ Illustration Intent Decision). Step 1 of that flow reads (2)'s
   result; later steps read (1)'s narrativeIntent / informationDensity /
   narrativeRole.

For each slide, define:

| Field                | Purpose                                                                                                                                                                                                                                                                                                                                                                                                           |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `slideId`            | Unique identifier (s01, s02, ...)                                                                                                                                                                                                                                                                                                                                                                                 |
| `title`              | Working title                                                                                                                                                                                                                                                                                                                                                                                                     |
| `headlineMessage`    | The one thing the audience should take away from this slide (the "so what"). May be null for structural slides — cover, divider, agenda, executive-summary, recap, appendix                                                                                                                                                                                                                                       |
| `supportingPoints`   | Evidence, data, examples that prove the headline. Each traceable to source                                                                                                                                                                                                                                                                                                                                        |
| `narrativeRole`      | Function in the story (see glossary below)                                                                                                                                                                                                                                                                                                                                                                        |
| `slideType`          | Physical/structural type: `cover`, `executive-summary`, `agenda`, `divider`, `content_text`, `content_data`, `content_mixed`, `recap`, `closing`, `appendix`. Drives Step 5 layout pattern selection and the no-headline-required exemption. Distinct from `narrativeRole` (story function).                                                                                                                      |
| `narrativeIntent`    | Narrative-level delivery mode — paired with `narrativeRole`: role = function in story, intent = mode of delivery. One of: `title-card`, `text-narrative`, `data-visualization`, `comparison`, `process`, `timeline`, `matrix`, `metaphor`, `stat-callout`, `quote`, `full-bleed-image`, `architecture`, `system`, `code-walkthrough`, `data-flow`. Step 4c maps to `contentForm`; Step 5d picks the final layout. |
| `transitionIn`       | How this slide connects FROM the previous                                                                                                                                                                                                                                                                                                                                                                         |
| `transitionOut`      | How this slide leads TO the next                                                                                                                                                                                                                                                                                                                                                                                  |
| `informationDensity` | `minimal`, `light`, `medium`, `dense`                                                                                                                                                                                                                                                                                                                                                                             |
| `contentSource`      | `document`, `generated`, `hybrid`                                                                                                                                                                                                                                                                                                                                                                                 |
| `sourceRef`          | `"<filename>#<heading>"` or `null`                                                                                                                                                                                                                                                                                                                                                                                |
| `mediaAttachments`   | Array of media assets from `s01c-content-digest.json → mediaAssets` to include on this slide (see below). Null or empty when no media is used                                                                                                                                                                                                                                                                     |

### Batching (large decks)

Phases 3a/3b always run once (single pass). Only Phase 3c
(per-slide blueprint) may be batched.

**When to batch:** default to single-pass. Only split when the
per-slide output would truncate or quality visibly degrades. Do
not pre-emptively batch based on slide count alone — estimate
total output volume before starting.

**How to split:** along act boundaries — one batch per act (plus
its divider). Cover → first batch; closing → last batch. If one
act is still too large, split at a sub-topic boundary.

**Context:** each batch receives the full upstream artifacts
(`s01b`, `s01c`, `s02`, and the `architecture` block from
3a/3b) as read-only shared context. Carry only minimal
continuity from prior batches — prior slide headlines and
`transitionOut` of the last slide — not the entire prior-batch
output.

**Post-merge:** concatenate all batches, then verify:
- Transition coherence at act boundaries (`transitionIn` /
  `transitionOut` align across batch seams).
- Cover and closing slides exist exactly once.
- Divider symmetry (if enabled, every act has one).
- Floor satisfaction pass runs over the merged result.

### Media Attachment Decision (per slide)

For each slide, review `s01c-content-digest.json → mediaAssets` and
decide whether any media asset should appear on the slide.

**Decision criteria:**
- The media must be **directly relevant** to the slide's
  `headlineMessage` or `supportingPoints`.
- Prefer images/diagrams that **illustrate a key concept** the
  slide is explaining — they add visual evidence.
- A figure referenced in the same source section as the slide's
  `sourceRef` is a strong candidate.
- Do **not** attach media that is purely decorative, redundant
  with on-slide text, or from an unrelated section.
- Each media asset should appear on **at most one slide** (no
  reuse). If two slides could use the same figure, assign it to
  the slide where it is most central.

**`mediaAttachments` entry schema:**
```json
{
  "ref": "images/fig03-coding-harness-layers.png",
  "type": "image",
  "alt": "Three layers of a coding harness",
  "placement": "primary-visual",
  "rationale": "Figure directly illustrates the three-layer architecture described in this slide's headline"
}
```

`placement` values: `primary-visual` (dominant visual element),
`supporting-visual` (secondary, placed alongside text),
`background` (full-bleed or faded behind text).

### Illustration Intent Decision (per slide)

After `mediaAttachments`, decide whether the slide needs **generated
illustrations** — images that don't exist in the content documents
but would strengthen the slide's communication.

**Decision flow (evaluate in order):**

1. Does the slide already have `mediaAttachments` with
   `placement: "primary-visual"` or `"supporting-visual"`?
   → **No generation needed.** User-provided media always takes
   priority.
2. Is `narrativeIntent` ∈ {`data-visualization`, `code-walkthrough`,
   `stat-callout`}? → **Skip.** Charts, code, and numbers
   communicate better than illustrations.
3. Does the `headlineMessage` describe something **inherently
   visual** (a physical object, spatial arrangement, artistic
   style, scenic setting, contrast between visible things)?
   → **Likely needed** — text alone cannot convey visual concepts.
4. Is `s01b.aestheticSignals.imageryHint == "favor-imagery"` (or
   the topic is visually expressive)? OR is
   `architecture.imageryDemand` (resolved in 3a sub-task 6) ==
   `"high"`? → **Lean toward needed** when the slide can plausibly
   support a meaningful illustration. Step 3 is responsible for
   making the per-slide selection that satisfies the Imagery Floor
   minimum; see the floor-satisfaction step below.
5. Is `narrativeRole` ∈ {`evidence`, `climax`, `pivot`} and the
   content includes a concrete subject that can be visualized
   (not an abstract argument)? → **Consider.**
6. Is `narrativeIntent` ∈ {`full-bleed-image`, `metaphor`} and no
   media is attached? → **Needed** — these intents presuppose
   visual content.

When the decision is positive, add an `illustrationIntent` to the
slide entry:

```json
{
  "slideId": "s06",
  "headlineMessage": "Northern boldness vs Southern subtlety defined two aesthetic traditions",
  "narrativeIntent": "comparison",
  "mediaAttachments": [],
  "illustrationIntent": {
    "needed": true,
    "subject": "Visual contrast between Northern school's bold axe-cut brushstrokes and Southern school's soft hemp-fiber texture",
    "narrativePurpose": "The aesthetic divergence is inherently visual — text cannot convey the difference between two brushwork styles",
    "placement": "primary-visual",
    "imageCount": 2,
    "perImageSubject": [
      "Close-up of bold angular axe-cut strokes on a rocky cliff face, ink on rice paper",
      "Close-up of soft flowing hemp-fiber strokes on rolling hills, ink on rice paper"
    ]
  }
}
```

**`illustrationIntent` field reference:**

| Field              | Type        | Description                                                                                                                                                                                                               |
| ------------------ | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `needed`           | bool        | Whether this slide needs generated illustrations                                                                                                                                                                          |
| `subject`          | string      | Conceptual description of what the illustration(s) should depict (narrative level, not a generation prompt)                                                                                                               |
| `narrativePurpose` | string      | Why this slide needs illustration — must be a communication argument, not "for visual interest"                                                                                                                           |
| `placement`        | enum        | Same enum as `mediaAttachments.placement`: `primary-visual` (illustration dominates), `supporting-visual` (text dominates, illustration alongside), `background` (mood/texture/full-bleed atmosphere — not informational) |
| `imageCount`       | int         | Number of distinct images on this slide (1–6).                                                                                                                                                                            |
| `perImageSubject`  | array\|null | When `imageCount > 1`, per-image subject descriptions; length must equal `imageCount`. Null when `imageCount == 1` (use `subject`).                                                                                       |

### Floor satisfaction (mandatory final pass)

After per-slide decisions, review the overall illustration
allocation against `architecture.imageryDemand`:
- `high` → most body slides with visualizable content should have
  `illustrationIntent.needed: true`. If too few, add entries to
  candidate slides (prefer `evidence`/`climax`/`pivot` with
  concrete visual subjects).
- `medium` → a meaningful proportion of body slides should have
  illustrations. Fill gaps on slides whose headline describes
  something inherently visual.
- `low`/`none` → remove entries whose subject is too abstract to
  produce a meaningful illustration.

## Narrative Role Glossary

`narrativeRole` = function in the story. `slideType` = physical
type. The two are independent.

| Role         | Meaning                                     |
| ------------ | ------------------------------------------- |
| `opening`    | Establishes context (cover)                 |
| `setup`      | Context for the argument that follows       |
| `evidence`   | Data/proof supporting the core argument     |
| `analysis`   | Interpretation of evidence                  |
| `pivot`      | Shift from retrospective to forward-looking |
| `climax`     | Key ask or most important insight           |
| `resolution` | Next steps and call to action (closing)     |
| `callback`   | References earlier content for coherence    |

## Slide count determination

Slide count is **bottom-up** in Phase 3c — the sole arbitration
point. Source: `s01b.explicitSignals.slideCountConstraint`.

1. Lay out all slides per narrative architecture.
2. Set `totalSlides` = actual count.
3. If constraint exists:
   - `exact` → merge/split to hit number.
   - `range` → clamp to `[min, max]`.
   - `duration` → convert via 1.0–2.5 min/slide, then clamp.
4. Sanity checks:
   - `totalSlides < keyMessages + 2` → merge or prioritize.
   - `totalSlides > 30` → likely needs splitting.
   - **Breathing-slide cadence:** every 6–8 consecutive body
     slides must contain ≥1 with `informationDensity: "minimal"`
     and ≤25 words supporting content. Insert in Phase 3c if
     missing — Step 5 must not insert breathing slides.

---

## Output

Write `s03-presentation-blueprint.json`
(schema: [../schemas/s03-presentation-blueprint.schema.json](../schemas/s03-presentation-blueprint.schema.json),
example: [../schemas/s03-presentation-blueprint.example.json](../schemas/s03-presentation-blueprint.example.json)).

The file must include an `architecture` top-level field containing
all narrative decisions from Phases 3a/3b.

**Final Checkpoint:**

```bash
python $COMPOSER_SKILL/scripts/s03_validate_blueprint.py "$SESSION"
```
