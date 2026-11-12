# 生徒もログインできるようにする

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_rename_teacher_user"),
        ("schools", "0002_school_code_address_registered_at"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="user",
            name="school_matches_role",
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("teacher", "教員"),
                    ("school_admin", "学校管理者"),
                    ("system_admin", "管理者"),
                    ("student", "生徒"),
                ],
                default="teacher",
                max_length=20,
                verbose_name="種類",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="name",
            field=models.CharField(blank=True, max_length=100, verbose_name="名前"),
        ),
        migrations.AddField(
            model_name="user",
            name="must_change_password",
            field=models.BooleanField(default=False, verbose_name="パスワード変更が必要"),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("role__in", ["teacher", "school_admin"]), ("school__isnull", False)),
                    models.Q(("role__in", ["system_admin", "student"]), ("school__isnull", True)),
                    _connector="OR",
                ),
                name="school_matches_role",
                violation_error_message="教員と学校管理者は所属学校が必須です。管理者と生徒には所属学校を設定できません",
            ),
        ),
    ]
