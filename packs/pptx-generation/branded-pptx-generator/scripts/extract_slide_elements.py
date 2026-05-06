"""Extract all element properties from a single slide within a .potx/.pptx template.

Reads the slide XML from the template ZIP and outputs a structured JSON
with every shape's position, size, fill, line, font, text, and layering.
Used by the on-demand Slide Visual Design Analysis step.

Usage:
    python extract_slide_elements.py template.pptx slide3.xml -o slide-elements-slide3.json
"""

import argparse
import json
import posixpath
import sys
import zipfile
from pathlib import Path
from lxml import etree

# OOXML namespaces
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}

REL_SLIDE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
)
REL_SLIDE_LAYOUT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
)
REL_SLIDE_MASTER = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"
)
REL_THEME = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _read_xml(zf: zipfile.ZipFile, path: str) -> etree._Element | None:
    try:
        with zf.open(path) as f:
            return etree.parse(f).getroot()
    except (KeyError, etree.XMLSyntaxError):
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


def _emu_to_pt(emu: int) -> float:
    return round(emu / 12700, 1)


# ---------------------------------------------------------------------------
# Color extraction
# ---------------------------------------------------------------------------

def _extract_color(container: etree._Element) -> dict | None:
    """Extract color as a structured dict with type and value."""
    srgb = container.find(f"{{{NS['a']}}}srgbClr")
    if srgb is not None:
        mods = _extract_color_mods(srgb)
        return {"type": "srgb", "value": f"#{srgb.get('val', '')}", **mods}

    sys_clr = container.find(f"{{{NS['a']}}}sysClr")
    if sys_clr is not None:
        v = sys_clr.get("lastClr", "") or sys_clr.get("val", "")
        mods = _extract_color_mods(sys_clr)
        return {"type": "sys", "value": f"#{v}", **mods}

    scheme_clr = container.find(f"{{{NS['a']}}}schemeClr")
    if scheme_clr is not None:
        mods = _extract_color_mods(scheme_clr)
        return {"type": "scheme", "value": scheme_clr.get("val", ""), **mods}

    return None


def _extract_color_mods(clr_el: etree._Element) -> dict:
    """Extract color transform modifiers (lumMod, lumOff, alpha, tint, shade, etc.)."""
    mods = {}
    for child in clr_el:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        val = child.get("val")
        if val is not None:
            mods[tag] = int(val)
    return {"mods": mods} if mods else {}


# ---------------------------------------------------------------------------
# Fill, line, effect extraction
# ---------------------------------------------------------------------------

def _extract_fill(sp: etree._Element) -> dict | None:
    """Extract fill properties from a shape."""
    spPr = sp.find(f".//{{{NS['a']}}}spPr")
    if spPr is None:
        return None

    noFill = spPr.find(f"{{{NS['a']}}}noFill")
    if noFill is not None:
        return {"type": "none"}

    solidFill = spPr.find(f"{{{NS['a']}}}solidFill")
    if solidFill is not None:
        return {"type": "solid", "color": _extract_color(solidFill)}

    gradFill = spPr.find(f"{{{NS['a']}}}gradFill")
    if gradFill is not None:
        stops = []
        for gs in gradFill.findall(f".//{{{NS['a']}}}gs"):
            pos = gs.get("pos")
            color = _extract_color(gs) if len(gs) > 0 else None
            stops.append({"pos": int(pos) if pos else 0, "color": color})
        return {"type": "gradient", "stops": stops}

    blipFill = spPr.find(f"{{{NS['a']}}}blipFill")
    if blipFill is not None:
        return {"type": "image"}

    pattFill = spPr.find(f"{{{NS['a']}}}pattFill")
    if pattFill is not None:
        return {"type": "pattern", "preset": pattFill.get("prst")}

    return None


def _extract_line(sp: etree._Element) -> dict | None:
    """Extract line/outline properties."""
    ln = sp.find(f".//{{{NS['a']}}}spPr/{{{NS['a']}}}ln")
    if ln is None:
        return None

    noFill = ln.find(f"{{{NS['a']}}}noFill")
    if noFill is not None:
        return {"type": "none"}

    result: dict = {}
    w = ln.get("w")
    if w:
        result["width_emu"] = int(w)
        result["width_pt"] = _emu_to_pt(int(w))

    solidFill = ln.find(f"{{{NS['a']}}}solidFill")
    if solidFill is not None:
        result["fill"] = {"type": "solid", "color": _extract_color(solidFill)}

    dash = ln.find(f"{{{NS['a']}}}prstDash")
    if dash is not None:
        result["dash"] = dash.get("val")

    return result if result else None


