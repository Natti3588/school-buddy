import calendar
import datetime

from django.conf import settings
from django.core import signing
from django.db import models, transaction
from django.db.models import Count, Q
from django.utils import timezone

from students.models import Student


class Status(models.TextChoices):
    # 並び順は画面のボタンの順（出席・欠席・遅刻・早退）
    PRESENT = "present", "出席"
    ABSENT = "absent", "欠席"
    LATE = "late", "遅刻"
    EARLY_LEAVE = "early_leave", "早退"


class Reason(models.TextChoices):
    # 出席以外のときに選ぶ理由
    ILLNESS = "illness", "体調不良"
    HOSPITAL = "hospital", "通院"
    FAMILY = "family", "家庭の事情"
    BEREAVEMENT = "bereavement", "忌引"
    OFFICIAL = "official", "公欠"
    OTHER = "other", "その他"


class Attendance(models.Model):
    """生徒の1日の出欠（朝のHRで1回）"""

    # 生徒を削除したら、その生徒の出欠の記録も削除する
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="attendances",
        verbose_name="生徒",
    )
    date = models.DateField("日付")
    status = models.CharField("状態", max_length=20, choices=Status.choices)
    # QR コードで付いた遅刻や、受付終了後の欠席は、先生が保存するまで理由が空になる
    reason = models.CharField("理由", max_length=20, choices=Reason.choices, blank=True)
    # 先生が一覧で付けた記録では空
    scanned_at = models.DateTimeField("QRコードで読んだ時刻", null=True, blank=True)

    class Meta:
        verbose_name = "出欠"
        verbose_name_plural = "出欠"
        ordering = ["-date", "student"]
        constraints = [
            # 同じ生徒が同時に2回 QR コードを読んでも、記録は1日1つにする
            models.UniqueConstraint(
                fields=["student", "date"],
                name="unique_attendance_per_day",
                violation_error_message="この生徒のこの日の出欠はすでにあります",
            ),
            models.CheckConstraint(
                condition=~Q(status=Status.PRESENT) | Q(reason=""),
                name="no_reason_when_present",
                violation_error_message="出席のときは理由を入れられません",
            ),
        ]

    def __str__(self):
        return f"{self.date} {self.student} {self.get_status_display()}"

    def scanned_time(self):
        """QR コードで読んだ時刻を「8:31」の形で返す（先生が付けた記録では空）"""
        if self.scanned_at is None:
            return ""
        return format_hm(timezone.localtime(self.scanned_at).time())

    def to_item(self):
        """QR 画面に送る形（WebSocket で JSON にする）"""
        return {"student": self.student_id, "status": self.status, "time": self.scanned_time()}


def format_hm(t):
    # 「08:31」ではなく「8:31」と表示する
    return f"{t.hour}:{t.minute:02d}"


# ---------- 受付の時刻 ----------

class Phase(models.TextChoices):
    BEFORE = "before", "受付前"
    OPEN = "open", "受付中"
    LATE = "late", "遅刻の時間"
    CLOSED = "closed", "受付終了"


def _parse_hm(text):
    hour, minute = text.split(":")
    return datetime.time(int(hour), int(minute))


def reception_times():
    """QR コードの受付の時刻（settings の ATTENDANCE_OPEN / LATE / CLOSE）"""
    return {
        "open": _parse_hm(settings.ATTENDANCE_OPEN),
        "late": _parse_hm(settings.ATTENDANCE_LATE),
        "close": _parse_hm(settings.ATTENDANCE_CLOSE),
    }


def reception_times_text():
    """画面に出す「8:25」などの文字"""
    return {key: format_hm(t) for key, t in reception_times().items()}


def reception_phase(now):
    times = reception_times()
    t = now.time()
    if t < times["open"]:
        return Phase.BEFORE
    if t < times["late"]:
        return Phase.OPEN
    if t < times["close"]:
        return Phase.LATE
    return Phase.CLOSED


def seconds_until_next_phase(now):
    """次に受付の状態が変わるまでの秒数（受付終了のあとは None）"""
    for t in reception_times().values():
        boundary = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        if boundary > now:
            return (boundary - now).total_seconds()
    return None


# ---------- QR コードのトークン ----------

# 新しいトークンを出す間隔と、トークンを受け付ける時間（秒）
# 切り替えの直前に読んだ生徒がはじかれないように、有効期限は10秒長くする
TOKEN_INTERVAL = 30
TOKEN_MAX_AGE = 40
# ほかの機能の署名と取り違えないように、出欠管理専用の salt にする
TOKEN_SALT = "attendance.qr"


def make_token(classroom):
    # クラスと日付を入れて署名する（ほかのクラスや前の日の QR コードをはじくため）。DB には保存しない
    return signing.dumps({"c": classroom.pk, "d": timezone.localdate().isoformat()}, salt=TOKEN_SALT)


class ScanResult(models.TextChoices):
    """QR コードを読んだあとの結果画面の種類"""

    DONE = "done", "出席"
    LATE = "late", "遅刻"
    ALREADY = "already", "読み取り済み"
    EXPIRED = "expired", "有効期限切れ"
    INVALID = "invalid", "無効なQRコード"
    BEFORE = "before", "受付前"
    CLOSED = "closed", "受付終了"


class ScanError(Exception):
    """QR コードで出席できなかったとき。result は結果画面の種類（ScanResult）"""

    def __init__(self, result):
        super().__init__(result)
        self.result = result


