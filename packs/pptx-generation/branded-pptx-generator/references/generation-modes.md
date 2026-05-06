# Generation Modes — Design Dimension Reference

Per-dimension decision boundaries for each generation mode. Consult
this when making design choices during slide generation (Steps 7–8).

For mode definitions, template layer model, and mode selection logic,
see SKILL.md Step 2. For strategy availability per mode, see SKILL.md
Step 5a. For compliance expectations per mode, see
[brand-compliance.md](brand-compliance.md).

---

## Per-Dimension Decision Matrix

### Layout Selection

| Strict                                                     | Balanced                                                                            | Creative                                                                                  |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Must use existing layouts/samples 1:1                      | Prefer existing layouts; may adjust placeholder arrangement within layout structure | May design new layouts; must preserve the template's spatial proportions and margin logic |
| **Forbidden:** creating any structure absent from template | **Forbidden:** discarding template layout logic entirely                            | **Forbidden:** layouts that feel visually alien to the brand                              |

### Typography

| Strict                                      | Balanced                                                                                                  | Creative                                                         |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Reproduce template font sizes exactly       | Use the template's typographic scale (the set of sizes it establishes), apply freely across content needs | Use template font families; may establish new size relationships |
| Copy weight/spacing/emphasis patterns as-is | Follow emphasis rules (e.g. "titles bold, body regular") with variation within those rules                | May introduce new weight/spacing combinations for visual rhythm  |

### Color Usage

| Strict                                                                       | Balanced                                                                                              | Creative                                                                                                     |
| ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Reproduce template's color-role mapping exactly (title=dk1, accent=accent1…) | Use theme colors; may reassign roles (accent2 for emphasis instead of accent1) when it serves content | Free use of full theme palette including combinations the template never showed; tint/shade variants allowed |
| **Forbidden:** any color assignment not demonstrated in template             | **Forbidden:** colors outside theme definitions                                                       | **Forbidden:** colors outside theme definitions (tint/shade of theme colors is permitted)                    |

### Shapes & Decoration

| Strict                                                 | Balanced                                                                                                                | Creative                                                                                                     |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| No new shapes; use only what exists in layouts/samples | May create new arrangements using the template's shape vocabulary (template uses rounded-rects → you use rounded-rects) | May introduce new shape types; must match the template's visual weight (minimal template → no heavy borders) |

### Data Visualization

| Strict                                                                      | Balanced                                                                                | Creative                                                                           |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Chart sample exists → reproduce its style; no sample → use text/tables only | May create charts following template color and visual weight even without chart samples | May create infographics, custom visuals, complex charts; full use of theme palette |

### Content Density & Whitespace

| Strict                                             | Balanced                                                                      | Creative                                                                                |
| -------------------------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Match the density demonstrated in template samples | Adjust density to content needs; respect template minimum margins and spacing | May push density boundaries for impact (e.g. full-bleed); readability remains mandatory |

### Placeholder Repurposing

| Strict                                                 | Balanced                                                        | Creative                                                                              |
| ------------------------------------------------------ | --------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Fill each placeholder exactly per its original purpose | May reasonably redefine (e.g. subtitle area for a key takeaway) | Content organization drives layout; placeholders are starting points, not constraints |

### Aesthetic Principles (Pattern Recipes & Shape/Color Grammar)

| Strict                                                                                         | Balanced                                                                                                                                       | Creative                                                                                                                                          |
| ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| When a matching patternRecipe exists, follow its skeleton, colorAssignment, and spacingSpec exactly; only item count may change via scalingRules | Recipes are the preferred starting point; may adapt proportions, combine recipe elements, or modify wrapper treatment to fit content needs | Recipes inform design direction but do not constrain; may invent new patterns following the shapeGrammar vocabulary and colorSemantics role map |
| Shape choices limited to `shapeGrammar.primitiveVocabulary`; color assignments must match `colorSemantics.roleAssignment` exactly | Shape vocabulary is the default palette; may introduce simple variants (e.g. rounded version of a sharp rect) if they match visual weight | May extend the shape vocabulary if new shapes are consistent with the template's visual weight and treatment style |
| **Forbidden:** deviating from recipe skeleton when one exists; shapes or colors outside the grammar | **Forbidden:** shapes or color roles that violate the grammar's core conventions (e.g. adding gradients to a flat-design template) | **Forbidden:** shapes or colors that visually clash with the brand's established aesthetic |

---

## Absolute Invariants (Mode-Independent)

These five constraints are never negotiable, regardless of mode:

1. **Accessibility** — Title contrast ≥ 3:1, body contrast ≥ 4.5:1 (WCAG AA). Not a design preference; a legal and ethical requirement.
2. **Brand Identity elements** — Theme color definitions, theme font families, logo placement, slide dimensions, legal/disclaimer text. Altering these means it is no longer this brand.
3. **Content accuracy** — Numbers consistent across slides, terminology stable, narrative coherent. Independent of design mode.
4. **Readability at projection distance** — Text must be legible when projected. Beautiful but illegible = failed.
5. **Professional craft** — No element overlap, no text clipping, no orphan bullets, no leftover placeholder text. This is a quality floor, not a style choice.
