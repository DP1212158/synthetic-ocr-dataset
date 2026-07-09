# 远程提交资产说明

本次整理目标：让远程仓库只承载服务器继续生成所需的源材料和脚本，不再承载历史 VL 生成数据。

## 保留内容

- `00_共享资源/`
  - 阿拉伯系字体、字体修复脚本和少量检查报告。
- `02_语种工程资源/`
  - 7 个语种的文本源 `records.jsonl`、`source_manifest.json`、`text_source_report.md`。
  - 7 个语种的 `*_language_profile.json`。
  - 蒙古语竖排模板构建相关配置仍保留，后续可单独修。
  - 已删除各语种目录下重复的 `scripts/` 和 `configs/layout_templates_v2/` 副本，避免服务器侧出现多套入口。
- `03_通用生成pipeline/`
  - VL7/VL9 主生成脚本、结构树阅读顺序模块、渲染脚本、图片资产接入脚本、QA 脚本。
  - `configs/layout_templates_v2/*.json` 四个通用结构树模板文件。
  - PP-DocLayout 和 OmniDocBench 研究脚本保留，但不保留模型/数据缓存。
- `04_共享图片资产/random120-coco2014/`
  - 120 张小规模真实图片资产，用于生成时替换图片占位。
- `05_总报告与索引/`
  - 仅保留 `text_source_validation/` 这类文本源确认/provenance 记录。
  - 已删除 OmniDocBench 下载缓存和 142MB 原始模板图库。
- `图片浏览_demo/`
  - 静态浏览页面、JS/CSS 和 manifest 构建脚本。
  - 不提交 `data/image_manifest.json`，服务器生成数据后再构建。
- 根目录运行材料
  - `AGENT.md`
  - `README.md`
  - `SERVER_RUNBOOK.md`
  - `requirements-server.txt`
  - `package.json`

## 已删除/不再提交内容

- `01_最终VL2数据/`
  - 已淘汰旧交付版本，删除。
- `02_语种工程资源/*/03_合成数据生成/VL*/`
  - VL3/VL4/VL5/VL6/VL7/VL8/VL9、`VL_latest_*` 等生成输出，全部删除。
- `02_语种工程资源/*/03_合成数据生成/scripts/`
  - 旧的语种侧脚本副本已删除，统一使用 `03_通用生成pipeline/`。
- `02_语种工程资源/*/03_合成数据生成/configs/layout_templates_v2/`
  - 旧的语种侧通用模板副本已删除，统一使用通用 pipeline 的模板。
- 本地环境与缓存
  - `.venv_pp_layout/`
  - `__pycache__/`
  - `.DS_Store`
  - 各类日志、下载缓存、pilot/smoke/probe/dashboard 输出。
- 大体积可视化报告图
  - `05_总报告与索引/VL6_omni_original_templates/`
  - `多语种合成数据生成汇总_20260702/*.jpg`
- 历史汇总报告
  - `多语种合成数据生成汇总_20260702/`
  - `05_总报告与索引/` 下 VL2/VL6/VL7 的历史生成报告。

## 服务器重建入口

推荐先 smoke：

```bash
python 03_通用生成pipeline/多语种合成数据生成/scripts/run_full_generation.py \
  --version-name VL9 \
  --languages tibetan \
  --max-language-workers 1 \
  --attach-image-assets
```

非蒙古语六语种：

```bash
python 03_通用生成pipeline/多语种合成数据生成/scripts/run_full_generation.py \
  --version-name VL9 \
  --languages tibetan zhuang korean bai uyghur kazakh \
  --max-language-workers 2 \
  --attach-image-assets
```
