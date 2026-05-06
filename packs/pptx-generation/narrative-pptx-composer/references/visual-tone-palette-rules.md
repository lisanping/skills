# Visual Tone — Dimension 7: Palette Derivation Rules

When `s01d-design-config.json` has `source: "deferred"` (or any
`palette` leaf with provenance `deferred-step5b`), derive the
expanded palette (10 tokens) from the 4 base colors:

| Token           | Derivation from base palette                                   |
| --------------- | -------------------------------------------------------------- |
| `primary`       | User-specified or derived from purpose                         |
| `secondary`     | Lighter tint of primary (40-60% toward white)                  |
| `accent`        | User-specified or complementary to primary                     |
| `accent2`       | Shift accent hue 120-180°, same saturation. For contrast pairs |
| `background`    | White or near-white                                            |
| `backgroundAlt` | 3-5% gray tint of background                                   |
| `surface`       | accent at 8-12% opacity over background. For card fills        |
| `text`          | Dark slate (not pure black)                                    |
| `textMuted`     | text at 50-60% opacity                                         |
| `divider`       | text at 20-30% opacity. For structural lines                   |

---

## Register-aware adjustments

The defaults above are tuned for `analytical`/`conversational`.
Apply per-register overrides:

| Register             | `secondary` tint             | `surface` opacity | `backgroundAlt` tint | `divider` opacity | Notes                                                   |
| -------------------- | ---------------------------- | ----------------- | -------------------- | ----------------- | ------------------------------------------------------- |
| `authoritative`      | 25-40% (deeper, confident)   | 6-9%              | 2-3%                 | 30-40%            | Crisper dividers; surface barely-there                  |
| `analytical`         | 40-60% (default)             | 8-12% (default)   | 3-5% (default)       | 20-30% (default)  | Engineered for data legibility                          |
| `conversational`     | 50-70% (lighter, friendlier) | 12-18%            | 4-6%                 | 15-25%            | Surface tints encode tone; lighter dividers feel open   |
| `inspirational`      | 50-70%                       | 10-15%            | 0-2% (near-pure bg)  | 20-30%            | Backgrounds stay clean for imagery and large type       |
| `instructional-rich` | 35-50%                       | 8-12%             | 3-5%                 | 25-35%            | Slightly stronger dividers for diagram structural lines |

When register and content domain disagree, prefer the register's
opacity range but cap `surface` at 12% so chart legibility is preserved.
