#!/usr/bin/env python3
"""Collect public Zhuang text records from MediaWiki sources."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import statistics
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


LATIN_RE = re.compile(r"[A-Za-z]")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
ZHUANG_WORD_RE = re.compile(
    r"\b[A-Za-z]+(?:[aeiou]{1,3}|[aeiou][ng]?)?[zjxbqvh]?\b",
    re.IGNORECASE,
)


SOURCES = {
    "za_wikipedia": {
        "source_name": "Zhuang Wikipedia",
        "api_endpoint": "https://za.wikipedia.org/w/api.php",
        "page_url_template": "https://za.wikipedia.org/wiki/{title}",
    }
}


def now_date() -> str:
    return dt.datetime.now().strftime("%Y%m%d")


def clean_text(text: str) -> str:
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def zhuang_ratio(text: str) -> float:
    if not text:
        return 0.0
    latin = len(LATIN_RE.findall(text))
    cjk = len(CJK_RE.findall(text))
    cyrillic = len(CYRILLIC_RE.findall(text))
    words = re.findall(r"[A-Za-z]{2,}", text)
    if not words:
        return 0.0
    zhuang_like = len([w for w in words if ZHUANG_WORD_RE.fullmatch(w)])
    cjk_penalty = min(0.5, cjk / max(len(text), 1))
    cyr_penalty = min(0.5, cyrillic / max(len(text), 1))
    return max(0.0, min(1.0, (latin / max(len(text), 1)) * 0.55 + (zhuang_like / len(words)) * 0.45 - cjk_penalty - cyr_penalty))


def get_json(api: str, params: dict[str, Any]) -> dict[str, Any]:
    url = api + "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": "CMU-Minority-OCR-SyntheticData/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_allpage_titles(api: str, max_pages: int, page_batch: int) -> list[str]:
    titles: list[str] = []
    apcontinue = None
    while len(titles) < max_pages:
        params = {
            "action": "query",
            "list": "allpages",
            "aplimit": min(page_batch, max_pages - len(titles)),
            "format": "json",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue
        data = get_json(api, params)
        for page in data.get("query", {}).get("allpages", []):
            title = str(page.get("title", "")).strip()
            if title:
                titles.append(title)
        apcontinue = data.get("continue", {}).get("apcontinue")
        if not apcontinue:
            break
        time.sleep(0.1)
    return titles


def fetch_page_extract(api: str, title: str) -> dict[str, Any] | None:
    params = {
        "action": "query",
        "prop": "extracts|info",
        "explaintext": 1,
        "exsectionformat": "plain",
        "inprop": "url",
        "redirects": 1,
        "titles": title,
        "format": "json",
    }
    pages = get_json(api, params).get("query", {}).get("pages", {})
    for row in pages.values():
        if row.get("missing") is not None:
            continue
        text = clean_text(str(row.get("extract", "")))
        if text:
            return {
                "title": str(row.get("title") or title),
                "text": text,
                "url": str(row.get("fullurl", "")),
            }
    return None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_source(args: argparse.Namespace, source_id: str, source: dict[str, str]) -> dict[str, Any]:
    out_dir = Path(args.output_root) / f"{source_id}_allpages_sample_{now_date()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    titles = fetch_allpage_titles(source["api_endpoint"], args.max_pages, args.page_batch)
    records = []
    rejected = []
    for idx, title in enumerate(titles, start=1):
        try:
            page = fetch_page_extract(source["api_endpoint"], title)
        except Exception as exc:
            rejected.append({"title": title, "reason": f"fetch_error:{exc}"})
            continue
        if not page:
            rejected.append({"title": title, "reason": "empty_extract"})
            continue
        ratio = zhuang_ratio(page["text"])
        if len(page["text"]) < args.min_chars or ratio < args.min_zhuang_ratio:
            rejected.append({"title": page["title"], "reason": "low_length_or_ratio", "chars": len(page["text"]), "zhuang_ratio": round(ratio, 4)})
            continue
        records.append(
            {
                "record_id": f"{source_id}_{len(records)+1:05d}",
                "language_code": "za",
                "language_name": "壮语",
                "script_note": "现代标准壮文 Vahcuengh，拉丁字母拼写",
                "source_name": source["source_name"],
                "source_id": source_id,
                "title": page["title"],
                "url": page["url"] or source["page_url_template"].format(title=page["title"].replace(" ", "_")),
                "text": page["text"],
                "char_count": len(page["text"]),
                "zhuang_ratio": round(ratio, 4),
                "collected_at": dt.datetime.now().isoformat(timespec="seconds"),
            }
        )
        time.sleep(args.delay)

    records_jsonl = out_dir / "records.jsonl"
    with records_jsonl.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    csv_path = out_dir / "records.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["record_id", "language_code", "language_name", "source_name", "title", "url", "char_count", "zhuang_ratio"],
        )
        writer.writeheader()
        for row in records:
            writer.writerow({k: row.get(k, "") for k in writer.fieldnames})

    lengths = [r["char_count"] for r in records]
    ratios = [r["zhuang_ratio"] for r in records]
    summary = {
        "source_id": source_id,
        "source_name": source["source_name"],
        "api_endpoint": source["api_endpoint"],
        "output_dir": str(out_dir),
        "titles_seen": len(titles),
        "records_kept": len(records),
        "records_rejected": len(rejected),
        "total_chars": sum(lengths),
        "avg_length": round(statistics.mean(lengths), 2) if lengths else 0,
        "median_length": round(statistics.median(lengths), 2) if lengths else 0,
        "avg_zhuang_ratio": round(statistics.mean(ratios), 4) if ratios else 0,
        "min_zhuang_ratio": min(ratios) if ratios else 0,
        "max_zhuang_ratio": max(ratios) if ratios else 0,
        "min_chars": args.min_chars,
        "min_zhuang_ratio_threshold": args.min_zhuang_ratio,
        "records_jsonl": str(records_jsonl),
        "records_csv": str(csv_path),
        "rejected_sample": rejected[:30],
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--page-batch", type=int, default=50)
    parser.add_argument("--min-chars", type=int, default=80)
    parser.add_argument("--min-zhuang-ratio", type=float, default=0.36)
    parser.add_argument("--delay", type=float, default=0.05)
    args = parser.parse_args()

    summaries = [collect_source(args, source_id, source) for source_id, source in SOURCES.items()]
    root = Path(args.output_root)
    write_json(root / f"collection_summary_{now_date()}.json", {"summaries": summaries})
    print(json.dumps({"summaries": summaries}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
