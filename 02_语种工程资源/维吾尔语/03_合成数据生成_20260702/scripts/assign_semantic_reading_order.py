#!/usr/bin/env python3
"""Assign VL3 semantic reading order to rendered labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


HEADER_LABELS = {"document_title", "document_subtitle", "metadata"}
FOOTER_LABELS = {"footer", "page_number"}
IMAGE_LABELS = {"image", "photo", "figure", "photo_lead", "image_figure"}
TABLE_LABELS = {"table_header", "table_cell_text", "table_cell_number"}
FORM_LABELS = {"field_label", "field_value", "option", "answer_area"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def center(block: dict[str, Any]) -> tuple[float, float]:
    c = block.get("coordinates") or {}
    return ((float(c.get("x_min", 0)) + float(c.get("x_max", 0))) / 2, (float(c.get("y_min", 0)) + float(c.get("y_max", 0))) / 2)


def group_for(label: str, y: float, page_h: float, is_text: bool) -> str:
    if not is_text:
        return "image" if label in IMAGE_LABELS else "non_text"
    if label in HEADER_LABELS and y < page_h * 0.24:
        return "header"
    if label in FOOTER_LABELS or y > page_h * 0.91:
        return "footer"
    if label in TABLE_LABELS:
        return "table"
    if label in FORM_LABELS:
        return "form"
    return "body"


def role_for(label: str, is_text: bool) -> str:
    if not is_text:
        return "image" if label in IMAGE_LABELS else "non_text"
    return {
        "document_title": "title",
        "document_subtitle": "subtitle",
        "section_title": "section_title",
        "paragraph": "paragraph",
        "quote": "quote",
        "caption": "caption",
        "field_label": "field_label",
        "field_value": "field_value",
        "answer_area": "answer_area",
        "option": "option",
        "question": "question",
        "question_text": "question",
        "table_header": "table_header",
        "table_cell_text": "table_cell",
        "metadata": "metadata",
        "note": "note",
        "list_item": "list_item",
        "footer": "footer",
        "page_number": "page_number",
    }.get(label, label or "text")


def policy_for(profile: dict[str, Any]) -> str:
    writing_mode = str(profile.get("css_writing_mode", "horizontal-tb")).lower()
    direction = str(profile.get("css_direction", "ltr")).lower()
    cleanup = str(profile.get("cleanup_profile", "")).lower()
    if writing_mode.startswith("vertical") or cleanup == "traditional_mongolian":
        return "semantic_vertical_lr_columns"
    if direction == "rtl":
        return "semantic_rtl_regions_columns"
    return "semantic_ltr_regions_columns"


def infer_column(cx: float, page_w: float, policy: str) -> int:
    if page_w <= 0:
        return 0
    if policy == "semantic_vertical_lr_columns":
        return int(cx / page_w * 8)
    raw = int(cx / page_w * 6)
    if policy == "semantic_rtl_regions_columns":
        return 5 - raw
    return raw


def flow_rank(group: str) -> int:
    return {
        "header": 0,
        "body": 1,
        "table": 2,
        "form": 2,
        "image": 3,
        "footer": 4,
        "non_text": 5,
    }.get(group, 5)


def assign_label(label: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    attrs = label.setdefault("attributes", {})
    diagnostics = attrs.get("diagnostics", {})
    crop = diagnostics.get("crop", {})
    page_w = float(crop.get("width") or diagnostics.get("page_width") or 1)
    page_h = float(crop.get("height") or diagnostics.get("page_height") or 1)
    policy = policy_for(profile)
    decorated = []
    for idx, block in enumerate(label.get("blocks", [])):
        label_name = block.get("block_label") or ""
        cx, cy = center(block)
        is_text = block.get("is_text", True) is not False
        group = group_for(label_name, cy, page_h, is_text)
        role = role_for(label_name, is_text)
        block_attrs = block.setdefault("attributes", {})
        dom_index = int(block_attrs.get("dom_index") or block.get("order") or idx)
        column = block_attrs.get("column_index")
        try:
            column_index = int(column) if column is not None else infer_column(cx, page_w, policy)
        except ValueError:
            column_index = infer_column(cx, page_w, policy)
        region = str(block_attrs.get("reading_region") or group)
        flow_id = str(block_attrs.get("reading_flow_id") or region)
        flow_value = block_attrs.get("reading_flow_rank")
        try:
            semantic_rank = int(flow_value) if flow_value is not None else flow_rank(group)
        except ValueError:
            semantic_rank = flow_rank(group)
        if policy == "semantic_vertical_lr_columns":
            sort_key = (semantic_rank, column_index, cy, cx, dom_index)
        else:
            sort_key = (semantic_rank, column_index, cy, cx, dom_index)
        decorated.append((sort_key, block, group, role, flow_id, semantic_rank, region, column_index))
    decorated.sort(key=lambda item: item[0])
    for order, item in enumerate(decorated, 1):
        _, block, group, role, flow_id, semantic_rank, region, column_index = item
        block["reading_order"] = order
        block["reading_group"] = group
        block["reading_role"] = role
        block["reading_order_confidence"] = "high" if group in {"header", "footer", "table", "form"} else "medium"
        block["reading_flow_id"] = flow_id
        block["reading_flow_rank"] = semantic_rank
        block["reading_region"] = region
        block["column_index"] = column_index
    attrs["reading_order_policy"] = f"{policy}_v1"
    return label


def labels(version_dir: Path) -> list[Path]:
    return sorted(version_dir.glob("*/labels/*.json"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    parser.add_argument("--language-profile", required=True)
    args = parser.parse_args()
    version_dir = Path(args.version_dir)
    profile = read_json(Path(args.language_profile))
    docs = 0
    blocks = 0
    failures = []
    for label_path in labels(version_dir):
        label = assign_label(read_json(label_path), profile)
        orders = [b.get("reading_order") for b in label.get("blocks", [])]
        expected = list(range(1, len(orders) + 1))
        if sorted(orders) != expected:
            failures.append(str(label_path))
        write_json(label_path, label)
        docs += 1
        blocks += len(orders)
    summary = {
        "documents": docs,
        "blocks": blocks,
        "policy": policy_for(profile),
        "failed_documents": failures,
        "semantic_reading_order_pass": not failures and docs > 0,
        "pass": not failures and docs > 0,
    }
    write_json(version_dir / "reports" / "semantic_reading_order_summary.json", summary)
    (version_dir / "reports" / "QA_SEMANTIC_READING_ORDER_REPORT.md").write_text(
        f"""# Semantic Reading Order QA

- 文档数：{docs}
- 标签块数：{blocks}
- 策略：{summary['policy']}
- 失败文档数：{len(failures)}
- 结论：{'通过' if summary['pass'] else '需处理'}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
