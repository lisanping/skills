# Step 5f — Generate LLM-Authored Images (optional)

Scan every slide for image needs. Four sources of demand:
1. Body-slide `illustrationSpec` with `source: "to-generate"`.
2. Image zones with `source: "generated"` added in 5d.
3. Backgrounds with `type: "image-generated"`.
4. Decorative pattern zones.

**Generate when:**
- Slide has `illustrationSpec.source: "to-generate"`.
- Bookend `*BackgroundType` is `image-generated`.
- Imagery Floor demands are not met.
- `reproduce`/`beautify` mode with distinctive icon groups.

**Do NOT generate when:**
- User-provided `mediaAttachments` already cover the slot.
- Slide purpose is data/analysis/instruction.
- `imageryDemand` is `low`/`none` and shape primitives suffice.

No artificial cap on image count.

---

## Schema additions

**Zone-level (image inside a layout zone):**

```json
{
  "role": "hero-illustration",
  "type": "image",
  "x": 50, "y": 12, "w": 45, "h": 76,
  "source": "generated",
  "imageRequest": {
    "id": "s03-illustration",
    "prompt": "Editorial illustration of a developer at a workstation, ...",
    "style_reference": "minimalist editorial vector illustration, flat colors",
    "negative_prompt": "photorealistic, text, logos, watermarks",
    "backend": "flux"
  },
  "fallback": {
    "type": "text-reflow",
    "replaceWithRole": "right-body",
    "reason": "If illustration fails, expand the body text into the freed zone"
  },
  "path": null
}
```

**Background-level (full-bleed):**

```json
"background": {
  "type": "image-generated",
  "imageRequest": {
    "id": "cover-bg",
    "prompt": "Soft abstract gradient evoking dawn light: warm coral fading into deep navy, subtle film grain, no objects, centered focal softness",
    "backend": "gpt-image"
  },
  "fallback": {
    "type": "gradient",
    "colors": ["primary", "accent"],
    "direction": "to-bottom-right"
  },
  "path": null
}
```

`source` enum: `"user-media"` (existing) | `"generated"` (new).
`fallback` is **mandatory** for every generated image — without it,
s07-build.py has no graceful path when generation fails.

---

## Prompt authoring rules

Required elements per prompt: **subject**, **composition**,
**color guidance** (named colors, not hex), **style register**
matching `visualRegister`, **negation** (FLUX only), **aspect
awareness**.

**Resolution:** zone inches × DPI. ~150 DPI for backgrounds,
~200 DPI for illustrations. Match zone aspect ratio (within 10%).

| Zone use              | Sizing rule                            |
| --------------------- | -------------------------------------- |
| Full-bleed background | 1920×1080 or 2400×1350                 |
| Hero illustration     | Zone w×h at 200 DPI, ≥1024px long edge |
| Supporting (square)   | 768×768 to 1024×1024                   |
| Strip                 | Full slide dimension at 150 DPI        |
| Small accent/icon     | 512×512                                |

Effects python-pptx cannot render (glow, blur, grain, etc.)
belong in the prompt, not zone instructions. See
[image-prompt-guide.md](image-prompt-guide.md).

---

## Procedure

**Step 1 — Aggregate.** Build `s05f-image-requests.json` from all
`source: "generated"` zones + `type: "image-generated"` backgrounds.
Backgrounds get `variations: 1`; illustrations get `variations: 3`.

**Step 2 — Generate (mandatory invocation).**

```bash
python $IMAGE_SKILL/scripts/generate_images.py \
  "$SESSION/s05f-image-requests.json" -w "$SESSION" \
  --report-name s05f-image_generation_output.json
```

`-w` makes images land in `$SESSION/images/` and `--report-name` writes
the manifest at `$SESSION/s05f-image_generation_output.json`. The script
is idempotent — already-generated `output_filename`s are skipped on re-run.

**Timeout guidance for large image batches.** When the request
file contains > 10 images, the script may run for several minutes
(~15–30 s per image depending on backend and concurrency). Run in
**async mode** so the terminal does not time out while waiting.
Budget approximately `imageCount × 30 s` as the expected runtime.

**Step 3 — VLM-based variation selection (illustrations only).**
Illustration requests (those with `variations: 3`) each produced
3 candidates. Use a VLM subagent to evaluate candidates and select
the best one for each slot. **Background images (`variations: 1`)
skip this step entirely** — they are patched directly without
selection.

For the full subagent procedure see
[vlm-image-selection.md](vlm-image-selection.md).

**Step 4 — Patch zones with paths.**

```bash
python $COMPOSER_SKILL/scripts/s05f_patch_image_paths.py "$SESSION"
```

The script reads `s05f-image-selection.json` (preferred) or
`s05f-image_generation_output.json` (fallback) and matches
`imageRequest.id` to each selection's `originalId`. Idempotent.
Outcomes per zone:

- Selection exists → writes `path = "<selected file>"`.
- All variations failed → sets `path: null` + `fallbackApplied: true`
  so s07-build.py falls through to the declared `fallback`.

`s05_validate_plan.py` is **read-only**. It enforces that every
`source: "generated"` zone ends up with either a resolvable
`path` or `fallbackApplied: true`, and it errors fast with a
fix-it message when generation output exists but the plan still
has unpatched paths — prompting you to run
`s05f_patch_image_paths.py` before re-validating.

**Step 5 — Append `imageGenerationLog`** to
`s05-slide-visual-design.json` (deck-level, not per-slide):

```json
"imageGenerationLog": {
  "totalRequested": 4,
  "totalVariations": 8,
  "generated": 7,
  "failed": 1,
  "selected": 4,
  "selectionMethod": "vlm-comparative",
  "failures": [
    { "id": "s07-metaphor_v2", "error": "content filter rejection" }
  ],
  "selections": [
    { "originalId": "cover-bg", "selected": "cover-bg.png", "weightedScore": null, "note": "single variation, no selection" },
    { "originalId": "s03-illustration", "selected": "s03-illustration_v1.png", "weightedScore": 44 }
  ]
}
```

---

## Cost awareness

Backgrounds: 1 variation each. Illustrations: 3 each.
Total API calls = (bg requests × 1) + (illustration requests × 3).
See [image-prompt-guide.md § Operational notes](image-prompt-guide.md).
