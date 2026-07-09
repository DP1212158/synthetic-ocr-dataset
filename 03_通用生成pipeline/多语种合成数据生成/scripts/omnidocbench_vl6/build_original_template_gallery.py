#!/usr/bin/env python3
"""Build a gallery of the original OmniDocBench templates used by VL6."""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download
from PIL import Image, ImageDraw, ImageFont


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
OMNI_REPO = "opendatalab/OmniDocBench"
OMNI_JSON = PROJECT_ROOT / "05_总报告与索引" / "omnidocbench_cache" / "OmniDocBench.json"
INVENTORY_JSON = PROJECT_ROOT / "05_总报告与索引" / "VL6_omni_template_inventory.json"
OUTPUT_DIR = PROJECT_ROOT / "05_总报告与索引" / "VL6_omni_original_templates"

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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def proxy_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("http_proxy", "http://agent.baidu.com:8891")
    env.setdefault("https_proxy", "http://agent.baidu.com:8891")
    env.setdefault("no_proxy", "baidu.com,baidubce.com,bj.bcebos.com,bfsu.edu.cn,tsinghua.edu.cn")
    return env


def esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


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


def poly_to_bbox(poly: list[Any]) -> tuple[float, float, float, float] | None:
    if not isinstance(poly, list) or len(poly) < 8:
        return None
    xs = [float(poly[i]) for i in range(0, len(poly), 2)]
    ys = [float(poly[i]) for i in range(1, len(poly), 2)]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def download_original(image_name: str, out_path: Path, use_proxy: bool) -> None:
    if out_path.exists():
        return
    env = proxy_env() if use_proxy else os.environ.copy()
    old_env = os.environ.copy()
    try:
        os.environ.update(env)
        cached = Path(
            hf_hub_download(
                repo_id=OMNI_REPO,
                repo_type="dataset",
                filename=f"images/{image_name}",
                local_dir=str(PROJECT_ROOT / "05_总报告与索引" / "omnidocbench_cache"),
            )
        )
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cached, out_path)


