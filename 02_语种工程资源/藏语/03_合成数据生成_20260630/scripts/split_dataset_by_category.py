#!/usr/bin/env python3
"""Split a rendered dataset into per-category folders."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, List


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_name(name: str) -> str:
    return (
        name.replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace("·", "_")
        .replace("（", "_")
        .replace("）", "_")
    )


def copy_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for sub in ["metadata", "reports", "reports/by_category", "reports/overlays"]:
        (output_dir / sub).mkdir(parents=True, exist_ok=True)

    html_manifest = read_json(input_dir / "metadata" / "html_manifest.json")
    render_manifest = read_json(input_dir / "metadata" / "render_manifest.json")
    category_plan = read_json(input_dir / "metadata" / "category_plan.json")
    render_by_id = {item["document_id"]: item for item in render_manifest}

    grouped: Dict[str, List[Dict]] = {}
    category_cn: Dict[str, str] = {}
    for item in html_manifest:
        category = item["category"]
        grouped.setdefault(category, []).append(item)
        category_cn[category] = item.get("category_cn") or category

    ordered_categories = [item["category"] for item in category_plan if item["category"] in grouped]

    summary = []
    for idx, category in enumerate(ordered_categories, 1):
        items = grouped[category]
        folder_name = f"{idx:02d}_{safe_name(category_cn[category])}"
        root = output_dir / folder_name
        for sub in ["html", "images", "labels", "metadata", "reports", "reports/overlays"]:
            (root / sub).mkdir(parents=True, exist_ok=True)

        filtered_render = []
        for item in items:
            document_id = item["document_id"]
            render_item = render_by_id[document_id]
            copy_if_exists(input_dir / "html" / f"{document_id}.html", root / "html" / f"{document_id}.html")
            copy_if_exists(input_dir / "images" / f"{document_id}.png", root / "images" / f"{document_id}.png")
            copy_if_exists(input_dir / "labels" / f"{document_id}.json", root / "labels" / f"{document_id}.json")
            copy_if_exists(
                input_dir / "reports" / "overlays" / f"{document_id}_overlay.jpg",
                root / "reports" / "overlays" / f"{document_id}_overlay.jpg",
            )
            filtered_render.append(render_item)

        write_json(root / "metadata" / "html_manifest.json", items)
        write_json(root / "metadata" / "render_manifest.json", filtered_render)
        write_json(
            root / "metadata" / "category_plan.json",
            [{"category": category, "category_cn": category_cn[category], "samples": len(items)}],
        )

        copy_if_exists(input_dir / "reports" / "by_category" / f"{category}.jpg", root / "reports" / "contact_sheet.jpg")
        copy_if_exists(
            input_dir / "reports" / "by_category" / f"{category}_with_boxes.jpg",
            root / "reports" / "contact_sheet_with_boxes.jpg",
        )

        readme = f"""# {idx:02d} {category_cn[category]}（{category}）

本目录从：

`{input_dir}`

按类别拆分而来，包含该类别的独立文件。

## 目录

- `html/`：HTML 模板
- `images/`：渲染图片
- `labels/`：标签 JSON
- `metadata/`：该类别的 manifest
- `reports/contact_sheet.jpg`：该类别联系图
- `reports/contact_sheet_with_boxes.jpg`：带标签框联系图

## 数量

- 样本数：{len(items)}
"""
        (root / "README.md").write_text(readme, encoding="utf-8")
        summary.append({"folder": folder_name, "category": category, "category_cn": category_cn[category], "samples": len(items)})

    for metadata_name in ["html_manifest.json", "render_manifest.json", "category_plan.json"]:
        copy_if_exists(input_dir / "metadata" / metadata_name, output_dir / "metadata" / metadata_name)
    for report_name in ["QA_REPORT.md", "contact_sheet.jpg", "contact_sheet_with_boxes.jpg", "qa_summary.json"]:
        copy_if_exists(input_dir / "reports" / report_name, output_dir / "reports" / report_name)
    if (input_dir / "reports" / "by_category").exists():
        for report_image in (input_dir / "reports" / "by_category").glob("*.jpg"):
            copy_if_exists(report_image, output_dir / "reports" / "by_category" / report_image.name)

    top_readme_lines = [
        "# 专项优化试跑按类别拆分版",
        "",
        f"来源目录：`{input_dir}`",
        "",
        "## 类别目录",
        "",
    ]
    top_readme_lines.extend(
        f"- `{row['folder']}`：{row['category_cn']}，{row['samples']} 张" for row in summary
    )
    (output_dir / "README.md").write_text("\n".join(top_readme_lines) + "\n", encoding="utf-8")
    write_json(output_dir / "split_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
