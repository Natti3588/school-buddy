from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    # ログアウト後の移動先は settings.LOGOUT_REDIRECT_URL（ログイン画面）
    path("logout/", LogoutView.as_view(), name="logout"),
]
