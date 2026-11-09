import uuid

from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .devices import is_device_allowed, read_device_id
from .models import Role, User


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "入力情報が誤っています",
        "inactive": "入力情報が誤っています",
        # どの生徒がこの端末を登録しているかは表示しない
        "device_not_allowed": "この端末ではログインできません。先生に相談してください",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "ログインID"
        # メッセージはユースケース記述のとおり（ラベルは「ログインID」だが、ここは「ユーザーID」）
        self.fields["username"].error_messages["required"] = "ユーザーIDが未入力です"
        self.fields["password"].error_messages["required"] = "パスワードが未入力です"
        # 生徒がログインできたときに使う端末の UUID（LoginView が登録と Cookie の保存に使う）
        self.device_id = None

    def confirm_login_allowed(self, user):
        # ID とパスワードが正しいとわかったあとに呼ばれる
        super().confirm_login_allowed(user)
        if user.role != Role.STUDENT:
            return  # 端末を確かめるのは生徒だけ
        device_id = read_device_id(self.request)
        device_owner = User.objects.filter(device_id=device_id).first() if device_id else None
        if not is_device_allowed(user, device_id, device_owner):
            raise ValidationError(self.error_messages["device_not_allowed"], code="device_not_allowed")
        # 登録済みならその端末、未登録なら今の端末（Cookie がなければ新しい UUID）
        self.device_id = user.device_id or device_id or uuid.uuid4()
