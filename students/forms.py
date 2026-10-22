from django import forms
from django.core.validators import MaxValueValidator

from accounts.models import Role

from .models import Classroom, Student, current_school_year

# クラス登録で選べる学年（中学校なので 1〜3年）
GRADES = [1, 2, 3]
# 出席番号の上限（UI の入力欄に合わせる）
MAX_ATTENDANCE_NUMBER = 45


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ["classroom", "attendance_number", "name", "furigana", "birth_date"]
        labels = {"name": "氏名"}

    def __init__(self, *args, teacher, **kwargs):
        super().__init__(*args, **kwargs)
        # 選べるクラスは、クラス登録で登録した、自分の学校の今の年度のクラス
        # （画面に出していないクラスの id を送られても、ここで弾かれる）
        self.fields["classroom"].queryset = selectable_classes(teacher)
        self.fields["classroom"].empty_label = None
        # 初期値は担任のクラス（担任でない先生は一番上のクラス）
        self.fields["classroom"].initial = self.fields["classroom"].queryset.filter(homeroom_teacher=teacher).first()
        self.fields["attendance_number"].validators.append(MaxValueValidator(MAX_ATTENDANCE_NUMBER))
        # 空欄のときのメッセージを「〇〇を入力してください」にそろえる
        for field in self.fields.values():
            field.error_messages["required"] = f"{field.label}を入力してください"

    def clean(self):
        cleaned_data = super().clean()
        classroom = cleaned_data.get("classroom")
        number = cleaned_data.get("attendance_number")
        # モデルの制約でも止まるが、出席番号の欄にエラーを出すためにここで確認する
        if classroom and number and classroom.students.filter(attendance_number=number).exists():
            self.add_error("attendance_number", f"{classroom}の出席番号 {number} はすでに使われています")
        return cleaned_data


def selectable_classes(teacher):
    return Classroom.objects.filter(school=teacher.school, year=current_school_year()).order_by("grade", "number")


class TeacherChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, teacher):
        return f"{teacher.name} 先生"


class ClassroomForm(forms.ModelForm):
    # 年度は前年度・今年度・来年度から選ぶ（来年度のクラスを先に登録できるように）
    year = forms.TypedChoiceField(label="年度", coerce=int)
    grade = forms.TypedChoiceField(
        label="学年", coerce=int, choices=[("", "選択してください")] + [(g, f"{g}年") for g in GRADES]
    )
    number = forms.IntegerField(label="クラス", min_value=1, max_value=20)
    homeroom_teacher = TeacherChoiceField(label="担任の先生", queryset=None, empty_label="選択してください")

    class Meta:
        model = Classroom
        fields = ["year", "grade", "number", "homeroom_teacher"]

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        # 学校は入力させず、ログイン中の学校管理者の学校にする
        self.instance.school = school
        school_year = current_school_year()
        self.fields["year"].choices = [(y, f"{y}年度") for y in range(school_year - 1, school_year + 2)]
        self.fields["year"].initial = school_year
        # 担任に選べるのは同じ学校の教員だけ
        self.fields["homeroom_teacher"].queryset = school.teachers.filter(role=Role.TEACHER).order_by("name")
        # 空欄のときのメッセージを「〇〇を入力してください」にそろえる
        for field in self.fields.values():
            field.error_messages["required"] = f"{field.label}を入力してください"

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get("year")
        grade = cleaned_data.get("grade")
        number = cleaned_data.get("number")
        # モデルの制約でも止まるが、クラスの欄にエラーを出すためにここで確認する
        if year and grade and number and self.instance.school.classrooms.filter(
            year=year, grade=grade, number=number
        ).exists():
            self.add_error("number", f"{grade}年{number}組はすでに存在しています")
        return cleaned_data
