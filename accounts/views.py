from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views.generic import FormView

from .forms import LoginForm


class LoginView(FormView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    success_url = reverse_lazy("top")

    def get_form_kwargs(self):
        # AuthenticationForm は第 1 引数に request を受け取る
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        login(self.request, form.get_user())
        return super().form_valid(form)
