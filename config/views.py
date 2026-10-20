from django.db.models import Count
from django.utils import timezone
from django.views.generic import TemplateView

from accounts.mixins import RoleRequiredMixin
from accounts.models import Role
from schools.models import School

# 仮データ（時間割の機能を作ったら DB から取得する）
PERIODS = [1, 2, 3, 4, 5, 6]

# 今日の自分の授業  値：(クラス, 教科, 種別)  種別 = normal / sub(補欠) / event(行事)
TODAY_TIMETABLE = {
    1: ("3年2組", "数学", "normal"),
    2: ("3年1組", "数学", "normal"),
    4: ("1年3組", "数学", "normal"),
    5: ("2年1組", "理科", "sub"),
}


class TopView(RoleRequiredMixin, TemplateView):
    """教員のトップ画面"""

    template_name = "dashboard.html"
    allowed_roles = [Role.TEACHER]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 空きコマは None にして、テンプレート側で「空き」と表示する
        context["today"] = [(p, TODAY_TIMETABLE.get(p)) for p in PERIODS]
        return context


def current_school_year():
    # 年度は4月始まり（1〜3月は前の年の年度）
    today = timezone.localdate()
    return today.year if today.month >= 4 else today.year - 1


class SchoolAdminTopView(RoleRequiredMixin, TemplateView):
    """学校管理者（校長）のトップ画面"""

    template_name = "school_admin/top.html"
    allowed_roles = [Role.SCHOOL_ADMIN]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = self.request.user.school
        # 教員アカウントの数（校長などの学校管理者も含む）
        context["teacher_count"] = school.teachers.count()
        # クラスごとの生徒数は Count でまとめて数える（クラスごとに SQL を出さない）
        # Count を使うと Meta の ordering が効かなくなるので、並び順をここで指定する
        context["classrooms"] = (
            school.classrooms.select_related("homeroom_teacher")
            .annotate(student_count=Count("students"))
            .order_by("grade", "number")
        )
        # クラスにはまだ年度の項目がないので、今の年度を表示するだけ
        context["school_year"] = current_school_year()
        return context


class SystemAdminTopView(RoleRequiredMixin, TemplateView):
    """管理者のトップ画面"""

    template_name = "system_admin/top.html"
    allowed_roles = [Role.SYSTEM_ADMIN]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["school_count"] = School.objects.count()
        # 今月1日の 0:00（日本時間）以降に登録された学校の数
        month_start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        context["new_school_count"] = School.objects.filter(registered_at__gte=month_start).count()
        context["recent_schools"] = School.objects.order_by("-registered_at", "-pk")[:5]
        return context
