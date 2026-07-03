# Language Validity QA

- 版本目录：`/Users/dp/Downloads/中央民族大学合作项目/藏语/03_合成数据生成_20260630/VL2`
- 语言：藏语 / `bo`
- 目标文字体系：`tibetan`
- 允许 mixed 样本中文：True
- 文档数：72
- 通过文档数：72
- 文本块数：2536
- 异常/方框风险字符块：0
- 其他文字体系残留块：0
- 失败项：0
- 风险警告：1
- 结论：通过

## 类别汇总

| 类别 | 文档 | 通过 | pure | mixed | 平均目标文字占比 | 平均中文占比 |
|---|---:|---:|---:|---:|---:|---:|
| academic_paper | 6 | 6 | 3 | 3 | 0.8917 | 0.0824 |
| book_page | 6 | 6 | 3 | 3 | 0.8861 | 0.0673 |
| certificate_proof | 6 | 6 | 3 | 3 | 0.8736 | 0.0802 |
| complex_form | 6 | 6 | 3 | 3 | 0.8727 | 0.0744 |
| exam_paper | 6 | 6 | 3 | 3 | 0.8659 | 0.0866 |
| handwritten_letter | 6 | 6 | 3 | 3 | 0.8928 | 0.0815 |
| historical_classic | 6 | 6 | 3 | 3 | 0.9005 | 0.0741 |
| magazine_journal | 6 | 6 | 3 | 3 | 0.8894 | 0.0839 |
| newspaper_page | 6 | 6 | 3 | 3 | 0.8911 | 0.0839 |
| notice_announcement | 6 | 6 | 3 | 3 | 0.8928 | 0.0861 |
| sign_poster_scene | 6 | 6 | 3 | 3 | 0.8511 | 0.118 |
| textbook_page | 6 | 6 | 3 | 3 | 0.8777 | 0.0775 |

## 失败样本

| document_id | block_id | issue | text_sample |
|---|---|---|---|


## 风险警告

| document_id | issue | value |
|---|---|---:|
| 03_sign_poster_scene_json_06 | mixed_cjk_ratio_out_of_range |  |

## 边界说明

- 本 QA 能自动检查乱码、方框风险字符、私用区字符、错文字体系混入、pure/mixed 中文规则。
- 本 QA 不能完全证明民族语语法自然；语法自然性依赖真实文本源和抽检。
