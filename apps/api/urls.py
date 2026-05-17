"""URL configuration for the public REST API. Mounted at ``/api/v1/``."""

from django.urls import path

from . import views_identity

app_name = "api"

urlpatterns = [
    path("whoami/", views_identity.whoami, name="whoami"),
]
