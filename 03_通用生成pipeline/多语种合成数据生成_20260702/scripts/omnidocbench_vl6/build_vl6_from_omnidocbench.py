#!/usr/bin/env python3
"""Build VL6 from OmniDocBench layouts only.

VL6 is quality-first: it uses only templates with explicit OmniDocBench order
annotations and does not fall back to local templates when a category is sparse.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download
from PIL import Image, ImageDraw, ImageFont


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
ENGINE_SCRIPTS = SCRIPT_DIR.parent
RUNTIME_ROOT = Path("/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies")

OMNI_REPO = "opendatalab/OmniDocBench"
OMNI_JSON = "OmniDocBench.json"

LANGUAGES = [
    ("壮语", "zhuang"),
    ("藏语", "tibetan"),
    ("朝鲜语", "korean"),
    ("白语", "bai"),
    ("维吾尔语", "uyghur"),
    ("哈萨克语", "kazakh"),
    ("蒙古语", "mongolian"),
]

CATEGORY_DIRS = {
    "newspaper_page": ("01_报纸页", "报纸页"),
    "exam_paper": ("03_考试卷", "考试卷"),
    "book_page": ("05_书籍页", "书籍页"),
    "textbook_page": ("06_教科书页", "教科书页"),
    "magazine_journal": ("07_杂志期刊页", "杂志期刊页"),
    "academic_paper": ("08_学术文献页", "学术文献页"),
    "historical_classic": ("09_历史文档_古籍", "历史文档_古籍"),
}

ORIGINAL_CATEGORY_DIRS = [
    "01_报纸页",
    "02_证书证明",
    "03_考试卷",
    "04_标牌海报场景",
    "05_书籍页",
    "06_教科书页",
    "07_杂志期刊页",
    "08_学术文献页",
    "09_历史文档_古籍",
    "10_公告通知",
    "11_复杂表单登记页",
    "12_手写笔记信件",
]

DATA_SOURCE_TO_CATEGORY = {
    "newspaper": "newspaper_page",
    "exam_paper": "exam_paper",
    "book": "book_page",
    "colorful_textbook": "textbook_page",
    "magazine": "magazine_journal",
    "academic_literature": "academic_paper",
    "research_report": "academic_paper",
    "historical_document": "historical_classic",
}

TEXT_TYPES = {
    "title",
    "text_block",
    "list_group",
    "reference",
    "figure_caption",
    "table_caption",
    "page_number",
}
STRUCTURE_TYPES = {"figure", "table"}
FILTER_PREFIXES = ("equation",)
FILTER_TYPES = {
    "abandon",
    "header",
    "footer",
    "page_footnote",
    "table_footnote",
    "figure_footnote",
    "text_mask",
    "chart_mask",
    "table_mask",
    "unknown_mask",
    "organic_chemical_formula_mask",
    "need_mask",
    "algorithm_mask",
    "code_txt",
    "code_txt_caption",
}

LABEL_MAP = {
    "title": "document_title",
    "text_block": "paragraph",
    "list_group": "list_item",
    "reference": "reference",
    "figure_caption": "caption",
    "table_caption": "caption",
    "page_number": "page_number",
    "figure": "image",
    "table": "table",
}

SHORT_LABELS = {"document_title", "page_number", "caption", "reference"}
PAGE_BG = "#fffdf8"
MIN_TEXT_BLOCKS_PER_PAGE = 8
MIN_TEXT_BOX_WIDTH = 24
MIN_TEXT_BOX_HEIGHT = 10


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def runtime_node() -> str:
    candidate = RUNTIME_ROOT / "node" / "bin" / "node"
    return str(candidate) if candidate.exists() else "node"


def node_env() -> dict[str, str]:
    env = os.environ.copy()
    candidate = RUNTIME_ROOT / "node" / "node_modules"
    if candidate.exists():
        env["NODE_PATH"] = str(candidate)
    return env


def proxy_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("http_proxy", "http://agent.baidu.com:8891")
    env.setdefault("https_proxy", "http://agent.baidu.com:8891")
    env.setdefault("no_proxy", "baidu.com,baidubce.com,bj.bcebos.com,bfsu.edu.cn,tsinghua.edu.cn")
    return env


def stable_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(r"\\[a-zA-Z]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def poly_to_bbox(poly: list[Any]) -> tuple[float, float, float, float] | None:
    if not isinstance(poly, list) or len(poly) < 8:
        return None
    xs = [float(poly[i]) for i in range(0, len(poly), 2)]
    ys = [float(poly[i]) for i in range(1, len(poly), 2)]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None
    return x1, y1, x2, y2


def normalize_box(box: tuple[float, float, float, float], src_w: float, src_h: float, dst_w: int, dst_h: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    sx, sy = dst_w / src_w, dst_h / src_h
    return x1 * sx, y1 * sy, x2 * sx, y2 * sy


def box_area(box: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2, (y1 + y2) / 2


def visual_column(box: tuple[float, float, float, float], page_w: float) -> int:
    cx, _ = center(box)
    return max(0, min(5, int(cx / max(page_w, 1) * 6)))


def role_rank(category_type: str, label: str) -> int:
    if category_type == "title":
        return 0
    if label in {"caption", "note", "reference"}:
        return 35
    if category_type == "page_number":
        return 90
    return 20


def sort_blocks(blocks: list[dict[str, Any]], page_w: int, vertical: bool) -> list[dict[str, Any]]:
    if vertical:
        # Keep Omni order for traditional Mongolian vertical pages. The source
        # order is the only reliable signal after changing writing mode.
        return sorted(blocks, key=lambda b: (role_rank(b["category_type"], b["block_label"]), b["omni_order"]))

    def key(block: dict[str, Any]) -> tuple[Any, ...]:
        rank = role_rank(block["category_type"], block["block_label"])
        x1, y1, x2, y2 = block["box"]
        if rank < 10 or rank >= 80:
            return (rank, y1, x1, block["omni_order"])
        return (rank, visual_column(block["box"], page_w), y1, x1, block["omni_order"])

    return sorted(blocks, key=key)


def role_from_label(label: str) -> str:
    return {
        "document_title": "title",
        "paragraph": "paragraph",
        "list_item": "list_item",
        "reference": "reference",
        "caption": "caption",
        "page_number": "page_number",
        "metadata": "metadata",
        "footer": "footer",
        "note": "note",
    }.get(label, label)


def language_profiles() -> dict[str, dict[str, Any]]:
    profiles = {}
    for lang, key in LANGUAGES:
        matches = sorted((PROJECT_ROOT / "02_语种工程资源" / lang).glob("03_合成数据生成_20260702/configs/*language_profile.json"))
        if not matches:
            raise FileNotFoundError(f"missing language profile for {lang}")
        profiles[lang] = read_json(matches[0])
        profiles[lang]["_profile_path"] = str(matches[0])
        profiles[lang]["_key"] = key
    return profiles


def choose_records() -> dict[str, Path]:
    chosen = {}
    for lang, _key in LANGUAGES:
        root = PROJECT_ROOT / "02_语种工程资源" / lang
        candidates = [p for p in root.glob("01_文本数据获取_*/data/**/records.jsonl") if p.is_file()]
        if not candidates:
            raise FileNotFoundError(f"missing records.jsonl for {lang}")

        def score(path: Path) -> tuple[int, int, str]:
            text = str(path)
            priority = 1
            if "records_generation" in text and "final" in text:
                priority = 7
            elif "zhuang_expanded" in text:
                priority = 7
            elif "vl3_long_text_sources" in text:
                priority = 6
            elif "people_daily" in text:
                priority = 6
            elif "cleaned" in text or "clean" in text:
                priority = 5
            elif "local_verified" in text:
                priority = 4
            line_count = sum(1 for _ in path.open(encoding="utf-8"))
            return priority, line_count, text

        chosen[lang] = sorted(candidates, key=score, reverse=True)[0]
    return chosen


class TextSampler:
    def __init__(self, path: Path) -> None:
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = clean_text(str(obj.get("text") or obj.get("block_content") or obj.get("title") or ""))
            if len(text) >= 2:
                rows.append(text)
        if not rows:
            raise RuntimeError(f"no usable text in {path}")
        self.rows = rows
        self.index = 0

    def take(self, max_chars: int, short: bool = False) -> str:
        if short:
            for _ in range(len(self.rows)):
                text = self.rows[self.index % len(self.rows)]
                self.index += 1
                if 2 <= len(text) <= max_chars * 2:
                    return text[:max_chars]
        text = self.rows[self.index % len(self.rows)]
        self.index += 1
        if len(text) <= max_chars:
            return text
        cut = text[:max_chars]
        for sep in ["。", ".", "?", "!", "།", "؟", "،", ",", " "]:
            pos = cut.rfind(sep)
            if pos > max_chars * 0.45:
                return cut[: pos + 1].strip()
        return cut.strip()


def hf_download(filename: str, cache_dir: Path, use_proxy: bool = True) -> Path:
    env = proxy_env() if use_proxy else os.environ.copy()
    cache_dir.mkdir(parents=True, exist_ok=True)
    old_env = os.environ.copy()
    try:
        os.environ.update(env)
        return Path(hf_hub_download(repo_id=OMNI_REPO, repo_type="dataset", filename=filename, local_dir=str(cache_dir)))
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def load_omni(cache_dir: Path, use_proxy: bool) -> list[dict[str, Any]]:
    path = cache_dir / OMNI_JSON
    if not path.exists():
        path = hf_download(OMNI_JSON, cache_dir, use_proxy)
    return read_json(path)


def classify_block(block: dict[str, Any]) -> str:
    typ = str(block.get("category_type") or "")
    if block.get("ignore") is True:
        return "ignored"
    if typ in FILTER_TYPES or typ.startswith(FILTER_PREFIXES):
        return "filtered"
    if typ in TEXT_TYPES:
        text = clean_text(str(block.get("text") or ""))
        if not text and typ not in {"page_number", "header", "footer"}:
            return "empty"
        return "text"
    if typ in STRUCTURE_TYPES:
        return "structure"
    return "unknown"


def audit_page(item: dict[str, Any], idx: int) -> dict[str, Any] | None:
    page_info = item.get("page_info") or {}
    attrs = page_info.get("page_attribute") or {}
    data_source = str(attrs.get("data_source") or "")
    category = DATA_SOURCE_TO_CATEGORY.get(data_source)
    if not category:
        return None
    width = int(page_info.get("width") or 0)
    height = int(page_info.get("height") or 0)
    image_path = str(page_info.get("image_path") or "")
    if width < 300 or height < 300 or not image_path:
        return None

    text_blocks = []
    structure_blocks = []
    counts = Counter()
    invalid = 0
    orders = []
    for block in item.get("layout_dets") or []:
        status = classify_block(block)
        counts[status] += 1
        box = poly_to_bbox(block.get("poly") or [])
        if not box:
            invalid += 1
            continue
        x1, y1, x2, y2 = box
        if x1 < -2 or y1 < -2 or x2 > width + 2 or y2 > height + 2:
            invalid += 1
            continue
        if status == "text":
            if x2 - x1 < MIN_TEXT_BOX_WIDTH or y2 - y1 < MIN_TEXT_BOX_HEIGHT:
                invalid += 1
                continue
            try:
                order = int(block.get("order"))
            except (TypeError, ValueError):
                invalid += 1
                continue
            if order <= 0:
                invalid += 1
                continue
            orders.append(order)
            text_blocks.append(block)
        elif status == "structure":
            structure_blocks.append(block)

    if len(text_blocks) < MIN_TEXT_BLOCKS_PER_PAGE:
        return None
    if invalid:
        return None
    if len(set(orders)) != len(orders):
        return None
    if any(o is None for o in orders):
        return None

    return {
        "omni_index": idx,
        "template_id": f"omni_{idx:05d}_{stable_id(image_path)}",
        "category": category,
        "category_dir": CATEGORY_DIRS[category][0],
        "category_cn": CATEGORY_DIRS[category][1],
        "data_source": data_source,
        "language": attrs.get("language"),
        "layout": attrs.get("layout"),
        "subset": attrs.get("subset"),
        "image_path": image_path,
        "page_width": width,
        "page_height": height,
        "text_blocks": len(text_blocks),
        "structure_blocks": len(structure_blocks),
        "filtered_blocks": counts["filtered"] + counts["ignored"] + counts["empty"] + counts["unknown"],
        "equation_blocks": sum(1 for b in item.get("layout_dets") or [] if str(b.get("category_type") or "").startswith("equation")),
    }


def build_inventory(omni: list[dict[str, Any]], max_templates_per_category: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = []
    for idx, item in enumerate(omni):
        row = audit_page(item, idx)
        if row:
            candidates.append(row)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        grouped[row["category"]].append(row)
    selected = []
    for category in CATEGORY_DIRS:
        rows = sorted(
            grouped.get(category, []),
            key=lambda r: (
                r["equation_blocks"],
                -r["text_blocks"],
                r["filtered_blocks"],
                r["omni_index"],
            ),
        )
        selected.extend(rows[:max_templates_per_category])
    summary = {
        "total_pages": len(omni),
        "qualified_pages": len(candidates),
        "selected_pages": len(selected),
        "qualified_by_category": {CATEGORY_DIRS[k][1]: len(v) for k, v in grouped.items()},
        "selected_by_category": dict(Counter(row["category_cn"] for row in selected)),
    }
    return selected, summary


def block_html(block: dict[str, Any], block_id: str, box: tuple[float, float, float, float], profile: dict[str, Any], content: str, is_text: bool, order: int | None) -> str:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    typ = str(block.get("category_type") or "")
    label = LABEL_MAP.get(typ, typ)
    classes = ["blk", f"lbl-{label}", f"src-{typ}"]
    if not is_text:
        classes.append("structure")
    font_size = max(10, min(42, h * (0.52 if label in SHORT_LABELS else 0.32)))
    if profile.get("css_writing_mode", "horizontal-tb").startswith("vertical"):
        font_size = max(12, min(30, w * 0.38))
    style = (
        f"left:{x1:.1f}px;top:{y1:.1f}px;width:{w:.1f}px;height:{h:.1f}px;"
        f"font-size:{font_size:.1f}px;"
    )
    attrs = [
        f'class="{esc(" ".join(classes))}"',
        f'style="{style}"',
        f'data-block-id="{esc(block_id)}"',
        f'data-label="{esc(label)}"',
        f'data-source-type="{esc(typ)}"',
        f'data-is-text="{str(is_text).lower()}"',
    ]
    if order is not None:
        attrs.append(f'data-reading-order="{order}"')
    if is_text:
        return f"<div {' '.join(attrs)}>{esc(content)}</div>"
    if typ == "table":
        return f"<div {' '.join(attrs)}><div class=\"table-lines\"></div></div>"
    return f"<div {' '.join(attrs)}></div>"


def render_html_doc(
    row: dict[str, Any],
    omni_item: dict[str, Any],
    profile: dict[str, Any],
    sampler: TextSampler,
    document_id: str,
    page_w: int,
    page_h: int,
) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
    vertical = str(profile.get("css_writing_mode", "")).startswith("vertical")
    text_blocks = []
    structure_blocks = []
    source_w, source_h = row["page_width"], row["page_height"]
    stats = Counter()
    for block in omni_item.get("layout_dets") or []:
        status = classify_block(block)
        stats[status] += 1
        if status not in {"text", "structure"}:
            continue
        box = poly_to_bbox(block.get("poly") or [])
        if not box:
            continue
        out_box = normalize_box(box, source_w, source_h, page_w, page_h)
        if status == "text":
            typ = str(block.get("category_type") or "")
            label = LABEL_MAP.get(typ, typ)
            max_chars = max(8, int(box_area(out_box) / (120 if vertical else 210)))
            content = sampler.take(max_chars, short=label in SHORT_LABELS)
            try:
                omni_order = int(block.get("order"))
            except (TypeError, ValueError):
                continue
            text_blocks.append(
                {
                    "source": block,
                    "box": out_box,
                    "block_label": label,
                    "category_type": typ,
                    "omni_order": omni_order,
                    "block_content": content,
                }
            )
        elif status == "structure":
            structure_blocks.append({"source": block, "box": out_box})

    ordered = sort_blocks(text_blocks, page_w, vertical)
    html_blocks = []
    label_blocks = []
    for order, item in enumerate(ordered, 1):
        block_id = f"{document_id}_b{order:04d}"
        src = item["source"]
        x1, y1, x2, y2 = item["box"]
        html_blocks.append(block_html(src, block_id, item["box"], profile, item["block_content"], True, order))
        label_blocks.append(
            {
                "block_id": block_id,
                "coordinates": {
                    "x_min": round(x1, 1),
                    "y_min": round(y1, 1),
                    "x_max": round(x2, 1),
                    "y_max": round(y2, 1),
                },
                "points": None,
                "block_label": item["block_label"],
                "block_content": item["block_content"],
                "is_text": True,
                "reading_order": order,
                "reading_group": "body" if role_rank(item["category_type"], item["block_label"]) == 20 else item["block_label"],
                "reading_role": role_from_label(item["block_label"]),
                "reading_order_confidence": "high",
                "reading_region": "body",
                "reading_flow_id": f"{row['category_dir']}:omni",
                "reading_flow_rank": order,
                "column_index": visual_column(item["box"], page_w),
                "attributes": {
                    "omnidocbench_order": item["omni_order"],
                    "omnidocbench_category_type": item["category_type"],
                    "omnidocbench_anno_id": src.get("anno_id"),
                    "template_source": "omnidocbench",
                },
            }
        )

    struct_start = len(label_blocks) + 1
    for idx, item in enumerate(structure_blocks, struct_start):
        src = item["source"]
        block_id = f"{document_id}_s{idx:04d}"
        typ = str(src.get("category_type") or "")
        label = LABEL_MAP.get(typ, typ)
        x1, y1, x2, y2 = item["box"]
        html_blocks.append(block_html(src, block_id, item["box"], profile, "", False, None))
        label_blocks.append(
            {
                "block_id": block_id,
                "coordinates": {
                    "x_min": round(x1, 1),
                    "y_min": round(y1, 1),
                    "x_max": round(x2, 1),
                    "y_max": round(y2, 1),
                },
                "points": None,
                "block_label": label,
                "block_content": "",
                "is_text": False,
                "reading_group": "non_ocr",
                "reading_role": label,
                "reading_order_confidence": "none",
                "reading_region": "non_ocr",
                "reading_flow_id": f"{row['category_dir']}:non_ocr",
                "reading_flow_rank": 999,
                "attributes": {
                    "omnidocbench_category_type": typ,
                    "omnidocbench_anno_id": src.get("anno_id"),
                    "template_source": "omnidocbench",
                },
            }
        )

    direction = profile.get("css_direction", "ltr")
    writing_mode = profile.get("css_writing_mode", "horizontal-tb")
    text_align = profile.get("css_text_align", "right" if direction == "rtl" else "left")
    font_family = profile.get("font_family", "Arial, sans-serif")
    html_text = f"""<!doctype html>
