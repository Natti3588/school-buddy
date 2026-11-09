from django.shortcuts import redirect

# パスワード変更が必要なユーザーでも開ける画面（URL の名前）
ALLOWED_VIEW_NAMES = {"accounts:password_change", "accounts:logout"}


class PasswordChangeRequiredMiddleware:
    """must_change_password が True のユーザーは、パスワード変更画面にしか進めないようにする

    ビューごとに書くと付け忘れが起きるので、すべての画面に効くミドルウェアで止める。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        # process_view は URL が決まったあとに呼ばれるので、resolver_match で開こうとしている画面がわかる
        user = request.user
        if not (user.is_authenticated and user.must_change_password):
            return None
        if request.resolver_match.view_name in ALLOWED_VIEW_NAMES:
            return None
        return redirect("accounts:password_change")
