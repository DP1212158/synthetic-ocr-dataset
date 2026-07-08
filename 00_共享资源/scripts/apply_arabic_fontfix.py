#!/usr/bin/env python3
"""Create an Arabic-script font-fixed copy of a generated OCR version."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path("/Users/dp/Downloads/中央民族大学合作项目/合成OCR数据集_交付版")
FONT_DIR = PROJECT_ROOT / "00_共享资源" / "fonts" / "arabic"

FONT_FACE_CSS = f"""
    @font-face {{ font-family: 'Local Noto Naskh Arabic'; src: url('{(FONT_DIR / "NotoNaskhArabic-Regular.ttf").as_uri()}') format('truetype'); font-weight: 400; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Noto Naskh Arabic'; src: url('{(FONT_DIR / "NotoNaskhArabic-Bold.ttf").as_uri()}') format('truetype'); font-weight: 700 900; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Noto Sans Arabic'; src: url('{(FONT_DIR / "NotoSansArabic-Regular.ttf").as_uri()}') format('truetype'); font-weight: 400; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Noto Sans Arabic'; src: url('{(FONT_DIR / "NotoSansArabic-Bold.ttf").as_uri()}') format('truetype'); font-weight: 700 900; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Scheherazade New'; src: url('{(FONT_DIR / "ScheherazadeNew-Regular.ttf").as_uri()}') format('truetype'); font-weight: 400; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Scheherazade New'; src: url('{(FONT_DIR / "ScheherazadeNew-Bold.ttf").as_uri()}') format('truetype'); font-weight: 700 900; font-style: normal; font-display: block; }}
"""

FONT_STACK = '"Local Noto Naskh Arabic", "Local Noto Sans Arabic", "Local Scheherazade New", serif'
HAND_FONT_STACK = '"Local Scheherazade New", "Local Noto Naskh Arabic", "Local Noto Sans Arabic", serif'

ARABIC_SHAPING_CSS = f"""
    html, body, .page, [data-block-id] {{
      font-family: {FONT_STACK} !important;
      font-kerning: normal;
      text-rendering: geometricPrecision;
      font-feature-settings: "calt" 1, "liga" 1, "rlig" 1, "kern" 1;
      letter-spacing: 0 !important;
      unicode-bidi: plaintext;
    }}
    .hand-para, .hand-small, .hand-line, .sticky, .letter, .memo, .diary, .lined, .class-notes {{
      font-family: {HAND_FONT_STACK} !important;
      font-feature-settings: "calt" 1, "liga" 1, "rlig" 1, "kern" 1;
      letter-spacing: 0 !important;
    }}
"""


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_version(src: Path, dst: Path, overwrite: bool) -> None:
    if dst.exists():
        if not overwrite:
            raise FileExistsError(f"Destination already exists: {dst}")
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def update_profile(profile_path: Path, src: Path, dst: Path) -> None:
    profile = read_json(profile_path)
    profile["font_family"] = FONT_STACK
    profile["arabic_fontfix"] = {
        "enabled": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_version": src.name,
        "target_version": dst.name,
        "font_stack": FONT_STACK,
        "hand_font_stack": HAND_FONT_STACK,
        "font_files": [
            str(FONT_DIR / "NotoNaskhArabic-Regular.ttf"),
            str(FONT_DIR / "NotoNaskhArabic-Bold.ttf"),
            str(FONT_DIR / "NotoSansArabic-Regular.ttf"),
            str(FONT_DIR / "NotoSansArabic-Bold.ttf"),
            str(FONT_DIR / "ScheherazadeNew-Regular.ttf"),
            str(FONT_DIR / "ScheherazadeNew-Bold.ttf"),
        ],
        "notes": [
            "Use local OpenType Arabic fonts instead of system fallback.",
            "Keep original Unicode text and labels unchanged; rely on Chromium shaping.",
            "Do not insert presentation-form codepoints, ZWJ, or ZWNJ.",
        ],
    }
    write_json(profile_path, profile)


def inject_css(html: str) -> str:
    html = re.sub(
        r"body\s*\{\s*font-family:\s*[^;]+;",
        f"body {{ font-family: {FONT_STACK};",
        html,
        count=1,
    )
    html = re.sub(
        r'"Local Bradley Hand",\s*"Bradley Hand",\s*"Marker Felt",\s*"Comic Sans MS",\s*"Local Arial",\s*cursive',
        HAND_FONT_STACK,
        html,
    )
    html = re.sub(r"letter-spacing\s*:\s*[^;]+;", "letter-spacing: 0;", html)
    marker = "@font-face { font-family: 'Local Arial Unicode';"
    if marker in html and "Local Noto Naskh Arabic" not in html:
        html = html.replace(marker, FONT_FACE_CSS + "    " + marker, 1)
    elif "</style>" in html and "Local Noto Naskh Arabic" not in html:
        html = html.replace("</style>", FONT_FACE_CSS + "\n</style>", 1)
    if "arabic-fontfix-start" not in html:
        html = html.replace("</style>", f"    /* arabic-fontfix-start */\n{ARABIC_SHAPING_CSS}    /* arabic-fontfix-end */\n    </style>", 1)
    return html


def update_html_files(dst: Path) -> int:
    count = 0
    for html_path in sorted(dst.glob("*/html/*.html")):
        original = html_path.read_text(encoding="utf-8")
        updated = inject_css(original)
        if updated != original:
            html_path.write_text(updated, encoding="utf-8")
            count += 1
    return count


def write_report(dst: Path, src: Path, html_count: int) -> None:
    report = dst / "reports" / "ARABIC_FONTFIX_REPORT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "\n".join(
            [
                "# Arabic Font Fix Report",
                "",
                f"- Source version: `{src}`",
                f"- Target version: `{dst}`",
                f"- HTML files updated: `{html_count}`",
                f"- Main font stack: `{FONT_STACK}`",
                f"- Handwritten-style stack: `{HAND_FONT_STACK}`",
                "- Strategy: keep Unicode text/labels unchanged and use local OpenType Arabic fonts through Chromium shaping.",
                "- Avoided: Arabic presentation-form conversion, ZWJ/ZWNJ insertion, per-character text splitting.",
                "",
                "## Font Files",
                "",
                f"- `{FONT_DIR / 'NotoNaskhArabic-Regular.ttf'}`",
                f"- `{FONT_DIR / 'NotoNaskhArabic-Bold.ttf'}`",
                f"- `{FONT_DIR / 'NotoSansArabic-Regular.ttf'}`",
                f"- `{FONT_DIR / 'NotoSansArabic-Bold.ttf'}`",
                f"- `{FONT_DIR / 'ScheherazadeNew-Regular.ttf'}`",
                f"- `{FONT_DIR / 'ScheherazadeNew-Bold.ttf'}`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-version-dir", required=True, type=Path)
    parser.add_argument("--target-version-dir", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    src = args.source_version_dir
    dst = args.target_version_dir
    if not src.exists():
        raise FileNotFoundError(src)
    missing_fonts = [p for p in [FONT_DIR / "NotoNaskhArabic-Regular.ttf", FONT_DIR / "NotoNaskhArabic-Bold.ttf"] if not p.exists()]
    if missing_fonts:
        raise FileNotFoundError(f"Missing required fonts: {missing_fonts}")

    copy_version(src, dst, args.overwrite)
    profile_path = dst / "metadata" / "language_profile.json"
    update_profile(profile_path, src, dst)
    html_count = update_html_files(dst)
    write_report(dst, src, html_count)
    print(json.dumps({"target": str(dst), "html_files_updated": html_count}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
