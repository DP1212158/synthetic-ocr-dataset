#!/usr/bin/env python3
"""Run PaddleX PP-DocLayout on a delivery version and cache layout regions.

This script is intentionally side-effect-light: it does not modify labels.
It writes one normalized JSON file per image under reports/pp_doclayout by
default. The companion script can consume these cached regions to propose or
write an improved reading order.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(p for p in version_dir.iterdir() if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit())


def image_for_label(label_path: Path) -> Path:
    image_dir = label_path.parents[1] / "images"
    for suffix in IMAGE_SUFFIXES:
        candidate = image_dir / f"{label_path.stem}{suffix}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"no image found for {label_path}")


def iter_label_image_pairs(version_dir: Path) -> list[tuple[Path, Path, str]]:
    pairs: list[tuple[Path, Path, str]] = []
    for cat_dir in category_dirs(version_dir):
        label_dir = cat_dir / "labels"
        if not label_dir.exists():
            continue
        for label_path in sorted(label_dir.glob("*.json")):
            pairs.append((label_path, image_for_label(label_path), cat_dir.name))
    return pairs


def result_to_dict(result: Any, image_path: Path) -> dict[str, Any]:
    """Normalize a PaddleX result object into a stable dict.

    PaddleX result objects have changed shape across minor versions. The most
    stable public path is save_to_json(), so we use that first and fall back to
    common object/dict attributes when needed.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "result.json"
        if hasattr(result, "save_to_json"):
            result.save_to_json(save_path=str(out))
            if out.exists():
                payload = read_json(out)
                if isinstance(payload, dict):
                    return payload

    if isinstance(result, dict):
        return result
    for attr in ("res", "json", "data"):
        value = getattr(result, attr, None)
        if isinstance(value, dict):
            return value
        if callable(value):
            try:
                called = value()
            except TypeError:
                called = None
            if isinstance(called, dict):
                return called
    raise TypeError(f"unsupported PaddleX result object for {image_path}: {type(result)!r}")


def normalize_boxes(raw: dict[str, Any]) -> list[dict[str, Any]]:
    res = raw.get("res") if isinstance(raw.get("res"), dict) else raw
    boxes = res.get("boxes", []) if isinstance(res, dict) else []
    normalized: list[dict[str, Any]] = []
    for idx, box in enumerate(boxes):
        if not isinstance(box, dict):
            continue
        coord = box.get("coordinate") or box.get("bbox") or box.get("box")
        if not isinstance(coord, (list, tuple)) or len(coord) < 4:
            continue
        try:
            x1, y1, x2, y2 = [float(v) for v in coord[:4]]
        except (TypeError, ValueError):
            continue
        if x2 <= x1 or y2 <= y1:
            continue
        normalized.append(
            {
                "id": f"pp_{idx:03d}",
                "cls_id": box.get("cls_id"),
                "label": str(box.get("label") or box.get("class_name") or "unknown"),
                "score": float(box.get("score", 0.0) or 0.0),
                "coordinate": [x1, y1, x2, y2],
            }
        )
    return normalized


def create_pp_model(model_name: str, model_dir: str | None, device: str):
    try:
        from paddlex import create_model
    except Exception as exc:  # pragma: no cover - depends on local env
        raise RuntimeError(
            "PaddleX is not installed. Install it first, for example: "
            "python -m pip install 'paddlex[ocr]' paddlepaddle -i https://www.paddlepaddle.org.cn/packages/stable/cpu/"
        ) from exc

    kwargs: dict[str, Any] = {"model_name": model_name, "device": device}
    if model_dir:
        kwargs["model_dir"] = model_dir
    return create_model(**kwargs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True, help="VL version directory, e.g. .../VL4")
    parser.add_argument("--output-dir", help="Cache dir. Defaults to VERSION/reports/pp_doclayout")
    parser.add_argument("--model-name", default="PP-DocLayout-L")
    parser.add_argument("--model-dir", help="Optional local PaddleX model dir")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0, help="Debug limit; 0 means all")
    parser.add_argument("--force", action="store_true", help="Re-run images with existing cache")
    parser.add_argument(
        "--model-source",
        default=os.environ.get("PADDLE_PDX_MODEL_SOURCE", "bos"),
        choices=["huggingface", "aistudio", "bos", "modelscope"],
    )
    args = parser.parse_args()

    version_dir = Path(args.version_dir)
    output_dir = Path(args.output_dir) if args.output_dir else version_dir / "reports" / "pp_doclayout"
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", args.model_source)

    pairs = iter_label_image_pairs(version_dir)
    if args.limit:
        pairs = pairs[: args.limit]
    if not pairs:
        raise SystemExit(f"no labels found under {version_dir}")

    try:
        model = create_pp_model(args.model_name, args.model_dir, args.device)
    except Exception as exc:
        print(f"[pp-doclayout] failed to initialize model: {exc}", file=sys.stderr)
        return 2

    done = 0
    skipped = 0
    failures: list[dict[str, str]] = []
    for label_path, image_path, category in pairs:
        rel = label_path.relative_to(version_dir)
        out_json = output_dir / category / f"{label_path.stem}.json"
        if out_json.exists() and not args.force:
            skipped += 1
            continue
        try:
            output = model.predict(
                str(image_path),
                batch_size=args.batch_size,
                threshold=args.threshold,
                layout_nms=True,
            )
            results = list(output)
            if not results:
                raise RuntimeError("empty PaddleX prediction result")
            raw = result_to_dict(results[0], image_path)
            boxes = normalize_boxes(raw)
            payload = {
                "image": str(image_path),
                "label": str(label_path),
                "category_dir": category,
                "model_name": args.model_name,
                "device": args.device,
                "threshold": args.threshold,
                "boxes": boxes,
                "raw": raw,
            }
            write_json(out_json, payload)
            done += 1
            print(f"[pp-doclayout] {rel}: {len(boxes)} boxes")
        except Exception as exc:  # pragma: no cover - depends on local model/runtime
            failures.append({"label": str(label_path), "image": str(image_path), "error": str(exc)})
            print(f"[pp-doclayout] failed {rel}: {exc}", file=sys.stderr)

    summary = {
        "version_dir": str(version_dir),
        "output_dir": str(output_dir),
        "model_name": args.model_name,
        "device": args.device,
        "threshold": args.threshold,
        "total_requested": len(pairs),
        "processed": done,
        "skipped_existing": skipped,
        "failed": len(failures),
        "failures": failures,
        "pass": not failures and (done + skipped) == len(pairs),
    }
    write_json(output_dir / "pp_doclayout_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
