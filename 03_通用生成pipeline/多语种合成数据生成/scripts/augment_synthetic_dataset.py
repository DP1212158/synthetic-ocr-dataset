#!/usr/bin/env python3
"""Post-process a classified synthetic dataset with realistic image augmentation.

The script keeps the source version untouched, creates a new version directory,
copies the category structure, augments images, and rewrites labels/manifests so
that axis-aligned text boxes stay synchronized after mild geometric changes.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import random
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat


GEOMETRY_EPSILON = 0.01


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def stable_seed(base_seed: int, key: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{key}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in version_dir.iterdir()
        if p.is_dir()
        and len(p.name) >= 3
        and p.name[:2].isdigit()
        and (p / "metadata" / "render_manifest.json").exists()
        and (p / "metadata" / "html_manifest.json").exists()
    )


def copy_static_category_files(src_cat: Path, dst_cat: Path) -> None:
    for name in ["html", "images", "labels", "metadata", "reports"]:
        (dst_cat / name).mkdir(parents=True, exist_ok=True)
    for html in (src_cat / "html").glob("*"):
        if html.is_file():
            shutil.copy2(html, dst_cat / "html" / html.name)
    for meta in (src_cat / "metadata").glob("*"):
        if meta.is_file() and meta.name not in {"html_manifest.json", "render_manifest.json", "category_plan.json", "augmentation_manifest.json"}:
            shutil.copy2(meta, dst_cat / "metadata" / meta.name)
    if (src_cat / "README.md").exists():
        shutil.copy2(src_cat / "README.md", dst_cat / "README.md")


def copy_root_static_files(src_root: Path, dst_root: Path) -> None:
    (dst_root / "metadata").mkdir(parents=True, exist_ok=True)
    (dst_root / "reports").mkdir(parents=True, exist_ok=True)
    for meta in (src_root / "metadata").glob("*"):
        if meta.is_file() and meta.name not in {"html_manifest.json", "render_manifest.json", "category_plan.json", "augmentation_manifest.json"}:
            shutil.copy2(meta, dst_root / "metadata" / meta.name)
    text_source = src_root / "reports" / "text_source"
    if text_source.exists():
        shutil.copytree(text_source, dst_root / "reports" / "text_source", dirs_exist_ok=True)


def clamp(v: float, low: float, high: float) -> float:
    return max(low, min(high, v))


def label_boxes(label: dict[str, Any]) -> list[dict[str, float]]:
    boxes = []
    for block in label.get("blocks", []):
        c = block.get("coordinates") or {}
        boxes.append(
            {
                "x_min": float(c.get("x_min", 0.0)),
                "y_min": float(c.get("y_min", 0.0)),
                "x_max": float(c.get("x_max", 0.0)),
                "y_max": float(c.get("y_max", 0.0)),
            }
        )
    return boxes


def bounds_from_label(label: dict[str, Any], width: int, height: int) -> dict[str, float]:
    boxes = label_boxes(label)
    if not boxes:
        return {"x_min": 0.0, "y_min": 0.0, "x_max": float(width), "y_max": float(height)}
    return {
        "x_min": min(b["x_min"] for b in boxes),
        "y_min": min(b["y_min"] for b in boxes),
        "x_max": max(b["x_max"] for b in boxes),
        "y_max": max(b["y_max"] for b in boxes),
    }


def transform_box(box: dict[str, float], fn) -> dict[str, float]:
    points = [
        fn(box["x_min"], box["y_min"]),
        fn(box["x_max"], box["y_min"]),
        fn(box["x_max"], box["y_max"]),
        fn(box["x_min"], box["y_max"]),
    ]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return {"x_min": min(xs), "y_min": min(ys), "x_max": max(xs), "y_max": max(ys)}


def update_label_boxes(label: dict[str, Any], fn, width: int, height: int) -> None:
    for block in label.get("blocks", []):
        c = block.get("coordinates") or {}
        box = {
            "x_min": float(c.get("x_min", 0.0)),
            "y_min": float(c.get("y_min", 0.0)),
            "x_max": float(c.get("x_max", 0.0)),
            "y_max": float(c.get("y_max", 0.0)),
        }
        new_box = transform_box(box, fn)
        c["x_min"] = round(clamp(new_box["x_min"], 0.0, width - GEOMETRY_EPSILON), 2)
        c["y_min"] = round(clamp(new_box["y_min"], 0.0, height - GEOMETRY_EPSILON), 2)
        c["x_max"] = round(clamp(new_box["x_max"], 0.0, width), 2)
        c["y_max"] = round(clamp(new_box["y_max"], 0.0, height), 2)
        if c["x_max"] <= c["x_min"]:
            c["x_max"] = min(width, c["x_min"] + 1.0)
        if c["y_max"] <= c["y_min"]:
            c["y_max"] = min(height, c["y_min"] + 1.0)


def scale_geometry(img: Image.Image, label: dict[str, Any], scale: float) -> tuple[Image.Image, dict[str, Any]]:
    if abs(scale - 1.0) < 0.001:
        return img, {"scale": 1.0, "width": img.width, "height": img.height}
    new_w = max(1, int(round(img.width * scale)))
    new_h = max(1, int(round(img.height * scale)))
    img = img.resize((new_w, new_h), Image.Resampling.BICUBIC)
    update_label_boxes(label, lambda x, y: (x * scale, y * scale), new_w, new_h)
    return img, {"scale": round(scale, 5), "width": new_w, "height": new_h}


def rotate_geometry(img: Image.Image, label: dict[str, Any], angle_deg: float, fill: tuple[int, int, int]) -> tuple[Image.Image, dict[str, Any]]:
    if abs(angle_deg) < 0.01:
        return img, {"angle_degrees": 0.0, "width": img.width, "height": img.height}

    width, height = img.size
    theta = math.radians(angle_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    cx = (width - 1) / 2.0
    cy = (height - 1) / 2.0

    def raw_forward(x: float, y: float) -> tuple[float, float]:
        dx = x - cx
        dy = y - cy
        return cos_t * dx - sin_t * dy, sin_t * dx + cos_t * dy

    raw_corners = [raw_forward(x, y) for x, y in [(0, 0), (width, 0), (width, height), (0, height)]]
    min_x = min(p[0] for p in raw_corners)
    min_y = min(p[1] for p in raw_corners)
    max_x = max(p[0] for p in raw_corners)
    max_y = max(p[1] for p in raw_corners)
    out_w = max(1, int(math.ceil(max_x - min_x)))
    out_h = max(1, int(math.ceil(max_y - min_y)))
    tx = -min_x
    ty = -min_y

    a = cos_t
    b = -sin_t
    c = -cos_t * cx + sin_t * cy + tx
    d = sin_t
    e = cos_t
    f = -sin_t * cx - cos_t * cy + ty
    inv_a = e
    inv_b = -b
    inv_d = -d
    inv_e = a
    inv_c = -(inv_a * c + inv_b * f)
    inv_f = -(inv_d * c + inv_e * f)
    img = img.transform(
        (out_w, out_h),
        Image.Transform.AFFINE,
        (inv_a, inv_b, inv_c, inv_d, inv_e, inv_f),
        resample=Image.Resampling.BICUBIC,
        fillcolor=fill,
    )

    update_label_boxes(label, lambda x, y: (a * x + b * y + c, d * x + e * y + f), out_w, out_h)
    return img, {"angle_degrees": round(angle_deg, 4), "width": out_w, "height": out_h}


def translate_geometry(img: Image.Image, label: dict[str, Any], dx: int, dy: int, fill: tuple[int, int, int]) -> tuple[Image.Image, dict[str, Any]]:
    if dx == 0 and dy == 0:
        return img, {"dx": 0, "dy": 0, "width": img.width, "height": img.height}
    width, height = img.size
    shifted = Image.new("RGB", (width, height), fill)
    src_left = max(0, -dx)
    src_top = max(0, -dy)
    src_right = min(width, width - dx)
    src_bottom = min(height, height - dy)
    dst_left = max(0, dx)
    dst_top = max(0, dy)
    if src_right > src_left and src_bottom > src_top:
        shifted.paste(img.crop((src_left, src_top, src_right, src_bottom)), (dst_left, dst_top))
    update_label_boxes(label, lambda x, y: (x + dx, y + dy), width, height)
    return shifted, {"dx": dx, "dy": dy, "width": width, "height": height}


def safe_translate_offsets(label: dict[str, Any], width: int, height: int, rng: random.Random, max_shift: int) -> tuple[int, int]:
    bounds = bounds_from_label(label, width, height)
    min_dx = math.ceil(-bounds["x_min"] + 1)
    max_dx = math.floor(width - bounds["x_max"] - 1)
    min_dy = math.ceil(-bounds["y_min"] + 1)
    max_dy = math.floor(height - bounds["y_max"] - 1)
    lo_x = max(-max_shift, min_dx)
    hi_x = min(max_shift, max_dx)
    lo_y = max(-max_shift, min_dy)
    hi_y = min(max_shift, max_dy)
    dx = rng.randint(lo_x, hi_x) if lo_x <= hi_x else 0
    dy = rng.randint(lo_y, hi_y) if lo_y <= hi_y else 0
    return dx, dy


def safe_edge_crop(img: Image.Image, label: dict[str, Any], rng: random.Random, max_crop: int) -> tuple[Image.Image, dict[str, Any]]:
    width, height = img.size
    bounds = bounds_from_label(label, width, height)
    left_max = max(0, min(max_crop, int(math.floor(bounds["x_min"] - 1))))
    top_max = max(0, min(max_crop, int(math.floor(bounds["y_min"] - 1))))
    right_max = max(0, min(max_crop, int(math.floor(width - bounds["x_max"] - 1))))
    bottom_max = max(0, min(max_crop, int(math.floor(height - bounds["y_max"] - 1))))
    left = rng.randint(0, left_max) if left_max > 0 else 0
    top = rng.randint(0, top_max) if top_max > 0 else 0
    right = rng.randint(0, right_max) if right_max > 0 else 0
    bottom = rng.randint(0, bottom_max) if bottom_max > 0 else 0
    if left == top == right == bottom == 0:
        return img, {"left": 0, "top": 0, "right": 0, "bottom": 0, "width": width, "height": height}
    cropped = img.crop((left, top, width - right, height - bottom))
    new_w, new_h = cropped.size
    update_label_boxes(label, lambda x, y: (x - left, y - top), new_w, new_h)
    return cropped, {"left": left, "top": top, "right": right, "bottom": bottom, "width": new_w, "height": new_h}


def family_for(category: str, variant: int) -> str:
    common = ["clean_scan", "warm_paper", "printed_noise", "soft_copy", "shadow_photo", "compressed_scan"]
    families = {
        "newspaper_page": ["printed_noise", "warm_paper", "compressed_scan", "shadow_photo", "clean_scan", "aged_archive"],
        "historical_classic": ["aged_archive", "warm_paper", "low_contrast_archive", "soft_copy", "shadow_photo", "printed_noise"],
        "certificate_proof": ["clean_scan", "soft_copy", "warm_paper", "compressed_scan", "shadow_photo", "clean_scan"],
        "sign_poster_scene": ["shadow_photo", "compressed_scan", "warm_paper", "clean_scan", "printed_noise", "shadow_photo"],
        "handwritten_letter": ["warm_paper", "soft_copy", "aged_archive", "clean_scan", "shadow_photo", "compressed_scan"],
        "book_page": ["warm_paper", "clean_scan", "soft_copy", "printed_noise", "compressed_scan", "shadow_photo"],
        "textbook_page": ["clean_scan", "warm_paper", "compressed_scan", "soft_copy", "printed_noise", "shadow_photo"],
        "magazine_journal": ["clean_scan", "shadow_photo", "compressed_scan", "warm_paper", "printed_noise", "soft_copy"],
        "academic_paper": ["clean_scan", "soft_copy", "compressed_scan", "warm_paper", "printed_noise", "shadow_photo"],
        "notice_announcement": ["clean_scan", "warm_paper", "shadow_photo", "compressed_scan", "soft_copy", "printed_noise"],
        "complex_form": ["clean_scan", "compressed_scan", "soft_copy", "warm_paper", "printed_noise", "shadow_photo"],
        "exam_paper": ["clean_scan", "soft_copy", "warm_paper", "compressed_scan", "printed_noise", "shadow_photo"],
    }
    chosen = families.get(category, common)
    return chosen[(max(variant, 1) - 1) % len(chosen)]


def category_rotation_cap(category: str) -> float:
    caps = {
        "certificate_proof": 3.0,
        "complex_form": 3.0,
        "academic_paper": 3.0,
        "book_page": 4.5,
        "textbook_page": 4.5,
        "magazine_journal": 4.5,
        "exam_paper": 4.5,
        "notice_announcement": 4.5,
        "newspaper_page": 5.5,
        "historical_classic": 5.5,
        "handwritten_letter": 5.5,
        "sign_poster_scene": 8.0,
    }
    return caps.get(category, 4.5)


def rotation_range_for(category: str, profile: str) -> tuple[float, float]:
    if profile in {"delivery_balanced", "delivery_all_light"}:
        return (0.0, category_rotation_cap(category))
    if profile != "geo_rotation_trial":
        return (-0.65, 0.65)
    ranges = {
        "certificate_proof": (1.5, 2.5),
        "complex_form": (1.5, 2.5),
        "academic_paper": (1.5, 2.5),
        "book_page": (2.0, 4.0),
        "textbook_page": (2.0, 4.0),
        "magazine_journal": (2.0, 4.0),
        "exam_paper": (2.0, 4.0),
        "notice_announcement": (2.0, 4.0),
        "newspaper_page": (3.0, 5.0),
        "historical_classic": (3.0, 5.0),
        "handwritten_letter": (3.0, 5.0),
        "sign_poster_scene": (4.0, 8.0),
    }
    return ranges.get(category, (2.0, 4.0))


def sampled_rotation(category: str, variant: int, profile: str, rng: random.Random) -> float:
    if profile in {"delivery_balanced", "delivery_all_light"}:
        cap = category_rotation_cap(category)
        slot = ((max(variant, 1) - 1) % 6) + 1
        if slot == 1:
            mag = rng.uniform(0.05, min(1.0, cap))
        elif slot in {2, 3, 4}:
            mag = rng.uniform(min(1.5, cap), min(4.0, cap))
        elif slot == 5:
            low = min(max(cap * 0.68, 2.4), cap)
            mag = rng.uniform(low, cap)
        else:
            mag = rng.uniform(min(1.2, cap), min(3.2, cap))
        return mag if rng.random() < 0.5 else -mag
    if profile != "geo_rotation_trial":
        angle = rng.uniform(-0.65, 0.65)
        if abs(angle) < 0.08:
            angle = 0.12 if rng.random() < 0.5 else -0.12
        return angle
    low, high = rotation_range_for(category, profile)
    # Keep the trial visibly rotated without pushing every page to the upper bound.
    bucket = rng.random()
    if bucket < 0.40:
        mag = rng.uniform(min(low, 2.0), min(max(low, 2.0), high))
    elif bucket < 0.82:
        mag = rng.uniform(low, min(max(low, 4.0), high))
    else:
        mag = rng.uniform(min(max(low, 4.0), high), high)
    if mag <= 0:
        mag = rng.uniform(low, high)
    return mag if rng.random() < 0.5 else -mag


def directional_light_strength(category: str) -> tuple[float, float]:
    if category in {"certificate_proof", "complex_form", "academic_paper"}:
        return (0.08, 0.16)
    if category in {"sign_poster_scene", "notice_announcement", "handwritten_letter"}:
        return (0.16, 0.30)
    if category in {"newspaper_page", "historical_classic"}:
        return (0.12, 0.24)
    return (0.10, 0.22)


def directional_light_recipe(category: str, variant: int, profile: str, rng: random.Random) -> dict[str, Any]:
    if profile not in {"delivery_balanced", "delivery_all_light"}:
        return {"enabled": False}
    slot = ((max(variant, 1) - 1) % 6) + 1
    if profile == "delivery_balanced" and slot not in {4, 6}:
        return {"enabled": False}
    low, high = directional_light_strength(category)
    directions = ["top_left", "top_right", "left", "right", "diagonal_down", "diagonal_up"]
    shapes = ["soft_beam", "window_band", "elliptical_highlight", "edge_shadow"]
    if category in {"newspaper_page", "historical_classic"}:
        shapes = ["edge_shadow", "soft_beam", "window_band", "elliptical_highlight"]
    elif category in {"certificate_proof", "complex_form", "academic_paper"}:
        shapes = ["soft_beam", "edge_shadow", "elliptical_highlight", "window_band"]
    return {
        "enabled": True,
        "direction": directions[(slot + rng.randrange(len(directions))) % len(directions)],
        "shape": shapes[(slot + rng.randrange(len(shapes))) % len(shapes)],
        "strength": rng.uniform(low, high),
        "warmth": rng.uniform(0.015, 0.055),
        "softness": rng.uniform(0.18, 0.36),
    }


def base_recipe(category: str, variant: int, rng: random.Random, profile: str) -> dict[str, Any]:
    family = family_for(category, variant)
    recipe: dict[str, Any] = {
        "family": family,
        "brightness": rng.uniform(0.94, 1.07),
        "contrast": rng.uniform(0.92, 1.08),
        "saturation": rng.uniform(0.90, 1.04),
        "gamma": rng.uniform(0.94, 1.08),
        "temperature": rng.uniform(-0.035, 0.05),
        "paper_tint": [rng.randint(238, 255), rng.randint(236, 252), rng.randint(224, 246)],
        "paper_tint_alpha": rng.uniform(0.025, 0.08),
        "texture_strength": rng.uniform(0.012, 0.035),
        "noise_std": rng.uniform(1.2, 4.2),
        "speckle_amount": rng.uniform(0.0004, 0.0016),
        "blur_radius": rng.uniform(0.0, 0.34),
        "jpeg_quality": rng.randint(76, 91),
        "shadow_strength": rng.uniform(0.025, 0.075),
        "vignette_strength": rng.uniform(0.0, 0.045),
        "profile": profile,
        "angle_degrees": sampled_rotation(category, variant, profile, rng),
        "scale": rng.uniform(0.992, 1.008),
        "max_shift_px": rng.randint(2, 6),
        "max_edge_crop_px": rng.randint(3, 12),
        "directional_light": directional_light_recipe(category, variant, profile, rng),
    }

    if family == "clean_scan":
        recipe.update(
            paper_tint_alpha=rng.uniform(0.01, 0.035),
            texture_strength=rng.uniform(0.006, 0.018),
            noise_std=rng.uniform(0.8, 2.2),
            speckle_amount=rng.uniform(0.0001, 0.0006),
            blur_radius=rng.uniform(0.0, 0.18),
            shadow_strength=rng.uniform(0.0, 0.025),
            vignette_strength=rng.uniform(0.0, 0.012),
            jpeg_quality=rng.randint(86, 94),
        )
        if profile not in {"geo_rotation_trial", "delivery_balanced", "delivery_all_light"}:
            recipe["angle_degrees"] = rng.uniform(-0.35, 0.35)
    elif family == "warm_paper":
        recipe.update(
            paper_tint=[rng.randint(244, 255), rng.randint(235, 248), rng.randint(205, 232)],
            paper_tint_alpha=rng.uniform(0.06, 0.12),
            texture_strength=rng.uniform(0.025, 0.052),
            temperature=rng.uniform(0.035, 0.08),
            noise_std=rng.uniform(2.0, 4.8),
        )
    elif family == "printed_noise":
        recipe.update(
            contrast=rng.uniform(0.88, 1.02),
            texture_strength=rng.uniform(0.025, 0.045),
            noise_std=rng.uniform(3.2, 6.2),
            speckle_amount=rng.uniform(0.0012, 0.0030),
            jpeg_quality=rng.randint(70, 84),
        )
    elif family == "soft_copy":
        recipe.update(
            blur_radius=rng.uniform(0.18, 0.50),
            contrast=rng.uniform(0.88, 1.0),
            brightness=rng.uniform(0.97, 1.08),
            noise_std=rng.uniform(1.0, 2.8),
        )
    elif family == "shadow_photo":
        recipe.update(
            shadow_strength=rng.uniform(0.08, 0.18),
            vignette_strength=rng.uniform(0.025, 0.09),
            brightness=rng.uniform(0.90, 1.03),
            max_shift_px=rng.randint(4, 8),
        )
        if profile not in {"geo_rotation_trial", "delivery_balanced", "delivery_all_light"}:
            recipe["angle_degrees"] = rng.uniform(-0.85, 0.85)
    elif family == "compressed_scan":
        recipe.update(
            jpeg_quality=rng.randint(62, 78),
            noise_std=rng.uniform(2.0, 4.4),
            contrast=rng.uniform(0.90, 1.05),
            paper_tint_alpha=rng.uniform(0.025, 0.07),
        )
    elif family == "aged_archive":
        recipe.update(
            paper_tint=[rng.randint(232, 250), rng.randint(214, 237), rng.randint(174, 210)],
            paper_tint_alpha=rng.uniform(0.10, 0.18),
            texture_strength=rng.uniform(0.04, 0.075),
            contrast=rng.uniform(0.78, 0.95),
            brightness=rng.uniform(0.94, 1.04),
            temperature=rng.uniform(0.055, 0.11),
            speckle_amount=rng.uniform(0.0018, 0.0045),
            vignette_strength=rng.uniform(0.05, 0.12),
            blur_radius=rng.uniform(0.10, 0.40),
            jpeg_quality=rng.randint(70, 85),
        )
    elif family == "low_contrast_archive":
        recipe.update(
            paper_tint=[rng.randint(236, 251), rng.randint(224, 242), rng.randint(192, 222)],
            paper_tint_alpha=rng.uniform(0.08, 0.15),
            contrast=rng.uniform(0.74, 0.90),
            brightness=rng.uniform(0.96, 1.06),
            texture_strength=rng.uniform(0.035, 0.065),
            speckle_amount=rng.uniform(0.001, 0.0035),
        )

    if category == "certificate_proof":
        if profile not in {"geo_rotation_trial", "delivery_balanced", "delivery_all_light"}:
            recipe["angle_degrees"] = rng.uniform(-0.35, 0.35)
        recipe["max_edge_crop_px"] = min(recipe["max_edge_crop_px"], 7)
        recipe["noise_std"] = min(recipe["noise_std"], 3.0)
        recipe["speckle_amount"] = min(recipe["speckle_amount"], 0.001)
    elif category == "sign_poster_scene":
        recipe["shadow_strength"] = max(recipe["shadow_strength"], rng.uniform(0.08, 0.16))
        if profile not in {"geo_rotation_trial", "delivery_balanced", "delivery_all_light"}:
            recipe["angle_degrees"] = rng.uniform(-0.95, 0.95)
        recipe["jpeg_quality"] = min(recipe["jpeg_quality"], rng.randint(68, 82))
    elif category == "newspaper_page":
        recipe["speckle_amount"] = max(recipe["speckle_amount"], rng.uniform(0.0012, 0.0026))
        recipe["noise_std"] = max(recipe["noise_std"], rng.uniform(2.8, 5.0))
        recipe["contrast"] = min(recipe["contrast"], rng.uniform(0.86, 1.0))
    elif category == "historical_classic":
        recipe["paper_tint_alpha"] = max(recipe["paper_tint_alpha"], rng.uniform(0.09, 0.16))
        recipe["texture_strength"] = max(recipe["texture_strength"], rng.uniform(0.04, 0.07))
        recipe["vignette_strength"] = max(recipe["vignette_strength"], rng.uniform(0.04, 0.10))

    if profile not in {"geo_rotation_trial", "delivery_balanced", "delivery_all_light"} and abs(recipe["angle_degrees"]) < 0.08:
        recipe["angle_degrees"] = 0.12 if rng.random() < 0.5 else -0.12
    if profile in {"delivery_balanced", "delivery_all_light"}:
        recipe["scale"] = rng.uniform(0.985, 1.015)
        recipe["max_shift_px"] = rng.randint(3, 9)
        recipe["max_edge_crop_px"] = rng.randint(4, 14)
    return recipe


def apply_gamma(arr: np.ndarray, gamma: float) -> np.ndarray:
    if abs(gamma - 1.0) < 0.005:
        return arr
    normalized = np.clip(arr / 255.0, 0.0, 1.0)
    corrected = np.power(normalized, gamma) * 255.0
    return corrected


def apply_temperature(arr: np.ndarray, temperature: float) -> np.ndarray:
    if abs(temperature) < 0.001:
        return arr
    result = arr.copy()
    result[:, :, 0] *= 1.0 + temperature
    result[:, :, 2] *= 1.0 - temperature * 0.8
    return result


def apply_texture_and_light(img: Image.Image, recipe: dict[str, Any], rng: random.Random, np_rng: np.random.Generator) -> Image.Image:
    arr = np.asarray(img).astype(np.float32)
    h, w = arr.shape[:2]

    alpha = float(recipe["paper_tint_alpha"])
    tint = np.array(recipe["paper_tint"], dtype=np.float32).reshape(1, 1, 3)
    arr = arr * (1.0 - alpha) + tint * alpha
    arr = apply_temperature(arr, float(recipe["temperature"]))
    arr = apply_gamma(arr, float(recipe["gamma"]))

    if recipe["texture_strength"] > 0:
        small_w = max(2, w // 36)
        small_h = max(2, h // 36)
        texture_small = np_rng.normal(0.0, 1.0, (small_h, small_w)).astype(np.float32)
        texture_range = float(np.ptp(texture_small))
        texture_img = Image.fromarray(((texture_small - texture_small.min()) / max(texture_range, 1e-6) * 255).astype(np.uint8))
        texture_img = texture_img.resize((w, h), Image.Resampling.BICUBIC)
        texture = (np.asarray(texture_img).astype(np.float32) / 255.0 - 0.5) * 2.0
        arr *= 1.0 + texture[:, :, None] * float(recipe["texture_strength"])

    if recipe["shadow_strength"] > 0 or recipe["vignette_strength"] > 0:
        yy, xx = np.mgrid[0:h, 0:w]
        x_norm = (xx / max(w - 1, 1)) - 0.5
        y_norm = (yy / max(h - 1, 1)) - 0.5
        angle = rng.uniform(0, math.tau)
        directional = (math.cos(angle) * x_norm + math.sin(angle) * y_norm)
        directional = directional - directional.min()
        directional = directional / max(float(directional.max()), 1e-6)
        light = 1.0 - float(recipe["shadow_strength"]) * directional
        radius = np.sqrt(x_norm * x_norm + y_norm * y_norm)
        vignette = 1.0 - float(recipe["vignette_strength"]) * np.clip(radius / 0.72, 0.0, 1.0)
        arr *= (light * vignette)[:, :, None]

    if recipe["noise_std"] > 0:
        arr += np_rng.normal(0.0, float(recipe["noise_std"]), arr.shape).astype(np.float32)

    speckles = int(w * h * float(recipe["speckle_amount"]))
    if speckles > 0:
        ys = np_rng.integers(0, h, speckles)
        xs = np_rng.integers(0, w, speckles)
        dark = np_rng.random(speckles) < 0.72
        arr[ys[dark], xs[dark], :] *= np_rng.uniform(0.20, 0.70, dark.sum()).reshape(-1, 1)
        light = ~dark
        arr[ys[light], xs[light], :] = arr[ys[light], xs[light], :] * 0.55 + 255 * 0.45

    arr = np.clip(arr, 0, 255).astype(np.uint8)
    out = Image.fromarray(arr, "RGB")
    return out


def smoothstep(x: np.ndarray, edge0: float, edge1: float) -> np.ndarray:
    t = np.clip((x - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def apply_directional_light(img: Image.Image, recipe: dict[str, Any], rng: random.Random) -> Image.Image:
    light = recipe.get("directional_light") or {}
    if not light.get("enabled"):
        return img
    arr = np.asarray(img).astype(np.float32)
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    x = xx / max(w - 1, 1)
    y = yy / max(h - 1, 1)
    x0 = x - 0.5
    y0 = y - 0.5
    direction = light.get("direction", "top_left")
    shape = light.get("shape", "soft_beam")
    strength = float(light.get("strength", 0.16))
    softness = float(light.get("softness", 0.25))
    warmth = float(light.get("warmth", 0.03))

    vectors = {
        "top_left": (1.0, 0.9),
        "top_right": (-1.0, 0.9),
        "left": (1.0, 0.15),
        "right": (-1.0, 0.15),
        "diagonal_down": (0.75, 1.0),
        "diagonal_up": (-0.75, 1.0),
    }
    vx, vy = vectors.get(direction, (1.0, 0.9))
    norm = math.sqrt(vx * vx + vy * vy) or 1.0
    vx, vy = vx / norm, vy / norm
    along = vx * x0 + vy * y0
    across = -vy * x0 + vx * y0

    if shape == "window_band":
        center = rng.uniform(-0.14, 0.18)
        width = rng.uniform(0.10, 0.18)
        band = 1.0 - smoothstep(np.abs(across - center), width, width + softness)
        falloff = 0.76 + 0.24 * smoothstep(along, -0.55, 0.55)
        highlight = band * falloff
        shadow = (1.0 - band) * smoothstep(along, -0.45, 0.62) * 0.45
    elif shape == "elliptical_highlight":
        cx = rng.uniform(-0.18, 0.22)
        cy = rng.uniform(-0.22, 0.10)
        rx = rng.uniform(0.34, 0.55)
        ry = rng.uniform(0.24, 0.42)
        dist = ((x0 - cx) / rx) ** 2 + ((y0 - cy) / ry) ** 2
        highlight = 1.0 - smoothstep(dist, 0.45, 1.0 + softness)
        shadow = smoothstep(dist, 0.95, 1.7) * 0.32
    elif shape == "edge_shadow":
        side = smoothstep(along, -0.55, 0.58)
        highlight = side * 0.38
        shadow = (1.0 - side) * (0.70 + 0.30 * smoothstep(np.abs(across), 0.15, 0.60))
    else:
        beam_center = rng.uniform(-0.10, 0.12)
        beam = 1.0 - smoothstep(np.abs(across - beam_center), 0.18, 0.18 + softness)
        gradient = smoothstep(along, -0.58, 0.58)
        highlight = np.clip(0.42 * gradient + 0.75 * beam * gradient, 0.0, 1.0)
        shadow = (1.0 - gradient) * 0.48

    multiplier = 1.0 + strength * highlight - strength * 0.72 * shadow
    multiplier = np.clip(multiplier, 0.72, 1.24)
    arr *= multiplier[:, :, None]
    arr[:, :, 0] *= 1.0 + warmth * highlight
    arr[:, :, 2] *= 1.0 - warmth * highlight * 0.75
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def apply_visual_augmentation(img: Image.Image, recipe: dict[str, Any], rng: random.Random, np_rng: np.random.Generator) -> Image.Image:
    img = ImageEnhance.Brightness(img).enhance(float(recipe["brightness"]))
    img = ImageEnhance.Contrast(img).enhance(float(recipe["contrast"]))
    img = ImageEnhance.Color(img).enhance(float(recipe["saturation"]))
    img = apply_texture_and_light(img, recipe, rng, np_rng)
    img = apply_directional_light(img, recipe, rng)

    blur_radius = float(recipe["blur_radius"])
    if blur_radius > 0.03:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    quality = int(recipe["jpeg_quality"])
    if quality < 95:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, subsampling=1)
        buffer.seek(0)
        img = Image.open(buffer).convert("RGB")
    return img


def validate_label_bounds(label: dict[str, Any], width: int, height: int) -> list[dict[str, Any]]:
    issues = []
    for block in label.get("blocks", []):
        c = block.get("coordinates") or {}
        if c.get("x_min", 0) < -0.01 or c.get("y_min", 0) < -0.01 or c.get("x_max", 0) > width + 0.01 or c.get("y_max", 0) > height + 0.01:
            issues.append({"block_id": block.get("block_id"), "coordinates": c})
    return issues


def boxes_area(label: dict[str, Any]) -> float:
    area = 0.0
    for block in label.get("blocks", []):
        c = block.get("coordinates") or {}
        area += max(0.0, float(c.get("x_max", 0.0)) - float(c.get("x_min", 0.0))) * max(
            0.0, float(c.get("y_max", 0.0)) - float(c.get("y_min", 0.0))
        )
    return area


def image_quality_stats(img: Image.Image) -> dict[str, float]:
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    arr = np.asarray(gray).astype(np.float32)
    gx = np.diff(arr, axis=1)
    gy = np.diff(arr, axis=0)
    sharpness = float(np.mean(np.abs(gx))) + float(np.mean(np.abs(gy)))
    return {
        "mean_luma": round(float(stat.mean[0]), 3),
        "contrast_std": round(float(stat.stddev[0]), 3),
        "edge_sharpness": round(sharpness, 3),
    }


def remove_unsupported_placeholder_blocks(label: dict[str, Any]) -> int:
    blocks = label.get("blocks") or []
    kept = []
    removed = 0
    for block in blocks:
        text = str(block.get("block_content") or "").strip()
        if text and set(text) <= {"□"}:
            removed += 1
            continue
        kept.append(block)
    if removed:
        label["blocks"] = kept
        diagnostics = label.setdefault("attributes", {}).setdefault("diagnostics", {})
        diagnostics["removed_unsupported_placeholder_blocks"] = removed
    return removed


def augment_one(
    item: dict[str, Any],
    src_cat: Path,
    dst_cat: Path,
    base_seed: int,
    source_root: Path,
    output_root: Path,
    profile: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    document_id = item["document_id"]
    category = item.get("category") or "uncategorized"
    variant = int(item.get("variant") or 1)
    seed = stable_seed(base_seed, document_id)
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    recipe = base_recipe(category, variant, rng, profile)

    src_image = Path(item["image"])
    src_label = Path(item["label"])
    src_html = Path(item["html"])
    dst_image = dst_cat / "images" / src_image.name
    dst_label = dst_cat / "labels" / src_label.name
    dst_html = dst_cat / "html" / src_html.name

    img = Image.open(src_image).convert("RGB")
    label = read_json(src_label)
    source_label = read_json(src_label)
    source_size = {"width": img.width, "height": img.height}
    fill = tuple(int(v) for v in recipe["paper_tint"])

    geometry: dict[str, Any] = {"source_size": source_size}
    img, geometry["scale"] = scale_geometry(img, label, float(recipe["scale"]))
    img, geometry["rotation"] = rotate_geometry(img, label, float(recipe["angle_degrees"]), fill)
    dx, dy = safe_translate_offsets(label, img.width, img.height, rng, int(recipe["max_shift_px"]))
    img, geometry["translation"] = translate_geometry(img, label, dx, dy, fill)
    img, geometry["edge_crop"] = safe_edge_crop(img, label, rng, int(recipe["max_edge_crop_px"]))
    geometry["output_size_before_visual"] = {"width": img.width, "height": img.height}

    img = apply_visual_augmentation(img, recipe, rng, np_rng)
    output_size = {"width": img.width, "height": img.height}
    quality = image_quality_stats(img)
    source_area = max(boxes_area(source_label), 1.0)
    output_area = boxes_area(label)

    diagnostics = label.setdefault("attributes", {}).setdefault("diagnostics", {})
    diagnostics["augmentation"] = {
        "enabled": True,
        "source_version": source_root.name,
        "output_version": output_root.name,
        "seed": seed,
        "family": recipe["family"],
        "geometry": geometry,
        "output_size": output_size,
    }
    diagnostics["page_width"] = output_size["width"]
    diagnostics["page_height"] = output_size["height"]
    diagnostics["body_scroll_width"] = output_size["width"]
    diagnostics["body_scroll_height"] = output_size["height"]
    label["file_name"] = dst_image.name
    label["updated_at"] = datetime.now().replace(microsecond=0).isoformat()

    removed_placeholders = remove_unsupported_placeholder_blocks(label)
    bounds_issues = validate_label_bounds(label, output_size["width"], output_size["height"])
    if bounds_issues:
        raise RuntimeError(f"{document_id}: label out of bounds after augmentation: {bounds_issues[:3]}")

    dst_image.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst_image, format="PNG", optimize=True)
    write_json(dst_label, label)

    new_render_item = copy.deepcopy(item)
    new_render_item["image"] = str(dst_image)
    new_render_item["label"] = str(dst_label)
    new_render_item["html"] = str(dst_html)
    new_render_item["page_width"] = output_size["width"]
    new_render_item["page_height"] = output_size["height"]
    new_render_item["augmentation_family"] = recipe["family"]
    new_render_item["blocks"] = len(label.get("blocks", []))

    augmentation_item = {
        "document_id": document_id,
        "category": category,
        "variant": variant,
        "source_image": str(src_image),
        "source_label": str(src_label),
        "output_image": str(dst_image),
        "output_label": str(dst_label),
        "seed": seed,
        "recipe": {k: round(v, 5) if isinstance(v, float) else v for k, v in recipe.items()},
        "geometry": geometry,
        "source_size": source_size,
        "output_size": output_size,
        "box_area_growth_ratio": round(output_area / source_area, 5),
        "quality": quality,
        "removed_unsupported_placeholder_blocks": removed_placeholders,
    }
    return new_render_item, label, augmentation_item, {"image": dst_image, "label": dst_label}


def remap_html_manifest(html_items: list[dict[str, Any]], output_root: Path, source_root: Path) -> list[dict[str, Any]]:
    new_items = []
    for item in html_items:
        new_item = copy.deepcopy(item)
        new_item["augmentation_source_version"] = source_root.name
        new_item["augmentation_output_version"] = output_root.name
        new_item["created_at"] = item.get("created_at")
        new_items.append(new_item)
    return new_items


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


def make_source_augmented_contact_sheet(items: list[dict[str, Any]], out_path: Path) -> None:
    thumb_w, thumb_h = 190, 260
    pair_gap = 8
    cols = 3
    rows = math.ceil(len(items) / cols) or 1
    pad = 20
    caption_h = 58
    cell_w = thumb_w * 2 + pair_gap
    sheet = Image.new("RGB", (cols * (cell_w + pad) + pad, rows * (thumb_h + caption_h + pad) + pad), "#f1f3f5")
    draw = ImageDraw.Draw(sheet)
    font = safe_font(15)
    small = safe_font(13)
    for idx, item in enumerate(items):
        row, col = divmod(idx, cols)
        x = pad + col * (cell_w + pad)
        y = pad + row * (thumb_h + caption_h + pad)
        for offset, key, label in [(0, "source_image", "src"), (thumb_w + pair_gap, "output_image", "aug")]:
            img = Image.open(item[key]).convert("RGB")
            img.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            bg = Image.new("RGB", (thumb_w, thumb_h), "white")
            bg.paste(img, ((thumb_w - img.width) // 2, (thumb_h - img.height) // 2))
            sheet.paste(bg, (x + offset, y))
            draw.rectangle([x + offset, y, x + offset + thumb_w, y + thumb_h], outline="#9aa3ad", width=1)
            draw.text((x + offset + 6, y + 6), label, fill="#1f2937", font=small)
        angle = abs(float(item["recipe"].get("angle_degrees", 0.0)))
        light = item["recipe"].get("directional_light") or {}
        caption = f"{item['document_id']} angle={angle:.1f}"
        draw.text((x, y + thumb_h + 7), caption, fill="#1f2937", font=font)
        draw.text((x, y + thumb_h + 29), f"{item['recipe'].get('family')} light={bool(light.get('enabled'))}", fill="#4b5563", font=small)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def summarize_augmentation(all_augments: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, dict[str, Any]] = {}
    warning_items: list[dict[str, Any]] = []
    angles = []
    light_count = 0
    for item in all_augments:
        cat = item["category"]
        recipe = item["recipe"]
        light = recipe.get("directional_light") or {}
        angle = abs(float(recipe.get("angle_degrees", 0.0)))
        angles.append(angle)
        stat = by_category.setdefault(
            cat,
            {
                "total": 0,
                "families": {},
                "directional_light_count": 0,
                "angles": [],
                "max_box_area_growth_ratio": 0.0,
                "quality_warnings": 0,
            },
        )
        stat["total"] += 1
        family = recipe.get("family")
        stat["families"][family] = stat["families"].get(family, 0) + 1
        stat["angles"].append(round(angle, 4))
        if light.get("enabled"):
            stat["directional_light_count"] += 1
            light_count += 1
        growth = float(item.get("box_area_growth_ratio", 1.0))
        stat["max_box_area_growth_ratio"] = max(stat["max_box_area_growth_ratio"], round(growth, 4))
        quality = item.get("quality") or {}
        reasons = []
        if float(quality.get("mean_luma", 180.0)) < 115 or float(quality.get("mean_luma", 180.0)) > 246:
            reasons.append("mean_luma_out_of_range")
        if float(quality.get("contrast_std", 40.0)) < 13:
            reasons.append("low_contrast")
        if float(quality.get("edge_sharpness", 10.0)) < 2.2:
            reasons.append("low_edge_sharpness")
        if growth > 1.95:
            reasons.append("box_area_growth_high")
        if reasons:
            stat["quality_warnings"] += 1
            warning_items.append(
                {
                    "document_id": item["document_id"],
                    "category": cat,
                    "reasons": reasons,
                    "angle_abs": round(angle, 3),
                    "box_area_growth_ratio": round(growth, 4),
                    "quality": quality,
                }
            )
    for stat in by_category.values():
        stat["unique_family_count"] = len(stat["families"])
        stat["angle_min"] = round(min(stat["angles"]), 4)
        stat["angle_max"] = round(max(stat["angles"]), 4)
        stat["angle_mean"] = round(sum(stat["angles"]) / max(len(stat["angles"]), 1), 4)
    return {
        "total_images": len(all_augments),
        "directional_light_total": light_count,
        "angle_min": round(min(angles), 4) if angles else 0.0,
        "angle_max": round(max(angles), 4) if angles else 0.0,
        "angle_mean": round(sum(angles) / max(len(angles), 1), 4),
        "category_summary": by_category,
        "warning_items": warning_items,
        "warning_count": len(warning_items),
    }


def augment_dataset(source_root: Path, output_root: Path, seed: int, profile: str, force: bool = False) -> dict[str, Any]:
    if not source_root.exists():
        raise FileNotFoundError(source_root)
    if output_root.exists():
        if not force:
            raise FileExistsError(f"{output_root} already exists; use --force to replace it")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    copy_root_static_files(source_root, output_root)

    all_render: list[dict[str, Any]] = []
    all_html: list[dict[str, Any]] = []
    category_plan: list[dict[str, Any]] = []
    all_augments: list[dict[str, Any]] = []

    source_category_plan = read_json(source_root / "metadata" / "category_plan.json")
    plan_by_folder = {row.get("folder"): row for row in source_category_plan}

    for src_cat in category_dirs(source_root):
        dst_cat = output_root / src_cat.name
        copy_static_category_files(src_cat, dst_cat)

        src_render = read_json(src_cat / "metadata" / "render_manifest.json")
        src_html = read_json(src_cat / "metadata" / "html_manifest.json")
        dst_render: list[dict[str, Any]] = []
        dst_augments: list[dict[str, Any]] = []

        for item in src_render:
            new_render_item, _label, augmentation_item, _paths = augment_one(item, src_cat, dst_cat, seed, source_root, output_root, profile)
            dst_render.append(new_render_item)
            dst_augments.append(augmentation_item)

        dst_html = remap_html_manifest(src_html, output_root, source_root)
        write_json(dst_cat / "metadata" / "render_manifest.json", dst_render)
        write_json(dst_cat / "metadata" / "html_manifest.json", dst_html)
        plan_row = copy.deepcopy(plan_by_folder.get(src_cat.name))
        if not plan_row:
            first = src_html[0] if src_html else src_render[0]
            plan_row = {
                "category": first.get("category"),
                "category_cn": first.get("category_cn") or src_cat.name,
                "samples": len(dst_render),
                "folder": src_cat.name,
            }
        plan_row["samples"] = len(dst_render)
        write_json(dst_cat / "metadata" / "category_plan.json", [{k: v for k, v in plan_row.items() if k != "folder"}])
        write_json(dst_cat / "metadata" / "augmentation_manifest.json", dst_augments)

        all_render.extend(dst_render)
        all_html.extend(dst_html)
        category_plan.append(plan_row)
        all_augments.extend(dst_augments)

    write_json(output_root / "metadata" / "render_manifest.json", all_render)
    write_json(output_root / "metadata" / "html_manifest.json", all_html)
    write_json(output_root / "metadata" / "category_plan.json", category_plan)
    write_json(output_root / "metadata" / "augmentation_manifest.json", all_augments)

    families_by_category: dict[str, dict[str, int]] = {}
    for item in all_augments:
        category = item["category"]
        family = item["recipe"]["family"]
        families_by_category.setdefault(category, {})
        families_by_category[category][family] = families_by_category[category].get(family, 0) + 1

    augmentation_qa = summarize_augmentation(all_augments)
    summary = {
        "source_version_dir": str(source_root),
        "output_version_dir": str(output_root),
        "seed": seed,
        "total_images": len(all_render),
        "categories": len(category_plan),
        "augmentation_strength": "moderate_stable",
        "augmentation_profile": profile,
        "geometric_policy": "scale, category-aware rotation with expanded canvas, safe translation, safe edge crop",
        "visual_policy": "paper tint, texture, illumination, directional light, noise, speckles, blur, and JPEG recompression",
        "families_by_category": families_by_category,
        "augmentation_qa": augmentation_qa,
    }
    write_json(output_root / "metadata" / "augmentation_summary.json", summary)
    write_json(output_root / "reports" / "augmentation_quality_summary.json", augmentation_qa)
    write_augmentation_report(output_root, summary)
    write_readme(output_root, summary, category_plan)
    return summary


def write_augmentation_report(output_root: Path, summary: dict[str, Any]) -> None:
    rows = []
    for category, families in summary["families_by_category"].items():
        family_text = ", ".join(f"{name}:{count}" for name, count in sorted(families.items()))
        rows.append(f"| {category} | {family_text} |")
    qa = summary.get("augmentation_qa") or {}
    qa_rows = []
    for category, stat in (qa.get("category_summary") or {}).items():
        qa_rows.append(
            f"| {category} | {stat['unique_family_count']} | {stat['directional_light_count']} | "
            f"{stat['angle_min']} | {stat['angle_max']} | {stat['angle_mean']} | {stat['max_box_area_growth_ratio']} | {stat['quality_warnings']} |"
        )
    warning_rows = "\n".join(
        f"| {item['document_id']} | {item['category']} | {item['angle_abs']} | {item['box_area_growth_ratio']} | {', '.join(item['reasons'])} |"
        for item in qa.get("warning_items", [])
    )
    md = f"""# Image Augmentation Report