def _extract_effect(sp: etree._Element) -> list | None:
    """Extract effect list (shadow, glow, etc.)."""
    effectLst = sp.find(f".//{{{NS['a']}}}spPr/{{{NS['a']}}}effectLst")
    if effectLst is None or len(effectLst) == 0:
        return None
    effects = []
    for child in effectLst:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        effects.append(tag)
    return effects


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_text_body(sp: etree._Element) -> dict | None:
    """Extract text body with paragraphs and run-level formatting."""
    txBody = sp.find(f"{{{NS['p']}}}txBody")
    if txBody is None:
        txBody = sp.find(f".//{{{NS['a']}}}txBody")
    if txBody is None:
        return None

    # Body properties
    bodyPr = txBody.find(f"{{{NS['a']}}}bodyPr")
    body_props = {}
    if bodyPr is not None:
        for attr in ("anchor", "anchorCtr", "wrap", "lIns", "tIns", "rIns", "bIns", "rot"):
            v = bodyPr.get(attr)
            if v is not None:
                body_props[attr] = v
        if bodyPr.find(f"{{{NS['a']}}}spAutoFit") is not None:
            body_props["autoFit"] = "shape"
        elif bodyPr.find(f"{{{NS['a']}}}normAutofit") is not None:
            body_props["autoFit"] = "normal"
        else:
            body_props["autoFit"] = "none"

    paragraphs = []
    for p in txBody.findall(f"{{{NS['a']}}}p"):
        para = _extract_paragraph(p)
        paragraphs.append(para)

    return {
        "bodyProperties": body_props,
        "paragraphs": paragraphs,
    }


def _extract_paragraph(p: etree._Element) -> dict:
    """Extract a single paragraph with its properties and runs."""
    para: dict = {}

    # Paragraph properties
    pPr = p.find(f"{{{NS['a']}}}pPr")
    if pPr is not None:
        pprops: dict = {}
        for attr in ("algn", "lvl", "indent", "marL", "marR"):
            v = pPr.get(attr)
            if v is not None:
                pprops[attr] = v
        lnSpc = pPr.find(f"{{{NS['a']}}}lnSpc")
        if lnSpc is not None:
            spcPct = lnSpc.find(f".//{{{NS['a']}}}spcPct")
            spcPts = lnSpc.find(f".//{{{NS['a']}}}spcPts")
            if spcPct is not None:
                pprops["lineSpacing"] = {"type": "pct", "val": spcPct.get("val")}
            elif spcPts is not None:
                pprops["lineSpacing"] = {"type": "pts", "val": spcPts.get("val")}
        buChar = pPr.find(f"{{{NS['a']}}}buChar")
        buAutoNum = pPr.find(f"{{{NS['a']}}}buAutoNum")
        buNone = pPr.find(f"{{{NS['a']}}}buNone")
        if buChar is not None:
            pprops["bullet"] = {"type": "char", "char": buChar.get("char", "")}
        elif buAutoNum is not None:
            pprops["bullet"] = {"type": "autoNum", "scheme": buAutoNum.get("type", "")}
        elif buNone is not None:
            pprops["bullet"] = {"type": "none"}
        if pprops:
            para["properties"] = pprops

    # Runs
    runs = []
    for r in p.findall(f"{{{NS['a']}}}r"):
        run = _extract_run(r)
        runs.append(run)

    # End paragraph run (for empty paragraphs with formatting)
    endParaRPr = p.find(f"{{{NS['a']}}}endParaRPr")
    if endParaRPr is not None and not runs:
        runs.append({"text": "", "properties": _extract_run_properties(endParaRPr)})

    para["runs"] = runs
    return para


def _extract_run(r: etree._Element) -> dict:
    """Extract a text run with its properties."""
    run: dict = {}
    t = r.find(f"{{{NS['a']}}}t")
    run["text"] = t.text if t is not None and t.text else ""

    rPr = r.find(f"{{{NS['a']}}}rPr")
    if rPr is not None:
        run["properties"] = _extract_run_properties(rPr)
    return run


def _extract_run_properties(rPr: etree._Element) -> dict:
    """Extract run-level text properties."""
    props: dict = {}
    for attr in ("sz", "b", "i", "u", "strike", "kern", "spc", "baseline"):
        v = rPr.get(attr)
        if v is not None:
            props[attr] = v
    if "sz" in props:
        props["size_pt"] = round(int(props["sz"]) / 100, 1)

    solidFill = rPr.find(f"{{{NS['a']}}}solidFill")
    if solidFill is not None:
        props["color"] = _extract_color(solidFill)

    latin = rPr.find(f"{{{NS['a']}}}latin")
    if latin is not None:
        props["latin"] = latin.get("typeface", "")
    ea = rPr.find(f"{{{NS['a']}}}ea")
    if ea is not None:
        props["ea"] = ea.get("typeface", "")
    cs = rPr.find(f"{{{NS['a']}}}cs")
    if cs is not None:
        props["cs"] = cs.get("typeface", "")

    hlinkClick = rPr.find(f"{{{NS['a']}}}hlinkClick")
    if hlinkClick is not None:
        props["hasHyperlink"] = True

    return props


