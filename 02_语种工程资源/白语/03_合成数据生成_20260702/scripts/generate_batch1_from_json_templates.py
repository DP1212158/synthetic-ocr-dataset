#!/usr/bin/env python3
"""Generate Zhuang certificate, exam, and sign layouts from category JSON templates."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import random
import re
import shutil
from pathlib import Path
from typing import Any


CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
TIBETAN_DECORATIVE_MARK_RE = re.compile(r"[\u0f04-\u0f0a\u0f0c\u0f0e-\u0f14\u0f3a-\u0f3d]")
TIBETAN_SHAD_RE = re.compile(r"\s*།+\s*")
TIBETAN_RE = re.compile(r"[\u0f00-\u0fff]")
ZERO_WIDTH_CONTROL_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]")
PROJECT_ROOT = Path(__file__).resolve().parents[1]

THEMES = [
    {"ink": "#202326", "muted": "#656b72", "line": "#b8bec6", "accent": "#2c5f78", "paper": "#fffefa", "soft": "#f3f6f8"},
    {"ink": "#2b2420", "muted": "#75665c", "line": "#c9bbae", "accent": "#8a4e2d", "paper": "#fffdf5", "soft": "#f8f0e5"},
    {"ink": "#1d2a21", "muted": "#66766b", "line": "#b3c4b8", "accent": "#366b51", "paper": "#fcfff9", "soft": "#eef7f0"},
    {"ink": "#27222b", "muted": "#6d6574", "line": "#bbb3c8", "accent": "#5e5b90", "paper": "#fdfcff", "soft": "#f2f0f8"},
]


def now_local() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def cleanse_text(text: str) -> str:
    text = ZERO_WIDTH_CONTROL_RE.sub("", str(text or ""))
    text = CYRILLIC_RE.sub("", text)
    text = TIBETAN_DECORATIVE_MARK_RE.sub(" ", text)
    text = TIBETAN_SHAD_RE.sub(" ", text)
    text = TIBETAN_RE.sub(" ", text)
    text = text.replace("།", " ")
    text = text.replace("...", " ")
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


def read_text_records(path: Path, language_profile: dict[str, Any], min_records: int) -> list[dict[str, str]]:
    records = []
    script_re = re.compile(str(language_profile["script_regex"]))
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
        start = rng.randint(0, max(0, len(words) - 5))
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

    def block(self, label: str, text: str, cls: str, tag: str = "div", attrs: str = "") -> str:
        cleaned = cleanse_text(text)
        if not cleaned and label != "image":
            cleaned = fallback_text(label)
        return f'<{tag} class="{cls}" data-block-id="{self.bid()}" data-label="{label}" {attrs}>{esc(cleaned)}</{tag}>'


def base_css(page: dict[str, Any], theme: dict[str, str], font_family: str, base_size: int = 23, profile: dict[str, Any] | None = None) -> str:
    profile = profile or {}
    css_direction = profile.get("css_direction", profile.get("writing_direction", "ltr"))
    css_writing_mode = profile.get("css_writing_mode", "horizontal-tb")
    css_text_align = profile.get("css_text_align", "right" if css_direction == "rtl" else "left")
    vertical_extra = shared_vertical_css(profile, base_size)
    return tibetan_font_faces() + f"""
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: #d9dde2; }}
    body {{ font-family: {font_family}; color: {theme['ink']}; direction: {css_direction}; writing-mode: {css_writing_mode}; text-align: {css_text_align}; unicode-bidi: plaintext; }}
    .page {{ width: {int(page['width'])}px; min-height: {int(page['height'])}px; margin: 0 auto; padding: 50px; background: {theme['paper']}; position: relative; overflow: hidden; direction: {css_direction}; writing-mode: {css_writing_mode}; text-align: {css_text_align}; }}
    [data-block-id] {{ overflow: visible; }}
    .doc-title {{ font-size: {base_size + 24}px; line-height: 1.38; font-weight: 900; }}
    .section-title {{ font-size: {base_size + 3}px; line-height: 1.36; font-weight: 900; color: {theme['accent']}; }}
    .meta {{ font-size: {base_size - 5}px; line-height: 1.32; color: {theme['muted']}; }}
    .para {{ font-size: {base_size}px; line-height: 1.46; margin: 0 0 12px; }}
    .small {{ font-size: {base_size - 3}px; line-height: 1.34; }}
    .field-label {{ font-size: {base_size - 6}px; color: {theme['muted']}; line-height: 1.25; }}
    .field-value {{ font-size: {base_size - 1}px; line-height: 1.34; }}
    .image-box {{ background: repeating-linear-gradient(135deg, #ded8ca, #ded8ca 12px, #f3eee4 12px, #f3eee4 24px); border: 1.5px solid {theme['line']}; }}
    .stamp {{ border: 3px solid {theme['accent']}; color: {theme['accent']}; font-weight: 900; text-align: center; padding: 12px 18px; transform: rotate(-6deg); }}
    .seal-circle {{ width: 150px; height: 150px; border: 5px double {theme['accent']}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: {theme['accent']}; font-weight: 900; margin: 0 auto; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    td, th {{ border: 1px solid {theme['line']}; padding: 8px; font-size: {base_size - 5}px; line-height: 1.28; vertical-align: top; }}
    {vertical_extra}
    """


def wrap(doc: dict[str, Any], body: str, css: str, page: dict[str, Any], cls: str) -> str:
    return f"""<!doctype html>
<html lang="{esc(doc['html_lang'])}" dir="{esc(str(doc.get('css_direction', doc.get('writing_direction', 'ltr'))))}">
<head><meta charset="utf-8"><title>{esc(doc['title'])}</title><style>{css}</style></head>
<body><main class="page {cls}" data-template-id="{esc(doc['template_id'])}">{body}</main></body>
</html>
"""


def kv(b: Builder, label: str, value: str, cls: str = "kv") -> str:
    return f'<div class="{cls}">{b.block("field_label", label, "field-label")}{b.block("field_value", value, "field-value")}</div>'


def simple_table(b: Builder, headers: list[str], rows: list[list[str]]) -> str:
    head = "<tr>" + "".join(b.block("table_header", h, "", "th") for h in headers) + "</tr>"
    body = "".join("<tr>" + "".join(b.block("table_cell_text", cell, "", "td") for cell in row) + "</tr>" for row in rows)
    return f"<table>{head}{body}</table>"


def certificate_renderer(b: Builder, template: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any], theme: dict[str, str]) -> str:
    v = int(template["variant"])
    page = template["page"]
    if v == 1:
        body = f"""<section class="award-cert">
          {b.block('metadata', f"No C-{3000+v:04d}", 'meta cert-no')}
          {b.block('document_title', doc['title'], 'doc-title cert-title')}
          {b.block('field_value', record_title(records, rng, 8, 22), 'recipient')}
          {b.block('paragraph', record_text(records, rng, 120, 210), 'para cert-body')}
          <footer>{b.block('metadata', '2026-07-01', 'meta')}{b.block('seal', 'Caiq', 'seal-circle')}{b.block('metadata', 'Giz cungj', 'meta')}</footer>
        </section>"""
        extra = f""".award-cert{{min-height:900px;border:12px double {theme['accent']};padding:58px;text-align:center;display:flex;flex-direction:column;justify-content:center;background:radial-gradient(circle,#fff 0,{theme['soft']} 62%,#fff 100%)}}.cert-no{{text-align:right}}.cert-title{{font-size:66px}}.recipient{{font-size:44px;font-weight:900;border-bottom:2px solid {theme['line']};margin:32px auto 22px;padding:0 90px 12px}}.cert-body{{max-width:950px;margin:0 auto;font-size:29px}}.award-cert footer{{display:grid;grid-template-columns:1fr 170px 1fr;gap:28px;align-items:center;margin-top:50px}}"""
    elif v == 2:
        fields = "".join(kv(b, label, record_title(records, rng, 8, 18), "proof-kv") for label in ["Mingz", "Bienhhao", "Ngoenz", "Cingmingz"])
        clauses = "".join(
            f'<section class="proof-clause">{b.block("metadata", f"{i:02d}", "clause-no")}{b.block("paragraph", record_text(records, rng, 56, 108), "small")}</section>'
            for i in range(1, 7)
        )
        body = f"""<section class="formal-proof">
          <header>{b.block('metadata', f"Proof {7200+v}", 'meta')}{b.block('document_title', doc['title'], 'doc-title')}</header>
          {b.block('paragraph', record_text(records, rng, 160, 270), 'para proof-body')}
          <section class="proof-grid">{fields}</section>
          <section class="proof-clauses">{clauses}</section>
          <footer>{b.block('metadata', '2026-07-01', 'meta')}{b.block('metadata', f"ZA-{7200+v}", 'meta')}{b.block('seal', 'Caiq', 'stamp')}</footer>
        </section>"""
        extra = f""".formal-proof{{min-height:1280px;border-left:18px solid {theme['accent']};background:white;padding:44px 56px}}.formal-proof header{{border-bottom:2px solid {theme['line']};padding-bottom:16px}}.proof-body{{font-size:27px;line-height:1.54;margin:30px 0 24px}}.proof-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.proof-kv{{border:1.4px solid {theme['line']};padding:12px;background:{theme['soft']}}}.proof-clauses{{margin-top:28px;border-top:2px solid {theme['line']};padding-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:8px 18px}}.proof-clause{{display:grid;grid-template-columns:42px 1fr;gap:8px;border-bottom:1px dotted {theme['line']};padding:7px 0}}.clause-no{{font-size:19px;font-weight:900;color:{theme['accent']}}}.proof-clause .small{{font-size:16px;line-height:1.34}}.formal-proof footer{{display:flex;justify-content:flex-end;gap:34px;align-items:center;margin-top:38px}}"""
    elif v == 3:
        body = f"""<section class="ornamental-cert">
          <div class="inner-frame">{b.block('metadata', f"No A-{9100+v}", 'meta')}{b.block('document_title', doc['title'], 'doc-title')}
          {b.block('field_value', record_title(records, rng, 8, 22), 'recipient')}
          {b.block('paragraph', record_text(records, rng, 100, 180), 'para')}
          <div class="seal-row">{b.block('seal', 'Caiq', 'seal-circle')}{b.block('metadata', '2026-07-01', 'meta')}</div></div>
        </section>"""
        extra = f""".ornamental-cert{{min-height:900px;border:18px solid {theme['accent']};padding:28px;background:{theme['soft']};text-align:center}}.inner-frame{{min-height:808px;border:6px double {theme['line']};background:white;padding:56px;display:flex;flex-direction:column;justify-content:center}}.recipient{{font-size:42px;font-weight:900;margin:28px auto;border-bottom:2px solid {theme['line']};padding:0 70px 10px}}.seal-row{{display:flex;justify-content:center;align-items:center;gap:60px;margin-top:36px}}"""
    elif v == 4:
        body = f"""<section class="credential-card">
          <aside>{b.block('metadata', f"ID {9000+v}", 'meta')}{b.block('seal', 'Caiq', 'seal-circle')}</aside>
          <main>{b.block('document_title', doc['title'], 'doc-title')}{b.block('field_value', record_title(records, rng, 8, 20), 'recipient')}{b.block('paragraph', record_text(records, rng, 95, 170), 'para')}</main>
          <footer>{kv(b, 'VALID', '2026-2028')}{kv(b, 'CODE', f'B{6200+v}')}</footer>
        </section>"""
        extra = f""".credential-card{{min-height:820px;border:4px solid {theme['accent']};background:{theme['soft']};display:grid;grid-template-columns:260px 1fr;grid-template-rows:1fr auto;gap:24px;padding:46px}}.credential-card aside{{background:{theme['accent']};color:white;display:flex;flex-direction:column;justify-content:center;gap:32px;padding:24px}}.credential-card main{{background:white;padding:52px}}.credential-card footer{{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr;gap:18px}}.recipient{{font-size:36px;font-weight:900;margin:24px 0;border-bottom:2px solid {theme['line']}}}"""
    elif v == 5:
        rows = "".join(f'<div class="number-line">{b.block("metadata", f"{i:02d}", "line-no")}{b.block("field_value", record_text(records, rng, 34, 76), "field-value")}</div>' for i in range(1, 9))
        body = f"""<section class="proof-list">{b.block('metadata', f"No C-{3000+v:04d}", 'meta')}{b.block('document_title', doc['title'], 'doc-title')}{rows}<footer>{b.block('metadata', '2026-07-01', 'meta')}{b.block('seal', 'Caiq', 'stamp')}</footer></section>"""
        extra = f""".proof-list{{min-height:1280px;border:2px solid {theme['line']};padding:44px;background:linear-gradient(45deg,white,{theme['soft']})}}.proof-list .doc-title{{border-bottom:4px double {theme['line']};padding-bottom:16px}}.number-line{{display:grid;grid-template-columns:70px 1fr;gap:14px;border-bottom:1px dotted {theme['line']};padding:18px 0}}.line-no{{font-size:30px;font-weight:900;color:{theme['accent']}}}.proof-list footer{{display:flex;justify-content:space-between;align-items:center;margin-top:42px}}"""
    else:
        boxes = "".join(kv(b, record_title(records, rng, 6, 14), record_title(records, rng, 8, 18), "digital-kv") for _ in range(6))
        body = f"""<section class="digital-cert"><header>{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'DIGITAL PROOF', 'meta')}</header><section class="digital-grid">{boxes}</section><aside class="qr-box">{b.block('metadata', 'QR', 'qr-text')}</aside></section>"""
        extra = f""".digital-cert{{min-height:820px;border:1.5px solid {theme['line']};padding:36px;background:white}}.digital-cert header{{display:flex;justify-content:space-between;align-items:end;border-bottom:2px solid {theme['line']};padding-bottom:14px}}.digital-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:28px}}.digital-kv{{border:1px solid {theme['line']};padding:12px;background:{theme['soft']}}}.qr-box{{width:210px;height:210px;border:8px solid {theme['accent']};margin:38px auto 0;display:flex;align-items:center;justify-content:center}}.qr-text{{font-size:42px;font-weight:900;color:{theme['accent']}}}"""
    return wrap(doc, body, base_css(page, theme, doc["font_family"], 24, doc) + extra, page, "certificate-page")


def mcq(b: Builder, records: list[dict[str, str]], rng: random.Random, start: int, count: int) -> str:
    items = []
    for i in range(start, start + count):
        options = "".join(b.block("option", f"{chr(64+j)}  {record_title(records, rng, 6, 16)}", "option") for j in range(1, 5))
        items.append(f'<section class="question">{b.block("question", f"{i}. " + record_text(records, rng, 34, 78), "question-text")}<div class="options">{options}</div></section>')
    return "".join(items)


def exam_renderer(b: Builder, template: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any], theme: dict[str, str]) -> str:
    v = int(template["variant"])
    page = template["page"]
    if v == 1:
        body = f"""<header class="exam-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata', 'Seizgan 90 min    Score 100', 'meta')}</header><div class="student-line">{kv(b,'Mingz','________')}{kv(b,'Hauh','________')}{kv(b,'Ban','________')}</div><main class="exam-cols">{mcq(b, records, rng, 1, 14)}</main>"""
        extra = f""".exam-head{{text-align:center;border-bottom:3px double {theme['line']};padding-bottom:14px}}.student-line{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin:18px 0}}.kv{{border-bottom:1.5px solid {theme['line']};padding:8px}}.exam-cols{{columns:2;column-gap:28px}}.question{{break-inside:avoid;border-bottom:1px solid {theme['line']};padding-bottom:9px;margin-bottom:11px}}.question-text{{font-size:19px;line-height:1.36}}.options{{display:grid;grid-template-columns:1fr 1fr;gap:5px 10px;margin-top:7px}}.option{{font-size:16px;line-height:1.3}}"""
    elif v == 2:
        passages = "".join(f'<section class="reading-block">{b.block("section_title", f"Part {i}", "section-title")}{b.block("paragraph", record_text(records, rng, 130, 220), "passage")}{mcq(b, records, rng, i*3-2, 3)}</section>' for i in range(1, 4))
        body = f"""<header class="reading-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata','Reading / comprehension','meta')}</header><main>{passages}</main>"""
        extra = f""".reading-head{{border-left:12px solid {theme['accent']};padding-left:18px;margin-bottom:18px}}.reading-block{{border:1.4px solid {theme['line']};padding:15px;background:white;margin-bottom:16px}}.passage{{font-size:19px;line-height:1.42;margin-bottom:10px}}.question{{margin-top:7px}}.question-text{{font-size:17px;line-height:1.3}}.options{{display:grid;grid-template-columns:1fr 1fr;gap:4px 8px}}.option{{font-size:15px}}"""
    elif v == 3:
        bubbles = "".join(f'<div class="bubble-row">{b.block("metadata", f"{i:02d}", "bubble-no")}<span>A</span><span>B</span><span>C</span><span>D</span></div>' for i in range(1, 41))
        body = f"""<header class="answer-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata','ANSWER SHEET','meta')}</header><section class="student-line">{kv(b,'Mingz','________')}{kv(b,'Hauh','________')}</section><main class="answer-sheet">{bubbles}</main><section class="short-answer">{b.block('section_title','Dap an','section-title')}{''.join(b.block('answer_area',' ','answer-line') for _ in range(5))}</section>"""
        extra = f""".answer-head{{display:flex;justify-content:space-between;align-items:end;border-bottom:3px solid {theme['line']};padding-bottom:14px}}.student-line{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:18px 0}}.answer-sheet{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px 14px}}.bubble-row{{display:grid;grid-template-columns:42px repeat(4,34px);gap:6px;align-items:center;border-bottom:1px dotted {theme['line']};padding:5px 0}}.bubble-row span{{border:1.4px solid {theme['line']};border-radius:50%;height:26px;text-align:center;font-size:14px;line-height:24px}}.answer-line{{height:38px;border-bottom:1.5px solid {theme['line']}}}"""
    elif v == 4:
        questions = "".join(f'<section class="essay-q">{b.block("question", f"{i}. " + record_text(records, rng, 54, 104), "question-text")}{b.block("answer_area"," ","essay-area")}</section>' for i in range(1, 4))
        rubric = "".join(b.block("list_item", record_title(records, rng, 8, 18), "rubric-line") for _ in range(10))
        body = f"""<header class="essay-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata','Daezmoq Gijman','meta')}</header><main class="essay-layout"><section>{questions}</section><aside class="rubric-box">{b.block('section_title','Gijbiz','section-title')}{rubric}</aside></main>{b.block('metadata','Score and review notes are placed at the end of the paper.','meta essay-foot')}"""
        extra = f""".essay-head{{border-bottom:2px solid {theme['line']};padding-bottom:14px;margin-bottom:18px}}.essay-layout{{display:grid;grid-template-columns:1fr 260px;gap:20px}}.essay-q{{margin-bottom:18px}}.question-text{{font-size:21px;line-height:1.36;border-left:7px solid {theme['accent']};padding-left:14px}}.essay-area{{height:265px;border:1.5px dashed {theme['line']};background:repeating-linear-gradient(white,white 34px,{theme['soft']} 35px);margin-top:10px}}.rubric-box{{border:1.4px solid {theme['line']};padding:12px;background:{theme['soft']}}}.rubric-line{{font-size:17px;line-height:1.26;border-bottom:1px dotted {theme['line']};padding:6px 0}}.essay-foot{{position:absolute;left:50px;right:50px;bottom:28px;border-top:1px solid {theme['line']};padding-top:8px;text-align:right}}"""
    elif v == 5:
        rows = [[str(i), record_text(records, rng, 24, 52), "____"] for i in range(1, 11)]
        body = f"""<header class="score-head">{b.block('document_title', doc['title'], 'doc-title')}{b.block('metadata','Score Review','meta')}</header><main class="score-layout"><section>{mcq(b, records, rng, 1, 8)}</section><aside>{simple_table(b,['No','Gijman','Score'],rows)}</aside></main>"""
        extra = f""".score-head{{display:flex;justify-content:space-between;align-items:end;border-bottom:4px solid {theme['accent']};padding-bottom:12px}}.score-layout{{display:grid;grid-template-columns:1fr 360px;gap:22px;margin-top:22px}}.question{{border-bottom:1px solid {theme['line']};padding-bottom:10px;margin-bottom:12px}}.question-text{{font-size:19px;line-height:1.34}}.options{{display:grid;grid-template-columns:1fr 1fr;gap:5px}}.option{{font-size:15px}}"""
    else:
        cards = "".join(f'<section class="oral-card">{b.block("section_title", record_title(records, rng, 8, 20), "section-title")}{b.block("question", record_text(records, rng, 48, 92), "question-text")}{b.block("answer_area", " ", "answer-box")}</section>' for _ in range(6))
        body = f"""<header class="oral-head">{b.block('metadata','Oral / Practice','meta')}{b.block('document_title', doc['title'], 'doc-title')}</header><main class="oral-grid">{cards}</main>"""
        extra = f""".oral-head{{text-align:center;border-top:8px solid {theme['accent']};border-bottom:1px solid {theme['line']};padding:16px 0}}.oral-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-top:24px}}.oral-card{{border:1.5px solid {theme['line']};padding:14px;background:{theme['soft']};min-height:250px}}.question-text{{font-size:19px;line-height:1.34}}.answer-box{{height:70px;border:1px dashed {theme['line']};background:white;margin-top:12px}}"""
    return wrap(doc, body, base_css(page, theme, doc["font_family"], 22, doc) + extra, page, "exam-page")


def sign_renderer(b: Builder, template: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any], theme: dict[str, str]) -> str:
    v = int(template["variant"])
    page = template["page"]
    if v == 1:
        arrows = "".join(b.block("metadata", label, "route-chip") for label in ["A-01", "B-02", "Loux", "Heuz"])
        body = f"""<section class="street-scene"><div class="sign-board">{b.block('document_title', record_title(records,rng,10,24), 'sign-title')}{b.block('metadata','Loux Byaij','meta')}{b.block('paragraph', record_text(records,rng,60,130), 'sign-copy')}<div class="route-row">{arrows}</div></div></section>"""
        extra = """.page{background:linear-gradient(145deg,#c9d2d7,#f4f1e8 50%,#b8b0a2)}.street-scene{min-height:760px;display:flex;align-items:center;justify-content:center}.sign-board{width:1040px;border:18px solid #314a58;background:#fffdf4;box-shadow:20px 22px 0 rgba(30,40,50,.18);padding:58px;text-align:center}.sign-title{font-size:82px;font-weight:900;line-height:1.4}.sign-copy{font-size:34px;line-height:1.42;margin-top:24px}.route-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:24px}.route-chip{padding:10px;font-size:22px;font-weight:900;text-decoration:underline;text-underline-offset:5px}"""
    elif v == 2:
        tags = "".join(b.block("list_item", record_title(records, rng, 8, 20), "tag") for _ in range(5))
        body = f"""<section class="event-poster">{b.block('image','','image-box')}{b.block('metadata','EVENT','event-mark')}{b.block('document_title',doc['title'],'poster-title')}{b.block('paragraph',record_text(records,rng,95,175),'poster-copy')}<div>{tags}</div></section>"""
        extra = f""".event-poster{{min-height:1260px;border-top:20px solid {theme['accent']};border-bottom:20px solid {theme['accent']};padding:38px;display:flex;flex-direction:column;justify-content:center}}.image-box{{min-height:320px;margin-bottom:28px}}.event-mark{{font-size:24px;font-weight:900;color:{theme['accent']}}}.poster-title{{font-size:66px;font-weight:900;line-height:1.36;margin:22px 0}}.poster-copy{{font-size:30px;line-height:1.42}}.tag{{display:inline-block;padding:8px 12px;margin:6px;font-size:21px;font-weight:700;color:{theme['accent']}}}"""
    elif v == 3:
        notes = "".join(f'<section class="wall-note">{b.block("section_title", record_title(records,rng,8,20), "section-title")}{b.block("paragraph", record_text(records,rng,42,90), "small")}</section>' for _ in range(5))
        body = f"""<section class="wall-board">{notes}<aside>{b.block('image','','image-box')}{b.block('metadata','Byaij Mbwn','meta')}</aside></section>"""
        extra = """.page{background:linear-gradient(90deg,#b7b0a0,#e5dfd0)}.wall-board{display:grid;grid-template-columns:1fr 1fr 360px;gap:22px;align-items:start;min-height:760px}.wall-note{background:#fffaf0;border:4px solid #695f50;padding:24px;box-shadow:8px 10px 0 rgba(70,60,50,.12)}.wall-note:nth-child(2n){transform:rotate(.8deg)}.wall-note:nth-child(2n+1){transform:rotate(-.7deg)}.image-box{height:430px;background:#efe8d7}"""
    elif v == 4:
        tiles = "".join(f'<section class="shop-tile">{b.block("section_title", record_title(records,rng,7,18), "tile-title")}{b.block("metadata", record_text(records,rng,20,46), "tile-copy")}</section>' for _ in range(5))
        body = f"""<main class="shopfront"><header>{b.block('document_title',doc['title'],'shop-title')}{b.block('metadata','SHOP SIGN','meta')}</header><section class="shop-tiles">{tiles}</section></main>"""
        extra = f""".page{{background:linear-gradient(#c8d4d8,#eef1e7)}}.shopfront{{min-height:740px;border:10px solid #263238;background:#fffef4;padding:30px;box-shadow:0 20px 0 rgba(40,50,50,.18)}}.shopfront header{{display:grid;grid-template-columns:1fr 180px;align-items:end;border-bottom:8px solid {theme['accent']};padding-bottom:18px}}.shop-title{{font-size:70px;font-weight:900;line-height:1.42}}.shop-tiles{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-top:26px}}.shop-tile{{background:{theme['soft']};border:2px solid {theme['line']};min-height:230px;padding:18px}}.tile-title{{font-size:29px;font-weight:900;line-height:1.3}}.tile-copy{{font-size:18px;line-height:1.35;margin-top:12px}}"""
    elif v == 5:
        lines = "".join(b.block("list_item", record_text(records, rng, 30, 70), "flyer-line") for _ in range(9))
        body = f"""<section class="flyer">{b.block('metadata','INFO','event-mark')}{b.block('document_title',doc['title'],'poster-title')}{b.block('paragraph',record_text(records,rng,90,160),'poster-copy')}<div class="flyer-lines">{lines}</div></section>"""
        extra = f""".flyer{{min-height:1190px;background:{theme['soft']};border:6px solid {theme['accent']};padding:48px;display:flex;flex-direction:column;justify-content:center}}.event-mark{{font-size:24px;font-weight:900;color:{theme['accent']}}}.poster-title{{font-size:66px;font-weight:900;line-height:1.34;margin:22px 0}}.poster-copy{{font-size:30px;line-height:1.38}}.flyer-line{{font-size:23px;line-height:1.34;border-top:1px solid {theme['line']};padding:10px 0}}"""
    else:
        body = f"""<main class="package-scene"><section>{b.block('metadata','PACKAGE','meta')}{b.block('document_title',record_title(records,rng,9,22),'pack-title')}{b.block('paragraph',record_text(records,rng,58,118),'pack-copy')}</section><aside>{b.block('image','','image-box')}{b.block('metadata',doc['title'],'meta')}</aside></main>"""
        extra = f""".page{{background:linear-gradient(135deg,#d3c6b6,#f2eee4)}}.package-scene{{display:grid;grid-template-columns:1fr 420px;gap:34px;align-items:center;min-height:820px}}.package-scene section{{border:14px solid {theme['accent']};background:#fffdf7;padding:44px;transform:rotate(1.5deg)}}.pack-title{{font-size:60px;font-weight:900;line-height:1.42}}.pack-copy{{font-size:29px;line-height:1.38;margin-top:22px}}.image-box{{height:420px;background:#f7f3e8}}"""
    return wrap(doc, body, base_css(page, theme, doc["font_family"], 24, doc) + extra, page, "sign-page")


RENDERERS = {
    "certificate_proof": certificate_renderer,
    "exam_paper": exam_renderer,
    "sign_poster_scene": sign_renderer,
}


def validate_spec(spec: dict[str, Any]) -> None:
    if spec.get("schema_version") != "category_layout_templates.v1":
        raise RuntimeError("unsupported schema")
    cats = spec.get("categories")
    if not isinstance(cats, list) or len(cats) != 3:
        raise RuntimeError("batch1 spec must contain exactly 3 categories")
    for cat in cats:
        templates = cat.get("templates")
        if not isinstance(templates, list) or len(templates) != 6:
            raise RuntimeError(f"{cat.get('category_id')} must contain 6 templates")
        variants = [tpl.get("variant") for tpl in templates]
        if variants != [1, 2, 3, 4, 5, 6]:
            raise RuntimeError(f"{cat.get('category_id')} variants invalid: {variants}")


def safe_name(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


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
    parser.add_argument("--output-root")
    parser.add_argument("--output-dir")
    parser.add_argument("--language-profile")
    parser.add_argument("--start-index", type=int, default=2)
    parser.add_argument("--min-records", type=int, default=40)
    parser.add_argument("--seed", type=int, default=2026070102)
    parser.add_argument("--version-name")
    args = parser.parse_args()
    if not args.output_root and not args.output_dir:
        parser.error("one of --output-root or --output-dir is required")

    profile = load_language_profile(Path(args.language_profile) if args.language_profile else None)
    records = read_text_records(Path(args.text_jsonl), profile, args.min_records)
    spec = json.loads(Path(args.templates_json).read_text(encoding="utf-8"))
    validate_spec(spec)
    version_name = args.version_name or (Path(args.output_root).name if args.output_root else "v2")

    rng = random.Random(args.seed)

    if args.output_dir and not args.output_root:
        out_dir = Path(args.output_dir)
        html_dir = out_dir / "html"
        meta_dir = out_dir / "metadata"
        html_dir.mkdir(parents=True, exist_ok=True)
        meta_dir.mkdir(parents=True, exist_ok=True)
        manifest = []
        category_plan = []
        for cat_idx, cat in enumerate(spec["categories"], 1):
            category_id = cat["category_id"]
            category_cn = cat["category_cn"]
            category_plan.append({"category": category_id, "category_cn": category_cn, "samples": 6})
            renderer = RENDERERS[category_id]
            for tpl in cat["templates"]:
                variant = int(tpl["variant"])
                document_id = f"{cat_idx:02d}_{category_id}_json_{variant:02d}"
                b = Builder(document_id)
                theme = THEMES[(cat_idx + variant - 2) % len(THEMES)]
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
                (html_dir / f"{document_id}.html").write_text(html_text, encoding="utf-8")
                page = tpl["page"]
                manifest.append(
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
                        "generator": "batch1_json_renderer_za_v1",
                        "doc_no": f"B1-{cat_idx:02d}-{variant:02d}",
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
        write_json(meta_dir / "html_manifest.json", manifest)
        write_json(meta_dir / "category_plan.json", category_plan)
        write_json(meta_dir / "batch1_template_spec.json", spec)
        print(f"generated {len(manifest)} html files across {len(category_plan)} categories in {html_dir}")
        return 0

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
                    "generator": "batch1_json_renderer_za_v1",
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
        write_json(folder / "metadata" / "batch1_template_spec.json", {"category": cat, "source_schema": spec["schema_version"]})
        (folder / "README.md").write_text(
            f"# {args.start_index + offset:02d} {category_cn}\n\n本目录属于壮语 `{version_name}`，由分类 JSON 结构树生成，共 6 张。\n\n- `html/`\n- `images/`\n- `labels/`\n- `metadata/`\n- `reports/`\n",
            encoding="utf-8",
        )
        written.append(str(folder))
    print(json.dumps({"generated_category_dirs": written}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
