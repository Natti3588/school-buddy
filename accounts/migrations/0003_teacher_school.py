import django.db.models.deletion
from django.db import migrations, models

PLACEHOLDER_SCHOOL_NAME = "未設定"


def assign_placeholder_school(apps, schema_editor):
    # 既存の教員は所属学校が決まっていないので、仮の学校に所属させる
    Teacher = apps.get_model("accounts", "Teacher")
    School = apps.get_model("schools", "School")
    teachers = Teacher.objects.filter(school__isnull=True)
    if teachers.exists():
        school, _ = School.objects.get_or_create(name=PLACEHOLDER_SCHOOL_NAME)
        teachers.update(school=school)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_teacher_name"),
        ("schools", "0001_initial"),
    ]

    operations = [
        # 1. いったん NULL を許可して列を追加
        migrations.AddField(
            model_name="teacher",
            name="school",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="teachers",
                to="schools.school",
                verbose_name="所属学校",
            ),
        ),
        # 2. 既存の教員を仮の学校に所属させる（戻すときは何もしない）
        migrations.RunPython(assign_placeholder_school, migrations.RunPython.noop),
        # 3. 必須（NOT NULL）にする
        migrations.AlterField(
            model_name="teacher",
            name="school",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="teachers",
                to="schools.school",
                verbose_name="所属学校",
            ),
        ),
    ]
