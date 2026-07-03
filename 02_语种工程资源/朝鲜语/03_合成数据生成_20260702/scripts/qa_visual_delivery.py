#!/usr/bin/env python3
"""Visual delivery QA for synthetic OCR datasets.

This catches failure modes that basic box QA misses: repeated image assets,
extreme aspect ratios, excessive blank pages, and vertical Mongolian layout
collapse.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(p for p in version_dir.iterdir() if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit())


def image_for_label(label_path: Path) -> Path | None:
    image_dir = label_path.parents[1] / "images"
    for suffix in [".png", ".jpg", ".jpeg", ".webp"]:
        candidate = image_dir / f"{label_path.stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


def crop_blank_ratio(image: Image.Image, box: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = box
    if x2 <= x1 or y2 <= y1:
        return 1.0
    gray = image.crop(box).convert("L")
    stat = ImageStat.Stat(gray)
    mean = float(stat.mean[0])
    pixels = list(gray.getdata())
    ink = sum(1 for px in pixels if abs(px - mean) >= 18)
    return 1.0 - (ink / max(len(pixels), 1))


def document_content_bbox(label: dict[str, Any], width: int, height: int) -> tuple[int, int, int, int] | None:
    boxes = []
    for block in label.get("blocks", []):
        c = block.get("coordinates") or {}
        try:
            x1 = max(0, min(width, int(float(c.get("x_min", 0)))))
            y1 = max(0, min(height, int(float(c.get("y_min", 0)))))
            x2 = max(0, min(width, int(float(c.get("x_max", 0)))))
            y2 = max(0, min(height, int(float(c.get("y_max", 0)))))
        except Exception:
            continue
        if x2 > x1 and y2 > y1:
            boxes.append((x1, y1, x2, y2))
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def qa_version(version_dir: Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or {}
    writing_mode = str(profile.get("css_writing_mode", "horizontal-tb")).lower()
    is_vertical = writing_mode.startswith("vertical") or str(profile.get("cleanup_profile", "")) == "traditional_mongolian"
    max_aspect = 3.2 if not is_vertical else 4.2
    max_side = 3800 if not is_vertical else 3600
    max_blank_ratio = 0.985
    min_content_area_ratio = 0.025 if not is_vertical else 0.035

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    docs = 0
    aspect_values: list[float] = []
    content_area_ratios: list[float] = []

    for label_path in sorted(version_dir.glob("*/labels/*.json")):
        image_path = image_for_label(label_path)
        if image_path is None:
            failures.append({"document": str(label_path), "issue": "missing_image_for_label"})
            continue
        docs += 1
        image = Image.open(image_path).convert("RGB")
        width, height = image.size
        aspect = max(width / max(height, 1), height / max(width, 1))
        aspect_values.append(round(aspect, 4))
        label = read_json(label_path)
        bbox = document_content_bbox(label, width, height)
        content_area_ratio = 0.0
        blank_ratio = 1.0
        if bbox:
            content_area_ratio = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / max(width * height, 1)
            blank_ratio = crop_blank_ratio(image, bbox)
        content_area_ratios.append(round(content_area_ratio, 4))
        doc_id = label.get("attributes", {}).get("document_id") or label_path.stem
        category = label.get("attributes", {}).get("category") or label_path.parts[-3]
        if aspect > max_aspect:
            failures.append({"document_id": doc_id, "category": category, "issue": "extreme_aspect_ratio", "size": [width, height], "aspect": round(aspect, 3), "limit": max_aspect})
        if max(width, height) > max_side:
            failures.append({"document_id": doc_id, "category": category, "issue": "extreme_canvas_side", "size": [width, height], "limit": max_side})
        if content_area_ratio < min_content_area_ratio:
            failures.append({"document_id": doc_id, "category": category, "issue": "low_content_area_ratio", "ratio": round(content_area_ratio, 4), "limit": min_content_area_ratio})
        if blank_ratio > max_blank_ratio:
            warnings.append({"document_id": doc_id, "category": category, "issue": "very_blank_content_bbox", "blank_ratio": round(blank_ratio, 4)})

    image_manifest_path = version_dir / "metadata" / "image_asset_manifest.json"
    image_assets = []
    if image_manifest_path.exists():
        manifest = read_json(image_manifest_path)
        image_assets = [str(row.get("asset_id")) for row in manifest]
        if len(set(image_assets)) < len(image_assets):
            failures.append({"issue": "duplicate_image_assets_within_version", "slots": len(image_assets), "unique": len(set(image_assets))})

    summary = {
        "version_dir": str(version_dir),
        "documents": docs,
        "is_vertical": is_vertical,
        "max_aspect": max(aspect_values) if aspect_values else 0,
        "min_content_area_ratio": min(content_area_ratios) if content_area_ratios else 0,
        "image_slots": len(image_assets),
        "unique_image_assets": len(set(image_assets)),
        "failures": failures,
        "warnings": warnings,
        "pass": docs == 72 and not failures,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    parser.add_argument("--language-profile")
    args = parser.parse_args()
    version_dir = Path(args.version_dir)
    profile = read_json(Path(args.language_profile)) if args.language_profile else {}
    summary = qa_version(version_dir, profile)
    write_json(version_dir / "reports" / "visual_delivery_summary.json", summary)
    rows = "\n".join(
        f"| {item.get('category', '')} | {item.get('document_id', '')} | {item['issue']} | {json.dumps(item, ensure_ascii=False)} |"
        for item in summary["failures"] + summary["warnings"][:20]
    )
    (version_dir / "reports" / "QA_VISUAL_DELIVERY_REPORT.md").write_text(
        f"""# Visual Delivery QA

- 文档数：{summary['documents']}
- 竖排模式：{summary['is_vertical']}
- 最大长宽比：{summary['max_aspect']}
- 最小内容面积比：{summary['min_content_area_ratio']}
- 图片槽位：{summary['image_slots']}
- 唯一图片：{summary['unique_image_assets']}
- 失败项：{len(summary['failures'])}
- 警告项：{len(summary['warnings'])}
- 结论：{'通过' if summary['pass'] else '需处理'}

| 类别 | 文档 | 问题 | 详情 |
|---|---|---|---|
{rows}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2)[:6000])
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
