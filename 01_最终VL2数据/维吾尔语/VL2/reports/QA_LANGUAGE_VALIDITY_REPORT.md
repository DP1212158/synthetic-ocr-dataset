# Language Validity QA

- 版本目录：`/Users/dp/Downloads/中央民族大学合作项目/维吾尔语/03_合成数据生成_20260702/VL2`
- 语言：维吾尔语 / `ug`
- 目标文字体系：`arabic`
- 允许 mixed 样本中文：True
- 文档数：72
- 通过文档数：72
- 文本块数：3324
- 异常/方框风险字符块：0
- 其他文字体系残留块：0
- 失败项：0
- 风险警告：1
- 结论：通过

## 类别汇总

| 类别 | 文档 | 通过 | pure | mixed | 平均目标文字占比 | 平均中文占比 |
|---|---:|---:|---:|---:|---:|---:|
| academic_paper | 6 | 6 | 3 | 3 | 0.7847 | 0.0732 |
| book_page | 6 | 6 | 3 | 3 | 0.7586 | 0.0726 |
| certificate_proof | 6 | 6 | 3 | 3 | 0.7456 | 0.0697 |
| complex_form | 6 | 6 | 3 | 3 | 0.7947 | 0.0731 |
| exam_paper | 6 | 6 | 3 | 3 | 0.715 | 0.0769 |
| handwritten_letter | 6 | 6 | 3 | 3 | 0.7527 | 0.0769 |
| historical_classic | 6 | 6 | 3 | 3 | 0.7746 | 0.073 |
| magazine_journal | 6 | 6 | 3 | 3 | 0.7779 | 0.0762 |
| newspaper_page | 6 | 6 | 3 | 3 | 0.7811 | 0.075 |
| notice_announcement | 6 | 6 | 3 | 3 | 0.7596 | 0.076 |
| sign_poster_scene | 6 | 6 | 3 | 3 | 0.7604 | 0.0756 |
| textbook_page | 6 | 6 | 3 | 3 | 0.7707 | 0.0725 |

## 失败样本

| document_id | block_id | issue | text_sample |
|---|---|---|---|


## 风险警告

| document_id | issue | value |
|---|---|---:|
| 03_exam_paper_json_03 | high_digit_ratio | 0.4828 |

## 边界说明

- 本 QA 能自动检查乱码、方框风险字符、私用区字符、错文字体系混入、pure/mixed 中文规则。
- 本 QA 不能完全证明民族语语法自然；语法自然性依赖真实文本源和抽检。
