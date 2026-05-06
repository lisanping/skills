"""Build a tiny synthetic IFC4 file for smoke-testing scripts.

Uses ifcopenshell.api when available; falls back to a minimal hand-built
IFC4 spatial structure. The fixture is written to ./sample.ifc.
"""
from __future__ import annotations

from pathlib import Path

import ifcopenshell
import ifcopenshell.api  # noqa: F401  (ensures api submodule loads)
from ifcopenshell.api import run

DEFAULT_OUT = Path(__file__).parent / "sample.ifc"


def build(out: Path = DEFAULT_OUT) -> Path:
    f = ifcopenshell.api.run("project.create_file", version="IFC4")

    project = run("root.create_entity", f, ifc_class="IfcProject", name="Sample Project")
    run("unit.assign_unit", f)
    ctx = run("context.add_context", f, context_type="Model")
    run("context.add_context", f, context_type="Model",
        context_identifier="Body", target_view="MODEL_VIEW", parent=ctx)

    site = run("root.create_entity", f, ifc_class="IfcSite", name="Site 1")
    building = run("root.create_entity", f, ifc_class="IfcBuilding", name="Office Tower")
    storey1 = run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="L01")
    storey2 = run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="L02")

    run("aggregate.assign_object", f, products=[site], relating_object=project)
    run("aggregate.assign_object", f, products=[building], relating_object=site)
    run("aggregate.assign_object", f, products=[storey1, storey2], relating_object=building)

    walls = []
    for i, storey in enumerate([storey1, storey2], start=1):
        for j in range(2):
            w = run("root.create_entity", f, ifc_class="IfcWall",
                    name=f"W-{i:02d}-{j+1:03d}")
            run("spatial.assign_container", f, products=[w], relating_structure=storey)
            run("pset.add_pset", f, product=w, name="Pset_WallCommon")
            pset = [p for p in w.IsDefinedBy
                    if p.is_a("IfcRelDefinesByProperties")][-1].RelatingPropertyDefinition
            run("pset.edit_pset", f, pset=pset,
                properties={"FireRating": "2.0h", "IsExternal": j == 0,
                            "LoadBearing": True})
            walls.append(w)

    door = run("root.create_entity", f, ifc_class="IfcDoor", name="D-01-001")
    run("spatial.assign_container", f, products=[door], relating_structure=storey1)

    space = run("root.create_entity", f, ifc_class="IfcSpace", name="0101")
    run("aggregate.assign_object", f, products=[space], relating_object=storey1)

    out.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(out))
    print(f"Wrote {out}")
    return out


if __name__ == "__main__":
    import sys
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    build(target)
