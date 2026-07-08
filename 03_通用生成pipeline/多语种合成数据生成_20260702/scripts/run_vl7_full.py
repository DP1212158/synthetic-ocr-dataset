#!/usr/bin/env python3
"""Generate full VL7-style datasets with template-declared reading flow."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = ENGINE_ROOT.parents[1]
DEFAULT_RUNTIME_ROOT = Path("/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies")


LANGUAGE_SPECS = [
    {
        "id": "tibetan",
        "name": "藏语",
        "language_dir": "藏语",
        "records": "02_语种工程资源/藏语/01_文本数据获取_20260702/data/vl3_long_text_sources/records.jsonl",
        "profile": "02_语种工程资源/藏语/03_合成数据生成_20260702/configs/tibetan_language_profile.json",
    },
    {
        "id": "zhuang",
        "name": "壮语",
        "language_dir": "壮语",
        "records": "02_语种工程资源/壮语/01_文本数据获取_20260703/data/zhuang_expanded_text_pool_20260703/records.jsonl",
        "profile": "02_语种工程资源/壮语/03_合成数据生成_20260702/configs/zhuang_language_profile.json",
    },
    {
        "id": "korean",
        "name": "朝鲜语",
        "language_dir": "朝鲜语",
        "records": "02_语种工程资源/朝鲜语/01_文本数据获取_20260702/data/vl3_long_text_sources/records.jsonl",
        "profile": "02_语种工程资源/朝鲜语/03_合成数据生成_20260702/configs/korean_language_profile.json",
    },
    {
        "id": "bai",
        "name": "白语",
        "language_dir": "白语",
        "records": "02_语种工程资源/白语/01_文本数据获取_20260702/data/vl3_long_text_sources/records.jsonl",
        "profile": "02_语种工程资源/白语/03_合成数据生成_20260702/configs/bai_language_profile.json",
    },
    {
        "id": "uyghur",
        "name": "维吾尔语",
        "language_dir": "维吾尔语",
        "records": "02_语种工程资源/维吾尔语/01_文本数据获取_20260702/data/vl3_long_text_sources/records.jsonl",
        "profile": "02_语种工程资源/维吾尔语/03_合成数据生成_20260702/configs/uyghur_language_profile.json",
    },
    {
        "id": "kazakh",
        "name": "哈萨克语",
        "language_dir": "哈萨克语",
        "records": "02_语种工程资源/哈萨克语/01_文本数据获取_20260702/data/people_daily_kazakh_20260702/records.jsonl",
        "profile": "02_语种工程资源/哈萨克语/03_合成数据生成_20260702/configs/kazakh_language_profile.json",
    },
    {
        "id": "mongolian",
        "name": "蒙古语",
        "language_dir": "蒙古语",
        "records": "02_语种工程资源/蒙古语/01_文本数据获取_20260702/data/vl3_long_text_sources/records.jsonl",
        "profile": "02_语种工程资源/蒙古语/03_合成数据生成_20260702/configs/mongolian_language_profile.json",
    },
]


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
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(p for p in version_dir.iterdir() if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit())


def generate_language(spec: dict[str, str], args: argparse.Namespace, py: str, node: str) -> dict[str, Any]:
    lang_dir = PROJECT_ROOT / "02_语种工程资源" / spec["language_dir"] / "03_合成数据生成_20260702"
    output_dir = lang_dir / args.version_name
    records = PROJECT_ROOT / spec["records"]
    profile = PROJECT_ROOT / spec["profile"]
    if not records.exists():
        raise FileNotFoundError(records)
    if not profile.exists():
        raise FileNotFoundError(profile)
    if output_dir.exists() and not args.keep_existing:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "reports").mkdir(parents=True, exist_ok=True)
    configs = ENGINE_ROOT / "configs" / "layout_templates_v2"
    jobs = [
        (SCRIPT_DIR / "generate_newspaper_from_json_templates.py", configs / "newspaper_layout_templates_v2.json", 1, 40),
        (SCRIPT_DIR / "generate_batch1_from_json_templates.py", configs / "batch1_layout_templates_v2.json", 2, 40),
        (SCRIPT_DIR / "generate_reading_pages_from_json_templates.py", configs / "reading_pages_layout_templates_v2.json", 5, 40),
        (SCRIPT_DIR / "generate_remaining_pages_from_json_templates.py", configs / "remaining_pages_layout_templates_v2.json", 8, 30),
    ]
    seed_base = args.seed + sum(ord(ch) for ch in spec["id"])
    for idx, (generator, templates, start_index, min_records) in enumerate(jobs):
        run(
            [
                py,
                str(generator),
                "--text-jsonl",
                str(records),
                "--templates-json",
                str(templates),
                "--output-root",
                str(output_dir),
                "--language-profile",
                str(profile),
                "--start-index",
                str(start_index),
                "--min-records",
                str(min_records),
                "--seed",
                str(seed_base + idx * 100),
                "--version-name",
                args.version_name,
            ]
        )
    if args.attach_image_assets:
        run(
            [
                py,
                str(SCRIPT_DIR / "attach_image_assets_to_vl7.py"),
                "--version-dir",
                str(output_dir),
                "--language-profile",
                str(profile),
                "--image-assets-dir",
                str(PROJECT_ROOT / args.image_assets_dir),
                "--seed",
                str(args.image_seed + sum(ord(ch) for ch in spec["id"])),
            ]
        )
    qa_summaries = []
    for cat_dir in category_dirs(output_dir):
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
        )
        run(
            [
                py,
                str(SCRIPT_DIR / "qa_table_dataset.py"),
                "--dataset-dir",
                str(cat_dir),
                "--language-profile",
                str(profile),
            ]
        )
        qa_path = cat_dir / "reports" / "qa_summary.json"
        if qa_path.exists():
            qa_summaries.append(read_json(qa_path))
    run([py, str(SCRIPT_DIR / "qa_reading_flow_v1.py"), "--version-dir", str(output_dir)])
    run([py, str(SCRIPT_DIR / "make_reading_order_contact_sheet.py"), "--version-dir", str(output_dir)])
    flow_summary = read_json(output_dir / "reports" / "label_flow_audit.json")
    overlay_summary = read_json(output_dir / "reports" / "reading_order_overlay_summary.json")
    total_images = sum(int(item.get("total_images", 0)) for item in qa_summaries)
    passed_basic = sum(int(item.get("passed_basic", 0)) for item in qa_summaries)
    summary = {
        "language_id": spec["id"],
        "language_name": spec["name"],
        "version_dir": str(output_dir),
        "records": str(records),
        "profile": str(profile),
        "category_count": len(category_dirs(output_dir)),
        "total_images": total_images,
        "passed_basic": passed_basic,
        "flow_pass": bool(flow_summary.get("pass")),
        "overlay_pass": bool(overlay_summary.get("pass")),
        "pass": total_images == 72 and passed_basic == 72 and bool(flow_summary.get("pass")) and bool(overlay_summary.get("pass")),
    }
    manifest_name = f"{args.version_name.lower()}_manifest.json"
    write_json(output_dir / "metadata" / manifest_name, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-name", default="VL7")
    parser.add_argument("--languages", nargs="*", help="language ids or Chinese names; default all seven")
    parser.add_argument("--max-language-workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=2026070801)
    parser.add_argument("--keep-existing", action="store_true")
    parser.add_argument("--attach-image-assets", action="store_true")
    parser.add_argument("--image-assets-dir", default="04_共享图片资产/random120-coco2014")
    parser.add_argument("--image-seed", type=int, default=2026070802)
    args = parser.parse_args()
    selected = set(args.languages or [])
    specs = [
        item
        for item in LANGUAGE_SPECS
        if not selected or item["id"] in selected or item["name"] in selected or item["language_dir"] in selected
    ]
    if not specs:
        raise RuntimeError(f"no languages selected: {sorted(selected)}")
    py = runtime_python()
    node = runtime_node()
    if args.max_language_workers > 1 and len(specs) > 1:
        summaries = []
        with ThreadPoolExecutor(max_workers=args.max_language_workers) as executor:
            futures = {executor.submit(generate_language, spec, args, py, node): spec for spec in specs}
            for future in as_completed(futures):
                summaries.append(future.result())
    else:
        summaries = [generate_language(spec, args, py, node) for spec in specs]
    out_dir = PROJECT_ROOT / "05_总报告与索引"
    summary_name = f"{args.version_name}_generation_summary.json"
    report_name = f"{args.version_name}_generation_report.md"
    write_json(out_dir / summary_name, summaries)
    rows = [
        "| 语种 | 图片数 | 基础通过 | Flow QA | Overlay | 目录 |",
        "|---|---:|---:|---|---|---|",
    ]
    for item in summaries:
        rows.append(
            f"| {item['language_name']} | {item['total_images']} | {item['passed_basic']} | "
            f"{item['flow_pass']} | {item['overlay_pass']} | `{item['version_dir']}` |"
        )
    md = f"# {args.version_name} 全量生成报告\n\n" + "\n".join(rows) + "\n"
    (out_dir / report_name).write_text(md, encoding="utf-8")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0 if all(item["pass"] for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
