"""Helpers that fan an agent-activity event out to the right humans.

Recipients:

- **Workspace key** → all OrgMembership rows in the workspace's org with role
  in (owner, admin), plus all WorkspaceMembership owners of that workspace.
  (Two-way notification: org leadership and the workspace's own owners.)
- **Org-shared key** → all OrgMembership rows in the org with role in (owner, admin).

Notifications go in-app only by default. Users with email enabled for these
events in their preferences also get an email — the engine respects that.
"""

from __future__ import annotations

import logging

from apps.members.models import OrgMembership, WorkspaceMembership
from apps.notifications.engine import notify
from apps.notifications.models import EventType

logger = logging.getLogger(__name__)


def _admin_users(api_key):
    """Resolve the set of users to notify based on the key's scope."""
    user_ids: set = set()

    org_admins = OrgMembership.objects.filter(
        organization=api_key.organization,
        org_role__in=(OrgMembership.OrgRole.OWNER, OrgMembership.OrgRole.ADMIN),
    ).values_list("user_id", flat=True)
    user_ids.update(org_admins)

    if api_key.workspace_id is not None:
        ws_owners = WorkspaceMembership.objects.filter(
            workspace=api_key.workspace,
            workspace_role=WorkspaceMembership.WorkspaceRole.OWNER,
        ).values_list("user_id", flat=True)
        user_ids.update(ws_owners)

    if not user_ids:
        return []

    from apps.accounts.models import User

    return list(User.objects.filter(id__in=user_ids, is_active=True))


def notify_agent_upload(asset, api_key):
    """Fire an in-app notification after an agent uploads an asset.

    Failures here are swallowed and logged — a notification glitch must
    never break the upload flow itself.
    """
    workspace_label = api_key.workspace.name if api_key.workspace_id else "Shared Library"
    title = f"Agent uploaded {asset.filename} to {workspace_label}"
    body = f"{asset.filename} ({asset.file_size_display}, {asset.media_type}) via API key {api_key.name}."
    data = {
        "asset_id": str(asset.id),
        "api_key_id": str(api_key.id),
        "api_key_name": api_key.name,
        "workspace_id": str(asset.workspace_id) if asset.workspace_id else None,
        "organization_id": str(asset.organization_id),
    }
    for user in _admin_users(api_key):
        try:
            notify(
                user=user,
                event_type=EventType.MEDIA_AGENT_UPLOADED,
                title=title,
                body=body,
                data=data,
            )
        except Exception:
            logger.exception("Failed to notify %s about agent upload %s", user.id, asset.id)


def notify_agent_draft(post, api_key):
    """Fire an in-app notification after an agent creates a draft post."""
    workspace_label = api_key.workspace.name if api_key.workspace_id else "Shared Library"
    title = f"Agent drafted a post in {workspace_label}"
    platforms = list(post.platform_posts.values_list("social_account__platform", flat=True))
    body = (
        f"Caption: {(post.caption[:80] + '…') if len(post.caption) > 80 else post.caption} "
        f"— targeting {', '.join(platforms) or '(no platforms)'}. Via API key {api_key.name}."
    )
    data = {
        "post_id": str(post.id),
        "api_key_id": str(api_key.id),
        "api_key_name": api_key.name,
        "workspace_id": str(post.workspace_id),
        "platforms": platforms,
    }
    for user in _admin_users(api_key):
        try:
            notify(
                user=user,
                event_type=EventType.POST_AGENT_DRAFTED,
                title=title,
                body=body,
                data=data,
            )
        except Exception:
            logger.exception("Failed to notify %s about agent draft %s", user.id, post.id)