def draw_original_overlay(original_path: Path, omni_item: dict[str, Any], out_path: Path) -> None:
    img = Image.open(original_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = safe_font(max(16, int(min(img.size) * 0.025)))

    for block in omni_item.get("layout_dets") or []:
        typ = str(block.get("category_type") or "")
        box = poly_to_bbox(block.get("poly") or [])
        if not box:
            continue
        x1, y1, x2, y2 = box
        if typ in STRUCTURE_TYPES:
            draw.rectangle([x1, y1, x2, y2], outline=(135, 145, 160), width=3)
            continue
        if typ not in TEXT_TYPES:
            continue
        try:
            order = int(block.get("order"))
        except (TypeError, ValueError):
            continue
        color = (20, 96, 190)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        badge = str(order)
        bbox = draw.textbbox((x1 + 4, y1 + 4), badge, font=font)
        draw.rounded_rectangle([x1 + 4, y1 + 4, bbox[2] + 12, bbox[3] + 10], radius=5, fill="white", outline=color, width=2)
        draw.text((x1 + 8, y1 + 6), badge, fill=(0, 0, 0), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)


def find_generated_by_template(language: str) -> dict[str, dict[str, str]]:
    root = PROJECT_ROOT / "02_语种工程资源" / language / "03_合成数据生成" / "VL6"
    found: dict[str, dict[str, str]] = {}
    for label_path in sorted(root.glob("*/labels/*.json")):
        label = read_json(label_path)
        template_id = (label.get("attributes") or {}).get("omnidocbench_template_id")
        if not template_id or template_id in found:
            continue
        image_path = label_path.parents[1] / "images" / f"{label_path.stem}.png"
        overlay_path = root / "reports" / "reading_order_overlays" / f"{label_path.stem}_reading_order.jpg"
        found[template_id] = {
            "label": str(label_path),
            "image": str(image_path),
            "overlay": str(overlay_path),
            "document_id": label_path.stem,
        }
    return found


def fit_image(path: Path, box: tuple[int, int], bg: str = "white") -> Image.Image:
    img = Image.open(path).convert("RGB")
    img.thumbnail(box, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", box, bg)
    canvas.paste(img, ((box[0] - img.width) // 2, (box[1] - img.height) // 2))
    return canvas


def make_comparison(row: dict[str, Any], original_overlay: Path, generated_overlay: Path | None, out_path: Path) -> None:
    panel_w, panel_h = 520, 720
    caption_h = 72
    gap = 24
    cols = 2 if generated_overlay and generated_overlay.exists() else 1
    sheet = Image.new("RGB", (cols * panel_w + (cols + 1) * gap, panel_h + caption_h + 2 * gap), "#f3f4f6")
    draw = ImageDraw.Draw(sheet)
    font = safe_font(18)
    small = safe_font(14)

    panels = [(original_overlay, "OmniDocBench 原图 + 原始 order")]
    if generated_overlay and generated_overlay.exists():
        panels.append((generated_overlay, "VL6 生成图 + VL6 reading_order"))

    for idx, (path, title) in enumerate(panels):
        x = gap + idx * (panel_w + gap)
        y = gap
        sheet.paste(fit_image(path, (panel_w, panel_h)), (x, y))
        draw.rectangle([x, y, x + panel_w, y + panel_h], outline="#9ca3af", width=1)
        draw.text((x, y + panel_h + 10), title, fill="#111827", font=font)
        draw.text((x, y + panel_h + 38), f"{row['category_cn']} / {row['template_id']}", fill="#4b5563", font=small)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def make_contact_sheet(rows: list[dict[str, Any]], out_path: Path) -> None:
    if not rows:
        return
    thumb_w, thumb_h = 260, 360
    cols = 4
    gap = 18
    caption_h = 66
    sheet_h = ((len(rows) + cols - 1) // cols) * (thumb_h + caption_h + gap) + gap
    sheet_w = cols * (thumb_w + gap) + gap
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#f3f4f6")
    draw = ImageDraw.Draw(sheet)
    font = safe_font(14)
    small = safe_font(12)
    for idx, row in enumerate(rows):
        r, c = divmod(idx, cols)
        x = gap + c * (thumb_w + gap)
        y = gap + r * (thumb_h + caption_h + gap)
        img = fit_image(Path(row["original_overlay"]), (thumb_w, thumb_h))
        sheet.paste(img, (x, y))
        draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline="#9ca3af", width=1)
        draw.text((x, y + thumb_h + 8), row["category_cn"], fill="#111827", font=font)
        draw.text((x, y + thumb_h + 30), row["template_id"][:30], fill="#4b5563", font=small)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def to_rel(path: str | Path, base: Path = OUTPUT_DIR) -> str:
    return os.path.relpath(Path(path).resolve(), base.resolve()).replace(os.sep, "/")


def write_gallery_html(rows: list[dict[str, Any]], out_path: Path) -> None:
    cards = []
    for row in rows:
        original = to_rel(row["original"])
        original_overlay = to_rel(row["original_overlay"])
        comparison = to_rel(row["comparison"])
        generated = row.get("generated_overlay")
        generated_rel = to_rel(generated) if generated else ""
        cards.append(
            f"""
      <article class="card">
        <header>
          <div><strong>{esc(row['category_cn'])}</strong><span>{esc(row['data_source'])} / {esc(row.get('layout') or '')}</span></div>
          <code>{esc(row['template_id'])}</code>
        </header>
        <div class="meta">文本块 {row['text_blocks']} · 结构块 {row['structure_blocks']} · 原始图片 {esc(row['image_path'])}</div>
        <div class="grid">
          <figure><img src="{esc(original)}" alt=""><figcaption>原始模板</figcaption></figure>
          <figure><img src="{esc(original_overlay)}" alt=""><figcaption>原始 order overlay</figcaption></figure>
          <figure><img src="{esc(comparison)}" alt=""><figcaption>原图 / VL6 对照</figcaption></figure>
        </div>
        <p class="links"><a href="{esc(original)}">打开原图</a><a href="{esc(original_overlay)}">打开原图 overlay</a>{f'<a href="{esc(generated_rel)}">打开 VL6 overlay</a>' if generated_rel else ''}</p>
      </article>"""
        )

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VL6 OmniDocBench 原始模板对照</title>
  <style>
    body{{margin:0;background:#f4f6f8;color:#17202a;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans CJK SC",sans-serif;}}
    header.top{{position:sticky;top:0;background:#fff;border-bottom:1px solid #d8dee7;padding:16px 28px;z-index:2;}}
    h1{{margin:0;font-size:22px;letter-spacing:0;}}
    header.top p{{margin:6px 0 0;color:#687381;font-size:13px;}}
    main{{padding:22px 28px 48px;display:grid;gap:18px;}}
    .card{{background:#fff;border:1px solid #d8dee7;border-radius:8px;padding:16px;box-shadow:0 12px 30px rgba(24,37,53,.08);}}
    .card header{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;}}
    .card strong{{display:block;font-size:18px;}}
    .card span,.meta{{color:#687381;font-size:13px;}}
    code{{font-size:12px;color:#334155;overflow-wrap:anywhere;}}
    .grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:14px;}}
    figure{{margin:0;min-width:0;}}
    img{{display:block;width:100%;height:460px;object-fit:contain;background:#f9fafb;border:1px solid #d8dee7;}}
    figcaption{{margin-top:6px;color:#4b5563;font-size:13px;}}
    .links{{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0 0;font-size:13px;}}
    a{{color:#0e5360;text-decoration:none;font-weight:700;}}
    @media(max-width:980px){{.grid{{grid-template-columns:1fr;}}img{{height:auto;max-height:720px;}}.card header{{display:block;}}}}
  </style>
</head>
<body>
  <header class="top">
    <h1>VL6 OmniDocBench 原始模板对照</h1>
    <p>共 {len(rows)} 个模板。蓝色编号为原始 OmniDocBench order；灰色框为表格/图片区等非 OCR 结构块。</p>
  </header>
  <main>{''.join(cards)}
  </main>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare-language", default="藏语")
    parser.add_argument("--no-proxy", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory = read_json(INVENTORY_JSON)
    omni = read_json(OMNI_JSON)
    generated_by_template = find_generated_by_template(args.compare_language)
    rows = []

    for row in inventory["selected"]:
        omni_item = omni[row["omni_index"]]
        image_name = row["image_path"]
        original = OUTPUT_DIR / "original_images" / image_name
        original_overlay = OUTPUT_DIR / "original_order_overlays" / f"{row['template_id']}_order.jpg"
        comparison = OUTPUT_DIR / "comparisons" / row["category_dir"] / f"{row['template_id']}_compare.jpg"
        generated = generated_by_template.get(row["template_id"], {})
        generated_overlay = Path(generated["overlay"]) if generated.get("overlay") else None

        download_original(image_name, original, use_proxy=not args.no_proxy)
        draw_original_overlay(original, omni_item, original_overlay)
        make_comparison(row, original_overlay, generated_overlay, comparison)

        rows.append(
            {
                **row,
                "original": str(original),
                "original_overlay": str(original_overlay),
                "comparison": str(comparison),
                "generated_overlay": str(generated_overlay) if generated_overlay else "",
                "generated_image": generated.get("image", ""),
                "generated_label": generated.get("label", ""),
                "compare_language": args.compare_language,
            }
        )

    write_json(OUTPUT_DIR / "template_origin_manifest.json", rows)
    make_contact_sheet(rows, OUTPUT_DIR / "VL6_omni_original_template_contact_sheet.jpg")
    write_gallery_html(rows, OUTPUT_DIR / "index.html")
    print(json.dumps({"templates": len(rows), "output": str(OUTPUT_DIR)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
