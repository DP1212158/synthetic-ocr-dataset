#!/usr/bin/env python3
"""Run VL7 order-tree pilot for three high-risk reading-order categories."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = ENGINE_ROOT.parents[1]
DEFAULT_RUNTIME_ROOT = Path("/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies")
PILOT_CATEGORIES = {"01_报纸页", "07_杂志期刊页", "08_学术文献页"}


def runtime_python() -> str:
    candidate = DEFAULT_RUNTIME_ROOT / "python" / "bin" / "python3"
    return str(candidate) if candidate.exists() else sys.executable


def runtime_node() -> str:
    candidate = DEFAULT_RUNTIME_ROOT / "node" / "bin" / "node"
    return str(candidate) if candidate.exists() else "node"


def node_env() -> dict[str, str]:
    env = os.environ.copy()
    candidate = DEFAULT_RUNTIME_ROOT / "node" / "node_modules"
    if candidate.exists():
        env["NODE_PATH"] = str(candidate)
    return env


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def default_zhuang_paths() -> dict[str, Path]:
    lang_gen = PROJECT_ROOT / "02_语种工程资源" / "壮语" / "03_合成数据生成"
    return {
        "output_dir": lang_gen / "VL7_order_tree_pilot",
        "text_jsonl": PROJECT_ROOT / "02_语种工程资源" / "壮语" / "01_文本数据获取" / "data" / "zhuang_expanded_text_pool" / "records.jsonl",
        "language_profile": lang_gen / "configs" / "zhuang_language_profile.json",
    }


def render_and_qa(version_dir: Path, language_profile: Path, py: str, node: str) -> None:
    for cat_dir in sorted(p for p in version_dir.iterdir() if p.is_dir() and p.name[:2].isdigit()):
        if cat_dir.name not in PILOT_CATEGORIES:
            continue
        run(
            [
                node,
                str(SCRIPT_DIR / "render_table_dataset.mjs"),
                "--input-dir",
                str(cat_dir),
                "--language-profile",
                str(language_profile),
                "--auto-crop",
                "true",
                "--tight-crop",
                "true",
            ],
            env=node_env(),
        )
        run(
            [
                py,
                str(SCRIPT_DIR / "qa_table_dataset.py"),
                "--dataset-dir",
                str(cat_dir),
                "--language-profile",
                str(language_profile),
            ]
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    defaults = default_zhuang_paths()
    parser.add_argument("--language", default="壮语")
    parser.add_argument("--text-jsonl", default=str(defaults["text_jsonl"]))
    parser.add_argument("--language-profile", default=str(defaults["language_profile"]))
    parser.add_argument("--output-dir", default=str(defaults["output_dir"]))
    parser.add_argument("--version-name", default="VL7_order_tree_pilot")
    parser.add_argument("--seed", type=int, default=2026070701)
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()

    if args.language != "壮语":
        raise RuntimeError("current pilot entry defaults to 壮语 only; extend language paths after pilot acceptance")
    output_dir = Path(args.output_dir)
    text_jsonl = Path(args.text_jsonl)
    language_profile = Path(args.language_profile)
    if not text_jsonl.exists():
        raise FileNotFoundError(text_jsonl)
    if not language_profile.exists():
        raise FileNotFoundError(language_profile)
    if output_dir.exists() and not args.keep_existing:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "reports").mkdir(parents=True, exist_ok=True)

    py = runtime_python()
    node = runtime_node()
    configs = ENGINE_ROOT / "configs" / "layout_templates_v2"
    jobs = [
        (
            SCRIPT_DIR / "generate_newspaper_from_json_templates.py",
            configs / "newspaper_layout_templates_v2.json",
            1,
            args.seed + 1,
            40,
        ),
        (
            SCRIPT_DIR / "generate_reading_pages_from_json_templates.py",
            configs / "reading_pages_layout_templates_v2.json",
            5,
            args.seed + 5,
            40,
        ),
        (
            SCRIPT_DIR / "generate_remaining_pages_from_json_templates.py",
            configs / "remaining_pages_layout_templates_v2.json",
            8,
            args.seed + 8,
            30,
        ),
    ]
    for generator, templates, start_index, seed, min_records in jobs:
        run(
            [
                py,
                str(generator),
                "--text-jsonl",
                str(text_jsonl),
                "--templates-json",
                str(templates),
                "--output-root",
                str(output_dir),
                "--language-profile",
                str(language_profile),
                "--start-index",
                str(start_index),
                "--min-records",
                str(min_records),
                "--seed",
                str(seed),
                "--version-name",
                args.version_name,
            ]
        )

    for child in list(output_dir.iterdir()):
        if child.is_dir() and child.name[:2].isdigit() and child.name not in PILOT_CATEGORIES:
            shutil.rmtree(child)

    render_and_qa(output_dir, language_profile, py, node)
    run([py, str(SCRIPT_DIR / "qa_reading_flow_v1.py"), "--version-dir", str(output_dir)])
    run([py, str(SCRIPT_DIR / "make_reading_order_contact_sheet.py"), "--version-dir", str(output_dir)])
    manifest = {
        "version_name": args.version_name,
        "language": args.language,
        "output_dir": str(output_dir),
        "categories": sorted(PILOT_CATEGORIES),
        "text_jsonl": str(text_jsonl),
        "language_profile": str(language_profile),
    }
    write_json(output_dir / "metadata" / "vl7_order_tree_pilot_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

