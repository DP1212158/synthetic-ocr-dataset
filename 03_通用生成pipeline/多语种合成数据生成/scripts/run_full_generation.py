#!/usr/bin/env python3
"""Generate full multilingual OCR datasets with template-declared reading flow.

Six horizontal/RTL languages go through the generic layout_templates_v2 pipeline.
Traditional Mongolian goes through its dedicated vertical pipeline
(``generate_mongolian_vertical_from_json_v3.py`` + ``mongolian_vertical_templates_v*``).

The version name (VL10, VL11, ...) is a runtime argument, not baked into the
file name, so this orchestrator is reused across versions.

Rendering is the bottleneck stage, so all per-category render jobs across every
language feed a single shared pool whose size adapts to the machine's CPU count
(bounded by ``--max-render-workers``). This keeps cores busy without spawning an
unbounded number of Chromium instances.
"""

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
        "records": "02_语种工程资源/藏语/01_文本数据获取/data/vl3_long_text_sources/records.jsonl",
        "profile": "02_语种工程资源/藏语/03_合成数据生成/configs/tibetan_language_profile.json",
    },
    {
        "id": "zhuang",
        "name": "壮语",
        "language_dir": "壮语",
        "records": "02_语种工程资源/壮语/01_文本数据获取/data/zhuang_expanded_text_pool/records.jsonl",
        "profile": "02_语种工程资源/壮语/03_合成数据生成/configs/zhuang_language_profile.json",
    },
    {
        "id": "korean",
        "name": "朝鲜语",
        "language_dir": "朝鲜语",
        "records": "02_语种工程资源/朝鲜语/01_文本数据获取/data/vl3_long_text_sources/records.jsonl",
        "profile": "02_语种工程资源/朝鲜语/03_合成数据生成/configs/korean_language_profile.json",
    },
    {
        "id": "bai",
        "name": "白语",
        "language_dir": "白语",
        "records": "02_语种工程资源/白语/01_文本数据获取/data/vl3_long_text_sources/records.jsonl",
        "profile": "02_语种工程资源/白语/03_合成数据生成/configs/bai_language_profile.json",
    },
    {
        "id": "uyghur",
        "name": "维吾尔语",
        "language_dir": "维吾尔语",
        "records": "02_语种工程资源/维吾尔语/01_文本数据获取/data/vl3_long_text_sources/records.jsonl",
        "profile": "02_语种工程资源/维吾尔语/03_合成数据生成/configs/uyghur_language_profile.json",
    },
    {
        "id": "kazakh",
        "name": "哈萨克语",
        "language_dir": "哈萨克语",
        "records": "02_语种工程资源/哈萨克语/01_文本数据获取/data/people_daily_kazakh/records.jsonl",
        "profile": "02_语种工程资源/哈萨克语/03_合成数据生成/configs/kazakh_language_profile.json",
    },
    {
        "id": "mongolian",
        "name": "蒙古语",
        "language_dir": "蒙古语",
        "records": "02_语种工程资源/蒙古语/01_文本数据获取/data/vl3_long_text_sources/records.jsonl",
        "profile": "02_语种工程资源/蒙古语/03_合成数据生成/configs/mongolian_language_profile.json",
        "vertical": True,
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


def run_soft(cmd: list[str], *, env: dict[str, str] | None = None) -> bool:
    """Run a best-effort step (QA). Never aborts the whole run on failure."""
    print("+ " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        print(f"! non-fatal step failed (exit {result.returncode}): {' '.join(cmd)}", flush=True)
        return False
    return True


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(p for p in version_dir.iterdir() if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit())


def mongolian_templates_root(template_version: str) -> Path:
    return (
        PROJECT_ROOT
        / "02_语种工程资源"
        / "蒙古语"
        / "03_合成数据生成"
        / "configs"
        / f"mongolian_vertical_templates_{template_version}"
    )


def generate_html(spec: dict[str, Any], args: argparse.Namespace, py: str, output_dir: Path, records: Path, profile: Path) -> None:
    """Stage 1: produce HTML for every category of one language."""
    seed_base = args.seed + sum(ord(ch) for ch in spec["id"])
    # Vertical-writing languages (traditional Mongolian) always use the dedicated
    # vertical pipeline + purpose-built templates, even under --schema v3. The
    # generic generate_layout CSS-column path produces extreme aspect ratios
    # (columns overflow into ~1:3 tall strips), so it must not handle Mongolian.
    if spec.get("vertical"):
        templates_root = mongolian_templates_root(args.mongolian_template_version)
        if not templates_root.exists():
            raise FileNotFoundError(templates_root)
        run(
            [
                py,
                str(SCRIPT_DIR / "generate_mongolian_vertical_from_json_v3.py"),
                "--text-jsonl",
                str(records),
                "--output-root",
                str(output_dir),
                "--language-profile",
                str(profile),
                "--templates-root",
                str(templates_root),
                "--min-records",
                "30",
                "--seed",
                str(seed_base),
                "--version-name",
                args.version_name,
                "--image-assets-dir",
                str(PROJECT_ROOT / "04_共享图片资产"),
            ]
        )
        return
    if getattr(args, "schema", "v2") == "v3":
        run(
            [
                py,
                str(SCRIPT_DIR / "generate_layout.py"),
                "--templates-dir",
                str(ENGINE_ROOT / "configs" / "layout_templates_v3"),
                "--text-jsonl",
                str(records),
                "--language-profile",
                str(profile),
                "--output-root",
                str(output_dir),
                "--version-name",
                args.version_name,
                "--seed",
                str(seed_base),
                "--zh-bank",
                str(PROJECT_ROOT / args.zh_bank),
                "--mix-ratio",
                str(args.mix_ratio),
            ]
        )
        return

    configs = ENGINE_ROOT / "configs" / "layout_templates_v2"
    jobs = [
        (SCRIPT_DIR / "generate_newspaper_from_json_templates.py", configs / "newspaper_layout_templates_v2.json", 1, 40),
        (SCRIPT_DIR / "generate_batch1_from_json_templates.py", configs / "batch1_layout_templates_v2.json", 2, 40),
        (SCRIPT_DIR / "generate_reading_pages_from_json_templates.py", configs / "reading_pages_layout_templates_v2.json", 5, 40),
        (SCRIPT_DIR / "generate_remaining_pages_from_json_templates.py", configs / "remaining_pages_layout_templates_v2.json", 8, 30),
    ]
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


def render_category(cat_dir: Path, node: str, py: str, profile: Path) -> dict[str, Any] | None:
    """Stage 2 (pooled): render one category with Chromium, then run basic QA."""
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
    run_soft(
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
    return read_json(qa_path) if qa_path.exists() else None


def generate_language(spec: dict[str, Any], args: argparse.Namespace, py: str, node: str, render_pool: ThreadPoolExecutor) -> dict[str, Any]:
    lang_dir = PROJECT_ROOT / "02_语种工程资源" / spec["language_dir"] / "03_合成数据生成"
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

    generate_html(spec, args, py, output_dir, records, profile)

    # Stage 2: render every category in parallel through the shared render pool.
    futures = {
        render_pool.submit(render_category, cat_dir, node, py, profile): cat_dir
        for cat_dir in category_dirs(output_dir)
    }
    qa_summaries = []
    for future in as_completed(futures):
        summary = future.result()
        if summary:
            qa_summaries.append(summary)

    # Stage 3: version-level QA (best-effort; reading-flow QA may legitimately
    # flag the vertical Mongolian path, which is under active fixing).
    flow_ok = run_soft([py, str(SCRIPT_DIR / "qa_reading_flow_v1.py"), "--version-dir", str(output_dir)])
    overlay_ok = run_soft([py, str(SCRIPT_DIR / "make_reading_order_contact_sheet.py"), "--version-dir", str(output_dir)])
    lang_ok = run_soft([
        py,
        str(SCRIPT_DIR / "qa_language_validity.py"),
        "--version-dir",
        str(output_dir),
        "--language-profile",
        str(profile),
        "--allow-mixed-cjk",
    ])
    flow_summary = read_json(output_dir / "reports" / "label_flow_audit.json") if (output_dir / "reports" / "label_flow_audit.json").exists() else {}
    overlay_summary = read_json(output_dir / "reports" / "reading_order_overlay_summary.json") if (output_dir / "reports" / "reading_order_overlay_summary.json").exists() else {}
    lang_summary = read_json(output_dir / "reports" / "language_validity_summary.json") if (output_dir / "reports" / "language_validity_summary.json").exists() else {}

    total_images = sum(int(item.get("total_images", 0)) for item in qa_summaries)
    passed_basic = sum(int(item.get("passed_basic", 0)) for item in qa_summaries)
    summary = {
        "language_id": spec["id"],
        "language_name": spec["name"],
        "pipeline": "mongolian_vertical" if spec.get("vertical") else "generic_horizontal",
        "version_dir": str(output_dir),
        "records": str(records),
        "profile": str(profile),
        "category_count": len(category_dirs(output_dir)),
        "total_images": total_images,
        "passed_basic": passed_basic,
        "flow_pass": bool(flow_summary.get("pass")) and flow_ok,
        "overlay_pass": bool(overlay_summary.get("pass")) and overlay_ok,
        "language_pass": bool(lang_summary.get("pass")) and lang_ok,
        "pass": total_images > 0
        and passed_basic == total_images
        and bool(flow_summary.get("pass"))
        and bool(overlay_summary.get("pass")),
    }
    manifest_name = f"{args.version_name.lower()}_manifest.json"
    write_json(output_dir / "metadata" / manifest_name, summary)
    print(f"== done {spec['name']}: images={total_images} basic={passed_basic} flow={summary['flow_pass']} overlay={summary['overlay_pass']} lang={summary['language_pass']}", flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-name", default="VL10")
    parser.add_argument("--languages", nargs="*", help="language ids or Chinese names; default all seven")
    parser.add_argument("--max-language-workers", type=int, default=4)
    parser.add_argument(
        "--max-render-workers",
        type=int,
        default=0,
        help="Chromium render pool size; 0 = auto = min(cpu_count, 24)",
    )
    parser.add_argument("--mongolian-template-version", default="v4", choices=["v3", "v4"])
    parser.add_argument("--schema", default="v2", choices=["v2", "v3"])
    parser.add_argument("--zh-bank", default="00_共享资源/中文语料/zh_content_bank.json")
    parser.add_argument("--mix-ratio", type=float, default=0.5)
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

    auto_render = min(os.cpu_count() or 8, 24)
    render_workers = args.max_render_workers if args.max_render_workers > 0 else auto_render
    lang_workers = max(1, min(args.max_language_workers, len(specs)))
    print(
        f"[run_full_generation] version={args.version_name} languages={[s['id'] for s in specs]} "
        f"lang_workers={lang_workers} render_workers={render_workers} cpu={os.cpu_count()}",
        flush=True,
    )

    summaries: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=render_workers) as render_pool:
        if lang_workers > 1 and len(specs) > 1:
            with ThreadPoolExecutor(max_workers=lang_workers) as lang_pool:
                futures = {lang_pool.submit(generate_language, spec, args, py, node, render_pool): spec for spec in specs}
                for future in as_completed(futures):
                    summaries.append(future.result())
        else:
            summaries = [generate_language(spec, args, py, node, render_pool) for spec in specs]

    summaries.sort(key=lambda item: [s["id"] for s in LANGUAGE_SPECS].index(item["language_id"]))
    out_dir = PROJECT_ROOT / "05_总报告与索引"
    write_json(out_dir / f"{args.version_name}_generation_summary.json", summaries)
    rows = [
        "| 语种 | 流程 | 图片数 | 基础通过 | Flow QA | Overlay | 目录 |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for item in summaries:
        rows.append(
            f"| {item['language_name']} | {item['pipeline']} | {item['total_images']} | {item['passed_basic']} | "
            f"{item['flow_pass']} | {item['overlay_pass']} | `{item['version_dir']}` |"
        )
    md = f"# {args.version_name} 全量生成报告\n\n" + "\n".join(rows) + "\n"
    (out_dir / f"{args.version_name}_generation_report.md").write_text(md, encoding="utf-8")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0 if all(item["pass"] for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
