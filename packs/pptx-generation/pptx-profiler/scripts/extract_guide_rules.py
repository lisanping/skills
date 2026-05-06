"""Extract raw text and structural cues from confirmed guide slides.

This script provides the programmatic text-extraction layer for guide slide
analysis. It reads confirmed guide slide entries from the profile's
sample_slide_catalog (those with role == "guide" or "hybrid") and extracts
all text content, shape metadata, and visual cues needed for the downstream
VLM subagent to parse structured rules.

The output JSON is designed to feed directly into a VLM prompt that converts
raw guide text into structured rule objects (ruleKind, applies_to, constraint,
rawQuote).

Usage:
    python extract_guide_rules.py template.pptx profile.json -o guide-rules-raw.json
    python extract_guide_rules.py template.potx profile.json -o guide-rules-raw.json
"""

import argparse
import json
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

# OOXML namespaces
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

VERSION = "1.0.0"

# Rule kind classification patterns (used for preliminary tagging).
# These are hints for the downstream VLM, which makes the final call.
# Word boundaries (\b) prevent substring false positives.
_RULE_KIND_PATTERNS = {
    "typography": re.compile(
        r"\bfonts?\b|typeface|typograph|字体|字号"
        r"|(?<!\w)\d+\s*pt\b|(?<!\w)pt\s"
        r"|point\s*size|\bheading\b|body\s*text|\bcaption\b",
        re.IGNORECASE,
    ),
    "colorUsage": re.compile(
        r"\bcolou?rs?\b|\bpalette\b|accent\s+colou?r|\bswatch"
        r"|\bcolor\s+fill\b|\bshade\b|\btint\b|配色|颜色|色彩",
        re.IGNORECASE,
    ),
    "spacing": re.compile(
        r"\bspacing\b|\bmargins?\b|\bpadding\b|\bwhitespace\b|间距|留白|行距",
        re.IGNORECASE,
    ),
    "layoutUsage": re.compile(
        r"\blayout\b|slide\s*type|when\s*to\s*use|use\s*this\s*slide|版式|布局",
        re.IGNORECASE,
    ),
    "donts": re.compile(
        r"\bdon['\u2019]?t\b|\bdo\s*not\b|\bavoid\b|\bnever\b|\bprohibit|不要|避免|禁止",
        re.IGNORECASE,
    ),
    "logoUsage": re.compile(
        r"\blogos?\b|brand\s*mark|\blogo\s*usage\b|标志|商标",
        re.IGNORECASE,
    ),
    "imagery": re.compile(
        r"\bimages?\b|\bphotos?\b|\bpictures?\b|\billustration|图片|图像|摄影",
        re.IGNORECASE,
    ),
    "iconography": re.compile(
        r"\bicons?\b(?!ic)|\bglyph|\bsymbols?\b|\bpictogram|图标",
        re.IGNORECASE,
    ),
}


def _read_xml(zf: zipfile.ZipFile, path: str) -> ET.Element | None:
    """Read and parse XML from ZIP archive."""
    try:
        with zf.open(path) as f:
            return ET.parse(f).getroot()
    except (KeyError, ET.ParseError):
        return None


def _extract_text_blocks(slide_elem: ET.Element) -> list[dict[str, Any]]:
    """
    Extract text content from a slide as structured blocks.
    Each block represents a shape's text body with paragraph-level detail.
    """
    cSld = slide_elem.find(f"{{{NS['p']}}}cSld")
    if cSld is None:
        return []

    sp_tree = cSld.find(f"{{{NS['p']}}}spTree")
    if sp_tree is None:
        return []

    blocks = []
    for sp in sp_tree.findall(f"{{{NS['p']}}}sp"):
        txBody = sp.find(f"{{{NS['p']}}}txBody")
        if txBody is None:
            continue

        # Check if placeholder
        is_placeholder = False
        ph_type = None
        nvSpPr = sp.find(f"{{{NS['p']}}}nvSpPr")
        if nvSpPr is not None:
            nvPr = nvSpPr.find(f"{{{NS['p']}}}nvPr")
            if nvPr is not None:
                ph = nvPr.find(f"{{{NS['p']}}}ph")
                if ph is not None:
                    is_placeholder = True
                    ph_type = ph.get("type")

        # Extract paragraphs
        paragraphs = []
        for para in txBody.findall(f"{{{NS['a']}}}p"):
            runs_text = []
            for run in para.findall(f"{{{NS['a']}}}r"):
                t = run.find(f"{{{NS['a']}}}t")
                if t is not None and t.text:
                    runs_text.append(t.text)
            para_text = "".join(runs_text).strip()
            if para_text:
                paragraphs.append(para_text)

        if not paragraphs:
            continue

        full_text = "\n".join(paragraphs)

        # Preliminary rule-kind tagging
        detected_kinds = []
        for kind, pattern in _RULE_KIND_PATTERNS.items():
            if pattern.search(full_text):
                detected_kinds.append(kind)

        blocks.append({
            "isPlaceholder": is_placeholder,
            "placeholderType": ph_type,
            "paragraphs": paragraphs,
            "fullText": full_text,
            "detectedRuleKinds": detected_kinds,
        })

    return blocks


