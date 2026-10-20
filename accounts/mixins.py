from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


class RoleRequiredMixin(LoginRequiredMixin):
    """allowed_roles に入っている種類のユーザーだけが開ける画面にする"""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        # ほかの種類のユーザーが開いたときは、その人のトップ画面に戻す
        # （ログインしていないときは LoginRequiredMixin がログイン画面に移動させる）
        if request.user.is_authenticated and request.user.role not in self.allowed_roles:
            return redirect(request.user.get_top_url())
        return super().dispatch(request, *args, **kwargs)
