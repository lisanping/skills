"""Common helpers for DWG/DXF scripts in the aec-dwg-dxf skill."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import ezdxf
from ezdxf import recover
from ezdxf.document import Drawing


def open_dxf(path: str | Path) -> Drawing:
    """Open a DXF file with automatic structure recovery on failure."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    try:
        return ezdxf.readfile(str(p))
    except ezdxf.DXFStructureError:
        doc, auditor = recover.readfile(str(p))
        if auditor.has_errors:
            for err in auditor.errors:
                print(f"[recover-warn] {err}")
        return doc


def iter_dxf_files(target: str | Path) -> Iterable[Path]:
    """Yield every .dxf file under a path (file or directory)."""
    p = Path(target)
    if p.is_file():
        if p.suffix.lower() == ".dxf":
            yield p
        return
    if p.is_dir():
        yield from sorted(p.rglob("*.dxf"))


def normalize_tag(tag: str) -> str:
    """Normalise an ATTRIB tag for case-insensitive lookup."""
    return tag.strip().upper()


def matches_any(name: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.match(name) for p in patterns)
