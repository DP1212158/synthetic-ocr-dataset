#!/usr/bin/env python3
"""Run the multilingual synthetic-data pipeline from language_jobs.json."""

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
RUNTIME_ROOT = Path("/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies")


def runtime_python() -> str:
    candidate = RUNTIME_ROOT / "python" / "bin" / "python3"
    return str(candidate) if candidate.exists() else sys.executable


def runtime_node() -> str:
    candidate = RUNTIME_ROOT / "node" / "bin" / "node"
    return str(candidate) if candidate.exists() else "node"


def node_env() -> dict[str, str]:
    env = os.environ.copy()
    candidate = RUNTIME_ROOT / "node" / "node_modules"
    if candidate.exists():
        env["NODE_PATH"] = str(candidate)
    return env


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, allow_fail: bool = False) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(proc.stdout, end="", flush=True)
    if proc.returncode and not allow_fail:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout)
    return proc


def proxy_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("http_proxy", "http://agent.baidu.com:8891")
    env.setdefault("https_proxy", "http://agent.baidu.com:8891")
    env.setdefault("no_proxy", "baidu.com,baidubce.com,bj.bcebos.com,bfsu.edu.cn,tsinghua.edu.cn")
    return env


BUILTIN_LANGUAGE_JOBS: dict[str, dict[str, Any]] = {
    "壮语": {
        "key": "zhuang",
        "language_dir": "壮语",
        "language_code": "za",
        "language_name": "壮语",
        "script_note": "现代标准壮文 Vahcuengh，拉丁字母拼写",
        "html_lang": "za",
        "script_regex": "[A-Za-z]",
        "cleanup_profile": "latin_zhuang",
        "min_script_ratio": 0.45,
        "min_span_words": 2,
        "writing_direction": "ltr",
        "css_direction": "ltr",
        "css_writing_mode": "horizontal-tb",
        "css_text_align": "left",
        "font_family": "\"Local Arial\", \"Local Arial Unicode\", Arial, Helvetica, sans-serif",
        "source_type": "vl3_long_text",
        "safe_title_fragments": ["Vahcuengh Sawcuengh", "Bouxcuengh Gijbon", "Gvangjsih Bouxcuengh", "Sawbon Canghva"],
    },
    "藏语": {
        "key": "tibetan",
        "language_dir": "藏语",
        "language_code": "bo",
        "language_name": "藏语",
        "script_note": "藏文字母，横排从左到右",
        "html_lang": "bo",
        "script_regex": "[\\u0f00-\\u0fff]",
        "cleanup_profile": "tibetan",
        "min_script_ratio": 0.35,
        "min_span_words": 1,
        "writing_direction": "ltr",
        "css_direction": "ltr",
        "css_writing_mode": "horizontal-tb",
        "css_text_align": "left",
        "font_family": "\"Qomolangma-Uchen Sarchung\", \"Kailasa\", \"Arial Unicode MS\", serif",
        "source_type": "vl3_long_text",
        "local_ebook_candidates": ["Kriya Tantra Leethong.epub"],
        "safe_title_fragments": ["བོད་ཡིག་ཡིག་ཆ།", "སློབ་སྦྱོང་ཡིག་ཆ།", "གསལ་བསྒྲགས།"],
    },
}


def discover_all_jobs(config: dict[str, Any], project_root: Path) -> list[dict[str, Any]]:
    jobs_by_dir = {job["language_dir"]: dict(job) for job in config.get("jobs", [])}
    for language_dir, job in BUILTIN_LANGUAGE_JOBS.items():
        jobs_by_dir.setdefault(language_dir, dict(job))
    final_root = project_root / "01_最终VL2数据"
    if final_root.exists():
        for lang_dir in sorted(p.name for p in final_root.iterdir() if p.is_dir()):
            if lang_dir in jobs_by_dir:
                continue
            raise RuntimeError(f"VL2 language exists but no profile is known: {lang_dir}")
    return [jobs_by_dir[name] for name in sorted(jobs_by_dir)]


