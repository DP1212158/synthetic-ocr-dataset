#!/usr/bin/env python3
"""QA text records before synthetic layout generation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from statistics import mean
from typing import Any


HTML_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
TIBETAN_RE = re.compile(r"[\u0f00-\u0fff]")
ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
MONGOLIAN_RE = re.compile(r"[\u1800-\u18af]")
HANGUL_RE = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
PRIVATE_USE_RE = re.compile(r"[\ue000-\uf8ff]")
REPLACEMENT_OR_BOX_RE = re.compile(r"[\ufffd\u25a0\u25a1\u25af]")
ZERO_WIDTH_UNSUPPORTED_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]")
MONGOLIAN_PRESENTATION_PUNCT_RE = re.compile(r"[︽︾︕︖︵︶︔﹇﹈]")
MONGOLIAN_UNSAFE_SYMBOL_RE = re.compile(r"[=+~※%!—–]")
NUMERIC_TITLE_RE = re.compile(r"^[\d\s\-:/.()]+$")
DATE_WORD_RE = re.compile(r"\b(nyied|hauh|nienz|ngoenz|month|year|day)\b", re.IGNORECASE)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profile(path: Path | None) -> dict[str, Any]:
    profile = read_json(path) if path else {}
    profile.setdefault("language_code", "unknown")
    profile.setdefault("language_name", "unknown")
    profile.setdefault("script_regex", r".")
    profile.setdefault("min_script_ratio", 0.35)
    profile.setdefault("max_digit_ratio", 0.25)
    profile.setdefault("max_latin_ratio", 1.0)
    profile.setdefault("max_cjk_ratio", 1.0)
    profile.setdefault("max_cyrillic_ratio", 1.0)
    profile.setdefault("max_tibetan_ratio", 1.0)
    profile.setdefault("max_arabic_ratio", 1.0)
    profile.setdefault("max_mongolian_ratio", 1.0)
    profile.setdefault("max_hangul_ratio", 1.0)
    profile.setdefault("max_unsupported_char_ratio", 0.0)
    profile.setdefault("max_pua_ratio", 0.0)
    return profile


def clean_markup(text: str) -> str:
    text = HTML_RE.sub(" ", str(text or ""))
    text = URL_RE.sub(" ", text)
    text = text.replace("\u00a0", " ")
    return " ".join(text.split())


def ratio(count: int, text: str) -> float:
    return count / max(len(text), 1)


def unsupported_chars(text: str, profile: dict[str, Any]) -> list[str]:
    """Return chars that are likely to render as tofu or break this profile's script."""
    text = text or ""
    cleanup = str(profile.get("cleanup_profile", "")).lower()
    bad: list[str] = []
    for pattern in [PRIVATE_USE_RE, REPLACEMENT_OR_BOX_RE]:
        bad.extend(pattern.findall(text))
    if cleanup not in {"arabic", "uyghur", "kazakh_arabic"}:
        bad.extend(ZERO_WIDTH_UNSUPPORTED_RE.findall(text))
    if cleanup in {"mongolian", "traditional_mongolian"}:
        bad.extend(MONGOLIAN_PRESENTATION_PUNCT_RE.findall(text))
        bad.extend(MONGOLIAN_UNSAFE_SYMBOL_RE.findall(text))
    return bad


def is_bad_title(title: str, script_re: re.Pattern[str]) -> bool:
    title = clean_markup(title)
    if len(title) < 4:
        return True
    if NUMERIC_TITLE_RE.fullmatch(title):
        return True
    script_chars = len(script_re.findall(title))
    digits = sum(ch.isdigit() for ch in title)
    if digits and digits >= script_chars:
        return True
    if DATE_WORD_RE.search(title) and digits:
        return True
    return script_chars < 3


