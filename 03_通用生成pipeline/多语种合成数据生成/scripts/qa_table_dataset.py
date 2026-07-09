#!/usr/bin/env python3
"""QA report for generated table-document dataset."""

from __future__ import annotations

import argparse
import collections
import json
import math
import re
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont, ImageStat


CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
TIBETAN_SMALL_MARK_RE = re.compile(r"[\u0f04-\u0f0a\u0f0c-\u0f14\u0f3a-\u0f3d]")
LATIN_RE = re.compile(r"[A-Za-z]")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
TIBETAN_RE = re.compile(r"[\u0f00-\u0fff]")
ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
MONGOLIAN_RE = re.compile(r"[\u1800-\u18af]")
HANGUL_RE = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
PRIVATE_USE_RE = re.compile(r"[\ue000-\uf8ff]")
REPLACEMENT_OR_BOX_RE = re.compile(r"[\ufffd\u25a0\u25a1\u25af]")
ZERO_WIDTH_UNSUPPORTED_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]")
MONGOLIAN_PRESENTATION_PUNCT_RE = re.compile(r"[︽︾︕︖︵︶︔﹇﹈]")
MONGOLIAN_UNSAFE_SYMBOL_RE = re.compile(r"[=+~※%!—–]")
SCRIPT_RESIDUE_PATTERNS = {
    "latin": LATIN_RE,
    "cjk": CJK_RE,
    "cyrillic": CYRILLIC_RE,
    "tibetan": TIBETAN_RE,
    "arabic": ARABIC_RE,
    "mongolian": MONGOLIAN_RE,
    "hangul": HANGUL_RE,
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profile(path: Path | None) -> Dict:
    profile = read_json(path) if path and path.exists() else {}
    for name in SCRIPT_RESIDUE_PATTERNS:
        profile.setdefault(f"max_{name}_ratio", 1.0)
    return profile


def allow_tibetan_small_marks(profile: Dict) -> bool:
    return str(profile.get("cleanup_profile", "")).lower().startswith("tibetan")


def ratio(count: int, text: str) -> float:
    return count / max(len(text), 1)


def unsupported_chars(text: str, profile: Dict | None = None) -> list[str]:
    """Return chars that are likely to render as tofu or break this profile's script."""
    text = text or ""
    profile = profile or {}
    cleanup = str(profile.get("cleanup_profile", "")).lower()
    bad: list[str] = []
    for pattern in [PRIVATE_USE_RE, REPLACEMENT_OR_BOX_RE]:
        bad.extend(pattern.findall(text))
    if cleanup not in {"arabic", "uyghur", "kazakh_arabic"}:
        bad.extend(ZERO_WIDTH_UNSUPPORTED_RE.findall(text))
    if cleanup in {"mongolian", "traditional_mongolian"}:
        bad.extend(MONGOLIAN_PRESENTATION_PUNCT_RE.findall(text))
        bad.extend(MONGOLIAN_UNSAFE_SYMBOL_RE.findall(text))
    return bad


def safe_font(size: int):
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        p = Path(candidate)
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def image_nonblank_score(img: Image.Image) -> float:
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    return float(stat.stddev[0])


def draw_overlay(image_path: Path, label_path: Path, output_path: Path) -> Dict:
    img = Image.open(image_path).convert("RGB")
    label = read_json(label_path)
    draw = ImageDraw.Draw(img)
    colors = {
        "document_title": (190, 40, 40),
        "document_subtitle": (220, 120, 30),
        "metadata": (120, 80, 180),
        "table_header": (30, 100, 190),
        "table_cell_number": (20, 150, 90),
        "table_cell_text": (30, 140, 150),
        "note": (180, 90, 30),
        "footer": (110, 110, 110),
    }
    for block in label.get("blocks", []):
        c = block["coordinates"]
        color = colors.get(block.get("block_label"), (240, 30, 160))
        draw.rectangle([c["x_min"], c["y_min"], c["x_max"], c["y_max"]], outline=color, width=3)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=92)
    return {"overlay": str(output_path), "blocks": len(label.get("blocks", []))}