# ---------------------------------------------------------------------------
# Shape extraction (position + transform)
# ---------------------------------------------------------------------------

def _extract_xfrm(el: etree._Element) -> dict:
    """Extract position and size from xfrm."""
    xfrm = el.find(f".//{{{NS['a']}}}xfrm")
    if xfrm is None:
        return {"x": 0, "y": 0, "cx": 0, "cy": 0, "rot": 0, "flipH": False, "flipV": False}
    off = xfrm.find(f"{{{NS['a']}}}off")
    ext = xfrm.find(f"{{{NS['a']}}}ext")
    x = int(off.get("x", "0")) if off is not None else 0
    y = int(off.get("y", "0")) if off is not None else 0
    cx = int(ext.get("cx", "0")) if ext is not None else 0
    cy = int(ext.get("cy", "0")) if ext is not None else 0
    rot = int(xfrm.get("rot", "0"))
    flipH = xfrm.get("flipH", "0") == "1"
    flipV = xfrm.get("flipV", "0") == "1"
    return {"x": x, "y": y, "cx": cx, "cy": cy, "rot": rot, "flipH": flipH, "flipV": flipV}


def _extract_geometry(sp: etree._Element) -> dict | None:
    """Extract shape geometry (preset or custom)."""
    spPr = sp.find(f".//{{{NS['a']}}}spPr")
    if spPr is None:
        return None
    prstGeom = spPr.find(f"{{{NS['a']}}}prstGeom")
    if prstGeom is not None:
        return {"type": "preset", "preset": prstGeom.get("prst", "")}
    custGeom = spPr.find(f"{{{NS['a']}}}custGeom")
    if custGeom is not None:
        return {"type": "custom"}
    return None


def _get_name(el: etree._Element, nv_tag: str) -> str:
    """Extract shape name from nvSpPr/nvPicPr/etc."""
    nv = el.find(f"{{{NS['p']}}}{nv_tag}")
    if nv is not None:
        cNvPr = nv.find(f"{{{NS['p']}}}cNvPr")
        if cNvPr is not None:
            return cNvPr.get("name", "")
    return ""


def _get_id(el: etree._Element, nv_tag: str) -> int:
    nv = el.find(f"{{{NS['p']}}}{nv_tag}")
    if nv is not None:
        cNvPr = nv.find(f"{{{NS['p']}}}cNvPr")
        if cNvPr is not None:
            return int(cNvPr.get("id", "0"))
    return 0


# ---------------------------------------------------------------------------
# Top-level element parsers
# ---------------------------------------------------------------------------

def _extract_sp(sp: etree._Element, z_index: int) -> dict:
    """Extract a <p:sp> shape element."""
    name = _get_name(sp, "nvSpPr")
    shape_id = _get_id(sp, "nvSpPr")

    ph = sp.find(f".//{{{NS['p']}}}ph")
    is_placeholder = ph is not None
    ph_info = None
    if is_placeholder:
        ph_info = {"type": ph.get("type", "body"), "idx": int(ph.get("idx", "0"))}

    return {
        "elementType": "sp",
        "id": shape_id,
        "name": name,
        "zIndex": z_index,
        "isPlaceholder": is_placeholder,
        "placeholder": ph_info,
        "xfrm": _extract_xfrm(sp),
        "geometry": _extract_geometry(sp),
        "fill": _extract_fill(sp),
        "line": _extract_line(sp),
        "effects": _extract_effect(sp),
        "textBody": _extract_text_body(sp),
    }


def _extract_pic(pic: etree._Element, z_index: int) -> dict:
    """Extract a <p:pic> picture element."""
    name = _get_name(pic, "nvPicPr")
    shape_id = _get_id(pic, "nvPicPr")

    ph = pic.find(f".//{{{NS['p']}}}ph")
    is_placeholder = ph is not None
    ph_info = None
    if is_placeholder:
        ph_info = {"type": ph.get("type", "pic"), "idx": int(ph.get("idx", "0"))}

    return {
        "elementType": "pic",
        "id": shape_id,
        "name": name,
        "zIndex": z_index,
        "isPlaceholder": is_placeholder,
        "placeholder": ph_info,
        "xfrm": _extract_xfrm(pic),
    }


