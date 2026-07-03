#!/usr/bin/env python3
"""Generate v12 remaining Tibetan layout categories from structured JSON templates."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import random
import re
import shutil
from pathlib import Path
from typing import Any, Callable


CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
TIBETAN_DECORATIVE_MARK_RE = re.compile(r"[\u0f04-\u0f0a\u0f0c\u0f0e-\u0f14\u0f3a-\u0f3d]")
TIBETAN_SHAD_RE = re.compile(r"\s*།+\s*")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIBETAN_FONT_DIR = PROJECT_ROOT / "assets" / "fonts" / "tibetan"

THEMES = [
    {"ink": "#24272a", "muted": "#646c73", "line": "#b8c0c8", "accent": "#315f72", "paper": "#fffefa", "soft": "#eef4f6"},
    {"ink": "#2b2520", "muted": "#78685c", "line": "#c7b8a9", "accent": "#8a5738", "paper": "#fff9ed", "soft": "#f4ead8"},
    {"ink": "#1e2921", "muted": "#617163", "line": "#b7c6bb", "accent": "#386b52", "paper": "#fcfff7", "soft": "#eef7ef"},
    {"ink": "#2a2630", "muted": "#6e6675", "line": "#c0b8cb", "accent": "#5b5f94", "paper": "#fdfcff", "soft": "#f2f0f8"},
]


def now_local() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def cleanse_text(text: str) -> str:
    text = CYRILLIC_RE.sub("", text)
    text = CJK_RE.sub("", text)
    text = TIBETAN_DECORATIVE_MARK_RE.sub(" ", text)
    text = TIBETAN_SHAD_RE.sub(" ", text)
    text = text.replace("།", " ").replace("...", " ")
    return " ".join(text.split())


def tibetan_font_faces() -> str:
    regular = (TIBETAN_FONT_DIR / "NotoSerifTibetan-Regular.ttf").resolve().as_uri()
    bold = (TIBETAN_FONT_DIR / "NotoSerifTibetan-Bold.ttf").resolve().as_uri()
    black = (TIBETAN_FONT_DIR / "NotoSerifTibetan-Black.ttf").resolve().as_uri()
    jomo = (TIBETAN_FONT_DIR / "Jomolhari-Regular.ttf").resolve().as_uri()
    return f"""
    @font-face {{ font-family: 'Local Noto Serif Tibetan'; src: url('{regular}') format('truetype'); font-weight: 400; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Noto Serif Tibetan'; src: url('{bold}') format('truetype'); font-weight: 700; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Noto Serif Tibetan'; src: url('{black}') format('truetype'); font-weight: 900; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Jomolhari'; src: url('{jomo}') format('truetype'); font-weight: 400; font-style: normal; font-display: block; }}
    """


def load_language_profile(path: Path | None) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8")) if path else {}
    profile.setdefault("language_code", "bo")
    profile.setdefault("language_name", "藏语")
    profile.setdefault("script_note", "藏文横排文本，v12 剩余类别 JSON 结构树分类生成")
    profile.setdefault("html_lang", "bo")
    profile.setdefault("script_regex", r"[\u0f00-\u0fff]")
    profile.setdefault("min_script_ratio", 0.35)
    profile["font_family"] = '"Local Noto Serif Tibetan", "Local Jomolhari", "Noto Serif Tibetan", Kailasa, serif'
    return profile


def read_text_records(path: Path, profile: dict[str, Any], min_records: int) -> list[dict[str, str]]:
    script_re = re.compile(str(profile["script_regex"]))
    min_ratio = float(profile["min_script_ratio"])
    records: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        title = cleanse_text(str(row.get("title", "")))
        text = cleanse_text(str(row.get("text", "")))
        if len(text) < 40:
            continue
        if len(script_re.findall(text)) / max(len(text), 1) < min_ratio:
            continue
        records.append({"title": title, "text": text, "url": str(row.get("url", "")), "source_record_id": str(row.get("record_id", ""))})
    if len(records) < min_records:
        raise RuntimeError(f"not enough Tibetan records in {path}: {len(records)}")
    return records


def clip(text: str, min_len: int, max_len: int) -> str:
    text = cleanse_text(text)
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    for sep in [" ", "་"]:
        idx = cut.rfind(sep)
        if idx >= min_len:
            return cut[: idx + (1 if sep == "་" else 0)].strip()
    return cut.rstrip()


def select_span(text: str, rng: random.Random, min_len: int, max_len: int) -> str:
    text = cleanse_text(text)
    if len(text) <= max_len:
        return text
    parts = [p for p in re.split(r"(?<=་)", text) if p.strip()]
    if len(parts) > 8:
        start = rng.randint(0, max(0, len(parts) - 6))
        out = ""
        for part in parts[start:]:
            if len(out) + len(part) > max_len:
                break
            out += part
            if len(out) >= min_len:
                return cleanse_text(out)
    return clip(text, min_len, max_len)


def record_text(records: list[dict[str, str]], rng: random.Random, min_len: int, max_len: int) -> str:
    pool = [rec for rec in records if len(rec["text"]) >= min_len] or records
    return select_span(rng.choice(pool)["text"], rng, min_len, max_len)


def record_title(records: list[dict[str, str]], rng: random.Random, min_len: int = 8, max_len: int = 28) -> str:
    rec = rng.choice(records)
    title = cleanse_text(rec["title"])
    if min_len <= len(title) <= max_len:
        return title
    return select_span(title or rec["text"], rng, min_len, max_len)


class Builder:
    def __init__(self, document_id: str):
        self.document_id = document_id
        self.counter = 0

    def bid(self) -> str:
        self.counter += 1
        return f"{self.document_id}_b{self.counter:04d}"

    def block(self, label: str, text: str, cls: str, tag: str = "div") -> str:
        cleaned = cleanse_text(text)
        if not cleaned and label != "image":
            cleaned = fallback_text(label)
        return f'<{tag} class="{cls}" data-block-id="{self.bid()}" data-label="{label}">{esc(cleaned)}</{tag}>'


def base_css(page: dict[str, Any], theme: dict[str, str], font_family: str, base: int = 20) -> str:
    return tibetan_font_faces() + f"""
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: #d9dde2; }}
    body {{ font-family: {font_family}; color: {theme['ink']}; }}
    .page {{ width: {int(page['width'])}px; min-height: {int(page['height'])}px; margin: 0 auto; padding: 54px 62px 44px; background: {theme['paper']}; position: relative; overflow: hidden; }}
    [data-block-id] {{ overflow: visible; }}
    .doc-title {{ font-size: {base + 24}px; line-height: 1.48; font-weight: 900; }}
    .section-title {{ font-size: {base + 2}px; line-height: 1.42; font-weight: 900; color: {theme['accent']}; }}
    .meta {{ font-size: {base - 5}px; line-height: 1.45; color: {theme['muted']}; }}
    .para {{ font-size: {base - 1}px; line-height: 1.44; margin: 0 0 9px; }}
    .small {{ font-size: {base - 4}px; line-height: 1.34; }}
    .folio {{ position: absolute; left: 62px; right: 62px; bottom: 18px; border-top: 1px solid {theme['line']}; padding-top: 6px; text-align: center; color: {theme['muted']}; font-size: {base - 5}px; }}
    .image-box {{ min-height: 260px; background: repeating-linear-gradient(135deg, #dfd9ce, #dfd9ce 12px, #f5f0e8 12px, #f5f0e8 24px); border: 1.4px solid {theme['line']}; }}
    .caption {{ font-size: {base - 4}px; line-height: 1.28; color: {theme['muted']}; margin-top: 7px; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    td, th {{ border: 1px solid {theme['line']}; padding: 7px; font-size: {base - 5}px; line-height: 1.25; vertical-align: top; }}
    """


def wrap(doc: dict[str, Any], body: str, css: str, cls: str) -> str:
    return f"""<!doctype html>
<html lang="{esc(doc['html_lang'])}">
<head><meta charset="utf-8"><title>{esc(doc['title'])}</title><style>{css}</style></head>
<body><main class="page {cls}" data-template-id="{esc(doc['template_id'])}">{body}</main></body>
</html>
"""


def para_stack(b: Builder, records: list[dict[str, str]], rng: random.Random, count: int, min_len: int, max_len: int, cls: str = "para") -> str:
    return "".join(b.block("paragraph", record_text(records, rng, min_len, max_len), cls) for _ in range(count))


def kv(b: Builder, label: str, value: str, cls: str = "kv") -> str:
    return f'<section class="{cls}">{b.block("field_label", label, "field-label")}{b.block("field_value", value, "field-value")}</section>'


def small_table(b: Builder, records: list[dict[str, str]], rng: random.Random, rows: int, cols: int = 3) -> str:
    head = "<tr>" + "".join(b.block("table_header", f"H{i}", "", "th") for i in range(1, cols + 1)) + "</tr>"
    body = ""
    for _ in range(rows):
        body += "<tr>" + "".join(b.block("table_cell_text", record_text(records, rng, 16, 38), "", "td") for _ in range(cols)) + "</tr>"
    return f"<table>{head}{body}</table>"


def academic_renderer(b: Builder, tpl: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any], theme: dict[str, str]) -> str:
    v = int(tpl["variant"])
    page = tpl["page"]
    if v == 1:
        kws = "".join(b.block("metadata", record_title(records, rng, 5, 13), "keyword") for _ in range(6))
        footnotes = "".join(f'<section class="paper-footnote">{b.block("metadata", f"{i:02d}", "ref-no")}{b.block("note", record_text(records, rng, 28, 58), "small")}</section>' for i in range(1, 13))
        body = f"""<header class="paper-head">{b.block('document_title', record_title(records, rng, 12, 32), 'doc-title')}{b.block('metadata','Author 1 / Institute 2 / 2026','meta')}{b.block('document_subtitle', record_text(records, rng, 150, 240), 'abstract')}<div class="keywords">{kws}</div></header><article class="paper-cols">{para_stack(b, records, rng, 58, 64, 118)}</article><section class="paper-footnotes">{footnotes}</section>{b.block('page_number','1','folio')}"""
        extra = f""".paper-head{{text-align:center;border-bottom:3px double {theme['line']};padding-bottom:14px;margin-bottom:16px;}}.abstract{{text-align:left;background:{theme['soft']};border:1px solid {theme['line']};padding:11px;margin-top:10px;font-size:16px;line-height:1.32;}}.keywords{{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:9px;}}.keyword{{border:1px solid {theme['line']};padding:4px 8px;font-size:13px;}}.paper-cols{{columns:2;column-gap:24px;}}.paper-cols .para{{font-size:15px;line-height:1.25;margin-bottom:5px;}}.paper-footnotes{{position:absolute;left:62px;right:62px;bottom:68px;border-top:2px solid {theme['line']};padding-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:4px 18px;}}.paper-footnote{{display:grid;grid-template-columns:34px 1fr;gap:7px;}}.paper-footnote .small{{font-size:12px;line-height:1.14;}}"""
    elif v == 2:
        analysis_notes = "".join(f'<section class="analysis-note">{b.block("metadata", f"N{i}", "ref-no")}{b.block("note", record_text(records, rng, 30, 64), "small")}</section>' for i in range(1, 11))
        body = f"""{b.block('section_title', record_title(records, rng, 10, 22), 'section-title')}<section class="fig-paper"><main>{para_stack(b, records, rng, 28, 58, 108)}{b.block('section_title','དཔྱད་ཞིབ','section-title')}{para_stack(b, records, rng, 14, 48, 92)}</main><aside>{b.block('image','','image-box')}{b.block('caption',record_text(records,rng,55,96),'caption')}{small_table(b, records, rng, 10, 3)}</aside></section><section class="analysis-notes">{analysis_notes}</section>{b.block('page_number','2','folio')}"""
        extra = f""".fig-paper{{display:grid;grid-template-columns:1fr 380px;gap:24px;align-items:start;}}.fig-paper main{{columns:2;column-gap:20px;}}.fig-paper main .para{{font-size:15px;line-height:1.27;margin-bottom:5px;}}.fig-paper .image-box{{height:420px;margin-bottom:12px;}}.fig-paper td,.fig-paper th{{font-size:13px;padding:6px;}}.analysis-notes{{position:absolute;left:62px;right:62px;bottom:68px;border-top:2px solid {theme['line']};padding-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:6px 20px;}}.analysis-note{{display:grid;grid-template-columns:38px 1fr;gap:8px;}}.analysis-note .small{{font-size:12px;line-height:1.14;}}"""
    elif v == 3:
        metrics = "".join(f'<section class="metric">{b.block("metadata", f"M{i}", "metric-no")}{b.block("paragraph", record_text(records, rng, 28, 58), "small")}</section>' for i in range(1, 10))
        appendix = "".join(f'<section class="appendix-row">{b.block("metadata", f"A{i:02d}", "appendix-no")}{b.block("paragraph", record_text(records, rng, 38, 78), "small")}</section>' for i in range(1, 13))
        body = f"""{b.block('document_title','ཚོད་ལྟ་དང་དཔྱད་ཞིབ','doc-title')}<main class="experiment"><section>{para_stack(b, records, rng, 20, 54, 104)}{small_table(b, records, rng, 10, 4)}</section><aside>{metrics}</aside></main>{b.block('section_title','མཇུག་སྡོམ','section-title')}{para_stack(b, records, rng, 8, 48, 92)}<section class="appendix">{appendix}</section>"""
        extra = f""".experiment{{display:grid;grid-template-columns:1fr 300px;gap:22px;margin-top:14px;}}.experiment section .para{{font-size:15px;line-height:1.28;margin-bottom:5px;}}.metric{{border-left:5px solid {theme['accent']};padding:7px 0 7px 10px;border-bottom:1px dotted {theme['line']};}}.metric-no,.appendix-no{{font-weight:900;color:{theme['accent']};}}.appendix{{display:grid;grid-template-columns:1fr 1fr;gap:5px 18px;border-top:2px solid {theme['line']};margin-top:14px;padding-top:10px;}}.appendix-row{{display:grid;grid-template-columns:46px 1fr;gap:8px;border-bottom:1px dotted {theme['line']};padding:4px 0;}}"""
    elif v == 4:
        refs = "".join(f'<section class="ref-item">{b.block("metadata", f"[{i}]", "ref-no")}{b.block("paragraph", record_text(records, rng, 45, 88), "small")}</section>' for i in range(1, 57))
        body = f"""{b.block('document_title','དཔྱད་གཞི་ཡིག་ཆ','doc-title')}<main class="refs">{refs}</main>{b.block('page_number','18','folio')}"""
        extra = f""".refs{{columns:2;column-gap:28px;margin-top:16px;}}.ref-item{{break-inside:avoid;display:grid;grid-template-columns:42px 1fr;gap:8px;border-bottom:1px dotted {theme['line']};padding:4px 0;}}.ref-no{{font-size:14px;color:{theme['accent']};font-weight:900;}}.ref-item .small{{font-size:13px;line-height:1.2;}}"""
    elif v == 5:
        boxes = "".join(f'<section class="review-box">{b.block("section_title", record_title(records,rng,7,16), "section-title")}{b.block("paragraph", record_text(records,rng,46,84), "small")}</section>' for _ in range(12))
        review_notes = "".join(f'<section class="review-note">{b.block("metadata", f"R{i}", "ref-no")}{b.block("note", record_text(records, rng, 30, 62), "small")}</section>' for i in range(1, 11))
        body = f"""{b.block('document_title',record_title(records,rng,12,28),'doc-title')}<main class="review-paper"><section>{para_stack(b, records, rng, 42, 50, 96)}</section><aside>{boxes}</aside></main><section class="review-notes">{review_notes}</section>{b.block('page_number','9','folio')}"""
        extra = f""".review-paper{{display:grid;grid-template-columns:1fr 330px;gap:22px;}}.review-paper section{{columns:2;column-gap:20px;}}.review-paper section .para{{font-size:15px;line-height:1.25;margin-bottom:5px;}}.review-box{{background:{theme['soft']};border:1px solid {theme['line']};padding:8px;margin-bottom:7px;}}.review-box .section-title{{font-size:15px;}}.review-box .small{{font-size:12.5px;line-height:1.18;}}.review-notes{{position:absolute;left:62px;right:62px;bottom:68px;border-top:2px solid {theme['line']};padding-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:5px 20px;}}.review-note{{display:grid;grid-template-columns:38px 1fr;gap:8px;}}.review-note .small{{font-size:12px;line-height:1.14;}}"""
    else:
        comments = "".join(f'<section class="comment">{b.block("metadata", f"C{i}", "comment-no")}{b.block("note", record_text(records,rng,32,66), "small")}</section>' for i in range(1, 19))
        body = f"""<main class="reviewed"><article>{b.block('section_title',record_title(records,rng,8,20),'section-title')}{para_stack(b, records, rng, 42, 50, 98)}</article><aside>{b.block('section_title','མཆན','section-title')}{comments}</aside></main>{b.block('page_number','12','folio')}"""
        extra = f""".reviewed{{display:grid;grid-template-columns:1fr 285px;gap:24px;}}.reviewed article{{columns:2;column-gap:22px;}}.reviewed article .para{{font-size:15px;line-height:1.25;margin-bottom:5px;}}.comment{{border-top:2px solid {theme['accent']};padding-top:5px;margin-bottom:6px;}}.comment-no{{font-weight:900;color:{theme['accent']};}}.comment .small{{font-size:12.5px;line-height:1.18;}}"""
    return wrap(doc, body, base_css(page, theme, doc["font_family"], 20) + extra, "academic-page")


def historical_renderer(b: Builder, tpl: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any], theme: dict[str, str]) -> str:
    v = int(tpl["variant"])
    page = tpl["page"]
    old = {"paper": "#f7efd9", "soft": "#efe2c3", **theme}
    if v == 1:
        colophon = "".join(f'<section class="colophon-row">{b.block("metadata", f"{i}", "note-no")}{b.block("note", record_text(records,rng,30,62), "small")}</section>' for i in range(1, 11))
        body = f"""<section class="classic-frame"><header>{b.block('metadata','དེབ་ཐེར གཅིག','meta')}{b.block('metadata','folio 07','meta')}</header><main class="classic-cols">{para_stack(b, records, rng, 54, 56, 104)}</main><footer class="colophon">{colophon}</footer></section>"""
        extra = """.page{background:#f7efd9}.classic-frame{border:8px double #7a6040;min-height:1600px;padding:28px}.classic-frame header{display:flex;justify-content:space-between;border-bottom:2px solid #7a6040;padding-bottom:8px}.classic-cols{columns:2;column-gap:30px;column-rule:2px solid #8a7352;margin-top:18px}.classic-cols .para{font-size:15.5px;line-height:1.26;margin-bottom:5px}.colophon{display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;border-top:2px solid #8a7352;margin-top:18px;padding-top:10px}.colophon-row{display:grid;grid-template-columns:30px 1fr;gap:7px}.colophon-row .small{font-size:12.5px;line-height:1.16}"""
    elif v == 2:
        notes = "".join(f'<section class="sutra-note">{b.block("metadata", f"{i:02d}", "meta")}{b.block("note", record_text(records,rng,24,50), "small")}</section>' for i in range(1, 19))
        body = f"""<section class="sutra">{b.block('document_title','གླེགས་བམ','doc-title')}<main>{para_stack(b, records, rng, 42, 54, 100)}</main><aside>{notes}</aside></section>"""
        extra = """.page{background:#f8eed5}.sutra{border:5px solid #866e4b;min-height:1600px;padding:32px 54px}.sutra .doc-title{text-align:center;font-size:40px}.sutra main{columns:2;column-gap:26px}.sutra main .para{font-size:15.5px;line-height:1.26;margin-bottom:5px}.sutra aside{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px 10px;margin-top:18px}.sutra-note{border-top:1px solid #927b5a;padding-top:5px}.sutra-note .small{font-size:12.5px;line-height:1.16}"""
    elif v == 3:
        sigs = "".join(kv(b, record_title(records,rng,5,12), record_text(records,rng,24,50), "archive-kv") for _ in range(12))
        body = f"""<section class="archive"><header>{b.block('metadata','ARCHIVE 26-07','meta')}{b.block('document_title',record_title(records,rng,10,24),'doc-title')}{b.block('metadata','1928 / copy','meta')}</header>{para_stack(b, records, rng, 20, 66, 128)}<section class="signatures">{sigs}</section></section>"""
        extra = f""".archive{{border-left:14px solid #826b4f;background:#fbf4e2;min-height:1420px;padding:34px;}}.archive header{{border-bottom:2px solid #826b4f;padding-bottom:12px;margin-bottom:18px;}}.archive .para{{font-size:17px;line-height:1.32;margin-bottom:8px;}}.signatures{{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:22px;}}.archive-kv{{border:1px solid #b7a487;padding:8px;background:#fffaf0;}}"""
    elif v == 4:
        clips = "".join(f'<section class="clip c{i}">{b.block("section_title", record_title(records,rng,7,18), "section-title")}{b.block("paragraph", record_text(records,rng,62,118), "small")}{b.block("metadata","source", "meta")}</section>' for i in range(1, 9))
        body = f"""<main class="clippings">{b.block('document_title','ལོ་རྒྱུས་ཡིག་ཆ','doc-title')}<section class="main-clip">{b.block('section_title',record_title(records,rng,8,22),'section-title')}{para_stack(b, records, rng, 12, 58, 108)}</section>{clips}</main>"""
        extra = """.page{background:#eee4cc}.clippings{position:relative;min-height:1320px}.main-clip,.clip{background:#fff8e8;border:1.5px solid #a38b65;box-shadow:7px 8px 0 rgba(70,50,20,.08);padding:14px}.main-clip{width:60%;}.clip{position:relative;margin:12px;display:inline-block;width:43%;vertical-align:top}.clip .small,.main-clip .para{font-size:15px;line-height:1.26;margin-bottom:5px}"""
    elif v == 5:
        notes = "".join(f'<section class="note-row">{b.block("metadata", f"{i}", "note-no")}{b.block("note", record_text(records,rng,36,72), "small")}</section>' for i in range(1, 34))
        body = f"""<section class="collation"><header>{b.block('document_title','དཔྱད་མཆན','doc-title')}{b.block('metadata','volume 3','meta')}</header><main>{para_stack(b, records, rng, 24, 54, 100)}</main><section class="notes">{notes}</section></section>"""
        extra = """.page{background:#f7efd9}.collation{border:5px double #7f6949;padding:28px;min-height:1600px}.collation header{display:flex;justify-content:space-between;border-bottom:2px solid #7f6949}.collation main{columns:2;column-gap:26px;margin-top:16px}.collation main .para{font-size:15.5px;line-height:1.26;margin-bottom:5px}.notes{display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;border-top:2px solid #7f6949;margin-top:18px;padding-top:10px}.note-row{display:grid;grid-template-columns:34px 1fr;gap:8px;border-bottom:1px dotted #a38b65;padding:3px 0}.note-row .small{font-size:12.5px;line-height:1.14}"""
    else:
        catalog = "".join(kv(b, record_title(records,rng,5,12), record_text(records,rng,20,46), "archive-kv") for _ in range(8))
        body = f"""<main class="rubbing">{b.block('image','','image-box')}<section>{b.block('document_title','རྡོ་རིང་ཡི་གེ','doc-title')}{b.block('section_title','འགྲེལ་བ','section-title')}{para_stack(b, records, rng, 16, 48, 92)}<div class="catalog">{catalog}</div>{b.block('metadata','catalog / archive / 2026','meta')}</section></main>"""
        extra = """.page{background:#f4ead5}.rubbing{display:grid;grid-template-columns:470px 1fr;gap:28px;align-items:start}.rubbing .image-box{height:1120px;background:repeating-linear-gradient(90deg,#3a362d,#3a362d 9px,#4a4438 9px,#4a4438 18px);border:10px solid #78654b}.rubbing section .para{font-size:16px;line-height:1.28;margin-bottom:6px}.catalog{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:16px 0}.archive-kv{border:1px solid #b7a487;padding:7px;background:#fffaf0}"""
    return wrap(doc, body, base_css(page, old, doc["font_family"], 20) + extra, "historical-page")


def notice_renderer(b: Builder, tpl: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any], theme: dict[str, str]) -> str:
    v = int(tpl["variant"])
    page = tpl["page"]
    if v == 1:
        body = f"""<header class="notice-head">{b.block('metadata','ཡིག་ཨང 2026-07','meta')}{b.block('document_title',doc['title'],'doc-title')}</header><main class="notice-body">{para_stack(b, records, rng, 18, 72, 132)}</main><section class="notice-appendix">{b.block('section_title','གལ་ཆེའི་དོན་ཚན','section-title')}{para_stack(b, records, rng, 6, 44, 82, 'small')}</section><footer>{b.block('metadata','ལས་ཁུངས','meta')}{b.block('metadata','2026-07-01','meta')}</footer>"""
        extra = f""".notice-head{{border-top:8px solid {theme['accent']};border-bottom:2px solid {theme['line']};text-align:center;padding:16px 0;}}.notice-body{{margin-top:24px;}}.notice-body .para{{font-size:20px;line-height:1.42;margin-bottom:10px;}}.notice-appendix{{border-top:2px solid {theme['line']};margin-top:18px;padding-top:12px;columns:2;column-gap:22px;}}.notice-appendix .small{{font-size:15px;line-height:1.25;margin-bottom:5px;}}footer{{position:absolute;right:70px;bottom:70px;text-align:right;}}"""
    elif v == 2:
        items = "".join(f'<section class="notice-item">{b.block("metadata", f"{i:02d}", "item-no")}{b.block("paragraph", record_text(records,rng,55,112), "small")}</section>' for i in range(1, 11))
        body = f"""<section class="bulletin">{b.block('document_title','བརྡ་ཁྱབ','doc-title')}<main>{items}</main><aside>{kv(b,'time','2026-07')}{kv(b,'place',record_title(records,rng,8,18))}{kv(b,'contact',record_title(records,rng,8,18))}</aside></section>"""
        extra = f""".bulletin{{border:10px solid {theme['accent']};padding:34px;min-height:1220px;}}.bulletin .doc-title{{text-align:center;font-size:62px;}}.notice-item{{display:grid;grid-template-columns:58px 1fr;gap:12px;border-bottom:1px solid {theme['line']};padding:10px 0;}}.item-no{{font-size:26px;font-weight:900;color:{theme['accent']};}}.bulletin aside{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:24px;}}.kv{{background:{theme['soft']};padding:12px;border:1px solid {theme['line']};}}"""
    elif v == 3:
        agenda = "".join(f'<section class="agenda">{b.block("metadata", f"{8+i}:00", "time")}{b.block("paragraph", record_text(records,rng,40,82), "small")}</section>' for i in range(1, 13))
        body = f"""<header class="meeting-head">{b.block('metadata','MEETING','meta')}{b.block('document_title',record_title(records,rng,10,24),'doc-title')}</header><main class="meeting"><section>{kv(b,'དུས་ཚོད','2026-07')}{kv(b,'ས་གནས',record_title(records,rng,8,18))}{kv(b,'ཞུགས་མཁན',record_text(records,rng,30,70))}{para_stack(b, records, rng, 5, 42, 78, 'small')}</section><aside>{agenda}</aside></main>{b.block('note',record_text(records,rng,110,180),'para')}"""
        extra = f""".meeting-head{{border-left:14px solid {theme['accent']};padding-left:18px;border-bottom:2px solid {theme['line']};}}.meeting{{display:grid;grid-template-columns:360px 1fr;gap:28px;margin-top:24px;}}.kv{{border:1px solid {theme['line']};padding:12px;margin-bottom:12px;background:{theme['soft']};}}.agenda{{display:grid;grid-template-columns:90px 1fr;gap:10px;border-bottom:1px dotted {theme['line']};padding:10px 0;}}.time{{font-weight:900;color:{theme['accent']};}}"""
    elif v == 4:
        attachments = "".join(f'<section class="attachment">{b.block("metadata", f"{i}", "item-no")}{b.block("paragraph", record_text(records,rng,34,72), "small")}</section>' for i in range(1, 23))
        sign_boxes = "".join(kv(b, record_title(records, rng, 5, 12), record_text(records, rng, 18, 42), "notice-sign") for _ in range(6))
        body = f"""{b.block('document_title','ཟུར་སྦྱར་བརྡ་ཐོ','doc-title')}<main class="attach-notice">{para_stack(b, records, rng, 12, 66, 124)}<section class="attachments">{b.block('section_title','ཟུར་སྦྱར','section-title')}{attachments}</section><section class="notice-signs">{sign_boxes}</section></main>"""
        extra = f""".attach-notice .para{{font-size:18px;line-height:1.34;margin-bottom:9px;}}.attachments{{border-top:3px solid {theme['accent']};margin-top:20px;padding-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;}}.attachment{{display:grid;grid-template-columns:38px 1fr;gap:8px;border-bottom:1px dotted {theme['line']};padding:4px 0;}}.attachment .small{{font-size:13px;line-height:1.18;}}.notice-signs{{position:absolute;left:62px;right:62px;bottom:66px;border-top:1px solid {theme['line']};padding-top:10px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;}}.notice-sign{{border:1px solid {theme['line']};padding:7px;background:{theme['soft']};}}"""
    elif v == 5:
        info = "".join(kv(b, record_title(records,rng,5,12), record_text(records,rng,22,48), "info-kv") for _ in range(12))
        body = f"""<section class="public-notice">{b.block('document_title','སྤྱི་བསྒྲགས','doc-title')}<main>{para_stack(b, records, rng, 16, 66, 124)}</main><aside>{info}</aside></section>"""
        extra = f""".public-notice{{border:3px solid {theme['line']};padding:34px;min-height:1320px;}}.public-notice .doc-title{{text-align:center;border-bottom:6px double {theme['accent']};padding-bottom:16px;}}.public-notice{{display:grid;grid-template-columns:1fr 300px;gap:24px;}}.public-notice main .para{{font-size:18px;line-height:1.34;margin-bottom:9px;}}.info-kv{{background:{theme['soft']};border-left:6px solid {theme['accent']};padding:8px;margin-bottom:8px;}}"""
    else:
        nodes = "".join(f'<section class="node">{b.block("metadata", f"07-{i:02d}", "node-date")}{b.block("paragraph", record_text(records,rng,44,84), "small")}</section>' for i in range(1, 13))
        body = f"""{b.block('document_title','དུས་རིམ་བརྡ་ཐོ','doc-title')}<main class="timeline">{nodes}</main><section class="remarks">{b.block('section_title','མཆན','section-title')}{para_stack(b, records, rng, 8, 38, 74, 'small')}</section>"""
        extra = f""".timeline{{border-left:8px solid {theme['accent']};margin:28px 0 0 80px;}}.node{{display:grid;grid-template-columns:120px 1fr;gap:16px;padding:10px 0 10px 24px;border-bottom:1px solid {theme['line']};}}.node-date{{font-weight:900;color:{theme['accent']};}}.remarks{{background:{theme['soft']};border:1px solid {theme['line']};padding:16px;margin-top:20px;columns:2;column-gap:18px;}}"""
    return wrap(doc, body, base_css(page, theme, doc["font_family"], 20) + extra, "notice-page")


def form_renderer(b: Builder, tpl: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any], theme: dict[str, str]) -> str:
    v = int(tpl["variant"])
    page = tpl["page"]
    labels = ["མིང", "ཨང", "ཁ་བྱང", "འབྲེལ་བ", "དུས་ཚོད", "ས་གནས", "རིགས", "གནས་ཚུལ"]
    if v == 1:
        fields = "".join(kv(b, rng.choice(labels), record_text(records,rng,18,44), "field") for _ in range(28))
        body = f"""{b.block('document_title',doc['title'],'doc-title')}<main class="form-grid">{fields}</main><section class="long-area">{b.block('section_title','གསལ་བཤད','section-title')}{para_stack(b, records, rng, 4, 50, 95, 'small')}</section><footer>{kv(b,'signature','________')}{kv(b,'date','2026-07')}</footer>"""
        extra = f""".form-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:18px;}}.field{{border:1px solid {theme['line']};padding:9px;background:white;}}.field-label{{font-size:14px;color:{theme['muted']};}}.field-value{{font-size:17px;line-height:1.28;}}.long-area{{border:1.5px solid {theme['line']};background:{theme['soft']};padding:14px;margin-top:18px;}}footer{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:20px;}}"""
    elif v == 2:
        fields = "".join(kv(b, rng.choice(labels), record_text(records,rng,18,48), "field") for _ in range(16))
        approvals = "".join(f'<section class="approval">{b.block("section_title", record_title(records,rng,6,14), "section-title")}{b.block("paragraph", record_text(records,rng,45,86), "small")}{kv(b,"sign","________")}</section>' for _ in range(6))
        body = f"""{b.block('document_title','ཞུ་ཡིག་ཞིབ་བཤེར','doc-title')}<section class="field-grid">{fields}</section><section class="request">{para_stack(b, records, rng, 4, 58, 110)}</section><section class="approvals">{approvals}</section>"""
        extra = f""".field-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:16px;}}.field{{border:1px solid {theme['line']};padding:8px;}}.request{{border:1.5px solid {theme['line']};padding:14px;margin:16px 0;background:{theme['soft']};}}.approvals{{display:grid;grid-template-columns:1fr 1fr;gap:10px;}}.approval{{border:1px solid {theme['line']};padding:10px;min-height:150px;}}"""
    elif v == 3:
        rows = "".join(f'<section class="material">{b.block("metadata", f"{i:02d}", "item-no")}{b.block("paragraph", record_text(records,rng,32,66), "small")}{b.block("field_value", rng.choice(["OK","Review","Need"]), "status")}{b.block("note", record_text(records,rng,16,34), "small")}</section>' for i in range(1, 22))
        body = f"""{b.block('document_title','ཡིག་ཆ་ཞིབ་བཤེར','doc-title')}<main class="materials">{rows}</main>{b.block('metadata','handler / date / office','meta footer-meta')}"""
        extra = f""".materials{{display:grid;grid-template-columns:1fr;gap:6px;margin-top:18px;}}.material{{display:grid;grid-template-columns:54px 1fr 90px 190px;gap:10px;border-bottom:1px solid {theme['line']};padding:7px 0;}}.status{{font-weight:900;color:{theme['accent']};}}.footer-meta{{position:absolute;bottom:32px;right:62px;}}"""
    elif v == 4:
        qs = "".join(f'<section class="survey-q">{b.block("question", f"{i}. " + record_text(records,rng,34,70), "question")}{b.block("option", "A  " + record_title(records,rng,5,12), "option")}{b.block("option", "B  " + record_title(records,rng,5,12), "option")}{b.block("answer_area", " ", "answer-line")}</section>' for i in range(1, 19))
        body = f"""{b.block('document_title','དྲི་ཤོག','doc-title')}{b.block('document_subtitle',record_text(records,rng,70,125),'para intro')}<main class="survey">{qs}</main>"""
        extra = f""".intro{{background:{theme['soft']};padding:12px;border:1px solid {theme['line']};}}.survey{{display:grid;grid-template-columns:1fr 1fr;gap:10px 18px;margin-top:18px;}}.survey-q{{border-bottom:1px solid {theme['line']};padding-bottom:7px;}}.question{{font-size:15px;line-height:1.25;}}.option{{display:inline-block;margin-right:12px;font-size:13px;}}.answer-line{{height:26px;border-bottom:1px dashed {theme['line']};}}"""
    elif v == 5:
        fields = "".join(kv(b, rng.choice(labels), record_text(records,rng,16,40), "card-field") for _ in range(14))
        body = f"""<main class="archive-card"><aside>{b.block('metadata','ID 2026-07','meta')}{b.block('image','','photo')}</aside><section>{b.block('document_title','ཡིག་ཚགས་བྱང་བུ','doc-title')}<div class="card-grid">{fields}</div>{b.block('paragraph',record_text(records,rng,80,140),'para')}</section><footer>{kv(b,'review','OK')}{kv(b,'date','2026')}</footer></main>"""
        extra = f""".archive-card{{display:grid;grid-template-columns:260px 1fr;grid-template-rows:1fr auto;gap:18px;border:3px solid {theme['line']};padding:24px;min-height:820px;}}.photo{{height:260px;background:repeating-linear-gradient(135deg,#ded8cc,#ded8cc 12px,#f5efe3 12px,#f5efe3 24px);border:1px solid {theme['line']};}}.card-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}.card-field{{border:1px solid {theme['line']};padding:8px;}}footer{{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr;gap:12px;}}"""
    else:
        left = "".join(kv(b, rng.choice(labels), record_text(records,rng,16,42), "field") for _ in range(16))
        right = "".join(kv(b, rng.choice(labels), record_text(records,rng,16,42), "field") for _ in range(16))
        body = f"""{b.block('document_title','ཐོ་འགོད་རེའུ་མིག','doc-title')}<main class="signup"><section>{left}</section><section>{right}</section></main><section class="declaration">{b.block('section_title','གསལ་བསྒྲགས','section-title')}{para_stack(b, records, rng, 4, 48, 90, 'small')}</section><footer>{kv(b,'sign','________')}{kv(b,'date','2026')}</footer>"""
        extra = f""".signup{{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:18px;}}.field{{border-bottom:1px solid {theme['line']};padding:7px 0;display:grid;grid-template-columns:110px 1fr;gap:8px;}}.field-label{{font-size:14px;color:{theme['muted']};}}.field-value{{font-size:16px;line-height:1.25;}}.declaration{{margin-top:18px;background:{theme['soft']};padding:14px;border:1px solid {theme['line']};}}footer{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px;}}"""
    return wrap(doc, body, base_css(page, theme, doc["font_family"], 20) + extra, "form-page")


def handwritten_renderer(b: Builder, tpl: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any], theme: dict[str, str]) -> str:
    v = int(tpl["variant"])
    page = tpl["page"]
    hand_family = '"Local Jomolhari", "Local Noto Serif Tibetan", serif'
    if v == 1:
        lines = "".join(b.block("paragraph", record_text(records,rng,30,70), "hand-line") for _ in range(34))
        body = f"""<section class="lined">{b.block('document_title',record_title(records,rng,8,22),'doc-title')}{b.block('metadata','2026-07','meta')}{lines}</section>"""
        extra = f""".page{{font-family:{hand_family};background:#fffdf3;}}.lined{{min-height:1580px;background:repeating-linear-gradient(#fffdf3,#fffdf3 42px,#d9e4ec 43px);border-left:5px solid #d88;padding:22px 36px;}}.lined .doc-title{{font-size:40px;}}.hand-line{{font-size:18px;line-height:42px;margin:0;transform:rotate(-.08deg);}}"""
    elif v == 2:
        body = f"""<section class="letter">{b.block('metadata',record_title(records,rng,6,14),'salutation')}{para_stack(b, records, rng, 18, 58, 112, 'hand-para')}<section class="postscript">{b.block('section_title','P.S.','section-title')}{para_stack(b, records, rng, 4, 36, 72, 'hand-small')}</section><footer>{b.block('metadata',record_title(records,rng,5,12),'meta')}{b.block('metadata','2026-07','meta')}</footer></section>"""
        extra = f""".page{{font-family:{hand_family};background:#fffaf0;}}.letter{{min-height:1320px;border:1px solid {theme['line']};padding:46px 62px;box-shadow:12px 14px 0 rgba(80,70,50,.08);}}.salutation{{font-size:27px;margin-bottom:18px;}}.hand-para{{font-size:20px;line-height:1.46;margin-bottom:11px;}}.postscript{{border-top:1px dashed {theme['line']};margin-top:18px;padding-top:12px;}}.hand-small{{font-size:18px;line-height:1.32;}}.letter footer{{text-align:right;margin-top:22px;}}"""
    elif v == 3:
        notes = "".join(f'<section class="note-line">{b.block("metadata", f"{i:02d}", "note-no")}{b.block("paragraph", record_text(records,rng,34,72), "hand-small")}</section>' for i in range(1, 45))
        bottom_notes = "".join(f'<section class="bottom-note">{b.block("metadata", f"*{i}", "note-no")}{b.block("note", record_text(records,rng,24,52), "hand-small")}</section>' for i in range(1, 9))
        body = f"""{b.block('document_title','ཟིན་བྲིས','doc-title')}<main class="class-notes">{notes}</main><section class="bottom-notes">{bottom_notes}</section>"""
        extra = f""".page{{font-family:{hand_family};background:#fffdf5;}}.class-notes{{display:grid;grid-template-columns:1fr 1fr;gap:5px 26px;margin-top:16px;}}.note-line{{display:grid;grid-template-columns:42px 1fr;gap:8px;border-bottom:1px solid #d6e1e8;padding:5px 0;}}.note-no{{font-weight:900;color:{theme['accent']};}}.hand-small{{font-size:15.5px;line-height:1.16;}}.bottom-notes{{position:absolute;left:62px;right:62px;bottom:58px;border-top:1px dashed #c7d3dc;padding-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:5px 18px;}}.bottom-note{{display:grid;grid-template-columns:34px 1fr;gap:7px;}}"""
    elif v == 4:
        notes = "".join(f'<section class="sticky s{i}">{b.block("paragraph", record_text(records,rng,34,72), "hand-small")}{b.block("metadata","07-" + str(i), "meta")}</section>' for i in range(1, 11))
        body = f"""<main class="board">{notes}</main>"""
        extra = f""".page{{font-family:{hand_family};background:#d9d2c4;padding:62px;}}.board{{min-height:1180px;position:relative;}}.sticky{{display:inline-block;width:306px;min-height:210px;background:#fff6ad;border:1px solid #d2c66c;margin:14px;padding:20px;vertical-align:top;box-shadow:8px 10px 0 rgba(80,70,50,.12);transform:rotate(-.4deg);}}.s2,.s5,.s8{{background:#dff1ff;transform:rotate(.35deg);}}.s3,.s6,.s9{{background:#f6dfef;transform:rotate(-.2deg);}}.hand-small{{font-size:18px;line-height:1.3;}}"""
    elif v == 5:
        body = f"""<section class="diary">{b.block('metadata','2026-07 / weather','meta')}{b.block('document_title',record_title(records,rng,8,22),'doc-title')}{para_stack(b, records, rng, 28, 52, 100, 'hand-para')}</section>"""
        extra = f""".page{{font-family:{hand_family};background:#fffaf0;}}.diary{{min-height:1580px;border-left:28px solid #e7d7bd;padding:36px 54px;background:repeating-linear-gradient(#fffaf0,#fffaf0 40px,#efe4d2 41px);}}.diary .doc-title{{font-size:40px;}}.hand-para{{font-size:19px;line-height:1.38;margin-bottom:8px;}}"""
    else:
        todos = "".join(f'<section class="todo">{b.block("metadata", "□", "box")}{b.block("paragraph", record_text(records,rng,28,64), "hand-small")}</section>' for _ in range(20))
        body = f"""<section class="memo">{b.block('document_title','MEMO','doc-title')}{todos}<footer>{b.block('metadata','signature / 2026','meta')}</footer></section>"""
        extra = f""".page{{font-family:{hand_family};background:#f5f0df;}}.memo{{border:3px solid {theme['accent']};background:#fffde9;padding:36px;min-height:1260px;}}.memo .doc-title{{font-size:54px;border-bottom:4px solid {theme['accent']};}}.todo{{display:grid;grid-template-columns:44px 1fr;gap:10px;border-bottom:1px solid {theme['line']};padding:9px 0;}}.box{{font-size:24px;color:{theme['accent']};}}.hand-small{{font-size:18px;line-height:1.26;}}"""
    return wrap(doc, body, base_css(page, theme, doc["font_family"], 20) + extra, "handwritten-page")


RENDERERS: dict[str, Callable[..., str]] = {
    "academic_paper": academic_renderer,
    "historical_classic": historical_renderer,
    "notice_announcement": notice_renderer,
    "complex_form": form_renderer,
    "handwritten_letter": handwritten_renderer,
}


from tibetan_text_utils import (  # noqa: E402
    cleanse_text,
    clip,
    fallback_text,
    load_language_profile,
    read_text_records,
    record_text,
    record_title,
    select_span,
)


def safe_name(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def validate_spec(spec: dict[str, Any]) -> None:
    if spec.get("schema_version") != "category_layout_templates.v1":
        raise RuntimeError("unsupported template schema")
    categories = spec.get("categories")
    if not isinstance(categories, list) or len(categories) != 5:
        raise RuntimeError("remaining pages spec must contain exactly 5 categories")
    for cat in categories:
        if cat.get("category_id") not in RENDERERS:
            raise RuntimeError(f"unsupported category: {cat.get('category_id')}")
        variants = [tpl.get("variant") for tpl in cat.get("templates", [])]
        if variants != [1, 2, 3, 4, 5, 6]:
            raise RuntimeError(f"{cat.get('category_id')} variants invalid: {variants}")


def reset_category_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    for sub in ["html", "images", "labels", "metadata", "reports", "reports/overlays"]:
        (path / sub).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-jsonl", required=True)
    parser.add_argument("--templates-json", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--language-profile")
    parser.add_argument("--start-index", type=int, default=8)
    parser.add_argument("--min-records", type=int, default=30)
    parser.add_argument("--seed", type=int, default=2026070112)
    parser.add_argument("--version-name")
    args = parser.parse_args()

    profile = load_language_profile(Path(args.language_profile) if args.language_profile else None)
    records = read_text_records(Path(args.text_jsonl), profile, args.min_records)
    spec = json.loads(Path(args.templates_json).read_text(encoding="utf-8"))
    validate_spec(spec)

    rng = random.Random(args.seed)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    version_name = args.version_name or output_root.name
    written = []

    for offset, cat in enumerate(spec["categories"]):
        category_id = cat["category_id"]
        category_cn = cat["category_cn"]
        folder = output_root / f"{args.start_index + offset:02d}_{safe_name(category_cn)}"
        reset_category_dir(folder)
        renderer = RENDERERS[category_id]
        html_manifest = []
        for tpl in cat["templates"]:
            variant = int(tpl["variant"])
            document_id = f"{args.start_index + offset:02d}_{category_id}_json_{variant:02d}"
            b = Builder(document_id)
            theme = THEMES[(offset + variant - 1) % len(THEMES)]
            doc = {
                "document_id": document_id,
                "title": cat["title"],
                "html_lang": profile["html_lang"],
                "font_family": profile["font_family"],
                "template_id": tpl["template_id"],
            }
            html_text = renderer(b, tpl, records, rng, doc, theme)
            (folder / "html" / f"{document_id}.html").write_text(html_text, encoding="utf-8")
            page = tpl["page"]
            html_manifest.append(
                {
                    "document_id": document_id,
                    "title": cat["title"],
                    "category": category_id,
                    "category_cn": category_cn,
                    "variant": variant,
                    "layout_name": tpl["template_id"],
                    "layout_family": tpl["layout_family"],
                    "template_type": category_id,
                    "template_source": str(Path(args.templates_json).resolve()),
                    "generator": "remaining_pages_json_renderer_bo_v13",
                    "doc_no": f"BO-{version_name.upper()}-{args.start_index + offset:02d}-{variant:02d}",
                    "date": now_local()[:10],
                    "page_width": int(page["width"]),
                    "page_height": int(page["height"]),
                    "preserve_full_page": bool(tpl.get("preserve_full_page", False)),
                    "rows": None,
                    "columns": None,
                    "created_at": now_local(),
                    "source_records": [],
                    "content_density": tpl.get("content_density"),
                }
            )
        write_json(folder / "metadata" / "html_manifest.json", html_manifest)
        write_json(folder / "metadata" / "category_plan.json", [{"category": category_id, "category_cn": category_cn, "samples": 6}])
        write_json(folder / "metadata" / "remaining_pages_template_spec.json", {"category": cat, "source_schema": spec["schema_version"]})
        (folder / "README.md").write_text(
            f"# {args.start_index + offset:02d} {category_cn}\n\n本目录属于藏语 `{version_name}`，由剩余类别 JSON 结构树生成，共 6 张。\n\n- `html/`\n- `images/`\n- `labels/`\n- `metadata/`\n- `reports/`\n",
            encoding="utf-8",
        )
        written.append(str(folder))

    print(json.dumps({"generated_category_dirs": written}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
