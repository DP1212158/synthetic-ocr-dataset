# PP-DocLayout Assisted Reading Order

本目录用于把 PaddleX / PaddleOCR 的 PP-DocLayout 版面检测结果接入当前 VL 数据，辅助改进 `reading_order`。

## 设计原则

- 不直接用模型替代现有 OCR block 标签。
- PP-DocLayout 只提供页面区域证据，例如标题、正文、表格、图片、页眉、页脚。
- 最终阅读顺序仍由本项目脚本生成，排序依据为：语义组、PP 区域、列号、区域内位置。
- 默认不覆盖 VL4，而是生成独立输出目录，确认 overlay 后再决定是否写回。

## 安装依赖

建议在独立 Python 环境中安装 PaddleX：

```bash
python -m pip install "paddlex[ocr]" paddlepaddle
```

如果下载模型较慢，可以设置模型源：

```bash
export PADDLE_PDX_MODEL_SOURCE=bos
```

## 第一步：运行 PP-DocLayout 检测

以壮语 VL4 为例：

```bash
python 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/layout_order/run_pp_doclayout.py \
  --version-dir 02_语种工程资源/壮语/03_合成数据生成_20260702/VL4 \
  --model-name PP-DocLayout-L \
  --device cpu
```

输出缓存默认写入：

```text
02_语种工程资源/壮语/03_合成数据生成_20260702/VL4/reports/pp_doclayout/
```

缓存格式已经标准化为：

```json
{
  "boxes": [
    {
      "id": "pp_000",
      "label": "text",
      "score": 0.91,
      "coordinate": [x_min, y_min, x_max, y_max]
    }
  ]
}
```

## 第二步：生成 PP 辅助阅读顺序版本

```bash
python 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/layout_order/apply_pp_layout_reading_order.py \
  --version-dir 02_语种工程资源/壮语/03_合成数据生成_20260702/VL4 \
  --language-profile 02_语种工程资源/壮语/03_合成数据生成_20260702/configs/zhuang_language_profile.json
```

默认输出目录为：

```text
02_语种工程资源/壮语/03_合成数据生成_20260702/VL4_pp_order/
```

重点查看：

```text
VL4_pp_order/reports/contact_sheet_pp_layout_reading_order.jpg
VL4_pp_order/reports/pp_layout_reading_order_summary.json
```

## 写回模式

确认效果后才使用：

```bash
python 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/layout_order/apply_pp_layout_reading_order.py \
  --version-dir 02_语种工程资源/壮语/03_合成数据生成_20260702/VL4 \
  --language-profile 02_语种工程资源/壮语/03_合成数据生成_20260702/configs/zhuang_language_profile.json \
  --in-place
```

## 建议验收流程

先每语种抽样运行：

```bash
--limit 12
```

确认报纸、书籍页、学术文献、公告、考试卷这几类双栏或多区域页面的编号顺序正常后，再扩展到完整 72 张。

