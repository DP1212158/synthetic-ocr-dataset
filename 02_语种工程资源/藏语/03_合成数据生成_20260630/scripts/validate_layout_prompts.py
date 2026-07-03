#!/usr/bin/env python3
"""Validate structured layout prompt specs for synthetic OCR generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


EXPECTED_CATEGORIES = [
    ("book_page", "书籍页"),
    ("textbook_page", "教科书页"),
    ("newspaper_page", "报纸页"),
    ("magazine_journal", "杂志期刊页"),
    ("academic_paper", "学术文献页"),
    ("historical_classic", "历史文档_古籍"),
    ("notice_announcement", "公告通知"),
    ("exam_paper", "考试卷"),
    ("complex_form", "复杂表单登记页"),
    ("certificate_proof", "证书证明"),
    ("sign_poster_scene", "标牌海报场景"),
    ("handwritten_letter", "手写笔记信件"),
]

FORBIDDEN_CATEGORY_IDS = {
    "invoice_receipt",
    "schedule_timetable",
    "menu_price_list",
    "official_letter",
    "table_document",
}

FORBIDDEN_CATEGORY_CN = {
    "发票票据",
    "课表时刻表",
    "菜单价目表",
    "信函公文",
    "表格文档",
}

REQUIRED_TEMPLATE_FIELDS = [
    "template_id",
    "variant",
    "template_name_cn",
    "layout_family",
    "prompt",
    "layout_elements",
    "randomization_parameters",
    "qa_notes",
    "expected_manifest_layout_name",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_prompt_spec(data: dict[str, Any], manifest_category_plan: list[dict[str, Any]] | None = None) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []

    if data.get("schema_version") != "layout_prompts.v2":
        fail(errors, "schema_version must be layout_prompts.v2")

    categories = data.get("categories")
    if not isinstance(categories, list):
        fail(errors, "categories must be a list")
        categories = []

    expected_ids = [item[0] for item in EXPECTED_CATEGORIES]
    expected_cn = dict(EXPECTED_CATEGORIES)
    actual_ids = [cat.get("category_id") for cat in categories if isinstance(cat, dict)]

    if actual_ids != expected_ids:
        fail(errors, f"category order mismatch: expected {expected_ids}, got {actual_ids}")

    seen_template_ids: set[str] = set()
    seen_layout_names: set[str] = set()
    total_templates = 0

    for cat_index, cat in enumerate(categories, 1):
        if not isinstance(cat, dict):
            fail(errors, f"category #{cat_index} is not an object")
            continue

        category_id = cat.get("category_id")
        category_cn = cat.get("category_cn")
        if category_id in FORBIDDEN_CATEGORY_IDS or category_cn in FORBIDDEN_CATEGORY_CN:
            fail(errors, f"forbidden legacy category found: {category_id} / {category_cn}")

        if category_id not in expected_cn:
            fail(errors, f"unexpected category_id: {category_id}")
        elif category_cn != expected_cn[category_id]:
            fail(errors, f"category_cn mismatch for {category_id}: expected {expected_cn[category_id]}, got {category_cn}")

        if cat.get("expected_samples") != 6:
            fail(errors, f"{category_id}: expected_samples must be 6")

        templates = cat.get("templates")
        if not isinstance(templates, list):
            fail(errors, f"{category_id}: templates must be a list")
            continue
        if len(templates) != 6:
            fail(errors, f"{category_id}: must contain 6 templates, got {len(templates)}")

        variants = [tpl.get("variant") for tpl in templates if isinstance(tpl, dict)]
        if variants != [1, 2, 3, 4, 5, 6]:
            fail(errors, f"{category_id}: variant sequence must be [1,2,3,4,5,6], got {variants}")

        layout_families = set()
        for tpl in templates:
            total_templates += 1
            if not isinstance(tpl, dict):
                fail(errors, f"{category_id}: template item is not an object")
                continue
            variant = tpl.get("variant")
            for field in REQUIRED_TEMPLATE_FIELDS:
                if field not in tpl:
                    fail(errors, f"{category_id} v{variant}: missing field {field}")

            template_id = tpl.get("template_id")
            if not isinstance(template_id, str) or not template_id:
                fail(errors, f"{category_id} v{variant}: template_id must be non-empty string")
            elif template_id in seen_template_ids:
                fail(errors, f"duplicate template_id: {template_id}")
            else:
                seen_template_ids.add(template_id)

            expected_template_id = f"{category_id}_v{int(variant):02d}" if isinstance(variant, int) else None
            if expected_template_id and template_id != expected_template_id:
                warnings.append(f"{category_id} v{variant}: template_id differs from recommended {expected_template_id}")

            layout_family = tpl.get("layout_family")
            if isinstance(layout_family, str) and layout_family:
                layout_families.add(layout_family)

            layout_name = tpl.get("expected_manifest_layout_name")
            expected_layout_name = f"{category_id}_variant_{variant}"
            if layout_name != expected_layout_name:
                fail(errors, f"{category_id} v{variant}: expected_manifest_layout_name must be {expected_layout_name}")
            if isinstance(layout_name, str):
                if layout_name in seen_layout_names:
                    fail(errors, f"duplicate expected_manifest_layout_name: {layout_name}")
                seen_layout_names.add(layout_name)

            prompt = tpl.get("prompt")
            if not isinstance(prompt, str) or len(prompt.strip()) < 20:
                fail(errors, f"{category_id} v{variant}: prompt too short or empty")

            for field in ["layout_elements", "randomization_parameters", "qa_notes"]:
                value = tpl.get(field)
                if not isinstance(value, list) or not value:
                    fail(errors, f"{category_id} v{variant}: {field} must be a non-empty list")

        if len(layout_families) != 6:
            fail(errors, f"{category_id}: layout_family must contain 6 unique values, got {len(layout_families)}")

    if total_templates != 72:
        fail(errors, f"total templates must be 72, got {total_templates}")

    if manifest_category_plan is not None:
        manifest_pairs = [(item.get("category"), item.get("category_cn")) for item in manifest_category_plan]
        expected_pairs = EXPECTED_CATEGORIES
        if manifest_pairs != expected_pairs:
            fail(errors, f"manifest category plan mismatch: expected {expected_pairs}, got {manifest_pairs}")

    summary = {
        "categories": len(categories),
        "templates": total_templates,
        "warnings": warnings,
    }
    return errors, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt_json", type=Path)
    parser.add_argument("--category-plan", type=Path, default=None)
    args = parser.parse_args()

    data = load_json(args.prompt_json)
    category_plan = load_json(args.category_plan) if args.category_plan else None
    errors, summary = validate_prompt_spec(data, category_plan)

    if errors:
        print("FAILED layout prompt validation", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(json.dumps({"status": "ok", **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
