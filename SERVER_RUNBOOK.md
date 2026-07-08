# 服务器运行说明

本仓库用于少数民族语言合成 OCR 数据集的生成、检查和交付整理。推荐把代码、配置、文本池、最终交付数据提交到 Git；虚拟环境、缓存、临时实验版本和大体积 benchmark 缓存不要提交。

## 推荐提交范围

- `00_共享资源/`：共享字体和修复脚本。
- `01_最终VL2数据/`：当前稳定交付数据。
- `02_语种工程资源/`：语种配置、文本池、模板、脚本副本和已确认资源。
- `03_通用生成pipeline/`：通用生成流水线代码、配置和运行文档。
- `04_共享图片资产/`：生成时使用的小规模共享图片资产。
- `05_总报告与索引/`：交付报告与索引，但不包含大体积缓存。
- `AGENT.md`、`README.md`、`SERVER_RUNBOOK.md`。

不要提交：

- `.venv_pp_layout/`、`.venv*/`、`node_modules/`。
- `05_总报告与索引/omnidocbench_cache/`。
- `02_语种工程资源/*/03_合成数据生成_20260702/VL3/` 到 `VL9/`、`VL_latest_*` 等临时实验版本。
- `图片浏览_demo/`、临时 dashboard、pilot/smoke/probe 输出。

## 服务器环境

建议配置：

- CPU：16 核起步，32 核以上更合适；80 核服务器可以明显缩短全量生成时间。
- 内存：至少 32G，推荐 64G 以上。
- 磁盘：本地 NVMe SSD，避免把生成目录放在网络盘。
- 系统：Linux。

依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pillow numpy requests beautifulsoup4 lxml

npm install playwright
npx playwright install chromium
```

如使用系统 Chromium/Chrome，需要确保 Playwright 能找到浏览器。Linux 服务器上如果缺系统库，按 `npx playwright install-deps chromium` 补齐。

## 字体

服务器必须安装或可访问以下文字系统字体，否则渲染换行、连写和标签框可能与 Mac 不一致：

- 藏文：Noto Serif Tibetan / Noto Sans Tibetan 或等价字体。
- 阿拉伯系维吾尔语、哈萨克语：`00_共享资源/fonts/arabic/` 中的 Noto/Scheherazade 字体。
- 传统蒙古文：Noto Sans Mongolian。
- 朝鲜文：Noto Sans CJK KR 或等价字体。

建议把 `00_共享资源/fonts/` 复制到服务器字体目录后刷新缓存：

```bash
mkdir -p ~/.local/share/fonts/synthetic-ocr
cp -R 00_共享资源/fonts/* ~/.local/share/fonts/synthetic-ocr/
fc-cache -fv
```

## 路径配置

`03_通用生成pipeline/多语种合成数据生成_20260702/configs/language_jobs.json` 中的 `project_root` 当前是 Mac 本地路径。服务器 clone 后需要改为服务器仓库绝对路径，例如：

```json
"project_root": "/data/synthetic-ocr-dataset"
```

如果只运行通用 pipeline，优先使用 `03_通用生成pipeline/多语种合成数据生成_20260702/scripts/` 下的脚本。

## 推荐运行

先跑 pilot，确认字体、Chromium 和 QA 都正常：

```bash
python3 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/run_multilingual_pipeline.py \
  --pilot \
  --finalize-delivery \
  --delivery-output-name VL3 \
  --delivery-version-name VL3 \
  --max-language-workers 2 \
  --max-category-workers 2 \
  --resume-from-cache
```

全量运行：

```bash
python3 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/run_multilingual_pipeline.py \
  --finalize-delivery \
  --delivery-output-name VL3 \
  --delivery-version-name VL3 \
  --max-language-workers 7 \
  --max-category-workers 4 \
  --resume-from-cache
```

80 核服务器上不改代码时，当前主要并发上限约为 `7 x 4 = 28` 个类别批次任务。先从 `4 x 4` 或 `7 x 4` 试起，观察 CPU、内存和磁盘。

监控：

```bash
htop
iostat -x 1
free -h
```

判断：

- CPU 长时间高占用且 iowait 低：正常，瓶颈主要在 CPU/Chromium 渲染。
- iowait 高：磁盘瓶颈，迁到本地 SSD。
- 内存或 Chromium 崩溃：降低 `--max-language-workers`。

## 提交前检查

```bash
git status --short
git status --ignored --short | sed -n '1,80p'
find . -path ./.git -prune -o -type f -size +50M -print
```

确认没有 `.venv`、缓存、临时 VL 版本进入 staged 区域后再提交。
