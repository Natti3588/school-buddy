import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from accounts.models import Role

# 生徒ID に使う文字（見間違えやすい 0/O・1/I は使わない）
STUDENT_ID_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
STUDENT_ID_LENGTH = 8


def generate_student_id():
    # secrets は推測されにくい乱数を作る（random は使わない）
    return "".join(secrets.choice(STUDENT_ID_CHARS) for _ in range(STUDENT_ID_LENGTH))


class Classroom(models.Model):
    # 学校を削除すると、その学校のクラスも削除される
    # （ただし生徒がいるクラスは Student 側の PROTECT で止まる）
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="classrooms",
        verbose_name="学校",
    )
    grade = models.PositiveSmallIntegerField("学年", validators=[MinValueValidator(1)])
    number = models.PositiveSmallIntegerField("組", validators=[MinValueValidator(1)])
    # 担任が削除されても、クラスは残して担任を空にする
    homeroom_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        # 担任に選べるのは教員だけ（学校管理者と管理者は生徒登録の画面を使わない）
        limit_choices_to={"role": Role.TEACHER},
        related_name="homeroom_classes",
        verbose_name="担任",
    )

    class Meta:
        verbose_name = "クラス"
        verbose_name_plural = "クラス"
        ordering = ["school", "grade", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "grade", "number"],
                name="unique_classroom_per_school",
                violation_error_message="同じ学校に同じ学年・組のクラスがすでにあります",
            ),
        ]

    def __str__(self):
        return f"{self.grade}年{self.number}組"

    def clean(self):
        # 担任は同じ学校の教員でなければならない
        if (
            self.homeroom_teacher_id
            and self.school_id
            and self.homeroom_teacher.school_id != self.school_id
        ):
            raise ValidationError({"homeroom_teacher": "担任は同じ学校の教員を選んでください"})


class Student(models.Model):
    # 保存するときにバックエンドが自動で付ける（画面からは入力・変更させない）
    student_id = models.CharField(
        "生徒ID", max_length=STUDENT_ID_LENGTH, unique=True, editable=False
    )
    # 生徒がいるクラスは削除できない
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.PROTECT,
        related_name="students",
        verbose_name="クラス",
    )
    attendance_number = models.PositiveSmallIntegerField(
        "出席番号", validators=[MinValueValidator(1)]
    )
    name = models.CharField("名前", max_length=100)
    furigana = models.CharField("ふりがな", max_length=100)
    birth_date = models.DateField("生年月日")

    class Meta:
        verbose_name = "生徒"
        verbose_name_plural = "生徒"
        ordering = ["classroom", "attendance_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["classroom", "attendance_number"],
                name="unique_attendance_number_per_classroom",
                violation_error_message="このクラスにはすでに同じ出席番号の生徒がいます",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.student_id:
            # 32文字×8桁で約1兆通りあるが、万一の重複に備えて使われていないものを選ぶ
            student_id = generate_student_id()
            while Student.objects.filter(student_id=student_id).exists():
                student_id = generate_student_id()
            self.student_id = student_id
        super().save(*args, **kwargs)
