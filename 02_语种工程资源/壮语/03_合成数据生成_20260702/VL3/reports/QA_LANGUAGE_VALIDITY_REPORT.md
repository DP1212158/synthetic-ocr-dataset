# Language Validity QA

- 版本目录：`02_语种工程资源/壮语/03_合成数据生成_20260702/VL3`
- 语言：壮语 / `za`
- 目标文字体系：`latin`
- 允许 mixed 样本中文：True
- 文档数：72
- 通过文档数：72
- 文本块数：2689
- 异常/方框风险字符块：0
- 其他文字体系残留块：0
- 失败项：0
- 风险警告：0
- 结论：通过

## 类别汇总

| 类别 | 文档 | 通过 | pure | mixed | 平均目标文字占比 | 平均中文占比 |
|---|---:|---:|---:|---:|---:|---:|
| academic_paper | 6 | 6 | 3 | 3 | 0.7369 | 0.0707 |
| book_page | 6 | 6 | 3 | 3 | 0.7477 | 0.0565 |
| certificate_proof | 6 | 6 | 3 | 3 | 0.7821 | 0.068 |
| complex_form | 6 | 6 | 3 | 3 | 0.7527 | 0.064 |
| exam_paper | 6 | 6 | 3 | 3 | 0.7768 | 0.0772 |
| handwritten_letter | 6 | 6 | 3 | 3 | 0.727 | 0.0771 |
| historical_classic | 6 | 6 | 3 | 3 | 0.7306 | 0.0655 |
| magazine_journal | 6 | 6 | 3 | 3 | 0.7642 | 0.0785 |
| newspaper_page | 6 | 6 | 3 | 3 | 0.7509 | 0.075 |
| notice_announcement | 6 | 6 | 3 | 3 | 0.7417 | 0.0756 |
| sign_poster_scene | 6 | 6 | 3 | 3 | 0.7261 | 0.092 |
| textbook_page | 6 | 6 | 3 | 3 | 0.7254 | 0.0663 |

## 失败样本

| document_id | block_id | issue | text_sample |
|---|---|---|---|


## 风险警告

| document_id | issue | value |
|---|---|---:|


## 边界说明

- 本 QA 能自动检查乱码、方框风险字符、私用区字符、错文字体系混入、pure/mixed 中文规则。
- 本 QA 不能完全证明民族语语法自然；语法自然性依赖真实文本源和抽检。
