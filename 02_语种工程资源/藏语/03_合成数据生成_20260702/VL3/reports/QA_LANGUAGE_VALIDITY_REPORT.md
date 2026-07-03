# Language Validity QA

- 版本目录：`02_语种工程资源/藏语/03_合成数据生成_20260702/VL3`
- 语言：藏语 / `bo`
- 目标文字体系：`tibetan`
- 允许 mixed 样本中文：True
- 文档数：72
- 通过文档数：72
- 文本块数：2676
- 异常/方框风险字符块：0
- 其他文字体系残留块：0
- 失败项：0
- 风险警告：0
- 结论：通过

## 类别汇总

| 类别 | 文档 | 通过 | pure | mixed | 平均目标文字占比 | 平均中文占比 |
|---|---:|---:|---:|---:|---:|---:|
| academic_paper | 6 | 6 | 3 | 3 | 0.8882 | 0.0786 |
| book_page | 6 | 6 | 3 | 3 | 0.8919 | 0.0683 |
| certificate_proof | 6 | 6 | 3 | 3 | 0.8778 | 0.0717 |
| complex_form | 6 | 6 | 3 | 3 | 0.8751 | 0.0707 |
| exam_paper | 6 | 6 | 3 | 3 | 0.875 | 0.0817 |
| handwritten_letter | 6 | 6 | 3 | 3 | 0.8796 | 0.0846 |
| historical_classic | 6 | 6 | 3 | 3 | 0.8986 | 0.0679 |
| magazine_journal | 6 | 6 | 3 | 3 | 0.8909 | 0.0798 |
| newspaper_page | 6 | 6 | 3 | 3 | 0.8937 | 0.0812 |
| notice_announcement | 6 | 6 | 3 | 3 | 0.8844 | 0.0787 |
| sign_poster_scene | 6 | 6 | 3 | 3 | 0.8711 | 0.0961 |
| textbook_page | 6 | 6 | 3 | 3 | 0.8775 | 0.0733 |

## 失败样本

| document_id | block_id | issue | text_sample |
|---|---|---|---|


## 风险警告

| document_id | issue | value |
|---|---|---:|


## 边界说明

- 本 QA 能自动检查乱码、方框风险字符、私用区字符、错文字体系混入、pure/mixed 中文规则。
- 本 QA 不能完全证明民族语语法自然；语法自然性依赖真实文本源和抽检。
