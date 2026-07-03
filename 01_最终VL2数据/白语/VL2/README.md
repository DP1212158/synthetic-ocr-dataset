# VL2 delivery

本版本由 `finalize_delivery_version.py` 生成，采用壮语 v4 固化后的准交付标准。

## 来源

- clean 输入目录：`/Users/dp/Downloads/中央民族大学合作项目/白语/03_合成数据生成_20260702/v1`
- 图片资产目录：`/Users/dp/Downloads/中央民族大学合作项目/random120-coco2014`

## 核心策略

- 每类 3 张纯目标语、3 张混合中文。
- 混合样本中文比例控制为 10%-30%。
- 图片占位已替换为真实图片。
- 已应用 `delivery_all_light` 数据增强。
- 标签新增 `reading_order / reading_group / reading_role / reading_order_confidence`。

## QA

- 中文混合 QA：True
- 图片资产 QA：True
- 阅读顺序 QA：True
- 语言有效性 QA：True
