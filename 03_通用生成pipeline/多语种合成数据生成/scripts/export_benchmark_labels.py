#!/usr/bin/env python3
"""Export VL12 rich labels into the benchmark (data/raw) compatible schema.

For every ``<version-dir>/<category>/labels/*.json`` this writes a slimmed-down
label into a sibling ``labels_benchmark/`` directory whose schema matches
``synthetic-benchmark/data/raw/*/batch_*/*.json``:

    top:   image_id, file_name, status, attributes, blocks[], created_at, updated_at
    block: block_id, coordinates{x_min,y_min,x_max,y_max}, points,
           block_label, block_content, order(string), attributes

Design decisions (confirmed):
  * points  <- VL12 ``polygon`` 4-point rotated quad (method A); null if absent.
  * status  = "synthetic".
  * doc attributes keep a small provenance subset (yi-style); block attributes = {}.
  * block_label is remapped to the real-data vocabulary; Mongolian vertical text
    blocks map to ``vertical_text``.
  * order is a 0-based string assigned by a global stable sort (reading_order
    first, non-OCR blocks after).

This does NOT touch the original ``labels/`` files.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# --- real-data (benchmark) block_label vocabulary -------------------------
REAL_VOCAB = {
    "text", "image", "vertical_text", "paragraph_title", "number", "doc_title",
    "header", "footer", "table", "vision_footnote", "header_image", "abstract",
    "footnote", "figure_title", "footer_image", "content", "algorithm",
    "aside_text", "reference_content", "chart", "seal", "display_formula",
    "reference", "inline_formula", "formula_number",
}

# VL12 native label -> benchmark label
LABEL_MAP = {
    "document_title": "doc_title",
    "section_title": "paragraph_title",
    "paragraph": "text",
    "list_item": "text",
    "quote": "text",
    "metadata": "text",
    "note": "footnote",
    "caption": "figure_title",
    "page_number": "number",
    "header": "header",
    "footer": "footer",
    "image": "image",
    "figure": "image",
    "photo": "image",
    "table": "table",
}

# labels that are non-text (kept but never forced to vertical_text)
NON_TEXT_LABELS = {"image", "header_image", "footer_image", "chart", "table", "seal"}

def is_mongolian(doc_attrs, version_dir_str):
    lc = (doc_attrs.get("language_code") or "").lower()
    gen = (doc_attrs.get("generator") or "").lower()
    if lc.startswith("mn"):
        return True
    if "mongolian" in gen or "vertical" in gen:
        return True
    if "蒙古" in version_dir_str:
        return True
    return False


def writing_direction(doc_attrs, mongolian):
    if mongolian:
        return "vertical"
    lc = (doc_attrs.get("language_code") or "").lower()
    if lc in {"ug", "kk"} or "阿拉伯" in (doc_attrs.get("script_note") or ""):
        return "rtl"
    return "ltr"


def map_label(src_label, *, is_text, mongolian):
    lbl = LABEL_MAP.get(src_label, src_label)
    if lbl not in REAL_VOCAB:
        lbl = "text" if is_text else lbl
    if mongolian and is_text and lbl not in NON_TEXT_LABELS:
        lbl = "vertical_text"
    return lbl


def _order_key(block, pos):
    ro = block.get("reading_order")
    if isinstance(ro, int):
        return (0, ro, pos)
    attrs = block.get("attributes") or {}
    dom = attrs.get("dom_index")
    if isinstance(dom, int):
        return (1, dom, pos)
    coord = block.get("coordinates") or {}
    return (2, coord.get("y_min", 0), pos)


def _transform_block(blk, new_order, points_mode, mongolian, warnings):
    content = blk.get("block_content") or ""
    is_text = bool(blk.get("is_text", bool(content.strip())))
    src_label = blk.get("block_label") or ("text" if is_text else "image")
    label = map_label(src_label, is_text=is_text, mongolian=mongolian)
    if label not in REAL_VOCAB:
        warnings.append(f"unmapped label kept as-is: {src_label!r}")
    points = None
    if points_mode == "polygon":
        poly = blk.get("polygon")
        if isinstance(poly, list) and len(poly) == 4:
            points = poly
    return {
        "block_id": blk.get("block_id"),
        "coordinates": blk.get("coordinates"),
        "points": points,
        "block_label": label,
        "block_content": content,
        "order": str(new_order),
        "attributes": {},
    }


def transform_document(data, *, points_mode, mongolian, warnings):
    src_attrs = data.get("attributes") or {}
    diag = src_attrs.get("diagnostics") or {}
    aug = diag.get("augmentation") or {}
    wd = writing_direction(src_attrs, mongolian)
    out_attrs = {
        "language_name": src_attrs.get("language_name"),
        "language_code": src_attrs.get("language_code"),
        "script": src_attrs.get("script_note"),
        "writing_direction": wd,
        "generator": src_attrs.get("generator"),
        "category": src_attrs.get("category") or src_attrs.get("template_type"),
        "template_type": src_attrs.get("template_type"),
        "variant": src_attrs.get("variant"),
        "source_version": aug.get("output_version") or "VL12",
        "augmentation_family": aug.get("family"),
    }
    out_attrs = {k: v for k, v in out_attrs.items() if v is not None}

    blocks = data.get("blocks") or []
    ordered = sorted(enumerate(blocks), key=lambda t: _order_key(t[1], t[0]))
    out_blocks = [
        _transform_block(blk, i, points_mode, mongolian, warnings)
        for i, (_, blk) in enumerate(ordered)
    ]
    return {
        "image_id": data.get("image_id"),
        "file_name": data.get("file_name"),
        "status": "synthetic",
        "attributes": out_attrs,
        "blocks": out_blocks,
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


def self_check(doc, path, errors):
    for b in doc["blocks"]:
        try:
            int(b["order"])
        except (TypeError, ValueError):
            errors.append(f"{path}: order not int: {b.get('order')!r}")
        c = b.get("coordinates") or {}
        if not all(k in c for k in ("x_min", "y_min", "x_max", "y_max")):
            errors.append(f"{path}: coordinates missing keys")
        elif not (c["x_min"] < c["x_max"] and c["y_min"] < c["y_max"]):
            errors.append(f"{path}: degenerate box {c}")
        if (b.get("block_content") or "").strip() and b["block_label"] not in REAL_VOCAB:
            errors.append(f"{path}: text label not in vocab: {b['block_label']}")


def run(version_dir, *, points_mode, dry_run):
    version_dir = Path(version_dir)
    vstr = str(version_dir)
    total = 0
    stats_label, stats_points = {}, {"with_points": 0, "null_points": 0}
    errors, warnings = [], []
    for labels_dir in sorted(version_dir.glob("*/labels")):
        if not labels_dir.is_dir():
            continue
        out_dir = labels_dir.parent / "labels_benchmark"
        if not dry_run:
            out_dir.mkdir(exist_ok=True)
        for jf in sorted(labels_dir.glob("*.json")):
            data = json.loads(jf.read_text(encoding="utf-8"))
            mongolian = is_mongolian(data.get("attributes") or {}, vstr)
            doc = transform_document(
                data, points_mode=points_mode, mongolian=mongolian, warnings=warnings
            )
            self_check(doc, str(jf), errors)
            for b in doc["blocks"]:
                stats_label[b["block_label"]] = stats_label.get(b["block_label"], 0) + 1
                stats_points["with_points" if b["points"] else "null_points"] += 1
            total += 1
            if not dry_run:
                (out_dir / jf.name).write_text(
                    json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
                )
    return total, stats_label, stats_points, errors, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export VL12 labels to benchmark schema.")
    ap.add_argument("--version-dir", required=True,
                    help="VL12 dir containing <category>/labels/*.json")
    ap.add_argument("--points-mode", choices=["polygon", "null"], default="polygon")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    total, stats_label, stats_points, errors, warnings = run(
        args.version_dir, points_mode=args.points_mode, dry_run=args.dry_run
    )
    mode = "DRY-RUN" if args.dry_run else "WROTE"
    print(f"[{mode}] documents: {total}  points_mode={args.points_mode}")
    print(f"points: {stats_points}")
    print("block_label distribution:")
    for k in sorted(stats_label, key=lambda x: -stats_label[x]):
        print(f"  {stats_label[k]:6d}  {k}")
    if warnings:
        uniq = sorted(set(warnings))
        print(f"warnings ({len(warnings)} total, {len(uniq)} unique):")
        for w in uniq[:20]:
            print("  " + w)
    if errors:
        print(f"ERRORS ({len(errors)}):", file=sys.stderr)
        for e in errors[:20]:
            print("  " + e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
