"""URL configuration for the public REST API. Mounted at ``/api/v1/``."""

from django.urls import path

from . import views_identity, views_media, views_posts

app_name = "api"

urlpatterns = [
    # Identity
    path("whoami/", views_identity.whoami, name="whoami"),
    # Workspace-scoped media
    path(
        "workspaces/<uuid:workspace_id>/media/assets/",
        views_media.workspace_assets,
        name="workspace_assets",
    ),
    path(
        "workspaces/<uuid:workspace_id>/media/assets/<uuid:asset_id>/",
        views_media.workspace_asset_detail,
        name="workspace_asset_detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/media/folders/",
        views_media.workspace_folders,
        name="workspace_folders",
    ),
    # Org-shared media
    path(
        "organizations/<uuid:org_id>/media/assets/",
        views_media.org_assets,
        name="org_assets",
    ),
    path(
        "organizations/<uuid:org_id>/media/assets/<uuid:asset_id>/",
        views_media.org_asset_detail,
        name="org_asset_detail",
    ),
    path(
        "organizations/<uuid:org_id>/media/folders/",
        views_media.org_folders,
        name="org_folders",
    ),
    # Workspace-scoped composer drafts
    path(
        "workspaces/<uuid:workspace_id>/posts/drafts/",
        views_posts.workspace_drafts,
        name="workspace_drafts",
    ),
    path(
        "workspaces/<uuid:workspace_id>/posts/drafts/<uuid:post_id>/",
        views_posts.workspace_draft_detail,
        name="workspace_draft_detail",
    ),
]
