# Language Validity QA

- 版本目录：`/Users/dp/Downloads/中央民族大学合作项目/合成OCR数据集_交付版/02_语种工程资源/蒙古语/03_合成数据生成_20260702/VL4`
- 语言：传统蒙古文 / `mn-trad`
- 目标文字体系：`mongolian`
- 允许 mixed 样本中文：True
- 文档数：72
- 通过文档数：72
- 文本块数：985
- 异常/方框风险字符块：0
- 其他文字体系残留块：0
- 失败项：0
- 风险警告：0
- 结论：通过

## 类别汇总

| 类别 | 文档 | 通过 | pure | mixed | 平均目标文字占比 | 平均中文占比 |
|---|---:|---:|---:|---:|---:|---:|
| academic_paper | 6 | 6 | 3 | 3 | 0.7778 | 0.0628 |
| book_page | 6 | 6 | 3 | 3 | 0.7727 | 0.0633 |
| certificate_proof | 6 | 6 | 3 | 3 | 0.7725 | 0.0655 |
| complex_form | 6 | 6 | 3 | 3 | 0.7908 | 0.0692 |
| exam_paper | 6 | 6 | 3 | 3 | 0.6626 | 0.0779 |
| handwritten_letter | 6 | 6 | 3 | 3 | 0.7816 | 0.0647 |
| historical_classic | 6 | 6 | 3 | 3 | 0.7767 | 0.0645 |
| magazine_journal | 6 | 6 | 3 | 3 | 0.7762 | 0.0609 |
| newspaper_page | 6 | 6 | 3 | 3 | 0.769 | 0.0716 |
| notice_announcement | 6 | 6 | 3 | 3 | 0.7796 | 0.0623 |
| sign_poster_scene | 6 | 6 | 3 | 3 | 0.7559 | 0.0647 |
| textbook_page | 6 | 6 | 3 | 3 | 0.768 | 0.0638 |

## 失败样本

| document_id | block_id | issue | text_sample |
|---|---|---|---|


## 风险警告

| document_id | issue | value |
|---|---|---:|


## 边界说明

- 本 QA 能自动检查乱码、方框风险字符、私用区字符、错文字体系混入、pure/mixed 中文规则。
- 本 QA 不能完全证明民族语语法自然；语法自然性依赖真实文本源和抽检。
