from django.urls import path

from . import views

app_name = "quizzes"

# テスト作成：基本情報 → 問題入力 → プレビュー → 完成
urlpatterns = [
    path("", views.QuizListView.as_view(), name="list"),
    path("new/", views.QuizNewView.as_view(), name="new"),
    path("<int:pk>/edit/", views.QuizNewView.as_view(), name="edit"),
    path("<int:pk>/questions/", views.QuizQuestionsView.as_view(), name="questions"),
    path("<int:pk>/preview/", views.QuizPreviewView.as_view(), name="preview"),
    path("<int:pk>/created/", views.QuizCreatedView.as_view(), name="created"),
    path("<int:pk>/pdf/<str:sheet>/", views.QuizPdfView.as_view(), name="pdf"),
]
