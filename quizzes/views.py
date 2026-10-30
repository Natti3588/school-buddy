import io

from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from accounts.mixins import RoleRequiredMixin
from accounts.models import Role
from students.models import current_school_year

from .forms import ChoiceForm, QuestionForm, QuizForm, SectionForm
from .models import (
    CHOICE_SYMBOLS,
    ENGLISH_WRITTEN_PLACEHOLDER,
    INSTRUCTION_PLACEHOLDERS,
    SUBJECT_FORMATS,
    Choice,
    Mode,
    Question,
    QuestionType,
    Quiz,
    Section,
    Status,
    Subject,
    circled_number,
)
from .pdf import SHEETS, make_quiz_pdf

# 数学の問題入力で、ボタンから入れられる記号
MATH_SYMBOLS = ["²", "³", "√", "π", "×", "÷", "−", "≦", "≧", "°", "／"]


class QuizMixin(RoleRequiredMixin):
    allowed_roles = [Role.TEACHER]

    def get_quiz(self, pk, editable=True):
        # 自分が作ったテストだけ扱える（URL を書き換えても他の先生のテストは見えない）
        quiz = get_object_or_404(Quiz, pk=pk, author=self.request.user)
        if editable and not quiz.is_editable():
            raise Http404("受付を始めたテストは編集できません")
        return quiz


class QuizListView(QuizMixin, ListView):
    """テスト一覧"""

    template_name = "quizzes/list.html"
    context_object_name = "quizzes"
    extra_context = {"sheets": SHEETS}

    def get_queryset(self):
        return Quiz.objects.filter(author=self.request.user)


class QuizNewView(QuizMixin, View):
    """1. 基本情報（新しく作るとき・「基本情報に戻る」で直すとき）"""

    def get(self, request, pk=None):
        quiz = self.get_quiz(pk) if pk else None
        return self.render_form(QuizForm(instance=quiz), quiz)

    def post(self, request, pk=None):
        quiz = self.get_quiz(pk) if pk else None
        form = QuizForm(request.POST, instance=quiz)
        if not form.is_valid():
            return self.render_form(form, quiz)
        is_new = quiz is None
        subject_changed = "subject" in form.changed_data
        with transaction.atomic():
            quiz = form.save(commit=False)
            if is_new:
                quiz.author = request.user
            quiz.save()
            if subject_changed and not is_new:
                # 教科を変えたら、何も入力していない大問は消して、新しい教科のフォーマットで作り直す
                for section in quiz.sections.prefetch_related("questions__choices"):
                    if section.is_blank():
                        section.delete()
            if (is_new or subject_changed) and not quiz.sections.exists():
                add_blank_sections(quiz)
        # 作り始めたテストは「作成中」として保存しておき、続けて問題を入力する
        return redirect("quizzes:questions", pk=quiz.pk)

    def render_form(self, form, quiz):
        return render(
            self.request,
            "quizzes/new.html",
            {
                "form": form,
                "quiz": quiz,
                # (値, 表示名, 使えるか)  使えない教科は「準備中」と出す
                "subjects": [(s.value, s.label, s in SUBJECT_FORMATS) for s in Subject],
                "modes": [
                    (Mode.PRINT, "問題用紙・解答用紙・模範解答をPDFで出力して印刷します。"),
                    (Mode.ONLINE, "生徒がタブレットで受験します。選択式・計算・穴埋めは自動で採点されます。"),
                ],
            },
        )


