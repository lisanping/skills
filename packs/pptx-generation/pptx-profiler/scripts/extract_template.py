"""Template Parser — Extract structural profile from .potx/.pptx templates.

Self-contained: reads the OOXML ZIP directly (no external services).
Extracts theme colors, fonts, slide size, masters, layouts (with
placeholders and decorative shapes), and sample slide catalog.

Multi-master aware: identifies the brand master (skips Office Theme).

Usage:
    python template_parser.py template.pptx -o template-profile.json
    python template_parser.py template.potx -o template-profile.json
"""

import argparse
import json
import posixpath
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

VERSION = "1.0.0"

# OOXML namespaces
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}

# Relationship type URIs
REL_SLIDE_LAYOUT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
)
REL_SLIDE_MASTER = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"
)
REL_THEME = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
)
REL_SLIDE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _read_xml(zf: zipfile.ZipFile, path: str) -> ET.Element | None:
    try:
        with zf.open(path) as f:
            return ET.parse(f).getroot()
    except (KeyError, ET.ParseError):
        return None


def _rels_path(part_path: str) -> str:
    """ppt/slideMasters/slideMaster1.xml -> ppt/slideMasters/_rels/slideMaster1.xml.rels"""
    d = posixpath.dirname(part_path)
    name = posixpath.basename(part_path)
    return posixpath.join(d, "_rels", name + ".rels")


def _resolve_target(part_path: str, target: str) -> str:
    """Resolve a relationship target relative to the part's directory."""
    base = posixpath.dirname(part_path)
    return posixpath.normpath(posixpath.join(base, target))


def _parse_rels(zf: zipfile.ZipFile, part_path: str) -> dict[str, list[dict]]:
    """Return relationships grouped by type."""
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
# Unit conversions
# ---------------------------------------------------------------------------

def _emu_to_pt(emu: int) -> float:
    return round(emu / 12700, 1)


