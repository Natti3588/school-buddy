import asyncio

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from accounts.models import Role
from students.models import homeroom_classroom

from .models import (
    TOKEN_INTERVAL,
    Phase,
    make_token,
    reception_phase,
    seconds_until_next_phase,
)
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
        """受付の状態を送り、受付中は30秒ごとに新しいトークンを送る"""
        while True:
            now = timezone.localtime()
            phase = reception_phase(now)
            until_next = seconds_until_next_phase(now)
            if phase == Phase.CLOSED:
                await self.send_json({"type": "phase", "phase": phase})
                return
            # 8:40 などの切り替えの時刻には、30秒たっていなくても送り直す
            wait = min(TOKEN_INTERVAL, until_next)
            message = {"type": "phase", "phase": phase, "seconds": round(wait)}
            if phase != Phase.BEFORE:
                message["token"] = make_token(self.classroom)
            await self.send_json(message)
            await asyncio.sleep(wait)

    async def attendance_status(self, event):
        # realtime.notify() がグループに送ったものを、そのまま画面に渡す
        await self.send_json({"type": "status", "items": event["items"]})
