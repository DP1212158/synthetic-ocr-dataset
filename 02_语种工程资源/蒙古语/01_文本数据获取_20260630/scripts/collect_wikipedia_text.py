#!/usr/bin/env python3
"""Collect plain-text samples from a Wikipedia language edition.

This collector is intentionally dependency-free so it can run in a clean
macOS/Python environment. It uses the MediaWiki API, saves structured JSONL
records, and writes enough metadata to judge whether the source is suitable for
layout/template data generation.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


USER_AGENT = (
    "CMU-Minority-Language-Data-Collector/0.1 "
    "(research data feasibility; MediaWiki API; local project)"
)

SECTION_HEADING_RE = re.compile(r"^={2,}\s*.*?\s*={2,}$")
WHITESPACE_RE = re.compile(r"\s+")
CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
MONGOLIAN_VERTICAL_RE = re.compile(r"[\u1800-\u18af]")
LATIN_RE = re.compile(r"[A-Za-z]")


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def request_json(
    endpoint: str,
    params: Dict[str, Any],
    timeout: int,
    retries: int,
    sleep_seconds: float,
) -> Dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{endpoint}?{query}"
    last_error: Optional[BaseException] = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(sleep_seconds * (attempt + 1))
    raise RuntimeError(f"request failed after {retries + 1} attempts: {last_error}") from last_error


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def split_paragraphs(extract: str, min_chars: int) -> List[str]:
    paragraphs: List[str] = []
    seen = set()
    for raw in extract.splitlines():
        text = normalize_text(raw)
        if not text:
            continue
        if SECTION_HEADING_RE.match(text):
            continue
        if text.startswith("==") and text.endswith("=="):
            continue
        if len(text) < min_chars:
            continue
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        paragraphs.append(text)
    return paragraphs


def char_ratio(text: str, pattern: re.Pattern[str]) -> float:
    if not text:
        return 0.0
    return len(pattern.findall(text)) / max(len(text), 1)


def script_profile(text: str) -> Dict[str, Any]:
    cyrillic_count = len(CYRILLIC_RE.findall(text))
    vertical_mongolian_count = len(MONGOLIAN_VERTICAL_RE.findall(text))
    latin_count = len(LATIN_RE.findall(text))
    return {
        "cyrillic_chars": cyrillic_count,
        "vertical_mongolian_chars": vertical_mongolian_count,
        "latin_chars": latin_count,
        "cyrillic_ratio": round(char_ratio(text, CYRILLIC_RE), 4),
        "vertical_mongolian_ratio": round(char_ratio(text, MONGOLIAN_VERTICAL_RE), 4),
        "latin_ratio": round(char_ratio(text, LATIN_RE), 4),
    }


def list_allpages_batch(
    endpoint: str,
    limit: int,
    timeout: int,
    retries: int,
    sleep_seconds: float,
    apcontinue: Optional[str],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    params: Dict[str, Any] = {
        "action": "query",
        "list": "allpages",
        "apnamespace": "0",
        "apfilterredir": "nonredirects",
        "aplimit": str(limit),
        "format": "json",
        "formatversion": "2",
    }
    if apcontinue:
        params["apcontinue"] = apcontinue
    data = request_json(endpoint, params, timeout, retries, sleep_seconds)
    pages = data.get("query", {}).get("allpages", [])
    next_continue = data.get("continue", {}).get("apcontinue")
    return pages, next_continue


def list_randompages_batch(
    endpoint: str,
    limit: int,
    timeout: int,
    retries: int,
    sleep_seconds: float,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "action": "query",
        "list": "random",
        "rnnamespace": "0",
        "rnlimit": str(limit),
        "format": "json",
        "formatversion": "2",
    }
    data = request_json(endpoint, params, timeout, retries, sleep_seconds)
    return data.get("query", {}).get("random", [])


def fetch_pages_by_ids(
    endpoint: str,
    pageids: Iterable[int],
    timeout: int,
    retries: int,
    sleep_seconds: float,
) -> List[Dict[str, Any]]:
    pageid_text = "|".join(str(x) for x in pageids)
    params: Dict[str, Any] = {
        "action": "query",
        "pageids": pageid_text,
        "prop": "extracts|info",
        "explaintext": "1",
        "exsectionformat": "plain",
        "inprop": "url",
        "format": "json",
        "formatversion": "2",
    }
    data = request_json(endpoint, params, timeout, retries, sleep_seconds)
    return data.get("query", {}).get("pages", [])


def fetch_site_statistics(
    endpoint: str,
    timeout: int,
    retries: int,
    sleep_seconds: float,
) -> Dict[str, Any]:
    params = {
        "action": "query",
        "meta": "siteinfo",
        "siprop": "statistics|general",
        "format": "json",
        "formatversion": "2",
    }
    data = request_json(endpoint, params, timeout, retries, sleep_seconds)
    return data.get("query", {})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "record_id",
        "language_code",
        "language_name",
        "script_note",
        "source",
        "title",
        "pageid",
        "paragraph_index",
        "chars",
        "cyrillic_ratio",
        "vertical_mongolian_ratio",
        "latin_ratio",
        "url",
        "text",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = {k: r.get(k, "") for k in fieldnames}
            writer.writerow(row)


def build_summary(
    args: argparse.Namespace,
    siteinfo: Dict[str, Any],
    pages_seen: int,
    pages_with_text: int,
    records: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
    started_at: str,
    ended_at: str,
) -> Dict[str, Any]:
    char_counts = [int(r["chars"]) for r in records]
    cyrillic_ratios = [float(r["cyrillic_ratio"]) for r in records]
    vertical_ratios = [float(r["vertical_mongolian_ratio"]) for r in records]
    latin_ratios = [float(r["latin_ratio"]) for r in records]
    return {
        "run": {
            "started_at": started_at,
            "ended_at": ended_at,
            "endpoint": args.endpoint,
            "mode": args.mode,
            "language_code": args.language_code,
            "language_name": args.language_name,
            "script_note": args.script_note,
            "max_pages": args.max_pages,
            "batch_size": args.batch_size,
            "min_paragraph_chars": args.min_paragraph_chars,
            "sleep_seconds": args.sleep_seconds,
            "timeout": args.timeout,
            "retries": args.retries,
        },
        "siteinfo": siteinfo,
        "collection": {
            "pages_seen": pages_seen,
            "pages_with_text": pages_with_text,
            "paragraph_records": len(records),
            "errors": len(errors),
            "total_chars": sum(char_counts),
            "avg_chars_per_record": round(statistics.mean(char_counts), 1) if char_counts else 0,
            "median_chars_per_record": statistics.median(char_counts) if char_counts else 0,
            "avg_cyrillic_ratio": round(statistics.mean(cyrillic_ratios), 4) if cyrillic_ratios else 0,
            "avg_vertical_mongolian_ratio": round(statistics.mean(vertical_ratios), 4) if vertical_ratios else 0,
            "avg_latin_ratio": round(statistics.mean(latin_ratios), 4) if latin_ratios else 0,
        },
    }


def write_report(path: Path, summary: Dict[str, Any], records: List[Dict[str, Any]]) -> None:
    stats = summary.get("siteinfo", {}).get("statistics", {})
    coll = summary["collection"]
    run = summary["run"]
    enough_for_layout = coll["paragraph_records"] >= 100 and coll["total_chars"] >= 20000
    script_warning = ""
    if run["language_code"] == "mn" and coll["avg_vertical_mongolian_ratio"] < 0.01:
        script_warning = (
            "\n- 注意：本批样本几乎全部是西里尔蒙古文，不是传统竖排蒙古文。"
            "如果后续模板目标是内蒙古传统蒙文版面，需要额外来源或转写流程。\n"
        )
    sample_lines = []
    for r in records[:5]:
        text = r["text"]
        if len(text) > 180:
            text = text[:180] + "..."
        sample_lines.append(f"- `{r['title']}`：{text}")
    sample_block = "\n".join(sample_lines) if sample_lines else "- 无"
    verdict = (
        "可以作为第一批造数据文本来源，但建议配合其他来源扩充。"
        if enough_for_layout
        else "当前样本量偏小，只能验证流程；需要扩大采集或改用 dumps。"
    )
    md = f"""# Wikipedia 文本采集评估：{run['language_name']}（{run['language_code']}）

