#!/usr/bin/env python3
"""Generate Zhuang newspaper pages from structured JSON layout trees."""

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
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TITLE = "Vahcuengh Yienghneix"
KICKERS = ["Ngoenzneix", "Vwnzva · Sawcuengh · Gijyez", "Gijmingz Saedsaed", "Cawxgya Cangh"]
SECTION_TITLES = ["Doengh", "Gvangj Gau", "Yienghneix", "Vwnzva", "Sawcuengh", "Dakbieq"]
CONTACT_LABELS = ["Lienzyau", "Dihdeiz", "Seizgan", "Deihce"]


def now_local() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def cleanse_text(text: str) -> str:
    text = CYRILLIC_RE.sub("", text)
    text = TIBETAN_DECORATIVE_MARK_RE.sub(" ", text)
    text = TIBETAN_SHAD_RE.sub(" ། ", text)
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
    profile.setdefault("font_family", '"Local Arial", "Local Arial Unicode", Arial, Helvetica, sans-serif')
    profile.setdefault("title_prefix", "")
    return profile


def read_text_records(path: Path, language_profile: dict[str, Any], min_records: int) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
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
    cut = text[:max_len]
    for sep in [" ", "་"]:
        idx = cut.rfind(sep)
        if idx >= min_len:
            end = idx + (1 if sep == "་" else 0)
            return cut[:end].strip()
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
    long_records = [rec for rec in records if len(rec["text"]) >= min_len]
    pool = long_records or records
    return select_span(rng.choice(pool)["text"], rng, min_len, max_len)


def record_title(records: list[dict[str, str]], rng: random.Random, min_len: int = 8, max_len: int = 34) -> str:
    rec = rng.choice(records)
    title = cleanse_text(rec["title"])
    if title and re.search(r"[A-Za-z]", title) and min_len <= len(title) <= max_len:
        return title
    return select_span(rec["text"], rng, min_len, max_len)


def fallback_text(label: str) -> str:
    return {
        "document_title": "Vahcuengh",
        "document_subtitle": "Bouxcuengh Vahcuengh",
        "section_title": "Gij Doengh",
        "metadata": "2026",
        "field_label": "Gizgou",
        "field_value": "Neiyungz",
        "table_header": "Mingz",
        "table_cell_text": "Neiyungz",
        "table_cell_number": "01",
        "note": "Fuenghsaq",
        "seal": "Seal",
        "page_number": "1",
        "footer": "Vahcuengh",
        "paragraph": "Vahcuengh neiyungz",
        "quote": "Vahcuengh neiyungz",
        "question": "Gijman",
        "option": "A",
        "answer_area": " ",
    }.get(label, "Vahcuengh")


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


