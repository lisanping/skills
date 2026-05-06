"""Convert .potx (PowerPoint template) to .pptx (presentation).

The only structural difference between .potx and .pptx is the
ContentType declared in [Content_Types].xml for the main part:
  - .potx: ...presentationml.template.main+xml
  - .pptx: ...presentationml.presentation.main+xml

This script copies the file with a .pptx extension and patches
that single ContentType entry. All other content is preserved
byte-for-byte.

Usage:
    python potx2pptx.py input.potx [-o output.pptx]

If -o is omitted, outputs to the same directory with .pptx extension.
"""

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

TEMPLATE_CT = b"application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"
PRESENTATION_CT = b"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"


def convert(src: Path, dst: Path) -> Path:
    if src == dst:
        raise ValueError("Source and destination must differ")

    tmp = dst.with_suffix(".pptx.tmp")
    try:
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(tmp, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "[Content_Types].xml":
                    data = data.replace(TEMPLATE_CT, PRESENTATION_CT)
                zout.writestr(item, data)
        shutil.move(str(tmp), str(dst))
    finally:
        if tmp.exists():
            tmp.unlink()

    return dst


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert .potx to .pptx by patching ContentType"
    )
    parser.add_argument("input", type=Path, help="Input .potx file")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output .pptx path (default: same name, .pptx)")
    args = parser.parse_args()

    src = args.input.resolve()
    if not src.exists():
        print(f"Error: {src} not found", file=sys.stderr)
        sys.exit(1)
    if src.suffix.lower() != ".potx":
        print(f"Warning: {src.name} is not a .potx file", file=sys.stderr)

    dst = (args.output or src.with_suffix(".pptx")).resolve()
    result = convert(src, dst)
    print(result)


if __name__ == "__main__":
    main()
