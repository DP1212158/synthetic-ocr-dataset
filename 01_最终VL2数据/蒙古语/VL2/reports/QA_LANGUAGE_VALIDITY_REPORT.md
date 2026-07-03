# Language Validity QA

- 版本目录：`/Users/dp/Downloads/中央民族大学合作项目/蒙古语/03_合成数据生成_20260702/VL2`
- 语言：传统蒙古文 / `mn-trad`
- 目标文字体系：`mongolian`
- 允许 mixed 样本中文：True
- 文档数：72
- 通过文档数：72
- 文本块数：986
- 异常/方框风险字符块：0
- 其他文字体系残留块：0
- 失败项：0
- 风险警告：0
- 结论：通过

## 类别汇总

| 类别 | 文档 | 通过 | pure | mixed | 平均目标文字占比 | 平均中文占比 |
|---|---:|---:|---:|---:|---:|---:|
| academic_paper | 6 | 6 | 3 | 3 | 0.772 | 0.0639 |
| book_page | 6 | 6 | 3 | 3 | 0.771 | 0.0646 |
| certificate_proof | 6 | 6 | 3 | 3 | 0.7782 | 0.0622 |
| complex_form | 6 | 6 | 3 | 3 | 0.7927 | 0.0651 |
| exam_paper | 6 | 6 | 3 | 3 | 0.6612 | 0.0795 |
| handwritten_letter | 6 | 6 | 3 | 3 | 0.7725 | 0.0648 |
| historical_classic | 6 | 6 | 3 | 3 | 0.776 | 0.0619 |
| magazine_journal | 6 | 6 | 3 | 3 | 0.7813 | 0.0603 |
| newspaper_page | 6 | 6 | 3 | 3 | 0.7718 | 0.0703 |
| notice_announcement | 6 | 6 | 3 | 3 | 0.7833 | 0.0613 |
| sign_poster_scene | 6 | 6 | 3 | 3 | 0.7641 | 0.0804 |
| textbook_page | 6 | 6 | 3 | 3 | 0.7677 | 0.0616 |

## 失败样本

| document_id | block_id | issue | text_sample |
|---|---|---|---|


## 风险警告

| document_id | issue | value |
|---|---|---:|


## 边界说明

- 本 QA 能自动检查乱码、方框风险字符、私用区字符、错文字体系混入、pure/mixed 中文规则。
- 本 QA 不能完全证明民族语语法自然；语法自然性依赖真实文本源和抽检。
