# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx[brotli]>=0.28,<1"]
# ///
"""从已核实的来源清单下载校徽；uv run scripts/fetch_logos.py。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "logo-sources.json"
OUTPUT = ROOT / "public" / "logos"
MAP = ROOT / "src" / "lib" / "logos.json"


def image_extension(content: bytes) -> str:
    """检查文件签名，拒绝将错误页保存为校徽。"""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if content.startswith(b"\x00\x00\x01\x00"):
        return "ico"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "webp"
    raise ValueError("来源未返回受支持的校徽图片")


def download(entry: dict[str, Any], refresh: bool) -> dict[str, Any]:
    identifier = entry["schoolId"]
    if not re.fullmatch(r"[a-z0-9-]+", identifier):
        raise ValueError(f"无效学校 ID：{identifier}")
    existing = OUTPUT / Path(entry.get("localPath", "missing")).name
    if not refresh and existing.is_file():
        return entry
    if not entry.get("imageUrl"):
        return entry
    try:
        with httpx.Client(
            timeout=25,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0", "Referer": entry["sourcePage"]},
        ) as client:
            response = client.get(entry["imageUrl"])
            response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError("校徽图片超过 2 MB，请先核对来源")
        extension = image_extension(response.content)
        destination = OUTPUT / f"{identifier}.{extension}"
        destination.write_bytes(response.content)
        return {
            **entry,
            "localPath": f"logos/{destination.name}",
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "downloadedAt": datetime.now(timezone.utc).isoformat(),
            "status": "available",
            "error": None,
        }
    except (httpx.HTTPError, OSError, ValueError) as error:
        # 保留旧图片及映射，单个来源失败不影响其他校徽。
        return {**entry, "status": "available" if existing.is_file() else "unavailable", "error": str(error)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="重新下载已有校徽")
    args = parser.parse_args()
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda entry: download(entry, args.refresh), entries))
    mapping = {
        entry["schoolId"]: entry["localPath"]
        for entry in results
        if entry.get("localPath") and (ROOT / "public" / entry["localPath"]).is_file()
    }
    MANIFEST.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MAP.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"本地校徽 {len(mapping)}/{len(results)}")
    for entry in results:
        if entry.get("error"):
            print(f"{entry['schoolId']}: {entry['error']}")


if __name__ == "__main__":
    main()
