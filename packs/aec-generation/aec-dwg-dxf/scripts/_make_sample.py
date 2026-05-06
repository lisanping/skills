"""Build a tiny synthetic DXF with a titleblock for smoke-testing scripts."""
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

DEFAULT_OUT = Path(__file__).parent / "sample.dxf"


def build(out: Path = DEFAULT_OUT) -> Path:
    doc = ezdxf.new(dxfversion="R2018", setup=True)
    msp = doc.modelspace()

    for name, color, lt in [
        ("WALL", 7, "CONTINUOUS"),
        ("DOOR", 4, "CONTINUOUS"),
        ("WINDOW", 5, "CONTINUOUS"),
        ("DIM", 2, "CONTINUOUS"),
        ("TEXT", 7, "CONTINUOUS"),
        ("AXIS", 1, "CENTER"),
        ("TITLEBLOCK", 7, "CONTINUOUS"),
        ("TEMP", 6, "CONTINUOUS"),  # forbidden
    ]:
        doc.layers.add(name, color=color, linetype=lt)

    block = doc.blocks.new(name="TITLEBLOCK_A1")
    block.add_lwpolyline(
        [(0, 0), (594, 0), (594, 100), (0, 100), (0, 0)],
        dxfattribs={"layer": "TITLEBLOCK"},
    )
    for tag, default, x in [
        ("DWG_NO", "A-101", 50),
        ("DWG_NAME", "一层平面图", 200),
        ("REV", "C", 350),
        ("SCALE", "1:100", 420),
        ("DATE", "2026-04-15", 500),
    ]:
        attdef = block.add_attdef(
            tag=tag,
            insert=(x, 50),
            text=default,
            height=5,
        )
        attdef.dxf.layer = "TITLEBLOCK"

    insert = msp.add_blockref(
        "TITLEBLOCK_A1", insert=(0, 0), dxfattribs={"layer": "TITLEBLOCK"}
    )
    insert.add_auto_attribs(
        {
            "DWG_NO": "A-101",
            "DWG_NAME": "一层平面图",
            "REV": "C",
            "SCALE": "1:100",
            "DATE": "2026-04-15",
        }
    )

    msp.add_lwpolyline(
        [(1000, 1000), (5000, 1000), (5000, 4000), (1000, 4000), (1000, 1000)],
        dxfattribs={"layer": "WALL"},
    )
    msp.add_text(
        "OFFICE",
        dxfattribs={"layer": "TEXT", "height": 100},
    ).set_placement((3000, 2500), align=TextEntityAlignment.MIDDLE_CENTER)

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out))
    print(f"Wrote {out}")
    return out


if __name__ == "__main__":
    import sys
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    build(target)
