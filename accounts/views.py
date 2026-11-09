from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.db import IntegrityError, transaction
from django.urls import reverse_lazy
from django.views.generic import FormView

from .devices import set_device_cookie
from .forms import LoginForm
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
        user = form.get_user()
        if user.role == Role.STUDENT and user.device_id is None:
            # 初回ログイン（または教員が登録を解除したあと）なので、今の端末を登録する
            user.device_id = form.device_id
            try:
                with transaction.atomic():
                    user.save(update_fields=["device_id"])
            except IntegrityError:
                # 確かめてから保存するまでの間に、同じ端末を別の生徒が登録した場合（device_id は unique）
                form.add_error(None, form.error_messages["device_not_allowed"])
                return self.form_invalid(form)

        login(self.request, user)
        response = super().form_valid(form)
        if user.role == Role.STUDENT:
            # ログインのたびに Cookie を保存しなおして、期限を延ばす
            set_device_cookie(response, user.device_id)
        return response


class PasswordChangeView(RoleRequiredMixin, auth_views.PasswordChangeView):
    """生徒が自分のパスワードを変更する画面（初回ログインのあとは、ここで必ず変更させる）"""

    allowed_roles = [Role.STUDENT]
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("student_top")

    def form_valid(self, form):
        # 親の form_valid が form.save() でユーザーを保存するので、その前にフラグを下ろしておく
        # （保存のあとはセッションも更新されるので、ログインしたままになる）
        form.user.must_change_password = False
        messages.success(self.request, "パスワードを変更しました")
        return super().form_valid(form)
