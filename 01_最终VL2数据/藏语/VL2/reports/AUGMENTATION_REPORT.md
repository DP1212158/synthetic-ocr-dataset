# Image Augmentation Report

- 源版本：`/Users/dp/Downloads/中央民族大学合作项目/藏语/03_合成数据生成_20260630/VL2_clean_source`
- 输出版本：`/Users/dp/Downloads/中央民族大学合作项目/藏语/03_合成数据生成_20260630/VL2`
- 图片数：72
- 类别数：12
- 随机种子：20260705
- 增强档位：delivery_all_light
- 增强强度：交付级平衡
- 几何策略：scale, category-aware rotation with expanded canvas, safe translation, safe edge crop
- 视觉策略：paper tint, texture, illumination, directional light, noise, speckles, blur, and JPEG recompression
- 方向光照样本数：72
- 增强专项风险样本：16

## 类别增强族分布

| 类别 | 增强族 |
|---|---|
| newspaper_page | aged_archive:1, clean_scan:1, compressed_scan:1, printed_noise:1, shadow_photo:1, warm_paper:1 |
| certificate_proof | clean_scan:2, compressed_scan:1, shadow_photo:1, soft_copy:1, warm_paper:1 |
| exam_paper | clean_scan:1, compressed_scan:1, printed_noise:1, shadow_photo:1, soft_copy:1, warm_paper:1 |
| sign_poster_scene | clean_scan:1, compressed_scan:1, printed_noise:1, shadow_photo:2, warm_paper:1 |
| book_page | clean_scan:1, compressed_scan:1, printed_noise:1, shadow_photo:1, soft_copy:1, warm_paper:1 |
| textbook_page | clean_scan:1, compressed_scan:1, printed_noise:1, shadow_photo:1, soft_copy:1, warm_paper:1 |
| magazine_journal | clean_scan:1, compressed_scan:1, printed_noise:1, shadow_photo:1, soft_copy:1, warm_paper:1 |
| academic_paper | clean_scan:1, compressed_scan:1, printed_noise:1, shadow_photo:1, soft_copy:1, warm_paper:1 |
| historical_classic | aged_archive:1, low_contrast_archive:1, printed_noise:1, shadow_photo:1, soft_copy:1, warm_paper:1 |
| notice_announcement | clean_scan:1, compressed_scan:1, printed_noise:1, shadow_photo:1, soft_copy:1, warm_paper:1 |
| complex_form | clean_scan:1, compressed_scan:1, printed_noise:1, shadow_photo:1, soft_copy:1, warm_paper:1 |
| handwritten_letter | aged_archive:1, clean_scan:1, compressed_scan:1, shadow_photo:1, soft_copy:1, warm_paper:1 |

## 增强专项 QA

| 类别 | 增强族数 | 方向光照张数 | 最小角度 | 最大角度 | 平均角度 | 最大框面积膨胀 | 风险数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| newspaper_page | 6 | 6 | 0.3338 | 4.3075 | 2.5855 | 1.8705 | 0 |
| certificate_proof | 5 | 6 | 0.751 | 2.7776 | 1.9323 | 2.0716 | 2 |
| exam_paper | 6 | 6 | 0.9058 | 4.4798 | 2.5721 | 2.2845 | 3 |
| sign_poster_scene | 5 | 6 | 0.184 | 7.4267 | 2.7998 | 2.7094 | 1 |
| book_page | 6 | 6 | 0.6119 | 3.2112 | 2.3695 | 2.026 | 1 |
| textbook_page | 6 | 6 | 0.4788 | 3.9598 | 2.5496 | 2.5831 | 1 |
| magazine_journal | 6 | 6 | 0.3471 | 3.6777 | 2.1481 | 2.2683 | 1 |
| academic_paper | 6 | 6 | 0.9077 | 2.9862 | 1.9494 | 2.159 | 1 |
| historical_classic | 6 | 6 | 0.6266 | 4.1519 | 2.4092 | 2.2156 | 2 |
| notice_announcement | 6 | 6 | 0.3857 | 4.2353 | 2.453 | 2.0796 | 1 |
| complex_form | 6 | 6 | 0.1753 | 2.7616 | 2.065 | 1.8888 | 0 |
| handwritten_letter | 6 | 6 | 0.0978 | 5.3952 | 2.4078 | 4.4704 | 3 |

## 风险样本

| 样本 | 类别 | 角度 | 框面积膨胀 | 原因 |
|---|---|---:|---:|---|
| 01_certificate_proof_json_01 | certificate_proof | 0.751 | 1.2065 | mean_luma_out_of_range |
| 01_certificate_proof_json_03 | certificate_proof | 2.778 | 2.0716 | box_area_growth_high |
| 02_exam_paper_json_02 | exam_paper | 2.307 | 2.1852 | box_area_growth_high |
| 02_exam_paper_json_03 | exam_paper | 2.995 | 2.2845 | box_area_growth_high |
| 02_exam_paper_json_05 | exam_paper | 4.48 | 1.9727 | box_area_growth_high |
| 03_sign_poster_scene_json_05 | sign_poster_scene | 7.427 | 2.7094 | box_area_growth_high |
| 05_book_page_json_05 | book_page | 3.211 | 2.026 | box_area_growth_high |
| 06_textbook_page_json_02 | textbook_page | 3.96 | 2.5831 | box_area_growth_high |
| 07_magazine_journal_json_05 | magazine_journal | 3.678 | 2.2683 | box_area_growth_high |
| 08_academic_paper_json_03 | academic_paper | 2.986 | 2.159 | box_area_growth_high |
| 09_historical_classic_json_03 | historical_classic | 2.599 | 2.2156 | box_area_growth_high |
| 09_historical_classic_json_05 | historical_classic | 4.152 | 1.953 | box_area_growth_high |
| 10_notice_announcement_json_04 | notice_announcement | 3.163 | 2.0796 | box_area_growth_high |
| 12_handwritten_letter_json_02 | handwritten_letter | 2.034 | 2.1832 | box_area_growth_high |
| 12_handwritten_letter_json_05 | handwritten_letter | 5.395 | 4.4704 | box_area_growth_high |
| 12_handwritten_letter_json_06 | handwritten_letter | 2.088 | 2.512 | box_area_growth_high |

## 说明

本版本不做强透视、shear、纸张弯曲或复杂褶皱扭曲，优先保证矩形标签框与文本区域仍然贴合。
每张图片的完整增强参数见 `metadata/augmentation_manifest.json`。
