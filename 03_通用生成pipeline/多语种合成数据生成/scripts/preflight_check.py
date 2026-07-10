#!/usr/bin/env python3
"""Preflight environment check for the synthetic-OCR generation pipeline.

Codifies the environment assumptions that were previously tribal knowledge
(node20 on PATH, Playwright + Chromium, fonts installed, python deps). Run it
before generating a new version; it fails loudly with actionable messages
instead of producing tofu / crashing mid-render.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]

REQUIRED_FONT_HINTS = {
    "Mongolian": "mongolian",
    "Tibetan/Noto": "tibetan",
    "Korean/Hangul": "korean",
    "Arabic(Naskh/Scheherazade)": "arabic",
}


def ok(msg):
    print(f"  [OK]   {msg}")


def bad(msg):
    print(f"  [FAIL] {msg}")


def check_node():
    node = shutil.which("node")
    if not node:
        bad("node 不在 PATH（需 `export PATH=/root/tools/node20/bin:$PATH`）")
        return False
    try:
        v = subprocess.check_output([node, "--version"], text=True).strip()
    except Exception as e:  # noqa: BLE001
        bad(f"node 执行失败: {e}")
        return False
    major = int(v.lstrip("v").split(".")[0]) if v.lstrip("v")[:1].isdigit() else 0
    if major < 18:
        bad(f"node 版本过低 {v}（建议 v20）")
        return False
    ok(f"node {v} @ {node}")
    return True


def check_playwright():
    node = shutil.which("node")
    if not node:
        return False
    try:
        out = subprocess.run(
            [node, "-e", "console.log(require.resolve('playwright'))"],
            cwd=str(SCRIPT_DIR),
            capture_output=True,
            text=True,
        )
        if out.returncode == 0 and out.stdout.strip():
            ok(f"playwright 可解析: {out.stdout.strip()}")
            return True
        bad("node 无法 require('playwright')（在项目根 `npm install`）")
        return False
    except Exception as e:  # noqa: BLE001
        bad(f"playwright 检查失败: {e}")
        return False


def check_chromium():
    caches = list(Path.home().glob(".cache/ms-playwright/chromium-*"))
    if caches:
        ok(f"chromium 缓存: {caches[0].name}（共 {len(caches)}）")
        return True
    bad("无 chromium 缓存（`npx playwright install chromium`）")
    return False


def check_fonts():
    fc = shutil.which("fc-list")
    if not fc:
        bad("无 fc-list，无法校验字体（安装 fontconfig）")
        return False
    try:
        listing = subprocess.check_output([fc], text=True, errors="ignore").lower()
    except Exception as e:  # noqa: BLE001
        bad(f"fc-list 执行失败: {e}")
        return False
    all_ok = True
    for label, hint in REQUIRED_FONT_HINTS.items():
        if hint in listing:
            ok(f"字体 {label} 已安装")
        else:
            bad(f"字体 {label} 缺失（cp 00_共享资源/fonts/* ~/.local/share/fonts/synthetic-ocr/ && fc-cache -fv）")
            all_ok = False
    return all_ok


def check_python_deps():
    all_ok = True
    for mod in ("PIL", "numpy"):
        try:
            __import__(mod)
            ok(f"python 模块 {mod}")
        except Exception:  # noqa: BLE001
            bad(f"python 缺模块 {mod}（pip install pillow numpy）")
            all_ok = False
    return all_ok


def main() -> int:
    print("== 生成流水线环境自检 ==")
    results = {
        "node": check_node(),
        "playwright": check_playwright(),
        "chromium": check_chromium(),
        "fonts": check_fonts(),
        "python_deps": check_python_deps(),
    }
    passed = all(results.values())
    print(f"\n结论: {'全部通过 ✅' if passed else '存在缺项 ❌ — 修复后再生成'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
