from django.contrib import admin

from .models import School


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "address", "registered_at")
    search_fields = ("code", "name", "address")
    # 学校コードと登録日は自動で入るので、表示だけする
    readonly_fields = ("code", "registered_at")
