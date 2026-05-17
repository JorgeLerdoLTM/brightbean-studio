"""Auth decorator for public-API endpoints.

The agent presents a bearer token in the ``Authorization`` header. We:

1. SHA-256 the token, look up the row, reject if missing/revoked/expired.
2. Populate ``request.api_key``, ``request.org``, and ``request.workspace``
   (the latter may be ``None`` for org-shared keys).
3. Touch ``last_used_at`` so the UI can show recency.

Sessions / CSRF are bypassed — these views are exclusively bearer-auth and
the URL routes that mount them are ``@csrf_exempt``.
"""

import functools

from django.http import JsonResponse
from django.utils import timezone

from .models import APIKey, hash_token


def require_api_key(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            return JsonResponse({"error": "missing_or_malformed_authorization"}, status=401)
        token = header[7:].strip()
        if not token:
            return JsonResponse({"error": "missing_or_malformed_authorization"}, status=401)

        token_hash = hash_token(token)
        try:
            key = APIKey.objects.select_related("organization", "workspace").get(
                token_hash=token_hash,
                revoked_at__isnull=True,
            )
        except APIKey.DoesNotExist:
            return JsonResponse({"error": "invalid_token"}, status=401)

        if key.expires_at is not None and key.expires_at <= timezone.now():
            return JsonResponse({"error": "expired_token"}, status=401)

        request.api_key = key
        request.org = key.organization
        request.workspace = key.workspace  # None for org-shared keys
        APIKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())

        return view_func(request, *args, **kwargs)

    return wrapper
