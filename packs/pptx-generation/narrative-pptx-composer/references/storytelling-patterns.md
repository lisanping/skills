# Storytelling Patterns — Reference Catalog

A vocabulary of named narrative structures and an anti-pattern
checklist. Consult this when designing `storytellingPattern` in
Step 3 (Narrative Architecture).

**This is a vocabulary, not a template library.** Select, combine,
or design a pattern that serves the audience and `coreArgument`.
Record your rationale in `s03-presentation-blueprint.json →
architecture.storytellingPattern.rationale` — reference the content
and audience signals that drove the choice, not this document.

---

## Anti-Patterns (read first)

These failure modes are the **primary value** of this reference.
Any pattern you choose must avoid all of them.

| Anti-pattern                   | Why it fails                                                                                                                                                                                                      |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Data dump**                  | Presenting all available data without a narrative thread. Audience retains nothing.                                                                                                                               |
| **Solution before problem**    | Jumping to recommendations without establishing why they're needed. Audience doesn't buy in.                                                                                                                      |
| **Symmetric sections**         | Equal slide count per section regardless of importance. Dilutes the climax.                                                                                                                                       |
| **Buried lead**                | Key insight arrives on slide 8 of 12. Executives check out after slide 4.                                                                                                                                         |
| **Thank-you closing**          | Ending with "Thank you" / "Questions?" instead of the single most important takeaway or a specific ask. Wastes the last impression.                                                                               |
| **Terminology drift**          | Different terms for the same concept across slides. Signals careless thinking.                                                                                                                                    |
| **Orphan transitions**         | Slides that don't logically connect to their neighbors. Breaks narrative flow.                                                                                                                                    |
| **Consulting cliché openings** | Rhetorical formulas like *"[Result] wasn't luck — it was proof."* Authentic voice beats template voice.                                                                                                           |
| **Forced pattern fit**         | Contorting content to match a named pattern when the content doesn't naturally suit it. Invent or hybridize instead.                                                                                              |
| **Flat emotional arc**         | Every act at the same intensity (all `tension` or all `calm`). Downstream visual rhythm has no basis for contrast — the deck looks monotone.                                                                      |
| **Role monotony**              | Three or more consecutive slides sharing the same `narrativeRole` (e.g. `evidence`, `evidence`, `evidence`). Starves the layout selector of variety signals. Intersperse with `analysis`, `pivot`, or `callback`. |
| **Uniform density**            | All acts at the same information density. Prevents the whitespace/density alternation that makes a deck breathe. At least one act should be markedly lighter or heavier than the rest.                            |

---

## How to Design a Pattern

The `storytellingPattern` you record is a shape that serves this
specific content and audience. **Default to designing a pattern
that mirrors the content's natural shape.** Reuse a named pattern
only when the content clearly fits one — not as a shortcut.

1. **Design a new pattern** by deriving acts directly from the
   content's natural shape. This is the default path — start here.
2. **Reuse a named pattern** from the seed vocabulary below, but
   only when the content genuinely and obviously fits. If you must
   bend the content to match, you are on the wrong path.
3. **Compose or nest** two patterns (named or designed) when one
   shape covers the macro flow and another covers a recurring
   micro flow.

### When to reuse instead of designing

Design is the default. Reuse only when **both** columns check out:

| Signal                                                                                                                    | Reuse justified | Stay with design |
| ------------------------------------------------------------------------------------------------------------------------- | --------------- | ---------------- |
| Content resembles a common scenario (quarterly review, pitch, proposal, technical survey)                                 | ✅               |                  |
| Audience is familiar with a known structure (e.g. McKinsey SCR for advisory boards)                                       | ✅               |                  |
| A named pattern fits without bending or padding the content                                                               | ✅               |                  |
| Reusing would force you to bend the content (anti-pattern: *forced pattern fit*)                                          |                 | ✅                |
| Content has an unusual shape: paradox, historical arc, cultural ritual, multi-threaded investigation, recursive structure |                 | ✅                |
| The `coreArgument` cannot be expressed in 3–4 named acts from any vocabulary entry                                        |                 | ✅                |

### Naming a new pattern

When you design, give the pattern a descriptive hyphenated
identifier (e.g. `paradox-unpacking`, `lineage-to-present`,
`two-threads-converge`, `question-cascade`, `ritual-then-rupture`).
Record the full act structure under
`s03-presentation-blueprint.json → architecture.storytellingPattern`:

```json
{
  "name": "lineage-to-present",
  "origin": "designed",
  "acts": [
    { "name": "Bottleneck", "goal": "...", "emotionalArc": "..." },
    { "name": "Breakthrough", "goal": "...", "emotionalArc": "..." },
    { "name": "Family", "goal": "...", "emotionalArc": "..." },
    { "name": "Present-day reuse", "goal": "...", "emotionalArc": "..." }
  ],
  "rationale": "..."
}
```

`origin` is one of: `reused`, `composed`, `nested`, `designed`.
Every pattern — named or designed — must produce the same
`rationale` quality described at the end of this document.

---

## Seed Vocabulary

