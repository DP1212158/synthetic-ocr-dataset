#!/usr/bin/env python3
"""Check that a rendered version's category folders match the canonical registry.

Freezes category naming so it cannot drift across versions (a past drift —
VL11「书籍页」vs VL12「书籍内页」— silently broke the demo's category filter).
Registry: configs/category_registry.json. Exit 1 on any mismatch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRY = SCRIPT_DIR.parent / "configs" / "category_registry.json"


def category_dirs(version_dir: Path) -> list[str]:
    return sorted(
        p.name
        for p in version_dir.iterdir()
        if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit()
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version-dir", required=True, help="one language version dir, e.g. .../蒙古语/03_合成数据生成/VL12")
    ap.add_argument("--language", help="language dir name (蒙古语...); inferred from path if omitted")
    ap.add_argument("--registry", default=str(REGISTRY))
    args = ap.parse_args()

    reg = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    vd = Path(args.version_dir)
    lang = args.language
    if not lang:
        # .../02_语种工程资源/<lang>/03_合成数据生成/<version>
        parts = vd.resolve().parts
        lang = parts[parts.index("02_语种工程资源") + 1] if "02_语种工程资源" in parts else None
    pipeline = reg["languages"].get(lang)
    if not pipeline:
        print(f"[check_category_naming] FAIL: 未知语种 {lang!r}，注册表无对应流水线")
        return 1

    expected = reg["pipelines"][pipeline]
    actual = category_dirs(vd)
    missing = [c for c in expected if c not in actual]
    extra = [c for c in actual if c not in expected]
    ok = not missing and not extra
    print(f"[check_category_naming] {lang} ({pipeline}) pass={ok}")
    if missing:
        print(f"  缺失/命名漂移: {missing}")
    if extra:
        print(f"  多余/命名漂移: {extra}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
