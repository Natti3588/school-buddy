from django.db import models, transaction


class School(models.Model):
    # 登録したときにバックエンドが自動で付ける（例：SC0001）。画面からは入力・変更させない
    # 付けるのは保存の直後なので、一瞬だけ空（NULL）になる。
    # 空文字にすると unique で2校目以降がぶつかるので、null=True にしている
    code = models.CharField("学校コード", max_length=10, unique=True, null=True, editable=False)
    name = models.CharField("学校名", max_length=100, unique=True)
    address = models.CharField("所在地", max_length=200)
    registered_at = models.DateTimeField("登録日", auto_now_add=True)

    class Meta:
        verbose_name = "学校"
        verbose_name_plural = "学校"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # 学校の保存と学校コードの書き込みを1つのトランザクションにする（途中で失敗したら両方取り消す）
        with transaction.atomic():
            super().save(*args, **kwargs)
            if not self.code:
                # id は学校ごとに重ならず、あとから変わることもないので、そのまま学校コードの番号にする
                self.code = f"SC{self.pk:04d}"
                super().save(update_fields=["code"])
