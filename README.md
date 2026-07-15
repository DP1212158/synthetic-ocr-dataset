# 合成OCR数据集生成工程

本仓库是少数民族语言合成 OCR 数据的源码资源仓库。它保留服务器重新生成数据所需的脚本、模板、文本源、字体和小规模图片资产，不再提交历史 VL 生成结果。

## 克隆仓库（推荐浅克隆）

早期提交中曾包含大量已淘汰的生成产物，仍留存在 Git 历史里，普通全量克隆需下载约 1.8GB。**当前 HEAD 快照不含这些生成数据，浅克隆只需下载约 45MB**，强烈建议按下面方式克隆：

```bash
git clone --depth 1 --single-branch --branch main \
  https://github.com/DP1212158/synthetic-ocr-dataset.git synthetic-ocr-delivery
```

说明：

- 浅克隆只取最新一次提交的快照，历史里的旧大文件不会被下载。
- 请勿执行 `git fetch --unshallow`，否则会把 1.8GB 全历史补下来。
- 后续 `git pull` 正常增量更新，不受影响。
- 若确需完整历史（如 `git blame`/`bisect`），再用普通 `git clone`。

## 核心内容

- `00_共享资源/`：各语种所需开源字体（Arabic-script、藏文、谚文、传统蒙古文）、字体修复脚本和少量字体检查材料。这是"字体支持机制"而非全语种整包，服务器跑生成前需按 `SERVER_RUNBOOK.md` 完成字体安装与识别验证。
- `02_语种工程资源/`：7 个语种的文本源、来源记录、文本报告和 language profile。
- `03_通用生成pipeline/`：通用生成、渲染、图片资产接入、阅读顺序、QA 和可视化辅助脚本。
- `04_共享图片资产/`：用于替换版面图片占位符的 `random120-coco2014` 图片池。
- `05_总报告与索引/`：文本源确认/provenance 记录。
- `图片浏览_demo/`：静态图片浏览平台源码。

## 当前主线

旧版 `01_最终VL2数据/` 已淘汰并从仓库中移除。当前生成路线以 VL7 结构树阅读顺序为基础，VL9 在此基础上继续做视觉清理和真实图片接入。

推荐先生成非蒙古语六语种：

```bash
python 03_通用生成pipeline/多语种合成数据生成/scripts/run_full_generation.py \
  --version-name VL9 \
  --languages tibetan zhuang korean bai uyghur kazakh \
  --max-language-workers 2 \
  --attach-image-assets
```

蒙古语竖排当前仍需单独优化，不建议并入默认批量生成。

## 服务器运行

完整安装和运行说明见：

- `SERVER_RUNBOOK.md`
- `SUBMISSION_ASSET_INVENTORY.md`

生成完成后可构建浏览 demo 清单：

```bash
python 图片浏览_demo/scripts/build_image_manifest.py \
  --version VL9 \
  --languages tibetan zhuang korean bai uyghur kazakh
```

然后启动静态服务：

```bash
python3 -m http.server 8766
```

访问：

```text
http://127.0.0.1:8766/图片浏览_demo/index.html
```

## 不提交内容

- 历史生成版本：`VL2`、`VL3`、`VL4`、`VL5`、`VL6`、`VL7`、`VL8`、`VL9` 等输出目录。
- 本地环境：`.venv*/`、`node_modules/`、`__pycache__/`。
- 下载缓存和可视化大图缓存。
- `图片浏览_demo/data/image_manifest.json`，该文件由服务器生成后重建。
