---
name: brightbean-studio-agent
description: Use when you need to publish AI-generated images, videos, or post drafts into a running BrightBean Studio deployment. Triggers on requests like "upload to Brightbean", "save this image to the figus media library", "create a draft post in Brightbean", "send the generated image to the social-media studio", "push these assets to my Brightbean workspace", or any instruction to push generated content into a connected BrightBean instance. Handles authentication, single-asset and multi-asset upload, processing-status polling, draft-post creation with per-platform caption overrides, error recovery, and verification.
---

# BrightBean Studio Agent

## Overview

Push AI-generated images, videos, and draft posts into a running BrightBean
Studio via its REST API. **You always work through the public REST API,
never directly against the studio's database or storage.**

## Core principle

**Read configuration → verify with `/whoami` → upload → poll → (optional)
draft post → tell the user where to look.** Never claim "done" before the
verification step.

## Setup (first run only)

1. **Look for config.** In this order:
   - `BRIGHTBEAN_URL` and `BRIGHTBEAN_API_KEY` environment variables
   - `~/.config/brightbean-agent/.env` (parse `KEY=VALUE` lines)
   - If both missing, ask the user once: "What's your BrightBean URL? (e.g. https://socials.figus.ai)" and "Paste your API key (starts with `bbs_`):". Persist to `~/.config/brightbean-agent/.env`, then `chmod 600` the file.

2. **Verify with /whoami.** Call `GET ${BRIGHTBEAN_URL}/api/v1/whoami/` with `Authorization: Bearer ${BRIGHTBEAN_API_KEY}`. Expect 200 with `{"scope": "workspace" | "organization", "organization_id": ..., "workspace_id": ... | null, ...}`. Cache the response to `~/.config/brightbean-agent/whoami.json`.

3. **Refuse to continue** if `/whoami` returns non-200 — re-prompt for the key and retry once before surfacing the error to the user.

The cached `whoami.json` lets subsequent runs skip the network round-trip. Re-run `/whoami` whenever you see a 403 `forbidden_scope` to refresh.

## Workflow: upload a single image

```python
import httpx, os, json

BRIGHTBEAN_URL = os.environ["BRIGHTBEAN_URL"].rstrip("/")
API_KEY = os.environ["BRIGHTBEAN_API_KEY"]
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Pull workspace_id from the cached whoami
with open(os.path.expanduser("~/.config/brightbean-agent/whoami.json")) as f:
    whoami = json.load(f)
WS_ID = whoami["workspace_id"]    # None for org-shared keys
ORG_ID = whoami["organization_id"]

# Pick base URL by scope
if WS_ID:
    base = f"{BRIGHTBEAN_URL}/api/v1/workspaces/{WS_ID}/media"
else:
    base = f"{BRIGHTBEAN_URL}/api/v1/organizations/{ORG_ID}/media"

# Validate locally first
import os
path = "./generated.png"
size = os.path.getsize(path)
assert size <= 20 * 1024 * 1024, f"Image > 20 MB ({size} bytes)"

with open(path, "rb") as f:
    resp = httpx.post(
        f"{base}/assets/",
        headers=HEADERS,
        files={"file": (os.path.basename(path), f, "image/png")},
        data={
            "alt_text": "A cat sitting on a red rug, photorealistic",
            "title": "Campaign A — hero shot 1",
            "tags": "campaign-a,hero,cats",
            "source": "agent",
            "source_url": "https://example.com/generation/run-xyz",
            "attribution": "Stable Diffusion XL 1.0",
        },
        timeout=60.0,
    )
resp.raise_for_status()
asset = resp.json()
print(f"Uploaded asset {asset['id']} (status: {asset['processing_status']})")
```

## Workflow: poll for processing

After every upload, poll until `processing_status == "COMPLETED"`. The
studio generates a thumbnail and extracts metadata in the background; the
poll is fast (images <5s, videos <30s).

```python
import time

def wait_for_processing(asset_id, *, max_seconds=120):
    deadline = time.time() + max_seconds
    delay = 1.0
    while time.time() < deadline:
        r = httpx.get(f"{base}/assets/{asset_id}/", headers=HEADERS, timeout=10.0)
        r.raise_for_status()
        status = r.json()["processing_status"]
        if status == "COMPLETED":
            return r.json()
        if status == "FAILED":
            raise RuntimeError(f"Processing failed for {asset_id}")
        time.sleep(delay)
        delay = min(delay * 1.5, 8.0)
    raise TimeoutError(f"Processing did not complete in {max_seconds}s for {asset_id}")

completed = wait_for_processing(asset["id"])
print(f"Thumbnail: {completed['thumbnail_url']}")
```

## Workflow: upload a video

Same as images but with a longer cap (1 GB) and longer poll window (5 min).

```python
path = "./generated.mp4"
size = os.path.getsize(path)
assert size <= 1024 * 1024 * 1024, f"Video > 1 GB ({size} bytes)"

with open(path, "rb") as f:
    resp = httpx.post(
        f"{base}/assets/",
        headers=HEADERS,
        files={"file": (os.path.basename(path), f, "video/mp4")},
        data={
            "alt_text": "Product spinning on a white background",
            "title": "Campaign A — product 360",
            "tags": "campaign-a,product,360",
            "source": "agent",
            "attribution": "Sora 2",
        },
        timeout=600.0,   # generous; you're streaming megabytes
    )
resp.raise_for_status()
video = resp.json()
completed = wait_for_processing(video["id"], max_seconds=300)
```