class QuizQuestionsView(QuizMixin, View):
    """2. 問題入力

    画面のボタン（大問・小問の追加と削除、下書き保存、プレビュー）は、すべて同じフォームから送る。
    先に入力中の内容を保存してから、押されたボタンの処理をするので、入力した内容が消えない。
    """

    def get(self, request, pk):
        quiz = self.get_quiz(pk)
        return self.render_page(quiz, self.build_forms(quiz))

    def post(self, request, pk):
        quiz = self.get_quiz(pk)
        blocks = self.build_forms(quiz, request.POST)
        if not all_valid(blocks):
            return self.render_page(quiz, blocks)
        with transaction.atomic():
            save_blocks(blocks, request.POST)
            action, _, value = request.POST.get("action", "save").partition(":")
            if action == "add_section" and value in SUBJECT_FORMATS[quiz.subject]["types"]:
                add_question(quiz.sections.create(qtype=value))
            elif action == "delete_section":
                quiz.sections.filter(pk=value).delete()
            elif action == "add_question":
                add_question(get_object_or_404(quiz.sections, pk=value))
            elif action == "delete_question":
                Question.objects.filter(section__quiz=quiz, pk=value).delete()
        if action == "back":
            return redirect("quizzes:edit", pk=quiz.pk)
        if action == "preview":
            errors = check_questions(quiz)
            if errors:
                return self.render_page(quiz, self.build_forms(quiz), errors=errors)
            return redirect("quizzes:preview", pk=quiz.pk)
        url = reverse("quizzes:questions", kwargs={"pk": quiz.pk})
        return redirect(url + ("?saved=1" if action == "save" else ""))

    def build_forms(self, quiz, data=None):
        """大問 → 小問 → 選択肢 の入れ子で、画面に出すフォームを作る"""
        blocks = []
        for section in quiz.sections.prefetch_related("questions__choices"):
            items = []
            for question in section.questions.all():
                choices = [
                    (symbol, choice, ChoiceForm(data, instance=choice, prefix=f"c{choice.pk}"))
                    for symbol, choice in zip(CHOICE_SYMBOLS, question.choices.all())
                ]
                items.append(
                    {
                        "question": question,
                        "form": QuestionForm(data, instance=question, prefix=f"q{question.pk}"),
                        "choices": choices,
                    }
                )
            is_english_written = quiz.subject == Subject.ENGLISH and section.qtype == QuestionType.WRITTEN
            blocks.append(
                {
                    "section": section,
                    "form": SectionForm(data, instance=section, prefix=f"s{section.pk}", subject=quiz.subject),
                    "items": items,
                    "placeholder": (
                        ENGLISH_WRITTEN_PLACEHOLDER if is_english_written else INSTRUCTION_PLACEHOLDERS[section.qtype]
                    ),
                    # 英作文は指示文だけで問題になるので、問題文は任意
                    "text_optional": is_english_written,
                }
            )
        return blocks

    def render_page(self, quiz, blocks, errors=None):
        return render(
            self.request,
            "quizzes/questions.html",
            {
                "quiz": quiz,
                "blocks": blocks,
                "errors": errors or [],
                "fmt": SUBJECT_FORMATS[quiz.subject],
                "math_symbols": MATH_SYMBOLS,
                "saved": self.request.GET.get("saved") == "1",
            },
        )


def all_valid(blocks):
    # 全部のフォームを検証して、エラーを画面に出す（途中で止めない）
    forms = []
    for block in blocks:
        forms.append(block["form"])
        for item in block["items"]:
            forms.append(item["form"])
            forms.extend(form for _, _, form in item["choices"])
    return all([form.is_valid() for form in forms])


def save_blocks(blocks, data):
    for block in blocks:
        section = block["form"].save()
        for item in block["items"]:
            question = item["form"].save()
            for _, _, form in item["choices"]:
                form.save()
            # 正解の選択肢は、小問ごとのラジオボタン（値は選択肢の id）で送られてくる
            correct = data.get(f"q{question.pk}-correct", "")
            question.choices.update(is_correct=False)
            question.choices.filter(pk=correct if correct.isdigit() else None).update(is_correct=True)
            # 形式を変えたときは、選択肢を作る・消す
            if section.uses_choices() and not question.choices.exists():
                add_choices(question)
            elif not section.uses_choices():
                question.choices.all().delete()


def add_blank_sections(quiz):
    """教科のフォーマットにある形式の大問を、1つずつ空で作る（小問も1つずつ）"""
    for qtype in SUBJECT_FORMATS[quiz.subject]["types"]:
        # 英語の選択式は、リスニングと同じ形なので最初は作らない（「＋ 大問を追加」から足せる）
        if quiz.subject == Subject.ENGLISH and qtype == QuestionType.CHOICE:
            continue
        add_question(quiz.sections.create(qtype=qtype))


def add_question(section):
    question = section.questions.create()
    if section.uses_choices():
        add_choices(question)


def add_choices(question):
    Choice.objects.bulk_create(Choice(question=question) for _ in CHOICE_SYMBOLS)