def base_css(page: dict[str, Any], style: dict[str, Any], font_family: str) -> str:
    width = int(page["width"])
    height = int(page["height"])
    font_scale = style.get("font_scale", "regular")
    base_size = {
        "small_dense": 17,
        "compact": 18,
        "regular": 19,
        "medium_high": 19,
        "feature": 20,
        "modern": 19,
    }.get(font_scale, 19)
    return tibetan_font_faces() + f"""
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: #d9dde2; }}
    body {{ font-family: {font_family}; color: {style['ink']}; }}
    .page {{
      width: {width}px;
      min-height: {height}px;
      margin: 0 auto;
      padding: 48px 54px 42px;
      background: {style['paper']};
      position: relative;
      overflow: hidden;
    }}
    [data-block-id] {{ overflow: visible; }}
    .masthead {{ border-top: 5px solid {style['line']}; border-bottom: 2px solid {style['line']}; padding: 12px 0 14px; margin-bottom: 18px; }}
    .masthead-split, .masthead-minimal {{ display: grid; grid-template-columns: 1fr 320px; gap: 20px; align-items: end; border-bottom: 4px double {style['line']}; padding-bottom: 13px; margin-bottom: 18px; }}
    .masthead-compact {{ display: grid; grid-template-columns: 210px 1fr 260px; gap: 14px; align-items: end; border-bottom: 3px solid {style['line']}; padding-bottom: 10px; margin-bottom: 15px; }}
    .masthead-banner {{ border-left: 14px solid {style['accent']}; border-bottom: 2px solid {style['line']}; padding: 12px 0 13px 18px; margin-bottom: 18px; }}
    .special-masthead {{ display: grid; grid-template-columns: 170px 1fr 270px; gap: 18px; align-items: end; border-top: 6px solid {style['accent']}; border-bottom: 2px solid {style['line']}; padding: 12px 0; margin-bottom: 20px; }}
    .newspaper-name {{ font-size: {base_size + 43}px; font-weight: 900; line-height: 1.34; text-align: center; }}
    .newspaper-name.left {{ text-align: left; }}
    .kicker, .meta {{ font-size: {base_size - 2}px; line-height: 1.28; color: {style['muted']}; }}
    .issue-bar {{ display: flex; justify-content: space-between; gap: 12px; border-top: 1px solid {style['line']}; margin-top: 8px; padding-top: 6px; }}
    .grid {{ display: grid; gap: 18px; align-items: start; }}
    .story {{ break-inside: avoid; border-bottom: 1px solid {style['line']}; padding-bottom: 10px; margin-bottom: 12px; }}
    .lead-story .headline {{ font-size: {base_size + 14}px; }}
    .headline {{ font-size: {base_size + 5}px; font-weight: 900; line-height: 1.42; margin-bottom: 7px; }}
    .headline.xl {{ font-size: {base_size + 16}px; line-height: 1.38; }}
    .headline.xxl {{ font-size: {base_size + 21}px; line-height: 1.36; }}
    .news-para {{ font-size: {base_size}px; line-height: 1.36; margin: 0 0 7px; }}
    .small-para {{ font-size: {base_size - 2}px; line-height: 1.34; margin: 0 0 7px; }}
    .columns-2 {{ columns: 2; column-gap: 18px; }}
    .columns-3 {{ columns: 3; column-gap: 17px; }}
    .columns-4 {{ columns: 4; column-gap: 15px; }}
    .sidebar {{ border-left: 3px solid {style['accent']}; padding-left: 13px; }}
    .side-title {{ font-size: {base_size + 3}px; font-weight: 900; color: {style['accent']}; margin-bottom: 8px; }}
    .brief-line {{ font-size: {base_size - 2}px; line-height: 1.29; border-bottom: 1px dotted {style['line']}; padding: 6px 0; }}
    .image-box {{ min-height: 250px; background: repeating-linear-gradient(135deg, #e4e0d6, #e4e0d6 12px, #f4f0e7 12px, #f4f0e7 24px); border: 1.5px solid {style['line']}; margin: 10px 0 7px; }}
    .caption {{ font-size: {base_size - 4}px; color: {style['muted']}; line-height: 1.28; margin-bottom: 10px; }}
    .brief-strip, .related-strip, .metric-strip {{ display: grid; gap: 10px; margin-top: 14px; border-top: 2px solid {style['line']}; padding-top: 10px; }}
    .brief-strip {{ grid-template-columns: repeat(5, 1fr); }}
    .related-strip {{ grid-template-columns: repeat(4, 1fr); }}
    .metric-strip {{ grid-template-columns: repeat(4, 1fr); }}
    .strip-item {{ font-size: {base_size - 3}px; line-height: 1.25; background: rgba(0,0,0,.035); padding: 8px; min-height: 74px; }}
    .community-box, .fact-box, .calendar-box, .contact-box, .small-ad-box, .digest-card {{ border: 1.4px solid {style['line']}; background: rgba(255,255,255,.58); padding: 12px; margin-bottom: 12px; break-inside: avoid; }}
    .community-box .headline, .fact-box .headline, .digest-card .headline {{ font-size: {base_size + 2}px; }}
    .timeline-item {{ display: grid; grid-template-columns: 58px 1fr; gap: 9px; border-bottom: 1px dotted {style['line']}; padding: 7px 0; }}
    .timeline-no {{ font-size: {base_size + 4}px; font-weight: 900; color: {style['accent']}; }}
    .micro-ad {{ border: 2px solid {style['accent']}; padding: 10px; margin: 8px 0 12px; font-weight: 700; }}
    .footer {{ position: absolute; left: 54px; right: 54px; bottom: 18px; border-top: 1px solid {style['line']}; padding-top: 6px; font-size: {base_size - 5}px; color: {style['muted']}; text-align: right; }}
    """


def wrap(doc: dict[str, Any], body: str, css: str, page: dict[str, Any]) -> str:
    return f"""<!doctype html>
<html lang="{esc(doc['html_lang'])}">
<head>
<meta charset="utf-8">
<title>{esc(doc['title'])}</title>
<style>{css}</style>
</head>
<body><main class="page newspaper-json-page" data-template-id="{esc(doc['template_id'])}">{body}</main></body>
</html>
"""


