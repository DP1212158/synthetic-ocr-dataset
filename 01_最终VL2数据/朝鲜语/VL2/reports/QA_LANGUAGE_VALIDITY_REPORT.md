# Language Validity QA

- 版本目录：`/Users/dp/Downloads/中央民族大学合作项目/朝鲜语/03_合成数据生成_20260702/VL2`
- 语言：朝鲜语 / `ko`
- 目标文字体系：`hangul`
- 允许 mixed 样本中文：True
- 文档数：72
- 通过文档数：72
- 文本块数：3324
- 异常/方框风险字符块：0
- 其他文字体系残留块：0
- 失败项：0
- 风险警告：3
- 结论：通过

## 类别汇总

| 类别 | 文档 | 通过 | pure | mixed | 平均目标文字占比 | 平均中文占比 |
|---|---:|---:|---:|---:|---:|---:|
| academic_paper | 6 | 6 | 3 | 3 | 0.654 | 0.0657 |
| book_page | 6 | 6 | 3 | 3 | 0.6535 | 0.0639 |
| certificate_proof | 6 | 6 | 3 | 3 | 0.6143 | 0.075 |
| complex_form | 6 | 6 | 3 | 3 | 0.6715 | 0.066 |
| exam_paper | 6 | 6 | 3 | 3 | 0.578 | 0.0701 |
| handwritten_letter | 6 | 6 | 3 | 3 | 0.6378 | 0.0692 |
| historical_classic | 6 | 6 | 3 | 3 | 0.6514 | 0.0664 |
| magazine_journal | 6 | 6 | 3 | 3 | 0.6507 | 0.0694 |
| newspaper_page | 6 | 6 | 3 | 3 | 0.6568 | 0.0674 |
| notice_announcement | 6 | 6 | 3 | 3 | 0.6398 | 0.0663 |
| sign_poster_scene | 6 | 6 | 3 | 3 | 0.6157 | 0.0804 |
| textbook_page | 6 | 6 | 3 | 3 | 0.6503 | 0.0666 |

## 失败样本

| document_id | block_id | issue | text_sample |
|---|---|---|---|


## 风险警告

| document_id | issue | value |
|---|---|---:|
| 03_exam_paper_json_03 | low_target_script_ratio |  |
| 03_exam_paper_json_03 | high_digit_ratio | 0.7 |
| 04_sign_poster_scene_json_01 | high_digit_ratio | 0.1895 |

## 边界说明

- 本 QA 能自动检查乱码、方框风险字符、私用区字符、错文字体系混入、pure/mixed 中文规则。
- 本 QA 不能完全证明民族语语法自然；语法自然性依赖真实文本源和抽检。
