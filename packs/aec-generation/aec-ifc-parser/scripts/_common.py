"""Common helpers for IFC scripts in the aec-ifc-parser skill."""
from __future__ import annotations

from pathlib import Path

import ifcopenshell


def open_ifc(path: str | Path) -> ifcopenshell.file:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    return ifcopenshell.open(str(p))
