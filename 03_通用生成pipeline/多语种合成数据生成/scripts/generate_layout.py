#!/usr/bin/env python3
"""Unified ordered-layout generator (schema v3, one file per category).

- One generator for all 12 categories, all writing directions (ltr / rtl /
  vertical-lr). Replaces the four v2 generators + the Mongolian vertical
  generator.
- Reading order is AUTHORED explicitly in each template block (``reading_order``)
  and emitted verbatim as ``data-flow-rank``; the renderer (strict mode) uses it
  directly, with no visual re-sort. Direction only mirrors visual placement.
- Block-level Chinese bilingual mixing: ~50% of documents become ``mixed`` with a
  page CJK ratio in [0.10, 0.30], sourced from the per-category Chinese bank.

One invocation generates every category for one language into ``--output-root``.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

from synthetic_text_utils import (
    cleanse_text,
    load_language_profile,
    read_text_records,
    record_text,
    record_title,
    safe_fragment,
    select_span,
)

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

# Real image assets used to fill image/photo/figure regions (instead of a gray
# placeholder). Chosen randomly per block so every language/category differs.
IMAGE_ASSET_DIR = Path(__file__).resolve().parents[3] / "04_共享图片资产"
IMAGE_ASSET_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def load_image_assets() -> list[str]:
    if not IMAGE_ASSET_DIR.exists():
        return []
    return sorted(
        str(p.resolve())
        for p in IMAGE_ASSET_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_ASSET_EXTS
    )


def select_variants(category: dict[str, Any], writing_mode_wanted: str, rng: random.Random) -> list[dict[str, Any]]:
    """Per category: keep all portrait variants + a random 3 of the landscape pool.

    Orientation refers to the rendered image aspect (portrait = taller than wide,
    landscape = wider than tall); text stays in the language's natural direction.
    Falls back to all matching variants when no portrait variants are defined.
    """
    vs = [v for v in category["variants"] if v.get("writing_mode", "horizontal-tb") == writing_mode_wanted]
    portrait = [v for v in vs if v.get("orientation") == "portrait"]
    landscape = [v for v in vs if v.get("orientation") != "portrait"]
    if portrait and len(landscape) > 3:
        landscape = rng.sample(landscape, 3)
    return landscape + portrait


NON_OCR_LABELS = {
    "image", "photo", "figure", "answer_area", "rule", "divider",
    "decorative_rule", "table_structure", "visual", "seal", "stamp",
}

# role -> Chinese bank key
ZH_ROLE_MAP = {
    "title": "document_title", "document_title": "document_title",
    "subtitle": "section_title", "document_subtitle": "section_title",
    "section_title": "section_title", "heading": "section_title",
    "caption": "caption", "figure_caption": "caption", "table_caption": "caption",
    "metadata": "metadata", "page_number": "metadata",
    "list_item": "list_item",
    "field_label": "field_label", "field_value": "field_value",
    "question": "question",
}

# role -> css font class
ROLE_CLASS = {
    "title": "v3-title", "document_title": "v3-title",
    "subtitle": "v3-subtitle", "document_subtitle": "v3-subtitle",
    "section_title": "v3-heading", "heading": "v3-heading",
    "paragraph": "v3-body", "body": "v3-body", "quote": "v3-body",
    "caption": "v3-small", "note": "v3-small", "metadata": "v3-small",
    "list_item": "v3-small", "page_number": "v3-tiny", "footer": "v3-tiny",
    "field_label": "v3-small", "field_value": "v3-body", "question": "v3-body",
}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(text: str) -> str:
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


# --------------------------------------------------------------------------- #
# Text sampling
# --------------------------------------------------------------------------- #
class TextSampler:
    def __init__(self, records: list[dict[str, Any]], rng: random.Random):
        self.records = records
        self.rng = rng

    def _long(self, min_len: int, max_len: int) -> str:
        pool = [r for r in self.records if len(r["text"]) >= min_len] or self.records
        for _ in range(12):
            t = select_span(self.rng.choice(pool)["text"], self.rng, min_len, max_len)
            if len(t) >= min_len:
                return t
        return cleanse_text(self.rng.choice(self.records)["text"])[:max_len]

    def sample(self, spec: dict[str, Any]) -> str:
        source = str(spec.get("source", "paragraph"))
        lo = int(spec.get("min_chars", 20))
        hi = int(spec.get("max_chars", 90))
        if source == "blank":
            return ""
        if source == "literal":
            return str(spec.get("value", ""))
        if source == "safe_fragment":
            return safe_fragment(lo, hi)
        if source in ("title", "heading", "section_title"):
            return record_title(self.records, self.rng, lo, hi)
        if source in ("metadata", "list_item", "short", "field_value", "note", "caption"):
            return record_text(self.records, self.rng, lo, hi)
        if source == "question":
            return f"{self.rng.randint(1, 30)}. {record_text(self.records, self.rng, lo, hi)}"
        return self._long(lo, hi)


# --------------------------------------------------------------------------- #
# Chinese bilingual mixing (block level)
# --------------------------------------------------------------------------- #
ZH_PREF = [
    "document_title", "title", "section_title", "heading", "subtitle",
    "caption", "metadata", "list_item", "field_label", "note", "paragraph", "body",
]


def zh_text_for(role: str, target_len: int, bank_cat: dict[str, Any], rng: random.Random) -> str | None:
    key = ZH_ROLE_MAP.get(role, "paragraph")
    if key in ("paragraph",) or role in ("paragraph", "body", "quote"):
        sents = bank_cat.get("paragraph_sentences") or []
        if not sents:
            return None
        out = ""
        guard = 0
        while len(out) < max(target_len, 12) and guard < 40:
            out += rng.choice(sents)
            guard += 1
        return out[: max(target_len, 12)]
    pool = bank_cat.get(key) or bank_cat.get("section_title") or []
    if pool:
        return str(rng.choice(pool))
    sents = bank_cat.get("paragraph_sentences") or []
    return (rng.choice(sents)[: max(target_len, 8)]) if sents else None


def apply_chinese_mix(blocks: list[dict[str, Any]], category_id: str, rng: random.Random,
                      mix_ratio: float, bank: dict[str, Any]) -> tuple[str, float]:
    """Decide pure/mixed; convert a subset of blocks to Chinese in [0.10,0.30]."""
    bank_cat = (bank.get("categories") or {}).get(category_id)
    ocr = [b for b in blocks if b["_orderable"] and b["_text"]]
    if not bank_cat or not ocr or rng.random() >= mix_ratio:
        return "pure", 0.0
    base_total = sum(len(b["_text"]) for b in ocr)
    if base_total == 0:
        return "pure", 0.0
    target_r = rng.uniform(0.12, 0.26)
    hard = 0.30
    ordered = sorted(ocr, key=lambda b: (ZH_PREF.index(b["role"]) if b["role"] in ZH_PREF else 99, rng.random()))
    picks: list[tuple[dict[str, Any], str]] = []
    cur_total = base_total
    cur_cjk = 0
    for b in ordered:
        if cur_cjk / cur_total >= target_r:
            break
        lf = len(b["_text"])
        zt = zh_text_for(b["role"], lf, bank_cat, rng)
        if not zt:
            continue
        lz = len(zt)
        if (cur_cjk + lz) / (cur_total - lf + lz) > hard:
            if cur_cjk / cur_total >= 0.10:
                continue  # already in band; don't overshoot the 0.30 cap
            room = int((hard * (cur_total - lf) - cur_cjk) / (1 - hard))  # trim zt to fit under cap
            if room >= 8:
                zt = zt[:room]
                lz = len(zt)
            else:
                continue
        picks.append((b, zt))
        cur_total = cur_total - lf + lz
        cur_cjk += lz
    ratio = cur_cjk / max(cur_total, 1)
    # Guarantee mixed documents land strictly in [0.10, 0.30]; otherwise stay pure.
    if not picks or not (0.10 <= ratio <= 0.30):
        return "pure", 0.0
    for b, zt in picks:
        b["_text"] = zt
        b["_zh"] = True
    return "mixed", round(ratio, 4)


# --------------------------------------------------------------------------- #
# CSS
# --------------------------------------------------------------------------- #
def base_css(profile: dict[str, Any], tokens: dict[str, Any], writing_mode: str) -> str:
    font = profile.get("font_family", "sans-serif")
    direction = profile.get("css_direction", profile.get("writing_direction", "ltr"))
    if direction not in ("ltr", "rtl"):
        direction = "ltr"
    text_align = profile.get("css_text_align", "right" if direction == "rtl" else "left")
    paper = tokens.get("paper", "#fbf8ee")
    ink = tokens.get("ink", "#161616")
    line = tokens.get("line", "#222")
    accent = tokens.get("accent", "#8a2f2f")
    accent2 = tokens.get("accent2", accent)
    band_ink = tokens.get("band_ink", "#f7f2e6")
    vertical = writing_mode == "vertical-lr"
    vtext_css = (
        """
    .v3-blk.text { writing-mode: vertical-lr; text-orientation: mixed; }
    .v3region.cols { align-items: flex-start; }
    """
        if vertical else ""
    )
    return f"""
    * {{ box-sizing: border-box; }}
    html, body {{ margin:0; padding:0; background:#d9dde2; }}
    body {{ font-family:{font}; color:{ink}; direction:{direction}; text-align:{text_align}; unicode-bidi: plaintext; }}
    .page {{ margin:0 auto; background:{paper}; position:relative; overflow:hidden; padding:48px; }}
    .v3region {{ margin-bottom:20px; }}
    .v3region.stack > .v3-blk {{ margin-bottom:12px; }}
    .v3col > .v3-blk {{ margin-bottom:12px; }}
    .v3-blk {{ overflow:visible; }}
    .v3-blk.zh {{ font-family:"Noto Sans SC","Noto Sans CJK SC",{font}; }}
    .v3-title {{ font-size:40px; line-height:1.32; font-weight:900; }}
    .v3-subtitle {{ font-size:24px; line-height:1.34; font-weight:700; }}
    .v3-heading {{ font-size:22px; line-height:1.34; font-weight:800; }}
    .v3-body {{ font-size:19px; line-height:1.5; }}
    .v3-small {{ font-size:15px; line-height:1.4; color:#3a3a3a; }}
    .v3-tiny {{ font-size:13px; line-height:1.3; color:#555; }}
    .v3-image {{ background:repeating-linear-gradient(135deg,#d8d2c2,#d8d2c2 14px,#efe9d9 14px,#efe9d9 28px); border:2px solid #303030; }}
    .v3-rule {{ border-top:2px solid {line}; height:0; }}
    .v3-answer {{ border:1.4px solid {line}; background:rgba(255,255,255,.5); }}

    /* --- refined visual vocabulary --- */
    .page.framed {{ border:3px double {accent}; }}
    .page.framed-inset::before {{ content:""; position:absolute; inset:22px; border:1.5px solid {line}; pointer-events:none; }}
    .accent {{ color:{accent}; }}
    .v3-title.accent, .v3-heading.accent, .v3-subtitle.accent {{ color:{accent}; }}
    /* header / masthead band */
    .v3region.band {{ background:{accent}; color:{band_ink}; padding:14px 20px; border-radius:2px; margin-bottom:18px; }}
    .v3region.band .v3-blk {{ color:{band_ink}; }}
    .v3region.band .v3-title {{ letter-spacing:1px; }}
    .v3region.softband {{ background:rgba(138,47,47,.08); border-left:5px solid {accent}; padding:12px 16px; }}
    /* card / framed region */
    .v3region.card {{ border:1.4px solid {line}; background:rgba(255,255,255,.5); padding:16px; border-radius:3px; }}
    .v3region.framed {{ border:2px solid {accent}; padding:16px; }}
    /* footer strip */
    .v3region.footer {{ border-top:1.5px solid {line}; padding-top:8px; margin-top:14px; color:#4a4a4a; }}
    /* section divider */
    .v3-divider {{ border:0; border-top:2px solid {accent}; height:0; opacity:.8; }}
    .v3-divider.thin {{ border-top:1px solid {line}; opacity:.6; }}
    /* form field rows */
    .v3-field-label {{ font-weight:800; color:#2a2a2a; }}
    .v3-field-value {{ border-bottom:1.4px solid {line}; padding-bottom:2px; min-height:1.4em; }}
    /* seal / stamp */
    .v3-seal {{ border:3px solid {accent}; color:{accent}; border-radius:50%; display:flex; align-items:center; justify-content:center; text-align:center; font-weight:800; opacity:.82; transform:rotate(-8deg); line-height:1.1; }}
    /* badge / tag */
    .v3-badge {{ display:inline-block; background:{accent}; color:{band_ink}; padding:3px 10px; border-radius:10px; font-size:13px; font-weight:700; }}
    /* table grid (region layout=grid) */
    .v3region.grid {{ border:1.4px solid {line}; }}
    .v3region.grid .v3col {{ border-right:1px solid {line}; }}
    .v3region.grid .v3col:last-child {{ border-right:0; }}
    .v3region.grid .v3-blk {{ border-bottom:1px solid {line}; padding:6px 8px; margin:0; }}
    .v3region.grid .v3-blk:last-child {{ border-bottom:0; }}
    .v3region.grid .v3-blk.th {{ background:rgba(138,47,47,.14); font-weight:800; }}
    .v3-title {{ margin:0 0 6px; }}
    .v3-heading {{ margin:10px 0 4px; }}
    {vtext_css}
    """


# --------------------------------------------------------------------------- #
# Block / region rendering
# --------------------------------------------------------------------------- #
def render_block(blk: dict[str, Any], direction: str) -> str:
    label = blk["label"]
    role = blk.get("role", label)
    block_id = blk["_id"]
    if not blk["_orderable"]:
        if label in ("image", "photo", "figure"):
            h = int(blk.get("height", 300))
            style = f"height:{h}px;"
            if blk.get("_asset"):
                style += f"background-image:url('file://{quote(blk['_asset'])}');background-size:cover;background-position:center;background-repeat:no-repeat;"
            return (
                f'<div data-block-id="{block_id}" data-label="{esc(label)}" data-is-text="false" '
                f'data-ocr-orderable="false" class="v3-blk v3-image" style="{style}" data-caption-anchor="1"></div>'
            )
        if label in ("seal", "stamp"):
            sz = int(blk.get("size", blk.get("height", 118)))
            fs = max(11, sz // 7)
            txt = esc(str(blk.get("seal_text", "")))
            return (
                f'<div data-label="{esc(label)}" data-is-text="false" aria-hidden="true" '
                f'class="v3-blk v3-seal" style="width:{sz}px;height:{sz}px;font-size:{fs}px;margin:6px 0;">{txt}</div>'
            )
        if label in ("divider", "decorative_rule"):
            thin = " thin" if blk.get("thin") else ""
            return f'<div data-label="{esc(label)}" data-is-text="false" aria-hidden="true" class="v3-blk v3-divider{thin}" style="height:0;"></div>'
        if label == "rule":
            return f'<div data-label="rule" data-is-text="false" aria-hidden="true" class="v3-blk v3-rule" style="height:0;"></div>'
        h = int(blk.get("height", 120))
        return (
            f'<div data-block-id="{block_id}" data-label="{esc(label)}" data-is-text="false" '
            f'data-ocr-orderable="false" class="v3-blk v3-answer" style="height:{h}px;"></div>'
        )
    role_cls = ROLE_CLASS.get(role, "v3-body")
    extra_cls = ""
    if blk.get("accent"):
        extra_cls += " accent"
    if role == "field_label" or label == "field_label":
        extra_cls += " v3-field-label"
    if role == "field_value" or label == "field_value":
        extra_cls += " v3-field-value"
    if blk.get("th"):
        extra_cls += " th"
    zh_cls = " zh" if blk.get("_zh") else ""
    cap = f' data-caption-of="{blk["_caption_of"]}"' if blk.get("_caption_of") else ""
    flow_path = f'{esc(blk["region"])}/{esc(role)}/{blk["reading_order"]}'
    return (
        f'<div data-block-id="{block_id}" data-label="{esc(label)}" '
        f'data-flow-path="{flow_path}" '
        f'data-flow-rank="{blk["reading_order"]}" data-flow-region="{esc(blk["region"])}" '
        f'data-flow-container="{esc(blk["region"])}" data-flow-role="{esc(role)}" '
        f'data-flow-direction="{direction}" data-ocr-orderable="true"{cap} '
        f'class="v3-blk text {role_cls}{extra_cls}{zh_cls}">{esc(blk["_text"])}</div>'
    )


def render_region(region: dict[str, Any], blocks: list[dict[str, Any]], direction: str) -> str:
    layout = region.get("layout", "stack")
    visual = str(region.get("visual") or region.get("style") or "")
    vcls = f" {visual}" if visual in {"band", "card", "framed", "footer", "softband"} else ""
    region_blocks = [b for b in blocks if b["region"] == region["id"]]
    if layout in ("columns", "grid"):
        gridcls = " grid" if layout == "grid" else ""
        ncols = int(region.get("columns", 1))
        ratios = region.get("column_ratios")
        gap = int(region.get("gap", 0 if layout == "grid" else 18))
        cols: dict[int, list[dict[str, Any]]] = {i: [] for i in range(ncols)}
        for b in region_blocks:
            cols[min(int(b.get("column", 0)), ncols - 1)].append(b)
        col_divs = []
        for i in range(ncols):
            inner = "".join(render_block(b, direction) for b in sorted(cols[i], key=lambda x: x["reading_order"] if x["_orderable"] else 10**9))
            flex = ratios[i] if ratios and i < len(ratios) else 1
            col_divs.append(f'<div class="v3col" style="flex:{flex}">{inner}</div>')
        # The flex container inherits `direction:rtl` from <body>, which already
        # lays row items out right-to-left for RTL languages (so column 0 ends up
        # on the right and is read first). Using flex-direction:row-reverse here
        # would double-reverse it back to left-to-right — the RTL bug. Always use
        # plain "row" and let the container direction handle column progression.
        return f'<section class="v3region cols{gridcls}{vcls}" style="display:flex;gap:{gap}px;flex-direction:row">{"".join(col_divs)}</section>'
    inner = "".join(render_block(b, direction) for b in region_blocks)
    return f'<section class="v3region stack{vcls}">{inner}</section>'


# --------------------------------------------------------------------------- #
# Document build
# --------------------------------------------------------------------------- #
def build_document(category: dict[str, Any], variant: dict[str, Any], profile: dict[str, Any],
                   sampler: TextSampler, rng: random.Random, mix_ratio: float,
                   bank: dict[str, Any], doc_id: str, assets: list[str]) -> tuple[str, dict[str, Any]]:
    direction = profile.get("css_direction", profile.get("writing_direction", "ltr"))
    if direction not in ("ltr", "rtl"):
        direction = "ltr"
    writing_mode = variant.get("writing_mode", "horizontal-tb")

    # materialize blocks (assign ids, sample text)
    blocks = [dict(b) for b in variant["blocks"]]
    last_target = None  # nearest caption-able anchor: image/figure block or table cell
    for idx, b in enumerate(blocks, 1):
        b["_id"] = f"{doc_id}_b{idx:04d}"
        b["role"] = b.get("role", b["label"])
        b["_orderable"] = bool(b.get("ocr_orderable", True)) and b["label"] not in NON_OCR_LABELS
        b["_zh"] = False
        b["_caption_of"] = None
        b["_asset"] = None
        is_caption = b["label"] in ("caption", "figure_caption", "table_caption")
        if b["_orderable"]:
            b["_text"] = cleanse_text(sampler.sample(b.get("text", {"source": "paragraph"})))
            if not b["_text"]:
                b["_text"] = safe_fragment(4, 20)
        else:
            b["_text"] = ""
            if b["label"] in ("image", "photo", "figure"):
                last_target = b["_id"]
                if assets:
                    b["_asset"] = rng.choice(assets)
        # table cells are a valid caption target too ("表 X 说明")
        if not is_caption and b.get("region") == "table":
            last_target = b["_id"]
        if is_caption and last_target:
            b["_caption_of"] = last_target

    mode, cjk_ratio = apply_chinese_mix(blocks, category["category_id"], rng, mix_ratio, bank)

    page = variant["page"]
    width, height = int(page["width"]), int(page["height"])
    css = base_css(profile, variant.get("style_tokens", {}), writing_mode)
    regions = sorted(variant["regions"], key=lambda r: r.get("order", 999))
    body = "".join(render_region(r, blocks, direction) for r in regions)
    frame = page.get("frame")
    page_cls = "page"
    if frame in (True, "framed", "border"):
        page_cls += " framed"
    elif frame in ("inset", "framed-inset"):
        page_cls += " framed-inset"
    elif frame in ("both", "framed-both"):
        page_cls += " framed framed-inset"
    html = (
        f'<!doctype html><html lang="{esc(profile.get("html_lang","und"))}" dir="{direction}">'
        f"<head><meta charset=\"utf-8\"><title>{esc(category['category_cn'])} {esc(doc_id)}</title>"
        f"<style>{css}</style></head>"
        f'<body><main class="{page_cls}" style="width:{width}px;min-height:{height}px">{body}</main></body></html>'
    )
    n_ocr = sum(1 for b in blocks if b["_orderable"])
    manifest = {
        "document_id": doc_id,
        "category": category["category_id"],
        "category_cn": category["category_cn"],
        "template_type": category["category_id"],
        "layout_name": variant["template_id"],
        "variant": variant["variant"],
        "page_width": width,
        "page_height": height,
        "tight_crop": bool(variant.get("tight_crop", True)),
        "preserve_full_page": bool(variant.get("preserve_full_page", False)),
        "generator": "layout_v3",
        "reading_order_mode": "template_strict",
        "language_mix_mode": mode,
        "target_cjk_ratio": cjk_ratio,
        "ocr_block_count": n_ocr,
        "title": category["category_cn"],
        "doc_no": doc_id,
        "date": "2026-07-11",
    }
    return html, manifest


def variants_for_direction(category: dict[str, Any], writing_mode_wanted: str) -> list[dict[str, Any]]:
    out = [v for v in category["variants"] if v.get("writing_mode", "horizontal-tb") == writing_mode_wanted]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--templates-dir", required=True)
    parser.add_argument("--text-jsonl", required=True)
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--version-name", default="VL11")
    parser.add_argument("--seed", type=int, default=2026071101)
    parser.add_argument("--min-records", type=int, default=30)
    parser.add_argument("--mix-ratio", type=float, default=0.5)
    parser.add_argument("--zh-bank", required=True)
    parser.add_argument("--only-category", default=None, help="limit to one category_id (pilot)")
    args = parser.parse_args()

    profile = load_language_profile(Path(args.language_profile))
    records = read_text_records(Path(args.text_jsonl), profile, args.min_records)
    bank = read_json(Path(args.zh_bank)) if Path(args.zh_bank).exists() else {"categories": {}}
    rng = random.Random(args.seed)
    assets = load_image_assets()

    wm = "vertical-lr" if str(profile.get("css_writing_mode", "")).startswith("vertical") else "horizontal-tb"

    version_dir = Path(args.output_root)
    if version_dir.exists():
        for child in version_dir.iterdir():
            if child.is_dir() and child.name[:2].isdigit():
                shutil.rmtree(child)
    (version_dir / "reports").mkdir(parents=True, exist_ok=True)

    template_files = sorted(Path(args.templates_dir).glob("[0-9][0-9]_*.layout.json"))
    produced = 0
    for tf in template_files:
        category = read_json(tf)
        if args.only_category and category["category_id"] != args.only_category:
            continue
        idx = int(category["category_index"])
        folder = f"{idx:02d}_{category['category_cn']}"
        sel_rng = random.Random(f"{args.seed}-{idx}-sel")
        variants = select_variants(category, wm, sel_rng)
        if not variants:
            continue
        cat_dir = version_dir / folder
        for sub in ("html", "images", "labels", "metadata", "reports"):
            (cat_dir / sub).mkdir(parents=True, exist_ok=True)
        html_manifest = []
        for variant in sorted(variants, key=lambda v: v["variant"]):
            doc_id = f"{idx:02d}_{category['category_id']}_v3_{int(variant['variant']):02d}"
            sampler = TextSampler(records, rng)
            html, manifest = build_document(category, variant, profile, sampler, rng, args.mix_ratio, bank, doc_id, assets)
            (cat_dir / "html" / f"{doc_id}.html").write_text(html, encoding="utf-8")
            html_manifest.append(manifest)
            produced += 1
        write_json(cat_dir / "metadata" / "html_manifest.json", html_manifest)

    print(json.dumps({"version_dir": str(version_dir), "documents": produced, "writing_mode": wm}, ensure_ascii=False))
    return 0 if produced else 2


if __name__ == "__main__":
    raise SystemExit(main())