def latest_prebuilt_records(project_root: Path, language_dir: str) -> Path | None:
    root = project_root / "02_语种工程资源" / language_dir
    candidates = sorted(root.glob("01_文本数据获取_*/data/**/*.jsonl"))
    candidates = [p for p in candidates if p.is_file()]
    if not candidates:
        return None

    def score(path: Path) -> tuple[int, str, int]:
        name = path.name
        text = str(path)
        priority = 0
        if "records_generation" in name and "final" in name:
            priority = 6
        elif "cleaned" in text or "clean" in text:
            priority = 5
        elif name == "records.jsonl" and "vl3_long_text_sources" in text:
            priority = 4
        elif name == "records.jsonl" and "people_daily" in text:
            priority = 4
        elif name == "records.jsonl":
            priority = 3
        elif "raw_segments" in name:
            priority = 1
        return (priority, text, path.stat().st_size)

    scored = sorted(candidates, key=score, reverse=True)
    return scored[0]


def merged_profile(job: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    profile = dict(defaults)
    profile.update({k: v for k, v in job.items() if k not in {"key", "language_dir", "source_type", "label_roots", "api_endpoint"}})
    profile.setdefault("sampling_policy", "continuous_paragraph_v1")
    target = job["key"]
    if target == "korean":
        profile.update({"max_latin_ratio": 0.0, "max_hangul_ratio": 1.0, "max_arabic_ratio": 0.0, "max_mongolian_ratio": 0.0})
    elif target in {"uyghur", "kazakh"}:
        profile.update({"max_latin_ratio": 0.0, "max_arabic_ratio": 1.0, "max_hangul_ratio": 0.0, "max_mongolian_ratio": 0.0})
    elif target == "mongolian":
        profile.update({"max_latin_ratio": 0.0, "max_mongolian_ratio": 1.0, "max_arabic_ratio": 0.0, "max_hangul_ratio": 0.0})
    elif target == "tibetan":
        profile.update({"max_latin_ratio": 0.0, "max_tibetan_ratio": 1.0, "max_arabic_ratio": 0.0, "max_hangul_ratio": 0.0, "max_mongolian_ratio": 0.0})
    else:
        profile.update({"max_latin_ratio": 1.0, "max_arabic_ratio": 0.0, "max_hangul_ratio": 0.0, "max_mongolian_ratio": 0.0})
    return profile


def setup_language_dirs(project_root: Path, date_tag: str, job: dict[str, Any], profile: dict[str, Any]) -> dict[str, Path]:
    resource_root = project_root / "02_语种工程资源"
    lang_root = resource_root / job["language_dir"]
    text_root = lang_root / f"01_文本数据获取_{date_tag}"
    template_root = lang_root / f"02_版面模板调研_{date_tag}"
    gen_root = lang_root / f"03_合成数据生成_{date_tag}"
    version_dir = gen_root / str(job.get("_source_version_dir_name", "v1"))
    for p in [lang_root / "00_中文导航_快速入口", text_root, template_root, gen_root, version_dir / "metadata", version_dir / "reports"]:
        p.mkdir(parents=True, exist_ok=True)
    configs_dir = gen_root / "configs"
    scripts_dir = gen_root / "scripts"
    configs_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SCRIPT_DIR, scripts_dir, dirs_exist_ok=True)
    shutil.copytree(ENGINE_ROOT / "configs" / "layout_templates_v2", configs_dir / "layout_templates_v2", dirs_exist_ok=True)
    vertical_templates = ENGINE_ROOT / "configs" / "mongolian_vertical_templates_v3"
    if vertical_templates.exists():
        shutil.copytree(vertical_templates, configs_dir / "mongolian_vertical_templates_v3", dirs_exist_ok=True)
    profile_path = configs_dir / f"{job['key']}_language_profile.json"
    write_json(profile_path, profile)
    readme_path = lang_root / "README.md"
    if not readme_path.exists():
        readme_path.write_text(
            f"# {job['language_name']}\n\n本目录由多语种合成数据流水线创建，当前批次日期 `{date_tag}`。\n\n- 文本数据：`01_文本数据获取_{date_tag}`\n- 模板参考：`02_版面模板调研_{date_tag}`\n- 合成数据：`03_合成数据生成_{date_tag}/{version_dir.name}`\n",
            encoding="utf-8",
        )
    quick_readme = lang_root / "00_中文导航_快速入口" / "README.md"
    if not quick_readme.exists():
        quick_readme.write_text(
            f"# {job['language_name']} 快速入口\n\n- 合成数据：`../03_合成数据生成_{date_tag}/{version_dir.name}`\n- 总览图：`../03_合成数据生成_{date_tag}/{version_dir.name}/reports/contact_sheet.jpg`\n",
            encoding="utf-8",
        )
    return {
        "lang_root": lang_root,
        "text_root": text_root,
        "template_root": template_root,
        "gen_root": gen_root,
        "version_dir": version_dir,
        "configs_dir": configs_dir,
        "scripts_dir": scripts_dir,
        "profile_path": profile_path,
    }


