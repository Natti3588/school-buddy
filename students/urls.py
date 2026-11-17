from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("", views.StudentListView.as_view(), name="list"),
    path("new/", views.StudentNewView.as_view(), name="new"),
    path("confirm/", views.StudentConfirmView.as_view(), name="confirm"),
    path("<str:student_id>/registered/", views.StudentRegisteredView.as_view(), name="registered"),
]
