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
LATIN_RE = re.compile(r"[A-Za-z]")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
HTML_RE = re.compile(r"<[^>]+>")
LATEX_RE = re.compile(r"\\[A-Za-z]+|\$+|[{}_^]")

NUMERIC_TITLE_RE = re.compile(r"^[\d\s\-:/.()]+$")
DATE_WORD_RE = re.compile(r"\b(nyied|hauh|nienz|bi'?nyinh|ngoenz)\b", re.IGNORECASE)

ACTIVE_PROFILE: dict[str, Any] = {}

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


def _ratio(count: int, text: str) -> float:
    return count / max(len(text), 1)


def cleanse_text(text: str) -> str:
    """Clean text for Latin-script Zhuang synthetic rendering.

    The function deliberately removes Chinese, Cyrillic and Tibetan residues.
    This keeps generated Zhuang pages from inheriting mixed-language OCR labels
    or stale Tibetan/Mongolian content from previous project stages.
    """

    text = str(text or "")
    text = HTML_RE.sub(" ", text)
    text = LATEX_RE.sub(" ", text)
    text = text.replace("\u00a0", " ")
    text = CYRILLIC_RE.sub(" ", text)
    text = CJK_RE.sub(" ", text)
    text = TIBETAN_DECORATIVE_MARK_RE.sub(" ", text)
    text = TIBETAN_SHAD_RE.sub(" ", text)
    text = TIBETAN_RE.sub(" ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[\[\]【】（）()<>]+", " ", text)
    text = text.replace("...", " ")
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
    profile.setdefault("max_cjk_ratio", 0.02)
    profile.setdefault("max_cyrillic_ratio", 0.0)
    profile.setdefault("max_tibetan_ratio", 0.0)
    ACTIVE_PROFILE.clear()
    ACTIVE_PROFILE.update(profile)
    return profile


def text_quality(text: str, script_re: re.Pattern[str] | None = None) -> dict[str, float]:
    cleaned = cleanse_text(text)
    script_re = script_re or re.compile(str(ACTIVE_PROFILE.get("script_regex", r"[A-Za-z]")))
    letters = len(script_re.findall(cleaned))
    digits = sum(ch.isdigit() for ch in cleaned)
    cjk = len(CJK_RE.findall(str(text or "")))
    cyr = len(CYRILLIC_RE.findall(str(text or "")))
    tib = len(TIBETAN_RE.findall(str(text or "")))
    words = WORD_RE.findall(cleaned)
    return {
        "script_ratio": _ratio(letters, cleaned),
        "digit_ratio": _ratio(digits, cleaned),
        "cjk_ratio": _ratio(cjk, str(text or "")),
        "cyrillic_ratio": _ratio(cyr, str(text or "")),
        "tibetan_ratio": _ratio(tib, str(text or "")),
        "word_count": float(len(words)),
        "char_count": float(len(cleaned)),
    }


def is_bad_title(title: str) -> bool:
    title = cleanse_text(title)
    if len(title) < 5:
        return True
    if NUMERIC_TITLE_RE.fullmatch(title):
        return True
    digits = sum(ch.isdigit() for ch in title)
    letters = len(LATIN_RE.findall(title))
    if digits > 0 and digits >= letters:
        return True
    if DATE_WORD_RE.search(title) and digits > 0:
        return True
    if len(WORD_RE.findall(title)) < 2:
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
    score -= q["tibetan_ratio"] * 2.0
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
    return q["digit_ratio"] <= float(ACTIVE_PROFILE.get("max_digit_ratio", 0.18)) and q["word_count"] >= 3


def select_span(text: str, rng: random.Random, min_len: int, max_len: int) -> str:
    text = cleanse_text(text)
    if len(text) <= max_len and len(text) >= min_len and _span_ok(text):
        return text
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


def record_text(records: list[dict[str, str]], rng: random.Random, min_len: int, max_len: int) -> str:
    pool = [rec for rec in records if len(rec["text"]) >= min_len and float(rec.get("quality_score", 0)) > 1.0] or [
        rec for rec in records if len(rec["text"]) >= min_len
    ] or records
    for _ in range(12):
        text = select_span(rng.choice(pool)["text"], rng, min_len, max_len)
        if len(text) >= min(16, min_len) and _span_ok(text):
            return text
    return select_span(rng.choice(pool)["text"], rng, min_len, max_len)


def safe_title(rng: random.Random, min_len: int = 8, max_len: int = 34) -> str:
    titles = [cleanse_text(t) for t in ACTIVE_PROFILE.get("safe_title_fragments", DEFAULT_SAFE_TITLES)]
    titles = [t for t in titles if min_len <= len(t) <= max_len and not is_bad_title(t)]
    if not titles:
        titles = DEFAULT_SAFE_TITLES
    return rng.choice(titles)


def record_title(records: list[dict[str, str]], rng: random.Random, min_len: int = 8, max_len: int = 34) -> str:
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
