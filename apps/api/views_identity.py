"""Identity endpoint — the agent's first call after configuration.

Lets a freshly-configured agent confirm that its token works AND learn
what scope it has (workspace_id, organization_id) so subsequent calls hit
the right URL.
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django_ratelimit.decorators import ratelimit

from .decorators import require_api_key
from .serializers import whoami_to_dict


@csrf_exempt
@require_GET
@ratelimit(key="header:authorization", rate="600/h", block=True)
@require_api_key
def whoami(request):
    return JsonResponse(whoami_to_dict(request.api_key))
