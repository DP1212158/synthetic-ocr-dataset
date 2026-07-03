#!/usr/bin/env python3
"""Finalize a clean synthetic dataset into the v4-standard delivery version.

This is a light wrapper around the proven Zhuang v4 finalization logic. It is
intended for follow-up language batches after a clean 12-category version has
already been generated and rendered.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ZHUANG_V4_SCRIPT = SCRIPT_DIR / "build_zhuang_v4_from_v2.py"


def load_v4_module() -> Any:
    spec = importlib.util.spec_from_file_location("delivery_v4_core", ZHUANG_V4_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {ZHUANG_V4_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["delivery_v4_core"] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_profile(core: Any, source_profile: Path, output_profile: Path, target_cjk_ratio: float) -> dict[str, Any]:
    profile = core.build_profile(source_profile, output_profile, target_cjk_ratio)
    profile["delivery_profile"] = "delivery_v4_standard"
    write_json(output_profile, profile)
    return profile


def write_readme(
    output_dir: Path,
    source_dir: Path,
    asset_dir: Path,
    mix_summary: dict[str, Any],
    image_summary: dict[str, Any],
    reading_summary: dict[str, Any],
    validity_summary: dict[str, Any],
    version_name: str,
) -> None:
    output_dir.joinpath("README.md").write_text(
        f"""# {version_name} delivery

本版本由 `finalize_delivery_version.py` 生成，采用壮语 v4 固化后的准交付标准。

## 来源

- clean 输入目录：`{source_dir}`
- 图片资产目录：`{asset_dir}`

## 核心策略

- 每类 3 张纯目标语、3 张混合中文。
- 混合样本中文比例控制为 10%-30%。
- 图片占位已替换为真实图片。
- 已应用 `delivery_all_light` 数据增强。
- 标签新增 `reading_order / reading_group / reading_role / reading_order_confidence`。

## QA

