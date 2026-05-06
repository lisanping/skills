---
name: image-generator
description: >
  Standalone batch image generation skill. Accepts a JSON request file
  with per-image prompt, size, and quality parameters. Supports two
  backends: Azure OpenAI gpt-image-1.5 (fast) and Azure FLUX.1-Kontext-pro
  (high fidelity). Generates images concurrently, writes results to an
  output JSON + images/ directory.
  Trigger: "generate images", "create images", "fill image prompts",
  or when any skill needs AI-generated images.
  Not for: template profiling (pptx-profiler), slide layout generation
  (branded-pptx-generator), or slide content authoring (narrative-pptx-composer).
compatibility: >
  Requires Python 3.10+ with httpx, python-dotenv. Optional: azure-identity
  (for Azure AD auth). Environment variables in .env at project root.
---

# Image Generator

## Purpose

Standalone batch image generation tool. Accepts a structured JSON
request file containing one or more image generation tasks, each
with its own prompt, dimensions, quality level, and optional
parameters. Generates images via Azure AI backends and produces
an output manifest mapping each request to its generated file.

Two generation backends:
- **gpt-image-1.5** — Azure OpenAI (fast, ~10–15 s/image)
- **FLUX.1-Kontext-pro** — Azure Serverless FLUX (high fidelity, ~30–60 s/image)

## Architecture

This skill is a **tool-only skill** — no LLM judgment required.

**This skill's tools:**

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| `generate_images.py` | Batch image generation | `image_requests.json` | `images/*.png` + `image_generation_output.json` |

**Environment variables** (configured in `.env` at project root):

| Backend | Variables | Notes |
|---------|-----------|-------|
| **gpt-image-1.5** | `AZURE_OPENAI_IMAGE_ENDPOINT`, `AZURE_OPENAI_IMAGE_DEPLOYMENT`, `AZURE_OPENAI_IMAGE_API_VERSION`, `AZURE_OPENAI_IMAGE_TIMEOUT` | Default backend. |
| **FLUX.1-Kontext-pro** | `AZURE_FLUX_IMAGE_ENDPOINT`, `AZURE_FLUX_IMAGE_DEPLOYMENT`, `AZURE_FLUX_IMAGE_API_VERSION`, `AZURE_FLUX_IMAGE_TIMEOUT` | Higher fidelity, longer timeout. **Disabled by default.** |

**Backend enable/disable** (configured in `.env` or environment):

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAGE_BACKEND_GPT_IMAGE_ENABLED` | `true` | Set `false` to disable gpt-image backend |
| `IMAGE_BACKEND_FLUX_ENABLED` | `false` | Set `true` to enable FLUX backend |

When a backend is disabled, tasks targeting it are automatically
remapped to the default backend. If all needed backends are disabled,
the script aborts with an error.

**Authentication** priority (both backends):
1. `AZURE_OPENAI_IMAGE_API_KEY` / `AZURE_FLUX_IMAGE_API_KEY` env var
2. `azure-identity` DefaultAzureCredential (if installed)
3. `az account get-access-token` (Azure CLI fallback)

## When to Use

| Scenario | Skill |
|----------|-------|
| Need to generate one or more images from text prompts | **This skill** |
| Any skill's workflow needs AI-generated images | **This skill** |
| "Generate images" / "Create illustrations" / "Fill image prompts" | **This skill** |
| Need to compare gpt-image vs FLUX quality | **This skill** |
| Generate multiple variations for the same prompt to pick the best | **This skill** |

---

## Input Format

A JSON file with `defaults` (optional) and `requests` (required):

```json
{
  "defaults": {
    "backend": "gpt-image",
    "quality": "high",
    "width": 1536,
    "height": 1024,
    "output_format": "png"
  },
  "requests": [
    {
      "id": "hero-bg",
      "prompt": "Abstract gradient with deep blue and warm gold tones, soft bokeh",
      "width": 1536,
      "height": 1024,
      "quality": "high",
      "style_reference": "minimalist, corporate, clean edges",
      "negative_prompt": "text, watermark, blurry",
      "output_filename": "hero_background.png",
      "variations": 3
    },
    {
      "id": "diagram-01",
      "prompt": "Isometric data flow architecture diagram with nodes and arrows",
      "width": 1024,
      "height": 1024,
      "backend": "flux",
      "seed": 42
    }
  ]
}
```

### Per-request parameters

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | **Yes** | `string` | Unique identifier — links input to output |
| `prompt` | **Yes** | `string` | Image generation prompt |
| `width` | No | `int` | Pixel width (default: from `defaults` or 1024) |
| `height` | No | `int` | Pixel height (default: from `defaults` or 1024) |
| `quality` | No | `string` | `low` / `medium` / `high` (default: `medium`) |
| `negative_prompt` | No | `string` | Elements to exclude (FLUX only; ignored by gpt-image) |
| `style_reference` | No | `string` | Appended to prompt as style guidance |
| `output_format` | No | `string` | `png` / `jpg` / `webp` (default: `png`) |
| `output_filename` | No | `string` | Custom filename; auto-generated if omitted |
| `backend` | No | `string` | Per-request backend override (`gpt-image` / `flux`) |
| `seed` | No | `int` | Reproducibility seed (backend support varies) |
| `variations` | No | `int` | Number of images to generate for this prompt (default: `3`). Each variation is saved as `{id}_v1.png`, `{id}_v2.png`, etc. |

### Defaults block

Any field from the per-request table (except `id`, `prompt`) can
appear in `defaults` to set batch-wide values. Per-request values
override defaults.

---

## Workflow

### Step 1 — Prepare Request JSON

The caller (another skill, the agent, or the user) writes an
`image_requests.json` file following the input format above.

### Step 2 — Invoke Image Generation

```bash
# Default backend (gpt-image-1.5)
python $SKILL/scripts/generate_images.py image_requests.json

