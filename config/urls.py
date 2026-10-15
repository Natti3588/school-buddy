from django.contrib import admin
from django.urls import path, include

from .views import TopView

urlpatterns = [
    path("", TopView.as_view(), name="top"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("students/", include("students.urls")),
]
