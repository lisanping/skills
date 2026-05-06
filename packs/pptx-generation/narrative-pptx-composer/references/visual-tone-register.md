# Visual Tone — Dimension 1: Visual Register

The overall design posture of the deck. Determined by
**domain × purpose × formality** in two steps.

---

## Step 1 — Detect content domain

Classify the content domain from `s01c-content-digest.json`, the
blueprint, and the brief. Record `contentDomain` on
`s05b-style-policy.json → visualTone.contentDomain`.

Detection rules are evaluated **in priority order** — first match
wins (most constrained domain first):

| Priority | Detection signal                                                                                                                                                                                                             | Domain                    |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| 1        | `content-digest` contains ≥ 3 fenced code blocks, OR ≥ 1 fenced code block AND `audience.role` matches engineer/developer/architect/SRE/ML                                                                                   | `technical-instructional` |
| 2        | Blueprint has ≥ 2 slides with `narrativeIntent` in {`process`, `architecture`, `system`, `code-walkthrough`, `data-flow`} AND purpose is `inform`/`report`                                                                   | `technical-instructional` |
| 3        | `audience.role` matches `engineer`/`developer`/`architect`/`data scientist`/`SRE`/`ML` AND purpose is `inform`/`report`                                                                                                      | `technical-instructional` |
| 4        | ≥ 3 slides with `narrativeIntent` in {`data-visualization`, `stat-callout`, `matrix`} OR ≥ 3 `content_data` sections in `content-digest`                                                                                     | `data-analytical`         |
| 5        | Purpose is `report` AND ≥ 50% of body slides have `narrativeIntent` in {`data-visualization`, `stat-callout`, `comparison`, `matrix`}                                                                                        | `data-analytical`         |
| 6        | The resolved `imageryDemand === "high"` (aesthetic/cultural/sensory topics)                                                                                                                                                  | `creative-portfolio`      |
| 7        | `explicitSignals.topic` or `keyMessages` matches aesthetic/cultural lexicon: art, painting, calligraphy, design, photography, brand, heritage, museum, fashion, music, film, architecture, travel, food, gallery, exhibition | `creative-portfolio`      |
| 8        | ≥ 3 slides with `narrativeIntent` in {`full-bleed-image`, `metaphor`, `quote`} OR `audience.role` matches `designer`/`creative`/`marketing`/`brand`                                                                          | `creative-portfolio`      |
| 9        | Purpose is `inspire` AND `moodKeywords` includes visual/creative/portfolio-family terms                                                                                                                                      | `creative-portfolio`      |
| 10       | Otherwise                                                                                                                                                                                                                    | `general`                 |

---

## Step 2 — Look up register

Use the table for the detected domain. Purpose and formality
always participate — no axis is bypassed.

**`general` domain:**

|                | `executive-formal` | `business-standard` | `casual`       | `regulatory`  |
| -------------- | ------------------ | ------------------- | -------------- | ------------- |
| **`persuade`** | authoritative      | analytical          | conversational | authoritative |
| **`propose`**  | authoritative      | analytical          | conversational | authoritative |
| **`report`**   | analytical         | analytical          | conversational | analytical    |
| **`inform`**   | analytical         | analytical          | conversational | analytical    |
| **`inspire`**  | authoritative      | inspirational       | inspirational  | —             |

**`technical-instructional` domain:**

|                | `executive-formal` | `business-standard` | `casual`           | `regulatory`       |
| -------------- | ------------------ | ------------------- | ------------------ | ------------------ |
| **`persuade`** | authoritative      | instructional-rich  | instructional-rich | authoritative      |
| **`propose`**  | authoritative      | instructional-rich  | instructional-rich | authoritative      |
| **`report`**   | analytical         | instructional-rich  | instructional-rich | analytical         |
| **`inform`**   | instructional-rich | instructional-rich  | instructional-rich | instructional-rich |
| **`inspire`**  | inspirational      | instructional-rich  | inspirational      | —                  |

**`data-analytical` domain:**

|                | `executive-formal` | `business-standard` | `casual`      | `regulatory`  |
| -------------- | ------------------ | ------------------- | ------------- | ------------- |
| **`persuade`** | authoritative      | analytical          | analytical    | authoritative |
| **`propose`**  | authoritative      | analytical          | analytical    | authoritative |
| **`report`**   | analytical         | analytical          | analytical    | analytical    |
| **`inform`**   | analytical         | analytical          | analytical    | analytical    |
| **`inspire`**  | authoritative      | inspirational       | inspirational | —             |

**`creative-portfolio` domain:**

|                | `executive-formal` | `business-standard` | `casual`      | `regulatory`  |
| -------------- | ------------------ | ------------------- | ------------- | ------------- |
| **`persuade`** | inspirational      | inspirational       | inspirational | authoritative |
| **`propose`**  | authoritative      | inspirational       | inspirational | authoritative |
| **`report`**   | analytical         | inspirational       | inspirational | analytical    |
| **`inform`**   | inspirational      | inspirational       | inspirational | inspirational |
| **`inspire`**  | inspirational      | inspirational       | inspirational | —             |

---

## Domain-specific register notes

**`technical-instructional`** — diagrams-first posture:
- `business-standard`/`casual` → `instructional-rich` for most
  purposes. `executive-formal` retains `authoritative`/`analytical`.

**`data-analytical`** — data visualization as primary language:
- `casual` no longer falls to `conversational` (data needs
  structured grids). `inspire` retains `inspirational` because
  hero numbers and KPI callouts are valid data-driven
  inspirational vocabulary.

**`creative-portfolio`** — visual impact as primary language:
- Nearly all cells → `inspirational` (imagery-led posture).
  `propose` × `executive-formal` stays `authoritative` (budget
  requests require structural credibility).

---

## Cross-domain independent constraints

| Domain                    | Independent constraint                                                                 |
| ------------------------- | -------------------------------------------------------------------------------------- |
| `technical-instructional` | Dimension 6 forces `diagram-led`; technical `narrativeIntent` slides need tech layouts |
| `data-analytical`         | Dimension 6 forces `data-forward`; data slides must use chart/KPI/table compositions   |
| `creative-portfolio`      | Dimension 6 forces `imagery-led`; ≥ 50% body slides should include image zones         |
| `general`                 | No independent constraints — register drives everything                                |

---

## Register definitions

| Register             | Visual characteristics                                                                                                              |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `authoritative`      | High contrast, deliberate accent placement, generous margins, minimal decoration                                                    |
| `analytical`         | Structured grids, consistent spacing, data-forward layouts. Decoration is functional, not ornamental                                |
| `conversational`     | Relaxed spacing, lighter visual weight, more whitespace. Icons and illustrations preferred                                          |
| `inspirational`      | Bold imagery, large type, high whitespace ratio. Fewer elements per slide, maximum visual impact                                    |
| `instructional-rich` | High-density with strong visual scaffolding: diagrams, code blocks, step pills, semantic color coding. Bullet lists are last resort |
