#!/usr/bin/env python3
"""Upload a single image to BrightBean Studio and wait for processing.

Usage:
    BRIGHTBEAN_URL=https://socials.figus.ai \\
    BRIGHTBEAN_API_KEY=bbs_... \\
    python upload_image.py path/to/image.png "alt text" "tag1,tag2"
"""

from __future__ import annotations

import json
import os
import sys
import time

import httpx

CONFIG = os.path.expanduser("~/.config/brightbean-agent")


def _load_whoami(base_url: str, headers: dict) -> dict:
    """Resolve scope. Use cached whoami if present, otherwise call /whoami."""
    cache_path = os.path.join(CONFIG, "whoami.json")
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            return json.load(f)
    r = httpx.get(f"{base_url}/api/v1/whoami/", headers=headers, timeout=10.0)
    r.raise_for_status()
    data = r.json()
    os.makedirs(CONFIG, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(data, f)
    return data


def _base_path(base_url: str, whoami: dict) -> str:
    if whoami["workspace_id"]:
        return f"{base_url}/api/v1/workspaces/{whoami['workspace_id']}/media"
    return f"{base_url}/api/v1/organizations/{whoami['organization_id']}/media"


def upload(image_path: str, alt_text: str, tags_csv: str) -> dict:
    base_url = os.environ["BRIGHTBEAN_URL"].rstrip("/")
    headers = {"Authorization": f"Bearer {os.environ['BRIGHTBEAN_API_KEY']}"}
    whoami = _load_whoami(base_url, headers)
    base = _base_path(base_url, whoami)

    size = os.path.getsize(image_path)
    if size > 20 * 1024 * 1024:
        raise SystemExit(f"Image > 20 MB ({size:,} bytes) — refusing to upload")

    with open(image_path, "rb") as f:
        r = httpx.post(
            f"{base}/assets/",
            headers=headers,
            files={"file": (os.path.basename(image_path), f, _guess_mime(image_path))},
            data={
                "alt_text": alt_text,
                "title": os.path.basename(image_path),
                "tags": tags_csv,
                "source": "agent",
            },
            timeout=120.0,
        )
    r.raise_for_status()
    asset = r.json()
    print(f"Uploaded: {asset['id']}  (status: {asset['processing_status']})")

    # Poll until processing completes
    deadline = time.time() + 120
    delay = 1.0
    while time.time() < deadline:
        rr = httpx.get(f"{base}/assets/{asset['id']}/", headers=headers, timeout=10.0)
        rr.raise_for_status()
        status = rr.json()["processing_status"]
        if status == "COMPLETED":
            print(f"Processed. Thumbnail: {rr.json()['thumbnail_url']}")
            return rr.json()
        if status == "FAILED":
            raise SystemExit(f"Processing failed for {asset['id']}")
        time.sleep(delay)
        delay = min(delay * 1.5, 8.0)
    raise SystemExit(f"Processing did not finish in 120s for {asset['id']}")


def _guess_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
    }.get(ext, "application/octet-stream")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: upload_image.py PATH [ALT_TEXT] [TAGS_CSV]", file=sys.stderr)
        raise SystemExit(2)
    upload(
        sys.argv[1],
        sys.argv[2] if len(sys.argv) > 2 else "",
        sys.argv[3] if len(sys.argv) > 3 else "",
    )
