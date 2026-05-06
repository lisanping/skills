# aec-ifc-parser scripts

All scripts assume the `aec-generation` conda environment (or any Python env
with `ifcopenshell >= 0.8` and `pyyaml`). Run them from this directory so
local imports of `_common.py` resolve.

| Script                | Purpose                                                        |
| --------------------- | -------------------------------------------------------------- |
| `summarize.py`        | Schema, entity counts, spatial structure overview              |
| `extract_by_type.py`  | List entities of one IFC type (optional storey filter)         |
| `query_pset.py`       | Read Pset_* / Qto_* values for a given type                    |
| `spatial_tree.py`     | Print Project → Site → Building → Storey → Element tree        |
| `quantity_takeoff.py` | Aggregate Qto values by type and / or storey                   |
| `qa_check.py`         | Validate naming, required properties, spatial integrity        |
| `model_diff.py`       | Entity-level diff of two IFC files (added / removed / changed) |
| `_make_sample.py`     | Build a minimal `sample.ifc` for smoke testing                 |
| `_common.py`          | Shared helpers (do not run directly)                           |

## Quick smoke test

```bash
python _make_sample.py
python summarize.py sample.ifc
python spatial_tree.py sample.ifc
python query_pset.py sample.ifc IfcWall --pset Pset_WallCommon
python qa_check.py sample.ifc            # exits 1 if errors found
```

## Exit codes

`qa_check.py` exits with `1` when any error-level issue is found (suitable for
CI gating). All other scripts return `0` on successful parse.

## Performance notes

- `summarize.py`, `extract_by_type.py`, `query_pset.py` are O(model size) and
  fast even on 500MB+ models.
- `quantity_takeoff.py` reads Qto attributes only (no geometry computation).
- For geometry-derived quantities (when no `Qto_*BaseQuantities` exists),
  enable `ifcopenshell.geom` separately — it is **off by default** for speed.

## Safety

All scripts are **read-only**. None of them modifies the input IFC.
