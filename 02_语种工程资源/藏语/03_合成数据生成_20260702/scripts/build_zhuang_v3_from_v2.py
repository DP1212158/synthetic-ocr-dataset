#!/usr/bin/env python3
"""Build Zhuang v3 from v2 with real image assets, Chinese text mixing, and augmentation."""

from __future__ import annotations

import argparse
import copy
import html
import json
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


DELIVERY_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = DELIVERY_ROOT
ENGINE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_ROOT = Path("/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")

NATURAL_LABELS = {
    "document_title",
    "document_subtitle",
    "section_title",
    "paragraph",
    "quote",
    "question",
    "option",
    "field_value",
    "table_cell_text",
    "note",
    "list_item",
    "caption",
    "footer",
}

CHINESE_SNIPPETS = {
    "newspaper_page": [
        "社区服务持续优化", "本周重点新闻", "文化活动有序开展", "公共信息请及时关注",
        "相关部门发布最新通知", "读者来信反映情况", "专题报道继续推进",
    ],
    "certificate_proof": [
        "经审核情况属实", "特此证明", "证书编号已登记", "本证明用于材料核验",
        "发证单位留存备案", "有效期以登记信息为准",
    ],
    "exam_paper": [
        "请认真阅读材料", "按要求完成作答", "本题共四个选项", "答案写在指定区域",
        "注意保持卷面整洁", "考试时间以通知为准",
    ],
    "sign_poster_scene": [
        "欢迎参加活动", "请按指引有序进入", "今日开放时间", "文明参观请勿拥挤",
        "咨询服务台在前方", "现场信息以公告为准",
    ],
    "book_page": [
        "本章介绍相关背景", "阅读时注意关键词", "以下内容节选自教材", "作者在文中强调",
        "本节内容可作为参考", "请结合上下文理解",
    ],
    "textbook_page": [
        "学习目标", "课堂练习", "知识拓展", "请完成课后思考", "重点词句如下",
        "教师可组织讨论", "本课内容建议复习",
    ],
    "magazine_journal": [
        "专题栏目", "人物访谈", "图文报道", "编辑推荐", "本期关注",
        "读者交流", "地方文化观察",
    ],
    "academic_paper": [
        "研究方法", "实验结果", "关键词", "摘要内容", "相关工作",
        "数据分析显示", "结论仍需进一步验证",
    ],
    "historical_classic": [
        "整理说明", "馆藏记录", "抄本来源", "版本校注", "档案编号",
        "此处文字略有残损", "据旧本重新校对",
    ],
    "notice_announcement": [
        "公告事项", "请相关人员知悉", "办理时间另行通知", "材料提交截止日期",
        "联系人及电话", "本通知自发布之日起执行",
    ],
    "complex_form": [
        "申请事项", "基本信息", "审核意见", "联系电话", "提交材料",
        "本人承诺信息真实", "经办人签字",
    ],
    "handwritten_letter": [
        "近来一切都好", "收到来信很高兴", "请代我问候家人", "这些事情慢慢再说",
        "愿你工作顺利", "有空再详细回复",
    ],
    "default": [
        "请核对相关信息", "内容仅供参考", "具体安排见通知", "材料已经整理完成",
        "后续事项另行说明",
    ],
}

LABEL_CJK_TARGETS = {
    "document_title": 0.12,
    "document_subtitle": 0.16,
    "section_title": 0.14,
    "paragraph": 0.26,
    "quote": 0.25,
    "question": 0.23,
    "option": 0.12,
    "field_value": 0.13,
    "table_cell_text": 0.18,
    "note": 0.22,
    "list_item": 0.21,
    "caption": 0.18,
    "footer": 0.18,
}

LABEL_LENGTH_GROWTH = {
    "document_title": 1.10,
    "document_subtitle": 1.05,
    "section_title": 1.08,
    "paragraph": 1.02,
    "quote": 1.02,
    "question": 1.03,
    "option": 1.05,
    "field_value": 1.08,
    "table_cell_text": 1.05,
    "note": 1.04,
    "list_item": 1.04,
    "caption": 1.05,
    "footer": 1.05,
}

