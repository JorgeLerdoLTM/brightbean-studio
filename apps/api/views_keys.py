"""Settings UI for managing API keys.

Two parallel surfaces, same model:

  * Workspace owners/managers: ``/workspace/<id>/settings/api-keys/``
    See/manage only keys scoped to this workspace.
  * Org owners/admins: ``/organizations/settings/api-keys/``
    See/manage every key in the org (workspace-scoped + shared).

HTMX-driven; on create the response renders the one-shot reveal modal so
the operator can copy the token exactly once.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.members.decorators import require_org_role, require_workspace_role
from apps.organizations.models import Organization
from apps.workspaces.models import Workspace

from .models import APIKey


# ---------------------------------------------------------------------------
# Workspace-scoped UI
# ---------------------------------------------------------------------------

@login_required
@require_workspace_role("manager")
@require_GET
def workspace_keys_index(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id, organization=request.org)
    keys = APIKey.objects.filter(organization=request.org, workspace=workspace).order_by("-created_at")
    return render(
        request,
        "api/keys_list.html",
        {
            "layout_template": "layouts/workspace_settings.html",
            "settings_active": "api_keys",
            "scope_label": "Workspace",
            "scope_subhead": f"Keys that can write into {workspace.name}'s media library and create drafts in this workspace.",
            "workspace": workspace,
            "organization": request.org,
            "keys": keys,
            "is_org_scope_page": False,
            "create_action_url": _ws_url(workspace.id, "create"),
            "revoke_action_url_pattern": "ws",
            "workspaces_for_scope_picker": None,
        },
    )


@login_required
@require_workspace_role("manager")
@require_POST
def workspace_keys_create(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id, organization=request.org)
    name = (request.POST.get("name") or "").strip()
    if not name:
        return HttpResponse('<div class="text-red-600 text-sm p-3">A name is required.</div>', status=422)

    key, raw_token = APIKey.issue(
        name=name,
        organization=request.org,
        workspace=workspace,
        created_by=request.user,
    )
    return render(
        request,
        "api/partials/new_api_key_token_modal.html",
        {"key": key, "raw_token": raw_token, "revoke_url": _ws_url(workspace.id, "revoke", key_id=key.id)},
    )


@login_required
@require_workspace_role("manager")
@require_POST
def workspace_keys_revoke(request, workspace_id, key_id):
    workspace = get_object_or_404(Workspace, id=workspace_id, organization=request.org)
    key = get_object_or_404(APIKey, id=key_id, organization=request.org, workspace=workspace)
    if key.revoked_at is None:
        key.revoked_at = timezone.now()
        key.save(update_fields=["revoked_at"])
    return HttpResponse(status=200, headers={"HX-Trigger": "apiKeyRevoked"})


# ---------------------------------------------------------------------------
# Org-scoped UI (sees every key in the org)
# ---------------------------------------------------------------------------

@login_required
@require_org_role("admin")
@require_GET
def org_keys_index(request):
    keys = (
        APIKey.objects.filter(organization=request.org)
        .select_related("workspace")
        .order_by("-created_at")
    )
    workspaces = Workspace.objects.filter(organization=request.org, is_archived=False).order_by("name")
    return render(
        request,
        "api/keys_list.html",
        {
            "layout_template": "layouts/settings.html",
            "settings_active": "api_keys",
            "scope_label": "Organization",
            "scope_subhead": "Every key in this organization — workspace-scoped and org-shared. Use the scope toggle when creating a new one.",
            "workspace": None,
            "organization": request.org,
            "keys": keys,
            "is_org_scope_page": True,
            "create_action_url": _org_url("create"),
            "revoke_action_url_pattern": "org",
            "workspaces_for_scope_picker": workspaces,
        },
    )


@login_required
@require_org_role("admin")
@require_POST
def org_keys_create(request):
    name = (request.POST.get("name") or "").strip()
    if not name:
        return HttpResponse('<div class="text-red-600 text-sm p-3">A name is required.</div>', status=422)

    workspace_id = (request.POST.get("workspace_id") or "").strip()
    workspace = None
    if workspace_id:
        try:
            workspace = Workspace.objects.get(id=workspace_id, organization=request.org)
        except (Workspace.DoesNotExist, ValueError):
            return HttpResponse('<div class="text-red-600 text-sm p-3">Invalid workspace.</div>', status=422)

    key, raw_token = APIKey.issue(
        name=name,
        organization=request.org,
        workspace=workspace,
        created_by=request.user,
    )
    return render(
        request,
        "api/partials/new_api_key_token_modal.html",
        {"key": key, "raw_token": raw_token, "revoke_url": _org_url("revoke", key_id=key.id)},
    )


@login_required
@require_org_role("admin")
@require_POST
def org_keys_revoke(request, key_id):
    key = get_object_or_404(APIKey, id=key_id, organization=request.org)
    if key.revoked_at is None:
        key.revoked_at = timezone.now()
        key.save(update_fields=["revoked_at"])
    return HttpResponse(status=200, headers={"HX-Trigger": "apiKeyRevoked"})


# ---------------------------------------------------------------------------
# URL helpers (used by templates via context vars to avoid hard-coding paths)
# ---------------------------------------------------------------------------

def _ws_url(workspace_id, action, *, key_id=None):
    if action == "create":
        return f"/workspace/{workspace_id}/settings/api-keys/create/"
    if action == "revoke":
        return f"/workspace/{workspace_id}/settings/api-keys/{key_id}/revoke/"
    return ""


def _org_url(action, *, key_id=None):
    if action == "create":
        return "/organizations/settings/api-keys/create/"
    if action == "revoke":
        return f"/organizations/settings/api-keys/{key_id}/revoke/"
    return ""