def _extract_color_swatches(slide_elem: ET.Element) -> list[dict[str, Any]]:
    """
    Extract color swatch shapes: small rectangles with solid fills
    that likely represent a color palette.
    """
    cSld = slide_elem.find(f"{{{NS['p']}}}cSld")
    if cSld is None:
        return []
    sp_tree = cSld.find(f"{{{NS['p']}}}spTree")
    if sp_tree is None:
        return []

    swatches = []
    for sp in sp_tree.findall(f"{{{NS['p']}}}sp"):
        spPr = sp.find(f"{{{NS['p']}}}spPr")
        if spPr is None:
            continue
        solidFill = spPr.find(f"{{{NS['a']}}}solidFill")
        if solidFill is None:
            continue

        # Get color value
        color = None
        srgbClr = solidFill.find(f"{{{NS['a']}}}srgbClr")
        if srgbClr is not None:
            color = f"#{srgbClr.get('val', '000000')}"
        else:
            schemeClr = solidFill.find(f"{{{NS['a']}}}schemeClr")
            if schemeClr is not None:
                color = f"scheme:{schemeClr.get('val', 'unknown')}"

        if color is None:
            continue

        # Check size (small = potential swatch)
        xfrm = spPr.find(f"{{{NS['a']}}}xfrm")
        if xfrm is None:
            continue
        ext = xfrm.find(f"{{{NS['a']}}}ext")
        if ext is None:
            continue
        try:
            cx = int(ext.get("cx", "0"))
            cy = int(ext.get("cy", "0"))
        except (ValueError, TypeError):
            continue

        if cx > 0 and cy > 0 and cx < 2 * 914400 and cy < 2 * 914400:
            # Get any label text
            label = ""
            txBody = sp.find(f"{{{NS['p']}}}txBody")
            if txBody is not None:
                texts = []
                for t in txBody.iter(f"{{{NS['a']}}}t"):
                    if t.text:
                        texts.append(t.text)
                label = " ".join(texts).strip()

            swatches.append({
                "color": color,
                "label": label if label else None,
                "width_emu": cx,
                "height_emu": cy,
            })

    return swatches


def extract_guide_content(
    zf: zipfile.ZipFile,
    profile: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract raw text and structural cues from confirmed guide slides.

    Candidates are selected by role == "guide" or "hybrid" in
    sample_slide_catalog (set by VLM in Step 5c).

    Returns a dict ready for VLM rule-extraction prompt.
    """
    catalog = profile.get("sample_slide_catalog", []) or []

    candidates = []
    for entry in catalog:
        if not entry.get("has_content"):
            continue

        slide_file = entry.get("slide_file")
        if not slide_file:
            continue

        role = entry.get("role")
        if role in ("guide", "hybrid"):
            candidates.append(entry)

    if not candidates:
        return {
            "meta": {"version": VERSION, "candidateCount": 0},
            "guideSlides": [],
        }

    results = []
    for entry in candidates:
        slide_file = entry.get("slide_file")
        slide_path = f"ppt/slides/{slide_file}"
        slide_elem = _read_xml(zf, slide_path)
        if slide_elem is None:
            continue

        text_blocks = _extract_text_blocks(slide_elem)
        color_swatches = _extract_color_swatches(slide_elem)

        # Aggregate all text for full-slide analysis
        all_text = "\n\n".join(b["fullText"] for b in text_blocks)

        # Collect all detected rule kinds across blocks
        all_kinds = set()
        for b in text_blocks:
            all_kinds.update(b["detectedRuleKinds"])

        results.append({
            "slideFile": slide_file,
            "slideIndex": entry.get("slide_index"),
            "title": entry.get("title", "(untitled)"),
            "role": entry.get("role"),
            "textBlocks": text_blocks,
            "colorSwatches": color_swatches,
            "allText": all_text,
            "detectedRuleKinds": sorted(all_kinds),
        })

    return {
        "meta": {
            "version": VERSION,
            "candidateCount": len(results),
        },
        "guideSlides": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract raw text and structural cues from guide slides."
    )
    parser.add_argument("template", help="Path to .potx/.pptx template file")
    parser.add_argument("profile", help="Path to template-profile.json")
    parser.add_argument(
        "-o", "--output",
        default="guide-rules-raw.json",
        help="Output file path (default: guide-rules-raw.json)",
    )

    args = parser.parse_args()

    # Load profile
    try:
        with open(args.profile, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading profile: {e}", file=sys.stderr)
        sys.exit(1)

    # Open template ZIP
    try:
        with zipfile.ZipFile(args.template, "r") as zf:
            result = extract_guide_content(zf, profile)
    except zipfile.BadZipFile as e:
        print(f"Error opening template: {e}", file=sys.stderr)
        sys.exit(1)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    count = result["meta"]["candidateCount"]
    print(f"✓ Extracted text from {count} guide slide candidate(s)", file=sys.stderr)
    print(f"✓ Output: {output_path}", file=sys.stderr)

    if count > 0:
        for gs in result["guideSlides"]:
            kinds = ", ".join(gs["detectedRuleKinds"]) or "general"
            print(
                f"  {gs['slideFile']} (role={gs['role']}): {kinds}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
