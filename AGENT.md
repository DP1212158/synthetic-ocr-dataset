# AGENT.md

## 项目背景

本项目用于建设少数民族语言多模态 OCR 评估集的合成补充数据。目标不是替代真实数据，而是在真实数据之外，补充覆盖更多版面类型、书写方向、文字系统、图文混排和真实环境扰动的可控样本。

当前仓库已从早期“交付结果目录”整理为“源码资源仓库”：保留生成脚本、结构树模板、语种文本源、语言 profile、共享字体和小规模图片资产；不再保留历史 VL2/VL3/VL4/VL5/VL6/VL7/VL9 生成结果。服务器 clone 后应基于这些源材料重新生成新版本。

## 当前主线

- 旧版 `01_最终VL2数据/` 已淘汰，不再作为交付或维护对象。
- 当前生成主线来自 VL7 的结构树阅读顺序方案。
- 当前视觉清理和图片资产接入方向按 VL9 继续迭代。
- 蒙古语竖排暂不建议并入非蒙古语批量生成，需要单独修模板、数字方向和竖排版面。

覆盖语种仍为 7 个：

1. 壮语：拉丁字母，LTR。
2. 藏语：藏文字母，LTR。
3. 朝鲜语：谚文，LTR。
4. 白语：白文拉丁方案，LTR。
5. 维吾尔语：改良阿拉伯字母，RTL。
6. 哈萨克语：改良阿拉伯字母，RTL。
7. 传统蒙古文：传统蒙古文，竖排 vertical-lr。

非蒙古语当前推荐先生成 6 个语种；蒙古语作为独立分支处理。

## 目录约定

- `00_共享资源/`：共享字体、字体修复脚本和少量字体检查材料。
- `02_语种工程资源/`：语种级文本源、来源 manifest、清洗报告、language profile。不要在这里维护通用脚本副本。
- `03_通用生成pipeline/`：唯一的通用生成流水线入口，包含文本采样、HTML 生成、渲染、真实图片插入、阅读顺序 QA、视觉清理和浏览清单构建相关脚本。
- `04_共享图片资产/`：本地 COCO 随机图片池，用于替换版面图片占位。
- `05_总报告与索引/`：只保留文本源确认/provenance 记录；生成报告由服务器重新生成。
- `图片浏览_demo/`：静态图片浏览平台源码；`data/image_manifest.json` 是运行时产物，不提交。

## 生成逻辑概述

完整 pipeline 分为以下阶段：

1. 文本源构建：各语种保留 `records.jsonl`、`source_manifest.json`、`text_source_report.md` 等可追溯文本池。
2. 语言 profile：每个语种配置文字系统、书写方向、字体、脚本正则、残留阈值和中文混合策略。
3. 版面生成：通过通用 JSON 结构树模板驱动 12 类版面，结构树在生成 HTML 前声明阅读顺序。
4. 阅读顺序：`reading_flow_v1.py` 将模板语义结构编译为 `reading_order`，不再依赖渲染后坐标猜测主顺序。
5. 视觉清理：VL9 方向去掉普通文本框和大量隔离横线，保留表格、表单、证书、答题区、图片等语义结构线。
6. 图片接入：`attach_image_assets_to_vl7.py` 将版面中的 image/photo/figure 占位替换为 `random120-coco2014` 中的真实图片。
7. 渲染与裁切：HTML 由 Playwright/Chromium 渲染为图片，并按标签同步裁切。
8. QA：运行基础 QA、阅读顺序 QA、普通文本框风险扫描、图片资产 QA 和 overlay/contact sheet 可视化。

## 当前主入口

主入口位于：

```bash
03_通用生成pipeline/多语种合成数据生成_20260702/scripts/run_vl7_full.py
```

单语种 smoke：

```bash
python 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/run_vl7_full.py \
  --version-name VL9 \
  --languages tibetan \
  --max-language-workers 1 \
  --attach-image-assets
```

非蒙古语六语种：

```bash
python 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/run_vl7_full.py \
  --version-name VL9 \
  --languages tibetan zhuang korean bai uyghur kazakh \
  --max-language-workers 2 \
  --attach-image-assets
```

生成完成后重建浏览 demo manifest：

```bash
python 图片浏览_demo/scripts/build_image_manifest.py \
  --version VL9 \
  --languages tibetan zhuang korean bai uyghur kazakh
```

## 标签字段

OCR 文本标签保持矩形框 `coordinates`，并包含阅读顺序字段：

- `reading_order`
- `reading_group`
- `reading_role`
- `reading_region`
- `reading_flow_id`
- `reading_flow_rank`
- `reading_order_confidence`

图片块、装饰线、答题区和表格结构线通常通过 `is_text=false` 或 `data-ocr-orderable=false` 排除在 OCR 阅读编号之外。

## 维护原则

- 不要恢复或提交历史生成版本目录；生成数据应在服务器重新产出。
- 新一轮实验使用新版本名，例如 `VL9_server_smoke`、`VL10`，不要覆盖已有结果。
- 通用脚本只维护在 `03_通用生成pipeline/`，语种目录只放文本源、profile 和少量语种特化模板。
- RTL 与传统蒙古文必须做视觉抽检，不能只看自动 QA。
- 自动 QA 不能证明语法母语级正确，只能排除乱码、错脚本、方块、越界、密度、图片占位和阅读顺序流程类问题。
