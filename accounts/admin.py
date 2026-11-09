from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # UserAdmin は username / email などを前提にしているので、表示項目を差し替える
    list_display = ("user_id", "name", "role", "school", "must_change_password", "is_staff", "is_active")
    list_filter = ("role", "school", "is_staff", "is_superuser", "is_active")
    search_fields = ("user_id", "name", "school__name")
    ordering = ("user_id",)
    fieldsets = (
        (None, {"fields": ("user_id", "name", "role", "school", "password", "must_change_password")}),
        # 生徒の登録端末。空にして保存すると登録を解除できる（教員の画面から解除できるようになるまでの代わり）
        ("端末", {"fields": ("device_id",)}),
        ("権限", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("日時", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("user_id", "name", "role", "school", "password1", "password2")}),
    )
