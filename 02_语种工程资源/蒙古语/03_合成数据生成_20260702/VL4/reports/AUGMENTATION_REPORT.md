# Image Augmentation Report

- 源版本：`/Users/dp/Downloads/中央民族大学合作项目/合成OCR数据集_交付版/02_语种工程资源/蒙古语/03_合成数据生成_20260702/VL4_finalize_work`
- 输出版本：`/Users/dp/Downloads/中央民族大学合作项目/合成OCR数据集_交付版/02_语种工程资源/蒙古语/03_合成数据生成_20260702/VL4`
- 图片数：72
- 类别数：12
- 随机种子：20260705
- 增强档位：delivery_all_light
- 增强强度：交付级平衡
- 几何策略：scale, category-aware rotation with expanded canvas, safe translation, safe edge crop
- 视觉策略：paper tint, texture, illumination, directional light, noise, speckles, blur, and JPEG recompression
- 方向光照样本数：72
- 增强专项风险样本：37

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
| newspaper_page | 6 | 6 | 0.4186 | 4.3208 | 2.2948 | 2.4047 | 4 |
| certificate_proof | 5 | 6 | 0.8004 | 2.998 | 2.0322 | 1.8106 | 0 |
| exam_paper | 6 | 6 | 0.736 | 3.9385 | 2.5185 | 3.2626 | 4 |
| sign_poster_scene | 5 | 6 | 0.4961 | 5.8398 | 2.8132 | 2.5485 | 1 |
| book_page | 6 | 6 | 0.4558 | 4.4752 | 2.7567 | 4.2617 | 5 |
| textbook_page | 6 | 6 | 0.5376 | 4.1953 | 2.1627 | 2.655 | 2 |
| magazine_journal | 6 | 6 | 0.963 | 4.432 | 2.5677 | 2.8525 | 4 |
| academic_paper | 6 | 6 | 0.6153 | 2.6993 | 1.9018 | 2.8463 | 3 |
| historical_classic | 6 | 6 | 0.0955 | 5.0242 | 2.4817 | 4.5611 | 5 |
| notice_announcement | 6 | 6 | 0.2039 | 3.7688 | 2.5664 | 3.1666 | 3 |
| complex_form | 6 | 6 | 0.9272 | 2.8616 | 2.0143 | 2.4834 | 1 |
| handwritten_letter | 6 | 6 | 0.6845 | 5.0333 | 2.8904 | 2.7 | 5 |

## 风险样本

| 样本 | 类别 | 角度 | 框面积膨胀 | 原因 |
|---|---|---:|---:|---|
| 01_newspaper_page_vertical_tree_03 | newspaper_page | 3.155 | 2.3597 | box_area_growth_high |
| 01_newspaper_page_vertical_tree_04 | newspaper_page | 2.509 | 2.4047 | box_area_growth_high |
| 01_newspaper_page_vertical_tree_05 | newspaper_page | 4.321 | 2.3297 | box_area_growth_high |
| 01_newspaper_page_vertical_tree_06 | newspaper_page | 1.52 | 2.0336 | box_area_growth_high |
| 03_exam_paper_vertical_tree_02 | exam_paper | 3.939 | 1.9966 | box_area_growth_high |
| 03_exam_paper_vertical_tree_03 | exam_paper | 2.077 | 2.0505 | box_area_growth_high |
| 03_exam_paper_vertical_tree_04 | exam_paper | 2.91 | 3.2626 | box_area_growth_high |
| 03_exam_paper_vertical_tree_05 | exam_paper | 3.73 | 2.2182 | box_area_growth_high |
| 04_sign_poster_scene_vertical_tree_05 | sign_poster_scene | 5.84 | 2.5485 | box_area_growth_high |
| 05_book_page_vertical_tree_02 | book_page | 3.38 | 3.4941 | box_area_growth_high |
| 05_book_page_vertical_tree_03 | book_page | 3.85 | 2.6095 | box_area_growth_high |
| 05_book_page_vertical_tree_04 | book_page | 3.097 | 3.2722 | box_area_growth_high |
| 05_book_page_vertical_tree_05 | book_page | 4.475 | 4.2617 | box_area_growth_high |
| 05_book_page_vertical_tree_06 | book_page | 1.282 | 1.9833 | box_area_growth_high |
| 06_textbook_page_vertical_tree_03 | textbook_page | 2.632 | 2.655 | box_area_growth_high |
| 06_textbook_page_vertical_tree_05 | textbook_page | 4.195 | 2.2579 | box_area_growth_high |
| 07_magazine_journal_vertical_tree_03 | magazine_journal | 2.914 | 2.0393 | box_area_growth_high |
| 07_magazine_journal_vertical_tree_04 | magazine_journal | 3.117 | 2.8525 | box_area_growth_high |
| 07_magazine_journal_vertical_tree_05 | magazine_journal | 4.432 | 2.5773 | box_area_growth_high |
| 07_magazine_journal_vertical_tree_06 | magazine_journal | 2.252 | 2.4611 | box_area_growth_high |
| 08_academic_paper_vertical_tree_02 | academic_paper | 1.634 | 2.1117 | box_area_growth_high |
| 08_academic_paper_vertical_tree_04 | academic_paper | 2.434 | 2.8463 | box_area_growth_high |
| 08_academic_paper_vertical_tree_06 | academic_paper | 1.61 | 2.0324 | box_area_growth_high |
| 09_historical_classic_vertical_tree_02 | historical_classic | 2.71 | 2.8856 | box_area_growth_high |
| 09_historical_classic_vertical_tree_03 | historical_classic | 3.298 | 2.9848 | box_area_growth_high |
| 09_historical_classic_vertical_tree_04 | historical_classic | 1.778 | 2.171 | mean_luma_out_of_range, box_area_growth_high |
| 09_historical_classic_vertical_tree_05 | historical_classic | 5.024 | 4.5611 | box_area_growth_high |
| 09_historical_classic_vertical_tree_06 | historical_classic | 1.984 | 2.3968 | box_area_growth_high |
| 10_notice_announcement_vertical_tree_02 | notice_announcement | 3.028 | 2.3069 | box_area_growth_high |
| 10_notice_announcement_vertical_tree_04 | notice_announcement | 3.769 | 3.1666 | box_area_growth_high |
| 10_notice_announcement_vertical_tree_05 | notice_announcement | 3.379 | 2.1453 | box_area_growth_high |
| 11_complex_form_vertical_tree_06 | complex_form | 2.48 | 2.4834 | box_area_growth_high |
| 12_handwritten_letter_vertical_tree_02 | handwritten_letter | 2.947 | 2.7 | box_area_growth_high |
| 12_handwritten_letter_vertical_tree_03 | handwritten_letter | 3.792 | 2.2257 | box_area_growth_high |
| 12_handwritten_letter_vertical_tree_04 | handwritten_letter | 2.573 | 2.4789 | box_area_growth_high |
| 12_handwritten_letter_vertical_tree_05 | handwritten_letter | 5.033 | 2.4534 | box_area_growth_high |
| 12_handwritten_letter_vertical_tree_06 | handwritten_letter | 2.313 | 2.44 | box_area_growth_high |

## 说明

本版本不做强透视、shear、纸张弯曲或复杂褶皱扭曲，优先保证矩形标签框与文本区域仍然贴合。
每张图片的完整增强参数见 `metadata/augmentation_manifest.json`。
