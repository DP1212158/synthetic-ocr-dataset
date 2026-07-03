#!/usr/bin/env python3
"""Collect Arabic-script Kazakh text from kazakh.people.com.cn."""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from synthetic_text_utils import cleanse_text, load_language_profile, text_quality


BASE_URL = "http://kazakh.people.com.cn"
ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
LINK_RE = re.compile(r"""href=["']([^"']+\.html)["']""", re.I)
P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.I | re.S)
SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")


SEED_URLS = [
    BASE_URL + "/",
    BASE_URL + "/194020/index.html",
    BASE_URL + "/155419/index.html",
    BASE_URL + "/158373/index.html",
    BASE_URL + "/155425/index.html",
    BASE_URL + "/155421/index.html",
    BASE_URL + "/155423/index.html",
    BASE_URL + "/65181/index.html",
    BASE_URL + "/306608/index.html",
    BASE_URL + "/306609/index.html",
]


def is_article_url(url: str) -> bool:
    return "/n4/" in url and re.search(r"/c\d+-\d+\.html$", url)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch(url: str, timeout: int) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 minority-language-synthetic-data/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as res:
        raw = res.read()
    for enc in ("utf-8", "gb18030"):
        text = raw.decode(enc, "ignore")
        if "<html" in text.lower() or ARABIC_RE.search(text):
            return text
    return raw.decode("utf-8", "ignore")


def normalize_url(url: str, base: str) -> str:
    joined = urllib.parse.urljoin(base, url)
    parsed = urllib.parse.urlparse(joined)
    if parsed.netloc and parsed.netloc != "kazakh.people.com.cn":
        return ""
    return urllib.parse.urlunparse(("http", "kazakh.people.com.cn", parsed.path, "", "", ""))


def extract_links(page_html: str, base_url: str) -> list[str]:
    article_links = []
    index_links = []
    for raw in LINK_RE.findall(page_html):
        url = normalize_url(html.unescape(raw), base_url)
        if not url:
            continue
        if is_article_url(url):
            article_links.append(url)
        elif re.search(r"/\d{5,}/.*index\.html$", url) or re.search(r"/\d+/index\.html$", url):
            index_links.append(url)
    return list(dict.fromkeys(article_links + index_links))


def clean_fragment(fragment: str) -> str:
    fragment = SCRIPT_STYLE_RE.sub(" ", fragment)
    fragment = TAG_RE.sub(" ", fragment)
    fragment = html.unescape(fragment)
    return " ".join(fragment.split())


def extract_article(url: str, page_html: str, profile: dict[str, Any], min_chars: int) -> dict[str, Any] | None:
    title_match = TITLE_RE.search(page_html)
    title = clean_fragment(title_match.group(1)) if title_match else ""
    title = re.split(r"--|人民网|حالىق تورابى", title)[0].strip()

    paragraphs = []
    for fragment in P_RE.findall(page_html):
        paragraph = cleanse_text(clean_fragment(fragment))
        if len(paragraph) < 20:
            continue
        q = text_quality(paragraph)
        if q["script_ratio"] >= float(profile["min_script_ratio"]):
            paragraphs.append(paragraph)

    text = cleanse_text(" ".join(paragraphs))
    if len(text) < min_chars:
        return None
    q = text_quality(text)
    if q["script_ratio"] < float(profile["min_script_ratio"]):
        return None
    if q["cyrillic_ratio"] > float(profile.get("max_cyrillic_ratio", 0.0)):
        return None
    if q["cjk_ratio"] > float(profile.get("max_cjk_ratio", 0.02)):
        return None
    return {
        "title": cleanse_text(title),
        "url": url,
        "text": text,
        "chars": len(text),
        "target_script_ratio": round(q["script_ratio"], 4),
        "digit_ratio": round(q["digit_ratio"], 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--target-records", type=int, default=120)
    parser.add_argument("--max-pages", type=int, default=260)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260702)
    parser.add_argument("--min-chars", type=int, default=80)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    profile = load_language_profile(Path(args.language_profile))
    queue = list(SEED_URLS)
    rng.shuffle(queue)
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    while queue and len(seen) < args.max_pages and len(records) < args.target_records:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            page_html = fetch(url, args.timeout)
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)})
            continue

        new_links = [link for link in extract_links(page_html, url) if link not in seen and link not in queue]
        queue.extend(new_links)

        if not is_article_url(url):
            continue

        article = extract_article(url, page_html, profile, args.min_chars)
        if article:
            article.update(
                {
                    "record_id": f"people_kz_{len(records)+1:05d}",
                    "language_code": profile["language_code"],
                    "language_name": profile["language_name"],
                    "script_note": profile["script_note"],
                    "source": "people_daily_kazakh",
                    "source_record_id": url,
                }
            )
            records.append(article)
            if len(records) % 10 == 0:
                print(json.dumps({"records": len(records), "pages_checked": len(seen), "queue": len(queue)}, ensure_ascii=False), flush=True)
        time.sleep(0.05)

    out = Path(args.output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_json(
        out.with_suffix(".summary.json"),
        {
            "records": len(records),
            "pages_checked": len(seen),
            "remaining_queue": len(queue),
            "failures": failures[:30],
            "source": "kazakh.people.com.cn",
            "seed_urls": SEED_URLS,
            "output_jsonl": str(out),
        },
    )
    print(json.dumps({"records": len(records), "output_jsonl": str(out)}, ensure_ascii=False, indent=2))
    return 0 if len(records) >= min(args.target_records, 40) else 2


if __name__ == "__main__":
    raise SystemExit(main())
