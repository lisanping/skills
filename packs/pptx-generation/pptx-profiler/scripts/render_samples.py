"""Render each sample slide in a .potx/.pptx template as a standalone image.

Produces one JPEG per slide found in the template's <p:sldIdLst>.
Only slides with substantive text content (not just placeholder markers)
are considered "samples", but all slides in sldIdLst are rendered so the
caller can decide which to use.

Rendering backends (auto-detected):
  1. PowerPoint COM (Windows + Office installed) — best quality
  2. LibreOffice headless + pdftoppm (Docker/Linux) — fallback

Requires: Pillow. Optional: pywin32 (Windows), soffice + pdftoppm (Linux).

Usage:
    python render_samples.py template.potx -o sample-slides/
    python render_samples.py template.pptx -o sample-slides/ --width 1920

Output structure:
    sample-slides/
        slide1.jpg
        slide2.jpg
        ...
"""

import argparse
import platform
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import defusedxml.minidom
from PIL import Image

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_WIDTH_PX = 1280
JPEG_QUALITY = 95
CONVERSION_DPI = 150

# ---------------------------------------------------------------------------
# Slide enumeration from template ZIP
# ---------------------------------------------------------------------------


def _get_sample_slides(pptx_path: Path) -> list[dict]:
    """Return list of slides in presentation order from <p:sldIdLst>.

    Each entry: {"name": "slide1.xml", "hidden": bool}
    """
    with zipfile.ZipFile(pptx_path, "r") as zf:
        rels_content = zf.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
        rels_dom = defusedxml.minidom.parseString(rels_content)

        rid_to_slide: dict[str, str] = {}
        for rel in rels_dom.getElementsByTagName("Relationship"):
            rid = rel.getAttribute("Id")
            target = rel.getAttribute("Target")
            rel_type = rel.getAttribute("Type")
            if "slide" in rel_type and target.startswith("slides/"):
                rid_to_slide[rid] = target.replace("slides/", "")

        pres_content = zf.read("ppt/presentation.xml").decode("utf-8")
        pres_dom = defusedxml.minidom.parseString(pres_content)

        slides = []
        for sld_id in pres_dom.getElementsByTagName("p:sldId"):
            rid = sld_id.getAttribute("r:id")
            if rid in rid_to_slide:
                hidden = sld_id.getAttribute("show") == "0"
                slides.append({"name": rid_to_slide[rid], "hidden": hidden})

        return slides


# ---------------------------------------------------------------------------
# Rendering backends
# ---------------------------------------------------------------------------


def _powerpoint_available() -> bool:
    """Check if PowerPoint COM automation is available (Windows + Office)."""
    if platform.system() != "Windows":
        return False
    try:
        import win32com.client  # noqa: F401

        return True
    except ImportError:
        return False


