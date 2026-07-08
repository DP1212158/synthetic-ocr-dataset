#!/usr/bin/env python3
"""Generate Zhuang reading-page categories from structured JSON templates."""

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
TIBETAN_RE = re.compile(r"[\u0f00-\u0fff]")
ZERO_WIDTH_CONTROL_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]")
PROJECT_ROOT = Path(__file__).resolve().parents[1]

THEMES = [
    {"ink": "#232629", "muted": "#68707a", "line": "#b6bec7", "accent": "#315f72", "paper": "#fffefa", "soft": "#f1f5f6"},
    {"ink": "#2b2521", "muted": "#786a60", "line": "#c9bdae", "accent": "#8a5738", "paper": "#fffdf6", "soft": "#f7efe3"},
    {"ink": "#1f2a22", "muted": "#617164", "line": "#b7c5bb", "accent": "#356b52", "paper": "#fcfff8", "soft": "#eef7ef"},
    {"ink": "#292530", "muted": "#6d6675", "line": "#c0b8ca", "accent": "#5b5f94", "paper": "#fdfcff", "soft": "#f2f0f8"},
]


def now_local() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def cleanse_text(text: str) -> str:
    text = ZERO_WIDTH_CONTROL_RE.sub("", str(text or ""))
    text = CYRILLIC_RE.sub("", text)
    text = CJK_RE.sub("", text)
    text = TIBETAN_DECORATIVE_MARK_RE.sub(" ", text)
    text = TIBETAN_SHAD_RE.sub(" ", text)
    text = TIBETAN_RE.sub(" ", text)
    text = text.replace("།", " ").replace("...", " ")
    return " ".join(text.split())


def tibetan_font_faces() -> str:
    regular = Path("/System/Library/Fonts/Supplemental/Arial.ttf").resolve().as_uri()
    bold = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf").resolve().as_uri()
    unicode_font = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf").resolve().as_uri()
    return f"""
    @font-face {{ font-family: 'Local Arial'; src: url('{regular}') format('truetype'); font-weight: 400; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Arial'; src: url('{bold}') format('truetype'); font-weight: 700 900; font-style: normal; font-display: block; }}
    @font-face {{ font-family: 'Local Arial Unicode'; src: url('{unicode_font}') format('truetype'); font-weight: 400; font-style: normal; font-display: block; }}
    """


def load_language_profile(path: Path | None) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8")) if path else {}
    profile.setdefault("language_code", "za")
    profile.setdefault("language_name", "壮语")
    profile.setdefault("script_note", "现代标准壮文 Vahcuengh，拉丁字母拼写")
    profile.setdefault("html_lang", "za")
    profile.setdefault("script_regex", r"[A-Za-z]")
    profile.setdefault("min_script_ratio", 0.45)
    profile.setdefault("font_family", "\"Local Arial\", \"Local Arial Unicode\", Arial, Helvetica, sans-serif")
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
        raise RuntimeError(f"not enough text records in {path}: {len(records)}")
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
    words = text.split()
    if len(words) > 8:
        start = rng.randint(0, max(0, len(words) - 6))
        out: list[str] = []
        for word in words[start:]:
            candidate = " ".join(out + [word])
            if len(candidate) > max_len:
                break
            out.append(word)
            if len(candidate) >= min_len:
                return cleanse_text(candidate)
    return clip(text, min_len, max_len)


def record_text(records: list[dict[str, str]], rng: random.Random, min_len: int, max_len: int) -> str:
    pool = [rec for rec in records if len(rec["text"]) >= min_len] or records
    return select_span(rng.choice(pool)["text"], rng, min_len, max_len)


def record_title(records: list[dict[str, str]], rng: random.Random, min_len: int = 8, max_len: int = 30) -> str:
    rec = rng.choice(records)
    title = cleanse_text(rec["title"])
    if title and re.search(r"[A-Za-z]", title) and min_len <= len(title) <= max_len:
        return title
    return select_span(rec["text"], rng, min_len, max_len)


def fallback_text(label: str) -> str:
    return shared_fallback_text(label)


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


