#!/usr/bin/env python3
"""Collect public text from a MediaWiki API into records.jsonl."""

from __future__ import annotations

import argparse
import json
import random
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from synthetic_text_utils import cleanse_text, load_language_profile, text_quality


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def api_get(endpoint: str, params: dict[str, Any], timeout: int) -> dict[str, Any]:
    url = endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "minority-language-synthetic-data/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def fetch_random_titles(endpoint: str, limit: int, timeout: int) -> list[str]:
    titles: list[str] = []
    while len(titles) < limit:
        data = api_get(
            endpoint,
            {
                "action": "query",
                "format": "json",
                "list": "random",
                "rnnamespace": 0,
                "rnlimit": min(50, limit - len(titles)),
            },
            timeout,
        )
        titles.extend(item["title"] for item in data.get("query", {}).get("random", []))
        time.sleep(0.2)
    return titles


def fetch_extract(endpoint: str, title: str, timeout: int) -> tuple[str, str]:
    data = api_get(
        endpoint,
        {
            "action": "query",
            "format": "json",
            "prop": "extracts|info",
            "explaintext": 1,
            "exsectionformat": "plain",
            "inprop": "url",
            "titles": title,
            "redirects": 1,
        },
        timeout,
    )
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        return str(page.get("extract", "")), str(page.get("fullurl", ""))
    return "", ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-endpoint", required=True)
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--target-records", type=int, default=120)
    parser.add_argument("--random-pages", type=int, default=300)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--seed", type=int, default=20260702)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    profile = load_language_profile(Path(args.language_profile))
    script_re = re.compile(str(profile["script_regex"]))
    titles = fetch_random_titles(args.api_endpoint, args.random_pages, args.timeout)
    rng.shuffle(titles)

    records = []
    failures = []
    for title in titles:
        try:
            raw_text, url = fetch_extract(args.api_endpoint, title, args.timeout)
        except Exception as exc:
            failures.append({"title": title, "error": str(exc)})
            continue
        text = cleanse_text(raw_text)
        if len(text) < 80:
            continue
        q = text_quality(text, script_re)
        if q["script_ratio"] < float(profile["min_script_ratio"]):
            continue
        records.append(
            {
                "record_id": f"wiki_{len(records)+1:05d}",
                "language_code": profile["language_code"],
                "language_name": profile["language_name"],
                "script_note": profile["script_note"],
                "source": "wikipedia_random",
                "source_record_id": title,
                "title": cleanse_text(title),
                "url": url,
                "text": text,
                "chars": len(text),
                "target_script_ratio": round(q["script_ratio"], 4),
                "digit_ratio": round(q["digit_ratio"], 4),
            }
        )
        if len(records) >= args.target_records:
            break
        time.sleep(0.2)

    out = Path(args.output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_json(
        out.with_suffix(".summary.json"),
        {
            "records": len(records),
            "titles_checked": len(titles),
            "failures": failures[:20],
            "api_endpoint": args.api_endpoint,
            "output_jsonl": str(out),
        },
    )
    print(json.dumps({"records": len(records), "output_jsonl": str(out)}, ensure_ascii=False, indent=2))
    return 0 if records else 2


if __name__ == "__main__":
    raise SystemExit(main())
