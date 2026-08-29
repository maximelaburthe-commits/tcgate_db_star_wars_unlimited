"""Reproducible, resumable SWU image metadata and lightweight dHash audit.

The dHash is audit evidence only. It is not a TCGate matcher descriptor.
"""
import argparse
import concurrent.futures
import hashlib
import io
import json
import os
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CACHE_VERSION = 1
ANALYSIS_VERSION = 1


def cache_key(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def dhash(image):
    pixels = list(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS).getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return f"{bits:016x}"


def valid_cached(value, url):
    required = {"cacheVersion", "url", "httpStatus", "analysisVersion"}
    return isinstance(value, dict) and required <= value.keys() and value["cacheVersion"] == CACHE_VERSION and value["url"] == url


def load_cache(path, url):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if valid_cached(value, url) else None
    except (OSError, ValueError):
        return None


def analyze(url, cache_dir, timeout, retries):
    path = cache_dir / f"{cache_key(url)}.json"
    cached = load_cache(path, url)
    if cached is not None:
        return cached
    error = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers={"User-Agent": "TCGate-SWU-visual-audit/1"})
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            value = {
                "cacheVersion": CACHE_VERSION, "analysisVersion": ANALYSIS_VERSION,
                "url": url, "httpStatus": response.status_code, "contentType": content_type,
                "byteSize": len(response.content), "imageSha256": None, "visualHash": None,
                "width": None, "height": None, "error": None,
            }
            if response.ok:
                value["imageSha256"] = hashlib.sha256(response.content).hexdigest()
                with Image.open(io.BytesIO(response.content)) as image:
                    image.load()
                    value.update(width=image.width, height=image.height, visualHash=dhash(image))
            else:
                value["error"] = f"HTTP {response.status_code}"
            path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            return value
        except Exception as exc:  # network and decoder failures are audit data
            error = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(min(2 ** attempt, 5))
    value = {
        "cacheVersion": CACHE_VERSION, "analysisVersion": ANALYSIS_VERSION,
        "url": url, "httpStatus": None, "contentType": None, "byteSize": None,
        "imageSha256": None, "visualHash": None, "width": None, "height": None,
        "error": error,
    }
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache/swu-vision-audit")
    args = parser.parse_args()
    faces = json.loads((ROOT / "data/faces.json").read_text(encoding="utf-8"))
    urls = sorted({face["imageUrl"] for face in faces})
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        jobs = {executor.submit(analyze, url, args.cache_dir, args.timeout, args.retries): url for url in urls}
        for index, job in enumerate(concurrent.futures.as_completed(jobs), 1):
            url = jobs[job]
            results[url] = job.result()
            if index % 250 == 0 or index == len(jobs):
                ok = sum(bool(x.get("imageSha256")) for x in results.values())
                print(f"analyzed={index}/{len(jobs)} ok={ok} failed={index-ok}", flush=True)
    fingerprints = []
    for face in sorted(faces, key=lambda item: item["refId"]):
        result = results[face["imageUrl"]]
        fingerprints.append({
            "refId": face["refId"], "imageUrl": face["imageUrl"],
            **{key: result.get(key) for key in ("httpStatus", "contentType", "byteSize", "width", "height", "imageSha256", "visualHash", "error")},
            "analysisVersion": ANALYSIS_VERSION,
        })
    (ROOT / "data/visual-fingerprints.json").write_text(json.dumps(fingerprints, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"fingerprints={len(fingerprints)} successful={sum(bool(x['imageSha256']) for x in fingerprints)}")


if __name__ == "__main__":
    main()
