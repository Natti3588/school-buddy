from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "入力情報が誤っています",
        "inactive": "入力情報が誤っています",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "ユーザーID"
        self.fields["username"].error_messages["required"] = "ユーザーIDが未入力です"
        self.fields["password"].error_messages["required"] = "パスワードが未入力です"
