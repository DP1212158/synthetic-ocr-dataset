#!/usr/bin/env python3
"""Layout-quality QA — the checks that were missing and let real defects pass.

Covers three failure classes discovered in practice:
  1. Variant diversity — each category's N variants must be geometrically distinct
     (a whole category rendering "all the same" was previously undetected).
  2. Occlusion — parallel vertical text columns must not overlap and must keep a
     minimum horizontal gap (tight/overlapping columns previously passed QA).
  3. Fill — pages must not be near-empty; and no "big box holding short text"
     (large box + short source = visually bare but box-area coverage looked fine).

Two input modes:
  --mongolian-templates <dir>   full checks on mongolian_vertical_templates_v4
  --version-dir <lang version>  universal rendered-label checks (diversity + no
                                text-box overlap) for any language/version.

Exit code 1 when any hard check fails (usable as a pipeline gate).
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
from pathlib import Path

FONT_PX = {"title": 34, "subtitle": 24, "body": 20, "small": 16, "tiny": 13}
FORM_FOLDER_HINT = "复杂表单"


def font_px(cls: str) -> int:
    for k, v in FONT_PX.items():
        if k in (cls or ""):
            return v
    return 20


def y_overlap(a, b) -> float:
    return max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))


def box_sig(elements) -> str:
    boxes = sorted(
        (e.get("kind"), *[round(e["box"][k]) for k in "xywh"])
        for e in elements
        if e.get("box")
    )
    return hashlib.md5(str(boxes).encode()).hexdigest()[:10]


def est_chars(box, fpx, src, tx):
    cols = max(1, int(box["w"] // (fpx * 1.4)))
    cpc = max(1, int(box["h"] // fpx))
    cap = cols * cpc
    if src == "fill":
        return 0.85 * cap, cap
    if src == "blank":
        return 0.0, cap
    if src == "literal":
        return float(len(tx.get("value", ""))), cap
    return float(min(tx.get("max_chars") or 40, cap)), cap


def check_mongolian_template(path: str):
    """Return (sig, problems:list[str], stats:dict) for one v4 template."""
    t = json.loads(Path(path).read_text(encoding="utf-8"))
    W, H = t["page"]["width"], t["page"]["height"]
    area = float(W * H)
    is_form = FORM_FOLDER_HINT in (t.get("folder", "") + t.get("category_cn", ""))
    gap_floor = 4 if is_form else 12

    text_boxes = []
    filled_area = 0.0
    eff_fill = 0.0
    big_empty = []
    for e in t.get("elements", []):
        if e.get("kind") != "text" or not e.get("box"):
            continue
        tx = e.get("text", {}) or {}
        src = tx.get("source", "fill")
        if src == "blank":
            continue
        b = e["box"]
        fpx = font_px(e.get("class", ""))
        text_boxes.append((b["x"], b["y"], b["w"], b["h"], fpx))
        filled_area += b["w"] * b["h"]
        chars, cap = est_chars(b, fpx, src, tx)
        eff_fill += chars * (fpx * fpx * 0.55)
        # big box holding short text -> visually bare
        if (b["w"] * b["h"]) / area > 0.06 and src in {"short", "title", "question", "safe_fragment"}:
            if cap > 0 and chars / cap < 0.30:
                big_empty.append(e.get("id"))

    cov = filled_area / area
    problems = []
    # occlusion: overlaps + min parallel-column gap
    min_gap = 1e9
    for i in range(len(text_boxes)):
        for j in range(i + 1, len(text_boxes)):
            a, bb = text_boxes[i], text_boxes[j]
            if y_overlap(a, bb) < 0.4 * min(a[3], bb[3]):
                continue
            gap = (bb[0] - (a[0] + a[2])) if a[0] < bb[0] else (a[0] - (bb[0] + bb[2]))
            if gap < 0:
                problems.append("text_overlap")
            min_gap = min(min_gap, gap)
    if min_gap < gap_floor and min_gap < 1e9:
        problems.append(f"tight_columns(gap={min_gap}<{gap_floor})")
    if cov < 0.30:
        problems.append(f"sparse(cov={cov:.2f})")
    if big_empty:
        problems.append(f"big_empty_boxes({len(big_empty)})")
    return box_sig(t.get("elements", [])), sorted(set(problems)), {"cov": round(cov, 3), "min_gap": None if min_gap > 1e8 else min_gap, "eff_fill": round(eff_fill / area, 3)}


def run_mongolian_templates(root: str) -> dict:
    cats = sorted(d for d in glob.glob(os.path.join(root, "*")) if os.path.isdir(d) and os.path.basename(d)[:2].isdigit())
    result = {"mode": "mongolian_templates", "root": root, "categories": {}, "pass": True}
    for cat in cats:
        name = os.path.basename(cat)
        files = sorted(glob.glob(os.path.join(cat, "*.json")))
        sigs = []
        per_file = {}
        cat_problems = []
        for f in files:
            sig, probs, stats = check_mongolian_template(f)
            sigs.append(sig)
            bn = os.path.basename(f)
            per_file[bn] = {"problems": probs, **stats}
            if probs:
                cat_problems.append(bn)
        distinct = len(set(sigs))
        diversity_ok = distinct == len(files) and len(files) > 0
        cat_ok = diversity_ok and not cat_problems
        result["categories"][name] = {
            "variants": len(files),
            "distinct_layouts": distinct,
            "diversity_ok": diversity_ok,
            "files_with_problems": cat_problems,
            "detail": per_file,
            "pass": cat_ok,
        }
        result["pass"] = result["pass"] and cat_ok
    return result


def category_dirs(version_dir: Path):
    return sorted(p for p in version_dir.iterdir() if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit())


def rendered_label_sig(label: dict) -> str:
    coords = []
    for b in label.get("blocks", []):
        c = b.get("coordinates") or {}
        if c and b.get("is_text", True) is not False:
            coords.append((round(c["x_min"] / 8), round(c["y_min"] / 8), round(c["x_max"] / 8), round(c["y_max"] / 8)))
    return hashlib.md5(str(sorted(coords)).encode()).hexdigest()[:10]


def rendered_overlaps(label: dict) -> int:
    boxes = []
    for b in label.get("blocks", []):
        c = b.get("coordinates") or {}
        if not c or b.get("is_text", True) is False:
            continue
        if not str(b.get("block_content") or "").strip():
            continue
        boxes.append((float(c["x_min"]), float(c["y_min"]), float(c["x_max"]), float(c["y_max"])))
    n = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
            iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
            inter = ix * iy
            if inter <= 0:
                continue
            smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
            if smaller > 0 and inter / smaller > 0.25:
                n += 1
    return n


def run_version_dir(version_dir: str) -> dict:
    vd = Path(version_dir)
    result = {"mode": "version_dir", "version_dir": version_dir, "categories": {}, "pass": True}
    for cat in category_dirs(vd):
        labels = sorted((cat / "labels").glob("*.json"))
        sigs = []
        overlap_docs = []
        for lb in labels:
            d = json.loads(lb.read_text(encoding="utf-8"))
            sigs.append(rendered_label_sig(d))
            if rendered_overlaps(d) > 0:
                overlap_docs.append(lb.stem)
        distinct = len(set(sigs))
        diversity_ok = distinct == len(labels) and len(labels) > 0
        cat_ok = diversity_ok and not overlap_docs
        result["categories"][cat.name] = {
            "variants": len(labels),
            "distinct_layouts": distinct,
            "diversity_ok": diversity_ok,
            "overlap_docs": overlap_docs,
            "pass": cat_ok,
        }
        result["pass"] = result["pass"] and cat_ok
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mongolian-templates", help="dir of mongolian_vertical_templates_v4")
    ap.add_argument("--version-dir", help="rendered version dir of one language")
    ap.add_argument("--output-json", help="optional path to dump full report json")
    args = ap.parse_args()
    if not args.mongolian_templates and not args.version_dir:
        ap.error("need --mongolian-templates or --version-dir")

    report = run_mongolian_templates(args.mongolian_templates) if args.mongolian_templates else run_version_dir(args.version_dir)
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[qa_layout_quality] mode={report['mode']} pass={report['pass']}")
    for name, c in report["categories"].items():
        flag = "OK" if c["pass"] else "FAIL"
        extra = ""
        if not c["diversity_ok"]:
            extra += f" distinct={c['distinct_layouts']}/{c['variants']}"
        if c.get("files_with_problems"):
            extra += f" problems={c['files_with_problems']}"
        if c.get("overlap_docs"):
            extra += f" overlaps={c['overlap_docs']}"
        print(f"  {name}: {flag}{extra}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