## Workflow: create a draft post

After all assets are `COMPLETED`, create a draft post with a caption and
target platforms. Only available on workspace-scoped keys (drafts always
belong to a workspace).

```python
import httpx
draft_resp = httpx.post(
    f"{BRIGHTBEAN_URL}/api/v1/workspaces/{WS_ID}/posts/drafts/",
    headers={**HEADERS, "Content-Type": "application/json"},
    json={
        "title": "Campaign A teaser",
        "caption": "New drop tomorrow. Link in bio. 🎯",
        "asset_ids": [asset["id"], video["id"]],   # order preserved
        "platforms": ["instagram_login", "linkedin_company"],
        "platform_captions": {
            # Optional per-platform overrides — fall back to `caption` if missing
            "linkedin_company": "Excited to announce our new collection — available tomorrow. Click the bio link for early access."
        },
        "tags": ["campaign-a", "spring-2026"],
        "schedule_at": None,   # leave human to pick a slot, OR pass ISO-8601
    },
    timeout=30.0,
)
draft_resp.raise_for_status()
draft = draft_resp.json()
print(f"Draft created. Review at: {BRIGHTBEAN_URL}{draft['compose_url']}")
```

The full list of allowed platform values (must match a connected social
account in the workspace): `facebook`, `instagram`, `instagram_login`,
`linkedin_personal`, `linkedin_company`, `tiktok`, `youtube`, `pinterest`,
`threads`, `bluesky`, `google_business`, `mastodon`. If any requested
platform has no connected account in the workspace, the API returns
`422 no_connected_account_for_platforms` with the unmatched list — surface
that to the user; only they can connect more accounts.

## Error-handling matrix

| Status | Body `error` | What to do |
|---|---|---|
| 401 | `missing_or_malformed_authorization` | Re-prompt user for key; retry once |
| 401 | `invalid_token` | Key wrong/revoked. Re-prompt; retry once |
| 401 | `expired_token` | Tell user to mint a new key; stop |
| 403 | `forbidden_scope` | Re-fetch `/whoami`, refresh cache, retry once |
| 403 | `workspace_key_required` | Use workspace endpoints (your key is workspace-scoped); fix URL |
| 403 | `org_key_required` | Use organization endpoints; fix URL |
| 422 | `file_required` | Local bug — you didn't attach the file |
| 422 | `validation_failed` | File too big or wrong MIME — surface the response details to the user |
| 422 | `folder_not_found` | Re-fetch the folders list; reconcile |
| 422 | `no_connected_account_for_platforms` | Tell user to connect the listed platforms in BrightBean; stop |
| 409 | `asset_in_use` | Asset is on a scheduled post — surface the post IDs |
| 429 | (rate limit) | Back off 60s, retry once. If still 429, stop and tell user. |
| 5xx | any | Don't retry. Tell user, include `key_prefix` so admin can correlate in logs. |

## Verification before declaring "done"

After every successful action:

1. Asset upload: report `asset["id"]` AND the studio URL `{BRIGHTBEAN_URL}/workspace/{WS_ID}/media/` (or `/organizations/media/shared/` for org-shared keys) so the user can visually confirm.
2. Draft post: report `draft["compose_url"]` AND include it as a clickable URL in the response.
3. Never claim success based only on a 2xx response — also confirm `processing_status == "COMPLETED"` for uploads.

## Constraints / gotchas

- **Workspace keys can see org-shared assets when listing**, but cannot
  modify them. Match the asset's `workspace_id` to your `whoami` workspace
  before attempting PATCH/DELETE.
- **Folder IDs are workspace- or org-scoped**, not cross-scope. Listing
  folders from one URL family doesn't return folders from the other.
- **`platforms` is array of platform strings**, not social-account IDs.
  Many social accounts can be connected on the same platform — the studio
  will create a PlatformPost for *each* connected account matching each
  listed platform.
- **`schedule_at` is ISO-8601 with timezone** (e.g. `"2026-06-01T15:00:00-04:00"`). Naive datetimes are rejected.

## Companion files

Three runnable example scripts live next to this skill at
`brightbean-studio-agent/examples/`. Copy them into your project if you
want a typed starting point:

- `upload_image.py` — single-image upload + poll
- `upload_video.py` — single-video upload + longer poll
- `create_draft.py` — multi-asset draft post with per-platform captions

## Real-world impact

When this skill is loaded, a content-generation Claude Code session can:

1. Generate 4 images for a campaign (DALL-E, SDXL, Midjourney, etc.).
2. Upload each one with `source="agent"` and rich `alt_text`.
3. Create a draft post that targets Instagram + LinkedIn with per-platform
   caption variants.
4. Hand the human a `compose_url` for review.

End-to-end, with no manual file moving, no manual caption pasting, no
manual workspace targeting.
