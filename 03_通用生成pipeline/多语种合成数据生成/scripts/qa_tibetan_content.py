#!/usr/bin/env python3
"""Content-level QA for Tibetan synthetic OCR labels and text pools."""

from __future__ import annotations

import argparse
import collections
import json
import re
import unicodedata
from pathlib import Path
from statistics import mean
from typing import Any


TIBETAN_RE = re.compile(r"[\u0f00-\u0fff]")
TIBETAN_BASE_RE = re.compile(r"[\u0f40-\u0f6c\u0f88-\u0f8c]")
TIBETAN_MARK_RE = re.compile(r"[\u0f71-\u0f84\u0f86-\u0f87\u0f90-\u0fbc]")
LATIN_RE = re.compile(r"[A-Za-z]")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
MONGOLIAN_RE = re.compile(r"[\u1800-\u18af]")
HANGUL_RE = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
PUA_RE = re.compile(r"[\ue000-\uf8ff]")
BOX_RE = re.compile(r"[\ufffd\u25a0\u25a1\u25af]")
TSHEG = "་"
SHADS = set("།༎༏༐༑༔")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ratio(count: int, text: str) -> float:
    return count / max(len(text), 1)


def text_from_record(row: dict[str, Any]) -> str:
    return str(row.get("text", row.get("block_content", "")) or "")


def split_tibetan_syllables(text: str) -> list[str]:
    parts = re.split(r"[\s་།༎༏༐༑༔,.;:!?，。；：！？()（）\[\]【】<>《》\"“”‘’/\\|\-]+", text)
    return [part for part in parts if part and TIBETAN_RE.search(part)]


def analyze_text(text: str) -> dict[str, Any]:
    text = str(text or "")
    syllables = split_tibetan_syllables(text)
    weird_syllables = []
    for syl in syllables:
        if syl.isdigit():
            continue
        has_base = bool(TIBETAN_BASE_RE.search(syl))
        has_mark = bool(TIBETAN_MARK_RE.search(syl))
        if len(syl) > 9 or (has_mark and not has_base):
            weird_syllables.append(syl)
    return {
        "length": len(text),
        "tibetan_chars": len(TIBETAN_RE.findall(text)),
        "tibetan_ratio": round(ratio(len(TIBETAN_RE.findall(text)), text), 4),
        "latin_chars": len(LATIN_RE.findall(text)),
        "cjk_chars": len(CJK_RE.findall(text)),
        "cyrillic_chars": len(CYRILLIC_RE.findall(text)),
        "arabic_chars": len(ARABIC_RE.findall(text)),
        "mongolian_chars": len(MONGOLIAN_RE.findall(text)),
        "hangul_chars": len(HANGUL_RE.findall(text)),
        "pua_chars": len(PUA_RE.findall(text)),
        "box_chars": len(BOX_RE.findall(text)),
        "tsheg_count": text.count(TSHEG),
        "shad_count": sum(text.count(ch) for ch in SHADS),
        "syllable_count": len(syllables),
        "avg_syllable_length": round(mean([len(s) for s in syllables]) if syllables else 0, 3),
        "max_syllable_length": max([len(s) for s in syllables], default=0),
        "weird_syllables": weird_syllables[:8],
    }


def issue_codes(text: str, stats: dict[str, Any], strict_labels: bool) -> list[str]:
    issues: list[str] = []
    if stats["pua_chars"]:
        issues.append("private_use_chars")
    if stats["box_chars"]:
        issues.append("box_or_replacement_chars")
    if stats["cjk_chars"]:
        issues.append("cjk_residue")
    if stats["cyrillic_chars"]:
        issues.append("cyrillic_residue")
    if stats["arabic_chars"]:
        issues.append("arabic_residue")
    if stats["mongolian_chars"]:
        issues.append("mongolian_residue")
    if stats["hangul_chars"]:
        issues.append("hangul_residue")
    if stats["latin_chars"] and (strict_labels or stats["tibetan_ratio"] < 0.55):
        issues.append("latin_residue")
    if stats["length"] >= 20 and stats["tibetan_chars"] > 0 and stats["tsheg_count"] == 0:
        issues.append("long_tibetan_without_tsheg")
    if stats["length"] >= 90 and stats["tibetan_chars"] > 0 and stats["shad_count"] == 0:
        issues.append("long_tibetan_without_shad")
    if stats["weird_syllables"]:
        issues.append("suspicious_syllables")
    return issues


def iter_label_blocks(dataset_dir: Path) -> list[dict[str, Any]]:
    label_paths = sorted(dataset_dir.glob("*/labels/*.json")) or sorted((dataset_dir / "labels").glob("*.json"))
    rows: list[dict[str, Any]] = []
    for path in label_paths:
        label = read_json(path)
        category = path.parts[-3] if path.parent.name == "labels" and len(path.parts) >= 3 else ""
        for block in label.get("blocks", []):
            text = block.get("block_content") or ""
            if not str(text).strip():
                continue
            rows.append(
                {
                    "source_type": "label",
                    "file": str(path.relative_to(dataset_dir)),
                    "category": category,
                    "block_label": block.get("block_label"),
                    "text": str(text),
                }
            )
    return rows