def record_scan(student, token):
    """QR コードを読んだ生徒を出席（遅刻の時間なら遅刻）にする

    戻り値は (今日の Attendance, 記録を変えたか)。出席できないときは ScanError を出す。
    """
    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.SignatureExpired:
        raise ScanError(ScanResult.EXPIRED)
    except signing.BadSignature:
        # 出欠管理の QR コードではない（ほかの QR コード・書き換えたトークンなど）
        raise ScanError(ScanResult.INVALID)

    now = timezone.localtime()
    today = now.date()
    # 前の日の QR コード（写真など）は、期限切れとして扱う
    if data.get("d") != today.isoformat():
        raise ScanError(ScanResult.EXPIRED)
    # ほかのクラスの QR コードは、自分のクラスでは無効
    if data.get("c") != student.classroom_id:
        raise ScanError(ScanResult.INVALID)

    phase = reception_phase(now)
    if phase == Phase.BEFORE:
        raise ScanError(ScanResult.BEFORE)
    if phase == Phase.CLOSED:
        raise ScanError(ScanResult.CLOSED)
    status = Status.PRESENT if phase == Phase.OPEN else Status.LATE

    with transaction.atomic():
        record, created = Attendance.objects.get_or_create(
            student=student, date=today, defaults={"status": status, "scanned_at": now}
        )
        if created:
            return record, True
        # 先生が欠席にしたあとで来た生徒は、読み取った時刻で付け直す
        if record.status == Status.ABSENT:
            record.status = status
            record.reason = ""
            record.scanned_at = now
            record.save()
            return record, True
    # 出席・遅刻・早退が付いていれば変えない（先生の入力を優先）
    return record, False


# ---------- 今日の出欠 ----------

def todays_records(classroom):
    """今日のクラスの記録を {生徒の pk: Attendance} で返す"""
    records = Attendance.objects.filter(student__classroom=classroom, date=timezone.localdate())
    return {r.student_id: r for r in records}


def todays_record(student):
    return Attendance.objects.filter(student=student, date=timezone.localdate()).first()


def save_daily(students, values, loaded_at):
    """今日の出欠の一覧を保存する。書き換えなかった生徒のリストを返す

    values は {生徒の pk: (状態, 理由)}、loaded_at は先生が画面を開いた時刻。
    画面を開いたあとで QR コードを読んだ生徒は、開いたときの表示（欠席）で上書きしないように、書き換えない。
    """
    today = timezone.localdate()
    kept = []
    with transaction.atomic():
        records = Attendance.objects.filter(student__in=students, date=today)
        existing = {r.student_id: r for r in records}
        for student in students:
            record = existing.get(student.pk)
            if record is not None and record.scanned_at is not None and record.scanned_at > loaded_at:
                kept.append(student)
                continue
            status, reason = values[student.pk]
            Attendance.objects.update_or_create(
                student=student,
                date=today,
                # QR コードで読んだ時刻は残す（defaults に入れない）
                defaults={"status": status, "reason": "" if status == Status.PRESENT else reason},
            )
    return kept


# ---------- 期間集計 ----------

# 学期は月で決める（夏休みなど記録のない日は授業日に数えないので、休みの期間を決めなくてよい）
TERM_MONTHS = {"1": (4, 8), "2": (9, 12), "3": (1, 3)}
TERM_CHOICES = [("year", "学年"), ("1", "1学期"), ("2", "2学期"), ("3", "3学期")]
# 欠席がこの日数以上の生徒を赤で表示する
ALERT_ABSENT_DAYS = 3


def term_range(term, school_year):
    """期間の最初と最後の日（term は year / 1 / 2 / 3）"""
    if term == "year":
        return datetime.date(school_year, 4, 1), datetime.date(school_year + 1, 3, 31)
    start_month, end_month = TERM_MONTHS[term]
    # 1〜3月は次の年（年度は4月始まり）
    year = school_year if start_month >= 4 else school_year + 1
    last_day = calendar.monthrange(year, end_month)[1]
    return datetime.date(year, start_month, 1), datetime.date(year, end_month, last_day)


def summarize(classroom, start, end):
    """期間中の生徒ごとの出席日数・欠席日数・遅刻回数・早退回数

    授業日は「クラスに記録が1件でもある日」。その日に記録のない生徒は欠席に数える。
    """
    records = Attendance.objects.filter(student__classroom=classroom, date__range=(start, end))
    dates = list(records.order_by("date").values_list("date", flat=True).distinct())
    days = len(dates)
    # 生徒ごとの数を1回の SQL で数える（order_by() で Meta の並び順を外し、生徒ごとにまとめる）
    counts = {
        row["student"]: row
        for row in records.order_by().values("student").annotate(
            recorded=Count("pk"),
            absent=Count("pk", filter=Q(status=Status.ABSENT)),
            late=Count("pk", filter=Q(status=Status.LATE)),
            early=Count("pk", filter=Q(status=Status.EARLY_LEAVE)),
        )
    }
    rows = []
    for student in classroom.students.order_by("attendance_number"):
        c = counts.get(student.pk, {})
        absent = c.get("absent", 0) + days - c.get("recorded", 0)
        rows.append({
            "student": student,
            "present": days - absent,
            "absent": absent,
            "late": c.get("late", 0),
            "early": c.get("early", 0),
        })
    return {
        "days": days,
        "first": dates[0] if dates else None,
        "last": dates[-1] if dates else None,
        "rows": rows,
    }
