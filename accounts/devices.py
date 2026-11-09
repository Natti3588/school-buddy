"""生徒の端末の登録（代返を防ぐため、生徒のアカウントとタブレットを1対1で結びつける）

端末は Cookie に保存した UUID で見分ける。生徒がログインするときだけ使い、教員などのログインでは使わない。
"""

import uuid
from datetime import timedelta

from django.conf import settings

DEVICE_COOKIE_NAME = "device_id"
# Chrome は Cookie の期限を最長 400 日に切り詰めるので、それに合わせる
# （生徒がログインするたびに期限を延ばすので、400 日に 1 回ログインすれば消えない）
DEVICE_COOKIE_MAX_AGE = timedelta(days=400)


def read_device_id(request):
    """Cookie から端末の UUID を読む。ない・形が正しくないときは None"""
    value = request.COOKIES.get(DEVICE_COOKIE_NAME)
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def is_device_allowed(user, device_id, device_owner):
    """この端末から、この生徒がログインしてよいか

    user:         ログインしようとしている生徒（User）。user.device_id は登録済みの端末（未登録なら None）
    device_id:    今使っている端末の UUID（Cookie がなければ None）
    device_owner: device_id をすでに登録している User（誰も登録していない・Cookie がないときは None）
    """
    if user.device_id is not None:
        # 登録済みの生徒は、登録した端末からだけログインできる（1アカウント1端末）
        # Cookie がない（None）ときも一致しないのでログインできない
        return device_id == user.device_id
    # 未登録の生徒は、他の生徒が登録している端末ではログインできない（1端末1アカウント）
    # Cookie がない・まだ誰も登録していない端末なら、その端末で登録する
    return device_owner is None


def set_device_cookie(response, device_id):
    """端末の UUID を Cookie に保存する（期限もここで延びる）"""
    response.set_cookie(
        DEVICE_COOKIE_NAME,
        str(device_id),
        max_age=DEVICE_COOKIE_MAX_AGE,
        # JavaScript から読めないようにする
        httponly=True,
        # HTTPS のときだけ送るかどうかは、ログインの Cookie（セッション）と同じにする
        # （本番が HTTP のまま Secure を付けると Cookie が戻ってこず、2回目からログインできなくなる）
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="Lax",
    )