- 中文混合 QA：{mix_summary.get('pass')}
- 图片资产 QA：{image_summary.get('pass')}
- 阅读顺序 QA：{reading_summary.get('pass')}
- 语言有效性 QA：{validity_summary.get('pass')}
""",
        encoding="utf-8",
    )


def runtime_python() -> str:
    candidate = Path("/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3")
    return str(candidate) if candidate.exists() else sys.executable


def run_language_validity(version_dir: Path, profile_path: Path) -> dict[str, Any]:
    cmd = [
        runtime_python(),
        str(SCRIPT_DIR / "qa_language_validity.py"),
        "--version-dir",
        str(version_dir),
        "--language-profile",
        str(profile_path),
        "--allow-mixed-cjk",
        "--fail-on-warning",
    ]
    subprocess.run(cmd, check=True)
    return read_json(version_dir / "reports" / "language_validity_summary.json")


def run_visual_delivery(version_dir: Path, profile_path: Path) -> dict[str, Any]:
    cmd = [
        runtime_python(),
        str(SCRIPT_DIR / "qa_visual_delivery.py"),
        "--version-dir",
        str(version_dir),
        "--language-profile",
        str(profile_path),
    ]
    subprocess.run(cmd, check=True)
    return read_json(version_dir / "reports" / "visual_delivery_summary.json")


def run_reading_order_contact_sheet(version_dir: Path) -> dict[str, Any]:
    cmd = [
        runtime_python(),
        str(SCRIPT_DIR / "make_reading_order_contact_sheet.py"),
        "--version-dir",
        str(version_dir),
    ]
    subprocess.run(cmd, check=True)
    return read_json(version_dir / "reports" / "reading_order_overlay_summary.json")


def run_semantic_reading_order(version_dir: Path, profile_path: Path) -> dict[str, Any]:
    cmd = [
        runtime_python(),
        str(SCRIPT_DIR / "assign_semantic_reading_order.py"),
        "--version-dir",
        str(version_dir),
        "--language-profile",
        str(profile_path),
    ]
    subprocess.run(cmd, check=True)
    return read_json(version_dir / "reports" / "semantic_reading_order_summary.json")


def run_no_unwanted_text_box_qa(version_dir: Path) -> dict[str, Any]:
    cmd = [
        runtime_python(),
        str(SCRIPT_DIR / "qa_no_unwanted_text_boxes.py"),
        "--version-dir",
        str(version_dir),
    ]
    subprocess.run(cmd, check=True)
    return read_json(version_dir / "reports" / "no_unwanted_text_box_summary.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-version-dir", required=True, help="Clean rendered 12-category version directory.")
    parser.add_argument("--output-version-dir", required=True, help="Final delivery version directory.")
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--image-assets-dir")
    parser.add_argument("--version-name", default="v2")
    parser.add_argument("--delivery-profile", default="v4")
    parser.add_argument("--target-cjk-ratio", type=float, default=0.18)
    parser.add_argument("--seed", type=int, default=2026070401)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--keep-clean-source", action="store_true")
    args = parser.parse_args()

    core = load_v4_module()
    source_dir = Path(args.source_version_dir)
    output_dir = Path(args.output_version_dir)
    temp_dir = output_dir.parent / f"{output_dir.name}_clean_source"
    asset_dir = core.find_asset_dir(PROJECT_ROOT, Path(args.image_assets_dir) if args.image_assets_dir else None)
    assets = core.load_image_assets(asset_dir)

    if output_dir.exists():
        if not args.force:
            raise FileExistsError(f"{output_dir} exists; use --force")
        shutil.rmtree(output_dir)
    if temp_dir.exists():
        if not args.force:
            raise FileExistsError(f"{temp_dir} exists; use --force")
        shutil.rmtree(temp_dir)

    core.copy_clean_static(source_dir, temp_dir, force=True)
    profile_path = temp_dir / "metadata" / "delivery_language_profile.json"
    build_profile(core, Path(args.language_profile), profile_path, args.target_cjk_ratio)

    profile = read_json(profile_path)
    transform_stats = core.transform_htmls(temp_dir, assets, args.target_cjk_ratio, args.seed, profile)
    write_json(temp_dir / "metadata" / "language_mix_generation_summary.json", transform_stats)
    write_json(temp_dir / "metadata" / "decor_line_summary.json", transform_stats.get("decor_line_summary", {}))
    core.render_clean_version(temp_dir, profile_path)
    core.write_image_asset_report(temp_dir, core.image_asset_qa(temp_dir))

    core.augment_to_v3(temp_dir, output_dir, True)
    core.copy_v3_metadata(temp_dir, output_dir, profile_path)
    write_json(output_dir / "metadata" / "decor_line_summary.json", transform_stats.get("decor_line_summary", {}))

    core.run_final_qa(output_dir, profile_path)
    reading_summary = run_semantic_reading_order(output_dir, profile_path) if args.delivery_profile == "vl3" else core.apply_reading_order(output_dir, profile)
    mix_summary = core.language_mix_v4_qa(output_dir, profile)
    validity_summary = run_language_validity(output_dir, profile_path)
    image_summary = core.image_asset_qa(output_dir)
    core.write_image_asset_report(output_dir, image_summary)

    core.run_final_qa(output_dir, profile_path)
    reading_summary = run_semantic_reading_order(output_dir, profile_path) if args.delivery_profile == "vl3" else core.apply_reading_order(output_dir, profile)
    mix_summary = core.language_mix_v4_qa(output_dir, profile)
    validity_summary = run_language_validity(output_dir, profile_path)
    image_summary = core.image_asset_qa(output_dir)
    visual_summary = run_visual_delivery(output_dir, profile_path)
    text_box_summary = run_no_unwanted_text_box_qa(output_dir) if args.delivery_profile == "vl3" else {"pass": True}
    reading_overlay_summary = run_reading_order_contact_sheet(output_dir)
    write_readme(output_dir, source_dir, asset_dir, mix_summary, image_summary, reading_summary, validity_summary, args.version_name)

    failures = {
        "language_mix": mix_summary["pass"],
        "reading_order": reading_summary["pass"],
        "language_validity": validity_summary["pass"],
        "image_asset": image_summary["pass"],
        "visual_delivery": visual_summary["pass"],
        "no_unwanted_text_box": text_box_summary["pass"],
        "reading_order_overlay": reading_overlay_summary["pass"],
    }
    if not all(failures.values()):
        raise RuntimeError(f"delivery finalization failed: {failures}")
    if not args.keep_clean_source and temp_dir.exists():
        shutil.rmtree(temp_dir)

    result = {
        "output_version_dir": str(output_dir),
        "source_version_dir": str(source_dir),
        "image_assets": str(asset_dir),
        "checks": failures,
        "pass": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