- 源版本：`{summary['source_version_dir']}`
- 输出版本：`{summary['output_version_dir']}`
- 图片数：{summary['total_images']}
- 类别数：{summary['categories']}
- 随机种子：{summary['seed']}
- 增强档位：{summary.get('augmentation_profile')}
- 增强强度：交付级平衡
- 几何策略：{summary['geometric_policy']}
- 视觉策略：{summary['visual_policy']}
- 方向光照样本数：{qa.get('directional_light_total', 0)}
- 增强专项风险样本：{qa.get('warning_count', 0)}

## 类别增强族分布

| 类别 | 增强族 |
|---|---|
{chr(10).join(rows)}

## 增强专项 QA

| 类别 | 增强族数 | 方向光照张数 | 最小角度 | 最大角度 | 平均角度 | 最大框面积膨胀 | 风险数 |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(qa_rows)}

## 风险样本

| 样本 | 类别 | 角度 | 框面积膨胀 | 原因 |
|---|---|---:|---:|---|
{warning_rows}

## 说明

本版本不做强透视、shear、纸张弯曲或复杂褶皱扭曲，优先保证矩形标签框与文本区域仍然贴合。
每张图片的完整增强参数见 `metadata/augmentation_manifest.json`。
"""
    (output_root / "reports" / "AUGMENTATION_REPORT.md").write_text(md, encoding="utf-8")


def write_readme(output_root: Path, summary: dict[str, Any], category_plan: list[dict[str, Any]]) -> None:
    cat_rows = "\n".join(f"- `{row['folder']}`：{row.get('category_cn') or row.get('category')}，{row['samples']} 张" for row in category_plan)
    readme = f"""# {output_root.name}