def _extract_graphicFrame(gf: etree._Element, z_index: int) -> dict:
    """Extract a <p:graphicFrame> (table, chart, SmartArt, etc.)."""
    name = _get_name(gf, "nvGraphicFramePr")
    shape_id = _get_id(gf, "nvGraphicFramePr")

    xfrm = _extract_xfrm(gf)

    # Determine graphic type
    graphic_type = "unknown"
    graphic = gf.find(f".//{{{NS['a']}}}graphic")
    if graphic is not None:
        graphicData = graphic.find(f"{{{NS['a']}}}graphicData")
        if graphicData is not None:
            uri = graphicData.get("uri", "")
            if "table" in uri:
                graphic_type = "table"
            elif "chart" in uri:
                graphic_type = "chart"
            elif "dgm" in uri or "diagram" in uri:
                graphic_type = "smartArt"
            else:
                graphic_type = uri.split("/")[-1] if uri else "unknown"

    # Extract table data if present
    table_data = None
    tbl = gf.find(f".//{{{NS['a']}}}tbl")
    if tbl is not None:
        table_data = _extract_table(tbl)

    return {
        "elementType": "graphicFrame",
        "id": shape_id,
        "name": name,
        "zIndex": z_index,
        "graphicType": graphic_type,
        "xfrm": xfrm,
        "tableData": table_data,
    }


def _extract_table(tbl: etree._Element) -> dict:
    """Extract table structure and styling."""
    tblPr = tbl.find(f"{{{NS['a']}}}tblPr")
    style_id = None
    if tblPr is not None:
        tblStyle = tblPr.find(f"{{{NS['a']}}}tblStyle")
        if tblStyle is not None:
            style_id = tblStyle.text if tblStyle.text else tblStyle.get("val")

    # Grid columns
    grid_cols = []
    tblGrid = tbl.find(f"{{{NS['a']}}}tblGrid")
    if tblGrid is not None:
        for gc in tblGrid.findall(f"{{{NS['a']}}}gridCol"):
            w = gc.get("w", "0")
            grid_cols.append(int(w))

    rows = []
    for tr in tbl.findall(f"{{{NS['a']}}}tr"):
        row_h = int(tr.get("h", "0"))
        cells = []
        for tc in tr.findall(f"{{{NS['a']}}}tc"):
            cell_text = ""
            for t in tc.iter(f"{{{NS['a']}}}t"):
                if t.text:
                    cell_text += t.text
            cells.append(cell_text.strip())
        rows.append({"height_emu": row_h, "cells": cells})

    return {
        "styleId": style_id,
        "gridCols_emu": grid_cols,
        "rows": rows,
    }


def _extract_grpSp(grp: etree._Element, z_index: int) -> dict:
    """Extract a <p:grpSp> group shape with its children."""
    name = _get_name(grp, "nvGrpSpPr")
    shape_id = _get_id(grp, "nvGrpSpPr")

    # Group transform
    grpSpPr = grp.find(f"{{{NS['p']}}}grpSpPr")
    xfrm = {"x": 0, "y": 0, "cx": 0, "cy": 0, "rot": 0, "flipH": False, "flipV": False}
    chOff = {"x": 0, "y": 0}
    chExt = {"cx": 0, "cy": 0}
    if grpSpPr is not None:
        grpXfrm = grpSpPr.find(f"{{{NS['a']}}}xfrm")
        if grpXfrm is not None:
            off = grpXfrm.find(f"{{{NS['a']}}}off")
            ext = grpXfrm.find(f"{{{NS['a']}}}ext")
            if off is not None:
                xfrm["x"] = int(off.get("x", "0"))
                xfrm["y"] = int(off.get("y", "0"))
            if ext is not None:
                xfrm["cx"] = int(ext.get("cx", "0"))
                xfrm["cy"] = int(ext.get("cy", "0"))
            xfrm["rot"] = int(grpXfrm.get("rot", "0"))
            xfrm["flipH"] = grpXfrm.get("flipH", "0") == "1"
            xfrm["flipV"] = grpXfrm.get("flipV", "0") == "1"

            chOffEl = grpXfrm.find(f"{{{NS['a']}}}chOff")
            chExtEl = grpXfrm.find(f"{{{NS['a']}}}chExt")
            if chOffEl is not None:
                chOff = {"x": int(chOffEl.get("x", "0")), "y": int(chOffEl.get("y", "0"))}
            if chExtEl is not None:
                chExt = {"cx": int(chExtEl.get("cx", "0")), "cy": int(chExtEl.get("cy", "0"))}

    children = _extract_spTree_children(grp)

    return {
        "elementType": "grpSp",
        "id": shape_id,
        "name": name,
        "zIndex": z_index,
        "xfrm": xfrm,
        "childOffset": chOff,
        "childExtent": chExt,
        "children": children,
    }


