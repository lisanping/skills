# Design Guardrails

Absolute design rules that override all other design decisions.
Violating any of them produces a visually cheap, "default
PowerPoint" result.

This document is the **single source of truth** for banned
typography / colors / layouts / shapes / content labeling / image
handling and the mandatory text-on-image color discipline.
Math/formula authoring rules live in
[build-script-template.md § Formula zones](build-script-template.md).
Philosophy and rationale for *why* design exists at all live in
[design-principles.md](design-principles.md); this file is the
lookup catalog.

Consulted throughout Step 5 and referenced again during
Step 8 visual review.

## When to consult which section

| When                                           | Read                                                                                                             |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Picking heading / body fonts                   | [Typography — banned fonts](#typography--banned-fonts) + [Font selection guidelines](#font-selection-guidelines) |
| Choosing palette / accent tokens               | [Colors — banned patterns](#colors--banned-patterns)                                                             |
| Designing any slide with text over an image    | [Text-on-image colors (mandatory)](#text-on-image-colors-mandatory)                                              |
| Composing zone layout / bullet structure       | [Layout — banned patterns](#layout--banned-patterns)                                                             |
| Adding shapes, decoration, emphasis treatments | [Shape and decoration — banned patterns](#shape-and-decoration--banned-patterns)                                 |
| Writing section / divider slide text           | [Content labeling — banned patterns](#content-labeling--banned-patterns)                                         |
| Placing any image (user-media or generated)    | [Image — mandatory rules](#image--mandatory-rules)                                                               |

---

## Typography — banned fonts

Never use these fonts. They are overused system defaults that
instantly signal "no design effort":

| Banned                 | Severity     | Why                                                      |
| ---------------------- | ------------ | -------------------------------------------------------- |
| Comic Sans MS          | hard-ban     | Never appropriate                                        |
| Arial                  | hard-ban     | Generic, ubiquitous, no character                        |
| Calibri                | hard-ban     | Microsoft default since 2007, everyone has seen it       |
| Times New Roman        | hard-ban     | Academic default, wrong register for presentations       |
| Segoe UI               | strong-avoid | Windows system font, looks like an OS dialog             |
| Cambria                | strong-avoid | Default serif alternative to Calibri                     |
| Trebuchet MS           | strong-avoid | Dated web-era font                                       |
| Tahoma                 | strong-avoid | Another Windows system font                              |
| Consolas / Courier New | strong-avoid | Monospace — wrong for presentations (except code slides) |

`hard-ban`: never use. `strong-avoid`: acceptable only when user explicitly requests.

## Font selection guidelines

You may freely choose any font **not** in the banned list above,
subject to these principles:

1. **Prefer Google Fonts** — freely available, no licensing issues,
   wide language coverage.
2. **Match the deck's tone** — pick fonts whose visual personality
   fits the audience and topic (e.g., geometric sans for tech,
   humanist serif for editorial, rounded sans for playful).
3. **Heading ≠ body is optional** — a single versatile family
   (with enough weight range) works well; mixing two families is
   fine when they create intentional contrast (e.g., serif heading +
   sans body).
4. **Verify weight range** — the chosen family should offer at
   least Regular and Bold; SemiBold / Light are a bonus.
5. **Avoid pairing two decorative / display fonts** — at most one
   high-personality font per deck (use it for headings).

### Example Latin pairings (for reference, not exhaustive)

| Heading           | Body              | Style                            |
| ----------------- | ----------------- | -------------------------------- |
| Playfair Display  | Source Sans 3     | Formal, authoritative            |
| DM Sans           | DM Sans           | Clean, modern                    |
| Plus Jakarta Sans | Plus Jakarta Sans | Friendly, professional           |
| Fraunces          | Inter             | Expressive heading, neutral body |
| Manrope           | Manrope           | Geometric, technical             |
| Outfit            | Outfit            | Contemporary, versatile          |
| Lora              | Source Sans 3     | Warm, editorial                  |

### CJK (Chinese / Japanese / Korean) fonts

Most Latin-only fonts (DM Sans, Inter, Manrope …) contain **zero**
CJK glyphs. If the deck content includes CJK text, you **must**
set an East Asian font — otherwise PowerPoint falls back to the OS
default (e.g., 等线 / SimSun) and the result looks unintentional.

**Recommended CJK fonts** (all open-source / Google Fonts):

| Font                        | Type       | Style / Use                                                      |
| --------------------------- | ---------- | ---------------------------------------------------------------- |
| Noto Sans SC (思源黑体)     | Sans-serif | Clean, modern, excellent weight range (Thin–Black). Best default |
| Noto Serif SC (思源宋体)    | Serif      | Editorial, formal, pairs well with Noto Sans SC                  |
| LXGW WenKai (霞鹜文楷)      | Kai / 楷书 | Literary, warm, handwritten feel — good for storytelling decks   |
| LXGW Neo XiHei (霞鹜新晰黑) | Sans-serif | Tight, technical, slightly narrower than Noto Sans SC            |
| Xiaolai SC (小赖字体)       | Rounded    | Playful, friendly — great for kids / casual topics               |

**CJK + Latin pairing strategy:**

- **Same-family match:** Noto Sans SC already includes harmonized
  Latin glyphs — using it alone for both scripts is perfectly fine.
- **Cross-family pair:** Set a Latin font for `typeface` and a CJK
  font for `ea_typeface` (East Asian typeface in python-pptx). The
  CJK font handles Chinese characters; the Latin font handles A–Z
  and numbers. Example: DM Sans (Latin) + Noto Sans SC (CJK).
- **Avoid mixing serif CJK + sans Latin** (or vice versa) unless
  creating deliberate contrast for headings.

### Default font policy

| Content language      | Default heading | Default body |
| --------------------- | --------------- | ------------ |
| Latin-only (EN, etc.) | DM Sans         | DM Sans      |
| Chinese or CJK-mixed  | Noto Sans SC    | Noto Sans SC |

When a deck contains **both** Latin and Chinese text, set
**Noto Sans SC** as the primary font. Its built-in Latin glyphs
are well-designed and visually consistent — no separate Latin font
is needed unless the user requests a specific one.

When the user specifies a Latin-only font (e.g., "use Playfair
Display") for a Chinese deck, pair it with **Noto Sans SC** as the
East Asian typeface automatically.

---

## Colors — banned patterns

| Banned                                                 | Severity     | Why                                                                                                                                                              |
| ------------------------------------------------------ | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Rainbow gradients                                      | hard-ban     | Never professional                                                                                                                                               |
| Primary blue `0070C0`                                  | hard-ban     | PowerPoint default accent — instantly recognizable as "no design"                                                                                                |
| Default red `FF0000` / green `00B050`                  | hard-ban     | Traffic-light cliche, poor accessibility                                                                                                                         |
| Pure black text (`000000`)                             | strong-avoid | Too harsh. Use `1E293B` or similar dark slate                                                                                                                    |
| Pure white background only                             | strong-avoid | Monotonous. Alternate with `backgroundAlt` for variety                                                                                                           |
| Neon / fully saturated colors                          | strong-avoid | Low contrast with text, screen fatigue                                                                                                                           |
| More than 3 strong colors (non-neutral palette tokens) | strong-avoid | Visual noise. Counts `primary`, `accent`, `accent2`, and any additional chromatic token — excludes `text`, `textMuted`, `background`, `backgroundAlt`, `surface` |

## Text-on-image colors (mandatory)

When a text zone overlays an `image-generated` background — whether
the image fills the canvas (cover, closing, full-bleed slides) or
occupies a partial zone with a scrim — the text color MUST come
from the **light side** of the palette:

| ✓ Allowed (light side)                    | ✗ Banned on image backgrounds                       |
| ----------------------------------------- | --------------------------------------------------- |
| `background`, `backgroundAlt`, `surface`  | `secondary`, `accent2`, `text`, `textMuted`         |
| `accent` (only for short emphasis labels) | `primary` (the dark base — invisible on dark image) |

**Rule of thumb.** Any palette token darker than `#999999` will
fail contrast over a typical dark / atmospheric image. When in
doubt, pick `background` or `backgroundAlt`.

**Scope:** applies to `image-generated` full-bleed backgrounds
and partial image zones with `scrim` overlays. Does NOT apply to
`solid` / `tinted` / `gradient` backgrounds or shape-decorated
dark backgrounds (no image variability to worry about).

---

## Layout — banned patterns

| Banned                                           | Severity     | Why                                                                                        |
| ------------------------------------------------ | ------------ | ------------------------------------------------------------------------------------------ |
| Drop shadows on text                             | hard-ban     | Dated effect. Use contrast (dark bg + light text) instead                                  |
| Sub-bullets (nested lists)                       | hard-ban     | Indicates the content isn't decomposed properly. Flatten or restructure                    |
| Decorative clip art or generic stock icons       | hard-ban     | Cheap look. Use no icon rather than a bad icon                                             |
| Text smaller than 11pt                           | hard-ban     | Unreadable in presentation context. Minimum body: 12pt, minimum caption: 10pt              |
| More than 6 bullet points per slide              | hard-ban     | Information overload. Split into multiple slides                                           |
| Full sentences as bullet points                  | strong-avoid | Bullet points are fragments. Full sentences go in paragraphs or speaker notes              |
| Center-aligned body text                         | strong-avoid | Hard to scan. Body text must be left-aligned (title-only slides excepted)                  |
| Walls of text (> 8 lines continuous paragraph)   | strong-avoid | Audience cannot read this in real-time. Summarize or split                                 |
| Centered title + centered body on the same slide | strong-avoid | Everything floats with no anchor. Left-align body under centered title, or left-align both |

---

## Shape and decoration — banned patterns

| Banned                                               | Severity     | Why                                                                                                                                                                                                                                                                                                                                         |
| ---------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 3D effects on shapes                                 | hard-ban     | Dated. Use flat design with subtle color differentiation                                                                                                                                                                                                                                                                                    |
| Busy backgrounds (patterns, photos under dense text) | hard-ban     | Destroys readability. Dark solid or light solid only                                                                                                                                                                                                                                                                                        |
| Decorative short underline/dash beneath the title    | hard-ban     | Cliché "template" tic that adds nothing. Applies to **both** section/divider slides and content slides. If the title needs separation from the body, use whitespace, a full-width hairline tied to the layout grid, or a vertical accent bar to the left of the title — never a centered/short horizontal dash dropped under the title text |
| Thick borders (> 1pt) on content shapes              | strong-avoid | Heavy, distracting. Use fill color or thin hairline (0.5pt)                                                                                                                                                                                                                                                                                 |
| Underline for emphasis                               | strong-avoid | Looks like a hyperlink. Use **bold** or color accent                                                                                                                                                                                                                                                                                        |
| ALL CAPS for body text                               | strong-avoid | Shouting. ALL CAPS only for short labels (< 4 words)                                                                                                                                                                                                                                                                                        |
| Multiple decoration styles on one slide              | strong-avoid | One motif per slide. Accent bar OR side stripe, not both                                                                                                                                                                                                                                                                                    |

---

## Content labeling — banned patterns

| Banned                                                                               | Severity     | Why / what to do instead                                                                                                                                                                               |
| ------------------------------------------------------------------------------------ | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Labeling section/divider slides as `Act 01`, `Act 02`, `Chapter 01`, `Part 01`, etc. | hard-ban     | "Act" is internal narrative-blueprint vocabulary (see `actStructure` in s03/s05 artifacts) — it must **never** leak into rendered slide text.                                                          |
| Numbered eyebrow on section slides                                                   | strong-avoid | If a number is genuinely useful, render it bare — `01`, `02` (oversized numeral or small eyebrow) — never `Act 01` / `Section 01` / `Part 01`.                                                         |
| Number + label on every section                                                      | strong-avoid | In most decks, drop the number entirely and let the **section title itself** carry the slide. Reserve numbered eyebrows for decks where the audience needs to track progress through a fixed sequence. |

---

## Image — mandatory rules

| Rule                                 | Rationale                                                                                                                                                                                    |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Preserve original aspect ratio**   | Stretched or squashed images look unprofessional. Use `sizing: { type: 'contain' }` or calculate display dimensions from actual image width/height                                           |
| **No image reuse across slides**     | Each image file may appear on at most **one** slide in the deck. If multiple slides could use the same diagram, assign it to the single best-fit slide; use text-only layouts for the others |
| **Calculate dimensions from source** | Before placing an image, read its actual pixel dimensions and compute aspect-ratio-preserving `w`/`h` that fits within the layout zone. Center the image within the zone                     |
