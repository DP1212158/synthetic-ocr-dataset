#!/usr/bin/env python3
"""Build the image manifest used by the static browsing demo."""

from __future__ import annotations

import json
import argparse
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = DEMO_ROOT / "data" / "image_manifest.json"

DEFAULT_VERSION = "VL7"

LANGUAGE_SPECS = [
    {
        "id": "tibetan",
        "name": "藏语",
        "language_dir": "藏语",
    },
    {
        "id": "zhuang",
        "name": "壮语",
        "language_dir": "壮语",
    },
    {
        "id": "korean",
        "name": "朝鲜语",
        "language_dir": "朝鲜语",
    },
    {
        "id": "bai",
        "name": "白语",
        "language_dir": "白语",
    },
    {
        "id": "uyghur",
        "name": "维吾尔语",
        "language_dir": "维吾尔语",
    },
    {
        "id": "kazakh",
        "name": "哈萨克语",
        "language_dir": "哈萨克语",
    },
    {
        "id": "mongolian",
        "name": "蒙古语",
        "language_dir": "蒙古语",
    },
]

CATEGORY_NAMES = [
    "报纸页",
    "证书证明",
    "考试卷",
    "标牌海报场景",
    "书籍页",
    "教科书页",
    "杂志期刊页",
    "学术文献页",
    "历史文档_古籍",
    "公告通知",
    "复杂表单登记页",
    "手写笔记信件",
]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def to_demo_relative(path: Path) -> str:
    return "../" + path.relative_to(PROJECT_ROOT).as_posix()


def category_sort_key(path: Path) -> tuple[int, str]:
    prefix = path.name.split("_", 1)[0]
    if prefix.isdigit():
        return (int(prefix), path.name)
    return (999, path.name)


def collect_category(category_dir: Path) -> dict:
    images_dir = category_dir / "images"
    labels_dir = category_dir / "labels"
    images = []
    if images_dir.exists():
        for image_path in sorted(images_dir.iterdir(), key=lambda p: p.name):
            if image_path.is_file() and image_path.suffix.lower() in IMAGE_EXTENSIONS:
                label_path = labels_dir / f"{image_path.stem}.json"
                images.append(
                    {
                        "filename": image_path.name,
                        "path": to_demo_relative(image_path),
                        "source_path": image_path.relative_to(PROJECT_ROOT).as_posix(),
                        "label_path": to_demo_relative(label_path) if label_path.exists() else None,
                        "label_source_path": label_path.relative_to(PROJECT_ROOT).as_posix()
                        if label_path.exists()
                        else None,
                    }
                )

    return {
        "id": category_dir.name,
        "name": category_dir.name.split("_", 1)[1] if "_" in category_dir.name else category_dir.name,
        "source_path": category_dir.relative_to(PROJECT_ROOT).as_posix(),
        "image_count": len(images),
        "images": images,
    }


def selected_languages(language_args: list[str] | None, version: str) -> list[dict]:
    selected = set(language_args or [])
    specs = [
        item
        for item in LANGUAGE_SPECS
        if not selected or item["id"] in selected or item["name"] in selected or item["language_dir"] in selected
    ]
    if not specs:
        raise RuntimeError(f"no languages selected: {sorted(selected)}")
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "version": version,
            "root": f"02_语种工程资源/{item['language_dir']}/03_合成数据生成/{version}",
        }
        for item in specs
    ]


def build_languages(version: str, language_args: list[str] | None = None) -> list[dict]:
    languages = []
    for language in selected_languages(language_args, version):
        version_root = PROJECT_ROOT / language["root"]
        categories = []
        if version_root.exists():
            category_dirs = [
                path
                for path in version_root.iterdir()
                if path.is_dir()
                and path.name[:2].isdigit()
                and (path / "images").exists()
                and any(name in path.name for name in CATEGORY_NAMES)
            ]
            categories = [collect_category(path) for path in sorted(category_dirs, key=category_sort_key)]

        total_images = sum(category["image_count"] for category in categories)
        language_entry = {
            **language,
            "source_path": language["root"],
            "exists": version_root.exists(),
            "category_count": len(categories),
            "image_count": total_images,
            "categories": categories,
        }
        languages.append(language_entry)
    return languages


VERSION_DIR_RE = __import__("re").compile(r"^VL\d+$")


def version_sort_key(version: str) -> int:
    digits = "".join(ch for ch in version if ch.isdigit())
    return int(digits) if digits else 0


def discover_versions(language_args: list[str] | None = None) -> list[str]:
    """Auto-discover clean version dirs (VL10, VL11, future VL12, ...) present on disk."""
    versions: set[str] = set()
    for item in LANGUAGE_SPECS:
        if language_args and not (
            item["id"] in language_args or item["name"] in language_args or item["language_dir"] in language_args
        ):
            continue
        base = PROJECT_ROOT / "02_语种工程资源" / item["language_dir"] / "03_合成数据生成"
        if base.exists():
            for path in base.iterdir():
                if path.is_dir() and VERSION_DIR_RE.match(path.name):
                    versions.add(path.name)
    return sorted(versions, key=version_sort_key, reverse=True)


def build_manifest(versions: list[str], language_args: list[str] | None = None) -> dict:
    # Keep only versions that actually contain images for the selected languages.
    datasets: dict[str, list[dict]] = {}
    kept: list[str] = []
    for version in versions:
        langs = build_languages(version, language_args)
        if any(language["image_count"] > 0 for language in langs):
            datasets[version] = langs
            kept.append(version)
    if not kept:  # fall back to whatever was requested, even if empty, so the UI still renders
        version = versions[0]
        datasets[version] = build_languages(version, language_args)
        kept = [version]

    default_version = kept[0]
    return {
        "title": "多语种合成图片浏览 Demo",
        "project_root": PROJECT_ROOT.as_posix(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "versions": kept,
        "default_version": default_version,
        "datasets": datasets,
        # Backward-compatible single-version view (default version).
        "languages": datasets[default_version],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="single version (compat); ignored if --versions given")
    parser.add_argument("--versions", nargs="*", help="explicit version list; default = auto-discover all VLxx on disk")
    parser.add_argument("--languages", nargs="*")
    args = parser.parse_args()

    if args.versions:
        versions = sorted(set(args.versions), key=version_sort_key, reverse=True)
    elif args.version:
        versions = [args.version]
    else:
        versions = discover_versions(args.languages) or [DEFAULT_VERSION]

    manifest = build_manifest(versions, args.languages)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
    MANIFEST_PATH.write_text(manifest_text + "\n", encoding="utf-8")
    # Also emit a JS global so the demo can load the manifest via <script src>,
    # which works through IDE port-forwarding proxies that mangle fetch()/XHR.
    js_path = MANIFEST_PATH.with_suffix(".js")
    js_path.write_text(f"window.__IMAGE_MANIFEST__ = {manifest_text};\n", encoding="utf-8")

    print(f"Wrote {MANIFEST_PATH}")
    print(f"Versions: {', '.join(manifest['versions'])} (default {manifest['default_version']})")
    for version in manifest["versions"]:
        langs = manifest["datasets"][version]
        image_count = sum(language["image_count"] for language in langs)
        print(f"# {version}: {len(langs)} languages, {image_count} images")
        for language in langs:
            print(
                f"- {language['name']} {version}: "
                f"{language['category_count']} categories, {language['image_count']} images"
            )


if __name__ == "__main__":
    main()
