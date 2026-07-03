#!/usr/bin/env python3
"""Collect per-language VL3 outputs into delivery folders and summary index."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def latest_vl3(language_root: Path) -> Path | None:
    candidates = sorted(language_root.glob("03_合成数据生成_*/VL3"))
    candidates = [p for p in candidates if (p / "reports" / "qa_summary.json").exists()]
    return candidates[-1] if candidates else None


def copy_or_link(src: Path, dst: Path, force: bool) -> None:
    if dst.exists():
        if force:
            shutil.rmtree(dst)
        else:
            raise FileExistsError(f"{dst} exists; use --force")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def language_summary(language: str, src: Path, dst: Path) -> dict[str, Any]:
    reports = src / "reports"
    qa = read_json(reports / "qa_summary.json")
    density = read_json(reports / "qa_density_summary.json") if (reports / "qa_density_summary.json").exists() else {}
    acceptance = read_json(reports / "acceptance_summary.json") if (reports / "acceptance_summary.json").exists() else {}
    semantic = read_json(reports / "semantic_reading_order_summary.json") if (reports / "semantic_reading_order_summary.json").exists() else {}
    boxes = read_json(reports / "no_unwanted_text_box_summary.json") if (reports / "no_unwanted_text_box_summary.json").exists() else {}
    validity = read_json(reports / "language_validity_summary.json") if (reports / "language_validity_summary.json").exists() else {}
    image_asset = read_json(reports / "image_asset_summary.json") if (reports / "image_asset_summary.json").exists() else {}
    aug = read_json(reports / "augmentation_quality_summary.json") if (reports / "augmentation_quality_summary.json").exists() else {}
    return {
        "language": language,
        "vl3_dir": str(dst),
        "images": qa.get("total_images", 0),
        "passed_basic": qa.get("passed_basic", 0),
        "failed_basic": qa.get("failed_basic", []),
        "overflow_blocks": qa.get("total_overflow_blocks", 0),
        "out_of_bounds_blocks": qa.get("total_out_of_bounds_blocks", 0),
        "density_warning_images": density.get("warning_images", 0),
        "acceptance_pass": acceptance.get("pass", False),
        "language_validity_pass": validity.get("pass", False),
        "image_asset_pass": image_asset.get("pass", False),
        "directional_light_total": aug.get("directional_light_total", 0),
        "semantic_reading_order_pass": semantic.get("pass", False),
        "no_unwanted_text_box_pass": boxes.get("pass", False),
        "contact_sheet": str(dst / "reports" / "contact_sheet.jpg"),
        "contact_sheet_with_boxes": str(dst / "reports" / "contact_sheet_with_boxes.jpg"),
        "qa_report": str(dst / "reports" / "QA_REPORT.md"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    project_root = Path(args.project_root)
    out_root = project_root / "01_最终VL3数据"
    report_root = project_root / "05_总报告与索引"
    summaries = []
    source_root = project_root / "02_语种工程资源"
    for lang_dir in sorted(p for p in source_root.iterdir() if p.is_dir()):
        src = latest_vl3(lang_dir)
        if not src:
            continue
        dst = out_root / lang_dir.name / "VL3"
        copy_or_link(src, dst, args.force)
        summaries.append(language_summary(lang_dir.name, src, dst))
    payload = {"dataset_name": "少数民族语言多模态OCR合成评估数据_VL3", "languages": summaries}
    write_json(report_root / "VL3_交付索引.json", payload)
    rows = [
        "| 语种 | 图片数 | 基础QA | 密度警告 | 验收 | 语言有效性 | 图片资产 | 光照增强 | 语义阅读顺序 | 去文本框 |",
        "|---|---:|---:|---:|---|---|---|---:|---|---|",
    ]
    for item in summaries:
        rows.append(
            f"| {item['language']} | {item['images']} | {item['passed_basic']} | {item['density_warning_images']} | "
            f"{item['acceptance_pass']} | {item['language_validity_pass']} | {item['image_asset_pass']} | "
            f"{item['directional_light_total']} | {item['semantic_reading_order_pass']} | {item['no_unwanted_text_box_pass']} |"
        )
    (report_root / "VL3_QA_汇总.md").write_text("# VL3 QA 汇总\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps({"languages": len(summaries), "index": str(report_root / "VL3_交付索引.json")}, ensure_ascii=False, indent=2))
    return 0 if len(summaries) == 7 and all(item["acceptance_pass"] for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
