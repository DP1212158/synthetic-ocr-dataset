#!/usr/bin/env python3
"""Build richer native vertical Mongolian JSON layout trees.

Version 4 keeps the v3 JSON schema shape but rebuilds the 72 layouts around
category-specific vertical document structures.  The output is intended for the
VL8 Mongolian delivery.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from build_mongolian_vertical_templates_v3 import CATEGORIES, answer, decor, image, text_el


PAGE_SIZES: dict[str, list[tuple[int, int]]] = {
    "newspaper_page": [(1320, 1860), (1180, 1760), (1440, 1760), (1240, 1640), (1360, 1820), (1180, 1680)],
    "certificate_proof": [(1040, 1460), (1120, 1520), (1280, 940), (1020, 1380), (1180, 1500), (980, 1320)],
    "exam_paper": [(1180, 1660), (1320, 1560), (1120, 1700), (1240, 1640), (1160, 1580), (1320, 1680)],
    "sign_poster_scene": [(1480, 860), (920, 1280), (980, 1360), (1500, 900), (1080, 1320), (900, 1180)],
    "book_page": [(980, 1540), (1060, 1500), (940, 1420), (1120, 1580), (980, 1500), (1040, 1480)],
    "textbook_page": [(1120, 1540), (1180, 1500), (1040, 1480), (1160, 1580), (1100, 1500), (1200, 1520)],
    "magazine_journal": [(1180, 1520), (1280, 1580), (1120, 1500), (1180, 1460), (1320, 1540), (1100, 1500)],
    "academic_paper": [(1180, 1640), (1320, 1620), (1160, 1580), (1060, 1600), (1280, 1600), (1120, 1540)],
    "historical_classic": [(960, 1640), (880, 1760), (1080, 1520), (960, 1600), (1120, 1660), (1040, 1560)],
    "notice_announcement": [(980, 1380), (1120, 1420), (960, 1360), (1180, 1500), (940, 1320), (1040, 1400)],
    "complex_form": [(1240, 1540), (1160, 1600), (1320, 1500), (1180, 1560), (1280, 1580), (1160, 1480)],
    "handwritten_letter": [(1040, 1500), (980, 1440), (1120, 1500), (980, 1380), (900, 1180), (1100, 1520)],
}


V4_NAMES: dict[str, list[tuple[str, str, str]]] = {
    "newspaper_page": [
        ("通栏头版多栏日报", "v4_broadsheet_masthead_columns", "通栏刊名、头条、新闻照片和密集竖栏同时出现。"),
        ("图片分区新闻版", "v4_photo_grid_news", "大图、短讯栏和下方正文形成明显图片新闻版。"),
        ("三段式晚报版", "v4_evening_three_band", "上中下三段新闻区，栏目边界清晰。"),
        ("副刊评论版", "v4_editorial_feature", "引言框、作者栏、正文栏和小图形成副刊感。"),
        ("地方综合周报版", "v4_local_weekly_mixed", "专题、广告盒、新闻列表和页脚组合。"),
        ("快讯索引版", "v4_dispatch_index", "大量短讯索引和竖线分隔，接近日报快讯页。"),
    ],
    "certificate_proof": [
        ("重框正式证书", "v4_formal_double_frame", "双重边框、纵向标题、正文和章印。"),
        ("机关证明函", "v4_official_proof_letter", "编号、证明正文、签发列和双章。"),
        ("横幅荣誉证书", "v4_landscape_award", "横向页面内保留竖排列，章位和标题突出。"),
        ("登记式证明", "v4_registry_certificate", "字段列、编号、备注和章印构成登记证明。"),
        ("奖状装饰版", "v4_award_decorated", "大标题、装饰色带、正文列和落款分区。"),
        ("简式单位证明", "v4_minimal_unit_proof", "留白较大但标题、正文、日期、章印完整。"),
    ],
    "exam_paper": [
        ("标准双栏试卷", "v4_exam_two_zone", "题目与答题区分列，上下两区。"),
        ("分卷分区测验", "v4_exam_sectioned", "三大题区，每区题目和答案列独立。"),
        ("阅读材料试卷", "v4_exam_reading", "长阅读材料与右侧问题区并列。"),
        ("填空答题卡", "v4_exam_blank_sheet", "短题和长答题线密集排列。"),
        ("综合练习卷", "v4_exam_mixed_practice", "评分栏、材料框、简答题混排。"),
        ("评分记录试卷", "v4_exam_scoring_grid", "题号、得分列和答题区形成正式评分卷。"),
    ],
    "sign_poster_scene": [
        ("横向店招门头", "v4_shopfront_banner", "横向招牌，极大标题和短说明。"),
        ("竖向公告牌", "v4_public_notice_board", "竖版公告牌，标题、正文和日期集中。"),
        ("活动海报", "v4_event_poster", "图片、时间地点和活动标题组合。"),
        ("导向标识牌", "v4_wayfinding_board", "多条导向项和编号列。"),
        ("墙面宣传栏", "v4_wall_publicity_panel", "宣传栏内含图片、栏目和短条目。"),
        ("警示提示牌", "v4_warning_sign", "少量大字、重点提示和边框。"),
    ],
    "book_page": [
        ("密排正文书页", "v4_dense_book_columns", "多列正文铺满，页眉页码清晰。"),
        ("页眉章标题书页", "v4_running_header_book", "页眉、章节题、正文和页脚分离。"),
        ("章首页留白版", "v4_chapter_opener", "大章题、引言和较少正文形成章首页。"),
        ("批注边栏书页", "v4_annotated_margin_book", "正文旁带边注和批注框。"),
        ("上下分段书页", "v4_segmented_book", "正文分为两段区域，栏高不同。"),
        ("目录索引书页", "v4_contents_index_book", "目录短项和页码列密集排列。"),
    ],
    "textbook_page": [
        ("图文课程页", "v4_lesson_figure", "课程标题、图示、说明和课文。"),
        ("词汇练习页", "v4_vocab_workbook", "词汇字段、例句和练习区。"),
        ("知识点讲解页", "v4_concept_boxes", "知识框、正文、提示栏组合。"),
        ("活动任务页", "v4_activity_steps", "步骤、填写区和提示卡片。"),
        ("复习检测页", "v4_review_questions", "复习正文、题目和答题区。"),
        ("图表教材页", "v4_diagram_textbook", "大图表、图注、正文和要点。"),
    ],
    "magazine_journal": [
        ("封面式杂志页", "v4_magazine_cover", "大图、大标题和封面短线索。"),
        ("专题文章内页", "v4_feature_article", "专题标题、图片、正文多栏。"),
        ("访谈问答页", "v4_interview_qa", "人物图与问答列交错。"),
        ("栏目目录页", "v4_contents_columns", "目录条目、页码和栏目色块。"),
        ("图片故事页", "v4_photo_story", "多图配短文，视觉块明显。"),
        ("评论专栏页", "v4_opinion_column", "引语框、作者信息和正文专栏。"),
    ],
    "academic_paper": [
        ("论文首页", "v4_academic_first_page", "题名、摘要、关键词、正文和图表。"),
        ("双栏论文内页", "v4_academic_two_column", "双栏正文、页脚、图注。"),
        ("实验报告页", "v4_experiment_report", "方法、结果、图表和说明。"),
        ("参考文献页", "v4_references_dense", "参考文献条目密集排列。"),
        ("图表论文页", "v4_figure_table_paper", "大图表和分段说明并重。"),
        ("会议摘要页", "v4_conference_abstract", "会议编号、摘要、作者和正文。"),
    ],
    "historical_classic": [
        ("古籍刻本页", "v4_woodblock_classic", "双框、版心、正文和页码。"),
        ("卷轴长文档", "v4_scroll_document", "长条卷轴感，正文区集中。"),
        ("档案记录页", "v4_archive_record", "编号、正文、章印和附件栏。"),
        ("碑帖拓片页", "v4_rubbing_page", "深底浅字风格与竖列。"),
        ("批注古籍页", "v4_annotated_classic", "正文、眉批、边批明显分区。"),
        ("谱牒名单页", "v4_genealogy_register", "多列名单和分隔线。"),
    ],
    "notice_announcement": [
        ("正式公告页", "v4_formal_notice", "标题、正文、日期、签发栏完整。"),
        ("公告栏多条通知", "v4_bulletin_board", "多个通知条目分区排列。"),
        ("会议通知", "v4_meeting_notice", "时间地点事项字段与正文。"),
        ("公示名单", "v4_public_list", "名单短项和编号列。"),
        ("紧急提示", "v4_urgent_notice", "醒目色块、重点说明和联系人。"),
        ("校园通知", "v4_campus_notice", "轻量公告结构，信息完整。"),
    ],
    "complex_form": [
        ("登记申请表", "v4_registration_form", "标题、字段、备注和签名区。"),
        ("人员信息表", "v4_personnel_form", "人员字段密集，带章位。"),
        ("检查清单表", "v4_inspection_checklist", "勾选列和说明列。"),
        ("调查问卷", "v4_survey_form", "问题、选项、填写区并列。"),
        ("业务办理单", "v4_service_sheet", "分区字段、处理意见和复核栏。"),
        ("日志记录表", "v4_log_record", "记录条目、备注和审核列。"),
    ],
    "handwritten_letter": [
        ("私人信件", "v4_personal_letter", "称呼、正文、署名和日期。"),
        ("课堂笔记", "v4_class_notes", "标题、要点、边栏标记。"),
        ("会议记录", "v4_meeting_minutes", "事项、结论和补充列。"),
        ("日记页", "v4_diary_page", "日期、正文和短注。"),
        ("便签留言", "v4_memo_note", "便签纸、短正文和附注。"),
        ("批注信纸", "v4_annotated_letter", "信纸正文、批注和补充说明。"),
    ],
}


def cols(prefix: str, xs: list[int], y: int, w: int, h: int, label: str = "paragraph", cls: str = "body", min_chars: int = 28, max_chars: int = 110) -> list[dict[str, Any]]:
    return [text_el(f"{prefix}_{i:02d}", label, x, y, w, h, "vertical_text_column", cls, "fill", min_chars, max_chars) for i, x in enumerate(xs, 1)]


def items(prefix: str, xs: list[int], y: int, w: int, h: int, label: str = "list_item", cls: str = "small") -> list[dict[str, Any]]:
    return [text_el(f"{prefix}_{i:02d}", label, x, y, w, h, "short_item", cls, "fill", 12, 44) for i, x in enumerate(xs, 1)]


def field_grid(prefix: str, x0: int, y0: int, cols_n: int, rows_n: int, col_gap: int, row_gap: int, value_h: int = 260) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    n = 1
    for row in range(rows_n):
        for col in range(cols_n):
            x = x0 + col * col_gap
            y = y0 + row * row_gap
            out.append(text_el(f"{prefix}_label_{n:02d}", "field_label", x, y, 28, value_h, "field_label", "tiny", "safe_fragment", 2, 10))
            out.append(text_el(f"{prefix}_value_{n:02d}", "field_value", x + 34, y, 42, value_h, "field_value", "small boxed", "short", 6, 24))
            n += 1
    return out


def q_and_a(prefix: str, xs: list[int], y: int, q_h: int, a_h: int, q_w: int = 32, a_w: int = 38) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, x in enumerate(xs, 1):
        out.append(text_el(f"{prefix}_q_{i:02d}", "question_text", x, y, q_w, q_h, "question", "body", "question", 12, 42))
        out.append(answer(f"{prefix}_a_{i:02d}", x + q_w + 6, y, a_w, a_h))
    return out


def caption(el_id: str, x: int, y: int, w: int, h: int, target_id: str) -> dict[str, Any]:
    item = text_el(el_id, "caption", x, y, w, h, "caption", "small", "short", 12, 34)
    item["attributes"] = {"caption_of": target_id}
    return item


def page_for(category: str, variant: int) -> tuple[int, int]:
    return PAGE_SIZES[category][variant - 1]


def newspaper(v: int) -> list[dict[str, Any]]:
    w, h = page_for("newspaper_page", v)
    if v == 1:
        return [decor("outer", 38, 42, w - 76, h - 84, "box"), text_el("masthead", "document_title", 70, 70, 70, h - 180, "masthead", "title", "safe_fragment", 4, 28), text_el("date", "metadata", 158, 70, 28, h - 180, "issue", "tiny", "literal", value="20260702"), decor("lead_rule", 220, 76, 2, h - 190, "rule-v"), text_el("lead", "section_title", 250, 86, 54, h - 220, "lead", "title", "title", 8, 48), *cols("lead_body", [330, 378, 426, 474, 522], 96, 30, h - 240, "paragraph", "body", 54, 145), image("news_photo", 610, 110, 260, 430, "news_photo"), caption("caption", 894, 110, 28, 430, "news_photo"), *cols("right_body", [610, 658, 706, 754, 802, 850, 940, 988, 1036, 1084], 610, 30, h - 780, "paragraph", "body", 30, 96), text_el("footer", "footer", w - 78, 90, 24, h - 220, "footer", "tiny", "literal", value="01")]
    if v == 2:
        return [text_el("name", "document_title", 56, 60, 58, h - 120, "name", "title", "safe_fragment", 4, 28), image("hero", 150, 80, 430, 620, "hero_photo"), text_el("headline", "section_title", 630, 86, 62, 560, "headline", "title", "title", 8, 48), *cols("hero_text", [720, 772, 824, 876], 90, 34, 560, "paragraph", "body", 28, 90), decor("lower_rule", 130, 760, w - 220, 2, "rule-h"), *cols("lower", list(range(160, w - 110, 52)), 820, 30, 780, "paragraph", "body", 26, 88), *items("brief", list(range(165, w - 180, 78)), 1630, 26, 90)]
    if v == 3:
        return [decor("top_band", 50, 52, w - 100, 450, "box note-fill"), text_el("name", "document_title", 90, 76, 58, 360, "evening_name", "title", "safe_fragment", 4, 28), *items("top_news", list(range(200, w - 180, 72)), 92, 30, 340), decor("mid_band", 70, 560, w - 140, 520, "box"), text_el("mid_title", "section_title", 116, 595, 44, 450, "section", "subtitle", "title", 8, 38), *cols("mid", list(range(190, w - 190, 56)), 600, 32, 440, "paragraph", "body", 22, 72), image("photo", 890, 610, 300, 380, "photo"), decor("bottom_band", 50, 1130, w - 100, 540, "box soft-fill"), *cols("bottom", list(range(100, w - 130, 50)), 1170, 28, 420, "paragraph", "small", 18, 60)]
    if v == 4:
        return [text_el("title", "document_title", 62, 72, 64, h - 140, "feature_title", "title", "title", 8, 48), decor("quote_box", 170, 100, 220, 620, "box note-fill"), text_el("quote", "paragraph", 212, 130, 38, 560, "quote", "subtitle", "fill", 30, 86), image("portrait", 430, 110, 190, 320, "portrait"), text_el("author", "metadata", 650, 110, 28, 320, "author", "tiny", "short", 6, 20), *cols("body", list(range(430, w - 110, 50)), 500, 32, 980, "paragraph", "body", 32, 105), *items("side", [180, 222, 264, 306], 820, 28, 520)]
    if v == 5:
        return [text_el("weekly", "document_title", 52, 58, 62, h - 120, "weekly", "title", "safe_fragment", 4, 28), text_el("topic", "section_title", 142, 80, 52, 720, "topic", "title", "title", 8, 46), *cols("topic_body", [220, 270, 320, 370, 420], 90, 32, 700, "paragraph", "body", 30, 96), image("center", 530, 110, 310, 520, "feature_image"), decor("ad", 910, 120, 230, 500, "box soft-fill"), *items("ad_item", [940, 982, 1024, 1066], 150, 30, 430), *cols("bottom", list(range(170, w - 120, 48)), 900, 30, 720, "paragraph", "body", 22, 76)]
    return [text_el("name", "document_title", 46, 52, 46, h - 105, "dispatch_name", "title", "safe_fragment", 4, 28), text_el("date", "metadata", 104, 52, 26, h - 105, "date", "tiny", "literal", value="20260702"), *[decor(f"rule_{i:02d}", x, 72, 1, h - 210, "rule-v") for i, x in enumerate(range(150, w - 80, 118), 1)], *[text_el(f"topic_{i:02d}", "section_title", x + 18, 82, 30, 300, "brief_topic", "subtitle", "title", 5, 24) for i, x in enumerate(range(150, w - 130, 118), 1)], *items("dispatch", list(range(192, w - 86, 58)), 420, 26, h - 620)]


def certificate(v: int) -> list[dict[str, Any]]:
    w, h = page_for("certificate_proof", v)
    if v == 3:
        return [decor("outer", 48, 48, w - 96, h - 96, "box ornate"), text_el("title", "document_title", 120, 96, 82, h - 190, "award_title", "title", "safe_fragment", 4, 28), text_el("sub", "document_subtitle", 260, 126, 50, h - 250, "award_subtitle", "subtitle", "title", 8, 38), *cols("body", [390, 450, 510, 570, 630, 690], 136, 34, h - 300, "paragraph", "body", 24, 74), text_el("seal", "seal", w - 230, 260, 126, 126, "seal", "subtitle stamp", "safe_fragment", 2, 10), text_el("date", "metadata", w - 150, 120, 32, h - 260, "date", "small", "literal", value="20260702")]
    out = [decor("outer", 52, 52, w - 104, h - 104, "box ornate" if v in {1, 5} else "box"), text_el("serial", "metadata", 94, 100, 30, h - 210, "serial", "tiny", "literal", value="20260702"), text_el("title", "document_title", 170, 120, 62, h - 260, "title", "title", "safe_fragment", 4, 28)]
    if v == 1:
        out += [text_el("subtitle", "document_subtitle", 286, 150, 44, h - 360, "subtitle", "subtitle", "title", 8, 38), *cols("body", [400, 458, 516, 574, 632], 170, 36, h - 520, "paragraph", "body", 26, 76), text_el("seal", "seal", 805, 780, 120, 120, "seal", "subtitle stamp", "safe_fragment", 2, 10), text_el("date", "metadata", 835, 180, 34, 700, "date", "small", "literal", value="20260702")]
    elif v == 2:
        out += [*cols("body", [290, 350, 410, 470, 530, 590], 160, 36, h - 430, "paragraph", "body", 24, 72), text_el("seal_a", "seal", 780, 250, 110, 110, "seal", "subtitle stamp", "safe_fragment", 2, 10), text_el("seal_b", "seal", 805, 870, 110, 110, "seal", "subtitle stamp", "safe_fragment", 2, 10)]
    elif v == 4:
        out += field_grid("reg", 280, 150, 4, 2, 118, 410) + [text_el("note", "paragraph", 820, 170, 44, 820, "note", "body", "fill", 22, 68), text_el("seal", "seal", 830, 920, 104, 104, "seal", "subtitle stamp", "safe_fragment", 2, 10)]
    elif v == 5:
        out += [decor("ribbon", 280, 110, 100, h - 220, "soft-fill"), text_el("subtitle", "document_subtitle", 430, 150, 48, h - 380, "subtitle", "subtitle", "title", 8, 40), *cols("body", [540, 600, 660, 720, 780], 170, 36, h - 470, "paragraph", "body", 24, 76), text_el("seal", "seal", 920, 800, 124, 124, "seal", "subtitle stamp", "safe_fragment", 2, 10)]
    else:
        out += [*cols("body", [290, 350, 410, 470], 180, 38, h - 420, "paragraph", "body", 22, 68), text_el("date", "metadata", 760, 190, 34, 700, "date", "small", "literal", value="20260702"), text_el("seal", "seal", 800, 700, 112, 112, "seal", "subtitle stamp", "safe_fragment", 2, 10)]
    return out


def exam(v: int) -> list[dict[str, Any]]:
    w, h = page_for("exam_paper", v)
    out = [text_el("title", "document_title", 56, 56, 52, h - 120, "exam_title", "title", "title", 8, 42), text_el("meta", "metadata", 126, 60, 28, h - 130, "exam_meta", "tiny", "literal", value="2026")]
    if v == 1:
        return out + q_and_a("top", list(range(220, w - 200, 92)), 90, 610, 610) + q_and_a("bottom", list(range(220, w - 200, 92)), 820, 610, 610)
    if v == 2:
        for band, y in enumerate([90, 585, 1080], 1):
            out.append(text_el(f"section_{band}", "section_title", 205, y, 40, 390, "section", "subtitle", "safe_fragment", 2, 14))
            out += q_and_a(f"sec{band}", list(range(285, w - 190, 110)), y + 8, 350, 350)
        return out
    if v == 3:
        return out + [decor("reading_box", 190, 86, 330, h - 220, "box note-fill"), text_el("reading_title", "section_title", 225, 120, 40, h - 300, "reading_title", "subtitle", "title", 6, 30), *cols("reading", [290, 336, 382, 428], 130, 30, h - 320, "paragraph", "body", 38, 110)] + q_and_a("readq", list(range(580, w - 130, 86)), 130, 600, 600) + q_and_a("readq_b", list(range(580, w - 130, 86)), 870, 520, 520)
    if v == 4:
        return out + [decor("answer_sheet", 180, 80, w - 260, h - 220, "box")] + q_and_a("blank", list(range(230, w - 120, 70)), 120, h - 340, h - 340, 28, 30)
    if v == 5:
        return out + [decor("score", 180, 90, 130, h - 250, "box soft-fill"), text_el("rubric", "paragraph", 215, 120, 34, h - 320, "rubric", "small", "fill", 20, 62)] + q_and_a("mix_a", list(range(360, w - 150, 92)), 120, 520, 520) + q_and_a("mix_b", list(range(360, w - 150, 92)), 780, 560, 560)
    for x in range(230, w - 150, 92):
        i = len([e for e in out if e.get("label") == "question_text"]) + 1
        out += [text_el(f"q_{i}", "question_text", x, 110, 34, 470, "question", "body", "question", 12, 40), answer(f"a_{i}", x + 42, 110, 40, 470), text_el(f"score_{i}", "metadata", x, 640, 28, 250, "score", "tiny", "literal", value=str(i)), text_el(f"q_b_{i}", "question_text", x, 950, 34, 470, "question", "body", "question", 12, 40), answer(f"a_b_{i}", x + 42, 950, 40, 470)]
    return out


def sign(v: int) -> list[dict[str, Any]]:
    w, h = page_for("sign_poster_scene", v)
    if v == 1:
        return [decor("panel", 48, 48, w - 96, h - 96, "box note-fill"), text_el("title", "document_title", 120, 100, 90, h - 200, "shop_title", "title", "safe_fragment", 4, 24), text_el("sub", "section_title", 300, 120, 54, h - 240, "shop_sub", "subtitle", "title", 6, 28), *cols("body", [420, 500, 580, 660, 740, 820, 900], 130, 40, h - 260, "paragraph", "body", 16, 52), text_el("meta", "metadata", w - 150, 140, 40, h - 280, "meta", "small", "literal", value="2026")]
    if v == 2:
        return [decor("board", 58, 58, w - 116, h - 116, "box"), text_el("title", "document_title", 130, 100, 78, h - 220, "notice_title", "title", "safe_fragment", 4, 28), *cols("body", [270, 340, 410, 480, 550], 130, 42, h - 320, "paragraph", "body", 18, 58), text_el("date", "metadata", 760, 140, 34, h - 360, "date", "small", "literal", value="20260702")]
    if v == 3:
        return [decor("bg", 60, 60, w - 120, h - 120, "box soft-fill"), image("poster_image", 110, 100, 300, 460, "poster_image"), text_el("title", "document_title", 460, 100, 80, h - 240, "event_title", "title", "safe_fragment", 4, 28), *cols("event", [585, 650, 715, 780], 130, 40, h - 340, "paragraph", "body", 18, 58), text_el("time", "metadata", 850, 140, 36, h - 360, "time", "small", "literal", value="20260702")]
    if v == 4:
        return [decor("panel", 54, 54, w - 108, h - 108, "box"), text_el("title", "document_title", 120, 100, 76, h - 220, "wayfinding", "title", "safe_fragment", 4, 24), *[text_el(f"dir_{i}", "list_item", x, 120, 42, h - 280, "direction", "subtitle boxed", "fill", 12, 36) for i, x in enumerate(range(300, w - 220, 160), 1)]]
    if v == 5:
        return [decor("wall", 62, 62, w - 124, h - 124, "box note-fill"), image("image", 120, 110, 310, 420, "publicity_image"), text_el("title", "document_title", 475, 110, 68, h - 250, "wall_title", "title", "safe_fragment", 4, 28), *items("wall_item", [580, 640, 700, 760, 820, 880], 140, 36, h - 360)]
    return [decor("warning", 80, 80, w - 160, h - 160, "box urgent-fill"), text_el("title", "document_title", 190, 140, 92, h - 300, "warning_title", "title", "safe_fragment", 4, 24), text_el("message", "paragraph", 390, 160, 58, h - 360, "warning_message", "subtitle", "fill", 18, 58), text_el("detail", "note", 545, 180, 38, h - 420, "warning_detail", "small", "fill", 12, 40), text_el("meta", "metadata", 640, 190, 30, h - 460, "warning_meta", "tiny", "literal", value="2026")]


def book(v: int, textbook: bool = False) -> list[dict[str, Any]]:
    category = "textbook_page" if textbook else "book_page"
    w, h = page_for(category, v)
    if not textbook:
        if v == 1:
            return [text_el("page", "page_number", 54, 70, 28, h - 160, "page", "tiny", "literal", value="1"), text_el("header", "metadata", 96, 70, 26, h - 160, "header", "tiny", "short", 4, 16), *cols("body", list(range(160, w - 90, 48)), 80, 30, h - 180, "paragraph", "body", 34, 112)]
        if v == 2:
            return [text_el("title", "document_title", 76, 72, 48, h - 150, "chapter", "title", "title", 8, 42), decor("header_rule", 146, 80, 2, h - 180, "rule-v"), *cols("body", list(range(190, w - 120, 56)), 88, 32, h - 220, "paragraph", "body", 30, 100), text_el("footer", "page_number", w - 75, 90, 24, h - 220, "page", "tiny", "literal", value=str(v))]
        if v == 3:
            return [text_el("chapter", "document_title", 130, 130, 84, h - 350, "chapter_opener", "title", "title", 8, 44), text_el("intro", "paragraph", 300, 220, 46, h - 560, "intro", "subtitle", "fill", 24, 76), *cols("body", list(range(430, w - 100, 58)), 260, 32, h - 620, "paragraph", "body", 22, 74)]
        if v == 4:
            return [*cols("main", list(range(120, 760, 50)), 88, 30, h - 190, "paragraph", "body", 32, 108), decor("margin", 820, 110, 220, h - 260, "box note-fill"), *items("note", [850, 890, 930, 970], 140, 26, h - 340)]
        if v == 5:
            return [text_el("title", "document_title", 90, 80, 48, 620, "section", "title", "title", 8, 40), *cols("top", list(range(180, w - 130, 54)), 90, 30, 560, "paragraph", "body", 22, 74), decor("split", 90, 720, w - 180, 2, "rule-h"), *cols("bottom", list(range(140, w - 110, 50)), 780, 30, 560, "paragraph", "body", 22, 74)]
        return [text_el("title", "document_title", 90, 80, 50, h - 170, "contents", "title", "safe_fragment", 4, 24), *items("content", list(range(170, w - 110, 48)), 120, 30, h - 330), *[text_el(f"page_{i:02d}", "page_number", x + 30, 120, 18, h - 330, "page", "tiny", "literal", value=str(10 + i)) for i, x in enumerate(range(170, w - 110, 48), 1)]]
    if v == 1:
        return [text_el("chapter", "chapter_title", 80, 70, 54, h - 150, "lesson", "title", "title", 8, 42), image("fig", 180, 100, 240, 460, "lesson_figure"), caption("caption", 450, 100, 30, 460, "fig"), *cols("body", list(range(520, w - 100, 54)), 100, 32, h - 250, "paragraph", "body", 28, 96)]
    if v == 2:
        return [text_el("title", "chapter_title", 78, 70, 54, h - 150, "vocab", "title", "safe_fragment", 4, 24), *field_grid("vocab", 180, 100, 5, 2, 116, 520), *cols("examples", list(range(810, w - 100, 54)), 120, 32, h - 310, "paragraph", "body", 20, 66)]
    if v == 3:
        return [text_el("title", "chapter_title", 80, 70, 54, h - 150, "concept", "title", "title", 8, 40), decor("key_box", 180, 100, 230, 980, "box soft-fill"), text_el("key", "note", 230, 130, 38, 910, "key", "small", "fill", 20, 66), *cols("body", list(range(470, w - 100, 54)), 110, 32, h - 280, "paragraph", "body", 26, 90)]
    if v == 4:
        return [text_el("title", "chapter_title", 80, 70, 54, h - 150, "activity", "title", "safe_fragment", 4, 24), *items("step", list(range(190, 750, 92)), 120, 36, 640), *[answer(f"ans_{i:02d}", x + 42, 120, 42, 640) for i, x in enumerate(range(190, 750, 92), 1)], *cols("hint", list(range(820, w - 110, 50)), 140, 30, h - 350, "note", "small", 16, 50)]
    if v == 5:
        return [text_el("title", "chapter_title", 80, 70, 54, h - 150, "review", "title", "safe_fragment", 4, 24), *cols("summary", list(range(170, 520, 50)), 100, 30, h - 320, "paragraph", "body", 20, 66)] + q_and_a("review", list(range(560, w - 120, 86)), 120, 560, 560)
    return [text_el("title", "chapter_title", 80, 70, 54, h - 150, "diagram", "title", "title", 8, 40), image("diagram", 180, 100, 360, 560, "diagram"), caption("caption", 580, 100, 30, 560, "diagram"), text_el("note", "note", 180, 730, 36, 540, "note", "small", "fill", 14, 44), *cols("body", list(range(660, w - 110, 54)), 110, 32, h - 300, "paragraph", "body", 24, 82)]


def magazine(v: int) -> list[dict[str, Any]]:
    w, h = page_for("magazine_journal", v)
    if v == 1:
        return [text_el("name", "document_title", 60, 60, 78, h - 140, "magazine_name", "title", "safe_fragment", 4, 28), image("cover", 180, 95, 470, 760, "cover"), text_el("feature", "section_title", 710, 100, 76, h - 380, "feature", "title", "title", 8, 44), *items("line", [830, 880, 930, 980, 1030, 1080], 130, 30, h - 520)]
    if v == 2:
        return [text_el("title", "document_title", 64, 70, 56, h - 160, "feature", "title", "title", 8, 44), image("image", 160, 96, 300, 560, "feature_image"), caption("caption", 500, 96, 30, 560, "image"), text_el("section", "section_title", 590, 100, 46, h - 260, "section", "subtitle", "title", 8, 38), *cols("body", list(range(670, w - 110, 50)), 100, 32, h - 280, "paragraph", "body", 28, 96)]
    if v == 3:
        return [image("portrait", 80, 90, 250, 430, "portrait"), text_el("title", "document_title", 370, 90, 60, h - 220, "interview", "title", "title", 8, 42), *[text_el(f"q_{i:02d}", "section_title", x, 125, 30, 470, "question", "small", "safe_fragment", 2, 14) for i, x in enumerate(range(470, w - 150, 92), 1)], *[text_el(f"a_{i:02d}", "paragraph", x + 36, 125, 34, h - 340, "answer", "body", "fill", 26, 86) for i, x in enumerate(range(470, w - 150, 92), 1)]]
    if v == 4:
        return [decor("side_color", 64, 80, 86, h - 180, "soft-fill"), text_el("title", "document_title", 90, 100, 54, h - 220, "contents", "title", "safe_fragment", 4, 24), *items("contents", list(range(190, w - 90, 54)), 120, 32, h - 320), *[text_el(f"page_{i:02d}", "page_number", x + 32, 120, 18, h - 320, "page", "tiny", "literal", value=str(4 + i)) for i, x in enumerate(range(190, w - 90, 54), 1)]]
    if v == 5:
        return [text_el("title", "document_title", 60, 80, 56, h - 160, "photo_story", "title", "title", 8, 42), image("photo_a", 160, 90, 260, 380, "photo"), image("photo_b", 480, 190, 270, 420, "photo"), image("photo_c", 820, 90, 250, 360, "photo"), caption("cap_a", 170, 500, 28, 320, "photo_a"), caption("cap_b", 770, 190, 28, 420, "photo_b"), *cols("body", list(range(180, w - 130, 56)), 900, 32, 430, "paragraph", "body", 18, 60)]
    return [text_el("title", "document_title", 70, 80, 58, h - 160, "opinion", "title", "title", 8, 44), decor("quote", 180, 120, 220, 760, "box note-fill"), text_el("quote_text", "paragraph", 230, 150, 40, 700, "quote", "subtitle", "fill", 22, 70), text_el("author", "metadata", 430, 120, 30, 760, "author", "tiny", "short", 4, 18), *cols("body", list(range(510, w - 100, 54)), 100, 32, h - 260, "paragraph", "body", 30, 100)]


def academic(v: int) -> list[dict[str, Any]]:
    w, h = page_for("academic_paper", v)
    base = [text_el("meta", "metadata", 54, 58, 34, h - 135, "meta", "tiny", "literal", value="2026"), text_el("title", "document_title", 118, 64, 58, h - 150, "paper_title", "title", "title", 8, 52)]
    if v == 1:
        return base + [text_el("abstract_t", "section_title", 210, 86, 36, h - 260, "abstract", "subtitle", "safe_fragment", 2, 16), *cols("abstract", [270, 318, 366, 414], 90, 30, 650, "paragraph", "body", 28, 92), image("fig", 520, 110, 290, 410, "figure"), caption("caption", 840, 110, 28, 410, "fig"), *cols("body", list(range(520, w - 100, 50)), 620, 30, h - 790, "paragraph", "body", 28, 94)]
    if v == 2:
        return base + [decor("mid_rule", w // 2, 90, 2, h - 240, "rule-v"), *cols("left", list(range(230, w // 2 - 40, 48)), 90, 30, h - 260, "paragraph", "body", 30, 100), *cols("right", list(range(w // 2 + 45, w - 90, 48)), 90, 30, h - 260, "paragraph", "body", 30, 100)]
    if v == 3:
        return base + [text_el("method_t", "section_title", 220, 90, 38, 640, "method", "subtitle", "safe_fragment", 2, 16), *cols("method", list(range(280, 520, 48)), 100, 30, 620, "paragraph", "body", 24, 78), image("chart", 590, 100, 330, 460, "chart"), caption("caption", 950, 100, 28, 460, "chart"), *cols("result", list(range(230, w - 100, 50)), 820, 30, 560, "paragraph", "body", 22, 76)]
    if v == 4:
        return base + items("ref", list(range(230, w - 80, 44)), 90, 28, h - 260)
    if v == 5:
        return base + [image("figure", 220, 100, 400, 530, "figure"), caption("cap", 650, 100, 30, 530, "figure"), *cols("explain", list(range(720, w - 100, 52)), 100, 32, 530, "paragraph", "body", 20, 68), *cols("body", list(range(230, w - 100, 48)), 760, 30, 610, "paragraph", "body", 22, 78)]
    return base + [text_el("conf", "metadata", 220, 86, 32, h - 250, "conf", "small", "literal", value="20260702"), text_el("abs_t", "section_title", 285, 90, 42, h - 260, "abstract", "subtitle", "safe_fragment", 2, 16), *cols("abstract", list(range(360, w - 100, 54)), 95, 32, h - 280, "paragraph", "body", 28, 94)]


def historical(v: int) -> list[dict[str, Any]]:
    w, h = page_for("historical_classic", v)
    if v == 4:
        bg = {"background": "#2c2924", "color": "#efe5c9"}
        return [decor("dark", 44, 44, w - 88, h - 88, "box dark-fill", bg), text_el("meta", "metadata", 96, 96, 34, h - 220, "rubbing_meta", "small light", "safe_fragment", 2, 16), *cols("rubbing", list(range(160, w - 110, 58)), 110, 36, h - 260, "paragraph", "body light", 24, 80)]
    out = [decor("outer", 44, 44, w - 88, h - 88, "box"), text_el("meta", "metadata", 86, 86, 34, h - 180, "classic_meta", "tiny", "safe_fragment", 2, 16)]
    if v == 1:
        out += [decor("inner", 135, 76, w - 250, h - 160, "box"), *cols("classic", list(range(170, w - 130, 54)), 100, 34, h - 240, "paragraph", "body", 28, 90), text_el("page", "page_number", w - 92, 120, 24, h - 260, "page", "tiny", "literal", value="1")]
    elif v == 2:
        out += [decor("scroll", 140, 70, w - 280, h - 140, "note-fill"), *cols("scroll", list(range(190, w - 170, 60)), 105, 36, h - 260, "paragraph", "body", 30, 92)]
    elif v == 3:
        out += [text_el("serial", "metadata", 150, 100, 28, h - 240, "serial", "tiny", "literal", value="20260702"), *cols("record", list(range(220, w - 180, 64)), 110, 36, h - 330, "paragraph", "body", 24, 76), text_el("seal", "seal", w - 190, 780, 106, 106, "seal", "subtitle stamp", "safe_fragment", 2, 10)]
    elif v == 5:
        out += [*cols("main", list(range(150, 730, 54)), 100, 34, h - 240, "paragraph", "body", 28, 92), decor("note_box", 780, 120, 250, h - 320, "box note-fill"), *items("note", [810, 850, 890, 930, 970], 150, 26, h - 420)]
    else:
        out += [*[decor(f"line_{i:02d}", x, 100, 1, h - 240, "rule-v") for i, x in enumerate(range(155, w - 120, 58), 1)], *items("name", list(range(170, w - 130, 58)), 110, 30, h - 270)]
    return out


def notice(v: int) -> list[dict[str, Any]]:
    w, h = page_for("notice_announcement", v)
    base = [decor("panel", 68, 68, w - 136, h - 136, "box note-fill"), text_el("title", "document_title", 140, 110, 66, h - 250, "notice_title", "title", "safe_fragment", 4, 28)]
    if v == 1:
        return base + [text_el("section", "section_title", 270, 135, 44, h - 330, "section", "subtitle", "title", 8, 38), *cols("body", list(range(370, w - 170, 62)), 140, 36, h - 380, "paragraph", "body", 28, 88), text_el("date", "metadata", w - 150, 150, 34, h - 420, "date", "small", "literal", value="20260702")]
    if v == 2:
        return base + [*[decor(f"item_box_{i:02d}", x - 10, 125, 58, h - 360, "box") for i, x in enumerate(range(280, w - 160, 80), 1)], *items("bulletin", list(range(285, w - 160, 80)), 150, 34, h - 420)]
    if v == 3:
        return base + field_grid("meeting", 280, 150, 3, 1, 120, 300) + cols("body", list(range(300, w - 140, 60)), 560, 34, h - 760, "paragraph", "body", 22, 72) + [text_el("date", "metadata", w - 140, 160, 32, h - 430, "date", "small", "literal", value="20260702")]
    if v == 4:
        return base + items("public", list(range(260, w - 130, 44)), 150, 28, h - 360)
    if v == 5:
        return [decor("panel", 68, 68, w - 136, h - 136, "box urgent-fill"), text_el("title", "document_title", 150, 115, 82, h - 260, "urgent", "title", "safe_fragment", 4, 24), text_el("important", "section_title", 315, 150, 54, h - 360, "important", "subtitle", "title", 6, 30), *cols("body", list(range(450, w - 150, 64)), 160, 38, h - 430, "paragraph", "body", 20, 68)]
    return base + cols("campus", list(range(280, w - 130, 58)), 145, 34, h - 370, "paragraph", "body", 22, 74) + [text_el("date", "metadata", w - 120, 160, 30, h - 420, "date", "small", "literal", value="20260702")]


def form(v: int) -> list[dict[str, Any]]:
    w, h = page_for("complex_form", v)
    out = [decor("outer", 54, 54, w - 108, h - 108, "box"), text_el("title", "document_title", 100, 88, 58, h - 180, "form_title", "title", "safe_fragment", 4, 28)]
    if v == 1:
        return out + field_grid("field", 210, 115, 8, 2, 96, 430) + field_grid("bottom", 230, 1030, 5, 1, 145, 330)
    if v == 2:
        return out + field_grid("person", 195, 115, 6, 3, 122, 360) + [text_el("seal", "seal", w - 210, 990, 108, 108, "seal", "subtitle stamp", "safe_fragment", 2, 10)]
    if v == 3:
        for i, x in enumerate(range(210, w - 150, 74), 1):
            out += [text_el(f"check_{i:02d}", "field_label", x, 120, 28, h - 390, "check", "small", "safe_fragment", 2, 10), answer(f"box_{i:02d}", x + 34, 120, 30, h - 390)]
        return out
    if v == 4:
        return out + q_and_a("survey_a", list(range(210, w - 220, 90)), 120, 520, 520) + q_and_a("survey_b", list(range(210, w - 220, 90)), 760, 520, 520)
    if v == 5:
        return out + field_grid("service", 210, 120, 5, 2, 136, 390) + field_grid("service_bottom", 260, 1010, 4, 1, 150, 320) + [text_el("opinion", "paragraph", w - 300, 150, 48, 820, "opinion", "body boxed", "fill", 20, 64), text_el("review", "metadata", w - 155, 160, 32, 820, "review", "tiny", "literal", value="2026"), text_el("bottom_note", "note", w - 250, 1010, 42, 320, "bottom_note", "small boxed", "fill", 14, 44)]
    return out + items("log", list(range(210, w - 90, 54)), 120, 30, h - 340) + [text_el("note", "note", w - 145, 130, 34, h - 380, "note", "small", "fill", 16, 50)]


def letter(v: int) -> list[dict[str, Any]]:
    w, h = page_for("handwritten_letter", v)
    base = [decor("paper", 70, 70, w - 140, h - 140, "box")]
    if v == 1:
        return base + [text_el("recipient", "recipient", 130, 120, 46, h - 300, "recipient", "subtitle hand", "title", 4, 22), *cols("body", list(range(220, w - 220, 58)), 130, 34, h - 330, "paragraph", "body hand", 26, 86), text_el("date", "metadata", w - 170, 160, 34, h - 420, "date", "small", "literal", value="20260702")]
    if v == 2:
        return [decor("paper", 80, 80, w - 160, h - 160, "note-fill"), text_el("title", "document_title", 130, 120, 46, h - 280, "note_title", "subtitle hand", "safe_fragment", 4, 22), *items("note", list(range(220, w - 160, 58)), 130, 34, h - 330)]
    if v == 3:
        return base + [text_el("title", "document_title", 120, 110, 44, h - 260, "meeting", "subtitle hand", "safe_fragment", 4, 22), *items("item", list(range(220, w - 160, 90)), 130, 32, 520), *cols("conclusion", list(range(220, w - 160, 58)), 780, 32, 480, "paragraph", "body hand", 18, 58)]
    if v == 4:
        return [decor("diary", 80, 80, w - 160, h - 160, "box note-fill"), text_el("date", "metadata", 130, 120, 36, h - 300, "date", "small", "literal", value="20260702"), *cols("diary", list(range(210, w - 170, 58)), 130, 34, h - 330, "paragraph", "body hand", 24, 78)]
    if v == 5:
        return [decor("memo", 120, 130, w - 240, h - 260, "box note-fill"), text_el("title", "document_title", 190, 190, 62, h - 500, "memo", "title hand", "safe_fragment", 4, 22), *cols("memo_body", list(range(330, w - 190, 76)), 210, 42, h - 560, "paragraph", "body hand", 16, 52), text_el("post", "note", w - 180, 260, 34, h - 620, "postscript", "small hand", "fill", 12, 38)]
    return base + [*cols("main", list(range(125, w - 260, 54)), 120, 34, h - 310, "paragraph", "body hand", 24, 78), decor("annot_box", w - 250, 130, 140, h - 360, "box note-fill"), *items("annot", [w - 220, w - 180, w - 140], 160, 26, h - 430)]


def elements_for(category: str, variant: int) -> list[dict[str, Any]]:
    if category == "newspaper_page":
        return newspaper(variant)
    if category == "certificate_proof":
        return certificate(variant)
    if category == "exam_paper":
        return exam(variant)
    if category == "sign_poster_scene":
        return sign(variant)
    if category == "book_page":
        return book(variant, False)
    if category == "textbook_page":
        return book(variant, True)
    if category == "magazine_journal":
        return magazine(variant)
    if category == "academic_paper":
        return academic(variant)
    if category == "historical_classic":
        return historical(variant)
    if category == "notice_announcement":
        return notice(variant)
    if category == "complex_form":
        return form(variant)
    if category == "handwritten_letter":
        return letter(variant)
    raise KeyError(category)


def build_template(folder: str, category: str, category_cn: str, variant: int) -> dict[str, Any]:
    name, family, prompt = V4_NAMES[category][variant - 1]
    width, height = page_for(category, variant)
    return {
        "schema_version": "mongolian_vertical_layout_tree.v4",
        "template_id": f"{category}_vertical_tree_v4_{variant:02d}",
        "variant": variant,
        "category_id": category,
        "category_cn": category_cn,
        "folder": folder,
        "template_name_cn": name,
        "layout_family": family,
        "design_prompt": prompt,
        "writing_system": {
            "language": "传统蒙古文",
            "writing_mode": "vertical-lr",
            "line_direction": "top_to_bottom",
            "column_order": "left_to_right",
            "page_rotation": "none",
        },
        "page": {
            "width": width,
            "height": height,
            "orientation": "landscape" if width > height else "portrait",
            "background": "warm_paper",
            "tight_crop": True,
        },
        "style_tokens": {
            "paper": "#fbf8ed",
            "ink": "#151515",
            "muted": "#625d55",
            "accent": "#8f2f2f",
            "line": "#222222",
            "font_scale": "native_vertical_v4",
        },
        "qa_expectations": {
            "min_blocks": {
                "newspaper_page": 20,
                "certificate_proof": 8,
                "exam_paper": 20,
                "sign_poster_scene": 5,
                "book_page": 9,
                "textbook_page": 10,
                "magazine_journal": 9,
                "academic_paper": 12,
                "historical_classic": 10,
                "notice_announcement": 6,
                "complex_form": 18,
                "handwritten_letter": 8,
            }[category],
            "overflow_blocks": 0,
            "out_of_bounds_blocks": 0,
            "latin_residue_blocks": 0,
        },
        "elements": elements_for(category, variant),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    root = Path(args.output_root)
    if root.exists():
        shutil.rmtree(root)
    index = []
    for folder, category, category_cn in CATEGORIES:
        for variant in range(1, 7):
            payload = build_template(folder, category, category_cn, variant)
            out = root / folder / f"{payload['template_id']}.json"
            write_json(out, payload)
            index.append(
                {
                    "template_id": payload["template_id"],
                    "variant": variant,
                    "category_id": category,
                    "category_cn": category_cn,
                    "folder": folder,
                    "template_name_cn": payload["template_name_cn"],
                    "layout_family": payload["layout_family"],
                    "path": str(out),
                }
            )
    write_json(root / "index.json", {"schema_version": "mongolian_vertical_template_index.v4", "templates": index})
    (root / "README.md").write_text(
        "# 传统蒙古文 v4 JSON 结构树模板库\n\n"
        "本目录包含 12 类 x 6 套 = 72 个完整 JSON 结构树，用于 VL8。v4 在 v3 的 schema 上重写页面尺寸、分区、栏数、图片/表单/答题/边注配置，使每类蒙古语竖版样本具有更明显的版面差异。\n",
        encoding="utf-8",
    )
    print(json.dumps({"output_root": str(root), "templates": len(index)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
