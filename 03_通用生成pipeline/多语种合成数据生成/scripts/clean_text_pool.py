#!/usr/bin/env python3
"""Create a cleaned JSONL text pool from an existing records.jsonl file."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from statistics import mean
from typing import Any

from synthetic_text_utils import cleanse_text, load_language_profile, text_quality


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--min-text-length", type=int, default=40)
    args = parser.parse_args()

    in_path = Path(args.input_jsonl)
    out_path = Path(args.output_jsonl)
    profile = load_language_profile(Path(args.language_profile))
    script_re = re.compile(str(profile["script_regex"]))
    min_script_ratio = float(profile.get("min_script_ratio", 0.35))

    kept: list[dict[str, Any]] = []
    skipped = 0
    changed = 0
    for line_no, line in enumerate(in_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        raw_title = str(row.get("title", ""))
        raw_text = str(row.get("text", row.get("block_content", "")))
        title = cleanse_text(raw_title)
        text = cleanse_text(raw_text)
        if title != raw_title or text != raw_text:
            changed += 1
        if len(text) < args.min_text_length:
            skipped += 1
            continue
        q = text_quality(text, script_re)
        if q["script_ratio"] < min_script_ratio:
            skipped += 1
            continue
        out = dict(row)
        out["title"] = title
        out["text"] = text
        out["source_record_id"] = str(row.get("record_id", row.get("source_record_id", line_no)))
        out["cleaned_from"] = str(in_path)
        out["cleanup_profile"] = profile.get("cleanup_profile")
        out["script_ratio_after_cleaning"] = round(q["script_ratio"], 4)
        out["digit_ratio_after_cleaning"] = round(q["digit_ratio"], 4)
        kept.append(out)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "input_jsonl": str(in_path),
        "output_jsonl": str(out_path),
        "language_code": profile.get("language_code"),
        "language_name": profile.get("language_name"),
        "input_records": sum(1 for line in in_path.read_text(encoding="utf-8").splitlines() if line.strip()),
        "kept_records": len(kept),
        "skipped_records": skipped,
        "changed_records": changed,
        "avg_text_length": round(mean([len(row["text"]) for row in kept]) if kept else 0, 2),
        "avg_script_ratio": round(mean([row["script_ratio_after_cleaning"] for row in kept]) if kept else 0, 4),
    }
    write_json(out_path.parent / "clean_text_pool_summary.json", summary)
    report = f"""# Clean Text Pool Report

- 输入：`{in_path}`
- 输出：`{out_path}`
- 语言：{summary['language_name']} / `{summary['language_code']}`
- 输入记录数：{summary['input_records']}
- 保留记录数：{summary['kept_records']}
- 跳过记录数：{summary['skipped_records']}
- 清洗发生变化的记录数：{summary['changed_records']}
- 清洗后平均长度：{summary['avg_text_length']}
- 清洗后平均目标文字占比：{summary['avg_script_ratio']}
"""
    (out_path.parent / "CLEAN_TEXT_POOL_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if kept else 1


if __name__ == "__main__":
    raise SystemExit(main())
