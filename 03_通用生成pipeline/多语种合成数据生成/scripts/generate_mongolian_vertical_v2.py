#!/usr/bin/env python3
"""Generate native vertical-layout synthetic pages for traditional Mongolian."""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path
from typing import Any

from synthetic_text_utils import cleanse_text, load_language_profile, read_text_records, record_text, record_title, safe_fragment, select_span


CATEGORIES = [
    ("01_报纸页", "newspaper_page", "报纸页"),
    ("02_证书证明", "certificate_proof", "证书证明"),
    ("03_考试卷", "exam_paper", "考试卷"),
    ("04_标牌海报场景", "sign_poster_scene", "标牌海报场景"),
    ("05_书籍页", "book_page", "书籍页"),
    ("06_教科书页", "textbook_page", "教科书页"),
    ("07_杂志期刊页", "magazine_journal", "杂志期刊页"),
    ("08_学术文献页", "academic_paper", "学术文献页"),
    ("09_历史文档_古籍", "historical_classic", "历史文档_古籍"),
    ("10_公告通知", "notice_announcement", "公告通知"),
    ("11_复杂表单登记页", "complex_form", "复杂表单登记页"),
    ("12_手写笔记信件", "handwritten_letter", "手写笔记信件"),
]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def clean_version_dir(version_dir: Path) -> None:
    if version_dir.exists():
        for child in version_dir.iterdir():
            if child.is_dir() and child.name[:2].isdigit():
                shutil.rmtree(child)
    (version_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (version_dir / "reports").mkdir(parents=True, exist_ok=True)


def base_css(profile: dict[str, Any]) -> str:
    font = profile.get("font_family", '"Noto Sans Mongolian", "Arial Unicode", sans-serif')
    return f"""
* {{ box-sizing: border-box; }}
html, body {{ margin:0; padding:0; background:#d8dadd; }}
body {{ font-family:{font}; color:#161616; }}
.page {{
  width: 1180px;
  min-height: 1680px;
  margin: 0 auto;
  background: #fbf8ed;
  position: relative;
  overflow: hidden;
}}
.vtext {{
  writing-mode: vertical-lr;
  direction: ltr;
  text-orientation: mixed;
  line-height: 1.42;
  word-break: keep-all;
  overflow-wrap: normal;
  overflow: hidden;
}}
[data-block-id] {{ position:absolute; overflow:visible; }}
.title {{ font-weight:900; font-size:34px; line-height:1.36; }}
.subtitle {{ font-weight:800; font-size:24px; line-height:1.36; }}
.body {{ font-size:20px; line-height:1.42; }}
.small {{ font-size:16px; line-height:1.34; }}
.tiny {{ font-size:13px; line-height:1.28; }}
.box {{ border:2px solid #202020; background:rgba(255,255,255,.42); }}
.thin {{ border:1px solid #373737; }}
.rule-v {{ position:absolute; top:54px; bottom:54px; width:2px; background:#222; opacity:.75; }}
.rule-h {{ position:absolute; left:54px; right:54px; height:2px; background:#222; opacity:.75; }}
.stamp {{ border:4px solid #9c2f2f; color:#9c2f2f; border-radius:50%; opacity:.7; }}
.image-fill {{
  background: repeating-linear-gradient(135deg,#d8d2c2,#d8d2c2 14px,#efe9d9 14px,#efe9d9 28px);
  border:2px solid #303030;
}}
.soft-fill {{ background:rgba(204,218,212,.36); }}
.note-fill {{ background:rgba(242,224,181,.45); }}
"""


class BlockBuilder:
    def __init__(self, doc_id: str, records: list[dict[str, str]], rng: random.Random):
        self.doc_id = doc_id
        self.records = records
        self.rng = rng
        self.n = 0
        self.blocks: list[str] = []

    def add(self, x: int, y: int, w: int, h: int, label: str, text: str = "", cls: str = "body", extra: str = "") -> None:
        self.n += 1
        block_id = f"{self.doc_id}_b{self.n:04d}"
        classes = extra or ""
        if label not in {"image", "answer_area", "decor"}:
            classes = f"vtext {cls} {classes}".strip()
            content = esc(text)
        else:
            classes = f"{cls} {classes}".strip()
            content = esc(text)
        style = f"position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px"
        if label == "decor":
            self.blocks.append(f'<div class="{classes}" style="{style}">{content}</div>')
            return
        self.blocks.append(
            f'<div data-block-id="{block_id}" data-label="{label}" class="{classes}" '
            f'style="{style}">{content}</div>'
        )

    def text(self, min_len: int, max_len: int) -> str:
        return record_text(self.records, self.rng, min_len, max_len)

    def long_text(self, min_len: int, max_len: int) -> str:
        pool = [rec for rec in self.records if len(rec["text"]) >= min_len] or self.records
        for _ in range(16):
            text = select_span(self.rng.choice(pool)["text"], self.rng, min_len, max_len)
            if len(text) >= min_len:
                return text
        parts: list[str] = []
        while len(" ".join(parts)) < min_len and len(parts) < 6:
            parts.append(cleanse_text(self.rng.choice(self.records)["text"]))
        return select_span(" ".join(parts), self.rng, min_len, max_len)

    def fill_text(self, height: int, min_len: int, max_len: int, cls: str = "body") -> str:
        # Native vertical pages need text length derived from column height. The
        # shared horizontal sampler intentionally shortens vertical text, which
        # leaves tall Mongolian columns visually empty.
        if "tiny" in cls:
            ratio_min, ratio_max = 0.055, 0.085
        elif "small" in cls:
            ratio_min, ratio_max = 0.075, 0.115
        else:
            ratio_min, ratio_max = 0.10, 0.16
        target_min = max(min_len, int(height * ratio_min))
        target_max = max(max_len, int(height * ratio_max), target_min + 16)
        return self.long_text(target_min, target_max)

    def title(self, min_len: int = 6, max_len: int = 48) -> str:
        return record_title(self.records, self.rng, min_len, max_len)


def add_column_text(bb: BlockBuilder, x0: int, y0: int, cols: int, col_w: int, col_gap: int, h: int, label: str = "paragraph", cls: str = "body", min_len: int = 24, max_len: int = 72) -> None:
    for i in range(cols):
        bb.add(x0 + i * (col_w + col_gap), y0, col_w, h, label, bb.fill_text(h, min_len, max_len, cls), cls)


def layout_newspaper(bb: BlockBuilder, variant: int) -> tuple[int, int]:
    w, h = 1180, 1760
    bb.add(36, 48, 36, 1640, "metadata", "2026", "small")
    bb.add(86, 48, 52, 1640, "document_title", safe_fragment(4, 30), "title")
    for x in [160, 500, 840]:
        bb.add(x, 58, 2, 1588, "decor", "", "rule-v")
    bb.add(184, 58, 42, 1540, "section_title", bb.title(), "subtitle")
    add_column_text(bb, 244, 58, 5, 32, 20, 1540, min_len=40, max_len=88)
    bb.add(538, 58, 170, 430, "image", "", "image-fill")
    bb.add(724, 58, 28, 430, "caption", bb.text(16, 38), "small")
    add_column_text(bb, 538, 528, 5, 30, 18, 1068, min_len=28, max_len=74)
    bb.add(876, 58, 40, 1540, "section_title", bb.title(), "subtitle")
    add_column_text(bb, 936, 58, 4, 30, 18, 1540, "list_item", "small", 20, 56)
    bb.add(1080, 58, 28, 1540, "footer", "01", "tiny")
    return w, h


def layout_certificate(bb: BlockBuilder, variant: int) -> tuple[int, int]:
    w, h = 1040, 1420
    bb.add(54, 54, 932, 1312, "decor", "", "box")
    bb.add(112, 112, 52, 1120, "metadata", "20260702", "small")
    bb.add(214, 112, 70, 1120, "document_title", safe_fragment(4, 30), "title")
    bb.add(340, 176, 46, 940, "document_subtitle", bb.title(), "subtitle")
    add_column_text(bb, 440, 176, 4, 34, 36, 940, "paragraph", "body", 24, 60)
    bb.add(784, 248, 112, 112, "seal", safe_fragment(2, 10), "subtitle stamp")
    bb.add(846, 176, 34, 940, "metadata", "2026-07-02", "small")
    return w, h


def layout_exam(bb: BlockBuilder, variant: int) -> tuple[int, int]:
    w, h = 1120, 1620
    bb.add(52, 52, 50, 1500, "document_title", bb.title(), "title")
    bb.add(128, 52, 30, 1500, "metadata", "2026", "small")
    for i, x in enumerate(range(210, 950, 92), 1):
        bb.add(x, 68, 32, 640, "question_text", f"{i}. {bb.text(18, 52)}", "body")
        bb.add(x + 38, 68, 38, 640, "answer_area", "", "box soft-fill")
        bb.add(x, 760, 32, 640, "question_text", f"{i+8}. {bb.text(18, 52)}", "body")
        bb.add(x + 38, 760, 38, 640, "answer_area", "", "box")
    return w, h


def layout_sign(bb: BlockBuilder, variant: int) -> tuple[int, int]:
    w, h = (1380, 760) if variant % 2 else (900, 1180)
    bb.add(50, 50, w - 100, h - 100, "decor", "", "box note-fill")
    bb.add(120, 100, 74, h - 200, "document_title", safe_fragment(4, 28), "title")
    bb.add(250, 120, 52, h - 240, "section_title", bb.title(), "subtitle")
    add_column_text(bb, 360, 130, 5 if w > 1000 else 3, 40, 42, h - 260, "paragraph", "body", 18, 54)
    bb.add(w - 150, 130, 48, h - 260, "metadata", "2026", "small")
    return w, h


def layout_book(bb: BlockBuilder, variant: int, textbook: bool = False) -> tuple[int, int]:
    w, h = 980, 1500
    bb.add(56, 64, 34, 1350, "page_number", str(variant), "tiny")
    bb.add(122, 74, 48, 1320, "chapter_title" if textbook else "document_title", bb.title(), "title")
    if textbook:
        bb.add(210, 90, 140, 430, "image", "", "image-fill")
        bb.add(372, 90, 30, 430, "caption", bb.text(14, 36), "small")
        add_column_text(bb, 450, 90, 7, 32, 20, 1280, "paragraph", "body", 28, 72)
    else:
        add_column_text(bb, 220, 74, 13, 30, 20, 1320, "paragraph", "body", 34, 84)
    return w, h


def layout_magazine(bb: BlockBuilder, variant: int) -> tuple[int, int]:
    w, h = 1120, 1500
    bb.add(60, 62, 52, 1360, "document_title", safe_fragment(4, 30), "title")
    bb.add(150, 84, 260, 520, "image", "", "image-fill")
    bb.add(438, 84, 34, 520, "caption", bb.text(14, 34), "small")
    bb.add(520, 84, 46, 1280, "section_title", bb.title(), "subtitle")
    add_column_text(bb, 600, 84, 8, 32, 18, 1280, "paragraph", "body", 28, 76)
    return w, h


def layout_academic(bb: BlockBuilder, variant: int) -> tuple[int, int]:
    w, h = 1120, 1580
    bb.add(54, 58, 42, 1460, "metadata", "2026", "small")
    bb.add(128, 58, 56, 1460, "document_title", bb.title(), "title")
    bb.add(220, 76, 34, 1380, "section_title", safe_fragment(2, 18), "subtitle")
    add_column_text(bb, 280, 76, 7, 30, 18, 1380, "paragraph", "body", 32, 82)
    bb.add(710, 96, 250, 360, "image", "", "box soft-fill")
    bb.add(988, 96, 28, 360, "caption", bb.text(12, 34), "small")
    add_column_text(bb, 710, 510, 5, 30, 18, 900, "paragraph", "body", 24, 68)
    return w, h


def layout_historical(bb: BlockBuilder, variant: int) -> tuple[int, int]:
    w, h = 960, 1600
    bb.add(44, 44, 872, 1512, "decor", "", "box")
    bb.add(92, 86, 42, 1400, "metadata", "ᠮᠡᠳᠡᠭᠳᠡᠯ", "small")
    for i, x in enumerate(range(178, 820, 58)):
        bb.add(x, 98 + (i % 2) * 24, 34, 1330, "paragraph", bb.text(26, 70), "body")
    bb.add(850, 102, 28, 1320, "page_number", str(variant), "tiny")
    return w, h


def layout_notice(bb: BlockBuilder, variant: int) -> tuple[int, int]:
    w, h = 960, 1360
    bb.add(70, 70, 820, 1220, "decor", "", "box note-fill")
    bb.add(150, 118, 62, 1080, "document_title", safe_fragment(4, 28), "title")
    bb.add(282, 140, 44, 1020, "section_title", bb.title(), "subtitle")
    add_column_text(bb, 380, 140, 5, 36, 34, 1020, "paragraph", "body", 26, 70)
    bb.add(760, 150, 38, 980, "metadata", "2026-07-02", "small")
    return w, h


def layout_form(bb: BlockBuilder, variant: int) -> tuple[int, int]:
    w, h = 1160, 1500
    bb.add(54, 54, 1052, 1392, "decor", "", "box")
    bb.add(102, 92, 54, 1320, "document_title", safe_fragment(4, 30), "title")
    x = 210
    for col in range(8):
        bb.add(x, 110, 30, 260, "field_label", safe_fragment(2, 12), "small")
        bb.add(x, 396, 40, 360, "field_value", bb.text(10, 32), "body box")
        bb.add(x, 806, 30, 250, "field_label", safe_fragment(2, 12), "small")
        bb.add(x, 1080, 40, 300, "field_value", bb.text(10, 32), "body box")
        x += 92
    return w, h


def layout_letter(bb: BlockBuilder, variant: int) -> tuple[int, int]:
    w, h = 1040, 1480
    bb.add(70, 70, 900, 1340, "decor", "", "box")
    bb.add(130, 120, 44, 1180, "recipient", bb.title(4, 24), "subtitle")
    add_column_text(bb, 220, 130, 9, 34, 24, 1160, "paragraph", "body", 24, 68)
    bb.add(820, 160, 40, 1000, "metadata", "2026-07-02", "small")
    return w, h


LAYOUTS = {
    "newspaper_page": layout_newspaper,
    "certificate_proof": layout_certificate,
    "exam_paper": layout_exam,
    "sign_poster_scene": layout_sign,
    "book_page": lambda bb, v: layout_book(bb, v, False),
    "textbook_page": lambda bb, v: layout_book(bb, v, True),
    "magazine_journal": layout_magazine,
    "academic_paper": layout_academic,
    "historical_classic": layout_historical,
    "notice_announcement": layout_notice,
    "complex_form": layout_form,
    "handwritten_letter": layout_letter,
}


def render_html(profile: dict[str, Any], doc_id: str, category_cn: str, blocks: list[str], width: int, height: int) -> str:
    return f"""<!doctype html>
<html lang="{profile.get('html_lang', 'mn-Mong')}" dir="ltr">
<head>
<meta charset="utf-8">
<title>{esc(category_cn)} {esc(doc_id)}</title>
<style>{base_css(profile)}</style>
</head>
<body><main class="page" style="width:{width}px;min-height:{height}px">{''.join(blocks)}</main></body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-jsonl", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--min-records", type=int, default=40)
    parser.add_argument("--seed", type=int, default=2026070209)
    parser.add_argument("--version-name", default="v2")
    args = parser.parse_args()

    profile = load_language_profile(Path(args.language_profile))
    records = read_text_records(Path(args.text_jsonl), profile, args.min_records)
    rng = random.Random(args.seed)
    version_dir = Path(args.output_root)
    clean_version_dir(version_dir)

    all_category_plan = []
    for cat_index, (folder, category, category_cn) in enumerate(CATEGORIES, 1):
        cat_dir = version_dir / folder
        for sub in ["html", "images", "labels", "metadata", "reports"]:
            (cat_dir / sub).mkdir(parents=True, exist_ok=True)
        html_manifest = []
        for variant in range(1, 7):
            doc_id = f"{cat_index:02d}_{category}_vertical_{variant:02d}"
            bb = BlockBuilder(doc_id, records, rng)
            width, height = LAYOUTS[category](bb, variant)
            html_text = render_html(profile, doc_id, category_cn, bb.blocks, width, height)
            html_path = cat_dir / "html" / f"{doc_id}.html"
            html_path.write_text(html_text, encoding="utf-8")
            html_manifest.append(
                {
                    "document_id": doc_id,
                    "category": category,
                    "category_cn": category_cn,
                    "variant": variant,
                    "layout_name": f"{category}_vertical_v{variant:02d}",
                    "template_type": category,
                    "title": category_cn,
                    "doc_no": f"MN-V2-{cat_index:02d}-{variant:02d}",
                    "date": "2026-07-02",
                    "rows": None,
                    "columns": None,
                    "source_records": [],
                    "generator": "mongolian_vertical_native_v2",
                    "page_width": width,
                    "page_height": height,
                    "tight_crop": True,
                }
            )
        write_json(cat_dir / "metadata" / "html_manifest.json", html_manifest)
        write_json(cat_dir / "metadata" / "category_plan.json", {"category": category, "category_cn": category_cn, "samples": 6})
        write_json(cat_dir / "metadata" / "mongolian_vertical_template_spec.json", {"category": category, "category_cn": category_cn, "layout_family": "native_vertical_absolute"})
        all_category_plan.append({"category": category, "category_cn": category_cn, "samples": 6, "folder": folder})

    write_json(version_dir / "metadata" / "category_plan.json", all_category_plan)
    print(json.dumps({"version_dir": str(version_dir), "categories": len(CATEGORIES), "html": len(CATEGORIES) * 6}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
