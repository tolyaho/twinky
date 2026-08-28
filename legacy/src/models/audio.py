from .base import BaseModel, User
from peewee import (
    ForeignKeyField,
    TextField,
    BooleanField,
    BigIntegerField
)


class AudioTranscription(BaseModel):
    """Result of Deepgram's transcription."""
    broadcaster = ForeignKeyField(User, on_delete="CASCADE", related_name="speech")
    text = TextField()
    is_final = BooleanField(index=True)
    start_ms = BigIntegerField(null=False, index=True)
    end_ms = BigIntegerField(null=False, index=True)

    class Meta:
        table_name = "audio_transcriptions"
