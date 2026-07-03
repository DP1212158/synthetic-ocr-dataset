#!/usr/bin/env python3
"""Rebuild a classified synthetic-data version index and top-level reports."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_font(size: int):
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        p = Path(candidate)
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in version_dir.iterdir()
        if p.is_dir()
        and len(p.name) >= 3
        and p.name[:2].isdigit()
        and (p / "metadata" / "html_manifest.json").exists()
        and (p / "metadata" / "render_manifest.json").exists()
    )


def make_contact_sheet(items: list[dict[str, Any]], out_path: Path) -> None:
    thumb_w, thumb_h = 260, 360
    cols = 4
    rows = math.ceil(len(items) / cols) or 1
    pad = 22
    caption_h = 58
    sheet = Image.new("RGB", (cols * (thumb_w + pad) + pad, rows * (thumb_h + caption_h + pad) + pad), "#f1f3f5")
    draw = ImageDraw.Draw(sheet)
    title_font = safe_font(18)
    small_font = safe_font(15)
    for idx, item in enumerate(items):
        row, col = divmod(idx, cols)
        x = pad + col * (thumb_w + pad)
        y = pad + row * (thumb_h + caption_h + pad)
        img = Image.open(item["image"]).convert("RGB")
        img.thumbnail((thumb_w, thumb_h), Image.LANCZOS)
        bg = Image.new("RGB", (thumb_w, thumb_h), "white")
        bg.paste(img, ((thumb_w - img.width) // 2, (thumb_h - img.height) // 2))
        sheet.paste(bg, (x, y))
        draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline="#9aa3ad", width=1)
        draw.text((x, y + thumb_h + 7), item["document_id"], fill="#1f2937", font=title_font)
        caption = f"{item.get('category_cn', item.get('category'))} blocks={item['blocks']} ov={item['overflow_blocks']}"
        draw.text((x, y + thumb_h + 31), caption, fill="#4b5563", font=small_font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def overlay_path_for(item: dict[str, Any]) -> str:
    label_path = Path(item["label"])
    return str(label_path.parents[1] / "reports" / "overlays" / f"{item['document_id']}_overlay.jpg")


def rebuild(version_dir: Path) -> dict[str, Any]:
    reports_dir = version_dir / "reports"
    by_category_dir = reports_dir / "by_category"
    by_category_dir.mkdir(parents=True, exist_ok=True)

    all_items: list[dict[str, Any]] = []
    html_manifest: list[dict[str, Any]] = []
    render_manifest: list[dict[str, Any]] = []
    category_plan: list[dict[str, Any]] = []
    category_summary: dict[str, Any] = {}

    for cat_dir in category_dirs(version_dir):
        html_items = read_json(cat_dir / "metadata" / "html_manifest.json")
        render_items = read_json(cat_dir / "metadata" / "render_manifest.json")
        qa_summary = read_json(cat_dir / "reports" / "qa_summary.json")
        if not html_items:
            continue
        category = html_items[0]["category"]
        category_cn = html_items[0].get("category_cn") or cat_dir.name
        for item in qa_summary["items"]:
            item["category_cn"] = category_cn
        all_items.extend(qa_summary["items"])
        html_manifest.extend(html_items)
        render_manifest.extend(render_items)
        category_plan.append({"category": category, "category_cn": category_cn, "samples": len(html_items), "folder": cat_dir.name})
        category_summary[category] = {
            "category_cn": category_cn,
            "folder": cat_dir.name,
            "total": qa_summary["total_images"],
            "passed_basic": qa_summary["passed_basic"],
            "total_blocks": qa_summary["total_blocks"],
            "overflow_blocks": qa_summary["total_overflow_blocks"],
            "out_of_bounds_blocks": qa_summary["total_out_of_bounds_blocks"],
            "cyrillic_blocks": qa_summary["total_cyrillic_blocks"],
            "tibetan_small_mark_blocks": qa_summary["total_tibetan_small_mark_blocks"],
        }
        for name in ["contact_sheet.jpg", "contact_sheet_with_boxes.jpg"]:
            src = cat_dir / "reports" / name
            if not src.exists():
                continue
            suffix = "_with_boxes.jpg" if "with_boxes" in name else ".jpg"
            shutil.copy2(src, by_category_dir / f"{category}{suffix}")

    summary = {
        "dataset_dir": str(version_dir),
        "total_images": len(all_items),
        "passed_basic": sum(1 for item in all_items if item["pass_basic"]),
        "failed_basic": [item["document_id"] for item in all_items if not item["pass_basic"]],
        "total_blocks": sum(item["blocks"] for item in all_items),
        "total_overflow_blocks": sum(item["overflow_blocks"] for item in all_items),
        "total_out_of_bounds_blocks": sum(item["out_of_bounds_blocks"] for item in all_items),
        "total_cyrillic_blocks": sum(item["cyrillic_blocks"] for item in all_items),
        "total_tibetan_small_mark_blocks": sum(item["tibetan_small_mark_blocks"] for item in all_items),
        "category_summary": category_summary,
        "items": all_items,
    }

    write_json(version_dir / "metadata" / "html_manifest.json", html_manifest)
    write_json(version_dir / "metadata" / "render_manifest.json", render_manifest)
    write_json(version_dir / "metadata" / "category_plan.json", category_plan)
    write_json(reports_dir / "qa_summary.json", summary)

    make_contact_sheet(all_items, reports_dir / "contact_sheet.jpg")
    make_contact_sheet([{**item, "image": overlay_path_for(item)} for item in all_items], reports_dir / "contact_sheet_with_boxes.jpg")

    rows = "\n".join(
        f"| {stats['folder']} | {stats['category_cn']} | {stats['total']} | {stats['passed_basic']} | "
        f"{stats['total_blocks']} | {stats['overflow_blocks']} | {stats['out_of_bounds_blocks']} |"
        for stats in category_summary.values()
    )
    md = f"""# {version_dir.name} QA 汇总

