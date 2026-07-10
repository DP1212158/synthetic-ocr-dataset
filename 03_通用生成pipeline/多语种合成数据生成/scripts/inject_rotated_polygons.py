#!/usr/bin/env python3
"""Inject tight rotated-quadrilateral `polygon` fields into augmented VL12 labels.

Geometric augmentation (scale/rotate/translate/edge-crop) skews the rendered
page, and the delivered labels already carry the *axis-aligned* bounding box of
each rotated region in ``coordinates`` (verified to enclose the text with 0px
error). For a rotated-text benchmark GT that axis box is too loose, so this
post-process reconstructs the exact 4-corner polygon for every block from the
augmentation recipe stored in ``metadata/augmentation_manifest.json`` and writes
it back into each block as an additive ``polygon`` field. ``coordinates`` is left
untouched for backward compatibility.

Reconstruction is exact: it replays the same forward transform the augmenter
applied to the clean-label corners. A self-check compares the polygon's
axis-aligned envelope against the stored ``coordinates`` and reports any drift.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LANG_BASE = PROJECT_ROOT / "02_语种工程资源"
LANGUAGE_DIRS = ["藏语", "壮语", "朝鲜语", "白语", "维吾尔语", "哈萨克语", "蒙古语"]


def read_json(path: str | Path) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_forward(geometry: dict):
    """Return fwd(x, y) mapping a clean-label pixel to the augmented image."""
    scale = geometry.get("scale", {})
    s = float(scale.get("scale", 1.0))
    sw = int(scale.get("width", 0))
    sh = int(scale.get("height", 0))

    rot = geometry.get("rotation", {})
    ang = float(rot.get("angle_degrees", 0.0))

    tr = geometry.get("translation", {})
    dx = float(tr.get("dx", 0.0))
    dy = float(tr.get("dy", 0.0))

    ec = geometry.get("edge_crop", {})
    left = float(ec.get("left", 0.0))
    top = float(ec.get("top", 0.0))

    if abs(ang) < 0.01:
        a, b, c, d, e, f = 1.0, 0.0, 0.0, 0.0, 1.0, 0.0
    else:
        th = math.radians(ang)
        ct, st = math.cos(th), math.sin(th)
        cx, cy = (sw - 1) / 2.0, (sh - 1) / 2.0
        corners = [(0, 0), (sw, 0), (sw, sh), (0, sh)]
        raw = [(ct * (x - cx) - st * (y - cy), st * (x - cx) + ct * (y - cy)) for x, y in corners]
        minx = min(p[0] for p in raw)
        miny = min(p[1] for p in raw)
        a, b = ct, -st
        c = -ct * cx + st * cy - minx
        d, e = st, ct
        f = -st * cx - ct * cy - miny

    def fwd(x: float, y: float) -> tuple[float, float]:
        x *= s
        y *= s
        x, y = a * x + b * y + c, d * x + e * y + f
        x += dx
        y += dy
        x -= left
        y -= top
        return x, y

    return fwd


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def process_entry(entry: dict) -> dict:
    """Inject polygons for one document. Returns per-doc stats."""
    geometry = entry.get("geometry") or {}
    out_size = entry.get("output_size") or {}
    out_w = float(out_size.get("width", 0)) or 1e9
    out_h = float(out_size.get("height", 0)) or 1e9

    clean = read_json(entry["source_label"])
    aug_path = Path(entry["output_label"])
    aug = read_json(aug_path)

    clean_boxes = {}
    for block in clean.get("blocks", []):
        c = block.get("coordinates") or {}
        if c:
            clean_boxes[block.get("block_id")] = c

    fwd = build_forward(geometry)

    injected = 0
    max_drift = 0.0
    for block in aug.get("blocks", []):
        cc = clean_boxes.get(block.get("block_id"))
        aug_c = block.get("coordinates") or {}
        if not cc or not aug_c:
            continue
        corners = [
            (cc["x_min"], cc["y_min"]),
            (cc["x_max"], cc["y_min"]),
            (cc["x_max"], cc["y_max"]),
            (cc["x_min"], cc["y_max"]),
        ]
        poly = [fwd(x, y) for x, y in corners]
        poly = [(clamp(px, 0.0, out_w), clamp(py, 0.0, out_h)) for px, py in poly]

        # self-check: polygon envelope vs stored axis box
        env = {
            "x_min": min(p[0] for p in poly),
            "y_min": min(p[1] for p in poly),
            "x_max": max(p[0] for p in poly),
            "y_max": max(p[1] for p in poly),
        }
        drift = max(abs(env[k] - aug_c.get(k, env[k])) for k in env)
        max_drift = max(max_drift, drift)

        block["polygon"] = [[round(px, 2), round(py, 2)] for px, py in poly]
        injected += 1

    write_json(aug_path, aug)
    return {"doc": entry.get("document_id"), "injected": injected, "max_drift": round(max_drift, 3)}


def process_language(lang_dir: str, version: str) -> dict | None:
    manifest_path = LANG_BASE / lang_dir / "03_合成数据生成" / version / "metadata" / "augmentation_manifest.json"
    if not manifest_path.exists():
        return None
    entries = read_json(manifest_path)
    total_docs = 0
    total_boxes = 0
    worst_drift = 0.0
    for entry in entries:
        stats = process_entry(entry)
        total_docs += 1
        total_boxes += stats["injected"]
        worst_drift = max(worst_drift, stats["max_drift"])
    return {"language": lang_dir, "docs": total_docs, "polygons": total_boxes, "max_drift": round(worst_drift, 3)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="VL12")
    parser.add_argument("--languages", nargs="*", help="subset of language dir names")
    args = parser.parse_args()

    langs = args.languages or LANGUAGE_DIRS
    print(f"Injecting rotated polygons into {args.version} labels")
    for lang in langs:
        result = process_language(lang, args.version)
        if result is None:
            print(f"- {lang}: no augmentation_manifest (skipped)")
        else:
            print(
                f"- {result['language']}: {result['docs']} docs, "
                f"{result['polygons']} polygons, max_drift={result['max_drift']}px"
            )


if __name__ == "__main__":
    main()