## 采集结论

{verdict}
{script_warning}
## 本次运行

- API endpoint：`{run['endpoint']}`
- 采集模式：`{run['mode']}`
- 页面扫描数：{coll['pages_seen']}
- 有效页面数：{coll['pages_with_text']}
- 段落记录数：{coll['paragraph_records']}
- 总字符数：{coll['total_chars']}
- 平均段落字符数：{coll['avg_chars_per_record']}
- 平均西里尔字符占比：{coll['avg_cyrillic_ratio']}
- 平均传统蒙古文 Unicode 区段占比：{coll['avg_vertical_mongolian_ratio']}
- 平均拉丁字符占比：{coll['avg_latin_ratio']}

## 站点规模参考

- 页面总数：{stats.get('pages', '未知')}
- 文章数：{stats.get('articles', '未知')}
- Wikimedia 统计词量：{stats.get('cirrussearch-article-words', '未知')}
- 活跃用户：{stats.get('activeusers', '未知')}

## 样本文本

{sample_block}

## 对项目的意义

- 适合：百科类正文、短段落、普通横排西里尔蒙古文文本填充。
- 不足：题材偏百科；很多页面较短；不覆盖传统竖排蒙古文视觉特征。
- 建议：先用 API 小批量验证模板流程；后续若需要数万段文本，优先使用 Wikimedia dumps；若目标是传统蒙文版式，应补充传统蒙古文网站、教材 OCR 或转写后的人工质检文本。

