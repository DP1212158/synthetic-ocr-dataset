#!/usr/bin/env python3
"""Acceptance QA for a classified synthetic-data version."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_CATEGORIES = [
    "newspaper_page",
    "certificate_proof",
    "exam_paper",
    "sign_poster_scene",
    "book_page",
    "textbook_page",
    "magazine_journal",
    "academic_paper",
    "historical_classic",
    "notice_announcement",
    "complex_form",
    "handwritten_letter",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profile(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    return read_json(path)


def allow_tibetan_small_marks(profile: dict[str, Any]) -> bool:
    return str(profile.get("cleanup_profile", "")).lower().startswith("tibetan")


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in version_dir.iterdir()
        if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit()
    )


def missing_subdirs(cat_dir: Path) -> list[str]:
    return [name for name in ["html", "images", "labels", "metadata", "reports"] if not (cat_dir / name).is_dir()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    parser.add_argument("--expected-categories", nargs="*", default=EXPECTED_CATEGORIES)
    parser.add_argument("--samples-per-category", type=int, default=6)
    parser.add_argument("--max-density-warnings", type=int, default=0)
    parser.add_argument("--fail-on-warning", action="store_true")
    parser.add_argument("--language-profile")
    args = parser.parse_args()

    version_dir = Path(args.version_dir)
    profile = load_profile(Path(args.language_profile) if args.language_profile else None)
    reports_dir = version_dir / "reports"
    qa_path = reports_dir / "qa_summary.json"
    density_path = reports_dir / "qa_density_summary.json"
    if not qa_path.exists():
        raise FileNotFoundError(f"missing {qa_path}")
    if not density_path.exists():
        raise FileNotFoundError(f"missing {density_path}")

    qa = read_json(qa_path)
    density = read_json(density_path)
    category_plan = read_json(version_dir / "metadata" / "category_plan.json") if (version_dir / "metadata" / "category_plan.json").exists() else []
    present_categories = {row["category"] for row in category_plan}
    expected_categories = set(args.expected_categories)

    issues: list[dict[str, Any]] = []
    if qa.get("failed_basic"):
        issues.append({"level": "error", "code": "basic_qa_failed", "detail": qa["failed_basic"]})
    qa_error_keys = [
        "total_overflow_blocks",
        "total_out_of_bounds_blocks",
        "total_cyrillic_blocks",
        "total_pua_blocks",
        "total_unsupported_char_blocks",
    ]
    if not allow_tibetan_small_marks(profile):
        qa_error_keys.append("total_tibetan_small_mark_blocks")
    for key in qa_error_keys:
        if int(qa.get(key, 0)) != 0:
            issues.append({"level": "error", "code": key, "detail": qa.get(key)})
    for name, count in (qa.get("total_script_residue_blocks") or {}).items():
        if int(count) != 0:
            issues.append({"level": "error", "code": f"{name}_residue_blocks", "detail": count})
    missing_categories = sorted(expected_categories - present_categories)
    extra_categories = sorted(present_categories - expected_categories)
    if missing_categories:
        issues.append({"level": "error", "code": "missing_categories", "detail": missing_categories})
    if extra_categories:
        issues.append({"level": "warning", "code": "extra_categories", "detail": extra_categories})
    for row in category_plan:
        if int(row.get("samples", 0)) != args.samples_per_category:
            issues.append({"level": "error", "code": "wrong_sample_count", "category": row.get("category"), "detail": row.get("samples")})
    for cat_dir in category_dirs(version_dir):
        missing = missing_subdirs(cat_dir)
        if missing:
            issues.append({"level": "error", "code": "missing_category_subdirs", "folder": cat_dir.name, "detail": missing})
    warning_images = int(density.get("warning_images", 0))
    if warning_images > args.max_density_warnings:
        issues.append({"level": "warning", "code": "density_warnings", "detail": warning_images})

    errors = [issue for issue in issues if issue["level"] == "error"]
    warnings = [issue for issue in issues if issue["level"] == "warning"]
    summary = {
        "version_dir": str(version_dir),
        "total_images": qa.get("total_images"),
        "passed_basic": qa.get("passed_basic"),
        "expected_categories": sorted(expected_categories),
        "present_categories": sorted(present_categories),
        "density_warning_images": warning_images,
        "errors": errors,
        "warnings": warnings,
        "pass": not errors and warning_images <= args.max_density_warnings,
    }
    write_json(reports_dir / "acceptance_summary.json", summary)

    issue_rows = "\n".join(
        f"| {issue['level']} | {issue['code']} | {json.dumps(issue.get('detail', ''), ensure_ascii=False)} |"
        for issue in issues
    )
    md = f"""# Version Acceptance QA

- 版本目录：`{version_dir}`
- 图片数：{summary['total_images']}
- 基础 QA：{summary['passed_basic']} / {summary['total_images']}
- 密度风险图：{summary['density_warning_images']}
- 结论：{'通过' if summary['pass'] else '需处理'}

## 问题

| 级别 | 代码 | 详情 |
|---|---|---|
{issue_rows}
"""
    (reports_dir / "ACCEPTANCE_REPORT.md").write_text(md, encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["total_images", "passed_basic", "density_warning_images", "pass"]}, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
