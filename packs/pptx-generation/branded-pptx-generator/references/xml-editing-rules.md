## XML Editing Rules

These rules apply to **all** direct XML edits — Steps 7, 8, and 11.
They are the most common breakage sources:

- **Bold headers and inline labels** — `b="1"` on `<a:rPr>`
- **Never** use unicode bullets (`•`) — use `<a:buChar>` / `<a:buAutoNum>`
- **One `<a:p>` per list item** — never concatenate
- **Copy `<a:pPr>`** from the original paragraph to keep line spacing
- **Smart quotes** as XML entities: `&#x201C;` `&#x201D;` `&#x2018;` `&#x2019;`
- Use `xml:space="preserve"` on `<a:t>` with leading/trailing spaces
- When content has fewer items than the template's slot count,
  **delete the unused shapes/text boxes entirely** — don't just clear text
- Pull colors and fonts from `style-policy.json` (which references theme
  slots in `$PROFILE`); never hardcode hex unless it already matches a
  theme color
- **Never use `<p:cxnSp>` (connector shapes)** in spec-composed or
  augmented-clone slides — always use `<p:sp>` with
  `<a:prstGeom prst="line"/>` plus `<a:tailEnd type="triangle"/>` for
  arrows. Connector shapes carry implicit context (stCxn/endCxn
  references, shape-connection metadata) that is lost during the
  spTree merge pipeline, causing PowerPoint to reject the entire file.
  This failure is undetectable by lxml parsing, python-pptx, or
  `validate.py` — only PowerPoint COM catches it.
- **Never use `xml.etree.ElementTree`** for any OOXML read/write —
  always use `lxml.etree` (see Troubleshooting for details)

---