def base_css(page: dict[str, Any], theme: dict[str, str], font_family: str, base: int = 21, profile: dict[str, Any] | None = None) -> str:
    profile = profile or {}
    css_direction = profile.get("css_direction", profile.get("writing_direction", "ltr"))
    css_writing_mode = profile.get("css_writing_mode", "horizontal-tb")
    css_text_align = profile.get("css_text_align", "right" if css_direction == "rtl" else "left")
    vertical_extra = shared_vertical_css(profile, base)
    return tibetan_font_faces() + f"""
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: #d9dde2; }}
    body {{ font-family: {font_family}; color: {theme['ink']}; direction: {css_direction}; writing-mode: {css_writing_mode}; text-align: {css_text_align}; unicode-bidi: plaintext; }}
    .page {{ width: {int(page['width'])}px; min-height: {int(page['height'])}px; margin: 0 auto; padding: 54px 62px 44px; background: {theme['paper']}; position: relative; overflow: hidden; direction: {css_direction}; writing-mode: {css_writing_mode}; text-align: {css_text_align}; }}
    [data-block-id] {{ overflow: visible; }}
    .running-header {{ display: flex; justify-content: space-between; border-bottom: 1.5px solid {theme['line']}; padding-bottom: 8px; margin-bottom: 26px; }}
    .doc-title {{ font-size: {base + 22}px; line-height: 1.66; font-weight: 900; }}
    .chapter-title {{ font-size: {base + 16}px; line-height: 1.66; font-weight: 900; margin: 18px 0 20px; }}
    .section-title {{ font-size: {base + 1}px; line-height: 1.62; font-weight: 900; color: {theme['accent']}; }}
    .meta {{ font-size: {base - 5}px; line-height: 1.7; color: {theme['muted']}; }}
    .para {{ font-size: {base - 1}px; line-height: 1.72; margin: 0 0 12px; }}
    .small {{ font-size: {base - 4}px; line-height: 1.66; }}
    .folio {{ position: absolute; left: 62px; right: 62px; bottom: 18px; border-top: 1px solid {theme['line']}; padding-top: 6px; text-align: center; color: {theme['muted']}; font-size: {base - 5}px; line-height: 1.7; }}
    .image-box {{ min-height: 260px; background: repeating-linear-gradient(135deg, #dfd9ce, #dfd9ce 12px, #f5f0e8 12px, #f5f0e8 24px); border: 1.4px solid {theme['line']}; }}
    .caption {{ font-size: {base - 4}px; line-height: 1.28; color: {theme['muted']}; margin-top: 8px; }}
    .rule {{ height: 1px; background: {theme['line']}; margin: 16px 0; }}
    {vertical_extra}
    """


def wrap(doc: dict[str, Any], body: str, css: str, cls: str) -> str:
    return f"""<!doctype html>
<html lang="{esc(doc['html_lang'])}" dir="{esc(str(doc.get('css_direction', doc.get('writing_direction', 'ltr'))))}">
<head><meta charset="utf-8"><title>{esc(doc['title'])}</title><style>{css}</style></head>
<body><main class="page {cls}" data-template-id="{esc(doc['template_id'])}">{body}</main></body>
</html>
"""


def para_stack(b: Builder, records: list[dict[str, str]], rng: random.Random, count: int, min_len: int, max_len: int, cls: str = "para") -> str:
    return "".join(b.block("paragraph", record_text(records, rng, min_len, max_len), cls) for _ in range(count))


