from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.urls import reverse


class Role(models.TextChoices):
    # ユーザーの種類（1人に1つ）
    TEACHER = "teacher", "教員"
    SCHOOL_ADMIN = "school_admin", "学校管理者"
    SYSTEM_ADMIN = "system_admin", "管理者"


# ログイン後に表示する、種類ごとのトップ画面（URL の名前）
TOP_URL_NAMES = {
    Role.TEACHER: "top",
    Role.SCHOOL_ADMIN: "school_admin_top",
    Role.SYSTEM_ADMIN: "system_admin_top",
}


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
        # createsuperuser で作るのは管理者（学校に所属しない）
        extra_fields.setdefault("role", Role.SYSTEM_ADMIN)
        return self.create_user(user_id, password, **extra_fields)


class Teacher(AbstractBaseUser, PermissionsMixin):
    # password と last_login は AbstractBaseUser が持っている
    user_id = models.CharField("ユーザーID", max_length=150, unique=True)
    name = models.CharField("教員名", max_length=100)
    role = models.CharField("種類", max_length=20, choices=Role.choices, default=Role.TEACHER)
    # 学校を削除すると、所属する教員も一緒に削除される
    # 管理者はどの学校にも所属しないので空にする
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="teachers",
        verbose_name="所属学校",
    )

    # Django の認証・管理画面が参照するフラグ
    is_active = models.BooleanField("有効", default=True)
    is_staff = models.BooleanField("管理画面へのアクセス", default=False)

    objects = TeacherManager()

    USERNAME_FIELD = "user_id"
    # createsuperuser で USERNAME_FIELD とパスワード以外に入力を求める項目
    # （createsuperuser で作る管理者は学校に所属しないので、学校は聞かない）
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = "教員"
        verbose_name_plural = "教員"
        constraints = [
            # 教員と学校管理者は所属学校が必須、管理者は所属学校なし
            models.CheckConstraint(
                condition=(
                    models.Q(role__in=[Role.TEACHER, Role.SCHOOL_ADMIN], school__isnull=False)
                    | models.Q(role=Role.SYSTEM_ADMIN, school__isnull=True)
                ),
                name="school_matches_role",
                violation_error_message="教員と学校管理者は所属学校が必須です。管理者には所属学校を設定できません",
            ),
        ]

    def __str__(self):
        return self.user_id

    def get_top_url(self):
        return reverse(TOP_URL_NAMES[self.role])
