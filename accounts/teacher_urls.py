from django.urls import path

from . import views

app_name = "teachers"

urlpatterns = [
    path("", views.TeacherListView.as_view(), name="list"),
    path("new/", views.TeacherNewView.as_view(), name="new"),
    path("confirm/", views.TeacherConfirmView.as_view(), name="confirm"),
    path("<str:user_id>/registered/", views.TeacherRegisteredView.as_view(), name="registered"),
]
