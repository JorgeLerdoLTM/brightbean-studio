"""Media library REST endpoints for the external-agent API.

Two parallel surfaces:

  * Workspace-scoped: ``/api/v1/workspaces/<workspace_id>/media/...``
  * Org-shared:      ``/api/v1/organizations/<org_id>/media/...``

Every view is ``@csrf_exempt`` + ratelimited + ``@require_api_key``. The
shared service layer (``apps.media_library.services``) is reused verbatim so
storage backend, MIME/size validation, and post-upload processing all match
the existing browser-upload flow.
"""

from __future__ import annotations

import json
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from apps.media_library.models import MediaAsset, MediaFolder
from apps.media_library.services import (
    ProtectedAssetError,
    create_asset,
    create_folder,
    delete_asset,
)
from apps.media_library.tasks import process_media_asset

from .decorators import require_api_key
from .notifications import notify_agent_upload
from .serializers import asset_to_dict, folder_to_dict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------

def _enforce_workspace_scope(request, url_workspace_id):
    """Workspace endpoint: key must be workspace-scoped AND match the URL."""
    if request.workspace is None:
        return JsonResponse({"error": "workspace_key_required"}, status=403)
    if str(request.workspace.id) != str(url_workspace_id):
        return JsonResponse({"error": "forbidden_scope"}, status=403)
    return None


def _enforce_org_scope(request, url_org_id):
    """Org-shared endpoint: key must be org-scoped AND org IDs match."""
    if request.workspace is not None:
        return JsonResponse({"error": "org_key_required"}, status=403)
    if str(request.org.id) != str(url_org_id):
        return JsonResponse({"error": "forbidden_scope"}, status=403)
    return None


# ---------------------------------------------------------------------------
# Asset metadata helpers
# ---------------------------------------------------------------------------

def _parse_tags(raw):
    """Accept either a JSON array or a comma-separated string."""
    if not raw:
        return []
    if raw.startswith("["):
        try:
            tags = json.loads(raw)
            if isinstance(tags, list):
                return [str(t).strip() for t in tags if str(t).strip()]
        except (ValueError, TypeError):
            pass
    return [t.strip() for t in raw.split(",") if t.strip()]


def _apply_metadata_to_new_asset(asset, request):
    """Stamp agent-provided metadata onto a freshly-created asset."""
    asset.alt_text = request.POST.get("alt_text", "") or ""
    asset.title = request.POST.get("title", "") or ""
    asset.tags = _parse_tags(request.POST.get("tags", ""))
    asset.source = request.POST.get("source", "") or "agent"
    asset.source_url = request.POST.get("source_url", "") or ""
    asset.attribution = request.POST.get("attribution", "") or ""
    asset.save(
        update_fields=[
            "alt_text",
            "title",
            "tags",
            "source",
            "source_url",
            "attribution",
            "updated_at",
        ]
    )


def _resolve_folder(request, *, organization, workspace):
    folder_id = request.POST.get("folder_id")
    if not folder_id:
        return None, None
    try:
        qs = MediaFolder.objects.filter(id=folder_id, organization=organization)
        if workspace is None:
            qs = qs.filter(workspace__isnull=True)
        else:
            qs = qs.filter(workspace=workspace)
        return qs.get(), None
    except (MediaFolder.DoesNotExist, ValueError):
        return None, JsonResponse({"error": "folder_not_found"}, status=422)


