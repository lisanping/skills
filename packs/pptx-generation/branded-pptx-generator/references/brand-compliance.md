# Brand Compliance Reference

Cross-phase reference for the three-tier compliance model. This document defines what is checked, how it is enforced, and where violations are caught.

---

## Three-Tier Model

### 🔒 Locked — Zero Tolerance

Elements that must exactly match the template. Any deviation is a **critical violation** that forces a FAIL verdict in the Rule Engine.

| Element                  | Source in `template_profile.json`                                         | Check Logic                                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Theme colors**         | `identity.colors.scheme` (dk1, dk2, lt1, lt2, accent1–6, hlink, folHlink) | Every color in `generation_log.metrics.colors_used` must exist in the scheme (HEX) or be a valid `MSO_THEME_COLOR` slot name |
| **Font families**        | `identity.fonts.major` + `identity.fonts.minor` (latin, ea, cs)           | Every font in `generation_log.metrics.fonts_used` must be one of the declared families                                       |
| **Slide size**           | `identity.slide_size` (width_pt, height_pt, aspect)                       | Must not change from template                                                                                                |
| **Logo positions**       | `compliance.logo.positions[]` (x_pct, y_pct, w_pct, h_pct per context)    | Logos must appear in declared positions; `clear_space` respected; `min_size` enforced                                        |
| **Footer structure**     | `compliance.footer` (has_page_number, has_date, has_footer_text)          | Footer placeholders must match template configuration                                                                        |
| **Disclaimer/copyright** | `compliance.disclaimer_text`, `compliance.copyright_format`               | Exact text match when present                                                                                                |

### 🟡 Guided — Parameterized Ranges

Elements that have a preferred value with allowed deviations. Ranges are mode-dependent:

| Mode     | Tolerance         |
| -------- | ----------------- |
| Strict   | ±5% (near-locked) |
| Balanced | ±15%              |
| Creative | ±25%              |

| Element             | Source                                  | Range Example                      |
| ------------------- | --------------------------------------- | ---------------------------------- |
| **Title font size** | `layouts[].placeholders[].font_size_pt` | 36pt ±15% → 30.6–41.4pt (balanced) |
| **Body font size**  | Same                                    | 14pt ±15% → 11.9–16.1pt            |
| **Spacing/margins** | Design language conventions             | Template baseline ±tolerance       |
| **Color ratios**    | `identity.colors.usage_ratio`           | Approximate within tolerance       |

**Verdict:** Individual guided deviations produce WARNINGs. Accumulated deviations may warrant a fix pass.

### 🟢 Flexible — Design Language Principles

Elements where creative judgment applies, guided by the design language and aesthetic principles rather than exact values.

| Element                         | Guidance Source                                                                                                |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Content narrative structure** | `design_language.style_tone`                                                                                   |
| **Whitespace rhythm**           | `aesthetic_principles.compositionSystem.densitySpectrum` → `design_language.whitespace_rhythm` (fallback)      |
| **Visual hierarchy approach**   | `aesthetic_principles.typographicSystem.scaleStops` → `design_language.visual_hierarchy_method` (fallback)     |
| **Component styling**           | `aesthetic_principles.shapeGrammar.primitiveVocabulary` → `design_language.component_style_pattern` (fallback) |
| **Color role assignment**       | `aesthetic_principles.colorSemantics.roleAssignment` (prescriptive mapping of semantic roles to theme slots)   |
| **Pattern structure**           | `aesthetic_principles.patternRecipes` (reusable structural templates with scaling and color logic)             |
| **Layout selection**            | `layouts[].inferred_type` + content intent matching                                                            |

When `aesthetic_principles` is null (fewer than 3 content-bearing
samples), fall back to the `design_language.*` fields listed as
fallback above. The `design_language` fields remain descriptive
("what the template looks like"); `aesthetic_principles` fields are
prescriptive ("how to design new elements that match").

**Enforcement:** Qualitative visual review only (Step 10 subagent). No deterministic rule checks.

---

