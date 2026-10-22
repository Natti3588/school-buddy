from django.urls import path

from . import views

app_name = "classrooms"

# シーケンス図に合わせて、入力・確認・完了をすべて ClassroomNewView が受け持つ
urlpatterns = [
    path("new/", views.ClassroomNewView.as_view(), name="new"),
    path("<int:pk>/registered/", views.ClassroomNewView.as_view(), name="registered"),
]
