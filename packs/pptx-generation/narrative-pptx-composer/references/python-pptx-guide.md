# python-pptx Guide

> **Scope.** This guide documents **python-pptx primitives** —
> textboxes, shapes, backgrounds, tables, charts, notes. For
> *composed patterns* (cards, accent bars, badges, image fitting,
> rounded rects with text), call the helpers in
> [`scripts/s07_slide_helpers.py`](../scripts/s07_slide_helpers.py).
> Do not re-implement them.

## Setup & Basic Structure

```python
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

prs = Presentation()
prs.slide_width = Inches(13.333)   # widescreen 16:9
prs.slide_height = Inches(7.5)

# Use blank layout for full design control
blank_layout = prs.slide_layouts[6]
slide = prs.slides.add_slide(blank_layout)

prs.save("output.pptx")
```

## Layout Dimensions

Slide dimensions (set via `Inches()`):
- **16:9 Widescreen**: `13.333" × 7.5"` (default for modern presentations)
- **16:10**: `13.333" × 8.333"`
- **4:3 Standard**: `10" × 7.5"`

---

## Text & Formatting

```python
# Basic textbox
txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2))
tf = txBox.text_frame
tf.word_wrap = True
tf.auto_size = None  # prevent auto-shrink

p = tf.paragraphs[0]
p.text = "Hello World"
p.font.size = Pt(36)
p.font.bold = True
p.font.color.rgb = RGBColor(0x36, 0x36, 0x36)
# In production: resolve font name from s05b-style-policy.json
# (typography.headingFont / bodyFont / monoFont). Do not hardcode.
p.alignment = PP_ALIGN.CENTER
```

### Multi-line text (newline-separated)

```python
text = "Line 1\nLine 2\nLine 3"
paragraphs = text.split("\n")
for i, para_text in enumerate(paragraphs):
    if i == 0:
        p = tf.paragraphs[0]
    else:
        p = tf.add_paragraph()
    p.text = para_text
    p.font.size = Pt(14)
    p.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    # Font name omitted — resolve from style-policy in production
    p.space_after = Pt(4)
```

### Rich text (mixed formatting in one paragraph)

```python
p = tf.paragraphs[0]
run1 = p.add_run()
run1.text = "Bold "
run1.font.bold = True

run2 = p.add_run()
run2.text = "and italic"
run2.font.italic = True
```

### Vertical alignment

```python
from pptx.enum.text import MSO_ANCHOR
tf.auto_size = None
txBox.text_frame.word_wrap = True

# Set vertical alignment on the text frame
from pptx.oxml.ns import qn
txBody = txBox.text_frame._txBody
bodyPr = txBody.find(qn('a:bodyPr'))
bodyPr.set('anchor', 'ctr')  # 't' = top, 'ctr' = middle, 'b' = bottom
```

---

## Shapes

```python
# Rectangle
shape = slide.shapes.add_shape(
    MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(0.8), Inches(1.5), Inches(3.0)
)
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(0xFF, 0x00, 0x00)
shape.line.color.rgb = RGBColor(0x00, 0x00, 0x00)
shape.line.width = Pt(2)

# Oval / circle
shape = slide.shapes.add_shape(
    MSO_SHAPE.OVAL, Inches(4), Inches(1), Inches(2), Inches(2)
)
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(0x00, 0x00, 0xFF)

# Rounded rectangle with adjustable corner radius
shape = slide.shapes.add_shape(
    MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1), Inches(1), Inches(3), Inches(2)
)
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
if hasattr(shape, 'adjustments') and len(shape.adjustments) > 0:
    shape.adjustments[0] = 0.1  # corner radius (0.0 = sharp, 0.5 = max)

# Hide border (transparent line)
shape.line.fill.background()

# With transparency (requires direct XML manipulation)
from pptx.oxml.ns import qn
import lxml.etree as etree
solidFill = shape.fill._fill
alpha = etree.SubElement(solidFill.find(qn('a:srgbClr')), qn('a:alpha'))
alpha.set('val', '50000')  # 50% opacity (value is in 1000ths of percent)
```

### Shape with text

```python
shape = slide.shapes.add_shape(
    MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1), Inches(1), Inches(3), Inches(0.7)
)
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(0x00, 0x78, 0xD4)
shape.line.fill.background()

tf = shape.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "Button Label"
p.font.size = Pt(16)
p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
p.font.bold = True
p.alignment = PP_ALIGN.CENTER
```

---

## Images

For **every** image, call
[`s07_slide_helpers.add_image_safe(slide, img_path, left, top, width, height=None)`](../scripts/s07_slide_helpers.py).
It preserves aspect ratio, fits within the zone, and falls back to
a placeholder rectangle when the file is missing. The bare
`add_picture(path, left, top, w, h)` API stretches images to fill
the box and is forbidden by
[design-guardrails.md § Image](design-guardrails.md).

For an image with a text overlay (full-bleed image with caption,
hero with title), use
[`s07_slide_helpers.add_image_with_overlay(...)`](../scripts/s07_slide_helpers.py).

---

## Slide Backgrounds

```python
# Solid color
bg = slide.background
fill = bg.fill
fill.solid()
fill.fore_color.rgb = RGBColor(0xF1, 0xF1, 0xF1)
```

### Gradient backgrounds (via XML)

