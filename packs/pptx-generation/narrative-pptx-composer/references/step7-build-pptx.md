# Step 7 — Build PPTX

Full procedural detail for Step 7. See [SKILL.md](../SKILL.md)
for the mandatory rules summary.

One generation path: `python-pptx`.

Inputs: `s05-slide-visual-design.json` + `s06-slide-content.json` +
`s05b-style-policy.json`.
Output: `output.pptx`.

---

## 7a — Generate the Build Script

Write a `s07-build.py` script that uses **per-slide builder functions**
with shared helpers from `$COMPOSER_SKILL/scripts/s07_slide_helpers.py`.

The script:

1. Creates a new `Presentation()` and sets slide dimensions from
   `s01d-design-config.json`.
2. Loads `s06-slide-content.json`, `s05b-style-policy.json`, and
   (when the deck has formula zones, or unconditionally — load is
   harmless when absent) `s05-slide-visual-design.json`.
3. **Formula pre-pass (when any `type: "formula"` zone exists).**
   Call `render_formulas(plan, content, session_dir=SESSION,
   style_policy=style)` once at the top of `main()`. This walks the
   plan + content, renders every mathtext expression to PNG @ 300dpi
   under `<session>/formulas/<taskId>-<role>.png` with a `.png.sig`
   sidecar for cache invalidation, and returns a dict
   `(taskId, role) → cache_path` for the per-slide builders to look
   up. Per-slide builders then call `add_formula(..., cache_path=...)`
   with the cached artifact (zero per-slide rendering cost). Full
   contract + worked example:
   [build-script-template.md § Formula zones](build-script-template.md);
   design background:
   [sessions/formula-svg-design-2026-05-01.md](../../../../sessions/formula-svg-design-2026-05-01.md).
4. Defines builder functions, one per `taskId` by default
   (`build_s01`, `build_s02`, …). When two or more slides share
   an identical layout pattern, promote the body to a shared
   `build_<composition>` (e.g. `build_card_grid`,
   `build_diagram_callouts`) and map each reusing `taskId` to it
   in the dispatch table. **Disallowed:** a single generic
   `build_slide(tid)` that branches on `layoutPattern` internally —
   it pushes composition logic into a switch statement and defeats
   the per-slide builder rationale.

   Each builder:
   a. Creates a slide with `prs.slides.add_slide(blank_layout)`.
   b. Sets the background via `set_slide_bg()`.
   c. Adds shapes, text boxes, images, and (when present) formulas
      using shared helpers (`add_textbox`, `add_card`,
      `add_accent_bar`, `add_rounded_rect`, `add_image_safe`,
      `resolve_image_path`, `add_formula`) with full compositional
      control.
   d. Reads slot text from `s06-slide-content.json` via `get_slot()`.
   e. Adds speaker notes via `add_speaker_notes()`.
5. Maps each `taskId` to its builder function and iterates
   `s06-slide-content.json` in order. Shared builders appear
   multiple times in the map; per-slide builders appear once.
6. Calls `prs.save()`.

**See [build-script-template.md](build-script-template.md)
for the full Python skeleton, the shared helpers library, and the
python-pptx critical rules.** Start from that template and adapt
per slide visual design.

### Batching (large decks)

When `totalSlides` exceeds the dynamic threshold for Step 7a
(default ~15 slides), generate `s07-build.py` in batches following
the unified protocol in
[batching-strategy.md](batching-strategy.md) § Step 7a.

The batch unit is **act-based** (same as other steps), but the
merge order is **code-structural**: header → per-act builders →
dispatch table + `__main__`. See batching-strategy.md for the
full assembly sequence.

**Cross-batch validation:** run `python s07-build.py`. A
`SyntaxError` or `NameError` means a batch referenced an undefined
name — fix the specific batch and re-run.

### Step 7 owns no fitting decisions

Font sizes and slot text in `s06-slide-content.json` are guaranteed
to fit by Step 6b's two-stage trimming. Builders **always** use
`add_textbox`; do not call `add_textbox_autofit` speculatively. A
runtime shrink at Step 7 masks Step 6b heuristic errors instead of
fixing them. The helper still exists in `s07_slide_helpers.py` as
an escape hatch; if you reach for it, log the trigger in
`s09-session-retrospective.json` so the 6b heuristic can be tuned.

---

## 7b — Execute

```bash
python s07-build.py
python $COMPOSER_SKILL/scripts/s07_validate_build.py "$SESSION"
```

**Checkpoint 7b.** The validator runs three cheap structural checks
that would otherwise only surface in Step 8 after a full render:

1. **Slide count** — `len(prs.slides) == len(s06.slides)`. A mismatch
   usually means a `taskId` is missing from the dispatch table or a
   builder emits more than one slide.
2. **Image paths resolve** — every plan zone with a non-null `path`
   (including `layoutSpec.background.path`) points to a file that
   exists on disk. Catches the silent image-path resolution bug
   class (audit 1.5) without needing to render.
3. **Agenda sentinel cleared** — no rendered text frame of length
   ≤ 12 characters still ends with the em-dash `"—"`. If any does,
   the 7c agenda page-number patch did not run for that slot.

Step 8 is still the real downstream gate; this validator only fails
fast on structural defects.

---

## 7c — Post-generation Patches

**Execution shape:** 7c is an **inline tail-block of `s07-build.py`**,
not a separate execution stage and not a separate `s07d-*.py` file.
The convention across sessions is a `patch_agenda_pages()` function
defined at the bottom of `s07-build.py` and called as the last step
before `prs.save()`. The 7c label is preserved as a named rule
because it carries the canonical justification for the `"—"`
sentinel left by Steps 4/5/6.

### Agenda numbering

Minimal post-processing:

1. **Agenda page numbers.** If the deck has an agenda slide whose
   page-number slots carry the em-dash sentinel `"—"`, patch them
   using python-pptx to open the output file, locate the text
   frames, and replace each `"—"` with the actual slide number
   for that act / section.

This is the **canonical source** for the agenda-page-number rule.
Earlier steps (4, 5, 6) leave page-number slots as `"—"` precisely
because final slide order is only known here, after Step 7b
generation. The literal string `"TBD"` must not be used as the
sentinel — `s06_validate_content.py`'s placeholder check
hard-fails on it.

That's it. No orphan cleanup, no Content_Types repair, no connector
shape rejection, no chart cache verification.
