import asyncio
import logging
import os

from .llm import LlmClient
from .prompts import create_prompt, TIMEFRAMES
from models import User
from models.chat import Message
from models.audio import AudioTranscription
from models.image_annotations import ImageAnnotation
from models.chat_summaries import ChatSummary
from utils import now_ms

logger = logging.getLogger(__name__)




class ChatSummariesBuilder:
    def __init__(
        self,
        *,
        llm: LlmClient,
        model: str,
        broadcaster: User,
        room_id: int | None = None,
        temperature: float = 0.2,
    ):
        self.llm = llm
        self.model = model
        self.broadcaster = broadcaster
        self.room_id = room_id
        self.temperature = temperature

    async def build_one(
        self,
        *,
        window_s: int,
        end_ms: int | None = None,
        chat_limit: int = 500,
        image_annotations_limit: int = 20,
        audio_transcriptions_limit: int = 100,
    ) -> ChatSummary:
        if end_ms is None:
            end_ms = now_ms()
        start_ms = end_ms - window_s * 1000

        def load_messages():
            q = Message.select().where(
                (Message.broadcaster == self.broadcaster) &
                (Message.time_ms >= start_ms) &
                (Message.time_ms < end_ms)
            ).order_by(Message.time_ms.desc()).limit(chat_limit)
            return list(q)[::-1]

        def load_audio_transcriptions():
            q = AudioTranscription.select().where(
                (AudioTranscription.broadcaster == self.broadcaster) &
                (AudioTranscription.start_ms < end_ms) &
                (AudioTranscription.end_ms > start_ms)
            ).order_by(AudioTranscription.start_ms.desc()).limit(audio_transcriptions_limit)
            return list(q)[::-1]

        def load_image_annotations():
            q = ImageAnnotation.select().where(
                (ImageAnnotation.broadcaster == self.broadcaster) &
                (ImageAnnotation.time_ms >= start_ms) &
                (ImageAnnotation.time_ms < end_ms)
            ).order_by(ImageAnnotation.time_ms.desc()).limit(image_annotations_limit)
            return list(q)[::-1]

        def prev_window(ws: int) -> int | None:
            for i in range(1, len(TIMEFRAMES)):
                if TIMEFRAMES[i][0] == ws:
                    return TIMEFRAMES[i - 1][0]
            return None

        def load_prev_chat_summaries(ws: int) -> list[ChatSummary]:
            prev_ws = prev_window(ws)
            if prev_ws is None:
                return []

            k = max(1, ws // prev_ws)

            q = ChatSummary.select().where(
                (ChatSummary.broadcaster == self.broadcaster) &
                (ChatSummary.window_s == prev_ws) &
                (ChatSummary.time_ms >= start_ms) &
                (ChatSummary.time_ms < end_ms)
            ).order_by(ChatSummary.time_ms.desc()).limit(k)

            return list(q)[::-1]
        
        messages, audio_transcriptions, image_annotations, prev_chat_summaries = await asyncio.gather(
            asyncio.to_thread(load_messages),
            asyncio.to_thread(load_audio_transcriptions),
            asyncio.to_thread(load_image_annotations),
            asyncio.to_thread(load_prev_chat_summaries, window_s),
        )

        chat_text = "\n".join(
            f"{m.time_ms}: {m.chatter.login}: {m.text}"
            for m in messages
        )

        audio_text = "\n".join(
            f"{a.start_ms}-{a.end_ms}: {a.text}"
            for a in audio_transcriptions
        )

        image_annotations_text = "\n".join(
            f"{i.time_ms}: {i.annotation}"
            for i in image_annotations
        )

        prev_chat_summaries_text = [
            f"{s.time_ms}: {s.summary}"
            for s in prev_chat_summaries
        ]

        system_msg, user_msg = create_prompt(
            window_s=window_s,
            broadcaster=self.broadcaster.login,
            room_id=self.room_id,
            start_ms=start_ms,
            end_ms=end_ms,
            chat=chat_text,
            audio=audio_text or None,
            frames=image_annotations_text or None,
            prev=prev_chat_summaries_text or None,
        )

        if not messages and not audio_transcriptions and not image_annotations:
            summary = "no data in this window"
            room_id = self.room_id or 0
            summary_id = ChatSummary.mk_id(self.broadcaster.login, window_s, end_ms)
            def save_empty():
                ChatSummary.insert(
                    summary_id=summary_id,
                    broadcaster=self.broadcaster,
                    room_id=int(room_id),
                    time_ms=int(end_ms),
                    window_s=int(window_s),
                    start_ms=int(start_ms),
                    summary=summary,
                    model=self.model,
                    msg_count=0,
                    audio_count=0,
                    frame_count=0,
                ).on_conflict(
                    conflict_target=[ChatSummary.broadcaster, ChatSummary.window_s, ChatSummary.time_ms],
                    update={
                        "room_id": int(room_id),
                        "start_ms": int(start_ms),
                        "summary": summary,
                        "model": self.model,
                        "msg_count": 0,
                        "audio_count": 0,
                        "frame_count": 0,
                    }
                ).execute()
                return ChatSummary.get(
                    ChatSummary.summary_id == summary_id
                )
            return await asyncio.to_thread(save_empty)

        text, obj, resp = await self.llm.content(
            json_mode=True,
            system_msg=system_msg,
            user_msg=user_msg,
            model=self.model,
            temperature=self.temperature,
            max_tokens=512,
        )

        summary = text.strip() if isinstance(text, str) else str(text)
        if isinstance(obj, dict):
            s = obj.get("summary")
            if isinstance(s, str) and s.strip():
                summary = s.strip()


        room_id = self.room_id
        if room_id is None:
            if messages:
                room_id = messages[0].room_id
            elif image_annotations:
                room_id = image_annotations[0].room_id
            else:
                room_id = 0
        summary_id = ChatSummary.mk_id(self.broadcaster.login, window_s, end_ms)

        def save_summary() -> ChatSummary:
            ChatSummary.insert(
                summary_id=summary_id,
                broadcaster=self.broadcaster,
                room_id=int(room_id),
                time_ms=int(end_ms),
                window_s=int(window_s),
                start_ms=int(start_ms),
                summary=summary,
                model=self.model,
                msg_count=len(messages),
                audio_count=len(audio_transcriptions),
                frame_count=len(image_annotations),
            ).on_conflict(
                conflict_target=[ChatSummary.broadcaster, ChatSummary.window_s, ChatSummary.time_ms],
                update={
                    "room_id": int(room_id),
                    "start_ms": int(start_ms),
                    "summary": summary,
                    "model": self.model,
                    "msg_count": len(messages),
                    "audio_count": len(audio_transcriptions),
                    "frame_count": len(image_annotations),
                }
            ).execute()
            return ChatSummary.get(
                ChatSummary.summary_id == summary_id
            )

        row = await asyncio.to_thread(save_summary)
        return row

    async def build_all(
        self,
        *,
        end_ms: int | None = None,
    ) -> dict[int, ChatSummary]:
        if end_ms is None:
            end_ms = now_ms()

        out: dict[int, ChatSummary] = {}
        for ws, _ in TIMEFRAMES:
            try:
                out[ws] = await self.build_one(window_s=ws, end_ms=end_ms)
            except Exception:
                logger.exception("summary build failed for window_s=%s", ws)
        return out


async def save_summaries(broadcaster: User) -> None:
    """Continuously generate chat summaries for a broadcaster.
    
    Runs in a loop, generating summaries every 60 seconds using the ChatSummariesBuilder.
    Handles errors gracefully and can be cancelled cleanly.
    """
    base_url = (os.getenv("LLM_BASE_URL") or "https://api.deepseek.com").rstrip("/")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    model = os.getenv("LLM_MODEL") or "deepseek-chat"

    timeout_s = float(os.getenv("LLM_TIMEOUT_S") or 180)
    async with LlmClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_s=timeout_s,
    ) as llm:
        b = ChatSummariesBuilder(
            llm=llm,
            model=model,
            broadcaster=broadcaster,
        )

        while True:
            try:
                await b.build_all()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("summaries loop failed")
                await asyncio.sleep(5)
