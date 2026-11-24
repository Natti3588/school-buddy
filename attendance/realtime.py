from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction


def group_name(classroom_id):
    """QR 画面（教員）がつなぐ WebSocket のグループ"""
    return f"attendance_classroom_{classroom_id}"


def notify(classroom_id, records):
    """QR 画面に、生徒の出欠が変わったことを送る

    保存が取り消されたときに送らないように、DB への保存が確定してから送る。
    """
    items = [r.to_item() for r in records]

    def send():
        async_to_sync(get_channel_layer().group_send)(
            group_name(classroom_id),
            # type の「.」は「_」に変わり、Consumer の attendance_status が呼ばれる
            {"type": "attendance.status", "items": items},
        )

    transaction.on_commit(send)