def _extract_cxnSp(cxn: etree._Element, z_index: int) -> dict:
    """Extract a <p:cxnSp> connector shape."""
    name = _get_name(cxn, "nvCxnSpPr")
    shape_id = _get_id(cxn, "nvCxnSpPr")
    return {
        "elementType": "cxnSp",
        "id": shape_id,
        "name": name,
        "zIndex": z_index,
        "xfrm": _extract_xfrm(cxn),
        "line": _extract_line(cxn),
    }


# ---------------------------------------------------------------------------
# Shape tree traversal
# ---------------------------------------------------------------------------

def _extract_spTree_children(parent: etree._Element) -> list[dict]:
    """Extract all child elements from a spTree or grpSp, preserving z-order."""
    elements = []
    z_index = 0

    for child in parent:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "sp":
            elements.append(_extract_sp(child, z_index))
            z_index += 1
        elif tag == "pic":
            elements.append(_extract_pic(child, z_index))
            z_index += 1
        elif tag == "graphicFrame":
            elements.append(_extract_graphicFrame(child, z_index))
            z_index += 1
        elif tag == "grpSp":
            elements.append(_extract_grpSp(child, z_index))
            z_index += 1
        elif tag == "cxnSp":
            elements.append(_extract_cxnSp(child, z_index))
            z_index += 1

    return elements


# ---------------------------------------------------------------------------
# Slide background
# ---------------------------------------------------------------------------

def _extract_background(root: etree._Element) -> dict:
    bg = root.find(f".//{{{NS['p']}}}bg")
    if bg is None:
        return {"type": "inherited"}

    solidFill = bg.find(f".//{{{NS['a']}}}solidFill")
    if solidFill is not None:
        return {"type": "solid", "color": _extract_color(solidFill)}

    gradFill = bg.find(f".//{{{NS['a']}}}gradFill")
    if gradFill is not None:
        stops = []
        for gs in gradFill.findall(f".//{{{NS['a']}}}gs"):
            pos = gs.get("pos")
            color = _extract_color(gs) if len(gs) > 0 else None
            stops.append({"pos": int(pos) if pos else 0, "color": color})
        return {"type": "gradient", "stops": stops}

    blipFill = bg.find(f".//{{{NS['a']}}}blipFill")
    if blipFill is not None:
        return {"type": "image"}

    return {"type": "other"}


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def _find_slide_path(zf: zipfile.ZipFile, slide_file: str) -> str | None:
    """Find the full ZIP path for a slide XML file (e.g. slide3.xml -> ppt/slides/slide3.xml)."""
    candidate = f"ppt/slides/{slide_file}"
    if candidate in zf.namelist():
        return candidate
    # Fallback: search
    for name in zf.namelist():
        if name.endswith(f"/{slide_file}"):
            return name
    return None


def extract_slide_elements(template_path: str, slide_file: str) -> dict:
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    with zipfile.ZipFile(path, "r") as zf:
        slide_path = _find_slide_path(zf, slide_file)
        if slide_path is None:
            raise ValueError(f"Slide not found in template: {slide_file}")

        slide_root = _read_xml(zf, slide_path)
        if slide_root is None:
            raise ValueError(f"Failed to parse slide XML: {slide_path}")

        # Find shape tree
        spTree = slide_root.find(f".//{{{NS['p']}}}spTree")
        elements = _extract_spTree_children(spTree) if spTree is not None else []

        background = _extract_background(slide_root)

        # Get slide's layout reference
        slide_rels = _parse_rels(zf, slide_path)
        layout_file = None
        for lr in slide_rels.get(REL_SLIDE_LAYOUT, []):
            layout_file = posixpath.basename(lr["target"])
            break

        return {
            "slideFile": slide_file,
            "slidePath": slide_path,
            "layoutFile": layout_file,
            "background": background,
            "elementCount": len(elements),
            "elements": elements,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract all element properties from a single slide in a .potx/.pptx template."
    )
    parser.add_argument("template", help="Path to .potx/.pptx template file")
    parser.add_argument("slide", help="Slide XML filename (e.g. slide3.xml)")
    parser.add_argument("-o", "--output", required=True, help="Output JSON file path")
    args = parser.parse_args()

    try:
        result = extract_slide_elements(args.template, args.slide)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Extracted {result['elementCount']} elements from {args.slide} → {args.output}")


if __name__ == "__main__":
    main()
