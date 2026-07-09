#!/usr/bin/env python3
"""Build 72 native vertical Mongolian JSON layout trees.

The generated JSON files are the source of truth for Mongolian v3 layouts:
12 categories x 6 explicitly different templates.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


CATEGORIES = [
    ("01_报纸页", "newspaper_page", "报纸页"),
    ("02_证书证明", "certificate_proof", "证书证明"),
    ("03_考试卷", "exam_paper", "考试卷"),
    ("04_标牌海报场景", "sign_poster_scene", "标牌海报场景"),
    ("05_书籍页", "book_page", "书籍页"),
    ("06_教科书页", "textbook_page", "教科书页"),
    ("07_杂志期刊页", "magazine_journal", "杂志期刊页"),
    ("08_学术文献页", "academic_paper", "学术文献页"),
    ("09_历史文档_古籍", "historical_classic", "历史文档_古籍"),
    ("10_公告通知", "notice_announcement", "公告通知"),
    ("11_复杂表单登记页", "complex_form", "复杂表单登记页"),
    ("12_手写笔记信件", "handwritten_letter", "手写笔记信件"),
]


NAMES: dict[str, list[tuple[str, str, str]]] = {
    "newspaper_page": [
        ("传统竖排日报头版", "classic_vertical_broadsheet", "竖排日报头版，报头、头条、多栏正文、图片区和短讯栏同时出现，文字密度高。"),
        ("图片主导新闻版", "photo_led_frontpage", "以新闻图片和头条为中心，旁侧配置短新闻，下半页使用多列竖排正文。"),
        ("公告短讯密集版", "bulletin_dense_page", "多条短讯并列排列，强调密集信息块和分隔线，接近日报内页。"),
        ("评论副刊版", "editorial_supplement", "副刊式报纸页面，有大标题、引言框、正文栏目和小图文区。"),
        ("地方周报综合版", "weekly_mixed_news", "地方周报风格，左侧刊名和专题，主体为图文混排和底部信息条。"),
        ("无图快讯版", "text_only_evening_news", "几乎无图片的快讯版，使用大量短栏、竖线和紧凑标题形成报纸感。"),
    ],
    "certificate_proof": [
        ("庄重边框证书", "formal_framed_certificate", "竖排证书，重边框、编号、标题、证明正文和红色印章。"),
        ("双章证明页", "dual_seal_proof", "证明材料风格，双印章、编号栏和多列说明文字。"),
        ("奖状式证书", "award_certificate", "奖状样式，标题更突出，正文居中，底部签发信息清晰。"),
        ("登记证明", "registry_proof", "接近登记证明，有字段式内容、编号和印章，弱化装饰。"),
        ("横向荣誉证书", "landscape_honor_certificate", "横向证书版式，竖排文本列沿横向展开，边框和印章明显。"),
        ("简式单位证明", "minimal_official_proof", "简洁单位证明，留白较多但结构完整，签发信息和章位明确。"),
    ],
    "exam_paper": [
        ("双栏标准试卷", "two_column_exam", "标题、考号区、双栏题目和答题框并列，题块密集。"),
        ("分区测验卷", "sectioned_quiz", "按一、二、三部分分区，每区有题目与答案区。"),
        ("阅读理解卷", "reading_comprehension_exam", "左侧阅读材料，右侧题目与答题区，形成明显考试场景。"),
        ("填空答题卷", "fill_blank_answer_sheet", "大量短题和窄答题格，强调答题卡属性。"),
        ("综合练习卷", "mixed_practice_sheet", "选择、简答、材料题混排，题型块差异明显。"),
        ("评分栏试卷", "scored_exam_sheet", "带评分栏、题号栏和长答题区，结构更接近正式试卷。"),
    ],
    "sign_poster_scene": [
        ("横向门头标牌", "landscape_shop_sign", "横向标牌，粗标题、短说明和边框，适合作为招牌类 OCR。"),
        ("竖向公告牌", "portrait_public_sign", "竖向标牌公告，标题醒目，正文短而集中。"),
        ("活动海报", "event_poster", "活动海报风格，有大标题、时间地点、正文和装饰色块。"),
        ("导向标识", "wayfinding_sign", "导向牌样式，多个方向条目和编号。"),
        ("墙面宣传牌", "wall_notice_board", "宣传栏/墙面牌，有大色块、图片占位和多列文字。"),
        ("简洁警示牌", "minimal_warning_sign", "警示标牌风格，少量大字和说明文字，视觉简洁。"),
    ],
    "book_page": [
        ("经典密排书页", "classic_dense_book", "传统竖排书籍正文页，多列正文铺满页面。"),
        ("带页眉书页", "running_header_book", "有页眉、页码、章节题和正文栏。"),
        ("章首页", "chapter_opener", "章节开头页，大标题、引言和较少正文。"),
        ("批注边栏书页", "annotated_margin_book", "正文外带边栏批注，呈现古籍或教材批注感。"),
        ("双栏分段书页", "segmented_book_page", "正文分为上下段或左右区，结构不同于单一密排。"),
        ("目录式书页", "contents_like_book_page", "目录/索引式书页，多条短项和页码。"),
    ],
    "textbook_page": [
        ("图文课程页", "lesson_with_figure", "教材课文页，有图片/图示、说明和正文。"),
        ("词汇练习页", "vocabulary_exercise", "词汇栏、例句、练习题和答案区。"),
        ("知识点讲解页", "concept_explanation", "知识点框、正文、图示和小结。"),
        ("活动任务页", "activity_workbook", "活动任务、步骤说明、填写区和提示。"),
        ("复习检测页", "review_check_page", "复习要点、题目和多个小答题框。"),
        ("图表说明页", "diagram_textbook_page", "图表/示意图占位配合竖排说明和练习。"),
    ],
    "magazine_journal": [
        ("封面式杂志页", "magazine_cover_like", "大标题、大图和少量导语，具有杂志封面感。"),
        ("专题内页", "feature_article_spread", "专题文章内页，图文混排和多栏正文。"),
        ("人物访谈页", "interview_page", "访谈式 Q/A 结构，人物图和问答栏目。"),
        ("目录栏目页", "contents_column_page", "目录或栏目索引，多个短条目和页码。"),
        ("图片故事页", "photo_story_page", "多图配短文，视觉块明显。"),
        ("评论专栏页", "opinion_column_page", "评论文章，有引言框、作者信息和正文。"),
    ],
    "academic_paper": [
        ("论文首页", "academic_first_page", "题名、摘要、关键词、正文和图表占位。"),
        ("双栏论文页", "two_column_academic", "双栏学术正文，有小标题、图注和页脚。"),
        ("实验报告页", "experiment_report", "实验目的、方法、结果和图示块。"),
        ("参考文献页", "references_page", "参考文献/注释式密集条目页面。"),
        ("图表论文页", "figure_table_paper", "图表占比更高，配多段说明文字。"),
        ("会议摘要页", "conference_abstract", "会议摘要风格，标题、作者信息、摘要和编号。"),
    ],
    "historical_classic": [
        ("古籍刻本文档", "classic_woodblock_page", "古籍刻本风格，边框、密集竖排正文和页码。"),
        ("卷轴式文档", "scroll_document", "卷轴/长条文档感，正文列集中，纸张偏旧。"),
        ("档案页", "archive_record_page", "档案记录页，有编号、正文、章印和边框。"),
        ("碑帖拓片样式", "rubbing_style_page", "拓片式页面，深色底、浅色字感和竖列。"),
        ("批注古籍页", "annotated_classic", "古籍正文配边注和小批注。"),
        ("家谱谱牒页", "genealogy_record", "谱牒/名单式页面，多列短条目和分隔线。"),
    ],
    "notice_announcement": [
        ("正式公告", "formal_notice", "标题、正文、日期和签发区域完整的正式公告。"),
        ("栏板通知", "bulletin_board_notice", "公告栏样式，多个通知条目分区排列。"),
        ("会议通知", "meeting_notice", "会议通知，有时间、地点、事项和落款。"),
        ("公示名单", "public_list_notice", "名单公示样式，短条目和编号较多。"),
        ("紧急提示", "urgent_notice", "醒目提示条、重点说明和联系人信息。"),
        ("校园通知", "campus_notice", "校园/机构通知，结构轻量但信息完整。"),
    ],
    "complex_form": [
        ("登记申请表", "registration_application", "多字段登记表，有标题、字段标签、填写格和备注。"),
        ("人员信息表", "personnel_form", "人员信息登记，字段密集，含编号和签名区。"),
        ("检查清单表", "inspection_checklist", "检查清单，多个勾选框和说明列。"),
        ("调查问卷", "survey_form", "问卷式页面，题目、选项和填写区并存。"),
        ("业务办理单", "service_form", "业务办理表，有分区字段、编号和处理意见。"),
        ("日志记录表", "log_record_form", "日志/记录表，多行条目和备注栏。"),
    ],
    "handwritten_letter": [
        ("私人信件", "personal_letter", "信件格式，有称呼、正文、日期和署名。"),
        ("课堂笔记", "class_note", "笔记页面，标题、分点内容和边栏标记。"),
        ("会议记录", "meeting_note", "会议记录式手写笔记，事项和结论分区。"),
        ("日记页", "diary_page", "日记页面，有日期、正文和小段落。"),
        ("便签留言", "memo_note", "便签式短文，正文较少但风格不同。"),
        ("批注信纸", "annotated_letter", "信纸上有正文、批注和补充说明。"),
    ],
}


def text_el(
    el_id: str,
    label: str,
    x: int,
    y: int,
    w: int,
    h: int,
    role: str,
    cls: str = "body",
    source: str = "fill",
    min_chars: int = 24,
    max_chars: int = 96,
    value: str | None = None,
    visual: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text: dict[str, Any] = {"source": source, "min_chars": min_chars, "max_chars": max_chars}
    if value is not None:
        text["value"] = value
    return {
        "id": el_id,
        "kind": "text",
        "label": label,
        "role": role,
        "class": cls,
        "box": {"x": x, "y": y, "w": w, "h": h},
        "text": text,
        "visual": visual or {},
    }


def decor(el_id: str, x: int, y: int, w: int, h: int, cls: str = "box", visual: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": el_id, "kind": "decor", "label": "decor", "class": cls, "box": {"x": x, "y": y, "w": w, "h": h}, "visual": visual or {}}


def image(el_id: str, x: int, y: int, w: int, h: int, role: str = "image") -> dict[str, Any]:
    return {"id": el_id, "kind": "image", "label": "image", "role": role, "class": "image-fill", "box": {"x": x, "y": y, "w": w, "h": h}, "text": {"source": "blank"}}


def answer(el_id: str, x: int, y: int, w: int, h: int, role: str = "answer_area") -> dict[str, Any]:
    return {"id": el_id, "kind": "answer_area", "label": "answer_area", "role": role, "class": "answer-box", "box": {"x": x, "y": y, "w": w, "h": h}, "text": {"source": "blank"}}


def columns(prefix: str, x0: int, y: int, count: int, w: int, gap: int, h: int, label: str = "paragraph", cls: str = "body", min_chars: int = 28, max_chars: int = 120) -> list[dict[str, Any]]:
    return [text_el(f"{prefix}_{i+1:02d}", label, x0 + i * (w + gap), y, w, h, "vertical_text_column", cls, "fill", min_chars, max_chars) for i in range(count)]


def briefs(prefix: str, x0: int, y: int, count: int, w: int, gap: int, h: int) -> list[dict[str, Any]]:
    return [text_el(f"{prefix}_{i+1:02d}", "list_item", x0 + i * (w + gap), y, w, h, "brief_item", "small", "fill", 14, 52) for i in range(count)]


def fields(prefix: str, x0: int, y0: int, cols: int, rows: int, col_gap: int = 92, row_gap: int = 330) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    n = 1
    for r in range(rows):
        for c in range(cols):
            x = x0 + c * col_gap
            y = y0 + r * row_gap
            out.append(text_el(f"{prefix}_label_{n:02d}", "field_label", x, y, 30, 210, "field_label", "small", "safe_fragment", 2, 12))
            out.append(text_el(f"{prefix}_value_{n:02d}", "field_value", x + 34, y, 42, 250, "field_value", "body boxed", "short", 8, 32))
            n += 1
    return out


def template_meta(category: str, category_cn: str, variant: int) -> tuple[str, str, str]:
    return NAMES[category][variant - 1]


def page_for(category: str, variant: int) -> tuple[int, int]:
    if category == "sign_poster_scene" and variant in {1, 4}:
        return 1380, 820
    if category == "certificate_proof" and variant == 5:
        return 1360, 920
    return {
        "newspaper_page": (1180, 1760),
        "certificate_proof": (1040, 1420),
        "exam_paper": (1120, 1620),
        "sign_poster_scene": (920, 1180),
        "book_page": (980, 1500),
        "textbook_page": (1040, 1500),
        "magazine_journal": (1120, 1500),
        "academic_paper": (1120, 1580),
        "historical_classic": (960, 1600),
        "notice_announcement": (960, 1360),
        "complex_form": (1160, 1500),
        "handwritten_letter": (1040, 1480),
    }[category]


def newspaper(v: int) -> list[dict[str, Any]]:
    if v == 1:
        return [
            text_el("year", "metadata", 34, 48, 34, 1640, "issue_year", "small", "literal", value="2026"),
            text_el("name", "document_title", 86, 48, 54, 1640, "newspaper_name", "title", "safe_fragment", 4, 30),
            decor("rule_a", 160, 58, 2, 1588, "rule-v"),
            text_el("lead_title", "section_title", 184, 58, 42, 1540, "lead_story_title", "subtitle", "title", 10, 52),
            *columns("lead", 244, 58, 5, 32, 20, 1540, "paragraph", "body", 60, 160),
            image("photo", 538, 58, 170, 430, "news_photo"),
            text_el("caption", "caption", 724, 58, 28, 430, "photo_caption", "small", "short", 12, 34),
            *columns("mid", 538, 528, 5, 30, 18, 1068, "paragraph", "body", 44, 120),
            decor("rule_b", 840, 58, 2, 1588, "rule-v"),
            text_el("side_title", "section_title", 876, 58, 40, 1540, "briefs_title", "subtitle", "title", 8, 42),
            *briefs("brief", 936, 58, 4, 30, 18, 1540),
            text_el("footer", "footer", 1080, 58, 28, 1540, "page_footer", "tiny", "literal", value="01"),
        ]
    if v == 2:
        return [
            text_el("name", "document_title", 48, 50, 54, 1620, "newspaper_name", "title", "safe_fragment", 4, 30),
            text_el("issue", "metadata", 118, 50, 28, 1620, "issue_bar", "tiny", "literal", value="20260702"),
            image("hero", 190, 70, 300, 620, "lead_photo"),
            text_el("hero_caption", "caption", 510, 70, 28, 620, "lead_caption", "small", "short", 16, 42),
            text_el("headline", "section_title", 574, 70, 52, 620, "lead_headline", "title", "title", 10, 54),
            *columns("lead_body", 650, 70, 3, 32, 20, 620, "paragraph", "body", 36, 90),
            *columns("lower", 190, 760, 12, 30, 18, 820, "paragraph", "body", 38, 110),
            decor("bottom_rule", 170, 1605, 900, 2, "rule-h"),
            *briefs("bottom_brief", 210, 1620, 9, 26, 16, 80),
        ]
    if v == 3:
        return [
            decor("outer", 42, 42, 1096, 1670, "box"),
            text_el("name", "document_title", 74, 74, 48, 1560, "newspaper_name", "title", "safe_fragment", 4, 30),
            text_el("edition", "metadata", 134, 74, 28, 1560, "edition_meta", "tiny", "literal", value="2026"),
            *[decor(f"rule_{i}", x, 84, 1, 1510, "rule-v") for i, x in enumerate([206, 388, 570, 752, 934], 1)],
            *[text_el(f"section_{i}", "section_title", x, 90, 34, 300, "news_section", "subtitle", "title", 6, 28) for i, x in enumerate([226, 408, 590, 772, 954], 1)],
            *columns("dense_a", 226, 420, 5, 28, 154, 600, "paragraph", "body", 34, 90),
            *briefs("dense_b", 226, 1060, 10, 24, 64, 420),
        ]
    if v == 4:
        return [
            text_el("masthead", "document_title", 54, 62, 46, 1320, "supplement_name", "title", "safe_fragment", 4, 30),
            decor("quote_box", 140, 70, 240, 640, "box note-fill"),
            text_el("quote", "paragraph", 168, 96, 34, 580, "editorial_quote", "subtitle", "fill", 36, 100),
            text_el("editorial_title", "section_title", 430, 70, 52, 1400, "editorial_title", "title", "title", 8, 48),
            *columns("editorial", 510, 70, 8, 32, 22, 1400, "paragraph", "body", 54, 150),
            *briefs("supplement_brief", 150, 790, 6, 26, 24, 520),
            image("small_photo", 930, 920, 160, 360, "column_photo"),
            text_el("photo_note", "caption", 1110, 920, 28, 360, "photo_caption", "small", "short", 12, 36),
        ]
    if v == 5:
        return [
            text_el("weekly_name", "document_title", 50, 50, 58, 1620, "weekly_name", "title", "safe_fragment", 4, 30),
            text_el("feature", "section_title", 138, 62, 46, 760, "feature_title", "title", "title", 8, 46),
            *columns("feature_body", 210, 62, 5, 32, 20, 760, "paragraph", "body", 44, 120),
            image("center_image", 510, 110, 260, 520, "feature_image"),
            text_el("image_caption", "caption", 790, 110, 28, 520, "image_caption", "small", "short", 14, 40),
            decor("ad_box", 840, 110, 210, 520, "box soft-fill"),
            *briefs("ad_text", 870, 140, 4, 28, 26, 460),
            *columns("bottom_news", 140, 890, 13, 30, 18, 650, "paragraph", "body", 30, 90),
        ]
    return [
        text_el("name", "document_title", 44, 44, 42, 1660, "evening_name", "title", "safe_fragment", 4, 30),
        text_el("date", "metadata", 96, 44, 26, 1660, "date", "tiny", "literal", value="20260702"),
        *[decor(f"rule_{i}", x, 58, 1, 1570, "rule-v") for i, x in enumerate(range(150, 1080, 130), 1)],
        *[text_el(f"title_{i}", "section_title", x, 64, 32, 410, "brief_title", "subtitle", "title", 5, 24) for i, x in enumerate(range(170, 1080, 130), 1)],
        *[text_el(f"brief_{i}", "list_item", x, 500, 26, 1060, "news_brief", "small", "fill", 22, 68) for i, x in enumerate(range(210, 1120, 65), 1)],
    ]


def certificate(v: int) -> list[dict[str, Any]]:
    w, h = page_for("certificate_proof", v)
    if v == 5:
        return [
            decor("outer", 50, 50, w - 100, h - 100, "box ornate"),
            text_el("title", "document_title", 130, 100, 74, 700, "certificate_title", "title", "safe_fragment", 4, 30),
            text_el("subtitle", "document_subtitle", 260, 120, 46, 660, "certificate_subtitle", "subtitle", "title", 8, 40),
            *columns("body", 380, 130, 5, 34, 48, 640, "paragraph", "body", 28, 80),
            text_el("seal", "seal", 1050, 240, 120, 120, "seal", "subtitle stamp", "safe_fragment", 2, 10),
            text_el("date", "metadata", 1190, 120, 34, 660, "date", "small", "literal", value="20260702"),
        ]
    base = [
        decor("outer", 54, 54, w - 108, h - 108, "box ornate" if v in {1, 3} else "box"),
        text_el("serial", "metadata", 108, 110, 42, h - 240, "serial_no", "small", "literal", value="20260702"),
        text_el("title", "document_title", 198, 118, 62, h - 260, "certificate_title", "title", "safe_fragment", 4, 30),
        text_el("subtitle", "document_subtitle", 310, 160, 44, h - 360, "certificate_subtitle", "subtitle", "title", 8, 42),
    ]
    if v == 1:
        base += [*columns("body", 430, 180, 4, 34, 42, 900, "paragraph", "body", 30, 80), text_el("seal", "seal", 780, 260, 120, 120, "seal", "subtitle stamp", "safe_fragment", 2, 10), text_el("date", "metadata", 850, 170, 32, 880, "issue_date", "small", "literal", value="20260702")]
    elif v == 2:
        base += [*columns("body", 410, 170, 5, 34, 34, 880, "paragraph", "body", 26, 76), text_el("seal_a", "seal", 760, 220, 110, 110, "seal", "subtitle stamp", "safe_fragment", 2, 10), text_el("seal_b", "seal", 780, 760, 110, 110, "seal", "subtitle stamp", "safe_fragment", 2, 10)]
    elif v == 3:
        base += [decor("ribbon", 390, 110, 90, 1120, "soft-fill"), *columns("body", 510, 180, 4, 38, 48, 900, "paragraph", "body", 30, 84), text_el("seal", "seal", 790, 740, 128, 128, "seal", "subtitle stamp", "safe_fragment", 2, 10)]
    elif v == 4:
        base += [*fields("cert_field", 430, 190, 3, 2, 110, 390), text_el("note", "paragraph", 780, 190, 42, 820, "registry_note", "body", "fill", 28, 82), text_el("seal", "seal", 830, 860, 110, 110, "seal", "subtitle stamp", "safe_fragment", 2, 10)]
    else:
        base += [*columns("body", 430, 190, 5, 32, 38, 760, "paragraph", "body", 24, 72), text_el("seal", "seal", 790, 720, 112, 112, "seal", "subtitle stamp", "safe_fragment", 2, 10), text_el("date", "metadata", 850, 180, 32, 760, "date", "small", "literal", value="20260702")]
    return base


def exam(v: int) -> list[dict[str, Any]]:
    out = [text_el("title", "document_title", 52, 52, 50, 1500, "exam_title", "title", "title", 8, 42), text_el("meta", "metadata", 120, 52, 28, 1500, "exam_meta", "small", "literal", value="2026")]
    if v == 1:
        for i, x in enumerate(range(210, 950, 92), 1):
            out += [text_el(f"q{i:02d}", "question_text", x, 68, 32, 640, "question", "body", "question", 18, 52), answer(f"a{i:02d}", x + 38, 68, 38, 640), text_el(f"q{i+8:02d}", "question_text", x, 760, 32, 640, "question", "body", "question", 18, 52), answer(f"a{i+8:02d}", x + 38, 760, 38, 640)]
    elif v == 2:
        for band, y in enumerate([80, 570, 1060], 1):
            out.append(text_el(f"section_{band}", "section_title", 190, y, 40, 420, "section", "subtitle", "safe_fragment", 2, 16))
            for i, x in enumerate(range(270, 950, 110), 1):
                out += [text_el(f"q{band}_{i}", "question_text", x, y, 34, 360, "question", "body", "question", 16, 48), answer(f"ans{band}_{i}", x + 42, y, 42, 360)]
    elif v == 3:
        out += [text_el("reading_title", "section_title", 200, 70, 40, 1340, "reading_title", "subtitle", "title", 6, 30), *columns("reading", 260, 70, 5, 30, 18, 1340, "paragraph", "body", 40, 110)]
        for i, x in enumerate(range(570, 1000, 86), 1):
            out += [text_el(f"q{i}", "question_text", x, 90, 32, 560, "question", "body", "question", 14, 44), answer(f"a{i}", x + 38, 90, 36, 560), text_el(f"q{i+6}", "question_text", x, 760, 32, 560, "question", "body", "question", 14, 44), answer(f"a{i+6}", x + 38, 760, 36, 560)]
    elif v == 4:
        for i, x in enumerate(range(190, 1010, 70), 1):
            out += [text_el(f"blank_{i}", "question_text", x, 80, 28, 1260, "fill_blank", "small", "question", 10, 30), answer(f"line_{i}", x + 32, 80, 26, 1260)]
    elif v == 5:
        out += [decor("score_box", 180, 70, 120, 1320, "box soft-fill")]
        for i, x in enumerate(range(340, 980, 90), 1):
            out += [text_el(f"q{i}", "question_text", x, 80, 32, 560, "mixed_question", "body", "question", 14, 46), answer(f"a{i}", x + 38, 80, 40, 560), text_el(f"q{i+8}", "question_text", x, 760, 32, 560, "mixed_question", "body", "question", 14, 46), answer(f"a{i+8}", x + 38, 760, 40, 560)]
    else:
        out += [decor("rubric", 170, 70, 130, 1320, "box note-fill"), text_el("rubric_text", "paragraph", 200, 100, 36, 1220, "rubric", "small", "fill", 24, 72)]
        for i, x in enumerate(range(350, 1000, 92), 1):
            out += [text_el(f"q{i}", "question_text", x, 100, 34, 460, "scored_question", "body", "question", 14, 42), answer(f"a{i}", x + 42, 100, 40, 460), text_el(f"score{i}", "metadata", x, 620, 30, 260, "score", "tiny", "literal", value=str(i)), text_el(f"q{i+7}", "question_text", x, 920, 34, 460, "scored_question", "body", "question", 14, 42), answer(f"a{i+7}", x + 42, 920, 40, 460)]
    return out


def sign(v: int) -> list[dict[str, Any]]:
    w, h = page_for("sign_poster_scene", v)
    if v in {1, 4}:
        return [decor("panel", 50, 50, w - 100, h - 100, "box note-fill"), text_el("title", "document_title", 120, 100, 78, h - 200, "sign_title", "title", "safe_fragment", 4, 28), text_el("sub", "section_title", 260, 120, 52, h - 240, "sign_subtitle", "subtitle", "title", 6, 32), *columns("sign_body", 380, 130, 6 if v == 1 else 4, 40, 54, h - 260, "paragraph", "body", 20, 64), text_el("meta", "metadata", w - 150, 130, 42, h - 260, "sign_meta", "small", "literal", value="2026")]
    if v == 2:
        return [decor("panel", 54, 54, w - 108, h - 108, "box"), text_el("title", "document_title", 130, 90, 72, 940, "public_sign_title", "title", "safe_fragment", 4, 28), *columns("body", 250, 120, 4, 42, 50, 860, "paragraph", "body", 18, 56), text_el("meta", "metadata", 760, 120, 40, 860, "meta", "small", "literal", value="20260702")]
    if v == 3:
        return [decor("bg", 60, 60, w - 120, h - 120, "box soft-fill"), image("poster_image", 120, 90, 230, 420, "poster_image"), text_el("title", "document_title", 400, 90, 72, 900, "event_title", "title", "safe_fragment", 4, 28), *columns("event", 520, 120, 4, 38, 46, 820, "paragraph", "body", 18, 58), text_el("time", "metadata", 780, 120, 36, 820, "event_time", "small", "literal", value="20260702")]
    if v == 5:
        return [decor("board", 60, 60, w - 120, h - 120, "box note-fill"), image("image", 120, 100, 260, 360, "notice_image"), text_el("title", "document_title", 420, 100, 64, 920, "board_title", "title", "safe_fragment", 4, 28), *briefs("board_item", 530, 120, 5, 34, 44, 820)]
    return [decor("warning", 80, 80, w - 160, h - 160, "box"), text_el("title", "document_title", 190, 130, 86, 820, "warning_title", "title", "safe_fragment", 4, 28), text_el("message", "paragraph", 380, 150, 56, 780, "warning_message", "subtitle", "fill", 20, 64), text_el("detail", "note", 520, 170, 34, 720, "warning_detail", "small", "fill", 16, 48), text_el("meta", "metadata", 640, 150, 42, 780, "warning_meta", "small", "literal", value="2026")]


def book(v: int, textbook: bool = False) -> list[dict[str, Any]]:
    w, h = page_for("textbook_page" if textbook else "book_page", v)
    if not textbook:
        if v == 3:
            return [text_el("page", "page_number", 54, 70, 30, 1300, "page_number", "tiny", "literal", value=str(v)), text_el("chapter", "document_title", 150, 110, 76, 1120, "chapter_opener", "title", "title", 8, 44), text_el("intro", "paragraph", 300, 190, 44, 880, "opening_quote", "subtitle", "fill", 28, 82), *columns("body", 420, 190, 7, 32, 24, 880, "paragraph", "body", 30, 96)]
        if v == 4:
            return [text_el("page", "page_number", 50, 70, 30, 1300, "page_number", "tiny", "literal", value=str(v)), *columns("main", 140, 80, 10, 30, 22, 1280, "paragraph", "body", 40, 130), *briefs("margin_note", 820, 120, 3, 24, 36, 1120)]
        if v == 6:
            return [text_el("title", "document_title", 96, 80, 48, 1280, "contents_title", "title", "safe_fragment", 4, 28), *[text_el(f"item_{i}", "list_item", x, 120, 30, 1060, "contents_item", "small", "fill", 14, 42) for i, x in enumerate(range(190, 900, 48), 1)], *[text_el(f"page_{i}", "page_number", x + 28, 120, 18, 1060, "contents_page", "tiny", "literal", value=str(10 + i)) for i, x in enumerate(range(190, 900, 48), 1)]]
        return [text_el("page", "page_number", 56, 64, 34, 1350, "page_number", "tiny", "literal", value=str(v)), text_el("title", "document_title", 122, 74, 48, 1320, "book_title", "title", "title", 8, 42), *columns("body", 220, 74, 13 if v == 1 else 11, 30, 20 if v == 1 else 26, 1320, "paragraph", "body", 44, 140)]
    if v == 1:
        return [text_el("chapter", "chapter_title", 82, 74, 52, 1320, "lesson_title", "title", "title", 8, 42), image("fig", 190, 90, 170, 430, "lesson_figure"), text_el("caption", "caption", 385, 90, 30, 430, "figure_caption", "small", "short", 14, 36), *columns("body", 455, 90, 8, 32, 22, 1280, "paragraph", "body", 36, 120)]
    if v == 2:
        return [text_el("title", "chapter_title", 80, 70, 52, 1320, "vocabulary_title", "title", "safe_fragment", 4, 28), *fields("vocab", 180, 100, 4, 2, 118, 540), *columns("examples", 700, 110, 4, 32, 24, 1140, "paragraph", "body", 24, 80)]
    if v == 3:
        return [text_el("title", "chapter_title", 80, 70, 52, 1320, "concept_title", "title", "title", 8, 42), decor("note", 180, 100, 180, 960, "box soft-fill"), text_el("note_text", "note", 220, 130, 36, 900, "concept_note", "small", "fill", 24, 72), *columns("body", 410, 100, 8, 32, 22, 1200, "paragraph", "body", 34, 110)]
    if v == 4:
        return [text_el("title", "chapter_title", 80, 70, 52, 1320, "activity_title", "title", "safe_fragment", 4, 28), *[text_el(f"step_{i}", "list_item", x, 110, 34, 650, "activity_step", "body", "fill", 20, 64) for i, x in enumerate(range(190, 700, 90), 1)], *[answer(f"ans_{i}", x + 42, 110, 42, 650) for i, x in enumerate(range(190, 700, 90), 1)], *columns("note", 760, 120, 4, 30, 22, 1120, "note", "small", 18, 56)]
    if v == 5:
        return [text_el("title", "chapter_title", 80, 70, 52, 1320, "review_title", "title", "safe_fragment", 4, 28), *[text_el(f"q_{i}", "question_text", x, 100, 32, 520, "review_question", "body", "question", 14, 44) for i, x in enumerate(range(190, 900, 86), 1)], *[answer(f"a_{i}", x + 38, 100, 38, 520) for i, x in enumerate(range(190, 900, 86), 1)], *columns("summary", 190, 760, 8, 32, 22, 560, "paragraph", "body", 20, 68)]
    return [text_el("title", "chapter_title", 80, 70, 52, 1320, "diagram_title", "title", "title", 8, 42), image("diagram", 190, 100, 300, 520, "diagram"), text_el("caption", "caption", 520, 100, 30, 520, "diagram_caption", "small", "short", 14, 36), text_el("key_note", "note", 190, 690, 34, 640, "diagram_key_note", "small", "fill", 16, 52), *columns("body", 600, 100, 6, 32, 24, 1180, "paragraph", "body", 30, 96)]


def magazine(v: int) -> list[dict[str, Any]]:
    if v == 1:
        return [text_el("name", "document_title", 64, 64, 70, 1360, "magazine_name", "title", "safe_fragment", 4, 30), image("cover", 180, 100, 420, 760, "cover_image"), text_el("feature", "section_title", 650, 100, 68, 1100, "cover_feature", "title", "title", 8, 46), *briefs("cover_line", 720, 130, 6, 30, 42, 900)]
    if v == 2:
        return [text_el("title", "document_title", 60, 62, 52, 1360, "feature_title", "title", "title", 8, 46), image("image", 150, 84, 260, 520, "feature_image"), text_el("caption", "caption", 438, 84, 34, 520, "caption", "small", "short", 14, 34), text_el("section", "section_title", 520, 84, 46, 1280, "section_title", "subtitle", "title", 8, 40), *columns("body", 600, 84, 8, 32, 18, 1280, "paragraph", "body", 34, 120)]
    if v == 3:
        return [image("portrait", 80, 90, 220, 420, "portrait"), text_el("title", "document_title", 340, 90, 56, 1240, "interview_title", "title", "title", 8, 44), *[text_el(f"q_{i}", "section_title", x, 120, 30, 520, "interview_question", "small", "safe_fragment", 2, 14) for i, x in enumerate(range(430, 960, 90), 1)], *[text_el(f"a_{i}", "paragraph", x + 34, 120, 34, 1040, "interview_answer", "body", "fill", 28, 90) for i, x in enumerate(range(430, 960, 90), 1)]]
    if v == 4:
        return [text_el("title", "document_title", 70, 80, 54, 1300, "contents_title", "title", "safe_fragment", 4, 30), *[text_el(f"item_{i}", "list_item", x, 120, 32, 1120, "contents_item", "small", "fill", 16, 44) for i, x in enumerate(range(160, 1030, 58), 1)]]
    if v == 5:
        return [text_el("title", "document_title", 60, 80, 52, 1320, "photo_story_title", "title", "title", 8, 44), image("photo_a", 160, 90, 230, 390, "photo"), text_el("cap_a", "caption", 410, 90, 28, 390, "caption", "small", "short", 12, 34), image("photo_b", 500, 170, 230, 390, "photo"), text_el("cap_b", "caption", 750, 170, 28, 390, "caption", "small", "short", 12, 34), *columns("body", 830, 90, 5, 32, 20, 1180, "paragraph", "body", 28, 86)]
    return [text_el("title", "document_title", 70, 80, 54, 1320, "opinion_title", "title", "title", 8, 46), decor("quote", 170, 120, 180, 720, "box note-fill"), text_el("quote_text", "paragraph", 210, 150, 36, 660, "quote", "subtitle", "fill", 24, 76), *columns("body", 400, 100, 9, 32, 22, 1240, "paragraph", "body", 34, 118)]


def academic(v: int) -> list[dict[str, Any]]:
    base = [text_el("meta", "metadata", 54, 58, 42, 1460, "paper_meta", "small", "literal", value="2026"), text_el("title", "document_title", 128, 58, 56, 1460, "paper_title", "title", "title", 8, 52)]
    if v == 1:
        return base + [text_el("abstract", "section_title", 220, 76, 34, 1380, "abstract", "subtitle", "safe_fragment", 2, 18), *columns("body", 280, 76, 7, 30, 18, 1380, "paragraph", "body", 38, 120), image("fig", 710, 96, 250, 360, "figure"), text_el("caption", "caption", 988, 96, 28, 360, "caption", "small", "short", 12, 34), *columns("more", 710, 510, 5, 30, 18, 900, "paragraph", "body", 28, 90)]
    if v == 2:
        return base + [*columns("col_a", 230, 80, 6, 30, 18, 1320, "paragraph", "body", 34, 110), decor("mid_rule", 570, 80, 2, 1320, "rule-v"), *columns("col_b", 610, 80, 7, 30, 18, 1320, "paragraph", "body", 34, 110)]
    if v == 3:
        return base + [*columns("method", 230, 80, 5, 32, 20, 620, "paragraph", "body", 28, 90), image("chart", 560, 100, 300, 440, "experiment_chart"), text_el("caption", "caption", 890, 100, 28, 440, "chart_caption", "small", "short", 12, 34), *columns("result", 230, 780, 10, 30, 18, 620, "paragraph", "body", 24, 80)]
    if v == 4:
        return base + [*briefs("ref", 240, 90, 16, 28, 22, 1280)]
    if v == 5:
        return base + [image("figure", 230, 100, 360, 500, "figure"), text_el("caption", "caption", 620, 100, 30, 500, "figure_caption", "small", "short", 12, 34), *columns("explain", 700, 100, 6, 32, 22, 500, "paragraph", "body", 22, 76), *columns("body", 230, 720, 12, 30, 18, 680, "paragraph", "body", 26, 88)]
    return base + [text_el("conf", "metadata", 220, 80, 32, 1320, "conference_meta", "small", "literal", value="20260702"), text_el("abstract_title", "section_title", 280, 90, 40, 1260, "abstract_title", "subtitle", "safe_fragment", 2, 18), *columns("abstract", 350, 90, 10, 32, 22, 1260, "paragraph", "body", 30, 100)]


def historical(v: int) -> list[dict[str, Any]]:
    if v == 4:
        bg = {"background": "#2c2924", "color": "#efe5c9"}
        return [decor("dark_page", 46, 46, 868, 1508, "box dark-fill", bg), text_el("title", "metadata", 96, 96, 36, 1340, "rubbing_title", "small light", "safe_fragment", 2, 18), *columns("rubbing", 170, 110, 11, 34, 24, 1300, "paragraph", "body light", 30, 86)]
    out = [decor("outer", 44, 44, 872, 1512, "box"), text_el("meta", "metadata", 92, 86, 42, 1400, "archive_meta", "small", "literal" if v == 1 else "safe_fragment", 2, 20, "ᠮᠡᠳᠡᠭᠳᠡᠯ" if v == 1 else None)]
    if v == 2:
        out += [decor("scroll_band", 150, 70, 670, 1460, "note-fill"), *columns("scroll", 190, 100, 10, 34, 28, 1320, "paragraph", "body", 34, 96)]
    elif v == 3:
        out += [text_el("serial", "metadata", 170, 100, 28, 1300, "serial", "tiny", "literal", value="20260702"), *columns("record", 230, 110, 8, 34, 34, 1180, "paragraph", "body", 28, 84), text_el("seal", "seal", 790, 760, 100, 100, "seal", "subtitle stamp", "safe_fragment", 2, 10)]
    elif v == 5:
        out += [*columns("main", 170, 100, 8, 34, 24, 1320, "paragraph", "body", 34, 96), *briefs("note", 690, 130, 4, 24, 28, 1120)]
    elif v == 6:
        out += [*[text_el(f"name_{i}", "list_item", x, 100, 30, 1260, "genealogy_item", "small", "fill", 14, 44) for i, x in enumerate(range(170, 850, 52), 1)]]
    else:
        out += [*columns("classic", 178, 98, 11, 34, 24, 1330, "paragraph", "body", 34, 96), text_el("page", "page_number", 850, 102, 28, 1320, "page_number", "tiny", "literal", value=str(v))]
    return out


def notice(v: int) -> list[dict[str, Any]]:
    base = [decor("panel", 70, 70, 820, 1220, "box note-fill"), text_el("title", "document_title", 150, 118, 62, 1080, "notice_title", "title", "safe_fragment", 4, 28)]
    if v == 1:
        return base + [text_el("section", "section_title", 282, 140, 44, 1020, "notice_section", "subtitle", "title", 8, 42), *columns("body", 380, 140, 5, 36, 34, 1020, "paragraph", "body", 32, 92), text_el("date", "metadata", 760, 150, 38, 980, "date", "small", "literal", value="20260702")]
    if v == 2:
        return base + [*[text_el(f"item_{i}", "list_item", x, 140, 34, 900, "bulletin_item", "body", "fill", 20, 66) for i, x in enumerate(range(280, 800, 78), 1)]]
    if v == 3:
        return base + [*fields("meeting", 280, 150, 3, 1, 116, 300), *columns("body", 290, 560, 6, 34, 30, 620, "paragraph", "body", 24, 76), text_el("date", "metadata", 790, 150, 34, 980, "date", "small", "literal", value="20260702")]
    if v == 4:
        return base + [*[text_el(f"name_{i}", "list_item", x, 150, 28, 980, "public_name", "small", "fill", 12, 36) for i, x in enumerate(range(280, 820, 45), 1)]]
    if v == 5:
        return [decor("panel", 70, 70, 820, 1220, "box urgent-fill"), text_el("title", "document_title", 160, 120, 78, 1020, "urgent_title", "title", "safe_fragment", 4, 28), text_el("important", "section_title", 310, 150, 52, 920, "important", "subtitle", "title", 6, 32), *columns("body", 430, 150, 5, 38, 34, 900, "paragraph", "body", 22, 74)]
    return base + [*columns("campus", 290, 150, 7, 34, 28, 940, "paragraph", "body", 24, 78), text_el("date", "metadata", 820, 160, 32, 900, "date", "small", "literal", value="20260702")]


def form(v: int) -> list[dict[str, Any]]:
    out = [decor("outer", 54, 54, 1052, 1392, "box"), text_el("title", "document_title", 102, 92, 54, 1320, "form_title", "title", "safe_fragment", 4, 30)]
    if v == 1:
        return out + fields("field", 210, 110, 8, 2, 92, 420) + fields("field_bottom", 210, 1030, 5, 1, 130, 330)
    if v == 2:
        return out + fields("person", 200, 110, 6, 3, 118, 360) + [text_el("seal", "seal", 920, 980, 100, 100, "seal", "subtitle stamp", "safe_fragment", 2, 10)]
    if v == 3:
        for i, x in enumerate(range(210, 1020, 70), 1):
            out += [text_el(f"check_{i}", "field_label", x, 120, 26, 980, "check_label", "small", "safe_fragment", 2, 10), answer(f"box_{i}", x + 30, 120, 28, 980)]
        return out
    if v == 4:
        for i, x in enumerate(range(210, 940, 90), 1):
            out += [text_el(f"q_{i}", "question_text", x, 120, 32, 520, "survey_question", "body", "question", 12, 42), answer(f"a_{i}", x + 38, 120, 38, 520), text_el(f"q2_{i}", "question_text", x, 760, 32, 520, "survey_question", "body", "question", 12, 42), answer(f"a2_{i}", x + 38, 760, 38, 520)]
        return out
    if v == 5:
        return out + fields("service", 210, 120, 5, 2, 130, 390) + [text_el("opinion", "paragraph", 850, 150, 46, 780, "processing_opinion", "body boxed", "fill", 20, 66), text_el("bottom_note", "note", 250, 1030, 42, 330, "bottom_note", "small boxed", "fill", 16, 52), text_el("bottom_review", "metadata", 420, 1030, 34, 330, "bottom_review", "tiny", "literal", value="2026")]
    return out + [*[text_el(f"log_{i}", "list_item", x, 110, 30, 1100, "log_item", "small", "fill", 16, 44) for i, x in enumerate(range(210, 1030, 58), 1)], text_el("note", "note", 980, 110, 34, 1100, "note", "small", "fill", 18, 56), text_el("review", "metadata", 1030, 110, 28, 1100, "review_mark", "tiny", "literal", value="2026")]


def letter(v: int) -> list[dict[str, Any]]:
    base = [decor("paper", 70, 70, 900, 1340, "box")]
    if v == 1:
        return base + [text_el("recipient", "recipient", 130, 120, 44, 1180, "recipient", "subtitle hand", "title", 4, 24), *columns("body", 220, 130, 9, 34, 24, 1160, "paragraph", "body hand", 30, 90), text_el("date", "metadata", 820, 160, 40, 1000, "date", "small", "literal", value="20260702")]
    if v == 2:
        return [decor("note_paper", 80, 80, 880, 1320, "note-fill"), text_el("title", "document_title", 130, 120, 44, 1160, "note_title", "subtitle hand", "safe_fragment", 4, 24), *briefs("note", 220, 130, 9, 34, 24, 1100)]
    if v == 3:
        return base + [text_el("title", "document_title", 120, 110, 42, 1200, "meeting_title", "subtitle hand", "safe_fragment", 4, 24), *[text_el(f"item_{i}", "list_item", x, 130, 32, 520, "meeting_item", "body hand", "fill", 20, 64) for i, x in enumerate(range(220, 860, 90), 1)], *columns("conclusion", 220, 760, 7, 32, 24, 480, "paragraph", "body hand", 20, 64)]
    if v == 4:
        return [decor("diary", 80, 80, 880, 1320, "box note-fill"), text_el("date", "metadata", 130, 120, 36, 1180, "diary_date", "small", "literal", value="20260702"), *columns("diary", 210, 130, 10, 34, 24, 1120, "paragraph", "body hand", 28, 88)]
    if v == 5:
        return [decor("memo", 140, 160, 720, 940, "box note-fill"), text_el("title", "document_title", 210, 210, 58, 760, "memo_title", "title hand", "safe_fragment", 4, 26), *columns("memo_body", 340, 230, 5, 40, 44, 720, "paragraph", "body hand", 18, 58), text_el("memo_postscript", "note", 760, 260, 36, 620, "memo_postscript", "small hand", "fill", 14, 42)]
    return base + [*columns("main", 130, 120, 8, 34, 24, 1140, "paragraph", "body hand", 28, 88), *briefs("annot", 760, 160, 4, 26, 30, 980), text_el("date", "metadata", 900, 160, 32, 980, "date", "small", "literal", value="20260702")]


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
    name, family, prompt = template_meta(category, category_cn, variant)
    width, height = page_for(category, variant)
    template_id = f"{category}_vertical_tree_{variant:02d}"
    return {
        "schema_version": "mongolian_vertical_layout_tree.v3",
        "template_id": template_id,
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
            "font_scale": "native_vertical",
        },
        "qa_expectations": {
            "min_blocks": {
                "newspaper_page": 18,
                "certificate_proof": 6,
                "exam_paper": 20,
                "sign_poster_scene": 4,
                "book_page": 8,
                "textbook_page": 10,
                "magazine_journal": 9,
                "academic_paper": 12,
                "historical_classic": 10,
                "notice_announcement": 5,
                "complex_form": 18,
                "handwritten_letter": 10,
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
    write_json(root / "index.json", {"schema_version": "mongolian_vertical_template_index.v3", "templates": index})
    (root / "README.md").write_text(
        "# 传统蒙古文 v3 JSON 结构树模板库\n\n"
        "本目录包含 12 类 x 6 套 = 72 个完整 JSON 结构树。每个 JSON 文件都是一套独立版式，生成器只负责解释这些结构树并填充传统蒙古文文本。\n\n"
        "- `page`：画布尺寸与裁切策略\n"
        "- `design_prompt`：该模板的版面意图\n"
        "- `elements`：所有文本块、图片块、答题区、装饰框的坐标、标签和文本填充策略\n",
        encoding="utf-8",
    )
    print(json.dumps({"output_root": str(root), "templates": len(index)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
