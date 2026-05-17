"""Bump FileField/ImageField max_length to 255 to accommodate the new
tenant-prefixed object keys (org_uuid/workspace_uuid eats ~75 chars on
its own; default max_length=100 was rejecting valid paths).
"""

from django.db import migrations, models

import apps.media_library.models


class Migration(migrations.Migration):
    dependencies = [
        ("media_library", "0003_tenant_prefixed_upload_paths"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mediaasset",
            name="file",
            field=models.FileField(max_length=255, upload_to=apps.media_library.models.asset_upload_path),
        ),
        migrations.AlterField(
            model_name="mediaasset",
            name="thumbnail",
            field=models.ImageField(blank=True, max_length=255, upload_to=apps.media_library.models.asset_thumbnail_path),
        ),
        migrations.AlterField(
            model_name="mediaassetversion",
            name="file",
            field=models.FileField(max_length=255, upload_to=apps.media_library.models.version_upload_path),
        ),
        migrations.AlterField(
            model_name="mediaassetversion",
            name="thumbnail",
            field=models.ImageField(blank=True, default="", max_length=255, upload_to=apps.media_library.models.version_thumbnail_path),
        ),
    ]