def build_text_pool(paths: dict[str, Path], job: dict[str, Any], py: str) -> tuple[Path | None, str | None]:
    data_dir = paths["text_root"] / "data"
    if job["source_type"] in {"prebuilt_records_in_delivery", "vl3_long_text"}:
        project_root = paths["lang_root"].parents[1]
        prebuilt = latest_prebuilt_records(project_root, job["language_dir"])
        out_dir = data_dir / "vl3_long_text_sources"
        out = out_dir / "records.jsonl"
        urls_file = paths["configs_dir"] / f"{job['key']}_vl3_urls.txt"
        local_files = []
        for name in job.get("local_ebook_candidates", []):
            candidate = project_root / name
            if candidate.exists():
                local_files.append(str(candidate))
        cmd = [
            py,
            str(paths["scripts_dir"] / "build_vl3_text_sources.py"),
            "--language-profile",
            str(paths["profile_path"]),
            "--output-dir",
            str(out_dir),
            "--output-jsonl",
            str(out),
            "--min-records",
            "40",
            "--min-chars",
            "40",
            "--resume-from-cache",
        ]
        if urls_file.exists():
            cmd.extend(["--urls-file", str(urls_file)])
        if local_files:
            cmd.extend(["--local-files", *local_files])
        if prebuilt:
            cmd.extend(["--fallback-records", str(prebuilt)])
        proc = run(cmd, env=proxy_env(), allow_fail=True)
        return (out, None) if proc.returncode == 0 else (None, proc.stdout)
    if job["source_type"] == "local_labels":
        out = data_dir / "local_verified_label_text_pool_20260702" / "records.jsonl"
        cmd = [
            py,
            str(paths["scripts_dir"] / "build_text_pool_from_labels.py"),
            "--label-roots",
            *job["label_roots"],
            "--output-jsonl",
            str(out),
            "--language-profile",
            str(paths["profile_path"]),
            "--min-chars",
            "40",
        ]
        proc = run(cmd, allow_fail=True)
        return (out, None) if proc.returncode == 0 else (None, proc.stdout)
    if job["source_type"] == "people_kazakh":
        out = data_dir / "people_daily_kazakh_20260702" / "records.jsonl"
        cmd = [
            py,
            str(paths["scripts_dir"] / "collect_people_kazakh_text.py"),
            "--language-profile",
            str(paths["profile_path"]),
            "--output-jsonl",
            str(out),
            "--target-records",
            "60",
            "--max-pages",
            "180",
        ]
        proc = run(cmd, env=proxy_env(), allow_fail=True)
        return (out, None) if proc.returncode == 0 else (None, proc.stdout)
    out = data_dir / "wikipedia_random_20260702" / "records.jsonl"
    cmd = [
        py,
        str(paths["scripts_dir"] / "collect_wikipedia_text.py"),
        "--api-endpoint",
        job["api_endpoint"],
        "--language-profile",
        str(paths["profile_path"]),
        "--output-jsonl",
        str(out),
        "--target-records",
        "120",
        "--random-pages",
        "400",
    ]
    proc = run(cmd, env=proxy_env(), allow_fail=True)
    return (out, None) if proc.returncode == 0 else (None, proc.stdout)


