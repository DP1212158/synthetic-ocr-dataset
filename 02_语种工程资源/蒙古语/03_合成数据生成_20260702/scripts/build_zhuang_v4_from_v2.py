#!/usr/bin/env python3
"""Build Zhuang v4 from v2 with split Chinese mixing, image assets, reading order, and augmentation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


DELIVERY_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = DELIVERY_ROOT
ENGINE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_ROOT = Path("/Users/dp/.cache/codex-runtimes/codex-primary-runtime/dependencies")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")

NATURAL_LABELS = {
    "document_title",
    "document_subtitle",
    "section_title",
    "paragraph",
    "quote",
    "question",
    "question_text",
    "option",
    "field_value",
    "table_cell_text",
    "note",
    "list_item",
    "caption",
    "footer",
    "chapter_title",
}

CHINESE_SNIPPETS = {
    "newspaper_page": [
        "社区服务中心发布便民消息", "村镇道路维护安排已经确认", "本地学校组织文化展示", "卫生服务点延长开放时间",
        "农业技术人员开展现场指导", "公共交通班次临时调整", "读者反馈栏目收到新来信", "基层治理经验正在整理",
        "青年志愿者参与社区巡查", "传统节庆活动有序筹备", "市场监管人员完成例行检查", "图书阅览室新增借阅服务",
        "乡村广播提醒群众注意安全", "文化馆开放周末培训课程", "便民热线记录群众诉求", "专题报道关注民生变化",
        "水利设施检修计划公布", "农产品展销活动吸引居民", "社区医生开展健康咨询", "校园社团展示学习成果",
    ],
    "certificate_proof": [
        "经审核材料真实有效", "本证明仅用于资格核验", "证书编号已完成登记", "发证单位留存备案材料",
        "持有人信息与档案一致", "有效期限以系统记录为准", "相关印章由经办机构确认", "复印件需与原件同时核对",
        "申请事项已经完成审查", "登记日期以签发记录为准", "证明内容不得擅自涂改", "业务窗口保留查验记录",
        "身份信息已按流程复核", "本页用于档案归集", "授权范围限本次办理", "经办人已完成签收",
    ],
    "exam_paper": [
        "请在指定区域内作答", "本题要求结合材料分析", "选择答案前请认真审题", "答题卡保持整洁清晰",
        "每小题只有一个正确答案", "阅读短文后完成问题", "考试结束后交回试卷", "不得在密封线外书写",
        "请按题号顺序填写答案", "作文部分注意段落完整", "听力材料播放两遍", "评分标准以卷面说明为准",
        "请使用黑色签字笔作答", "漏答题目不另行补时", "判断题请写明理由", "计算过程需要保留",
    ],
    "sign_poster_scene": [
        "请按现场指引有序通行", "服务窗口今日正常开放", "活动入口设置在广场东侧", "请勿遮挡安全通道",
        "咨询台提供资料领取", "参观人员请保持队形", "临时停车区域已经划定", "开放时间以公告为准",
        "报名信息请现场确认", "文明参与共同维护秩序", "紧急出口保持畅通", "展览路线从左侧开始",
        "预约人员优先办理", "请保管好个人物品", "现场广播将发布提示", "服务点提供饮用水",
    ],
    "book_page": [
        "本章介绍地方社会生活", "作者在这里说明背景", "以下段落可作为阅读材料", "请结合上下文理解含义",
        "人物关系在本节逐步展开", "故事发生在一个普通清晨", "叙述中保留了地方风俗", "读者需要注意时间线索",
        "这一节强调语言与文化", "材料选自课堂延伸阅读", "文中描写了劳动场景", "章节末尾附有思考问题",
        "请留意关键词的重复出现", "本页内容用于课外阅读", "段落之间存在承接关系", "作者采用平实叙述方式",
    ],
    "textbook_page": [
        "学习目标包括词语理解", "课堂活动建议分组完成", "请朗读课文并标出重点", "课后练习用于巩固知识",
        "教师可引导学生讨论", "本课包含阅读与表达训练", "知识拓展部分联系生活", "例句展示常用表达方式",
        "请比较两段材料差异", "练习题按难度逐步增加", "复习时注意书写规范", "学习评价关注理解能力",
        "小组交流后完成记录", "课堂导入可使用图片材料", "本单元强调综合运用", "请根据提示补充句子",
    ],
    "magazine_journal": [
        "本期专题关注地方文化", "编辑部整理读者来稿", "人物访谈记录生活细节", "图文栏目展示社区变化",
        "青年作者分享学习经验", "专题策划围绕传统技艺", "地方观察呈现新面貌", "摄影作品记录日常瞬间",
        "栏目导语说明选题背景", "评论文章讨论公共议题", "读者互动页面摘录留言", "文化随笔保持轻松风格",
        "封面故事延伸到内页", "本期推荐三篇长文", "专题图片来自活动现场", "编辑手记记录采访过程",
    ],
    "academic_paper": [
        "研究方法采用文本统计", "样本来源经过人工复核", "实验结果显示明显差异", "相关工作主要集中在识别任务",
        "本文讨论数据构建流程", "评价指标包括准确率和召回率", "表格列出主要实验设置", "结论部分仍需进一步验证",
        "摘要概述研究目的和方法", "关键词反映核心研究对象", "误差分析关注边界样本", "消融实验说明模块贡献",
        "数据清洗过程保留日志", "模型输出经过一致性检查", "本文使用公开资料作为补充", "未来工作将扩展语种范围",
    ],
    "historical_classic": [
        "整理说明记录版本来源", "馆藏编号用于档案检索", "抄本边缘存在轻微残损", "校注人员保留原文次序",
        "旧纸颜色影响辨识效果", "本页依据影印件重新排版", "缺字位置已在备注中说明", "版本差异需要继续核对",
        "档案来源见目录登记", "释文仅供研究参考", "残页内容按上下文补录", "收藏单位保存扫描副本",
        "纸面折痕不影响主体文字", "古籍页码与现代编号不同", "题记位置保持原貌", "校勘说明附在页末",
    ],
    "notice_announcement": [
        "请相关人员按时办理", "材料提交截止日期另行通知", "公告事项自发布之日起执行", "联系人信息见页面下方",
        "办理地点设在综合服务窗口", "申请材料需保持完整", "逾期未办将顺延处理", "本通知适用于本次活动",
        "现场审核需要携带证件", "具体安排以电话确认为准", "公示期间接受群众监督", "请各单位及时转发",
        "报名名单将在公告栏更新", "如遇特殊情况另行说明", "咨询时间为工作日上午", "附件材料请按顺序装订",
    ],
    "complex_form": [
        "申请事项请如实填写", "基本信息用于档案登记", "联系电话需保持畅通", "审核意见由经办人填写",
        "本人承诺材料真实", "提交材料请逐项核对", "签名栏不得代签", "表格涂改处需要确认",
        "受理编号由系统生成", "办理结果将短信通知", "证件号码仅用于核验", "备注栏可补充特殊情况",
        "单位意见需加盖公章", "家庭住址请填写完整", "复核结果由窗口保存", "附件清单随表提交",
    ],
    "handwritten_letter": [
        "近来一切都还顺利", "收到来信后很高兴", "请代我问候家里人", "这些事情以后慢慢细说",
        "天气转凉记得添衣", "有空请再写信给我", "路上见到的景色很好", "我把近况简单写下",
        "工作虽然忙但还安稳", "朋友们都很惦记你", "希望你保持身体健康", "下次见面再详细谈",
        "这封短信写得匆忙", "家中事情都已安排", "愿你学习工作顺利", "收到后请回个消息",
    ],
    "default": [
        "请核对相关信息", "内容仅供参考", "具体安排见通知", "材料已经整理完成",
        "后续事项另行说明", "记录内容已经归档", "页面信息按要求填写", "请保持文本清晰",
    ],
}

LABEL_CJK_TARGETS = {
    "document_title": 0.04,
    "document_subtitle": 0.05,
    "section_title": 0.04,
    "chapter_title": 0.04,
    "paragraph": 0.11,
    "quote": 0.10,
    "question": 0.10,
    "question_text": 0.10,
    "option": 0.04,
    "field_value": 0.06,
    "table_cell_text": 0.07,
    "note": 0.09,
    "list_item": 0.08,
    "caption": 0.07,
    "footer": 0.06,
}

LABEL_LENGTH_GROWTH = {
    "document_title": 1.04,
    "document_subtitle": 1.03,
    "section_title": 1.04,
    "paragraph": 1.00,
    "quote": 1.00,
    "question": 1.01,
    "option": 1.02,
    "field_value": 1.03,
    "table_cell_text": 1.02,
    "note": 1.01,
    "list_item": 1.01,
    "caption": 1.02,
    "footer": 1.02,
}

CATEGORY_TARGET_ADJUST = {
    "exam_paper": {"document_title": 0.04, "section_title": 0.04, "option": 0.04, "table_cell_text": 0.05, "question": 0.09, "question_text": 0.10},
    "certificate_proof": {"paragraph": 0.09, "field_value": 0.05},
    "sign_poster_scene": {"document_title": 0.06, "section_title": 0.06, "paragraph": 0.10, "list_item": 0.08},
    "academic_paper": {"paragraph": 0.11, "note": 0.09, "table_cell_text": 0.07},
    "historical_classic": {"paragraph": 0.10, "note": 0.08, "field_value": 0.06},
    "magazine_journal": {"paragraph": 0.10, "quote": 0.09},
    "book_page": {"paragraph": 0.10, "quote": 0.09},
    "notice_announcement": {"paragraph": 0.10, "field_value": 0.06},
}

MIX_LABEL_PRIORITY = {
    "paragraph": 0,
    "question": 1,
    "question_text": 1,
    "quote": 2,
    "list_item": 3,
    "note": 4,
    "field_value": 5,
    "table_cell_text": 6,
    "caption": 7,
    "option": 8,
    "section_title": 9,
    "document_subtitle": 10,
    "footer": 11,
    "document_title": 12,
}

BOOST_MIX_LABELS = {
    "paragraph",
    "question",
    "question_text",
    "quote",
    "list_item",
    "note",
    "field_value",
    "table_cell_text",
    "caption",
    "option",
    "footer",
}

DOCUMENT_CJK_TARGETS = {
    2: 0.14,
    4: 0.18,
    6: 0.16,
}

MIXED_DOCUMENT_MIN_CJK_RATIO = 0.10
MIXED_DOCUMENT_GENERATION_MIN_CJK_RATIO = 0.125
MIXED_DOCUMENT_MAX_CJK_RATIO = 0.28

MIXED_VARIANTS = {2, 4, 6}
PURE_VARIANTS = {1, 3, 5}

OTHER_SCRIPT_PATTERNS = {
    "cyrillic": re.compile(r"[\u0400-\u04ff]"),
    "tibetan": re.compile(r"[\u0f00-\u0fff]"),
    "arabic": re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]"),
    "mongolian": re.compile(r"[\u1800-\u18af]"),
    "hangul": re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]"),
}
ALL_SCRIPT_PATTERNS = {
    "latin": LATIN_RE,
    "cjk": CJK_RE,
    **OTHER_SCRIPT_PATTERNS,
}
PRIVATE_USE_RE = re.compile(r"[\ue000-\uf8ff]")
REPLACEMENT_OR_BOX_RE = re.compile(r"[\ufffd\u25a0\u25a1\u25af]")
ZERO_WIDTH_UNSUPPORTED_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]")


def runtime_python() -> str:
    candidate = DEFAULT_RUNTIME_ROOT / "python" / "bin" / "python3"
    return str(candidate) if candidate.exists() else sys.executable


def runtime_node() -> str:
    candidate = DEFAULT_RUNTIME_ROOT / "node" / "bin" / "node"
    return str(candidate) if candidate.exists() else "node"


def node_env() -> dict[str, str]:
    env = dict(**__import__("os").environ)
    candidate = DEFAULT_RUNTIME_ROOT / "node" / "node_modules"
    if candidate.exists():
        env["NODE_PATH"] = str(candidate)
    return env


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def category_dirs(version_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in version_dir.iterdir()
        if p.is_dir()
        and len(p.name) >= 3
        and p.name[:2].isdigit()
        and (p / "metadata" / "html_manifest.json").exists()
    )


def find_asset_dir(project_root: Path, explicit: Path | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    candidates.extend([
        project_root / "random120-coco2014",
        project_root / "random120_coco2014",
    ])
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    matches = [p for p in project_root.rglob("*") if p.is_dir() and p.name in {"random120-coco2014", "random120_coco2014"}]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError("cannot find random120-coco2014 or random120_coco2014 under project root")
    raise RuntimeError(f"multiple image asset dirs found: {matches}")


def load_image_assets(asset_dir: Path) -> list[dict[str, Any]]:
    assets = []
    for path in sorted(asset_dir.iterdir()):
        if path.suffix.lower() not in IMAGE_EXTS or not path.is_file():
            continue
        with Image.open(path) as img:
            width, height = img.size
        assets.append({
            "asset_id": path.stem,
            "source_path": str(path),
            "file_name": path.name,
            "width": width,
            "height": height,
        })
    if not assets:
        raise RuntimeError(f"no readable image assets in {asset_dir}")
    return assets


def copy_clean_static(src_v2: Path, clean_dir: Path, force: bool) -> None:
    if clean_dir.exists():
        if not force:
            raise FileExistsError(f"{clean_dir} exists; use --force")
        shutil.rmtree(clean_dir)
    clean_dir.mkdir(parents=True)
    for name in ["metadata", "reports", "assets"]:
        if (src_v2 / name).exists():
            shutil.copytree(src_v2 / name, clean_dir / name, dirs_exist_ok=True)
    for cat in category_dirs(src_v2):
        dst = clean_dir / cat.name
        for sub in ["html", "images", "labels", "metadata", "reports", "reports/overlays"]:
            (dst / sub).mkdir(parents=True, exist_ok=True)
        shutil.copytree(cat / "html", dst / "html", dirs_exist_ok=True)
        shutil.copytree(cat / "metadata", dst / "metadata", dirs_exist_ok=True)
        if (cat / "README.md").exists():
            shutil.copy2(cat / "README.md", dst / "README.md")


def build_profile(src_profile: Path, out_profile: Path, target_cjk_ratio: float) -> dict[str, Any]:
    profile = read_json(src_profile)
    profile["profile_note"] = "Zhuang v4 allows per-document Chinese mixing only for selected variants."
    profile["max_cjk_ratio"] = 1.0
    profile["min_script_ratio"] = min(float(profile.get("min_script_ratio", 0.45)), 0.30)
    profile["target_cjk_ratio"] = target_cjk_ratio
    profile["language_mix_policy"] = "per_category_variants_1_3_5_pure_2_4_6_mixed"
    write_json(out_profile, profile)
    return profile


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def compact_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def cjk_len(text: str) -> int:
    return len(CJK_RE.findall(text or ""))


def infer_target_script(profile: dict[str, Any] | None) -> str:
    profile = profile or {}
    cleanup = str(profile.get("cleanup_profile", "")).lower()
    code = str(profile.get("language_code", "")).lower()
    regex = str(profile.get("script_regex", "")).lower()
    if "hangul" in cleanup or code.startswith("ko") or "ac00" in regex:
        return "hangul"
    if "arabic" in cleanup or "uyghur" in cleanup or "kazakh" in cleanup or "0600" in regex or code in {"ug", "kk-arab"}:
        return "arabic"
    if "mongolian" in cleanup or "1800" in regex or "mong" in code:
        return "mongolian"
    if "tibetan" in cleanup or "0f00" in regex or code.startswith("bo"):
        return "tibetan"
    return "latin"


def sanitize_source_text_for_profile(text: str, profile: dict[str, Any] | None) -> str:
    """Remove source-side script contamination before controlled CJK mixing.

    This keeps the target script, digits, punctuation, and spacing. Any Chinese
    required by the delivery policy is injected later by ``mixed_text``; source
    CJK snippets from Wikipedia-style parentheticals are removed here so pure
    samples stay pure and mixed samples only contain controlled Chinese.
    """
    text = normalize_text(text)
    text = REPLACEMENT_OR_BOX_RE.sub("", text)
    target = infer_target_script(profile)
    if target == "latin":
        # Latin-script languages such as Zhuang/Bai intentionally use Latin; do
        # not strip ordinary ASCII words from their source pool.
        return text
    out = text
    for script_name, pattern in ALL_SCRIPT_PATTERNS.items():
        if script_name == target:
            continue
        out = pattern.sub("", out)
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\(\s*\)|（\s*）|《\s*》|:\s*(?=[。；，、,.!?;:]|$)", "", out)
    out = re.sub(r"\s+([。；，、,.!?;:])", r"\1", out)
    return out.strip(" ,.;:/|，。；、:-")


def take_compact_prefix(text: str, max_nonspace_chars: int) -> str:
    if max_nonspace_chars <= 0:
        return ""
    kept = []
    seen = 0
    for ch in text:
        if not ch.isspace():
            seen += 1
        kept.append(ch)
        if seen >= max_nonspace_chars:
            break
    return "".join(kept).strip(" ,.;:/|，。；、")


def should_mix(label: str, text: str, target_script_re: re.Pattern[str] | None = None) -> bool:
    if label not in NATURAL_LABELS:
        return False
    text = normalize_text(text)
    if len(text) < 6:
        return False
    target_script_re = target_script_re or LATIN_RE
    if not target_script_re.search(text):
        return False
    if CJK_RE.search(text):
        return False
    if sum(ch.isdigit() for ch in text) > max(4, len(text) * 0.35):
        return False
    return True


def choose_snippet(category: str, label: str, rng: random.Random) -> str:
    pool = CHINESE_SNIPPETS.get(category) or CHINESE_SNIPPETS["default"]
    snippet = rng.choice(pool)
    if label == "document_title" and len(snippet) > 10:
        return snippet[:10]
    if label in {"caption", "note", "option"} and len(snippet) > 12:
        return snippet[:12]
    return snippet


def target_for_block(category: str, label: str) -> float:
    target = LABEL_CJK_TARGETS.get(label, 0.30)
    return CATEGORY_TARGET_ADJUST.get(category, {}).get(label, target)


def build_chinese_text(category: str, label: str, min_cjk_chars: int, rng: random.Random) -> str:
    pool = CHINESE_SNIPPETS.get(category) or CHINESE_SNIPPETS["default"]
    snippets: list[str] = []
    used: set[str] = set()
    while cjk_len("".join(snippets)) < min_cjk_chars:
        if len(used) >= len(pool):
            used.clear()
        candidates = [item for item in pool if item not in used] or pool
        snippet = rng.choice(candidates)
        used.add(snippet)
        if label == "document_title" and len(snippet) > 6:
            snippet = snippet[: max(2, min(6, min_cjk_chars))]
        elif label in {"document_subtitle", "section_title"} and len(snippet) > 8:
            snippet = snippet[: max(2, min(8, min_cjk_chars))]
        elif label in {"caption", "note", "option", "field_value", "table_cell_text", "footer"} and len(snippet) > 8:
            snippet = snippet[: max(2, min(8, min_cjk_chars))]
        elif len(snippet) > 14:
            snippet = snippet[: max(2, min(14, min_cjk_chars))]
        snippets.append(snippet)
    return "；".join(snippets)


def mixed_text(text: str, category: str, label: str, rng: random.Random) -> str:
    text = normalize_text(text)
    original_chars = compact_len(text)
    if original_chars <= 0:
        return text
    target = target_for_block(category, label)
    growth = LABEL_LENGTH_GROWTH.get(label, 1.04)
    final_chars = max(original_chars, int(round(original_chars * growth)))
    if original_chars < 24:
        final_chars += 2
    desired_cjk = max(2, int(round(final_chars * target)))
    chinese = build_chinese_text(category, label, desired_cjk, rng)
    chinese_chars = cjk_len(chinese)
    separator_chars = 1 if label in {"document_title", "section_title", "document_subtitle"} else 2
    original_budget = max(6, final_chars - compact_len(chinese) - separator_chars)
    original_part = take_compact_prefix(text, min(original_chars, original_budget))
    if label in {"document_title", "section_title", "document_subtitle"}:
        return f"{original_part} {chinese}".strip()
    if label in {"caption", "note", "option", "field_value"}:
        return f"{original_part} / {chinese}".strip()
    if label == "table_cell_text":
        return f"{original_part}；{chinese}".strip()
    return f"{original_part}。{chinese}".strip()


def boost_mixed_text(text: str, category: str, label: str, min_extra_cjk: int, rng: random.Random) -> str:
    """Append enough Chinese context for short-block documents to pass mixed-ratio QA."""
    text = normalize_text(text)
    if min_extra_cjk <= 0:
        return text
    current_cjk = cjk_len(text)
    chinese = build_chinese_text(category, label, current_cjk + min_extra_cjk, rng)
    extra = chinese[current_cjk:] if current_cjk and chinese.startswith(text) else chinese
    if cjk_len(extra) < min_extra_cjk:
        extra = build_chinese_text(category, label, min_extra_cjk, rng)
    if label in {"document_title", "section_title", "document_subtitle"}:
        return f"{text} {extra}".strip()
    if label in {"caption", "note", "option", "field_value", "table_cell_text", "footer"}:
        return f"{text}；{extra}".strip()
    return f"{text}。{extra}".strip()


def extra_cjk_needed_for_ratio(total_chars: int, total_cjk: int, target_ratio: float) -> int:
    """Return extra CJK chars needed when appended text also grows denominator."""
    needed = 0
    while (total_cjk + needed) / max(total_chars + needed, 1) < target_ratio:
        needed += 1
    return needed


def html_block_replacer(
    html_text: str,
    category: str,
    rng: random.Random,
    stats: dict[str, Any],
    *,
    allow_mix: bool,
    document_target_cjk_ratio: float | None = None,
    target_script_re: re.Pattern[str] | None = None,
    profile: dict[str, Any] | None = None,
) -> str:
    pattern = re.compile(
        r'(<(?P<tag>[a-zA-Z0-9]+)(?P<attrs>[^>]*\bdata-block-id="(?P<bid>[^"]+)"[^>]*\bdata-label="(?P<label>[^"]+)"[^>]*)>)'
        r'(?P<inner>.*?)'
        r'(</(?P=tag)>)',
        re.DOTALL,
    )
    final_by_index: dict[int, str] = {}
    sanitized_by_index: dict[int, str] = {}
    if allow_mix:
        candidates: list[dict[str, Any]] = []
        total_chars = 0
        total_cjk = 0
        for idx, match in enumerate(pattern.finditer(html_text)):
            label = match.group("label")
            inner = match.group("inner")
            text = re.sub(r"<[^>]+>", " ", inner)
            normalized = sanitize_source_text_for_profile(text, profile)
            sanitized_by_index[idx] = normalized
            total_chars += compact_len(normalized)
            total_cjk += cjk_len(normalized)
            if not should_mix(label, normalized, target_script_re):
                continue
            mixed = mixed_text(normalized, category, label, rng)
            candidates.append({
                "idx": idx,
                "label": label,
                "text": normalized,
                "mixed": mixed,
                "chars": compact_len(normalized),
                "mixed_chars": compact_len(mixed),
                "mixed_cjk": cjk_len(mixed),
                "priority": MIX_LABEL_PRIORITY.get(label, 99),
                "jitter": rng.random(),
            })
        target_ratio = document_target_cjk_ratio or 0.16
        for item in sorted(candidates, key=lambda row: (row["priority"], -row["chars"], row["jitter"])):
            next_chars = total_chars - item["chars"] + item["mixed_chars"]
            next_cjk = total_cjk + item["mixed_cjk"]
            next_ratio = next_cjk / max(next_chars, 1)
            if next_ratio <= MIXED_DOCUMENT_MAX_CJK_RATIO or (total_cjk / max(total_chars, 1)) < MIXED_DOCUMENT_GENERATION_MIN_CJK_RATIO:
                final_by_index[item["idx"]] = item["mixed"]
                total_chars = next_chars
                total_cjk = next_cjk
            if total_cjk / max(total_chars, 1) >= target_ratio:
                break
        if (total_cjk / max(total_chars, 1)) < MIXED_DOCUMENT_GENERATION_MIN_CJK_RATIO:
            for item in sorted(candidates, key=lambda row: (-row["chars"], row["priority"], row["jitter"])):
                if item["idx"] in final_by_index:
                    continue
                next_chars = total_chars - item["chars"] + item["mixed_chars"]
                next_cjk = total_cjk + item["mixed_cjk"]
                next_ratio = next_cjk / max(next_chars, 1)
                if next_ratio <= MIXED_DOCUMENT_MAX_CJK_RATIO:
                    final_by_index[item["idx"]] = item["mixed"]
                    total_chars = next_chars
                    total_cjk = next_cjk
                if total_cjk / max(total_chars, 1) >= MIXED_DOCUMENT_GENERATION_MIN_CJK_RATIO:
                    break
        if candidates and (total_cjk / max(total_chars, 1)) < MIXED_DOCUMENT_GENERATION_MIN_CJK_RATIO:
            # Vertical Mongolian and form/exam pages can have only a few short
            # eligible blocks. In that case, replacing every candidate may still
            # undershoot the document-level mixed ratio, so extend selected blocks
            # while respecting the upper bound.
            boost_candidates = [item for item in candidates if item["label"] in BOOST_MIX_LABELS]
            for item in sorted(boost_candidates, key=lambda row: (row["priority"], -row["chars"], row["jitter"])):
                current_text = final_by_index.get(item["idx"], item["mixed"])
                current_chars = compact_len(current_text)
                current_cjk = cjk_len(current_text)
                other_chars = total_chars - current_chars
                other_cjk = total_cjk - current_cjk
                needed = extra_cjk_needed_for_ratio(total_chars, total_cjk, MIXED_DOCUMENT_GENERATION_MIN_CJK_RATIO)
                if needed <= 0:
                    break
                max_total_cjk = int(MIXED_DOCUMENT_MAX_CJK_RATIO * max(total_chars + needed, 1))
                allowed_extra = max_total_cjk - total_cjk
                extra_cjk = max(1, min(needed, allowed_extra))
                if extra_cjk <= 0:
                    continue
                boosted = boost_mixed_text(current_text, category, item["label"], extra_cjk, rng)
                next_chars = other_chars + compact_len(boosted)
                next_cjk = other_cjk + cjk_len(boosted)
                if next_cjk / max(next_chars, 1) <= MIXED_DOCUMENT_MAX_CJK_RATIO:
                    final_by_index[item["idx"]] = boosted
                    total_chars = next_chars
                    total_cjk = next_cjk
                if total_cjk / max(total_chars, 1) >= MIXED_DOCUMENT_GENERATION_MIN_CJK_RATIO:
                    break
        stats["document_target_cjk_ratio"] = target_ratio
        stats["eligible_mix_blocks"] = len(candidates)
        stats["selected_mix_blocks"] = len(final_by_index)
        stats["estimated_document_cjk_ratio"] = round(total_cjk / max(total_chars, 1), 4)
    else:
        for idx, match in enumerate(pattern.finditer(html_text)):
            inner = match.group("inner")
            text = re.sub(r"<[^>]+>", " ", inner)
            normalized = sanitize_source_text_for_profile(text, profile)
            if normalized != normalize_text(text):
                sanitized_by_index[idx] = normalized

    def repl(match: re.Match[str]) -> str:
        idx = repl.match_index
        repl.match_index += 1
        label = match.group("label")
        inner = match.group("inner")
        text = re.sub(r"<[^>]+>", " ", inner)
        candidate_text = sanitized_by_index.get(idx, text)
        if allow_mix and idx in final_by_index and should_mix(label, candidate_text, target_script_re):
            new_text = final_by_index[idx]
            stats["mixed_blocks"] += 1
            stats["inserted_cjk_chars"] += len(CJK_RE.findall(new_text)) - len(CJK_RE.findall(text))
            return f'{match.group(1)}{html.escape(new_text, quote=False)}{match.group(7)}'
        if idx in sanitized_by_index:
            return f'{match.group(1)}{html.escape(sanitized_by_index[idx], quote=False)}{match.group(7)}'
        return match.group(0)

    repl.match_index = 0
    return pattern.sub(repl, html_text)


def reduce_decor_lines(html_text: str) -> tuple[str, dict[str, int]]:
    """Reduce non-structural horizontal separators while preserving tables/forms."""
    stats = {
        "border_bottom_removed": 0,
        "border_top_softened": 0,
        "dotted_softened": 0,
        "text_container_border_removed": 0,
        "text_container_box_shadow_removed": 0,
    }
    replacements = [
        (r"border-bottom:\s*1px\s+solid\s+[^;}{]+;", "", "border_bottom_removed"),
        (r"border-bottom:\s*1px\s+dotted\s+[^;}{]+;", "border-bottom:0;", "dotted_softened"),
        (r"border-top:\s*1px\s+solid\s+[^;}{]+;", "border-top:0;", "border_top_softened"),
        (r"border-top:\s*1px\s+dotted\s+[^;}{]+;", "border-top:0;", "dotted_softened"),
    ]
    out = html_text
    for pattern, repl, key in replacements:
        out, count = re.subn(pattern, repl, out)
        stats[key] += count
    text_container_classes = [
        "community-box", "fact-box", "calendar-box", "contact-box", "small-ad-box",
        "digest-card", "proof-kv", "proof-clause", "digital-kv", "number-line",
        "margin-note", "reading-map-item", "figure-note", "followup", "side-note",
        "toc-row", "extract", "point", "mini-ex", "appendix-row", "metric",
        "analysis-note", "paper-footnote", "ref-item", "review-card", "timeline-item",
        "brief-line", "strip-item",
    ]
    for cls in text_container_classes:
        pattern = rf"(\.{re.escape(cls)}\s*\{{[^}}]*?)border(?:-(?:left|right|top|bottom))?\s*:\s*(?!0\b|none\b)[^;}}]+;([^}}]*\}})"
        while True:
            out, count = re.subn(pattern, r"\1\2", out, flags=re.IGNORECASE)
            stats["text_container_border_removed"] += count
            if count == 0:
                break
        shadow_pattern = rf"(\.{re.escape(cls)}\s*\{{[^}}]*?)box-shadow\s*:\s*[^;}}]+;([^}}]*\}})"
        out, count = re.subn(shadow_pattern, r"\1\2", out, flags=re.IGNORECASE)
        stats["text_container_box_shadow_removed"] += count
    # Restore important structural line styles by keeping stronger borders untouched.
    return out, stats


def img_tag(asset: dict[str, Any], rel_src: str) -> str:
    return (
        f'<img src="{html.escape(rel_src, quote=True)}" '
        f'style="width:100%;height:100%;object-fit:cover;display:block;" '
        f'alt="" data-asset-img="true" />'
    )


def replace_image_placeholders(
    html_text: str,
    document_id: str,
    category: str,
    assets: list[dict[str, Any]],
    asset_dest_dir: Path,
    html_file: Path,
    manifest: list[dict[str, Any]],
    *,
    profile: dict[str, Any] | None = None,
    seed: int = 0,
) -> tuple[str, int]:
    pattern = re.compile(
        r'(<(?P<tag>[a-zA-Z0-9]+)(?P<attrs>[^>]*\bdata-block-id="(?P<bid>[^"]+)"[^>]*\bdata-label="(?P<label>image|photo|figure|photo_lead|image_figure)"[^>]*)>)'
        r'(?P<inner>.*?)'
        r'(</(?P=tag)>)',
        re.DOTALL,
    )
    profile = profile or {}
    language_code = str(profile.get("language_code") or profile.get("language_name") or "unknown")
    used_asset_ids = {str(row.get("asset_id")) for row in manifest}

    def select_asset(block_id: str, slot_index: int) -> dict[str, Any]:
        # Stable per language/document/block randomness. This prevents every
        # language from consuming the sorted COCO list in the same order.
        key = f"{seed}|{language_code}|{category}|{document_id}|{block_id}|{slot_index}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        start = int(digest[:12], 16) % len(assets)
        for offset in range(len(assets)):
            candidate = assets[(start + offset) % len(assets)]
            if candidate["asset_id"] not in used_asset_ids:
                used_asset_ids.add(candidate["asset_id"])
                return candidate
        candidate = assets[start]
        used_asset_ids.add(candidate["asset_id"])
        return candidate

    def repl(match: re.Match[str]) -> str:
        slot_index = repl.slot_index
        repl.slot_index += 1
        asset = select_asset(match.group("bid"), slot_index)
        dst_asset = asset_dest_dir / asset["file_name"]
        if not dst_asset.exists():
            shutil.copy2(asset["source_path"], dst_asset)
        rel_src = Path("../../assets/random120-coco2014") / asset["file_name"]
        open_tag = match.group(1)
        if "data-is-text=" not in open_tag:
            open_tag = open_tag[:-1] + ' data-is-text="false">'
        for attr, value in [
            ("data-asset-id", asset["asset_id"]),
            ("data-asset-source", "random120-coco2014"),
            ("data-asset-crop", "object-fit-cover"),
        ]:
            if f"{attr}=" not in open_tag:
                open_tag = open_tag[:-1] + f' {attr}="{html.escape(value, quote=True)}">'
        manifest.append({
            "document_id": document_id,
            "category": category,
            "block_id": match.group("bid"),
            "block_label": match.group("label"),
            "asset_id": asset["asset_id"],
            "asset_source": "random120-coco2014",
            "asset_file": str(dst_asset),
            "asset_original_path": asset["source_path"],
            "asset_width": asset["width"],
            "asset_height": asset["height"],
            "asset_crop": "object-fit-cover",
            "asset_selection_key": f"{seed}|{language_code}|{category}|{document_id}|{match.group('bid')}|{slot_index}",
            "asset_selection_policy": "stable_hash_language_category_document_block",
            "html": str(html_file),
        })
        return f'{open_tag}{img_tag(asset, rel_src.as_posix())}{match.group(7)}'

    repl.slot_index = len(manifest)
    out = pattern.sub(repl, html_text)
    return out, repl.slot_index


def transform_htmls(
    clean_dir: Path,
    assets: list[dict[str, Any]],
    target_cjk_ratio: float,
    seed: int,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rng = random.Random(seed)
    profile = profile or {}
    target_script_re = re.compile(str(profile.get("script_regex", r"[A-Za-z]")))
    asset_dir = clean_dir / "assets" / "random120-coco2014"
    asset_dir.mkdir(parents=True, exist_ok=True)
    all_asset_manifest: list[dict[str, Any]] = []
    asset_index = 0
    language_stats = {
        "target_cjk_ratio": target_cjk_ratio,
        "mixed_blocks": 0,
        "inserted_cjk_chars": 0,
        "pure_documents": 0,
        "mixed_documents": 0,
        "decor_line_summary": {},
    }
    for cat in category_dirs(clean_dir):
        html_manifest = read_json(cat / "metadata" / "html_manifest.json")
        cat_decor = {"border_bottom_removed": 0, "border_top_softened": 0, "dotted_softened": 0}
        for item in html_manifest:
            html_path = cat / "html" / f"{item['document_id']}.html"
            text = html_path.read_text(encoding="utf-8")
            stats = {"mixed_blocks": 0, "inserted_cjk_chars": 0, "eligible_mix_blocks": 0, "selected_mix_blocks": 0}
            variant = int(item.get("variant") or 0)
            mix_mode = "mixed" if variant in MIXED_VARIANTS else "pure"
            document_target = DOCUMENT_CJK_TARGETS.get(variant, target_cjk_ratio)
            text = html_block_replacer(
                text,
                item.get("category") or "default",
                rng,
                stats,
                allow_mix=(mix_mode == "mixed"),
                document_target_cjk_ratio=document_target,
                target_script_re=target_script_re,
                profile=profile,
            )
            text, decor_stats = reduce_decor_lines(text)
            for key, value in decor_stats.items():
                cat_decor[key] += value
            text, asset_index = replace_image_placeholders(
                text,
                item["document_id"],
                item.get("category") or "unknown",
                assets,
                asset_dir,
                html_path,
                all_asset_manifest,
                profile=profile,
                seed=seed,
            )
            html_path.write_text(text, encoding="utf-8")
            item["version_name"] = "v4_clean_source"
            item["generator"] = f"{item.get('generator', 'html_layout')}_v4_split_mix_assets"
            item["image_assets_enabled"] = True
            item["language_mix_mode"] = mix_mode
            item["target_cjk_ratio"] = document_target if mix_mode == "mixed" else 0.0
            item["chinese_topic"] = item.get("category") or "default"
            item["source_version"] = "v2"
            item["eligible_mix_blocks"] = stats.get("eligible_mix_blocks", 0)
            item["selected_mix_blocks"] = stats.get("selected_mix_blocks", 0)
            language_stats["mixed_blocks"] += stats["mixed_blocks"]
            language_stats["inserted_cjk_chars"] += stats["inserted_cjk_chars"]
            language_stats[f"{mix_mode}_documents"] += 1
        write_json(cat / "metadata" / "html_manifest.json", html_manifest)
        language_stats["decor_line_summary"][cat.name] = cat_decor
    write_json(clean_dir / "metadata" / "image_asset_manifest.json", all_asset_manifest)
    language_stats["image_slots"] = len(all_asset_manifest)
    language_stats["unique_assets_used"] = len({row["asset_id"] for row in all_asset_manifest})
    return language_stats


def render_clean_version(clean_dir: Path, profile_path: Path) -> None:
    node = runtime_node()
    py = runtime_python()
    for cat in category_dirs(clean_dir):
        run([
            node,
            str(ENGINE_ROOT / "scripts" / "render_table_dataset.mjs"),
            "--input-dir",
            str(cat),
            "--language-profile",
            str(profile_path),
            "--auto-crop",
            "true",
            "--tight-crop",
            "true",
        ], env=node_env())
        run([
            py,
            str(ENGINE_ROOT / "scripts" / "qa_table_dataset.py"),
            "--dataset-dir",
            str(cat),
            "--language-profile",
            str(profile_path),
        ])
    run([py, str(ENGINE_ROOT / "scripts" / "rebuild_version_index.py"), "--version-dir", str(clean_dir)])
    run([py, str(ENGINE_ROOT / "scripts" / "qa_layout_density.py"), "--dataset-dir", str(clean_dir)])


def augment_to_v3(clean_dir: Path, out_v3: Path, force: bool) -> None:
    py = runtime_python()
    run([
        py,
        str(ENGINE_ROOT / "scripts" / "augment_synthetic_dataset.py"),
        "--source-version-dir",
        str(clean_dir),
        "--output-version-dir",
        str(out_v3),
        "--seed",
        "20260705",
        "--profile",
        "delivery_all_light",
        "--force" if force else "--force",
    ])


def copy_v3_metadata(clean_dir: Path, out_v3: Path, profile_path: Path) -> None:
    if (clean_dir / "metadata" / "image_asset_manifest.json").exists():
        shutil.copy2(clean_dir / "metadata" / "image_asset_manifest.json", out_v3 / "metadata" / "image_asset_manifest.json")
    if (clean_dir / "metadata" / "language_mix_summary.json").exists():
        shutil.copy2(clean_dir / "metadata" / "language_mix_summary.json", out_v3 / "metadata" / "language_mix_summary.json")
    shutil.copy2(profile_path, out_v3 / "metadata" / "language_profile.json")
    assets_src = clean_dir / "assets" / "random120-coco2014"
    assets_dst = out_v3 / "assets" / "random120-coco2014"
    if assets_src.exists():
        shutil.copytree(assets_src, assets_dst, dirs_exist_ok=True)


def text_ratios_from_labels(version_dir: Path) -> dict[str, Any]:
    total_cjk = 0
    total_latin = 0
    total_chars = 0
    by_category: dict[str, dict[str, Any]] = {}
    zero_cjk_docs = []
    for label_path in sorted(version_dir.glob("*/labels/*.json")):
        label = read_json(label_path)
        category = label.get("attributes", {}).get("category") or label_path.parts[-3]
        doc_cjk = doc_latin = doc_chars = 0
        for block in label.get("blocks", []):
            if block.get("is_text", True) is False:
                continue
            text = block.get("block_content") or ""
            if not text.strip():
                continue
            cjk = len(CJK_RE.findall(text))
            latin = len(LATIN_RE.findall(text))
            chars = len(re.sub(r"\s+", "", text))
            doc_cjk += cjk
            doc_latin += latin
            doc_chars += chars
        if doc_cjk == 0:
            zero_cjk_docs.append(label.get("attributes", {}).get("document_id") or label_path.stem)
        total_cjk += doc_cjk
        total_latin += doc_latin
        total_chars += doc_chars
        stat = by_category.setdefault(category, {"documents": 0, "cjk_chars": 0, "latin_chars": 0, "chars": 0})
        stat["documents"] += 1
        stat["cjk_chars"] += doc_cjk
        stat["latin_chars"] += doc_latin
        stat["chars"] += doc_chars
    for stat in by_category.values():
        stat["cjk_ratio"] = round(stat["cjk_chars"] / max(stat["chars"], 1), 4)
        stat["latin_ratio"] = round(stat["latin_chars"] / max(stat["chars"], 1), 4)
    return {
        "total_cjk_chars": total_cjk,
        "total_latin_chars": total_latin,
        "total_text_chars": total_chars,
        "cjk_ratio": round(total_cjk / max(total_chars, 1), 4),
        "latin_ratio": round(total_latin / max(total_chars, 1), 4),
        "zero_cjk_documents": zero_cjk_docs,
        "by_category": by_category,
        "pass": 0.25 <= (total_cjk / max(total_chars, 1)) <= 0.35 and not zero_cjk_docs,
    }


def image_asset_qa(version_dir: Path) -> dict[str, Any]:
    manifest = read_json(version_dir / "metadata" / "image_asset_manifest.json")
    missing = []
    for row in manifest:
        if not Path(row["asset_file"].replace(str(version_dir.parent / "v4_clean_source"), str(version_dir))).exists():
            # v4 stores a copied asset dir; asset_file itself points to the clean source for traceability.
            if not (version_dir / "assets" / "random120-coco2014" / Path(row["asset_file"]).name).exists():
                missing.append(row)
    html_missing = []
    # Only count real DOM blocks. Vertical Mongolian CSS contains selectors such as
    # [data-label="image"], which must not be treated as an unfilled placeholder.
    placeholder_re = re.compile(
        r"<[^>]+data-block-id=\"[^\"]+\"[^>]+data-label=\"(?:image|photo|figure|photo_lead|image_figure)\"[^>]*>",
        re.IGNORECASE,
    )
    for html_path in version_dir.glob("*/html/*.html"):
        text = html_path.read_text(encoding="utf-8")
        for match in placeholder_re.finditer(text):
            tag = match.group(0)
            if 'data-asset-id="' not in tag or 'data-is-text="false"' not in tag:
                html_missing.append(str(html_path))
                break
    return {
        "image_slots": len(manifest),
        "unique_assets_used": len({row["asset_id"] for row in manifest}),
        "missing_image_assets": len(missing),
        "unfilled_image_slot_files": html_missing,
        "unfilled_image_slots": len(html_missing),
        "pass": len(manifest) > 0 and not missing and not html_missing,
    }


def parse_variant_from_document_id(document_id: str) -> int:
    m = re.search(r"_json_(\d+)$", document_id or "")
    return int(m.group(1)) if m else 0


def block_center(block: dict[str, Any]) -> tuple[float, float]:
    c = block.get("coordinates") or {}
    return ((float(c.get("x_min", 0)) + float(c.get("x_max", 0))) / 2, (float(c.get("y_min", 0)) + float(c.get("y_max", 0))) / 2)


def reading_group_for(label: str, y: float, page_h: float, is_text: bool) -> str:
    if not is_text:
        return "image" if label in {"image", "photo", "figure", "photo_lead", "image_figure"} else "non_text"
    if label in {"document_title", "document_subtitle", "metadata"} and y < page_h * 0.22:
        return "header"
    if label in {"footer", "page_number"} or y > page_h * 0.90:
        return "footer"
    if label in {"table_header", "table_cell_text", "table_cell_number"}:
        return "table"
    if label in {"field_label", "field_value", "option", "answer_area"}:
        return "form"
    return "body"


def reading_role_for(label: str, is_text: bool) -> str:
    if not is_text:
        return "image" if label in {"image", "photo", "figure", "photo_lead", "image_figure"} else "non_text"
    mapping = {
        "document_title": "title",
        "document_subtitle": "subtitle",
        "section_title": "section_title",
        "paragraph": "paragraph",
        "quote": "quote",
        "caption": "caption",
        "field_label": "field_label",
        "field_value": "field_value",
        "answer_area": "answer_area",
        "option": "option",
        "question": "question",
        "table_header": "table_header",
        "table_cell_text": "table_cell",
        "metadata": "metadata",
        "note": "note",
        "list_item": "list_item",
        "footer": "footer",
        "page_number": "page_number",
    }
    return mapping.get(label, label or "text")


def reading_policy(profile: dict[str, Any] | None) -> str:
    profile = profile or {}
    writing_mode = str(profile.get("css_writing_mode", "horizontal-tb")).lower()
    direction = str(profile.get("css_direction", "ltr")).lower()
    cleanup = str(profile.get("cleanup_profile", "")).lower()
    if writing_mode.startswith("vertical") or cleanup == "traditional_mongolian":
        return "vertical_lr_columns_top_to_bottom"
    if direction == "rtl":
        return "rtl_visual_top_to_bottom_right_to_left"
    return "ltr_visual_top_to_bottom_left_to_right"


def assign_reading_order_to_label(label: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    blocks = label.get("blocks", [])
    attrs = label.get("attributes", {})
    diagnostics = attrs.get("diagnostics", {})
    crop = diagnostics.get("crop", {})
    page_w = float(crop.get("width") or diagnostics.get("page_width") or 1)
    page_h = float(crop.get("height") or diagnostics.get("page_height") or 1)
    policy = reading_policy(profile)

    decorated = []
    for idx, block in enumerate(blocks):
        label_name = block.get("block_label") or ""
        cx, cy = block_center(block)
        is_text = block.get("is_text", True) is not False
        group = reading_group_for(label_name, cy, page_h, is_text)
        role = reading_role_for(label_name, is_text)
        if group == "header":
            group_rank = 0
        elif group == "body":
            group_rank = 1
        elif group in {"table", "form"}:
            group_rank = 2
        elif group == "image":
            group_rank = 3
        elif group == "footer":
            group_rank = 4
        else:
            group_rank = 5
        row_bucket = round(cy / max(page_h, 1) * 80)
        col_bucket = round(cx / max(page_w, 1) * 80)
        if policy == "rtl_visual_top_to_bottom_right_to_left":
            decorated.append((group_rank, row_bucket, -col_bucket, cy, -cx, idx, block, group, role))
        elif policy == "vertical_lr_columns_top_to_bottom":
            decorated.append((group_rank, col_bucket, row_bucket, cx, cy, idx, block, group, role))
        else:
            decorated.append((group_rank, row_bucket, col_bucket, cy, cx, idx, block, group, role))
    decorated.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4], x[5]))
    for order, item in enumerate(decorated, 1):
        block = item[6]
        block["reading_order"] = order
        block["reading_group"] = item[7]
        block["reading_role"] = item[8]
        block["reading_order_confidence"] = "high" if item[7] in {"header", "footer", "table", "form"} else "medium"
    attrs["reading_order_policy"] = f"{policy}_v1"
    return label


def apply_reading_order(version_dir: Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    docs = 0
    blocks = 0
    failures = []
    for label_path in sorted(version_dir.glob("*/labels/*.json")):
        label = assign_reading_order_to_label(read_json(label_path), profile)
        orders = [b.get("reading_order") for b in label.get("blocks", [])]
        expected = list(range(1, len(orders) + 1))
        if sorted(orders) != expected:
            failures.append(str(label_path))
        write_json(label_path, label)
        docs += 1
        blocks += len(orders)
    summary = {
        "documents": docs,
        "blocks": blocks,
        "policy": reading_policy(profile),
        "failed_documents": failures,
        "pass": not failures,
    }
    write_json(version_dir / "reports" / "reading_order_summary.json", summary)
    (version_dir / "reports" / "QA_READING_ORDER_REPORT.md").write_text(
        f"""# Reading Order QA