def make_contact_sheet(items: List[Dict], out_path: Path) -> None:
    thumb_w = 260
    thumb_h = 360
    cols = 4
    rows = math.ceil(len(items) / cols)
    pad = 22
    caption_h = 52
    sheet = Image.new("RGB", (cols * (thumb_w + pad) + pad, rows * (thumb_h + caption_h + pad) + pad), "#f1f3f5")
    draw = ImageDraw.Draw(sheet)
    font = safe_font(20)
    small = safe_font(16)
    for idx, item in enumerate(items):
        row, col = divmod(idx, cols)
        x = pad + col * (thumb_w + pad)
        y = pad + row * (thumb_h + caption_h + pad)
        img = Image.open(item["image"]).convert("RGB")
        img.thumbnail((thumb_w, thumb_h), Image.LANCZOS)
        bg = Image.new("RGB", (thumb_w, thumb_h), "white")
        ox = (thumb_w - img.width) // 2
        oy = (thumb_h - img.height) // 2
        bg.paste(img, (ox, oy))
        sheet.paste(bg, (x, y))
        draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline="#9aa3ad", width=1)
        draw.text((x, y + thumb_h + 8), item["document_id"], fill="#1f2937", font=font)
        draw.text(
            (x, y + thumb_h + 31),
            f"blocks={item['blocks']} overflow={item['overflow_blocks']}",
            fill="#4b5563",
            font=small,
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def min_blocks_for(item: Dict, label: Dict | None = None) -> int:
    category = item.get("category") or "default"
    thresholds = {
        "table_document": 18,
        "newspaper": 8,
        "invoice_receipt": 18,
        "notice_announcement": 6,
        "book_textbook": 5,
        "poster_flyer": 4,
        "certificate": 5,
        "form_registration": 14,
        "schedule_timetable": 18,
        "report_brief": 16,
        "menu_price_list": 16,
        "letter_official": 8,
        "book_page": 8,
        "textbook_page": 10,
        "newspaper_page": 18,
        "magazine_journal": 9,
        "academic_paper": 12,
        "historical_classic": 10,
        "exam_paper": 20,
        "complex_form": 18,
        "certificate_proof": 6,
        "sign_poster_scene": 4,
        "handwritten_letter": 10,
        "default": 8,
    }
    threshold = thresholds.get(category, thresholds["default"])
    crop = ((label or {}).get("attributes") or {}).get("diagnostics", {}).get("crop", {})
    if crop.get("enabled"):
        original_area = max(float(crop.get("original_width") or 0) * float(crop.get("original_height") or 0), 1.0)
        cropped_area = max(float(crop.get("width") or 0) * float(crop.get("height") or 0), 1.0)
        area_ratio = cropped_area / original_area
        if area_ratio < 0.45:
            threshold = max(4, math.ceil(threshold * 0.70))
        elif area_ratio < 0.65:
            threshold = max(4, math.ceil(threshold * 0.82))
    return threshold


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--language-profile")
    args = parser.parse_args()

    root = Path(args.dataset_dir)
    profile = load_profile(Path(args.language_profile) if args.language_profile else None)
    render_manifest = read_json(root / "metadata" / "render_manifest.json")
    qa_items = []
    overlays = []
    for item in render_manifest:
        image_path = Path(item["image"])
        label_path = Path(item["label"])
        img = Image.open(image_path)
        label = read_json(label_path)
        doc_mixed = str((label.get("attributes") or {}).get("language_mix_mode", "")) == "mixed"
        nonblank = image_nonblank_score(img)
        out_of_bounds = 0
        tiny_boxes = 0
        cyrillic_blocks = 0
        small_mark_blocks = 0
        pua_blocks = 0
        unsupported_char_blocks = 0
        unsupported_char_counts = collections.Counter()
        residue_blocks = {name: 0 for name in SCRIPT_RESIDUE_PATTERNS}
        width, height = img.size
        for block in label.get("blocks", []):
            c = block["coordinates"]
            text = block.get("block_content") or ""
            is_text = block.get("is_text", True)
            if is_text:
                if CYRILLIC_RE.search(text):
                    cyrillic_blocks += 1
                if TIBETAN_SMALL_MARK_RE.search(text):
                    small_mark_blocks += 1
                if PRIVATE_USE_RE.search(text):
                    pua_blocks += 1
                bad_chars = unsupported_chars(text, profile)
                if bad_chars:
                    unsupported_char_blocks += 1
                    unsupported_char_counts.update(bad_chars)
                for name, pattern in SCRIPT_RESIDUE_PATTERNS.items():
                    if name in ("cjk", "latin") and doc_mixed:
                        continue  # intentional Chinese mixing may carry incidental Latin (citations/emails/pinyin); validated by qa_language_validity
                    if ratio(len(pattern.findall(text)), text) > float(profile.get(f"max_{name}_ratio", 1.0)):
                        residue_blocks[name] += 1
            if is_text and (c["x_min"] < 0 or c["y_min"] < 0 or c["x_max"] > width + 1 or c["y_max"] > height + 1):
                out_of_bounds += 1
            if is_text and ((c["x_max"] - c["x_min"]) < 5 or (c["y_max"] - c["y_min"]) < 5):
                tiny_boxes += 1
        overlay_path = root / "reports" / "overlays" / f"{item['document_id']}_overlay.jpg"
        overlays.append(draw_overlay(image_path, label_path, overlay_path))
        min_blocks = min_blocks_for(item, label)
        pass_basic = (
            nonblank > 8
            and item["blocks"] >= min_blocks
            and item["overflow_blocks"] == 0
            and out_of_bounds == 0
            and tiny_boxes == 0
            and all(count == 0 for count in residue_blocks.values())
            and (small_mark_blocks == 0 or allow_tibetan_small_marks(profile))
            and pua_blocks == 0
            and unsupported_char_blocks == 0
        )
        qa_items.append(
            {
                **item,
                "width": width,
                "height": height,
                "nonblank_score": round(nonblank, 3),
                "min_blocks_required": min_blocks,
                "out_of_bounds_blocks": out_of_bounds,
                "tiny_boxes": tiny_boxes,
                "cyrillic_blocks": cyrillic_blocks,
                "tibetan_small_mark_blocks": small_mark_blocks,
                "pua_blocks": pua_blocks,
                "unsupported_char_blocks": unsupported_char_blocks,
                "unsupported_char_counts": dict(unsupported_char_counts.most_common(30)),
                "script_residue_blocks": residue_blocks,
                "pass_basic": pass_basic,
            }
        )

    make_contact_sheet(qa_items, root / "reports" / "contact_sheet.jpg")
    make_contact_sheet(
        [{**item, "image": str(root / "reports" / "overlays" / f"{item['document_id']}_overlay.jpg")} for item in qa_items],
        root / "reports" / "contact_sheet_with_boxes.jpg",
    )

    by_category = collections.defaultdict(list)
    for item in qa_items:
        by_category[item.get("category") or "uncategorized"].append(item)
    for category, items in sorted(by_category.items()):
        make_contact_sheet(items, root / "reports" / "by_category" / f"{category}.jpg")
        make_contact_sheet(
            [{**item, "image": str(root / "reports" / "overlays" / f"{item['document_id']}_overlay.jpg")} for item in items],
            root / "reports" / "by_category" / f"{category}_with_boxes.jpg",
        )

    category_summary = {}
    for category, items in sorted(by_category.items()):
        category_summary[category] = {
            "total": len(items),
            "passed_basic": sum(1 for item in items if item["pass_basic"]),
            "total_blocks": sum(item["blocks"] for item in items),
            "overflow_blocks": sum(item["overflow_blocks"] for item in items),
            "out_of_bounds_blocks": sum(item["out_of_bounds_blocks"] for item in items),
            "cyrillic_blocks": sum(item["cyrillic_blocks"] for item in items),
            "tibetan_small_mark_blocks": sum(item["tibetan_small_mark_blocks"] for item in items),
            "pua_blocks": sum(item["pua_blocks"] for item in items),
            "unsupported_char_blocks": sum(item["unsupported_char_blocks"] for item in items),
            "script_residue_blocks": {
                name: sum(item["script_residue_blocks"].get(name, 0) for item in items)
                for name in SCRIPT_RESIDUE_PATTERNS
            },
        }
    summary = {
        "dataset_dir": str(root),
        "total_images": len(qa_items),
        "passed_basic": sum(1 for item in qa_items if item["pass_basic"]),
        "failed_basic": [item["document_id"] for item in qa_items if not item["pass_basic"]],
        "total_blocks": sum(item["blocks"] for item in qa_items),
        "total_overflow_blocks": sum(item["overflow_blocks"] for item in qa_items),
        "total_out_of_bounds_blocks": sum(item["out_of_bounds_blocks"] for item in qa_items),
        "total_cyrillic_blocks": sum(item["cyrillic_blocks"] for item in qa_items),
        "total_tibetan_small_mark_blocks": sum(item["tibetan_small_mark_blocks"] for item in qa_items),
        "total_pua_blocks": sum(item["pua_blocks"] for item in qa_items),
        "total_unsupported_char_blocks": sum(item["unsupported_char_blocks"] for item in qa_items),
        "unsupported_char_counts": dict(
            sum((collections.Counter(item["unsupported_char_counts"]) for item in qa_items), collections.Counter()).most_common(60)
        ),
        "total_script_residue_blocks": {
            name: sum(item["script_residue_blocks"].get(name, 0) for item in qa_items)
            for name in SCRIPT_RESIDUE_PATTERNS
        },
        "category_summary": category_summary,
        "items": qa_items,
    }
    write_json(root / "reports" / "qa_summary.json", summary)

    category_rows = "\n".join(
        f"| {category} | {stats['total']} | {stats['passed_basic']} | {stats['total_blocks']} | {stats['overflow_blocks']} | {stats['out_of_bounds_blocks']} | {stats['cyrillic_blocks']} | {stats['tibetan_small_mark_blocks']} | {stats['pua_blocks']} | {stats['unsupported_char_blocks']} |"
        for category, stats in category_summary.items()
    )
    md_rows = "\n".join(
        f"| {item['document_id']} | {item['blocks']} | {item['overflow_blocks']} | "
        f"{item['out_of_bounds_blocks']} | {item['cyrillic_blocks']} | {item['tibetan_small_mark_blocks']} | {item['pua_blocks']} | {item['unsupported_char_blocks']} | {item['min_blocks_required']} | {item['nonblank_score']} | {'通过' if item['pass_basic'] else '需检查'} |"
        for item in qa_items
    )
    md = f"""# 表格文档合成样本质检报告

## 自动检查结论

- 图片数：{summary['total_images']}
- 基础检查通过：{summary['passed_basic']} / {summary['total_images']}
- 总标签块数：{summary['total_blocks']}
- DOM 溢出块数：{summary['total_overflow_blocks']}
- 越界标签块数：{summary['total_out_of_bounds_blocks']}
- 西里尔残留块数：{summary['total_cyrillic_blocks']}
- 藏文句读/装饰小圆圈残留块数：{summary['total_tibetan_small_mark_blocks']}
- 私用区字符块数：{summary['total_pua_blocks']}
- 异常/方框风险字符块数：{summary['total_unsupported_char_blocks']}

## 总览图

- 原图联系图：`reports/contact_sheet.jpg`
- 标签框联系图：`reports/contact_sheet_with_boxes.jpg`
- 按类别联系图：`reports/by_category/`

## 类别汇总

| 类别 | 图片数 | 通过数 | 标签块 | DOM溢出 | 越界框 | 西里尔残留 | 小圆圈残留 | 私用区字符 | 异常字符 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{category_rows}

## 明细

| 样本 | 标签块 | DOM溢出 | 越界框 | 西里尔残留 | 小圆圈残留 | 私用区字符 | 异常字符 | 最小块数阈值 | 非空分数 | 结论 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
{md_rows}

## 建议人工查看点

1. 报纸是否为竖版、多栏、文本密集，而不是横向资讯页。
2. 证书与标牌海报是否有明显视觉区分。
3. 整体是否仍然表格过多，除表单/考试/论文外不应以大表格为主体。
4. 藏文是否显示正常，有无乱码、缺字、西里尔残留或小圆圈残留。
5. 标签框是否覆盖文字区域，是否明显偏移。
"""
    (root / "reports" / "QA_REPORT.md").write_text(md, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
