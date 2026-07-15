# 服务器运行说明

本仓库现在按“源码资源仓库”整理：保留生成脚本、结构树模板、语种文本源、语言 profile、共享字体和小规模图片资产；不保留 VL2/VL3/VL4/VL5/VL6/VL7/VL9 等生成数据。服务器 clone 后从这些源材料重新生成新版本。

## 提交范围

建议纳入 Git：

- `00_共享资源/`：共享字体、字体修复脚本和少量字体检查材料。
- `02_语种工程资源/`：7 个语种的文本源、source manifest、language profile；蒙古语另保留竖排专项模板配置。
- `03_通用生成pipeline/`：通用生成、渲染、阅读顺序、图片资产接入、QA、VL6/PP-layout 研究脚本。
- `04_共享图片资产/random120-coco2014/`：生成时用于替换图片占位的小规模真实图片池。
- `05_总报告与索引/`：仅保留文本源确认/provenance 记录，不含大缓存/大图库。
- `图片浏览_demo/`：静态浏览 demo 代码，不含生成 manifest。
- `AGENT.md`、`README.md`、`SERVER_RUNBOOK.md`、`requirements-server.txt`、`package.json`。

不要提交：

- `01_最终VL2数据/`：已淘汰的旧交付数据。
- `02_语种工程资源/*/03_合成数据生成/VL*/`、`VL_latest_*`：所有生成输出。
- `.venv*/`、`node_modules/`、`__pycache__/`、`.DS_Store`、日志和浏览器测试缓存。
- `05_总报告与索引/omnidocbench_cache/`、`05_总报告与索引/VL6_omni_original_templates/` 等下载缓存/可视化图库。
- `多语种合成数据生成汇总_20260702/`：历史汇总与可视化产物。
- `图片浏览_demo/data/image_manifest.json`：服务器生成后再重建。

## 环境安装

Linux 服务器建议 32 核/64G 起步，生成目录放本地 SSD。

```bash
git clone --depth 1 --single-branch --branch main <repo-url> synthetic-ocr-delivery
cd synthetic-ocr-delivery
# 说明：仓库历史含已淘汰的旧生成产物(~1.8GB)，浅克隆(--depth 1)只下当前快照(~45MB)。
# 切勿 git fetch --unshallow，否则会补下全历史。

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-server.txt

npm install
npx playwright install chromium
# 如服务器缺浏览器系统依赖，再执行：
npx playwright install-deps chromium
```

## 字体前置检查（服务器跑生成前必做）

`00_共享资源/fonts/` 不是"全语种字体整包"，它是字体支持机制：仓库内置各语种所需的开源字体（见下表），拷贝到用户字体目录并刷新 font cache 后由 fontconfig/Chromium 识别；不足的部分再从系统 Noto 字体补齐。**跑生成前必须先完成字体识别验证，否则会渲染出方块（tofu）。**

各语种字体来源：

- 维吾尔语、哈萨克语（Arabic-script）：仓库内置 `00_共享资源/fonts/arabic/`（Noto Naskh/Sans Arabic、Scheherazade New）。
- 藏语：仓库内置 `00_共享资源/fonts/tibetan/`（Noto Serif Tibetan）。
- 朝鲜语（谚文）：仓库内置 `00_共享资源/fonts/korean/`（Noto Sans KR）。
- 传统蒙古文：仓库内置 `00_共享资源/fonts/mongolian/`（Noto Sans Mongolian，竖排）。
- 兜底/CJK 混排：依赖服务器系统 Noto 字体（`fonts-noto`、`fonts-noto-cjk`）。

第一步，安装内置字体到用户字体目录：

```bash
mkdir -p ~/.local/share/fonts/synthetic-ocr
cp -R 00_共享资源/fonts/* ~/.local/share/fonts/synthetic-ocr/
fc-cache -fv
```

第二步，按需补装系统 Noto 字体（服务器缺字体时）：

```bash
# Ubuntu/Debian 示例
sudo apt-get update
sudo apt-get install -y fontconfig fonts-noto fonts-noto-cjk fonts-noto-extra
fc-cache -fv
```

第三步，验证目标字体已被 fontconfig 识别：

```bash
fc-list | grep -Ei "Tibetan|Mongolian|Noto Sans KR|Naskh|Scheherazade|Noto"
```

应能分别看到 `Noto Serif Tibetan`、`Noto Sans Mongolian`、`Noto Sans KR`、`Noto Naskh Arabic`、`Scheherazade New`。若某项缺失，先补装再继续。

第四步，跑单语种 smoke 后**人工看图**确认无方块，特别是 RTL（维吾尔/哈萨克）和传统蒙古文竖排，自动 QA 无法证明字形正确，只能排乱码/越界/图片占位等流程问题。

## 当前主入口

当前质量主线是 VL7 阅读顺序结构树，VL9 在 VL7 基础上增加视觉清理和真实图片资产接入。

核心入口：

- `03_通用生成pipeline/多语种合成数据生成/scripts/run_full_generation.py`
- `03_通用生成pipeline/多语种合成数据生成/scripts/render_table_dataset.mjs`
- `03_通用生成pipeline/多语种合成数据生成/scripts/attach_image_assets_to_vl7.py`
- `03_通用生成pipeline/多语种合成数据生成/scripts/qa_reading_flow_v1.py`
- `03_通用生成pipeline/多语种合成数据生成/scripts/make_reading_order_contact_sheet.py`

先跑单语种 smoke：

```bash
python 03_通用生成pipeline/多语种合成数据生成/scripts/run_full_generation.py \
  --version-name VL9 \
  --languages tibetan \
  --max-language-workers 1 \
  --attach-image-assets
```

确认 smoke 通过后，生成非蒙古语六语种：

```bash
python 03_通用生成pipeline/多语种合成数据生成/scripts/run_full_generation.py \
  --version-name VL9 \
  --languages tibetan zhuang korean bai uyghur kazakh \
  --max-language-workers 2 \
  --attach-image-assets
```

如果服务器稳定，可把 `--max-language-workers` 提到 `3`。如果 Chromium 或字体渲染不稳定，降到 `1`。

暂时不要把蒙古语并入 VL9；蒙古语竖排还有独立排版问题，需要单独修模板。

## Demo

生成完成后重建浏览 manifest：

```bash
python 图片浏览_demo/scripts/build_image_manifest.py \
  --version VL9 \
  --languages tibetan zhuang korean bai uyghur kazakh
```

启动静态服务：

```bash
python3 -m http.server 8766
```

浏览：

```text
http://127.0.0.1:8766/图片浏览_demo/index.html
```

## 已进入脚本的关键修复

- `render_table_dataset.mjs`：渲染成功后显式退出，避免浏览器句柄导致 Node 卡住。
- `run_full_generation.py`：支持 `--attach-image-assets`，生成 HTML 后、渲染前接入真实图片资产。
- `vl9_visual_style.py`：VL9 去掉普通文本框、大量隔离横线，保留表格/表单/证书/答题区/图片等语义结构线。
- `qa_no_unwanted_text_boxes.py`：增加对普通容器 class 的文本框风险扫描。

## 提交前检查

```bash
git status --short
git status --ignored --short | sed -n '1,120p'
find . -path ./.git -prune -o -type f -size +50M -print
```

如看到 `.venv*/`、`node_modules/`、`VL*/` 生成目录、`image_manifest.json` 进入 staged，先从暂存区移除。
