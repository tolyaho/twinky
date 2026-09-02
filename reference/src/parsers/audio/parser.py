import asyncio
import logging
import subprocess
import time
import typing as tp

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets.listen_v1_results_event import (
    ListenV1ResultsEvent,
    ListenV1Word,
)
import streamlink

from models import User, db
from models.audio import AudioTranscription

from ..exceptions import NoStreamError
import os

logger = logging.getLogger("audio_parser")


def print_task_exception(task: asyncio.Task) -> None:
    try:
        task.result()
    except Exception as error:
        logger.error("Task %r exception: %r", task, error)


def save_message(message: ListenV1ResultsEvent, start_time_ms: int, broadcaster: User):
    def _word_start_ms(word: ListenV1Word) -> int:
        return start_time_ms + int(word.start * 1000)

    def _word_end_ms(word: ListenV1Word) -> int:
        return start_time_ms + int((word.end) * 1000)

    alternatives = message.channel.alternatives

    for alternative in alternatives:
        if not alternative.transcript:
            continue

        transcription_start_ms = _word_start_ms(alternative.words[0])
        transcription_end_ms = _word_end_ms(alternative.words[-1])

        try:
            AudioTranscription.delete().where(
                (AudioTranscription.broadcaster == broadcaster) &
                (AudioTranscription.start_ms > transcription_start_ms - 2_000) &
                (AudioTranscription.end_ms < transcription_end_ms + 2_000) &
                (AudioTranscription.is_final == False)
            ).execute()

            players: tp.Dict[int, tp.List[ListenV1Word]] = {}

            for word in alternative.words:
                speaker_id = word.speaker if word.speaker is not None else 0
                if speaker_id not in players:
                    players[speaker_id] = []
                players[speaker_id].append(word)

            for words in players.values():
                text = ' '.join([word.punctuated_word or '' for word in words])

                logger.debug("Received message from deepgram for broadcaster %r: %r", broadcaster.login, text)

                phrase_start_ms = _word_start_ms(words[0])
                phrase_end_ms = _word_end_ms(words[-1])

                AudioTranscription.create(
                    broadcaster=broadcaster,
                    text=text,
                    is_final=message.is_final,
                    start_ms=phrase_start_ms,
                    end_ms=phrase_end_ms,
                )
        except Exception as e:
            logger.error("Error saving to database: %r", e)
            if not db.is_closed():
                db.close()


class AudioFragment:
    timestamp_ms: int
    data: tp.Optional[bytes] = None

    def __init__(self, data: tp.Optional[bytes], timestamp_ms: tp.Optional[int] = None):
        self.data = data
        if timestamp_ms is None:
            from utils import now_ms
            self.timestamp_ms = now_ms()
        else:
            self.timestamp_ms = timestamp_ms

    def __bool__(self) -> bool:
        return self.data is not None

    def __len__(self) -> int:
        return len(self.data) if self.data is not None else 0


def from_stream_to_converter(broadcaster: User, converter_process: subprocess.Popen, started_event: asyncio.Event, loop: asyncio.AbstractEventLoop) -> None:
    broadcast_url = f"https://www.twitch.tv/{broadcaster.login}"

    session = streamlink.Streamlink()
    available_streams: tp.Dict[str, tp.Any] = session.streams(broadcast_url)
    stream: tp.Optional[tp.Any] = None

    for stream_name in ["audio_only", "best", "worst"]:
        if stream_name in available_streams:
            logger.info("Selected stream: %r", stream_name)
            stream = available_streams.get(stream_name)
            break

    if stream is None:
        raise NoStreamError(str(broadcaster.login))

    with stream.open() as fd:
        logger.info("Opened stream %r of broadcaster %r", stream_name, broadcaster.login)
        loop.call_soon_threadsafe(started_event.set)

        assert converter_process.stdin is not None, "stdin should not be None"
        
        while True:
            bytes_from_stream = fd.read(8192)
            if not bytes_from_stream:
                converter_process.stdin.close()
                logger.info("Catched EOF for stream %r of broadcaster %r", stream_name, broadcaster.login)
                break
            converter_process.stdin.write(bytes_from_stream)
            converter_process.stdin.flush()


