from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import typing as tp

from peewee import BigIntegerField, CharField, ForeignKeyField, TextField

from .base import BaseModel, User


@dataclass(slots=True)
class frame_job:
    broadcaster: User
    room_id: tp.Optional[int]
    time_ms: int
    path: Path
    frame_id: str


class ImageAnnotation(BaseModel):
    """Persisted image annotation from a stream frame.

    Attributes:
        broadcaster: Reference to the `User` representing the broadcaster whose stream
            produced this annotation.
        room_id: Numeric identifier for the chat room/stream in which the annotation
            was generated.
        time_ms: Millisecond epoch timestamp indicating when the image frame was
            captured.
        annotation: Text annotation describing the content of the image frame.
    """
    annotation_id = CharField(primary_key=True)
    broadcaster = ForeignKeyField(User, on_delete="CASCADE", related_name="image_annotations")
    room_id = BigIntegerField()
    time_ms = BigIntegerField(null=False, index=True)
    annotation = TextField()

    class Meta:
        table_name = "image_annotations"
        indexes = (
            (("broadcaster", "time_ms"), True),
        )
