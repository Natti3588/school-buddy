from django import forms
from django.utils import timezone

from .models import Reason, Status


class DailyAttendanceForm(forms.Form):
    """今日の出欠（クラスの生徒全員分を1つのフォームで送る）"""

    # 画面を開いた時刻。これより後に QR コードを読んだ生徒は、開いたときの表示（欠席）で上書きしない
    loaded_at = forms.DateTimeField(widget=forms.HiddenInput, initial=timezone.now)

    def __init__(self, *args, students, initial_values, **kwargs):
        # initial_values は {生徒の pk: (状態, 理由)}（画面を開いたときの表示）
        super().__init__(*args, **kwargs)
        self.students = students
        for student in students:
            status, reason = initial_values[student.pk]
            self.fields[f"status_{student.pk}"] = forms.ChoiceField(choices=Status.choices, initial=status)
            self.fields[f"reason_{student.pk}"] = forms.ChoiceField(
                choices=[("", "選択してください")] + Reason.choices,
                required=False,
                initial=reason,
            )

    def clean(self):
        cleaned_data = super().clean()
        for student in self.students:
            status = cleaned_data.get(f"status_{student.pk}")
            if status and status != Status.PRESENT and not cleaned_data.get(f"reason_{student.pk}"):
                self.add_error(f"reason_{student.pk}", "理由を選んでください")
        return cleaned_data

    def rows(self):
        """テンプレートで1行ずつ表示する（生徒・状態の項目・理由の項目）"""
        return [
            {
                "student": student,
                "status": self[f"status_{student.pk}"],
                "reason": self[f"reason_{student.pk}"],
            }
            for student in self.students
        ]

    def values(self):
        """{生徒の pk: (状態, 理由)}（is_valid() のあとで使う）"""
        return {
            s.pk: (self.cleaned_data[f"status_{s.pk}"], self.cleaned_data[f"reason_{s.pk}"])
            for s in self.students
        }
