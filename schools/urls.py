from django.urls import path

from . import views

app_name = "schools"

urlpatterns = [
    path("new/", views.SchoolNewView.as_view(), name="new"),
    path("confirm/", views.SchoolConfirmView.as_view(), name="confirm"),
    path("<int:pk>/registered/", views.SchoolRegisteredView.as_view(), name="registered"),
]
