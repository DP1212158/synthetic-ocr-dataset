# Text Records QA

- 文本文件：`/Users/dp/Downloads/中央民族大学合作项目/蒙古语/01_文本数据获取_20260702/data/local_verified_label_text_pool_20260702/records.jsonl`
- 语言：传统蒙古文 / `mn-trad`
- 总记录数：388
- 可用记录数：293
- 坏标题/数字标题记录数：388
- 硬问题记录数：95
- 标题质量是否阻断：False
- 是否需要安全标题回退：True
- 平均文本长度：253.08
- 平均目标文字占比：0.8236
- 平均私用区字符占比：0.0063
- 平均异常/方框风险字符占比：0.0096
- 结论：需处理

## 硬问题样本

| 行号 | record_id | title | script_ratio | digit_ratio | pua_ratio | unsupported_char_ratio | issues |
|---:|---|---|---:|---:|---:|---:|---|
| 6 | label_pool_00006 |  | 0.8467 | 0.0 | 0.0 | 0.0133 | unsupported_or_box_risk_chars, bad_or_numeric_title |
| 7 | label_pool_00007 |  | 0.8049 | 0.0 | 0.0 | 0.0488 | unsupported_or_box_risk_chars, bad_or_numeric_title |
| 10 | label_pool_00010 |  | 0.7857 | 0.0 | 0.0 | 0.0286 | unsupported_or_box_risk_chars, bad_or_numeric_title |
| 12 | label_pool_00012 |  | 0.8386 | 0.0 | 0.0 | 0.008 | unsupported_or_box_risk_chars, bad_or_numeric_title |
| 23 | label_pool_00023 |  | 0.8399 | 0.0 | 0.0 | 0.006 | unsupported_or_box_risk_chars, bad_or_numeric_title |
| 24 | label_pool_00024 |  | 0.8242 | 0.0 | 0.0 | 0.0046 | unsupported_or_box_risk_chars, bad_or_numeric_title |
| 33 | label_pool_00033 |  | 0.8022 | 0.0054 | 0.0 | 0.0027 | unsupported_or_box_risk_chars, bad_or_numeric_title |
| 45 | label_pool_00045 |  | 0.8431 | 0.0 | 0.0 | 0.0028 | unsupported_or_box_risk_chars, bad_or_numeric_title |
| 54 | label_pool_00054 |  | 0.8055 | 0.0254 | 0.0 | 0.0021 | unsupported_or_box_risk_chars, bad_or_numeric_title |
| 56 | label_pool_00056 |  | 0.8366 | 0.0024 | 0.0 | 0.0012 | unsupported_or_box_risk_chars, bad_or_numeric_title |
| 57 | label_pool_00057 |  | 0.8231 | 0.0204 | 0.0 | 0.0204 | unsupported_or_box_risk_chars, bad_or_numeric_title |
| 60 | label_pool_00060 |  | 0.8413 | 0.0 | 0.0 | 0.004 | unsupported_or_box_risk_chars, bad_or_numeric_title |

## 坏标题样本

| 行号 | record_id | title | text_length |
|---:|---|---|---:|
| 1 | label_pool_00001 |  | 51 |
| 2 | label_pool_00002 |  | 139 |
| 3 | label_pool_00003 |  | 282 |
| 4 | label_pool_00004 |  | 175 |
| 5 | label_pool_00005 |  | 84 |
| 6 | label_pool_00006 |  | 150 |
| 7 | label_pool_00007 |  | 41 |
| 8 | label_pool_00008 |  | 78 |
| 9 | label_pool_00009 |  | 524 |
| 10 | label_pool_00010 |  | 70 |
| 11 | label_pool_00011 |  | 247 |
| 12 | label_pool_00012 |  | 502 |
