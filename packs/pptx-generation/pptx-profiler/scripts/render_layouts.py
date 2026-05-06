"""Render each slideLayout in a .potx/.pptx template as standalone images.

Produces two image types per layout:
  1. Clean preview  — the layout rendered as-is
  2. Annotated preview — clean preview overlaid with placeholder bounding
     boxes, placeholder types, and key font/paragraph properties

Rendering backends (auto-detected):
  1. PowerPoint COM (Windows + Office installed) — best quality
  2. LibreOffice headless + pdftoppm (Docker/Linux) — fallback

Requires: Pillow. Optional: pywin32 (Windows), soffice + pdftoppm (Linux).

Usage:
    python render_layouts.py template.potx -o layout-previews/
    python render_layouts.py template.pptx -o layout-previews/ --width 1920

Output structure:
    layout-previews/
        slideLayout1.jpg                  # clean preview
        slideLayout1_annotated.jpg        # annotated with placeholders
        slideLayout2.jpg
        slideLayout2_annotated.jpg
        ...
"""

import argparse
import os
import platform
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_WIDTH_PX = 1280
JPEG_QUALITY = 95
ANNOTATION_FONT_SIZE = 14
LABEL_FONT_SIZE = 11
BOX_ALPHA = 50  # transparency of fill overlay (0-255)

# OOXML namespaces
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}

REL_SLIDE_LAYOUT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
)
REL_SLIDE_MASTER = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"
)
REL_SLIDE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
)

# Distinct colors for different placeholder types
PH_COLORS = {
    "title": (220, 50, 50),      # red
    "ctrTitle": (220, 50, 50),    # red
    "subTitle": (230, 120, 50),   # orange
    "body": (50, 130, 220),       # blue
    "obj": (50, 130, 220),        # blue (object = body variant)
    "tbl": (50, 180, 100),        # green
    "chart": (50, 180, 100),      # green
    "dgm": (50, 180, 100),        # green
    "pic": (160, 80, 200),        # purple
    "clipArt": (160, 80, 200),    # purple
    "media": (160, 80, 200),      # purple
    "dt": (128, 128, 128),        # gray (date)
    "ftr": (128, 128, 128),       # gray (footer)
    "sldNum": (128, 128, 128),    # gray (slide number)
    "hdr": (128, 128, 128),       # gray (header)
}
DEFAULT_PH_COLOR = (80, 80, 80)


# ---------------------------------------------------------------------------
# Rendering backends
# ---------------------------------------------------------------------------

def _powerpoint_available() -> bool:
    """Check if PowerPoint COM automation is available (Windows + Office)."""
    if platform.system() != "Windows":
        return False
    try:
        import win32com.client
        return True
    except ImportError:
        return False


