# 生徒もログインするので、ログインする人のモデルを Teacher から User に変えた。
#
# 他のアプリ（admin・students・quizzes）のマイグレーションは settings.AUTH_USER_MODEL（accounts.User）を参照する。
# RenameModel で名前を変えると、適用済みのマイグレーションを読み直すときに「accounts.User がない」と失敗するので、
# 0001〜0004 のモデル名を User に書き換え、テーブル名は db_table で accounts_teacher のままにしてある。
# このマイグレーションで、データベースの名前を User に合わせる。

from django.db import migrations

# ManyToManyField が作った中間テーブル
M2M_TABLES = ["accounts_teacher_groups", "accounts_teacher_user_permissions"]


def rename_m2m_columns(apps, schema_editor):
    # 中間テーブルの列名はモデル名から作られる。
    # Teacher のときに作ったデータベースは teacher_id、0001 から User で作ったデータベースは user_id になっている
    connection = schema_editor.connection
    quote = schema_editor.quote_name
    with connection.cursor() as cursor:
        for table in M2M_TABLES:
            columns = [c.name for c in connection.introspection.get_table_description(cursor, table)]
            if "teacher_id" in columns:
                schema_editor.execute(
                    f"ALTER TABLE {quote(table)} RENAME COLUMN {quote('teacher_id')} TO {quote('user_id')}"
                )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_teacher_role"),
    ]

    operations = [
        # 1. 中間テーブルの列名を user_id にそろえる（戻すときは user_id のままにする）
        migrations.RunPython(rename_m2m_columns, migrations.RunPython.noop),
        # 2. テーブル名を accounts_user に変える（中間テーブルも accounts_user_groups などに変わる）
        migrations.AlterModelTable(name="user", table=None),
        migrations.AlterModelOptions(
            name="user",
            options={"verbose_name": "利用者", "verbose_name_plural": "利用者"},
        ),
    ]