<html lang="{esc(profile.get('html_lang', ''))}" dir="{esc(direction)}">
<head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;background:#d8dde3;}}
.page{{position:relative;width:{page_w}px;height:{page_h}px;background:{PAGE_BG};overflow:hidden;font-family:{font_family};direction:{direction};writing-mode:{writing_mode};text-align:{text_align};unicode-bidi:plaintext;color:#1f2933;}}
.blk{{position:absolute;box-sizing:border-box;overflow:hidden;line-height:1.25;white-space:normal;word-break:normal;overflow-wrap:anywhere;padding:2px 4px;}}
.lbl-document_title{{font-weight:800;line-height:1.12;}}
.lbl-metadata,.lbl-page_number,.lbl-footer,.lbl-caption,.lbl-reference,.lbl-note{{color:#4d5967;line-height:1.18;}}
.structure{{border:1.4px solid #aeb7c2;background:repeating-linear-gradient(135deg,#edf0f3,#edf0f3 12px,#f8f8f6 12px,#f8f8f6 24px);}}
.src-table{{background:#fff;border:1.5px solid #8f9aa6;}}
.table-lines{{width:100%;height:100%;background:linear-gradient(#c7d0da 1px,transparent 1px),linear-gradient(90deg,#c7d0da 1px,transparent 1px);background-size:100% 22%,20% 100%;}}
</style></head>
<body><main class="page" data-template-source="omnidocbench" data-template-id="{esc(row['template_id'])}">{''.join(html_blocks)}</main></body></html>
"""
    return html_text, label_blocks, dict(stats)


def safe_font(size: int) -> ImageFont.ImageFont:
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def draw_overlay(image_path: Path, label_path: Path, out_path: Path) -> dict[str, Any]:
    img = Image.open(image_path).convert("RGB")
    label = read_json(label_path)
    draw = ImageDraw.Draw(img)
    font = safe_font(max(18, int(min(img.size) * 0.032)))
    missing = []
    for block in label.get("blocks", []):
        if block.get("is_text") is False:
            continue
        order = block.get("reading_order")
        if order is None:
            missing.append(block.get("block_id"))
            continue
        c = block.get("coordinates") or {}
        x1, y1, x2, y2 = float(c["x_min"]), float(c["y_min"]), float(c["x_max"]), float(c["y_max"])
        color = (24, 109, 220)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        text = str(order)
        bbox = draw.textbbox((x1 + 4, y1 + 4), text, font=font)
        draw.rounded_rectangle([x1 + 4, y1 + 4, bbox[2] + 12, bbox[3] + 10], radius=5, fill="white", outline=color, width=2)
        draw.text((x1 + 8, y1 + 6), text, fill="black", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)
    return {"document_id": label_path.stem, "image": str(out_path), "missing": missing}


def make_contact_sheet(items: list[dict[str, Any]], out_path: Path) -> None:
    if not items:
        return
    thumb_w, thumb_h = 260, 360
    cols = 4
    rows = math.ceil(len(items) / cols)
    pad, caption_h = 20, 44
    sheet = Image.new("RGB", (cols * (thumb_w + pad) + pad, rows * (thumb_h + caption_h + pad) + pad), "#f3f4f6")
    draw = ImageDraw.Draw(sheet)
    font = safe_font(14)
    for idx, item in enumerate(items):
        row, col = divmod(idx, cols)
        x = pad + col * (thumb_w + pad)
        y = pad + row * (thumb_h + caption_h + pad)
        img = Image.open(item["image"]).convert("RGB")
        img.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        bg = Image.new("RGB", (thumb_w, thumb_h), "white")
        bg.paste(img, ((thumb_w - img.width) // 2, (thumb_h - img.height) // 2))
        sheet.paste(bg, (x, y))
        draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline="#9ca3af", width=1)
        draw.text((x, y + thumb_h + 7), item["document_id"][:30], fill="#111827", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(proc.stdout, end="", flush=True)
    if proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout)


def build_version(
    omni: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    output_root: Path,
    max_pages_per_category: int,
    languages: list[str],
) -> dict[str, Any]:
    profiles = language_profiles()
    records = choose_records()
    samplers = {lang: TextSampler(records[lang]) for lang in languages}
    page_w, page_h = 1240, 1754
    by_category = defaultdict(list)
    for row in selected:
        by_category[row["category"]].append(row)
    selected_by_category = {
        cat: sorted(rows, key=lambda r: r["omni_index"])[:max_pages_per_category]
        for cat, rows in by_category.items()
    }

    generation_rows = []
    for lang in languages:
        profile = profiles[lang]
        version_dir = output_root / "02_语种工程资源" / lang / "03_合成数据生成_20260702" / "VL6"
        if version_dir.exists():
            shutil.rmtree(version_dir)
        (version_dir / "metadata").mkdir(parents=True, exist_ok=True)
        write_json(version_dir / "metadata" / "language_profile.json", profile)
        html_manifest = []
        category_plan = []
        for category, rows in selected_by_category.items():
            cat_dir_name, cat_cn = CATEGORY_DIRS[category]
            cat_dir = version_dir / cat_dir_name
            for sub in ["html", "labels", "images", "metadata", "reports"]:
                (cat_dir / sub).mkdir(parents=True, exist_ok=True)
            category_plan.append({"category": category, "category_cn": cat_cn, "samples": len(rows), "template_source": "omnidocbench"})
            cat_render_manifest = []
            for local_idx, row in enumerate(rows, 1):
                omni_item = omni[row["omni_index"]]
                doc_id = f"{cat_dir_name[:2]}_{category}_omni_{local_idx:02d}"
                html_text, label_blocks, block_stats = render_html_doc(
                    row, omni_item, profile, samplers[lang], doc_id, page_w, page_h
                )
                html_path = cat_dir / "html" / f"{doc_id}.html"
                html_path.write_text(html_text, encoding="utf-8")
                label = {
                    "image_id": stable_id(f"{lang}:{doc_id}"),
                    "file_name": f"{doc_id}.png",
                    "status": "synthetic",
                    "attributes": {
                        "generator": "omnidocbench_vl6_generator_v1",
                        "template_source": "omnidocbench",
                        "omnidocbench_template_id": row["template_id"],
                        "omnidocbench_index": row["omni_index"],
                        "omnidocbench_image_path": row["image_path"],
                        "omnidocbench_data_source": row["data_source"],
                        "language_code": profile.get("language_code"),
                        "language_name": profile.get("language_name"),
                        "script_note": profile.get("script_note"),
                        "category": category,
                        "category_cn": cat_cn,
                        "document_id": doc_id,
                        "reading_order_policy": "omnidocbench_order_multicolumn_ltr_v1",
                        "filtered_blocks": row["filtered_blocks"],
                        "equation_blocks_filtered": row["equation_blocks"],
                        "structure_blocks_non_ocr": row["structure_blocks"],
                        "block_status_counts": block_stats,
                        "source_records": str(records[lang]),
                    },
                    "blocks": label_blocks,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                }
                label_path = cat_dir / "labels" / f"{doc_id}.json"
                write_json(label_path, label)
                item = {
                    "document_id": doc_id,
                    "html": str(html_path),
                    "label": str(label_path),
                    "image": str(cat_dir / "images" / f"{doc_id}.png"),
                    "page_width": page_w,
                    "page_height": page_h,
                    "category": category,
                    "category_cn": cat_cn,
                    "template_source": "omnidocbench",
                    "omnidocbench_template_id": row["template_id"],
                }
                html_manifest.append(item)
                cat_render_manifest.append(item)
                generation_rows.append({"language": lang, **item})
            write_json(cat_dir / "metadata" / "html_manifest.json", cat_render_manifest)
            write_json(cat_dir / "metadata" / "category_plan.json", [category_plan[-1]])
        write_json(version_dir / "metadata" / "html_manifest.json", html_manifest)
        write_json(version_dir / "metadata" / "category_plan.json", category_plan)
        write_json(
            version_dir / "metadata" / "text_source_manifest.json",
            {"language": lang, "records_jsonl": str(records[lang]), "template_source": "omnidocbench_only"},
        )
        run(
            [
                runtime_node(),
                str(SCRIPT_DIR / "render_vl6_omni.mjs"),
                "--version-dir",
                str(version_dir),
            ],
            env=node_env(),
        )
        overlay_items = []
        missing = []
        for label_path in sorted(version_dir.glob("*/labels/*.json")):
            image_path = label_path.parents[1] / "images" / f"{label_path.stem}.png"
            overlay = version_dir / "reports" / "reading_order_overlays" / f"{label_path.stem}_reading_order.jpg"
            item = draw_overlay(image_path, label_path, overlay)
            overlay_items.append(item)
            if item["missing"]:
                missing.append(item)
        make_contact_sheet(overlay_items, version_dir / "reports" / "contact_sheet_reading_order.jpg")
        summary = {
            "language": lang,
            "total_images": len(html_manifest),
            "categories": category_plan,
            "missing_reading_order_images": len(missing),
            "pass": bool(html_manifest) and not missing,
        }
        write_json(version_dir / "reports" / "vl6_omni_summary.json", summary)
    return {"generated": generation_rows}


def make_inventory_markdown(summary: dict[str, Any], selected: list[dict[str, Any]], out_path: Path) -> None:
    lines = [
        "# VL6 OmniDocBench 模板库存审计",
        "",
        f"- OmniDocBench 总页数：{summary['total_pages']}",
        f"- 合格模板页数：{summary['qualified_pages']}",
        f"- 本轮选用模板页数：{summary['selected_pages']}",
        "",
        "## 按类别统计",
        "",
        "| 类别 | 合格模板 | 选用模板 |",
        "|---|---:|---:|",
    ]
    qualified = summary.get("qualified_by_category", {})
    selected_counts = summary.get("selected_by_category", {})
    for _cat, (_dir, cn) in CATEGORY_DIRS.items():
        lines.append(f"| {cn} | {qualified.get(cn, 0)} | {selected_counts.get(cn, 0)} |")
    lines.extend(["", "## 选用模板", "", "| 类别 | template_id | data_source | layout | 文本块 | 公式过滤 | 结构块 |", "|---|---|---|---|---:|---:|---:|"])
    for row in selected:
        lines.append(
            f"| {row['category_cn']} | `{row['template_id']}` | {row['data_source']} | {row.get('layout') or ''} | "
            f"{row['text_blocks']} | {row['equation_blocks']} | {row['structure_blocks']} |"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_delivery_report(output_root: Path, inventory_summary: dict[str, Any], languages: list[str], out_path: Path) -> None:
    selected_category_dirs = {
        category_dir
        for _category, (category_dir, category_cn) in CATEGORY_DIRS.items()
        if inventory_summary.get("selected_by_category", {}).get(category_cn, 0) > 0
    }
    lines = [
        "# VL6 OmniDocBench 高质量模板版生成报告",
        "",
        "- 模板来源：OmniDocBench，仅使用带明确 `order` 的合格模板。",
        "- 本地模板：未使用。",
        "- 数量策略：质量优先，不补齐 12 x 6。",
        "- 阅读顺序：Omni order + 水平多栏左到右；非 OCR 结构块不编号。",
        "",
        "## 总览",
        "",
        f"- 语种数：{len(languages)}",
        f"- 选用模板页数：{inventory_summary['selected_pages']}",
        "",
        "| 语种 | 图片数 | 类别数 |",
        "|---|---:|---:|",
    ]
    total = 0
    for lang in languages:
        version_dir = output_root / "02_语种工程资源" / lang / "03_合成数据生成_20260702" / "VL6"
        summary_path = version_dir / "reports" / "vl6_omni_summary.json"
        summary = read_json(summary_path) if summary_path.exists() else {}
        total += int(summary.get("total_images", 0))
        lines.append(f"| {lang} | {summary.get('total_images', 0)} | {len(summary.get('categories', []))} |")
    lines.extend(["", f"- 总图片数：{total}", "", "## 已覆盖类别", ""])
    for _cat, (category_dir, cn) in CATEGORY_DIRS.items():
        count = inventory_summary.get("selected_by_category", {}).get(cn, 0)
        if count > 0:
            lines.append(f"- {category_dir}：{count} 个 OmniDocBench 模板。")
    lines.extend(["", "## 缺省说明", ""])
    missing_lines = []
    for category_dir in ORIGINAL_CATEGORY_DIRS:
        if category_dir not in selected_category_dirs:
            missing_lines.append(f"- {category_dir}：未找到可可靠映射且带完整 `order` 的 OmniDocBench 高质量模板，本轮不生成。")
    for _cat, (_dir, cn) in CATEGORY_DIRS.items():
        if inventory_summary.get("selected_by_category", {}).get(cn, 0) == 0:
            missing_lines.append(f"- {cn}：OmniDocBench 合格模板不足，本轮不生成。")
    lines.extend(missing_lines or ["- 无。"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", default="05_总报告与索引/omnidocbench_cache")
    parser.add_argument("--output-root", default=".")
    parser.add_argument("--max-templates-per-category", type=int, default=6)
    parser.add_argument("--languages", nargs="*", default=[lang for lang, _ in LANGUAGES])
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--no-proxy", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cache_dir = PROJECT_ROOT / args.cache_dir
    output_root = PROJECT_ROOT / args.output_root
    languages = args.languages
    omni = load_omni(cache_dir, not args.no_proxy)
    selected, summary = build_inventory(omni, args.max_templates_per_category)
    inventory_json = PROJECT_ROOT / "05_总报告与索引" / "VL6_omni_template_inventory.json"
    inventory_md = PROJECT_ROOT / "05_总报告与索引" / "VL6_omni_template_inventory.md"
    write_json(inventory_json, {"summary": summary, "selected": selected})
    make_inventory_markdown(summary, selected, inventory_md)
    if args.inventory_only:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    build_version(omni, selected, output_root, args.max_templates_per_category, languages)
    make_delivery_report(output_root, summary, languages, PROJECT_ROOT / "05_总报告与索引" / "VL6_omni_delivery_report.md")
    print(json.dumps({"inventory": summary, "languages": languages}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