def write_blocked(paths: dict[str, Path], job: dict[str, Any], reason: str) -> None:
    report = f"""# BLOCKED Text Source Report

- 语种：{job['language_name']}
- 状态：未生成正式 72 张数据
- 原因：文本源构建失败

## 失败输出

```text
{reason[-4000:]}
```

## 可恢复命令

重新运行：

```bash
python3 {SCRIPT_DIR / 'run_multilingual_pipeline.py'} --only {job['key']}
```
"""
    (paths["text_root"] / "BLOCKED_TEXT_SOURCE_REPORT.md").write_text(report, encoding="utf-8")


def run_text_qa(paths: dict[str, Path], records: Path, py: str) -> bool:
    proc = run(
        [
            py,
            str(paths["scripts_dir"] / "qa_text_records.py"),
            "--text-jsonl",
            str(records),
            "--language-profile",
            str(paths["profile_path"]),
            "--output-dir",
            str(paths["version_dir"] / "reports" / "text_source"),
            "--min-usable-records",
            "40",
            "--fail-on-warning",
        ],
        allow_fail=True,
    )
    return proc.returncode == 0


def run_font_check(paths: dict[str, Path], records: Path, py: str) -> bool:
    proc = run(
        [
            py,
            str(paths["scripts_dir"] / "check_font_rendering.py"),
            "--language-profile",
            str(paths["profile_path"]),
            "--records-jsonl",
            str(records),
            "--output-dir",
            str(paths["version_dir"] / "reports" / "font_check"),
        ],
        allow_fail=True,
    )
    return proc.returncode == 0


