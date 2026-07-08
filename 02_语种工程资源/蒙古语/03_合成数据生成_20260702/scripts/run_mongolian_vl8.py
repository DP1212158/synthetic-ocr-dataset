#!/usr/bin/env python3
"""Server entrypoint for rebuilding Mongolian vertical VL8."""

from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
GEN_ROOT = SCRIPT_DIR.parent
LANG_ROOT = GEN_ROOT.parent
PROJECT_ROOT = LANG_ROOT.parents[1]
DEFAULT_RUNTIME_ROOT = Path("/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies")


def runtime_python() -> str:
    env_python = os.environ.get("PYTHON")
    if env_python:
        return env_python
    candidate = DEFAULT_RUNTIME_ROOT / "python" / "bin" / "python3"
    return str(candidate) if candidate.exists() else sys.executable


def runtime_node() -> str:
    env_node = os.environ.get("NODE")
    if env_node:
        return env_node
    candidate = DEFAULT_RUNTIME_ROOT / "node" / "bin" / "node"
    return str(candidate) if candidate.exists() else "node"


def node_env() -> dict[str, str]:
    env = os.environ.copy()
    if "NODE_PATH" not in env:
        candidate = DEFAULT_RUNTIME_ROOT / "node" / "node_modules"
        if candidate.exists():
            env["NODE_PATH"] = str(candidate)
    return env


def run(cmd: list[str], *, env: dict[str, str] | None = None, dry_run: bool = False, timeout: int | None = None, allow_timeout: bool = False) -> bool:
    print("+ " + " ".join(cmd), flush=True)
    if dry_run:
        return True
    proc = subprocess.Popen(cmd, env=env, start_new_session=True)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        if allow_timeout:
            print(f"render timed out after {timeout}s; continuing if manifest is complete: {' '.join(cmd)}", flush=True)
            return False
        raise
    if proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return True


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def remove_generated_outputs(version_dir: Path) -> None:
    if not version_dir.exists():
        return
    for cat_dir in sorted(p for p in version_dir.iterdir() if p.is_dir() and p.name[:2].isdigit()):
        for name in ["images", "labels", "reports"]:
            shutil.rmtree(cat_dir / name, ignore_errors=True)
        for name in ["images", "labels", "reports"]:
            (cat_dir / name).mkdir(parents=True, exist_ok=True)
        render_manifest = cat_dir / "metadata" / "render_manifest.json"
        render_manifest.unlink(missing_ok=True)
    shutil.rmtree(version_dir / "reports", ignore_errors=True)
    (version_dir / "reports").mkdir(parents=True, exist_ok=True)
    (version_dir / "metadata" / "render_manifest.json").unlink(missing_ok=True)


def category_dirs(version_dir: Path, only_category: str | None = None) -> list[Path]:
    dirs = sorted(p for p in version_dir.iterdir() if p.is_dir() and p.name[:2].isdigit())
    if only_category:
        dirs = [p for p in dirs if p.name.startswith(only_category) or p.name == only_category]
    return dirs


def manifest_len(path: Path) -> int:
    try:
        data = read_json(path)
    except Exception:
        return 0
    return len(data) if isinstance(data, list) else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-name", default="VL8")
    parser.add_argument("--seed", type=int, default=2026070808)
    parser.add_argument("--min-records", type=int, default=40)
    parser.add_argument("--text-jsonl", default=str(LANG_ROOT / "01_文本数据获取_20260702/data/vl3_long_text_sources/records.jsonl"))
    parser.add_argument("--language-profile", default=str(GEN_ROOT / "configs/mongolian_language_profile.json"))
    parser.add_argument("--templates-root", default=str(GEN_ROOT / "configs/mongolian_vertical_templates_v4"))
    parser.add_argument("--output-root", default=str(GEN_ROOT / "VL8"))
    parser.add_argument("--only-category", help="Run only one category folder prefix/name, for example 01 or 01_报纸页.")
    parser.add_argument("--skip-build-templates", action="store_true")
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--skip-category-qa", action="store_true")
    parser.add_argument("--skip-version-qa", action="store_true")
    parser.add_argument("--clean-rendered", action="store_true", help="Remove images/labels/reports before rendering.")
    parser.add_argument("--render-timeout", type=int, default=0, help="Optional per-category render timeout in seconds. 0 disables timeout.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    py = runtime_python()
    node = runtime_node()
    version_dir = Path(args.output_root)
    templates_root = Path(args.templates_root)
    profile = Path(args.language_profile)

    if args.clean_rendered:
        remove_generated_outputs(version_dir)

    if not args.skip_build_templates:
        run([py, str(SCRIPT_DIR / "build_mongolian_vertical_templates_v4.py"), "--output-root", str(templates_root)], dry_run=args.dry_run)

    if not args.skip_generate:
        run(
            [
                py,
                str(SCRIPT_DIR / "generate_mongolian_vertical_from_json_v3.py"),
                "--text-jsonl",
                str(Path(args.text_jsonl)),
                "--output-root",
                str(version_dir),
                "--language-profile",
                str(profile),
                "--templates-root",
                str(templates_root),
                "--min-records",
                str(args.min_records),
                "--seed",
                str(args.seed),
                "--version-name",
                args.version_name,
            ],
            dry_run=args.dry_run,
        )

    cats = category_dirs(version_dir, args.only_category)
    if not cats:
        raise RuntimeError(f"no category dirs found under {version_dir}")

    if not args.skip_render:
        for cat_dir in cats:
            expected = manifest_len(cat_dir / "metadata" / "html_manifest.json")
            run(
                [
                    node,
                    str(SCRIPT_DIR / "render_table_dataset.mjs"),
                    "--input-dir",
                    str(cat_dir),
                    "--language-profile",
                    str(profile),
                    "--auto-crop",
                    "true",
                    "--tight-crop",
                    "true",
                ],
                env=node_env(),
                dry_run=args.dry_run,
                timeout=args.render_timeout or None,
                allow_timeout=bool(args.render_timeout),
            )
            rendered = manifest_len(cat_dir / "metadata" / "render_manifest.json")
            if not args.dry_run and rendered != expected:
                raise RuntimeError(f"render incomplete for {cat_dir}: {rendered}/{expected}")

    if not args.skip_category_qa:
        for cat_dir in cats:
            run([py, str(SCRIPT_DIR / "qa_table_dataset.py"), "--dataset-dir", str(cat_dir), "--language-profile", str(profile)], dry_run=args.dry_run)

    if not args.skip_version_qa and not args.only_category:
        run([py, str(SCRIPT_DIR / "rebuild_version_index.py"), "--version-dir", str(version_dir)], dry_run=args.dry_run)
        run([py, str(SCRIPT_DIR / "qa_layout_density.py"), "--dataset-dir", str(version_dir)], dry_run=args.dry_run)
        run(
            [
                py,
                str(SCRIPT_DIR / "qa_version_acceptance.py"),
                "--version-dir",
                str(version_dir),
                "--language-profile",
                str(profile),
                "--max-density-warnings",
                "0",
            ],
            dry_run=args.dry_run,
        )
        run([py, str(SCRIPT_DIR / "qa_reading_flow_v1.py"), "--version-dir", str(version_dir)], dry_run=args.dry_run)
        run([py, str(SCRIPT_DIR / "make_reading_order_contact_sheet.py"), "--version-dir", str(version_dir)], dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