- 文档数：{docs}
- 标签块数：{blocks}
- 阅读顺序策略：{summary['policy']}
- 失败文档数：{len(failures)}
- 结论：{'通过' if summary['pass'] else '需处理'}
""",
        encoding="utf-8",
    )
    return summary


def language_mix_v4_qa(version_dir: Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or {}
    target_script_re = re.compile(str(profile.get("script_regex", r"[A-Za-z]")))
    target_script_name = str(profile.get("language_code", "target"))
    by_category: dict[str, dict[str, Any]] = {}
    failures = []
    warnings = []
    repeated_snippets: dict[str, int] = {}
    for label_path in sorted(version_dir.glob("*/labels/*.json")):
        label = read_json(label_path)
        attrs = label.get("attributes", {})
        category = attrs.get("category") or label_path.parts[-3]
        doc_id = attrs.get("document_id") or label_path.stem
        variant = int(attrs.get("variant") or parse_variant_from_document_id(doc_id))
        mode = attrs.get("language_mix_mode") or ("mixed" if variant in MIXED_VARIANTS else "pure")
        cjk = target = chars = 0
        natural_blocks = 0
        snippets_seen = []
        for block in label.get("blocks", []):
            if block.get("is_text", True) is False:
                continue
            block_label = str(block.get("block_label") or "")
            text = block.get("block_content") or ""
            if block_label in {"metadata", "page_number", "answer_area"}:
                continue
            if re.fullmatch(r"[_\\/\-–—:：|·•\s\d.,，。；;()（）\[\]【】]+", text or ""):
                continue
            natural_blocks += 1
            cjk += cjk_len(text)
            target += len(target_script_re.findall(text))
            chars += compact_len(text)
            snippets_seen.extend(CHINESE_SNIPPITS for CHINESE_SNIPPITS in CJK_RE.findall(text))
        ratio = cjk / max(chars, 1)
        stat = by_category.setdefault(category, {"pure": 0, "mixed": 0, "documents": []})
        stat[mode] += 1
        stat["documents"].append({
            "document_id": doc_id,
            "variant": variant,
            "mode": mode,
            "cjk_ratio": round(ratio, 4),
            "cjk_chars": cjk,
            "target_script_chars": target,
            "target_script_name": target_script_name,
            "chars": chars,
        })
        if mode == "pure" and cjk != 0:
            failures.append({"document_id": doc_id, "issue": "pure_has_cjk", "cjk_ratio": round(ratio, 4)})
        if mode == "mixed" and not (0.10 <= ratio <= 0.30):
            payload = {"document_id": doc_id, "issue": "mixed_cjk_ratio_out_of_range", "cjk_ratio": round(ratio, 4)}
            if natural_blocks <= 12 and chars <= 260:
                warnings.append(payload | {"note": "short_mixed_layout"})
            else:
                failures.append(payload)
    for category, stat in by_category.items():
        if stat["pure"] != 3 or stat["mixed"] != 3:
            failures.append({"category": category, "issue": "category_mix_count_invalid", "pure": stat["pure"], "mixed": stat["mixed"]})
    summary = {"by_category": by_category, "failures": failures, "warnings": warnings, "pass": not failures}
    write_json(version_dir / "reports" / "language_mix_summary.json", summary)
    write_json(version_dir / "metadata" / "language_mix_summary.json", summary)
    rows = []
    for category, stat in sorted(by_category.items()):
        ratios = ", ".join(f"{d['variant']}:{d['mode']}:{d['cjk_ratio']}" for d in stat["documents"])
        rows.append(f"| {category} | {stat['pure']} | {stat['mixed']} | {ratios} |")
    (version_dir / "reports" / "QA_LANGUAGE_MIX_REPORT.md").write_text(
        "# Language Mix QA\n\n"
        f"- 失败项：{len(failures)}\n"
        f"- 警告项：{len(warnings)}\n"
        f"- 结论：{'通过' if summary['pass'] else '需处理'}\n\n"
        "| 类别 | pure | mixed | 样本比例 |\n|---|---:|---:|---|\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )
    return summary


def language_validity_qa(version_dir: Path) -> dict[str, Any]:
    failures = []
    totals = {"documents": 0, "blocks": 0, "unsupported_char_blocks": 0, "other_script_blocks": 0}
    for label_path in sorted(version_dir.glob("*/labels/*.json")):
        label = read_json(label_path)
        attrs = label.get("attributes", {})
        doc_id = attrs.get("document_id") or label_path.stem
        mode = attrs.get("language_mix_mode") or "unknown"
        totals["documents"] += 1
        for block in label.get("blocks", []):
            if block.get("is_text", True) is False:
                continue
            text = block.get("block_content") or ""
            totals["blocks"] += 1
            bad_chars = PRIVATE_USE_RE.findall(text) + REPLACEMENT_OR_BOX_RE.findall(text) + ZERO_WIDTH_UNSUPPORTED_RE.findall(text)
            if bad_chars:
                totals["unsupported_char_blocks"] += 1
                failures.append({"document_id": doc_id, "block_id": block.get("block_id"), "issue": "unsupported_chars", "chars": sorted(set(bad_chars))})
            other_hits = {name: len(pattern.findall(text)) for name, pattern in OTHER_SCRIPT_PATTERNS.items()}
            other_hits = {k: v for k, v in other_hits.items() if v}
            if other_hits:
                totals["other_script_blocks"] += 1
                failures.append({"document_id": doc_id, "block_id": block.get("block_id"), "issue": "other_script_residue", "scripts": other_hits})
            if mode == "pure" and CJK_RE.search(text):
                failures.append({"document_id": doc_id, "block_id": block.get("block_id"), "issue": "pure_cjk_residue"})
    summary = {**totals, "failures": failures, "pass": not failures}
    write_json(version_dir / "reports" / "language_validity_summary.json", summary)
    (version_dir / "reports" / "QA_LANGUAGE_VALIDITY_REPORT.md").write_text(
        f"""# Language Validity QA

