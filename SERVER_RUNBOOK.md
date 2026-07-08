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
- `02_语种工程资源/*/03_合成数据生成_20260702/VL*/`、`VL_latest_*`：所有生成输出。
- `.venv*/`、`node_modules/`、`__pycache__/`、`.DS_Store`、日志和浏览器测试缓存。
- `05_总报告与索引/omnidocbench_cache/`、`05_总报告与索引/VL6_omni_original_templates/` 等下载缓存/可视化图库。
- `多语种合成数据生成汇总_20260702/`：历史汇总与可视化产物。
- `图片浏览_demo/data/image_manifest.json`：服务器生成后再重建。

## 环境安装

Linux 服务器建议 32 核/64G 起步，生成目录放本地 SSD。

```bash
git clone <repo-url> synthetic-ocr-delivery
cd synthetic-ocr-delivery

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-server.txt

npm install
npx playwright install chromium
# 如服务器缺浏览器系统依赖，再执行：
npx playwright install-deps chromium
```

字体需要在服务器可见：

```bash
mkdir -p ~/.local/share/fonts/synthetic-ocr
cp -R 00_共享资源/fonts/* ~/.local/share/fonts/synthetic-ocr/
fc-cache -fv
```

重点确认藏文、朝鲜文、阿拉伯系维吾尔/哈萨克、传统蒙古文字体都能被 Chromium 识别。

## 当前主入口

当前质量主线是 VL7 阅读顺序结构树，VL9 在 VL7 基础上增加视觉清理和真实图片资产接入。

核心入口：

- `03_通用生成pipeline/多语种合成数据生成_20260702/scripts/run_vl7_full.py`
- `03_通用生成pipeline/多语种合成数据生成_20260702/scripts/render_table_dataset.mjs`
- `03_通用生成pipeline/多语种合成数据生成_20260702/scripts/attach_image_assets_to_vl7.py`
- `03_通用生成pipeline/多语种合成数据生成_20260702/scripts/qa_reading_flow_v1.py`
- `03_通用生成pipeline/多语种合成数据生成_20260702/scripts/make_reading_order_contact_sheet.py`

先跑单语种 smoke：

```bash
python 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/run_vl7_full.py \
  --version-name VL9 \
  --languages tibetan \
  --max-language-workers 1 \
  --attach-image-assets
```

确认 smoke 通过后，生成非蒙古语六语种：

```bash
python 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/run_vl7_full.py \
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
- `run_vl7_full.py`：支持 `--attach-image-assets`，生成 HTML 后、渲染前接入真实图片资产。
- `vl9_visual_style.py`：VL9 去掉普通文本框、大量隔离横线，保留表格/表单/证书/答题区/图片等语义结构线。
- `qa_no_unwanted_text_boxes.py`：增加对普通容器 class 的文本框风险扫描。

## 提交前检查

```bash
git status --short
git status --ignored --short | sed -n '1,120p'
find . -path ./.git -prune -o -type f -size +50M -print
```

如看到 `.venv*/`、`node_modules/`、`VL*/` 生成目录、`image_manifest.json` 进入 staged，先从暂存区移除。
