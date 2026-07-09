#!/usr/bin/env python3
"""Build a reusable synthetic text pool from existing verified label JSON files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from synthetic_text_utils import cleanse_text, load_language_profile, text_quality


def iter_strings(obj: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if key_l in {"text", "content", "block_content", "transcription", "value"} and isinstance(value, str):
                texts.append(value)
            else:
                texts.extend(iter_strings(value))
    elif isinstance(obj, list):
        for item in obj:
            texts.extend(iter_strings(item))
    return texts


def split_candidate_text(text: str, min_chars: int) -> list[str]:
    cleaned = cleanse_text(text)
    parts = re.split(r"[。！？；;|]\s*|\n+", cleaned)
    out = []
    for part in parts:
        part = cleanse_text(part)
        if len(part) >= min_chars:
            out.append(part)
    if not out and len(cleaned) >= min_chars:
        out.append(cleaned)
    return out


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label-roots", nargs="+", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--min-chars", type=int, default=45)
    parser.add_argument("--min-script-ratio", type=float)
    args = parser.parse_args()

    profile = load_language_profile(Path(args.language_profile))
    min_ratio = args.min_script_ratio if args.min_script_ratio is not None else float(profile["min_script_ratio"])
    records = []
    seen = set()

    for root_text in args.label_roots:
        root = Path(root_text)
        for json_path in sorted(root.glob("*.json")):
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for raw in iter_strings(data):
                for text in split_candidate_text(raw, args.min_chars):
                    quality = text_quality(text)
                    if quality["script_ratio"] < min_ratio:
                        continue
                    if quality["digit_ratio"] > float(profile.get("max_digit_ratio", 0.18)):
                        continue
                    residue_failed = False
                    for name in ["latin", "cjk", "cyrillic", "tibetan", "arabic", "mongolian", "hangul"]:
                        if quality.get(f"{name}_ratio", 0.0) > float(profile.get(f"max_{name}_ratio", 1.0)):
                            residue_failed = True
                            break
                    if residue_failed:
                        continue
                    if quality["word_count"] < 4:
                        continue
                    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
                    if digest in seen:
                        continue
                    seen.add(digest)
                    records.append(
                        {
                            "record_id": f"label_pool_{len(records)+1:05d}",
                            "language_code": profile["language_code"],
                            "language_name": profile["language_name"],
                            "script_note": profile["script_note"],
                            "source": "verified_local_labels",
                            "source_record_id": json_path.name,
                            "title": "",
                            "url": "",
                            "text": text,
                            "chars": len(text),
                            "target_script_ratio": round(quality["script_ratio"], 4),
                            "digit_ratio": round(quality["digit_ratio"], 4),
                        }
                    )

    out = Path(args.output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_json(
        out.with_suffix(".summary.json"),
        {
            "records": len(records),
            "output_jsonl": str(out),
            "label_roots": args.label_roots,
            "min_chars": args.min_chars,
            "min_script_ratio": min_ratio,
        },
    )
    print(json.dumps({"records": len(records), "output_jsonl": str(out)}, ensure_ascii=False, indent=2))
    return 0 if records else 2


if __name__ == "__main__":
    raise SystemExit(main())
