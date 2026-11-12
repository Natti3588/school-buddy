# 生徒がログインできるように、生徒ごとにログイン情報（User）を作ってつなぐ

import django.db.models.deletion
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations, models

# accounts.models.STUDENT_INITIAL_PASSWORD と同じ値
# （マイグレーションはあとでモデルの定数が変わっても同じ結果になるように、値をここに書く）
INITIAL_PASSWORD = "password"


def create_student_users(apps, schema_editor):
    # すでに登録されている生徒にもログイン情報を作る。
    # ログインID は生徒ID、パスワードは初回のパスワードで、最初のログインで変更させる
    Student = apps.get_model("students", "Student")
    User = apps.get_model("accounts", "User")
    for student in Student.objects.filter(user__isnull=True):
        student.user = User.objects.create(
            user_id=student.student_id,
            password=make_password(INITIAL_PASSWORD),  # ハッシュ化して保存する
            role="student",
            must_change_password=True,
        )
        student.save(update_fields=["user"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_student_role"),
        ("students", "0003_classroom_year"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. いったん NULL を許可して列を追加
        migrations.AddField(
            model_name="student",
            name="user",
            field=models.OneToOneField(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="student",
                to=settings.AUTH_USER_MODEL,
                verbose_name="ログイン情報",
            ),
        ),
        # 2. 既存の生徒のログイン情報を作る（戻すときは何もしない）
        migrations.RunPython(create_student_users, migrations.RunPython.noop),
        # 3. 必須（NOT NULL）にする
        migrations.AlterField(
            model_name="student",
            name="user",
            field=models.OneToOneField(
                editable=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="student",
                to=settings.AUTH_USER_MODEL,
                verbose_name="ログイン情報",
            ),
        ),
    ]
