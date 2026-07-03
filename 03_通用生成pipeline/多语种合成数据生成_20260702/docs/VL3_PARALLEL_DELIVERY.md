# VL3 并行交付运行说明

## Pilot

先跑壮语和藏语，验证长文本、去文本框和语义阅读顺序：

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

## Full VL3

Pilot 通过后跑 7 个语种。默认建议 3 个语种并行、每语种 4 个类别并行：

```bash
python3 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/run_multilingual_pipeline.py \
  --finalize-delivery \
  --delivery-output-name VL3 \
  --delivery-version-name VL3 \
  --max-language-workers 3 \
  --max-category-workers 4 \
  --resume-from-cache
```

如果本机字体渲染或 Chrome 内存不稳定，降级为：

```bash
python3 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/run_multilingual_pipeline.py \
  --finalize-delivery \
  --delivery-output-name VL3 \
  --delivery-version-name VL3 \
  --max-language-workers 2 \
  --max-category-workers 3 \
  --resume-from-cache
```

## Delivery Index

全量通过后汇总到交付目录：

```bash
python3 03_通用生成pipeline/多语种合成数据生成_20260702/scripts/build_vl3_delivery_index.py --force
```

输出：

- `01_最终VL3数据/`
- `05_总报告与索引/VL3_交付索引.json`
- `05_总报告与索引/VL3_QA_汇总.md`

## VL3 Gates

每个语种必须通过：

- `text_source_report.md`
- `QA_NO_UNWANTED_TEXT_BOX_REPORT.md`
- `QA_SEMANTIC_READING_ORDER_REPORT.md`
- 原有基础 QA、密度 QA、验收 QA、语言有效性 QA、图片资产 QA、增强质量 QA。
