#!/usr/bin/env python3
"""Generate 12 layout categories x 6 diverse samples for evaluation data.

The generator creates HTML pages only. The existing renderer reads marked DOM
nodes and produces screenshots plus JSON labels.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import random
import re
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple


CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
TIBETAN_RE = re.compile(r"[\u0f00-\u0fff]")


CATEGORIES = [
    ("table_document", "表格文档"),
    ("newspaper", "报纸"),
    ("invoice_receipt", "发票票据"),
    ("notice_announcement", "公告通知"),
    ("book_textbook", "书籍教材页"),
    ("poster_flyer", "宣传海报传单"),
    ("certificate", "证书证明"),
    ("form_registration", "表单登记页"),
    ("schedule_timetable", "日程课程表"),
    ("report_brief", "报告简报"),
    ("menu_price_list", "菜单价目表"),
    ("letter_official", "信函公文"),
]


THEMES = [
    {"ink": "#1f2933", "muted": "#607083", "line": "#aebccc", "head": "#e6edf5", "accent": "#2f6680", "paper": "#fbfaf6", "soft": "#f4f7fb"},
    {"ink": "#27231e", "muted": "#72675d", "line": "#c5b8a7", "head": "#eee7d8", "accent": "#7b4c2d", "paper": "#fffdf7", "soft": "#f7f0e6"},
    {"ink": "#17241d", "muted": "#5f7468", "line": "#a7c0b4", "head": "#e2efe8", "accent": "#2e6b4f", "paper": "#fbfff9", "soft": "#eef7f1"},
    {"ink": "#2a2025", "muted": "#725d67", "line": "#c8aebb", "head": "#f0e3ea", "accent": "#8a3f68", "paper": "#fffafd", "soft": "#f8eef3"},
    {"ink": "#20222a", "muted": "#666b78", "line": "#aeb4c1", "head": "#e8ebf2", "accent": "#4e5f91", "paper": "#fcfcff", "soft": "#f1f3fb"},
    {"ink": "#222222", "muted": "#636363", "line": "#b8b8b8", "head": "#eeeeee", "accent": "#444444", "paper": "#fbfbf8", "soft": "#f4f4f1"},
]


def now_local() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def load_language_profile(path: Path | None) -> Dict[str, str]:
    if path is None:
        return {
            "language_code": "mn",
            "language_name": "蒙古语",
            "script_note": "西里尔蒙古文",
            "html_lang": "mn",
            "script_regex": r"[\u0400-\u04ff]",
            "min_script_ratio": 0.35,
            "font_family": "Arial, 'Helvetica Neue', sans-serif",
            "title_prefix": "",
        }
    profile = json.loads(path.read_text(encoding="utf-8"))
    profile.setdefault("html_lang", profile.get("language_code", "mn"))
    profile.setdefault("script_regex", r"[\u0400-\u04ff]")
    profile.setdefault("min_script_ratio", 0.35)
    profile.setdefault("font_family", "Arial, 'Helvetica Neue', sans-serif")
    profile.setdefault("title_prefix", "")
    return profile


def read_text_records(path: Path, language_profile: Dict[str, str], min_records: int = 40) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    script_re = re.compile(language_profile["script_regex"])
    min_ratio = float(language_profile["min_script_ratio"])
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        text = " ".join(str(row.get("text", "")).split())
        if len(text) < 20:
            continue
        if len(script_re.findall(text)) / max(len(text), 1) < min_ratio:
            continue
        records.append(
            {
                "title": str(row.get("title", "")),
                "text": text,
                "url": str(row.get("url", "")),
                "source_record_id": str(row.get("record_id", "")),
            }
        )
    if len(records) < min_records:
        raise RuntimeError(f"not enough text records in {path}: {len(records)}")
    return records


def clip(text: str, min_len: int, max_len: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    for sep in ["。", ".", "；", ";", "，", ",", " "]:
        idx = cut.rfind(sep)
        if idx >= min_len:
            return cut[: idx + 1].strip()
    return cut.rstrip() + "..."


def record_text(records: List[Dict[str, str]], rng: random.Random, min_len: int, max_len: int) -> str:
    return clip(rng.choice(records)["text"], min_len, max_len)


def record_title(records: List[Dict[str, str]], rng: random.Random, min_len: int = 8, max_len: int = 38) -> str:
    rec = rng.choice(records)
    return clip(rec["title"] or rec["text"], min_len, max_len)


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
            f'data-label="{label}" {attrs}>{esc(text)}</{tag}>'
        )

    def cell(self, tag: str, label: str, text: str, row: int, col: int, cls: str = "") -> str:
        return (
            f'<{tag} class="{cls}" data-block-id="{self.bid()}" data-label="{label}" '
            f'data-row="{row}" data-col="{col}">{esc(text)}</{tag}>'
        )


def base_css(
    page_w: int,
    page_h: int,
    theme: Dict[str, str],
    font_size: int,
    font_family: str,
    margin_x: int = 78,
    margin_y: int = 70,
) -> str:
    return f"""
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: #d8dde4; }}
    body {{ font-family: {font_family}; color: {theme['ink']}; }}
    .page {{
      width: {page_w}px;
      min-height: {page_h}px;
      margin: 0 auto;
      padding: {margin_y}px {margin_x}px;
      background: {theme['paper']};
      position: relative;
      overflow: hidden;
    }}
    .title {{ font-size: {font_size + 14}px; line-height: 1.35; font-weight: 700; letter-spacing: 0; }}
    .subtitle {{ font-size: {font_size - 2}px; color: {theme['muted']}; line-height: 1.34; margin-top: 8px; }}
    .section-title {{ font-size: {font_size + 1}px; color: {theme['accent']}; font-weight: 700; line-height: 1.2; margin: 0 0 10px; }}
    .text {{ font-size: {font_size}px; line-height: 1.34; }}
    .small {{ font-size: {font_size - 5}px; line-height: 1.25; color: {theme['muted']}; }}
    .meta {{ font-size: {font_size - 4}px; line-height: 1.35; color: {theme['muted']}; }}
    .panel {{ border: 1.5px solid {theme['line']}; background: rgba(255,255,255,.72); padding: 14px; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; font-size: {font_size - 1}px; line-height: 1.25; background: white; }}
    th, td {{ border: 1.4px solid {theme['line']}; padding: 8px 10px; vertical-align: top; overflow-wrap: break-word; }}
    th {{ background: {theme['head']}; font-weight: 700; text-align: left; }}
    .num {{ text-align: center; font-variant-numeric: tabular-nums; }}
    .footer {{ position: absolute; left: {margin_x}px; right: {margin_x}px; bottom: 28px; border-top: 1.2px solid {theme['line']}; padding-top: 9px; text-align: right; font-size: {font_size - 6}px; color: {theme['muted']}; }}
    .stamp {{ border: 2px solid {theme['accent']}; color: {theme['accent']}; text-align: center; padding: 8px 12px; font-weight: 700; transform: rotate(-4deg); }}
    .image-box {{ border: 1.4px solid {theme['line']}; background: linear-gradient(135deg, {theme['soft']}, #fff); position: relative; min-height: 120px; }}
    .image-box::after {{ content: ""; position: absolute; inset: 18px; border: 1px dashed rgba(90,100,112,.42); }}
    """


def wrap(doc: Dict[str, str], body: str, css: str, page_w: int, page_h: int, html_lang: str, cls: str = "") -> str:
    return f"""<!doctype html>
<html lang="{esc(html_lang)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width={page_w}, initial-scale=1">
  <title>{esc(doc['title'])}</title>
  <style>{css}</style>
</head>
<body>
  <main class="page {cls}" data-page-width="{page_w}" data-page-height="{page_h}">
    {body}
  </main>
</body>
</html>
"""


def simple_table(b: Builder, headers: List[str], rows: List[List[str]]) -> str:
    out = ["<table><tbody><tr>"]
    for col, h in enumerate(headers):
        out.append(b.cell("th", "table_header", h, 0, col, "num" if col == 0 else ""))
    out.append("</tr>")
    for row_idx, row in enumerate(rows, 1):
        out.append("<tr>")
        for col_idx, value in enumerate(row):
            label = "table_cell_number" if col_idx == 0 and value.strip().isdigit() else "table_cell_text"
            out.append(b.cell("td", label, value, row_idx, col_idx, "num" if label == "table_cell_number" else ""))
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def money(value: int) -> str:
    return f"{value:,}"


def kv_box(b: Builder, label: str, value: str, cls: str = "kv-box") -> str:
    return (
        f'<div class="{cls}">'
        f"{b.block('field_label', label, 'field-label')}"
        f"{b.block('field_value', value, 'field-value')}"
        "</div>"
    )


def option_group(b: Builder, title: str, options: List[str], selected: int, cls: str = "option-group") -> str:
    items = []
    for idx, item in enumerate(options):
        mark = "[x]" if idx == selected else "[ ]"
        items.append(b.block("option", f"{mark} {item}", "option-line"))
    return f'<div class="{cls}">{b.block("field_label", title, "field-label")}{"".join(items)}</div>'


def code_boxes(b: Builder, label: str, value: str, cells: int = 8) -> str:
    chars = list(value[:cells].ljust(cells))
    boxes = "".join(b.block("code_cell", ch, "code-cell") for ch in chars)
    return f'<div class="code-boxes">{b.block("field_label", label, "field-label")}<div class="code-row">{boxes}</div></div>'


def article_module(
    b: Builder,
    title: str,
    paragraphs: List[str],
    cls: str = "story-card",
    title_label: str = "section_title",
) -> str:
    parts = [f'<section class="{cls}">', b.block(title_label, title, "story-head")]
    parts.extend(b.block("paragraph", paragraph, "story-para") for paragraph in paragraphs)
    parts.append("</section>")
    return "".join(parts)


def table_document(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = 1240, 1754, 23
    base_rows = []
    for i in range(1, 7 + variant % 3):
        base_rows.append([str(i), record_title(records, rng), record_text(records, rng, 42, 96), rng.choice(["батлав", "шинэ", "хянана"])])

    if variant == 1:
        headers = ["№", "Сэдэв", "Тайлбар", "Төлөв"]
        body = f"""
          <div class="split-head"><div>{b.block('document_title', doc['title'], 'title')}{b.block('document_subtitle', record_text(records, rng, 50, 110), 'subtitle')}</div>{b.block('metadata', '№ TBL-%03d' % variant, 'stamp')}</div>
          <div class="two-zone"><section>{b.block('section_title', 'Үндсэн хүснэгт', 'section-title')}{simple_table(b, headers, base_rows)}</section><aside class="panel">{b.block('section_title', 'Тайлбар', 'section-title')}{b.block('note', record_text(records, rng, 90, 170), 'text')}</aside></div>
          {b.block('footer', 'table document · basic variant %d' % variant, 'footer')}
        """
        extra = ".split-head{display:grid;grid-template-columns:1fr 190px;gap:24px;border-bottom:4px solid %s;padding-bottom:16px}.two-zone{display:grid;grid-template-columns:1fr 280px;gap:20px;margin-top:22px;align-items:start}" % theme["accent"]
    elif variant == 2:
        headers = ["Ангилал", "I улирал", "II улирал", "III улирал", "Нийт"]
        rows = [[record_title(records, rng, 8, 20), str(rng.randint(12, 98)), str(rng.randint(12, 98)), str(rng.randint(12, 98)), str(rng.randint(100, 260))] for _ in range(8)]
        body = f"""
          <div class="stat-head">{b.block('document_title', doc['title'], 'title')}{b.block('metadata', '统计汇总表', 'stat-mark')}</div>
          <div class="summary-cards">{''.join(b.block('metric', str(rng.randint(20,99)), 'summary-card') for _ in range(4))}</div>
          {simple_table(b, headers, rows)}
          {b.block('footer', 'table document · summary variant %d' % variant, 'footer')}
        """
        extra = ".stat-head{display:flex;justify-content:space-between;align-items:end;border-bottom:4px double %s;padding-bottom:12px}.stat-mark{font-size:18px;color:%s}.summary-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}.summary-card{border:1px solid %s;background:%s;padding:16px;text-align:center;font-size:36px;font-weight:900}" % (theme["accent"], theme["muted"], theme["line"], theme["soft"])
    elif variant == 3:
        headers = ["Код", "Материал", "Хариуцагч", "Эхлэх", "Дуусах", "Төлөв"]
        rows = [[f"A-{rng.randint(100,999)}", record_title(records, rng, 8, 24), record_title(records, rng, 6, 16), f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}", f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}", rng.choice(["OK","WAIT","REV"])] for _ in range(9)]
        body = f"""
          <div class="ledger-head">{b.block('document_title', doc['title'], 'title')}{b.block('metadata', '台账编号 L-%03d' % variant, 'stamp')}</div>
          <div class="ledger-wrap">{simple_table(b, headers, rows)}</div>
          <div class="audit-row">{kv_box(b, '制表', record_title(records, rng, 6, 16), 'audit-box')}{kv_box(b, '审核', record_title(records, rng, 6, 16), 'audit-box')}{kv_box(b, '日期', '2026-%02d-%02d' % (rng.randint(1,12), rng.randint(1,28)), 'audit-box')}</div>
          {b.block('footer', 'table document · ledger variant %d' % variant, 'footer')}
        """
        extra = ".ledger-head{display:grid;grid-template-columns:1fr 170px;gap:18px;align-items:start;border-bottom:3px solid %s;padding-bottom:12px}.ledger-wrap{margin-top:18px}.ledger-wrap td,.ledger-wrap th{font-size:18px;padding:7px}.audit-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:16px}.audit-box{border:1px solid %s;padding:8px 10px;min-height:60px}" % (theme["accent"], theme["line"])
    elif variant == 4:
        headers = ["№", "Шалгах зүйл", "Үр дүн", "Тэмдэглэл"]
        rows = [[str(i), record_text(records, rng, 24, 58), rng.choice(["[ ]", "[x]"]), record_text(records, rng, 20, 48)] for i in range(1, 11)]
        body = f"""
          {b.block('document_title', doc['title'], 'title')}
          <div class="checkdoc-grid">
            <section>{simple_table(b, headers, rows)}</section>
            <aside class="checkdoc-side">{b.block('section_title', '检查说明', 'section-title')}{''.join(b.block('list_item', record_text(records, rng, 30, 68), 'checkdoc-note') for _ in range(5))}</aside>
          </div>
          {b.block('footer', 'table document · checklist variant %d' % variant, 'footer')}
        """
        extra = ".checkdoc-grid{display:grid;grid-template-columns:1fr 300px;gap:18px;margin-top:18px}.checkdoc-side{border:2px solid %s;background:%s;padding:14px}.checkdoc-note{font-size:19px;line-height:1.34;border-bottom:1px dashed %s;padding:8px 0}" % (theme["accent"], theme["soft"], theme["line"])
    elif variant == 5:
        headers = ["分组", "项目", "说明"]
        rows = [[rng.choice(["A","B","C"]), record_title(records, rng, 8, 20), record_text(records, rng, 34, 82)] for _ in range(10)]
        body = f"""
          <div class="group-table-head">{b.block('document_title', doc['title'], 'title')}{b.block('document_subtitle', record_text(records, rng, 45, 96), 'subtitle')}</div>
          <div class="group-table">{simple_table(b, headers, rows)}</div>
          <div class="note-band">{b.block('note', record_text(records, rng, 80, 150), 'text')}</div>
          {b.block('footer', 'table document · grouped variant %d' % variant, 'footer')}
        """
        extra = ".group-table-head{border-left:10px solid %s;padding-left:16px}.group-table{margin-top:20px}.group-table tr:nth-child(4n+1) td{background:%s}.note-band{border-top:3px solid %s;margin-top:18px;padding-top:12px}" % (theme["accent"], theme["soft"], theme["accent"])
    else:
        headers = ["字段", "值", "字段", "值"]
        rows = [[record_title(records, rng, 6, 16), record_text(records, rng, 16, 42), record_title(records, rng, 6, 16), record_text(records, rng, 16, 42)] for _ in range(8)]
        body = f"""
          <div class="card-table-shell">
            <header>{b.block('document_title', doc['title'], 'title')}{b.block('metadata', '档案卡片式表格', 'meta')}</header>
            <div class="card-table-body">{simple_table(b, headers, rows)}</div>
            <div class="card-footer">{kv_box(b, '编号', f'CARD-{rng.randint(1000,9999)}', 'audit-box')}{kv_box(b, '责任人', record_title(records, rng, 6, 18), 'audit-box')}</div>
          </div>
          {b.block('footer', 'table document · card variant %d' % variant, 'footer')}
        """
        extra = ".card-table-shell{border:2px solid %s;background:white;padding:18px}.card-table-shell header{display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid %s;padding-bottom:12px}.card-table-body{margin-top:16px}.card-footer{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}" % (theme["accent"], theme["line"])
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"]) + extra, page_w, page_h, doc["html_lang"])


def newspaper(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = 1240, 1754, 20
    issue_meta = f"№ {rng.randint(120, 480)} · 2026/{rng.randint(1,12):02d}/{rng.randint(1,28):02d}"
    deck = record_text(records, rng, 62, 120)
    hero_title = record_title(records, rng, 22, 68)
    hero_paras = [record_text(records, rng, 58, 120) for _ in range(2)]
    side_story_a = article_module(
        b,
        record_title(records, rng, 12, 34),
        [record_text(records, rng, 48, 108), record_text(records, rng, 48, 108)],
        cls="side-story",
    )
    side_story_b = article_module(
        b,
        record_title(records, rng, 12, 34),
        [record_text(records, rng, 48, 108), record_text(records, rng, 48, 108)],
        cls="side-story",
    )
    briefs = "".join(
        f'<section class="brief-item">{b.block("section_title", record_title(records, rng, 10, 30), "brief-head")}{b.block("paragraph", record_text(records, rng, 40, 90), "brief-copy")}</section>'
        for _ in range(4)
    )
    column_story_a = article_module(
        b,
        record_title(records, rng, 14, 42),
        [record_text(records, rng, 55, 120) for _ in range(3)],
        cls="column-story",
    )
    column_story_b = article_module(
        b,
        record_title(records, rng, 14, 42),
        [record_text(records, rng, 55, 120) for _ in range(3)],
        cls="column-story",
    )
    column_story_c = article_module(
        b,
        record_title(records, rng, 14, 42),
        [record_text(records, rng, 55, 120) for _ in range(3)],
        cls="column-story",
    )
    ad_box = f'<section class="ad-box">{b.block("section_title", "ЗАР СУРТАЛЧИЛГАА", "ad-head")}{b.block("paragraph", record_text(records, rng, 42, 96), "ad-copy")}{b.block("paragraph", record_text(records, rng, 42, 96), "ad-copy")}</section>'
    digest_cards = "".join(
        f'<section class="digest-card">{b.block("section_title", record_title(records, rng, 10, 30), "digest-head")}{b.block("paragraph", record_text(records, rng, 36, 82), "digest-copy")}{b.block("metadata", f"{rng.randint(1,12):02d}:{rng.randint(0,59):02d}", "digest-meta")}</section>'
        for _ in range(6)
    )
    community_items = "".join(
        f'<div class="community-item">{b.block("list_item", record_text(records, rng, 28, 62), "community-copy")}</div>'
        for _ in range(6)
    )
    calendar_items = "".join(
        f'<div class="calendar-row">{b.block("metadata", f"{rng.randint(1,28):02d}", "calendar-day")}{b.block("list_item", record_text(records, rng, 22, 48), "calendar-text")}</div>'
        for _ in range(4)
    )
    dense_items = "".join(
        f'<section class="dense-story">{b.block("section_title", record_title(records, rng, 10, 28), "dense-head")}{b.block("paragraph", record_text(records, rng, 42, 86), "dense-copy")}</section>'
        for _ in range(10)
    )

    if variant == 1:
        body = f"""
          <header class="press-band">{b.block('metadata', 'УЛСЫН ӨДРИЙН СОНИН', 'press-note')}{b.block('metadata', issue_meta, 'issue-meta')}</header>
          <div class="masthead">{b.block('document_title', doc['title'], 'newspaper-title')}{b.block('metadata', 'Нийгэм · Соёл · Боловсрол', 'edition-line')}</div>
          <div class="headline-bar">{b.block('headline', hero_title, 'hero-title')}{b.block('paragraph', deck, 'deck')}</div>
          <div class="hero-grid">
            <section class="hero-main">
              {''.join(b.block('paragraph', p, 'hero-copy') for p in hero_paras)}
              <div class="photo-wrap">{b.block('image', '', 'press-photo')}{b.block('caption', record_text(records, rng, 26, 62), 'caption')}</div>
            </section>
            <aside class="side-stack">{side_story_a}{side_story_b}</aside>
          </div>
          <div class="brief-strip">{briefs}</div>
          <div class="news-columns">{column_story_a}{column_story_b}{column_story_c}</div>
          {b.block('footer', 'newspaper · refined variant %d' % variant, 'footer')}
        """
    elif variant == 2:
        body = f"""
          <header class="press-band image-led-band">{b.block('metadata', 'PHOTO NEWS', 'press-note')}{b.block('metadata', issue_meta, 'issue-meta')}</header>
          <div class="masthead image-led-head">{b.block('document_title', doc['title'], 'newspaper-title')}{b.block('metadata', 'Онцлох зураг · Мэдээний тойм', 'edition-line')}</div>
          <section class="image-led-layout">
            <div class="lead-visual">{b.block('image', '', 'press-photo lead')}{b.block('caption', record_text(records, rng, 28, 64), 'caption')}</div>
            <div class="lead-copy">
              {b.block('headline', hero_title, 'hero-title')}
              {b.block('paragraph', deck, 'deck')}
              {''.join(b.block('paragraph', p, 'hero-copy') for p in hero_paras)}
            </div>
          </section>
          <div class="digest-grid">{digest_cards}</div>
          {b.block('footer', 'newspaper · image-led variant %d' % variant, 'footer')}
        """
    elif variant == 3:
        body = f"""
          <header class="press-band alt">{b.block('metadata', 'ТУСГАЙ ДУГААР', 'press-note')}{b.block('metadata', issue_meta, 'issue-meta')}</header>
          <div class="masthead alt">{b.block('document_title', doc['title'], 'newspaper-title')}{b.block('metadata', 'Хот · Аймаг · Дэлхий', 'edition-line')}</div>
          <div class="front-layout">
            <section class="banner-story">
              {b.block('headline', hero_title, 'banner-title')}
              {b.block('paragraph', deck, 'deck')}
              <div class="banner-body">{''.join(b.block('paragraph', record_text(records, rng, 52, 108), 'banner-copy') for _ in range(2))}</div>
            </section>
            <section class="front-photo">{b.block('image', '', 'press-photo tall')}{b.block('caption', record_text(records, rng, 24, 56), 'caption')}</section>
          </div>
          <div class="below-fold">
            <div class="news-columns">{column_story_a}{column_story_b}</div>
            <aside class="ad-rail">{ad_box}{side_story_a}</aside>
          </div>
          <div class="ticker">{''.join(b.block('list_item', record_text(records, rng, 24, 52), 'ticker-item') for _ in range(5))}</div>
          {b.block('footer', 'newspaper · refined variant %d' % variant, 'footer')}
        """
    elif variant == 4:
        body = f"""
          <header class="press-band community-band">{b.block('metadata', 'COMMUNITY BULLETIN', 'press-note')}{b.block('metadata', issue_meta, 'issue-meta')}</header>
          <div class="community-mast">{b.block('document_title', doc['title'], 'newspaper-title')}{b.block('metadata', 'Зарлал · Үйл явдал · Холбоо барих', 'edition-line')}</div>
          <div class="community-layout">
            <section class="notice-board">
              {b.block('headline', hero_title, 'community-title')}
              {b.block('paragraph', deck, 'community-lead')}
              {community_items}
            </section>
            <aside class="calendar-box">
              {b.block('section_title', 'Календарь', 'calendar-title')}
              {calendar_items}
              {kv_box(b, 'Contact', record_title(records, rng, 8, 20), 'community-kv')}
            </aside>
          </div>
          <div class="classified-strip">{briefs}</div>
          {b.block('footer', 'newspaper · community variant %d' % variant, 'footer')}
        """
    elif variant == 5:
        body = f"""
          <header class="press-band">{b.block('metadata', 'ДОЛОО ХОНОГИЙН ТОЙМ', 'press-note')}{b.block('metadata', issue_meta, 'issue-meta')}</header>
          <div class="masthead wide">{b.block('document_title', doc['title'], 'newspaper-title')}{b.block('metadata', 'Эдийн засаг · Тайлбар · Нийтлэл', 'edition-line')}</div>
          <section class="centerpiece">
            {b.block('headline', hero_title, 'center-title')}
            <div class="center-grid">
              <div class="lead-column">{''.join(b.block('paragraph', record_text(records, rng, 55, 120), 'center-copy') for _ in range(3))}</div>
              <div class="visual-column">{b.block('image', '', 'press-photo wide')}{b.block('caption', record_text(records, rng, 24, 54), 'caption')}</div>
            </div>
          </section>
          <div class="bottom-paper">
            {column_story_a}
            {column_story_b}
            {ad_box}
          </div>
          <div class="footer-briefs">{briefs}</div>
          {b.block('footer', 'newspaper · refined variant %d' % variant, 'footer')}
        """
    else:
        body = f"""
          <header class="press-band dense-band">{b.block('metadata', 'DAILY DIGEST', 'press-note')}{b.block('metadata', issue_meta, 'issue-meta')}</header>
          <div class="dense-mast">{b.block('document_title', doc['title'], 'newspaper-title')}{b.block('metadata', 'Товч мэдээ · Шуурхай мэдээлэл', 'edition-line')}</div>
          <section class="dense-lead">
            {b.block('headline', hero_title, 'dense-title')}
            {b.block('paragraph', deck, 'dense-deck')}
          </section>
          <div class="dense-grid">{dense_items}</div>
          <div class="ticker compact">{''.join(b.block('list_item', record_text(records, rng, 20, 42), 'ticker-item') for _ in range(6))}</div>
          {b.block('footer', 'newspaper · dense variant %d' % variant, 'footer')}
        """

    title_size = 42 if doc.get("html_lang") == "bo" else 62
    hero_size = 29 if doc.get("html_lang") == "bo" else 44
    story_head_size = 22 if doc.get("html_lang") == "bo" else 26
    brief_head_size = 17 if doc.get("html_lang") == "bo" else 19
    body_size = 18 if doc.get("html_lang") == "bo" else 20
    extra = """
    .press-band{display:grid;grid-template-columns:1fr auto;border-bottom:1px solid #252525;padding-bottom:8px;font-size:15px;letter-spacing:1px}
    .press-band.alt{border-top:4px solid #181818;padding-top:10px}
    .press-note{font-size:15px;font-weight:700;text-transform:uppercase}
    .issue-meta{font-size:15px;text-align:right}
    .masthead{display:grid;grid-template-columns:1fr auto;align-items:end;border-bottom:6px double #111;padding:14px 0 12px}
    .masthead.alt{border-bottom:5px solid #111}
    .masthead.wide{grid-template-columns:1fr}
    .newspaper-title{font-size:%dpx;font-weight:900;line-height:1.34;letter-spacing:0}
    .edition-line{font-size:17px;color:%s;align-self:center}
    .headline-bar{padding:16px 0 12px;border-bottom:1px solid %s}
    .hero-title,.banner-title,.center-title{font-size:%dpx;line-height:1.38;font-weight:800;margin-bottom:10px}
    .deck{font-size:24px;line-height:1.22;font-weight:600}
    .hero-grid{display:grid;grid-template-columns:1.35fr .8fr;gap:20px;margin-top:18px}
    .hero-main{border-right:1px solid %s;padding-right:18px}
    .hero-copy,.banner-copy,.center-copy,.story-para{font-size:%dpx;line-height:1.42;margin:0 0 12px;text-align:justify}
    .photo-wrap{margin-top:14px}
    .press-photo{min-height:230px;background:linear-gradient(135deg,%s,#ffffff);border:1.3px solid %s;position:relative}
    .press-photo::before{content:'';position:absolute;left:18px;right:18px;top:18px;bottom:18px;border:1px dashed rgba(50,50,50,.35)}
    .press-photo.tall{min-height:420px}
    .press-photo.wide{min-height:250px}
    .press-photo.lead{min-height:530px}
    .caption{font-size:14px;line-height:1.25;color:%s;border-bottom:1px solid %s;padding:8px 0 10px}
    .side-stack{display:grid;gap:16px}
    .side-story,.column-story,.story-card{break-inside:avoid;border-top:3px solid #111;padding-top:8px}
    .story-head{font-size:%dpx;line-height:1.16;font-weight:800;margin-bottom:8px}
    .brief-strip,.footer-briefs{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:18px}
    .brief-item{border-top:2px solid %s;padding-top:8px}
    .brief-head{font-size:%dpx;font-weight:800;line-height:1.2}
    .brief-copy{font-size:17px;line-height:1.28;margin-top:6px}
    .news-columns{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:18px}
    .front-layout{display:grid;grid-template-columns:1.2fr .8fr;gap:18px;margin-top:18px;align-items:start}
    .banner-story{border-top:4px solid #111;padding-top:10px}
    .banner-body{columns:2;column-gap:18px;margin-top:14px}
    .below-fold{display:grid;grid-template-columns:1fr 320px;gap:18px;margin-top:18px}
    .ad-rail{display:grid;gap:16px}
    .ad-box{border:2px solid #111;padding:10px 12px;background:%s}
    .ad-head{font-size:20px;font-weight:900;letter-spacing:1px}
    .ad-copy{font-size:17px;line-height:1.25;margin-top:8px}
    .ticker{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;border-top:1px solid %s;border-bottom:1px solid %s;padding:10px 0;margin-top:18px}
    .ticker-item{font-size:16px;line-height:1.22}
    .centerpiece{border-top:4px solid #111;padding-top:12px;margin-top:18px}
    .center-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:18px;margin-top:10px}
    .lead-column{columns:2;column-gap:18px}
    .bottom-paper{display:grid;grid-template-columns:1fr 1fr 310px;gap:18px;margin-top:18px}
    .image-led-layout{display:grid;grid-template-columns:1.05fr .95fr;gap:20px;margin-top:18px;align-items:start}
    .lead-copy{border-left:5px solid #111;padding-left:18px}
    .digest-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:18px}
    .digest-card{border:1px solid %s;padding:10px 12px;background:white;min-height:132px}
    .digest-head{font-size:19px;font-weight:800;line-height:1.24}
    .digest-copy{font-size:16px;line-height:1.32;margin-top:6px}
    .digest-meta{font-size:13px;color:%s;margin-top:6px;text-align:right}
    .community-mast{border:4px solid #111;padding:12px 14px;margin-top:12px;display:grid;grid-template-columns:1fr auto;align-items:end}
    .community-layout{display:grid;grid-template-columns:1fr 330px;gap:18px;margin-top:18px}
    .notice-board{background:%s;border:2px solid %s;padding:16px}
    .community-title{font-size:%dpx;line-height:1.32;font-weight:900;margin-bottom:8px}
    .community-lead{font-size:19px;line-height:1.42;margin-bottom:12px}
    .community-item{border-top:1px dashed %s;padding:8px 0}
    .community-copy{font-size:17px;line-height:1.32}
    .calendar-box{border:2px solid #111;padding:14px;background:white}
    .calendar-title{font-size:22px;font-weight:900;border-bottom:2px solid #111;padding-bottom:8px}
    .calendar-row{display:grid;grid-template-columns:42px 1fr;gap:10px;border-bottom:1px solid %s;padding:8px 0}
    .calendar-day{font-size:22px;font-weight:900;text-align:center}
    .calendar-text{font-size:16px;line-height:1.28}
    .community-kv{border:1px solid %s;margin-top:12px;padding:8px 10px}
    .classified-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:18px}
    .dense-mast{display:grid;grid-template-columns:1fr auto;align-items:end;border-top:8px solid #111;border-bottom:2px solid #111;padding:12px 0}
    .dense-lead{border-bottom:1px solid %s;padding:12px 0}
    .dense-title{font-size:%dpx;line-height:1.32;font-weight:900}
    .dense-deck{font-size:20px;line-height:1.34;font-weight:700}
    .dense-grid{columns:4;column-gap:16px;margin-top:16px}
    .dense-story{break-inside:avoid;border-top:2px solid #111;padding-top:7px;margin-bottom:12px}
    .dense-head{font-size:17px;font-weight:900;line-height:1.22}
    .dense-copy{font-size:15px;line-height:1.34;margin-top:5px}
    """ % (
        title_size,
        theme["muted"],
        theme["line"],
        hero_size,
        theme["line"],
        body_size,
        theme["soft"],
        theme["line"],
        theme["muted"],
        theme["line"],
        story_head_size,
        theme["accent"],
        brief_head_size,
        theme["head"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["muted"],
        theme["soft"],
        theme["line"],
        hero_size,
        theme["line"],
        theme["line"],
        theme["line"],
        theme["line"],
        hero_size,
    )
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"], 64, 56) + extra, page_w, page_h, doc["html_lang"])


def invoice_receipt(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = 980, 1380, 20
    items = []
    subtotal = 0
    for idx in range(1, 4 + variant % 4):
        qty = rng.randint(1, 6)
        unit_price = rng.randint(45, 320) * 100
        amount = qty * unit_price
        subtotal += amount
        items.append(
            {
                "idx": str(idx),
                "name": record_title(records, rng, 8, 28),
                "spec": record_text(records, rng, 18, 48),
                "unit": rng.choice(["ш", "багц", "кг", "цуглуулга"]),
                "qty": str(qty),
                "price": money(unit_price),
                "amount": money(amount),
            }
        )
    tax = int(subtotal * 0.1)
    payable = subtotal + tax
    note_text = record_text(records, rng, 36, 92)
    tax_id = f"{rng.randint(100000,999999)}{rng.randint(100000,999999)}"
    invoice_no = f"{rng.randint(10000000,99999999)}"
    invoice_code = f"{rng.randint(1100000000,1199999999)}"
    buyer = record_title(records, rng, 10, 28)
    seller = record_title(records, rng, 10, 28)
    issue_date = f"2026-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"

    if variant == 1:
        table_rows = []
        for row in items:
            table_rows.append(
                "<tr>"
                + b.cell("td", "table_cell_number", row["idx"], int(row["idx"]), 0, "num")
                + b.cell("td", "item_name", row["name"], int(row["idx"]), 1)
                + b.cell("td", "item_spec", row["spec"], int(row["idx"]), 2)
                + b.cell("td", "item_qty", row["qty"], int(row["idx"]), 3, "num")
                + b.cell("td", "item_price", row["price"], int(row["idx"]), 4, "num")
                + b.cell("td", "item_amount", row["amount"], int(row["idx"]), 5, "num")
                + "</tr>"
            )
        detail_table = (
            '<table class="invoice-grid"><tbody><tr>'
            + b.cell("th", "table_header", "货物或应税劳务、服务名称", 0, 0)
            + b.cell("th", "table_header", "规格型号", 0, 1)
            + b.cell("th", "table_header", "数量", 0, 2)
            + b.cell("th", "table_header", "单价", 0, 3)
            + b.cell("th", "table_header", "金额", 0, 4)
            + "</tr>"
            + "".join(
                "<tr>"
                + b.cell("td", "item_name", row["name"], int(row["idx"]), 0)
                + b.cell("td", "item_spec", row["spec"], int(row["idx"]), 1)
                + b.cell("td", "item_qty", row["qty"], int(row["idx"]), 2, "num")
                + b.cell("td", "item_price", row["price"], int(row["idx"]), 3, "num")
                + b.cell("td", "item_amount", row["amount"], int(row["idx"]), 4, "num")
                + "</tr>"
                for row in items
            )
            + "</tbody></table>"
        )
        body = f"""
          <div class="invoice-shell">
            <div class="invoice-topline">{b.block('metadata', '增值税电子发票（参考样式）', 'tax-banner')}{b.block('metadata', issue_date, 'issue-date')}</div>
            <header class="invoice-header">
              <div>{b.block('document_title', '发票', 'invoice-title')}{b.block('metadata', '票据代码', 'field-label')}{b.block('field_value', invoice_code, 'invoice-code')}</div>
              <div class="code-side">{code_boxes(b, '发票号码', invoice_no, 8)}{b.block('metadata', '校验码', 'field-label')}{b.block('field_value', f"{rng.randint(1000,9999)} {rng.randint(1000,9999)}", 'check-value')}</div>
            </header>
            <div class="buyer-seller">
              {kv_box(b, '购买方名称', buyer)}
              {kv_box(b, '纳税人识别号', tax_id)}
              {kv_box(b, '销售方名称', seller)}
              {kv_box(b, '销售方识别号', tax_id[::-1])}
            </div>
            {detail_table}
            <div class="totals-band">
              <div class="amount-card">{b.block('summary_label', '金额合计', 'sum-label')}{b.block('summary_value', money(subtotal), 'sum-value')}</div>
              <div class="amount-card">{b.block('summary_label', '税额', 'sum-label')}{b.block('summary_value', money(tax), 'sum-value')}</div>
              <div class="amount-card payable">{b.block('summary_label', '价税合计', 'sum-label')}{b.block('summary_value', money(payable), 'sum-value')}</div>
            </div>
            <div class="bottom-meta">
              {kv_box(b, '备注', note_text, 'note-box')}
              <div class="signature-grid">
                {b.block('field_label', '开票人', 'field-label')}
                {b.block('field_value', record_title(records, rng, 6, 18), 'sign-line')}
                {b.block('field_label', '收款人', 'field-label')}
                {b.block('field_value', record_title(records, rng, 6, 18), 'sign-line')}
                {b.block('field_label', '复核', 'field-label')}
                {b.block('field_value', record_title(records, rng, 6, 18), 'sign-line')}
              </div>
            </div>
          </div>
          {b.block('footer', 'invoice receipt · refined variant %d' % variant, 'footer')}
        """
    elif variant == 2:
        rows = []
        for row in items:
            rows.append([row["name"], row["qty"], row["amount"]])
        receipt_table = simple_table(b, ["品名", "数量", "金额"], rows)
        summary_lines = "".join(
            f'<div class="receipt-line">{b.block("summary_label", label, "text")}{b.block("summary_value", value, "amount")}</div>'
            for label, value in [("小计", money(subtotal)), ("税额", money(tax)), ("实收", money(payable))]
        )
        body = f"""
          <div class="receipt-roll">
            <div class="store-head">{b.block('document_title', record_title(records, rng, 10, 24), 'store-name')}{b.block('metadata', '销售小票 / RECEIPT', 'store-meta')}</div>
            {b.block('metadata', f'时间 {issue_date}  {rng.randint(8,21):02d}:{rng.randint(0,59):02d}', 'receipt-meta')}
            {b.block('metadata', f'流水号 {invoice_no}', 'receipt-meta')}
            {receipt_table}
            <div class="receipt-summary">{summary_lines}</div>
            {option_group(b, '支付方式', ['现金', '刷卡', '移动支付'], variant % 3, 'pay-box')}
            {b.block('note', note_text, 'receipt-note')}
            <div class="barcode-zone">{''.join(b.block('barcode_bar', '|', 'barcode-bar') for _ in range(38))}</div>
          </div>
          {b.block('footer', 'invoice receipt · refined variant %d' % variant, 'footer')}
        """
    elif variant == 3:
        body = f"""
          <div class="receipt-slip">
            <div class="slip-top">{b.block('document_title', '收据', 'slip-title')}{b.block('metadata', f'No. {invoice_no}', 'receipt-meta')}</div>
            <div class="slip-fields">
              {kv_box(b, '付款单位', buyer, 'line-kv')}
              {kv_box(b, '收款事由', record_text(records, rng, 30, 72), 'line-kv')}
              {kv_box(b, '金额大写', record_text(records, rng, 18, 46), 'line-kv')}
              {kv_box(b, '金额小写', money(payable), 'line-kv')}
            </div>
            <div class="slip-note">{b.block('note', note_text, 'receipt-note')}</div>
            <div class="slip-signs">
              {kv_box(b, '经办人', record_title(records, rng, 6, 18), 'sign-box')}
              {kv_box(b, '收款人', record_title(records, rng, 6, 18), 'sign-box')}
              {b.block('stamp', '财务专用', 'stamp round-stamp')}
            </div>
            <div class="copy-tabs">{b.block('metadata', '第一联 存根', 'copy-tab')}{b.block('metadata', '第二联 收据', 'copy-tab')}{b.block('metadata', '第三联 记账', 'copy-tab')}</div>
          </div>
          {b.block('footer', 'invoice receipt · receipt-slip variant %d' % variant, 'footer')}
        """
    elif variant == 4:
        expense_rows = [[row["name"], row["spec"], row["amount"]] for row in items[:5]]
        body = f"""
          <div class="expense-sheet">
            <header class="expense-head">{b.block('document_title', '费用报销单', 'expense-title')}{b.block('metadata', f'单号 {invoice_no}', 'receipt-meta')}</header>
            <div class="expense-meta">
              {kv_box(b, '报销人', buyer, 'expense-kv')}
              {kv_box(b, '部门', record_title(records, rng, 8, 20), 'expense-kv')}
              {kv_box(b, '日期', issue_date, 'expense-kv')}
            </div>
            {simple_table(b, ['费用项目','说明','金额'], expense_rows)}
            <div class="approval-flow">
              {kv_box(b, '合计', money(payable), 'approval-box')}
              {kv_box(b, '部门审核', record_title(records, rng, 6, 18), 'approval-box')}
              {kv_box(b, '财务复核', record_title(records, rng, 6, 18), 'approval-box')}
              {kv_box(b, '负责人', record_title(records, rng, 6, 18), 'approval-box')}
            </div>
          </div>
          {b.block('footer', 'invoice receipt · expense variant %d' % variant, 'footer')}
        """
    elif variant == 5:
        service_rows = [[row["name"], f"{rng.randint(1,12)} 月", row["amount"]] for row in items[:4]]
        body = f"""
          <div class="service-bill">
            <aside class="bill-side">
              {b.block('document_title', '账单', 'bill-title')}
              {b.block('metadata', f'BILL-{invoice_no}', 'bill-no')}
              {b.block('summary_value', money(payable), 'bill-total')}
            </aside>
            <main class="bill-main">
              <div class="bill-parties">
                {kv_box(b, '服务方', seller, 'bill-kv')}
                {kv_box(b, '客户', buyer, 'bill-kv')}
                {kv_box(b, '服务周期', f'2026-{rng.randint(1,12):02d}', 'bill-kv')}
              </div>
              {simple_table(b, ['服务项目','周期','金额'], service_rows)}
              <div class="bill-bottom">
                {b.block('note', note_text, 'receipt-note')}
                {b.block('image', '', 'qr-box')}
              </div>
            </main>
          </div>
          {b.block('footer', 'invoice receipt · service-bill variant %d' % variant, 'footer')}
        """
    else:
        voucher_rows = [[str(idx), record_title(records, rng, 8, 22), money(rng.randint(20, 280) * 100)] for idx in range(1, 5)]
        paste_boxes = "".join(
            f'<div class="paste-box">{b.block("image", "", "paste-placeholder")}{b.block("metadata", f"票据 {idx}", "paste-label")}</div>'
            for idx in range(1, 5)
        )
        body = f"""
          <div class="voucher-sheet">
            <header class="voucher-head">{b.block('document_title', '票据粘贴单', 'voucher-title')}{b.block('metadata', f'凭证号 {invoice_no}', 'receipt-meta')}</header>
            <div class="voucher-grid">
              <section class="paste-zone">{paste_boxes}</section>
              <aside class="voucher-info">
                {simple_table(b, ['序号','摘要','金额'], voucher_rows)}
                {kv_box(b, '合计金额', money(payable), 'approval-box')}
                {kv_box(b, '审核人', record_title(records, rng, 6, 18), 'approval-box')}
              </aside>
            </div>
          </div>
          {b.block('footer', 'invoice receipt · voucher variant %d' % variant, 'footer')}
        """

    extra = """
    .invoice-shell{border:2px solid %s;padding:18px 20px 16px;background:white}
    .invoice-topline{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid %s;padding-bottom:8px}
    .tax-banner{font-size:16px;letter-spacing:1px;color:%s}
    .issue-date{font-size:15px}
    .invoice-header{display:grid;grid-template-columns:1fr 260px;gap:16px;align-items:start;padding:14px 0;border-bottom:1px solid %s}
    .invoice-title{font-size:40px;font-weight:900;letter-spacing:10px;color:%s}
    .invoice-code{font-size:22px;font-weight:700;margin-top:6px}
    .check-value{font-size:18px;letter-spacing:2px;padding-top:6px}
    .buyer-seller{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:14px 0}
    .kv-box,.note-box{border:1px solid %s;padding:8px 10px;min-height:64px}
    .field-label{font-size:13px;color:%s;line-height:1.2}
    .field-value{font-size:21px;line-height:1.28;margin-top:4px}
    .invoice-grid{margin-top:4px}
    .invoice-grid th,.invoice-grid td{padding:8px 8px;border:1px solid %s}
    .invoice-grid th{font-size:17px;text-align:center}
    .invoice-grid td{font-size:18px}
    .code-boxes{margin-bottom:8px}
    .code-row{display:grid;grid-template-columns:repeat(8,1fr);gap:4px;margin-top:6px}
    .code-cell{border:1px solid %s;height:30px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700}
    .totals-band{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}
    .amount-card{border:1px solid %s;padding:10px 12px;background:%s}
    .amount-card.payable{border-width:2px}
    .sum-label{font-size:14px;color:%s}
    .sum-value{font-size:28px;font-weight:900;margin-top:6px;text-align:right}
    .bottom-meta{display:grid;grid-template-columns:1.1fr .9fr;gap:14px;margin-top:14px}
    .signature-grid{display:grid;grid-template-columns:90px 1fr;gap:8px 10px;border:1px solid %s;padding:10px}
    .sign-line{font-size:20px;border-bottom:1px solid %s;padding-bottom:4px}
    .receipt-roll{border:1px solid %s;background:white;padding:18px 22px 14px;width:760px;margin:0 auto}
    .store-head{text-align:center;border-bottom:2px dashed %s;padding-bottom:12px}
    .store-name{font-size:32px;font-weight:900;line-height:1.34}
    .store-meta{font-size:15px;letter-spacing:2px;margin-top:4px}
    .receipt-meta{font-size:16px;line-height:1.35;margin-top:6px}
    .receipt-roll table{margin-top:12px}
    .receipt-roll td,.receipt-roll th{padding:8px 6px}
    .receipt-summary{border-top:2px dashed %s;border-bottom:2px dashed %s;padding:10px 0;margin-top:12px}
    .receipt-line{display:grid;grid-template-columns:1fr auto;font-size:19px;line-height:1.4}
    .amount{text-align:right;font-weight:800}
    .pay-box{border-bottom:1px dashed %s;padding:10px 0;margin-top:10px}
    .option-line{font-size:18px;line-height:1.5}
    .receipt-note{font-size:16px;line-height:1.36;margin-top:10px}
    .barcode-zone{display:flex;gap:2px;justify-content:center;margin-top:14px;letter-spacing:1px}
    .barcode-bar{font-size:24px;line-height:1.42}
    .receipt-slip{border:2px solid %s;background:white;padding:22px 26px;min-height:980px}
    .slip-top{display:flex;justify-content:space-between;align-items:end;border-bottom:4px double %s;padding-bottom:12px}
    .slip-title{font-size:42px;font-weight:900;letter-spacing:8px;line-height:1.28}
    .slip-fields{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:22px}
    .line-kv{border-bottom:1.5px solid %s;padding:8px 4px;min-height:62px}
    .slip-note{border:1px dashed %s;margin-top:18px;padding:12px}
    .slip-signs{display:grid;grid-template-columns:1fr 1fr 140px;gap:14px;align-items:center;margin-top:26px}
    .sign-box{border:1px solid %s;padding:8px 10px;min-height:64px}
    .round-stamp{border-radius:50%%;height:112px;width:112px;display:flex;align-items:center;justify-content:center;transform:rotate(-8deg)}
    .copy-tabs{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:26px}
    .copy-tab{border:1px dashed %s;text-align:center;padding:8px;font-size:15px}
    .expense-sheet{border:1.5px solid %s;background:white;padding:20px}
    .expense-head{display:grid;grid-template-columns:1fr auto;align-items:end;border-bottom:3px solid %s;padding-bottom:12px}
    .expense-title{font-size:38px;font-weight:900;line-height:1.3}
    .expense-meta{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:14px 0}
    .expense-kv,.approval-box{border:1px solid %s;padding:8px 10px;min-height:58px}
    .approval-flow{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}
    .service-bill{display:grid;grid-template-columns:230px 1fr;border:1.5px solid %s;background:white;min-height:980px}
    .bill-side{background:%s;padding:22px 18px;display:flex;flex-direction:column;gap:18px}
    .bill-title{font-size:42px;font-weight:900;line-height:1.32}
    .bill-no{font-size:15px;line-height:1.3}
    .bill-total{font-size:34px;font-weight:900;margin-top:auto}
    .bill-main{padding:20px}
    .bill-parties{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:14px}
    .bill-kv{border:1px solid %s;padding:8px 10px;min-height:62px}
    .bill-bottom{display:grid;grid-template-columns:1fr 150px;gap:14px;margin-top:14px;align-items:start}
    .qr-box{min-height:150px;border:1.5px solid %s;background:repeating-linear-gradient(45deg,#fff,#fff 8px,%s 8px,%s 12px)}
    .voucher-sheet{border:2px solid %s;background:white;padding:20px}
    .voucher-head{display:flex;justify-content:space-between;align-items:end;border-bottom:2px solid %s;padding-bottom:12px}
    .voucher-title{font-size:38px;font-weight:900;line-height:1.3}
    .voucher-grid{display:grid;grid-template-columns:1fr 320px;gap:16px;margin-top:16px}
    .paste-zone{display:grid;grid-template-columns:1fr 1fr;gap:14px}
    .paste-box{border:1.5px dashed %s;min-height:280px;padding:10px;display:flex;flex-direction:column;justify-content:space-between;background:%s}
    .paste-placeholder{min-height:210px;border:1px solid %s;background:white}
    .paste-label{font-size:16px;text-align:right;color:%s}
    .voucher-info{display:grid;gap:12px;align-content:start}
    """ % (
        theme["accent"],
        theme["line"],
        theme["muted"],
        theme["line"],
        theme["accent"],
        theme["line"],
        theme["muted"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["head"],
        theme["muted"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["accent"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["accent"],
        theme["line"],
        theme["soft"],
        theme["line"],
        theme["line"],
        theme["soft"],
        theme["soft"],
        theme["accent"],
        theme["line"],
        theme["line"],
        theme["soft"],
        theme["line"],
        theme["muted"],
    )
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"], 54, 50) + extra, page_w, page_h, doc["html_lang"])


def notice_announcement(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = 1240, 1754, 23
    bullet_lines = "".join(
        f'<div class="gongwen-item">{b.block("list_item", f"（{idx}） {record_text(records, rng, 40, 96)}", "gongwen-copy")}</div>'
        for idx in range(1, 5 + variant % 3)
    )
    annex_rows = [[record_title(records, rng, 8, 24), record_text(records, rng, 24, 56)] for _ in range(4)]
    issue_no = f"〔2026〕{rng.randint(1,18)}号"
    date_text = f"2026年{rng.randint(1,12)}月{rng.randint(1,28)}日"

    if variant == 1:
        body = f"""
          <div class="gongwen-header">
            {b.block('metadata', '中央民族大学合作项目', 'issuer-line')}
            {b.block('document_title', doc['title'], 'gongwen-title')}
            {b.block('metadata', issue_no, 'gongwen-no')}
          </div>
          {b.block('recipient', '各相关单位：', 'recipient-line')}
          <div class="gongwen-body">
            {b.block('paragraph', record_text(records, rng, 100, 190), 'gongwen-lead')}
            {bullet_lines}
            {b.block('paragraph', record_text(records, rng, 88, 160), 'gongwen-tail')}
          </div>
          <div class="gongwen-sign">
            {b.block('signature', '中央民族大学合作项目组', 'issuer-sign')}
            {b.block('date', date_text, 'issuer-date')}
          </div>
          {b.block('footer', 'notice · refined variant %d' % variant, 'footer')}
        """
    elif variant == 2:
        body = f"""
          <div class="bulletin-shell">
            <header class="bulletin-head">
              {b.block('metadata', '专题公告栏', 'bulletin-mark')}
              {b.block('document_title', doc['title'], 'bulletin-title')}
              {b.block('metadata', issue_no, 'gongwen-no')}
            </header>
            <div class="bulletin-grid">
              <section class="main-bulletin">
                {b.block('section_title', '公告事项', 'section-title')}
                {bullet_lines}
                {b.block('paragraph', record_text(records, rng, 76, 150), 'gongwen-tail')}
              </section>
              <aside class="annex-panel">
                {b.block('section_title', '附件说明', 'section-title')}
                {simple_table(b, ['项目','说明'], annex_rows)}
                {kv_box(b, '联系人', record_title(records, rng, 8, 18), 'notice-kv')}
                {kv_box(b, '联系电话', f'010-{rng.randint(10000000,99999999)}', 'notice-kv')}
              </aside>
            </div>
            <div class="bulletin-foot">{b.block('signature', '发布单位：中央民族大学合作项目组', 'issuer-sign')}{b.block('date', date_text, 'issuer-date')}</div>
          </div>
          {b.block('footer', 'notice · refined variant %d' % variant, 'footer')}
        """
    elif variant == 3:
        agenda_items = "".join(
            f'<div class="agenda-row">{b.block("metadata", f"{8 + idx}:00", "agenda-time")}{b.block("list_item", record_text(records, rng, 30, 72), "agenda-text")}</div>'
            for idx in range(1, 6)
        )
        body = f"""
          <div class="meeting-notice">
            <header class="meeting-head">{b.block('document_title', doc['title'], 'meeting-title')}{b.block('metadata', issue_no, 'gongwen-no')}</header>
            <div class="meeting-grid">
              <section>{b.block('paragraph', record_text(records, rng, 90, 150), 'gongwen-lead')}{agenda_items}</section>
              <aside class="meeting-side">
                {kv_box(b, '时间', date_text, 'notice-kv')}
                {kv_box(b, '地点', record_title(records, rng, 8, 22), 'notice-kv')}
                {kv_box(b, '联系人', record_title(records, rng, 8, 18), 'notice-kv')}
              </aside>
            </div>
          </div>
          {b.block('footer', 'notice · meeting variant %d' % variant, 'footer')}
        """
    elif variant == 4:
        public_items = "".join(
            f'<div class="public-item">{b.block("list_item", record_text(records, rng, 34, 76), "public-copy")}</div>'
            for _ in range(7)
        )
        body = f"""
          <div class="public-board">
            {b.block('metadata', 'PUBLIC NOTICE', 'bulletin-mark')}
            {b.block('document_title', doc['title'], 'public-title')}
            <div class="public-list">{public_items}</div>
            <div class="public-foot">{b.block('signature', '发布单位：中央民族大学合作项目组', 'issuer-sign')}{b.block('date', date_text, 'issuer-date')}</div>
          </div>
          {b.block('footer', 'notice · public-board variant %d' % variant, 'footer')}
        """
    elif variant == 5:
        annex_rows = [[f"附件 {idx}", record_text(records, rng, 28, 62)] for idx in range(1, 6)]
        body = f"""
          <div class="annex-notice">
            <div class="annex-left">
              {b.block('document_title', doc['title'], 'gongwen-title')}
              {b.block('metadata', issue_no, 'gongwen-no')}
              {b.block('paragraph', record_text(records, rng, 120, 210), 'gongwen-lead')}
            </div>
            <aside class="annex-list">
              {b.block('section_title', '附件目录', 'section-title')}
              {simple_table(b, ['编号','说明'], annex_rows)}
            </aside>
          </div>
          <div class="gongwen-sign">{b.block('signature', '中央民族大学合作项目组', 'issuer-sign')}{b.block('date', date_text, 'issuer-date')}</div>
          {b.block('footer', 'notice · annex variant %d' % variant, 'footer')}
        """
    else:
        cards = "".join(
            f'<section class="notice-card">{b.block("section_title", record_title(records, rng, 8, 24), "notice-card-title")}{b.block("paragraph", record_text(records, rng, 36, 82), "notice-card-copy")}</section>'
            for _ in range(6)
        )
        body = f"""
          <div class="digest-notice-head">{b.block('document_title', doc['title'], 'bulletin-title')}{b.block('metadata', date_text, 'gongwen-no')}</div>
          <div class="notice-card-grid">{cards}</div>
          {b.block('footer', 'notice · digest variant %d' % variant, 'footer')}
        """

    gongwen_title_size = 32 if doc.get("html_lang") == "bo" else 48
    bulletin_title_size = 31 if doc.get("html_lang") == "bo" else 44
    body_size = 21 if doc.get("html_lang") == "bo" else 24
    extra = """
    .gongwen-header{text-align:center;border-top:10px solid %s;padding-top:18px;border-bottom:2px solid %s;padding-bottom:16px}
    .issuer-line{font-size:20px;letter-spacing:2px}
    .gongwen-title{font-size:%dpx;font-weight:900;line-height:1.28;margin-top:12px}
    .gongwen-no{font-size:18px;line-height:1.3;margin-top:8px}
    .recipient-line{font-size:25px;line-height:1.4;margin-top:34px}
    .gongwen-body{margin-top:18px}
    .gongwen-lead,.gongwen-tail{font-size:%dpx;line-height:1.66;text-indent:2em}
    .gongwen-item{font-size:%dpx;line-height:1.62;margin:12px 0}
    .gongwen-copy{font-size:%dpx;line-height:1.62}
    .gongwen-sign,.bulletin-foot{text-align:right;margin-top:44px}
    .issuer-sign,.issuer-date{font-size:23px;line-height:1.5}
    .bulletin-shell{border:1.5px solid %s;padding:18px 20px 20px;background:white}
    .bulletin-head{display:grid;grid-template-columns:1fr auto;gap:8px 18px;align-items:end;border-bottom:4px solid %s;padding-bottom:12px}
    .bulletin-mark{font-size:16px;letter-spacing:2px}
    .bulletin-title{grid-column:1/2;font-size:%dpx;font-weight:900;line-height:1.28}
    .bulletin-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:18px;margin-top:18px}
    .main-bulletin{border-right:1px solid %s;padding-right:18px}
    .annex-panel{display:grid;gap:12px}
    .notice-kv{border:1px solid %s;padding:8px 10px;min-height:58px}
    .meeting-notice{border-top:8px solid %s;background:white;padding-top:16px}
    .meeting-head{display:flex;justify-content:space-between;align-items:end;border-bottom:2px solid %s;padding-bottom:12px}
    .meeting-title{font-size:%dpx;font-weight:900;line-height:1.28}
    .meeting-grid{display:grid;grid-template-columns:1fr 300px;gap:18px;margin-top:18px}
    .meeting-side{display:grid;gap:12px;align-content:start}
    .agenda-row{display:grid;grid-template-columns:70px 1fr;gap:12px;border-bottom:1px dashed %s;padding:9px 0}
    .agenda-time{font-size:18px;font-weight:900;color:%s}
    .agenda-text{font-size:%dpx;line-height:1.4}
    .public-board{border:6px solid %s;background:%s;padding:28px}
    .public-title{font-size:%dpx;font-weight:900;text-align:center;line-height:1.3;border-bottom:2px solid %s;padding-bottom:12px}
    .public-list{margin-top:16px}
    .public-item{border-bottom:1px solid %s;padding:10px 0}
    .public-copy{font-size:%dpx;line-height:1.44}
    .public-foot{text-align:right;margin-top:24px}
    .annex-notice{display:grid;grid-template-columns:1fr 390px;gap:22px}
    .annex-left{border-left:8px solid %s;padding-left:18px}
    .annex-list{border:1.5px solid %s;background:white;padding:14px}
    .digest-notice-head{display:grid;grid-template-columns:1fr auto;align-items:end;border-bottom:4px solid %s;padding-bottom:12px}
    .notice-card-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}
    .notice-card{border:1.5px solid %s;background:white;padding:14px;min-height:150px}
    .notice-card-title{font-size:21px;font-weight:900;line-height:1.3}
    .notice-card-copy{font-size:18px;line-height:1.42;margin-top:8px}
    """ % (
        theme["accent"],
        theme["line"],
        gongwen_title_size,
        body_size,
        body_size,
        body_size,
        theme["line"],
        theme["accent"],
        bulletin_title_size,
        theme["line"],
        theme["line"],
        theme["accent"],
        theme["line"],
        gongwen_title_size,
        theme["line"],
        theme["accent"],
        body_size,
        theme["accent"],
        theme["soft"],
        bulletin_title_size,
        theme["line"],
        theme["line"],
        body_size,
        theme["accent"],
        theme["line"],
        theme["accent"],
        theme["line"],
    )
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"]) + extra, page_w, page_h, doc["html_lang"])


def book_textbook(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = 1120, 1600, 24
    paras = [record_text(records, rng, 90, 210) for _ in range(6)]
    if variant == 1:
        body = f"""
          {b.block('chapter_title', f"{variant}. {record_title(records, rng, 12, 42)}", 'chapter')}
          {b.block('paragraph', paras[0], 'lead')}
          <div class="book-cols">{''.join(b.block('paragraph', p, 'para') for p in paras[1:])}</div>
          {b.block('page_number', str(90 + variant), 'page-no')}
        """
        extra = ".chapter{font-size:42px;font-weight:700;border-bottom:2px solid %s;padding-bottom:12px}.lead{font-size:27px;line-height:1.38;margin:24px 0}.book-cols{columns:2;column-gap:34px}.para{font-size:24px;line-height:1.42;margin:0 0 16px;break-inside:avoid}.page-no{position:absolute;bottom:32px;left:0;right:0;text-align:center;color:%s}" % (theme["line"], theme["muted"])
    elif variant == 2:
        body = f"""
          <div class="chapter-opener">
            {b.block('metadata', 'CHAPTER %02d' % variant, 'chapter-no')}
            {b.block('chapter_title', doc['title'], 'chapter-open-title')}
            {b.block('paragraph', paras[0], 'lead')}
          </div>
          <div class="opener-notes">{''.join(b.block('list_item', record_text(records, rng, 30, 70), 'exercise-line') for _ in range(4))}</div>
          {b.block('page_number', str(100 + variant), 'page-no')}
        """
        extra = ".chapter-opener{min-height:760px;border-left:12px solid %s;padding-left:24px;display:flex;flex-direction:column;justify-content:center}.chapter-no{font-size:22px;color:%s;letter-spacing:2px}.chapter-open-title{font-size:56px;font-weight:900;line-height:1.4}.lead{font-size:27px;line-height:1.42;margin-top:24px}.opener-notes{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:28px}.exercise-line{border:1px solid %s;padding:12px;font-size:22px;line-height:1.35}.page-no{position:absolute;bottom:32px;right:78px;color:%s}" % (theme["accent"], theme["muted"], theme["line"], theme["muted"])
    elif variant == 3:
        rows = [[record_title(records, rng), record_text(records, rng, 30, 75)] for _ in range(4)]
        body = f"""
          {b.block('chapter_title', record_title(records, rng, 16, 46), 'chapter')}
          <div class="lesson-grid"><main>{''.join(b.block('paragraph', p, 'para') for p in paras[:4])}</main><aside class="panel">{b.block('section_title', 'Жишээ', 'section-title')}{simple_table(b, ['Үг','Тайлбар'], rows)}</aside></div>
          {b.block('page_number', str(110 + variant), 'page-no')}
        """
        extra = ".chapter{font-size:39px;font-weight:700;margin-bottom:22px}.lesson-grid{display:grid;grid-template-columns:1fr 340px;gap:28px}.para{font-size:24px;line-height:1.42;margin-bottom:18px}.page-no{position:absolute;bottom:32px;right:78px;color:%s}" % theme["muted"]
    elif variant == 4:
        figure_blocks = "".join(
            f'<div class="figure-card">{b.block("image", "", "book-image")}{b.block("caption", record_text(records, rng, 22, 48), "caption")}</div>'
            for _ in range(2)
        )
        body = f"""
          <div class="illustrated-head">{b.block('chapter_title', record_title(records, rng, 12, 36), 'chapter')}{b.block('metadata', '图文讲义', 'meta')}</div>
          <div class="illustrated-grid">
            <main>{''.join(b.block('paragraph', p, 'para') for p in paras[:3])}</main>
            <aside>{figure_blocks}</aside>
          </div>
          {b.block('page_number', str(120 + variant), 'page-no')}
        """
        extra = ".illustrated-head{display:flex;justify-content:space-between;border-bottom:3px solid %s;padding-bottom:12px}.chapter{font-size:38px;font-weight:800;line-height:1.3}.illustrated-grid{display:grid;grid-template-columns:1fr 360px;gap:24px;margin-top:22px}.para{font-size:24px;line-height:1.44;margin-bottom:16px}.figure-card{border:1px solid %s;padding:10px;margin-bottom:14px}.book-image{min-height:210px;background:%s;border:1px dashed %s}.caption{font-size:16px;line-height:1.3;margin-top:8px;color:%s}.page-no{position:absolute;bottom:32px;left:78px;color:%s}" % (theme["accent"], theme["line"], theme["soft"], theme["line"], theme["muted"], theme["muted"])
    elif variant == 5:
        body = f"""
          <div class="textbook-head">{b.block('chapter_title', doc['title'], 'chapter')}{b.block('metadata', 'Сургалтын хуудас', 'meta')}</div>
          <div class="exercise">{b.block('section_title', 'Дасгал', 'section-title')}{''.join(b.block('list_item', f"{i}. {record_text(records, rng, 38, 92)}", 'exercise-line') for i in range(1,7))}</div>
          <div class="reading">{b.block('section_title', 'Унших хэсэг', 'section-title')}{''.join(b.block('paragraph', p, 'para') for p in paras[:3])}</div>
          {b.block('page_number', str(130 + variant), 'page-no')}
        """
        extra = ".textbook-head{display:flex;justify-content:space-between;border-bottom:3px solid %s;padding-bottom:14px}.chapter{font-size:38px;font-weight:700}.exercise{background:%s;border:1px solid %s;padding:18px;margin:24px 0}.exercise-line{font-size:23px;line-height:1.35;border-bottom:1px dotted %s;padding:8px 0}.para{font-size:24px;line-height:1.42}.page-no{position:absolute;bottom:32px;left:78px;color:%s}" % (theme["accent"], theme["soft"], theme["line"], theme["line"], theme["muted"])
    else:
        vocab_rows = [[record_title(records, rng, 6, 18), record_text(records, rng, 24, 62)] for _ in range(8)]
        body = f"""
          <div class="vocab-page">
            <aside class="vocab-rail">{b.block('chapter_title', doc['title'], 'vocab-title')}{b.block('metadata', '词汇解释', 'meta')}</aside>
            <main class="vocab-main">
              {simple_table(b, ['词条','解释'], vocab_rows)}
              <div class="reading">{b.block('section_title', '阅读', 'section-title')}{''.join(b.block('paragraph', p, 'para') for p in paras[:2])}</div>
            </main>
          </div>
          {b.block('page_number', str(140 + variant), 'page-no')}
        """
        extra = ".vocab-page{display:grid;grid-template-columns:230px 1fr;gap:24px}.vocab-rail{border-right:6px solid %s;padding-right:16px}.vocab-title{font-size:36px;font-weight:900;line-height:1.35;writing-mode:vertical-rl}.vocab-main table{font-size:21px}.reading{margin-top:20px;border-top:2px solid %s;padding-top:12px}.para{font-size:23px;line-height:1.42}.page-no{position:absolute;bottom:32px;right:78px;color:%s}" % (theme["accent"], theme["line"], theme["muted"])
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"]) + extra, page_w, page_h, doc["html_lang"])


def poster_flyer(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = 1080, 1500, 25
    headline = record_title(records, rng, 16, 54)
    if variant == 1:
        body = f"""
          <div class="hero">{b.block('image', '', 'image-box')}{b.block('document_title', headline, 'poster-title')}{b.block('paragraph', record_text(records, rng, 70, 150), 'poster-copy')}</div>
          <div class="cta-row">{b.block('metadata', '2026', 'cta')}{b.block('metadata', 'MN DATA', 'cta')}{b.block('metadata', 'Туршилт', 'cta')}</div>
          {b.block('footer', 'poster · variant %d' % variant, 'footer')}
        """
        extra = ".hero{min-height:920px;display:grid;grid-template-rows:420px auto auto;gap:22px;align-content:start}.image-box{min-height:420px}.poster-title{font-size:60px;font-weight:900;line-height:1.34;color:%s}.poster-copy{font-size:29px;line-height:1.25}.cta-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-top:40px}.cta{background:%s;color:white;text-align:center;padding:18px;font-weight:700}" % (theme["accent"], theme["accent"])
    elif variant == 2:
        body = f"""
          <div class="event-poster">
            {b.block('metadata', 'EVENT', 'event-tag')}
            {b.block('document_title', headline, 'poster-title')}
            {b.block('paragraph', record_text(records, rng, 70, 140), 'poster-copy')}
            <div class="event-meta">{kv_box(b, 'Date', '2026-%02d-%02d' % (rng.randint(1,12), rng.randint(1,28)), 'event-kv')}{kv_box(b, 'Place', record_title(records, rng, 8, 22), 'event-kv')}</div>
          </div>
          {b.block('footer', 'poster · event variant %d' % variant, 'footer')}
        """
        extra = ".event-poster{min-height:1140px;border:12px solid %s;padding:46px;display:flex;flex-direction:column;justify-content:center}.event-tag{font-size:24px;font-weight:900;letter-spacing:4px;color:%s}.poster-title{font-size:68px;font-weight:900;line-height:1.32;margin:28px 0}.poster-copy{font-size:30px;line-height:1.35}.event-meta{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:44px}.event-kv{border-top:2px solid %s;padding-top:10px}" % (theme["accent"], theme["accent"], theme["line"])
    elif variant == 3:
        body = f"""
          <div class="diagonal">{b.block('document_title', headline, 'poster-title')}{b.block('paragraph', record_text(records, rng, 60, 130), 'poster-copy')}</div>
          <div class="tile-grid">{''.join(b.block('list_item', record_text(records, rng, 28, 62), 'tile') for _ in range(6))}</div>
          {b.block('footer', 'poster · variant %d' % variant, 'footer')}
        """
        extra = ".diagonal{background:%s;padding:44px 38px;transform:skewY(-2deg);margin:40px 0}.poster-title{font-size:54px;font-weight:900;line-height:1.34}.poster-copy{font-size:28px;line-height:1.28}.tile-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:58px}.tile{border:2px solid %s;padding:22px;font-size:25px;line-height:1.22;background:white}" % (theme["soft"], theme["line"])
    elif variant == 4:
        body = f"""
          <div class="lecture-poster">
            <aside class="lecture-date">{b.block('metadata', '2026', 'date-year')}{b.block('metadata', '%02d/%02d' % (rng.randint(1,12), rng.randint(1,28)), 'date-day')}</aside>
            <main>{b.block('document_title', headline, 'poster-title')}{b.block('paragraph', record_text(records, rng, 80, 160), 'poster-copy')}{''.join(b.block('list_item', record_text(records, rng, 22, 50), 'lecture-line') for _ in range(4))}</main>
          </div>
          {b.block('footer', 'poster · lecture variant %d' % variant, 'footer')}
        """
        extra = ".lecture-poster{display:grid;grid-template-columns:240px 1fr;gap:28px;min-height:1120px;align-items:center}.lecture-date{border-right:8px solid %s;padding-right:20px;text-align:right}.date-year{font-size:34px;font-weight:900}.date-day{font-size:60px;font-weight:900;line-height:1.5}.poster-title{font-size:58px;font-weight:900;line-height:1.34}.poster-copy{font-size:28px;line-height:1.34;margin:24px 0}.lecture-line{font-size:23px;line-height:1.32;border-bottom:1px solid %s;padding:10px 0}" % (theme["accent"], theme["line"])
    elif variant == 5:
        body = f"""
          <div class="centered">{b.block('metadata', 'SPECIAL', 'stamp')}{b.block('document_title', headline, 'poster-title')}{b.block('paragraph', record_text(records, rng, 80, 170), 'poster-copy')}{b.block('image', '', 'image-box')}</div>
          {b.block('footer', 'poster · variant %d' % variant, 'footer')}
        """
        extra = ".centered{text-align:center;border:8px solid %s;min-height:1180px;padding:46px}.poster-title{font-size:60px;font-weight:900;line-height:1.34;margin:36px 0}.poster-copy{font-size:29px;line-height:1.28}.image-box{min-height:280px;margin-top:42px}" % theme["accent"]
    else:
        panels = "".join(
            f'<section class="fold-panel">{b.block("section_title", record_title(records, rng, 8, 22), "fold-title")}{b.block("paragraph", record_text(records, rng, 32, 76), "fold-copy")}</section>'
            for _ in range(4)
        )
        body = f"""
          <div class="fold-flyer">
            <header>{b.block('document_title', headline, 'poster-title')}{b.block('metadata', '折页式传单', 'event-tag')}</header>
            <div class="fold-grid">{panels}</div>
          </div>
          {b.block('footer', 'poster · folded flyer variant %d' % variant, 'footer')}
        """
        extra = ".fold-flyer{border-top:12px solid %s;border-bottom:12px solid %s;padding:28px 0}.fold-flyer header{display:flex;justify-content:space-between;align-items:end;border-bottom:2px solid %s;padding-bottom:16px}.poster-title{font-size:48px;font-weight:900;line-height:1.34}.fold-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:22px}.fold-panel{border:1.5px solid %s;padding:18px;min-height:250px;background:white}.fold-title{font-size:26px;font-weight:900;line-height:1.3}.fold-copy{font-size:22px;line-height:1.36;margin-top:12px}" % (theme["accent"], theme["accent"], theme["line"], theme["line"])
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"], 70, 62) + extra, page_w, page_h, doc["html_lang"])


def certificate(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = (1500, 1060, 25) if variant % 2 else (1060, 1500, 25)
    cert_no = f"CERT-{rng.randint(10000,99999)}"
    if variant == 1:
        body = f"""
          <div class="cert-frame classic">
            {b.block('document_title', doc['title'], 'cert-title')}
            {b.block('field_value', record_title(records, rng, 14, 42), 'recipient')}
            {b.block('paragraph', record_text(records, rng, 90, 190), 'cert-body')}
            <div class="cert-meta">{b.block('date', '2026-%02d-%02d' % (rng.randint(1,12), rng.randint(1,28)), 'text')}{b.block('signature', 'Гарын үсэг: ____________', 'text')}{b.block('stamp', 'БАТЛАВ', 'stamp')}</div>
          </div>
          {b.block('footer', 'certificate · classic variant %d' % variant, 'footer')}
        """
    elif variant == 2:
        body = f"""
          <div class="proof-sheet">
            <header>{b.block('document_title', doc['title'], 'cert-title')}{b.block('metadata', cert_no, 'cert-no')}</header>
            {b.block('paragraph', record_text(records, rng, 140, 260), 'proof-body')}
            <div class="proof-fields">{kv_box(b, '对象', record_title(records, rng, 10, 30), 'proof-kv')}{kv_box(b, '日期', '2026-%02d-%02d' % (rng.randint(1,12), rng.randint(1,28)), 'proof-kv')}</div>
            <div class="proof-sign">{b.block('signature', '证明单位：中央民族大学合作项目组', 'issuer-sign')}{b.block('stamp', '证明专用', 'stamp')}</div>
          </div>
          {b.block('footer', 'certificate · proof variant %d' % variant, 'footer')}
        """
    elif variant == 3:
        body = f"""
          <div class="award-ribbon">
            {b.block('metadata', cert_no, 'cert-no')}
            {b.block('document_title', doc['title'], 'cert-title')}
            <div class="ribbon-name">{b.block('field_value', record_title(records, rng, 12, 36), 'recipient')}</div>
            {b.block('paragraph', record_text(records, rng, 90, 170), 'cert-body')}
            <div class="seal-row">{b.block('stamp', 'AWARD', 'stamp')}{b.block('date', '2026', 'text')}</div>
          </div>
          {b.block('footer', 'certificate · award variant %d' % variant, 'footer')}
        """
    elif variant == 4:
        body = f"""
          <div class="compact-cert">
            <aside>{b.block('metadata', cert_no, 'cert-no')}{b.block('stamp', 'OK', 'stamp')}</aside>
            <main>{b.block('document_title', doc['title'], 'cert-title')}{b.block('paragraph', record_text(records, rng, 120, 220), 'cert-body')}{kv_box(b, 'Recipient', record_title(records, rng, 10, 30), 'proof-kv')}</main>
          </div>
          {b.block('footer', 'certificate · compact variant %d' % variant, 'footer')}
        """
    elif variant == 5:
        body = f"""
          <div class="numbered-proof">
            {b.block('metadata', cert_no, 'cert-no')}
            {b.block('document_title', doc['title'], 'cert-title')}
            <div class="numbered-lines">{''.join(kv_box(b, record_title(records, rng, 6, 14), record_text(records, rng, 14, 36), 'proof-kv') for _ in range(5))}</div>
            {b.block('paragraph', record_text(records, rng, 80, 150), 'cert-body')}
          </div>
          {b.block('footer', 'certificate · numbered variant %d' % variant, 'footer')}
        """
    else:
        body = f"""
          <div class="digital-cert">
            <div class="digital-head">{b.block('document_title', doc['title'], 'cert-title')}{b.block('metadata', cert_no, 'cert-no')}</div>
            <div class="digital-grid">{kv_box(b, 'Name', record_title(records, rng, 10, 28), 'proof-kv')}{kv_box(b, 'Valid', '2026', 'proof-kv')}{kv_box(b, 'Issuer', 'CMUC', 'proof-kv')}</div>
            {b.block('paragraph', record_text(records, rng, 70, 130), 'cert-body')}
          </div>
          {b.block('footer', 'certificate · digital variant %d' % variant, 'footer')}
        """
    extra = ".cert-frame{min-height:%dpx;border:10px double %s;padding:62px;text-align:center;display:flex;flex-direction:column;justify-content:center}.cert-title{font-size:50px;font-weight:800;line-height:1.36}.recipient{font-size:40px;font-weight:700;margin:30px 0 22px;border-bottom:2px solid %s;display:inline-block;padding:0 40px 10px}.cert-body{font-size:26px;line-height:1.42;max-width:900px;margin:0 auto}.cert-meta{display:grid;grid-template-columns:1fr 1fr 150px;gap:20px;align-items:center;margin-top:44px}.stamp{transform:rotate(-8deg)}.cert-no{font-size:18px;color:%s;letter-spacing:1px}.proof-sheet{border-left:10px solid %s;padding-left:34px;min-height:%dpx;display:flex;flex-direction:column;justify-content:center}.proof-sheet header,.digital-head{display:flex;justify-content:space-between;align-items:end;border-bottom:2px solid %s;padding-bottom:12px}.proof-body{font-size:28px;line-height:1.6;margin:34px 0}.proof-fields,.digital-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.proof-kv{border:1px solid %s;padding:10px 12px;min-height:66px}.proof-sign{text-align:right;margin-top:38px}.award-ribbon{min-height:%dpx;border:14px solid %s;padding:54px;text-align:center;background:%s}.ribbon-name{border-top:3px solid %s;border-bottom:3px solid %s;margin:28px auto;padding:18px;max-width:720px}.seal-row{display:flex;justify-content:center;gap:34px;margin-top:34px}.compact-cert{display:grid;grid-template-columns:220px 1fr;gap:28px;align-items:center;border:5px solid %s;padding:44px;min-height:%dpx}.compact-cert aside{border-right:3px solid %s;padding-right:18px;display:grid;gap:18px}.numbered-proof{border:2px solid %s;padding:34px;min-height:%dpx}.numbered-lines{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:24px 0}.digital-cert{border-radius:0;border:2px solid %s;padding:34px;min-height:%dpx;background:white}" % (page_h - 160, theme["accent"], theme["line"], theme["muted"], theme["accent"], page_h - 160, theme["line"], theme["line"], page_h - 160, theme["accent"], theme["soft"], theme["line"], theme["line"], theme["accent"], page_h - 160, theme["line"], theme["line"], page_h - 160, theme["accent"], page_h - 160)
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"]) + extra, page_w, page_h, doc["html_lang"])


def form_registration(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = 1240, 1754, 21
    profile_fields = [
        ("Овог нэр", record_title(records, rng, 8, 20)),
        ("Регистр", f"{rng.randint(10000000, 99999999)}"),
        ("Төрсөн өдөр", f"19{rng.randint(70,99)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"),
        ("Утас", f"99{rng.randint(100000,999999)}"),
        ("Байгууллага", record_title(records, rng, 8, 22)),
        ("Албан тушаал", record_title(records, rng, 8, 22)),
    ]
    profile_html = "".join(kv_box(b, label, value, "profile-box") for label, value in profile_fields)
    checklist = "".join(
        f'<div class="check-row">{b.block("field_label", str(idx), "check-index")}{b.block("field_value", record_text(records, rng, 28, 68), "check-copy")}{b.block("option", "[ ]", "check-box")}</div>'
        for idx in range(1, 6 + variant % 3)
    )
    review_rows = [[record_title(records, rng, 8, 20), rng.choice(["тийм", "үгүй", "засах"]), record_text(records, rng, 22, 52)] for _ in range(4)]

    if variant == 1:
        body = f"""
          <div class="form-header">{b.block('document_title', doc['title'], 'form-title')}{b.block('metadata', 'Application Form', 'form-meta')}</div>
          <div class="profile-grid">{profile_html}</div>
          <div class="consent-row">
            {option_group(b, 'Хүсэлтийн төрөл', ['Шинэ бүртгэл', 'Сунгалт', 'Засвар'], variant % 3, 'option-card')}
            {option_group(b, 'Материал шалгалт', ['Бүрэн', 'Дутуу', 'Нэмэлт шаардах'], (variant + 1) % 3, 'option-card')}
          </div>
          <section class="check-panel">{b.block('section_title', 'Материалын шалгах хуудас', 'section-title')}{checklist}</section>
          <div class="sign-band">
            {kv_box(b, 'Хүлээн авсан ажилтан', record_title(records, rng, 6, 18), 'sign-box')}
            {kv_box(b, 'Өргөдөл гаргагч', record_title(records, rng, 6, 18), 'sign-box')}
            {kv_box(b, 'Огноо', f'2026-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}', 'sign-box')}
          </div>
          {b.block('footer', 'form · refined variant %d' % variant, 'footer')}
        """
    elif variant == 2:
        approval_steps = "".join(kv_box(b, label, record_title(records, rng, 6, 18), "approval-step") for label in ["初审", "复核", "批准"])
        body = f"""
          <div class="approval-form">
            <header>{b.block('document_title', doc['title'], 'form-title')}{b.block('metadata', f'APP-{rng.randint(1000,9999)}', 'form-meta')}</header>
            <div class="inline-fields">{profile_html}</div>
            <section class="long-answer">{b.block('field_label', '申请事项', 'field-label')}{''.join(b.block('paragraph', record_text(records, rng, 42, 92), 'answer-line') for _ in range(3))}</section>
            <div class="approval-flow-form">{approval_steps}</div>
          </div>
          {b.block('footer', 'form · approval variant %d' % variant, 'footer')}
        """
    elif variant == 3:
        body = f"""
          <div class="questionnaire-shell">
            <aside class="form-side-note">
              {b.block('document_title', doc['title'], 'form-title vertical')}
              {b.block('paragraph', record_text(records, rng, 70, 140), 'side-copy')}
            </aside>
            <main class="questionnaire-main">
              <div class="inline-fields">{profile_html}</div>
              {option_group(b, 'Холбоо барих хэлбэр', ['Утас', 'И-мэйл', 'Биечлэн'], variant % 3, 'option-band')}
              <section class="review-table">
                {b.block('section_title', 'Шалгалтын тэмдэглэл', 'section-title')}
                {simple_table(b, ['Үзүүлэлт','Статус','Тэмдэглэл'], review_rows)}
              </section>
              <section class="long-answer">
                {b.block('field_label', 'Нэмэлт тайлбар', 'field-label')}
                {''.join(b.block('paragraph', record_text(records, rng, 45, 96), 'answer-line') for _ in range(4))}
              </section>
            </main>
          </div>
          {b.block('footer', 'form · refined variant %d' % variant, 'footer')}
        """
    elif variant == 4:
        body = f"""
          <div class="checklist-form-head">{b.block('document_title', doc['title'], 'form-title')}{b.block('metadata', '材料核验表', 'form-meta')}</div>
          <div class="checklist-layout">
            <section class="check-panel">{b.block('section_title', '核验清单', 'section-title')}{checklist}</section>
            <aside class="check-aside">{option_group(b, '处理结论', ['通过', '补充材料', '退回'], variant % 3, 'option-card')}{kv_box(b, '经办人', record_title(records, rng, 6, 18), 'sign-box')}</aside>
          </div>
          {b.block('footer', 'form · checklist variant %d' % variant, 'footer')}
        """
    elif variant == 5:
        card_rows = "".join(kv_box(b, label, value, "archive-field") for label, value in profile_fields)
        body = f"""
          <div class="archive-card">
            <aside class="archive-rail">{b.block('document_title', doc['title'], 'form-title vertical')}{b.block('metadata', f'ID {rng.randint(10000,99999)}', 'form-meta')}</aside>
            <main class="archive-main">{card_rows}<section class="long-answer">{b.block('field_label', '备注', 'field-label')}{b.block('paragraph', record_text(records, rng, 70, 140), 'answer-line')}</section></main>
          </div>
          {b.block('footer', 'form · archive-card variant %d' % variant, 'footer')}
        """
    else:
        survey_items = "".join(
            f'<div class="survey-row">{b.block("field_label", str(i), "check-index")}{b.block("field_value", record_text(records, rng, 28, 64), "check-copy")}<div class="survey-options">{"".join(b.block("option", ("[x] " if j == 0 else "[ ] ") + opt, "option-line") for j, opt in enumerate(["A", "B", "C"]))}</div></div>'
            for i in range(1, 6)
        )
        body = f"""
          <div class="survey-form">
            {b.block('document_title', doc['title'], 'form-title')}
            {b.block('paragraph', record_text(records, rng, 60, 120), 'side-copy')}
            <div class="survey-list">{survey_items}</div>
            <div class="survey-signs">{kv_box(b, '填写人', record_title(records, rng, 6, 18), 'sign-box')}{kv_box(b, '日期', '2026-%02d-%02d' % (rng.randint(1,12), rng.randint(1,28)), 'sign-box')}</div>
          </div>
          {b.block('footer', 'form · survey variant %d' % variant, 'footer')}
        """

    form_title_size = 30 if doc.get("html_lang") == "bo" else 44
    option_size = 15 if doc.get("html_lang") == "bo" else 18
    check_copy_size = 17 if doc.get("html_lang") == "bo" else 19
    extra = """
    .form-header{display:grid;grid-template-columns:1fr auto;align-items:end;border-bottom:4px solid %s;padding-bottom:12px}
    .form-title{font-size:%dpx;font-weight:900;line-height:1.28}
    .form-title.vertical{writing-mode:vertical-rl;font-size:%dpx}
    .form-meta{font-size:16px;letter-spacing:2px}
    .profile-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:18px}
    .profile-box,.sign-box{border:1px solid %s;padding:8px 10px;background:white;min-height:70px}
    .consent-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:16px}
    .option-card,.option-band{border:1px solid %s;padding:10px 12px;background:%s}
    .option-line{font-size:%dpx;line-height:1.35}
    .check-panel{border:1px solid %s;padding:14px;margin-top:16px;background:white}
    .check-row{display:grid;grid-template-columns:34px 1fr 56px;gap:10px;align-items:start;padding:8px 0;border-bottom:1px dashed %s}
    .check-index{font-size:16px;padding-top:4px}
    .check-copy{font-size:%dpx;line-height:1.42}
    .check-box{font-size:17px;line-height:1.45;text-align:right}
    .sign-band{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:18px}
    .questionnaire-shell{display:grid;grid-template-columns:220px 1fr;gap:22px}
    .form-side-note{border-right:5px solid %s;padding-right:16px}
    .side-copy{font-size:19px;line-height:1.34;margin-top:18px}
    .questionnaire-main{padding-top:2px}
    .inline-fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .review-table{margin-top:16px}
    .long-answer{border:1px solid %s;margin-top:16px;padding:12px}
    .answer-line{font-size:19px;line-height:1.55;border-bottom:1px solid %s;padding:8px 0}
    .approval-form{border:1.5px solid %s;background:white;padding:18px}
    .approval-form header,.checklist-form-head{display:flex;justify-content:space-between;align-items:end;border-bottom:4px solid %s;padding-bottom:12px}
    .approval-flow-form{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:16px}
    .approval-step{border:1.5px solid %s;background:%s;padding:10px;min-height:78px}
    .checklist-layout{display:grid;grid-template-columns:1fr 310px;gap:16px;margin-top:16px}
    .check-aside{display:grid;gap:14px;align-content:start}
    .archive-card{display:grid;grid-template-columns:190px 1fr;gap:18px;border:2px solid %s;background:white;padding:18px}
    .archive-rail{border-right:5px solid %s;padding-right:14px}
    .archive-main{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .archive-field{border-bottom:1px solid %s;padding:8px 4px;min-height:62px}
    .archive-main .long-answer{grid-column:1/3}
    .survey-form{border-top:8px solid %s;background:white;padding-top:16px}
    .survey-list{display:grid;gap:12px;margin-top:16px}
    .survey-row{display:grid;grid-template-columns:34px 1fr 220px;gap:12px;align-items:start;border:1px solid %s;padding:10px}
    .survey-options{display:flex;gap:8px;justify-content:flex-end}
    .survey-options .field-label{display:none}
    .survey-options .option-line{min-width:52px;min-height:32px;padding:5px 8px;text-align:center;border:1px solid %s;background:white}
    .survey-signs{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}
    """ % (
        theme["accent"],
        form_title_size,
        form_title_size + 2,
        theme["line"],
        theme["line"],
        theme["soft"],
        option_size,
        theme["line"],
        theme["line"],
        check_copy_size,
        theme["accent"],
        theme["line"],
        theme["line"],
        theme["accent"],
        theme["accent"],
        theme["line"],
        theme["soft"],
        theme["accent"],
        theme["line"],
        theme["line"],
        theme["accent"],
        theme["line"],
        theme["line"],
    )
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"], 64, 54) + extra, page_w, page_h, doc["html_lang"])


def schedule_timetable(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = 1240, 1650, 22
    if variant == 1:
        days = ["Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан"]
        slots = ["08:00", "10:00", "14:00", "16:00"]
        rows = [[slot] + [record_title(records, rng, 8, 24) for _ in days] for slot in slots]
        body = f"""
          <div class="time-head">{b.block('document_title', doc['title'], 'title')}{b.block('metadata', '周课表 · 2026', 'meta')}</div>
          <div class="matrix">{simple_table(b, ['Цаг'] + days, rows)}</div>
          <div class="legend">{''.join(b.block('list_item', record_text(records, rng, 28, 70), 'legend-item') for _ in range(4))}</div>
          {b.block('footer', 'schedule · week variant %d' % variant, 'footer')}
        """
    elif variant == 2:
        rows = [[f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}", f"{rng.randint(8,16)}:00", record_title(records, rng, 8, 24), record_title(records, rng, 6, 16)] for _ in range(7)]
        body = f"""
          <div class="exam-head">{b.block('document_title', doc['title'], 'title')}{b.block('metadata', '考试安排', 'stamp')}</div>
          {simple_table(b, ['日期','时间','科目','地点'], rows)}
          {b.block('footer', 'schedule · exam variant %d' % variant, 'footer')}
        """
    elif variant == 3:
        agenda = "".join(
            f'<div class="timeline-item">{b.block("metadata", f"{8+i}:30", "time-dot")}{b.block("list_item", record_text(records, rng, 28, 70), "timeline-text")}</div>'
            for i in range(8)
        )
        body = f"""
          <div class="timeline-shell">{b.block('document_title', doc['title'], 'title')}{agenda}</div>
          {b.block('footer', 'schedule · agenda variant %d' % variant, 'footer')}
        """
    elif variant == 4:
        rows = [[f"{rng.randint(6,22):02d}:{rng.choice(['00','15','30','45'])}", record_title(records, rng, 8, 22), record_title(records, rng, 8, 22), rng.choice(["A","B","C"])] for _ in range(9)]
        body = f"""
          <div class="route-head">{b.block('document_title', doc['title'], 'title')}{b.block('metadata', '班次时刻表', 'meta')}</div>
          {simple_table(b, ['时间','起点','终点','班次'], rows)}
          {b.block('footer', 'schedule · route variant %d' % variant, 'footer')}
        """
    elif variant == 5:
        rows = [[record_title(records, rng, 6, 18), f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}", rng.choice(["白班","夜班","备班"]), record_text(records, rng, 18, 44)] for _ in range(8)]
        body = f"""
          <div class="duty-board">{b.block('document_title', doc['title'], 'title')}{simple_table(b, ['人员','日期','班次','备注'], rows)}</div>
          {b.block('footer', 'schedule · duty variant %d' % variant, 'footer')}
        """
    else:
        flow = "".join(
            f'<section class="flow-card">{b.block("metadata", f"STEP {i}", "flow-step")}{b.block("section_title", record_title(records, rng, 8, 24), "flow-title")}{b.block("paragraph", record_text(records, rng, 30, 68), "flow-copy")}</section>'
            for i in range(1, 7)
        )
        body = f"""
          <div class="flow-head">{b.block('document_title', doc['title'], 'title')}{b.block('metadata', '活动流程', 'meta')}</div>
          <div class="flow-grid">{flow}</div>
          {b.block('footer', 'schedule · flow variant %d' % variant, 'footer')}
        """
    extra = ".time-head,.exam-head,.route-head,.flow-head{display:flex;justify-content:space-between;align-items:end;border-bottom:4px solid %s;padding-bottom:16px}.matrix{margin-top:24px}.matrix td,.matrix th{height:120px}.legend{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:22px}.legend-item{border-left:6px solid %s;background:white;padding:12px;font-size:21px}.exam-head{margin-bottom:18px}.timeline-shell{border-left:8px solid %s;padding-left:22px}.timeline-shell .title{margin-bottom:22px}.timeline-item{display:grid;grid-template-columns:90px 1fr;gap:14px;border-bottom:1px solid %s;padding:14px 0}.time-dot{font-size:24px;font-weight:900;color:%s}.timeline-text{font-size:22px;line-height:1.4}.route-head{margin-bottom:18px}.duty-board{border:2px solid %s;padding:18px;background:white}.duty-board .title{border-bottom:3px solid %s;padding-bottom:12px;margin-bottom:16px}.flow-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-top:18px}.flow-card{border:1.5px solid %s;background:white;padding:14px;min-height:190px}.flow-step{font-size:14px;color:%s;font-weight:900}.flow-title{font-size:22px;font-weight:900;line-height:1.3}.flow-copy{font-size:18px;line-height:1.38;margin-top:8px}" % (theme["accent"], theme["accent"], theme["accent"], theme["line"], theme["accent"], theme["line"], theme["accent"], theme["line"], theme["muted"])
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"]) + extra, page_w, page_h, doc["html_lang"])


def report_brief(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = 1240, 1754, 23
    metrics = "".join(f'<div class="metric">{b.block("metadata", label, "small")}{b.block("metric", str(rng.randint(10,99)), "metric-val")}</div>' for label in ["Нийт", "Шинэ", "Хянасан", "Үлдсэн"])
    rows = [[record_title(records, rng), record_text(records, rng, 45, 105), rng.choice(["A","B","C"])] for _ in range(5 + variant % 3)]
    if variant == 1:
        body = f"""
          {b.block('document_title', doc['title'], 'title')}{b.block('document_subtitle', record_text(records, rng, 55, 120), 'subtitle')}
          <div class="metrics">{metrics}</div><div class="report-grid"><section>{simple_table(b, ['Сэдэв','Тайлбар','Түвшин'], rows)}</section><aside class="panel">{b.block('section_title', 'Дүгнэлт', 'section-title')}{b.block('paragraph', record_text(records, rng, 120, 260), 'text')}</aside></div>
          {b.block('footer', 'report · variant %d' % variant, 'footer')}
        """
        extra = ".metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}.metric{background:white;border:1.5px solid %s;padding:14px}.metric-val{font-size:38px;font-weight:700;color:%s}.report-grid{display:grid;grid-template-columns:1fr 330px;gap:22px}" % (theme["line"], theme["accent"])
    elif variant == 2:
        cover_points = "".join(b.block("list_item", record_text(records, rng, 28, 62), "cover-point") for _ in range(4))
        body = f"""
          <div class="brief-cover">{b.block('metadata', 'BRIEF', 'stamp')}{b.block('metadata', 'Report Cycle · 2026', 'cover-meta')}{b.block('document_title', doc['title'], 'cover-title')}{b.block('paragraph', record_text(records, rng, 90, 170), 'cover-summary')}<div class="cover-points">{cover_points}</div>{metrics}</div>
          {b.block('footer', 'report · cover variant %d' % variant, 'footer')}
        """
        extra = ".brief-cover{min-height:1180px;border-left:12px solid %s;padding-left:30px;display:flex;flex-direction:column;justify-content:center}.cover-meta{font-size:18px;color:%s;letter-spacing:1px;margin-top:12px}.cover-title{font-size:56px;font-weight:900;line-height:1.4}.cover-summary{font-size:28px;line-height:1.42;margin:28px 0}.cover-points{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px}.cover-point{border:1px solid %s;padding:10px;font-size:19px;line-height:1.32}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.metric{border:1px solid %s;padding:14px}.metric-val{font-size:36px;font-weight:900;color:%s}" % (theme["accent"], theme["muted"], theme["line"], theme["line"], theme["accent"])
    elif variant == 3:
        body = f"""
          <div class="brief-head">{b.block('document_title', doc['title'], 'title')}{b.block('metadata', 'Brief No.%03d' % variant, 'stamp')}</div>
          <div class="two-notes">{b.block('paragraph', record_text(records, rng, 120, 240), 'panel text')}{b.block('paragraph', record_text(records, rng, 120, 240), 'panel text')}</div>
          {simple_table(b, ['Сэдэв','Тайлбар','Түвшин'], rows)}
          {b.block('footer', 'report · variant %d' % variant, 'footer')}
        """
        extra = ".brief-head{display:flex;justify-content:space-between;border-bottom:4px double %s;padding-bottom:16px}.two-notes{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:22px 0}" % theme["accent"]
    elif variant == 4:
        chart_blocks = "".join(f'<div class="chart-box">{b.block("image", "", "chart-placeholder")}{b.block("caption", record_text(records, rng, 20, 46), "caption")}</div>' for _ in range(2))
        body = f"""
          <div class="chart-report-head">{b.block('document_title', doc['title'], 'title')}{b.block('metadata', '图表报告', 'meta')}</div>
          <div class="chart-report-grid"><section>{chart_blocks}</section><aside>{metrics}</aside></div>
          {b.block('paragraph', record_text(records, rng, 120, 220), 'text')}
          {b.block('footer', 'report · chart variant %d' % variant, 'footer')}
        """
        extra = ".chart-report-head{display:flex;justify-content:space-between;border-bottom:3px solid %s;padding-bottom:12px}.chart-report-grid{display:grid;grid-template-columns:1fr 320px;gap:18px;margin:20px 0}.chart-box{border:1.5px solid %s;padding:12px;margin-bottom:14px}.chart-placeholder{min-height:250px;background:linear-gradient(135deg,%s,#fff);border:1px dashed %s}.metrics{display:grid;gap:12px}.metric{border:1px solid %s;padding:12px}.metric-val{font-size:36px;font-weight:900;color:%s}" % (theme["accent"], theme["line"], theme["soft"], theme["line"], theme["line"], theme["accent"])
    elif variant == 5:
        action_items = "".join(b.block("list_item", record_text(records, rng, 35, 80), "action-item") for _ in range(7))
        body = f"""
          <div class="memo-report">{b.block('document_title', doc['title'], 'title')}{b.block('metadata', 'Action Memo · 2026', 'meta')}{b.block('paragraph', record_text(records, rng, 100, 180), 'text')}<div class="memo-meta">{kv_box(b, '编号', f'R-{rng.randint(100,999)}', 'audit-box')}{kv_box(b, '负责人', record_title(records, rng, 6, 18), 'audit-box')}</div><section>{b.block('section_title', '行动项', 'section-title')}{action_items}</section></div>
          {b.block('footer', 'report · action memo variant %d' % variant, 'footer')}
        """
        extra = ".memo-report{border-top:8px solid %s;padding-top:18px}.memo-report .text{font-size:23px;line-height:1.5}.memo-meta{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:14px 0}.audit-box{border:1px solid %s;padding:8px 10px;min-height:60px}.action-item{border-bottom:1px solid %s;padding:10px 0;font-size:21px;line-height:1.35}" % (theme["accent"], theme["line"], theme["line"])
    else:
        rows2 = [[record_title(records, rng, 8, 20), str(rng.randint(10,99)), record_text(records, rng, 22, 52)] for _ in range(7)]
        body = f"""
          <div class="dashboard-report">
            <aside class="dash-side">{b.block('document_title', doc['title'], 'dash-title')}{metrics}</aside>
            <main>{simple_table(b, ['指标','数值','说明'], rows2)}{b.block('paragraph', record_text(records, rng, 90, 170), 'text')}</main>
          </div>
          {b.block('footer', 'report · dashboard variant %d' % variant, 'footer')}
        """
        extra = ".dashboard-report{display:grid;grid-template-columns:280px 1fr;gap:18px}.dash-side{background:%s;border:1.5px solid %s;padding:16px}.dash-title{font-size:34px;font-weight:900;line-height:1.3}.metrics{display:grid;gap:12px;margin-top:20px}.metric{background:white;border:1px solid %s;padding:12px}.metric-val{font-size:34px;font-weight:900;color:%s}" % (theme["soft"], theme["line"], theme["line"], theme["accent"])
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"]) + extra, page_w, page_h, doc["html_lang"])


def menu_price_list(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = 980, 1380, 23
    items = [(record_title(records, rng, 8, 28), record_text(records, rng, 25, 65), f"{rng.randint(8,88)},000") for _ in range(10)]
    if variant == 1:
        item_html = "".join(f'<div class="menu-item">{b.block("item_name", n, "name")}{b.block("item_desc", d, "desc")}{b.block("price", p, "price")}</div>' for n, d, p in items)
        body = f"""
          {b.block('document_title', doc['title'], 'menu-title')}{b.block('document_subtitle', 'Үнийн жагсаалт / туршилтын загвар', 'subtitle')}
          <div class="menu-list">{item_html}</div>{b.block('footer', 'menu · variant %d' % variant, 'footer')}
        """
        extra = ".menu-title{font-size:54px;font-weight:900;text-align:center;border-bottom:4px solid %s;padding-bottom:16px}.menu-list{margin-top:28px}.menu-item{display:grid;grid-template-columns:1fr 110px;gap:14px;border-bottom:1px dashed %s;padding:13px 0}.name{font-size:25px;font-weight:700}.desc{grid-column:1/2;font-size:19px;color:%s}.price{grid-row:1/3;grid-column:2;text-align:right;font-size:24px;font-weight:700;color:%s}" % (theme["accent"], theme["line"], theme["muted"], theme["accent"])
    elif variant == 2:
        left = "".join(f'<div class="menu-item">{b.block("item_name", n, "name")}{b.block("price", p, "price")}</div>' for n, _, p in items[:5])
        right = "".join(f'<div class="menu-item">{b.block("item_name", n, "name")}{b.block("price", p, "price")}</div>' for n, _, p in items[5:])
        body = f"""
          <div class="double-menu-head">{b.block('document_title', doc['title'], 'menu-title')}{b.block('metadata', 'DOUBLE MENU', 'stamp')}</div>
          <div class="double-menu"><section>{left}</section><section>{right}</section></div>
          {b.block('footer', 'menu · double variant %d' % variant, 'footer')}
        """
        extra = ".double-menu-head{display:flex;justify-content:space-between;align-items:start;border-bottom:3px solid %s;padding-bottom:12px}.menu-title{font-size:46px;font-weight:900;line-height:1.3}.double-menu{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:24px}.menu-item{display:grid;grid-template-columns:1fr 100px;gap:12px;border-bottom:1px dashed %s;padding:14px 0}.name{font-size:24px;font-weight:800}.price{text-align:right;font-size:24px;font-weight:900;color:%s}" % (theme["accent"], theme["line"], theme["accent"])
    elif variant == 3:
        rows = [[n, d, p] for n, d, p in items[:7]]
        body = f"""
          <div class="menu-head">{b.block('document_title', doc['title'], 'title')}{b.block('metadata', 'PRICE LIST', 'stamp')}</div>
          <div class="menu-grid"><section>{simple_table(b, ['Нэр','Тайлбар','Үнэ'], rows)}</section><aside class="panel">{b.block('section_title', 'Тусгай', 'section-title')}{b.block('paragraph', record_text(records, rng, 80, 160), 'text')}</aside></div>
          {b.block('footer', 'menu · variant %d' % variant, 'footer')}
        """
        extra = ".menu-head{display:flex;justify-content:space-between;align-items:start;margin-bottom:24px}.menu-grid{display:grid;grid-template-columns:1fr 260px;gap:18px}"
    elif variant == 4:
        cards = "".join(f'<section class="photo-menu-card">{b.block("image", "", "menu-photo")}{b.block("item_name", n, "name")}{b.block("item_desc", d, "desc")}{b.block("price", p, "price")}</section>' for n, d, p in items[:6])
        body = f"""
          {b.block('document_title', doc['title'], 'menu-title')}
          <div class="photo-menu-grid">{cards}</div>
          {b.block('footer', 'menu · photo variant %d' % variant, 'footer')}
        """
        extra = ".menu-title{font-size:44px;font-weight:900;text-align:center;border-bottom:3px solid %s;padding-bottom:12px}.photo-menu-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:20px}.photo-menu-card{border:1px solid %s;background:white;padding:12px}.menu-photo{min-height:130px;background:%s;border:1px dashed %s}.name{font-size:22px;font-weight:900;margin-top:8px}.desc{font-size:16px;line-height:1.28;color:%s}.price{text-align:right;font-size:23px;font-weight:900;color:%s}" % (theme["accent"], theme["line"], theme["soft"], theme["line"], theme["muted"], theme["accent"])
    elif variant == 5:
        sets = "".join(f'<div class="combo-row">{b.block("item_name", n, "name")}{b.block("item_desc", d, "desc")}{b.block("price", p, "combo-price")}</div>' for n, d, p in items[:5])
        body = f"""
          <div class="combo-menu">{b.block('metadata', 'SET MENU', 'stamp')}{b.block('document_title', doc['title'], 'menu-title')}{sets}</div>
          {b.block('footer', 'menu · combo variant %d' % variant, 'footer')}
        """
        extra = ".combo-menu{border:4px solid %s;padding:24px;background:white}.menu-title{font-size:48px;font-weight:900;line-height:1.3;margin:20px 0}.combo-row{display:grid;grid-template-columns:1fr 120px;gap:14px;border-top:1px solid %s;padding:16px 0}.name{font-size:24px;font-weight:900}.desc{grid-column:1/2;font-size:17px;color:%s}.combo-price{grid-row:1/3;grid-column:2;text-align:right;font-size:28px;font-weight:900;color:%s}" % (theme["accent"], theme["line"], theme["muted"], theme["accent"])
    else:
        receipt_items = "".join(f'<div class="receipt-menu-row">{b.block("item_name", n, "name")}{b.block("price", p, "price")}</div>' for n, _, p in items[:8])
        body = f"""
          <div class="receipt-menu">{b.block('document_title', doc['title'], 'store-name')}{b.block('metadata', 'SERVICE PRICE LIST', 'store-meta')}{receipt_items}</div>
          {b.block('footer', 'menu · receipt style variant %d' % variant, 'footer')}
        """
        extra = ".receipt-menu{border:1px solid %s;background:white;width:720px;margin:0 auto;padding:22px}.store-name{text-align:center;font-size:36px;font-weight:900;line-height:1.3}.store-meta{text-align:center;font-size:15px;letter-spacing:2px;border-bottom:2px dashed %s;padding-bottom:10px}.receipt-menu-row{display:grid;grid-template-columns:1fr 110px;gap:10px;border-bottom:1px dashed %s;padding:10px 0}.name{font-size:21px;font-weight:700}.price{text-align:right;font-size:21px;font-weight:900}" % (theme["line"], theme["line"], theme["line"])
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"], 60, 56) + extra, page_w, page_h, doc["html_lang"])


def letter_official(b: Builder, records: List[Dict[str, str]], rng: random.Random, theme: Dict[str, str], variant: int, doc: Dict[str, str]) -> str:
    page_w, page_h, fs = 1120, 1580, 21
    paras = [record_text(records, rng, 78, 160) for _ in range(4)]
    subject_text = record_title(records, rng, 12, 44)
    if variant == 1:
        body = f"""
          <div class="letterpaper">
            <div class="letter-top">{b.block('metadata', 'OFFICIAL CORRESPONDENCE', 'letter-mark')}{b.block('metadata', 'Ref. L-%03d' % variant, 'letter-no')}</div>
            {b.block('document_title', doc['title'], 'letter-title')}
            <div class="address-row">
              {kv_box(b, 'To', 'Туршилтын өгөгдлийн баг', 'letter-kv')}
              {kv_box(b, 'From', 'Төслийн зохицуулах нэгж', 'letter-kv')}
            </div>
            {b.block('subject', 'Subject: ' + subject_text, 'letter-subject')}
            <div class="letter-body">{''.join(b.block('paragraph', p, 'letter-para') for p in paras)}</div>
            <div class="closing">
              {b.block('signature', 'Respectfully, ____________________', 'closing-line')}
              {b.block('date', f'2026-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}', 'closing-line')}
            </div>
          </div>
          {b.block('footer', 'official letter · refined variant %d' % variant, 'footer')}
        """
    elif variant == 2:
        annex_rows = [[record_title(records, rng, 8, 22), record_text(records, rng, 24, 52)] for _ in range(3)]
        body = f"""
          <div class="memo-sheet">
            <aside class="memo-rail">
              {b.block('metadata', 'MEMORANDUM', 'memo-tag')}
              {b.block('metadata', 'L-%03d' % variant, 'memo-no')}
            </aside>
            <main class="memo-main">
              {b.block('document_title', doc['title'], 'letter-title')}
              <div class="meta-stack">
                {kv_box(b, 'Recipient', 'Туршилтын баг', 'letter-kv')}
                {kv_box(b, 'Topic', subject_text, 'letter-kv')}
              </div>
              {''.join(b.block('paragraph', p, 'letter-para') for p in paras[:3])}
              <section class="annex-table">{simple_table(b, ['Attachment','Note'], annex_rows)}</section>
            </main>
          </div>
          {b.block('footer', 'official letter · refined variant %d' % variant, 'footer')}
        """
    elif variant == 3:
        body = f"""
          <div class="letterpaper notice-letter">
            <div class="letter-top">{b.block('metadata', '函告', 'letter-mark')}{b.block('metadata', 'Ref. H-%03d' % variant, 'letter-no')}</div>
            {b.block('document_title', doc['title'], 'letter-title')}
            {b.block('subject', 'Subject: ' + subject_text, 'letter-subject')}
            <div class="letter-body">{''.join(b.block('paragraph', p, 'letter-para') for p in paras[:3])}</div>
            <div class="closing">{b.block('signature', '中央民族大学合作项目组', 'closing-line')}{b.block('date', f'2026-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}', 'closing-line')}</div>
          </div>
          {b.block('footer', 'official letter · notice letter variant %d' % variant, 'footer')}
        """
    elif variant == 4:
        body = f"""
          <div class="request-doc">
            {b.block('metadata', '请示', 'doc-type')}
            {b.block('document_title', doc['title'], 'letter-title')}
            <div class="request-meta">{kv_box(b, '呈报单位', '中央民族大学合作项目组', 'letter-kv')}{kv_box(b, '事项', subject_text, 'letter-kv')}</div>
            {''.join(b.block('paragraph', p, 'letter-para') for p in paras)}
          </div>
          {b.block('footer', 'official letter · request variant %d' % variant, 'footer')}
        """
    elif variant == 5:
        body = f"""
          <div class="approval-doc">
            <header>{b.block('metadata', '批复', 'doc-type')}{b.block('metadata', 'L-%03d' % variant, 'letter-no')}</header>
            {b.block('document_title', doc['title'], 'letter-title')}
            {b.block('paragraph', record_text(records, rng, 110, 190), 'letter-para')}
            <div class="approval-items">{''.join(b.block('list_item', record_text(records, rng, 28, 60), 'approval-item') for _ in range(3))}</div>
            <div class="approval-stamp-row">{b.block('stamp', '同意', 'stamp')}{b.block('date', f'2026-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}', 'closing-line')}</div>
          </div>
          {b.block('footer', 'official letter · approval variant %d' % variant, 'footer')}
        """
    else:
        annex_rows = [[f"附件 {i}", record_text(records, rng, 22, 50)] for i in range(1, 5)]
        body = f"""
          <div class="attachment-letter">
            <main>{b.block('document_title', doc['title'], 'letter-title')}{''.join(b.block('paragraph', p, 'letter-para') for p in paras[:2])}</main>
            <aside>{b.block('section_title', '附件清单', 'section-title')}{simple_table(b, ['编号','说明'], annex_rows)}</aside>
          </div>
          {b.block('footer', 'official letter · attachment variant %d' % variant, 'footer')}
        """

    extra = """
    .letterpaper{border-top:6px solid %s;padding-top:10px}
    .letter-top{display:flex;justify-content:space-between;font-size:15px;letter-spacing:1px}
    .letter-mark{font-size:15px;font-weight:700}
    .letter-title{font-size:42px;font-weight:900;line-height:1.08;margin-top:12px;border-bottom:2px solid %s;padding-bottom:12px}
    .address-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}
    .letter-kv{border:1px solid %s;padding:8px 10px;min-height:62px}
    .letter-subject{font-size:24px;font-weight:700;margin-top:18px}
    .letter-body{margin-top:18px}
    .letter-para{font-size:22px;line-height:1.55;text-indent:2em;margin-bottom:16px}
    .closing{text-align:right;margin-top:40px}
    .closing-line{font-size:22px;line-height:1.5}
    .memo-sheet{display:grid;grid-template-columns:170px 1fr;gap:24px}
    .memo-rail{border-right:5px solid %s;padding-right:14px;display:flex;flex-direction:column;gap:10px}
    .memo-tag{font-size:26px;font-weight:900;letter-spacing:2px;writing-mode:vertical-rl}
    .memo-no{font-size:18px}
    .meta-stack{display:grid;gap:10px;margin:16px 0}
    .annex-table{margin-top:18px}
    .notice-letter{border-top-style:double}
    .request-doc{border-left:9px solid %s;padding-left:22px}
    .doc-type{font-size:24px;font-weight:900;color:%s;letter-spacing:2px}
    .request-meta{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0}
    .approval-doc{border:2px solid %s;padding:22px;background:white}
    .approval-doc header{display:flex;justify-content:space-between;border-bottom:2px solid %s;padding-bottom:10px}
    .approval-stamp-row{display:flex;justify-content:flex-end;align-items:center;gap:24px;margin-top:34px}
    .approval-items{display:grid;gap:8px;margin-top:14px}
    .approval-item{font-size:20px;line-height:1.35;border-bottom:1px dashed %s;padding:8px 0}
    .attachment-letter{display:grid;grid-template-columns:1fr 340px;gap:22px}
    .attachment-letter aside{border:1.5px solid %s;background:white;padding:14px}
    """ % (
        theme["accent"],
        theme["line"],
        theme["line"],
        theme["accent"],
        theme["accent"],
        theme["accent"],
        theme["line"],
        theme["line"],
        theme["line"],
        theme["line"],
    )
    return wrap(doc, body, base_css(page_w, page_h, theme, fs, doc["font_family"]) + extra, page_w, page_h, doc["html_lang"])


GENERATORS: Dict[str, Callable[[Builder, List[Dict[str, str]], random.Random, Dict[str, str], int, Dict[str, str]], str]] = {
    "table_document": table_document,
    "newspaper": newspaper,
    "invoice_receipt": invoice_receipt,
    "notice_announcement": notice_announcement,
    "book_textbook": book_textbook,
    "poster_flyer": poster_flyer,
    "certificate": certificate,
    "form_registration": form_registration,
    "schedule_timetable": schedule_timetable,
    "report_brief": report_brief,
    "menu_price_list": menu_price_list,
    "letter_official": letter_official,
}


TITLE_BY_CATEGORY = {
    "table_document": "Мэдээллийн хүснэгт",
    "newspaper": "Өдрийн мэдээ",
    "invoice_receipt": "Тооцооны баримт",
    "notice_announcement": "Албан мэдэгдэл",
    "book_textbook": "Сургалтын хуудас",
    "poster_flyer": "Мэдээллийн хуудас",
    "certificate": "Батламж",
    "form_registration": "Бүртгэлийн маягт",
    "schedule_timetable": "Ажлын хуваарь",
    "report_brief": "Товч тайлан",
    "menu_price_list": "Үнийн жагсаалт",
    "letter_official": "Албан бичиг",
}


TITLE_BY_CATEGORY_TIBETAN = {
    "table_document": "རེའུ་མིག་ཡིག་ཆ།",
    "newspaper": "གསར་འགྱུར་ཤོག་ངོས།",
    "invoice_receipt": "འཛིན་ཤོག་དང་ཐོ་འགོད།",
    "notice_announcement": "བརྡ་ཐོ་དང་བསྒྲགས་གཏམ།",
    "book_textbook": "དཔེ་དེབ་དང་སློབ་དེབ།",
    "poster_flyer": "འགྲེམས་བསྒྲགས་ཤོག་ལྷེ།",
    "certificate": "ལག་ཁྱེར་དང་དཔང་ཡིག",
    "form_registration": "ཐོ་འགོད་རེའུ་མིག",
    "schedule_timetable": "དུས་ཚོད་རེའུ་མིག",
    "report_brief": "སྙན་ཐོ་དང་མདོར་བསྡུས།",
    "menu_price_list": "ཟས་ཐོ་དང་གོང་ཐང་རེའུ་མིག",
    "letter_official": "གཞུང་ཡིག་དང་ཡིག་འཕྲིན།",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--language-profile")
    parser.add_argument("--per-category", type=int, default=6)
    parser.add_argument("--min-records", type=int, default=40)
    parser.add_argument("--seed", type=int, default=2026063012)
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
    manifest = []
    selected_categories = set(args.categories) if args.categories else None
    filtered_categories = [
        (category, category_cn)
        for category, category_cn in CATEGORIES
        if selected_categories is None or category in selected_categories
    ]
    if not filtered_categories:
        raise RuntimeError("no categories selected")

    for cat_idx, (category, category_cn) in enumerate(filtered_categories, 1):
        generator = GENERATORS[category]
        for variant in range(1, args.per_category + 1):
            document_id = f"{cat_idx:02d}_{category}_{variant:02d}"
            b = Builder(document_id)
            theme = THEMES[(cat_idx + variant - 2) % len(THEMES)]
            title_map = TITLE_BY_CATEGORY_TIBETAN if language_profile.get("language_code") == "bo" else TITLE_BY_CATEGORY
            title = title_map[category]
            if variant in [2, 5]:
                title = f"{title} · {record_title(records, rng, 8, 24)}"
            doc = {
                "document_id": document_id,
                "title": f"{language_profile.get('title_prefix', '')}{title}",
                "html_lang": language_profile["html_lang"],
                "font_family": language_profile["font_family"],
            }
            html_text = generator(b, records, rng, theme, variant, doc)
            html_name = f"{document_id}.html"
            (html_dir / html_name).write_text(html_text, encoding="utf-8")
            manifest.append(
                {
                    "document_id": document_id,
                    "title": title,
                    "category": category,
                    "category_cn": category_cn,
                    "variant": variant,
                    "layout_name": f"{category}_variant_{variant}",
                    "template_type": category,
                    "generator": f"layout_12classes_refined_{language_profile.get('language_code', 'mn')}",
                    "doc_no": f"{cat_idx:02d}-{variant:02d}",
                    "date": now_local()[:10],
                    "page_width": 1500 if category == "certificate" and variant % 2 else (980 if category in ["invoice_receipt", "menu_price_list"] else (1080 if category == "poster_flyer" else (1120 if category in ["book_textbook", "letter_official"] else 1240))),
                    "page_height": 1060 if category == "certificate" and variant % 2 else (1500 if category in ["poster_flyer", "certificate"] else (1380 if category in ["invoice_receipt", "menu_price_list"] else (1600 if category == "book_textbook" else (1580 if category == "letter_official" else (1650 if category in ["schedule_timetable"] else 1754))))),
                    "rows": None,
                    "columns": None,
                    "created_at": now_local(),
                    "source_records": [],
                }
            )
    (meta_dir / "html_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (meta_dir / "category_plan.json").write_text(
        json.dumps([{"category": c, "category_cn": cn, "samples": args.per_category} for c, cn in filtered_categories], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"generated {len(manifest)} html files across {len(filtered_categories)} categories in {html_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
