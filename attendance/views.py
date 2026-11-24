from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from accounts.mixins import RoleRequiredMixin
from accounts.models import Role
from students.models import current_school_year, homeroom_classroom

from .forms import DailyAttendanceForm
from .models import (
    ALERT_ABSENT_DAYS,
    TERM_CHOICES,
    Reason,
    ScanError,
    Status,
    record_scan,
    reception_times_text,
    save_daily,
    summarize,
    term_range,
    todays_record,
    todays_records,
)
from .realtime import notify


def initial_values(students, records):
    """今日の出欠の画面を開いたときの表示 {生徒の pk: (状態, 理由)}"""
    # まだ誰の記録もない日は、全員「出席」から始める（違う生徒だけ先生が変える）
    if not records:
        return {s.pk: (Status.PRESENT, "") for s in students}
    # QR コードで出席を取った日は、読まなかった生徒（記録がない）を「欠席」にする
    return {
        s.pk: (records[s.pk].status, records[s.pk].reason) if s.pk in records else (Status.ABSENT, "")
        for s in students
    }


class AttendanceTodayView(RoleRequiredMixin, View):
    """今日の出欠（担任のクラス）"""

    allowed_roles = [Role.TEACHER]
    template_name = "attendance/today.html"

    def get(self, request):
        classroom = homeroom_classroom(request.user)
        if classroom is None:
            return self.render(classroom, None)
        return self.render(classroom, self.make_form(classroom))

    def post(self, request):
        classroom = homeroom_classroom(request.user)
        if classroom is None:
            raise Http404
        form = self.make_form(classroom, data=request.POST)
        if not form.is_valid():
            return self.render(classroom, form)
        kept = save_daily(form.students, form.values(), form.cleaned_data["loaded_at"])
        if kept:
            names = "、".join(f"{s.name}さん" for s in kept)
            messages.info(request, f"{names}は、画面を開いたあとでQRコードを読み取ったので、読み取った結果のままにしました。")
        # QR 画面を開いていれば、一覧を保存した内容にそろえる
        notify(classroom.pk, todays_records(classroom).values())
        # 再読み込みでもう一度送らないように、保存のあとはリダイレクトする
        return redirect(reverse("attendance:today") + "?saved=1")

    def make_form(self, classroom, data=None):
        students = list(classroom.students.order_by("attendance_number"))
        return DailyAttendanceForm(
            data,
            students=students,
            initial_values=initial_values(students, todays_records(classroom)),
        )

    def render(self, classroom, form):
        context = {
            "classroom": classroom,
            "form": form,
            "times": reception_times_text(),
            "saved": self.request.GET.get("saved") == "1",
            "from_qr": self.request.GET.get("qr") == "1",
        }
        if form is not None:
            rows = form.rows()
            status_labels = dict(Status.choices)
            reason_labels = dict(Reason.choices)
            for row in rows:
                # 画面に出している状態（送り直したときは、先生が選んだ状態）
                row["value"] = row["status"].value()
                row["status_label"] = status_labels.get(row["value"], "")
                row["reason_label"] = reason_labels.get(row["reason"].value(), "")
            context["rows"] = rows
            context["counts"] = [
                (value, label, sum(1 for r in rows if r["value"] == value))
                for value, label in Status.choices
            ]
        return render(self.request, self.template_name, context)


class AttendanceQrView(RoleRequiredMixin, TemplateView):
    """QR コードで出席（教室のテレビや黒板に映す）"""

    allowed_roles = [Role.TEACHER]
    template_name = "attendance/qr.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom = homeroom_classroom(self.request.user)
        context["classroom"] = classroom
        if classroom is not None:
            context["students"] = classroom.students.order_by("attendance_number")
            # 画面を開いた時点の出欠（そのあとの変化は WebSocket で届く）
            context["items"] = [r.to_item() for r in todays_records(classroom).values()]
            context["times"] = reception_times_text()
            context["scan_path"] = reverse("attendance:scan")
        return context


class AttendanceSummaryView(RoleRequiredMixin, TemplateView):
    """期間集計（学年・学期ごと）"""

    allowed_roles = [Role.TEACHER]
    template_name = "attendance/summary.html"

    def get(self, request, *args, **kwargs):
        # 知らない期間が指定されたときは、はじめの「学年」に戻す
        if request.GET.get("term", "year") not in dict(TERM_CHOICES):
            return redirect("attendance:summary")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom = homeroom_classroom(self.request.user)
        context["classroom"] = classroom
        if classroom is None:
            return context
        term = self.request.GET.get("term", "year")
        school_year = current_school_year()
        start, end = term_range(term, school_year)
        context.update(summarize(classroom, start, end))
        today = timezone.localdate()
        context.update({
            "term": term,
            "term_choices": TERM_CHOICES,
            "term_label": f"{school_year}年度 {dict(TERM_CHOICES)[term]}",
            "start": start,
            "end": end,
            "not_started": start > today,
            "ongoing": start <= today <= end,
            "alert_days": ALERT_ABSENT_DAYS,
        })
        return context


class ScanView(RoleRequiredMixin, View):
    """生徒：QR コードを読み取って出席する"""

    allowed_roles = [Role.STUDENT]
    template_name = "attendance/scan.html"

    def get(self, request):
        record = todays_record(request.user.student)
        # 今日もう出席している生徒には、出席完了の画面を見せる
        if record is not None and record.status != Status.ABSENT:
            return redirect("attendance:scan_done")
        return self.render()

    def post(self, request):
        student = request.user.student
        try:
            record, changed = record_scan(student, request.POST.get("token", ""))
        except ScanError as e:
            # 読み取り画面に理由を出して、もう一度読めるようにする
            return self.render(error=str(e), status=400)
        if changed:
            notify(student.classroom_id, [record])
        # 再読み込みでもう一度送らないように、出席完了の画面へはリダイレクトで移る
        return redirect("attendance:scan_done")

    def render(self, error="", status=200):
        context = {
            "student": self.request.user.student,
            "error": error,
            "times": reception_times_text(),
        }
        return render(self.request, self.template_name, context, status=status)


class ScanDoneView(RoleRequiredMixin, TemplateView):
    """生徒：出席完了"""

    allowed_roles = [Role.STUDENT]
    template_name = "attendance/scan_done.html"

    def get(self, request, *args, **kwargs):
        self.record = todays_record(request.user.student)
        # まだ出席していないときは、読み取り画面に戻す
        if self.record is None or self.record.status == Status.ABSENT:
            return redirect("attendance:scan")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["student"] = self.request.user.student
        context["record"] = self.record
        return context
