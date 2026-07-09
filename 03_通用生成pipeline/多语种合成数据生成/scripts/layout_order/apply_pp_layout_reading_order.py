#!/usr/bin/env python3
"""Apply a PP-DocLayout assisted reading-order pass to VL labels.

The model is used as layout-region evidence, not as a replacement for the
synthetic labels. Each OCR block is assigned to the best PP region, then sorted
with a hybrid key:

  semantic group -> PP region rank -> inferred column -> in-region position

By default this script writes updated labels to a sibling output directory.
Use --in-place only after reviewing overlays.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
HEADER_LABELS = {"document_title", "document_subtitle", "metadata"}
FOOTER_LABELS = {"footer", "page_number"}
IMAGE_LABELS = {"image", "photo", "figure", "photo_lead", "image_figure"}
TABLE_LABELS = {"table_header", "table_cell_text", "table_cell_number"}
FORM_LABELS = {"field_label", "field_value", "option", "answer_area"}

REGION_ALIASES = {
    "title": "title",
    "doc_title": "title",
    "document_title": "title",
    "header": "header",
    "text": "text",
    "paragraph": "text",
    "plain text": "text",
    "abandon": "ignore",
    "figure": "figure",
    "image": "figure",
    "figure_title": "caption",
    "caption": "caption",
    "table": "table",
    "table_title": "table",
    "table_caption": "table",
    "formula": "formula",
    "footer": "footer",
    "reference": "reference",
    "algorithm": "text",
    "chart": "figure",
    "seal": "stamp",
    "stamp": "stamp",
}

REGION_RANK = {
    "header": 0,
    "title": 1,
    "text": 2,
    "caption": 2,
    "table": 3,
    "figure": 3,
    "formula": 3,
    "stamp": 4,
    "reference": 5,
    "footer": 6,
    "ignore": 7,
    "unknown": 8,
}


@dataclass
class Region:
    id: str
    label: str
    norm_label: str
    score: float
    box: tuple[float, float, float, float]
    column_index: int = 0
    region_rank: int = 99


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
    for suffix in IMAGE_SUFFIXES:
        candidate = image_dir / f"{label_path.stem}{suffix}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"no image found for {label_path}")


def center_box(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2, (y1 + y2) / 2


def block_box(block: dict[str, Any]) -> tuple[float, float, float, float]:
    c = block.get("coordinates") or {}
    return (
        float(c.get("x_min", 0)),
        float(c.get("y_min", 0)),
        float(c.get("x_max", 0)),
        float(c.get("y_max", 0)),
    )


def area(box: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = area((ix1, iy1, ix2, iy2))
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def containment(inner: tuple[float, float, float, float], outer: tuple[float, float, float, float]) -> float:
    ix1, iy1, ix2, iy2 = inner
    ox1, oy1, ox2, oy2 = outer
    inter = area((max(ix1, ox1), max(iy1, oy1), min(ix2, ox2), min(iy2, oy2)))
    denom = area(inner)
    return inter / denom if denom > 0 else 0.0


def point_inside(point: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    x, y = point
    x1, y1, x2, y2 = box
    return x1 <= x <= x2 and y1 <= y <= y2


def normalize_region_label(label: str) -> str:
    key = label.strip().lower().replace("_", " ")
    return REGION_ALIASES.get(key, REGION_ALIASES.get(key.replace(" ", "_"), key if key in REGION_RANK else "unknown"))


def load_regions(path: Path, min_score: float) -> list[Region]:
    payload = read_json(path)
    regions: list[Region] = []
    for idx, item in enumerate(payload.get("boxes", [])):
        score = float(item.get("score", 0.0) or 0.0)
        if score < min_score:
            continue
        coord = item.get("coordinate") or []
        if len(coord) < 4:
            continue
        box = tuple(float(v) for v in coord[:4])
        if area(box) <= 0:
            continue
        label = str(item.get("label") or "unknown")
        norm = normalize_region_label(label)
        regions.append(
            Region(
                id=str(item.get("id") or f"pp_{idx:03d}"),
                label=label,
                norm_label=norm,
                score=score,
                box=box,  # type: ignore[arg-type]
            )
        )
    return regions


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


def semantic_group(block: dict[str, Any], page_h: float) -> str:
    label = block.get("block_label") or ""
    cy = center_box(block_box(block))[1]
    is_text = block.get("is_text", True) is not False
    if not is_text:
        return "image" if label in IMAGE_LABELS else "non_text"
    if label in HEADER_LABELS and cy < page_h * 0.24:
        return "header"
    if label in FOOTER_LABELS or cy > page_h * 0.91:
        return "footer"
    if label in TABLE_LABELS:
        return "table"
    if label in FORM_LABELS:
        return "form"
    return "body"


def semantic_rank(group: str) -> int:
    return {
        "header": 0,
        "body": 1,
        "table": 2,
        "form": 2,
        "image": 3,
        "footer": 4,
        "non_text": 5,
    }.get(group, 5)


def assign_region_columns(regions: list[Region], page_w: float, policy: str) -> None:
    if not regions:
        return
    # Cluster regions by x center. This is deliberately simple and stable; it
    # gives us columns based on detected layout regions, not individual words.
    centers = sorted((center_box(r.box)[0], idx) for idx, r in enumerate(regions))
    threshold = max(70.0, page_w * 0.12)
    clusters: list[list[int]] = []
    for cx, idx in centers:
        if not clusters:
            clusters.append([idx])
            continue
        prev = clusters[-1]
        prev_mean = sum(center_box(regions[i].box)[0] for i in prev) / len(prev)
        if abs(cx - prev_mean) <= threshold:
            prev.append(idx)
        else:
            clusters.append([idx])
    if policy == "rtl":
        clusters = list(reversed(clusters))
    for col_idx, cluster in enumerate(clusters):
        for idx in cluster:
            regions[idx].column_index = col_idx
            base = REGION_RANK.get(regions[idx].norm_label, REGION_RANK["unknown"])
            cy = center_box(regions[idx].box)[1]
            regions[idx].region_rank = base * 1000 + col_idx * 100 + int(cy / 20)


def match_region(block: dict[str, Any], regions: list[Region]) -> tuple[Region | None, float]:
    if not regions:
        return None, 0.0
    box = block_box(block)
    center = center_box(box)
    best: tuple[Region | None, float] = (None, 0.0)
    for region in regions:
        score = max(iou(box, region.box), containment(box, region.box))
        if point_inside(center, region.box):
            score += 0.15
        if score > best[1]:
            best = (region, score)
    return best


def fallback_column(cx: float, page_w: float, policy: str) -> int:
    if page_w <= 0:
        return 0
    raw = int(cx / page_w * 4)
    if policy == "rtl":
        return 3 - raw
    return raw


def sort_blocks(label: dict[str, Any], regions: list[Region], profile: dict[str, Any] | None) -> dict[str, Any]:
    attrs = label.setdefault("attributes", {})
    diagnostics = attrs.get("diagnostics", {})
    crop = diagnostics.get("crop", {})
    page_w = float(crop.get("width") or diagnostics.get("page_width") or 1)
    page_h = float(crop.get("height") or diagnostics.get("page_height") or 1)
    policy = language_policy(profile)
    assign_region_columns(regions, page_w, policy)

    decorated = []
    for idx, block in enumerate(label.get("blocks", [])):
        box = block_box(block)
        cx, cy = center_box(box)
        group = semantic_group(block, page_h)
        region, match_score = match_region(block, regions)
        block_attrs = block.setdefault("attributes", {})
        if region and match_score >= 0.20:
            reading_region = region.norm_label
            region_rank = region.region_rank
            column_index = region.column_index
            flow_id = region.id
        else:
            reading_region = group
            region_rank = semantic_rank(group) * 1000 + int(cy / 20)
            column_index = fallback_column(cx, page_w, policy)
            flow_id = reading_region

        if policy == "vertical":
            in_region_key = (cx, cy, idx)
        elif policy == "rtl":
            in_region_key = (cy, -cx, idx)
        else:
            in_region_key = (cy, cx, idx)

        sort_key = (
            semantic_rank(group),
            region_rank,
            column_index,
            *in_region_key,
        )
        decorated.append((sort_key, block, group, reading_region, column_index, flow_id, match_score, region))

    decorated.sort(key=lambda item: item[0])
    for order, item in enumerate(decorated, 1):
        _, block, group, reading_region, column_index, flow_id, match_score, region = item
        block["reading_order"] = order
        block["reading_group"] = group
        block["reading_role"] = block.get("reading_role") or block.get("block_label") or "text"
        block["reading_order_confidence"] = "high" if region and match_score >= 0.35 else "medium"
        block["reading_region"] = reading_region
        block["reading_flow_id"] = flow_id
        block["reading_flow_rank"] = REGION_RANK.get(reading_region, REGION_RANK["unknown"])
        block["column_index"] = column_index
        block_attrs = block.setdefault("attributes", {})
        block_attrs["pp_layout_region_id"] = region.id if region else None
        block_attrs["pp_layout_label"] = region.label if region else None
        block_attrs["pp_layout_score"] = region.score if region else None
        block_attrs["pp_layout_match_score"] = round(match_score, 4)

    attrs["reading_order_policy"] = f"pp_doclayout_hybrid_{policy}_v1"
    attrs["pp_layout_region_count"] = len(regions)
    return label


def draw_overlay(image_path: Path, label: dict[str, Any], regions: list[Region], out_path: Path) -> None:
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = safe_font(max(18, int(min(img.size) * 0.032)))
    small = safe_font(max(13, int(min(img.size) * 0.016)))
    for region in regions:
        x1, y1, x2, y2 = region.box
        draw.rectangle([x1, y1, x2, y2], outline=(130, 80, 190), width=3)
        draw.text((x1 + 4, y1 + 4), f"{region.norm_label}:{region.column_index}", fill=(130, 80, 190), font=small)
    for block in label.get("blocks", []):
        order = block.get("reading_order")
        c = block.get("coordinates") or {}
        x1 = float(c.get("x_min", 0))
        y1 = float(c.get("y_min", 0))
        x2 = float(c.get("x_max", 0))
        y2 = float(c.get("y_max", 0))
        color = (18, 110, 210) if block.get("is_text", True) is not False else (230, 125, 35)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        text = str(order)
        bbox = draw.textbbox((x1 + 4, y1 + 4), text, font=font)
        draw.rounded_rectangle([x1 + 4, y1 + 4, bbox[2] + 12, bbox[3] + 10], radius=5, fill="white", outline=color, width=2)
        draw.text((x1 + 8, y1 + 6), text, fill="black", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)


def make_contact_sheet(items: list[dict[str, Any]], out_path: Path) -> None:
    thumb_w, thumb_h = 280, 380
    cols = 4
    rows = math.ceil(len(items) / cols)
    pad = 20
    caption_h = 48
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
        draw.text((x, y + thumb_h + 7), item["document_id"][:34], fill="#111827", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def output_label_path(input_label: Path, input_version: Path, output_version: Path) -> Path:
    return output_version / input_label.relative_to(input_version)


def copy_version_skeleton(input_version: Path, output_version: Path) -> None:
    for cat_dir in category_dirs(input_version):
        out_cat = output_version / cat_dir.name
        for sub in ("images", "html", "metadata", "reports"):
            src = cat_dir / sub
            dst = out_cat / sub
            if src.exists() and not dst.exists():
                shutil.copytree(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    parser.add_argument("--pp-cache-dir", help="Defaults to VERSION/reports/pp_doclayout")
    parser.add_argument("--language-profile")
    parser.add_argument("--output-version-dir", help="Default: VERSION_pp_order")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--min-region-score", type=float, default=0.25)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-copy-assets", action="store_true")
    args = parser.parse_args()

    version_dir = Path(args.version_dir)
    pp_cache_dir = Path(args.pp_cache_dir) if args.pp_cache_dir else version_dir / "reports" / "pp_doclayout"
    profile = read_json(Path(args.language_profile)) if args.language_profile else None

    if args.in_place:
        output_dir = version_dir
    else:
        output_dir = Path(args.output_version_dir) if args.output_version_dir else version_dir.with_name(f"{version_dir.name}_pp_order")
        output_dir.mkdir(parents=True, exist_ok=True)
        if not args.no_copy_assets:
            copy_version_skeleton(version_dir, output_dir)

    labels = []
    for cat_dir in category_dirs(version_dir):
        for label_path in sorted((cat_dir / "labels").glob("*.json")):
            labels.append((cat_dir.name, label_path))
    if args.limit:
        labels = labels[: args.limit]

    items: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    changed = 0
    for cat_name, label_path in labels:
        cache_path = pp_cache_dir / cat_name / f"{label_path.stem}.json"
        if not cache_path.exists():
            failures.append({"label": str(label_path), "error": f"missing PP cache: {cache_path}"})
            continue
        label = copy.deepcopy(read_json(label_path))
        regions = load_regions(cache_path, args.min_region_score)
        updated = sort_blocks(label, regions, profile)
        out_label = label_path if args.in_place else output_label_path(label_path, version_dir, output_dir)
        write_json(out_label, updated)
        image_path = image_for_label(label_path)
        overlay_path = output_dir / "reports" / "pp_layout_reading_order_overlays" / f"{label_path.stem}_pp_order.jpg"
        draw_overlay(image_path, updated, regions, overlay_path)
        items.append(
            {
                "category_dir": cat_name,
                "document_id": label_path.stem,
                "label": str(out_label),
                "overlay": str(overlay_path),
                "regions": len(regions),
                "blocks": len(updated.get("blocks", [])),
            }
        )
        changed += 1

    contact_sheet = output_dir / "reports" / "contact_sheet_pp_layout_reading_order.jpg"
    if items:
        make_contact_sheet(items, contact_sheet)
    summary = {
        "input_version_dir": str(version_dir),
        "output_version_dir": str(output_dir),
        "pp_cache_dir": str(pp_cache_dir),
        "labels_requested": len(labels),
        "labels_written": changed,
        "failed": len(failures),
        "failures": failures,
        "contact_sheet": str(contact_sheet) if items else None,
        "policy": f"pp_doclayout_hybrid_{language_policy(profile)}_v1",
        "pass": not failures and changed == len(labels),
    }
    write_json(output_dir / "reports" / "pp_layout_reading_order_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