def run_generation(paths: dict[str, Path], records: Path, job: dict[str, Any], py: str) -> bool:
    if job.get("key") == "mongolian" or str(job.get("writing_direction", "")).startswith("vertical"):
        templates_root = paths["configs_dir"] / "mongolian_vertical_templates_v3"
        if not (templates_root / "index.json").exists():
            proc = run(
                [
                    py,
                    str(paths["scripts_dir"] / "build_mongolian_vertical_templates_v3.py"),
                    "--output-root",
                    str(templates_root),
                ],
                allow_fail=True,
            )
            if proc.returncode != 0:
                write_json(paths["version_dir"] / "reports" / "failed_mongolian_template_build.json", {"output": proc.stdout})
                return False
        proc = run(
            [
                py,
                str(paths["scripts_dir"] / "generate_mongolian_vertical_from_json_v3.py"),
                "--text-jsonl",
                str(records),
                "--output-root",
                str(paths["version_dir"]),
                "--language-profile",
                str(paths["profile_path"]),
                "--templates-root",
                str(templates_root),
                "--min-records",
                "40",
                "--seed",
                "2026070213",
                "--version-name",
                "v1",
            ],
            allow_fail=True,
        )
        if proc.returncode != 0:
            write_json(paths["version_dir"] / "reports" / "failed_mongolian_generation.json", {"output": proc.stdout})
            return False
        generated_category_dirs = sorted(
            p
            for p in paths["version_dir"].iterdir()
            if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit() and (p / "metadata" / "html_manifest.json").exists()
        )
        for cat in generated_category_dirs:
            proc = run(
                [
                    runtime_node(),
                    str(paths["scripts_dir"] / "render_table_dataset.mjs"),
                    "--input-dir",
                    str(cat),
                    "--language-profile",
                    str(paths["profile_path"]),
                    "--auto-crop",
                    "true",
                    "--tight-crop",
                    "true",
                ],
                env=node_env(),
                allow_fail=True,
            )
            if proc.returncode != 0:
                write_json(paths["version_dir"] / "reports" / "failed_mongolian_render.json", {"category": cat.name, "output": proc.stdout})
                return False
            proc = run(
                [
                    py,
                    str(paths["scripts_dir"] / "qa_table_dataset.py"),
                    "--dataset-dir",
                    str(cat),
                    "--language-profile",
                    str(paths["profile_path"]),
                ],
                allow_fail=True,
            )
            if proc.returncode != 0:
                write_json(paths["version_dir"] / "reports" / "failed_mongolian_category_qa.json", {"category": cat.name, "output": proc.stdout})
                return False
        proc = run([py, str(paths["scripts_dir"] / "rebuild_version_index.py"), "--version-dir", str(paths["version_dir"])], allow_fail=True)
        if proc.returncode != 0:
            return False
        proc = run([py, str(paths["scripts_dir"] / "qa_layout_density.py"), "--dataset-dir", str(paths["version_dir"])], allow_fail=True)
        if proc.returncode != 0:
            return False
        proc = run(
            [
                py,
                str(paths["scripts_dir"] / "qa_version_acceptance.py"),
                "--version-dir",
                str(paths["version_dir"]),
                "--language-profile",
                str(paths["profile_path"]),
                "--max-density-warnings",
                "0",
            ],
            allow_fail=True,
        )
        return proc.returncode == 0

    batches = [
        ("generate_newspaper_from_json_templates.py", "newspaper_layout_templates_v2.json", 1, 2026070201),
        ("generate_batch1_from_json_templates.py", "batch1_layout_templates_v2.json", 2, 2026070202),
        ("generate_reading_pages_from_json_templates.py", "reading_pages_layout_templates_v2.json", 5, 2026070205),
        ("generate_remaining_pages_from_json_templates.py", "remaining_pages_layout_templates_v2.json", 8, 2026070208),
    ]
    max_category_workers = int(job.get("_max_category_workers", 1))

    def run_batch(batch: tuple[str, str, int, int]) -> tuple[bool, int, str]:
        script, template, start_index, seed = batch
        proc = run(
            [
                py,
                str(paths["scripts_dir"] / "run_category_batch.py"),
                "--version-dir",
                str(paths["version_dir"]),
                "--generator-script",
                str(paths["scripts_dir"] / script),
                "--templates-json",
                str(paths["configs_dir"] / "layout_templates_v2" / template),
                "--text-jsonl",
                str(records),
                "--language-profile",
                str(paths["profile_path"]),
                "--start-index",
                str(start_index),
                "--min-records",
                "40",
                "--seed",
                str(seed),
                "--version-name",
                str(job.get("_clean_version_name", "v1")),
                "--tight-crop",
                "true",
                "--skip-rebuild",
            ],
            allow_fail=True,
        )
        if proc.returncode != 0:
            write_json(paths["version_dir"] / "reports" / f"failed_batch_{start_index}.json", {"output": proc.stdout})
            return False, start_index, proc.stdout
        return True, start_index, proc.stdout

    if max_category_workers > 1:
        with ThreadPoolExecutor(max_workers=max_category_workers) as executor:
            futures = [executor.submit(run_batch, batch) for batch in batches]
            for future in as_completed(futures):
                ok, _, _ = future.result()
                if not ok:
                    return False
    else:
        for batch in batches:
            ok, _, _ = run_batch(batch)
            if not ok:
                return False
    proc = run(
        [py, str(paths["scripts_dir"] / "rebuild_version_index.py"), "--version-dir", str(paths["version_dir"])],
        allow_fail=True,
    )
    if proc.returncode != 0:
        return False
    proc = run(
        [
            py,
            str(paths["scripts_dir"] / "qa_version_acceptance.py"),
            "--version-dir",
            str(paths["version_dir"]),
            "--language-profile",
            str(paths["profile_path"]),
            "--max-density-warnings",
            "0",
        ],
        allow_fail=True,
    )
    return proc.returncode == 0


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in version_dir.iterdir()
        if p.is_dir()
        and len(p.name) >= 3
        and p.name[:2].isdigit()
        and (p / "metadata" / "render_manifest.json").exists()
    )


