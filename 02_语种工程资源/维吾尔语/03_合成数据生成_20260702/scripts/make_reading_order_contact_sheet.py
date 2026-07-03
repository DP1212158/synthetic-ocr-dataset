#!/usr/bin/env python3
"""Create reading-order overlays and a contact sheet for a delivery version."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(p for p in version_dir.iterdir() if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit())


def image_for_label(label_path: Path) -> Path:
    image_dir = label_path.parents[1] / "images"
    for suffix in [".png", ".jpg", ".jpeg", ".webp"]:
        candidate = image_dir / f"{label_path.stem}{suffix}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"no image found for {label_path}")


def draw_overlay(image_path: Path, label_path: Path, output_path: Path) -> dict[str, Any]:
    img = Image.open(image_path).convert("RGB")
    label = read_json(label_path)
    draw = ImageDraw.Draw(img)
    font = safe_font(max(18, int(min(img.size) * 0.035)))
    small = safe_font(max(14, int(min(img.size) * 0.018)))
    blocks = label.get("blocks", [])
    missing = []
    for block in blocks:
        order = block.get("reading_order")
        if order is None:
            missing.append(block.get("block_id"))
            continue
        c = block.get("coordinates") or {}
        x1 = float(c.get("x_min", 0))
        y1 = float(c.get("y_min", 0))
        x2 = float(c.get("x_max", 0))
        y2 = float(c.get("y_max", 0))
        is_text = block.get("is_text", True) is not False
        color = (32, 114, 220) if is_text else (230, 125, 35)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        label_text = str(order)
        tx, ty = x1 + 4, y1 + 4
        try:
            bbox = draw.textbbox((tx, ty), label_text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            tw, th = 28, 24
        draw.rounded_rectangle([tx, ty, tx + tw + 12, ty + th + 10], radius=6, fill=(255, 255, 255), outline=color, width=2)
        draw.text((tx + 6, ty + 4), label_text, fill=(0, 0, 0), font=font)
        role = block.get("reading_role") or block.get("block_label") or ""
        if role and (x2 - x1) > 90 and (y2 - y1) > 40:
            draw.text((tx + 6, ty + th + 14), str(role)[:18], fill=color, font=small)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=92)
    return {
        "document_id": label_path.stem,
        "image": str(output_path),
        "blocks": len(blocks),
        "missing_reading_order": missing,
    }


def make_contact_sheet(items: list[dict[str, Any]], out_path: Path) -> None:
    thumb_w = 260
    thumb_h = 360
    cols = 4
    rows = math.ceil(len(items) / cols)
    pad = 22
    caption_h = 54
    sheet = Image.new("RGB", (cols * (thumb_w + pad) + pad, rows * (thumb_h + caption_h + pad) + pad), "#f1f3f5")
    draw = ImageDraw.Draw(sheet)
    font = safe_font(16)
    for idx, item in enumerate(items):
        row, col = divmod(idx, cols)
        x = pad + col * (thumb_w + pad)
        y = pad + row * (thumb_h + caption_h + pad)
        img = Image.open(item["image"]).convert("RGB")
        img.thumbnail((thumb_w, thumb_h), Image.LANCZOS)
        bg = Image.new("RGB", (thumb_w, thumb_h), "white")
        bg.paste(img, ((thumb_w - img.width) // 2, (thumb_h - img.height) // 2))
        sheet.paste(bg, (x, y))
        draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline="#9aa3ad", width=1)
        draw.text((x, y + thumb_h + 8), item["document_id"][:32], fill="#111827", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    args = parser.parse_args()
    version_dir = Path(args.version_dir)
    items = []
    missing: list[dict[str, Any]] = []
    overlay_dir = version_dir / "reports" / "reading_order_overlays"
    for cat_dir in category_dirs(version_dir):
        for label_path in sorted((cat_dir / "labels").glob("*.json")):
            item = draw_overlay(
                image_for_label(label_path),
                label_path,
                overlay_dir / f"{label_path.stem}_reading_order.jpg",
            )
            item["category_dir"] = cat_dir.name
            items.append(item)
            if item["missing_reading_order"]:
                missing.append(item)
    make_contact_sheet(items, version_dir / "reports" / "contact_sheet_reading_order.jpg")
    summary = {
        "version_dir": str(version_dir),
        "total_images": len(items),
        "missing_reading_order_images": len(missing),
        "missing_reading_order_items": missing,
        "contact_sheet": str(version_dir / "reports" / "contact_sheet_reading_order.jpg"),
        "pass": len(items) == 72 and not missing,
    }
    (version_dir / "reports" / "reading_order_overlay_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