本目录是 `{Path(summary['source_version_dir']).name}` 的真实环境增强版，原始干净版未被覆盖。

## 内容

{cat_rows}

## 增强方式

- 强度：交付级平衡
- 几何：缩放、分类别旋转、安全平移、安全裁边，并同步更新标签坐标
- 视觉：纸张底色、纹理、扫描颗粒、轻微噪声、模糊、压缩、阴影、光照不均和方向光照模拟
- 不包含：shear、perspective、强透视、弯曲、褶皱扭曲

## 入口

- `metadata/augmentation_manifest.json`
- `metadata/augmentation_summary.json`
- `reports/augmentation_quality_summary.json`
- `reports/AUGMENTATION_REPORT.md`
- `reports/QA_REPORT.md`
- `reports/QA_DENSITY_REPORT.md`
- `reports/ACCEPTANCE_REPORT.md`
- `reports/contact_sheet.jpg`
- `reports/contact_sheet_with_boxes.jpg`
"""
    (output_root / "README.md").write_text(readme, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-version-dir", required=True)
    parser.add_argument("--output-version-dir", required=True)
    parser.add_argument("--seed", type=int, default=20260702)
    parser.add_argument(
        "--profile",
        choices=["moderate_avg", "geo_rotation_trial", "delivery_balanced", "delivery_all_light"],
        default="moderate_avg",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    summary = augment_dataset(Path(args.source_version_dir), Path(args.output_version_dir), args.seed, args.profile, args.force)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
