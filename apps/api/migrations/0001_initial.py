import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.api.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
        ("workspaces", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="APIKey",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(help_text="Human-readable label, e.g. 'Acme content agent'.", max_length=100)),
                ("token_prefix", models.CharField(help_text="First 12 chars of the raw token, shown in the UI for identification.", max_length=12)),
                ("token_hash", models.CharField(db_index=True, help_text="SHA-256 hex of the raw token. The raw token is never stored.", max_length=64, unique=True)),
                ("scopes", models.JSONField(default=apps.api.models._default_scopes)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="api_keys_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_keys",
                        to="organizations.organization",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        blank=True,
                        help_text="If set, the key is scoped to this workspace. If null, scope is the org-shared library.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_keys",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "api_keys",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="apikey",
            index=models.Index(fields=["organization", "workspace"], name="apikey_org_ws_idx"),
        ),
    ]