## 版权和归因

Wikipedia 文本通常在 CC BY-SA 等自由许可证下提供。后续生成数据集时建议保留 `source_url`、`title`、`license_note` 字段，并在项目说明中做统一归因。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")


def collect(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    started_at = now_utc()
    siteinfo: Dict[str, Any] = {}
    errors: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []
    pages_seen = 0
    pages_with_text = 0
    apcontinue: Optional[str] = None
    seen_pageids = set()

    try:
        siteinfo = fetch_site_statistics(args.endpoint, args.timeout, args.retries, args.sleep_seconds)
    except Exception as exc:
        errors.append({"stage": "siteinfo", "error": repr(exc), "time": now_utc()})

    while pages_seen < args.max_pages:
        batch_limit = min(args.batch_size, args.max_pages - pages_seen)
        if args.mode == "random":
            try:
                pages = list_randompages_batch(
                    args.endpoint,
                    batch_limit,
                    args.timeout,
                    args.retries,
                    args.sleep_seconds,
                )
            except Exception as exc:
                errors.append({"stage": "randompages", "error": repr(exc), "time": now_utc()})
                break
            apcontinue = None
        else:
            try:
                pages, apcontinue = list_allpages_batch(
                    args.endpoint,
                    batch_limit,
                    args.timeout,
                    args.retries,
                    args.sleep_seconds,
                    apcontinue,
                )
            except Exception as exc:
                errors.append({"stage": "allpages", "error": repr(exc), "time": now_utc(), "apcontinue": apcontinue})
                break
        if not pages:
            break
        pageids = []
        for p in pages:
            pageid = p.get("pageid") or p.get("id")
            if pageid is None:
                continue
            if pageid in seen_pageids:
                continue
            seen_pageids.add(pageid)
            pageids.append(pageid)
        if not pageids:
            if args.mode == "random":
                continue
            break
        pages_seen += len(pageids)
        try:
            fetched_pages = fetch_pages_by_ids(
                args.endpoint,
                pageids,
                args.timeout,
                args.retries,
                args.sleep_seconds,
            )
        except Exception as exc:
            errors.append({"stage": "extracts", "error": repr(exc), "time": now_utc(), "pageids": pageids})
            fetched_pages = []

        for page in fetched_pages:
            extract = page.get("extract") or ""
            paragraphs = split_paragraphs(extract, args.min_paragraph_chars)
            if paragraphs:
                pages_with_text += 1
            for idx, paragraph in enumerate(paragraphs):
                profile = script_profile(paragraph)
                record_id_base = f"{args.language_code}:{page.get('pageid')}:{idx}:{paragraph}"
                record_id = hashlib.sha1(record_id_base.encode("utf-8")).hexdigest()[:16]
                record = {
                    "record_id": record_id,
                    "language_code": args.language_code,
                    "language_name": args.language_name,
                    "script_note": args.script_note,
                    "source": "wikipedia_api",
                    "license_note": "Wikipedia text is generally available under CC BY-SA; retain source attribution.",
                    "title": page.get("title", ""),
                    "pageid": page.get("pageid", ""),
                    "paragraph_index": idx,
                    "chars": len(paragraph),
                    "url": page.get("fullurl", ""),
                    "text": paragraph,
                    "crawl_time_utc": now_utc(),
                    **profile,
                }
                records.append(record)

        print(
            f"seen_pages={pages_seen} valid_pages={pages_with_text} records={len(records)}",
            file=sys.stderr,
        )
        if args.mode == "allpages" and not apcontinue:
            break
        time.sleep(args.sleep_seconds)

    ended_at = now_utc()
    summary = build_summary(args, siteinfo, pages_seen, pages_with_text, records, errors, started_at, ended_at)
    write_jsonl(out_dir / "records.jsonl", records)
    write_csv(out_dir / "records.csv", records)
    write_json(out_dir / "summary.json", summary)
    write_json(out_dir / "errors.json", errors)
    write_report(out_dir / "README.md", summary, records)
    return 0 if records else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Wikipedia text samples through MediaWiki API.")
    parser.add_argument("--mode", choices=["allpages", "random"], default="allpages")
    parser.add_argument("--language-code", default="mn")
    parser.add_argument("--language-name", default="蒙古语")
    parser.add_argument("--script-note", default="mn.wikipedia.org 主要为西里尔蒙古文，非传统竖排蒙古文")
    parser.add_argument("--endpoint", default="https://mn.wikipedia.org/w/api.php")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--min-paragraph-chars", type=int, default=40)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--retries", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    return collect(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