def random_meta_items(rng: random.Random, variant: int) -> list[str]:
    return [f"No {180 + variant:03d}", f"2026-07-{variant:02d}", rng.choice(["Saw A", "Yieb 03", "Dakbieq"])]


def render_issue_bar(b: Builder, rng: random.Random, variant: int) -> str:
    return '<div class="issue-bar">' + ''.join(b.block("metadata", item, "meta") for item in random_meta_items(rng, variant)) + '</div>'


def render_masthead(b: Builder, template: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any]) -> str:
    region_type = template["regions"][0]["type"]
    variant = int(template["variant"])
    title_extra = record_title(records, rng, 8, 18) if variant in (2, 5) else ""
    title = cleanse_text(f"{doc['title']} {title_extra}")
    if region_type == "masthead_compact":
        return f"""<header class="masthead-compact">
          {b.block('metadata', rng.choice(KICKERS), 'kicker')}
          {b.block('document_title', title, 'newspaper-name')}
          <div>{render_issue_bar(b, rng, variant)}</div>
        </header>"""
    if region_type == "masthead_split":
        return f"""<header class="masthead-split">
          {b.block('document_title', title, 'newspaper-name left')}
          <div>{b.block('metadata', rng.choice(KICKERS), 'meta')}{render_issue_bar(b, rng, variant)}</div>
        </header>"""
    if region_type == "masthead_banner":
        return f"""<header class="masthead-banner">
          {b.block('document_title', title, 'newspaper-name left')}
          {b.block('metadata', rng.choice(KICKERS), 'meta')}
          {render_issue_bar(b, rng, variant)}
        </header>"""
    if region_type == "special_masthead":
        return f"""<header class="special-masthead">
          {b.block('metadata', 'SPECIAL', 'kicker')}
          {b.block('document_title', title, 'newspaper-name')}
          <div>{b.block('metadata', record_title(records, rng, 8, 22), 'meta')}{render_issue_bar(b, rng, variant)}</div>
        </header>"""
    if region_type == "masthead_minimal":
        return f"""<header class="masthead-minimal">
          {b.block('document_title', title, 'newspaper-name left')}
          <div>{render_issue_bar(b, rng, variant)}</div>
        </header>"""
    return f"""<header class="masthead">
      {b.block('metadata', rng.choice(KICKERS), 'kicker')}
      {b.block('document_title', title, 'newspaper-name')}
      {render_issue_bar(b, rng, variant)}
    </header>"""


def story_block(
    b: Builder,
    records: list[dict[str, str]],
    rng: random.Random,
    cls: str = "story",
    paragraphs: int = 1,
    headline_scale: str = "",
    include_image: bool = False,
    caption: bool = False,
    text_min: int = 58,
    text_max: int = 128,
) -> str:
    head_cls = f"headline {headline_scale}".strip()
    parts = [f'<article class="{cls}">', b.block("section_title", record_title(records, rng, 10, 32), head_cls)]
    if include_image:
        parts.append(b.block("image", "", "image-box"))
        if caption:
            parts.append(b.block("caption", record_text(records, rng, 26, 58), "caption"))
    for _ in range(paragraphs):
        parts.append(b.block("paragraph", record_text(records, rng, text_min, text_max), "news-para"))
    parts.append("</article>")
    return "".join(parts)


def brief_list(b: Builder, records: list[dict[str, str]], rng: random.Random, count: int, title: str | None = None, cls: str = "sidebar") -> str:
    header = b.block("section_title", title or rng.choice(SECTION_TITLES), "side-title") if title else ""
    lines = "".join(b.block("list_item", record_text(records, rng, 24, 64), "brief-line") for _ in range(count))
    return f'<aside class="{cls}">{header}{lines}</aside>'


def strip_items(b: Builder, records: list[dict[str, str]], rng: random.Random, count: int, cls: str) -> str:
    return f'<section class="{cls}">' + "".join(b.block("list_item", record_text(records, rng, 28, 68), "strip-item") for _ in range(count)) + "</section>"


def box_section(b: Builder, records: list[dict[str, str]], rng: random.Random, cls: str, title: str | None, count: int) -> str:
    parts = [f'<section class="{cls}">']
    if title:
        parts.append(b.block("section_title", title, "headline"))
    for _ in range(count):
        parts.append(b.block("list_item", record_text(records, rng, 22, 58), "small-para"))
    parts.append("</section>")
    return "".join(parts)


