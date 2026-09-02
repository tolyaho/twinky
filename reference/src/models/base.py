from __future__ import annotations
from peewee import (
    IntegerField,
    Model,
    CharField,
    DatabaseProxy,
    BigIntegerField,
)


proxy_db = DatabaseProxy()


timestamp_field = BigIntegerField(index=True, null=False)


class BaseModel(Model):
    """Base model - database will be set dynamically."""
    id = BigIntegerField(primary_key=True) # Inherited by child models if they don't have their own primary_key

    class Meta:
        database = proxy_db


class User(BaseModel):
    """Twitch user (both broadcaster and chatter are the same type).

    @param login: Username (must be lowercase) in Twitch.
    """
    login = CharField(index=True, unique=True)

    class Meta:
        table_name = "users"
