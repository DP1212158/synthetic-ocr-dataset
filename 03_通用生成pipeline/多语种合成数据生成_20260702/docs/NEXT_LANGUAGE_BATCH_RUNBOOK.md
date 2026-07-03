# 后续语种全量生成执行手册

目标：基于当前壮语 `v4` 准交付标准，生成剩余语种的完整 12 类数据。

## 推荐执行方式

先单语种试跑：

```bash
python3 /Users/dp/Downloads/中央民族大学合作项目/多语种合成数据生成_20260702/scripts/run_multilingual_pipeline.py \
  --only korean \
  --finalize-delivery \
  --delivery-output-name v2 \
  --delivery-version-name v2 \
  --image-assets-dir /Users/dp/Downloads/中央民族大学合作项目/random120-coco2014
```

确认质量后再批量：

```bash
python3 /Users/dp/Downloads/中央民族大学合作项目/多语种合成数据生成_20260702/scripts/run_multilingual_pipeline.py \
  --finalize-delivery \
  --delivery-output-name v2 \
  --delivery-version-name v2 \
  --image-assets-dir /Users/dp/Downloads/中央民族大学合作项目/random120-coco2014
```

## 输出逻辑

- clean 初版：各语种 `03_合成数据生成_20260702/v1`
- 最终交付版：各语种 `03_合成数据生成_20260702/v2`
- 不删除 clean 版本，便于定位问题。

## 成功标准

最终 `v2` 必须满足：

- `reports/qa_summary.json`: `total_images=72`, `passed_basic=72`, `failed_basic=[]`
- `reports/qa_summary.json`: `total_overflow_blocks=0`, `total_out_of_bounds_blocks=0`
- `reports/qa_density_summary.json`: `warning_images=0`
- `reports/acceptance_summary.json`: `pass=true`
- `reports/language_mix_summary.json`: `pass=true`
- `reports/language_validity_summary.json`: `pass=true`
- `reports/reading_order_summary.json`: `pass=true`
- `reports/image_asset_summary.json`: `pass=true`

## 重点抽检

- 朝鲜语：Hangul 显示、类别区分度、是否误混拉丁或中文过量。
- 白语：文本源真实性，避免使用壮语安全标题。
- 维吾尔语：RTL 对齐、标题方向、阿拉伯字母连写。
- 哈萨克语：文本源质量，确认不是西里尔哈萨克文混入。
- 传统蒙古文：竖排方向、列顺序、字体是否支持传统蒙古文。

## 失败定位

- 文本不够或质量差：看 `reports/text_source/` 和 `BLOCKED_TEXT_SOURCE_REPORT.md`
- 字体失败：看 `reports/font_check/`
- 版面或标签失败：看 `reports/qa_summary.json`
- 密度失败：看 `reports/qa_density_summary.json`
- 中文混合失败：看 `reports/language_mix_summary.json`
- 语言残留失败：看 `reports/language_validity_summary.json`
- 图片占位失败：看 `reports/image_asset_summary.json`
- 阅读顺序失败：看 `reports/reading_order_summary.json`

## 当前工程判断

后续不建议大重构。稳定路线是：

1. 继续使用现有 12 类结构树生成 clean 版本。
2. 使用 `finalize_delivery_version.py` 做统一交付化。
3. 对 RTL 和传统蒙古文只做必要方向特化。
4. 每个语种先单独跑通，再做全量。