def _create_asset_for_scope(request, *, organization, workspace):
    file_obj = request.FILES.get("file")
    if not file_obj:
        return None, JsonResponse({"error": "file_required"}, status=422)

    folder, err = _resolve_folder(request, organization=organization, workspace=workspace)
    if err:
        return None, err

    try:
        asset = create_asset(
            organization=organization,
            workspace=workspace,
            uploaded_file=file_obj,
            uploaded_by=None,
            folder=folder,
        )
    except ValidationError as exc:
        return None, JsonResponse(
            {"error": "validation_failed", "details": getattr(exc, "messages", str(exc))},
            status=422,
        )

    _apply_metadata_to_new_asset(asset, request)
    process_media_asset(str(asset.id))
    notify_agent_upload(asset, request.api_key)
    return asset, None


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def _list_assets(request, *, organization, workspace):
    """Return a paginated asset list scoped to the right tenant."""
    if workspace is None:
        qs = MediaAsset.objects.shared_only(organization.id)
    else:
        qs = MediaAsset.objects.for_workspace_with_shared(workspace.id, organization.id)

    folder_id = request.GET.get("folder_id")
    if folder_id == "null":
        qs = qs.filter(folder__isnull=True)
    elif folder_id:
        qs = qs.filter(folder_id=folder_id)

    media_type = request.GET.get("media_type")
    if media_type:
        qs = qs.filter(media_type=media_type)

    tag = request.GET.get("tag")
    if tag:
        qs = qs.filter(tags__contains=[tag])

    search = request.GET.get("search")
    if search:
        from django.db.models import Q

        qs = qs.filter(Q(filename__icontains=search) | Q(title__icontains=search) | Q(alt_text__icontains=search))

    qs = qs.order_by("-created_at")

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
            "results": [asset_to_dict(a) for a in page_obj.object_list],
            "page": page,
            "page_size": page_size,
            "total": paginator.count,
            "has_next": page_obj.has_next(),
        }
    )


# ---------------------------------------------------------------------------
# Asset detail (GET / PATCH / DELETE)
# ---------------------------------------------------------------------------

def _get_asset_or_404(*, asset_id, organization, workspace):
    try:
        asset = MediaAsset.objects.get(id=asset_id, organization=organization)
    except (MediaAsset.DoesNotExist, ValueError):
        return None
    if workspace is None:
        # org-shared scope can only touch workspace=NULL assets
        if asset.workspace_id is not None:
            return None
    else:
        # workspace scope can see its own workspace's assets plus shared (workspace=NULL)
        if asset.workspace_id not in (None, workspace.id):
            return None
    return asset


def _patch_asset(request, asset):
    try:
        payload = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"error": "invalid_json"}, status=422)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "invalid_json"}, status=422)

    updated_fields = []
    if "alt_text" in payload:
        asset.alt_text = str(payload["alt_text"] or "")
        updated_fields.append("alt_text")
    if "title" in payload:
        asset.title = str(payload["title"] or "")
        updated_fields.append("title")
    if "tags" in payload:
        tags = payload["tags"]
        if isinstance(tags, list):
            asset.tags = [str(t).strip() for t in tags if str(t).strip()]
        elif isinstance(tags, str):
            asset.tags = _parse_tags(tags)
        else:
            return JsonResponse({"error": "tags_must_be_list_or_string"}, status=422)
        updated_fields.append("tags")
    if "folder_id" in payload:
        new_folder_id = payload["folder_id"]
        if new_folder_id is None:
            asset.folder = None
        else:
            try:
                qs = MediaFolder.objects.filter(id=new_folder_id, organization=asset.organization)
                if asset.workspace_id is None:
                    qs = qs.filter(workspace__isnull=True)
                else:
                    qs = qs.filter(workspace_id=asset.workspace_id)
                asset.folder = qs.get()
            except (MediaFolder.DoesNotExist, ValueError):
                return JsonResponse({"error": "folder_not_found"}, status=422)
        updated_fields.append("folder")

    if updated_fields:
        updated_fields.append("updated_at")
        asset.save(update_fields=updated_fields)
    return JsonResponse(asset_to_dict(asset))


def _delete_asset_view(asset):
    try:
        delete_asset(asset)
    except ProtectedAssetError as exc:
        return JsonResponse(
            {
                "error": "asset_in_use",
                "referencing_posts": [str(p.id) for p in exc.referencing_posts],
            },
            status=409,
        )
    return JsonResponse({}, status=204)


# ---------------------------------------------------------------------------
# Workspace endpoints
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET", "POST"])
@ratelimit(key="header:authorization", rate="600/h", block=True)
@require_api_key
def workspace_assets(request, workspace_id):
    err = _enforce_workspace_scope(request, workspace_id)
    if err:
        return err

    if request.method == "POST":
        asset, err = _create_asset_for_scope(request, organization=request.org, workspace=request.workspace)
        if err:
            return err
        return JsonResponse(asset_to_dict(asset), status=201)

    return _list_assets(request, organization=request.org, workspace=request.workspace)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
