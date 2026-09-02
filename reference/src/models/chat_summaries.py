from __future__ import annotations

from peewee import BigIntegerField, CharField, ForeignKeyField, IntegerField, TextField

from .base import BaseModel, User


class ChatSummary(BaseModel):
    summary_id = CharField(primary_key=True)
    broadcaster = ForeignKeyField(User, on_delete="CASCADE", related_name="chat_summaries")
    room_id = BigIntegerField()
    time_ms = BigIntegerField(null=False, index=True)
    window_s = IntegerField(null=False, index=True)
    start_ms = BigIntegerField(null=False, index=True)
    summary = TextField()
    model = CharField(null=True)
    msg_count = IntegerField(null=True)
    audio_count = IntegerField(null=True)
    frame_count = IntegerField(null=True)

    @staticmethod
    def mk_id(broadcaster_login: str, window_s: int, time_ms: int) -> str:
        return f"{broadcaster_login}:{window_s}:{time_ms}"

    class Meta:
        table_name = "chat_summaries"
        indexes = (
            (("broadcaster", "window_s", "time_ms"), True),
        )
