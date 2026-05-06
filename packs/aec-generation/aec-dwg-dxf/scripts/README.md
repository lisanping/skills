# aec-dwg-dxf scripts

All scripts assume the `aec-generation` conda environment (or any Python env with
`ezdxf >= 1.1` and `pyyaml`). Run them from this directory so the local imports
of `_common.py` resolve.

| Script                  | Purpose                                                   |
| ----------------------- | --------------------------------------------------------- |
| `extract_titleblock.py` | Pull titleblock metadata from one or many DXF files       |
| `check_layers.py`       | Validate layers against `references/layer-standards.yaml` |
| `generate_index.py`     | Build a sheet list (Markdown / CSV / JSON) from a folder  |
| `batch_rename.py`       | Rename DXF files by titleblock; **dry-run by default**    |
| `query_blocks.py`       | Query INSERT entities and their attributes                |
| `geom_summary.py`       | Entity counts, layer distribution, bounding box           |
| `_make_sample.py`       | Build a minimal `sample.dxf` for smoke testing            |
| `_common.py`            | Shared helpers (do not run directly)                      |

## Quick smoke test

```bash
python _make_sample.py
python extract_titleblock.py sample.dxf
python check_layers.py sample.dxf
python generate_index.py . --format md
python batch_rename.py .                      # dry-run preview
```

## Exit codes

`check_layers.py` exits with `1` when any error-level issue is found, suitable
for CI gating. The other scripts always exit `0` on successful parse.

## Safety

- Scripts never modify the input DXF.
- `batch_rename.py` defaults to `--dry-run`. Pass `--apply` to perform renames,
  which writes a reversible `rename-log.json`.