def render_v01(b: Builder, template: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any]) -> str:
    masthead = render_masthead(b, template, records, rng, doc)
    lead = story_block(b, records, rng, "story lead-story", 4, "xl", True, True, 92, 176)
    center = '<section class="columns-2">' + "".join(story_block(b, records, rng, paragraphs=2, text_min=78, text_max=160) for _ in range(10)) + "</section>"
    side = brief_list(b, records, rng, 22, "Mboq Doengh")
    main = f'<main class="grid" style="grid-template-columns:1.08fr 1.22fr .72fr">{lead}{center}{side}</main>'
    footer = b.block("footer", "newspaper json template v01", "footer")
    return masthead + main + footer


def render_v02(b: Builder, template: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any]) -> str:
    masthead = render_masthead(b, template, records, rng, doc)
    hero = story_block(b, records, rng, "story lead-story", 2, "xxl", True, True, 72, 140)
    side = '<section>' + "".join(story_block(b, records, rng, paragraphs=1, text_min=56, text_max=116) for _ in range(3)) + "</section>"
    top = f'<section class="grid" style="grid-template-columns:1.55fr .8fr;margin-bottom:16px">{hero}{side}</section>'
    body = '<section class="columns-3">' + "".join(story_block(b, records, rng, paragraphs=1, text_min=58, text_max=118) for _ in range(6)) + "</section>"
    strip = strip_items(b, records, rng, 6, "brief-strip")
    return masthead + top + body + strip


def render_v03(b: Builder, template: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any]) -> str:
    masthead = render_masthead(b, template, records, rng, doc)
    stories = []
    for i in range(34):
        stories.append(story_block(b, records, rng, paragraphs=1, text_min=64, text_max=132))
        if i == 5:
            stories.append(f'<section class="micro-ad">{b.block("section_title", "Gvangj Gau", "headline")}{b.block("paragraph", record_text(records, rng, 40, 86), "small-para")}</section>')
    body = '<main class="columns-4">' + "".join(stories) + "</main>"
    strip = strip_items(b, records, rng, 8, "brief-strip")
    return masthead + body + strip


def render_v04(b: Builder, template: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any]) -> str:
    masthead = render_masthead(b, template, records, rng, doc)
    notice = box_section(b, records, rng, "community-box", "Gvangj Gau", 7)
    news = '<section>' + "".join(story_block(b, records, rng, paragraphs=1, text_min=54, text_max=112) for _ in range(5)) + "</section>"
    calendar = box_section(b, records, rng, "calendar-box", "06/2026", 6)
    contact = box_section(b, records, rng, "contact-box", rng.choice(CONTACT_LABELS), 3)
    ad = box_section(b, records, rng, "small-ad-box", "Gau Cek", 3)
    right = f"<aside>{calendar}{contact}{ad}</aside>"
    grid = f'<main class="grid" style="grid-template-columns:1fr 1fr .78fr">{notice}{news}{right}</main>'
    strip = strip_items(b, records, rng, 4, "brief-strip")
    return masthead + grid + strip


def render_v05(b: Builder, template: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any]) -> str:
    masthead = render_masthead(b, template, records, rng, doc)
    main_story = f'<section class="lead-story">{b.block("section_title", record_title(records, rng, 12, 34), "headline xxl")}{b.block("paragraph", record_text(records, rng, 120, 210), "news-para")}' + "".join(b.block("paragraph", record_text(records, rng, 92, 178), "news-para") for _ in range(12)) + "</section>"
    timeline = '<aside class="sidebar">' + b.block("section_title", "Seizgan", "side-title")
    for i in range(1, 13):
        timeline += f'<div class="timeline-item">{b.block("metadata", f"{i:02d}", "timeline-no")}{b.block("list_item", record_text(records, rng, 34, 80), "small-para")}</div>'
    timeline += box_section(b, records, rng, "fact-box", "Gij Yawj", 8) + "</aside>"
    grid = f'<main class="grid" style="grid-template-columns:1.35fr .75fr">{main_story}{timeline}</main>'
    related = strip_items(b, records, rng, 5, "related-strip")
    return masthead + grid + related


def render_v06(b: Builder, template: dict[str, Any], records: list[dict[str, str]], rng: random.Random, doc: dict[str, Any]) -> str:
    masthead = render_masthead(b, template, records, rng, doc)
    primary = story_block(b, records, rng, "story lead-story", 2, "xl", True, True, 70, 142)
    cards = '<section>' + "".join(f'<div class="digest-card">{story_block(b, records, rng, "story", 1, "", text_min=48, text_max=106)}</div>' for _ in range(6)) + "</section>"
    side = brief_list(b, records, rng, 10, "Doengh Vaiq")
    grid = f'<main class="grid" style="grid-template-columns:1.25fr 1fr .72fr">{primary}{cards}{side}</main>'
    metrics = strip_items(b, records, rng, 4, "metric-strip")
    return masthead + grid + metrics


