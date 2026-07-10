#!/usr/bin/env python3
"""Generate lightweight WebP thumbnails for the browsing demo.

Full-resolution PNGs (~750KB each) are slow to load, especially through an IDE
port-forward proxy. This script mirrors every dataset image under
``图片浏览_demo/previews/<same relative path>.webp`` at a capped resolution so the
grid can load small files, while the click-to-enlarge preview still uses the
original PNG.
"""

from __future__ import annotations

import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = Path(__file__).resolve().parents[1]
PREVIEW_ROOT = DEMO_ROOT / "previews"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VERSION_DIR_RE = re.compile(r"^VL\d+$")

MAX_DIM = 1100
QUALITY = 82


def source_images(versions: list[str] | None) -> list[Path]:
    base = PROJECT_ROOT / "02_语种工程资源"
    images: list[Path] = []
    for lang_dir in base.iterdir():
        gen_dir = lang_dir / "03_合成数据生成"
        if not gen_dir.is_dir():
            continue
        for version_dir in gen_dir.iterdir():
            if not (version_dir.is_dir() and VERSION_DIR_RE.match(version_dir.name)):
                continue
            if versions and version_dir.name not in versions:
                continue
            for img in version_dir.rglob("images/*"):
                if img.is_file() and img.suffix.lower() in IMAGE_EXTENSIONS:
                    images.append(img)
    return images


def thumb_path_for(image: Path) -> Path:
    rel = image.relative_to(PROJECT_ROOT)
    return PREVIEW_ROOT / rel.with_suffix(".webp")


def make_thumb(image: Path, force: bool) -> tuple[str, bool]:
    out = thumb_path_for(image)
    if out.exists() and not force and out.stat().st_mtime >= image.stat().st_mtime:
        return (str(out), False)
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image) as im:
        im = im.convert("RGB")
        im.thumbnail((MAX_DIM, MAX_DIM))
        im.save(out, "WEBP", quality=QUALITY, method=4)
    return (str(out), True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--versions", nargs="*", help="only these versions (default: all VLxx)")
    parser.add_argument("--force", action="store_true", help="regenerate even if up to date")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    images = source_images(args.versions)
    print(f"Found {len(images)} source images")

    generated = 0
    skipped = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(make_thumb, img, args.force): img for img in images}
        for future in as_completed(futures):
            try:
                _, created = future.result()
                if created:
                    generated += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"ERROR {futures[future]}: {exc}")

    print(f"Done. generated={generated} skipped={skipped} errors={errors}")
    print(f"Thumbnails root: {PREVIEW_ROOT}")


if __name__ == "__main__":
    main()
