"""Move upload_to= from a static string to a callable that includes the
tenant prefix (``<org_id>/<workspace_id or 'shared'>``) in the object key.

Old objects keep their existing keys (Django stores whatever path was
used at save time). Only new uploads use the new layout."""

from django.db import migrations, models

import apps.media_library.models


class Migration(migrations.Migration):
    dependencies = [
        ("media_library", "0002_mediaasset_is_starred_mediaasset_organization_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mediaasset",
            name="file",
            field=models.FileField(upload_to=apps.media_library.models.asset_upload_path),
        ),
        migrations.AlterField(
            model_name="mediaasset",
            name="thumbnail",
            field=models.ImageField(blank=True, upload_to=apps.media_library.models.asset_thumbnail_path),
        ),
        migrations.AlterField(
            model_name="mediaassetversion",
            name="file",
            field=models.FileField(upload_to=apps.media_library.models.version_upload_path),
        ),
        migrations.AlterField(
            model_name="mediaassetversion",
            name="thumbnail",
            field=models.ImageField(blank=True, default="", upload_to=apps.media_library.models.version_thumbnail_path),
        ),
    ]