## WCAG Accessibility (Always Enforced)

Contrast ratio requirements apply regardless of generation mode:

| Element              | Minimum Ratio | Standard            |
| -------------------- | ------------- | ------------------- |
| Title / heading text | ≥ 3:1         | WCAG AA Large Text  |
| Body / caption text  | ≥ 4.5:1       | WCAG AA Normal Text |

Background color is determined from:
1. Shape fill behind the text element
2. Slide background (layout → slide master fallback)
3. `identity.colors.scheme.lt1` as final fallback

---

## Augmentation Rules (Augmentable Layouts Only)

When a layout is marked `augmentable: true`, additional shapes (charts, tables, custom graphics) are permitted in the `custom_content_zone`. Extra rules apply:

| Rule                        | Check                                                        |
| --------------------------- | ------------------------------------------------------------ |
| Colors in bounds            | Custom shapes only use theme colors                          |
| Fonts in bounds             | Custom text only uses theme fonts                            |
| Zone boundary               | Custom shapes stay within `custom_content_zone` (x, y, w, h) |
| No placeholder modification | Existing placeholders and decorative shapes unchanged        |
| Consistency                 | Custom elements follow `design_language` patterns            |

---

## Compliance by Generation Mode

See [generation-modes.md](generation-modes.md) for the per-dimension
decision matrix (layout, typography, color, shapes, density, placeholders).

| Aspect               | Strict                         | Balanced                             | Creative                     |
| -------------------- | ------------------------------ | ------------------------------------ | ---------------------------- |
| 🔒 Locked elements    | Exact match                    | Exact match                          | Exact match                  |
| 🟡 Guided ranges      | ±5% (near-locked)              | ±15%                                 | ±25%                         |
| 🟢 Flexible           | Conservative interpretation    | Moderate interpretation              | Bold interpretation          |
| Layout selection     | Prefer exact template match    | Allow semantic-type matching         | Allow cross-type exploration |
| Augmentation         | Disabled                       | Allowed (conservative)               | Allowed (exploratory)        |
| Visual motifs        | Reproduce exactly              | Maintain pattern                     | Inspired variation           |
| Available strategies | `clone-sample`, `clone-layout` | + `augmented-clone`, `spec-composed` | All four, freely             |

---

## Gap Analysis Integration

When `template_profile.json` has null or missing fields, classify each gap by tier:

| Tier                     | Gap Impact                 | Action                                |
| ------------------------ | -------------------------- | ------------------------------------- |
| 🔒 Missing locked field   | Cannot validate compliance | Block generation or warn prominently  |
| 🟡 Missing guided field   | No range to check against  | Skip range check, note in report      |
| 🟢 Missing flexible field | Reduced design guidance    | Generator uses general best practices |

Gap entries are stored in `template_profile.json → gaps.missing_from_potx[]` with fields: `field`, `tier`, `source_needed`, `can_infer`, `inference_source`.

---

## Quick Checklist by Step

### After Step 3 (Obtain Profile)
- [ ] All locked elements extracted and non-null
- [ ] Color scheme complete (12 slots)
- [ ] Font families resolved (major + minor, latin at minimum)
- [ ] Logo positions detected (if applicable)
- [ ] Gaps reviewed — any missing locked field blocks generation

### After Step 5 (Plan the Deck)
- [ ] `style-policy.json` guardrails match chosen mode tolerance
- [ ] Layout references validated against profile
- [ ] Augmentable layouts identified for augmented content tasks

### After Step 7 (Generate Slides)
- [ ] Theme colors/fonts only — no hardcoded hex or off-theme fonts
- [ ] WCAG contrast ratios met on every slide
- [ ] Guided values within mode tolerance
- [ ] Augmented shapes stay within `custom_content_zone`

### After Steps 9–10 (Compliance + Visual QA)
- [ ] `compliance_checker.py` reports zero locked violations
- [ ] Visual QA subagent reviewed all slides
- [ ] No leftover placeholder text
- [ ] No style drift across dividers/covers
