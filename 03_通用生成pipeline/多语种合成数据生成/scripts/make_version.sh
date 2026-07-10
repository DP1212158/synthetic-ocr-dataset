#!/usr/bin/env bash
# make_version.sh — one-command, gated pipeline to produce a delivery version.
#
# Runs: preflight → clean render → hard QA gate (layout-quality + category naming
# + language validity) → augment → polygon injection → demo refresh.
# Any gate failure stops the run (set -e), so a version is only "done" when green.
#
# Usage:
#   scripts/make_version.sh VL13                       # all 7 languages
#   scripts/make_version.sh VL13 蒙古语                # subset (Chinese dir names)
#   scripts/make_version.sh VL13 蒙古语 藏语
#
# Env:
#   PROFILE=delivery_balanced   augmentation profile (default)
#   PATH must include node20 (script exports it if present).

set -euo pipefail

VERSION="${1:?用法: make_version.sh <VERSION> [语种...]}"
shift || true
LANGS=("$@")
if [ ${#LANGS[@]} -eq 0 ]; then
  LANGS=(藏语 壮语 朝鲜语 白语 维吾尔语 哈萨克语 蒙古语)
fi
PROFILE="${PROFILE:-delivery_balanced}"

[ -d /root/tools/node20/bin ] && export PATH=/root/tools/node20/bin:$PATH
PY=/usr/bin/python
ENGINE="/mnt/dengpenglongyi/synthetic-ocr-dataset/03_通用生成pipeline/多语种合成数据生成"
BASE="/mnt/dengpenglongyi/synthetic-ocr-dataset/02_语种工程资源"
DEMO="/mnt/dengpenglongyi/synthetic-ocr-dataset/图片浏览_demo"
LOGDIR="/tmp/make_version_${VERSION}"
mkdir -p "$LOGDIR"
cd "$ENGINE"

echo "=== [0/8] 环境自检 ==="
"$PY" scripts/preflight_check.py

echo "=== [1/8] 干净渲染 ${VERSION}_clean（${LANGS[*]}）==="
"$PY" scripts/run_full_generation.py --version-name "${VERSION}_clean" \
  --languages "${LANGS[@]}" --mongolian-template-version v4 2>&1 | tee "$LOGDIR/clean.log"

echo "=== [2/8] 硬 QA 门禁（clean：版面质量 + 命名 + 无冗余文本框）==="
for L in "${LANGS[@]}"; do
  CLEAN="$BASE/$L/03_合成数据生成/${VERSION}_clean"
  echo "-- $L --"
  "$PY" scripts/qa_layout_quality.py --version-dir "$CLEAN" \
    --output-json "$CLEAN/reports/layout_quality_summary.json"
  "$PY" scripts/check_category_naming.py --version-dir "$CLEAN" --language "$L"
  "$PY" scripts/qa_no_unwanted_text_boxes.py --version-dir "$CLEAN" >/dev/null \
    && echo "   no_unwanted_text_boxes OK" || { echo "FAIL: $L 冗余纯文本框"; exit 1; }
  N=$(ls "$CLEAN"/[01]*/images/*.png 2>/dev/null | wc -l)
  echo "   images=$N"
  [ "$N" -gt 0 ] || { echo "FAIL: $L 无图片"; exit 1; }
done

echo "=== [3/8] 数据增强 → ${VERSION}（profile=$PROFILE）==="
for L in "${LANGS[@]}"; do
  SRC="$BASE/$L/03_合成数据生成/${VERSION}_clean"
  OUT="$BASE/$L/03_合成数据生成/${VERSION}"
  echo "-- $L --"
  "$PY" scripts/augment_synthetic_dataset.py \
    --source-version-dir "$SRC" --output-version-dir "$OUT" \
    --profile "$PROFILE" --force 2>&1 | tail -2
done

echo "=== [4/8] 交付 QA 门禁（${VERSION}：视觉交付硬门禁 + 版面密度软检查）==="
for L in "${LANGS[@]}"; do
  OUT="$BASE/$L/03_合成数据生成/${VERSION}"
  PROF=$(ls "$BASE/$L/03_合成数据生成/configs/"*_language_profile.json 2>/dev/null | head -1)
  echo "-- $L --"
  "$PY" scripts/qa_visual_delivery.py --version-dir "$OUT" --language-profile "$PROF" >/dev/null \
    && echo "   visual_delivery OK" || { echo "FAIL: $L 视觉交付(极端长宽比/空白页/重复图)"; exit 1; }
  "$PY" scripts/qa_layout_density.py --dataset-dir "$OUT" >/dev/null 2>&1 \
    && echo "   layout_density(软) OK" || echo "   layout_density(软) 有告警(不阻断)"
done

echo "=== [5/8] 跨语种资产多样性（软检查）==="
if [ ${#LANGS[@]} -ge 2 ]; then
  CLA=(); for L in "${LANGS[@]}"; do CLA+=(--version-dir "$BASE/$L/03_合成数据生成/${VERSION}"); done
  "$PY" scripts/qa_cross_language_assets.py "${CLA[@]}" --output-dir "$LOGDIR" >/dev/null 2>&1 \
    && echo "   cross_language_assets(软) OK" || echo "   cross_language_assets(软) 有告警(共享图池,不阻断)"
fi
for L in "${LANGS[@]}"; do
  if [ "$L" = "藏语" ]; then
    "$PY" scripts/qa_tibetan_content.py --dataset-dir "$BASE/藏语/03_合成数据生成/${VERSION}" --output-dir "$LOGDIR" >/dev/null 2>&1 \
      && echo "   tibetan_content(软) OK" || echo "   tibetan_content(软) 有告警(不阻断)"
  fi
done

echo "=== [6/8] 注入旋转 polygon（${VERSION}）==="
"$PY" scripts/inject_rotated_polygons.py --version "$VERSION" --languages "${LANGS[@]}"

echo "=== [7/8] 刷新可视化（缩略图 + manifest，仅 ${VERSION}）==="
"$PY" "$DEMO/scripts/build_thumbnails.py" --versions "$VERSION" --force 2>&1 | tail -1
"$PY" "$DEMO/scripts/build_image_manifest.py" --versions "$VERSION" 2>&1 | head -3

echo "=== [8/8] 完成：$VERSION 已通过全部门禁并挂载 ==="
echo "日志目录: $LOGDIR"
