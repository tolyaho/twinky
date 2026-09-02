import pathlib

from peewee import MySQLDatabase
from peewee import SqliteDatabase
from .base import User, proxy_db
from . import chat
from . import audio
from . import image_annotations
from . import chat_summaries
from . import context

import os


database_path = pathlib.Path(__file__).parent.parent.parent / "db.sqlite3"

# db = MySQLDatabase(
#     os.getenv("DB_NAME"),
#     user=os.getenv("DB_USER"),
#     password=os.getenv("DB_PASSWORD"),
#     host=os.getenv("DB_HOST"),
#     port=3306,
# )
db = SqliteDatabase(database_path)

proxy_db.initialize(db)

db.create_tables([
    User,
    chat.Message,
    chat.MessageReason,
    audio.AudioTranscription,
    image_annotations.ImageAnnotation,
    chat_summaries.ChatSummary,
    context.StreamContext,
], safe=True)

__all__ = ["User", "chat", "audio", "image_annotations", "chat_summaries", "context", "db"]
