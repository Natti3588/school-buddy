from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from accounts.mixins import RoleRequiredMixin
from accounts.models import Role

from .forms import ClassroomForm, StudentForm, homeroom_classes
from .models import Student, classrooms_of_year, current_school_year

# 入力画面 → 確認画面 の間、入力内容をセッションに入れておくときのキー
SESSION_KEY = "student_new_data"


class StudentNewView(RoleRequiredMixin, View):
    """1. 入力"""

    allowed_roles = [Role.TEACHER]
    template_name = "students/new.html"

    def get(self, request):
        if request.GET.get("edit") == "1" and SESSION_KEY in request.session:
            # 確認画面の「修正する」から戻ったときは、入力済みの値を表示する
            form = StudentForm(request.session[SESSION_KEY], teacher=request.user)
        else:
            request.session.pop(SESSION_KEY, None)
            form = StudentForm(teacher=request.user)
        return self.render(form)

    def post(self, request):
        form = StudentForm(request.POST, teacher=request.user)
        if not form.is_valid():
            return self.render(form)
        # まだ保存しない。確認画面で「登録する」を押したときに保存する
        data = request.POST.dict()
        data.pop("csrfmiddlewaretoken", None)
        request.session[SESSION_KEY] = data
        return redirect("students:confirm")

    def render(self, form):
        classrooms = list(homeroom_classes(self.request.user))
        return render(self.request, self.template_name, {"form": form, "classrooms": classrooms})


class StudentConfirmView(RoleRequiredMixin, View):
    """2. 確認"""

    allowed_roles = [Role.TEACHER]

    def get(self, request):
        form = self.get_form()
        if form is None:
            return redirect("students:new")
        if not form.is_valid():
            # 入力のあとに同じ出席番号が登録された場合など
            return redirect(reverse("students:new") + "?edit=1")
        return render(request, "students/confirm.html", {"s": form.cleaned_data})

    def post(self, request):
        form = self.get_form()
        if form is None:
            return redirect("students:new")
        # 確認画面を開いている間に状況が変わることがあるので、保存の直前にもう一度チェックする
        if not form.is_valid():
            return redirect(reverse("students:new") + "?edit=1")
        student = form.save()
        del request.session[SESSION_KEY]
        return redirect("students:registered", student_id=student.student_id)

    def get_form(self):
        data = self.request.session.get(SESSION_KEY)
        if data is None:
            return None
        return StudentForm(data, teacher=self.request.user)


class StudentRegisteredView(RoleRequiredMixin, DetailView):
    """3. 完了"""

    allowed_roles = [Role.TEACHER]
    template_name = "students/registered.html"
    context_object_name = "s"
    slug_field = "student_id"
    slug_url_kwarg = "student_id"

    def get_queryset(self):
        # 自分が担任をしているクラスの生徒だけ表示できる（URL を書き換えても他の生徒は見えない）
        return Student.objects.filter(classroom__in=homeroom_classes(self.request.user))


class ClassroomNewView(RoleRequiredMixin, View):
    """クラス登録（入力 → 確認 → 完了 をこの View でまとめて扱う）"""

    allowed_roles = [Role.SCHOOL_ADMIN]

    def get(self, request, pk=None):
        if pk is not None:
            # 3. 完了（登録後のリダイレクト先）。自分の学校のクラスだけ表示できる
            classroom = get_object_or_404(request.user.school.classrooms, pk=pk)
            return render(request, "classrooms/registered.html", {"c": classroom})
        # 1. 入力
        return self.render_new(ClassroomForm(school=request.user.school))

    def post(self, request):
        form = ClassroomForm(request.POST, school=request.user.school)
        action = request.POST.get("action")
        if action == "edit":
            # 確認画面の「修正する」：入力済みの値を残したまま入力画面に戻る
            return self.render_new(form)
        if not form.is_valid():
            return self.render_new(form)
        if action == "register":
            # 確認画面の「登録する」：確認画面を開いている間に同じクラスが登録されることもあるので、
            # 保存の直前にもう一度チェックしてから保存する（上の is_valid）
            classroom = form.save()
            return redirect("classrooms:registered", pk=classroom.pk)
        # 2. 確認（まだ保存しない。入力内容は確認画面の hidden に入れて送り直す）
        return render(request, "classrooms/confirm.html", {"form": form, "c": form.cleaned_data})

    def render_new(self, form):
        school_year = current_school_year()
        return render(
            self.request,
            "classrooms/new.html",
            {
                "form": form,
                "school_year": school_year,
                # 重複して登録しないように、今の年度の登録済みクラスを横に表示する
                "classrooms": classrooms_of_year(self.request.user.school, school_year),
            },
        )
