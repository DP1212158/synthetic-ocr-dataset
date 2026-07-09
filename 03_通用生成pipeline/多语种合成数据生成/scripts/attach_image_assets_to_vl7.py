#!/usr/bin/env python3
"""Attach real image assets to an existing rendered VL7 version.

This script intentionally does not change text, layout HTML structure, or
reading-order fields. It fills image-like placeholders in category HTML files,
writes a version-level image asset manifest, then the normal renderer can be run
to refresh images and labels with asset metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"Pillow is required: {exc}") from exc


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
PLACEHOLDER_LABELS = "image|photo|figure|photo_lead|image_figure|visual"
PLACEHOLDER_RE = re.compile(
    rf'(<(?P<tag>[a-zA-Z0-9]+)(?P<attrs>[^>]*\bdata-block-id="(?P<bid>[^"]+)"[^>]*\bdata-label="(?P<label>{PLACEHOLDER_LABELS})"[^>]*)>)'
    r"(?P<inner>.*?)"
    r"(</(?P=tag)>)",
    re.DOTALL | re.IGNORECASE,
)
ORDERABLE_MEDIA_OR_CAPTION_RE = re.compile(
    r'<(?P<tag>[a-zA-Z0-9]+)(?P<attrs>[^>]*\bdata-block-id="(?P<bid>[^"]+)"[^>]*\bdata-label="(?P<label>image|photo|figure|photo_lead|image_figure|visual|caption)"[^>]*)>',
    re.IGNORECASE,
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in version_dir.iterdir()
        if p.is_dir()
        and len(p.name) >= 3
        and p.name[:2].isdigit()
        and (p / "metadata" / "html_manifest.json").exists()
    )


def load_assets(asset_dir: Path) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for path in sorted(asset_dir.iterdir()):
        if path.suffix.lower() not in IMAGE_EXTS or not path.is_file():
            continue
        with Image.open(path) as img:
            width, height = img.size
        assets.append(
            {
                "asset_id": path.stem,
                "source_path": str(path),
                "file_name": path.name,
                "width": width,
                "height": height,
            }
        )
    if not assets:
        raise RuntimeError(f"no image assets found in {asset_dir}")
    return assets


def img_tag(rel_src: str) -> str:
    return (
        f'<img src="{html.escape(rel_src, quote=True)}" '
        'style="width:100%;height:100%;object-fit:cover;display:block;" '
        'alt="" data-asset-img="true" />'
    )


def clean_existing_asset_attrs(open_tag: str) -> str:
    for attr in ["data-asset-id", "data-asset-source", "data-asset-crop"]:
        open_tag = re.sub(rf'\s+{attr}="[^"]*"', "", open_tag)
    if 'data-is-text="false"' not in open_tag:
        open_tag = open_tag[:-1] + ' data-is-text="false">'
    return open_tag


def attach_assets_to_html(
    html_text: str,
    *,
    document_id: str,
    category: str,
    language_code: str,
    assets: list[dict[str, Any]],
    asset_dest_dir: Path,
    html_path: Path,
    manifest: list[dict[str, Any]],
    used_asset_ids: set[str],
    seed: int,
) -> tuple[str, int]:
    def select_asset(block_id: str, slot_index: int) -> dict[str, Any]:
        key = f"{seed}|{language_code}|{category}|{document_id}|{block_id}|{slot_index}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        start = int(digest[:12], 16) % len(assets)
        for offset in range(len(assets)):
            candidate = assets[(start + offset) % len(assets)]
            if candidate["asset_id"] not in used_asset_ids:
                used_asset_ids.add(candidate["asset_id"])
                return candidate
        candidate = assets[start]
        used_asset_ids.add(candidate["asset_id"])
        return candidate

    def repl(match: re.Match[str]) -> str:
        slot_index = repl.slot_index
        repl.slot_index += 1
        block_id = match.group("bid")
        asset = select_asset(block_id, slot_index)
        dst_asset = asset_dest_dir / asset["file_name"]
        if not dst_asset.exists():
            shutil.copy2(asset["source_path"], dst_asset)
        rel_src = Path("../../assets/random120-coco2014") / asset["file_name"]
        open_tag = clean_existing_asset_attrs(match.group(1))
        for attr, value in [
            ("data-asset-id", asset["asset_id"]),
            ("data-asset-source", "random120-coco2014"),
            ("data-asset-crop", "object-fit-cover"),
        ]:
            open_tag = open_tag[:-1] + f' {attr}="{html.escape(value, quote=True)}">'
        manifest.append(
            {
                "document_id": document_id,
                "category": category,
                "block_id": block_id,
                "block_label": match.group("label"),
                "asset_id": asset["asset_id"],
                "asset_source": "random120-coco2014",
                "asset_file": str(dst_asset),
                "asset_original_path": asset["source_path"],
                "asset_width": asset["width"],
                "asset_height": asset["height"],
                "asset_crop": "object-fit-cover",
                "asset_selection_key": f"{seed}|{language_code}|{category}|{document_id}|{block_id}|{slot_index}",
                "asset_selection_policy": "stable_hash_language_category_document_block",
                "html": str(html_path),
            }
        )
        return f"{open_tag}{img_tag(rel_src.as_posix())}{match.group(7)}"

    repl.slot_index = 0
    out = PLACEHOLDER_RE.sub(repl, html_text)
    return out, repl.slot_index


def attach_caption_targets(html_text: str) -> str:
    last_media_id: str | None = None
    replacements: list[tuple[int, int, str]] = []
    for match in ORDERABLE_MEDIA_OR_CAPTION_RE.finditer(html_text):
        label = match.group("label").lower()
        block_id = match.group("bid")
        tag = match.group(0)
        if label in {"image", "photo", "figure", "photo_lead", "image_figure", "visual"}:
            last_media_id = block_id
            continue
        if label == "caption" and last_media_id and "data-caption-of=" not in tag:
            patched = tag[:-1] + f' data-caption-of="{html.escape(last_media_id, quote=True)}">'
            replacements.append((match.start(), match.end(), patched))
    if not replacements:
        return html_text
    out_parts: list[str] = []
    cursor = 0
    for start, end, patched in replacements:
        out_parts.append(html_text[cursor:start])
        out_parts.append(patched)
        cursor = end
    out_parts.append(html_text[cursor:])
    return "".join(out_parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--image-assets-dir", default="04_共享图片资产/random120-coco2014")
    parser.add_argument("--seed", type=int, default=2026070802)
    args = parser.parse_args()

    version_dir = Path(args.version_dir)
    profile = read_json(Path(args.language_profile))
    language_code = str(profile.get("language_code") or profile.get("language_name") or version_dir.parent.parent.name)
    assets = load_assets(Path(args.image_assets_dir))
    asset_dest_dir = version_dir / "assets" / "random120-coco2014"
    asset_dest_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, Any]] = []
    used_asset_ids: set[str] = set()
    updated_docs = 0
    slots = 0
    for cat_dir in category_dirs(version_dir):
        html_manifest_path = cat_dir / "metadata" / "html_manifest.json"
        html_manifest = read_json(html_manifest_path)
        for item in html_manifest:
            html_path = cat_dir / "html" / f"{item['document_id']}.html"
            if not html_path.exists():
                continue
            text = html_path.read_text(encoding="utf-8")
            out, count = attach_assets_to_html(
                text,
                document_id=item["document_id"],
                category=item.get("category") or "unknown",
                language_code=language_code,
                assets=assets,
                asset_dest_dir=asset_dest_dir,
                html_path=html_path,
                manifest=manifest,
                used_asset_ids=used_asset_ids,
                seed=args.seed,
            )
            out = attach_caption_targets(out)
            if count:
                html_path.write_text(out, encoding="utf-8")
                item["image_assets_enabled"] = True
                item["image_asset_source"] = "random120-coco2014"
                updated_docs += 1
                slots += count
        write_json(html_manifest_path, html_manifest)

    summary = {
        "version_dir": str(version_dir),
        "image_slots": slots,
        "documents_with_images": updated_docs,
        "unique_assets_used": len({row["asset_id"] for row in manifest}),
        "asset_dir": str(asset_dest_dir),
        "pass": slots > 0 and updated_docs > 0,
    }
    write_json(version_dir / "metadata" / "image_asset_manifest.json", manifest)
    write_json(version_dir / "reports" / "image_asset_attach_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
