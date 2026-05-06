# Step 9 — Session Retrospective

Runs after delivery (Step 8g). Output: `s09-session-retrospective.json`.

---

## 9a — Collect Evidence

Sweep session artifacts + conversation history. Five categories:

1. **Workflow** — skipped/rerun steps, bypassed validators,
   artifact handoff friction.
2. **Content & narrative** — inference accuracy, pattern fit,
   slide merges/splits, headline survival, terminology catches.
3. **Design & layout** — geometric violations, register fit,
   python-pptx errors (unit confusion, RGBColor, font fallbacks,
   image paths, z-order), image generation success rate.
4. **QA & fix** — round counts, severity distribution,
   fix regressions, preventable issues.
5. **Environment & tooling** — render failures, dependency
   issues, VLM/API failures.

---

## 9b — Analyze Root Causes

Classify each issue's root cause:

| Category              | Description                                            |
| --------------------- | ------------------------------------------------------ |
| `workflow-gap`        | Missing step, check, or handoff                        |
| `spec-ambiguity`      | Ambiguous schema/doc                                   |
| `code-quality`        | Bug in build script or helpers                         |
| `design-judgment`     | Suboptimal LLM design decision                         |
| `design-thesis-drift` | Deck didn't deliver declared `designThesis.mechanisms` |
| `content-judgment`    | Suboptimal content decision                            |
| `validation-miss`     | Validator should have caught it                        |
| `tooling-limitation`  | External tool limitation                               |
| `resource-constraint` | QA round limit or external constraint                  |

One root cause per issue. If unclear, pick the most upstream.
the most upstream cause (workflow-gap > spec-ambiguity >
validation-miss > code-quality > design-judgment).

---

## 9c — Optimization Recommendations

Each recommendation: `id`, `title`, `category` (∈ workflow /
validation / code-quality / design-system / content-pipeline /
tooling), `priority` (high/medium/low), `description` (2–4
sentences), `evidence` (issue IDs), `estimatedPayoff`
(`timeSavedMinutes`, `affectedSessions`, `confidence`).

---

## 9d — Write `s09-session-retrospective.json`

Required top-level fields: `sessionId`, `deckTopic`, `totalSlides`,
`workflowPath`, `executionSummary`, `stepMetrics[]`, `issues[]`,
`issueDistribution`, `recommendations[]`, `sessionInsights`.

Key rules:
- `stepMetrics[]` — one entry per executed step with
  `minutesSpent`, `retryCount`, `rootCauseCategory`.
- `issues[]` — every issue from 9a with all fields populated.
  `preventable: bool` + `preventionMethod` when true.
- `issueDistribution` — four cross-tabs (byStep, byCategory,
  bySeverity, byRootCause).
- `recommendations[]` — ordered by priority. Each references
  ≥1 issue ID and carries `estimatedPayoff`.
- `sessionInsights` — `workedWell[]`, `worthSurprise[]`,
  `wouldChange[]` (≥1 entry combined).

See schema example for full structure.

---

## Checkpoint

- `s09-session-retrospective.json` exists and is valid JSON.
- `stepMetrics[]` has one entry per `executionSummary.stepsExecuted`.
- Every issue in `s08-qa-log.json` appears in
  `s09-session-retrospective.json → issues[]`.
- Every recommendation references ≥ 1 issue ID that exists in
  `issues[]` AND carries an `estimatedPayoff` block.
- `issueDistribution` tallies match `issues[]` counts.
- `sessionInsights` has at least one entry across the three blocks
  combined.
