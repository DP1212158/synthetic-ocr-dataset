#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/dp/Downloads/中央民族大学合作项目/文本数据获取_20260630"
OUT_DIR="$ROOT/data/mn_wikipedia_random_sample_20260630"
LOG_DIR="$ROOT/logs"
mkdir -p "$OUT_DIR" "$LOG_DIR"

# 通用代理（P0推荐）。如果本机已能直连 Wikimedia，可注释掉这一段。
unset http_proxy https_proxy no_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY
export https_proxy="http://agent.baidu.com:8891"
export http_proxy="http://agent.baidu.com:8891"
export no_proxy="baidu.com,baidubce.com,bj.bcebos.com,bfsu.edu.cn,tsinghua.edu.cn"

python3 "$ROOT/scripts/collect_wikipedia_text.py" \
  --mode "random" \
  --language-code "mn" \
  --language-name "蒙古语" \
  --script-note "mn.wikipedia.org 主要为西里尔蒙古文，非传统竖排蒙古文" \
  --endpoint "https://mn.wikipedia.org/w/api.php" \
  --output-dir "$OUT_DIR" \
  --max-pages 300 \
  --batch-size 30 \
  --min-paragraph-chars 40 \
  --sleep-seconds 0.4 \
  --timeout 20 \
  --retries 2 \
  2>&1 | tee "$LOG_DIR/mn_wikipedia_random_sample_20260630.log"
