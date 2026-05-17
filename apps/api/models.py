"""Models for the public REST API.

Bearer tokens that an external agent presents to write into a specific
workspace's media library or compose drafts on its behalf. Tokens are stored
SHA-256 hashed; the raw value is shown to the human exactly once at creation.
"""

import hashlib
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.common.managers import OrgScopedManager


DEFAULT_SCOPES = ["media:read", "media:write", "posts:write"]


def _default_scopes():
    return list(DEFAULT_SCOPES)


def hash_token(raw_token: str) -> str:
    """SHA-256 hex digest of the raw bearer token. Used both at creation and
    on every authenticated request."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_raw_token() -> str:
    """Mint a fresh bearer token. Format: ``bbs_<40 url-safe chars>``."""
    return "bbs_" + secrets.token_urlsafe(30)


class APIKey(models.Model):
    """A tenant-scoped bearer token for the public REST API.

    - workspace=NULL  → org-shared key. Writes go to the shared library
      (assets with ``workspace_id IS NULL``) and the agent cannot touch
      workspace-scoped endpoints.
    - workspace set   → workspace key. Cannot touch the shared library.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Human-readable label, e.g. 'Acme content agent'.")

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="api_keys",
        null=True,
        blank=True,
        help_text="If set, the key is scoped to this workspace. If null, scope is the org-shared library.",
    )

    token_prefix = models.CharField(
        max_length=12,
        help_text="First 12 chars of the raw token, shown in the UI for identification.",
    )
    token_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="SHA-256 hex of the raw token. The raw token is never stored.",
    )
    scopes = models.JSONField(default=_default_scopes)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_keys_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = OrgScopedManager()

    class Meta:
        db_table = "api_keys"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=Q(workspace__isnull=True) | Q(workspace__organization=F("organization")),
                name="apikey_workspace_org_match",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "workspace"], name="apikey_org_ws_idx"),
        ]

    def __str__(self) -> str:
        scope = f"workspace={self.workspace_id}" if self.workspace_id else "org-shared"
        return f"APIKey({self.name}, {scope})"

    @property
    def scope_label(self) -> str:
        return "Workspace" if self.workspace_id else "Org-shared"

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None:
            from django.utils import timezone

            if self.expires_at <= timezone.now():
                return False
        return True

    @classmethod
    def issue(
        cls,
        *,
        name: str,
        organization,
        workspace=None,
        created_by=None,
        scopes=None,
        expires_at=None,
    ):
        """Create a new key and return ``(api_key_instance, raw_token)``.

        The raw token is returned exactly once. Persist it where the human
        can copy it; the database only keeps the hash.
        """
        raw_token = generate_raw_token()
        key = cls.objects.create(
            name=name,
            organization=organization,
            workspace=workspace,
            token_prefix=raw_token[:12],
            token_hash=hash_token(raw_token),
            scopes=scopes if scopes is not None else _default_scopes(),
            created_by=created_by,
            expires_at=expires_at,
        )
        return key, raw_token
