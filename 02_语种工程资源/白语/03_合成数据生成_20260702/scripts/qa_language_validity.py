#!/usr/bin/env python3
"""Profile-driven final label language validity QA.

This checks the text written into final labels, not the source records only.
It is intentionally conservative: it catches script contamination, tofu-risk
characters, private-use characters, and pure/mixed Chinese policy violations.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from statistics import mean
from typing import Any


SCRIPT_PATTERNS = {
    "latin": re.compile(r"[A-Za-z]"),
    "cjk": re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]"),
    "cyrillic": re.compile(r"[\u0400-\u04ff]"),
    "tibetan": re.compile(r"[\u0f00-\u0fff]"),
    "arabic": re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]"),
    "mongolian": re.compile(r"[\u1800-\u18af]"),
    "hangul": re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]"),
}
PRIVATE_USE_RE = re.compile(r"[\ue000-\uf8ff]")
REPLACEMENT_OR_BOX_RE = re.compile(r"[\ufffd\u25a0\u25a1\u25af\u25a3\u25a4\u25a5\u25a6\u25a7\u25a8\u25a9]")
ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]")
CONTROL_RE = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]")
MONGOLIAN_PRESENTATION_PUNCT_RE = re.compile(r"[︽︾︕︖︵︶︔﹇﹈]")
MONGOLIAN_UNSAFE_SYMBOL_RE = re.compile(r"[\u200d=+~※%!—–]")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profile(path: Path) -> dict[str, Any]:
    profile = read_json(path)
    profile.setdefault("language_code", "unknown")
    profile.setdefault("language_name", "unknown")
    profile.setdefault("script_regex", r".")
    profile.setdefault("min_script_ratio", 0.35)
    profile.setdefault("cleanup_profile", "")
    profile.setdefault("max_digit_ratio", 0.25)
    return profile


def infer_target_script(profile: dict[str, Any]) -> str:
    cleanup = str(profile.get("cleanup_profile", "")).lower()
    code = str(profile.get("language_code", "")).lower()
    regex = str(profile.get("script_regex", "")).lower()
    if "hangul" in cleanup or code.startswith("ko") or "ac00" in regex:
        return "hangul"
    if "arabic" in cleanup or "uyghur" in cleanup or "kazakh" in cleanup or "0600" in regex or code in {"ug", "kk-arab"}:
        return "arabic"
    if "mongolian" in cleanup or "1800" in regex or "mong" in code:
        return "mongolian"
    if "tibetan" in cleanup or "0f00" in regex or code.startswith("bo"):
        return "tibetan"
    return "latin"


def ratio(count: int, text: str) -> float:
    return count / max(len(text), 1)


def script_counts(text: str) -> dict[str, int]:
    return {name: len(pattern.findall(text or "")) for name, pattern in SCRIPT_PATTERNS.items()}


def bad_chars(text: str, profile: dict[str, Any]) -> list[str]:
    cleanup = str(profile.get("cleanup_profile", "")).lower()
    chars: list[str] = []
    for pattern in [PRIVATE_USE_RE, REPLACEMENT_OR_BOX_RE, CONTROL_RE]:
        chars.extend(pattern.findall(text or ""))
    if cleanup not in {"arabic", "uyghur", "kazakh_arabic"}:
        chars.extend(ZERO_WIDTH_RE.findall(text or ""))
    if cleanup in {"mongolian", "traditional_mongolian"}:
        chars.extend(MONGOLIAN_PRESENTATION_PUNCT_RE.findall(text or ""))
        chars.extend(MONGOLIAN_UNSAFE_SYMBOL_RE.findall(text or ""))
    return chars


def label_paths(version_dir: Path) -> list[Path]:
    direct = sorted(version_dir.glob("labels/*.json"))
    nested = sorted(version_dir.glob("*/labels/*.json"))
    return direct or nested


def infer_mode(label: dict[str, Any], label_path: Path) -> str:
    attrs = label.get("attributes") or {}
    mode = attrs.get("language_mix_mode")
    if mode in {"pure", "mixed"}:
        return mode
    variant = attrs.get("variant")
    try:
        variant_num = int(variant)
        return "mixed" if variant_num % 2 == 0 else "pure"
    except Exception:
        pass
    stem = label_path.stem
    m = re.search(r"_(\d{2})$", stem)
    if m:
        return "mixed" if int(m.group(1)) % 2 == 0 else "pure"
    return "pure"


def block_role(block: dict[str, Any]) -> str:
    return str(block.get("reading_role") or block.get("block_label") or "")


def is_textual_block(block: dict[str, Any]) -> bool:
    if block.get("is_text", True) is False:
        return False
    role = block_role(block)
    if role in {"metadata", "page_number", "answer_area", "image"}:
        return False
    text = str(block.get("block_content") or "").strip()
    if not text:
        return False
    if re.fullmatch(r"[_\\/\-–—:：|·•\s\d.,，。；;()（）\[\]【】]+", text):
        return False
    return True


def analyze_label(label_path: Path, profile: dict[str, Any], target_script: str, allow_mixed_cjk: bool) -> dict[str, Any]:
    label = read_json(label_path)
    attrs = label.get("attributes") or {}
    doc_id = attrs.get("document_id") or label_path.stem
    category = attrs.get("category") or label_path.parent.parent.name
    mode = infer_mode(label, label_path)
    allowed = {target_script}
    if allow_mixed_cjk and mode == "mixed":
        allowed.add("cjk")

    failures = []
    warnings = []
    text_chars = 0
    target_chars = 0
    cjk_chars = 0
    digit_chars = 0
    block_count = 0
    bad_char_blocks = 0
    other_script_blocks = 0
    script_block_counter = collections.Counter()

    for block in label.get("blocks", []):
        if not is_textual_block(block):
            continue
        block_count += 1
        text = str(block.get("block_content") or "")
        text_chars += len(text)
        digit_chars += sum(ch.isdigit() for ch in text)
        counts = script_counts(text)
        target_chars += counts[target_script]
        cjk_chars += counts["cjk"]
        bad = bad_chars(text, profile)
        if bad:
            bad_char_blocks += 1
            failures.append(
                {
                    "document_id": doc_id,
                    "block_id": block.get("block_id"),
                    "issue": "unsupported_or_tofu_risk_chars",
                    "role": block_role(block),
                    "chars": sorted(set(bad)),
                    "text_sample": text[:80],
                }
            )
        disallowed = {name: count for name, count in counts.items() if count and name not in allowed}
        if disallowed:
            other_script_blocks += 1
            script_block_counter.update(disallowed.keys())
            failures.append(
                {
                    "document_id": doc_id,
                    "block_id": block.get("block_id"),
                    "issue": "disallowed_script_residue",
                    "mode": mode,
                    "allowed": sorted(allowed),
                    "scripts": disallowed,
                    "text_sample": text[:80],
                }
            )

    target_ratio = ratio(target_chars, "x" * text_chars)
    cjk_ratio = ratio(cjk_chars, "x" * text_chars)
    digit_ratio = ratio(digit_chars, "x" * text_chars)
    min_target_ratio = float(profile.get("min_script_ratio", 0.35))
    hard_floor = float(profile.get("min_script_ratio_hard_floor", min(0.20, min_target_ratio)))
    if text_chars and target_ratio < min_target_ratio:
        payload = {
            "document_id": doc_id,
            "issue": "low_target_script_ratio",
            "target_script": target_script,
            "target_ratio": round(target_ratio, 4),
            "min_script_ratio": min_target_ratio,
            "hard_floor": hard_floor,
        }
        if target_ratio < hard_floor:
            failures.append(payload)
        else:
            warnings.append(payload)
    if mode == "pure" and cjk_chars:
        failures.append({"document_id": doc_id, "issue": "pure_sample_has_cjk", "cjk_ratio": round(cjk_ratio, 4)})
    if mode == "mixed" and allow_mixed_cjk and not (0.10 <= cjk_ratio <= 0.30):
        payload = {"document_id": doc_id, "issue": "mixed_cjk_ratio_out_of_range", "cjk_ratio": round(cjk_ratio, 4)}
        if block_count <= 12 and text_chars <= 260:
            warnings.append(payload | {"note": "short_mixed_layout"})
        else:
            failures.append(payload)
    if digit_ratio > float(profile.get("max_digit_ratio", 0.25)):
        warnings.append({"document_id": doc_id, "issue": "high_digit_ratio", "digit_ratio": round(digit_ratio, 4)})

    return {
        "document_id": doc_id,
        "category": category,
        "mode": mode,
        "blocks": block_count,
        "text_chars": text_chars,
        "target_script": target_script,
        "target_ratio": round(target_ratio, 4),
        "cjk_ratio": round(cjk_ratio, 4),
        "digit_ratio": round(digit_ratio, 4),
        "bad_char_blocks": bad_char_blocks,
        "other_script_blocks": other_script_blocks,
        "other_script_types": dict(script_block_counter),
        "failures": failures,
        "warnings": warnings,
        "pass": not failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--allow-mixed-cjk", action="store_true")
    parser.add_argument("--fail-on-warning", action="store_true")
    parser.add_argument("--sample-size", type=int, default=30)
    args = parser.parse_args()

    version_dir = Path(args.version_dir)
    profile = load_profile(Path(args.language_profile))
    target_script = infer_target_script(profile)
    docs = [
        analyze_label(path, profile, target_script, args.allow_mixed_cjk)
        for path in label_paths(version_dir)
    ]
    failures = [failure for doc in docs for failure in doc["failures"]]
    warnings = [warning for doc in docs for warning in doc["warnings"]]
    by_category: dict[str, dict[str, Any]] = {}
    for category in sorted({doc["category"] for doc in docs}):
        items = [doc for doc in docs if doc["category"] == category]
        by_category[category] = {
            "documents": len(items),
            "passed": sum(1 for item in items if item["pass"]),
            "pure": sum(1 for item in items if item["mode"] == "pure"),
            "mixed": sum(1 for item in items if item["mode"] == "mixed"),
            "avg_target_ratio": round(mean([item["target_ratio"] for item in items]) if items else 0, 4),
            "avg_cjk_ratio": round(mean([item["cjk_ratio"] for item in items]) if items else 0, 4),
        }
    summary = {
        "version_dir": str(version_dir),
        "language_code": profile.get("language_code"),
        "language_name": profile.get("language_name"),
        "target_script": target_script,
        "allow_mixed_cjk": args.allow_mixed_cjk,
        "documents": len(docs),
        "passed_documents": sum(1 for doc in docs if doc["pass"]),
        "failed_documents": [doc["document_id"] for doc in docs if not doc["pass"]],
        "text_blocks": sum(doc["blocks"] for doc in docs),
        "bad_char_blocks": sum(doc["bad_char_blocks"] for doc in docs),
        "other_script_blocks": sum(doc["other_script_blocks"] for doc in docs),
        "avg_target_ratio": round(mean([doc["target_ratio"] for doc in docs]) if docs else 0, 4),
        "avg_cjk_ratio": round(mean([doc["cjk_ratio"] for doc in docs]) if docs else 0, 4),
        "by_category": by_category,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failure_samples": failures[: args.sample_size],
        "warning_samples": warnings[: args.sample_size],
        "pass": not failures and bool(docs),
        "limitations": [
            "Regex QA can detect wrong script contamination and bad characters, but cannot prove grammar quality.",
            "Latin-script languages such as Zhuang and Bai require trusted source text to distinguish language from generic Latin text.",
        ],
    }
    out_dir = Path(args.output_dir) if args.output_dir else version_dir / "reports"
    write_json(out_dir / "language_validity_summary.json", summary)
    write_json(version_dir / "metadata" / "language_validity_summary.json", summary)
    rows = "\n".join(
        f"| {cat} | {stat['documents']} | {stat['passed']} | {stat['pure']} | {stat['mixed']} | {stat['avg_target_ratio']} | {stat['avg_cjk_ratio']} |"
        for cat, stat in by_category.items()
    )
    failure_rows = "\n".join(
        f"| {f.get('document_id')} | {f.get('block_id', '')} | {f.get('issue')} | {f.get('text_sample', '')[:60]} |"
        for f in failures[: args.sample_size]
    )
    warning_rows = "\n".join(
        f"| {f.get('document_id')} | {f.get('issue')} | {f.get('digit_ratio', '')} |"
        for f in warnings[: args.sample_size]
    )
    md = f"""# Language Validity QA