def book_renderer(b: Builder, tpl: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any], theme: dict[str, str]) -> str:
    v = int(tpl["variant"])
    page = tpl["page"]
    if v == 1:
        body = f"""<header class="running-header">{b.block('metadata', 'Sawbon Neiyungz', 'meta')}{b.block('metadata', '023', 'meta')}</header>
        {b.block('document_title', record_title(records, rng, 10, 24), 'chapter-title')}
        <section class="book-columns">{para_stack(b, records, rng, 24, 96, 185)}</section>
        {b.block('page_number', '23', 'folio')}"""
        extra = f""".book-columns{{columns:2;column-gap:34px;column-rule:1px solid {theme['line']};}} .book-columns .para{{break-inside:avoid;font-size:18px;line-height:1.44;margin-bottom:8px;}}"""
    elif v == 2:
        notes = "".join(b.block("note", record_text(records, rng, 32, 72), "margin-note") for _ in range(8))
        reading_map = "".join(f'<section class="reading-map-item">{b.block("metadata", f"{i:02d}", "map-no")}{b.block("note", record_text(records, rng, 34, 72), "small")}</section>' for i in range(1, 9))
        body = f"""<section class="opener"><div>{b.block('metadata', 'Chapter 02', 'chapter-no')}{b.block('document_title', record_title(records, rng, 12, 28), 'opener-title')}{b.block('document_subtitle', record_text(records, rng, 56, 100), 'epigraph')}</div><aside>{notes}</aside></section>
        <section class="opening-text">{para_stack(b, records, rng, 14, 72, 132)}</section><section class="reading-map">{reading_map}</section>{b.block('page_number', '24', 'folio')}"""
        extra = f""".opener{{display:grid;grid-template-columns:1fr 300px;gap:30px;align-items:end;min-height:310px;border-bottom:3px double {theme['line']};padding-bottom:18px;}}.chapter-no{{font-size:28px;font-weight:900;color:{theme['accent']};}}.opener-title{{font-size:54px;font-weight:900;line-height:1.34;}}.epigraph{{font-size:21px;line-height:1.36;color:{theme['muted']};margin-top:12px;}}.margin-note{{padding:6px 0 6px 10px;margin-bottom:8px;font-size:15px;line-height:1.36;color:{theme['muted']};}}.opening-text{{margin-top:20px;columns:2;column-gap:28px;}}.opening-text .para{{font-size:17px;line-height:1.4;margin-bottom:8px;}}.reading-map{{display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;border-top:1.5px solid {theme['line']};margin-top:18px;padding-top:12px;}}.reading-map-item{{display:grid;grid-template-columns:42px 1fr;gap:8px;border-bottom:1px dotted {theme['line']};padding-bottom:6px;}}.map-no{{font-size:18px;font-weight:900;color:{theme['accent']};}}"""
    elif v == 3:
        side_notes = "".join(f'<section class="figure-note">{b.block("metadata", f"{i:02d}", "meta")}{b.block("note", record_text(records, rng, 32, 66), "small")}</section>' for i in range(1, 6))
        followups = "".join(f'<section class="followup">{b.block("section_title", record_title(records, rng, 7, 16), "section-title")}{b.block("paragraph", record_text(records, rng, 48, 92), "small")}</section>' for _ in range(8))
        body = f"""<header class="running-header">{b.block('metadata', 'Doxgoj Doxgangj', 'meta')}{b.block('metadata', '031', 'meta')}</header>
        <section class="illustrated"><main>{b.block('section_title', record_title(records, rng, 9, 24), 'section-title')}{para_stack(b, records, rng, 18, 82, 150)}</main><aside>{b.block('image', '', 'image-box')}{b.block('caption', record_text(records, rng, 34, 72), 'caption')}{side_notes}</aside></section><section class="followups">{followups}</section>{b.block('page_number', '31', 'folio')}"""
        extra = f""".illustrated{{display:grid;grid-template-columns:1fr 360px;gap:28px;}}.illustrated main{{columns:2;column-gap:22px;}}.illustrated main .para{{font-size:18px;line-height:1.43;margin-bottom:8px;}}.illustrated .image-box{{height:340px;}}.figure-note{{border-top:1px dotted {theme['line']};padding-top:8px;margin-top:8px;}}.followups{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:18px;border-top:1.5px solid {theme['line']};padding-top:14px;}}.followup{{background:{theme['soft']};border:1px solid {theme['line']};padding:10px;min-height:150px;}}.followup .section-title{{font-size:16px;}}.followup .small{{font-size:13px;line-height:1.28;}}"""
    elif v == 4:
        notes = "".join(f'<section class="side-note">{b.block("section_title", record_title(records, rng, 7, 16), "section-title")}{b.block("note", record_text(records, rng, 36, 78), "small")}</section>' for _ in range(12))
        body = f"""<header class="running-header">{b.block('metadata', 'Saw Doxduz', 'meta')}{b.block('metadata', '042', 'meta')}</header>
        <section class="marginalia"><main>{b.block('document_title', record_title(records, rng, 10, 24), 'chapter-title')}{para_stack(b, records, rng, 20, 75, 145)}</main><aside>{notes}</aside></section>{b.block('page_number', '42', 'folio')}"""
        extra = f""".marginalia{{display:grid;grid-template-columns:1fr 270px;gap:28px;}}.marginalia main{{columns:2;column-gap:24px;}}.marginalia main .para{{font-size:17px;line-height:1.38;margin-bottom:7px;}}.side-note{{border-top:2px solid {theme['accent']};padding-top:6px;margin-bottom:9px;}}.side-note .section-title{{font-size:16px;}}.side-note .small{{font-size:13px;line-height:1.26;}}"""
    elif v == 5:
        entries = []
        for i in range(1, 25):
            entries.append(f'<div class="toc-row">{b.block("section_title", f"{i:02d}  " + record_title(records, rng, 8, 22), "toc-title")}{b.block("note", record_text(records, rng, 22, 58), "toc-desc")}{b.block("page_number", str(8 + i * 3), "toc-page")}</div>')
        body = f"""{b.block('document_title', 'Muluq', 'contents-title')}<section class="toc">{''.join(entries)}</section>"""
        extra = f""".contents-title{{font-size:52px;font-weight:900;text-align:center;border-bottom:4px double {theme['line']};padding-bottom:16px;margin-bottom:18px;}}.toc{{display:grid;grid-template-columns:1fr 1fr;gap:7px 30px;}}.toc-row{{display:grid;grid-template-columns:1fr 48px;gap:8px;border-bottom:1px dotted {theme['line']};padding:6px 0;}}.toc-title{{font-size:18px;font-weight:900;line-height:1.28;}}.toc-desc{{grid-column:1/2;font-size:14px;color:{theme['muted']};line-height:1.24;}}.toc-page{{grid-column:2;grid-row:1/3;text-align:right;font-size:18px;color:{theme['accent']};font-weight:900;}}"""
    else:
        extracts = []
        for i in range(8):
            extracts.append(f'<section class="extract">{b.block("section_title", record_title(records, rng, 8, 22), "section-title")}{b.block("quote", record_text(records, rng, 100, 170), "quote")}{b.block("metadata", "Ndaej " + str(i + 1), "meta")}</section>')
        body = f"""{b.block('document_title', 'Duz Cawx', 'doc-title')}<div class="rule"></div><section class="extracts">{''.join(extracts)}</section>{b.block('page_number', '56', 'folio')}"""
        extra = f""".extracts{{display:grid;grid-template-columns:1fr 1fr;gap:14px 16px;}}.extract{{border-left:7px solid {theme['accent']};padding:12px 16px;background:{theme['soft']};min-height:210px;}}.quote{{font-size:17px;line-height:1.36;}}.extract .section-title{{font-size:18px;}}"""
    return wrap(doc, body, base_css(page, theme, doc["font_family"], 21, doc) + extra, "book-page")