CATEGORY_TARGET_ADJUST = {
    "exam_paper": {
        "document_title": 0.10,
        "section_title": 0.10,
        "option": 0.10,
        "table_cell_text": 0.12,
        "question": 0.20,
    },
    "certificate_proof": {
        "paragraph": 0.24,
        "field_value": 0.12,
    },
    "sign_poster_scene": {
        "document_title": 0.14,
        "section_title": 0.14,
        "paragraph": 0.22,
        "list_item": 0.18,
    },
    "academic_paper": {
        "paragraph": 0.26,
        "note": 0.22,
        "table_cell_text": 0.18,
    },
    "historical_classic": {
        "paragraph": 0.26,
        "note": 0.22,
        "field_value": 0.16,
    },
    "magazine_journal": {
        "paragraph": 0.26,
        "quote": 0.25,
    },
    "book_page": {
        "paragraph": 0.25,
        "quote": 0.24,
    },
    "notice_announcement": {
        "paragraph": 0.25,
        "field_value": 0.14,
    },
}


def runtime_python() -> str:
    candidate = DEFAULT_RUNTIME_ROOT / "python" / "bin" / "python3"
    return str(candidate) if candidate.exists() else sys.executable


def runtime_node() -> str:
    candidate = DEFAULT_RUNTIME_ROOT / "node" / "bin" / "node"
    return str(candidate) if candidate.exists() else "node"


def node_env() -> dict[str, str]:
    env = dict(**__import__("os").environ)
    candidate = DEFAULT_RUNTIME_ROOT / "node" / "node_modules"
    if candidate.exists():
        env["NODE_PATH"] = str(candidate)
    return env


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


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


