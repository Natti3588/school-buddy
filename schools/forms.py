from django import forms
from django.db import transaction

from accounts.models import Role, User
from accounts.registration import clean_initial_password
from students.models import issue_login_id

from .models import School, SchoolType


class SchoolForm(forms.Form):
    """学校登録（学校と、その学校の学校管理者を一緒に作る）"""

    name = forms.CharField(label="学校名", max_length=100)
    # 最初は何も選ばれていない状態にする（UI のとおり）
    school_type = forms.ChoiceField(label="学校種別", choices=[("", "選択してください")] + SchoolType.choices)
    address = forms.CharField(label="所在地", max_length=200)
    admin_name = forms.CharField(label="学校管理者", max_length=100)
    admin_email = forms.EmailField(
        label="学校管理者メールアドレス",
        error_messages={"invalid": "メールアドレスの形式が正しくありません"},
    )
    # 完了画面で表示するので、確認画面から「修正する」で戻ったときも入っているようにする
    password = forms.CharField(label="初期パスワード", widget=forms.PasswordInput(render_value=True))

    def __init__(self, *args, require_password=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not require_password:
            # 確認画面と保存の直前は、パスワード以外をもう一度確かめる（パスワードは入力画面で確かめ済み）
            del self.fields["password"]
        # 空欄のときのメッセージを、ユースケースの代替フローの「〇〇を入力してください」にそろえる
        for field in self.fields.values():
            field.error_messages["required"] = f"{field.label}を入力してください"
        self.fields["admin_name"].error_messages["required"] = "学校管理者名を入力してください"

    def clean_name(self):
        name = self.cleaned_data["name"]
        # モデルの unique でも止まるが、学校名の欄にエラーを出すためにここで確かめる
        if School.objects.filter(name=name).exists():
            raise forms.ValidationError("この学校はすでに登録されています")
        return name

    def clean_password(self):
        return clean_initial_password(self.cleaned_data["password"])

    def save(self, password_hash):
        """学校と学校管理者を保存する（どちらか片方だけ保存されることがないように一緒に保存する）"""
        data = self.cleaned_data
        with transaction.atomic():
            school = School(name=data["name"], school_type=data["school_type"], address=data["address"])
            school.save()
            # create_user() はパスワードをハッシュにするので使わない（ここではもうハッシュになっている）
            User(
                user_id=issue_login_id(),
                name=data["admin_name"],
                email=data["admin_email"],
                role=Role.SCHOOL_ADMIN,
                school=school,
                password=password_hash,
                must_change_password=False,
            ).save()
        return school