def textbook_renderer(b: Builder, tpl: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any], theme: dict[str, str]) -> str:
    v = int(tpl["variant"])
    page = tpl["page"]
    if v == 1:
        points = "".join(f'<section class="point">{b.block("section_title", f"{i}. " + record_title(records, rng, 7, 18), "section-title")}{b.block("paragraph", record_text(records, rng, 58, 112), "small")}</section>' for i in range(1, 12))
        exercises = "".join(f'<section class="mini-ex">{b.block("question", f"{i}. " + record_text(records, rng, 34, 72), "small")}</section>' for i in range(1, 7))
        body = f"""<header class="lesson-head">{b.block('metadata', 'Lesson 01', 'lesson-no')}{b.block('document_title', record_title(records, rng, 10, 26), 'doc-title')}</header><main class="lesson-grid"><section>{points}{b.block('section_title', 'Laiqyangh', 'section-title')}{para_stack(b, records, rng, 5, 70, 130)}<div class="mini-ex-wrap">{exercises}</div></section><aside class="key-box">{b.block('section_title', 'Gyaezdawz', 'section-title')}{para_stack(b, records, rng, 10, 38, 82, 'small')}</aside></main>{b.block('page_number', '12', 'folio')}"""
        extra = f""".lesson-head{{border-left:16px solid {theme['accent']};padding-left:18px;border-bottom:2px solid {theme['line']};padding-bottom:16px;}}.lesson-no{{font-size:28px;font-weight:900;color:{theme['accent']};}}.lesson-grid{{display:grid;grid-template-columns:1fr 300px;gap:24px;margin-top:20px;}}.point{{border-bottom:1px solid {theme['line']};padding:6px 0;}}.point .section-title{{font-size:18px;line-height:1.35;}}.point .small{{font-size:15px;line-height:1.38;}}.key-box{{background:{theme['soft']};border:1.5px solid {theme['line']};padding:14px;}}.key-box .small{{font-size:15px;line-height:1.38;}}.mini-ex-wrap{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px;}}.mini-ex{{border-top:1px dotted {theme['line']};padding-top:6px;}}"""
    elif v == 2:
        qs = []
        for i in range(1, 33):
            qs.append(f'<section class="exercise">{b.block("question", f"{i}. " + record_text(records, rng, 36, 76), "question")}{b.block("answer_area", " ", "answer-line")}</section>')
        body = f"""<header class="exercise-head">{b.block('document_title', 'Lienh Cienx', 'doc-title')}{b.block('metadata', 'Answer area is reserved', 'meta')}</header><main class="exercise-cols">{''.join(qs)}</main>{b.block('note', record_text(records, rng, 50, 90), 'hint')}{b.block('page_number', '18', 'folio')}"""
        extra = f""".exercise-head{{display:flex;justify-content:space-between;align-items:end;border-bottom:3px double {theme['line']};padding-bottom:14px;}}.exercise-cols{{columns:2;column-gap:28px;margin-top:16px;}}.exercise{{break-inside:avoid;min-height:78px;margin-bottom:8px;padding-bottom:4px;}}.question{{font-size:15px;line-height:1.28;}}.answer-line{{height:42px;border-bottom:1.5px solid {theme['line']};background:linear-gradient(transparent 31px,{theme['soft']} 32px);}}.hint{{position:absolute;left:62px;right:62px;bottom:54px;background:{theme['soft']};padding:10px;font-size:15px;}}"""
    elif v == 3:
        calls = "".join(f'<section class="callout"><b>{i}</b>{b.block("note", record_text(records, rng, 36, 72), "small")}</section>' for i in range(1, 11))
        concept_cards = "".join(f'<section class="concept-card">{b.block("section_title", record_title(records, rng, 6, 14), "section-title")}{b.block("paragraph", record_text(records, rng, 34, 70), "small")}</section>' for _ in range(6))
        body = f"""{b.block('document_title', record_title(records, rng, 10, 24), 'doc-title')}<section class="diagram-page"><div>{b.block('image', '', 'image-box')}{b.block('caption', record_text(records, rng, 36, 76), 'caption')}{para_stack(b, records, rng, 5, 54, 105, 'small')}</div><aside>{calls}</aside></section><section class="summary-box">{b.block('section_title', 'Mboqdoengh', 'section-title')}{para_stack(b, records, rng, 6, 60, 110, 'small')}</section><section class="concept-grid">{concept_cards}</section>"""
        extra = f""".diagram-page{{display:grid;grid-template-columns:1fr 330px;gap:24px;margin-top:18px;}}.diagram-page .image-box{{height:410px;}}.callout{{display:grid;grid-template-columns:38px 1fr;gap:8px;border-bottom:1px dotted {theme['line']};padding:6px 0;}}.callout b{{font-size:24px;color:{theme['accent']};}}.summary-box{{margin-top:16px;border:1.5px solid {theme['line']};background:{theme['soft']};padding:12px;}}.summary-box .small,.callout .small{{font-size:14px;line-height:1.32;}}.concept-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px;}}.concept-card{{border:1px solid {theme['line']};padding:10px;background:white;min-height:118px;}}.concept-card .section-title{{font-size:16px;}}.concept-card .small{{font-size:13px;line-height:1.28;}}"""
    elif v == 4:
        entries = "".join(f'<section class="term">{b.block("section_title", record_title(records, rng, 5, 14), "term-head")}{b.block("paragraph", record_text(records, rng, 42, 86), "small")}{b.block("note", record_text(records, rng, 22, 48), "example")}</section>' for _ in range(16))
        body = f"""<header class="vocab-head">{b.block('document_title', 'Sawmingz Gaej', 'doc-title')}{b.block('metadata', 'A - B', 'meta')}</header><main class="terms">{entries}</main>{b.block('page_number', '27', 'folio')}"""
        extra = f""".vocab-head{{display:flex;justify-content:space-between;align-items:end;border-bottom:4px solid {theme['accent']};padding-bottom:12px;}}.terms{{columns:2;column-gap:28px;margin-top:22px;}}.term{{break-inside:avoid;border-bottom:1px solid {theme['line']};padding:8px 0;}}.term-head{{font-size:21px;font-weight:900;color:{theme['accent']};}}.example{{font-size:15px;color:{theme['muted']};line-height:1.24;}}"""
    elif v == 5:
        steps = "".join(f'<section class="step">{b.block("metadata", f"{i:02d}", "step-no")}{b.block("paragraph", record_text(records, rng, 44, 88), "small")}</section>' for i in range(1, 11))
        body = f"""<header class="activity-head">{b.block('metadata', 'Activity', 'meta')}{b.block('document_title', record_title(records, rng, 10, 24), 'doc-title')}</header><main class="activity-grid"><section>{b.block('section_title', 'Gongzcoz', 'section-title')}{para_stack(b, records, rng, 5, 65, 115)}{b.block('section_title', 'Guhfaz', 'section-title')}{steps}</section><aside>{b.block('section_title', 'Yawjndaej', 'section-title')}{para_stack(b, records, rng, 8, 30, 64, 'small')}{b.block('answer_area', ' ', 'observation')}</aside></main>"""
        extra = f""".activity-head{{background:{theme['soft']};border:2px solid {theme['line']};padding:18px;}}.activity-grid{{display:grid;grid-template-columns:1fr 340px;gap:24px;margin-top:20px;}}.step{{display:grid;grid-template-columns:50px 1fr;gap:10px;border-bottom:1px dotted {theme['line']};padding:6px 0;}}.step-no{{font-size:24px;font-weight:900;color:{theme['accent']};}}.step .small,.activity-grid .para,.activity-grid aside .small{{font-size:15px;line-height:1.38;}}.observation{{height:420px;border:1.5px dashed {theme['line']};background:repeating-linear-gradient(white,white 34px,{theme['soft']} 35px);margin-top:18px;}}"""
    else:
        blocks = "".join(f'<section class="review-card">{b.block("section_title", record_title(records, rng, 7, 17), "section-title")}{b.block("paragraph", record_text(records, rng, 38, 74), "small")}</section>' for _ in range(16))
        checks = "".join(b.block("list_item", record_text(records, rng, 22, 50), "check-line") for _ in range(16))
        body = f"""{b.block('document_title', 'Review Lesson', 'doc-title')}<main class="review-layout"><section class="review-grid">{blocks}</section><aside class="check-box">{b.block('section_title', 'Self Check', 'section-title')}{checks}</aside></main>{b.block('page_number', '38', 'folio')}"""
        extra = f""".review-layout{{display:grid;grid-template-columns:1fr 270px;gap:20px;margin-top:18px;}}.review-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}.review-card{{border:1.4px solid {theme['line']};padding:8px;background:white;min-height:106px;}}.review-card .section-title{{font-size:15px;}}.review-card .small{{font-size:13px;line-height:1.28;}}.check-box{{background:{theme['soft']};border-left:8px solid {theme['accent']};padding:12px;}}.check-line{{font-size:13px;border-bottom:1px dotted {theme['line']};padding:5px 0;line-height:1.24;}}"""
    return wrap(doc, body, base_css(page, theme, doc["font_family"], 21, doc) + extra, "textbook-page")