- 文档数：{totals['documents']}
- 文本块数：{totals['blocks']}
- 异常字符块数：{totals['unsupported_char_blocks']}
- 其他文字体系残留块数：{totals['other_script_blocks']}
- 失败项：{len(failures)}
- 结论：{'通过' if summary['pass'] else '需处理'}
""",
        encoding="utf-8",
    )
    return summary


def write_image_asset_report(version_dir: Path, image_summary: dict[str, Any]) -> None:
    write_json(version_dir / "reports" / "image_asset_summary.json", image_summary)
    (version_dir / "reports" / "QA_IMAGE_ASSETS_REPORT.md").write_text(
        f"""# Image Asset QA

- 图片槽位：{image_summary['image_slots']}
- 使用不同图片：{image_summary['unique_assets_used']}
- 缺失图片文件：{image_summary['missing_image_assets']}
- 未填充图片槽位：{image_summary['unfilled_image_slots']}
- 结论：{'通过' if image_summary['pass'] else '需处理'}
""",
        encoding="utf-8",
    )


def run_final_qa(out_v4: Path, profile_path: Path) -> None:
    py = runtime_python()
    for cat in category_dirs(out_v4):
        run([
            py,
            str(ENGINE_ROOT / "scripts" / "qa_table_dataset.py"),
            "--dataset-dir",
            str(cat),
            "--language-profile",
            str(profile_path),
        ])
    run([py, str(ENGINE_ROOT / "scripts" / "rebuild_version_index.py"), "--version-dir", str(out_v4)])
    run([py, str(ENGINE_ROOT / "scripts" / "qa_layout_density.py"), "--dataset-dir", str(out_v4)])
    run([
        py,
        str(ENGINE_ROOT / "scripts" / "qa_version_acceptance.py"),
        "--version-dir",
        str(out_v4),
        "--max-density-warnings",
        "0",
    ])


def write_readme(out_v4: Path, source_v2: Path, asset_dir: Path, mix_summary: dict[str, Any], image_summary: dict[str, Any], reading_summary: dict[str, Any], validity_summary: dict[str, Any]) -> None:
    (out_v4 / "README.md").write_text(
        f"""# 壮语 v4

