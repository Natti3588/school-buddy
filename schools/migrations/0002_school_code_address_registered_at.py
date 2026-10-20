import django.utils.timezone
from django.db import migrations, models


def set_codes_for_existing_schools(apps, schema_editor):
    # すでに登録されている学校にも、新しく登録する学校と同じ形の学校コードを付ける
    School = apps.get_model("schools", "School")
    for school in School.objects.filter(code__isnull=True):
        School.objects.filter(pk=school.pk).update(code=f"SC{school.pk:04d}")


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="school",
            name="code",
            field=models.CharField(editable=False, max_length=10, null=True, unique=True, verbose_name="学校コード"),
        ),
        # すでにある学校の所在地は空にしておく（管理画面で編集するときに入力する）
        migrations.AddField(
            model_name="school",
            name="address",
            field=models.CharField(default="", max_length=200, verbose_name="所在地"),
            preserve_default=False,
        ),
        # すでにある学校の登録日は、このマイグレーションを実行した日時にする
        migrations.AddField(
            model_name="school",
            name="registered_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, verbose_name="登録日"),
            preserve_default=False,
        ),
        migrations.RunPython(set_codes_for_existing_schools, migrations.RunPython.noop),
    ]
