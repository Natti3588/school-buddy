from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

# 仮データ（時間割の機能を作ったら DB から取得する）
PERIODS = [1, 2, 3, 4, 5, 6]

# 今日の自分の授業  値：(クラス, 教科, 種別)  種別 = normal / sub(補欠) / event(行事)
TODAY_TIMETABLE = {
    1: ("3年2組", "数学", "normal"),
    2: ("3年1組", "数学", "normal"),
    4: ("1年3組", "数学", "normal"),
    5: ("2年1組", "理科", "sub"),
}


class TopView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 空きコマは None にして、テンプレート側で「空き」と表示する
        context["today"] = [(p, TODAY_TIMETABLE.get(p)) for p in PERIODS]
        return context
