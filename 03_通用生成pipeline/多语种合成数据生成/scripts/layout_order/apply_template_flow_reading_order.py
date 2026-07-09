#!/usr/bin/env python3
"""Assign reading order with template semantics as the primary source.

This pass is designed for synthetic VL pages where the generator already knows
the intended DOM/template order. It intentionally does not let external layout
detectors override strong labels such as document_title. PP-DocLayout can still
be consumed as QA evidence, but sorting is driven by template labels, DOM order,
and category-specific flow policies.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
FOCUS_CATEGORIES = {"01_报纸页", "07_杂志期刊页", "08_学术文献页"}
HEADER_LABELS = {"metadata", "document_title", "document_subtitle"}
TITLE_LABELS = {"document_title", "document_subtitle", "section_title"}
FOOTER_LABELS = {"footer", "page_number"}
FIGURE_LABELS = {"image", "photo", "figure", "photo_lead", "image_figure", "caption"}
TABLE_LABELS = {"table_header", "table_cell_text", "table_cell_number"}
FORM_LABELS = {"field_label", "field_value", "option", "answer_area"}
QUESTION_LABELS = {"question", "question_text", "option", "answer_area"}
EMPTY_NON_OCR_LABELS = {"answer_area"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(p for p in version_dir.iterdir() if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit())


def image_for_label(label_path: Path) -> Path:
    image_dir = label_path.parents[1] / "images"
    for suffix in IMAGE_SUFFIXES:
        candidate = image_dir / f"{label_path.stem}{suffix}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"no image found for {label_path}")


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


def block_box(block: dict[str, Any]) -> tuple[float, float, float, float]:
    c = block.get("coordinates") or {}
    return (
        float(c.get("x_min", 0)),
        float(c.get("y_min", 0)),
        float(c.get("x_max", 0)),
        float(c.get("y_max", 0)),
    )


def center(block: dict[str, Any]) -> tuple[float, float]:
    x1, y1, x2, y2 = block_box(block)
    return (x1 + x2) / 2, (y1 + y2) / 2


def area(box: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def language_policy(profile: dict[str, Any] | None) -> str:
    profile = profile or {}
    writing_mode = str(profile.get("css_writing_mode", "horizontal-tb")).lower()
    direction = str(profile.get("css_direction", "ltr")).lower()
    cleanup = str(profile.get("cleanup_profile", "")).lower()
    if writing_mode.startswith("vertical") or cleanup == "traditional_mongolian":
        return "vertical"
    if direction == "rtl":
        return "rtl"
    return "ltr"


def effective_policy(profile: dict[str, Any] | None, force_horizontal_flow: str) -> str:
    policy = language_policy(profile)
    if policy == "vertical":
        return policy
    if force_horizontal_flow in {"ltr", "rtl"}:
        return force_horizontal_flow
    return policy


def is_ocr_text_block(block: dict[str, Any]) -> bool:
    if block.get("is_text", True) is False:
        return False
    text = str(block.get("block_content") or "").strip()
    if text:
        return True
    return (block.get("block_label") or "") not in EMPTY_NON_OCR_LABELS


def page_size(label: dict[str, Any]) -> tuple[float, float]:
    attrs = label.get("attributes", {})
    diagnostics = attrs.get("diagnostics", {})
    crop = diagnostics.get("crop", {})
    page_w = float(crop.get("width") or diagnostics.get("page_width") or 1)
    page_h = float(crop.get("height") or diagnostics.get("page_height") or 1)
    return page_w, page_h


def dom_index(block: dict[str, Any], idx: int) -> int:
    attrs = block.get("attributes") or {}
    value = attrs.get("dom_index", block.get("order", idx))
    try:
        return int(value)
    except (TypeError, ValueError):
        return idx


def semantic_role(label_name: str, is_text: bool) -> str:
    if not is_text:
        return "figure" if label_name in FIGURE_LABELS else "non_text"
    return {
        "metadata": "metadata",
        "document_title": "title",
        "document_subtitle": "subtitle",
        "section_title": "section_title",
        "paragraph": "paragraph",
        "caption": "caption",
        "quote": "quote",
        "list_item": "list_item",
        "table_header": "table_header",
        "table_cell_text": "table_cell",
        "table_cell_number": "table_cell",
        "footer": "footer",
        "page_number": "page_number",
    }.get(label_name, label_name or "text")


def group_for(block: dict[str, Any], page_h: float) -> str:
    label_name = block.get("block_label") or ""
    _, cy = center(block)
    is_text = block.get("is_text", True) is not False
    if not is_text:
        return "figure" if label_name in FIGURE_LABELS else "non_text"
    if label_name == "document_title":
        return "masthead"
    if label_name == "document_subtitle":
        return "masthead"
    if label_name == "metadata" and cy < page_h * 0.18:
        return "masthead"
    if label_name in FOOTER_LABELS or cy > page_h * 0.92:
        return "footer"
    if label_name in TABLE_LABELS:
        return "table"
    if label_name in QUESTION_LABELS:
        return "question"
    if label_name in FORM_LABELS:
        return "form"
    if label_name in FIGURE_LABELS:
        return "figure"
    return "body"


def strong_rank(block: dict[str, Any], page_h: float) -> int:
    label_name = block.get("block_label") or ""
    group = group_for(block, page_h)
    if label_name == "metadata" and center(block)[1] < page_h * 0.18:
        return 0
    if label_name == "document_title":
        return 1
    if label_name == "document_subtitle":
        return 2
    if group == "masthead":
        return 3
    if group == "body":
        return 10
    if group in {"table", "form", "question"}:
        return 20
    if group == "figure":
        return 25
    if group == "footer":
        return 90
    return 95


def visual_column(block: dict[str, Any], page_w: float, policy: str) -> int:
    cx, _ = center(block)
    if page_w <= 0:
        return 0
    raw = int(cx / page_w * 6)
    raw = max(0, min(5, raw))
    if policy == "rtl":
        return 5 - raw
    return raw


def multicolumn_key(
    block: dict[str, Any],
    idx: int,
    page_w: float,
    policy: str,
    multicolumn_flow: str,
) -> tuple[Any, ...]:
    x1, y1, _, _ = block_box(block)
    cx, cy = center(block)
    d = dom_index(block, idx)
    if multicolumn_flow == "template":
        return (d, y1, x1)
    flow_policy = policy if multicolumn_flow == "language" else multicolumn_flow
    col = visual_column(block, page_w, flow_policy)
    if flow_policy == "rtl":
        return (col, y1, -cx, d)
    return (col, y1, cx, d)


def vertical_column(block: dict[str, Any], page_w: float) -> int:
    cx, _ = center(block)
    if page_w <= 0:
        return 0
    return max(0, min(7, int(cx / page_w * 8)))


def category_policy(category_dir: str, policy: str) -> str:
    if category_dir == "01_报纸页":
        return f"template_newspaper_{policy}"
    if category_dir == "07_杂志期刊页":
        return f"template_magazine_{policy}"
    if category_dir == "08_学术文献页":
        return f"template_academic_{policy}"
    if category_dir == "02_证书证明":
        return f"template_certificate_{policy}"
    if category_dir == "03_考试卷":
        return f"template_exam_{policy}"
    if category_dir in {"05_书籍页", "06_教科书页", "09_历史文档_古籍", "10_公告通知", "12_手写笔记信件"}:
        return f"template_reading_page_{policy}"
    if category_dir == "11_复杂表单登记页":
        return f"template_form_{policy}"
    if category_dir == "04_标牌海报场景":
        return f"template_poster_{policy}"
    return f"template_generic_{policy}"


def template_flow_key(
    block: dict[str, Any],
    idx: int,
    category_dir: str,
    page_w: float,
    page_h: float,
    policy: str,
    multicolumn_flow: str = "template",
) -> tuple[Any, ...]:
    label_name = block.get("block_label") or ""
    x1, y1, x2, y2 = block_box(block)
    cx, cy = center(block)
    d = dom_index(block, idx)
    rank = strong_rank(block, page_h)
    group = group_for(block, page_h)

    # Strong labels must win. This fixes cases where external layout regions put
    # body text before the newspaper masthead/title.
    if rank < 10:
        return (rank, d, cy, cx)
    if group == "footer":
        return (90, cy, d)

    if policy == "vertical":
        col = vertical_column(block, page_w)
        # The generator DOM is the most reliable signal for traditional
        # Mongolian vertical layouts, where detector regions can be sparse.
        return (rank, d, col, cx, cy)

    if category_dir == "01_报纸页":
        # Newspaper templates were emitted story-by-story in DOM order. Use DOM
        # as primary body flow to avoid row-wise interleaving across columns.
        return (rank, *multicolumn_key(block, idx, page_w, policy, multicolumn_flow))

    if category_dir == "07_杂志期刊页":
        # Magazines often have an image lead on the left and title/content on the
        # right. DOM order already represents the intended feature flow better
        # than pure x/y sorting, but keep strong title labels first.
        return (rank, *multicolumn_key(block, idx, page_w, policy, multicolumn_flow))

    if category_dir == "08_学术文献页":
        # Academic pages usually read header/abstract first, then columns. DOM
        # order captures this in current templates and avoids alternating rows.
        return (rank, *multicolumn_key(block, idx, page_w, policy, multicolumn_flow))

    if category_dir in {
        "02_证书证明",
        "03_考试卷",
        "04_标牌海报场景",
        "05_书籍页",
        "06_教科书页",
        "09_历史文档_古籍",
        "10_公告通知",
        "11_复杂表单登记页",
        "12_手写笔记信件",
    }:
        # These templates are generated in the intended semantic reading flow:
        # certificates from title to recipient/body/signature; exams from
        # question to options/answer area; forms from label to value. DOM order
        # is a better source of truth than post-render geometry.
        return (rank, d, y1, x1)

    col = visual_column(block, page_w, policy)
    if policy == "rtl":
        return (rank, col, cy, -cx, d)
    return (rank, col, cy, cx, d)


def assign_label(
    label: dict[str, Any],
    category_dir: str,
    profile: dict[str, Any] | None,
    force_horizontal_flow: str = "language",
    multicolumn_flow: str = "template",
) -> dict[str, Any]:
    policy = effective_policy(profile, force_horizontal_flow)
    page_w, page_h = page_size(label)
    decorated = []
    for idx, block in enumerate(label.get("blocks", [])):
        if not is_ocr_text_block(block):
            block["is_text"] = False
            block.pop("reading_order", None)
            block["reading_group"] = "non_ocr"
            block["reading_role"] = semantic_role(block.get("block_label") or "", False)
            block["reading_order_confidence"] = "none"
            block["reading_region"] = "non_ocr"
            block["reading_flow_id"] = f"{category_dir}:non_ocr"
            block["reading_flow_rank"] = 999
            continue
        key = template_flow_key(block, idx, category_dir, page_w, page_h, policy, multicolumn_flow)
        decorated.append((key, idx, block))
    decorated.sort(key=lambda item: item[0])
    for order, (_, idx, block) in enumerate(decorated, 1):
        label_name = block.get("block_label") or ""
        is_text = block.get("is_text", True) is not False
        group = group_for(block, page_h)
        block["reading_order"] = order
        block["reading_group"] = group
        block["reading_role"] = semantic_role(label_name, is_text)
        block["reading_order_confidence"] = "high" if strong_rank(block, page_h) < 10 else "medium"
        block["reading_region"] = group
        block["reading_flow_id"] = f"{category_dir}:{group}"
        block["reading_flow_rank"] = strong_rank(block, page_h)
        block["column_index"] = vertical_column(block, page_w) if policy == "vertical" else visual_column(block, page_w, policy)
        attrs = block.setdefault("attributes", {})
        attrs["template_flow_dom_index"] = dom_index(block, idx)
        attrs["template_flow_policy"] = category_policy(category_dir, policy)
    label.setdefault("attributes", {})["reading_order_policy"] = f"{category_policy(category_dir, policy)}_v1"
    return label


def draw_overlay(image_path: Path, label: dict[str, Any], out_path: Path) -> None:
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = safe_font(max(18, int(min(img.size) * 0.032)))
    small = safe_font(max(13, int(min(img.size) * 0.016)))
    for block in label.get("blocks", []):
        order = block.get("reading_order")
        x1, y1, x2, y2 = block_box(block)
        color = (24, 109, 220) if block.get("is_text", True) is not False else (230, 125, 35)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        text = str(order)
        bbox = draw.textbbox((x1 + 4, y1 + 4), text, font=font)
        draw.rounded_rectangle([x1 + 4, y1 + 4, bbox[2] + 12, bbox[3] + 10], radius=5, fill="white", outline=color, width=2)
        draw.text((x1 + 8, y1 + 6), text, fill="black", font=font)
        role = str(block.get("reading_role") or "")
        if area(block_box(block)) > 5000:
            draw.text((x1 + 8, y1 + 30), role[:18], fill=color, font=small)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)


def make_contact_sheet(items: list[dict[str, Any]], out_path: Path) -> None:
    thumb_w, thumb_h = 280, 380
    cols = 3
    rows = math.ceil(len(items) / cols)
    pad, caption_h = 20, 46
    sheet = Image.new("RGB", (cols * (thumb_w + pad) + pad, rows * (thumb_h + caption_h + pad) + pad), "#f3f4f6")
    draw = ImageDraw.Draw(sheet)
    font = safe_font(15)
    for idx, item in enumerate(items):
        row, col = divmod(idx, cols)
        x = pad + col * (thumb_w + pad)
        y = pad + row * (thumb_h + caption_h + pad)
        img = Image.open(item["overlay"]).convert("RGB")
        img.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        bg = Image.new("RGB", (thumb_w, thumb_h), "white")
        bg.paste(img, ((thumb_w - img.width) // 2, (thumb_h - img.height) // 2))
        sheet.paste(bg, (x, y))
        draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline="#9ca3af", width=1)
        draw.text((x, y + thumb_h + 7), item["document_id"][:32], fill="#111827", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def copy_assets_for_category(src_cat: Path, dst_cat: Path) -> None:
    for sub in ("images", "html", "metadata"):
        src = src_cat / sub
        dst = dst_cat / sub
        if src.exists() and not dst.exists():
            shutil.copytree(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    parser.add_argument("--language-profile")
    parser.add_argument("--output-version-dir", required=True)
    parser.add_argument("--categories", nargs="*", default=[])
    parser.add_argument("--limit-per-category", type=int, default=0)
    parser.add_argument("--no-copy-assets", action="store_true")
    parser.add_argument(
        "--force-horizontal-flow",
        choices=["language", "ltr", "rtl"],
        default="language",
        help="Override horizontal language flow for reading_order; vertical scripts remain vertical.",
    )
    parser.add_argument(
        "--multicolumn-flow",
        choices=["template", "language", "ltr", "rtl"],
        default="template",
        help="Flow policy for newspaper/magazine/academic body columns.",
    )
    args = parser.parse_args()

    version_dir = Path(args.version_dir)
    output_dir = Path(args.output_version_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = read_json(Path(args.language_profile)) if args.language_profile else None
    wanted = set(args.categories)

    items: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for cat_dir in category_dirs(version_dir):
        if wanted and cat_dir.name not in wanted:
            continue
        out_cat = output_dir / cat_dir.name
        if not args.no_copy_assets:
            copy_assets_for_category(cat_dir, out_cat)
        labels = sorted((cat_dir / "labels").glob("*.json"))
        if args.limit_per_category:
            labels = labels[: args.limit_per_category]
        for label_path in labels:
            try:
                label = assign_label(
                    copy.deepcopy(read_json(label_path)),
                    cat_dir.name,
                    profile,
                    args.force_horizontal_flow,
                    args.multicolumn_flow,
                )
                out_label = output_dir / label_path.relative_to(version_dir)
                write_json(out_label, label)
                overlay = output_dir / "reports" / "template_flow_overlays" / cat_dir.name / f"{label_path.stem}_template_flow.jpg"
                draw_overlay(image_for_label(label_path), label, overlay)
                items.append(
                    {
                        "category": cat_dir.name,
                        "document_id": label_path.stem,
                        "label": str(out_label),
                        "overlay": str(overlay),
                        "blocks": len(label.get("blocks", [])),
                    }
                )
            except Exception as exc:  # pragma: no cover
                failures.append({"label": str(label_path), "error": str(exc)})

    contact_sheet = output_dir / "reports" / "contact_sheet_template_flow_reading_order.jpg"
    if items:
        make_contact_sheet(items, contact_sheet)
    summary = {
        "input_version_dir": str(version_dir),
        "output_version_dir": str(output_dir),
        "categories": sorted(wanted),
        "labels_written": len(items),
        "failed": len(failures),
        "failures": failures,
        "contact_sheet": str(contact_sheet) if items else None,
        "policy": f"template_flow_{effective_policy(profile, args.force_horizontal_flow)}_v1",
        "pass": not failures and bool(items),
    }
    write_json(output_dir / "reports" / "template_flow_reading_order_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
