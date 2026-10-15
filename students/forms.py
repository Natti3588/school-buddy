from django import forms

from .models import Classroom, Student


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ["classroom", "attendance_number", "name", "furigana", "birth_date"]
        labels = {"name": "氏名"}

    def __init__(self, *args, teacher, **kwargs):
        super().__init__(*args, **kwargs)
        # 選べるクラスは、ログイン中の先生が担任をしているクラスだけ
        # （画面に出していないクラスの id を送られても、ここで弾かれる）
        self.fields["classroom"].queryset = homeroom_classes(teacher)
        self.fields["classroom"].empty_label = None
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


def homeroom_classes(teacher):
    return Classroom.objects.filter(homeroom_teacher=teacher, school=teacher.school)