def _libreoffice_available() -> bool:
    """Check if soffice (LibreOffice) is on PATH."""
    try:
        result = subprocess.run(
            ["soffice", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _get_soffice_env():
    """Build env dict for running soffice, with SVP plugin for headless."""
    import os

    env = os.environ.copy()
    env["SAL_USE_VCLPLUGIN"] = "svp"
    return env


def _render_via_powerpoint(
    pptx_path: Path, out_dir: Path, width: int
) -> list[Path]:
    """Export each visible slide to PNG using PowerPoint COM automation.

    Copies the file to a temp directory first to avoid issues with
    OneDrive-synced paths or paths containing special characters.
    """
    import pythoncom
    import shutil

    import win32com.client

    # Copy to temp dir — COM automation can fail on OneDrive/cloud paths
    tmp_dir = Path(tempfile.mkdtemp(prefix="render_samples_"))
    tmp_pptx = tmp_dir / pptx_path.name
    shutil.copy2(pptx_path.resolve(), tmp_pptx)
    abs_path = str(tmp_pptx)

    pythoncom.CoInitialize()
    pptx_app = None
    prs = None
    images: list[Path] = []
    try:
        pptx_app = win32com.client.Dispatch("PowerPoint.Application")
        try:
            prs = pptx_app.Presentations.Open(
                abs_path, ReadOnly=True, WithWindow=False
            )
        except Exception:
            pptx_app.AutomationSecurity = 3
            prs = pptx_app.Presentations.Open(
                abs_path, ReadOnly=False, WithWindow=False
            )

        slide_w = prs.PageSetup.SlideWidth
        slide_h = prs.PageSetup.SlideHeight
        height = (
            int(width * slide_h / slide_w) if slide_w > 0 else int(width * 9 / 16)
        )

        for slide in prs.Slides:
            idx = slide.SlideIndex
            out_path = out_dir / f"page-{idx:03d}.png"
            slide.Export(str(out_path), "PNG", width, height)
            images.append(out_path)
    finally:
        if prs:
            prs.Close()
        if pptx_app:
            pptx_app.Quit()
        pythoncom.CoUninitialize()
        # Clean up temp copy
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return sorted(images)


def _render_via_libreoffice(
    pptx_path: Path, out_dir: Path, dpi: int
) -> list[Path]:
    """Convert PPTX to per-page JPEG via LibreOffice + pdftoppm."""
    pdf_path = out_dir / f"{pptx_path.stem}.pdf"

    result = subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(pptx_path),
        ],
        capture_output=True,
        text=True,
        env=_get_soffice_env(),
    )
    if result.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(
            f"LibreOffice PDF conversion failed: {result.stderr.strip()}"
        )

    result = subprocess.run(
        [
            "pdftoppm",
            "-jpeg",
            "-r",
            str(dpi),
            str(pdf_path),
            str(out_dir / "page"),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftoppm failed: {result.stderr.strip()}")

    return sorted(out_dir.glob("page-*.*"))


def _render_to_images(
    pptx_path: Path, out_dir: Path, width_px: int
) -> list[Path]:
    """Render PPTX to per-slide images using the best available backend."""
    if _powerpoint_available():
        return _render_via_powerpoint(pptx_path, out_dir, width_px)
    elif _libreoffice_available():
        # Estimate DPI from slide width for target pixel width
        try:
            with zipfile.ZipFile(pptx_path, "r") as zf:
                pres_bytes = zf.read("ppt/presentation.xml")
                pres_dom = defusedxml.minidom.parseString(pres_bytes)
                sz_el = pres_dom.getElementsByTagName("p:sldSz")
                if sz_el:
                    cx_emu = int(sz_el[0].getAttribute("cx") or "12192000")
                else:
                    cx_emu = 12192000
        except Exception:
            cx_emu = 12192000

        slide_width_inches = cx_emu / 914400
        dpi = (
            int(width_px / slide_width_inches)
            if slide_width_inches > 0
            else CONVERSION_DPI
        )
        return _render_via_libreoffice(pptx_path, out_dir, dpi)
    else:
        raise RuntimeError(
            "No rendering backend available. Install either:\n"
            "  - Microsoft PowerPoint (Windows) with pywin32, or\n"
            "  - LibreOffice headless + poppler-utils (pdftoppm)"
        )


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def render_samples(
    template_path: Path,
    output_dir: Path,
    width_px: int = DEFAULT_WIDTH_PX,
) -> list[dict]:
    """Render all sample slides as individual JPEG images.

    Returns a list of dicts:
        [{"slide_file": "slide1.xml", "image": "slide1.jpg", "hidden": False}]
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    slide_info = _get_sample_slides(template_path)
    if not slide_info:
        print("No sample slides found in template.", file=sys.stderr)
        return []

    print(f"  Found {len(slide_info)} slide(s) in template.")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rendered_images = _render_to_images(template_path, tmp_path, width_px)

        if not rendered_images:
            print("Error: Rendering produced no images.", file=sys.stderr)
            return []

        results = []
        visible_idx = 0

        for info in slide_info:
            slide_stem = info["name"].replace(".xml", "")

            if info["hidden"]:
                # Skip hidden slides — no rendered image produced
                results.append(
                    {
                        "slide_file": info["name"],
                        "image": None,
                        "hidden": True,
                    }
                )
                print(f"    {info['name']:20s}  (hidden, skipped)")
                continue

            if visible_idx >= len(rendered_images):
                print(
                    f"  Warning: No rendered image for {info['name']}",
                    file=sys.stderr,
                )
                break

            # Convert to JPEG at target quality, save with slide name
            out_path = output_dir / f"{slide_stem}.jpg"
            with Image.open(rendered_images[visible_idx]) as img:
                img.convert("RGB").save(str(out_path), "JPEG", quality=JPEG_QUALITY)

            results.append(
                {
                    "slide_file": info["name"],
                    "image": f"{slide_stem}.jpg",
                    "hidden": False,
                }
            )
            print(f"    {info['name']:20s}  -> {out_path.name}")
            visible_idx += 1

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Render each sample slide in a template as a preview image."
    )
    parser.add_argument(
        "input",
        help="Input PowerPoint template (.potx or .pptx)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="sample-slides",
        help="Output directory for slide images (default: sample-slides/)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH_PX,
        help=f"Output image width in pixels (default: {DEFAULT_WIDTH_PX}). "
        "Height is calculated from the slide aspect ratio.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    if input_path.suffix.lower() not in (".pptx", ".potx"):
        print(f"Error: Expected .pptx or .potx file: {args.input}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output)

    print(f"Rendering sample slides from {input_path.name}...")
    results = render_samples(input_path, output_dir, width_px=args.width)

    if not results:
        print("No sample slides were rendered.", file=sys.stderr)
        sys.exit(1)

    visible = [r for r in results if not r["hidden"]]
    hidden = [r for r in results if r["hidden"]]
    print(f"\nDone. {len(visible)} slide(s) rendered to {output_dir}/")
    if hidden:
        print(f"  ({len(hidden)} hidden slide(s) skipped)")


if __name__ == "__main__":
    main()