def check_questions(quiz):
    """プレビューに進む前のチェック（下書き保存のときは空欄があってもよい）

    画面の JavaScript と同じ順番・同じ文で、空の必須項目をすべて返す。
    JavaScript が動かないときや、別のタブで変えたときのために、サーバーでも同じチェックをする。
    """
    errors = []
    tail = []  # 小問が無い大問などは、最後にまとめて出す（画面と同じ）
    sections = list(quiz.sections.prefetch_related("questions__choices"))
    for sn, section in enumerate(sections, start=1):
        where = f"大問{sn}"
        if not section.instruction:
            errors.append(f"{where}：指示文を入力してください")
        if section.qtype == QuestionType.LISTENING and not section.script:
            errors.append(f"{where}：放送文を入力してください")
        if section.qtype == QuestionType.READING and not section.passage:
            errors.append(f"{where}：本文を入力してください")
        questions = list(section.questions.all())
        if not questions:
            tail.append(f"{where}：小問を1つ以上追加してください")
        for qn, question in enumerate(questions, start=1):
            wq = f"{where}（{qn}）"
            # 英作文は指示文だけで問題になるので、問題文は空でもよい
            if not question.text and not (quiz.subject == Subject.ENGLISH and section.qtype == QuestionType.WRITTEN):
                label = "式" if section.qtype == QuestionType.CALC else "問題文"
                errors.append(f"{wq}：{label}を入力してください")
            if section.uses_choices():
                for symbol, choice in question.symbol_choices():
                    if not choice.text:
                        errors.append(f"{wq}：選択肢「{symbol}」を入力してください")
                if not question.correct_symbol():
                    errors.append(f"{wq}：正解の選択肢にチェックしてください")
            elif not question.answer:
                label = "模範解答" if section.is_manual() else "正解"
                errors.append(f"{wq}：{label}を入力してください")
    if not sections:
        tail.append("大問を1つ以上追加してください（下の「＋ 大問を追加」から形式を選べます）")
    return errors + tail


class QuizPreviewView(QuizMixin, View):
    """3. プレビュー"""

    def get(self, request, pk):
        quiz = self.get_quiz(pk)
        sheet = request.GET.get("sheet")
        if sheet not in SHEETS:
            sheet = "question"
        return render(
            request,
            "quizzes/preview.html",
            {
                "quiz": quiz,
                # 問題用紙の大問番号は ①②③… にする
                "sections": [
                    (circled_number(n), section)
                    for n, section in enumerate(quiz.sections.prefetch_related("questions__choices"), start=1)
                ],
                "sheet": sheet,
                "sheet_label": SHEETS[sheet],
                "sheets": SHEETS,
                "school_year": current_school_year(),
            },
        )

    def post(self, request, pk):
        quiz = self.get_quiz(pk)
        # プレビューを開いている間に問題入力を別のタブで変えることもあるので、もう一度チェックする
        if check_questions(quiz):
            return redirect("quizzes:questions", pk=quiz.pk)
        quiz.status = Status.READY
        quiz.save(update_fields=["status"])
        return redirect("quizzes:created", pk=quiz.pk)


class QuizCreatedView(QuizMixin, View):
    """4. 完成"""

    def get(self, request, pk):
        quiz = self.get_quiz(pk)
        if quiz.status == Status.DRAFT:
            return redirect("quizzes:questions", pk=quiz.pk)
        return render(request, "quizzes/created.html", {"quiz": quiz, "sheets": SHEETS})


class QuizPdfView(QuizMixin, View):
    """印刷用PDF（問題用紙・解答用紙・模範解答）"""

    def get(self, request, pk, sheet):
        # 受付を始めたあとのテストも印刷できるようにする
        quiz = self.get_quiz(pk, editable=False)
        if sheet not in SHEETS:
            raise Http404("用紙の種類が正しくありません")
        # 作成中のテストは問題がそろっていないことがあるので、問題入力に戻す
        if quiz.status == Status.DRAFT:
            return redirect("quizzes:questions", pk=quiz.pk)
        pdf = make_quiz_pdf(quiz, sheet, school_year=current_school_year())
        # as_attachment=False で、ダウンロードではなくブラウザの新しいタブで開く
        filename = f"{quiz.get_subject_display()}_{quiz.title}_{SHEETS[sheet]}.pdf"
        return FileResponse(io.BytesIO(pdf), as_attachment=False, filename=filename, content_type="application/pdf")
