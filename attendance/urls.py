from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    # 教員（担任）
    path("", views.AttendanceTodayView.as_view(), name="today"),
    path("qr/", views.AttendanceQrView.as_view(), name="qr"),
    path("summary/", views.AttendanceSummaryView.as_view(), name="summary"),
    # 生徒（QR コードの中身はこの URL に ?t=トークン を付けたもの）
    path("scan/", views.ScanView.as_view(), name="scan"),
    path("scan/done/", views.ScanDoneView.as_view(), name="scan_done"),
]
