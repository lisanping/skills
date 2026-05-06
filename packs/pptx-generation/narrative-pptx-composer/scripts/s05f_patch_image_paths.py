"""
Step 5f — Patch generated image paths back into s05-slide-visual-design.json.

Reads `s05f-image-selection.json` (preferred) or `s05f-image_generation_output.json`
(no-variations fallback) and writes the selected image path into the
matching `source: "generated"` zones and `image-generated` backgrounds
in `s05-slide-visual-design.json`. Failed groups are marked with
`fallbackApplied: true` so s07-build.py can take the declared fallback path.

Match key: `imageRequest.id` (in the plan) == `originalId` (in
s05f-image-selection.json) or `id` (in s05f-image_generation_output.json).

Usage:
    python s05f_patch_image_paths.py <session_dir>

Idempotent: re-running with the same selection file is a no-op when
paths are already up to date.
"""
import json
import sys
from pathlib import Path

# Force UTF-8 stdout/stderr — the ✓/✗ markers below would otherwise crash
# on Windows cp1252 consoles after path patching is already complete.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_selection_index(session_dir: Path) -> dict[str, dict]:
    """Return {request_id: {"path": str|None, "fallback": bool, "source": str}}.

    Prefers s05f-image-selection.json (VLM picked best of N variations). Falls
    back to s05f-image_generation_output.json (no variations). As a last resort,
    tries image_generation_output.json (legacy name without step prefix).
    Returns {} if no file exists.

    When parsing generation output with variation IDs (e.g. 'bg-cover_v1'),
    the index is keyed by the base ID ('bg-cover') so that plan zones
    referencing the base ID can match.  If only one variation succeeded for
    a base ID, that one is selected automatically.  If multiple succeeded,
    the lowest-numbered variation is used (caller may override via the
    selection file).
    """
    sel = load_json(session_dir / "s05f-image-selection.json")
    if sel and isinstance(sel.get("groups"), list):
        index: dict[str, dict] = {}
        for g in sel["groups"]:
            rid = g.get("originalId") or g.get("id")
            if not rid:
                continue
            selected = g.get("selected")
            index[rid] = {
                "path": selected,
                "fallback": not selected,
                "source": "s05f-image-selection.json",
            }
        return index

    # Selection file with {selections: [{groupId, selectedFile}]} format
    # Also accepts {selections: [{imageId, winnerPath}]} (alias produced by some
    # VLM-subagent prompts — retrospective i7).
    if sel and isinstance(sel.get("selections"), list):
        index = {}
        for g in sel["selections"]:
            rid = g.get("groupId") or g.get("imageId") or g.get("id")
            if not rid:
                continue
            path = (
                g.get("selectedFile")
                or g.get("winnerPath")
                or g.get("path")
            )
            index[rid] = {
                "path": path,
                "fallback": not path,
                "source": "s05f-image-selection.json",
            }
        return index

    # Try generation output files (step-prefixed first, then legacy name)
    out = load_json(session_dir / "s05f-image_generation_output.json")
    if out is None:
        out = load_json(session_dir / "image_generation_output.json")
    if out and isinstance(out.get("results"), list):
        # Group results by base ID (strip _vN suffix)
        import re
        base_groups: dict[str, list[dict]] = {}
        for r in out["results"]:
            rid = r.get("id", "")
            if not rid:
                continue
            # Strip variation suffix: 'bg-cover_v2' -> 'bg-cover'
            base_id = re.sub(r"_v\d+$", "", rid)
            base_groups.setdefault(base_id, []).append(r)
            # Also keep exact id so both base and exact lookups work
            if base_id != rid:
                base_groups.setdefault(rid, []).append(r)

        index = {}
        for base_id, results in base_groups.items():
            # Among successful results, pick variation 1 (or lowest number)
            ok_results = [
                r for r in results
                if r.get("status") == "success" or r.get("output_path") or r.get("path") or r.get("file")
            ]
            if ok_results:
                # Sort by variation number (default 0)
                ok_results.sort(key=lambda r: r.get("variation", 0))
                best = ok_results[0]
                path = best.get("output_path") or best.get("path") or best.get("file")
                # Make path relative to session dir if absolute
                if path:
                    p = Path(path)
                    try:
                        path = str(p.relative_to(session_dir))
                    except ValueError:
                        path = str(p)
                index[base_id] = {
                    "path": path,
                    "fallback": False,
                    "source": "generation_output",
                }
            else:
                index[base_id] = {
                    "path": None,
                    "fallback": True,
                    "source": "generation_output",
                }
        return index

    return {}


