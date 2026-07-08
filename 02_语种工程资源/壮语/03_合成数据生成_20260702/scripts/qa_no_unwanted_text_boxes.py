#!/usr/bin/env python3
"""Check VL3 HTML for unwanted ordinary text container boxes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ALLOWED_LABELS = {
    "image",
    "photo",
    "figure",
    "photo_lead",
    "image_figure",
    "answer_area",
    "seal",
    "table_header",
    "table_cell_text",
    "table_cell_number",
}
ALLOWED_CLASSES = {
    "stamp",
    "seal-circle",
    "image-box",
    "qr-box",
    "answer-box",
    "award-cert",
    "ornamental-cert",
    "inner-frame",
}
TEXT_BOX_CLASS_PATTERNS = [
    re.compile(r"(?:^|[-_])(card|box|kv|clause|note|followup|extract|brief|digest|tag|chip|badge|pill)(?:$|[-_])", re.I),
]
STYLE_BORDER_RE = re.compile(r"border(?:-(?:left|right|top|bottom))?\s*:\s*(?!0\b|none\b)[^;]+;", re.I)
STYLE_SHADOW_RE = re.compile(r"box-shadow\s*:\s*(?!none\b)[^;]+;", re.I)
BLOCK_RE = re.compile(
    r"<(?P<tag>[a-zA-Z0-9]+)(?P<attrs>[^>]*\bdata-block-id=\"(?P<bid>[^\"]+)\"[^>]*)>",
    re.I,
)
STYLE_BLOCK_RE = re.compile(r"<style[^>]*>(?P<css>.*?)</style>", re.I | re.S)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def attr(attrs: str, name: str) -> str:
    m = re.search(rf'\b{name}="([^"]*)"', attrs)
    return m.group(1) if m else ""


def has_boxy_class(classes: str) -> bool:
    tokens = [token.strip() for token in classes.split() if token.strip()]
    if any(token in ALLOWED_CLASSES for token in tokens):
        return False
    return any(pattern.search(token) for token in tokens for pattern in TEXT_BOX_CLASS_PATTERNS)


def visible_boxy_css_for_classes(html_text: str, classes: str) -> bool:
    """Return true when a risky class still has visible CSS border/shadow."""
    tokens = [token.strip() for token in classes.split() if token.strip()]
    risky = [token for token in tokens if has_boxy_class(token)]
    if not risky:
        return False
    css = "\n".join(match.group("css") for match in STYLE_BLOCK_RE.finditer(html_text))
    for token in risky:
        pattern = re.compile(rf"\.{re.escape(token)}(?:[^\{{]*)\{{(?P<body>.*?)\}}", re.I | re.S)
        for match in pattern.finditer(css):
            body = match.group("body")
            if STYLE_BORDER_RE.search(body) or STYLE_SHADOW_RE.search(body):
                return True
    return False


def inspect_html(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    issues = []
    for match in BLOCK_RE.finditer(text):
        attrs = match.group("attrs")
        label = attr(attrs, "data-label")
        classes = attr(attrs, "class")
        style = attr(attrs, "style")
        if label in ALLOWED_LABELS:
            continue
        style_has_box = bool(STYLE_BORDER_RE.search(style) or STYLE_SHADOW_RE.search(style))
        css_has_box = visible_boxy_css_for_classes(text, classes)
        if style_has_box or css_has_box:
            issues.append({
                "html": str(path),
                "block_id": match.group("bid"),
                "label": label,
                "class": classes,
                "style_border": bool(STYLE_BORDER_RE.search(style)),
                "style_shadow": bool(STYLE_SHADOW_RE.search(style)),
                "css_box": css_has_box,
                "boxy_class": has_boxy_class(classes),
            })
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    parser.add_argument("--max-issues", type=int, default=0)
    args = parser.parse_args()
    version_dir = Path(args.version_dir)
    all_issues = []
    for html_path in sorted(version_dir.glob("*/html/*.html")):
        all_issues.extend(inspect_html(html_path))
    summary = {
        "documents_checked": len(list(version_dir.glob("*/html/*.html"))),
        "unwanted_text_box_issues": len(all_issues),
        "samples": all_issues[:30],
        "no_unwanted_text_box_pass": len(all_issues) <= args.max_issues,
        "pass": len(all_issues) <= args.max_issues,
    }
    write_json(version_dir / "reports" / "no_unwanted_text_box_summary.json", summary)
    sample_rows = "\n".join(
        f"| `{Path(item['html']).name}` | `{item['block_id']}` | {item['label']} | `{item['class']}` |"
        for item in summary["samples"]
    )
    (version_dir / "reports" / "QA_NO_UNWANTED_TEXT_BOX_REPORT.md").write_text(
        f"""# No Unwanted Text Box QA

- 检查文档数：{summary['documents_checked']}
- 普通文本框风险：{summary['unwanted_text_box_issues']}
- 结论：{'通过' if summary['pass'] else '需处理'}

| HTML | block_id | label | class |
|---|---|---|---|
{sample_rows}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
