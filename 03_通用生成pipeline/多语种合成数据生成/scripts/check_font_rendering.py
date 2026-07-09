#!/usr/bin/env python3
"""Create a font/direction smoke-check page before full generation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

from synthetic_text_utils import cleanse_text, load_language_profile

RUNTIME_ROOT = Path("/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def runtime_node() -> str:
    candidate = RUNTIME_ROOT / "node" / "bin" / "node"
    return str(candidate) if candidate.exists() else "node"


def node_env() -> dict[str, str]:
    env = os.environ.copy()
    candidate = RUNTIME_ROOT / "node" / "node_modules"
    if candidate.exists():
        env["NODE_PATH"] = str(candidate)
    return env


def sample_text(records_jsonl: Path, profile: dict[str, Any]) -> str:
    fallback = " ".join(profile.get("safe_title_fragments", [])) or profile["language_name"]
    if not records_jsonl.exists():
        return cleanse_text(fallback)
    for line in records_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        text = cleanse_text(str(row.get("text", "")).strip())
        if len(text) >= 20:
            return text[:260]
    return cleanse_text(fallback)


def text_crop_score(image_path: Path, label: dict[str, Any]) -> dict[str, Any]:
    img = Image.open(image_path).convert("L")
    width, height = img.size
    block_scores = []
    blank_blocks = []
    for block in label.get("blocks", []):
        if block.get("is_text", True) is False:
            continue
        if not str(block.get("block_content") or "").strip():
            continue
        c = block.get("coordinates") or {}
        x1 = max(0, int(float(c.get("x_min", 0))))
        y1 = max(0, int(float(c.get("y_min", 0))))
        x2 = min(width, int(float(c.get("x_max", 0))) + 1)
        y2 = min(height, int(float(c.get("y_max", 0))) + 1)
        if x2 <= x1 or y2 <= y1:
            blank_blocks.append(block.get("block_id"))
            continue
        crop = img.crop((x1, y1, x2, y2))
        stat = ImageStat.Stat(crop)
        stddev = float(stat.stddev[0])
        mean = float(stat.mean[0])
        pixels = list(crop.getdata())
        # Text ink is usually visible as a meaningful deviation from the local mean.
        ink_pixels = sum(1 for px in pixels if abs(px - mean) >= 18)
        ink_ratio = ink_pixels / max(len(pixels), 1)
        score = {"block_id": block.get("block_id"), "stddev": round(stddev, 3), "ink_ratio": round(ink_ratio, 4)}
        block_scores.append(score)
        if stddev < 2.0 and ink_ratio < 0.002:
            blank_blocks.append(block.get("block_id"))
    return {
        "text_blocks_checked": len(block_scores),
        "pixel_blank_text_blocks": len(blank_blocks),
        "pixel_blank_block_ids": blank_blocks,
        "block_pixel_scores": block_scores,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--records-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    profile = load_language_profile(Path(args.language_profile))
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    text = sample_text(Path(args.records_jsonl), profile)
    direction = profile.get("css_direction", "ltr")
    writing_mode = profile.get("css_writing_mode", "horizontal-tb")
    align = profile.get("css_text_align", "right" if direction == "rtl" else "left")
    font = profile.get("font_family", "sans-serif")
    html = f"""<!doctype html>
<html lang="{profile.get('html_lang', '')}" dir="{direction}">
<head><meta charset="utf-8"><style>
body{{margin:0;background:#e5e7eb;font-family:{font};}}
.page{{width:960px;min-height:620px;margin:0 auto;background:white;padding:54px;direction:{direction};writing-mode:{writing_mode};text-align:{align};font-family:{font};}}
.title{{font-size:44px;font-weight:800;line-height:1.6;border-bottom:2px solid #94a3b8;margin-bottom:24px;}}
.sample{{font-size:30px;line-height:1.75;}}
</style></head>
<body><main class="page">
<div class="title" data-block-id="font_check_title" data-label="document_title">{profile.get('language_name')}</div>
<div class="sample" data-block-id="font_check_sample" data-label="paragraph">{text}</div>
</main></body></html>"""
    (out / "html").mkdir(parents=True, exist_ok=True)
    html_path = out / "html" / "font_check.html"
    html_path.write_text(html, encoding="utf-8")
    manifest = [
        {
            "document_id": "font_check",
            "title": profile.get("language_name"),
            "category": "font_check",
            "variant": 1,
            "layout_name": "font_rendering_check",
            "template_type": "font_check",
            "generator": "font_rendering_check",
            "doc_no": "FONT-CHECK",
            "date": "2026-07-02",
            "page_width": 1068,
            "page_height": 728,
            "preserve_full_page": False,
            "tight_crop": True,
            "source_records": [],
        }
    ]
    write_json(out / "metadata" / "html_manifest.json", manifest)
    for name in ["images", "labels", "reports", "reports/overlays"]:
        (out / name).mkdir(parents=True, exist_ok=True)
    script_dir = Path(__file__).resolve().parent
    subprocess.run(
        [
            runtime_node(),
            str(script_dir / "render_table_dataset.mjs"),
            "--input-dir",
            str(out),
            "--language-profile",
            str(Path(args.language_profile)),
            "--auto-crop",
            "true",
            "--tight-crop",
            "true",
        ],
        check=True,
        env=node_env(),
    )
    label = read_json(out / "labels" / "font_check.json")
    blocks = label.get("blocks", [])
    empty_blocks = [b for b in blocks if not (b.get("block_content") or "").strip()]
    pixel_summary = text_crop_score(out / "images" / "font_check.png", label)
    pass_check = bool(blocks) and len(empty_blocks) == 0 and pixel_summary["pixel_blank_text_blocks"] == 0
    summary = {
        "language_code": profile.get("language_code"),
        "language_name": profile.get("language_name"),
        "font_family": font,
        "css_direction": direction,
        "css_writing_mode": writing_mode,
        "image": str(out / "images" / "font_check.png"),
        "label": str(out / "labels" / "font_check.json"),
        "blocks": len(blocks),
        "empty_blocks": len(empty_blocks),
        **pixel_summary,
        "pass": pass_check,
        "manual_check_required": writing_mode != "horizontal-tb" or direction == "rtl",
    }
    write_json(out / "font_check_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if pass_check else 2


if __name__ == "__main__":
    raise SystemExit(main())
