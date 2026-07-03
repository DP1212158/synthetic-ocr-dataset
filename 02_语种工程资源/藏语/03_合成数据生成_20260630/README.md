# 藏语合成数据生成目录

本目录保存藏语合成数据的生成脚本、配置、字体资源、数据版本和质检报告。

## 数据版本

结果目录已经按时间顺序统一命名：

- `v1` 到 `v13`

版本号越大越新。每个版本的调整区别见：

- `版本说明.md`

当前建议优先查看：

- `v13`

`v13` 是当前藏语文本规范修复版：复用 JSON 结构树版式体系，统一保存 12 类，每类 6 张，共 72 张。基础 QA 为 72 / 72 通过；藏语内容 QA 硬失败 0、警告 0。

本版文本池：

- `../01_文本数据获取_20260630/data/cleaned_tibetan_text_pool_20260702/records.jsonl`

## 工程目录

- `scripts/`：生成、渲染、拆分、QA 脚本。
- `configs/`：语言配置和生成配置。
- `assets/`：字体等渲染资源。
- `reports/`：阶段性报告或汇总材料。

## 结构化版面 prompt

当前结构化 prompt 文件位于：

- `../02_版面模板调研_20260630/layout_prompts_v2.json`

报纸页结构树模板位于：

- `../02_版面模板调研_20260630/newspaper_layout_templates_v1.json`

校验脚本：

- `scripts/validate_layout_prompts.py`

校验命令：

```bash
python3 scripts/validate_layout_prompts.py \
  ../02_版面模板调研_20260630/layout_prompts_v2.json \
  --category-plan v11/metadata/category_plan.json
```

当前状态：

- 12 类
- 每类 6 个模板
- 共 72 个模板规格
- 已和 `v11/metadata/category_plan.json` 对齐

说明：`layout_prompts_v2.json` 是 12 类总规格文件，具体生成时优先使用各类别的结构树 JSON。

`v13` 运行时读取结构树 JSON：

- 生成脚本：`scripts/generate_newspaper_from_json_templates.py`
- 生成脚本：`scripts/generate_batch1_from_json_templates.py`
- 生成脚本：`scripts/generate_reading_pages_from_json_templates.py`
- 生成脚本：`scripts/generate_remaining_pages_from_json_templates.py`
- 输出目录：`v13`

## 最新质检

- `v13/reports/QA_REPORT.md`
- `v13/reports/qa_summary.json`
- `v13/reports/QA_DENSITY_REPORT.md`
- `v13/reports/qa_density_summary.json`
- `v13/reports/tibetan_content_qa/TIBETAN_CONTENT_QA_REPORT.md`
- `v13/reports/tibetan_content_qa/tibetan_content_qa_summary.json`
- `v13/reports/by_category/`

## 复现工具

后续新增或重跑类别时，优先使用统一批处理脚本：

```bash
/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/run_category_batch.py \
  --version-dir v13 \
  --generator-script scripts/generate_reading_pages_from_json_templates.py \
  --templates-json ../02_版面模板调研_20260630/reading_pages_layout_templates_v1.json \
  --text-jsonl ../01_文本数据获取_20260630/data/cleaned_tibetan_text_pool_20260702/records.jsonl \
  --language-profile configs/tibetan_language_profile.json \
  --start-index 5 \
  --version-name v13
```

该脚本会串联：

- 生成 HTML
- 渲染图片和标签
- 基础 QA
- 版面密度 QA
- 重建 `v13` 顶层 manifest、QA 汇总和总览图

单独重建版本总索引：

```bash
/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/rebuild_version_index.py \
  --version-dir v13
```

单独检查竖版空白和内容覆盖率：

```bash
/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/qa_layout_density.py \
  --dataset-dir v13
```

单独检查藏语文本规范：

```bash
/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/qa_tibetan_content.py \
  --dataset-dir v13 \
  --output-dir v13/reports/tibetan_content_qa \
  --strict-labels
```
