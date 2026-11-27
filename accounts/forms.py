from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from students.models import issue_login_id

from .models import Role, User
from .registration import clean_initial_password


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "入力情報が誤っています",
        "inactive": "入力情報が誤っています",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "ログインID"
        # メッセージはユースケース記述のとおり（ラベルは「ログインID」だが、ここは「ユーザーID」）
        self.fields["username"].error_messages["required"] = "ユーザーIDが未入力です"
        self.fields["password"].error_messages["required"] = "パスワードが未入力です"


class NewPasswordMixin:
    """パスワード変更の 2 つのフォームで共通の部分（ラベルと「今と同じパスワードは使えない」の確認）"""

    same_password_message = "今のパスワードと同じものは使えません"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "新しいパスワード"
        self.fields["new_password2"].label = "確認用パスワード"
        self.fields["new_password1"].error_messages["required"] = "新しいパスワードが未入力です"
        self.fields["new_password2"].error_messages["required"] = "確認用パスワードが未入力です"
        self.error_messages = {
            **self.error_messages,
            # メッセージはユースケース記述「パスワードを変更する」のとおり
            "password_mismatch": "パスワードが一致しません",
            "password_invalid": "パスワードに不正な文字が含まれています",
        }

    def validate_password_for_user(self, user, password_field_name="password2"):
        # AUTH_PASSWORD_VALIDATORS の確認（8文字以上・英字と数字を入れる・使えない文字がない）。
        # Django 標準は理由ごとに別のメッセージを出すが、ユースケース記述に合わせて 1 つにまとめる
        password = self.cleaned_data.get(password_field_name)
        if password:
            try:
                validate_password(password, user)
            except ValidationError:
                self.add_error(
                    password_field_name,
                    ValidationError(self.error_messages["password_invalid"], code="password_invalid"),
                )

    def clean_new_password1(self):
        password = self.cleaned_data["new_password1"]
        # self.user は今ログインしている人。check_password はハッシュどうしを比べてくれる
        if self.user.check_password(password):
            raise ValidationError(self.same_password_message, code="password_same")
        return password


class FirstPasswordChangeForm(NewPasswordMixin, SetPasswordForm):
    """初回ログインのパスワード変更（今のパスワードは聞かない。ログインしたばかりなので）"""

    same_password_message = "先生からもらったパスワードと同じものは使えません"


class StudentPasswordChangeForm(NewPasswordMixin, PasswordChangeForm):
    """2 回目からのパスワード変更（本人か確かめるために、今のパスワードも聞く）"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "今のパスワード"
        self.fields["old_password"].error_messages["required"] = "今のパスワードが未入力です"
        self.error_messages = {
            **self.error_messages,
            "password_incorrect": "今のパスワードが正しくありません",
        }


class TeacherForm(forms.Form):
    """教員登録（ログイン中の学校管理者の学校に、教員を1人作る）"""

    name = forms.CharField(label="氏名", max_length=100)
    furigana = forms.CharField(label="ふりがな", max_length=100)
    # 完了画面で表示するので、確認画面から「修正する」で戻ったときも入っているようにする
    password = forms.CharField(label="初期パスワード", widget=forms.PasswordInput(render_value=True))

    def __init__(self, *args, school, require_password=True, **kwargs):
        super().__init__(*args, **kwargs)
        # 学校は入力させず、ログイン中の学校管理者の学校にする
        self.school = school
        if not require_password:
            # 確認画面と保存の直前は、パスワード以外をもう一度確かめる（パスワードは入力画面で確かめ済み）
            del self.fields["password"]
        # 空欄のときのメッセージを、ユースケースの代替フローの「〇〇を入力してください」にそろえる
        for field in self.fields.values():
            field.error_messages["required"] = f"{field.label}を入力してください"
        if "password" in self.fields:
            # ユースケース 7-3 の文（ラベルの「初期パスワード」とは違う）
            self.fields["password"].error_messages["required"] = "パスワードを入力してください"

    def clean_password(self):
        return clean_initial_password(self.cleaned_data["password"])

    def save(self, password_hash):
        data = self.cleaned_data
        # create_user() はパスワードをハッシュにするので使わない（ここではもうハッシュになっている）
        user = User(
            user_id=issue_login_id(),
            name=data["name"],
            furigana=data["furigana"],
            role=Role.TEACHER,
            school=self.school,
            password=password_hash,
            must_change_password=False,
        )
        user.save()
        return user
