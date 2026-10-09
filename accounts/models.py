from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class TeacherManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, user_id, password=None, **extra_fields):
        if not user_id:
            raise ValueError("ユーザーIDは必須です")
        teacher = self.model(user_id=user_id, **extra_fields)
        teacher.set_password(password)  # ハッシュ化して保存する
        teacher.save(using=self._db)
        return teacher

    def create_superuser(self, user_id, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # createsuperuser は所属学校を主キーの値（例: 2）で渡してくるので school_id として渡す
        if "school" in extra_fields and not hasattr(extra_fields["school"], "pk"):
            extra_fields["school_id"] = extra_fields.pop("school")
        return self.create_user(user_id, password, **extra_fields)


class Teacher(AbstractBaseUser, PermissionsMixin):
    # password と last_login は AbstractBaseUser が持っている
    user_id = models.CharField("ユーザーID", max_length=150, unique=True)
    name = models.CharField("教員名", max_length=100)
    # 学校を削除すると、所属する教員も一緒に削除される
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="teachers",
        verbose_name="所属学校",
    )

    # Django の認証・管理画面が参照するフラグ
    is_active = models.BooleanField("有効", default=True)
    is_staff = models.BooleanField("管理画面へのアクセス", default=False)

    objects = TeacherManager()

    USERNAME_FIELD = "user_id"
    # createsuperuser で USERNAME_FIELD とパスワード以外に入力を求める項目
    REQUIRED_FIELDS = ["name", "school"]

    class Meta:
        verbose_name = "教員"
        verbose_name_plural = "教員"

    def __str__(self):
        return self.user_id