def from_converter_to_queue(broadcaster: User, converter_process: subprocess.Popen, queue: asyncio.Queue[AudioFragment], loop: asyncio.AbstractEventLoop) -> None:
    assert converter_process.stdout is not None, "stdout should not be None"
    
    while True:
        bytes_from_converter = converter_process.stdout.read(2_000)
        if not bytes_from_converter:
            converter_process.stdout.close()
            loop.call_soon_threadsafe(queue.put_nowait, AudioFragment(data=None))
            logger.info("Catched EOF for converter stdout of broadcaster %r", broadcaster.login)
            break
        loop.call_soon_threadsafe(queue.put_nowait, AudioFragment(data=bytes_from_converter))


async def from_queue_to_deepgram(broadcaster: User, audio_fragments: asyncio.Queue[AudioFragment]) -> None:
    max_tries = 10

    for try_number in range(max_tries):
        logger.info("Trying to connect to Deepgram... (%s/%s) for broadcaster %r", try_number + 1, max_tries, broadcaster.login)
        logger.info("Waiting for first audio fragment before connecting to Deepgram...")

        first_fragment = await audio_fragments.get()

        if not first_fragment:
            logger.error("Got EOF before any audio for broadcaster %r", broadcaster.login)
            return

        logger.info("Got first fragment, connecting to Deepgram...")
    
        params = dict(
            model="nova-3-general",
            language="multi",
            encoding="linear16",
            sample_rate=16000,
            diarize=True,
            channels=1,
            interim_results=True,
            smart_format=True,
        )

        try:
            async_client = AsyncDeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"))
            async with async_client.listen.v1.connect(**params) as connection:
                start_time_ms = first_fragment.timestamp_ms

                connection_opened_event = asyncio.Event()

                def _on_open(_: tp.Any) -> None:
                    logger.info("Deepgram connection for broadcaster %r opened", broadcaster.login)
                    connection_opened_event.set()
            
                def _on_close(_: tp.Any) -> None:
                    logger.info("Deepgram connection for broadcaster %r closed", broadcaster.login)

                def _on_error(error: Exception) -> None:
                    logger.error("Got error from deepgram for broadcaster %r: %r", broadcaster.login, error)

                def _on_message(message: ListenV1ResultsEvent):
                    asyncio.create_task(
                        asyncio.to_thread(
                            save_message, message, start_time_ms, broadcaster
                        )
                    ).add_done_callback(print_task_exception)

                connection.on(EventType.OPEN, _on_open)
                connection.on(EventType.CLOSE, _on_close)
                connection.on(EventType.ERROR, _on_error)
                connection.on(EventType.MESSAGE, _on_message)

                listen_task = asyncio.create_task(connection.start_listening())
                listen_task.add_done_callback(print_task_exception)

                await connection_opened_event.wait()
                await connection.send_media(first_fragment.data)

                while True:
                    fragment: AudioFragment = await audio_fragments.get()

                    if not fragment:
                        listen_task.cancel()
                        break

                    await connection.send_media(fragment.data)
        except Exception as error:
            logger.error("Error in from_queue_to_deepgram for broadcaster %r: %r", broadcaster.login, error)
            continue


async def save_audio(broadcaster: User) -> None:
    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "warning", "-nostdin",
        "-fflags", "+nobuffer", "-flags", "low_delay",
        "-probesize", "32k", "-analyzeduration", "0",
        "-i", "pipe:0",
        "-vn", "-ac", "1", "-ar", "16000",
        "-f", "s16le",
        "pipe:1",
    ]

    converter_process = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    started_event = asyncio.Event()
    loop = asyncio.get_event_loop()

    stream_reading_task = asyncio.create_task(
        asyncio.to_thread(
            from_stream_to_converter, broadcaster, converter_process, started_event, loop
        )
    )

    stream_reading_task.add_done_callback(print_task_exception)
    await started_event.wait()

    if stream_reading_task.done():
        stream_reading_task.result()
        return

    audio_fragments: asyncio.Queue[AudioFragment] = asyncio.Queue()

    asyncio.create_task(
        asyncio.to_thread(
            from_converter_to_queue, broadcaster, converter_process, audio_fragments, loop
        )
    )

    asyncio.create_task(
        from_queue_to_deepgram(broadcaster, audio_fragments)   
    )

    # Keep the function alive by awaiting the stream reading task
    try:
        await stream_reading_task
    except Exception as e:
        logger.error("Error in stream reading for %r: %r", broadcaster.login, e)
    finally:
        if converter_process.poll() is None:
            converter_process.terminate()
        converter_process.wait()
        logger.info("Audio processing completed for %r", broadcaster.login)
