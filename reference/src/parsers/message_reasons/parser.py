import asyncio
import json
import logging
import os
import random
from pathlib import Path
from string import Template
import typing as tp

from openai import AsyncOpenAI
from models import User

from models.chat import Message, MessageReason
from models.audio import AudioTranscription
from models.context import StreamContext
from utils import minutes_in_ms, seconds_in_ms, batched, now_ms


PROMPTS_DIR = Path(__file__).parent / "prompts"

logger = logging.getLogger("message_reasons_parser")
POLL_INTERVAL_SECONDS = 0.5
MAX_BATCH_SIZE = 3
MAX_MESSAGE_AGE_MS = seconds_in_ms(1)
SPEECH_CONTEXT_WINDOW_MS = seconds_in_ms(45)
SCREEN_CONTEXT_WINDOW_MS = seconds_in_ms(60)
LLM_RETRIES = int(os.getenv("MESSAGE_REASONS_LLM_RETRIES", "2"))
LLM_BACKOFF_BASE_S = float(os.getenv("MESSAGE_REASONS_LLM_BACKOFF_BASE_S", "1.0"))
LLM_TIMEOUT_S = float(os.getenv("MESSAGE_REASONS_LLM_TIMEOUT_S", "60"))
SYSTEM_PROMPT = (PROMPTS_DIR / 'system.txt').read_text().strip()
GENERAL_TEMPLATE = Template((PROMPTS_DIR / 'general.txt').read_text())
_llm_client: tp.Optional[AsyncOpenAI] = None


def get_llm_client() -> AsyncOpenAI:
    """Reuse one client instead of creating a new session for every batch."""
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=os.environ.get('OPENAI_API_KEY'),
            base_url="https://api.openai.com/v1",
            timeout=LLM_TIMEOUT_S,
        )
    return _llm_client


class MessageReasonResult(tp.TypedDict):
    index: int
    category: str
    reason: str


class LLMResponse(tp.TypedDict):
    messages: tp.List[MessageReasonResult]


def parse_llm_response(data: dict) -> LLMResponse:
    messages_data = data.get("messages", [])
    messages: tp.List[MessageReasonResult] = []

    for item in messages_data:
        index = item.get("index")
        category = item.get("category", "")
        reason = item.get("reason", "")

        if index is None:
            continue

        try:
            index_int = int(index)
        except (ValueError, TypeError):
            logger.warning("Invalid index format: %r", index)
            continue

        messages.append({
            "index": index_int,
            "category": category,
            "reason": reason
        })

    return {"messages": messages}


def make_speech_context(messages: tp.List[Message], broadcaster: User) -> str:
    min_time = min(msg.time_ms for msg in messages)
    max_time = max(msg.time_ms for msg in messages)

    transcriptions = AudioTranscription.select().where(
        (AudioTranscription.broadcaster == broadcaster) &
        (AudioTranscription.is_final == True) &
        (AudioTranscription.start_ms >= min_time - SPEECH_CONTEXT_WINDOW_MS) &
        (AudioTranscription.start_ms <= max_time)
    ).order_by(AudioTranscription.start_ms.asc())

    items = messages.copy()
    items.extend(transcriptions)

    items.sort(key=lambda x: x.start_ms if isinstance(x, AudioTranscription) else x.time_ms)

    context = ""

    for item in items:
        if isinstance(item, AudioTranscription):
            context += f"From broadcaster: {item.text}\n"
        elif isinstance(item, Message):
            context += f"From chatter {item.chatter.login}: {item.text}\n"
        else:
            raise ValueError(f"Unknown item type: {type(item)}")

    return context


def get_screen_description(messages: tp.List[Message], broadcaster: User) -> str:
    stream_context = StreamContext.select().where(
        (StreamContext.broadcaster == broadcaster)
    ).order_by(StreamContext.time_ms.desc()).first()

    if not stream_context or stream_context.time_ms < messages[0].time_ms - SCREEN_CONTEXT_WINDOW_MS:
        return "No screen description available."
    return stream_context.text


def format_chat_messages(messages: tp.List[Message]) -> tp.Tuple[tp.List[Message], str]:
    sorted_messages = sorted(messages, key=lambda m: m.time_ms)
    chat_messages_list = []
    for i, msg in enumerate(sorted_messages, 1):
        chat_messages_list.append(f"{i}. {msg.chatter.login}: {msg.text}")
    chat_messages = '\n'.join(chat_messages_list)
    return sorted_messages, chat_messages


async def handle_messages(messages: tp.List[Message]) -> None:
    if not messages:
        return

    try:
        broadcaster = messages[0].broadcaster

        screen_description = get_screen_description(messages, broadcaster)
        sorted_messages, chat_messages = format_chat_messages(messages)

        user_prompt = GENERAL_TEMPLATE.substitute(
            streamer_transcript=make_speech_context(messages, broadcaster),
            screen_description=screen_description,
            chat_messages=chat_messages
        )

        client = get_llm_client()
        last_err: Exception | None = None
        for attempt in range(LLM_RETRIES + 1):
            try:
                response = await client.chat.completions.create(
                    model="gpt-4.1-nano-2025-04-14",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={'type': 'json_object'}
                )
                last_err = None
                break
            except Exception as e:
                last_err = e
                if attempt >= LLM_RETRIES:
                    break
                delay = LLM_BACKOFF_BASE_S * (2 ** attempt) + random.random() * 0.2
                await asyncio.sleep(delay)

        if last_err is not None:
            raise last_err

        data = json.loads(response.choices[0].message.content)
        llm_response = parse_llm_response(data)
        
        for result in llm_response["messages"]:
            msg_index = result["index"] - 1

            if msg_index < 0 or msg_index >= len(sorted_messages):
                raise ValueError(f"Index {msg_index} out of range (0-{len(sorted_messages) - 1})")

            message = sorted_messages[msg_index]

            if message.reasons.exists():
                raise ValueError(f"Message {message.id} already has reasons")

            MessageReason.create(
                message=message,
                category=result["category"],
                text=result["reason"],
                time_ms=now_ms()
            )

        logger.info("Processed %d messages for broadcaster %r", len(llm_response["messages"]), broadcaster.login)

    except Exception as e:
        logger.error("Error handling messages: %r", e, exc_info=True)


async def save_reasons(broadcaster) -> None:
    last_message_id = ""
    buffer: tp.List[Message] = []

    while True:
        current_ms = now_ms()

        free_messages = Message.select().where(
            (Message.broadcaster == broadcaster) &
            (Message.time_ms > current_ms - minutes_in_ms(2)) &
            (Message.message_id > last_message_id)
        ).order_by(Message.message_id.asc())

        for message in free_messages:
            last_message_id = max(last_message_id, message.message_id)
            if not message.reasons.exists():
                buffer.append(message)

        if buffer:
            oldest_age_ms = current_ms - buffer[0].time_ms
            flush_now = len(buffer) >= MAX_BATCH_SIZE or oldest_age_ms >= MAX_MESSAGE_AGE_MS

            if flush_now:
                for batch in batched(buffer, MAX_BATCH_SIZE):
                    asyncio.create_task(handle_messages(list(batch)))
                buffer.clear()

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