Starting points, not an option list. Audience fit is the primary
selection criterion — purpose alone is insufficient.

**`emotionalArc` is required for every act** (whether reusing a
seed or designing new). Use one of: `tension`, `release`, `build`,
`calm`, `surprise`, `resolve`. This drives Step 5b's `rhythmArc`
and ensures the visual rhythm has narrative backing. If every act
gets the same arc, you are hitting the *Flat emotional arc*
anti-pattern.

### Decision-driving patterns

| Pattern name                        | Essence                                                                  | Best audience                                                   |
| ----------------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------- |
| `evidence-opportunity-ask`          | Prove the track record → show what it unlocks → make a bounded request   | Budget holders, executives                                      |
| `situation-complication-resolution` | Shared baseline → what changed or what's at risk → path forward          | Advisory boards, cross-functional leadership (McKinsey default) |
| `problem-evidence-solution-impact`  | Scope the problem → prove it's real → present the fix → quantify outcome | Engineering leads, research committees                          |
| `before-after-transformation`       | Vivid starting state → what was done → measurably better state           | Board updates, retrospectives, change management                |

### Reporting patterns

| Pattern name                           | Essence                                                                    | Best audience                        |
| -------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------ |
| `context-performance-strategy-roadmap` | External frame → results vs. targets → strategic choices → next milestones | Quarterly reviews, investor updates  |
| `what-so-what-now-what`                | Facts → interpretation → recommendation                                    | Short (5–10 min) executive briefings |

### Inform / teach patterns

| Pattern name                               | Essence                                                                                                          | Best audience                           |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `context-deepdive-takeaways`               | Why this matters → the mechanism → what to remember                                                              | Internal training, domain overviews     |
| `problem-breakthrough-family-applications` | The bottleneck that forced invention → the breakthrough concept → the variants in its family → downstream reuses | Technical surveys, lineage explanations |
| `question-mechanism-implication`           | Anchor on a question the audience has → derive the answer → apply it                                             | Tutorials, conceptual teach-backs       |

### Inspire patterns

| Pattern name                  | Essence                                                                   | Best audience                        |
| ----------------------------- | ------------------------------------------------------------------------- | ------------------------------------ |
| `vision-proof-call-to-action` | Desirable future → evidence it's reachable → the audience's specific role | All-hands, partner pitches, keynotes |

### Examples of designed (non-vocabulary) patterns

These are illustrations, not options — they exist to show the
*shape* of legitimate custom designs:

| Pattern name           | Essence                                                             | When to design something like this                           |
| ---------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------ |
| `paradox-unpacking`    | State an apparent contradiction → reveal hidden mechanism → resolve | Content whose insight is counter-intuitive                   |
| `two-threads-converge` | Follow two parallel threads → show their intersection               | Content with two independent lines that unify                |
| `ritual-then-rupture`  | Establish the steady state → show the moment it broke               | Crisis retrospectives, disruption narratives                 |
| `recursive-zoom`       | Same pattern at macro → meso → micro scale                          | Fractal topics (systems, org structure, architecture layers) |

---

## Composition & Nesting

Named or designed, patterns can combine:

- **Sequential composition.** Use one pattern for the first half,
  another for the second. E.g., `situation-complication-resolution`
  for framing, then `vision-proof-call-to-action` for closing.
- **Macro + micro nesting.** Overall pattern covers the deck; a
  micro pattern structures each body slide or each evidence block.
- **Parallel threads.** Two patterns run in alternation when the
  content naturally has two strands.

When composing or nesting, record both patterns' names and the
`transitionStrategy` that handles the handoff between them.

---

## Extra signals to stay with design (resist reuse temptation)

Since design is the default, these are *reinforcing* signals — if
any apply, you are right to stay with a designed pattern:

- The content's natural shape has more than one climax.
- The content doesn't have a problem/solution structure at all
  (e.g., a concept explanation, a historical arc, a taxonomy).
- The audience's prior knowledge requires starting from an
  unusual place (a question, a paradox, a present-day artifact
  whose origin you'll unpack).
- Reusing forces you to generate filler acts ("we need a
  `setup` act because the pattern has one, but the content has
  no setup to do").

---

## What rationale looks like (and doesn't)

Applies equally to reused, composed, and designed patterns.

**Weak rationale (references this document):**

> "Selected `problem-evidence-solution-impact` because the table
> maps `propose` to this pattern."

**Strong rationale (references content and audience):**

> "Designed `lineage-to-present` because the audience reads
> Transformer papers but does not know attention predates
> Transformers. The core argument — attention is one idea with
> many specializations — requires a pattern that first motivates
> invention (seq2seq bottleneck), then isolates the breakthrough
> (self-attention in Transformer), and finally surveys the family
> so each variant is seen as a specialization rather than a
> separate concept. No decision- or report-pattern fits because
> the deck has no decision to drive; `context-deepdive-takeaways`
> is too flat for a story with a clear climax (Transformer);
> `problem-breakthrough-family-applications` is closest but
> conflates climax and family exposition — splitting them gives
> Transformer its own act."

The second explains *why*. The first merely cites a lookup.