@ratelimit(key="header:authorization", rate="600/h", block=True)
@require_api_key
def workspace_asset_detail(request, workspace_id, asset_id):
    err = _enforce_workspace_scope(request, workspace_id)
    if err:
        return err
    asset = _get_asset_or_404(asset_id=asset_id, organization=request.org, workspace=request.workspace)
    if asset is None:
        return JsonResponse({"error": "asset_not_found"}, status=404)

    if request.method == "GET":
        return JsonResponse(asset_to_dict(asset))
    if request.method == "PATCH":
        return _patch_asset(request, asset)
    return _delete_asset_view(asset)


@csrf_exempt
@require_http_methods(["GET", "POST"])
@ratelimit(key="header:authorization", rate="600/h", block=True)
@require_api_key
def workspace_folders(request, workspace_id):
    err = _enforce_workspace_scope(request, workspace_id)
    if err:
        return err

    if request.method == "POST":
        return _create_folder_view(request, organization=request.org, workspace=request.workspace)

    folders = MediaFolder.objects.filter(organization=request.org, workspace=request.workspace).order_by("name")
    return JsonResponse({"results": [folder_to_dict(f) for f in folders]})


# ---------------------------------------------------------------------------
# Org-shared endpoints
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET", "POST"])
@ratelimit(key="header:authorization", rate="600/h", block=True)
@require_api_key
def org_assets(request, org_id):
    err = _enforce_org_scope(request, org_id)
    if err:
        return err

    if request.method == "POST":
        asset, err = _create_asset_for_scope(request, organization=request.org, workspace=None)
        if err:
            return err
        return JsonResponse(asset_to_dict(asset), status=201)

    return _list_assets(request, organization=request.org, workspace=None)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
@ratelimit(key="header:authorization", rate="600/h", block=True)
@require_api_key
def org_asset_detail(request, org_id, asset_id):
    err = _enforce_org_scope(request, org_id)
    if err:
        return err
    asset = _get_asset_or_404(asset_id=asset_id, organization=request.org, workspace=None)
    if asset is None:
        return JsonResponse({"error": "asset_not_found"}, status=404)

    if request.method == "GET":
        return JsonResponse(asset_to_dict(asset))
    if request.method == "PATCH":
        return _patch_asset(request, asset)
    return _delete_asset_view(asset)


@csrf_exempt
@require_http_methods(["GET", "POST"])
@ratelimit(key="header:authorization", rate="600/h", block=True)
@require_api_key
def org_folders(request, org_id):
    err = _enforce_org_scope(request, org_id)
    if err:
        return err

    if request.method == "POST":
        return _create_folder_view(request, organization=request.org, workspace=None)

    folders = MediaFolder.objects.filter(organization=request.org, workspace__isnull=True).order_by("name")
    return JsonResponse({"results": [folder_to_dict(f) for f in folders]})


# ---------------------------------------------------------------------------
# Shared folder-create logic
# ---------------------------------------------------------------------------

def _create_folder_view(request, *, organization, workspace):
    try:
        payload = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"error": "invalid_json"}, status=422)
    name = (payload.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name_required"}, status=422)

    parent = None
    parent_id = payload.get("parent_folder_id")
    if parent_id:
        try:
            qs = MediaFolder.objects.filter(id=parent_id, organization=organization)
            if workspace is None:
                qs = qs.filter(workspace__isnull=True)
            else:
                qs = qs.filter(workspace=workspace)
            parent = qs.get()
        except (MediaFolder.DoesNotExist, ValueError):
            return JsonResponse({"error": "parent_folder_not_found"}, status=422)

    try:
        folder = create_folder(organization, workspace, name, parent_folder=parent)
    except ValidationError as exc:
        return JsonResponse(
            {"error": "validation_failed", "details": getattr(exc, "messages", str(exc))},
            status=422,
        )
    return JsonResponse(folder_to_dict(folder), status=201)
