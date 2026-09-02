import asyncio
import logging
import random
import typing as tp

import websockets

from models import User, db
from models.chat import Message


TWITCH_WS = "wss://irc-ws.chat.twitch.tv:443"


logger = logging.getLogger("chat_parser")


def _save_message_to_db(
    message_id: str,
    broadcaster: User,
    chatter_login: str,
    text: str,
    timestamp: int,
    room_id: int,
    chatter_type: str,
    parent_message_id: tp.Optional[str]
) -> None:
    try:
        if Message.select().where(Message.message_id == message_id).exists():
            logger.debug(f"Message #{message_id} already exists, skipping")
            return

        chatter, _ = User.get_or_create(login=chatter_login)

        Message.create(
            message_id=message_id,
            broadcaster=broadcaster,
            chatter=chatter,
            text=text,
            time_ms=timestamp,
            room_id=room_id,
            chatter_type=chatter_type,
            message_reply_id=parent_message_id
        )
        
        logger.debug("Saved message to DB: [%s] %s: %s", broadcaster.login, chatter_login, text[:50])
    except Exception as e:
        logger.error("Error saving message to database: %r", e)


async def save_chat(broadcaster: User) -> None:
    """Stream chat messages for a channel and push them through the parser."""
    logger.info("save_chat started for broadcaster %r", broadcaster.login)
    retry_delay = 5  # seconds

    while True:
        try:
            anonymous_nick = f"justinfan{random.randint(10_000, 99_999)}"
            logger.info("Connecting to Twitch IRC for broadcaster %r with nick %s", broadcaster.login, anonymous_nick)

            async with websockets.connect(TWITCH_WS) as ws:
                await ws.send("PASS SCHMOOPIIE")
                await ws.send(f"NICK {anonymous_nick}")

                # Requesting tags for additional information about the messages
                await ws.send("CAP REQ twitch.tv/tags")

                await ws.send(f"JOIN #{broadcaster.login}")
                logger.info("Successfully connected to chat for broadcaster %r", broadcaster.login)

                while True:
                    try:
                        raw_msg = await ws.recv()
                        # Decode bytes to string if needed
                        msg = raw_msg.decode('utf-8') if isinstance(raw_msg, bytes) else raw_msg
                        logging.debug(
                            "Received message for nick=%s from channel=%s: %s",
                            anonymous_nick,
                            broadcaster.login,
                            msg,
                        )
                    except websockets.exceptions.ConnectionClosedError as error:
                        logger.warning("Connection closed for broadcaster %r: %s. Reconnecting in %ds...", 
                                      broadcaster.login, error, retry_delay)
                        break  # Выходим только из внутреннего цикла

                    for line in msg.split("\r\n"):
                        if not line:
                            continue

                        if line == "PING :tmi.twitch.tv":
                            await ws.send("PONG :tmi.twitch.tv")
                            continue

                        if "PRIVMSG" in line:
                            if line[0] != "@":
                                raise ValueError(f"Expected message tags prefix '@', got: {line}")

                            first_space_index = line.find(" ")

                            if first_space_index == -1:
                                raise ValueError(f"Unable to locate tags delimiter in message: {line}")

                            raw_tags = line[1:first_space_index].split(";")
                            try:
                                tags: tp.Dict[str, str] = {
                                    tag_key: tag_value
                                    for tag_key, tag_value in (
                                        tag.split("=", 1) for tag in raw_tags if tag
                                    )
                                }
                            except ValueError as split_error:
                                raise ValueError(
                                    f"Failed to split IRC tags for message: {line}"
                                ) from split_error

                            message_id = tags.get("id")

                            if not message_id:
                                raise ValueError(f"Missing message id in PRIVMSG line: {line}")

                            try:
                                chatter_login = tags["display-name"].lower()
                                timestamp = int(tags["tmi-sent-ts"])
                                room_id = int(tags["room-id"])
                                chatter_type = tags["user-type"]
                            except KeyError as missing_key:
                                raise ValueError(
                                    f"Missing expected IRC tag '{missing_key.args[0]}' in message: {line}"
                                ) from missing_key
                            except ValueError as conversion_error:
                                raise ValueError(
                                    f"Failed to convert numeric fields in message: {line}"
                                ) from conversion_error

                            parent_message_id: tp.Optional[str] = tags.get("reply-parent-msg-id")
                            if not parent_message_id:
                                parent_message_id = None

                            message_part = line[first_space_index + 1 :]

                            if message_part[:1] != ":":
                                raise ValueError(f"Expected message prefix ':', got: {repr(message_part[:1])}. Whole message: {repr(line)}")

                            message_part = message_part[1:]
                            text = message_part[message_part.find(":") + 1:]

                            logger.debug("Received chat message from %s: %s", chatter_login, text[:50])
                            asyncio.create_task(
                                asyncio.to_thread(
                                    _save_message_to_db,
                                    message_id,
                                    broadcaster,
                                    chatter_login.lower(),
                                    text,
                                    timestamp,
                                    room_id,
                                    chatter_type,
                                    parent_message_id
                                )
                            )
        except Exception as error:
            logger.error("Unhandled error while parsing chat for broadcaster %r: %r. Reconnecting in %ds...", 
                        broadcaster.login, error, retry_delay)

        await asyncio.sleep(retry_delay)
