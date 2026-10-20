from django.contrib import admin
from django.urls import path, include

from .views import SchoolAdminTopView, SystemAdminTopView, TopView

urlpatterns = [
    path("", TopView.as_view(), name="top"),
    path("school-admin/", SchoolAdminTopView.as_view(), name="school_admin_top"),
    # /admin/ は Django の管理画面が使っているので、管理者の画面は /system-admin/ にする
    path("system-admin/", SystemAdminTopView.as_view(), name="system_admin_top"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("students/", include("students.urls")),
]
