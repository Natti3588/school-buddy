"""学校登録・教員登録で使う、入力 → 確認 → 完了 の間の入力内容の持ち方と初期パスワードのチェック

入力内容はセッションに入れておき、確認画面で「登録する」を押したときに保存する（生徒登録と同じ形）。
完了画面で初期パスワードを1回だけ表示するので、パスワードもそのままの文字でセッションに入れる。
完了画面を開いたらセッションから消すので、そのあとは残らない。
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

# 長さ・英字・数字のどれが足りなくても、画面にはこの1つの文を出す（UI の文）
INITIAL_PASSWORD_RULE_MESSAGE = "初期パスワードは8文字以上で、英字と数字を両方入れてください"
RULE_CODES = {"password_too_short", "password_no_letter", "password_no_digit"}


def stash(request, key):
    """入力画面で送られた内容を、確認画面と保存のためにセッションに入れる"""
    data = request.POST.dict()
    data.pop("csrfmiddlewaretoken", None)
    request.session[key] = data


def load(request, key):
    """セッションに入れた入力内容（なければ None）"""
    return request.session.get(key)


def remember_password(request, key, owner, password):
    """完了画面で1回だけ表示する初期パスワードを、登録したもの（owner）と一緒に入れておく"""
    request.session[key] = {"owner": owner, "password": password}


def take_password(request, key, owner):
    """1回だけ表示する初期パスワードを取り出す（取り出したらセッションから消す）

    再読み込みなどで2回目に開いたときや、別の登録の完了画面を開いたときは None。
    """
    saved = request.session.pop(key, None)
    if saved and saved.get("owner") == owner:
        return saved.get("password")
    return None


def clean_initial_password(value):
    """初期パスワードがパスワードの規則（settings の AUTH_PASSWORD_VALIDATORS）に合うか確かめる"""
    try:
        validate_password(value)
    except ValidationError as e:
        messages = []
        if any(error.code in RULE_CODES for error in e.error_list):
            messages.append(INITIAL_PASSWORD_RULE_MESSAGE)
        # 使えない文字（全角・空白など）は、今の検証の文のまま出す
        messages += [error.messages[0] for error in e.error_list if error.code not in RULE_CODES]
        raise ValidationError(messages)
    return value
