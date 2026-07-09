#!/usr/bin/env python3
"""Check visual density and lower-page usage for rendered layout datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


IGNORE_LABELS = {"footer", "page_number"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def dataset_dirs(root: Path) -> list[Path]:
    children = sorted(
        p
        for p in root.iterdir()
        if p.is_dir()
        and len(p.name) >= 3
        and p.name[:2].isdigit()
        and (p / "metadata" / "render_manifest.json").exists()
    )
    if children:
        return children
    if (root / "metadata" / "render_manifest.json").exists():
        return [root]
    return []


def block_rects(label: dict[str, Any]) -> list[dict[str, float]]:
    rects = []
    for block in label.get("blocks", []):
        if block.get("block_label") in IGNORE_LABELS:
            continue
        c = block.get("coordinates") or {}
        if c.get("x_max", 0) - c.get("x_min", 0) < 2 or c.get("y_max", 0) - c.get("y_min", 0) < 2:
            continue
        rects.append(c)
    return rects


def analyze_item(item: dict[str, Any]) -> dict[str, Any]:
    image_path = Path(item["image"])
    label_path = Path(item["label"])
    with Image.open(image_path) as img:
        width, height = img.size
    label = read_json(label_path)
    rects = block_rects(label)
    if not rects:
        content = {"x_min": 0, "y_min": 0, "x_max": 0, "y_max": 0}
    else:
        content = {
            "x_min": min(r["x_min"] for r in rects),
            "y_min": min(r["y_min"] for r in rects),
            "x_max": max(r["x_max"] for r in rects),
            "y_max": max(r["y_max"] for r in rects),
        }
    image_area = max(width * height, 1)
    label_area = sum((r["x_max"] - r["x_min"]) * (r["y_max"] - r["y_min"]) for r in rects)
    lower_blocks = [
        r for r in rects
        if ((r["y_min"] + r["y_max"]) / 2) >= height * 0.55
    ]
    lower_area = 0.0
    for r in rects:
        overlap = max(0.0, r["y_max"] - max(r["y_min"], height * 0.55))
        lower_area += max(0.0, r["x_max"] - r["x_min"]) * overlap
    return {
        "document_id": item["document_id"],
        "category": item.get("category"),
        "layout_name": item.get("layout_name"),
        "image": str(image_path),
        "width": width,
        "height": height,
        "portrait": height >= width * 1.15,
        "blocks": len(rects),
        "content_bbox": {k: round(v, 2) for k, v in content.items()},
        "content_height_ratio": round((content["y_max"] - content["y_min"]) / max(height, 1), 4),
        "top_blank_ratio": round(content["y_min"] / max(height, 1), 4),
        "bottom_blank_ratio": round((height - content["y_max"]) / max(height, 1), 4),
        "label_area_ratio": round(label_area / image_area, 4),
        "lower_half_block_ratio": round(len(lower_blocks) / max(len(rects), 1), 4),
        "lower_half_area_ratio": round(lower_area / max(width * height * 0.45, 1), 4),
    }


def summarize(items: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    warnings = []
    for item in items:
        if args.portrait_only and not item["portrait"]:
            continue
        reasons = []
        if item["bottom_blank_ratio"] > args.max_bottom_blank_ratio:
            reasons.append(f"bottom_blank_ratio>{args.max_bottom_blank_ratio}")
        if item["content_height_ratio"] < args.min_content_height_ratio:
            reasons.append(f"content_height_ratio<{args.min_content_height_ratio}")
        if (
            item["lower_half_block_ratio"] < args.min_lower_half_block_ratio
            and item["lower_half_area_ratio"] < args.min_lower_half_area_ratio
        ):
            reasons.append(f"lower_half_block_ratio<{args.min_lower_half_block_ratio}")
        if reasons:
            warnings.append({**item, "reasons": reasons})

    by_category: dict[str, dict[str, Any]] = {}
    for item in items:
        cat = item.get("category") or "uncategorized"
        stat = by_category.setdefault(cat, {"total": 0, "portrait": 0, "warnings": 0, "avg_bottom_blank_ratio": 0.0, "avg_content_height_ratio": 0.0})
        stat["total"] += 1
        stat["portrait"] += int(item["portrait"])
        stat["avg_bottom_blank_ratio"] += item["bottom_blank_ratio"]
        stat["avg_content_height_ratio"] += item["content_height_ratio"]
    warning_ids = {w["document_id"] for w in warnings}
    for cat, stat in by_category.items():
        cat_items = [item for item in items if (item.get("category") or "uncategorized") == cat]
        stat["warnings"] = sum(1 for item in cat_items if item["document_id"] in warning_ids)
        stat["avg_bottom_blank_ratio"] = round(stat["avg_bottom_blank_ratio"] / max(stat["total"], 1), 4)
        stat["avg_content_height_ratio"] = round(stat["avg_content_height_ratio"] / max(stat["total"], 1), 4)

    return {
        "thresholds": {
            "max_bottom_blank_ratio": args.max_bottom_blank_ratio,
            "min_content_height_ratio": args.min_content_height_ratio,
            "min_lower_half_block_ratio": args.min_lower_half_block_ratio,
            "min_lower_half_area_ratio": args.min_lower_half_area_ratio,
            "portrait_only": args.portrait_only,
        },
        "total_images": len(items),
        "warning_images": len(warnings),
        "warnings": warnings,
        "category_summary": by_category,
        "items": items,
    }


def write_report(summary: dict[str, Any], out_dir: Path) -> None:
    rows = "\n".join(
        f"| {cat} | {stat['total']} | {stat['portrait']} | {stat['warnings']} | {stat['avg_bottom_blank_ratio']} | {stat['avg_content_height_ratio']} |"
        for cat, stat in summary["category_summary"].items()
    )
    warning_rows = "\n".join(
        f"| {item['document_id']} | {item.get('category')} | {item['bottom_blank_ratio']} | {item['content_height_ratio']} | {item['lower_half_block_ratio']} | {item['lower_half_area_ratio']} | {', '.join(item['reasons'])} |"
        for item in summary["warnings"]
    )
    md = f"""# Layout Density QA

