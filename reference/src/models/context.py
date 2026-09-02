from __future__ import annotations

from peewee import BigIntegerField, CharField, ForeignKeyField, TextField

from .base import BaseModel, User


class StreamContext(BaseModel):
    """Model for saving description of some broadcast"""
    broadcaster = ForeignKeyField(User, on_delete="CASCADE", related_name="chat")
    time_ms = BigIntegerField(null=False, index=True)
    text = TextField()

    class Meta:
        table_name = "stream_contexts"
