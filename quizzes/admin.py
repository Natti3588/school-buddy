from django.contrib import admin

from .models import Choice, Question, Quiz, Section


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "kind", "date", "mode", "status", "author")
    list_filter = ("subject", "mode", "status")
    search_fields = ("title",)


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "qtype", "instruction")
    list_filter = ("qtype",)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "section", "answer", "points")
    inlines = [ChoiceInline]
