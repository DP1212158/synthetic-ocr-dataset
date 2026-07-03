# 多语种合成数据 v4 标准流程

本文档固化壮语 `v4` 已验证有效的准交付流程，供后续维吾尔语、哈萨克语、传统蒙古文、朝鲜语、白语等语种复用。

## 标准阶段

1. 建立语种工程目录与 `language_profile.json`。
2. 构建文本池，优先使用本地真实标注文本，公开网页或 Wikipedia 作为补充。
3. 运行文本 QA 与字体渲染检查。
4. 使用 12 类 JSON 结构树生成 clean 版本。
5. 调用 `finalize_delivery_version.py` 生成最终交付版：
   - 替换图片占位为 `random120-coco2014` 真实图片。
   - 每类 6 张中 3 张纯目标语、3 张混入中文。
   - 降低非结构性横线。
   - 重新渲染、自动裁切并同步标签。
   - 应用 `delivery_all_light` 数据增强。
   - 写入阅读顺序字段。
   - 运行完整 QA。

## 推荐命令

```bash
python3 /Users/dp/Downloads/中央民族大学合作项目/多语种合成数据生成_20260702/scripts/finalize_delivery_version.py \
  --source-version-dir /path/to/clean_v1 \
  --output-version-dir /path/to/final_v2 \
  --language-profile /path/to/language_profile.json \
  --image-assets-dir /Users/dp/Downloads/中央民族大学合作项目/random120-coco2014 \
  --version-name v2 \
  --force
```

## 语种差异

- LTR 语种：可直接使用当前阅读顺序策略。
- RTL 语种：后续正式生成时必须在 `language_profile.json` 中设置 `css_direction=rtl`、`css_text_align=right`；阅读顺序需要按 profile 镜像横向排序。
- 传统蒙古文：需要单独竖排模板或竖排布局分支，不建议直接套横排模板。
- 中文混合：默认只在 `variant 2/4/6` 执行，比例约束为 `10%-30%`。

## 必须通过的报告

- `reports/text_source/text_quality_summary.json`
- `reports/font_check/font_check_summary.json`
- `reports/qa_summary.json`
- `reports/qa_density_summary.json`
- `reports/acceptance_summary.json`
- `reports/language_mix_summary.json`
- `reports/language_validity_summary.json`
- `reports/reading_order_summary.json`
- `reports/image_asset_summary.json`
- `reports/augmentation_quality_summary.json`

## 不建议改动

- 不重写已稳定的 12 类结构树。
- 不修改 `delivery_all_light` 增强核心策略，除非人工验收发现系统性问题。
- 不在同一轮同时调整字体、版面、增强、标签协议，避免无法定位质量变化来源。

## 文本正确性门禁

后续语种必须同时通过三层检查：

1. 文本源 QA：`qa_text_records.py --fail-on-warning`
   - 检查目标文字占比、数字比例、错文字体系残留、私用区字符、方框/替换字符风险。
   - 报告为 `pass=false` 时阻断生成，不进入 72 张正式生成。
2. 字体渲染 QA：`check_font_rendering.py`
   - 生成小样图和标签。
   - 检查标签文本非空，并对文本框区域做像素级可见性检查，避免“标签有字但图片没渲染出来”。
   - RTL 与传统蒙古文仍需要人工重点看方向和连写。
3. 最终标签语言有效性 QA：`qa_language_validity.py`
   - 检查最终 label 中的文本块，确认无乱码、方框风险字符、私用区字符、错文字体系混入。
   - pure 样本禁止中文；mixed 样本只允许目标文字体系 + 中文。
   - 数字比例过高只作为风险警告，不作为硬失败，避免误伤考试卷、证书编号、表单编号。

自动 QA 能挡住明显错误，但不能完全证明民族语语法自然。语法自然性主要依赖真实文本源质量，正式交付前仍建议按语种抽检总览图和若干 label 文本。