def find_asset_dir(project_root: Path, explicit: Path | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    candidates.extend([
        project_root / "random120-coco2014",
        project_root / "random120_coco2014",
    ])
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    matches = [p for p in project_root.rglob("*") if p.is_dir() and p.name in {"random120-coco2014", "random120_coco2014"}]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError("cannot find random120-coco2014 or random120_coco2014 under project root")
    raise RuntimeError(f"multiple image asset dirs found: {matches}")


def load_image_assets(asset_dir: Path) -> list[dict[str, Any]]:
    assets = []
    for path in sorted(asset_dir.iterdir()):
        if path.suffix.lower() not in IMAGE_EXTS or not path.is_file():
            continue
        with Image.open(path) as img:
            width, height = img.size
        assets.append({
            "asset_id": path.stem,
            "source_path": str(path),
            "file_name": path.name,
            "width": width,
            "height": height,
        })
    if not assets:
        raise RuntimeError(f"no readable image assets in {asset_dir}")
    return assets


def copy_clean_static(src_v2: Path, clean_dir: Path, force: bool) -> None:
    if clean_dir.exists():
        if not force:
            raise FileExistsError(f"{clean_dir} exists; use --force")
        shutil.rmtree(clean_dir)
    clean_dir.mkdir(parents=True)
    for name in ["metadata", "reports", "assets"]:
        if (src_v2 / name).exists():
            shutil.copytree(src_v2 / name, clean_dir / name, dirs_exist_ok=True)
    for cat in category_dirs(src_v2):
        dst = clean_dir / cat.name
        for sub in ["html", "images", "labels", "metadata", "reports", "reports/overlays"]:
            (dst / sub).mkdir(parents=True, exist_ok=True)
        shutil.copytree(cat / "html", dst / "html", dirs_exist_ok=True)
        shutil.copytree(cat / "metadata", dst / "metadata", dirs_exist_ok=True)
        if (cat / "README.md").exists():
            shutil.copy2(cat / "README.md", dst / "README.md")


def build_profile(src_profile: Path, out_profile: Path, target_cjk_ratio: float) -> dict[str, Any]:
    profile = read_json(src_profile)
    profile["profile_note"] = "Zhuang v3 allows intentional Chinese text mixing."
    profile["max_cjk_ratio"] = 1.0
    profile["min_script_ratio"] = min(float(profile.get("min_script_ratio", 0.45)), 0.30)
    profile["target_cjk_ratio"] = target_cjk_ratio
    write_json(out_profile, profile)
    return profile


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def compact_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def cjk_len(text: str) -> int:
    return len(CJK_RE.findall(text or ""))


def take_compact_prefix(text: str, max_nonspace_chars: int) -> str:
    if max_nonspace_chars <= 0:
        return ""
    kept = []
    seen = 0
    for ch in text:
        if not ch.isspace():
            seen += 1
        kept.append(ch)
        if seen >= max_nonspace_chars:
            break
    return "".join(kept).strip(" ,.;:/|，。；、")


def should_mix(label: str, text: str) -> bool:
    if label not in NATURAL_LABELS:
        return False
    text = normalize_text(text)
    if len(text) < 6:
        return False
    if not LATIN_RE.search(text):
        return False
    if CJK_RE.search(text):
        return False
    if sum(ch.isdigit() for ch in text) > max(4, len(text) * 0.35):
        return False
    return True


def choose_snippet(category: str, label: str, rng: random.Random) -> str:
    pool = CHINESE_SNIPPETS.get(category) or CHINESE_SNIPPETS["default"]
    snippet = rng.choice(pool)
    if label == "document_title" and len(snippet) > 10:
        return snippet[:10]
    if label in {"caption", "note", "option"} and len(snippet) > 12:
        return snippet[:12]
    return snippet


def target_for_block(category: str, label: str) -> float:
    target = LABEL_CJK_TARGETS.get(label, 0.30)
    return CATEGORY_TARGET_ADJUST.get(category, {}).get(label, target)


def build_chinese_text(category: str, label: str, min_cjk_chars: int, rng: random.Random) -> str:
    pool = CHINESE_SNIPPETS.get(category) or CHINESE_SNIPPETS["default"]
    snippets: list[str] = []
    used: set[str] = set()
    while cjk_len("".join(snippets)) < min_cjk_chars:
        if len(used) >= len(pool):
            used.clear()
        candidates = [item for item in pool if item not in used] or pool
        snippet = rng.choice(candidates)
        used.add(snippet)
        if label == "document_title" and len(snippet) > 10:
            snippet = snippet[:10]
        elif label in {"caption", "note", "option", "field_value", "table_cell_text"} and len(snippet) > 12:
            snippet = snippet[:12]
        snippets.append(snippet)
    return "；".join(snippets)


def mixed_text(text: str, category: str, label: str, rng: random.Random) -> str:
    text = normalize_text(text)
    original_chars = compact_len(text)
    if original_chars <= 0:
        return text
    target = target_for_block(category, label)
    growth = LABEL_LENGTH_GROWTH.get(label, 1.04)
    final_chars = max(original_chars, int(round(original_chars * growth)))
    if original_chars < 24:
        final_chars += 2
    desired_cjk = max(2, int(round(final_chars * target)))
    chinese = build_chinese_text(category, label, desired_cjk, rng)
    chinese_chars = cjk_len(chinese)
    separator_chars = 1 if label in {"document_title", "section_title", "document_subtitle"} else 2
    original_budget = max(6, final_chars - compact_len(chinese) - separator_chars)
    original_part = take_compact_prefix(text, min(original_chars, original_budget))
    if label in {"document_title", "section_title", "document_subtitle"}:
        return f"{original_part} {chinese}".strip()
    if label in {"caption", "note", "option", "field_value"}:
        return f"{original_part} / {chinese}".strip()
    if label == "table_cell_text":
        return f"{original_part}；{chinese}".strip()
    return f"{original_part}。{chinese}".strip()


def html_block_replacer(html_text: str, category: str, rng: random.Random, stats: dict[str, Any]) -> str:
    pattern = re.compile(
        r'(<(?P<tag>[a-zA-Z0-9]+)(?P<attrs>[^>]*\bdata-block-id="(?P<bid>[^"]+)"[^>]*\bdata-label="(?P<label>[^"]+)"[^>]*)>)'
        r'(?P<inner>.*?)'
        r'(</(?P=tag)>)',
        re.DOTALL,
    )

    def repl(match: re.Match[str]) -> str:
        label = match.group("label")
        inner = match.group("inner")
        text = re.sub(r"<[^>]+>", " ", inner)
        if should_mix(label, text):
            new_text = mixed_text(text, category, label, rng)
            stats["mixed_blocks"] += 1
            stats["inserted_cjk_chars"] += len(CJK_RE.findall(new_text)) - len(CJK_RE.findall(text))
            return f'{match.group(1)}{html.escape(new_text, quote=False)}{match.group(7)}'
        return match.group(0)

    return pattern.sub(repl, html_text)


def img_tag(asset: dict[str, Any], rel_src: str) -> str:
    return (
        f'<img src="{html.escape(rel_src, quote=True)}" '
        f'style="width:100%;height:100%;object-fit:cover;display:block;" '
        f'alt="" data-asset-img="true" />'
    )


def replace_image_placeholders(
    html_text: str,
    document_id: str,
    category: str,
    assets: list[dict[str, Any]],
    asset_index: int,
    asset_dest_dir: Path,
    html_file: Path,
    manifest: list[dict[str, Any]],
) -> tuple[str, int]:
    pattern = re.compile(
        r'(<(?P<tag>[a-zA-Z0-9]+)(?P<attrs>[^>]*\bdata-block-id="(?P<bid>[^"]+)"[^>]*\bdata-label="(?P<label>image|photo|figure|photo_lead|image_figure)"[^>]*)>)'
        r'(?P<inner>.*?)'
        r'(</(?P=tag)>)',
        re.DOTALL,
    )

    def repl(match: re.Match[str]) -> str:
        nonlocal asset_index
        asset = assets[asset_index % len(assets)]
        asset_index += 1
        dst_asset = asset_dest_dir / asset["file_name"]
        if not dst_asset.exists():
            shutil.copy2(asset["source_path"], dst_asset)
        rel_src = Path("../../assets/random120-coco2014") / asset["file_name"]
        open_tag = match.group(1)
        if "data-is-text=" not in open_tag:
            open_tag = open_tag[:-1] + ' data-is-text="false">'
        for attr, value in [
            ("data-asset-id", asset["asset_id"]),
            ("data-asset-source", "random120-coco2014"),
            ("data-asset-crop", "object-fit-cover"),
        ]:
            if f"{attr}=" not in open_tag:
                open_tag = open_tag[:-1] + f' {attr}="{html.escape(value, quote=True)}">'
        manifest.append({
            "document_id": document_id,
            "category": category,
            "block_id": match.group("bid"),
            "block_label": match.group("label"),
            "asset_id": asset["asset_id"],
            "asset_source": "random120-coco2014",
            "asset_file": str(dst_asset),
            "asset_original_path": asset["source_path"],
            "asset_width": asset["width"],
            "asset_height": asset["height"],
            "asset_crop": "object-fit-cover",
            "html": str(html_file),
        })
        return f'{open_tag}{img_tag(asset, rel_src.as_posix())}{match.group(7)}'

    return pattern.sub(repl, html_text), asset_index


def transform_htmls(clean_dir: Path, assets: list[dict[str, Any]], target_cjk_ratio: float, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    asset_dir = clean_dir / "assets" / "random120-coco2014"
    asset_dir.mkdir(parents=True, exist_ok=True)
    all_asset_manifest: list[dict[str, Any]] = []
    asset_index = 0
    language_stats = {
        "target_cjk_ratio": target_cjk_ratio,
        "mixed_blocks": 0,
        "inserted_cjk_chars": 0,
    }
    for cat in category_dirs(clean_dir):
        html_manifest = read_json(cat / "metadata" / "html_manifest.json")
        for item in html_manifest:
            html_path = cat / "html" / f"{item['document_id']}.html"
            text = html_path.read_text(encoding="utf-8")
            stats = {"mixed_blocks": 0, "inserted_cjk_chars": 0}
            text = html_block_replacer(text, item.get("category") or "default", rng, stats)
            text, asset_index = replace_image_placeholders(
                text,
                item["document_id"],
                item.get("category") or "unknown",
                assets,
                asset_index,
                asset_dir,
                html_path,
                all_asset_manifest,
            )
            html_path.write_text(text, encoding="utf-8")
            item["version_name"] = "v3_clean_source"
            item["generator"] = f"{item.get('generator', 'html_layout')}_v3_mixed_assets"
            item["image_assets_enabled"] = True
            item["target_cjk_ratio"] = target_cjk_ratio
            item["source_version"] = "v2"
            language_stats["mixed_blocks"] += stats["mixed_blocks"]
            language_stats["inserted_cjk_chars"] += stats["inserted_cjk_chars"]
        write_json(cat / "metadata" / "html_manifest.json", html_manifest)
    write_json(clean_dir / "metadata" / "image_asset_manifest.json", all_asset_manifest)
    language_stats["image_slots"] = len(all_asset_manifest)
    language_stats["unique_assets_used"] = len({row["asset_id"] for row in all_asset_manifest})
    return language_stats


def render_clean_version(clean_dir: Path, profile_path: Path) -> None:
    node = runtime_node()
    py = runtime_python()
    for cat in category_dirs(clean_dir):
        run([
            node,
            str(ENGINE_ROOT / "scripts" / "render_table_dataset.mjs"),
            "--input-dir",
            str(cat),
            "--language-profile",
            str(profile_path),
            "--auto-crop",
            "true",
            "--tight-crop",
            "true",
        ], env=node_env())
        run([
            py,
            str(ENGINE_ROOT / "scripts" / "qa_table_dataset.py"),
            "--dataset-dir",
            str(cat),
            "--language-profile",
            str(profile_path),
        ])
    run([py, str(ENGINE_ROOT / "scripts" / "rebuild_version_index.py"), "--version-dir", str(clean_dir)])
    run([py, str(ENGINE_ROOT / "scripts" / "qa_layout_density.py"), "--dataset-dir", str(clean_dir)])


def augment_to_v3(clean_dir: Path, out_v3: Path, force: bool) -> None:
    py = runtime_python()
    run([
        py,
        str(ENGINE_ROOT / "scripts" / "augment_synthetic_dataset.py"),
        "--source-version-dir",
        str(clean_dir),
        "--output-version-dir",
        str(out_v3),
        "--seed",
        "20260705",
        "--profile",
        "delivery_all_light",
        "--force" if force else "--force",
    ])


def copy_v3_metadata(clean_dir: Path, out_v3: Path, profile_path: Path) -> None:
    if (clean_dir / "metadata" / "image_asset_manifest.json").exists():
        shutil.copy2(clean_dir / "metadata" / "image_asset_manifest.json", out_v3 / "metadata" / "image_asset_manifest.json")
    if (clean_dir / "metadata" / "language_mix_summary.json").exists():
        shutil.copy2(clean_dir / "metadata" / "language_mix_summary.json", out_v3 / "metadata" / "language_mix_summary.json")
    shutil.copy2(profile_path, out_v3 / "metadata" / "language_profile.json")
    assets_src = clean_dir / "assets" / "random120-coco2014"
    assets_dst = out_v3 / "assets" / "random120-coco2014"
    if assets_src.exists():
        shutil.copytree(assets_src, assets_dst, dirs_exist_ok=True)


def text_ratios_from_labels(version_dir: Path) -> dict[str, Any]:
    total_cjk = 0
    total_latin = 0
    total_chars = 0
    by_category: dict[str, dict[str, Any]] = {}
    zero_cjk_docs = []
    for label_path in sorted(version_dir.glob("*/labels/*.json")):
        label = read_json(label_path)
        category = label.get("attributes", {}).get("category") or label_path.parts[-3]
        doc_cjk = doc_latin = doc_chars = 0
        for block in label.get("blocks", []):
            if block.get("is_text", True) is False:
                continue
            text = block.get("block_content") or ""
            if not text.strip():
                continue
            cjk = len(CJK_RE.findall(text))
            latin = len(LATIN_RE.findall(text))
            chars = len(re.sub(r"\s+", "", text))
            doc_cjk += cjk
            doc_latin += latin
            doc_chars += chars
        if doc_cjk == 0:
            zero_cjk_docs.append(label.get("attributes", {}).get("document_id") or label_path.stem)
        total_cjk += doc_cjk
        total_latin += doc_latin
        total_chars += doc_chars
        stat = by_category.setdefault(category, {"documents": 0, "cjk_chars": 0, "latin_chars": 0, "chars": 0})
        stat["documents"] += 1
        stat["cjk_chars"] += doc_cjk
        stat["latin_chars"] += doc_latin
        stat["chars"] += doc_chars
    for stat in by_category.values():
        stat["cjk_ratio"] = round(stat["cjk_chars"] / max(stat["chars"], 1), 4)
        stat["latin_ratio"] = round(stat["latin_chars"] / max(stat["chars"], 1), 4)
    return {
        "total_cjk_chars": total_cjk,
        "total_latin_chars": total_latin,
        "total_text_chars": total_chars,
        "cjk_ratio": round(total_cjk / max(total_chars, 1), 4),
        "latin_ratio": round(total_latin / max(total_chars, 1), 4),
        "zero_cjk_documents": zero_cjk_docs,
        "by_category": by_category,
        "pass": 0.25 <= (total_cjk / max(total_chars, 1)) <= 0.35 and not zero_cjk_docs,
    }


def image_asset_qa(version_dir: Path) -> dict[str, Any]:
    manifest = read_json(version_dir / "metadata" / "image_asset_manifest.json")
    missing = []
    for row in manifest:
        if not Path(row["asset_file"].replace(str(version_dir.parent / "v3_clean_source"), str(version_dir))).exists():
            # v3 stores a copied asset dir; asset_file itself points to the clean source for traceability.
            if not (version_dir / "assets" / "random120-coco2014" / Path(row["asset_file"]).name).exists():
                missing.append(row)
    html_missing = []
    placeholder_re = re.compile(r'data-label="(?:image|photo|figure|photo_lead|image_figure)"')
    for html_path in version_dir.glob("*/html/*.html"):
        text = html_path.read_text(encoding="utf-8")
        if placeholder_re.search(text) and 'data-asset-img="true"' not in text:
            html_missing.append(str(html_path))
    return {
        "image_slots": len(manifest),
        "unique_assets_used": len({row["asset_id"] for row in manifest}),
        "missing_image_assets": len(missing),
        "unfilled_image_slot_files": html_missing,
        "unfilled_image_slots": len(html_missing),
        "pass": len(manifest) > 0 and not missing and not html_missing,
    }


def write_special_reports(version_dir: Path, mix_summary: dict[str, Any], image_summary: dict[str, Any]) -> None:
    write_json(version_dir / "metadata" / "language_mix_summary.json", mix_summary)
    write_json(version_dir / "reports" / "language_mix_summary.json", mix_summary)
    write_json(version_dir / "reports" / "image_asset_summary.json", image_summary)
    cat_rows = "\n".join(
        f"| {cat} | {stat['documents']} | {stat['cjk_chars']} | {stat['latin_chars']} | {stat['cjk_ratio']} |"
        for cat, stat in sorted(mix_summary["by_category"].items())
    )
    (version_dir / "reports" / "QA_LANGUAGE_MIX_REPORT.md").write_text(
        f"""# Language Mix QA

- 中文字符占比：{mix_summary['cjk_ratio']}
- 拉丁字符占比：{mix_summary['latin_ratio']}
- 中文字符数：{mix_summary['total_cjk_chars']}
- 总文本字符数：{mix_summary['total_text_chars']}
- 无中文样本数：{len(mix_summary['zero_cjk_documents'])}
- 结论：{'通过' if mix_summary['pass'] else '需处理'}

| 类别 | 样本数 | 中文字符 | 拉丁字符 | 中文占比 |
|---|---:|---:|---:|---:|
{cat_rows}
""",
        encoding="utf-8",
    )
    (version_dir / "reports" / "QA_IMAGE_ASSETS_REPORT.md").write_text(
        f"""# Image Asset QA

- 图片槽位：{image_summary['image_slots']}
- 使用不同图片：{image_summary['unique_assets_used']}
- 缺失图片文件：{image_summary['missing_image_assets']}
- 未填充图片槽位：{image_summary['unfilled_image_slots']}
- 结论：{'通过' if image_summary['pass'] else '需处理'}
""",
        encoding="utf-8",
    )


def run_final_qa(out_v3: Path, profile_path: Path) -> None:
    py = runtime_python()
    for cat in category_dirs(out_v3):
        run([
            py,
            str(ENGINE_ROOT / "scripts" / "qa_table_dataset.py"),
            "--dataset-dir",
            str(cat),
            "--language-profile",
            str(profile_path),
        ])
    run([py, str(ENGINE_ROOT / "scripts" / "rebuild_version_index.py"), "--version-dir", str(out_v3)])
    run([py, str(ENGINE_ROOT / "scripts" / "qa_layout_density.py"), "--dataset-dir", str(out_v3)])
    run([
        py,
        str(ENGINE_ROOT / "scripts" / "qa_version_acceptance.py"),
        "--version-dir",
        str(out_v3),
        "--max-density-warnings",
        "0",
    ])


def write_readme(out_v3: Path, source_v2: Path, asset_dir: Path, mix_summary: dict[str, Any], image_summary: dict[str, Any]) -> None:
    (out_v3 / "README.md").write_text(
        f"""# 壮语 v3

本版本基于 `{source_v2}` 生成，主要变化：

- 图片占位符替换为 `{asset_dir}` 中的真实 COCO 图片。
- 自然语言文本混入约 30% 中文。
- 已应用 `delivery_all_light` 数据增强。

## QA 摘要

- 中文字符占比：{mix_summary['cjk_ratio']}
- 图片槽位：{image_summary['image_slots']}
- 使用不同图片：{image_summary['unique_assets_used']}
- 无中文样本数：{len(mix_summary['zero_cjk_documents'])}

核心报告：

- `reports/QA_REPORT.md`
- `reports/QA_DENSITY_REPORT.md`
- `reports/ACCEPTANCE_REPORT.md`
- `reports/QA_LANGUAGE_MIX_REPORT.md`
- `reports/QA_IMAGE_ASSETS_REPORT.md`
- `reports/contact_sheet.jpg`
- `reports/contact_sheet_with_boxes.jpg`
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-v2", default=str(PROJECT_ROOT / "02_语种工程资源" / "壮语" / "03_合成数据生成_20260701" / "v2"))
    parser.add_argument("--output-v3", default=str(PROJECT_ROOT / "01_最终VL2数据" / "壮语" / "v3"))
    parser.add_argument("--image-assets-dir")
    parser.add_argument("--source-profile", default=str(PROJECT_ROOT / "02_语种工程资源" / "壮语" / "03_合成数据生成_20260701" / "configs" / "zhuang_language_profile.json"))
    parser.add_argument("--target-cjk-ratio", type=float, default=0.30)
    parser.add_argument("--seed", type=int, default=2026070301)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--keep-clean-source", action="store_true")
    args = parser.parse_args()

    source_v2 = Path(args.source_v2)
    out_v3 = Path(args.output_v3)
    clean_dir = out_v3.parent / "v3_clean_source"
    asset_dir = find_asset_dir(PROJECT_ROOT, Path(args.image_assets_dir) if args.image_assets_dir else None)
    assets = load_image_assets(asset_dir)
    if len(assets) < 15:
        raise RuntimeError(f"not enough image assets: {len(assets)}")

    if out_v3.exists():
        if not args.force:
            raise FileExistsError(f"{out_v3} exists; use --force")
        shutil.rmtree(out_v3)

    copy_clean_static(source_v2, clean_dir, args.force)
    profile_path = clean_dir / "metadata" / "zhuang_v3_language_profile.json"
    build_profile(Path(args.source_profile), profile_path, args.target_cjk_ratio)
    transform_stats = transform_htmls(clean_dir, assets, args.target_cjk_ratio, args.seed)
    write_json(clean_dir / "metadata" / "language_mix_generation_summary.json", transform_stats)
    render_clean_version(clean_dir, profile_path)

    clean_mix = text_ratios_from_labels(clean_dir)
    write_special_reports(clean_dir, clean_mix, image_asset_qa(clean_dir))

    augment_to_v3(clean_dir, out_v3, True)
    copy_v3_metadata(clean_dir, out_v3, profile_path)
    run_final_qa(out_v3, profile_path)
    mix_summary = text_ratios_from_labels(out_v3)
    image_summary = image_asset_qa(out_v3)
    write_special_reports(out_v3, mix_summary, image_summary)
    write_readme(out_v3, source_v2, asset_dir, mix_summary, image_summary)

    if not mix_summary["pass"]:
        raise RuntimeError(f"language mix QA failed: {mix_summary}")
    if not image_summary["pass"]:
        raise RuntimeError(f"image asset QA failed: {image_summary}")
    if not args.keep_clean_source and clean_dir.exists():
        shutil.rmtree(clean_dir)

    print(json.dumps({
        "output_v3": str(out_v3),
        "assets": str(asset_dir),
        "image_slots": image_summary["image_slots"],
        "cjk_ratio": mix_summary["cjk_ratio"],
        "pass": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