- 图片数：{summary['total_images']}
- 风险样本：{summary['warning_images']}
- 最大底部空白阈值：{summary['thresholds']['max_bottom_blank_ratio']}
- 最小内容高度覆盖阈值：{summary['thresholds']['min_content_height_ratio']}
- 最小下半页块比例阈值：{summary['thresholds']['min_lower_half_block_ratio']}
- 最小下半页面积覆盖阈值：{summary['thresholds']['min_lower_half_area_ratio']}
- 仅检查竖版：{summary['thresholds']['portrait_only']}

## 类别汇总

| 类别 | 图片数 | 竖版数 | 风险数 | 平均底部空白 | 平均内容高度覆盖 |
|---|---:|---:|---:|---:|---:|
{rows}

## 风险明细

| 样本 | 类别 | 底部空白 | 内容高度覆盖 | 下半页块比例 | 下半页面积覆盖 | 原因 |
|---|---|---:|---:|---:|---:|---|
{warning_rows}
"""
    (out_dir / "QA_DENSITY_REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", required=True, help="A category dataset dir or a classified version dir.")
    parser.add_argument("--max-bottom-blank-ratio", type=float, default=0.42)
    parser.add_argument("--min-content-height-ratio", type=float, default=0.42)
    parser.add_argument("--min-lower-half-block-ratio", type=float, default=0.12)
    parser.add_argument("--min-lower-half-area-ratio", type=float, default=0.10)
    parser.add_argument("--portrait-only", action="store_true", default=True)
    parser.add_argument("--include-landscape", action="store_false", dest="portrait_only")
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args()

    root = Path(args.dataset_dir)
    items = []
    for dataset_dir in dataset_dirs(root):
        for item in read_json(dataset_dir / "metadata" / "render_manifest.json"):
            items.append(analyze_item(item))

    summary = summarize(items, args)
    report_dir = root / "reports" if (root / "reports").exists() or len(dataset_dirs(root)) > 1 else root / "reports"
    write_json(report_dir / "qa_density_summary.json", summary)
    write_report(summary, report_dir)
    print(json.dumps({k: summary[k] for k in ["total_images", "warning_images"]}, ensure_ascii=False, indent=2))
    return 1 if args.fail_on_warning and summary["warning_images"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
