"""Standalone batch image generation tool.

Generate images from a structured JSON request file via Azure OpenAI
(gpt-image-1.5) or Azure FLUX.1-Kontext-pro. Each request specifies
prompt, dimensions, quality, and optional parameters. Results are
written to image_generation_output.json.

Usage:
    python generate_images.py <request_json> [-w DIR] [--backend gpt-image|flux] [--concurrency N] [-o DIR] [--dry-run]

Requirements:
    pip install httpx python-dotenv

Optional:
    pip install azure-identity   # For Azure AD token auth (fallback: az cli)
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Force UTF-8 stdout/stderr so the success ✓ / failure ✗ markers don't
# crash on Windows cp1252 consoles. A print failure here used to cascade
# into the wrapping try/except and get logged as a (false) generation
# failure — see retrospective I-02.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Install: pip install httpx", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv is required. Install: pip install python-dotenv", file=sys.stderr)
    sys.exit(1)

VERSION = "2.0.0"

# ---------------------------------------------------------------------------
# Backend configuration
# ---------------------------------------------------------------------------

BACKENDS: dict[str, dict[str, Any]] = {
    "gpt-image": {
        "enabled": True,
        "enabled_var": "IMAGE_BACKEND_GPT_IMAGE_ENABLED",
        "endpoint_var": "AZURE_OPENAI_IMAGE_ENDPOINT",
        "deployment_var": "AZURE_OPENAI_IMAGE_DEPLOYMENT",
        "api_version_var": "AZURE_OPENAI_IMAGE_API_VERSION",
        "timeout_var": "AZURE_OPENAI_IMAGE_TIMEOUT",
        "api_key_var": "AZURE_OPENAI_IMAGE_API_KEY",
        "token_scope_var": "AZURE_OPENAI_IMAGE_TOKEN_SCOPE",
        "default_api_version": "2025-04-01-preview",
        "default_timeout": 120,
        "default_concurrency": 1,
        "default_quality": "medium",
        "supports_negative_prompt": False,
        "supports_seed": False,
        "url_template": "{endpoint}/openai/deployments/{deployment}/images/generations?api-version={api_version}",
    },
    "flux": {
        "enabled": False,
        "enabled_var": "IMAGE_BACKEND_FLUX_ENABLED",
        "endpoint_var": "AZURE_FLUX_IMAGE_ENDPOINT",
        "deployment_var": "AZURE_FLUX_IMAGE_DEPLOYMENT",
        "api_version_var": "AZURE_FLUX_IMAGE_API_VERSION",
        "timeout_var": "AZURE_FLUX_IMAGE_TIMEOUT",
        "api_key_var": "AZURE_FLUX_IMAGE_API_KEY",
        "token_scope_var": "AZURE_FLUX_IMAGE_TOKEN_SCOPE",
        "default_api_version": "2025-04-01-preview",
        "default_timeout": 180,
        "default_concurrency": 1,
        "default_quality": "standard",
        "supports_negative_prompt": True,
        "supports_seed": True,
        "url_template": "{endpoint}/images/generations?api-version={api_version}",
    },
}


def _is_backend_enabled(backend_name: str) -> bool:
    """Check if a backend is enabled via config + env override.

    Resolution order:
    1. Env var (e.g. IMAGE_BACKEND_FLUX_ENABLED=true/false) — overrides config
    2. Hardcoded `enabled` flag in BACKENDS dict
    """
    cfg = BACKENDS.get(backend_name)
    if cfg is None:
        return False
    env_val = os.environ.get(cfg["enabled_var"], "").strip().lower()
    if env_val in ("true", "1", "yes"):
        return True
    if env_val in ("false", "0", "no"):
        return False
    return cfg.get("enabled", True)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ImageRequest:
    """A single image generation request (merged from defaults + per-item)."""
    id: str
    prompt: str
    width: int = 1024
    height: int = 1024
    quality: str = "medium"
    negative_prompt: str | None = None
    style_reference: str | None = None
    output_format: str = "png"
    output_filename: str | None = None
    backend: str | None = None  # per-request override
    seed: int | None = None
    variations: int = 1          # number of images to generate for this prompt
    variation_index: int = 0     # 0 = not a variation; 1..N = variation number
    variation_of: str = ""       # original request id (set after expansion)
    # Phase B/C — semantic image role from narrative-pptx-composer.
    # `atmospheric` = full-bleed background; `narrative` = subject image;
    # `accent` = small abstract motif. When set, the runner can
    # auto-augment the negative_prompt with role-specific guards (C-5)
    # and post-crop the output to match the zone aspect ratio (C-6).
    image_role: str | None = None

    def resolved_filename(self) -> str:
        if self.output_filename:
            if self.variation_index > 0:
                base = Path(self.output_filename)
                return f"{base.stem}_v{self.variation_index}{base.suffix}"
            return self.output_filename
        if self.variation_index > 0:
            return f"{self.variation_of}_v{self.variation_index}.{self.output_format}"
        return f"{self.id}.{self.output_format}"


@dataclass
class ImageResult:
    """Result for a single image request."""
    id: str
    status: str  # "success" | "failed" | "skipped"
    output_path: str | None = None
    revised_prompt: str | None = None
    backend: str | None = None
    model: str | None = None
    generated_at: str | None = None
    error: str | None = None
    variation: int | None = None       # 1-based variation index (None if not a variation)
    variation_of: str | None = None    # original request id (None if not a variation)


@dataclass
class Stats:
    generated: int = 0
    failed: int = 0
    skipped: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _preview(text: str, max_len: int = 80) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _build_prompt(prompt: str, style_reference: str | None = None) -> str:
    """Compose final prompt with optional style reference appended."""
    if not style_reference:
        return prompt
    return f"{prompt}\n\nStyle reference: {style_reference}"


def _pick_api_size(width: int, height: int) -> str:
    """Map requested dimensions to nearest API-supported size.

    Supported sizes: 1024x1024, 1536x1024, 1024x1536.
    """
    if width <= 0 or height <= 0:
        return "1024x1024"
    ratio = width / height
    if ratio >= 1.25:
        return "1536x1024"
    if ratio <= 0.8:
        return "1024x1536"
    return "1024x1024"


# ── C-5: accent imagery negative-prompt boilerplate ─────────────────
#
# When a request comes in tagged `image_role: "accent"` (set by the
# narrative-pptx-composer's accent-imagery flow, or by any caller that
# wants the same guards), automatically prepend a strong list of
# anti-representation tokens to the negative_prompt. This complements
# the validator's positive-keyword check (see `validate_plan.
# check_accent_imagery`) and removes the burden of remembering the
# exact incantation from the LLM that authors the request.
#
# Atmospheric backgrounds get a lighter touch — they often want a hint
# of subject (a horizon, a vague figure of color) — so we only block
# the hard-fail items (text, logos, watermarks, sharp brand marks).

_ACCENT_NEGATIVE_BOILERPLATE = (
    "people, faces, hands, body parts, text, letters, numbers, words, "
    "logos, watermarks, brand marks, recognizable objects, photographic "
    "detail, sharp geometric icons, vector art, charts, diagrams, "
    "screenshots, UI elements"
)

_ATMOSPHERIC_NEGATIVE_BOILERPLATE = (
    "text, letters, numbers, words, logos, watermarks, brand marks, "
    "screenshots, UI elements"
)


def _augment_negative_prompt(req: "ImageRequest") -> str | None:
    """Return the request's negative_prompt augmented with role-specific
    boilerplate. Called once per task at runtime — does not mutate the
    original request.
    """
    role = (req.image_role or "").lower()
    if role == "accent":
        boiler = _ACCENT_NEGATIVE_BOILERPLATE
    elif role == "atmospheric":
        boiler = _ATMOSPHERIC_NEGATIVE_BOILERPLATE
    else:
        return req.negative_prompt
    user_neg = (req.negative_prompt or "").strip()
    if not user_neg:
        return boiler
    # Avoid double-adding when the caller already includes the boilerplate.
    if boiler in user_neg:
        return user_neg
    return f"{boiler}, {user_neg}"


# ── C-6: aspect-ratio reconciliation ────────────────────────────────
#
# The Azure backends only return one of three sizes (1024x1024,
# 1536x1024, 1024x1536). When the caller asked for, say, 1536x256
# (a thin accent band), `_pick_api_size` snaps to 1536x1024 silently
# and the decorator zone gets a square-ish image instead of the band
# it requested.
#
# `_aspect_mismatch_pct` reports how far the picked aspect drifts from
# the requested one. When the drift exceeds a small threshold we (a)
# log a clear warning so the caller can spot it in the run output, and
# (b) post-process the saved image with `_crop_to_aspect` to re-cut it
# to the requested aspect ratio (center crop). This costs Pillow but
# Pillow is already an indirect dep via narrative-pptx-composer.
#
# Cropping is enabled by default; pass `--no-crop` on the CLI to
# disable for a session.

ASPECT_MISMATCH_WARN_THRESHOLD = 0.15  # 15%


def _aspect_mismatch_pct(req_w: int, req_h: int, api_size: str) -> float:
    """Fractional difference between requested and API aspect ratios.

    Returns a value in [0, +inf): 0 means identical aspect.
    """
    if req_w <= 0 or req_h <= 0:
        return 0.0
    try:
        api_w, api_h = (int(x) for x in api_size.split("x"))
    except Exception:
        return 0.0
    req_ratio = req_w / req_h
    api_ratio = api_w / api_h
    if api_ratio <= 0:
        return 0.0
    return abs(req_ratio - api_ratio) / api_ratio


def _crop_to_aspect(image_path: Path, target_w: int, target_h: int) -> bool:
    """Center-crop `image_path` (in place) so its aspect matches
    target_w/target_h. Returns True on success, False if Pillow is
    unavailable or any error occurs (we never fail the run on crop
    errors — the original full-size image is preserved).
    """
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        img = Image.open(image_path)
        w, h = img.size
        target_ratio = target_w / target_h
        actual_ratio = w / h
        if abs(target_ratio - actual_ratio) < 0.01:
            return True  # already close enough
        if actual_ratio > target_ratio:
            # Image is wider than target — trim sides.
            new_w = int(h * target_ratio)
            offset = (w - new_w) // 2
            box = (offset, 0, offset + new_w, h)
        else:
            # Image is taller than target — trim top/bottom.
            new_h = int(w / target_ratio)
            offset = (h - new_h) // 2
            box = (0, offset, w, offset + new_h)
        cropped = img.crop(box)
        cropped.save(image_path)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

def parse_requests(raw: dict[str, Any]) -> list[ImageRequest]:
    """Parse input JSON into a list of ImageRequest objects."""
    defaults = raw.get("defaults") or {}
    items = raw.get("requests")
    if not items or not isinstance(items, list):
        print("Error: input JSON must contain a 'requests' array", file=sys.stderr)
        sys.exit(1)

    requests: list[ImageRequest] = []
    seen_ids: set[str] = set()
    for i, item in enumerate(items):
        req_id = item.get("id")
        if not req_id:
            print(f"Error: request[{i}] missing required 'id' field", file=sys.stderr)
            sys.exit(1)
        if not item.get("prompt"):
            print(f"Error: request[{i}] (id={req_id}) missing required 'prompt' field",
                  file=sys.stderr)
            sys.exit(1)
        if req_id in seen_ids:
            print(f"Error: duplicate request id '{req_id}'", file=sys.stderr)
            sys.exit(1)
        seen_ids.add(req_id)

        variations = item.get("variations", defaults.get("variations", 1))
        if not isinstance(variations, int) or variations < 1:
            print(f"Error: request[{i}] (id={req_id}) 'variations' must be a positive integer",
                  file=sys.stderr)
            sys.exit(1)

        requests.append(ImageRequest(
            id=req_id,
            prompt=item["prompt"],
            width=item.get("width", defaults.get("width", 1024)),
            height=item.get("height", defaults.get("height", 1024)),
            quality=item.get("quality", defaults.get("quality", "medium")),
            negative_prompt=item.get("negative_prompt", defaults.get("negative_prompt")),
            style_reference=item.get("style_reference", defaults.get("style_reference")),
            output_format=item.get("output_format", defaults.get("output_format", "png")),
            output_filename=item.get("output_filename"),
            backend=item.get("backend", defaults.get("backend")),
            seed=item.get("seed", defaults.get("seed")),
            variations=variations,
            image_role=item.get("image_role", defaults.get("image_role")),
        ))
    return requests


def expand_variations(requests: list[ImageRequest]) -> list[ImageRequest]:
    """Expand requests with variations > 1 into individual tasks."""
    expanded: list[ImageRequest] = []
    for req in requests:
        if req.variations <= 1:
            expanded.append(req)
        else:
            for vi in range(1, req.variations + 1):
                clone = ImageRequest(
                    id=f"{req.id}_v{vi}",
                    prompt=req.prompt,
                    width=req.width,
                    height=req.height,
                    quality=req.quality,
                    negative_prompt=req.negative_prompt,
                    style_reference=req.style_reference,
                    output_format=req.output_format,
                    output_filename=req.output_filename,
                    backend=req.backend,
                    seed=req.seed,
                    variations=1,
                    variation_index=vi,
                    variation_of=req.id,
                    image_role=req.image_role,
                )
                expanded.append(clone)
    return expanded


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _get_az_cli_token(scope: str = "https://cognitiveservices.azure.com") -> str:
    cmd = (
        f'az account get-access-token --resource {scope} '
        f'--query accessToken -o tsv'
    )
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False, shell=True,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError(
            "Cannot obtain Azure credentials.\n"
            f"  Set the API key env var, or run `az login` first.\n"
            f"  az stderr: {result.stderr.strip()}"
        )
    return token


def resolve_auth(backend_cfg: dict[str, Any]) -> tuple[str, bool]:
    """Resolve authentication: API key → azure-identity → az cli.

    Returns (token, is_api_key).
    """
    api_key = os.environ.get(backend_cfg["api_key_var"], "")
    if api_key:
        return api_key, True

    try:
        from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
        scope = os.environ.get(
            backend_cfg["token_scope_var"],
            "https://cognitiveservices.azure.com/.default",
        )
        credential = DefaultAzureCredential()
        token = credential.get_token(scope).token
        return token, False
    except Exception:
        pass

    scope = os.environ.get(
        backend_cfg["token_scope_var"],
        "https://cognitiveservices.azure.com",
    )
    scope = scope.removesuffix("/.default")
    token = _get_az_cli_token(scope)
    return token, False


# ---------------------------------------------------------------------------
# Image generation API call
# ---------------------------------------------------------------------------

async def _call_api(
    client: httpx.AsyncClient,
    prompt: str,
    size: str,
    url: str,
    headers: dict[str, str],
    quality: str,
    timeout: float,
    *,
    negative_prompt: str | None = None,
    seed: int | None = None,
    supports_negative_prompt: bool = False,
    supports_seed: bool = False,
) -> tuple[bytes, str | None]:
    """Call Azure image generation API. Returns (image_bytes, revised_prompt)."""
    body: dict[str, Any] = {
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": quality,
    }
    if negative_prompt and supports_negative_prompt:
        body["negative_prompt"] = negative_prompt
    if seed is not None and supports_seed:
        body["seed"] = seed

    response = await client.post(url, json=body, headers=headers, timeout=timeout)
    response.raise_for_status()

    data = response.json()
    item = (data.get("data") or [{}])[0]
    b64 = item.get("b64_json")
    if not b64:
        raise RuntimeError("No image data returned from API")

    image_bytes = base64.b64decode(b64)
    return image_bytes, item.get("revised_prompt")


def _save_image(image_data: bytes, output_dir: Path, filename: str,
                relative_to: Path | None = None) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / filename
    image_path.write_bytes(image_data)
    if relative_to is not None:
        return str(image_path.resolve().relative_to(relative_to.resolve()))
    return str(image_path.resolve())


# ---------------------------------------------------------------------------
# Concurrency runner
# ---------------------------------------------------------------------------

async def _run_concurrent(
    tasks: list[Any],
    concurrency: int,
    worker: Any,
) -> None:
    sem = asyncio.Semaphore(concurrency)

    async def bounded(task: Any) -> None:
        async with sem:
            await worker(task)

    await asyncio.gather(*(bounded(t) for t in tasks))


# ---------------------------------------------------------------------------
# Backend resolver (handles per-request backend override)
# ---------------------------------------------------------------------------

@dataclass
class ResolvedBackend:
    name: str
    url: str
    headers: dict[str, str]
    quality: str
    timeout: float
    deployment: str
    supports_negative_prompt: bool
    supports_seed: bool


def _resolve_backend(
    backend_name: str,
    auth_cache: dict[str, tuple[str, bool]],
) -> ResolvedBackend:
    """Resolve a backend name to its API URL, headers, and config."""
    cfg = BACKENDS[backend_name]
    endpoint = os.environ.get(cfg["endpoint_var"], "").rstrip("/")
    deployment = os.environ.get(cfg["deployment_var"], "")
    api_version = os.environ.get(cfg["api_version_var"], cfg["default_api_version"])
    timeout = float(os.environ.get(cfg["timeout_var"], str(cfg["default_timeout"])))

    if not endpoint or not deployment:
        raise RuntimeError(
            f"{cfg['endpoint_var']} and {cfg['deployment_var']} must be set"
        )

    url = cfg["url_template"].format(
        endpoint=endpoint, deployment=deployment, api_version=api_version,
    )

    # Cache auth per backend to avoid repeated token fetches
    if backend_name not in auth_cache:
        auth_cache[backend_name] = resolve_auth(cfg)
    token, is_api_key = auth_cache[backend_name]

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if is_api_key:
        headers["api-key"] = token
    else:
        headers["Authorization"] = f"Bearer {token}"

    return ResolvedBackend(
        name=backend_name,
        url=url,
        headers=headers,
        quality=cfg["default_quality"],
        timeout=timeout,
        deployment=deployment,
        supports_negative_prompt=cfg["supports_negative_prompt"],
        supports_seed=cfg["supports_seed"],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def async_main() -> None:
    # Fix broken SSL_CERT_FILE (common in conda envs on Windows)
    ssl_cert = os.environ.get("SSL_CERT_FILE", "")
    if ssl_cert and not Path(ssl_cert).is_file():
        try:
            import certifi
            os.environ["SSL_CERT_FILE"] = certifi.where()
        except ImportError:
            del os.environ["SSL_CERT_FILE"]

    # Load .env from project root (4 levels up from scripts/)
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    env_path = project_root / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
    elif Path(".env").is_file():
        load_dotenv(Path(".env"))

    parser = argparse.ArgumentParser(
        description="Standalone batch image generation tool",
    )
    parser.add_argument(
        "request_json", type=Path,
        help="Path to image request JSON file",
    )
    parser.add_argument(
        "-w", "--work-dir", type=Path, default=None,
        help="Working directory: images go to <dir>/images/, JSON report to <dir>/",
    )
    parser.add_argument(
        "--backend", choices=["gpt-image", "flux"], default="gpt-image",
        help="Default image generation backend (default: gpt-image)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=None,
        help="Parallel image generation workers",
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=None,
        help="Output directory for images (default: <input_dir>/images/)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List tasks without generating images",
    )
    parser.add_argument(
        "--report-name", type=str, default="image_generation_output.json",
        help="Filename for the output JSON report (default: image_generation_output.json)",
    )
    parser.add_argument(
        "--no-crop", action="store_true",
        help="Disable C-6 aspect-ratio post-crop. By default, when the "
             "API-supported size differs from the requested aspect by "
             ">15%%, the saved image is center-cropped to the requested "
             "aspect ratio so accent / banner zones don't get a "
             "square-ish image instead of the band they asked for.",
    )
    args = parser.parse_args()

    # Parse input
    resolved_path = args.request_json.resolve()
    if not resolved_path.is_file():
        print(f"Error: file not found: {resolved_path}", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(resolved_path.read_text("utf-8"))
    requests = parse_requests(raw)

    if not requests:
        print("No image requests found in input file.")
        return

    # Track original request count before expansion
    original_count = len(requests)
    variation_requests = sum(1 for r in requests if r.variations > 1)

    # Expand variations: requests with variations > 1 become N individual tasks
    tasks = expand_variations(requests)

    # Output dirs — work_dir governs both images and JSON; -o overrides image dir only
    work_dir = args.work_dir.resolve() if args.work_dir else None
    output_dir = (
        args.output_dir.resolve() if args.output_dir
        else (work_dir / "images") if work_dir
        else resolved_path.parent / "images"
    ).resolve()
    report_dir = (work_dir if work_dir else resolved_path.parent).resolve()
    default_backend = args.backend
    default_concurrency = (
        args.concurrency
        or BACKENDS[default_backend]["default_concurrency"]
    )

    # Print summary
    backend_counts: dict[str, int] = {}
    for req in tasks:
        b = req.backend or default_backend
        backend_counts[b] = backend_counts.get(b, 0) + 1

    print(f"Requests:    {original_count}")
    if variation_requests:
        print(f"  with variations: {variation_requests} (expanded to {len(tasks)} tasks)")
    for b, cnt in backend_counts.items():
        print(f"  {b}: {cnt}")
    print(f"Concurrency: {default_concurrency}")
    print(f"Output dir:  {output_dir}\n")

    # Dry run
    if args.dry_run:
        print("=== DRY RUN — no images will be generated ===\n")
        for req in tasks:
            b = req.backend or default_backend
            size = _pick_api_size(req.width, req.height)
            var_info = f"  (variation {req.variation_index} of {req.variation_of})" if req.variation_index else ""
            print(f"  [{req.id}] backend={b}  size={size}  quality={req.quality}  "
                  f"file={req.resolved_filename()}{var_info}")
            print(f"    prompt=\"{_preview(req.prompt)}\"")
            if req.style_reference:
                print(f"    style_reference=\"{_preview(req.style_reference, 60)}\"")
            if req.negative_prompt:
                print(f"    negative_prompt=\"{_preview(req.negative_prompt, 60)}\"")
        print(f"\nTotal: {original_count} request(s), {len(tasks)} task(s)")
        return

    # Resolve backends and auth
    auth_cache: dict[str, tuple[str, bool]] = {}
    backend_cache: dict[str, ResolvedBackend] = {}

    needed_backends = {req.backend or default_backend for req in tasks}

    # Check enabled status before resolving auth / making API calls
    disabled = [b for b in needed_backends if not _is_backend_enabled(b)]
    if disabled:
        for b in disabled:
            cfg = BACKENDS[b]
            print(f"WARNING: backend '{b}' is disabled "
                  f"(set {cfg['enabled_var']}=true to re-enable)",
                  file=sys.stderr)
        # Remap disabled-backend tasks to default_backend if it's enabled
        if default_backend not in disabled:
            remapped = 0
            for req in tasks:
                effective = req.backend or default_backend
                if effective in disabled:
                    req.backend = default_backend
                    remapped += 1
            if remapped:
                print(f"  → {remapped} task(s) remapped to '{default_backend}'")
            # Recalculate needed backends after remapping
            needed_backends = {req.backend or default_backend for req in tasks}
        else:
            # All needed backends are disabled — nothing to do
            print("ERROR: all needed backends are disabled. Aborting.",
                  file=sys.stderr)
            sys.exit(1)

    for bname in needed_backends:
        backend_cache[bname] = _resolve_backend(bname, auth_cache)

    # Generate
    stats = Stats()
    results: list[ImageResult] = []

    async with httpx.AsyncClient() as client:

        async def worker(req: ImageRequest) -> None:
            bname = req.backend or default_backend
            be = backend_cache[bname]
            filename = req.resolved_filename()
            dest = output_dir / filename

            # Idempotent: skip if output already exists
            if dest.is_file():
                print(f"  [{req.id}] SKIP (already exists: {filename})")
                stats.skipped += 1
                rel_path = str(dest.resolve().relative_to(report_dir)) if report_dir else str(dest)
                results.append(ImageResult(
                    id=req.id, status="skipped",
                    output_path=rel_path, backend=bname,
                    variation=req.variation_index or None,
                    variation_of=req.variation_of or None,
                ))
                return

            composed_prompt = _build_prompt(req.prompt, req.style_reference)
            size = _pick_api_size(req.width, req.height)
            quality = req.quality or be.quality

            # C-5: auto-augment negative prompt for accent / atmospheric.
            effective_neg = _augment_negative_prompt(req)

            # C-6: warn loudly when the API-snapped aspect drifts from
            # the requested aspect by more than the threshold. The
            # caller's intended aspect is then restored via a center
            # crop after the image is written, unless --no-crop is set.
            mismatch = _aspect_mismatch_pct(req.width, req.height, size)
            if mismatch > ASPECT_MISMATCH_WARN_THRESHOLD:
                print(
                    f"  [{req.id}] ! aspect-ratio drift: requested "
                    f"{req.width}x{req.height} (ratio {req.width/req.height:.2f}); "
                    f"API will return {size} (drift {mismatch*100:.0f}%). "
                    + ("Will center-crop output to requested aspect."
                       if not args.no_crop
                       else "Crop disabled (--no-crop).")
                )

            print(f"  [{req.id}] backend={bname}  size={size}  "
                  f"quality={quality}  prompt=\"{_preview(req.prompt)}\"")
            try:
                image_bytes, revised = await _call_api(
                    client, composed_prompt, size,
                    be.url, be.headers, quality, be.timeout,
                    negative_prompt=effective_neg,
                    seed=req.seed,
                    supports_negative_prompt=be.supports_negative_prompt,
                    supports_seed=be.supports_seed,
                )
                img_path = _save_image(image_bytes, output_dir, filename,
                                       relative_to=report_dir)

                # C-6: post-crop to requested aspect if drift is large.
                if (mismatch > ASPECT_MISMATCH_WARN_THRESHOLD
                        and not args.no_crop):
                    cropped_ok = _crop_to_aspect(
                        output_dir / filename, req.width, req.height
                    )
                    if not cropped_ok:
                        print(
                            f"  [{req.id}] ! crop failed (Pillow missing or "
                            f"image error); kept full {size} image."
                        )

                stats.generated += 1
                results.append(ImageResult(
                    id=req.id, status="success",
                    output_path=img_path,
                    revised_prompt=revised,
                    backend=bname,
                    model=be.deployment,
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    variation=req.variation_index or None,
                    variation_of=req.variation_of or None,
                ))
                # Isolate the success log from the generation try/except —
                # a print failure (e.g. console encoding) must not be
                # mistaken for a generation failure. See retrospective I-02.
                try:
                    print(f"  [{req.id}] ✓ -> {filename}")
                except Exception:
                    pass
            except Exception as e:
                stats.failed += 1
                results.append(ImageResult(
                    id=req.id, status="failed",
                    error=str(e), backend=bname,
                    variation=req.variation_index or None,
                    variation_of=req.variation_of or None,
                ))
                try:
                    print(f"  [{req.id}] ✗ {e}", file=sys.stderr)
                except Exception:
                    pass

        print("Generating images...")
        await _run_concurrent(tasks, default_concurrency, worker)

    # Write output JSON
    output_json_path = report_dir / args.report_name
    output_data = {
        "results": [
            {k: v for k, v in r.__dict__.items() if v is not None}
            for r in results
        ],
        "summary": {
            "total_requests": original_count,
            "total_tasks": len(tasks),
            "generated": stats.generated,
            "skipped": stats.skipped,
            "failed": stats.failed,
        },
    }
    output_json_path.write_text(
        json.dumps(output_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Summary
    print(f"\n=== Image Generation Summary ===")
    print(f"  Requests  : {original_count}")
    if len(tasks) != original_count:
        print(f"  Tasks     : {len(tasks)} (with variations)")
    print(f"  Generated : {stats.generated}")
    print(f"  Skipped   : {stats.skipped}")
    print(f"  Failed    : {stats.failed}")
    print(f"\nOutput JSON: {output_json_path}")

    if stats.failed > 0:
        sys.exit(1)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
