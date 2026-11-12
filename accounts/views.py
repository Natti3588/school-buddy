from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from .forms import FirstPasswordChangeForm, LoginForm, StudentPasswordChangeForm
from .mixins import RoleRequiredMixin
from .models import Role


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


class PasswordChangeView(RoleRequiredMixin, auth_views.PasswordChangeView):
    """生徒が自分のパスワードを変更する画面（初回ログインのあとは、ここで必ず変更させる）"""

    allowed_roles = [Role.STUDENT]
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def get_form_class(self):
        # 初回ログインのときは、今のパスワードを聞かないフォームにする
        if self.request.user.must_change_password:
            return FirstPasswordChangeForm
        return StudentPasswordChangeForm

    def form_valid(self, form):
        # 親の form_valid が form.save() でユーザーを保存するので、その前にフラグを下ろしておく
        # （保存のあとはセッションも更新されるので、ログインしたままになる）
        form.user.must_change_password = False
        return super().form_valid(form)


class PasswordChangeDoneView(RoleRequiredMixin, TemplateView):
    """パスワード変更完了画面"""

    allowed_roles = [Role.STUDENT]
    template_name = "accounts/password_change_done.html"
