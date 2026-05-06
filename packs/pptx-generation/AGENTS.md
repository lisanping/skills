# AGENTS.md (pack-level)

> Second-level routing for tasks scoped to **pptx-generation**. Read this file before opening any `SKILL.md` inside the pack.

## Pack purpose

Generate, profile, and manipulate PowerPoint (`.pptx` / `.potx`) files — covering template profiling, narrative-driven composition, brand-compliant generation, batch image generation, and low-level OOXML operations.

## SKILL routing

Pick **one** SKILL by task type. Each entry's "Read first" file is the authoritative workflow — do not paraphrase from this table.

| Task type                                                                                          | Read first                                                           |
| -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Profile a template (`.potx` / `.pptx`) → `template-profile.json`                                   | [pptx-profiler/SKILL.md](pptx-profiler/SKILL.md)                     |
| Generate a brand-compliant deck **from a template + content brief** (strict / balanced / creative) | [branded-pptx-generator/SKILL.md](branded-pptx-generator/SKILL.md)   |
| Compose a deck **from content / brief / reference images** (content-first, narrative-driven)       | [narrative-pptx-composer/SKILL.md](narrative-pptx-composer/SKILL.md) |
| Batch-generate images from a JSON request (Azure gpt-image / FLUX backends)                        | [image-generator/SKILL.md](image-generator/SKILL.md)                 |
| Read / edit / create / unpack / repack any `.pptx`, render to PDF/PNG, validate OOXML              | [pptx/SKILL.md](pptx/SKILL.md)                                       |

### Picking between the three "generate a deck" SKILLs

- **Have a `.potx` / branded `.pptx` template + want pixel-faithful brand compliance?** → `branded-pptx-generator`
- **Have content (md / docx / pdf / pptx / image) + want a story-driven deck?** → `narrative-pptx-composer`
- **Just want to read / patch / merge a `.pptx`?** → `pptx`

`narrative-pptx-composer` and `branded-pptx-generator` both **call into** `pptx-profiler` (for template analysis) and `pptx` (for OOXML operations). Treat the latter two as infrastructure.

## Variables

Path variables referenced by the SKILL.md files in this pack. The values below assume the agent is invoked from inside the pack directory (`packs/pptx-generation/`); translate to repo-relative paths if the agent's working directory is the repo root.

| Variable         | Resolved path (relative to pack root) | Owner SKILL               |
| ---------------- | ------------------------------------- | ------------------------- |
| `SKILLS_ROOT`    | `.`                                   | (pack root)               |
| `PROFILER_SKILL` | `pptx-profiler`                       | `pptx-profiler`           |
| `BRANDED_SKILL`  | `branded-pptx-generator`              | `branded-pptx-generator`  |
| `COMPOSER_SKILL` | `narrative-pptx-composer`             | `narrative-pptx-composer` |
| `IMAGE_SKILL`    | `image-generator`                     | `image-generator`         |
| `PPTX_SKILL`     | `pptx`                                | `pptx`                    |

> Some `SKILL.md` files (e.g. `branded-pptx-generator`) export `SKILLS_ROOT=".claude/skills"`. That value is the **canonical** Anthropic Skills layout assumed by upstream prose; in **this pack** the actual on-disk layout is flat under the pack root, so when running scripts use the resolutions above.

## Key commands

```bash
# Activate the pack environment
conda activate pptx-generation

# Profile a template
python pptx-profiler/scripts/extract_template.py <file>.potx -o profile/

# Render template layouts to JPEGs (requires LibreOffice)
python pptx-profiler/scripts/render_layouts.py <file>.pptx -o layouts/

# Validate a brand-generation plan against its schema
python branded-pptx-generator/scripts/validate_plan.py plan.json

# Run a narrative-composer step (example: input validation)
python narrative-pptx-composer/scripts/s01_validate_inputs.py inputs/

# Batch image generation (requires .env at project root)
python image-generator/scripts/generate_images.py image_requests.json

# Low-level OOXML round-trip
python pptx/scripts/office/unpack.py deck.pptx unpacked/
python pptx/scripts/office/pack.py   unpacked/ deck.out.pptx --original deck.pptx
python pptx/scripts/office/validate.py deck.out.pptx --auto-repair
```

## Cross-skill data exchange

All SKILLs in this pack pass artifacts via **JSON files on disk**, never via in-memory objects:

| Producer                  | Artifact                          | Consumer(s)                                                                 |
| ------------------------- | --------------------------------- | --------------------------------------------------------------------------- |
| `pptx-profiler`           | `template-profile.json`           | `branded-pptx-generator`                                                    |
| `pptx-profiler`           | `composer-digest.json`            | `narrative-pptx-composer`                                                   |
| `branded-pptx-generator`  | `plan.json` + `style-policy.json` | (own pipeline downstream)                                                   |
| `narrative-pptx-composer` | `s01..s09-*.json` step artifacts  | (own pipeline; `s05f_patch_image_paths.py` consumes image-generator output) |
| `image-generator`         | `image_generation_output.json`    | `narrative-pptx-composer` (image embedding step)                            |

## Conventions

- Skills are at `packs/pptx-generation/<skill>/SKILL.md` (flat layout — kept intentionally for easy sharing; the linter accepts both this and `.claude/skills/`).
- `references/`: kebab-case `*.md` / `*.yaml` / `*.json` — load on demand
- `scripts/`: snake_case `*.py`, runnable as `python scripts/<name>.py --help`
- `prompts/` and `schemas/`: free-form structure (not subject to repo naming lint)
- No pack-local Python package; all logic in per-skill scripts
- Outputs (`*.pptx` artifacts, `images/`, rendered previews) are git-ignored — see [.gitignore](.gitignore)
