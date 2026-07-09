# 蒙古语 VL8 服务器生成说明

本目录已整理 VL8 所需脚本，当前本机已暂停继续渲染。服务器上建议从脚本重新完整生成。

## 入口脚本

```bash
cd /path/to/合成OCR数据集_交付版
python3 02_语种工程资源/蒙古语/03_合成数据生成/scripts/run_mongolian_vl8.py --clean-rendered
```

如果服务器上也遇到 Chrome 关闭阶段卡住，可增加单类超时；脚本会检查该类 `render_manifest.json` 是否已经完整：

```bash
python3 02_语种工程资源/蒙古语/03_合成数据生成/scripts/run_mongolian_vl8.py --clean-rendered --render-timeout 180
```

如果服务器 Node/Playwright 不在默认路径，可显式指定：

```bash
PYTHON=/usr/bin/python3 NODE=/usr/bin/node NODE_PATH=/path/to/node_modules \
python3 02_语种工程资源/蒙古语/03_合成数据生成/scripts/run_mongolian_vl8.py --clean-rendered
```

## 分阶段执行

只重建 v4 结构树和 VL8 HTML：

```bash
python3 02_语种工程资源/蒙古语/03_合成数据生成/scripts/run_mongolian_vl8.py --skip-render --skip-category-qa --skip-version-qa
```

只渲染某一类，例如报纸页：

```bash
python3 02_语种工程资源/蒙古语/03_合成数据生成/scripts/run_mongolian_vl8.py --skip-build-templates --skip-generate --only-category 01
```

全部类别渲染完成后，只跑版本级 QA：

```bash
python3 02_语种工程资源/蒙古语/03_合成数据生成/scripts/run_mongolian_vl8.py --skip-build-templates --skip-generate --skip-render --skip-category-qa
```

## 关键文件

- `scripts/build_mongolian_vertical_templates_v4.py`：72 套 v4 结构树源。
- `scripts/generate_mongolian_vertical_from_json_v3.py`：读取 v4 index 并生成 VL8 HTML。
- `scripts/render_table_dataset.mjs`：HTML 渲染 PNG/label，已补 reading_order 和增量 `render_manifest.json`。
- `scripts/run_mongolian_vl8.py`：服务器端一键入口。
- `configs/mongolian_vertical_templates_v4/`：v4 结构树输出目录，包含 12 类 x 6 张。

## 验收目标

- 结构树：72 个模板 JSON，覆盖 12 类 x 6 张，无重复 `template_id`。
- 生成：`VL8` 下 72 HTML、72 PNG、72 label JSON。
- 类别 QA：每类 `qa_table_dataset.py` 通过。
- 版本 QA：`qa_layout_density.py` warning 为 0，`qa_version_acceptance.py --max-density-warnings 0` 通过。
- 阅读顺序：`qa_reading_flow_v1.py` 与 `make_reading_order_contact_sheet.py` 通过。