- 图片总数：{summary['total_images']}
- 基础通过：{summary['passed_basic']} / {summary['total_images']}
- 标签块数：{summary['total_blocks']}
- overflow blocks：{summary['total_overflow_blocks']}
- out-of-bounds blocks：{summary['total_out_of_bounds_blocks']}
- 西里尔残留：{summary['total_cyrillic_blocks']}
- 藏文小圆圈/装饰符号残留：{summary['total_tibetan_small_mark_blocks']}

## 总览图

- `reports/contact_sheet.jpg`
- `reports/contact_sheet_with_boxes.jpg`
- `reports/by_category/`

## 类别汇总

| 目录 | 类别 | 图片数 | 通过 | 标注块 | overflow | out_of_bounds |
|---|---|---:|---:|---:|---:|---:|
{rows}
"""
    (reports_dir / "QA_REPORT.md").write_text(md, encoding="utf-8")

    readme = f"# {version_dir.name}\n\n本目录是 JSON 结构树驱动版式的分类版。当前包含 {len(category_plan)} 类，每类 6 张，共 {summary['total_images']} 张。\n\n## 类别\n\n"
    for row in category_plan:
        readme += f"- `{row['folder']}`：{row['category_cn']}\n"
    readme += f"""

每个类别目录内包含：

- `html/`
- `images/`
- `labels/`
- `metadata/`
- `reports/`

## QA 汇总

- 图片总数：{summary['total_images']}
- 基础通过：{summary['passed_basic']} / {summary['total_images']}
- 标签块数：{summary['total_blocks']}
- overflow blocks：{summary['total_overflow_blocks']}
- out-of-bounds blocks：{summary['total_out_of_bounds_blocks']}
- 西里尔残留：{summary['total_cyrillic_blocks']}
- 藏文小圆圈/装饰符号残留：{summary['total_tibetan_small_mark_blocks']}

## 总览入口

- `reports/QA_REPORT.md`
- `reports/qa_summary.json`
- `reports/contact_sheet.jpg`
- `reports/contact_sheet_with_boxes.jpg`
- `reports/by_category/`
"""
    (version_dir / "README.md").write_text(readme, encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    args = parser.parse_args()
    summary = rebuild(Path(args.version_dir))
    print(json.dumps({k: summary[k] for k in ["total_images", "passed_basic", "failed_basic", "total_blocks", "total_overflow_blocks", "total_out_of_bounds_blocks"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
