"""URL patterns for the Settings → API Keys UI.

Mounted twice from ``config/urls.py``:

  * ``/workspace/<uuid:workspace_id>/settings/api-keys/``  → workspace pages
  * ``/organizations/settings/api-keys/``                  → org pages
"""

from django.urls import path

from . import views_keys

# No module-level ``app_name``; two namespaces are applied at include time
# in ``config/urls.py`` (api_keys_ws and api_keys_org).

workspace_urlpatterns = [
    path("", views_keys.workspace_keys_index, name="workspace_index"),
    path("create/", views_keys.workspace_keys_create, name="workspace_create"),
    path("<uuid:key_id>/revoke/", views_keys.workspace_keys_revoke, name="workspace_revoke"),
]

org_urlpatterns = [
    path("", views_keys.org_keys_index, name="org_index"),
    path("create/", views_keys.org_keys_create, name="org_create"),
    path("<uuid:key_id>/revoke/", views_keys.org_keys_revoke, name="org_revoke"),
]
