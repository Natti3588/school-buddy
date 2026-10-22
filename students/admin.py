from django.contrib import admin

from .models import Classroom, Student


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ("__str__", "year", "school", "homeroom_teacher")
    list_filter = ("school", "year", "grade")
    ordering = ("school", "year", "grade", "number")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("student_id", "classroom", "attendance_number", "name", "furigana", "birth_date")
    list_filter = ("classroom__school", "classroom")
    search_fields = ("student_id", "name", "furigana")
    # 生徒ID は自動で付けるので、表示だけする
    readonly_fields = ("student_id",)
