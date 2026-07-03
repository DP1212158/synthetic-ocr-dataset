#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/dp/Downloads/中央民族大学合作项目/藏语/01_文本数据获取_20260630"
CFG="$ROOT/configs/bo_wikipedia_random_sample.json"
OUT="$ROOT/data/bo_wikipedia_random_sample_20260630"
LOG="$ROOT/logs/bo_wikipedia_random_sample_20260630.log"
PY="/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"

unset http_proxy https_proxy no_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY
export https_proxy="http://agent.baidu.com:8891"
export http_proxy="http://agent.baidu.com:8891"
export no_proxy=baidu.com,baidubce.com,bj.bcebos.com,bfsu.edu.cn,tsinghua.edu.cn

mkdir -p "$OUT" "$(dirname "$LOG")"

"$PY" - <<'PY' "$CFG" "$OUT" "$ROOT/scripts/collect_multilingual_text.py" 2>&1 | tee "$LOG"
import json
import subprocess
import sys

cfg_path, out_dir, script_path = sys.argv[1:4]
cfg = json.load(open(cfg_path, "r", encoding="utf-8"))
cmd = [sys.executable, script_path, "--output-dir", out_dir]
for key, value in cfg.items():
    flag = "--" + key.replace("_", "-")
    if isinstance(value, bool):
        if value:
            cmd.append(flag)
    else:
        cmd.extend([flag, str(value)])
print("RUN:", " ".join(cmd))
raise SystemExit(subprocess.call(cmd))
PY
