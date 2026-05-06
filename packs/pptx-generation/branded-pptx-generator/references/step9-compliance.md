# Step 9 — Check Compliance

Two cheap deterministic checks before paying for visual QA.

```bash
# Leftover placeholder text
python -m markitdown output.pptx | \
  grep -iE "xxxx|lorem|ipsum|click to|insert|this.*(page|slide).*layout"

# Locked-tier compliance (theme colors, fonts, slide size)
python $SKILL/scripts/compliance_checker.py output.pptx --profile $PROFILE \
  --output compliance-report.json
```

`compliance_checker.py` must report `locked_violations: 0`. Anything
non-zero means a hardcoded color/font or a slide-size mismatch slipped
in — fix at the source slide before continuing.

**Coverage note:** `compliance_checker.py` checks **colors, fonts,
slide size, and WCAG contrast**. The remaining locked elements
defined in [brand-compliance.md](brand-compliance.md) (logo positions,
footer structure, disclaimer/copyright) are not yet automated and
must be verified visually in Step 10.

**Checkpoint:** No leftover placeholders; zero locked violations.
