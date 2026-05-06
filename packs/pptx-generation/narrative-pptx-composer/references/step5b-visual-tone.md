# Step 5b — Derive the Visual Tone

Consult [visual-tone-mapping.md](visual-tone-mapping.md) for the
full decision framework.

Inputs: `s02-communication-brief.json` + `s03-presentation-blueprint.json`
+ `s01c-content-digest.json` + `s04-content-draft.json`.

Compute each dimension:

0. Read `contentDomain` and `imageryDemand` from
   `s03 → architecture` — authoritative, do not re-derive.
1. Visual register — domain × purpose × formality matrix.
   See [visual-tone-register.md](visual-tone-register.md).
2. Per-act visual treatment — color temperature, coupling table,
   background atmosphere (pattern → intensity → coupling → atmosphere).
   See [visual-tone-act-treatment.md](visual-tone-act-treatment.md).
3. Whitespace rhythm — density → minWhitespacePct.
   See [visual-tone-rhythm-contrast.md](visual-tone-rhythm-contrast.md).
4. Visual contrast strategy — from transitionStrategy.
   See [visual-tone-rhythm-contrast.md](visual-tone-rhythm-contrast.md).
5. Impact levels — openingHook/closingAnchor intensity.
   See [visual-tone-impact-imagery.md](visual-tone-impact-imagery.md).
6. Imagery guidance — register defaults + overrides.
   See [visual-tone-impact-imagery.md](visual-tone-impact-imagery.md).

**Write — pass 2 of 3.** Append to `s05b-style-policy.json`:
`visualTone` (all 6 dimensions), `designThesis`,
`compositionPalette`, `titleChoreography`.
Not yet frozen — 5c is the freeze checkpoint.
