#!/usr/bin/env python3
"""Create a draft post in BrightBean Studio targeting specific platforms.

Assumes the assets have already been uploaded and are COMPLETED. Run
``upload_image.py`` / ``upload_video.py`` first, collect the returned
asset IDs, then pass them to this script.

Usage:
    BRIGHTBEAN_URL=https://socials.figus.ai \\
    BRIGHTBEAN_API_KEY=bbs_... \\
    python create_draft.py \\
        "New product drop tomorrow. Link in bio." \\
        "instagram_login,linkedin_company" \\
        "uuid-1,uuid-2"
"""

from __future__ import annotations

import json
import os
import sys

import httpx

CONFIG = os.path.expanduser("~/.config/brightbean-agent")


def _load_whoami(base_url: str, headers: dict) -> dict:
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


def create(caption: str, platforms: list[str], asset_ids: list[str], *, schedule_at: str | None = None) -> dict:
    base_url = os.environ["BRIGHTBEAN_URL"].rstrip("/")
    headers = {
        "Authorization": f"Bearer {os.environ['BRIGHTBEAN_API_KEY']}",
        "Content-Type": "application/json",
    }
    whoami = _load_whoami(base_url, headers)
    if not whoami.get("workspace_id"):
        raise SystemExit("Draft posts require a workspace-scoped API key; this key is org-shared.")

    payload = {
        "caption": caption,
        "asset_ids": asset_ids,
        "platforms": platforms,
        "tags": [],
        "schedule_at": schedule_at,
    }
    r = httpx.post(
        f"{base_url}/api/v1/workspaces/{whoami['workspace_id']}/posts/drafts/",
        headers=headers,
        json=payload,
        timeout=30.0,
    )
    if r.status_code == 422:
        # Especially useful when one of the platforms has no connected account
        print(f"422 — {r.json()}", file=sys.stderr)
        raise SystemExit(1)
    r.raise_for_status()
    draft = r.json()
    full_url = f"{base_url}{draft['compose_url']}"
    print(f"Draft created: {draft['id']}")
    print(f"Review at: {full_url}")
    return draft


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: create_draft.py CAPTION PLATFORMS_CSV ASSET_IDS_CSV [SCHEDULE_AT_ISO]", file=sys.stderr)
        raise SystemExit(2)
    create(
        caption=sys.argv[1],
        platforms=[p.strip() for p in sys.argv[2].split(",") if p.strip()],
        asset_ids=[a.strip() for a in sys.argv[3].split(",") if a.strip()],
        schedule_at=sys.argv[4] if len(sys.argv) > 4 else None,
    )
