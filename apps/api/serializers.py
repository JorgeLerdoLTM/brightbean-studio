"""Plain-function serializers (no DRF). Each returns a dict ready for JsonResponse."""


def whoami_to_dict(api_key):
    return {
        "scope": "workspace" if api_key.workspace_id else "organization",
        "organization_id": str(api_key.organization_id),
        "organization_name": api_key.organization.name,
        "workspace_id": str(api_key.workspace_id) if api_key.workspace_id else None,
        "workspace_name": api_key.workspace.name if api_key.workspace_id else None,
        "scopes": list(api_key.scopes or []),
        "key_name": api_key.name,
        "key_prefix": api_key.token_prefix,
    }


def asset_to_dict(asset):
    return {
        "id": str(asset.id),
        "filename": asset.filename,
        "mime_type": asset.mime_type,
        "media_type": asset.media_type,
        "file_size": asset.file_size,
        "width": asset.width,
        "height": asset.height,
        "duration": asset.duration,
        "alt_text": asset.alt_text,
        "title": asset.title,
        "tags": list(asset.tags or []),
        "folder_id": str(asset.folder_id) if asset.folder_id else None,
        "workspace_id": str(asset.workspace_id) if asset.workspace_id else None,
        "organization_id": str(asset.organization_id) if asset.organization_id else None,
        "processing_status": asset.processing_status,
        "source": asset.source,
        "source_url": asset.source_url,
        "attribution": asset.attribution,
        "is_starred": asset.is_starred,
        "file_url": asset.file.url if asset.file else None,
        "thumbnail_url": asset.thumbnail.url if asset.thumbnail else None,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
    }


def folder_to_dict(folder):
    return {
        "id": str(folder.id),
        "name": folder.name,
        "parent_folder_id": str(folder.parent_folder_id) if folder.parent_folder_id else None,
        "workspace_id": str(folder.workspace_id) if folder.workspace_id else None,
        "organization_id": str(folder.organization_id),
        "depth": folder.depth,
        "created_at": folder.created_at.isoformat() if folder.created_at else None,
    }


def draft_post_to_dict(post, *, compose_url=None):
    """Serialise a composer ``Post`` for the API response after draft creation."""
    return {
        "id": str(post.id),
        "workspace_id": str(post.workspace_id),
        "title": post.title,
        "caption": post.caption,
        "tags": list(post.tags or []),
        "status": post.status,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "platforms": [
            {
                "platform": pp.social_account.platform,
                "social_account_id": str(pp.social_account_id),
                "account_name": pp.social_account.account_name,
                "platform_specific_caption": pp.platform_specific_caption,
                "status": pp.status,
            }
            for pp in post.platform_posts.select_related("social_account").all()
        ],
        "media": [
            {
                "asset_id": str(pm.media_asset_id),
                "position": pm.position,
            }
            for pm in post.media_attachments.all()
        ],
        "compose_url": compose_url,
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }
