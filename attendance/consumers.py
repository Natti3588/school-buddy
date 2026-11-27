import asyncio

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from accounts.models import Role
from students.models import homeroom_classroom

from .models import TOKEN_INTERVAL, make_token
from .realtime import group_name


@database_sync_to_async
def get_homeroom_classroom(user):
    # つなげるのは、今の年度のクラスで担任をしている教員だけ
    if not user.is_authenticated or user.role != Role.TEACHER:
        return None
    return homeroom_classroom(user)


class AttendanceConsumer(AsyncJsonWebsocketConsumer):
    """教員の QR 画面：QR コードのトークンと、生徒の出欠の変化を送る（教員からは何も受け取らない）"""

    async def connect(self):
        self.classroom = await get_homeroom_classroom(self.scope["user"])
        if self.classroom is None:
            await self.close()
            return
        self.group = group_name(self.classroom.pk)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        self.token_task = asyncio.create_task(self.send_tokens())

    async def disconnect(self, code):
        # 画面を閉じたらトークンを出すのをやめる（40秒たつと、最後の QR コードも使えなくなる）
        if hasattr(self, "token_task"):
            self.token_task.cancel()
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def send_tokens(self):
        """つないでから ATTENDANCE_QR_MINUTES 分の間、30秒ごとに新しいトークンを送る

        時間がたったら「受付終了」を送り、トークンを出すのをやめる。
        画面の方も同じ分数で出欠管理に戻るが、画面が戻らなくても QR コードはここで止まる。
        """
        loop = asyncio.get_running_loop()
        end = loop.time() + settings.ATTENDANCE_QR_MINUTES * 60
        while (left := end - loop.time()) > 0:
            # 最後の1回は、残りの秒数だけ待つ
            wait = min(TOKEN_INTERVAL, left)
            await self.send_json({"type": "token", "token": make_token(self.classroom), "seconds": round(wait)})
            await asyncio.sleep(wait)
        await self.send_json({"type": "closed"})

    async def attendance_status(self, event):
        # realtime.notify() がグループに送ったものを、そのまま画面に渡す
        await self.send_json({"type": "status", "items": event["items"]})
