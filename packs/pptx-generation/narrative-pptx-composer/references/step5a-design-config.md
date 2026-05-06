# Step 5a — Finalize Design Config

Resolve `s01d-design-config.json` leaves with `deferred-step5b`
provenance. Heuristics:

1. Purpose → palette mood.
2. Formality → typography pairing.
3. Audience → contrast strategy.
4. `secondaryFont` → set to serif/display when register is
   inspirational/creative/editorial, or when brief frames a
   pitch/keynote. Otherwise keep `null`.

`dimensions` is locked at Step 1. 5a may not change it.

**Write — pass 1 of 3.** Create `s05b-style-policy.json`:
`palette`, `typography`, `spacing`, `designLanguage`. Leave
`visualTone` and `designThesis` empty — 5b fills them.
Do not mutate `s01d-design-config.json`.
