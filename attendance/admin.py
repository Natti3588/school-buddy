from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ["date", "student", "status", "reason", "scanned_at"]
    list_filter = ["date", "status", "student__classroom"]
