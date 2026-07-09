#!/usr/bin/env python3
"""Check image asset diversity across language delivery versions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def asset_sequence(version_dir: Path) -> list[tuple[str, str]]:
    manifest_path = version_dir / "metadata" / "image_asset_manifest.json"
    if not manifest_path.exists():
        return []
    manifest = read_json(manifest_path)
    return [(str(row.get("document_id")), str(row.get("asset_id"))) for row in manifest]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-identical-pairs", type=int, default=0)
    args = parser.parse_args()

    versions = [Path(p) for p in args.version_dir]
    seqs = {str(v): asset_sequence(v) for v in versions}
    summaries = {}
    for path, seq in seqs.items():
        summaries[path] = {
            "slots": len(seq),
            "unique_assets": len({asset for _, asset in seq}),
            "sequence_hash": hashlib.md5(json.dumps(seq, ensure_ascii=False).encode("utf-8")).hexdigest(),
        }
    identical_pairs = []
    paths = list(seqs)
    for i, left in enumerate(paths):
        for right in paths[i + 1 :]:
            if seqs[left] and seqs[left] == seqs[right]:
                identical_pairs.append({"left": left, "right": right, "sequence_hash": summaries[left]["sequence_hash"]})
    summary = {
        "versions": summaries,
        "identical_pairs": identical_pairs,
        "pass": len(identical_pairs) <= args.max_identical_pairs,
    }
    out = Path(args.output_dir)
    write_json(out / "cross_language_asset_summary.json", summary)
    rows = "\n".join(f"| {item['left']} | {item['right']} | {item['sequence_hash']} |" for item in identical_pairs)
    (out / "QA_CROSS_LANGUAGE_ASSETS_REPORT.md").write_text(
        f"""# Cross-Language Image Asset QA

- 版本数：{len(versions)}
- 完全相同资产序列对：{len(identical_pairs)}
- 结论：{'通过' if summary['pass'] else '需处理'}

| 版本 A | 版本 B | 序列哈希 |
|---|---|---|
{rows}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2)[:6000])
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
