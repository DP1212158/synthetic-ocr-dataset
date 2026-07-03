#!/usr/bin/env python3
"""Tibetan-specific text cleaning and sentence-safe sampling utilities."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any


TIBETAN_RE = re.compile(r"[\u0f00-\u0fff]")
TIBETAN_BASE_RE = re.compile(r"[\u0f40-\u0f6c\u0f88-\u0f8c]")
LATIN_RE = re.compile(r"[A-Za-z\u00c0-\u024f]")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
MONGOLIAN_RE = re.compile(r"[\u1800-\u18af]")
HANGUL_RE = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
HTML_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
PUA_RE = re.compile(r"[\ue000-\uf8ff]")
BOX_RE = re.compile(r"[\ufffd\u25a0\u25a1\u25af\u25a2\u25a3\u25a4\u25a5\u25a6\u25a7\u25a8\u25a9]")
DECORATIVE_TIBETAN_RE = re.compile(r"[\u0f04-\u0f0a\u0f3a-\u0f3d]")
NON_STANDARD_SHAD_RE = re.compile(r"[\u0f0f\u0f10\u0f11\u0f14]")
BRACKET_RE = re.compile(r"[\(\[（【<《][^\)\]）】>》]{0,120}[\)\]）】>》]")
COMBINING_ONLY_RE = re.compile(r"(?:^|[\s་།༎])[\u0f71-\u0f84\u0f86-\u0f87\u0f90-\u0fbc]+(?=$|[\s་།༎])")

TIBETAN_DIGITS = str.maketrans("0123456789", "༠༡༢༣༤༥༦༧༨༩")
SHAD_CHARS = "།༎"
TSHEG = "་"

ACTIVE_PROFILE: dict[str, Any] = {}

SAFE_TITLE_FRAGMENTS = [
    "བོད་ཡིག",
    "བོད་སྐད",
    "རིག་གནས",
    "སློབ་གསོ",
    "གསར་འགྱུར",
    "བརྡ་ཁྱབ",
    "དཔྱད་གཞི",
    "ཡིག་ཆ",
    "མདོར་བསྡུས",
    "གནད་འགག",
]

FALLBACK_BY_LABEL = {
    "document_title": "བོད་ཡིག",
    "document_subtitle": "མདོར་བསྡུས་གསལ་བཤད།",
    "section_title": "གནད་འགག",
    "metadata": "༢༠༢༦",
    "field_label": "མིང",
    "field_value": "བོད་ཡིག",
    "table_header": "དོན་ཚན",
    "table_cell_text": "བོད་ཡིག་ནང་དོན།",
    "question": "དྲི་བ།",
    "option": "ཀ",
    "seal": "ཐམ་ག",
    "footer": "མཇུག་བྱང་།",
    "page_number": "༡",
    "list_item": "མདོར་བསྡུས།",
    "note": "མཆན།",
    "caption": "འགྲེལ་བཤད།",
    "quote": "དྲངས་ཚིག།",
}


def _ratio(count: int, text: str) -> float:
    return count / max(len(text), 1)


def to_tibetan_digits(text: str) -> str:
    return str(text or "").translate(TIBETAN_DIGITS)


def _remove_bad_brackets(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        segment = match.group(0)
        if LATIN_RE.search(segment) or CJK_RE.search(segment) or CYRILLIC_RE.search(segment) or ARABIC_RE.search(segment):
            return " "
        return segment

    return BRACKET_RE.sub(repl, text)


def normalize_tibetan_text(text: str) -> str:
    text = str(text or "")
    text = HTML_RE.sub(" ", text)
    text = URL_RE.sub(" ", text)
    text = text.replace("\u00a0", " ")
    text = text.replace("༌", "་")
    text = text.replace("༔", "།")
    text = NON_STANDARD_SHAD_RE.sub("།", text)
    text = _remove_bad_brackets(text)
    text = PUA_RE.sub(" ", text)
    text = BOX_RE.sub(" ", text)
    text = LATIN_RE.sub(" ", text)
    text = CJK_RE.sub(" ", text)
    text = CYRILLIC_RE.sub(" ", text)
    text = ARABIC_RE.sub(" ", text)
    text = MONGOLIAN_RE.sub(" ", text)
    text = HANGUL_RE.sub(" ", text)
    text = DECORATIVE_TIBETAN_RE.sub(" ", text)
    text = text.replace("...", " ")
    text = to_tibetan_digits(text)
    text = COMBINING_ONLY_RE.sub(" ", text)
    text = re.sub(r"[\"“”‘’'`~+=_*^$#@%&|\\]+", " ", text)
    text = re.sub(r"[;；:：,，.!?！？]+", " ", text)
    text = re.sub(r"\s*([།༎])\s*", r"\1 ", text)
    text = re.sub(r"་{2,}", "་", text)
    text = re.sub(r"།{3,}", "༎", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def cleanse_text(text: str) -> str:
    return normalize_tibetan_text(text)


def load_language_profile(path: Path | None) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8")) if path else {}
    profile.setdefault("language_code", "bo")
    profile.setdefault("language_name", "藏语")
    profile.setdefault("script_note", "藏文横排文本，保留 tsheg 与标准 shad")
    profile.setdefault("html_lang", "bo")
    profile.setdefault("script_regex", r"[\u0f00-\u0fff]")
    profile.setdefault("min_script_ratio", 0.35)
    profile.setdefault("font_family", '"Local Noto Serif Tibetan", "Local Jomolhari", "Noto Serif Tibetan", Kailasa, serif')
    profile.setdefault("safe_title_fragments", SAFE_TITLE_FRAGMENTS)
    profile.setdefault("cleanup_profile", "tibetan_v13")
    ACTIVE_PROFILE.clear()
    ACTIVE_PROFILE.update(profile)
    return profile


def text_quality(text: str, script_re: re.Pattern[str] | None = None) -> dict[str, float]:
    cleaned = cleanse_text(text)
    script_re = script_re or re.compile(str(ACTIVE_PROFILE.get("script_regex", r"[\u0f00-\u0fff]")))
    raw = str(text or "")
    return {
        "script_ratio": _ratio(len(script_re.findall(cleaned)), cleaned),
        "digit_ratio": _ratio(sum(ch.isdigit() for ch in cleaned), cleaned),
        "latin_ratio": _ratio(len(LATIN_RE.findall(raw)), raw),
        "cjk_ratio": _ratio(len(CJK_RE.findall(raw)), raw),
        "cyrillic_ratio": _ratio(len(CYRILLIC_RE.findall(raw)), raw),
        "arabic_ratio": _ratio(len(ARABIC_RE.findall(raw)), raw),
        "mongolian_ratio": _ratio(len(MONGOLIAN_RE.findall(raw)), raw),
        "hangul_ratio": _ratio(len(HANGUL_RE.findall(raw)), raw),
        "char_count": float(len(cleaned)),
        "shad_count": float(sum(cleaned.count(ch) for ch in SHAD_CHARS)),
        "tsheg_count": float(cleaned.count(TSHEG)),
    }


def has_foreign_residue(text: str) -> bool:
    return any(
        regex.search(text)
        for regex in [LATIN_RE, CJK_RE, CYRILLIC_RE, ARABIC_RE, MONGOLIAN_RE, HANGUL_RE, PUA_RE, BOX_RE]
    )


def is_bad_title(title: str) -> bool:
    title = cleanse_text(title)
    if len(title) < 3:
        return True
    if not TIBETAN_BASE_RE.search(title):
        return True
    if len(title) > 42:
        return True
    return has_foreign_residue(title)


def split_sentences(text: str) -> list[str]:
    text = cleanse_text(text)
    if not text:
        return []
    matches = re.findall(r"[^།༎]+[།༎]+", text)
    out = [cleanse_text(m) for m in matches if TIBETAN_BASE_RE.search(m)]
    if out:
        return out
    parts = [p for p in re.split(r"(?<=་)", text) if p.strip()]
    return [cleanse_text("".join(parts[i : i + 18])) for i in range(0, len(parts), 18) if parts[i : i + 18]]


def _ensure_long_text_shad(text: str, min_len: int) -> str:
    text = cleanse_text(text)
    if len(text) >= 90 and TIBETAN_BASE_RE.search(text) and not any(ch in text for ch in SHAD_CHARS):
        text = text.rstrip("་ ") + "།"
    return text


def clip(text: str, min_len: int, max_len: int) -> str:
    text = cleanse_text(text)
    if len(text) <= max_len:
        return _ensure_long_text_shad(text, min_len)
    cut = text[:max_len]
    for sep in ["༎", "།", "་", " "]:
        idx = cut.rfind(sep)
        if idx >= min_len:
            end = idx + len(sep)
            return _ensure_long_text_shad(cut[:end].strip(), min_len)
    return _ensure_long_text_shad(cut.rstrip(), min_len)


def select_span(text: str, rng: random.Random, min_len: int, max_len: int) -> str:
    text = cleanse_text(text)
    if len(text) <= max_len and len(text) >= min_len:
        return _ensure_long_text_shad(text, min_len)
    sentences = [s for s in split_sentences(text) if len(s) >= 8]
    if sentences:
        candidates: list[str] = []
        for _ in range(20):
            start = rng.randint(0, max(0, len(sentences) - 1))
            acc = ""
            for sent in sentences[start:]:
                if len(acc) + len(sent) + 1 > max_len:
                    break
                acc = cleanse_text(f"{acc} {sent}")
                if len(acc) >= min_len:
                    candidates.append(acc)
                    break
        if candidates:
            return _ensure_long_text_shad(rng.choice(candidates), min_len)
    return clip(text, min_len, max_len)


def _quality_score(text: str, title: str, script_re: re.Pattern[str]) -> float:
    q = text_quality(text, script_re)
    score = q["script_ratio"] * 2.0
    score += min(q["char_count"] / 800.0, 1.0)
    score += min(q["shad_count"] / 3.0, 1.0) * 0.7
    score += min(q["tsheg_count"] / 40.0, 1.0) * 0.5
    score -= q["latin_ratio"] * 4.0
    score -= q["cjk_ratio"] * 4.0
    score -= q["cyrillic_ratio"] * 4.0
    if not is_bad_title(title):
        score += 0.5
    return round(score, 4)


def read_text_records(path: Path, language_profile: dict[str, Any], min_records: int) -> list[dict[str, str]]:
    script_re = re.compile(str(language_profile["script_regex"]))
    min_ratio = float(language_profile.get("min_script_ratio", 0.35))
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        title = cleanse_text(str(row.get("title", "")))
        text = cleanse_text(str(row.get("text", row.get("block_content", ""))))
        if len(text) < 24:
            continue
        q = text_quality(text, script_re)
        if q["script_ratio"] < min_ratio or has_foreign_residue(text):
            continue
        records.append(
            {
                "title": title,
                "text": text,
                "url": str(row.get("url", "")),
                "source_record_id": str(row.get("record_id", row.get("source_record_id", ""))),
                "source": str(row.get("source", row.get("source_name", ""))),
                "quality_score": str(_quality_score(text, title, script_re)),
            }
        )
    records = sorted(records, key=lambda rec: float(rec["quality_score"]), reverse=True)
    if len(records) < min_records:
        raise RuntimeError(f"not enough Tibetan records in {path}: {len(records)}")
    return records


def record_text(records: list[dict[str, str]], rng: random.Random, min_len: int, max_len: int) -> str:
    pool = [rec for rec in records if len(rec["text"]) >= min_len] or records
    for _ in range(16):
        text = select_span(rng.choice(pool)["text"], rng, min_len, max_len)
        if len(text) >= min(min_len, 18) and TIBETAN_BASE_RE.search(text):
            return text
    return select_span(rng.choice(pool)["text"], rng, min_len, max_len)


def safe_title(rng: random.Random, min_len: int = 3, max_len: int = 34) -> str:
    pool = [cleanse_text(x) for x in ACTIVE_PROFILE.get("safe_title_fragments", SAFE_TITLE_FRAGMENTS)]
    pool = [x for x in pool if min_len <= len(x) <= max_len and not is_bad_title(x)]
    return rng.choice(pool or SAFE_TITLE_FRAGMENTS)


def safe_fragment(min_len: int = 1, max_len: int = 28) -> str:
    for frag in ACTIVE_PROFILE.get("safe_title_fragments", SAFE_TITLE_FRAGMENTS):
        cleaned = clip(frag, min_len, max_len)
        if cleaned:
            return cleaned
    return "བོད་ཡིག"


def fallback_text(label: str) -> str:
    if label in {"answer_area", "image"}:
        return " "
    return FALLBACK_BY_LABEL.get(label, safe_fragment(1, 28))


def record_title(records: list[dict[str, str]], rng: random.Random, min_len: int = 8, max_len: int = 34) -> str:
    titles = [
        cleanse_text(rec.get("title", ""))
        for rec in records
        if not is_bad_title(rec.get("title", "")) and min_len <= len(cleanse_text(rec.get("title", ""))) <= max_len
    ]
    if titles and rng.random() < 0.72:
        return rng.choice(titles)
    for _ in range(14):
        candidate = select_span(rng.choice(records)["text"], rng, min_len, max_len)
        if candidate and not is_bad_title(candidate):
            return candidate
    return safe_title(rng, max(3, min_len // 2), max_len)
