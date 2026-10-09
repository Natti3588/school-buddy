from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path("", login_required(TemplateView.as_view(template_name="top.html")), name="top"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
]
