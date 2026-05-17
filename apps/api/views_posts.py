"""Composer draft-post REST endpoints for the external-agent API.

Single supported scope today: workspace. An agent provides a caption,
asset_ids, and target platforms; we create a Post + PlatformPost rows
(one per matched, connected social account in the workspace) + PostMedia
rows (preserving the asset_ids order). Mirrors the existing browser
``idea_create_post`` flow in apps.composer.views.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from apps.composer.models import PlatformPost, Post, PostMedia
from apps.media_library.models import MediaAsset
from apps.social_accounts.models import SocialAccount

from .decorators import require_api_key
from .serializers import draft_post_to_dict
from .views_media import _enforce_workspace_scope

logger = logging.getLogger(__name__)


def _parse_iso8601(value):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        raise ValueError(f"Invalid ISO8601 datetime: {value!r}")
    return dt


def _compose_url(workspace_id, post_id):
    return reverse("composer:compose_edit", kwargs={"workspace_id": workspace_id, "post_id": post_id})


@csrf_exempt
@require_http_methods(["GET", "POST"])
@ratelimit(key="header:authorization", rate="600/h", block=True)
@require_api_key
def workspace_drafts(request, workspace_id):
    err = _enforce_workspace_scope(request, workspace_id)
    if err:
        return err

    if request.method == "POST":
        return _create_draft(request)

    # GET — list this workspace's drafts (paginated)
    qs = (
        Post.objects.filter(workspace=request.workspace)
        .prefetch_related("platform_posts__social_account", "media_attachments")
        .order_by("-created_at")
    )
    from django.core.paginator import EmptyPage, Paginator

    try:
        page = max(1, int(request.GET.get("page", "1")))
        page_size = min(200, max(1, int(request.GET.get("page_size", "50"))))
    except ValueError:
        return JsonResponse({"error": "invalid_pagination"}, status=422)

    paginator = Paginator(qs, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        return JsonResponse({"results": [], "page": page, "page_size": page_size, "total": paginator.count})

    return JsonResponse(
        {
            "results": [
                draft_post_to_dict(p, compose_url=_compose_url(request.workspace.id, p.id))
                for p in page_obj.object_list
            ],
            "page": page,
            "page_size": page_size,
            "total": paginator.count,
            "has_next": page_obj.has_next(),
        }
    )


def _create_draft(request):
    try:
        payload = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"error": "invalid_json"}, status=422)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "invalid_json"}, status=422)

    caption = (payload.get("caption") or "").strip()
    title = (payload.get("title") or "").strip()
    asset_ids = payload.get("asset_ids") or []
    platforms = payload.get("platforms") or []
    platform_captions = payload.get("platform_captions") or {}
    tags = payload.get("tags") or []
    schedule_at_raw = payload.get("schedule_at")

    if not isinstance(asset_ids, list):
        return JsonResponse({"error": "asset_ids_must_be_list"}, status=422)
    if not isinstance(platforms, list) or not platforms:
        return JsonResponse({"error": "platforms_must_be_nonempty_list"}, status=422)
    if not isinstance(platform_captions, dict):
        return JsonResponse({"error": "platform_captions_must_be_dict"}, status=422)
    if not isinstance(tags, list):
        return JsonResponse({"error": "tags_must_be_list"}, status=422)

    try:
        schedule_at = _parse_iso8601(schedule_at_raw)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_schedule_at", "details": str(exc)}, status=422)

    # Validate asset_ids — must exist in this workspace (or be org-shared)
    assets = list(
        MediaAsset.objects.filter(
            id__in=asset_ids,
            organization=request.org,
        )
    )
    asset_id_strs = {str(a.id) for a in assets}
    for aid in asset_ids:
        if str(aid) not in asset_id_strs:
            return JsonResponse({"error": "asset_not_found", "asset_id": str(aid)}, status=422)
    for a in assets:
        if a.workspace_id not in (None, request.workspace.id):
            return JsonResponse({"error": "asset_not_in_scope", "asset_id": str(a.id)}, status=403)

    # Resolve platforms → connected SocialAccount rows in the workspace
    social_accounts = list(
        SocialAccount.objects.filter(
            workspace=request.workspace,
            platform__in=platforms,
            connection_status=SocialAccount.ConnectionStatus.CONNECTED,
        )
    )
    matched_platforms = {a.platform for a in social_accounts}
    unmatched = [p for p in platforms if p not in matched_platforms]
    if unmatched:
        return JsonResponse(
            {
                "error": "no_connected_account_for_platforms",
                "unmatched_platforms": unmatched,
            },
            status=422,
        )

    # Preserve the order the agent supplied asset_ids in
    asset_id_to_pos = {str(aid): i for i, aid in enumerate(asset_ids)}

    with transaction.atomic():
        post = Post.objects.create(
            workspace=request.workspace,
            author=None,  # API key, not a user
            title=title,
            caption=caption,
            tags=[str(t).strip() for t in tags if str(t).strip()],
            scheduled_at=schedule_at,
        )

        if asset_ids:
            PostMedia.objects.bulk_create(
                [
                    PostMedia(post=post, media_asset_id=a.id, position=asset_id_to_pos[str(a.id)])
                    for a in assets
                ]
            )

        PlatformPost.objects.bulk_create(
            [
                PlatformPost(
                    post=post,
                    social_account=account,
                    platform_specific_caption=platform_captions.get(account.platform),
                    scheduled_at=schedule_at,
                )
                for account in social_accounts
            ]
        )

    post.refresh_from_db()
    return JsonResponse(
        draft_post_to_dict(post, compose_url=_compose_url(request.workspace.id, post.id)),
        status=201,
    )


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
@ratelimit(key="header:authorization", rate="600/h", block=True)
@require_api_key
def workspace_draft_detail(request, workspace_id, post_id):
    err = _enforce_workspace_scope(request, workspace_id)
    if err:
        return err

    try:
        post = (
            Post.objects.filter(workspace=request.workspace)
            .prefetch_related("platform_posts__social_account", "media_attachments")
            .get(id=post_id)
        )
    except (Post.DoesNotExist, ValueError):
        return JsonResponse({"error": "post_not_found"}, status=404)

    if request.method == "GET":
        return JsonResponse(draft_post_to_dict(post, compose_url=_compose_url(request.workspace.id, post.id)))

    # DELETE — only allowed while still draft / pending-review / changes_requested
    if post.status not in ("draft", "pending_review", "pending_client", "changes_requested", "rejected"):
        return JsonResponse(
            {"error": "post_not_deletable_in_current_status", "status": post.status},
            status=409,
        )
    post.delete()
    return JsonResponse({}, status=204)
