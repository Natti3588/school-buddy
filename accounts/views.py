from django.contrib.auth import login
from django.views.generic import FormView

from .forms import LoginForm


class LoginView(FormView):
    template_name = "accounts/login.html"
    form_class = LoginForm

    def get_success_url(self):
        # ユーザーの種類ごとのトップ画面に移動する（login() のあとなので request.user はログインした人）
        return self.request.user.get_top_url()

    def get_form_kwargs(self):
        # AuthenticationForm は第 1 引数に request を受け取る
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        login(self.request, form.get_user())
        return super().form_valid(form)
