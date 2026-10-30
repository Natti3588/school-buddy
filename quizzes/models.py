from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Subject(models.TextChoices):
    MATH = "math", "数学"
    ENGLISH = "eng", "英語"
    JAPANESE = "jpn", "国語"
    SCIENCE = "sci", "理科"
    SOCIAL = "soc", "社会"


# 今使える教科（ほかの教科は画面に「準備中」と出す）
AVAILABLE_SUBJECTS = [Subject.MATH, Subject.ENGLISH]


class Kind(models.TextChoices):
    QUIZ = "quiz", "小テスト"
    CHECK = "check", "確認テスト"
    MIDTERM = "midterm", "定期テスト（中間）"
    FINAL = "final", "定期テスト（期末）"


class Mode(models.TextChoices):
    PRINT = "print", "PDF"
    ONLINE = "online", "オンライン"


class Status(models.TextChoices):
    DRAFT = "draft", "作成中"
    READY = "ready", "作成済み"
    OPEN = "open", "受付中"
    CLOSED = "closed", "終了"


class QuestionType(models.TextChoices):
    CALC = "calc", "計算"
    CHOICE = "choice", "選択式"
    FILL = "fill", "穴埋め"
    LISTENING = "listening", "リスニング（選択式）"
    READING = "reading", "読解（記述式）"
    WRITTEN = "written", "記述式"


# 教科ごとに使える大問の形式と、問題入力画面に出す説明
SUBJECT_FORMATS = {
    Subject.MATH: {
        "note": "計算・選択式・文章題（記述式）。数式を入力できます。",
        "types": [QuestionType.CALC, QuestionType.CHOICE, QuestionType.WRITTEN],
    },
    Subject.ENGLISH: {
        "note": "リスニング・穴埋め（語彙・文法）・読解・英作文。放送文と本文を入力できます。",
        "types": [
            QuestionType.LISTENING,
            QuestionType.FILL,
            QuestionType.CHOICE,
            QuestionType.READING,
            QuestionType.WRITTEN,
        ],
    },
}

# 大問の指示文の入力例（形式ごと。記述式だけは教科で変える）
INSTRUCTION_PLACEHOLDERS = {
    QuestionType.CALC: "例：次の方程式を解きなさい。",
    QuestionType.CHOICE: "例：正しいものを選びなさい。",
    QuestionType.WRITTEN: "例：次の問いに答えなさい。式も書くこと。",
    QuestionType.LISTENING: "例：放送を聞いて、正しいものを選びなさい。",
    QuestionType.FILL: "例：（　）に入る適切な語を書きなさい。",
    QuestionType.READING: "例：次の英文を読んで、問いに日本語で答えなさい。",
}
ENGLISH_WRITTEN_PLACEHOLDER = "例：昨日したことを英語1文で書きなさい。"

# 選択肢を使う形式
CHOICE_TYPES = [QuestionType.CHOICE, QuestionType.LISTENING]
# オンラインで先生が採点する形式（ほかは自動で採点する）
MANUAL_TYPES = [QuestionType.READING, QuestionType.WRITTEN]
# 選択肢の記号（選択式の小問を追加したときは4つ作る）
CHOICE_SYMBOLS = "アイウエ"


def circled_number(n):
    """問題用紙の大問番号（①〜⑳。21からは (21) のようにする）"""
    return chr(0x2460 + n - 1) if 1 <= n <= 20 else f"({n})"


class Quiz(models.Model):
    # 作成した先生が削除されても、テストと結果は残す
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="quizzes",
        verbose_name="作成者",
    )
    subject = models.CharField("教科", max_length=10, choices=Subject.choices)
    kind = models.CharField("種類", max_length=10, choices=Kind.choices, default=Kind.QUIZ)
    title = models.CharField("タイトル", max_length=100)
    date = models.DateField("実施日", null=True, blank=True)
    minutes = models.PositiveSmallIntegerField(
        "制限時間",
        null=True,
        blank=True,
        validators=[MinValueValidator(5), MaxValueValidator(120)],
    )
    mode = models.CharField("出力方式", max_length=10, choices=Mode.choices, default=Mode.PRINT)
    status = models.CharField("状態", max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = "テスト"
        verbose_name_plural = "テスト"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def questions(self):
        """すべての小問（大問の順・小問の順）"""
        return Question.objects.filter(section__quiz=self).order_by("section", "pk")

    def total_points(self):
        return sum(q.points for q in self.questions())

    def manual_section_count(self):
        """先生が採点する大問の数"""
        return self.sections.filter(qtype__in=MANUAL_TYPES).count()

    def is_editable(self):
        # 受付を始めたあとは、問題を変えると採点が合わなくなるので編集させない
        return self.status in [Status.DRAFT, Status.READY]


class Section(models.Model):
    """大問"""

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="sections", verbose_name="テスト")
    qtype = models.CharField("形式", max_length=10, choices=QuestionType.choices)
    instruction = models.CharField("指示文", max_length=200, blank=True)
    # リスニングの放送文（生徒には表示しない）
    script = models.TextField("放送文", blank=True)
    # 読解の本文
    passage = models.TextField("本文", blank=True)
    # 英作文の語数（例：5語以上）
    words = models.CharField("語数の指定", max_length=50, blank=True)

    class Meta:
        verbose_name = "大問"
        verbose_name_plural = "大問"
        # 追加した順に並べる
        ordering = ["quiz", "pk"]

    def __str__(self):
        return f"{self.quiz}：{self.get_qtype_display()}"

    def uses_choices(self):
        return self.qtype in CHOICE_TYPES

    def is_manual(self):
        return self.qtype in MANUAL_TYPES

    def total_points(self):
        return sum(q.points for q in self.questions.all())

    def is_blank(self):
        """何も入力していない大問か（配点は初期値が入っているので見ない）"""
        if self.instruction or self.script or self.passage or self.words:
            return False
        for question in self.questions.all():
            if question.text or question.answer or any(c.text or c.is_correct for c in question.choices.all()):
                return False
        return True


class Question(models.Model):
    """小問"""

    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="questions", verbose_name="大問"
    )
    text = models.TextField("問題文", blank=True)
    # 選択式は選択肢の「正解」で決めるので、ここは使わない
    answer = models.CharField("正解（模範解答）", max_length=200, blank=True)
    points = models.PositiveSmallIntegerField(
        "配点", default=10, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    class Meta:
        verbose_name = "小問"
        verbose_name_plural = "小問"
        ordering = ["section", "pk"]

    def __str__(self):
        return self.text[:30] or f"小問 {self.pk}"

    def symbol_choices(self):
        """(記号, 選択肢) の組（ア・イ・ウ・エ の順）"""
        return list(zip(CHOICE_SYMBOLS, self.choices.all()))

    def correct_symbol(self):
        """選択式の正解の記号（ア〜エ）。正解が無いときは空"""
        for symbol, choice in self.symbol_choices():
            if choice.is_correct:
                return symbol
        return ""


class Choice(models.Model):
    """選択肢（記号は並び順で ア・イ・ウ・エ と付ける）"""

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="choices", verbose_name="小問"
    )
    text = models.CharField("内容", max_length=200, blank=True)
    is_correct = models.BooleanField("正解", default=False)

    class Meta:
        verbose_name = "選択肢"
        verbose_name_plural = "選択肢"
        ordering = ["question", "pk"]

    def __str__(self):
        return self.text
