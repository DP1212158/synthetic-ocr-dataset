#!/usr/bin/env python3
"""Generate spec-aligned Tibetan synthetic OCR layout samples.

This is a new-generation Tibetan-only generator. It keeps the existing HTML ->
image -> label rendering chain, but uses categories closer to the newly
received OCR evaluation guidance and avoids overusing table-like layouts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import random
import re
from pathlib import Path
from typing import Callable, Dict, List, Tuple


CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
TIBETAN_RE = re.compile(r"[\u0f00-\u0fff]")
TIBETAN_DECORATIVE_MARK_RE = re.compile(r"[\u0f04-\u0f0a\u0f0c\u0f0e-\u0f14\u0f3a-\u0f3d]")
TIBETAN_SHAD_RE = re.compile(r"\s*།+\s*")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIBETAN_FONT_DIR = PROJECT_ROOT / "assets" / "fonts" / "tibetan"


CATEGORIES = [
    ("book_page", "书籍页"),
    ("textbook_page", "教科书页"),
    ("newspaper_page", "报纸页"),
    ("magazine_journal", "杂志期刊页"),
    ("academic_paper", "学术文献页"),
    ("historical_classic", "历史文档_古籍"),
    ("notice_announcement", "公告通知"),
    ("exam_paper", "考试卷"),
    ("complex_form", "复杂表单登记页"),
    ("certificate_proof", "证书证明"),
    ("sign_poster_scene", "标牌海报场景"),
    ("handwritten_letter", "手写笔记信件"),
]


TITLE_BY_CATEGORY = {
    "book_page": "དཔེ་དེབ་ཤོག་ངོས",
    "textbook_page": "སློབ་དེབ་ཤོག་ངོས",
    "newspaper_page": "གསར་འགྱུར་ཤོག་ངོས",
    "magazine_journal": "དུས་དེབ་དང་དེབ་ཕྲེང",
    "academic_paper": "རིག་གཞུང་རྩོམ་ཡིག",
    "historical_classic": "གནའ་དཔེ་དང་ཡིག་ཆ",
    "notice_announcement": "བརྡ་ཐོ་དང་བསྒྲགས་གཏམ",
    "exam_paper": "རྒྱུགས་ཤོག",
    "complex_form": "ཐོ་འགོད་རེའུ་མིག",
    "certificate_proof": "ལག་ཁྱེར་དང་དཔང་ཡིག",
    "sign_poster_scene": "བྱང་བུ་དང་འགྲེམས་བསྒྲགས",
    "handwritten_letter": "ལག་བྲིས་ཟིན་ཐོ",
}


THEMES = [
    {"ink": "#202326", "muted": "#656b72", "line": "#b8bec6", "head": "#e7ebf0", "accent": "#2c5f78", "paper": "#fffefa", "soft": "#f3f6f8"},
    {"ink": "#2b2420", "muted": "#75665c", "line": "#c9bbae", "head": "#efe7dc", "accent": "#8a4e2d", "paper": "#fffdf5", "soft": "#f8f0e5"},
    {"ink": "#1d2a21", "muted": "#66766b", "line": "#b3c4b8", "head": "#e7f0ea", "accent": "#366b51", "paper": "#fcfff9", "soft": "#eef7f0"},
    {"ink": "#27222b", "muted": "#6d6574", "line": "#bbb3c8", "head": "#ece7f2", "accent": "#5e5b90", "paper": "#fdfcff", "soft": "#f2f0f8"},
    {"ink": "#232323", "muted": "#666666", "line": "#b9b9b4", "head": "#eeeeea", "accent": "#4a4a46", "paper": "#fbfbf6", "soft": "#f2f2ed"},
    {"ink": "#291f24", "muted": "#735f67", "line": "#c7b2bb", "head": "#f0e6eb", "accent": "#854664", "paper": "#fffafd", "soft": "#f8eef3"},
]


def now_local() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def cleanse_text(text: str) -> str:
    text = CYRILLIC_RE.sub("", text)
    text = TIBETAN_DECORATIVE_MARK_RE.sub(" ", text)
    text = TIBETAN_SHAD_RE.sub(" ། ", text)
    text = text.replace("།", " ")
    text = text.replace("...", " ")
    return " ".join(text.split())


def tibetan_font_faces() -> str:
    regular = (TIBETAN_FONT_DIR / "NotoSerifTibetan-Regular.ttf").resolve().as_uri()
    bold = (TIBETAN_FONT_DIR / "NotoSerifTibetan-Bold.ttf").resolve().as_uri()
    black = (TIBETAN_FONT_DIR / "NotoSerifTibetan-Black.ttf").resolve().as_uri()
    jomolhari = (TIBETAN_FONT_DIR / "Jomolhari-Regular.ttf").resolve().as_uri()
    return f"""
    @font-face {{ font-family: 'Local Noto Serif Tibetan'; src: url('{regular}') format('truetype'); font-weight: 400; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Noto Serif Tibetan'; src: url('{bold}') format('truetype'); font-weight: 700; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Noto Serif Tibetan'; src: url('{black}') format('truetype'); font-weight: 900; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Jomolhari'; src: url('{jomolhari}') format('truetype'); font-weight: 400; font-style: normal; font-display: block; }}
    """


def load_language_profile(path: Path | None) -> Dict[str, str]:
    profile = json.loads(path.read_text(encoding="utf-8")) if path else {}
    profile.setdefault("language_code", "bo")
    profile.setdefault("language_name", "藏语")
    profile.setdefault("script_note", "藏文横排文本，去除藏文句读装饰符号，保留音节分隔符")
    profile.setdefault("html_lang", "bo")
    profile.setdefault("script_regex", r"[\u0f00-\u0fff]")
    profile.setdefault("min_script_ratio", 0.35)
    profile.setdefault("font_family", '"Local Noto Serif Tibetan", "Noto Serif Tibetan", Kailasa, "Kohinoor Tibetan", serif')
    profile.setdefault("title_prefix", "")
    return profile


def read_text_records(path: Path, language_profile: Dict[str, str], min_records: int) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    script_re = re.compile(language_profile["script_regex"])
    min_ratio = float(language_profile["min_script_ratio"])
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        title = cleanse_text(str(row.get("title", "")))
        text = cleanse_text(str(row.get("text", "")))
        if len(text) < 20:
            continue
        if len(script_re.findall(text)) / max(len(text), 1) < min_ratio:
            continue
        records.append(
            {
                "title": title,
                "text": text,
                "url": str(row.get("url", "")),
                "source_record_id": str(row.get("record_id", "")),
            }
        )
    if len(records) < min_records:
        raise RuntimeError(f"not enough text records in {path}: {len(records)}")
    return records


def clip(text: str, min_len: int, max_len: int) -> str:
    text = cleanse_text(text)
    if len(text) <= max_len:
        return text
    candidates = []
    for match in re.finditer(r"།", text):
        if min_len <= match.end() <= max_len:
            candidates.append(match.end())
    if candidates:
        return text[: candidates[-1]].strip()
    cut = text[:max_len]
    for sep in [" ། ", " ", "་"]:
        idx = cut.rfind(sep)
        if idx >= min_len:
            end = idx + (1 if sep == "་" else 0)
            return cut[:end].strip()
    return cut.rstrip()


def select_tibetan_span(text: str, rng: random.Random, min_len: int, max_len: int) -> str:
    text = cleanse_text(text)
    if len(text) <= max_len:
        return text
    segments = [seg.strip() for seg in re.split(r"(?<=།)\s+", text) if len(seg.strip()) >= max(12, min_len // 2)]
    rng.shuffle(segments)
    for start_idx in range(len(segments)):
        out: List[str] = []
        total = 0
        for seg in segments[start_idx:]:
            next_total = total + len(seg) + (1 if out else 0)
            if next_total > max_len:
                break
            out.append(seg)
            total = next_total
            if total >= min_len:
                return " ".join(out).strip()
    return clip(text, min_len, max_len)


def record_text(records: List[Dict[str, str]], rng: random.Random, min_len: int, max_len: int) -> str:
    return select_tibetan_span(rng.choice(records)["text"], rng, min_len, max_len)


def record_title(records: List[Dict[str, str]], rng: random.Random, min_len: int = 8, max_len: int = 34) -> str:
    rec = rng.choice(records)
    title = cleanse_text(rec["title"])
    if title and min_len <= len(title) <= max_len:
        return title
    return select_tibetan_span(title or rec["text"], rng, min_len, max_len)


class Builder:
    def __init__(self, document_id: str):
        self.document_id = document_id
        self.counter = 0

    def bid(self) -> str:
        self.counter += 1
        return f"{self.document_id}_b{self.counter:04d}"

    def block(self, label: str, text: str, cls: str, tag: str = "div", attrs: str = "") -> str:
        return (
            f'<{tag} class="{cls}" data-block-id="{self.bid()}" '
            f'data-label="{label}" {attrs}>{esc(cleanse_text(text))}</{tag}>'
        )

    def cell(self, tag: str, label: str, text: str, row: int, col: int, cls: str = "") -> str:
        return (
            f'<{tag} class="{cls}" data-block-id="{self.bid()}" data-label="{label}" '
            f'data-row="{row}" data-col="{col}">{esc(cleanse_text(text))}</{tag}>'
        )


def base_css(page_w: int, page_h: int, theme: Dict[str, str], font_family: str, font_size: int = 24) -> str:
    return tibetan_font_faces() + f"""
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: #d7dce2; }}
    body {{ font-family: {font_family}; color: {theme['ink']}; }}
    .page {{
      width: {page_w}px; min-height: {page_h}px; margin: 0 auto;
      padding: 68px 72px; background: {theme['paper']}; position: relative; overflow: hidden;
    }}
    .doc-title {{ font-size: {font_size + 20}px; font-weight: 900; line-height: 1.45; }}
    .subhead {{ font-size: {font_size - 2}px; line-height: 1.35; color: {theme['muted']}; }}
    .meta {{ font-size: {font_size - 7}px; color: {theme['muted']}; line-height: 1.35; }}
    .section-title {{ font-size: {font_size + 3}px; font-weight: 800; line-height: 1.24; color: {theme['accent']}; }}
    .para {{ font-size: {font_size}px; line-height: 1.48; margin: 0 0 14px; }}
    .small-para {{ font-size: {font_size - 3}px; line-height: 1.42; margin: 0 0 10px; }}
    .tiny {{ font-size: {font_size - 7}px; line-height: 1.3; color: {theme['muted']}; }}
    .panel {{ border: 1.4px solid {theme['line']}; background: rgba(255,255,255,.76); padding: 14px 16px; }}
    .soft {{ background: {theme['soft']}; }}
    .image-box {{ min-height: 190px; border: 1.4px solid {theme['line']}; background: linear-gradient(135deg, {theme['soft']}, #fff); position: relative; }}
    .image-box::after {{ content: ""; position: absolute; inset: 18px; border: 1px dashed rgba(80,90,100,.36); }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; background: white; }}
    th,td {{ border: 1.25px solid {theme['line']}; padding: 9px 10px; vertical-align: top; overflow-wrap: break-word; }}
    th {{ background: {theme['head']}; }}
    .stamp {{ border: 2px solid {theme['accent']}; color: {theme['accent']}; padding: 8px 14px; font-weight: 900; text-align: center; transform: rotate(-5deg); }}
    .footer {{ position: absolute; left: 72px; right: 72px; bottom: 26px; border-top: 1px solid {theme['line']}; padding-top: 8px; text-align: right; font-size: {font_size - 8}px; color: {theme['muted']}; }}
    """


def wrap(doc: Dict[str, str], body: str, css: str, page_w: int, page_h: int, cls: str = "") -> str:
    return f"""<!doctype html>
<html lang="{esc(doc['html_lang'])}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width={page_w}, initial-scale=1">
  <title>{esc(cleanse_text(doc['title']))}</title>
  <style>{css}</style>
</head>
<body><main class="page {cls}" data-page-width="{page_w}" data-page-height="{page_h}">{body}</main></body>
</html>
"""


def simple_table(b: Builder, headers: List[str], rows: List[List[str]]) -> str:
    parts = ["<table><tbody><tr>"]
    for col, header in enumerate(headers):
        parts.append(b.cell("th", "table_header", header, 0, col))
    parts.append("</tr>")
    for row_idx, row in enumerate(rows, 1):
        parts.append("<tr>")
        for col_idx, value in enumerate(row):
            parts.append(b.cell("td", "table_cell_text", value, row_idx, col_idx))
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def kv(b: Builder, label: str, value: str, cls: str = "kv") -> str:
    return f'<div class="{cls}">{b.block("field_label", label, "field-label")}{b.block("field_value", value, "field-value")}</div>'


def footer(b: Builder, text: str) -> str:
    return b.block("footer", text, "footer")


def book_page(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    paras = [record_text(records, rng, 90, 170) for _ in range(8)]
    if variant == 1:
        body = f"""
        <header class="book-head">{b.block('chapter_title', doc['title'], 'doc-title')}{b.block('metadata', 'ལེའུ %02d' % variant, 'meta')}</header>
        <div class="book-cols">{''.join(b.block('paragraph', p, 'para') for p in paras)}</div>
        {b.block('page_number', str(20 + variant), 'page-no')}
        """
        extra = ".book-head{display:flex;justify-content:space-between;border-bottom:2px solid %s;padding-bottom:12px;margin-bottom:22px}.book-cols{columns:2;column-gap:38px}.para{break-inside:avoid}.page-no{position:absolute;bottom:36px;left:0;right:0;text-align:center;color:%s}" % (theme["line"], theme["muted"])
    elif variant == 2:
        body = f"""
        <section class="chapter-opener">{b.block('metadata', 'དེབ་ཕྲེང %02d' % variant, 'meta')}{b.block('metadata', record_title(records, rng, 8, 18), 'meta edition-meta')}{b.block('chapter_title', doc['title'], 'opener-title')}{b.block('paragraph', paras[0], 'lead')}</section>
        <div class="reading-notes">{''.join(b.block('note', record_text(records, rng, 36, 80), 'panel small-para') for _ in range(4))}</div>
        {b.block('page_number', str(30 + variant), 'page-no')}
        """
        extra = ".chapter-opener{min-height:780px;border-left:12px solid %s;padding-left:28px;display:flex;flex-direction:column;justify-content:center}.opener-title{font-size:62px;font-weight:900;line-height:1.46}.lead{font-size:30px;line-height:1.5;margin-top:26px}.reading-notes{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:26px}.page-no{position:absolute;bottom:36px;right:80px;color:%s}" % (theme["accent"], theme["muted"])
    else:
        body = f"""
        <div class="illustrated-head">{b.block('chapter_title', doc['title'], 'doc-title')}{b.block('metadata', 'དཔེ་ཀློག', 'meta')}</div>
        <main class="ill-grid"><section>{''.join(b.block('paragraph', p, 'para') for p in paras[:5])}</section><aside>{b.block('image', '', 'image-box')}{b.block('caption', record_text(records, rng, 28, 70), 'tiny')}{b.block('image', '', 'image-box small-img')}</aside></main>
        """
        extra = ".illustrated-head{display:flex;justify-content:space-between;border-bottom:3px solid %s;padding-bottom:13px;margin-bottom:22px}.ill-grid{display:grid;grid-template-columns:1fr 340px;gap:24px}.small-img{min-height:150px;margin-top:18px}" % theme["accent"]
    css = base_css(1120, 1600, theme, doc["font_family"]) + extra
    return wrap(doc, body, css, 1120, 1600, "book-page")


def textbook_page(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    bullets = [record_text(records, rng, 24, 56) for _ in range(5)]
    paras = [record_text(records, rng, 70, 150) for _ in range(4)]
    if variant in (1, 4):
        body = f"""
        <header class="lesson-head">{b.block('chapter_title', doc['title'], 'doc-title')}{b.block('metadata', 'Lesson %02d' % variant, 'meta')}</header>
        <section class="lesson-grid"><main>{''.join(b.block('paragraph', p, 'para') for p in paras)}</main><aside class="panel soft">{b.block('section_title', 'གཙོ་གནད', 'section-title')}{''.join(b.block('list_item', item, 'small-para') for item in bullets)}</aside></section>
        <section class="exercise-band">{b.block('section_title', 'སྦྱོང་ཚན', 'section-title')}{''.join(b.block('question', record_text(records, rng, 36, 80), 'question-line') for _ in range(4))}</section>
        """
        extra = ".lesson-head{border-bottom:4px solid %s;padding-bottom:14px;margin-bottom:22px}.lesson-grid{display:grid;grid-template-columns:1fr 320px;gap:22px}.exercise-band{margin-top:24px;border-top:2px solid %s;padding-top:16px}.question-line{font-size:23px;line-height:1.35;border-bottom:1px dotted %s;padding:9px 0}" % (theme["accent"], theme["line"], theme["line"])
    elif variant in (2, 5):
        body = f"""
        <header class="concept-head">{b.block('chapter_title', doc['title'], 'doc-title')}{b.block('document_subtitle', record_text(records, rng, 46, 90), 'subhead')}</header>
        <div class="concept-map">{''.join(f'<section class="concept">{b.block("section_title", record_title(records, rng, 8, 20), "section-title")}{b.block("paragraph", record_text(records, rng, 44, 90), "small-para")}</section>' for _ in range(6))}</div>
        <div class="image-row">{b.block('image', '', 'image-box')}{b.block('caption', record_text(records, rng, 34, 74), 'tiny')}</div>
        """
        extra = ".concept-head{display:grid;grid-template-columns:1fr 360px;gap:22px;align-items:end;border-bottom:2px solid %s;padding-bottom:16px}.concept-map{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-top:22px}.concept{border:1.4px solid %s;padding:15px;background:white;min-height:176px}.image-row{margin-top:24px}" % (theme["line"], theme["line"])
    else:
        rows = [[record_title(records, rng, 6, 18), record_text(records, rng, 20, 46), record_text(records, rng, 20, 46)] for _ in range(4)]
        body = f"""
        <header class="practice-head">{b.block('chapter_title', doc['title'], 'doc-title')}{b.block('metadata', 'དཔྱད་གཞི', 'stamp')}</header>
        <main class="practice-layout"><section>{''.join(b.block('paragraph', p, 'para') for p in paras[:3])}</section><aside>{simple_table(b, ['མིང', 'གནད', 'དཔྱད'], rows)}</aside></main>
        """
        extra = ".practice-head{display:flex;justify-content:space-between;align-items:end}.practice-layout{display:grid;grid-template-columns:1fr 420px;gap:24px;margin-top:28px}td,th{font-size:18px;line-height:1.28}"
    css = base_css(1180, 1580, theme, doc["font_family"]) + extra
    return wrap(doc, body, css, 1180, 1580, "textbook-page")


def newspaper_page(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    stories = []
    for _ in range(7):
        title = record_title(records, rng, 10, 28)
        paras = "".join(b.block("paragraph", record_text(records, rng, 58, 118), "news-para") for _ in range(rng.randint(1, 2)))
        stories.append(f'<article class="story">{b.block("section_title", title, "news-head")}{paras}</article>')
    side_items = "".join(b.block("list_item", record_text(records, rng, 26, 64), "brief-line") for _ in range(8))
    if variant in (1, 4):
        body = f"""
        <header class="press-top">{b.block('metadata', 'ཉིན་རེའི་གསར་འགྱུར', 'press-kicker')}{b.block('document_title', doc['title'], 'press-title')}{b.block('metadata', 'No %03d  2026-06-30' % (120 + variant), 'meta')}</header>
        <main class="press-grid"><section class="lead-story">{stories[0]}{b.block('image', '', 'image-box')}</section><section class="columns">{''.join(stories[1:5])}</section><aside class="briefs">{b.block('section_title', 'མདོར་བསྡུས', 'section-title')}{side_items}</aside></main>
        {footer(b, 'newspaper dense portrait')}
        """
        extra = ".press-top{text-align:center;border-top:5px solid #222;border-bottom:2px solid #222;padding:12px 0 14px}.press-title{font-size:66px;font-weight:900;line-height:1.36}.press-kicker{font-size:18px;letter-spacing:3px}.press-grid{display:grid;grid-template-columns:1.15fr 1.25fr 300px;gap:18px;margin-top:20px}.columns{columns:2;column-gap:18px}.story{break-inside:avoid;border-bottom:1px solid %s;padding-bottom:12px;margin-bottom:14px}.news-head{font-size:26px;font-weight:900;line-height:1.32}.news-para{font-size:18px;line-height:1.35;margin:8px 0}.briefs{border-left:3px solid %s;padding-left:14px}.brief-line{font-size:17px;line-height:1.3;border-bottom:1px solid %s;padding:8px 0}.image-box{min-height:260px;margin-top:14px}" % (theme["line"], theme["accent"], theme["line"])
    elif variant in (2, 5):
        body = f"""
        <header class="tabloid-head">{b.block('document_title', doc['title'], 'press-title')}{b.block('metadata', 'རིག་གནས · སློབ་གསོ · སྤྱི་ཚོགས', 'meta')}</header>
        <div class="banner">{b.block('section_title', record_title(records, rng, 14, 34), 'banner-title')}{b.block('paragraph', record_text(records, rng, 70, 130), 'banner-copy')}</div>
        <main class="tabloid-grid"><section>{''.join(stories[:3])}</section><section>{''.join(stories[3:6])}</section><aside class="ad-box">{b.block('section_title', 'བརྡ་ཁྱབ', 'section-title')}{side_items}</aside></main>
        """
        extra = ".tabloid-head{display:flex;justify-content:space-between;align-items:end;border-bottom:5px double #222;padding-bottom:12px}.press-title{font-size:58px;font-weight:900;line-height:1.36}.banner{display:grid;grid-template-columns:1fr 420px;gap:20px;background:%s;border:2px solid %s;padding:18px;margin:18px 0}.banner-title{font-size:34px;font-weight:900;line-height:1.34}.banner-copy{font-size:20px;line-height:1.34}.tabloid-grid{display:grid;grid-template-columns:1fr 1fr 280px;gap:18px}.story{border-bottom:1px solid %s;margin-bottom:13px;padding-bottom:12px}.news-head{font-size:24px;font-weight:900;line-height:1.32}.news-para{font-size:18px;line-height:1.35}.ad-box{border:2px solid %s;padding:12px}.brief-line{font-size:17px;line-height:1.3;border-bottom:1px dotted %s;padding:7px 0}" % (theme["soft"], theme["line"], theme["line"], theme["accent"], theme["line"])
    elif variant == 3:
        body = f"""
        <header class="compact-head">{b.block('metadata', 'གསར་འགྱུར་ཆུང་བ', 'meta')}{b.block('document_title', doc['title'], 'press-title')}</header>
        <main class="compact-news"><section class="main-col">{stories[0]}{stories[1]}{b.block('image', '', 'image-box')}</section><section class="multi-col">{''.join(stories[2:])}</section></main>
        {footer(b, 'newspaper compact multi-column')}
        """
        extra = ".compact-head{border-bottom:4px solid #222;padding-bottom:12px}.press-title{font-size:62px;font-weight:900;line-height:1.36}.compact-news{display:grid;grid-template-columns:410px 1fr;gap:22px;margin-top:20px}.multi-col{columns:3;column-gap:16px}.story{break-inside:avoid;border-bottom:1px solid %s;margin-bottom:12px;padding-bottom:10px}.news-head{font-size:23px;font-weight:900;line-height:1.32}.news-para{font-size:17px;line-height:1.33}.image-box{min-height:360px;margin-top:12px}" % theme["line"]
    elif variant == 4:
        body = f"""
        <header class="evening-head">{b.block('document_title', doc['title'], 'press-title')}{b.block('metadata', 'དགོང་མོའི་པར་ངོས 04', 'meta')}</header>
        <main class="evening-grid"><section class="photo-lead">{b.block('image', '', 'image-box')}{stories[0]}</section><section class="stacked">{''.join(stories[1:4])}</section><section class="narrow-news">{''.join(stories[4:])}{side_items}</section></main>
        """
        extra = ".evening-head{display:grid;grid-template-columns:1fr 260px;gap:20px;align-items:end;border-bottom:6px solid #222;padding-bottom:12px}.press-title{font-size:60px;font-weight:900;line-height:1.34}.evening-grid{display:grid;grid-template-columns:430px 1fr 250px;gap:18px;margin-top:20px}.photo-lead{background:%s;padding:12px}.image-box{min-height:390px;margin-bottom:12px}.story{border-bottom:1px solid %s;margin-bottom:12px;padding-bottom:10px}.news-head{font-size:23px;font-weight:900;line-height:1.3}.news-para{font-size:17px;line-height:1.32}.brief-line{font-size:16px;line-height:1.28;border-bottom:1px dotted %s;padding:6px 0}" % (theme["soft"], theme["line"], theme["line"])
    elif variant == 5:
        body = f"""
        <header class="bulletin-paper">{b.block('metadata', 'སྤྱི་ཚོགས་ཆེད་བསྒྲགས', 'meta')}{b.block('document_title', doc['title'], 'press-title')}</header>
        <main class="bulletin-news">{''.join(f'<section class="bullet-story">{story}</section>' for story in stories[:6])}</main>
        <aside class="bottom-strip">{side_items}</aside>
        """
        extra = ".bulletin-paper{text-align:left;border-left:14px solid %s;padding-left:20px}.press-title{font-size:56px;font-weight:900;line-height:1.36}.bulletin-news{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:24px}.bullet-story{border:1.3px solid %s;background:white;padding:12px;min-height:210px}.news-head{font-size:22px;font-weight:900;line-height:1.3}.news-para{font-size:17px;line-height:1.32}.bottom-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}.brief-line{font-size:15px;line-height:1.24;background:%s;padding:8px}" % (theme["accent"], theme["line"], theme["soft"])
    else:
        body = f"""
        <header class="classic-paper">{b.block('document_title', doc['title'], 'press-title')}{b.block('metadata', 'No 006 · རིག་གནས་ཟུར་བཀོད', 'meta')}</header>
        <main class="classic-news"><section class="left-rail">{side_items}</section><section class="center-col">{stories[0]}{stories[1]}{stories[2]}</section><section class="right-cols">{''.join(stories[3:])}</section></main>
        {footer(b, 'newspaper rail layout')}
        """
        extra = ".classic-paper{text-align:center;border-top:4px double #222;border-bottom:4px double #222;padding:10px 0}.press-title{font-size:64px;font-weight:900;line-height:1.34}.classic-news{display:grid;grid-template-columns:230px 390px 1fr;gap:18px;margin-top:20px}.left-rail{border-right:2px solid %s;padding-right:12px}.right-cols{columns:2;column-gap:16px}.story{break-inside:avoid;border-bottom:1px solid %s;margin-bottom:12px;padding-bottom:10px}.news-head{font-size:22px;font-weight:900}.news-para{font-size:17px;line-height:1.32}.brief-line{font-size:16px;line-height:1.28;border-bottom:1px solid %s;padding:7px 0}" % (theme["line"], theme["line"], theme["line"])
    css = base_css(1240, 1754, theme, doc["font_family"], 22) + extra
    return wrap(doc, body, css, 1240, 1754, "newspaper-page")


def magazine_journal(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    cards = "".join(f'<section class="feature-card">{b.block("section_title", record_title(records, rng, 8, 24), "section-title")}{b.block("paragraph", record_text(records, rng, 54, 110), "small-para")}</section>' for _ in range(5))
    page_w = 1280 if variant in (3, 6) else 1120
    if variant == 1:
        body = f"""
        <header class="mag-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'དུས་དེབ %02d' % variant, 'meta')}</header>
        <section class="hero-feature">{b.block('image', '', 'image-box')}{b.block('section_title', record_title(records, rng, 12, 32), 'hero-title')}{b.block('paragraph', record_text(records, rng, 90, 160), 'para')}</section>
        <main class="mag-grid">{cards}</main>
        {footer(b, 'magazine hero layout')}
        """
        extra = ".mag-head{display:flex;justify-content:space-between;align-items:end;border-bottom:2px solid %s;padding-bottom:14px}.hero-feature{display:grid;grid-template-columns:430px 1fr;gap:24px;margin-top:24px;align-items:center}.hero-title{font-size:42px;font-weight:900;line-height:1.38}.mag-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:26px}.feature-card{border-top:4px solid %s;background:white;padding:14px;min-height:172px}" % (theme["line"], theme["accent"])
    elif variant == 2:
        body = f"""
        <header class="cover-mag">{b.block('metadata', 'SPECIAL ISSUE', 'meta')}{b.block('document_title', doc['title'], 'cover-title')}{b.block('paragraph', record_text(records, rng, 70, 130), 'cover-copy')}</header>
        <main class="cover-bottom">{cards}</main>
        """
        extra = ".cover-mag{min-height:620px;background:%s;border:3px solid %s;padding:44px;display:flex;flex-direction:column;justify-content:end}.cover-title{font-size:68px;font-weight:900;line-height:1.42}.cover-copy{font-size:28px;line-height:1.38;margin-top:20px}.cover-bottom{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}.feature-card{border:1px solid %s;padding:14px;background:white;min-height:150px}" % (theme["soft"], theme["accent"], theme["line"])
    elif variant == 3:
        body = f"""
        <header class="wide-mag">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'རི་མོ་དང་རྩོམ་ཡིག', 'meta')}</header>
        <main class="wide-feature"><section>{b.block('image', '', 'image-box')}{b.block('caption', record_text(records, rng, 28, 60), 'tiny')}</section><section>{cards}</section></main>
        """
        extra = ".wide-mag{border-bottom:5px solid %s;padding-bottom:12px}.wide-feature{display:grid;grid-template-columns:460px 1fr;gap:22px;margin-top:22px}.image-box{min-height:620px}.wide-feature section:nth-child(2){display:grid;grid-template-columns:1fr 1fr;gap:14px}.feature-card{border-left:5px solid %s;background:white;padding:14px;min-height:190px}" % (theme["accent"], theme["accent"])
    elif variant == 4:
        body = f"""
        <header class="catalog-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'CONTENTS', 'meta')}</header>
        <main class="catalog-list">{''.join(f'<section class="catalog-row">{b.block("metadata", f"{i:02d}", "catalog-no")}{b.block("section_title", record_title(records, rng, 9, 24), "section-title")}{b.block("paragraph", record_text(records, rng, 38, 82), "small-para")}</section>' for i in range(1, 8))}</main>
        """
        extra = ".catalog-head{display:grid;grid-template-columns:1fr 190px;align-items:end;border-bottom:2px solid %s;padding-bottom:14px}.catalog-list{margin-top:22px}.catalog-row{display:grid;grid-template-columns:70px 260px 1fr;gap:18px;border-bottom:1px solid %s;padding:13px 0}.catalog-no{font-size:30px;font-weight:900;color:%s}" % (theme["line"], theme["line"], theme["accent"])
    elif variant == 5:
        body = f"""
        <main class="column-mag"><header>{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'དུས་དེབ་ཟུར་བཀོད', 'meta')}</header><section class="column-copy">{''.join(b.block('paragraph', record_text(records, rng, 70, 135), 'para') for _ in range(7))}</section></main>
        """
        extra = ".column-mag header{text-align:center;border-top:3px solid %s;border-bottom:3px solid %s;padding:12px 0}.column-copy{columns:3;column-gap:24px;margin-top:22px}.para{font-size:22px;line-height:1.44;break-inside:avoid}" % (theme["accent"], theme["accent"])
    else:
        body = f"""
        <header class="poster-mag">{b.block('metadata', 'VISUAL REPORT', 'meta')}{b.block('document_title', doc['title'], 'doc-title')}</header>
        <main class="poster-mag-grid">{b.block('image', '', 'image-box main-img')}{cards}</main>
        """
        extra = ".poster-mag{border-left:12px solid %s;padding-left:20px}.poster-mag-grid{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:14px;margin-top:24px}.main-img{grid-row:span 2;min-height:620px}.feature-card{border:1.4px solid %s;background:white;padding:14px;min-height:295px}" % (theme["accent"], theme["line"])
    css = base_css(page_w, 1500, theme, doc["font_family"], 23) + extra
    return wrap(doc, body, css, page_w, 1500, "magazine-journal")


def academic_paper(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    rows = [[str(i), record_title(records, rng, 8, 18), record_text(records, rng, 18, 42)] for i in range(1, 5)]
    refs = "".join(b.block("reference", f"[{i}] {record_title(records, rng, 10, 28)}", "ref-line") for i in range(1, 7))
    body = f"""
    <header class="paper-head">{b.block('document_title', doc['title'], 'paper-title')}{b.block('metadata', 'Vol %02d  No %02d' % (7 + variant, variant), 'meta')}</header>
    <section class="abstract">{b.block('section_title', 'གནད་བསྡུས', 'section-title')}{b.block('paragraph', record_text(records, rng, 120, 210), 'small-para')}</section>
    <main class="paper-cols">
      <section>{b.block('section_title', '1 ངོ་སྤྲོད', 'section-title')}{b.block('paragraph', record_text(records, rng, 100, 180), 'paper-para')}{b.block('section_title', '2 ཐབས་ལམ', 'section-title')}{b.block('paragraph', record_text(records, rng, 100, 190), 'paper-para')}</section>
      <section>{b.block('section_title', '3 དཔྱད་འབྲས', 'section-title')}{simple_table(b, ['No', 'དོན་ཚན', 'གསལ་བཤད'], rows)}{b.block('section_title', 'དཔྱད་གཞི', 'section-title ref-title')}{refs}</section>
    </main>
    """
    extra = ".paper-head{text-align:center;border-bottom:2px solid %s;padding-bottom:14px}.paper-title{font-size:42px;font-weight:900;line-height:1.28}.abstract{border:1px solid %s;background:%s;padding:14px 16px;margin:18px 0}.paper-cols{display:grid;grid-template-columns:1fr 1fr;gap:28px}.paper-para{font-size:20px;line-height:1.43;margin-bottom:12px}td,th{font-size:16px;line-height:1.25}.ref-line{font-size:15px;line-height:1.28;margin-bottom:5px}.ref-title{margin-top:14px}" % (theme["line"], theme["line"], theme["soft"])
    css = base_css(1180, 1580, theme, doc["font_family"], 22) + extra
    return wrap(doc, body, css, 1180, 1580, "academic-paper")


def historical_classic(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    lines = [record_text(records, rng, 38, 84) for _ in range(13)]
    body = f"""
    <div class="classic-frame">
      <header>{b.block('metadata', 'གནའ་དཔེ་དཔེ་མཚོན', 'meta')}{b.block('document_title', doc['title'], 'classic-title')}</header>
      <main class="classic-body">{''.join(b.block('paragraph', line, 'classic-line') for line in lines)}</main>
      {b.block('page_number', str(100 + variant), 'folio')}
    </div>
    """
    extra = ".page{background:#efe4ca}.classic-frame{min-height:1420px;border:8px double #7d6246;padding:42px;background:linear-gradient(90deg, rgba(150,105,64,.08), rgba(255,255,245,.72), rgba(150,105,64,.08))}.classic-title{font-size:44px;font-weight:900;text-align:center;line-height:1.35;margin:12px 0 30px}.classic-body{columns:2;column-gap:44px}.classic-line{font-size:25px;line-height:1.72;margin:0 0 10px;break-inside:avoid}.folio{text-align:center;margin-top:30px;color:#7b6a55}.meta{text-align:center}"
    if variant in (2, 5):
        extra += ".classic-body{columns:1;max-width:720px;margin:0 auto}.classic-line{font-size:28px;line-height:1.88}.classic-frame{border-style:solid}"
    css = base_css(1060, 1540, theme, doc["font_family"], 24) + extra
    return wrap(doc, body, css, 1060, 1540, "historical-classic")


def notice_announcement(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    title = b.block("document_title", doc["title"], "doc-title")
    if variant == 1:
        body = f"""
        <header class="notice-head ribbon">{b.block('metadata', 'བརྡ་ཐོ %04d' % (2020 + variant), 'meta')}{title}</header>
        <main class="notice-main">
          <section>{b.block('paragraph', record_text(records, rng, 120, 220), 'para')}{b.block('paragraph', record_text(records, rng, 90, 170), 'para')}</section>
          <aside class="notice-side panel soft">{kv(b, 'དུས་ཚོད', '2026-06-%02d' % (20 + variant))}{kv(b, 'ས་གནས', record_title(records, rng, 8, 20))}{kv(b, 'འབྲེལ་བ', record_title(records, rng, 8, 20))}</aside>
        </main>
        <section class="notice-list">{''.join(b.block('list_item', record_text(records, rng, 32, 72), 'notice-line') for _ in range(5))}</section>
        {footer(b, 'notice ribbon layout')}
        """
        extra = ".notice-head{border-top:8px solid %s;border-bottom:2px solid %s;padding:18px 0}.notice-main{display:grid;grid-template-columns:1fr 340px;gap:28px;margin-top:26px}.notice-side{display:grid;gap:12px}.field-label{font-size:16px;color:%s}.field-value{font-size:22px;line-height:1.3}.notice-list{margin-top:26px;border-left:6px solid %s;padding-left:18px}.notice-line{font-size:22px;line-height:1.38;border-bottom:1px solid %s;padding:9px 0}" % (theme["accent"], theme["line"], theme["muted"], theme["accent"], theme["line"])
    elif variant == 2:
        cards = "".join(f'<section class="notice-card">{b.block("section_title", record_title(records, rng, 8, 22), "section-title")}{b.block("paragraph", record_text(records, rng, 42, 86), "small-para")}</section>' for _ in range(6))
        body = f"""
        <header class="bulletin-head">{title}{b.block('metadata', 'དོན་ཚན་མང་བའི་བསྒྲགས་གཏམ', 'meta')}</header>
        <main class="card-board">{cards}</main>
        """
        extra = ".bulletin-head{display:grid;grid-template-columns:1fr 300px;gap:22px;align-items:end;border-bottom:5px solid %s;padding-bottom:16px}.card-board{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-top:24px}.notice-card{border:1.5px solid %s;background:white;padding:16px;min-height:220px}.notice-card:nth-child(2n){background:%s}" % (theme["accent"], theme["line"], theme["soft"])
    elif variant == 3:
        steps = "".join(f'<div class="step-row">{b.block("metadata", f"{i:02d}", "step-no")}{b.block("list_item", record_text(records, rng, 36, 86), "step-copy")}</div>' for i in range(1, 8))
        body = f"""
        <aside class="vertical-label">{b.block('metadata', 'NOTICE', 'meta')}</aside>
        <main class="process-notice">{title}{b.block('paragraph', record_text(records, rng, 80, 150), 'lead')}{steps}</main>
        """
        extra = ".page{display:grid;grid-template-columns:150px 1fr;gap:32px}.vertical-label{writing-mode:vertical-rl;border-right:8px solid %s;font-size:42px;font-weight:900;letter-spacing:8px;color:%s;display:flex;align-items:center;justify-content:center}.process-notice{padding-top:12px}.lead{font-size:26px;line-height:1.42;margin:18px 0}.step-row{display:grid;grid-template-columns:70px 1fr;gap:14px;border-bottom:1px solid %s;padding:12px 0}.step-no{font-size:28px;font-weight:900;color:%s}.step-copy{font-size:22px;line-height:1.35}" % (theme["accent"], theme["accent"], theme["line"], theme["accent"])
    elif variant == 4:
        body = f"""
        <section class="official-notice">
          <div class="seal-zone">{b.block('metadata', 'གཞུང་འབྲེལ', 'stamp')}</div>
          {title}
          {b.block('paragraph', record_text(records, rng, 150, 260), 'para')}
          {b.block('paragraph', record_text(records, rng, 90, 160), 'para')}
          <div class="signature-row">{b.block('metadata', record_title(records, rng, 8, 20), 'meta')}{b.block('metadata', '2026-06-%02d' % (20 + variant), 'meta')}</div>
        </section>
        """
        extra = ".official-notice{min-height:1200px;border:2px solid %s;padding:46px 58px;background:white}.seal-zone{text-align:right}.doc-title{text-align:center;margin:26px 0 34px}.para{text-indent:2em;font-size:27px;line-height:1.6}.signature-row{display:grid;grid-template-columns:1fr 1fr;gap:20px;text-align:right;margin-top:56px}" % theme["line"]
    elif variant == 5:
        left = "".join(b.block("paragraph", record_text(records, rng, 50, 110), "small-para") for _ in range(4))
        right = "".join(kv(b, label, record_title(records, rng, 8, 20), "notice-kv") for label in ["དུས", "ས་གནས", "ཁ་ཕྱོགས", "འགན"])
        body = f"""
        <header class="split-notice-head">{b.block('metadata', 'PUBLIC BOARD', 'meta')}{title}</header>
        <main class="split-notice"><section class="panel soft">{left}</section><aside>{right}</aside></main>
        """
        extra = ".split-notice-head{border-left:14px solid %s;padding-left:22px}.split-notice{display:grid;grid-template-columns:1.1fr .9fr;gap:24px;margin-top:30px}.notice-kv{border:1.4px solid %s;margin-bottom:12px;padding:14px;background:white}.field-label{font-size:16px;color:%s}.field-value{font-size:24px;line-height:1.35}" % (theme["accent"], theme["line"], theme["muted"])
    else:
        tiles = "".join(f'<section class="timeline-item">{b.block("metadata", f"06/{18+i}", "time")}{b.block("paragraph", record_text(records, rng, 42, 88), "timeline-copy")}</section>' for i in range(6))
        body = f"""
        <header class="timeline-head">{title}{b.block('metadata', 'དུས་རིམ་བརྡ་ཐོ', 'meta')}</header>
        <main class="timeline">{tiles}</main>
        """
        extra = ".timeline-head{text-align:center;border-bottom:2px solid %s;padding-bottom:16px}.timeline{margin-top:28px;display:grid;gap:14px}.timeline-item{display:grid;grid-template-columns:150px 1fr;gap:20px;border-left:8px solid %s;background:%s;padding:16px}.time{font-size:25px;font-weight:900;color:%s}.timeline-copy{font-size:23px;line-height:1.36}" % (theme["line"], theme["accent"], theme["soft"], theme["accent"])
    css = base_css(1120, 1480, theme, doc["font_family"], 24) + extra
    return wrap(doc, body, css, 1120, 1480, "notice-announcement")


def exam_paper(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    def mcq(start: int, count: int) -> str:
        items = []
        for i in range(start, start + count):
            options = "".join(b.block("option", f"{chr(64+j)}  {record_title(records, rng, 6, 18)}", "option") for j in range(1, 5))
            items.append(f'<section class="question">{b.block("question", f"{i}. " + record_text(records, rng, 36, 76), "question-text")}<div class="options">{options}</div></section>')
        return "".join(items)

    if variant == 1:
        body = f"""
        <header class="exam-head centered">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'རྒྱུགས་ཡུན 90 min    Score 100', 'meta')}</header>
        <div class="student-line">{kv(b, 'མིང', '________')}{kv(b, 'ཨང་རྟགས', '________')}{kv(b, 'ཁང་མིག', '________')}</div>
        <main class="exam-cols">{mcq(1, 8)}</main>
        """
        extra = ".exam-head{text-align:center;border-bottom:3px double %s;padding-bottom:14px}.student-line{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin:18px 0}.kv{border-bottom:1.5px solid %s;padding:8px}.field-label{font-size:15px;color:%s}.field-value{font-size:20px}.exam-cols{columns:2;column-gap:26px}.question{break-inside:avoid;border-bottom:1px solid %s;padding-bottom:10px;margin-bottom:12px}.question-text{font-size:19px;line-height:1.32}.options{display:grid;grid-template-columns:1fr 1fr;gap:6px 10px;margin-top:8px}.option{font-size:17px;line-height:1.28}" % (theme["line"], theme["line"], theme["muted"], theme["line"])
    elif variant == 2:
        blanks = "".join(f'<section class="blank-q">{b.block("question", f"{i}. " + record_text(records, rng, 34, 72), "question-text")}{b.block("answer_area", " ", "answer-line")}</section>' for i in range(1, 9))
        body = f"""
        <header class="fill-head">{b.block('metadata', 'A 卷', 'stamp')}{b.block('document_title', doc['title'], 'doc-title')}</header>
        <main class="fill-paper">{blanks}</main>
        """
        extra = ".fill-head{display:grid;grid-template-columns:150px 1fr;gap:20px;align-items:center;border-bottom:2px solid %s;padding-bottom:14px}.fill-paper{display:grid;grid-template-columns:1fr;gap:13px;margin-top:22px}.blank-q{display:grid;grid-template-columns:1fr 300px;gap:18px;border-bottom:1px dotted %s;padding:10px 0}.question-text{font-size:21px;line-height:1.36}.answer-line{height:32px;border-bottom:1.6px solid %s}" % (theme["line"], theme["line"], theme["muted"])
    elif variant == 3:
        sections = "".join(f'<section class="reading-block">{b.block("section_title", f"Part {i}", "section-title")}{b.block("paragraph", record_text(records, rng, 95, 165), "passage")}{mcq(i * 2 - 1, 2)}</section>' for i in range(1, 4))
        body = f"""
        <header class="reading-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'Reading / comprehension', 'meta')}</header>
        <main>{sections}</main>
        """
        extra = ".reading-head{border-left:12px solid %s;padding-left:18px}.reading-block{margin-top:18px;border:1.4px solid %s;padding:15px;background:white}.passage{font-size:20px;line-height:1.4;margin-bottom:12px}.question{margin-top:8px}.question-text{font-size:18px;line-height:1.3}.options{display:grid;grid-template-columns:1fr 1fr;gap:4px 10px}.option{font-size:16px;line-height:1.25}" % (theme["accent"], theme["line"])
    elif variant == 4:
        rows = [[str(i), record_text(records, rng, 24, 52), "____"] for i in range(1, 10)]
        body = f"""
        <header class="score-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'ཐོབ་སྐར་ཞིབ་བཤེར', 'meta')}</header>
        <main class="score-layout"><section>{mcq(1, 5)}</section><aside>{simple_table(b, ['No', 'དྲི་བ', 'སྐར'], rows)}</aside></main>
        """
        extra = ".score-head{display:flex;justify-content:space-between;align-items:end;border-bottom:4px solid %s;padding-bottom:12px}.score-layout{display:grid;grid-template-columns:1fr 360px;gap:22px;margin-top:22px}.question{border-bottom:1px solid %s;padding-bottom:10px;margin-bottom:12px}.question-text{font-size:20px;line-height:1.34}.options{display:grid;grid-template-columns:1fr 1fr;gap:5px}.option{font-size:16px}td,th{font-size:15px;padding:7px}" % (theme["accent"], theme["line"])
    elif variant == 5:
        groups = "".join(f'<section class="oral-card">{b.block("section_title", record_title(records, rng, 8, 20), "section-title")}{b.block("question", record_text(records, rng, 48, 90), "question-text")}{b.block("answer_area", " ", "answer-box")}</section>' for _ in range(6))
        body = f"""
        <header class="oral-head">{b.block('metadata', 'ངག་རྒྱུགས / ལག་ལེན', 'meta')}{b.block('document_title', doc['title'], 'doc-title')}</header>
        <main class="oral-grid">{groups}</main>
        """
        extra = ".oral-head{text-align:center;border-top:8px solid %s;border-bottom:1px solid %s;padding:16px 0}.oral-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-top:24px}.oral-card{border:1.5px solid %s;padding:14px;background:%s;min-height:260px}.question-text{font-size:19px;line-height:1.34}.answer-box{height:70px;border:1px dashed %s;background:white;margin-top:12px}" % (theme["accent"], theme["line"], theme["line"], theme["soft"], theme["line"])
    else:
        left = "".join(f'<section class="essay-q">{b.block("question", f"{i}. " + record_text(records, rng, 52, 98), "question-text")}{b.block("answer_area", " ", "essay-area")}</section>' for i in range(1, 4))
        rubric = "".join(b.block("list_item", record_title(records, rng, 8, 18), "rubric-line") for _ in range(9))
        body = f"""
        <header class="essay-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'རྩོམ་ཡིག་དྲི་ཤོག', 'meta')}</header>
        <main class="essay-paper"><section>{left}</section><aside class="rubric-box">{b.block('section_title', 'དཔྱད་གཞི', 'section-title')}{rubric}</aside></main>
        """
        extra = ".essay-head{border-bottom:2px solid %s;padding-bottom:14px}.essay-paper{display:grid;grid-template-columns:1fr 260px;gap:20px;margin-top:20px}.essay-q{margin-bottom:16px}.question-text{font-size:22px;line-height:1.34;border-left:6px solid %s;padding-left:14px}.essay-area{height:170px;border:1.5px dashed %s;background:repeating-linear-gradient(white, white 32px, %s 33px);margin-top:10px}.rubric-box{border:1.4px solid %s;padding:12px;background:%s}.rubric-line{font-size:17px;line-height:1.26;border-bottom:1px dotted %s;padding:6px 0}" % (theme["line"], theme["accent"], theme["line"], theme["soft"], theme["line"], theme["soft"], theme["line"])
    css = base_css(1160, 1560, theme, doc["font_family"], 22) + extra
    return wrap(doc, body, css, 1160, 1560, "exam-paper")


def complex_form(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    sections = "".join(f'<section class="form-section">{b.block("section_title", record_title(records, rng, 8, 22), "section-title")}{kv(b, "མིང", record_title(records, rng, 6, 16))}{kv(b, "དོན་ཚན", record_text(records, rng, 26, 60))}</section>' for _ in range(5))
    rows = [[record_title(records, rng, 6, 16), "□", "□", record_text(records, rng, 14, 34)] for _ in range(4)]
    if variant == 1:
        body = f"""
        <header class="form-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'Form-%03d' % variant, 'meta')}</header>
        <main class="form-grid">{sections}</main>
        <section class="check-area">{b.block('section_title', 'ཞིབ་བཤེར་དོན་ཚན', 'section-title')}{simple_table(b, ['མིང', 'ཡིན', 'མིན', 'གསལ་བཤད'], rows)}</section>
        """
        extra = ".form-head{border-bottom:4px solid %s;padding-bottom:14px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:22px}.form-section{border:1.4px solid %s;padding:14px;background:white}.kv{display:grid;grid-template-columns:110px 1fr;gap:10px;border-bottom:1px dotted %s;padding:8px 0}.field-label{font-size:16px;color:%s}.field-value{font-size:20px;line-height:1.3}.check-area{margin-top:20px}td,th{font-size:17px;line-height:1.28}" % (theme["accent"], theme["line"], theme["line"], theme["muted"])
    elif variant == 2:
        body = f"""
        <aside class="form-sidebar">{b.block('metadata', 'REG', 'side-code')}{b.block('metadata', '2026', 'meta')}{b.block('metadata', 'BO', 'meta')}</aside>
        <main class="vertical-form">{b.block('document_title', doc['title'], 'doc-title')}{''.join(kv(b, label, record_title(records, rng, 7, 18), 'line-field') for label in ['མིང', 'ཁ་བྱང', 'ལས་ཁུངས', 'འབྲེལ་བ', 'དོན་ཚན', 'ཡིག་ཨང', 'འགན་ཁུར'])}{b.block('paragraph', record_text(records, rng, 70, 130), 'remark-box')}</main>
        """
        extra = ".page{display:grid;grid-template-columns:140px 1fr;gap:28px}.form-sidebar{background:%s;color:white;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px}.side-code{font-size:44px;font-weight:900;writing-mode:vertical-rl}.vertical-form{padding-top:10px}.line-field{display:grid;grid-template-columns:160px 1fr;border-bottom:1.5px solid %s;padding:14px 0}.field-label{font-size:17px;color:%s}.field-value{font-size:22px}.remark-box{border:1.5px dashed %s;margin-top:24px;padding:16px;font-size:22px;line-height:1.4}" % (theme["accent"], theme["line"], theme["muted"], theme["line"])
    elif variant == 3:
        checks = "".join(f'<div class="check-row">{b.block("option", "□", "box")}{b.block("field_label", record_title(records, rng, 7, 18), "field-label")}{b.block("field_value", record_text(records, rng, 16, 38), "field-value")}</div>' for _ in range(10))
        body = f"""
        <header class="check-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'CHECKLIST', 'stamp')}</header>
        <main class="check-form">{checks}</main>
        """
        extra = ".check-head{display:flex;justify-content:space-between;align-items:end;border-bottom:3px solid %s;padding-bottom:14px}.check-form{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:24px}.check-row{display:grid;grid-template-columns:44px 150px 1fr;gap:10px;align-items:center;border:1.3px solid %s;padding:12px;background:white}.box{font-size:26px;text-align:center}.field-label{font-size:16px;color:%s}.field-value{font-size:19px;line-height:1.28}" % (theme["accent"], theme["line"], theme["muted"])
    elif variant == 4:
        body = f"""
        <header class="folder-head">{b.block('metadata', 'ཡིག་སྣོད', 'tab')}{b.block('document_title', doc['title'], 'doc-title')}</header>
        <main class="folder-form"><section>{sections}</section><aside class="attachment-box">{b.block('section_title', 'ཟུར་སྦྱར', 'section-title')}{''.join(b.block('list_item', record_title(records, rng, 8, 20), 'attach-line') for _ in range(6))}</aside></main>
        """
        extra = ".folder-head{border-top:26px solid %s;border-radius:0;padding-top:16px}.tab{display:inline-block;background:%s;color:white;padding:8px 18px;margin-top:-42px}.folder-form{display:grid;grid-template-columns:1fr 320px;gap:20px;margin-top:24px}.form-section{border-bottom:1.2px solid %s;padding:12px 0}.kv{display:grid;grid-template-columns:100px 1fr;gap:10px}.attachment-box{border:2px solid %s;padding:16px;background:%s}.attach-line{font-size:20px;line-height:1.36;border-bottom:1px dotted %s;padding:8px 0}" % (theme["accent"], theme["accent"], theme["line"], theme["line"], theme["soft"], theme["line"])
    elif variant == 5:
        rows2 = [[record_title(records, rng, 6, 16), record_text(records, rng, 16, 36), "____"] for _ in range(7)]
        body = f"""
        <header class="compact-form-head">{b.block('document_title', doc['title'], 'doc-title')}</header>
        <main class="compact-form">{simple_table(b, ['དོན་ཚན', 'གསལ་བཤད', 'ཐོ་འགོད'], rows2)}<section class="signature-strip">{kv(b, 'ཐམ་ག', '______')}{kv(b, 'ཚེས', '______')}</section></main>
        """
        extra = ".compact-form-head{text-align:center;border-bottom:1.5px solid %s;padding-bottom:12px}.compact-form{margin-top:20px}td,th{font-size:19px;line-height:1.32;padding:12px}.signature-strip{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:22px}.kv{border-top:1px solid %s;padding-top:12px}.field-label{font-size:17px;color:%s}.field-value{font-size:22px}" % (theme["line"], theme["line"], theme["muted"])
    else:
        body = f"""
        <header class="application-head">{b.block('metadata', 'APPLICATION', 'meta')}{b.block('document_title', doc['title'], 'doc-title')}</header>
        <main class="application-form"><section>{''.join(kv(b, record_title(records, rng, 6, 14), '________________', 'wide-field') for _ in range(8))}</section><section class="free-write">{b.block('section_title', 'གསལ་བཤད', 'section-title')}{b.block('paragraph', record_text(records, rng, 70, 130), 'para')}</section></main>
        """
        extra = ".application-head{border-left:10px solid %s;padding-left:18px}.application-form{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:26px}.wide-field{border-bottom:1.4px solid %s;padding:13px 0}.field-label{font-size:17px;color:%s}.field-value{font-size:22px}.free-write{border:1.5px solid %s;padding:18px;background:white}" % (theme["accent"], theme["line"], theme["muted"], theme["line"])
    css = base_css(1120, 1500, theme, doc["font_family"], 22) + extra
    return wrap(doc, body, css, 1120, 1500, "complex-form")


def certificate_proof(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h = (1500, 1060) if variant in (2, 4) else (1120, 1420)
    if variant == 1:
        body = f"""
        <div class="cert-frame classic">
          {b.block('metadata', 'No C-%04d' % (3000 + variant), 'cert-no')}
          {b.block('document_title', doc['title'], 'cert-title')}
          {b.block('field_value', record_title(records, rng, 8, 24), 'recipient')}
          {b.block('paragraph', record_text(records, rng, 100, 190), 'cert-body')}
          <div class="cert-bottom">{b.block('metadata', '2026-06-%02d' % (18 + variant), 'meta')}{b.block('seal', 'ཐམ་ག', 'stamp')}{b.block('metadata', 'སྤྲོད་མཁན', 'meta')}</div>
        </div>
        """
        extra = ".cert-frame{min-height:%dpx;border:12px double %s;padding:58px;text-align:center;display:flex;flex-direction:column;justify-content:center;background:radial-gradient(circle at center, %s 0, white 54%%)}.cert-no{text-align:right}.cert-title{font-size:56px;font-weight:900;line-height:1.32}.recipient{font-size:42px;font-weight:800;border-bottom:2px solid %s;margin:32px auto 20px;padding:0 60px 10px}.cert-body{font-size:27px;line-height:1.48;max-width:900px;margin:0 auto}.cert-bottom{display:grid;grid-template-columns:1fr 160px 1fr;gap:24px;align-items:center;margin-top:44px}" % (page_h - 130, theme["accent"], theme["soft"], theme["line"])
    elif variant == 2:
        body = f"""
        <main class="landscape-cert">
          <aside>{b.block('metadata', 'CERTIFICATE', 'side-word')}{b.block('metadata', 'No C-%04d' % (3000 + variant), 'cert-no')}</aside>
          <section>{b.block('document_title', doc['title'], 'cert-title')}{b.block('field_value', record_title(records, rng, 8, 24), 'recipient')}{b.block('paragraph', record_text(records, rng, 100, 180), 'cert-body')}<div class="cert-bottom">{b.block('metadata', '2026-06-%02d' % (18 + variant), 'meta')}{b.block('seal', 'ཐམ་ག', 'stamp')}</div></section>
        </main>
        """
        extra = ".landscape-cert{min-height:920px;border:8px solid %s;display:grid;grid-template-columns:250px 1fr;background:white}.landscape-cert aside{background:%s;color:white;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:30px}.side-word{writing-mode:vertical-rl;font-size:36px;font-weight:900;letter-spacing:7px}.landscape-cert section{padding:64px;text-align:center;display:flex;flex-direction:column;justify-content:center}.cert-title{font-size:58px;font-weight:900;line-height:1.32}.recipient{font-size:42px;border-bottom:2px solid %s;margin:28px auto;padding:0 70px 10px}.cert-body{font-size:27px;line-height:1.5}.cert-bottom{display:flex;justify-content:center;gap:60px;margin-top:34px}" % (theme["accent"], theme["accent"], theme["line"])
    elif variant == 3:
        fields = "".join(kv(b, label, record_title(records, rng, 8, 20), "proof-kv") for label in ["མིང", "ཡིག་ཨང", "སྤྲོད་ཚེས", "ར་སྤྲོད"])
        body = f"""
        <main class="proof-sheet">{b.block('metadata', 'PROOF SHEET', 'meta')}{b.block('document_title', doc['title'], 'cert-title')}{b.block('paragraph', record_text(records, rng, 120, 200), 'cert-body')}<section class="proof-grid">{fields}</section>{b.block('seal', 'ཐམ་ག', 'stamp')}</main>
        """
        extra = ".proof-sheet{min-height:1260px;border-left:18px solid %s;padding:44px 56px;background:white}.cert-title{font-size:46px;font-weight:900;line-height:1.34;border-bottom:2px solid %s;padding-bottom:14px}.cert-body{font-size:25px;line-height:1.52;margin:28px 0}.proof-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.proof-kv{border:1.4px solid %s;padding:12px}.field-label{font-size:16px;color:%s}.field-value{font-size:23px}.stamp{width:150px;margin:42px 0 0 auto}" % (theme["accent"], theme["line"], theme["line"], theme["muted"])
    elif variant == 4:
        body = f"""
        <main class="compact-proof">
          <section>{b.block('document_title', doc['title'], 'cert-title')}{b.block('field_value', record_title(records, rng, 8, 22), 'recipient')}{b.block('paragraph', record_text(records, rng, 78, 140), 'cert-body')}</section>
          <aside>{b.block('metadata', 'ID %04d' % (9000 + variant), 'cert-no')}{b.block('seal', 'ཐམ་ག', 'stamp')}{b.block('metadata', 'VALID', 'valid-mark')}</aside>
        </main>
        """
        extra = ".compact-proof{min-height:900px;display:grid;grid-template-columns:1fr 320px;gap:28px;border:4px solid %s;padding:52px;background:%s}.compact-proof section{background:white;padding:48px;text-align:left}.compact-proof aside{border-left:3px solid %s;padding-left:28px;display:flex;flex-direction:column;justify-content:space-around;align-items:center}.cert-title{font-size:50px;font-weight:900;line-height:1.36}.recipient{font-size:36px;font-weight:800;margin:28px 0;border-bottom:2px solid %s}.cert-body{font-size:26px;line-height:1.46}.valid-mark{font-size:42px;font-weight:900;color:%s}" % (theme["accent"], theme["soft"], theme["line"], theme["line"], theme["accent"])
    elif variant == 5:
        lines = "".join(f'<div class="number-line">{b.block("metadata", f"{i:02d}", "line-no")}{b.block("field_value", record_text(records, rng, 24, 58), "line-text")}</div>' for i in range(1, 6))
        body = f"""
        <main class="numbered-cert">{b.block('metadata', 'No C-%04d' % (3000 + variant), 'cert-no')}{b.block('document_title', doc['title'], 'cert-title')}{lines}<footer class="cert-footer">{b.block('metadata', '2026-06-%02d' % (18 + variant), 'meta')}{b.block('seal', 'ཐམ་ག', 'stamp')}</footer></main>
        """
        extra = ".numbered-cert{min-height:1260px;border:2px solid %s;padding:44px;background:linear-gradient(45deg,white,%s)}.cert-no{text-align:right}.cert-title{font-size:48px;font-weight:900;line-height:1.36;border-bottom:4px double %s;padding-bottom:16px}.number-line{display:grid;grid-template-columns:70px 1fr;gap:14px;border-bottom:1px dotted %s;padding:16px 0}.line-no{font-size:28px;font-weight:900;color:%s}.line-text{font-size:24px;line-height:1.36}.cert-footer{display:flex;justify-content:space-between;align-items:center;margin-top:38px}" % (theme["line"], theme["soft"], theme["line"], theme["line"], theme["accent"])
    else:
        boxes = "".join(kv(b, record_title(records, rng, 6, 14), record_title(records, rng, 8, 18), "digital-kv") for _ in range(6))
        body = f"""
        <main class="digital-cert"><header>{b.block('document_title', doc['title'], 'cert-title')}{b.block('metadata', 'DIGITAL PROOF', 'meta')}</header><section class="digital-grid">{boxes}</section><aside class="qr-box">{b.block('metadata', 'QR', 'qr-text')}</aside></main>
        """
        extra = ".digital-cert{min-height:1260px;border:1.5px solid %s;padding:36px;background:white}.digital-cert header{display:flex;justify-content:space-between;align-items:end;border-bottom:2px solid %s;padding-bottom:14px}.cert-title{font-size:44px;font-weight:900}.digital-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:26px}.digital-kv{border:1px solid %s;padding:12px;background:%s}.field-label{font-size:16px;color:%s}.field-value{font-size:22px}.qr-box{width:220px;height:220px;border:8px solid %s;margin:40px auto 0;display:flex;align-items:center;justify-content:center}.qr-text{font-size:42px;font-weight:900;color:%s}" % (theme["line"], theme["line"], theme["line"], theme["soft"], theme["muted"], theme["accent"], theme["accent"])
    css = base_css(page_w, page_h, theme, doc["font_family"], 24) + extra
    return wrap(doc, body, css, page_w, page_h, "certificate-proof")


def sign_poster_scene(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    if variant == 1:
        page_w, page_h = 1320, 920
        body = f"""
        <section class="street-sign">{b.block('document_title', record_title(records, rng, 10, 24), 'sign-title')}{b.block('metadata', doc['title'], 'meta')}{b.block('metadata', 'ལམ་བྱང་དཔེ་མཚོན', 'meta')}{b.block('paragraph', record_text(records, rng, 60, 130), 'sign-copy')}</section>
        """
        extra = ".page{padding:54px;background:linear-gradient(145deg,#d8d0c0,#f7f4ea 45%,#c5d1d8)}.street-sign{min-height:760px;border:16px solid #3c5462;background:#fffdf4;box-shadow:18px 18px 0 rgba(30,40,50,.18);display:flex;flex-direction:column;justify-content:center;text-align:center;padding:52px}.sign-title{font-size:78px;font-weight:900;line-height:1.42}.sign-copy{font-size:34px;line-height:1.42;margin-top:26px}"
    elif variant == 2:
        page_w, page_h = 980, 1450
        body = f"""
        <section class="poster-scene">{b.block('image', '', 'image-box')}{b.block('document_title', doc['title'], 'poster-title')}{b.block('paragraph', record_text(records, rng, 90, 170), 'poster-copy')}{''.join(b.block('list_item', record_title(records, rng, 8, 22), 'tag') for _ in range(4))}</section>
        """
        extra = ".poster-scene{min-height:1260px;border-top:18px solid %s;border-bottom:18px solid %s;padding:36px;display:flex;flex-direction:column;justify-content:center}.image-box{min-height:320px;margin-bottom:28px}.poster-title{font-size:62px;font-weight:900;line-height:1.42}.poster-copy{font-size:29px;line-height:1.42;margin:24px 0}.tag{display:inline-block;border:1.5px solid %s;padding:8px 12px;margin:6px;font-size:21px}" % (theme["accent"], theme["accent"], theme["line"])
    elif variant == 3:
        page_w, page_h = 1180, 920
        body = f"""
        <main class="wall-scene"><aside>{b.block('document_title', record_title(records, rng, 8, 22), 'sign-title')}{b.block('paragraph', record_text(records, rng, 55, 110), 'sign-copy')}</aside><section>{b.block('image', '', 'image-box')}{b.block('metadata', 'གྱང་ངོས་ཡི་གེ', 'meta')}</section></main>
        """
        extra = ".page{padding:48px;background:linear-gradient(90deg,#b7b0a0,#e5dfd0)}.wall-scene{display:grid;grid-template-columns:1fr 390px;gap:36px;align-items:center;min-height:800px}.wall-scene aside{background:#fffaf0;border:4px solid #695f50;padding:34px;transform:rotate(-1deg)}.sign-title{font-size:58px;font-weight:900;line-height:1.42}.sign-copy{font-size:28px;line-height:1.42;margin-top:22px}.image-box{min-height:420px;background:#efe8d7}"
    elif variant == 4:
        page_w, page_h = 1380, 860
        tiles = "".join(f'<section class="shop-tile">{b.block("section_title", record_title(records, rng, 7, 18), "tile-title")}{b.block("metadata", record_text(records, rng, 18, 42), "tile-copy")}</section>' for _ in range(4))
        body = f"""
        <main class="shopfront"><header>{b.block('document_title', doc['title'], 'shop-title')}{b.block('metadata', 'SHOP SIGN', 'meta')}</header><section class="shop-tiles">{tiles}</section></main>
        """
        extra = ".page{padding:46px;background:linear-gradient(#c8d4d8,#eef1e7)}.shopfront{min-height:760px;border:10px solid #263238;background:#fffef4;padding:30px;box-shadow:0 20px 0 rgba(40,50,50,.18)}.shopfront header{display:grid;grid-template-columns:1fr 180px;align-items:end;border-bottom:8px solid %s;padding-bottom:18px}.shop-title{font-size:68px;font-weight:900;line-height:1.42}.shop-tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:26px}.shop-tile{background:%s;border:2px solid %s;min-height:230px;padding:18px}.tile-title{font-size:30px;font-weight:900;line-height:1.3}.tile-copy{font-size:18px;line-height:1.35;margin-top:12px}" % (theme["accent"], theme["soft"], theme["line"])
    elif variant == 5:
        page_w, page_h = 1020, 1380
        notices = "".join(b.block("list_item", record_text(records, rng, 28, 64), "flyer-line") for _ in range(7))
        body = f"""
        <section class="event-flyer">{b.block('metadata', 'EVENT', 'event-mark')}{b.block('document_title', doc['title'], 'poster-title')}{b.block('paragraph', record_text(records, rng, 80, 150), 'poster-copy')}<div class="flyer-lines">{notices}</div></section>
        """
        extra = ".event-flyer{min-height:1190px;background:%s;border:6px solid %s;padding:48px;display:flex;flex-direction:column;justify-content:center}.event-mark{font-size:24px;font-weight:900;letter-spacing:4px;color:%s}.poster-title{font-size:68px;font-weight:900;line-height:1.34;margin:24px 0}.poster-copy{font-size:30px;line-height:1.38}.flyer-lines{margin-top:28px}.flyer-line{font-size:23px;line-height:1.34;border-top:1px solid %s;padding:10px 0}" % (theme["soft"], theme["accent"], theme["accent"], theme["line"])
    else:
        page_w, page_h = 1260, 980
        body = f"""
        <main class="package-scene"><section>{b.block('metadata', 'PACKAGE', 'meta')}{b.block('document_title', record_title(records, rng, 9, 22), 'pack-title')}{b.block('paragraph', record_text(records, rng, 54, 110), 'pack-copy')}</section><aside>{b.block('image', '', 'image-box')}{b.block('metadata', doc['title'], 'meta')}</aside></main>
        """
        extra = ".page{padding:56px;background:linear-gradient(135deg,#d3c6b6,#f2eee4)}.package-scene{display:grid;grid-template-columns:1fr 420px;gap:34px;align-items:center;min-height:820px}.package-scene section{border:14px solid %s;background:#fffdf7;padding:44px;transform:rotate(1.5deg)}.pack-title{font-size:60px;font-weight:900;line-height:1.42}.pack-copy{font-size:29px;line-height:1.38;margin-top:22px}.image-box{min-height:420px;background:#f7f3e8}" % theme["accent"]
    css = base_css(page_w, page_h, theme, doc["font_family"], 24) + extra
    return wrap(doc, body, css, page_w, page_h, "sign-poster-scene")


def handwritten_letter(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    doc = {**doc, "font_family": '"Local Jomolhari", Kailasa, "Local Noto Serif Tibetan", serif'}
    lines = [record_text(records, rng, 34, 86) for _ in range(12)]
    if variant == 1:
        body = f"""
        <section class="paper-note ruled">
          <header>{b.block('metadata', '2026-06-%02d' % (10 + variant), 'meta')}{b.block('document_title', doc['title'], 'hand-title')}</header>
          <main>{''.join(b.block('paragraph', line, 'hand-line') for line in lines)}</main>
          {b.block('signature', record_title(records, rng, 8, 18), 'signature')}
        </section>
        """
        extra = ".page{background:#e7e1d0;padding:70px}.paper-note{min-height:1360px;background:#fffdf1;border:1px solid #c8bea9;box-shadow:10px 12px 0 rgba(70,60,45,.10);padding:54px 62px;transform:rotate(-1deg)}.hand-title{font-size:36px;font-weight:700;line-height:1.55;border-bottom:1px solid #d4c8ae;padding-bottom:12px}.hand-line{font-size:28px;line-height:1.82;border-bottom:1px solid rgba(140,130,110,.38);margin:0;min-height:48px}.signature{text-align:right;font-size:30px;margin-top:32px}"
    elif variant == 2:
        body = f"""
        <section class="letter-sheet">{b.block('metadata', record_title(records, rng, 8, 18), 'recipient')}{b.block('document_title', doc['title'], 'hand-title')}{''.join(b.block('paragraph', line, 'letter-line') for line in lines[:8])}{b.block('signature', record_title(records, rng, 8, 18), 'signature')}</section>
        """
        extra = ".page{background:#ddd8cc;padding:62px}.letter-sheet{min-height:1300px;background:#fffaf0;border-left:10px solid %s;padding:58px 70px;box-shadow:0 10px 24px rgba(60,50,40,.16)}.recipient{font-size:24px;color:%s}.hand-title{font-size:39px;line-height:1.58;margin:20px 0}.letter-line{font-size:29px;line-height:1.68;text-indent:2em;margin-bottom:8px}.signature{text-align:right;font-size:31px;margin-top:42px}" % (theme["accent"], theme["muted"])
    elif variant == 3:
        body = f"""
        <main class="notebook-page"><aside>{b.block('metadata', 'NOTE', 'note-mark')}</aside><section>{''.join(b.block('paragraph', line, 'note-line') for line in lines)}</section></main>
        """
        extra = ".page{background:#dcdfe4;padding:64px}.notebook-page{min-height:1320px;background:repeating-linear-gradient(#fffefa,#fffefa 47px,#d6dce5 48px);display:grid;grid-template-columns:120px 1fr;border:1px solid #b8bdc6}.notebook-page aside{border-right:3px double #d45b5b;display:flex;align-items:center;justify-content:center}.note-mark{writing-mode:vertical-rl;font-size:34px;font-weight:900;color:#b84a4a}.notebook-page section{padding:38px 46px}.note-line{font-size:26px;line-height:1.82;margin:0 0 4px}"
    elif variant == 4:
        body = f"""
        <section class="sticky-board">{b.block('document_title', doc['title'], 'hand-title')}{b.block('metadata', 'ལག་བྲིས་ཟིན་ཐོ', 'meta')}{b.block('metadata', 'memo board', 'meta')}{''.join(f'<div class="sticky">{b.block("paragraph", record_text(records, rng, 28, 70), "sticky-line")}</div>' for _ in range(7))}</section>
        """
        extra = ".page{background:#c9c3b6;padding:54px}.sticky-board{min-height:1320px;background:#f4efe1;border:10px solid #7a6b58;padding:38px;display:grid;grid-template-columns:1fr 1fr;gap:18px;align-content:start}.hand-title{grid-column:1/-1;font-size:39px;font-weight:800;line-height:1.55}.sticky{min-height:220px;background:#fff6b8;padding:22px;box-shadow:6px 8px 0 rgba(70,60,40,.12);transform:rotate(-1deg)}.sticky:nth-child(2n){background:#dff1ff;transform:rotate(1deg)}.sticky-line{font-size:25px;line-height:1.45}"
    elif variant == 5:
        body = f"""
        <section class="diary-page">{b.block('metadata', 'Diary 06/%02d' % (10 + variant), 'meta')}{b.block('document_title', doc['title'], 'hand-title')}{''.join(b.block('paragraph', line, 'diary-line') for line in lines[:10])}</section>
        """
        extra = ".page{background:#e2dac9;padding:76px}.diary-page{min-height:1260px;background:#fffdf5;border:1px solid #c4b89e;padding:46px 58px;border-radius:0 24px 24px 0;box-shadow:14px 0 0 #d7cbb4}.hand-title{font-size:34px;line-height:1.58;color:%s}.diary-line{font-size:27px;line-height:1.72;margin:0 0 10px;border-bottom:1px dotted #c8bea6}" % theme["accent"]
    else:
        body = f"""
        <section class="memo-note"><header>{b.block('metadata', 'MEMO', 'memo-tag')}{b.block('document_title', doc['title'], 'hand-title')}</header>{''.join(b.block('paragraph', line, 'memo-line') for line in lines[:9])}{b.block('signature', record_title(records, rng, 8, 18), 'signature')}</section>
        """
        extra = ".page{background:#ddd5ca;padding:68px}.memo-note{min-height:1320px;background:#fffaf2;padding:50px 60px;border-top:12px solid %s;transform:rotate(.8deg)}.memo-note header{display:flex;justify-content:space-between;align-items:end;border-bottom:2px solid %s;padding-bottom:12px}.memo-tag{font-size:30px;font-weight:900;color:%s}.hand-title{font-size:36px;line-height:1.58}.memo-line{font-size:28px;line-height:1.62;margin-bottom:12px}.signature{text-align:right;font-size:30px;margin-top:36px}" % (theme["accent"], theme["line"], theme["accent"])
    css = base_css(1040, 1500, theme, doc["font_family"], 24) + extra
    return wrap(doc, body, css, 1040, 1500, "handwritten-letter")


GENERATORS: Dict[str, Callable[[Builder, List[Dict[str, str]], random.Random, Dict[str, str], int, Dict[str, str]], str]] = {
    "book_page": book_page,
    "textbook_page": textbook_page,
    "newspaper_page": newspaper_page,
    "magazine_journal": magazine_journal,
    "academic_paper": academic_paper,
    "historical_classic": historical_classic,
    "notice_announcement": notice_announcement,
    "exam_paper": exam_paper,
    "complex_form": complex_form,
    "certificate_proof": certificate_proof,
    "sign_poster_scene": sign_poster_scene,
    "handwritten_letter": handwritten_letter,
}


def page_size_for(category: str, variant: int) -> Tuple[int, int]:
    if category == "newspaper_page":
        return 1240, 1754
    if category == "magazine_journal" and variant in (3, 6):
        return 1280, 1500
    if category == "certificate_proof" and variant in (2, 5):
        return 1500, 1060
    if category == "certificate_proof" and variant == 4:
        return 1500, 1060
    if category == "certificate_proof":
        return 1120, 1420
    if category == "sign_poster_scene" and variant in (1, 4):
        return (1380, 860) if variant == 4 else (1320, 920)
    if category == "sign_poster_scene" and variant in (2, 5):
        return 980, 1450
    if category == "sign_poster_scene":
        return (1260, 980) if variant == 6 else (1180, 920)
    if category in {"book_page", "textbook_page", "academic_paper", "exam_paper"}:
        return 1160, 1580
    if category == "handwritten_letter":
        return 1040, 1500
    return 1120, 1500


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--language-profile")
    parser.add_argument("--per-category", type=int, default=6)
    parser.add_argument("--min-records", type=int, default=40)
    parser.add_argument("--seed", type=int, default=2026063021)
    parser.add_argument("--categories", nargs="*", default=None)
    args = parser.parse_args()

    language_profile = load_language_profile(Path(args.language_profile) if args.language_profile else None)
    records = read_text_records(Path(args.text_jsonl), language_profile, args.min_records)
    out_dir = Path(args.output_dir)
    html_dir = out_dir / "html"
    meta_dir = out_dir / "metadata"
    html_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    selected_categories = set(args.categories) if args.categories else None
    filtered = [(c, cn) for c, cn in CATEGORIES if selected_categories is None or c in selected_categories]
    if not filtered:
        raise RuntimeError("no categories selected")

    manifest = []
    for cat_idx, (category, category_cn) in enumerate(filtered, 1):
        generator = GENERATORS[category]
        for variant in range(1, args.per_category + 1):
            document_id = f"{cat_idx:02d}_{category}_{variant:02d}"
            b = Builder(document_id)
            theme = THEMES[(cat_idx + variant - 2) % len(THEMES)]
            title = TITLE_BY_CATEGORY[category]
            if variant in (2, 5):
                title = f"{title} {record_title(records, rng, 8, 20)}"
            doc = {
                "document_id": document_id,
                "title": f"{language_profile.get('title_prefix', '')}{cleanse_text(title)}",
                "html_lang": language_profile["html_lang"],
                "font_family": language_profile["font_family"],
            }
            html_text = generator(b, records, rng, theme, variant, doc)
            (html_dir / f"{document_id}.html").write_text(html_text, encoding="utf-8")
            page_w, page_h = page_size_for(category, variant)
            manifest.append(
                {
                    "document_id": document_id,
                    "title": doc["title"],
                    "category": category,
                    "category_cn": category_cn,
                    "variant": variant,
                    "layout_name": f"{category}_variant_{variant}",
                    "template_type": category,
                    "generator": f"layout_spec_aligned_{language_profile.get('language_code', 'bo')}",
                    "doc_no": f"{cat_idx:02d}-{variant:02d}",
                    "date": now_local()[:10],
                    "page_width": page_w,
                    "page_height": page_h,
                    "rows": None,
                    "columns": None,
                    "created_at": now_local(),
                    "source_records": [],
                }
            )

    (meta_dir / "html_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (meta_dir / "category_plan.json").write_text(
        json.dumps([{"category": c, "category_cn": cn, "samples": args.per_category} for c, cn in filtered], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"generated {len(manifest)} html files across {len(filtered)} categories in {html_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