# Working directory — images → work_dir/images/, JSON report → work_dir/
python $SKILL/scripts/generate_images.py image_requests.json -w sessions/my_session/

# Custom report filename (default: image_generation_output.json)
python $SKILL/scripts/generate_images.py image_requests.json -w sessions/my_session/ --report-name s06f-image_generation_output.json

# Explicit backend + concurrency
python $SKILL/scripts/generate_images.py image_requests.json --backend flux --concurrency 2

# Custom output directory (overrides image dir only)
python $SKILL/scripts/generate_images.py image_requests.json -o images/

# Dry run — list tasks without calling the API
python $SKILL/scripts/generate_images.py image_requests.json --dry-run
```

The script:
1. Loads `.env` from project root
2. Parses the request JSON
3. Merges per-request fields with `defaults`
4. Resolves `width × height` → nearest API-supported size
5. Skips requests whose `output_filename` already exists on disk (idempotent)
6. Generates images concurrently (configurable worker count)
7. Writes `image_generation_output.json` alongside the generated images

**Checkpoint:** `image_generation_output.json` exists; `images/` contains
one file per successful request.

### Step 3 — Verify Results

Check the summary at the end of generation:
```
=== Image Generation Summary ===
  Generated : N
  Skipped   : N
  Failed    : N
```

Failed requests can be re-run — already-generated images are skipped
automatically.

---

## Output Format

```json
{
  "results": [
    {
      "id": "hero-bg_v1",
      "status": "success",
      "output_path": "images/hero_background_v1.png",
      "revised_prompt": "...",
      "backend": "gpt-image",
      "model": "gpt-image-1.5",
      "generated_at": "2026-04-22T12:00:00+00:00",
      "variation": 1,
      "variation_of": "hero-bg"
    },
    {
      "id": "hero-bg_v2",
      "status": "success",
      "output_path": "images/hero_background_v2.png",
      "revised_prompt": "...",
      "backend": "gpt-image",
      "model": "gpt-image-1.5",
      "generated_at": "2026-04-22T12:00:01+00:00",
      "variation": 2,
      "variation_of": "hero-bg"
    },
    {
      "id": "diagram-01",
      "status": "failed",
      "error": "API error 429: rate limited",
      "backend": "flux"
    }
  ],
  "summary": {
    "total_requests": 2,
    "total_tasks": 3,
    "generated": 2,
    "skipped": 0,
    "failed": 1
  }
}
```

## Output Artifacts

When `-w <work_dir>` is specified:

```
<work_dir>/
├── image_generation_output.json         # Output manifest
└── images/
    ├── hero_background.png              # Custom filename
    ├── diagram-01.png                   # Auto-generated from id
    └── ...
```

Without `-w`, outputs land next to the input JSON (`-o` overrides
image directory only).

## Backend Selection Guide

| Criterion | gpt-image-1.5 | FLUX.1-Kontext-pro |
|-----------|----------------|---------------------|
| Speed | ~10–15 s/image | ~30–60 s/image |
| Prompt fidelity | High | Very high |
| Photorealism | Good | Excellent |
| Text in images | Good | Better |
| Negative prompt | Not supported | Supported |
| Seed (reproducibility) | Not supported | Supported |
| Default concurrency | 1 | 1 |
| Cost | Standard Azure OpenAI | Serverless billing |
