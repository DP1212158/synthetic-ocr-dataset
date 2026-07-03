#!/usr/bin/env python3
"""Run generate -> render -> QA -> density QA -> version rebuild for a category batch."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_RUNTIME_ROOT = Path("/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies")


def runtime_python() -> str:
    candidate = DEFAULT_RUNTIME_ROOT / "python" / "bin" / "python3"
    return str(candidate) if candidate.exists() else sys.executable


def runtime_node() -> str:
    candidate = DEFAULT_RUNTIME_ROOT / "node" / "bin" / "node"
    return str(candidate) if candidate.exists() else "node"


def node_path_env() -> dict[str, str]:
    env = os.environ.copy()
    candidate = DEFAULT_RUNTIME_ROOT / "node" / "node_modules"
    if candidate.exists():
        env["NODE_PATH"] = str(candidate)
    return env


def run(cmd: list[str], *, env: dict[str, str] | None = None, dry_run: bool = False) -> None:
    print("+ " + " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True, env=env)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def category_dirs_for_batch(version_dir: Path, start_index: int, templates_json: Path) -> list[Path]:
    spec = read_json(templates_json)
    count = len(spec.get("categories", []))
    if count == 0 and isinstance(spec.get("templates"), list):
        count = 1
    wanted = {f"{idx:02d}" for idx in range(start_index, start_index + count)}
    dirs = [
        p
        for p in version_dir.iterdir()
        if p.is_dir() and p.name[:2] in wanted and (p / "metadata" / "html_manifest.json").exists()
    ]
    return sorted(dirs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True)
    parser.add_argument("--generator-script", required=True)
    parser.add_argument("--templates-json", required=True)
    parser.add_argument("--text-jsonl", required=True)
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--start-index", type=int, required=True)
    parser.add_argument("--min-records", type=int, default=30)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--version-name")
    parser.add_argument("--auto-crop", default="true")
    parser.add_argument("--tight-crop", default="true")
    parser.add_argument("--crop-padding", default=None)
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--skip-density", action="store_true")
    parser.add_argument("--fail-on-density-warning", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    version_dir = Path(args.version_dir)
    generator_script = Path(args.generator_script)
    templates_json = Path(args.templates_json)
    py = runtime_python()
    node = runtime_node()

    if not args.skip_generate:
        generate_cmd = [
            py,
            str(generator_script),
            "--text-jsonl",
            str(Path(args.text_jsonl)),
            "--templates-json",
            str(templates_json),
            "--output-root",
            str(version_dir),
            "--language-profile",
            str(Path(args.language_profile)),
            "--start-index",
            str(args.start_index),
            "--min-records",
            str(args.min_records),
        ]
        if args.seed is not None:
            generate_cmd.extend(["--seed", str(args.seed)])
        if args.version_name:
            generate_cmd.extend(["--version-name", str(args.version_name)])
        run(generate_cmd, dry_run=args.dry_run)

    batch_dirs = category_dirs_for_batch(version_dir, args.start_index, templates_json)
    if not batch_dirs:
        raise RuntimeError(f"no category dirs found in {version_dir} for start index {args.start_index}")

    if not args.skip_render:
        for dataset_dir in batch_dirs:
            render_cmd = [
                    node,
                    str(SCRIPT_DIR / "render_table_dataset.mjs"),
                    "--input-dir",
                    str(dataset_dir),
                    "--language-profile",
                    str(Path(args.language_profile)),
                    "--auto-crop",
                    str(args.auto_crop),
                    "--tight-crop",
                    str(args.tight_crop),
            ]
            if args.crop_padding is not None:
                render_cmd.extend(["--crop-padding", str(args.crop_padding)])
            run(
                render_cmd,
                env=node_path_env(),
                dry_run=args.dry_run,
            )

    for dataset_dir in batch_dirs:
        run([py, str(SCRIPT_DIR / "qa_table_dataset.py"), "--dataset-dir", str(dataset_dir)], dry_run=args.dry_run)

    if not args.skip_density:
        density_cmd = [py, str(SCRIPT_DIR / "qa_layout_density.py"), "--dataset-dir", str(version_dir)]
        if args.fail_on_density_warning:
            density_cmd.append("--fail-on-warning")
        run(density_cmd, dry_run=args.dry_run)

    run([py, str(SCRIPT_DIR / "rebuild_version_index.py"), "--version-dir", str(version_dir)], dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
