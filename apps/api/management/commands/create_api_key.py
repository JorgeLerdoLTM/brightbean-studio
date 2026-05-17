"""Mint a new API key from the CLI.

Usage:
    python manage.py create_api_key --org "Figus" --name "Acme Agent" --workspace "Printio"
    python manage.py create_api_key --org-id <uuid> --name "Org-shared Agent"

The raw token is printed exactly once — copy it immediately.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.api.models import APIKey
from apps.organizations.models import Organization
from apps.workspaces.models import Workspace


class Command(BaseCommand):
    help = "Mint a new API key for an organization, optionally scoped to a workspace."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Display name for the key.")
        org_group = parser.add_mutually_exclusive_group(required=True)
        org_group.add_argument("--org", help="Organization name (must be unique).")
        org_group.add_argument("--org-id", help="Organization UUID.")
        ws_group = parser.add_mutually_exclusive_group(required=False)
        ws_group.add_argument("--workspace", help="Workspace name within the org (must be unique within the org).")
        ws_group.add_argument("--workspace-id", help="Workspace UUID.")

    def handle(self, *args, **opts):
        if opts.get("org_id"):
            try:
                org = Organization.objects.get(id=opts["org_id"])
            except Organization.DoesNotExist:
                raise CommandError(f"Organization with id={opts['org_id']} not found")
        else:
            matches = list(Organization.objects.filter(name=opts["org"]))
            if not matches:
                raise CommandError(f"No organization named {opts['org']!r}")
            if len(matches) > 1:
                raise CommandError(f"Multiple organizations named {opts['org']!r}; use --org-id")
            org = matches[0]

        workspace = None
        if opts.get("workspace_id"):
            try:
                workspace = Workspace.objects.get(id=opts["workspace_id"], organization=org)
            except Workspace.DoesNotExist:
                raise CommandError(f"Workspace with id={opts['workspace_id']} not found in org {org.name}")
        elif opts.get("workspace"):
            matches = list(Workspace.objects.filter(organization=org, name=opts["workspace"]))
            if not matches:
                raise CommandError(f"No workspace named {opts['workspace']!r} in org {org.name}")
            if len(matches) > 1:
                raise CommandError(f"Multiple workspaces named {opts['workspace']!r}; use --workspace-id")
            workspace = matches[0]

        key, raw_token = APIKey.issue(
            name=opts["name"],
            organization=org,
            workspace=workspace,
        )

        scope = f"workspace={workspace.name}" if workspace else "org-shared"
        self.stdout.write(self.style.SUCCESS(f"Created API key {key.id} ({scope})"))
        self.stdout.write("")
        self.stdout.write("⚠️  This token will not be shown again — copy it now:")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(raw_token))
        self.stdout.write("")
        self.stdout.write(f"Use it as:  Authorization: Bearer {raw_token}")
