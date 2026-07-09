# 当前生成主线

本目录只保留服务器侧继续生成所需的当前主线脚本和少量研究辅助脚本。历史 VL2/VL3/V4 交付脚本和报告已经从源码仓库中移除。

## 主入口

- `scripts/run_full_generation.py`
  - 按语种批量生成完整版本。
  - 读取 `configs/layout_templates_v2/*.json` 通用模板。
  - 读取各语种 `02_语种工程资源/<语种>/03_合成数据生成/configs/*_language_profile.json`。
  - 读取各语种当前文本池 `records.jsonl`。
  - 可通过 `--attach-image-assets` 在渲染前接入真实图片。

推荐先跑 smoke：

```bash
python 03_通用生成pipeline/多语种合成数据生成/scripts/run_full_generation.py \
  --version-name VL9 \
  --languages tibetan \
  --max-language-workers 1 \
  --attach-image-assets
```

非蒙古语批量：

```bash
python 03_通用生成pipeline/多语种合成数据生成/scripts/run_full_generation.py \
  --version-name VL9 \
  --languages tibetan zhuang korean bai uyghur kazakh \
  --max-language-workers 2 \
  --attach-image-assets
```

## 核心脚本

- `scripts/reading_flow_v1.py`：结构树阅读顺序字段和编译逻辑。
- `scripts/generate_*_from_json_templates.py`：12 类横排/RTL 版面生成器。
- `scripts/render_table_dataset.mjs`：Playwright/Chromium 渲染与裁切。
- `scripts/attach_image_assets_to_vl7.py`：真实图片资产接入。
- `scripts/vl9_visual_style.py`：去普通文本框、减少隔离横线等视觉清理。
- `scripts/qa_reading_flow_v1.py`：结构树 reading order QA。
- `scripts/qa_table_dataset.py`、`scripts/qa_no_unwanted_text_boxes.py`、`scripts/qa_language_validity.py`：基础标签、视觉结构和语言有效性 QA。
- `scripts/make_reading_order_contact_sheet.py`：阅读顺序 overlay/contact sheet。

## 辅助脚本

- `scripts/build_vl3_text_sources.py`、`scripts/qa_text_records.py`：文本源构建和检查，可用于后续扩充文本池。
- `scripts/collect_people_kazakh_text.py`、`scripts/collect_wikipedia_text.py`：公开文本采集辅助脚本。
- `scripts/layout_order/`：PP-DocLayout/模板 flow 的版面顺序研究脚本，当前不作为主排序器。
- `scripts/omnidocbench_vl6/`：OmniDocBench 模板研究脚本，当前不作为最终生成主线。
- `scripts/build_mongolian_vertical_templates_v4.py`、`scripts/generate_mongolian_vertical_from_json_v3.py`：蒙古语竖排专项修复入口，暂不并入默认非蒙古语批量生成。

## 不再保留

- 旧 VL2/VL3/V4 交付固化脚本。
- 旧 `reports_vl*` 审计报告目录。
- 各语种目录下的通用脚本副本和通用模板副本。
- 历史生成结果目录。