def patch_zone(zone: dict, index: dict[str, dict],
               applied: list[tuple[str, str]],
               failed: list[tuple[str, str]],
               vlm_selected: bool) -> None:
    """Patch a single zone (or background dict) with the resolved path.

    `vlm_selected` is True when the path came from a VLM-curated
    s05f-image-selection.json group; False when it was auto-picked
    from the raw generation output (typically v1 of N variations).
    The flag is recorded on the zone as `vlmSelectionApplied` so
    Step 8 QA / validate_plan can warn the operator that the choice
    was not human/VLM curated. See retrospective I-06.
    """
    req = zone.get("imageRequest") or {}
    rid = req.get("id") or zone.get("imageId")
    if not rid or rid not in index:
        return
    entry = index[rid]
    if entry["fallback"]:
        zone["fallbackApplied"] = True
        zone["path"] = None
        zone["vlmSelectionApplied"] = False
        failed.append((rid, "no selection / generation failed"))
    else:
        zone["path"] = entry["path"]
        zone.pop("fallbackApplied", None)
        zone["vlmSelectionApplied"] = bool(vlm_selected)
        applied.append((rid, entry["path"]))


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python s05f_patch_image_paths.py <session_dir>", file=sys.stderr)
        return 2

    session_dir = Path(sys.argv[1]).resolve()
    plan_path = session_dir / "s05-slide-visual-design.json"
    if not plan_path.exists():
        print(f"ERROR: {plan_path} not found", file=sys.stderr)
        return 2

    index = build_selection_index(session_dir)
    if not index:
        print("No s05f-image-selection.json or s05f-image_generation_output.json found "
              "in session — nothing to patch.", file=sys.stderr)
        return 0

    # Detect whether the index came from VLM curation or auto-fallback.
    # build_selection_index records "source" per entry — values starting
    # with "s05f-image-selection" are VLM-curated; "generation_output"
    # means we picked the lowest-numbered variation by ourselves.
    sample_source = next(iter(index.values())).get("source", "") if index else ""
    vlm_selected = sample_source.startswith("s05f-image-selection")
    if not vlm_selected and any("_v" in str(p.get("path", "") or "") for p in index.values()):
        print(
            "WARN: VLM selection file (s05f-image-selection.json) not found — "
            "patch_image_paths fell back to lowest-numbered variation per group. "
            "Step 8 QA should visually inspect the chosen images. "
            "(Affected zones marked vlmSelectionApplied=false.)",
            file=sys.stderr,
        )

    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)

    applied: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []
    unmatched_in_plan: list[str] = []

    for s in plan.get("slides", []):
        spec = s.get("layoutSpec", {})
        bg = spec.get("background")
        if isinstance(bg, dict) and bg.get("type") in ("image", "image-generated"):
            patch_zone(bg, index, applied, failed, vlm_selected)
        for z in spec.get("zones", []):
            if z.get("type") == "image" and z.get("source") == "generated":
                patch_zone(z, index, applied, failed, vlm_selected)

    # Detect ids in selection but not referenced by any zone (informational).
    plan_ids: set[str] = set()
    for s in plan.get("slides", []):
        spec = s.get("layoutSpec", {})
        bg = spec.get("background")
        if isinstance(bg, dict):
            req = bg.get("imageRequest") or {}
            if req.get("id"):
                plan_ids.add(req["id"])
            if bg.get("imageId"):
                plan_ids.add(bg["imageId"])
        for z in spec.get("zones", []):
            req = z.get("imageRequest") or {}
            if req.get("id"):
                plan_ids.add(req["id"])
            if z.get("imageId"):
                plan_ids.add(z["imageId"])
    orphan_ids = sorted(set(index) - plan_ids)

    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    print(f"patched {len(applied)} zones, {len(failed)} marked fallback")
    for rid, path in applied:
        print(f"  ✓ {rid} → {path}")
    for rid, reason in failed:
        print(f"  ✗ {rid} ({reason}) → fallbackApplied")
    if orphan_ids:
        print(f"note: {len(orphan_ids)} selection id(s) not referenced by plan: "
              f"{', '.join(orphan_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
