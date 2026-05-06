"""Example script for the SKILL.

Replace this with the actual script. Conventions:
  - CLI parameterized (no hardcoded paths)
  - `--help` works
  - No hidden side effects unless `--write` is passed
  - No network access
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="TODO: describe what this script does")
    parser.add_argument("--input", required=True, help="TODO")
    parser.add_argument("--write", action="store_true", help="Apply changes to disk")
    args = parser.parse_args()

    print(f"input={args.input} write={args.write}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
