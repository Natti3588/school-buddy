from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DetailView, FormView, TemplateView

from students.models import classrooms_of_year, current_school_year

from .forms import FirstPasswordChangeForm, LoginForm, StudentPasswordChangeForm, TeacherForm
from .mixins import RoleRequiredMixin
from .models import Role, User
from .registration import load, remember_password, stash, take_password


class LoginView(FormView):
    template_name = "accounts/login.html"
    form_class = LoginForm

    def get_success_url(self):
        # ユーザーの種類ごとのトップ画面に移動する（login() のあとなので request.user はログインした人）
        return self.request.user.get_top_url()

    def get_form_kwargs(self):
        # AuthenticationForm は第 1 引数に request を受け取る
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        login(self.request, form.get_user())
        return super().form_valid(form)


class PasswordChangeView(RoleRequiredMixin, auth_views.PasswordChangeView):
    """生徒が自分のパスワードを変更する画面（初回ログインのあとは、ここで必ず変更させる）"""

    allowed_roles = [Role.STUDENT]
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def get_form_class(self):
        # 初回ログインのときは、今のパスワードを聞かないフォームにする
        if self.request.user.must_change_password:
            return FirstPasswordChangeForm
        return StudentPasswordChangeForm

    def form_valid(self, form):
        # 親の form_valid が form.save() でユーザーを保存するので、その前にフラグを下ろしておく
        # （保存のあとはセッションも更新されるので、ログインしたままになる）
        form.user.must_change_password = False
        return super().form_valid(form)


class PasswordChangeDoneView(RoleRequiredMixin, TemplateView):
    """パスワード変更完了画面"""

    allowed_roles = [Role.STUDENT]
    template_name = "accounts/password_change_done.html"


# ---------- 教員アカウント管理・教員登録（学校管理者） ----------

# 入力画面 → 確認画面 の間、入力内容をセッションに入れておくときのキー
TEACHER_SESSION_KEY = "teacher_new_data"
# 完了画面で初期パスワードを1回だけ表示するためのキー
TEACHER_PASSWORD_KEY = "teacher_registered_password"


class TeacherListView(RoleRequiredMixin, TemplateView):
    """教員アカウント管理（自分の学校の教員と学校管理者の一覧）"""

    allowed_roles = [Role.SCHOOL_ADMIN]
    template_name = "teachers/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = self.request.user.school
        # role の値は "school_admin" < "teacher" なので、この並びで学校管理者が先になる
        teachers = school.teachers.filter(role__in=[Role.SCHOOL_ADMIN, Role.TEACHER]).order_by("role", "furigana", "pk")
        # 担任クラスは今年度のクラスから引く（教員ごとに SQL を出さないように、まとめて1回で読む）
        homerooms = {}
        for c in classrooms_of_year(school, current_school_year()):
            # 2クラスを担任していたら、homeroom_classroom() と同じく学年・組の順で最初のクラスにする
            homerooms.setdefault(c.homeroom_teacher_id, c)
        context["school"] = school
        context["rows"] = [(t, homerooms.get(t.pk)) for t in teachers]
        return context


class TeacherNewView(RoleRequiredMixin, View):
    """1. 入力"""

    allowed_roles = [Role.SCHOOL_ADMIN]
    template_name = "teachers/new.html"

    def get(self, request):
        data = load(request, TEACHER_SESSION_KEY)
        if request.GET.get("edit") == "1" and data is not None:
            # 確認画面の「修正する」から戻ったときは、入力済みの値を表示する
            form = TeacherForm(initial=data, school=request.user.school)
        else:
            request.session.pop(TEACHER_SESSION_KEY, None)
            form = TeacherForm(school=request.user.school)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = TeacherForm(request.POST, school=request.user.school)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        # まだ保存しない。確認画面で「登録する」を押したときに保存する
        stash(request, TEACHER_SESSION_KEY)
        return redirect("teachers:confirm")


class TeacherConfirmView(RoleRequiredMixin, View):
    """2. 確認"""

    allowed_roles = [Role.SCHOOL_ADMIN]

    def get(self, request):
        form = self.get_form()
        if form is None:
            return redirect("teachers:new")
        if not form.is_valid():
            return redirect(reverse("teachers:new") + "?edit=1")
        return render(request, "teachers/confirm.html", {"t": form.cleaned_data})

    def post(self, request):
        form = self.get_form()
        if form is None:
            # 「登録する」を2回送ったときなど（1回目でセッションを消している）
            return redirect("teachers:new")
        if not form.is_valid():
            return redirect(reverse("teachers:new") + "?edit=1")
        password = request.session[TEACHER_SESSION_KEY]["password"]
        user = form.save(make_password(password))
        # 完了画面で1回だけ表示する。入力内容は消す（再読み込みで二重に登録しない）
        remember_password(request, TEACHER_PASSWORD_KEY, user.user_id, password)
        del request.session[TEACHER_SESSION_KEY]
        return redirect("teachers:registered", user_id=user.user_id)

    def get_form(self):
        data = load(self.request, TEACHER_SESSION_KEY)
        if data is None:
            return None
        return TeacherForm(data, school=self.request.user.school, require_password=False)


class TeacherRegisteredView(RoleRequiredMixin, DetailView):
    """3. 完了"""

    allowed_roles = [Role.SCHOOL_ADMIN]
    template_name = "teachers/registered.html"
    context_object_name = "t"
    slug_field = "user_id"
    slug_url_kwarg = "user_id"

    def get_queryset(self):
        # 自分の学校の教員だけ表示できる（ほかの学校の教員は 404）
        return User.objects.filter(school=self.request.user.school, role=Role.TEACHER)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 2回目に開いたとき（再読み込みなど）は None になり、「表示できません」と出す
        context["initial_password"] = take_password(self.request, TEACHER_PASSWORD_KEY, self.object.user_id)
        return context
