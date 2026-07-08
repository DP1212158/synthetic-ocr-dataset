#!/usr/bin/env python3
"""Shared text cleaning and sampling utilities for synthetic layout generation."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any


CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
TIBETAN_DECORATIVE_MARK_RE = re.compile(r"[\u0f04-\u0f0a\u0f0c\u0f0e-\u0f14\u0f3a-\u0f3d]")
TIBETAN_SHAD_RE = re.compile(r"\s*།+\s*")
TIBETAN_RE = re.compile(r"[\u0f00-\u0fff]")
ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
MONGOLIAN_RE = re.compile(r"[\u1800-\u18af]")
HANGUL_RE = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
LATIN_RE = re.compile(r"[A-Za-z]")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’.·-]*")
HTML_RE = re.compile(r"<[^>]+>")
LATEX_RE = re.compile(r"\\[A-Za-z]+|\$+|[{}_^]")
PRIVATE_USE_RE = re.compile(r"[\ue000-\uf8ff]")
REPLACEMENT_OR_BOX_RE = re.compile(r"[\ufffd\u25a0\u25a1\u25af]")
MONGOLIAN_PRESENTATION_PUNCT_RE = re.compile(r"[︽︾︕︖︵︶︔﹇﹈]")
MONGOLIAN_UNSAFE_SYMBOL_RE = re.compile(r"[\u200d=+~※%!—–]")
ZERO_WIDTH_CONTROL_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]")

NUMERIC_TITLE_RE = re.compile(r"^[\d\s\-:/.()]+$")
BAD_TITLE_LITERAL_RE = re.compile(r"^(fallback records?|records?|untitled|unknown|none|null|na|n/a)$", re.IGNORECASE)
DATE_WORD_RE = re.compile(r"\b(nyied|hauh|nienz|bi'?nyinh|ngoenz)\b", re.IGNORECASE)

ACTIVE_PROFILE: dict[str, Any] = {}

SCRIPT_RESIDUE = {
    "latin": LATIN_RE,
    "cjk": CJK_RE,
    "cyrillic": CYRILLIC_RE,
    "tibetan": TIBETAN_RE,
    "arabic": ARABIC_RE,
    "mongolian": MONGOLIAN_RE,
    "hangul": HANGUL_RE,
}

DEFAULT_SAFE_TITLES = [
    "Vahcuengh Sawcuengh",
    "Bouxcuengh Gijbon",
    "Gij Doengh Vwnzva",
    "Gvangjsih Bouxcuengh",
    "Sawbon Canghva",
    "Doxgoj Doxgangj",
    "Gijyez Cwngzva",
    "Vwnzyen Sawcuengh",
    "Cingzdan Gijliux",
    "Saunghawj Neiyungz",
]

DEFAULT_BLOCKED_TEMPLATE_TERMS = {
    "bai": [
        "Vahcuengh",
        "Sawcuengh",
        "Ngoenzneix",
        "Yienghneix",
        "Bouxcuengh",
        "Gvangjsih",
        "Vwnzva",
        "Gijyez",
        "Gijmingz",
        "Saedsaed",
        "Cangh",
        "Doengh",
        "Gvangj Gau",
        "Mboq Doengh",
        "Doengh Vaiq",
        "Gij Yawj",
        "Gij Yienghguh",
        "Swhngim Bouxcuengh",
        "Gienzronz",
        "Vwnzyen Cawxgya",
        "Gijbon Lijsi",
        "Guj Sawbon",
        "Guj Saw Dak",
        "Gaejgangj",
        "Gij Cawxgya",
        "Gizci",
        "Seizgan",
        "Dihdeiz",
        "Duzgaiq",
        "Fujgan",
        "Sawmaj",
        "Mingz",
        "Hauh",
        "Dihci",
        "Lienzyau",
        "Cingzkuang",
        "Gijman",
        "Cingzdan",
        "Gijbiz",
        "Daezmoq",
        "Dakbieq",
        "Yieb",
        "Deihce",
        "Cawxgya",
    ]
}

SENTENCE_END_RE = re.compile(r"([.!?。！？]+|།+|።+)\s+")
CLAUSE_END_RE = re.compile(r"([,;:，；：、]+|།+)\s+")
TEXT_STREAMS: dict[int, "ContinuousTextSampler"] = {}


def _ratio(count: int, text: str) -> float:
    return count / max(len(text), 1)


def _blocked_template_terms() -> list[str]:
    profile = ACTIVE_PROFILE or {}
    configured = profile.get("blocked_template_terms")
    if isinstance(configured, list):
        return [str(item) for item in configured if str(item).strip()]
    language_code = str(profile.get("language_code", "")).lower()
    return DEFAULT_BLOCKED_TEMPLATE_TERMS.get(language_code, [])


def _remove_blocked_template_terms(text: str) -> str:
    terms = _blocked_template_terms()
    if not terms or not text:
        return text
    cleaned = text
    for term in terms:
        cleaned = re.sub(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def cleanse_text(text: str) -> str:
    """Clean text according to the active language profile."""
    text = str(text or "")
    text = ZERO_WIDTH_CONTROL_RE.sub("", text)
    text = HTML_RE.sub(" ", text)
    text = LATEX_RE.sub(" ", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[\[\]【】（）()<>]+", " ", text)
    text = text.replace("...", " ")
    text = PRIVATE_USE_RE.sub(" ", text)
    text = REPLACEMENT_OR_BOX_RE.sub(" ", text)
    profile = ACTIVE_PROFILE or {}
    cleanup = str(profile.get("cleanup_profile", "latin")).lower()
    if cleanup in {"latin", "latin_bai", "latin_zhuang"}:
        for name in ["cjk", "cyrillic", "tibetan", "arabic", "mongolian", "hangul"]:
            text = SCRIPT_RESIDUE[name].sub(" ", text)
    elif cleanup.startswith("tibetan"):
        for name in ["latin", "cjk", "cyrillic", "arabic", "mongolian", "hangul"]:
            text = SCRIPT_RESIDUE[name].sub(" ", text)
    elif cleanup in {"hangul", "korean"}:
        for name in ["latin", "cjk", "cyrillic", "tibetan", "arabic", "mongolian"]:
            text = SCRIPT_RESIDUE[name].sub(" ", text)
    elif cleanup in {"arabic", "uyghur", "kazakh_arabic"}:
        for name in ["latin", "cjk", "cyrillic", "tibetan", "mongolian", "hangul"]:
            text = SCRIPT_RESIDUE[name].sub(" ", text)
    elif cleanup in {"mongolian", "traditional_mongolian"}:
        for name in ["latin", "cjk", "cyrillic", "tibetan", "arabic", "hangul"]:
            text = SCRIPT_RESIDUE[name].sub(" ", text)
        text = MONGOLIAN_PRESENTATION_PUNCT_RE.sub(" ", text)
        text = MONGOLIAN_UNSAFE_SYMBOL_RE.sub(" ", text)
    else:
        for name in ["cjk", "cyrillic", "tibetan"]:
            text = SCRIPT_RESIDUE[name].sub(" ", text)
    if cleanup != "tibetan":
        text = TIBETAN_DECORATIVE_MARK_RE.sub(" ", text)
        text = TIBETAN_SHAD_RE.sub(" ", text)
    text = _remove_blocked_template_terms(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_language_profile(path: Path | None) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8")) if path else {}
    profile.setdefault("language_code", "za")
    profile.setdefault("language_name", "壮语")
    profile.setdefault("script_note", "现代标准壮文 Vahcuengh，拉丁字母拼写")
    profile.setdefault("html_lang", "za")
    profile.setdefault("script_regex", r"[A-Za-z]")
    profile.setdefault("min_script_ratio", 0.45)
    profile.setdefault("font_family", "\"Local Arial\", \"Local Arial Unicode\", Arial, Helvetica, sans-serif")
    profile.setdefault("safe_title_fragments", DEFAULT_SAFE_TITLES)
    profile.setdefault("max_digit_ratio", 0.18)
    profile.setdefault("max_latin_ratio", 1.0)
    profile.setdefault("max_cjk_ratio", 0.02)
    profile.setdefault("max_cyrillic_ratio", 0.0)
    profile.setdefault("max_tibetan_ratio", 0.0)
    profile.setdefault("max_arabic_ratio", 1.0)
    profile.setdefault("max_mongolian_ratio", 1.0)
    profile.setdefault("max_hangul_ratio", 1.0)
    profile.setdefault("cleanup_profile", "latin")
    profile.setdefault("css_direction", "ltr")
    profile.setdefault("css_writing_mode", "horizontal-tb")
    ACTIVE_PROFILE.clear()
    cleanup = str(profile.get("cleanup_profile", "")).lower()
    if cleanup.startswith("tibetan"):
        profile["max_tibetan_ratio"] = max(float(profile.get("max_tibetan_ratio", 0.0)), 1.0)
        profile.setdefault("max_latin_ratio", 0.0)
        profile.setdefault("max_arabic_ratio", 0.0)
        profile.setdefault("max_mongolian_ratio", 0.0)
        profile.setdefault("max_hangul_ratio", 0.0)
    ACTIVE_PROFILE.update(profile)
    return profile


def text_quality(text: str, script_re: re.Pattern[str] | None = None) -> dict[str, float]:
    cleaned = cleanse_text(text)
    script_re = script_re or re.compile(str(ACTIVE_PROFILE.get("script_regex", r"[A-Za-z]")))
    letters = len(script_re.findall(cleaned))
    digits = sum(ch.isdigit() for ch in cleaned)
    raw = str(text or "")
    cjk = len(CJK_RE.findall(raw))
    cyr = len(CYRILLIC_RE.findall(raw))
    tib = len(TIBETAN_RE.findall(raw))
    arabic = len(ARABIC_RE.findall(raw))
    mongolian = len(MONGOLIAN_RE.findall(raw))
    hangul = len(HANGUL_RE.findall(raw))
    words = [w for w in re.split(r"\s+", cleaned) if script_re.search(w)]
    script_runs = re.findall(r"(?:%s)+" % script_re.pattern, cleaned)
    return {
        "script_ratio": _ratio(letters, cleaned),
        "digit_ratio": _ratio(digits, cleaned),
        "latin_ratio": _ratio(len(LATIN_RE.findall(raw)), raw),
        "cjk_ratio": _ratio(cjk, raw),
        "cyrillic_ratio": _ratio(cyr, raw),
        "tibetan_ratio": _ratio(tib, raw),
        "arabic_ratio": _ratio(arabic, raw),
        "mongolian_ratio": _ratio(mongolian, raw),
        "hangul_ratio": _ratio(hangul, raw),
        "word_count": float(max(len(words), len(script_runs))),
        "char_count": float(len(cleaned)),
    }


def is_bad_title(title: str) -> bool:
    title = cleanse_text(title)
    if len(title) < 5:
        return True
    if BAD_TITLE_LITERAL_RE.fullmatch(title):
        return True
    if NUMERIC_TITLE_RE.fullmatch(title):
        return True
    digits = sum(ch.isdigit() for ch in title)
    script_re = re.compile(str(ACTIVE_PROFILE.get("script_regex", r"[A-Za-z]")))
    letters = len(script_re.findall(title))
    if digits > 0 and digits >= letters:
        return True
    if DATE_WORD_RE.search(title) and digits > 0:
        return True
    word_count = text_quality(title, script_re)["word_count"]
    if word_count < 1:
        return True
    return False


def _quality_score(text: str, title: str, script_re: re.Pattern[str]) -> float:
    q = text_quality(text, script_re)
    score = q["script_ratio"] * 2.0
    score += min(q["char_count"] / 600.0, 1.0)
    score += min(q["word_count"] / 90.0, 1.0) * 0.5
    score -= q["digit_ratio"] * 2.0
    score -= q["cjk_ratio"] * 2.0
    score -= q["cyrillic_ratio"] * 2.0
    for name in ["latin", "cjk", "cyrillic", "tibetan", "arabic", "mongolian", "hangul"]:
        max_key = f"max_{name}_ratio"
        max_ratio = float(ACTIVE_PROFILE.get(max_key, 1.0))
        if q[f"{name}_ratio"] > max_ratio:
            score -= q[f"{name}_ratio"] * 2.0
    if not is_bad_title(title):
        score += 0.6
    return round(score, 4)


def read_text_records(path: Path, language_profile: dict[str, Any], min_records: int) -> list[dict[str, str]]:
    script_re = re.compile(str(language_profile["script_regex"]))
    min_ratio = float(language_profile["min_script_ratio"])
    max_digit_ratio = float(language_profile.get("max_digit_ratio", 0.18))
    soft_records: list[dict[str, Any]] = []
    fallback_records: list[dict[str, Any]] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        title = cleanse_text(str(row.get("title", "")))
        text = cleanse_text(str(row.get("text", row.get("block_content", ""))))
        if len(text) < 40:
            continue
        q = text_quality(text, script_re)
        if q["script_ratio"] < min_ratio:
            continue
        residue_failed = False
        for name in ["latin", "cjk", "cyrillic", "tibetan", "arabic", "mongolian", "hangul"]:
            if q.get(f"{name}_ratio", 0.0) > float(language_profile.get(f"max_{name}_ratio", 1.0)):
                residue_failed = True
                break
        if residue_failed:
            continue
        record = {
            "title": title,
            "text": text,
            "url": str(row.get("url", "")),
            "source_record_id": str(row.get("record_id", row.get("source_record_id", ""))),
            "source": str(row.get("source", row.get("source_name", ""))),
            "quality_score": str(_quality_score(text, title, script_re)),
            "title_is_bad": str(is_bad_title(title)),
        }
        if q["digit_ratio"] <= max_digit_ratio:
            soft_records.append(record)
        else:
            fallback_records.append(record)

    records = sorted(soft_records or fallback_records, key=lambda r: float(r["quality_score"]), reverse=True)
    if len(records) < min_records:
        raise RuntimeError(f"not enough text records in {path}: {len(records)}")
    return records


def clip(text: str, min_len: int, max_len: int) -> str:
    text = cleanse_text(text)
    if len(text) <= max_len:
        return text
    for pattern in [SENTENCE_END_RE, CLAUSE_END_RE]:
        best = ""
        for match in pattern.finditer(text):
            end = match.end()
            if min_len <= end <= max_len:
                best = text[:end].strip()
            elif end > max_len:
                break
        if best:
            return best
    cut = text[:max_len]
    idx = cut.rfind(" ")
    if idx >= min_len:
        return cut[:idx].strip()
    return cut.rstrip()


def _span_ok(text: str) -> bool:
    cleaned = cleanse_text(text)
    if len(cleaned) < 12:
        return False
    q = text_quality(cleaned)
    min_words = float(ACTIVE_PROFILE.get("min_span_words", 2))
    return q["digit_ratio"] <= float(ACTIVE_PROFILE.get("max_digit_ratio", 0.18)) and q["word_count"] >= min_words


def select_span(text: str, rng: random.Random, min_len: int, max_len: int) -> str:
    text = cleanse_text(text)
    if len(text) <= max_len and len(text) >= min_len and _span_ok(text):
        return text
    sentences = split_sentences(text)
    if sentences:
        start_indexes = list(range(len(sentences)))
        rng.shuffle(start_indexes)
        for start in start_indexes[:12]:
            out: list[str] = []
            for sentence in sentences[start:]:
                candidate = " ".join(out + [sentence]).strip()
                if len(candidate) > max_len:
                    break
                out.append(sentence)
                if len(candidate) >= min_len and _span_ok(candidate):
                    return cleanse_text(candidate)
    words = text.split()
    if len(words) > 8:
        for _ in range(14):
            start = rng.randint(0, max(0, len(words) - 5))
            out: list[str] = []
            for word in words[start:]:
                candidate = " ".join(out + [word])
                if len(candidate) > max_len:
                    break
                out.append(word)
                if len(candidate) >= min_len and _span_ok(candidate):
                    return cleanse_text(candidate)
    return clip(text, min_len, max_len)


def split_sentences(text: str) -> list[str]:
    text = cleanse_text(text)
    if not text:
        return []
    parts: list[str] = []
    start = 0
    for match in SENTENCE_END_RE.finditer(text + " "):
        end = match.end()
        part = text[start:end].strip()
        if part:
            parts.append(part)
        start = end
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    if len(parts) <= 1 and " " in text:
        return []
    return parts


def paragraph_units(text: str) -> list[str]:
    text = cleanse_text(text)
    if not text:
        return []
    sentences = split_sentences(text)
    if sentences:
        return sentences
    words = text.split()
    if len(words) <= 12:
        return [text]
    units = []
    for idx in range(0, len(words), 16):
        units.append(" ".join(words[idx: idx + 16]))
    return units


class ContinuousTextSampler:
    """Consume records as contiguous text streams instead of random fragments."""

    def __init__(self, records: list[dict[str, str]], rng: random.Random):
        self.records = [rec for rec in records if cleanse_text(rec.get("text", ""))]
        if not self.records:
            self.records = records
        self.rng = rng
        self.record_order = list(range(len(self.records)))
        self.rng.shuffle(self.record_order)
        self.record_cursor = 0
        self.units: list[str] = []
        self.unit_cursor = 0
        self.current_record: dict[str, str] | None = None

    def _load_next_record(self, min_len: int) -> None:
        if not self.records:
            self.units = []
            self.current_record = None
            return
        for _ in range(max(len(self.record_order), 1)):
            if self.record_cursor >= len(self.record_order):
                self.rng.shuffle(self.record_order)
                self.record_cursor = 0
            rec = self.records[self.record_order[self.record_cursor]]
            self.record_cursor += 1
            units = paragraph_units(rec.get("text", ""))
            if sum(len(unit) for unit in units) >= min_len:
                self.current_record = rec
                self.units = units
                self.unit_cursor = 0
                return
        rec = self.rng.choice(self.records)
        self.current_record = rec
        self.units = paragraph_units(rec.get("text", "")) or [cleanse_text(rec.get("text", ""))]
        self.unit_cursor = 0

    def text(self, min_len: int, max_len: int) -> str:
        min_len, max_len = vertical_adjusted_lengths(min_len, max_len)
        for _ in range(4):
            if not self.units or self.unit_cursor >= len(self.units):
                self._load_next_record(min_len)
            out: list[str] = []
            while self.unit_cursor < len(self.units):
                candidate = " ".join(out + [self.units[self.unit_cursor]]).strip()
                if len(candidate) > max_len:
                    break
                out.append(self.units[self.unit_cursor])
                self.unit_cursor += 1
                if len(candidate) >= min_len and _span_ok(candidate):
                    return cleanse_text(candidate)
            if out:
                candidate = cleanse_text(" ".join(out))
                if len(candidate) >= min(12, min_len):
                    return clip(candidate, min_len, max_len)
            self._load_next_record(min_len)
        return select_span(self.rng.choice(self.records)["text"], self.rng, min_len, max_len)

    def title(self, min_len: int = 8, max_len: int = 34) -> str:
        min_len, max_len = vertical_adjusted_lengths(min_len, max_len)
        candidates = []
        if self.current_record:
            candidates.append(cleanse_text(self.current_record.get("title", "")))
        candidates.extend(
            cleanse_text(rec.get("title", ""))
            for rec in self.records
            if not is_bad_title(rec.get("title", ""))
        )
        for title in candidates:
            if min_len <= len(title) <= max_len and not is_bad_title(title):
                return title
        text = self.text(min_len, max_len)
        return text if not is_bad_title(text) else safe_title(self.rng, min_len, max_len)


def sampler_for(records: list[dict[str, str]], rng: random.Random) -> ContinuousTextSampler:
    key = id(rng)
    sampler = TEXT_STREAMS.get(key)
    if sampler is None:
        sampler = ContinuousTextSampler(records, rng)
        TEXT_STREAMS[key] = sampler
    return sampler


def is_vertical_profile(profile: dict[str, Any] | None = None) -> bool:
    profile = profile or ACTIVE_PROFILE
    writing_mode = str(profile.get("css_writing_mode", "")).lower()
    cleanup = str(profile.get("cleanup_profile", "")).lower()
    return writing_mode.startswith("vertical") or cleanup == "traditional_mongolian"


def vertical_adjusted_lengths(min_len: int, max_len: int) -> tuple[int, int]:
    if not is_vertical_profile():
        return min_len, max_len
    new_max = max(10, min(72, int(max_len * 0.46)))
    new_min = max(4, min(int(min_len * 0.55), max(4, new_max // 2)))
    if new_min > new_max:
        new_min = max(4, new_max // 2)
    return new_min, new_max


def vertical_css(profile: dict[str, Any] | None = None, base_size: int = 20) -> str:
    if not is_vertical_profile(profile):
        return ""
    small = max(11, base_size - 7)
    normal = max(13, base_size - 5)
    title = max(22, base_size + 8)
    return f"""
    body {{ writing-mode: horizontal-tb; }}
    .page {{
      writing-mode: horizontal-tb;
      direction: ltr;
      text-align: start;
      overflow: visible;
    }}
    [data-block-id] {{
      min-width: 12px;
      min-height: 12px;
      overflow: visible;
      word-break: keep-all;
      overflow-wrap: normal;
      text-orientation: mixed;
      line-height: 1.42;
    }}
    [data-label]:not([data-label="image"]):not([data-label="answer_area"]) {{
      writing-mode: vertical-lr;
      direction: ltr;
      text-align: start;
    }}
    .doc-title, .chapter-title, .newspaper-name, .poster-title, .feature-title, .journal-name, .sign-title {{
      font-size: {title}px !important;
      line-height: 1.35 !important;
      min-width: 30px;
    }}
    .headline, .section-title, .field-value, .question-text, .recipient {{
      font-size: {normal}px !important;
      line-height: 1.38 !important;
      min-width: 18px;
    }}
    .para, .news-para, .small-para, .small, .caption, .note, .option, .field-label, .meta,
    .list_item, .brief-line, .strip-item, td, th {{
      font-size: {small}px !important;
      line-height: 1.34 !important;
      min-width: 13px;
    }}
    table {{ writing-mode: horizontal-tb; }}
    .footer, .folio, .essay-foot {{ position: static !important; margin-top: 12px; }}
    """


def record_text(records: list[dict[str, str]], rng: random.Random, min_len: int, max_len: int) -> str:
    if str(ACTIVE_PROFILE.get("sampling_policy", "continuous_paragraph_v1")) == "legacy_random_span":
        min_len, max_len = vertical_adjusted_lengths(min_len, max_len)
        pool = [rec for rec in records if len(rec["text"]) >= min_len and float(rec.get("quality_score", 0)) > 1.0] or [
            rec for rec in records if len(rec["text"]) >= min_len
        ] or records
        return select_span(rng.choice(pool)["text"], rng, min_len, max_len)
    return sampler_for(records, rng).text(min_len, max_len)


def safe_title(rng: random.Random, min_len: int = 8, max_len: int = 34) -> str:
    titles = [cleanse_text(t) for t in ACTIVE_PROFILE.get("safe_title_fragments", DEFAULT_SAFE_TITLES)]
    titles = [t for t in titles if min_len <= len(t) <= max_len and not is_bad_title(t)]
    if not titles:
        titles = DEFAULT_SAFE_TITLES
    return rng.choice(titles)


def safe_fragment(min_len: int = 1, max_len: int = 28) -> str:
    """Return a deterministic target-script fragment for template fallbacks."""
    titles = [cleanse_text(t) for t in ACTIVE_PROFILE.get("safe_title_fragments", DEFAULT_SAFE_TITLES)]
    titles = [t for t in titles if t]
    if not titles:
        titles = DEFAULT_SAFE_TITLES
    for title in titles:
        clipped = clip(title, min_len, max_len)
        if clipped:
            return clipped
    return "2026"


def fallback_text(label: str) -> str:
    """Language-aware fallback used when hard-coded template text is cleaned away."""
    if label in {"answer_area", "image"}:
        return " "
    if label in {"page_number", "table_cell_number"}:
        return "1"
    if label == "metadata":
        return "2026"
    if label == "option":
        return safe_fragment(1, 6)
    if label in {"field_label", "table_header", "section_title", "seal"}:
        return safe_fragment(1, 18)
    if label in {"document_title", "document_subtitle"}:
        return safe_fragment(4, 34)
    return safe_fragment(2, 30)


def record_title(records: list[dict[str, str]], rng: random.Random, min_len: int = 8, max_len: int = 34) -> str:
    if str(ACTIVE_PROFILE.get("sampling_policy", "continuous_paragraph_v1")) != "legacy_random_span":
        return sampler_for(records, rng).title(min_len, max_len)
    min_len, max_len = vertical_adjusted_lengths(min_len, max_len)
    good_title_records = [
        rec for rec in records
        if not is_bad_title(rec.get("title", "")) and min_len <= len(cleanse_text(rec.get("title", ""))) <= max_len
    ]
    if good_title_records and rng.random() < 0.7:
        return cleanse_text(rng.choice(good_title_records)["title"])

    for _ in range(12):
        rec = rng.choice(records)
        candidate = select_span(rec["text"], rng, min_len, max_len)
        if not is_bad_title(candidate):
            return candidate
    return safe_title(rng, min_len, max_len)
