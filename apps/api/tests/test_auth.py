"""Tests for ``require_api_key`` decorator and the /whoami/ endpoint."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.api.models import APIKey
from apps.organizations.models import Organization
from apps.workspaces.models import Workspace


@pytest.fixture
def org(db):
    return Organization.objects.create(name="Test Org for API")


@pytest.fixture
def ws(db, org):
    return Workspace.objects.create(name="Test Workspace", organization=org)


@pytest.fixture
def workspace_key(db, org, ws):
    return APIKey.issue(name="WS Key", organization=org, workspace=ws)


@pytest.fixture
def org_key(db, org):
    return APIKey.issue(name="Org Key", organization=org)


@pytest.mark.django_db
def test_whoami_returns_workspace_scope_for_workspace_key(client, workspace_key, org, ws):
    _, raw = workspace_key
    resp = client.get(reverse("api:whoami"), HTTP_AUTHORIZATION=f"Bearer {raw}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "workspace"
    assert data["organization_id"] == str(org.id)
    assert data["workspace_id"] == str(ws.id)
    assert data["key_name"] == "WS Key"
    assert "media:write" in data["scopes"]


@pytest.mark.django_db
def test_whoami_returns_org_scope_for_org_key(client, org_key, org):
    _, raw = org_key
    resp = client.get(reverse("api:whoami"), HTTP_AUTHORIZATION=f"Bearer {raw}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "organization"
    assert data["workspace_id"] is None
    assert data["organization_id"] == str(org.id)


@pytest.mark.django_db
def test_missing_authorization_header_returns_401(client):
    resp = client.get(reverse("api:whoami"))
    assert resp.status_code == 401
    assert resp.json()["error"] == "missing_or_malformed_authorization"


@pytest.mark.django_db
def test_malformed_authorization_header_returns_401(client):
    resp = client.get(reverse("api:whoami"), HTTP_AUTHORIZATION="NotBearer abc")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_unknown_token_returns_401(client):
    resp = client.get(reverse("api:whoami"), HTTP_AUTHORIZATION="Bearer bbs_not_a_real_token_at_all_xx")
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_token"


@pytest.mark.django_db
def test_revoked_token_returns_401(client, workspace_key):
    key, raw = workspace_key
    key.revoked_at = timezone.now()
    key.save(update_fields=["revoked_at"])

    resp = client.get(reverse("api:whoami"), HTTP_AUTHORIZATION=f"Bearer {raw}")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_expired_token_returns_401(client, workspace_key):
    key, raw = workspace_key
    key.expires_at = timezone.now() - timedelta(seconds=1)
    key.save(update_fields=["expires_at"])

    resp = client.get(reverse("api:whoami"), HTTP_AUTHORIZATION=f"Bearer {raw}")
    assert resp.status_code == 401
    assert resp.json()["error"] == "expired_token"


@pytest.mark.django_db
def test_last_used_at_updates_on_request(client, workspace_key):
    key, raw = workspace_key
    assert key.last_used_at is None
    client.get(reverse("api:whoami"), HTTP_AUTHORIZATION=f"Bearer {raw}")
    key.refresh_from_db()
    assert key.last_used_at is not None


@pytest.mark.django_db
def test_apikey_issue_generates_unique_tokens(org):
    key_a, raw_a = APIKey.issue(name="A", organization=org)
    key_b, raw_b = APIKey.issue(name="B", organization=org)
    assert raw_a != raw_b
    assert key_a.token_hash != key_b.token_hash
    assert raw_a.startswith("bbs_")
    assert len(raw_a) >= 30