def _libreoffice_available() -> bool:
    """Check if soffice (LibreOffice) is on PATH."""
    try:
        result = subprocess.run(
            ["soffice", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _render_via_powerpoint(pptx_path: Path, out_dir: Path, width: int) -> list[Path]:
    """Render PPTX slides to PNG using PowerPoint COM automation."""
    import pythoncom
    import win32com.client

    abs_path = str(pptx_path.resolve())

    pythoncom.CoInitialize()
    pptx_app = None
    prs = None
    images: list[Path] = []
    try:
        pptx_app = win32com.client.Dispatch("PowerPoint.Application")
        try:
            prs = pptx_app.Presentations.Open(abs_path, ReadOnly=True, WithWindow=False)
        except Exception:
            pptx_app.AutomationSecurity = 3
            prs = pptx_app.Presentations.Open(abs_path, ReadOnly=False, WithWindow=False)

        slide_w = prs.PageSetup.SlideWidth
        slide_h = prs.PageSetup.SlideHeight
        height = int(width * slide_h / slide_w) if slide_w > 0 else int(width * 9 / 16)

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

    return sorted(images)


def _get_soffice_env():
    """Build env dict for running soffice, with SVP plugin."""
    env = os.environ.copy()
    env["SAL_USE_VCLPLUGIN"] = "svp"
    return env


def _render_via_libreoffice(pptx_path: Path, out_dir: Path, dpi: int) -> list[Path]:
    """Render PPTX to per-page JPEG images via LibreOffice + pdftoppm."""
    pdf_path = out_dir / f"{pptx_path.stem}.pdf"

    result = subprocess.run(
        [
            "soffice", "--headless", "--convert-to", "pdf",
            "--outdir", str(out_dir),
            str(pptx_path),
        ],
        capture_output=True, text=True,
        env=_get_soffice_env(),
    )
    if result.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(
            f"LibreOffice PDF conversion failed for {pptx_path.name}: "
            f"{result.stderr.strip()}"
        )

    result = subprocess.run(
        [
            "pdftoppm", "-jpeg", "-r", str(dpi),
            str(pdf_path),
            str(out_dir / "page"),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftoppm failed: {result.stderr.strip()}")

    return sorted(out_dir.glob("page-*.*"))


def _convert_pptx_to_images(
    pptx_path: Path, out_dir: Path, width_px: int, slide_cx_emu: int,
) -> list[Path]:
    """Render a PPTX to images using the best available backend."""
    if _powerpoint_available():
        return _render_via_powerpoint(pptx_path, out_dir, width_px)
    elif _libreoffice_available():
        # Convert desired pixel width to DPI based on actual slide width
        slide_width_inches = slide_cx_emu / 914400
        dpi = int(width_px / slide_width_inches) if slide_width_inches > 0 else 150
        return _render_via_libreoffice(pptx_path, out_dir, dpi)
    else:
        raise RuntimeError(
            "No rendering backend available. Install either:\n"
            "  - Microsoft PowerPoint (Windows) with pywin32, or\n"
            "  - LibreOffice headless + poppler-utils (pdftoppm)"
        )


# ---------------------------------------------------------------------------
# OOXML ZIP helpers
# ---------------------------------------------------------------------------

def _read_xml(zf: zipfile.ZipFile, path: str) -> ET.Element | None:
    try:
        with zf.open(path) as f:
            return ET.parse(f).getroot()
    except (KeyError, ET.ParseError):
        return None


def _rels_path(part_path: str) -> str:
    d = posixpath.dirname(part_path)
    name = posixpath.basename(part_path)
    return posixpath.join(d, "_rels", name + ".rels")


def _resolve_target(part_path: str, target: str) -> str:
    base = posixpath.dirname(part_path)
    return posixpath.normpath(posixpath.join(base, target))


def _parse_rels(zf: zipfile.ZipFile, part_path: str) -> dict[str, list[dict]]:
    root = _read_xml(zf, _rels_path(part_path))
    if root is None:
        return {}
    by_type: dict[str, list[dict]] = {}
    for rel in root.findall(f"{{{NS['pkg']}}}Relationship"):
        rtype = rel.get("Type", "")
        rid = rel.get("Id", "")
        target = _resolve_target(part_path, rel.get("Target", ""))
        by_type.setdefault(rtype, []).append({"id": rid, "target": target})
    return by_type


# ---------------------------------------------------------------------------
# Slide size extraction
# ---------------------------------------------------------------------------

def _get_slide_size_emu(zf: zipfile.ZipFile) -> tuple[int, int]:
    """Return (cx, cy) in EMU from presentation.xml."""
    pres = _read_xml(zf, "ppt/presentation.xml")
    if pres is None:
        return 12192000, 6858000  # default 16:9
    sz = pres.find(f"{{{NS['p']}}}sldSz")
    if sz is None:
        return 12192000, 6858000
    return int(sz.get("cx", "12192000")), int(sz.get("cy", "6858000"))


# ---------------------------------------------------------------------------
# Brand master detection (skip "Office Theme")
# ---------------------------------------------------------------------------

def _is_office_theme(name: str) -> bool:
    n = name.lower().strip()
    return n in ("office theme", "office", "") or n.startswith("office theme")


def _find_brand_master(zf: zipfile.ZipFile) -> tuple[str, list[str]]:
    """Return (master_path, [layout_paths]) for the brand master.

    Skips the default 'Office Theme' master if a brand master exists.
    """
    pres_rels = _parse_rels(zf, "ppt/presentation.xml")
    master_entries = pres_rels.get(REL_SLIDE_MASTER, [])

    candidates: list[tuple[str, list[str], str]] = []
    for entry in master_entries:
        master_path = entry["target"]
        master_xml = _read_xml(zf, master_path)
        if master_xml is None:
            continue

        # Get theme name
        master_rels = _parse_rels(zf, master_path)
        theme_name = ""
        theme_entries = master_rels.get(
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme",
            [],
        )
        if theme_entries:
            theme_xml = _read_xml(zf, theme_entries[0]["target"])
            if theme_xml is not None:
                theme_name = theme_xml.get("name", "")

        layout_entries = master_rels.get(REL_SLIDE_LAYOUT, [])
        layout_paths = [e["target"] for e in layout_entries]
        candidates.append((master_path, layout_paths, theme_name))

    if not candidates:
        return "", []

    # Prefer non-Office Theme master; among those, pick the one with the most layouts
    brand = [c for c in candidates if not _is_office_theme(c[2])]
    if brand:
        brand.sort(key=lambda c: len(c[1]), reverse=True)
        return brand[0][0], brand[0][1]
    candidates.sort(key=lambda c: len(c[1]), reverse=True)
    return candidates[0][0], candidates[0][1]


# ---------------------------------------------------------------------------
# Layout name extraction
# ---------------------------------------------------------------------------

def _get_layout_name(zf: zipfile.ZipFile, layout_path: str) -> str:
    """Return the human-readable layout name from cSld/@name."""
    root = _read_xml(zf, layout_path)
    if root is None:
        return posixpath.basename(layout_path)
    csld = root.find(f"{{{NS['p']}}}cSld")
    if csld is not None:
        name = csld.get("name", "")
        if name:
            return name
    return posixpath.basename(layout_path).replace(".xml", "")


# ---------------------------------------------------------------------------
# Placeholder extraction from layout XML
# ---------------------------------------------------------------------------

def _extract_color_value(container: ET.Element) -> str | None:
    srgb = container.find(f"{{{NS['a']}}}srgbClr")
    if srgb is not None:
        v = srgb.get("val", "")
        return f"#{v}" if v else None
    sys_clr = container.find(f"{{{NS['a']}}}sysClr")
    if sys_clr is not None:
        v = sys_clr.get("lastClr", "") or sys_clr.get("val", "")
        return f"#{v}" if v else None
    scheme_clr = container.find(f"{{{NS['a']}}}schemeClr")
    if scheme_clr is not None:
        return scheme_clr.get("val")
    return None


def _emu_to_pct(emu: int, total: int) -> float:
    if total == 0:
        return 0.0
    return emu / total * 100


_ALGN_LABELS = {
    "l": "Left",
    "ctr": "Center",
    "r": "Right",
    "just": "Justify",
    "dist": "Distribute",
}

_ANCHOR_LABELS = {
    "t": "Top",
    "ctr": "Middle",
    "b": "Bottom",
}


def _parse_placeholder_info(sp: ET.Element, cx: int, cy: int) -> dict | None:
    """Extract placeholder info for annotation overlay."""
    ph = sp.find(f".//{{{NS['p']}}}ph")
    if ph is None:
        return None

    ph_type = ph.get("type", "body")
    ph_idx = int(ph.get("idx", "0"))

    # Position in EMU
    x = y = w = h = 0
    xfrm = sp.find(f".//{{{NS['a']}}}xfrm")
    if xfrm is not None:
        off = xfrm.find(f"{{{NS['a']}}}off")
        ext = xfrm.find(f"{{{NS['a']}}}ext")
        if off is not None:
            x, y = int(off.get("x", "0")), int(off.get("y", "0"))
        if ext is not None:
            w, h = int(ext.get("cx", "0")), int(ext.get("cy", "0"))

    # Name
    name = ""
    nvSpPr = sp.find(f"{{{NS['p']}}}nvSpPr")
    if nvSpPr is not None:
        cNvPr = nvSpPr.find(f"{{{NS['p']}}}cNvPr")
        if cNvPr is not None:
            name = cNvPr.get("name", "")

    # Font and paragraph properties
    font_size = None
    font_color = None
    font_bold = None
    font_name = None
    alignment = None
    anchor = None
    auto_fit = None
    line_spacing = None
    space_before = None
    space_after = None
    margin_left = None
    bullet_type = None

    bodyPr = sp.find(f".//{{{NS['a']}}}bodyPr")
    if bodyPr is not None:
        anchor = bodyPr.get("anchor")

        if bodyPr.find(f"{{{NS['a']}}}spAutoFit") is not None:
            auto_fit = "shape"
        elif bodyPr.find(f"{{{NS['a']}}}normAutofit") is not None:
            auto_fit = "normal"
        else:
            auto_fit = "none"

    txBody = sp.find(f"{{{NS['p']}}}txBody")
    if txBody is not None:
        # First paragraph properties
        first_pPr = txBody.find(f".//{{{NS['a']}}}pPr")
        if first_pPr is not None:
            alignment = first_pPr.get("algn")
            marL = first_pPr.get("marL")
            if marL is not None:
                margin_left = round(int(marL) / 12700, 1)

            # Line spacing
            lnSpc = first_pPr.find(f"{{{NS['a']}}}lnSpc")
            if lnSpc is not None:
                spcPct = lnSpc.find(f"{{{NS['a']}}}spcPct")
                spcPts = lnSpc.find(f"{{{NS['a']}}}spcPts")
                if spcPct is not None:
                    val = int(spcPct.get("val", "100000"))
                    line_spacing = f"{val / 1000:.0f}%"
                elif spcPts is not None:
                    val = int(spcPts.get("val", "0"))
                    line_spacing = f"{val / 100:.1f}pt"

            # Space before
            spcBef = first_pPr.find(f"{{{NS['a']}}}spcBef")
            if spcBef is not None:
                pts = spcBef.find(f"{{{NS['a']}}}spcPts")
                if pts is not None:
                    space_before = f"{int(pts.get('val', '0')) / 100:.1f}pt"

            # Space after
            spcAft = first_pPr.find(f"{{{NS['a']}}}spcAft")
            if spcAft is not None:
                pts = spcAft.find(f"{{{NS['a']}}}spcPts")
                if pts is not None:
                    space_after = f"{int(pts.get('val', '0')) / 100:.1f}pt"

            # Bullet type
            if first_pPr.find(f"{{{NS['a']}}}buChar") is not None:
                char = first_pPr.find(f"{{{NS['a']}}}buChar").get("char", "")
                bullet_type = f"buChar '{char}'"
            elif first_pPr.find(f"{{{NS['a']}}}buAutoNum") is not None:
                num_type = first_pPr.find(f"{{{NS['a']}}}buAutoNum").get("type", "")
                bullet_type = f"buAutoNum({num_type})"
            elif first_pPr.find(f"{{{NS['a']}}}buNone") is not None:
                bullet_type = "none"

        # Font from defRPr or first rPr
        for tag in (f"{{{NS['a']}}}defRPr", f"{{{NS['a']}}}rPr"):
            rpr = txBody.find(f".//{tag}")
            if rpr is None:
                continue
            sz = rpr.get("sz")
            if sz and font_size is None:
                font_size = round(int(sz) / 100, 1)
            b = rpr.get("b")
            if b is not None and font_bold is None:
                font_bold = b == "1"
            sf = rpr.find(f"{{{NS['a']}}}solidFill")
            if sf is not None and font_color is None:
                font_color = _extract_color_value(sf)

            # Font name from <a:latin typeface="..."/>
            latin = rpr.find(f"{{{NS['a']}}}latin")
            if latin is not None and font_name is None:
                tf = latin.get("typeface", "")
                if tf and not tf.startswith("+"):
                    font_name = tf

    # Build property labels for annotation
    props = []
    if font_name:
        props.append(f"Font: {font_name}")
    if font_size is not None:
        bold_mark = " B" if font_bold else ""
        props.append(f"Size: {font_size}pt{bold_mark}")
    if font_color:
        props.append(f"Color: {font_color}")
    if alignment:
        props.append(f"Align: {_ALGN_LABELS.get(alignment, alignment)}")
    if anchor:
        props.append(f"Anchor: {_ANCHOR_LABELS.get(anchor, anchor)}")
    if line_spacing:
        props.append(f"LineSpacing: {line_spacing}")
    if space_before:
        props.append(f"SpaceBef: {space_before}")
    if space_after:
        props.append(f"SpaceAft: {space_after}")
    if margin_left is not None:
        props.append(f"MarginL: {margin_left}pt")
    if bullet_type:
        props.append(f"Bullet: {bullet_type}")
    if auto_fit and auto_fit != "none":
        props.append(f"AutoFit: {auto_fit}")

    # Keep in sync with extract_template.py _parse_placeholder
    is_meta = ph_type in ("dt", "ftr", "sldNum", "hdr")

    return {
        "type": ph_type,
        "idx": ph_idx,
        "name": name,
        "x_pct": _emu_to_pct(x, cx),
        "y_pct": _emu_to_pct(y, cy),
        "w_pct": _emu_to_pct(w, cx),
        "h_pct": _emu_to_pct(h, cy),
        "is_meta": is_meta,
        "props": props,
    }


def _get_layout_placeholders(
    zf: zipfile.ZipFile, layout_path: str, cx: int, cy: int
) -> list[dict]:
    """Parse all placeholders from a slideLayout XML."""
    root = _read_xml(zf, layout_path)
    if root is None:
        return []

    placeholders = []
    spTree = root.find(f".//{{{NS['p']}}}spTree")
    if spTree is None:
        return []

    for sp in spTree.findall(f"{{{NS['p']}}}sp"):
        ph_info = _parse_placeholder_info(sp, cx, cy)
        if ph_info is not None:
            placeholders.append(ph_info)

    return placeholders


# ---------------------------------------------------------------------------
# Temp PPTX construction — one slide per layout
# ---------------------------------------------------------------------------

def _build_single_layout_pptx(
    src_zip_path: Path,
    layout_path: str,
    master_path: str,
    out_pptx: Path,
) -> None:
    """Create a minimal PPTX with a single blank slide using the given layout.

    Copies the layout, its master, the theme, and all related media from the
    source template ZIP. Rewrites the master's .rels to reference only the
    single layout (PowerPoint fails if master rels reference missing layouts).
    """
    with zipfile.ZipFile(src_zip_path, "r") as src_zf:
        all_names = set(n.replace("\\", "/") for n in src_zf.namelist())

        # Collect all files we need to copy
        files_to_copy: set[str] = set()

        # Layout XML + rels
        files_to_copy.add(layout_path)
        layout_rels_file = _rels_path(layout_path)
        if layout_rels_file in all_names:
            files_to_copy.add(layout_rels_file)

        # Master XML (rels will be rewritten, so don't copy the original)
        files_to_copy.add(master_path)

        # Theme (from master rels)
        master_rels = _parse_rels(src_zf, master_path)
        theme_path = ""
        theme_rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
        theme_rel_id = ""
        for entry in master_rels.get(theme_rel_type, []):
            theme_path = entry["target"]
            theme_rel_id = entry["id"]
            files_to_copy.add(theme_path)
            break

        # Collect media from layout rels (images used by this specific layout)
        layout_rels = _parse_rels(src_zf, layout_path)
        for rel_type, entries in layout_rels.items():
            for entry in entries:
                t = entry["target"]
                if t in all_names:
                    files_to_copy.add(t)

        # Collect media from master rels (excluding other layouts)
        for rel_type, entries in master_rels.items():
            if rel_type == REL_SLIDE_LAYOUT:
                continue  # Skip layout references, we rewrite these
            for entry in entries:
                t = entry["target"]
                if t in all_names:
                    files_to_copy.add(t)

        # Copy all ppt/media/ and ppt/images/ (master background, logos, etc.)
        for name in all_names:
            if name.startswith("ppt/media/") or name.startswith("ppt/images/"):
                files_to_copy.add(name)

        # ── Build rewritten master .rels ──
        # Only keep: theme + the single layout + non-layout rels (images, etc.)
        layout_basename = posixpath.basename(layout_path)
        layout_rel_target = posixpath.relpath(layout_path, posixpath.dirname(master_path))

        # Build new master rels from original, filtering out other layouts
        master_rels_file = _rels_path(master_path)
        new_master_rels_parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        ]
        if master_rels_file in all_names:
            orig_root = _read_xml(src_zf, master_rels_file)
            if orig_root is not None:
                layout_rel_written = False
                for rel in orig_root.findall(f"{{{NS['pkg']}}}Relationship"):
                    rtype = rel.get("Type", "")
                    rid = rel.get("Id", "")
                    target = rel.get("Target", "")
                    if rtype == REL_SLIDE_LAYOUT:
                        # Only include the one layout we need;
                        # use the first layout rId for it
                        if not layout_rel_written:
                            new_master_rels_parts.append(
                                f'  <Relationship Id="{rid}" '
                                f'Type="{REL_SLIDE_LAYOUT}" '
                                f'Target="{layout_rel_target}"/>'
                            )
                            layout_rel_written = True
                    else:
                        new_master_rels_parts.append(
                            f'  <Relationship Id="{rid}" '
                            f'Type="{rtype}" Target="{target}"/>'
                        )
        new_master_rels_parts.append("</Relationships>")
        new_master_rels_xml = "\n".join(new_master_rels_parts)

        # Also rewrite the master XML's <p:sldLayoutIdLst> to reference
        # only the single layout
        master_xml_bytes = src_zf.read(
            next(n for n in src_zf.namelist()
                 if n.replace("\\", "/") == master_path)
        )
        master_xml_str = master_xml_bytes.decode("utf-8")

        # Remove existing sldLayoutIdLst and replace with single entry
        # Find the rId used for our layout in the rewritten rels
        # (it's the first layout rId we kept)
        layout_rid = None
        if master_rels_file in all_names:
            orig_root = _read_xml(src_zf, master_rels_file)
            if orig_root is not None:
                for rel in orig_root.findall(f"{{{NS['pkg']}}}Relationship"):
                    if rel.get("Type", "") == REL_SLIDE_LAYOUT:
                        layout_rid = rel.get("Id", "")
                        break

        if layout_rid:
            # Replace the sldLayoutIdLst block with a single entry
            master_xml_str = re.sub(
                r"<p:sldLayoutIdLst>.*?</p:sldLayoutIdLst>",
                f'<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="{layout_rid}"/></p:sldLayoutIdLst>',
                master_xml_str,
                flags=re.DOTALL,
            )

        master_basename = posixpath.basename(master_path)

        # ── Slide XML ──
        slide_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/>
          <a:ext cx="0" cy="0"/>
          <a:chOff x="0" y="0"/>
          <a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>'''

        slide_rels_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="{REL_SLIDE_LAYOUT}"
    Target="../slideLayouts/{layout_basename}"/>
</Relationships>'''

        # Get slide size
        pres_root = _read_xml(src_zf, "ppt/presentation.xml")
        sz_cx, sz_cy = 12192000, 6858000
        if pres_root is not None:
            sz_el = pres_root.find(f"{{{NS['p']}}}sldSz")
            if sz_el is not None:
                sz_cx = int(sz_el.get("cx", "12192000"))
                sz_cy = int(sz_el.get("cy", "6858000"))

        # ── Presentation XML ──
        pres_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                saveSubsetFonts="1">
  <p:sldMasterIdLst>
    <p:sldMasterId id="2147483648" r:id="rId1"/>
  </p:sldMasterIdLst>
  <p:sldIdLst>
    <p:sldId id="256" r:id="rId2"/>
  </p:sldIdLst>
  <p:sldSz cx="{sz_cx}" cy="{sz_cy}"/>
  <p:notesSz cx="{sz_cy}" cy="{sz_cx}"/>
</p:presentation>'''

        if theme_path:
            theme_rel_target_pres = posixpath.relpath(theme_path, "ppt")
        else:
            theme_rel_target_pres = "theme/theme1.xml"

        pres_rels_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="{REL_SLIDE_MASTER}"
    Target="slideMasters/{master_basename}"/>
  <Relationship Id="rId2"
    Type="{REL_SLIDE}"
    Target="slides/slide1.xml"/>
  <Relationship Id="rId3"
    Type="{theme_rel_type}"
    Target="{theme_rel_target_pres}"/>
</Relationships>'''

        content_types_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Default Extension="jpg" ContentType="image/jpeg"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="gif" ContentType="image/gif"/>
  <Default Extension="svg" ContentType="image/svg+xml"/>
  <Default Extension="emf" ContentType="image/x-emf"/>
  <Default Extension="wmf" ContentType="image/x-wmf"/>
  <Override PartName="/ppt/presentation.xml"
    ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml"
    ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
  <Override PartName="/ppt/slideMasters/{master_basename}"
    ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/{layout_basename}"
    ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/{theme_path}"
    ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
</Types>'''

        top_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="ppt/presentation.xml"/>
</Relationships>'''

        with zipfile.ZipFile(out_pptx, "w", zipfile.ZIP_DEFLATED) as out_zf:
            # Copy template files (layout, theme, media — but NOT master or master rels)
            for fname in files_to_copy:
                if fname == master_path or fname == master_rels_file:
                    continue  # We write rewritten versions below
                for src_name in src_zf.namelist():
                    if src_name.replace("\\", "/") == fname:
                        out_zf.writestr(fname, src_zf.read(src_name))
                        break

            # Write rewritten master XML and rels
            out_zf.writestr(master_path, master_xml_str.encode("utf-8"))
            out_zf.writestr(master_rels_file, new_master_rels_xml)

            # Write generated files
            out_zf.writestr("[Content_Types].xml", content_types_xml)
            out_zf.writestr("_rels/.rels", top_rels_xml)
            out_zf.writestr("ppt/presentation.xml", pres_xml)
            out_zf.writestr("ppt/_rels/presentation.xml.rels", pres_rels_xml)
            out_zf.writestr("ppt/slides/slide1.xml", slide_xml)
            out_zf.writestr("ppt/slides/_rels/slide1.xml.rels", slide_rels_xml)


# ---------------------------------------------------------------------------
# Annotation drawing
# ---------------------------------------------------------------------------

def _draw_annotations(
    base_image: Image.Image,
    placeholders: list[dict],
    layout_name: str,
) -> Image.Image:
    """Draw placeholder bounding boxes and property labels on a copy of the image."""
    img = base_image.copy().convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    img_w, img_h = img.size

    try:
        title_font = ImageFont.load_default(size=ANNOTATION_FONT_SIZE)
        prop_font = ImageFont.load_default(size=LABEL_FONT_SIZE)
    except Exception:
        title_font = ImageFont.load_default()
        prop_font = ImageFont.load_default()

    for ph in placeholders:
        color = PH_COLORS.get(ph["type"], DEFAULT_PH_COLOR)
        fill_color = color + (BOX_ALPHA,)
        outline_color = color + (200,)

        # Convert percentage positions to pixel coordinates (before clamping)
        raw_px = int(ph["x_pct"] / 100 * img_w)
        raw_py = int(ph["y_pct"] / 100 * img_h)
        raw_pw = int(ph["w_pct"] / 100 * img_w)
        raw_ph_h = int(ph["h_pct"] / 100 * img_h)

        # Detect off-canvas: any edge outside the slide bounds
        off_canvas = (
            raw_px < 0
            or raw_py < 0
            or raw_px + raw_pw > img_w
            or raw_py + raw_ph_h > img_h
        )

        # Clamp to image bounds
        px = max(0, min(raw_px, img_w - 1))
        py = max(0, min(raw_py, img_h - 1))
        pw = max(1, min(raw_pw, img_w - px))
        ph_h = max(1, min(raw_ph_h, img_h - py))

        # Draw filled rectangle
        if off_canvas:
            # Dashed outline for off-canvas placeholders
            draw.rectangle(
                [px, py, px + pw, py + ph_h],
                fill=fill_color,
            )
            dash_len = 8
            gap_len = 6
            # Top edge
            x_pos = px
            while x_pos < px + pw:
                x_end = min(x_pos + dash_len, px + pw)
                draw.line([(x_pos, py), (x_end, py)], fill=outline_color, width=2)
                x_pos += dash_len + gap_len
            # Bottom edge
            x_pos = px
            while x_pos < px + pw:
                x_end = min(x_pos + dash_len, px + pw)
                draw.line([(x_pos, py + ph_h), (x_end, py + ph_h)], fill=outline_color, width=2)
                x_pos += dash_len + gap_len
            # Left edge
            y_pos = py
            while y_pos < py + ph_h:
                y_end = min(y_pos + dash_len, py + ph_h)
                draw.line([(px, y_pos), (px, y_end)], fill=outline_color, width=2)
                y_pos += dash_len + gap_len
            # Right edge
            y_pos = py
            while y_pos < py + ph_h:
                y_end = min(y_pos + dash_len, py + ph_h)
                draw.line([(px + pw, y_pos), (px + pw, y_end)], fill=outline_color, width=2)
                y_pos += dash_len + gap_len
        else:
            draw.rectangle(
                [px, py, px + pw, py + ph_h],
                fill=fill_color,
                outline=outline_color,
                width=2,
            )

        # Header label: "type (idx: N)" with optional markers
        meta_mark = " [meta]" if ph["is_meta"] else ""
        canvas_mark = " [off-canvas]" if off_canvas else ""
        header = f"{ph['type']} (idx:{ph['idx']}){meta_mark}{canvas_mark}"

        # Calculate label block height
        lines = [header] + ph["props"]
        line_height = LABEL_FONT_SIZE + 3
        label_block_h = len(lines) * line_height + 6

        # Position labels inside the box if it fits, otherwise below
        label_x = px + 4
        if label_block_h < ph_h - 4:
            label_y = py + 3
        else:
            label_y = py + ph_h + 2

        # Draw semi-transparent background for label
        label_w = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=prop_font)
            label_w = max(label_w, bbox[2] - bbox[0])
        label_w += 8

        # Ensure label stays within image
        if label_x + label_w > img_w:
            label_x = max(0, img_w - label_w - 2)
        if label_y + label_block_h > img_h:
            label_y = max(0, img_h - label_block_h - 2)

        draw.rectangle(
            [label_x - 2, label_y - 2, label_x + label_w, label_y + label_block_h],
            fill=(255, 255, 255, 200),
        )

        # Draw header in bold color
        draw.text(
            (label_x, label_y),
            header,
            fill=color + (255,),
            font=title_font,
        )
        # Draw property lines
        y_offset = label_y + line_height + 2
        for prop_line in ph["props"]:
            draw.text(
                (label_x, y_offset),
                prop_line,
                fill=(40, 40, 40, 255),
                font=prop_font,
            )
            y_offset += line_height

    # Composite overlay onto base
    result = Image.alpha_composite(img, overlay)
    return result.convert("RGB")


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def render_layouts(
    template_path: Path,
    output_dir: Path,
    width_px: int = DEFAULT_WIDTH_PX,
) -> list[dict]:
    """Render all brand layouts as clean + annotated images.

    Returns a list of dicts describing each rendered layout:
        [{"layout_file": "slideLayout1.xml", "name": "Title Slide",
          "clean": "slideLayout1.jpg", "annotated": "slideLayout1_annotated.jpg"}]
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(template_path, "r") as zf:
        cx, cy = _get_slide_size_emu(zf)
        master_path, layout_paths = _find_brand_master(zf)

        if not layout_paths:
            print("Warning: No layouts found in template.", file=sys.stderr)
            return []

        # Sort layouts by filename number
        def _sort_key(p: str) -> int:
            m = re.search(r"(\d+)\.xml$", p)
            return int(m.group(1)) if m else 0

        layout_paths.sort(key=_sort_key)

        results = []

        for layout_path in layout_paths:
            layout_basename = posixpath.basename(layout_path)
            layout_stem = layout_basename.replace(".xml", "")
            layout_name = _get_layout_name(zf, layout_path)

            print(f"  Rendering {layout_stem} ({layout_name})...")

            # Extract placeholders for annotation
            placeholders = _get_layout_placeholders(zf, layout_path, cx, cy)

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                tmp_pptx = tmp_path / f"{layout_stem}.pptx"

                # Build a single-slide PPTX for this layout
                _build_single_layout_pptx(
                    template_path, layout_path, master_path, tmp_pptx
                )

                # Convert to image
                try:
                    images = _convert_pptx_to_images(tmp_pptx, tmp_path, width_px, cx)
                except RuntimeError as e:
                    print(f"  Warning: Failed to render {layout_stem}: {e}",
                          file=sys.stderr)
                    continue

                if not images:
                    print(f"  Warning: No image produced for {layout_stem}",
                          file=sys.stderr)
                    continue

                # Use the first (only) page
                base_img = Image.open(images[0])

                # 1. Save clean preview
                clean_path = output_dir / f"{layout_stem}.jpg"
                base_img.convert("RGB").save(
                    str(clean_path), "JPEG", quality=JPEG_QUALITY
                )

                # 2. Save annotated preview
                annotated_path = output_dir / f"{layout_stem}_annotated.jpg"
                annotated_img = _draw_annotations(base_img, placeholders, layout_name)
                annotated_img.save(
                    str(annotated_path), "JPEG", quality=JPEG_QUALITY
                )

                base_img.close()

                results.append({
                    "layout_file": layout_basename,
                    "name": layout_name,
                    "clean": f"{layout_stem}.jpg",
                    "annotated": f"{layout_stem}_annotated.jpg",
                    "placeholder_count": len(placeholders),
                })

                print(f"    -> {clean_path.name}, {annotated_path.name} "
                      f"({len(placeholders)} placeholders)")

        return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Render each slideLayout in a template as preview images."
    )
    parser.add_argument(
        "input",
        help="Input PowerPoint template (.potx or .pptx)",
    )
    parser.add_argument(
        "-o", "--output",
        default="layout-previews",
        help="Output directory for preview images (default: layout-previews/)",
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

    print(f"Rendering layouts from {input_path.name}...")
    results = render_layouts(input_path, output_dir, width_px=args.width)

    if not results:
        print("No layouts were rendered.", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone. {len(results)} layouts rendered to {output_dir}/")
    for r in results:
        print(f"  {r['layout_file']:30s}  {r['name']:40s}  "
              f"({r['placeholder_count']} placeholders)")


if __name__ == "__main__":
    main()
