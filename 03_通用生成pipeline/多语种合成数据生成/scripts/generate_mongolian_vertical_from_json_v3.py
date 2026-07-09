#!/usr/bin/env python3
"""Generate traditional Mongolian pages from v3 JSON layout trees."""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path
from typing import Any

from synthetic_text_utils import cleanse_text, load_language_profile, read_text_records, record_text, record_title, safe_fragment, select_span


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def clean_version_dir(version_dir: Path) -> None:
    if version_dir.exists():
        for child in version_dir.iterdir():
            if child.is_dir() and child.name[:2].isdigit():
                shutil.rmtree(child)
    (version_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (version_dir / "reports").mkdir(parents=True, exist_ok=True)


def base_css(profile: dict[str, Any], style_tokens: dict[str, Any] | None = None) -> str:
    tokens = style_tokens or {}
    font = profile.get("font_family", '"Noto Sans Mongolian", "Arial Unicode", sans-serif')
    paper = tokens.get("paper", "#fbf8ed")
    ink = tokens.get("ink", "#151515")
    line = tokens.get("line", "#222222")
    accent = tokens.get("accent", "#8f2f2f")
    return f"""
* {{ box-sizing: border-box; }}
html, body {{ margin:0; padding:0; background:#d8dadd; }}
body {{ font-family:{font}; color:{ink}; }}
.page {{
  margin: 0 auto;
  background: {paper};
  position: relative;
  overflow: hidden;
}}
.vtext {{
  writing-mode: vertical-lr;
  direction: ltr;
  text-orientation: mixed;
  line-height: 1.42;
  word-break: keep-all;
  overflow-wrap: normal;
  overflow: hidden;
}}
[data-block-id] {{ position:absolute; overflow:visible; }}
.title {{ font-weight:900; font-size:34px; line-height:1.36; }}
.subtitle {{ font-weight:800; font-size:24px; line-height:1.36; }}
.body {{ font-size:20px; line-height:1.42; }}
.small {{ font-size:16px; line-height:1.34; }}
.tiny {{ font-size:13px; line-height:1.28; }}
.hand {{ font-family:{font}; letter-spacing:0; transform:skewY(-1.2deg); }}
.light {{ color:#efe5c9; }}
.box {{ border:2px solid {line}; background:rgba(255,255,255,.42); }}
.boxed {{ border:1.4px solid {line}; background:rgba(255,255,255,.36); }}
.thin {{ border:1px solid #373737; }}
.ornate {{ border:4px double {line}; }}
.rule-v {{ position:absolute; width:2px; background:{line}; opacity:.75; }}
.rule-h {{ position:absolute; height:2px; background:{line}; opacity:.75; }}
.stamp {{ border:4px solid {accent}; color:{accent}; border-radius:50%; opacity:.74; display:flex; align-items:center; justify-content:center; }}
.image-fill {{
  background: repeating-linear-gradient(135deg,#d8d2c2,#d8d2c2 14px,#efe9d9 14px,#efe9d9 28px);
  border:2px solid #303030;
}}
.answer-box {{ border:1.6px solid {line}; background:rgba(255,255,255,.52); }}
.soft-fill {{ background:rgba(204,218,212,.36); }}
.note-fill {{ background:rgba(242,224,181,.45); }}
.urgent-fill {{ background:rgba(236,205,181,.58); }}
.dark-fill {{ background:#2c2924; }}
"""


class TextSampler:
    def __init__(self, records: list[dict[str, str]], rng: random.Random):
        self.records = records
        self.rng = rng

    def long_text(self, min_len: int, max_len: int) -> str:
        pool = [rec for rec in self.records if len(rec["text"]) >= min_len] or self.records
        for _ in range(16):
            text = select_span(self.rng.choice(pool)["text"], self.rng, min_len, max_len)
            if len(text) >= min_len:
                return text
        parts: list[str] = []
        while len(" ".join(parts)) < min_len and len(parts) < 6:
            parts.append(cleanse_text(self.rng.choice(self.records)["text"]))
        return select_span(" ".join(parts), self.rng, min_len, max_len)

    def fill_text(self, height: int, min_len: int, max_len: int, cls: str = "body") -> str:
        if "tiny" in cls:
            ratio_min, ratio_max = 0.055, 0.085
        elif "small" in cls:
            ratio_min, ratio_max = 0.075, 0.115
        else:
            ratio_min, ratio_max = 0.10, 0.16
        target_min = max(min_len, int(height * ratio_min))
        target_max = max(max_len, int(height * ratio_max), target_min + 16)
        return self.long_text(target_min, target_max)

    def sample(self, text_spec: dict[str, Any], height: int, cls: str) -> str:
        source = str(text_spec.get("source", "fill"))
        min_chars = int(text_spec.get("min_chars", 16))
        max_chars = int(text_spec.get("max_chars", 80))
        value = text_spec.get("value")
        if source == "blank":
            return ""
        if source == "literal":
            return str(value or "")
        if source == "safe_fragment":
            return safe_fragment(min_chars, max_chars)
        if source == "title":
            return record_title(self.records, self.rng, min_chars, max_chars)
        if source == "question":
            return f"{self.rng.randint(1, 36)}. {record_text(self.records, self.rng, min_chars, max_chars)}"
        if source == "short":
            return record_text(self.records, self.rng, min_chars, max_chars)
        return self.fill_text(height, min_chars, max_chars, cls)


def class_for_element(element: dict[str, Any]) -> str:
    kind = element.get("kind", "text")
    cls = str(element.get("class", "body"))
    if kind in {"text"}:
        return f"vtext {cls}".strip()
    return cls


def style_for_box(box: dict[str, Any], visual: dict[str, Any] | None = None) -> str:
    visual = visual or {}
    style = [
        f"position:absolute",
        f"left:{int(box['x'])}px",
        f"top:{int(box['y'])}px",
        f"width:{int(box['w'])}px",
        f"height:{int(box['h'])}px",
    ]
    for key, css_key in [
        ("background", "background"),
        ("color", "color"),
        ("border", "border"),
        ("opacity", "opacity"),
    ]:
        if key in visual:
            style.append(f"{css_key}:{visual[key]}")
    return ";".join(style)


def data_attrs(element: dict[str, Any], id_by_element: dict[str, str]) -> str:
    attrs = element.get("attributes") or {}
    out = []
    for key, value in attrs.items():
        if value is None:
            continue
        html_key = "data-" + str(key).replace("_", "-")
        html_value = str(value)
        if key == "caption_of":
            html_value = id_by_element.get(html_value, html_value)
        out.append(f'{html_key}="{esc(html_value)}"')
    return (" " + " ".join(out)) if out else ""


def html_element(doc_id: str, idx: int, element: dict[str, Any], sampler: TextSampler, id_by_element: dict[str, str]) -> str:
    kind = str(element.get("kind", "text"))
    label = str(element.get("label", kind))
    box = element["box"]
    cls = class_for_element(element)
    style = style_for_box(box, element.get("visual", {}))
    if kind == "decor" or label == "decor":
        return f'<div class="{esc(cls)}" aria-hidden="true" data-is-text="false" style="{style}"></div>'
    text = sampler.sample(element.get("text", {}), int(box["h"]), cls)
    content = esc(text)
    block_id = f"{doc_id}_b{idx:04d}"
    return f'<div data-block-id="{block_id}" data-label="{esc(label)}"{data_attrs(element, id_by_element)} class="{esc(cls)}" style="{style}">{content}</div>'


def render_html(profile: dict[str, Any], template: dict[str, Any], doc_id: str, elements: list[str]) -> str:
    page = template["page"]
    width = int(page["width"])
    height = int(page["height"])
    css = base_css(profile, template.get("style_tokens", {}))
    return f"""<!doctype html>
<html lang="{profile.get('html_lang', 'mn-Mong')}" dir="ltr">
<head>
<meta charset="utf-8">
<title>{esc(template.get('category_cn'))} {esc(doc_id)}</title>
<style>{css}</style>
</head>
<body><main class="page" style="width:{width}px;min-height:{height}px">{''.join(elements)}</main></body>
</html>
"""


def category_dirs_from_index(index: dict[str, Any]) -> list[tuple[str, str, str]]:
    seen: list[tuple[str, str, str]] = []
    for item in index["templates"]:
        row = (item["folder"], item["category_id"], item["category_cn"])
        if row not in seen:
            seen.append(row)
    return seen


def template_index_filename(index: dict[str, Any]) -> str:
    schema = str(index.get("schema_version", ""))
    if schema.endswith(".v4"):
        return "template_index_v4.json"
    if schema.endswith(".v3"):
        return "template_index_v3.json"
    return "template_index.json"


def template_version_label(index: dict[str, Any]) -> str:
    schema = str(index.get("schema_version", ""))
    if schema.endswith(".v4"):
        return "v4"
    if schema.endswith(".v3"):
        return "v3"
    return "json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-jsonl", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--templates-root", required=True)
    parser.add_argument("--min-records", type=int, default=40)
    parser.add_argument("--seed", type=int, default=2026070213)
    parser.add_argument("--version-name", default="v3")
    args = parser.parse_args()

    profile = load_language_profile(Path(args.language_profile))
    records = read_text_records(Path(args.text_jsonl), profile, args.min_records)
    rng = random.Random(args.seed)
    version_dir = Path(args.output_root)
    templates_root = Path(args.templates_root)
    index = read_json(templates_root / "index.json")
    clean_version_dir(version_dir)

    all_category_plan = []
    all_manifest = []
    for folder, category, category_cn in category_dirs_from_index(index):
        cat_dir = version_dir / folder
        for sub in ["html", "images", "labels", "metadata", "reports"]:
            (cat_dir / sub).mkdir(parents=True, exist_ok=True)
        cat_templates = [item for item in index["templates"] if item["folder"] == folder]
        html_manifest = []
        for item in sorted(cat_templates, key=lambda row: row["variant"]):
            tpath = Path(item["path"])
            if not tpath.exists():
                # index paths are stored relative to project root; fall back to
                # resolving against the templates-root so it works from any CWD.
                tpath = templates_root / item["folder"] / tpath.name
            template = read_json(tpath)
            variant = int(template["variant"])
            doc_id = f"{folder[:2]}_{category}_vertical_tree_{variant:02d}"
            sampler = TextSampler(records, rng)
            id_by_element = {str(element.get("id")): f"{doc_id}_b{idx:04d}" for idx, element in enumerate(template["elements"], 1) if element.get("id")}
            html_elements = [html_element(doc_id, idx, element, sampler, id_by_element) for idx, element in enumerate(template["elements"], 1)]
            html_text = render_html(profile, template, doc_id, html_elements)
            html_path = cat_dir / "html" / f"{doc_id}.html"
            html_path.write_text(html_text, encoding="utf-8")
            page = template["page"]
            manifest_item = {
                "document_id": doc_id,
                "category": category,
                "category_cn": category_cn,
                "variant": variant,
                "layout_name": template["template_id"],
                "template_type": category,
                "template_name_cn": template["template_name_cn"],
                "layout_family": template["layout_family"],
                "design_prompt": template["design_prompt"],
                "template_json": str(Path(item["path"])),
                "title": category_cn,
                "doc_no": f"MN-V3-{folder[:2]}-{variant:02d}",
                "date": "2026-07-02",
                "rows": None,
                "columns": None,
                "source_records": [],
                "generator": "mongolian_vertical_json_tree_v3",
                "page_width": int(page["width"]),
                "page_height": int(page["height"]),
                "tight_crop": bool(page.get("tight_crop", True)),
            }
            html_manifest.append(manifest_item)
            all_manifest.append({**manifest_item, "folder": folder})
        write_json(cat_dir / "metadata" / "html_manifest.json", html_manifest)
        write_json(cat_dir / "metadata" / "category_plan.json", {"category": category, "category_cn": category_cn, "samples": len(html_manifest)})
        write_json(
            cat_dir / "metadata" / "mongolian_vertical_template_spec.json",
            {
                "category": category,
                "category_cn": category_cn,
                "layout_family": "json_structure_tree_v3",
                "templates": [
                    {
                        "template_id": item["template_id"],
                        "variant": item["variant"],
                        "template_name_cn": item["template_name_cn"],
                        "layout_family": item["layout_family"],
                        "path": item["path"],
                    }
                    for item in sorted(cat_templates, key=lambda row: row["variant"])
                ],
            },
        )
        all_category_plan.append({"category": category, "category_cn": category_cn, "samples": len(html_manifest), "folder": folder})

    write_json(version_dir / "metadata" / "category_plan.json", all_category_plan)
    write_json(version_dir / "metadata" / "html_manifest.json", all_manifest)
    template_version = template_version_label(index)
    write_json(version_dir / "metadata" / template_index_filename(index), index)
    readme = (
        f"# {args.version_name}\n\n"
        f"本目录是传统蒙古文 JSON 结构树驱动版式（模板 {template_version}）。当前包含 12 类，每类 6 张，共 72 张。\n\n"
        "核心生成方式：每一类使用 6 套独立 JSON 结构树。"
        "每个 JSON 文件包含完整页面尺寸、版式说明、元素坐标、标签类型和文本填充策略。\n\n"
        f"模板库：`{templates_root}`\n"
    )
    (version_dir / "README.md").write_text(readme, encoding="utf-8")

    print(json.dumps({"version_dir": str(version_dir), "categories": len(all_category_plan), "html": len(all_manifest)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