本版本基于 `{source_v2}` 生成，主要变化：

- 图片占位符替换为 `{asset_dir}` 中的真实 COCO 图片。
- 每类 3 张纯壮语、3 张混合中文；混合样本中文比例为 10%-30%。
- 标签新增 `reading_order / reading_group / reading_role / reading_order_confidence`。
- 已应用 `delivery_all_light` 数据增强。

## QA 摘要

- 中文混合 QA：{'通过' if mix_summary['pass'] else '需处理'}
- 阅读顺序 QA：{'通过' if reading_summary['pass'] else '需处理'}
- 语言有效性 QA：{'通过' if validity_summary['pass'] else '需处理'}
- 图片槽位：{image_summary['image_slots']}
- 使用不同图片：{image_summary['unique_assets_used']}

核心报告：

- `reports/QA_REPORT.md`
- `reports/QA_DENSITY_REPORT.md`
- `reports/ACCEPTANCE_REPORT.md`
- `reports/QA_LANGUAGE_MIX_REPORT.md`
- `reports/QA_LANGUAGE_VALIDITY_REPORT.md`
- `reports/QA_READING_ORDER_REPORT.md`
- `reports/QA_IMAGE_ASSETS_REPORT.md`
- `reports/contact_sheet.jpg`
- `reports/contact_sheet_with_boxes.jpg`
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-v2", default=str(PROJECT_ROOT / "02_语种工程资源" / "壮语" / "03_合成数据生成_20260701" / "v2"))
    parser.add_argument("--output-v4", default=str(PROJECT_ROOT / "01_最终VL2数据" / "壮语" / "v4"))
    parser.add_argument("--image-assets-dir")
    parser.add_argument("--source-profile", default=str(PROJECT_ROOT / "02_语种工程资源" / "壮语" / "03_合成数据生成_20260701" / "configs" / "zhuang_language_profile.json"))
    parser.add_argument("--target-cjk-ratio", type=float, default=0.18)
    parser.add_argument("--seed", type=int, default=2026070401)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--keep-clean-source", action="store_true")
    args = parser.parse_args()

    source_v2 = Path(args.source_v2)
    out_v4 = Path(args.output_v4)
    clean_dir = out_v4.parent / "v4_clean_source"
    asset_dir = find_asset_dir(PROJECT_ROOT, Path(args.image_assets_dir) if args.image_assets_dir else None)
    assets = load_image_assets(asset_dir)
    if len(assets) < 15:
        raise RuntimeError(f"not enough image assets: {len(assets)}")

    if out_v4.exists():
        if not args.force:
            raise FileExistsError(f"{out_v4} exists; use --force")
        shutil.rmtree(out_v4)

    copy_clean_static(source_v2, clean_dir, args.force)
    profile_path = clean_dir / "metadata" / "zhuang_v4_language_profile.json"
    build_profile(Path(args.source_profile), profile_path, args.target_cjk_ratio)
    transform_stats = transform_htmls(clean_dir, assets, args.target_cjk_ratio, args.seed)
    write_json(clean_dir / "metadata" / "language_mix_generation_summary.json", transform_stats)
    write_json(clean_dir / "metadata" / "decor_line_summary.json", transform_stats.get("decor_line_summary", {}))
    render_clean_version(clean_dir, profile_path)

    write_image_asset_report(clean_dir, image_asset_qa(clean_dir))

    augment_to_v3(clean_dir, out_v4, True)
    copy_v3_metadata(clean_dir, out_v4, profile_path)
    write_json(out_v4 / "metadata" / "decor_line_summary.json", transform_stats.get("decor_line_summary", {}))
    run_final_qa(out_v4, profile_path)
    reading_summary = apply_reading_order(out_v4)
    mix_summary = language_mix_v4_qa(out_v4)
    validity_summary = language_validity_qa(out_v4)
    image_summary = image_asset_qa(out_v4)
    write_image_asset_report(out_v4, image_summary)
    # Rebuild final reports after reading-order label updates.
    run_final_qa(out_v4, profile_path)
    reading_summary = apply_reading_order(out_v4)
    mix_summary = language_mix_v4_qa(out_v4)
    validity_summary = language_validity_qa(out_v4)
    write_readme(out_v4, source_v2, asset_dir, mix_summary, image_summary, reading_summary, validity_summary)

    if not mix_summary["pass"]:
        raise RuntimeError(f"language mix QA failed: {mix_summary}")
    if not reading_summary["pass"]:
        raise RuntimeError(f"reading order QA failed: {reading_summary}")
    if not validity_summary["pass"]:
        raise RuntimeError(f"language validity QA failed: {validity_summary}")
    if not image_summary["pass"]:
        raise RuntimeError(f"image asset QA failed: {image_summary}")
    if not args.keep_clean_source and clean_dir.exists():
        shutil.rmtree(clean_dir)

    print(json.dumps({
        "output_v4": str(out_v4),
        "assets": str(asset_dir),
        "image_slots": image_summary["image_slots"],
        "mix_pass": mix_summary["pass"],
        "reading_order_pass": reading_summary["pass"],
        "language_validity_pass": validity_summary["pass"],
        "pass": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
