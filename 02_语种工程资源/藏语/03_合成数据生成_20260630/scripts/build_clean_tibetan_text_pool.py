#!/usr/bin/env python3
"""Build a cleaned Tibetan JSONL text pool from existing Wikipedia records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from tibetan_text_utils import (
    BOX_RE,
    CJK_RE,
    CYRILLIC_RE,
    LATIN_RE,
    PUA_RE,
    TIBETAN_RE,
    has_foreign_residue,
    normalize_tibetan_text,
    split_sentences,
    text_quality,
)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        row["_input_path"] = str(path)
        row["_input_line"] = line_no
        rows.append(row)
    return rows


def make_record(row: dict[str, Any], text: str, title: str, idx: int, split_index: int | None = None) -> dict[str, Any]:
    return {
        "record_id": f"clean_bo_{idx:05d}" if split_index is None else f"clean_bo_{idx:05d}_s{split_index:02d}",
        "language_code": "bo",
        "language_name": "藏语",
        "script_note": "藏文清洗文本池，保留 tsheg 与标准 shad",
        "source": row.get("source", "bo_wikipedia_cleaned"),
        "source_record_id": row.get("record_id", row.get("source_record_id", "")),
        "source_url": row.get("url", ""),
        "title": title,
        "text": text,
        "cleaned_from": row.get("_input_path", ""),
        "input_line": row.get("_input_line", ""),
        "license_note": row.get("license_note", "Wikipedia text is generally available under CC BY-SA; retain source attribution."),
        "tibetan_ratio": round(len(TIBETAN_RE.findall(text)) / max(len(text), 1), 4),
        "chars": len(text),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--min-record-length", type=int, default=40)
    parser.add_argument("--target-records", type=int, default=40)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for raw_path in args.input_jsonl:
        rows.extend(read_jsonl(Path(raw_path)))

    kept: list[dict[str, Any]] = []
    split_records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    changed = 0
    residue_counts = {"latin": 0, "cjk": 0, "cyrillic": 0, "pua": 0, "box": 0}
    for idx, row in enumerate(rows, 1):
        raw_title = str(row.get("title", ""))
        raw_text = str(row.get("text", row.get("block_content", "")))
        title = normalize_tibetan_text(raw_title)
        text = normalize_tibetan_text(raw_text)
        if raw_title != title or raw_text != text:
            changed += 1
        residue_counts["latin"] += len(LATIN_RE.findall(raw_text))
        residue_counts["cjk"] += len(CJK_RE.findall(raw_text))
        residue_counts["cyrillic"] += len(CYRILLIC_RE.findall(raw_text))
        residue_counts["pua"] += len(PUA_RE.findall(raw_text))
        residue_counts["box"] += len(BOX_RE.findall(raw_text))
        q = text_quality(text)
        reason = ""
        if len(text) < args.min_record_length:
            reason = "too_short"
        elif q["script_ratio"] < 0.95:
            reason = "low_tibetan_ratio"
        elif has_foreign_residue(text):
            reason = "foreign_residue_after_cleaning"
        elif q["shad_count"] == 0 and len(text) >= 90:
            reason = "long_text_without_shad"
        if reason:
            rejected.append(
                {
                    "reason": reason,
                    "source_record_id": row.get("record_id"),
                    "title_before": raw_title[:100],
                    "text_before": raw_text[:180],
                    "text_after": text[:180],
                    "tibetan_ratio_after": round(q["script_ratio"], 4),
                }
            )
            continue
        kept.append(make_record(row, text, title, idx))
        for sent_idx, sent in enumerate(split_sentences(text), 1):
            if len(sent) >= 45 and not has_foreign_residue(sent):
                split_records.append(make_record(row, sent, title, idx, sent_idx))

    final_records = kept[:]
    if len(final_records) < args.target_records:
        seen = {rec["text"] for rec in final_records}
        for rec in split_records:
            if rec["text"] in seen:
                continue
            final_records.append(rec)
            seen.add(rec["text"])
            if len(final_records) >= args.target_records:
                break

    records_path = output_dir / "records.jsonl"
    with records_path.open("w", encoding="utf-8") as f:
        for rec in final_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    ratios = [rec["tibetan_ratio"] for rec in final_records]
    lengths = [rec["chars"] for rec in final_records]
    summary = {
        "input_jsonl": args.input_jsonl,
        "output_records": str(records_path),
        "input_records": len(rows),
        "kept_original_records": len(kept),
        "sentence_records_available": len(split_records),
        "final_records": len(final_records),
        "changed_records": changed,
        "avg_length": round(mean(lengths) if lengths else 0, 2),
        "avg_tibetan_ratio": round(mean(ratios) if ratios else 0, 4),
        "latin_residue_after": sum(len(LATIN_RE.findall(rec["text"])) for rec in final_records),
        "cjk_residue_after": sum(len(CJK_RE.findall(rec["text"])) for rec in final_records),
        "pua_chars_after": sum(len(PUA_RE.findall(rec["text"])) for rec in final_records),
        "box_chars_after": sum(len(BOX_RE.findall(rec["text"])) for rec in final_records),
        "raw_residue_counts": residue_counts,
        "rejected_count": len(rejected),
        "rejected_samples": rejected[:40],
    }
    write_json(output_dir / "cleaned_text_pool_summary.json", summary)
    report = f"""# Cleaned Tibetan Text Pool Report

- 输入记录数：{summary['input_records']}
- 原段落保留数：{summary['kept_original_records']}
- 可用句子级记录数：{summary['sentence_records_available']}
- 最终记录数：{summary['final_records']}
- 清洗发生变化记录数：{summary['changed_records']}
- 平均长度：{summary['avg_length']}
- 平均藏文字符占比：{summary['avg_tibetan_ratio']}
- 清洗后 Latin 残留：{summary['latin_residue_after']}
- 清洗后 CJK 残留：{summary['cjk_residue_after']}
- 清洗后 PUA 残留：{summary['pua_chars_after']}
- 清洗后方框/替换字符：{summary['box_chars_after']}

## 规则说明

- 保留藏文音节分隔符 `་`。
- 保留标准句读 `།/༎`。
- 移除装饰性藏文符号、外文括注、HTML、URL、PUA、方框/替换字符以及 Latin/CJK/西里尔/阿拉伯/蒙古文/韩文残留。
- 当原始段落数量不足时，使用句子级切分补足文本池，但不混入其他来源。

## 异常样本

异常样本详情见 `cleaned_text_pool_summary.json` 的 `rejected_samples`。
"""
    (output_dir / "TEXT_QA_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if len(final_records) >= args.target_records else 1


if __name__ == "__main__":
    raise SystemExit(main())
