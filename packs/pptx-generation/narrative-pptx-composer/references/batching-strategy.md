# Large Deck Batching Strategy

Each step owns its batching decision. This document provides
rules, not thresholds.

---

## Rules

- Default to single-pass. Only split when output would truncate
  or quality visibly degrades.
- Do not pre-emptively batch based on slide count alone.
- Each step estimates its own total output volume before starting.
  If it exceeds one coherent response, split.
- Split along **act boundaries** — one batch per act (plus its
  divider). Cover → first batch; closing → last batch. If one
  act is still too large, split at a sub-topic boundary.
- Each batch receives the step's normal upstream artifacts
  (read-only, shared across batches).
- Carry only the minimal continuity context the step needs from
  prior batches (e.g., prior headlines, prior layout patterns).
  Do not replay entire prior-batch outputs. If the step has no
  cross-slide dependency, carry nothing.
- Run parallel subagents only when batches have no inter-batch
  dependency. Otherwise execute sequentially.
- After all batches: concatenate → run the same validator as
  single-pass → scan batch boundaries for narrative breaks →
  fix with minimal edits at boundary slides.
- For code output (build scripts): produce header and footer
  once (not batched); batch only per-act functions. Each batch
  receives the header's function signatures. Validate by running
  the merged script.

## Terminology

- `s04a-terminology-registry.json` is shared across all Step 4
  batches. Body text and the verbatim-copied `headlineMessage`
  must use the same canonical form within each slide.
- If a rejected variant appears in a headline from Step 3:
  accept the headline's wording or return to Step 3 — do not
  rewrite `s03-presentation-blueprint.json` from Step 4.
- `s06_validate_content.py` fails if any rejected variant
  survives in the final artifact.
