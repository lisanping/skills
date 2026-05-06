# Image Prompt Guide

Reference for authoring prompts in `s05f-image-requests.json`.
Step 5f points here for texture/light/material vocabulary,
prompt-level placement rules, anti-patterns, and operational
notes that are too specific for the workflow runbook.

---

## Texture, light, and material vocabulary

Effects that python-pptx **cannot** render natively — soft glow,
backdrop-blur (glassmorphism), grain, halftone, frosted-glass,
watercolor wash, ink-bleed, chromatic aberration, brushed-metal —
are valid here, in the image-generation prompt, **not as
zone-level rendering instructions**. The image carries the
texture; the slide composes it.

These vocabulary words help the model produce a consistent
material register across all generated images for one deck.
Pick **one** texture register and reuse it in every prompt of
the same deck so the bookend backgrounds, divider backgrounds,
and illustrations feel like one family.

| Register                      | Vocabulary to include in `prompt` / `style_reference`                                                          | Pairs well with                                          |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| **Editorial photoreal**       | "soft volumetric light", "natural depth of field", "atmospheric haze", "studio rim light"                      | Cover / closing / dividers on serious or technical decks |
| **Cinematic painterly**       | "digital painting, painterly brush", "soft chiaroscuro", "warm filament glow", "matte color blocking"          | Storytelling decks, keynote-style talks                  |
| **Glassmorphism / soft-tech** | "glassmorphic translucent panels", "soft gaussian blur halo", "subtle gradient bloom", "frosted-glass surface" | Product / SaaS / fintech decks                           |
| **Editorial vector**          | "flat editorial vector", "monoline strokes", "limited 3-color palette", "no gradients, no shadows"             | Diagram-heavy decks; supporting illustrations            |
| **Ink / paper**               | "sumi ink wash", "rice-paper texture", "soft bleed edges", "muted earth palette"                               | Cultural / heritage / craft topics                       |
| **Grainy / analog**           | "fine film grain", "warm 35mm photo", "soft halation", "low-saturation analog tones"                           | Retrospective, oral-history, documentary topics          |
| **Isometric flat**            | "clean isometric 30°/30° projection", "flat shading, no gradients", "limited 4-color palette"                  | Architecture / system / process visuals                  |

**Anti-patterns** — vocabulary the prompt should **avoid** unless
the deck specifically calls for it:

- *"vibrant", "modern", "futuristic"* — too generic; produces
  default stock-art aesthetic. Replace with one of the registers above.
- *"3D render", "Unreal Engine", "octane render"* — usually
  produces over-rendered video-game look that fights editorial
  decks. Use only when the deck's `aestheticSignals.moodKeywords`
  explicitly demand hyperreal CGI.
- *"trending on artstation"*, *"masterpiece"* — non-specific quality
  hacks that shift output in unpredictable directions.

**Prompt-level placement.** Texture vocabulary belongs **after**
the subject and composition, before the negation:

```
{subject}. {composition}. {color guidance}. {texture register
vocabulary — 1 short clause}. {negation}.
```

Example (matches this skill's actual cover prompt pattern):

> "Editorial cinematic cover image for a tech presentation. Deep
> navy atmosphere with subtle circuit-grid texture; floating
> translucent panels orbit a central warm-amber filament. Generous
> quiet area in the upper-left for a title overlay. **Soft
> volumetric light from upper-left; matte painterly finish; no
> harsh neon.** No text, no logos, no human figures."

**Reminder — these are prompt words, not zone properties.** Do
not add `glow: true` or `texture: "frosted"` to a Zone in
`s05-slide-visual-design.json`. The schema deliberately has no
such fields because s07-build.py / python-pptx cannot honor them.
The texture lives in the generated image; the slide arranges it.

---

## Operational notes

**Variation counts are per-type.** Backgrounds use
`"variations": 1` (single output is sufficient — the image is
used directly). Illustrations use `"variations": 3` (candidates
are compared by VLM in 5f-3; see
[vlm-image-selection.md](vlm-image-selection.md)).

**Backend choice.** `gpt-image` is the default — fast (~10–15 s
per image) and good for backgrounds and abstract decoration.
`flux` is slower (~30–60 s per image) and worth it for hero
illustrations where prompt fidelity matters most.

**Large batches.** When the request file contains > 10 images,
run the generation script in async mode so the terminal does
not time out while waiting; check completion via
`get_terminal_output`. For decks with 5+ images, consider
running 5f-Steps 1–2 as a background task and continuing with
5d refinements; block on completion before Step 3 (VLM selection).
Budget ≈ `imageCount × 30 s` as the expected runtime.