def run_version_qa(paths: dict[str, Path], version_dir: Path, py: str) -> bool:
    ok = True
    for dataset_dir in category_dirs(version_dir):
        proc = run(
            [
                py,
                str(paths["scripts_dir"] / "qa_table_dataset.py"),
                "--dataset-dir",
                str(dataset_dir),
                "--language-profile",
                str(paths["profile_path"]),
            ],
            allow_fail=True,
        )
        ok = ok and proc.returncode == 0
    proc = run([py, str(paths["scripts_dir"] / "rebuild_version_index.py"), "--version-dir", str(version_dir)], allow_fail=True)
    ok = ok and proc.returncode == 0
    proc = run([py, str(paths["scripts_dir"] / "qa_layout_density.py"), "--dataset-dir", str(version_dir)], allow_fail=True)
    ok = ok and proc.returncode == 0
    proc = run(
        [
            py,
            str(paths["scripts_dir"] / "qa_language_validity.py"),
            "--version-dir",
            str(version_dir),
            "--language-profile",
            str(paths["profile_path"]),
            "--fail-on-warning",
        ],
        allow_fail=True,
    )
    ok = ok and proc.returncode == 0
    proc = run(
        [
            py,
            str(paths["scripts_dir"] / "qa_version_acceptance.py"),
            "--version-dir",
            str(version_dir),
            "--language-profile",
            str(paths["profile_path"]),
            "--max-density-warnings",
            "0",
        ],
        allow_fail=True,
    )
    return ok and proc.returncode == 0


def run_augmentation(paths: dict[str, Path], py: str, profile: str, suffix: str, seed: int) -> tuple[bool, Path]:
    source_version_dir = paths["version_dir"]
    augmented_version_dir = source_version_dir.parent / f"{source_version_dir.name}{suffix}"
    proc = run(
        [
            py,
            str(paths["scripts_dir"] / "augment_synthetic_dataset.py"),
            "--source-version-dir",
            str(source_version_dir),
            "--output-version-dir",
            str(augmented_version_dir),
            "--seed",
            str(seed),
            "--profile",
            profile,
            "--force",
        ],
        allow_fail=True,
    )
    if proc.returncode != 0:
        write_json(source_version_dir / "reports" / "failed_augmentation.json", {"output": proc.stdout})
        return False, augmented_version_dir
    qa_ok = run_version_qa(paths, augmented_version_dir, py)
    return qa_ok, augmented_version_dir


def run_delivery_finalization(
    paths: dict[str, Path],
    py: str,
    output_name: str,
    image_assets_dir: Path | None,
    version_name: str,
    seed: int,
) -> tuple[bool, Path]:
    source_version_dir = paths["version_dir"]
    output_version_dir = source_version_dir.parent / output_name
    cmd = [
        py,
        str(paths["scripts_dir"] / "finalize_delivery_version.py"),
        "--source-version-dir",
        str(source_version_dir),
        "--output-version-dir",
        str(output_version_dir),
        "--language-profile",
        str(paths["profile_path"]),
        "--version-name",
        version_name,
        "--delivery-profile",
        str("vl3" if version_name.upper() == "VL3" else "v4"),
        "--seed",
        str(seed),
        "--force",
    ]
    if image_assets_dir:
        cmd.extend(["--image-assets-dir", str(image_assets_dir)])
    else:
        default_assets = paths["lang_root"].parents[1] / "04_共享图片资产" / "random120-coco2014"
        if default_assets.exists():
            cmd.extend(["--image-assets-dir", str(default_assets)])
    proc = run(cmd, allow_fail=True)
    if proc.returncode != 0:
        write_json(source_version_dir / "reports" / "failed_delivery_finalization.json", {"output": proc.stdout})
        return False, output_version_dir
    return True, output_version_dir