def iter_text_records(text_jsonl: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(text_jsonl.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        rows.append(
            {
                "source_type": "text_record",
                "file": f"{text_jsonl.name}:{line_no}",
                "category": "",
                "block_label": "",
                "title": str(row.get("title", "")),
                "text": text_from_record(row),
            }
        )
    return rows


def make_report(rows: list[dict[str, Any]], out_dir: Path, source_name: str, strict_labels: bool) -> dict[str, Any]:
    analyzed = []
    char_counter = collections.Counter()
    issue_counter = collections.Counter()
    issue_by_category = collections.Counter()
    issue_by_label = collections.Counter()
    for row in rows:
        text = row["text"]
        stats = analyze_text(text)
        issues = issue_codes(text, stats, strict_labels)
        char_counter.update(text)
        issue_counter.update(issues)
        if issues:
            issue_by_category[row.get("category") or row.get("source_type") or "unknown"] += 1
            issue_by_label[row.get("block_label") or row.get("source_type") or "unknown"] += 1
        analyzed.append({**row, **stats, "issues": issues})

    text_rows = [row for row in analyzed if row["length"] > 0]
    hard_issue_rows = [row for row in analyzed if row["issues"]]
    summary = {
        "source_name": source_name,
        "total_text_blocks": len(text_rows),
        "avg_tibetan_ratio": round(mean([row["tibetan_ratio"] for row in text_rows]) if text_rows else 0, 4),
        "total_tibetan_chars": sum(row["tibetan_chars"] for row in text_rows),
        "total_latin_chars": sum(row["latin_chars"] for row in text_rows),
        "total_cjk_chars": sum(row["cjk_chars"] for row in text_rows),
        "total_pua_chars": sum(row["pua_chars"] for row in text_rows),
        "total_box_chars": sum(row["box_chars"] for row in text_rows),
        "total_tsheg": sum(row["tsheg_count"] for row in text_rows),
        "total_shad": sum(row["shad_count"] for row in text_rows),
        "hard_issue_blocks": len(hard_issue_rows),
        "issue_counts": dict(issue_counter),
        "issue_by_category": dict(issue_by_category.most_common()),
        "issue_by_label": dict(issue_by_label.most_common()),
        "top_chars": [
            {"char": ch, "codepoint": f"U+{ord(ch):04X}", "count": count, "name": unicodedata.name(ch, "")}
            for ch, count in char_counter.most_common(60)
        ],
        "samples": [
            {
                "file": row["file"],
                "category": row.get("category"),
                "block_label": row.get("block_label"),
                "issues": row["issues"],
                "tibetan_ratio": row["tibetan_ratio"],
                "latin_chars": row["latin_chars"],
                "cjk_chars": row["cjk_chars"],
                "pua_chars": row["pua_chars"],
                "box_chars": row["box_chars"],
                "text": row["text"][:220],
            }
            for row in hard_issue_rows[:80]
        ],
    }
    write_json(out_dir / "tibetan_content_qa_summary.json", summary)

    issue_rows = "\n".join(f"| {k} | {v} |" for k, v in summary["issue_counts"].items())
    category_rows = "\n".join(f"| {k} | {v} |" for k, v in summary["issue_by_category"].items())
    sample_rows = "\n".join(
        f"| {sample['file']} | {sample.get('block_label') or ''} | {', '.join(sample['issues'])} | "
        f"{sample['tibetan_ratio']} | {sample['latin_chars']} | {sample['cjk_chars']} | {sample['box_chars']} | {sample['text'].replace('|', '/')} |"
        for sample in summary["samples"][:30]
    )
    md = f"""# Tibetan Content QA

- 来源：`{source_name}`
- 文本块数：{summary['total_text_blocks']}
- 平均藏文字符占比：{summary['avg_tibetan_ratio']}
- 藏文字符数：{summary['total_tibetan_chars']}
- Latin 字符数：{summary['total_latin_chars']}
- CJK 字符数：{summary['total_cjk_chars']}
- PUA 字符数：{summary['total_pua_chars']}
- 方框/替换字符数：{summary['total_box_chars']}
- 音节分隔符 `་` 数：{summary['total_tsheg']}
- 句读 `།/༎/...` 数：{summary['total_shad']}
- 有内容问题的文本块数：{summary['hard_issue_blocks']}

## 问题类型

| 问题 | 数量 |
|---|---:|
{issue_rows}

## 问题类别分布

| 类别/来源 | 问题块数 |
|---|---:|
{category_rows}

## 样本

| 文件 | 标签 | 问题 | 藏文占比 | Latin | CJK | 方框 | 文本片段 |
|---|---|---|---:|---:|---:|---:|---|
{sample_rows}

## 解释

这份报告只能做工程级文本规范检查，不能替代母语专家对语义、语序和用词自然度的最终判断。建议把 `latin_residue`、`cjk_residue`、`box_or_replacement_chars` 作为硬失败项；把 `long_tibetan_without_shad` 和 `suspicious_syllables` 作为人工抽检项。
"""
    (out_dir / "TIBETAN_CONTENT_QA_REPORT.md").write_text(md, encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir")
    parser.add_argument("--text-jsonl")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--strict-labels", action="store_true")
    args = parser.parse_args()

    if not args.dataset_dir and not args.text_jsonl:
        raise SystemExit("provide --dataset-dir or --text-jsonl")
    rows: list[dict[str, Any]] = []
    source_parts: list[str] = []
    if args.dataset_dir:
        dataset_dir = Path(args.dataset_dir)
        rows.extend(iter_label_blocks(dataset_dir))
        source_parts.append(str(dataset_dir))
    if args.text_jsonl:
        text_jsonl = Path(args.text_jsonl)
        rows.extend(iter_text_records(text_jsonl))
        source_parts.append(str(text_jsonl))
    summary = make_report(rows, Path(args.output_dir), " + ".join(source_parts), args.strict_labels)
    print(json.dumps({k: summary[k] for k in ["total_text_blocks", "avg_tibetan_ratio", "hard_issue_blocks", "issue_counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
