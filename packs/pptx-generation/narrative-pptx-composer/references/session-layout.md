# Session Artifact Layout

## Naming Convention

- `sN-{name}.json` = step's main output.
- `sN[letter]-{name}.json` = sub-task artifact (e.g. `s04a` = step 4, artifact a).

## Schema Contract

Three artifacts have formal JSON Schema: `s03-presentation-blueprint`, `s05-slide-visual-design`, `s08-qa-log`. The remaining artifacts use `*.example.json` as spec.

## Directory Tree

```
sessions/
└── {timestamp}_{topic}/  ← $SESSION
    ├── s01b-query-intent.json
    ├── s01c-content-digest.json
    ├── s01c-image-style-extraction.json        # if image input
    ├── s01d-design-config.json
    ├── s02-communication-brief.json
    ├── s03-presentation-blueprint.json
    ├── s04a-terminology-registry.json
    ├── s04-content-draft.json
    ├── s05-slide-visual-design.json
    ├── s05b-style-policy.json
    ├── s05f-image-requests.json                # if generating images
    ├── s05f-image_generation_output.json       # if generating images
    ├── s05f-image-selection.json               # if generating images
    ├── images/
    ├── s06-slide-content.json
    ├── s07-build.py
    ├── output.pptx                             # overwritten by rebuilds
    ├── output.pre-perslide-fix.pptx            # if 8b-fix ran
    ├── output.pre-cohort-fix.pptx              # if 8c-fix ran
    ├── s08-qa-log.json
    ├── s08e-perdeck-evaluation.json
    ├── s08f-perdeck-fix-decisions.json          # if 8f ran
    ├── s08g-generation-report.json
    ├── s09-session-retrospective.json
    └── slide-previews/
        ├── per-slide/
        ├── per-slide-verify/                   # if fix ran
        ├── per-cohort-verify/                  # if fix ran
        ├── contact-sheet.jpg                   # 8d
        ├── per-deck-samples/                   # 8d
        └── per-deck-verify/                    # if 8f ran

outputs/  ← $OUTPUTS_DIR                        # sibling of sessions/ at repo root, NEVER a child
└── {topic_slug}_{YYYYMMDD_HHMMSS}.pptx         # cp (not mv) from $SESSION/output.pptx
```

## Routing Rules

- `sessions/` and `outputs/` are siblings at repo root. Step 8d exports `$OUTPUTS_DIR` as absolute path.
- Sessions permanently retained. `output.pptx` overwritten per rebuild; `pre-*-fix.pptx` snapshots preserve fix-cycle starting points.
- Delivery is `cp` (session keeps its copy).