def summarize_language(
    paths: dict[str, Path],
    job: dict[str, Any],
    status: str,
    records: Path | None,
    augmented_version_dir: Path | None = None,
    augmentation_status: str | None = None,
) -> dict[str, Any]:
    reports = paths["version_dir"] / "reports"
    summary = {
        "language": job["language_name"],
        "key": job["key"],
        "status": status,
        "version_dir": str(paths["version_dir"]),
        "records": str(records) if records else None,
        "contact_sheet": str(reports / "contact_sheet.jpg"),
        "font_check": str(reports / "font_check" / "images" / "font_check.png"),
        "augmentation_status": augmentation_status,
        "augmented_version_dir": str(augmented_version_dir) if augmented_version_dir else None,
        "augmented_contact_sheet": str(augmented_version_dir / "reports" / "contact_sheet.jpg") if augmented_version_dir else None,
    }
    for name in ["qa_summary.json", "qa_density_summary.json", "acceptance_summary.json"]:
        p = reports / name
        if p.exists():
            summary[name] = read_json(p)
    if augmented_version_dir:
        augmented_reports = augmented_version_dir / "reports"
        for name in ["qa_summary.json", "qa_density_summary.json", "acceptance_summary.json", "augmentation_quality_summary.json"]:
            p = augmented_reports / name
            if p.exists():
                summary[f"augmented_{name}"] = read_json(p)
        for name in ["visual_delivery_summary.json", "image_asset_summary.json", "language_mix_summary.json", "language_validity_summary.json", "reading_order_summary.json"]:
            p = augmented_reports / name
            if p.exists():
                summary[f"augmented_{name}"] = read_json(p)
        for name in ["semantic_reading_order_summary.json", "no_unwanted_text_box_summary.json"]:
            p = augmented_reports / name
            if p.exists():
                summary[f"augmented_{name}"] = read_json(p)
    return summary