- 版本目录：`{version_dir}`
- 语言：{profile.get('language_name')} / `{profile.get('language_code')}`
- 目标文字体系：`{target_script}`
- 允许 mixed 样本中文：{args.allow_mixed_cjk}
- 文档数：{summary['documents']}
- 通过文档数：{summary['passed_documents']}
- 文本块数：{summary['text_blocks']}
- 异常/方框风险字符块：{summary['bad_char_blocks']}
- 其他文字体系残留块：{summary['other_script_blocks']}
- 失败项：{summary['failure_count']}
- 风险警告：{summary['warning_count']}
- 结论：{'通过' if summary['pass'] else '需处理'}

## 类别汇总

| 类别 | 文档 | 通过 | pure | mixed | 平均目标文字占比 | 平均中文占比 |
|---|---:|---:|---:|---:|---:|---:|
{rows}

## 失败样本

| document_id | block_id | issue | text_sample |
|---|---|---|---|
{failure_rows}

## 风险警告

| document_id | issue | value |
|---|---|---:|
{warning_rows}

## 边界说明

- 本 QA 能自动检查乱码、方框风险字符、私用区字符、错文字体系混入、pure/mixed 中文规则。
- 本 QA 不能完全证明民族语语法自然；语法自然性依赖真实文本源和抽检。
"""
    (out_dir / "QA_LANGUAGE_VALIDITY_REPORT.md").write_text(md, encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["documents", "passed_documents", "failure_count", "pass"]}, ensure_ascii=False, indent=2))
    return 1 if args.fail_on_warning and not summary["pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
