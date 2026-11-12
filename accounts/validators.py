import re

from django.core.exceptions import ValidationError


class LetterAndDigitValidator:
    """パスワードに英字と数字の両方が入っているか確かめる

    画面の「英字（a〜z）を入れる」「数字（0〜9）を入れる」と同じルール。
    画面の ✓ は JavaScript でつけているだけなので、サーバー側でも同じことを確かめる。
    """

    def validate(self, password, user=None):
        if not re.search(r"[a-zA-Z]", password):
            raise ValidationError("英字（a〜z）を入れてください", code="password_no_letter")
        if not re.search(r"[0-9]", password):
            raise ValidationError("数字（0〜9）を入れてください", code="password_no_digit")

    def get_help_text(self):
        return "英字と数字の両方を入れてください"


# パスワードに使える文字：半角の英字・数字・記号（空白は使えない）
# \x21〜\x7e は ASCII の「!」から「~」まで。画面の JavaScript も同じ範囲で確かめている
ALLOWED_PASSWORD_PATTERN = r"[\x21-\x7e]*"


class AllowedCharactersValidator:
    """パスワードに使えない文字（全角文字・空白・絵文字など）が入っていないか確かめる"""

    def validate(self, password, user=None):
        if not re.fullmatch(ALLOWED_PASSWORD_PATTERN, password):
            raise ValidationError(
                "パスワードに不正な文字が含まれています", code="password_invalid_character"
            )

    def get_help_text(self):
        return "半角の英字・数字・記号だけが使えます"
