from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from accounts.mixins import RoleRequiredMixin
from accounts.models import Role
from accounts.registration import load, remember_password, stash, take_password

from .forms import SchoolForm
from .models import School, SchoolType

# 入力画面 → 確認画面 の間、入力内容をセッションに入れておくときのキー
SESSION_KEY = "school_new_data"
# 完了画面で初期パスワードを1回だけ表示するためのキー
PASSWORD_KEY = "school_registered_password"


class SchoolNewView(RoleRequiredMixin, View):
    """1. 入力"""

    allowed_roles = [Role.SYSTEM_ADMIN]
    template_name = "schools/new.html"

    def get(self, request):
        data = load(request, SESSION_KEY)
        if request.GET.get("edit") == "1" and data is not None:
            # 確認画面の「修正する」から戻ったときは、入力済みの値を表示する
            # （initial で渡すので、戻った直前にエラーが出ることはない）
            form = SchoolForm(initial=data)
        else:
            request.session.pop(SESSION_KEY, None)
            form = SchoolForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = SchoolForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        # まだ保存しない。確認画面で「登録する」を押したときに保存する
        stash(request, SESSION_KEY)
        return redirect("schools:confirm")


class SchoolConfirmView(RoleRequiredMixin, View):
    """2. 確認"""

    allowed_roles = [Role.SYSTEM_ADMIN]

    def get(self, request):
        form = self.get_form()
        if form is None:
            return redirect("schools:new")
        if not form.is_valid():
            # 入力のあとに同じ学校名が登録された場合など
            return redirect(reverse("schools:new") + "?edit=1")
        s = dict(form.cleaned_data, school_type_label=SchoolType(form.cleaned_data["school_type"]).label)
        return render(request, "schools/confirm.html", {"s": s})

    def post(self, request):
        form = self.get_form()
        if form is None:
            # 「登録する」を2回送ったときなど（1回目でセッションを消している）
            return redirect("schools:new")
        # 確認画面を開いている間に状況が変わることがあるので、保存の直前にもう一度チェックする
        if not form.is_valid():
            return redirect(reverse("schools:new") + "?edit=1")
        password = request.session[SESSION_KEY]["password"]
        school = form.save(make_password(password))
        # 完了画面で1回だけ表示する。入力内容は消す（再読み込みで二重に登録しない）
        remember_password(request, PASSWORD_KEY, str(school.pk), password)
        del request.session[SESSION_KEY]
        return redirect("schools:registered", pk=school.pk)

    def get_form(self):
        data = load(self.request, SESSION_KEY)
        if data is None:
            return None
        return SchoolForm(data, require_password=False)


class SchoolRegisteredView(RoleRequiredMixin, DetailView):
    """3. 完了"""

    allowed_roles = [Role.SYSTEM_ADMIN]
    model = School
    template_name = "schools/registered.html"
    context_object_name = "school"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["admin"] = self.object.teachers.filter(role=Role.SCHOOL_ADMIN).first()
        # 2回目に開いたとき（再読み込みなど）は None になり、「表示できません」と出す
        context["initial_password"] = take_password(self.request, PASSWORD_KEY, str(self.object.pk))
        return context