def _emu_to_pct(emu: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{emu / total * 100:.1f}%"


def _detect_aspect(cx: int, cy: int) -> str:
    if cy == 0:
        return "unknown"
    r = cx / cy
    for label, ratio in [("16:9", 16 / 9), ("4:3", 4 / 3), ("16:10", 16 / 10)]:
        if abs(r - ratio) < 0.02:
            return label
    return f"{r:.2f}:1"


# ---------------------------------------------------------------------------
# Color / font extraction from theme XML
# ---------------------------------------------------------------------------

_COLOR_SLOTS = [
    "dk1", "dk2", "lt1", "lt2",
    "accent1", "accent2", "accent3", "accent4", "accent5", "accent6",
    "hlink", "folHlink",
]


def _extract_color(container: ET.Element) -> str | None:
    """Extract a color value from a DrawingML color container element."""
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
        return scheme_clr.get("val")  # e.g. "dk1", "accent1"
    return None


def _extract_color_with_source(container: ET.Element) -> tuple[str | None, str | None, dict | None]:
    """Extract color value, source type, and modifiers from a DrawingML color container.

    Returns (value, source, mods):
      - value: color string (hex "#RRGGBB" or scheme slot name)
      - source: "srgbClr", "sysClr", "schemeClr", or None
      - mods: dict with lumMod/lumOff if present (for schemeClr), else None
    """
    srgb = container.find(f"{{{NS['a']}}}srgbClr")
    if srgb is not None:
        v = srgb.get("val", "")
        return (f"#{v}" if v else None, "srgbClr", None)
    sys_clr = container.find(f"{{{NS['a']}}}sysClr")
    if sys_clr is not None:
        v = sys_clr.get("lastClr", "") or sys_clr.get("val", "")
        return (f"#{v}" if v else None, "sysClr", None)
    scheme_clr = container.find(f"{{{NS['a']}}}schemeClr")
    if scheme_clr is not None:
        val = scheme_clr.get("val")
        mods = {}
        lm = scheme_clr.find(f"{{{NS['a']}}}lumMod")
        if lm is not None:
            mods["lumMod"] = int(lm.get("val", "0"))
        lo = scheme_clr.find(f"{{{NS['a']}}}lumOff")
        if lo is not None:
            mods["lumOff"] = int(lo.get("val", "0"))
        return (val, "schemeClr", mods if mods else None)
    return (None, None, None)


def _parse_color_scheme(theme: ET.Element) -> dict[str, str]:
    scheme = theme.find(f".//{{{NS['a']}}}clrScheme")
    if scheme is None:
        return {}
    colors = {}
    for slot in _COLOR_SLOTS:
        elem = scheme.find(f"{{{NS['a']}}}{slot}")
        if elem is not None:
            c = _extract_color(elem)
            if c:
                colors[slot] = c
    return colors


def _parse_font_scheme(theme: ET.Element) -> dict:
    fonts = {
        "major": {"latin": "", "ea": "", "cs": ""},
        "minor": {"latin": "", "ea": "", "cs": ""},
    }
    fs = theme.find(f".//{{{NS['a']}}}fontScheme")
    if fs is None:
        return fonts
    for kind in ("major", "minor"):
        fe = fs.find(f"{{{NS['a']}}}{kind}Font")
        if fe is None:
            continue
        for script in ("latin", "ea", "cs"):
            sub = fe.find(f"{{{NS['a']}}}{script}")
            if sub is not None:
                fonts[kind][script] = sub.get("typeface", "")
    return fonts


def _theme_name(theme: ET.Element) -> str:
    return theme.get("name", "")


# Known Office default theme names across locales.
# Any theme whose name starts with "office" is also treated as default.
_OFFICE_THEME_NAMES = {
    # English
    "office theme", "office",
    # German
    "office-design", "office design",
    # French
    "thème office",
    # Spanish
    "tema de office",
    # Italian
    "tema di office",
    # Portuguese
    "tema do office",
    # Japanese
    "office テーマ",
    # Chinese (Simplified & Traditional)
    "office 主题", "office主题", "office 佈景主題",
    # Korean
    "office 테마",
}


def _is_office_theme(name: str) -> bool:
    n = name.lower().strip()
    if not n:
        return True  # empty name = default theme
    return n in _OFFICE_THEME_NAMES or n.startswith("office")


# ---------------------------------------------------------------------------
# Placeholder / shape extraction from layout or slide XML
# ---------------------------------------------------------------------------

def _parse_placeholder(sp: ET.Element, cx: int, cy: int) -> dict | None:
    """Extract placeholder info from a <p:sp> element. Returns None if not a placeholder."""
    ph = sp.find(f".//{{{NS['p']}}}ph")
    if ph is None:
        return None

    ph_type = ph.get("type", "body")
    ph_idx = int(ph.get("idx", "0"))

    # Position
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

    # Text body properties
    font_size = None
    font_color = None
    font_bold = None
    font_family = None
    alignment = None
    anchor = None
    auto_fit = None
    prompt_text = None

    bodyPr = sp.find(f".//{{{NS['a']}}}bodyPr")
    if bodyPr is not None:
        anchor = bodyPr.get("anchor")
        if bodyPr.find(f"{{{NS['a']}}}spAutoFit") is not None:
            auto_fit = "shape"
        elif bodyPr.find(f"{{{NS['a']}}}normAutofit") is not None:
            auto_fit = "normal"
        else:
            auto_fit = "none"

    # Font from defRPr or first rPr
    txBody = sp.find(f"{{{NS['p']}}}txBody")
    if txBody is not None:
        # Paragraph alignment
        first_pPr = txBody.find(f".//{{{NS['a']}}}pPr")
        if first_pPr is not None:
            alignment = first_pPr.get("algn")

        # Font size / bold / color / family from defRPr, then rPr
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
                font_color = _extract_color(sf)
            # Font family — check latin element first, then typeface attr
            if font_family is None:
                latin = rpr.find(f"{{{NS['a']}}}latin")
                if latin is not None:
                    tf = latin.get("typeface", "")
                    if tf and not tf.startswith("+"):
                        font_family = tf

        # Prompt text (placeholder hint)
        texts = []
        for t_el in txBody.iter(f"{{{NS['a']}}}t"):
            if t_el.text:
                texts.append(t_el.text)
        if texts:
            prompt_text = " ".join(texts).strip()

    return {
        "type": ph_type,
        "idx": ph_idx,
        "name": name,
        "x_pct": _emu_to_pct(x, cx),
        "y_pct": _emu_to_pct(y, cy),
        "w_pct": _emu_to_pct(w, cx),
        "h_pct": _emu_to_pct(h, cy),
        "font_size_pt": font_size,
        "font_color": font_color,
        "font_bold": font_bold,
        "font_family": font_family,
        "alignment": alignment,
        "anchor": anchor,
        "auto_fit": auto_fit,
        "prompt_text": prompt_text,
        # Keep in sync with render_layouts.py _get_layout_placeholder_info
        "is_meta": ph_type in ("dt", "ftr", "sldNum", "hdr"),
    }


# Shape role heuristic thresholds (tuned for 16:9 slides).
# VLM analysis in Step 3b overrides these preliminary labels.
_SHAPE_ROLE_THRESHOLDS = {
    "background_min_coverage": 0.95,   # w/cx AND h/cy >= this -> background
    "logo_max_size": 0.2,              # w/cx AND h/cy < this -> logo candidate
    "logo_corner_margin": 0.15,        # x/cx < this OR (x+w)/cx > (1-this) -> corner
    "divider_aspect_ratio": 15,        # w/h > this -> horizontal divider bar
    "accent_bar_aspect_ratio": 10,     # h/w > this -> vertical accent bar
}


def _infer_shape_role(
    stype: str, name: str, x: int, y: int, w: int, h: int,
    cx: int, cy: int, is_pic: bool,
) -> str:
    n = name.lower()
    t = _SHAPE_ROLE_THRESHOLDS
    # Full-slide background
    if w >= cx * t["background_min_coverage"] and h >= cy * t["background_min_coverage"]:
        return "background_pattern" if is_pic else "background_fill"
    # Logo: small picture in corners
    if is_pic and w < cx * t["logo_max_size"] and h < cy * t["logo_max_size"]:
        if x < cx * t["logo_corner_margin"] or x + w > cx * (1 - t["logo_corner_margin"]):
            return "likely_logo"
    # Thin horizontal bar
    if h > 0 and w / max(h, 1) > t["divider_aspect_ratio"]:
        return "likely_divider_bar"
    # Thin vertical bar
    if w > 0 and h / max(w, 1) > t["accent_bar_aspect_ratio"]:
        return "likely_accent_bar"
    if "logo" in n:
        return "likely_logo"
    return "decorative"


def _parse_decorative_shape(sp: ET.Element, cx: int, cy: int) -> dict | None:
    """Extract non-placeholder shape from <p:sp>. Returns None if it is a placeholder."""
    if sp.find(f".//{{{NS['p']}}}ph") is not None:
        return None

    xfrm = sp.find(f".//{{{NS['a']}}}xfrm")
    x = y = w = h = 0
    if xfrm is not None:
        off = xfrm.find(f"{{{NS['a']}}}off")
        ext = xfrm.find(f"{{{NS['a']}}}ext")
        if off is not None:
            x, y = int(off.get("x", "0")), int(off.get("y", "0"))
        if ext is not None:
            w, h = int(ext.get("cx", "0")), int(ext.get("cy", "0"))

    name = ""
    nvSpPr = sp.find(f"{{{NS['p']}}}nvSpPr")
    if nvSpPr is not None:
        cNvPr = nvSpPr.find(f"{{{NS['p']}}}cNvPr")
        if cNvPr is not None:
            name = cNvPr.get("name", "")

    is_pic = sp.find(f".//{{{NS['a']}}}blipFill") is not None
    stype = "picture" if is_pic else "shape"
    fill_color = None
    sf = sp.find(f".//{{{NS['a']}}}solidFill")
    if sf is not None:
        fill_color = _extract_color(sf)

    role = _infer_shape_role(stype, name, x, y, w, h, cx, cy, is_pic)
    return {
        "type": stype,
        "desc": name,
        "role": role,
        "x_pct": _emu_to_pct(x, cx),
        "y_pct": _emu_to_pct(y, cy),
        "w_pct": _emu_to_pct(w, cx),
        "h_pct": _emu_to_pct(h, cy),
        "fill_color": fill_color,
    }


def _parse_pic_element(pic: ET.Element, cx: int, cy: int) -> dict:
    """Extract a standalone <p:pic> element."""
    xfrm = pic.find(f".//{{{NS['a']}}}xfrm")
    x = y = w = h = 0
    if xfrm is not None:
        off = xfrm.find(f"{{{NS['a']}}}off")
        ext = xfrm.find(f"{{{NS['a']}}}ext")
        if off is not None:
            x, y = int(off.get("x", "0")), int(off.get("y", "0"))
        if ext is not None:
            w, h = int(ext.get("cx", "0")), int(ext.get("cy", "0"))
    name = ""
    nvPicPr = pic.find(f"{{{NS['p']}}}nvPicPr")
    if nvPicPr is not None:
        cNvPr = nvPicPr.find(f"{{{NS['p']}}}cNvPr")
        if cNvPr is not None:
            name = cNvPr.get("name", "")
    role = _infer_shape_role("picture", name, x, y, w, h, cx, cy, True)
    return {
        "type": "picture",
        "desc": name,
        "role": role,
        "x_pct": _emu_to_pct(x, cx),
        "y_pct": _emu_to_pct(y, cy),
        "w_pct": _emu_to_pct(w, cx),
        "h_pct": _emu_to_pct(h, cy),
        "fill_color": None,
    }


def _parse_background(root: ET.Element) -> dict:
    bg = root.find(f".//{{{NS['p']}}}bg")
    if bg is None:
        return {"type": "inherited", "color": None}
    if bg.find(f".//{{{NS['a']}}}solidFill") is not None:
        return {"type": "solid", "color": _extract_color(bg.find(f".//{{{NS['a']}}}solidFill"))}
    if bg.find(f".//{{{NS['a']}}}gradFill") is not None:
        return {"type": "gradient", "color": None}
    if bg.find(f".//{{{NS['a']}}}blipFill") is not None:
        return {"type": "image", "color": None}
    return {"type": "other", "color": None}


# ---------------------------------------------------------------------------
# Slide content analysis (for sample_slide_catalog)
# ---------------------------------------------------------------------------

# Known placeholder prompt texts across locales.  Used as a fallback when
# structural detection (presence of <p:ph>) is insufficient to distinguish
# real content from inherited placeholder text.
_PLACEHOLDER_MARKERS = {
    # English
    "click to add title", "click to add subtitle", "click to add text",
    "click to edit master title style", "click to edit master text styles",
    "click to add notes",
    # German
    "titel durch klicken hinzufügen", "untertitel durch klicken hinzufügen",
    "text durch klicken hinzufügen",
    "titelmasterformat durch klicken bearbeiten",
    "textmasterformat durch klicken bearbeiten",
    # French
    "cliquez pour ajouter un titre", "cliquez pour ajouter un sous-titre",
    "cliquez pour ajouter du texte",
    "modifiez le style du titre", "modifiez les styles du texte du masque",
    # Spanish
    "haga clic para agregar título", "haga clic para agregar subtítulo",
    "haga clic para agregar texto",
    # Italian
    "fare clic per aggiungere un titolo", "fare clic per aggiungere un sottotitolo",
    # Portuguese
    "clique para adicionar um título", "clique para adicionar um subtítulo",
    # Japanese
    "タイトルを入力", "サブタイトルを入力", "テキストを入力",
    "マスター タイトルの書式設定", "マスター テキストの書式設定",
    # Chinese (Simplified)
    "单击此处添加标题", "单击此处添加副标题", "单击此处添加文本",
    "单击此处编辑母版标题样式", "单击此处编辑母版文本样式",
    # Chinese (Traditional)
    "按一下以新增標題", "按一下以新增副標題", "按一下以新增文字",
    # Korean
    "제목을 입력하십시오", "부제목을 입력하십시오", "텍스트를 입력하십시오",
}


def _is_placeholder_text(text: str) -> bool:
    """Check if text is a known placeholder prompt (case-insensitive)."""
    t = text.lower().strip()
    if t in _PLACEHOLDER_MARKERS:
        return True
    # Catch variants: "Click to add …" / "Click to edit …" in any locale
    # by detecting the common "click to" / "cliquez" / "klicken" pattern.
    if t.startswith(("click to ", "klicken", "cliquez", "haga clic",
                     "fare clic", "clique para")):
        return True
    return False


def _analyze_slide_content(slide: ET.Element) -> tuple[str, bool, int]:
    """Return (title, has_real_content, shape_count).

    A slide has real content if it contains any of:
      - A graphicFrame (chart / table / embedded object)
      - A pic (image)
      - A grpSp (grouped shapes – diagrams, concepts, etc.)
      - At least one non-placeholder text segment longer than 1 char
    """
    title = ""
    texts: list[str] = []
    shape_count = 0
    has_visual_element = False

    spTree = slide.find(f".//{{{NS['p']}}}spTree")
    if spTree is None:
        return title, False, 0

    for child in spTree:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag in ("sp", "pic", "graphicFrame", "grpSp"):
            shape_count += 1
        if tag in ("pic", "graphicFrame", "grpSp"):
            has_visual_element = True
        if tag != "sp":
            continue

        ph = child.find(f".//{{{NS['p']}}}ph")
        is_title = ph is not None and ph.get("type", "") in ("title", "ctrTitle")

        for t_el in child.iter(f"{{{NS['a']}}}t"):
            if t_el.text and t_el.text.strip():
                texts.append(t_el.text.strip())
                if is_title and not title:
                    title = t_el.text.strip()

    real = [t for t in texts if not _is_placeholder_text(t) and len(t) > 1]
    has_content = has_visual_element or len(real) > 0
    return title, has_content, shape_count


# ---------------------------------------------------------------------------
# Layout-level typography & color aggregation
# ---------------------------------------------------------------------------

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _is_hex_color(val: str | None) -> bool:
    return val is not None and _HEX_RE.match(val) is not None


def _is_theme_ref(val: str | None) -> bool:
    return val is not None and not val.startswith("#")


def _aggregate_layout_typography(layout: dict) -> dict | None:
    """Compute typographySummary from a layout's placeholders."""
    families: set[str] = set()
    sizes: set[float] = set()
    has_bold = False
    for ph in layout["placeholders"]:
        ff = ph.get("font_family")
        if ff:
            families.add(ff)
        sz = ph.get("font_size_pt")
        if sz is not None:
            sizes.add(sz)
        if ph.get("font_bold"):
            has_bold = True
    if not families and not sizes:
        return None
    sorted_sizes = sorted(sizes)
    return {
        "fontFamilies": sorted(families),
        "sizeRange": [sorted_sizes[0], sorted_sizes[-1]] if sorted_sizes else [],
        "sizes": sorted_sizes,
        "hasBold": has_bold,
    }


def _aggregate_layout_colors(layout: dict) -> dict | None:
    """Compute colorSummary from a layout's placeholders, shapes, and background."""
    theme_refs: set[str] = set()
    hardcoded: set[str] = set()
    fills: set[str] = set()

    # Background
    bg = layout["background"]
    bg_val = bg.get("color") if bg.get("type") != "inherited" else None
    bg_label = "inherited" if bg.get("type") == "inherited" else (bg_val or bg.get("type"))

    # Placeholder font_color
    for ph in layout["placeholders"]:
        fc = ph.get("font_color")
        if fc is None:
            continue
        if _is_hex_color(fc):
            hardcoded.add(fc)
        elif _is_theme_ref(fc):
            theme_refs.add(fc)

    # Shape fill_color
    for sh in layout["shapes"]:
        fc = sh.get("fill_color")
        if fc is None:
            continue
        fills.add(fc)
        if _is_hex_color(fc):
            hardcoded.add(fc)
        elif _is_theme_ref(fc):
            theme_refs.add(fc)

    if not theme_refs and not hardcoded and bg_label == "inherited":
        return None

    return {
        "background": bg_label,
        "themeRefs": sorted(theme_refs),
        "hardcoded": sorted(hardcoded),
        "fills": sorted(fills),
    }


# ---------------------------------------------------------------------------
# Slide-level typography & color extraction
# ---------------------------------------------------------------------------

def _analyze_slide_typography(
    slide: ET.Element, theme_major: str, theme_minor: str,
) -> dict | None:
    """Extract typography inventory from all text runs in a slide."""
    families: set[str] = set()
    sizes: set[float] = set()
    has_bold = False

    for rpr in slide.iter(f"{{{NS['a']}}}rPr"):
        sz = rpr.get("sz")
        if sz:
            sizes.add(round(int(sz) / 100, 1))
        b = rpr.get("b")
        if b == "1":
            has_bold = True
        latin = rpr.find(f"{{{NS['a']}}}latin")
        if latin is not None:
            tf = latin.get("typeface", "")
            if tf and not tf.startswith("+"):
                families.add(tf)

    for drpr in slide.iter(f"{{{NS['a']}}}defRPr"):
        sz = drpr.get("sz")
        if sz:
            sizes.add(round(int(sz) / 100, 1))
        b = drpr.get("b")
        if b == "1":
            has_bold = True
        latin = drpr.find(f"{{{NS['a']}}}latin")
        if latin is not None:
            tf = latin.get("typeface", "")
            if tf and not tf.startswith("+"):
                families.add(tf)

    if not families and not sizes:
        return None

    theme_fonts = {f.lower() for f in (theme_major, theme_minor) if f}
    non_theme = sorted(f for f in families if f.lower() not in theme_fonts)
    sorted_sizes = sorted(sizes)
    return {
        "fontFamilies": sorted(families),
        "nonThemeFonts": non_theme,
        "sizeRange": [sorted_sizes[0], sorted_sizes[-1]] if sorted_sizes else [],
        "sizes": sorted_sizes,
        "hasBold": has_bold,
    }


def _analyze_slide_colors(
    slide: ET.Element, color_scheme: dict[str, str],
) -> dict | None:
    """Extract color inventory from all fills and text runs in a slide."""
    theme_refs: set[str] = set()
    theme_refs_with_mods: list[dict] = []
    _seen_mods: set[str] = set()  # dedup key: "slot|lumMod|lumOff"
    hardcoded: set[str] = set()
    scheme_clr_count = 0
    srgb_clr_count = 0
    no_fill_count = 0

    # Reverse lookup: hex → slot name
    hex_to_slot: dict[str, str] = {}
    for slot, hex_val in color_scheme.items():
        if hex_val:
            hex_to_slot[hex_val.upper()] = slot

    def _process_fill(container: ET.Element) -> None:
        nonlocal scheme_clr_count, srgb_clr_count, no_fill_count
        solid = container.find(f"{{{NS['a']}}}solidFill")
        if solid is not None:
            val, source, mods = _extract_color_with_source(solid)
            if source == "schemeClr" and val:
                scheme_clr_count += 1
                theme_refs.add(val)
                key = f"{val}|{(mods or {}).get('lumMod', '')}|{(mods or {}).get('lumOff', '')}"
                if key not in _seen_mods:
                    _seen_mods.add(key)
                    entry = {"slot": val}
                    if mods:
                        entry.update(mods)
                    theme_refs_with_mods.append(entry)
            elif source in ("srgbClr", "sysClr") and val:
                srgb_clr_count += 1
                hardcoded.add(val.upper())
            return
        if container.find(f"{{{NS['a']}}}noFill") is not None:
            no_fill_count += 1

    # Process all solidFill elements in the slide
    for sf in slide.iter(f"{{{NS['a']}}}solidFill"):
        val, source, mods = _extract_color_with_source(sf)
        if source == "schemeClr" and val:
            scheme_clr_count += 1
            theme_refs.add(val)
            key = f"{val}|{(mods or {}).get('lumMod', '')}|{(mods or {}).get('lumOff', '')}"
            if key not in _seen_mods:
                _seen_mods.add(key)
                entry = {"slot": val}
                if mods:
                    entry.update(mods)
                theme_refs_with_mods.append(entry)
        elif source in ("srgbClr", "sysClr") and val:
            srgb_clr_count += 1
            hardcoded.add(val.upper())

    # Count noFill elements
    for nf in slide.iter(f"{{{NS['a']}}}noFill"):
        no_fill_count += 1

    # Background fill
    bg_fill = None
    bg = slide.find(f".//{{{NS['p']}}}bg")
    if bg is not None:
        sf = bg.find(f".//{{{NS['a']}}}solidFill")
        if sf is not None:
            val, source, _ = _extract_color_with_source(sf)
            if source == "schemeClr":
                bg_fill = val
            elif val:
                bg_fill = val

    # Hardcoded-to-theme mapping
    hc_to_theme: dict[str, str] = {}
    for hc in hardcoded:
        slot = hex_to_slot.get(hc.upper())
        if slot:
            hc_to_theme[hc] = slot

    if not theme_refs and not hardcoded and bg_fill is None:
        return None

    return {
        "themeRefs": sorted(theme_refs),
        "themeRefsWithMods": sorted(theme_refs_with_mods, key=lambda x: x["slot"]),
        "hardcoded": sorted(hardcoded),
        "hardcodedToThemeMap": hc_to_theme,
        "backgroundFill": bg_fill,
        "stats": {
            "schemeClrCount": scheme_clr_count,
            "srgbClrCount": srgb_clr_count,
            "noFillCount": no_fill_count,
        },
    }


# ---------------------------------------------------------------------------
# Top-level inventory aggregation
# ---------------------------------------------------------------------------

def _build_font_inventory(
    fonts: dict, layouts: list[dict], samples: list[dict],
) -> dict:
    """Aggregate font info across theme, layouts, and samples."""
    theme_major = fonts["major"]["latin"] or ""
    theme_minor = fonts["minor"]["latin"] or ""
    theme_set = {f.lower() for f in (theme_major, theme_minor) if f}

    in_layouts: set[str] = set()
    for lo in layouts:
        ts = lo.get("typographySummary")
        if ts:
            in_layouts.update(ts["fontFamilies"])

    in_samples: set[str] = set()
    for s in samples:
        tu = s.get("typographyUsage")
        if tu:
            in_samples.update(tu["fontFamilies"])

    all_families = set()
    if theme_major:
        all_families.add(theme_major)
    if theme_minor:
        all_families.add(theme_minor)
    all_families.update(in_layouts)
    all_families.update(in_samples)

    non_theme = sorted(
        f for f in all_families if f.lower() not in theme_set
    )

    return {
        "theme": {"major": theme_major, "minor": theme_minor},
        "inLayouts": sorted(in_layouts),
        "inSamples": sorted(in_samples),
        "nonThemeFonts": non_theme,
        "allFamilies": sorted(all_families),
    }


def _build_color_inventory(
    color_scheme: dict[str, str], layouts: list[dict], samples: list[dict],
) -> dict:
    """Aggregate color info across theme scheme, layouts, and samples."""
    # Per-slot frequency
    slot_usage: dict[str, dict[str, int]] = {}
    for slot in _COLOR_SLOTS:
        slot_usage[slot] = {"inLayouts": 0, "inSamples": 0}

    for lo in layouts:
        cs = lo.get("colorSummary")
        if not cs:
            continue
        for ref in cs["themeRefs"]:
            if ref in slot_usage:
                slot_usage[ref]["inLayouts"] += 1

    for s in samples:
        cu = s.get("colorUsage")
        if not cu:
            continue
        for ref in cu["themeRefs"]:
            if ref in slot_usage:
                slot_usage[ref]["inSamples"] += 1

    # Hardcoded color aggregation
    hc_counts: dict[str, dict] = {}  # hex -> {inLayouts, inSamples}
    hex_to_slot: dict[str, str] = {}
    for slot, hex_val in color_scheme.items():
        if hex_val:
            hex_to_slot[hex_val.upper()] = slot

    for lo in layouts:
        cs = lo.get("colorSummary")
        if not cs:
            continue
        for hc in cs["hardcoded"]:
            key = hc.upper()
            if key not in hc_counts:
                hc_counts[key] = {"inLayouts": 0, "inSamples": 0}
            hc_counts[key]["inLayouts"] += 1

    for s in samples:
        cu = s.get("colorUsage")
        if not cu:
            continue
        for hc in cu["hardcoded"]:
            key = hc.upper()
            if key not in hc_counts:
                hc_counts[key] = {"inLayouts": 0, "inSamples": 0}
            hc_counts[key]["inSamples"] += 1

    hardcoded_list = []
    unmatched = 0
    for hex_val, counts in sorted(hc_counts.items()):
        match = hex_to_slot.get(hex_val)
        if not match:
            unmatched += 1
        hardcoded_list.append({
            "hex": hex_val,
            "matchesSlot": match,
            "inLayouts": counts["inLayouts"],
            "inSamples": counts["inSamples"],
        })

    total_hc = len(hc_counts)
    if total_hc == 0:
        risk = "low"
    elif unmatched / total_hc <= 0.3:
        risk = "medium" if unmatched > 0 else "low"
    else:
        risk = "high"

    return {
        "themeSlotUsage": slot_usage,
        "hardcodedColors": hardcoded_list,
        "complianceRisk": risk,
    }


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_template(template_path: str) -> dict:
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    if path.suffix.lower() not in (".pptx", ".potx"):
        raise ValueError(f"Unsupported file type: {path.suffix}")
    with zipfile.ZipFile(path, "r") as zf:
        return _parse_zip(zf, path.name)


def _parse_zip(zf: zipfile.ZipFile, source_name: str) -> dict:
    # ── presentation.xml ──
    pres = _read_xml(zf, "ppt/presentation.xml")
    if pres is None:
        raise ValueError("Invalid template: missing ppt/presentation.xml")
    pres_rels = _parse_rels(zf, "ppt/presentation.xml")

    # Slide size
    sz = pres.find(f"{{{NS['p']}}}sldSz")
    slide_cx = int(sz.get("cx", "0")) if sz is not None else 12192000
    slide_cy = int(sz.get("cy", "0")) if sz is not None else 6858000
    slide_size = {
        "width_emu": slide_cx,
        "height_emu": slide_cy,
        "width_pt": _emu_to_pt(slide_cx),
        "height_pt": _emu_to_pt(slide_cy),
        "aspect": _detect_aspect(slide_cx, slide_cy),
    }

    # ── Discover masters + themes ──
    masters: list[dict] = []
    for mi in pres_rels.get(REL_SLIDE_MASTER, []):
        mpath = mi["target"]
        mroot = _read_xml(zf, mpath)
        if mroot is None:
            continue
        m_rels = _parse_rels(zf, mpath)

        # Theme
        theme_path = theme_name = None
        theme_root = None
        for t in m_rels.get(REL_THEME, []):
            theme_path = t["target"]
            theme_root = _read_xml(zf, theme_path)
            if theme_root is not None:
                theme_name = _theme_name(theme_root)
            break

        layout_paths = sorted(
            l["target"] for l in m_rels.get(REL_SLIDE_LAYOUT, [])
        )
        masters.append({
            "path": mpath,
            "theme_path": theme_path,
            "theme_name": theme_name or "",
            "theme_root": theme_root,       # transient, not serialised
            "layout_paths": layout_paths,
            "is_office_theme": _is_office_theme(theme_name or ""),
        })

    # ── Identify brand master ──
    brand_candidates = [m for m in masters if not m["is_office_theme"]]
    if not brand_candidates:
        brand_candidates = masters[:]
    # Pick the candidate with the most layouts (most likely the real brand master)
    brand_candidates.sort(key=lambda m: len(m["layout_paths"]), reverse=True)
    brand = brand_candidates[0] if brand_candidates else None
    if brand is None:
        raise ValueError("No slide master found")

    # ── Theme identity ──
    colors: dict[str, str] = {}
    fonts = {"major": {"latin": "", "ea": "", "cs": ""},
             "minor": {"latin": "", "ea": "", "cs": ""}}
    if brand["theme_root"] is not None:
        colors = _parse_color_scheme(brand["theme_root"])
        fonts = _parse_font_scheme(brand["theme_root"])

    # ── Layouts (from brand master only) ──
    layouts: list[dict] = []
    for lpath in brand["layout_paths"]:
        lroot = _read_xml(zf, lpath)
        if lroot is None:
            continue
        cSld = lroot.find(f"{{{NS['p']}}}cSld")
        lname = cSld.get("name", "") if cSld is not None else ""

        idx_m = re.search(r"(\d+)$", Path(lpath).stem)
        lidx = int(idx_m.group(1)) if idx_m else 0

        spTree = lroot.find(f".//{{{NS['p']}}}spTree")
        placeholders: list[dict] = []
        shapes: list[dict] = []
        if spTree is not None:
            for sp in spTree.findall(f"{{{NS['p']}}}sp"):
                ph = _parse_placeholder(sp, slide_cx, slide_cy)
                if ph is not None:
                    placeholders.append(ph)
                else:
                    ds = _parse_decorative_shape(sp, slide_cx, slide_cy)
                    if ds is not None:
                        shapes.append(ds)
            for pic in spTree.findall(f"{{{NS['p']}}}pic"):
                shapes.append(_parse_pic_element(pic, slide_cx, slide_cy))

        content_phs = [p for p in placeholders if not p["is_meta"]]
        layout_data = {
            "name": lname,
            "index": lidx,
            "master_index": masters.index(brand),
            "background": _parse_background(lroot),
            "placeholders": placeholders,
            "shapes": shapes,
            "has_image_slot": any(
                p["type"] in ("pic", "obj") for p in content_phs
            ),
            "content_capacity": None,   # filled by VLM (Step 4)
            "visual_weight": None,      # filled by VLM (Step 4)
            "inferred_type": None,      # filled by VLM (Step 4)
            "inferred_type_confidence": None,  # filled by VLM (Step 4)
        }
        # Aggregate typography & color summaries
        layout_data["typographySummary"] = _aggregate_layout_typography(layout_data)
        layout_data["colorSummary"] = _aggregate_layout_colors(layout_data)
        layouts.append(layout_data)

    # ── Sample slides ──
    slide_rels = pres_rels.get(REL_SLIDE, [])
    rid_map = {r["id"]: r["target"] for r in slide_rels}
    sld_id_lst = pres.find(f"{{{NS['p']}}}sldIdLst")
    sample_slides: list[dict] = []

    if sld_id_lst is not None:
        for i, sld_id in enumerate(sld_id_lst.findall(f"{{{NS['p']}}}sldId")):
            rid = sld_id.get(f"{{{NS['r']}}}id", "")
            spath = rid_map.get(rid)
            if not spath:
                continue
            sroot = _read_xml(zf, spath)
            if sroot is None:
                continue

            # Layout reference
            s_rels = _parse_rels(zf, spath)
            layout_name = ""
            layout_idx = None
            for lr in s_rels.get(REL_SLIDE_LAYOUT, []):
                lr_root = _read_xml(zf, lr["target"])
                if lr_root is not None:
                    c = lr_root.find(f"{{{NS['p']}}}cSld")
                    layout_name = c.get("name", "") if c is not None else ""
                m = re.search(r"(\d+)", Path(lr["target"]).stem)
                layout_idx = int(m.group(1)) if m else None
                break

            title, has_content, shape_count = _analyze_slide_content(sroot)
            slide_entry = {
                "slide_index": i,
                "slide_file": posixpath.basename(spath),
                "layout_index": layout_idx,
                "layout_name": layout_name,
                "has_content": has_content,
                "title": title,
                "shape_count": shape_count,
            }
            # Typography & color analysis
            theme_major = fonts["major"]["latin"] or ""
            theme_minor = fonts["minor"]["latin"] or ""
            slide_entry["typographyUsage"] = _analyze_slide_typography(
                sroot, theme_major, theme_minor,
            )
            slide_entry["colorUsage"] = _analyze_slide_colors(sroot, colors)
            sample_slides.append(slide_entry)

    # ── Masters summary (serialisable) ──
    masters_out = []
    for m in masters:
        masters_out.append({
            "path": m["path"],
            "theme_path": m["theme_path"],
            "theme_name": m["theme_name"],
            "layout_count": len(m["layout_paths"]),
            "is_office_theme": m["is_office_theme"],
            "is_brand_master": m is brand,
        })

    return {
        "meta": {
            "source_file": source_name,
            "extraction_date": datetime.now(timezone.utc).isoformat(),
            "extractor_version": VERSION,
        },
        "identity": {
            "colors": {"scheme": colors},
            "fonts": fonts,
            "slide_size": slide_size,
        },
        "masters": masters_out,
        "layouts": layouts,
        "sample_slide_catalog": sample_slides,
        "fontInventory": _build_font_inventory(fonts, layouts, sample_slides),
        "colorInventory": _build_color_inventory(colors, layouts, sample_slides),
        "design_language": None,    # filled by VLM (Step 4)
        "table_styles": [],
        "compliance": None,         # filled by VLM
        "extended": {},
        "gaps": {
            "summary": "Initial extraction; VLM fields pending.",
            "missing_from_potx": [],
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _summarize(result: dict) -> None:
    meta = result["meta"]
    ident = result["identity"]
    colors = ident["colors"]["scheme"]
    fonts = ident["fonts"]
    sz = ident["slide_size"]
    layouts = result["layouts"]
    masters = result["masters"]
    samples = result["sample_slide_catalog"]

    print(f"Source:     {meta['source_file']}")
    print(f"Extractor:  v{meta['extractor_version']}")
    print(f"Size:       {sz['width_pt']}×{sz['height_pt']}pt ({sz['aspect']})")
    print(f"Colors:     {len(colors)} ({', '.join(list(colors.keys())[:6])}...)")
    print(
        f"Fonts:      major={fonts['major']['latin'] or '?'}, "
        f"minor={fonts['minor']['latin'] or '?'}"
    )

    print(f"\nMasters ({len(masters)}):")
    for m in masters:
        tag = " ← brand" if m["is_brand_master"] else " (Office Theme)" if m["is_office_theme"] else ""
        print(f"  {m['theme_name']:<30s} layouts={m['layout_count']}{tag}")

    print(f"\nLayouts ({len(layouts)}) — brand master only:")
    for lo in layouts:
        phs = lo["placeholders"]
        content = [p for p in phs if not p["is_meta"]]
        meta_phs = [p for p in phs if p["is_meta"]]
        print(
            f"  [{lo['index']:2d}] {lo['name']:<35s} "
            f"ph={len(content)} meta={len(meta_phs)} shapes={len(lo['shapes'])}"
        )

    print(f"\nSample slides ({len(samples)}):")
    for s in samples:
        flag = "✓" if s["has_content"] else "·"
        print(
            f"  [{s['slide_index']:2d}] {flag} {s['title'] or '(no title)':<40s} "
            f"layout={s['layout_name']} shapes={s['shape_count']}"
        )


def main():
    ap = argparse.ArgumentParser(
        description="Extract structural profile from .potx/.pptx template",
    )
    ap.add_argument("template", help="Path to .potx or .pptx template")
    ap.add_argument("-o", "--output", help="Output JSON path")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()

    if not Path(args.template).exists():
        print(f"ERROR: not found: {args.template}", file=sys.stderr)
        sys.exit(1)

    result = parse_template(args.template)

    if not args.quiet:
        _summarize(result)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        print(f"\n✓ Written to {out}")


if __name__ == "__main__":
    main()