RENDERERS = {
    1: render_v01,
    2: render_v02,
    3: render_v03,
    4: render_v04,
    5: render_v05,
    6: render_v06,
}


def validate_templates(spec: dict[str, Any]) -> None:
    if spec.get("schema_version") != "category_layout_templates.v1":
        raise RuntimeError("unsupported newspaper template schema")
    templates = spec.get("templates")
    if not isinstance(templates, list) or len(templates) != 6:
        raise RuntimeError("newspaper template spec must contain exactly 6 templates")
    variants = [t.get("variant") for t in templates]
    if variants != [1, 2, 3, 4, 5, 6]:
        raise RuntimeError(f"newspaper variants must be [1,2,3,4,5,6], got {variants}")


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
    load_language_profile,
    read_text_records,
    record_text,
    record_title,
    select_span,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-jsonl", required=True)
    parser.add_argument("--templates-json", required=True)
    parser.add_argument("--output-root")
    parser.add_argument("--output-dir")
    parser.add_argument("--language-profile")
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--min-records", type=int, default=40)
    parser.add_argument("--seed", type=int, default=2026070101)
    parser.add_argument("--version-name")
    args = parser.parse_args()
    if not args.output_root and not args.output_dir:
        parser.error("one of --output-root or --output-dir is required")

    language_profile = load_language_profile(Path(args.language_profile) if args.language_profile else None)
    records = read_text_records(Path(args.text_jsonl), language_profile, args.min_records)
    spec = json.loads(Path(args.templates_json).read_text(encoding="utf-8"))
    validate_templates(spec)
    version_name = args.version_name or (Path(args.output_root).name if args.output_root else "v2")

    out_dir = Path(args.output_dir) if args.output_dir and not args.output_root else Path(args.output_root) / f"{args.start_index:02d}_报纸页"
    if args.output_root:
        reset_category_dir(out_dir)
    html_dir = out_dir / "html"
    meta_dir = out_dir / "metadata"
    html_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    manifest = []
    for template in spec["templates"]:
        variant = int(template["variant"])
        document_id = f"01_newspaper_page_json_{variant:02d}"
        b = Builder(document_id)
        page = template["page"]
        style = template["style_tokens"]
        doc = {
            "document_id": document_id,
            "title": DEFAULT_TITLE,
            "html_lang": language_profile["html_lang"],
            "font_family": language_profile["font_family"],
            "template_id": template["template_id"],
        }
        body = RENDERERS[variant](b, template, records, rng, doc)
        css = base_css(page, style, doc["font_family"])
        (html_dir / f"{document_id}.html").write_text(wrap(doc, body, css, page), encoding="utf-8")
        manifest.append(
            {
                "document_id": document_id,
                "title": DEFAULT_TITLE,
                "category": "newspaper_page",
                "category_cn": "报纸页",
                "variant": variant,
                "layout_name": template["template_id"],
                "layout_family": template["layout_family"],
                "template_type": "newspaper_page",
                "template_source": str(Path(args.templates_json).resolve()),
                "generator": "newspaper_json_renderer_za_v1",
                "doc_no": f"ZA-{version_name.upper()}-{args.start_index:02d}-{variant:02d}",
                "date": now_local()[:10],
                "page_width": int(page["width"]),
                "page_height": int(page["height"]),
                "preserve_full_page": bool(template.get("preserve_full_page", variant in {1, 3, 5})),
                "tight_crop": bool(template.get("tight_crop", False)),
                "rows": None,
                "columns": None,
                "created_at": now_local(),
                "source_records": [],
                "content_plan": template.get("content_plan", {}),
                "qa_constraints": template.get("qa_constraints", {}),
            }
        )

    (meta_dir / "html_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (meta_dir / "category_plan.json").write_text(
        json.dumps([{"category": "newspaper_page", "category_cn": "报纸页", "samples": 6}], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (meta_dir / "newspaper_template_spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_root:
        (out_dir / "README.md").write_text(
            f"# {args.start_index:02d} 报纸页\n\n本目录属于壮语 `{version_name}`，由报纸专用 JSON 结构树生成，共 6 张。\n\n- `html/`\n- `images/`\n- `labels/`\n- `metadata/`\n- `reports/`\n",
            encoding="utf-8",
        )
    print(f"generated {len(manifest)} newspaper html files in {html_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
