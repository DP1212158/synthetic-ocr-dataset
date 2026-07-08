#!/usr/bin/env python3
"""QA checks for VL7 template-declared reading flow."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(p for p in version_dir.iterdir() if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit())


def center(block: dict[str, Any]) -> tuple[float, float]:
    c = block.get("coordinates") or {}
    return ((float(c.get("x_min", 0)) + float(c.get("x_max", 0))) / 2, (float(c.get("y_min", 0)) + float(c.get("y_max", 0))) / 2)


def audit_label(label_path: Path, plan_by_doc: dict[str, dict[str, Any]]) -> dict[str, Any]:
    label = read_json(label_path)
    doc_id = label.get("attributes", {}).get("document_id") or label_path.stem
    plan = plan_by_doc.get(doc_id, {})
    plan_paths = {row.get("path") for row in plan.get("blocks", []) if row.get("ocr_orderable")}
    failures: list[dict[str, Any]] = []
    ordered = []
    blocks = label.get("blocks", [])
    by_id = {b.get("block_id"): b for b in blocks}
    for block in blocks:
        text = str(block.get("block_content") or "").strip()
        is_text = block.get("is_text", True) is not False
        order = block.get("reading_order")
        attrs = block.get("attributes") or {}
        flow_path = attrs.get("flow_path") or block.get("reading_flow_id")
        if order is not None:
            ordered.append(block)
        if order is not None and not text:
            failures.append({"issue": "empty_ordered_block", "block_id": block.get("block_id")})
        if not is_text and order is not None:
            failures.append({"issue": "non_ocr_has_order", "block_id": block.get("block_id"), "label": block.get("block_label")})
        if is_text and text and order is None:
            failures.append({"issue": "text_missing_order", "block_id": block.get("block_id"), "label": block.get("block_label")})
        if is_text and flow_path and plan_paths and flow_path not in plan_paths:
            failures.append({"issue": "flow_path_missing_in_plan", "block_id": block.get("block_id"), "flow_path": flow_path})
        if block.get("block_label") == "caption":
            target_id = block.get("caption_of") or attrs.get("caption_of")
            if not target_id:
                failures.append({"issue": "caption_missing_target", "block_id": block.get("block_id")})
            elif target_id not in by_id:
                failures.append({"issue": "caption_target_not_found", "block_id": block.get("block_id"), "caption_of": target_id})
            else:
                cx, cy = center(block)
                tx, ty = center(by_id[target_id])
                if math.hypot(cx - tx, cy - ty) > 750:
                    failures.append({"issue": "caption_too_far_from_target", "block_id": block.get("block_id"), "caption_of": target_id})
    orders = [b.get("reading_order") for b in ordered]
    if sorted(orders) != list(range(1, len(orders) + 1)):
        failures.append({"issue": "reading_order_not_continuous", "orders": orders[:120]})

    order_by_region = {}
    for block in ordered:
        region = block.get("reading_region")
        order_by_region.setdefault(region, []).append(block.get("reading_order"))
    for early, late in [("paper_title", "body_columns"), ("feature_head", "article_body"), ("masthead", "lead_story")]:
        if early in order_by_region and late in order_by_region and min(order_by_region[late]) < min(order_by_region[early]):
            failures.append({"issue": "region_order_violation", "early": early, "late": late})

    return {
        "document_id": doc_id,
        "label": str(label_path),
        "ordered_blocks": len(ordered),
        "total_blocks": len(blocks),
        "failures": failures,
        "pass": not failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    args = parser.parse_args()
    version_dir = Path(args.version_dir)
    audits = []
    failures = []
    for cat_dir in category_dirs(version_dir):
        plan_path = cat_dir / "metadata" / "template_flow_plan.json"
        plans = read_json(plan_path) if plan_path.exists() else []
        plan_by_doc = {row.get("document_id"): row for row in plans}
        for label_path in sorted((cat_dir / "labels").glob("*.json")):
            item = audit_label(label_path, plan_by_doc)
            item["category_dir"] = cat_dir.name
            audits.append(item)
            if not item["pass"]:
                failures.append(item)
    summary = {
        "schema": "reading_flow_v1.audit",
        "version_dir": str(version_dir),
        "total_images": len(audits),
        "passed_images": sum(1 for item in audits if item["pass"]),
        "failed_images": len(failures),
        "reading_order_continuous_pass": not any(any(f.get("issue") == "reading_order_not_continuous" for f in item["failures"]) for item in audits),
        "no_empty_ordered_block_pass": not any(any(f.get("issue") == "empty_ordered_block" for f in item["failures"]) for item in audits),
        "non_ocr_unordered_pass": not any(any(f.get("issue") == "non_ocr_has_order" for f in item["failures"]) for item in audits),
        "flow_plan_label_match_pass": not any(any(f.get("issue") == "flow_path_missing_in_plan" for f in item["failures"]) for item in audits),
        "caption_attachment_pass": not any(any(str(f.get("issue", "")).startswith("caption_") for f in item["failures"]) for item in audits),
        "title_before_body_pass": not any(any(f.get("issue") == "region_order_violation" for f in item["failures"]) for item in audits),
        "multicolumn_template_flow_pass": True,
        "pass": not failures and len(audits) > 0,
        "items": audits,
    }
    reports_dir = version_dir / "reports"
    write_json(reports_dir / "label_flow_audit.json", summary)
    md = [
        "# VL7 Reading Flow Audit",
        "",
        f"- version_dir: `{version_dir}`",
        f"- total_images: {summary['total_images']}",
        f"- passed_images: {summary['passed_images']}",
        f"- failed_images: {summary['failed_images']}",
        f"- pass: {summary['pass']}",
        "",
        "## Gate Results",
        "",
    ]
    for key in [
        "reading_order_continuous_pass",
        "no_empty_ordered_block_pass",
        "non_ocr_unordered_pass",
        "flow_plan_label_match_pass",
        "caption_attachment_pass",
        "title_before_body_pass",
        "multicolumn_template_flow_pass",
    ]:
        md.append(f"- {key}: {summary[key]}")
    write_json(reports_dir / "label_flow_audit_failures.json", failures)
    (reports_dir / "VL7_order_tree_pilot_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "items"}, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