def write_master_report(project_root: Path, date_tag: str, summaries: list[dict[str, Any]]) -> None:
    out_dir = project_root / f"多语种合成数据生成汇总_{date_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "summary.json", summaries)
    rows = []
    for item in summaries:
        qa = item.get("qa_summary.json", {})
        density = item.get("qa_density_summary.json", {})
        acceptance = item.get("acceptance_summary.json", {})
        aug_qa = item.get("augmented_qa_summary.json", {})
        aug_density = item.get("augmented_qa_density_summary.json", {})
        aug_acceptance = item.get("augmented_acceptance_summary.json", {})
        aug_quality = item.get("augmented_augmentation_quality_summary.json", {})
        rows.append(
            f"| {item['language']} | {item['status']} | {qa.get('total_images', 0)} | {qa.get('passed_basic', 0)} | "
            f"{density.get('warning_images', 'NA')} | {acceptance.get('pass', False)} | "
            f"{item.get('augmentation_status') or 'NA'} | {aug_qa.get('passed_basic', 'NA')} | "
            f"{aug_density.get('warning_images', 'NA')} | {aug_acceptance.get('pass', 'NA')} | "
            f"{aug_quality.get('directional_light_total', 'NA')} | `{item['version_dir']}` | `{item.get('augmented_version_dir') or ''}` |"
        )
    md = f"""# 多语种合成数据生成汇总

批次日期：{date_tag}

| 语种 | 状态 | 干净图 | 干净通过 | 干净密度风险 | 干净验收 | 增强状态 | 增强通过 | 增强密度风险 | 增强验收 | 光照图 | 干净目录 | 增强目录 |
|---|---|---:|---:|---:|---|---|---:|---:|---|---:|---|---|
{chr(10).join(rows)}

## 人工重点抽检

- 维吾尔语、哈萨克语：RTL 字形连写、栏顺序、标题方向。
- 传统蒙古文：竖排方向、列顺序、标签框贴合。
- 白语：文本源真实性，确认未误用壮语文本。
- 朝鲜语：Hangul 显示和类别区分度。
"""
    (out_dir / "SUMMARY_REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs-config", default=str(ENGINE_ROOT / "configs" / "language_jobs.json"))
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--skip-augmentation", action="store_true")
    parser.add_argument("--augmentation-profile", default="delivery_all_light")
    parser.add_argument("--augmentation-suffix", default="_avg_v4")
    parser.add_argument("--augmentation-seed", type=int, default=20260705)
    parser.add_argument("--finalize-delivery", action="store_true", help="Use the Zhuang-v4-standard final delivery step after clean generation.")
    parser.add_argument("--delivery-output-name", default="VL2", help="Output folder name when --finalize-delivery is enabled.")
    parser.add_argument("--delivery-version-name", default="VL2")
    parser.add_argument("--image-assets-dir")
    parser.add_argument("--delivery-seed", type=int, default=2026070401)
    parser.add_argument("--languages", nargs="*", help="Alias for --only.")
    parser.add_argument("--max-language-workers", type=int, default=1)
    parser.add_argument("--max-category-workers", type=int, default=1)
    parser.add_argument("--resume-from-cache", action="store_true")
    parser.add_argument("--pilot", action="store_true", help="Run only Zhuang and Tibetan pilot.")
    args = parser.parse_args()
    config = read_json(Path(args.jobs_config))
    py = runtime_python()
    project_root = Path(config["project_root"])
    date_tag = config["date_tag"]
    defaults = config.get("defaults", {})
    selected = set(args.only or []) | set(args.languages or [])
    all_jobs = discover_all_jobs(config, project_root)
    if args.pilot:
        selected = {"zhuang", "tibetan", "壮语", "藏语"}
    jobs = []
    for job in all_jobs:
        if selected and job["key"] not in selected and job["language_dir"] not in selected:
            continue
        job = dict(job)
        job["_max_category_workers"] = args.max_category_workers
        if args.finalize_delivery:
            job["_clean_version_name"] = f"{args.delivery_output_name}_source"
            job["_source_version_dir_name"] = f"{args.delivery_output_name}_source"
        else:
            job["_clean_version_name"] = "VL3_clean" if args.delivery_version_name.upper() == "VL3" else "v1"
            job["_source_version_dir_name"] = "VL3_clean_source" if args.delivery_version_name.upper() == "VL3" else "v1"
        jobs.append(job)

    def run_one_language(job: dict[str, Any]) -> dict[str, Any]:
        profile = merged_profile(job, defaults)
        paths = setup_language_dirs(project_root, date_tag, job, profile)
        records, failure = build_text_pool(paths, job, py)
        if not records:
            write_blocked(paths, job, failure or "unknown failure")
            return summarize_language(paths, job, "blocked_text_source", None)
        text_ok = run_text_qa(paths, records, py)
        if not text_ok:
            return summarize_language(paths, job, "failed_text_qa", records)
        font_ok = run_font_check(paths, records, py)
        if not font_ok:
            return summarize_language(paths, job, "failed_font_check", records)
        gen_ok = run_generation(paths, records, job, py)
        if not gen_ok:
            return summarize_language(paths, job, "failed_generation_or_qa", records)
        augmented_dir = None
        augmentation_status = "skipped" if args.skip_augmentation else None
        if args.finalize_delivery:
            per_language_seed = args.delivery_seed + sum(ord(ch) for ch in str(job.get("key", "")))
            aug_ok, augmented_dir = run_delivery_finalization(
                paths,
                py,
                args.delivery_output_name,
                Path(args.image_assets_dir) if args.image_assets_dir else None,
                args.delivery_version_name,
                per_language_seed,
            )
            augmentation_status = "passed" if aug_ok else "failed"
        elif not args.skip_augmentation:
            aug_ok, augmented_dir = run_augmentation(
                paths,
                py,
                args.augmentation_profile,
                args.augmentation_suffix,
                args.augmentation_seed,
            )
            augmentation_status = "passed" if aug_ok else "failed"
        status = "passed" if augmentation_status in {None, "skipped", "passed"} else "failed_augmentation"
        return summarize_language(paths, job, status, records, augmented_dir, augmentation_status)

    summaries = []
    if args.max_language_workers > 1 and len(jobs) > 1:
        with ThreadPoolExecutor(max_workers=args.max_language_workers) as executor:
            future_by_key = {executor.submit(run_one_language, job): job["key"] for job in jobs}
            for future in as_completed(future_by_key):
                summaries.append(future.result())
        summaries.sort(key=lambda item: item["language"])
    else:
        for job in jobs:
            summaries.append(run_one_language(job))
    write_master_report(project_root, date_tag, summaries)
    print(json.dumps(summaries, ensure_ascii=False, indent=2)[:8000])
    return 0 if all(item["status"] == "passed" or item["status"] == "blocked_text_source" for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
