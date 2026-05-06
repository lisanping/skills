# Step 2 — Communication Brief

Full procedural detail for Step 2. See [SKILL.md](../SKILL.md)
for the mandatory rules summary.

---

## Scope

Step 2 produces `s02-communication-brief.json` for **every** session,
regardless of input modality (documents, chat brief, image input) or
deck size. Its sole job is to decide **what to communicate and to
whom** — purpose, audience, communication objectives, and key
messages. Step 2 is pure messaging strategy; no design decisions
and no quantity arbitration happen here.

**Out of scope (handled elsewhere):**

- `slideCountConstraint` — extracted in s01b, arbitrated in Step 3c.
  Step 2 does not consume or copy this field.
- `imageryDemand` — derived in Step 3a once `contentDomain` is
  resolved. Step 2 does not consume or set this field. The user's
  stated imagery preference is already captured in
  `s01b.aestheticSignals.imageryHint`.

---

## Thin-brief adaptation

Step 2's output thickness scales with the richness of the upstream
signals. The schema is the same; what varies is how many fields are
filled with high-confidence concrete values vs. low-confidence
inferences.

| Input richness | Typical inputs                                                                    | Brief thickness                                                                                        | Inference behavior                                                           |
| -------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| **Rich**       | Multi-page documents + explicit purpose / audience / formality in chat            | Full brief: 3–5 key messages, concrete audience profile, all `communicationObjectives` fields concrete | `inferences` mostly empty                                                    |
| **Medium**     | Topic-only chat brief + some hint of audience or purpose                          | 2–3 key messages, audience inferred from topic domain, objectives plausible-default                    | 2–4 fields land in `inferences` with `confidence: medium`                    |
| **Thin**       | Single sentence ("make me a deck about X") or image-only input with no text query | ≥ 1 key message, single most plausible audience, single most plausible purpose                         | Most non-`topic` fields land in `inferences` with `confidence: low`–`medium` |

**Thin briefs do not fail validation.** Every required schema field
is populated; the validator does not inspect confidence levels. The
`confidence` field exists so downstream Step 3 (and the Step 9 retro)
can see which choices were guesses.

**Authoring a thin brief — discipline rules:**

- **Never block to ask the user.** Make the most plausible inference
  and log it. The retro will surface miscalls if any.
- **Pick decisions that grant design freedom.** When choosing between
  `inform` / `report` / `propose` from a sparse signal, prefer
  `inform` (more design latitude than `report`, less commitment than
  `propose`).
- **Audience inference defaults by topic domain.** Technical topic →
  practitioner audience; business topic → manager / cross-functional;
  cultural / educational topic → general or student. Record the
  inference basis in `inferences[].basis`.
- **Key messages — quality over quantity.** Thin briefs may carry as
  few as 1 (e.g. *what the thing is*); add a second only when you
  can defend a distinct second message (*why it matters*). Don't pad.
- **`confidence` is honest.** A `low`-confidence audience guess on
  a one-line brief is a more useful signal to Step 3 / Step 9 than
  a falsely confident one. Use `low` whenever the inference rests
  on topic alone.

---

## Procedure

Inputs: user request + `s01b-query-intent.json` + `s01c-content-digest.json` (always exists, including image-derived synthetic sections when 1c-image ran).
Output: `s02-communication-brief.json`.

Consume `s01b-query-intent.json` first: copy `explicitSignals` directly
into the matching brief fields (audience, purpose, formality, language).
Read `s01b.aestheticSignals` and `s01b.inferences` for context only —
those recorded inferences cover topic and aesthetic signals, not
audience/purpose. **Step 2 is the sole authority for audience and
purpose inference**; all inference for unspecified audience/purpose
fields happens here. Never block to ask the user — make the most
plausible open inference and record it with `confidence`.

The procedure is a single-pass field-fill, not a sequence of phases.
Follow the field map below; field order is irrelevant.

**Field map** (single source of truth — must match
[../schemas/s02-communication-brief.example.json](../schemas/s02-communication-brief.example.json)
and `scripts/s02_validate_brief.py`):

| Field                                                  | Required                                                          | Notes                                                                                                                                 |
| ------------------------------------------------------ | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `presentationPurpose` (enum)                           | yes                                                               | One of `inform` / `persuade` / `report` / `propose` / `inspire`                                                                       |
| `purposeStatement` (one-sentence)                      | yes                                                               | Names the audience and the desired change in concrete terms                                                                           |
| `audience.who`                                         | yes                                                               | Concrete (possibly inferred) description of the viewer                                                                                |
| `audience.{priorKnowledge, concerns, role}`            | best-effort                                                       | Fill when known/inferable; otherwise omit                                                                                             |
| `audience.decisionPower`                               | required when `presentationPurpose` ∈ {persuade, propose, report} | Authority/scope to act on the ask                                                                                                     |
| `communicationObjectives.{think, feel, do}`            | yes (all three)                                                   | What the audience should think / feel / do after the presentation. Drives all downstream content decisions.                           |
| `keyMessages[].{rank, message, evidence}`              | ≥ 1                                                               | 1–5 ranked messages, each annotated with `document` / `generated` / `hybrid`. Thin briefs may carry only 1.                           |
| `constraints.{language, formalityLevel, timeMinutes?}` | yes (`language` and `formalityLevel`)                             | `slideCountConstraint` is **forbidden** here — it lives on `s01b.explicitSignals` and is consumed by Step 3c. `timeMinutes` optional. |
| `inferences[].{field, value, basis, confidence}`       | required when any field is inferred                               | Same shape as `s01b.inferences`                                                                                                       |

Write `s02-communication-brief.json`
(see [../schemas/s02-communication-brief.example.json](../schemas/s02-communication-brief.example.json)
for a rich-input deck and
[../schemas/s02-communication-brief.thin-example.json](../schemas/s02-communication-brief.thin-example.json)
for a single-sentence brief).

**When no content documents exist (brief-only mode) or only image
input was provided:** Infer **all unsupported fields** (purpose,
audience, objectives, formality, etc.) from the user's chat message
+ `s01b-query-intent.json` + image-derived synthetic sections in
`s01c-content-digest.json`. `keyMessages` evidence is `generated`
for entries with no document basis; `hybrid` when partly grounded
in image-derived content. Bias toward audience profiles that match
the topic domain (technical topic → engineer/practitioner audience),
and toward communication objectives that grant more design freedom
(`inform`/`inspire` over `report`/`propose` when ambiguous). Record
every inferred field in `inferences` (same field name and shape as
`s01b-query-intent.json → inferences`):

```json
"inferences": [
  { "field": "audience.role", "value": "engineer", "basis": "topic is technical", "confidence": "medium" }
]
```

**Checkpoint:** `s02-communication-brief.json` exists;
`presentationPurpose` is one of {inform, persuade, report, propose,
inspire}; `purposeStatement` is a non-empty sentence;
`communicationObjectives` has concrete entries for all three
dimensions (think/feel/do); `keyMessages` has at least 1 entry
(thin briefs) and each is traceable to its evidence source.
