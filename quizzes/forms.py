from django import forms

from .models import AVAILABLE_SUBJECTS, SUBJECT_FORMATS, Choice, Kind, Question, Quiz, Section


class QuizForm(forms.ModelForm):
    """1. 基本情報"""

    # 選べるのは今使える教科だけ（画面にはほかの教科も「準備中」で出す）
    subject = forms.ChoiceField(label="教科", choices=[(s.value, s.label) for s in AVAILABLE_SUBJECTS])

    class Meta:
        model = Quiz
        fields = ["subject", "kind", "title", "date", "minutes", "mode"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # テストの種類は「選択してください」から選ぶ
        self.fields["kind"].choices = [("", "選択してください"), *Kind.choices]
        if not self.instance.pk:
            # 新しく作るときは、種類と出力方式を何も選ばれていない状態にする（モデルの初期値を使わない）
            for name in ["kind", "mode"]:
                self.fields[name].initial = None
                self.initial.pop(name, None)
        self.fields["kind"].label = "テストの種類"
        # 空欄のときのメッセージ（選ぶ項目は「〇〇を選んでください」、入力する項目は「〇〇を入力してください」）
        for name, field in self.fields.items():
            verb = "選んで" if name in ["subject", "kind", "mode"] else "入力して"
            field.error_messages["required"] = f"{field.label}を{verb}ください"

    def clean_subject(self):
        subject = self.cleaned_data["subject"]
        # 教科を変えると、今ある大問の形式が使えなくなることがある
        # （何も入力していない大問は、教科を変えたときに作り直すのでかまわない）
        if self.instance.pk:
            types = SUBJECT_FORMATS[subject]["types"]
            unusable = [s for s in self.instance.sections.exclude(qtype__in=types) if not s.is_blank()]
            if unusable:
                names = "・".join(sorted({s.get_qtype_display() for s in unusable}))
                raise forms.ValidationError(
                    f"この教科では使えない形式の大問（{names}）があります。先に問題入力で削除してください"
                )
        return subject


class SectionForm(forms.ModelForm):
    """大問（問題入力画面で大問ごとに1つ作る）"""

    class Meta:
        model = Section
        fields = ["qtype", "instruction", "script", "passage", "words"]

    def __init__(self, *args, subject, **kwargs):
        super().__init__(*args, **kwargs)
        # 形式は、その教科のフォーマットにあるものだけ
        types = SUBJECT_FORMATS[subject]["types"]
        self.fields["qtype"].choices = [(t.value, t.label) for t in types]


class QuestionForm(forms.ModelForm):
    """小問"""

    class Meta:
        model = Question
        fields = ["text", "answer", "points"]
        error_messages = {"points": {"required": "配点を入力してください"}}


class ChoiceForm(forms.ModelForm):
    """選択肢（正解は小問ごとのラジオボタンで選ぶので、ここは内容だけ）"""

    class Meta:
        model = Choice
        fields = ["text"]