def magazine_renderer(b: Builder, tpl: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any], theme: dict[str, str]) -> str:
    v = int(tpl["variant"])
    page = tpl["page"]
    if v == 1:
        shorts = "".join(f'<section class="short-block">{b.block("section_title", record_title(records, rng, 7, 18), "section-title")}{b.block("paragraph", record_text(records, rng, 40, 80), "small")}</section>' for _ in range(12))
        lower_cards = "".join(
            f'<section class="feature-card">{b.block("metadata", f"{i:02d}", "card-no")}{b.block("section_title", record_title(records, rng, 7, 18), "section-title")}{b.block("paragraph", record_text(records, rng, 46, 90), "small")}</section>'
            for i in range(1, 7)
        )
        body = f"""<section class="feature-open"><div>{b.block('image', '', 'image-box')}{b.block('caption', record_text(records, rng, 28, 62), 'caption')}{para_stack(b, records, rng, 12, 42, 88, 'small')}</div><main>{b.block('metadata', 'FEATURE', 'mag-label')}{b.block('document_title', record_title(records, rng, 10, 28), 'feature-title')}{b.block('document_subtitle', record_text(records, rng, 70, 130), 'deck')}{shorts}</main></section><section class="feature-bottom">{lower_cards}</section>"""
        extra = f""".feature-open{{display:grid;grid-template-columns:500px 1fr;gap:28px;align-items:start;}}.feature-open .image-box{{height:430px;}}.mag-label{{font-size:20px;font-weight:900;color:{theme['accent']};letter-spacing:0;}}.feature-title{{font-size:48px;font-weight:900;line-height:1.32;}}.deck{{font-size:19px;color:{theme['muted']};line-height:1.34;margin:12px 0;}}.short-block{{border-top:2px solid {theme['line']};padding-top:6px;margin-top:7px;}}.short-block .section-title{{font-size:17px;}}.short-block .small,.feature-open div .small{{font-size:13px;line-height:1.28;}}.feature-bottom{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:22px;border-top:4px solid {theme['accent']};padding-top:16px}}.feature-card{{border:1.4px solid {theme['line']};background:{theme['soft']};padding:10px;min-height:130px}}.card-no{{font-size:20px;font-weight:900;color:{theme['accent']}}}.feature-card .section-title{{font-size:16px;line-height:1.26}}.feature-card .small{{font-size:13px;line-height:1.28}}"""
    elif v == 2:
        lines = "".join(b.block("list_item", record_title(records, rng, 8, 22), "cover-line") for _ in range(12))
        departments = "".join(f'<section class="cover-dept">{b.block("section_title", record_title(records, rng, 6, 14), "section-title")}{b.block("paragraph", record_text(records, rng, 30, 62), "small")}</section>' for _ in range(4))
        body = f"""<section class="cover-page">{b.block('metadata', '2026 / 07', 'issue')}{b.block('document_title', doc['title'], 'journal-name')}{b.block('image', '', 'cover-visual')}{b.block('document_subtitle', record_title(records, rng, 12, 30), 'cover-title')}<aside>{lines}</aside><section class="cover-depts">{departments}</section></section>"""
        extra = f""".cover-page{{min-height:1280px;border:18px solid {theme['accent']};padding:32px;position:relative;background:{theme['soft']};}}.issue{{text-align:right;font-size:22px;font-weight:900;}}.journal-name{{font-size:48px;font-weight:900;}}.cover-visual{{height:330px;margin:18px 0;background:repeating-linear-gradient(135deg,#d8dedb,#d8dedb 14px,#f9f6ea 14px,#f9f6ea 28px);border:1.5px solid {theme['line']};}}.cover-title{{font-size:46px;font-weight:900;line-height:1.34;}}.cover-line{{font-size:17px;line-height:1.32;border-top:1px solid {theme['line']};padding:7px 0;}}.cover-depts{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:18px;}}.cover-dept{{border:1px solid {theme['line']};background:rgba(255,255,255,.55);padding:10px;}}.cover-dept .section-title{{font-size:17px;}}.cover-dept .small{{font-size:14px;line-height:1.32;}}"""
    elif v == 3:
        body = f"""<section class="landscape"><div>{b.block('image', '', 'image-box')}{b.block('caption', record_text(records, rng, 38, 78), 'caption')}</div><article>{b.block('metadata', 'PHOTO ESSAY', 'mag-label')}{b.block('document_title', record_title(records, rng, 10, 26), 'land-title')}<section class="land-cols">{para_stack(b, records, rng, 6, 62, 118)}</section></article></section>"""
        extra = f""".page{{padding:48px 54px;}}.landscape{{display:grid;grid-template-columns:650px 1fr;gap:32px;align-items:center;min-height:820px;}}.landscape .image-box{{height:620px;}}.land-title{{font-size:52px;font-weight:900;line-height:1.35;margin:12px 0 18px;}}.land-cols{{columns:2;column-gap:22px;}}.land-cols .para{{font-size:18px;line-height:1.38;}}"""
    elif v == 4:
        entries = "".join(f'<section class="journal-entry">{b.block("metadata", f"{10+i*3}", "entry-page")}{b.block("section_title", record_title(records, rng, 8, 22), "section-title")}{b.block("paragraph", record_text(records, rng, 34, 74), "small")}</section>' for i in range(18))
        body = f"""{b.block('document_title', 'Muluq', 'contents-title')}{b.block('metadata', 'Vol. 07', 'meta')}<main class="journal-contents">{entries}</main>"""
        extra = f""".contents-title{{font-size:52px;font-weight:900;border-bottom:8px solid {theme['accent']};padding-bottom:12px;}}.journal-contents{{display:grid;grid-template-columns:1fr 1fr;gap:9px 24px;margin-top:18px;}}.journal-entry{{display:grid;grid-template-columns:54px 1fr;gap:8px;border-bottom:1px solid {theme['line']};padding-bottom:7px;}}.journal-entry .section-title{{font-size:17px;}}.journal-entry .small{{font-size:14px;line-height:1.28;}}.entry-page{{font-size:23px;font-weight:900;color:{theme['accent']};grid-row:1/3;}}"""
    elif v == 5:
        subheads = "".join(f'<section class="side-digest">{b.block("section_title", record_title(records, rng, 6, 14), "section-title")}{b.block("paragraph", record_text(records, rng, 28, 56), "small")}</section>' for _ in range(6))
        body = f"""<header class="column-head">{b.block('metadata', 'COLUMN', 'mag-label')}{b.block('document_title', record_title(records, rng, 10, 28), 'doc-title')}{b.block('metadata', 'Author / 2026', 'meta')}</header>{b.block('quote', record_text(records, rng, 58, 105), 'pull-quote')}<main class="column-layout"><article class="article-cols">{para_stack(b, records, rng, 38, 58, 112)}</article><aside>{subheads}</aside></main>{b.block('page_number', '64', 'folio')}"""
        extra = f""".column-head{{text-align:center;border-bottom:3px double {theme['line']};padding-bottom:14px;}}.pull-quote{{font-size:24px;line-height:1.34;color:{theme['accent']};border-left:10px solid {theme['accent']};padding:10px 16px;margin:14px 40px;background:{theme['soft']};}}.column-layout{{display:grid;grid-template-columns:1fr 245px;gap:18px;}}.article-cols{{columns:2;column-gap:20px;}}.article-cols .para{{font-size:15px;line-height:1.3;margin-bottom:5px;}}.side-digest{{border-top:2px solid {theme['accent']};padding-top:7px;margin-bottom:10px;}}.side-digest .section-title{{font-size:15px;}}.side-digest .small{{font-size:12px;line-height:1.22;}}"""
    else:
        modules = "".join(f'<section class="module m{i}">{b.block("section_title", record_title(records, rng, 7, 18), "section-title")}{b.block("paragraph", record_text(records, rng, 34, 78), "small")}{b.block("metadata", "No " + str(i), "meta")}</section>' for i in range(1, 13))
        body = f"""<header class="module-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'INFO MIX', 'mag-label')}</header><main class="modules">{b.block('image', '', 'visual-block')}{modules}</main>"""
        extra = f""".module-head{{display:flex;justify-content:space-between;align-items:end;border-bottom:3px solid {theme['line']};padding-bottom:14px;}}.modules{{display:grid;grid-template-columns:1.2fr 1fr 1fr;grid-auto-rows:minmax(128px,auto);gap:12px;margin-top:18px;}}.visual-block{{grid-row:span 2;min-height:290px;background:repeating-linear-gradient(135deg,#dfe3de,#dfe3de 12px,#f5efe6 12px,#f5efe6 24px);border:1.5px solid {theme['line']};}}.module{{border:1.4px solid {theme['line']};background:{theme['soft']};padding:11px;}}.module .section-title{{font-size:17px;}}.module .small{{font-size:14px;line-height:1.28;}}.m4,.m9{{grid-column:span 2;}}"""
    return wrap(doc, body, base_css(page, theme, doc["font_family"], 21, doc) + extra, "magazine-page")


