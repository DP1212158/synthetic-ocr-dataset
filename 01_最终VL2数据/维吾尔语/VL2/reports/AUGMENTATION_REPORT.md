# Image Augmentation Report

- 源版本：`/Users/dp/Downloads/中央民族大学合作项目/维吾尔语/03_合成数据生成_20260702/VL2_clean_source`
- 输出版本：`/Users/dp/Downloads/中央民族大学合作项目/维吾尔语/03_合成数据生成_20260702/VL2`
- 图片数：72
- 类别数：12
- 随机种子：20260705
- 增强档位：delivery_all_light
- 增强强度：交付级平衡
- 几何策略：scale, category-aware rotation with expanded canvas, safe translation, safe edge crop
- 视觉策略：paper tint, texture, illumination, directional light, noise, speckles, blur, and JPEG recompression
- 方向光照样本数：72
- 增强专项风险样本：15

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
| newspaper_page | 6 | 6 | 0.3338 | 4.3075 | 2.5855 | 1.9453 | 0 |
| certificate_proof | 5 | 6 | 0.8719 | 2.9727 | 2.4492 | 2.0223 | 1 |
| exam_paper | 6 | 6 | 0.1081 | 3.806 | 2.6974 | 2.1499 | 2 |
| sign_poster_scene | 5 | 6 | 0.6287 | 7.584 | 3.3851 | 2.8294 | 1 |
| book_page | 6 | 6 | 0.6119 | 3.2112 | 2.3695 | 2.0806 | 1 |
| textbook_page | 6 | 6 | 0.4788 | 3.9598 | 2.5496 | 2.2575 | 2 |
| magazine_journal | 6 | 6 | 0.3471 | 3.6777 | 2.1481 | 2.3101 | 1 |
| academic_paper | 6 | 6 | 0.9077 | 2.9862 | 1.9494 | 2.1597 | 1 |
| historical_classic | 6 | 6 | 0.6266 | 4.1519 | 2.4092 | 2.2845 | 2 |
| notice_announcement | 6 | 6 | 0.3857 | 4.2353 | 2.453 | 2.1648 | 1 |
| complex_form | 6 | 6 | 0.1753 | 2.7616 | 2.065 | 1.905 | 0 |
| handwritten_letter | 6 | 6 | 0.0978 | 5.3952 | 2.4078 | 4.4704 | 3 |

## 风险样本

| 样本 | 类别 | 角度 | 框面积膨胀 | 原因 |
|---|---|---:|---:|---|
| 02_certificate_proof_json_03 | certificate_proof | 2.907 | 2.0223 | box_area_growth_high |
| 03_exam_paper_json_02 | exam_paper | 2.958 | 2.1499 | box_area_growth_high |
| 03_exam_paper_json_03 | exam_paper | 2.729 | 2.0791 | box_area_growth_high |
| 04_sign_poster_scene_json_05 | sign_poster_scene | 7.584 | 2.8294 | box_area_growth_high |
| 05_book_page_json_05 | book_page | 3.211 | 2.0806 | box_area_growth_high |
| 06_textbook_page_json_02 | textbook_page | 3.96 | 2.2575 | box_area_growth_high |
| 06_textbook_page_json_05 | textbook_page | 3.484 | 1.8026 | mean_luma_out_of_range |
| 07_magazine_journal_json_05 | magazine_journal | 3.678 | 2.3101 | box_area_growth_high |
| 08_academic_paper_json_03 | academic_paper | 2.986 | 2.1597 | box_area_growth_high |
| 09_historical_classic_json_03 | historical_classic | 2.599 | 2.2845 | box_area_growth_high |
| 09_historical_classic_json_05 | historical_classic | 4.152 | 2.025 | box_area_growth_high |
| 10_notice_announcement_json_04 | notice_announcement | 3.163 | 2.1648 | box_area_growth_high |
| 12_handwritten_letter_json_02 | handwritten_letter | 2.034 | 2.1449 | box_area_growth_high |
| 12_handwritten_letter_json_05 | handwritten_letter | 5.395 | 4.4704 | box_area_growth_high |
| 12_handwritten_letter_json_06 | handwritten_letter | 2.088 | 2.0292 | box_area_growth_high |

## 说明

本版本不做强透视、shear、纸张弯曲或复杂褶皱扭曲，优先保证矩形标签框与文本区域仍然贴合。
每张图片的完整增强参数见 `metadata/augmentation_manifest.json`。
