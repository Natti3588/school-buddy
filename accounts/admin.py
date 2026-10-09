from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Teacher


@admin.register(Teacher)
class TeacherAdmin(UserAdmin):
    # UserAdmin は username / email などを前提にしているので、表示項目を差し替える
    list_display = ("user_id", "name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("user_id", "name")
    ordering = ("user_id",)
    fieldsets = (
        (None, {"fields": ("user_id", "name", "password")}),
        ("権限", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("日時", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("user_id", "name", "password1", "password2")}),
    )