def analyze_record(row: dict[str, Any], profile: dict[str, Any], script_re: re.Pattern[str]) -> dict[str, Any]:
    title = clean_markup(str(row.get("title", "")))
    text = clean_markup(str(row.get("text", row.get("block_content", ""))))
    script_ratio = ratio(len(script_re.findall(text)), text)
    digit_ratio = ratio(sum(ch.isdigit() for ch in text), text)
    latin_ratio = ratio(len(LATIN_RE.findall(text)), text)
    cjk_ratio = ratio(len(CJK_RE.findall(text)), text)
    cyrillic_ratio = ratio(len(CYRILLIC_RE.findall(text)), text)
    tibetan_ratio = ratio(len(TIBETAN_RE.findall(text)), text)
    arabic_ratio = ratio(len(ARABIC_RE.findall(text)), text)
    mongolian_ratio = ratio(len(MONGOLIAN_RE.findall(text)), text)
    hangul_ratio = ratio(len(HANGUL_RE.findall(text)), text)
    pua_ratio = ratio(len(PRIVATE_USE_RE.findall(text)), text)
    unsupported_char_ratio = ratio(len(unsupported_chars(text, profile)), text)
    issues: list[str] = []
    if len(text) < int(profile.get("min_text_length", 40)):
        issues.append("text_too_short")
    if script_ratio < float(profile["min_script_ratio"]):
        issues.append("low_script_ratio")
    if digit_ratio > float(profile["max_digit_ratio"]):
        issues.append("high_digit_ratio")
    if latin_ratio > float(profile["max_latin_ratio"]):
        issues.append("high_latin_ratio")
    if cjk_ratio > float(profile["max_cjk_ratio"]):
        issues.append("high_cjk_ratio")
    if cyrillic_ratio > float(profile["max_cyrillic_ratio"]):
        issues.append("high_cyrillic_ratio")
    if tibetan_ratio > float(profile["max_tibetan_ratio"]):
        issues.append("high_tibetan_ratio")
    if arabic_ratio > float(profile["max_arabic_ratio"]):
        issues.append("high_arabic_ratio")
    if mongolian_ratio > float(profile["max_mongolian_ratio"]):
        issues.append("high_mongolian_ratio")
    if hangul_ratio > float(profile["max_hangul_ratio"]):
        issues.append("high_hangul_ratio")
    if pua_ratio > float(profile["max_pua_ratio"]):
        issues.append("private_use_chars")
    if unsupported_char_ratio > float(profile["max_unsupported_char_ratio"]):
        issues.append("unsupported_or_box_risk_chars")
    if is_bad_title(title, script_re):
        issues.append("bad_or_numeric_title")
    return {
        "record_id": str(row.get("record_id", row.get("source_record_id", ""))),
        "title": title,
        "text_length": len(text),
        "script_ratio": round(script_ratio, 4),
        "digit_ratio": round(digit_ratio, 4),
        "latin_ratio": round(latin_ratio, 4),
        "cjk_ratio": round(cjk_ratio, 4),
        "cyrillic_ratio": round(cyrillic_ratio, 4),
        "tibetan_ratio": round(tibetan_ratio, 4),
        "arabic_ratio": round(arabic_ratio, 4),
        "mongolian_ratio": round(mongolian_ratio, 4),
        "hangul_ratio": round(hangul_ratio, 4),
        "pua_ratio": round(pua_ratio, 4),
        "unsupported_char_ratio": round(unsupported_char_ratio, 4),
        "issues": issues,
        "usable": not issues or issues == ["bad_or_numeric_title"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-jsonl", required=True)
    parser.add_argument("--language-profile")
    parser.add_argument("--output-dir")
    parser.add_argument("--min-usable-records", type=int, default=40)
    parser.add_argument("--max-bad-title-ratio", type=float, default=0.35)
    parser.add_argument("--max-hard-issue-ratio", type=float, default=0.02)
    parser.add_argument("--enforce-title-quality", action="store_true")
    parser.add_argument("--sample-size", type=int, default=12)
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args()

    text_path = Path(args.text_jsonl)
    profile = load_profile(Path(args.language_profile) if args.language_profile else None)
    script_re = re.compile(str(profile["script_regex"]))

    analyses = []
    for line_no, line in enumerate(text_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        item = analyze_record(row, profile, script_re)
        item["line_no"] = line_no
        analyses.append(item)

    usable = [item for item in analyses if item["usable"]]
    bad_titles = [item for item in analyses if "bad_or_numeric_title" in item["issues"]]
    hard_issue_items = [item for item in analyses if any(issue != "bad_or_numeric_title" for issue in item["issues"])]
    summary = {
        "text_jsonl": str(text_path),
        "language_code": profile["language_code"],
        "language_name": profile["language_name"],
        "total_records": len(analyses),
        "usable_records": len(usable),
        "bad_title_records": len(bad_titles),
        "hard_issue_records": len(hard_issue_items),
        "bad_title_ratio": round(len(bad_titles) / max(len(analyses), 1), 4),
        "hard_issue_ratio": round(len(hard_issue_items) / max(len(analyses), 1), 4),
        "avg_text_length": round(mean([item["text_length"] for item in analyses]) if analyses else 0, 2),
        "avg_script_ratio": round(mean([item["script_ratio"] for item in analyses]) if analyses else 0, 4),
        "avg_digit_ratio": round(mean([item["digit_ratio"] for item in analyses]) if analyses else 0, 4),
        "avg_pua_ratio": round(mean([item["pua_ratio"] for item in analyses]) if analyses else 0, 4),
        "avg_unsupported_char_ratio": round(mean([item["unsupported_char_ratio"] for item in analyses]) if analyses else 0, 4),
        "samples_with_issues": hard_issue_items[: args.sample_size],
        "samples_bad_titles": bad_titles[: args.sample_size],
        "title_quality_enforced": args.enforce_title_quality,
        "title_fallback_required": bool(bad_titles),
    }
    summary["pass"] = (
        summary["usable_records"] >= args.min_usable_records
        and summary["hard_issue_ratio"] <= args.max_hard_issue_ratio
        and (not args.enforce_title_quality or summary["bad_title_ratio"] <= args.max_bad_title_ratio)
    )

    out_dir = Path(args.output_dir) if args.output_dir else text_path.parent / "reports"
    write_json(out_dir / "text_quality_summary.json", summary)
    issue_rows = "\n".join(
        f"| {item['line_no']} | {item['record_id']} | {item['title'][:40]} | {item['script_ratio']} | {item['digit_ratio']} | {item['pua_ratio']} | {item['unsupported_char_ratio']} | {', '.join(item['issues'])} |"
        for item in summary["samples_with_issues"]
    )
    bad_title_rows = "\n".join(
        f"| {item['line_no']} | {item['record_id']} | {item['title'][:50]} | {item['text_length']} |"
        for item in summary["samples_bad_titles"]
    )
    md = f"""# Text Records QA

- 文本文件：`{text_path}`
- 语言：{summary['language_name']} / `{summary['language_code']}`
- 总记录数：{summary['total_records']}
- 可用记录数：{summary['usable_records']}
- 坏标题/数字标题记录数：{summary['bad_title_records']}
- 硬问题记录数：{summary['hard_issue_records']}
- 标题质量是否阻断：{summary['title_quality_enforced']}
- 是否需要安全标题回退：{summary['title_fallback_required']}
- 平均文本长度：{summary['avg_text_length']}
- 平均目标文字占比：{summary['avg_script_ratio']}
- 平均私用区字符占比：{summary['avg_pua_ratio']}
- 平均异常/方框风险字符占比：{summary['avg_unsupported_char_ratio']}
- 结论：{'通过' if summary['pass'] else '需处理'}

## 硬问题样本

| 行号 | record_id | title | script_ratio | digit_ratio | pua_ratio | unsupported_char_ratio | issues |
|---:|---|---|---:|---:|---:|---:|---|
{issue_rows}

## 坏标题样本

| 行号 | record_id | title | text_length |
|---:|---|---|---:|
{bad_title_rows}
"""
    (out_dir / "TEXT_QA_REPORT.md").write_text(md, encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["total_records", "usable_records", "bad_title_records", "hard_issue_records", "pass"]}, ensure_ascii=False, indent=2))
    return 1 if args.fail_on_warning and not summary["pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
