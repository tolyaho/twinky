from __future__ import annotations
from enum import unique

from peewee import BigIntegerField, CharField, ForeignKeyField, TextField

from .base import BaseModel, User


class Message(BaseModel):
    """Persisted chat message parsed from Twitch IRC `PRIVMSG` events.

    Attributes:
        message_id: Globally unique identifier for the chat message (in Twitch system).
        broadcaster: Reference to the `User` representing the broadcaster whose chat
            room produced this message.
        chatter: Reference to the `User` who authored the message.
        room_id: Numeric identifier for the chat room in which the message
            appeared.
        time_ms: Millisecond epoch timestamp indicating when the message was
            sent.
        text: Raw chat body exactly as received, including emotes and commands.
        chatter_type: Role of the chatter (for example moderator, staff, or
            regular viewer) if known.
        chatter_color: Preferred username color in HEX format, or `None` when
            unspecified.
        message_reply_id: Identifier of the parent message when this entry is a
            threaded reply, otherwise `None`.
    """
    message_id = CharField(primary_key=True)
    broadcaster = ForeignKeyField(User, on_delete="CASCADE", backref="chat")
    chatter = ForeignKeyField(User, on_delete="CASCADE", backref="messages")
    room_id = BigIntegerField()
    time_ms = BigIntegerField(null=False, index=True)
    text = TextField()
    chatter_type = CharField(max_length=10)

    class Meta:
        table_name = "messages"


class MessageReason(BaseModel):
    message = ForeignKeyField(Message, on_delete="CASCADE", backref="reasons", unique=True)
    category = CharField(max_length=100)
    text = TextField()
    time_ms = BigIntegerField(null=False, index=True)

    class Meta:
        table_name = "message_reasons"