RENDERERS: dict[str, Callable[..., str]] = {
    "book_page": book_renderer,
    "textbook_page": textbook_renderer,
    "magazine_journal": magazine_renderer,
}


def safe_name(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def validate_spec(spec: dict[str, Any]) -> None:
    if spec.get("schema_version") != "category_layout_templates.v1":
        raise RuntimeError("unsupported template schema")
    categories = spec.get("categories")
    if not isinstance(categories, list) or len(categories) != 3:
        raise RuntimeError("reading pages spec must contain exactly 3 categories")
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


from synthetic_text_utils import (  # noqa: E402
    cleanse_text,
    clip,
    fallback_text as shared_fallback_text,
    load_language_profile,
    read_text_records,
    record_text,
    record_title,
    select_span,
    vertical_css as shared_vertical_css,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-jsonl", required=True)
    parser.add_argument("--templates-json", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--language-profile")
    parser.add_argument("--start-index", type=int, default=5)
    parser.add_argument("--min-records", type=int, default=40)
    parser.add_argument("--seed", type=int, default=2026070105)
    parser.add_argument("--version-name")
    args = parser.parse_args()

    profile = load_language_profile(Path(args.language_profile) if args.language_profile else None)
    records = read_text_records(Path(args.text_jsonl), profile, args.min_records)
    spec = json.loads(Path(args.templates_json).read_text(encoding="utf-8"))
    validate_spec(spec)
    version_name = args.version_name or Path(args.output_root).name

    rng = random.Random(args.seed)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
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
                    "css_direction": profile.get("css_direction", profile.get("writing_direction", "ltr")),
                    "css_writing_mode": profile.get("css_writing_mode", "horizontal-tb"),
                    "writing_direction": profile.get("writing_direction", "ltr"),
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
                    "generator": "reading_pages_json_renderer_za_v1",
                    "doc_no": f"ZA-{version_name.upper()}-{args.start_index + offset:02d}-{variant:02d}",
                    "date": now_local()[:10],
                    "page_width": int(page["width"]),
                    "page_height": int(page["height"]),
                    "preserve_full_page": bool(tpl.get("preserve_full_page", False)),
                    "tight_crop": bool(tpl.get("tight_crop", False)),
                    "rows": None,
                    "columns": None,
                    "created_at": now_local(),
                    "source_records": [],
                    "content_density": tpl.get("content_density"),
                }
            )
        write_json(folder / "metadata" / "html_manifest.json", html_manifest)
        write_json(folder / "metadata" / "category_plan.json", [{"category": category_id, "category_cn": category_cn, "samples": 6}])
        write_json(folder / "metadata" / "reading_pages_template_spec.json", {"category": cat, "source_schema": spec["schema_version"]})
        (folder / "README.md").write_text(
            f"# {args.start_index + offset:02d} {category_cn}\n\n本目录属于壮语 `{version_name}`，由阅读型页面 JSON 结构树生成，共 6 张。\n\n- `html/`\n- `images/`\n- `labels/`\n- `metadata/`\n- `reports/`\n",
            encoding="utf-8",
        )
        written.append(str(folder))

    print(json.dumps({"generated_category_dirs": written}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
