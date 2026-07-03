# Language Validity QA

- 版本目录：`/Users/dp/Downloads/中央民族大学合作项目/哈萨克语/03_合成数据生成_20260702/VL2`
- 语言：哈萨克语 / `kk-arab`
- 目标文字体系：`arabic`
- 允许 mixed 样本中文：True
- 文档数：72
- 通过文档数：72
- 文本块数：3323
- 异常/方框风险字符块：0
- 其他文字体系残留块：0
- 失败项：0
- 风险警告：1
- 结论：通过

## 类别汇总

| 类别 | 文档 | 通过 | pure | mixed | 平均目标文字占比 | 平均中文占比 |
|---|---:|---:|---:|---:|---:|---:|
| academic_paper | 6 | 6 | 3 | 3 | 0.7667 | 0.0734 |
| book_page | 6 | 6 | 3 | 3 | 0.7525 | 0.0717 |
| certificate_proof | 6 | 6 | 3 | 3 | 0.7225 | 0.0708 |
| complex_form | 6 | 6 | 3 | 3 | 0.7754 | 0.0729 |
| exam_paper | 6 | 6 | 3 | 3 | 0.6933 | 0.0774 |
| handwritten_letter | 6 | 6 | 3 | 3 | 0.7286 | 0.0759 |
| historical_classic | 6 | 6 | 3 | 3 | 0.7668 | 0.0729 |
| magazine_journal | 6 | 6 | 3 | 3 | 0.7658 | 0.0794 |
| newspaper_page | 6 | 6 | 3 | 3 | 0.7647 | 0.0774 |
| notice_announcement | 6 | 6 | 3 | 3 | 0.7399 | 0.0751 |
| sign_poster_scene | 6 | 6 | 3 | 3 | 0.7475 | 0.0791 |
| textbook_page | 6 | 6 | 3 | 3 | 0.7587 | 0.0731 |

## 失败样本

| document_id | block_id | issue | text_sample |
|---|---|---|---|


## 风险警告

| document_id | issue | value |
|---|---|---:|
| 03_exam_paper_json_03 | high_digit_ratio | 0.5185 |

## 边界说明

- 本 QA 能自动检查乱码、方框风险字符、私用区字符、错文字体系混入、pure/mixed 中文规则。
- 本 QA 不能完全证明民族语语法自然；语法自然性依赖真实文本源和抽检。
