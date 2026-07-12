#!/usr/bin/env python3
"""Fill reviewed-content translation gaps during offline content preparation."""

import argparse
import concurrent.futures
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def atomic_write(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        for item in items:
            stream.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        temporary = Path(stream.name)
    os.replace(temporary, path)


def translate(text: str) -> str:
    query = urlencode({"client": "gtx", "sl": "en", "tl": "zh-TW", "dt": "t", "q": text})
    error = ""
    for attempt in range(3):
        result = subprocess.run(
            ["curl", "-fsS", "--max-time", "15", f"https://translate.googleapis.com/translate_a/single?{query}"],
            text=True,
            capture_output=True,
            check=False,
        )
        if not result.returncode:
            payload = json.loads(result.stdout)
            translated = "".join(part[0] for part in payload[0] if part and part[0]).strip()
            if translated:
                return translated
            error = "Google Translate returned no text"
        else:
            error = result.stderr.strip()
        time.sleep(attempt + 1)
    raise RuntimeError(f"Google Translate failed: {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    requested = read_jsonl(args.work_dir / "translation-input.jsonl")
    output = args.work_dir / "translation-output.jsonl"
    translated = {item["id"]: item for item in read_jsonl(output)}
    missing = [item for item in requested if item["id"] not in translated]
    if any(not item["id"].endswith("::meaning") for item in missing):
        raise RuntimeError("only meaning translation gaps may use Google Translate")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(translate, item["text"]): item for item in missing}
        for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
            item = futures[future]
            try:
                translated[item["id"]] = {"id": item["id"], "text": future.result()}
            except Exception:
                atomic_write(output, sorted(translated.values(), key=lambda item: item["id"]))
                raise
            if completed % 25 == 0 or completed == len(missing):
                atomic_write(output, sorted(translated.values(), key=lambda item: item["id"]))
                print(json.dumps({"translated": completed, "total": len(translated)}, sort_keys=True), flush=True)
    items = sorted(translated.values(), key=lambda item: item["id"])
    atomic_write(output, items)
    print(json.dumps({"translated": len(missing), "total": len(items)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