```python
from pptx.oxml.ns import qn
import lxml.etree as etree

bg = slide.background
bgPr = bg._element.find(qn('p:bgPr'))
if bgPr is None:
    bgPr = etree.SubElement(bg._element, qn('p:bgPr'))

gradFill = etree.SubElement(bgPr, qn('a:gradFill'))
gsLst = etree.SubElement(gradFill, qn('a:gsLst'))

# Stop 1
gs1 = etree.SubElement(gsLst, qn('a:gs'))
gs1.set('pos', '0')
srgb1 = etree.SubElement(gs1, qn('a:srgbClr'))
srgb1.set('val', '1B1B2F')

# Stop 2
gs2 = etree.SubElement(gsLst, qn('a:gs'))
gs2.set('pos', '100000')
srgb2 = etree.SubElement(gs2, qn('a:srgbClr'))
srgb2.set('val', '0078D4')

# Linear gradient direction
lin = etree.SubElement(gradFill, qn('a:lin'))
lin.set('ang', '5400000')  # 90 degrees (top to bottom)
lin.set('scaled', '1')
```

---

## Tables

```python
from pptx.util import Inches, Pt

rows, cols = 3, 2
table_shape = slide.shapes.add_table(
    rows, cols, Inches(1), Inches(1), Inches(8), Inches(2)
)
table = table_shape.table

# Header row
table.cell(0, 0).text = "Header 1"
table.cell(0, 1).text = "Header 2"

# Data rows
table.cell(1, 0).text = "Cell 1"
table.cell(1, 1).text = "Cell 2"

# Style cells
for row in table.rows:
    for cell in row.cells:
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(12)
```

---

## Charts

```python
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

chart_data = CategoryChartData()
chart_data.categories = ['Q1', 'Q2', 'Q3', 'Q4']
chart_data.add_series('Sales', (4500, 5500, 6200, 7100))

chart = slide.shapes.add_chart(
    XL_CHART_TYPE.COLUMN_CLUSTERED,
    Inches(0.5), Inches(1), Inches(6), Inches(4),
    chart_data
).chart

chart.has_legend = False
```

---

## Speaker Notes

```python
notes_slide = slide.notes_slide
tf = notes_slide.notes_text_frame
tf.text = "Speaker notes for this slide."
```

---

## Common Patterns — call the helpers

These compositions are implemented in
[`scripts/s07_slide_helpers.py`](../scripts/s07_slide_helpers.py). Call the
helpers; do not inline the equivalents.

| Pattern                               | Helper                                                                    |
| ------------------------------------- | ------------------------------------------------------------------------- |
| Accent bar                            | `add_accent_bar(slide, left, top, width, height, color)`                  |
| Card (rounded rect)                   | `add_card(slide, left, top, width, height, fill_color, ...)`              |
| Card with title+body                  | `add_card(...)` + `add_textbox(...)`                                      |
| Image (aspect-safe)                   | `add_image_safe(slide, img_path, left, top, width, height=None)`          |
| Image with text overlay               | `add_image_with_overlay(slide, img_path, left, top, width, height, ...)`  |
| Outline capsule                       | `add_outline_capsule(slide, left, top, width, height, ...)`               |
| Outline circle / badge                | `add_outline_circle(slide, left, top, width, height, ...)`                |
| Rounded rect                          | `add_rounded_rect(slide, left, top, width, height, fill_color, ...)`      |
| Speaker notes                         | `add_speaker_notes(slide, text)`                                          |
| Slide background                      | `set_slide_bg(slide, color)` / `set_slide_bg_image(slide, img_path, ...)` |
| Textbox                               | `add_textbox(slide, left, top, width, height, text, ...)`                 |
| Textbox (auto-fit, escape hatch only) | `add_textbox_autofit(...)` — do not use at Step 7; Step 6b owns fit       |
| Mixed-weight title runs               | `add_textbox_runs(slide, left, top, width, height, runs=[{...}], ...)`    |
| Oversized numeral / char              | `add_oversized_numeral(slide, left, top, width, height, char, ...)`       |
| Vertical edge label                   | `add_vertical_label(slide, left, top, width, height, text, ...)`          |

A number badge = `add_outline_circle` + a small `add_textbox`
centered over it; s07-build.py composes these as needed.

---

## Critical Rules (python-pptx API)

These are **API-level** invariants for the python-pptx library
itself. Design rules (palette choice, layout variety, when to use
images, typography heuristics) live in
[design-guardrails.md](design-guardrails.md) —
that file is canonical. Do not duplicate them here.

1. **Use `RGBColor(r, g, b)`** — never pass hex strings to color properties
2. **Use `Inches()` for all positioning** — raw numbers are EMUs, not inches
3. **Use `Pt()` for font sizes** — raw numbers are EMUs
4. **Set `word_wrap = True`** on text frames to prevent overflow
5. **Use `line.fill.background()`** to hide shape borders
6. **Z-order follows creation order** — in python-pptx, shapes are
   painted in the order they are added. Apply backgrounds first
   (`set_slide_bg` / `set_slide_bg_image` / large background
   rectangles), then text and images on top. For
   `add_image_with_overlay`, add the title textbox **after** the
   helper call so it paints above the scrim. **Canonical statement
   — do not duplicate this rule in other docs; cross-reference here.**
7. **Use blank layout** (`slide_layouts[6]`) for full design control
8. **Image aspect ratio** — always preserve original ratio; never stretch to fill a zone (use `s07_slide_helpers.add_image_safe`)
9. **`adjustments[0]`** controls corner radius on `ROUNDED_RECTANGLE` (0.0–0.5)

---

## QA (Required)

### Content QA

```bash
python -m markitdown output.pptx
```

Check for missing content, typos, wrong order.

### Visual QA

**Use subagents** — even for 2-3 slides. Convert slides to images, then inspect:

```bash
python scripts/office/soffice.py --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 150 output.pdf slide
```

---

## Dependencies

- `pip install python-pptx` - creating/editing presentations
- `pip install "markitdown[pptx]"` - text extraction
- `pip install Pillow` - image handling and thumbnails
