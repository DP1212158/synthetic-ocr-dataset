#!/usr/bin/env python3
"""Build cached VL3 long-text records from web and ebook sources."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from synthetic_text_utils import cleanse_text, load_language_profile, text_quality  # noqa: E402


HTML_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)[\s\S]*?</\1>", re.I)
PARA_RE = re.compile(r"<(?:p|h1|h2|h3|h4|li|div)[^>]*>(?P<inner>[\s\S]*?)</(?:p|h1|h2|h3|h4|li|div)>", re.I)
PDF_TEXT_RE = re.compile(rb"[\x09\x0a\x0d\x20-\x7e]{20,}")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_markup(raw: str) -> str:
    raw = SCRIPT_STYLE_RE.sub(" ", raw)
    raw = HTML_RE.sub(" ", raw)
    raw = html.unescape(raw)
    return cleanse_text(raw)


def split_paragraphs(text: str) -> list[str]:
    chunks = [cleanse_text(part) for part in re.split(r"(?:\n\s*){2,}", text)]
    out = []
    for chunk in chunks:
        if len(chunk) > 1800:
            sentences = re.split(r"(?<=[.!?。！？།])\s+", chunk)
            buf = ""
            for sentence in sentences:
                candidate = (buf + " " + sentence).strip()
                if len(candidate) > 900 and buf:
                    out.append(buf)
                    buf = sentence
                else:
                    buf = candidate
            if buf:
                out.append(buf)
        elif chunk:
            out.append(chunk)
    return out


def parse_html_bytes(data: bytes, source_name: str) -> list[dict[str, str]]:
    raw = data.decode("utf-8", "ignore")
    matches = list(PARA_RE.finditer(raw))
    if matches:
        paras = [clean_markup(m.group("inner")) for m in matches]
    else:
        paras = split_paragraphs(clean_markup(raw))
    return [{"chapter": source_name, "text": para} for para in paras if para]


def parse_text_bytes(data: bytes, source_name: str) -> list[dict[str, str]]:
    raw = data.decode("utf-8", "ignore")
    return [{"chapter": source_name, "text": para} for para in split_paragraphs(raw) if para]


def parse_epub(path: Path) -> list[dict[str, str]]:
    rows = []
    with ZipFile(path) as zf:
        names = sorted(n for n in zf.namelist() if n.lower().endswith((".xhtml", ".html", ".htm")))
        for name in names:
            rows.extend(parse_html_bytes(zf.read(name), name))
    return rows


def parse_pdf_bytes(data: bytes, source_name: str) -> list[dict[str, str]]:
    try:
        from pypdf import PdfReader  # type: ignore
        import io

        reader = PdfReader(io.BytesIO(data))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        return [{"chapter": source_name, "text": para} for para in split_paragraphs(text) if para]
    except Exception:
        text = "\n".join(m.group(0).decode("utf-8", "ignore") for m in PDF_TEXT_RE.finditer(data))
        return [{"chapter": source_name, "text": para} for para in split_paragraphs(text) if para]


def parse_source(path: Path, source_name: str) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    data = path.read_bytes()
    if suffix == ".epub":
        return parse_epub(path)
    if suffix in {".html", ".htm", ".xhtml"}:
        return parse_html_bytes(data, source_name)
    if suffix == ".pdf":
        return parse_pdf_bytes(data, source_name)
    return parse_text_bytes(data, source_name)


def download(url: str, cache_dir: Path, resume: bool) -> tuple[Path, dict[str, Any]]:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    ext = Path(url.split("?")[0]).suffix or ".html"
    target = cache_dir / f"{digest}{ext}"
    if target.exists() and resume:
        data = target.read_bytes()
        return target, {"url": url, "cache_path": str(target), "sha256": sha256_bytes(data), "cached": True}
    req = urllib.request.Request(url, headers={"User-Agent": "VL3-OCR-TextSource/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target, {"url": url, "cache_path": str(target), "sha256": sha256_bytes(data), "cached": False}


def load_urls(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def make_records(rows: list[dict[str, str]], profile: dict[str, Any], source_label: str, min_chars: int) -> list[dict[str, Any]]:
    records = []
    for idx, row in enumerate(rows, 1):
        text = cleanse_text(row.get("text", ""))
        if len(text) < min_chars:
            continue
        q = text_quality(text, re.compile(str(profile.get("script_regex", r"."))))
        if q["script_ratio"] < float(profile.get("min_script_ratio", 0.35)):
            continue
        title = cleanse_text(row.get("title") or row.get("chapter") or source_label)
        records.append({
            "language": profile.get("language_name"),
            "script": profile.get("script_note"),
            "title": title[:120],
            "source_url": row.get("source_url", ""),
            "source_type": row.get("source_type", source_label),
            "license_note": row.get("license_note", "source license not verified by script"),
            "chapter": row.get("chapter", ""),
            "paragraph_id": f"{source_label}_{idx:06d}",
            "text": text,
            "char_count": len(text),
            "script_ratio": round(q["script_ratio"], 4),
            "quality_score": str(round(q["script_ratio"] * 2 + min(len(text) / 800, 1), 4)),
            "record_id": f"{source_label}_{idx:06d}",
            "source": source_label,
        })
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language-profile", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-jsonl")
    parser.add_argument("--urls-file")
    parser.add_argument("--local-files", nargs="*", default=[])
    parser.add_argument("--fallback-records")
    parser.add_argument("--min-records", type=int, default=40)
    parser.add_argument("--min-chars", type=int, default=40)
    parser.add_argument("--resume-from-cache", action="store_true")
    args = parser.parse_args()

    profile = load_language_profile(Path(args.language_profile))
    out_dir = Path(args.output_dir)
    cache_dir = out_dir / "cache"
    raw_rows = []
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "language": profile.get("language_name"),
        "sources": [],
    }

    for url in load_urls(Path(args.urls_file) if args.urls_file else None):
        try:
            path, info = download(url, cache_dir, args.resume_from_cache)
            rows = parse_source(path, url)
            for row in rows:
                row["source_url"] = url
                row["source_type"] = "web"
            raw_rows.extend(rows)
            info["paragraphs"] = len(rows)
            info["status"] = "ok"
            manifest["sources"].append(info)
        except Exception as exc:
            manifest["sources"].append({"url": url, "status": "failed", "error": str(exc)})

    for file_name in args.local_files:
        path = Path(file_name)
        if not path.exists():
            manifest["sources"].append({"local_file": str(path), "status": "missing"})
            continue
        rows = parse_source(path, path.name)
        for row in rows:
            row["source_type"] = "local_file"
        raw_rows.extend(rows)
        manifest["sources"].append({
            "local_file": str(path),
            "status": "ok",
            "sha256": sha256_bytes(path.read_bytes()),
            "paragraphs": len(rows),
        })

    records = make_records(raw_rows, profile, "vl3_long_text", args.min_chars)
    if len(records) < args.min_records and args.fallback_records and Path(args.fallback_records).exists():
        for line in Path(args.fallback_records).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            row.setdefault("source_type", "fallback_records")
            row.setdefault("source", "fallback_records")
            records.extend(make_records([row], profile, "fallback_records", args.min_chars))
        manifest["fallback_records"] = args.fallback_records

    out_jsonl = Path(args.output_jsonl) if args.output_jsonl else out_dir / "records.jsonl"
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    out_jsonl.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in records) + ("\n" if records else ""), encoding="utf-8")
    write_json(out_dir / "raw_segments.jsonl.meta.json", {"raw_segments": len(raw_rows)})
    (out_dir / "raw_segments.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in raw_rows), encoding="utf-8")
    manifest["records"] = len(records)
    manifest["output_jsonl"] = str(out_jsonl)
    write_json(out_dir / "source_manifest.json", manifest)
    report = f"""# VL3 Text Source Report

- 语种：{profile.get('language_name')}
- 原始段落：{len(raw_rows)}
- 可用 records：{len(records)}
- 输出：`{out_jsonl}`
- 结论：{'通过' if len(records) >= args.min_records else '不足'}
"""
    (out_dir / "text_source_report.md").write_text(report, encoding="utf-8")
    print(json.dumps({"records": len(records), "output_jsonl": str(out_jsonl), "pass": len(records) >= args.min_records}, ensure_ascii=False, indent=2))
    return 0 if len(records) >= args.min_records else 1


if __name__ == "__main__":
    raise SystemExit(main())
