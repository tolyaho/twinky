import asyncio
import contextlib
import os
import subprocess
import typing as tp
import logging
from pathlib import Path

import streamlink
import time

from models import db, User
from models.image_annotations import ImageAnnotation
from ..exceptions import NoStreamError

from models.image_annotations import frame_job
from utils import now_ms

logger = logging.getLogger("image_annotations_parser")


def print_task_exception(task: asyncio.Task) -> None:
    try:
        task.result()
    except Exception as error:
        logger.error("Task %r exception: %r", task, error)


async def _wait_stable(p: Path, tries: int = 10, dt: float = 0.05) -> bool:
    last = -1
    for _ in range(tries):
        try:
            cur = p.stat().st_size
        except FileNotFoundError:
            return False
        if cur > 0 and cur == last:
            return True
        last = cur
        await asyncio.sleep(dt)
    return last > 0


def _q_put_drop_oldest(q: asyncio.Queue, item) -> None:
    while True:
        try:
            q.put_nowait(item)
            return
        except asyncio.QueueFull:
            try:
                q.get_nowait()
                q.task_done()
            except asyncio.QueueEmpty:
                continue


async def produce_frames(
    broadcaster: User,
    out_dir: Path,
    q: asyncio.Queue,
    stop_event: asyncio.Event,
    poll: float = 0.2,
) -> None:
    logger.info("produce_frames started for %r; watching %s", broadcaster.login, out_dir)
    i = 1
    initial_ts = now_ms()
    logger.info("produce_frames initial timestamp for %r: %d", broadcaster.login, initial_ts)

    while not stop_event.is_set():
        p = out_dir / f"{i:010d}.jpg"
        if not p.exists():
            await asyncio.sleep(poll)
            continue

        ok = await _wait_stable(p)
        if not ok:
            await asyncio.sleep(poll)
            continue

        # Rename the frame to a timestamp-based filename to avoid sequential IDs
        t = now_ms()
        new_path = out_dir / f"{t}.jpg"
        while new_path.exists():
            t += 1
            new_path = out_dir / f"{t}.jpg"
        try:
            p.rename(new_path)
            logger.debug("Renamed frame %s -> %s", p.name, new_path.name)
        except Exception as e:
            logger.error("Failed to rename frame %s: %r", p, e)
            await asyncio.sleep(poll)
            continue

        fid = f"{broadcaster.login}:{t}"
        job = frame_job(broadcaster=broadcaster, room_id=0, time_ms=t, path=new_path, frame_id=fid)
        _q_put_drop_oldest(q, job)
        logger.info("Enqueued frame %s for %r (frame_id=%s)", new_path.name, broadcaster.login, fid)
        i += 1


async def save_images(
    broadcaster: User,
    interval: int = 30,
    base_dir: tp.Optional[str] = None,
    frame_q: asyncio.Queue[frame_job] = asyncio.Queue(maxsize=50),
) -> None:
    logger.info("save_images started for broadcaster %r", broadcaster.login)
    retry_delay_s = float(os.getenv("IMAGE_STREAM_RETRY_DELAY_S", "5"))
    attempt = 0
    while True:
        attempt += 1
        ok = await _save_images_once(
            broadcaster=broadcaster,
            interval=interval,
            base_dir=base_dir,
            frame_q=frame_q,
        )
        if ok:
            return
        logger.warning(
            "save_images restarting for %r after %.1fs (attempt=%d)",
            broadcaster.login,
            retry_delay_s,
            attempt,
        )
        await asyncio.sleep(retry_delay_s)


async def _save_images_once(
    broadcaster: User,
    interval: int = 30,
    base_dir: tp.Optional[str] = None,
    frame_q: asyncio.Queue[frame_job] = asyncio.Queue(maxsize=50),
) -> bool:
    root_dir = (
        Path(base_dir)
        if base_dir is not None
        else Path(__file__).resolve().parent / "frames"
    )

    out_dir = root_dir / broadcaster.login
    out_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "warning", "-nostdin",
        "-fflags", "+nobuffer", "-flags", "low_delay",
        "-probesize", "32k", "-analyzeduration", "0",
        "-i", "pipe:0",
        "-an",
        "-vf", f"fps=1/{interval},scale=-1:720",
        "-vsync", "vfr",
        "-f", "image2",
        str(out_dir / "%010d.jpg"),
    ]

    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    started_event = asyncio.Event()
    start_timeout_s = float(os.getenv("IMAGE_STREAM_START_TIMEOUT_S", "15"))
    loop = asyncio.get_running_loop()

    async def monitor_ffmpeg_stderr():
        if not proc.stderr:
            return
        while proc.poll() is None:
            line = await asyncio.to_thread(proc.stderr.readline)
            if line:
                logger.warning("ffmpeg stderr for %r: %s", broadcaster.login,
                            line.decode("utf-8", errors="ignore").strip())
            else:
                await asyncio.sleep(0.1)

    stderr_monitor_task = asyncio.create_task(monitor_ffmpeg_stderr())

    stream_reading_task = asyncio.create_task(
        asyncio.to_thread(
            from_stream_to_image_converter, broadcaster, proc, started_event, loop
        )
    )

    stream_reading_task.add_done_callback(print_task_exception)
    start_wait = asyncio.create_task(started_event.wait())
    stop_event = asyncio.Event()
    prod_task: asyncio.Task | None = None

    try:
        done, pending = await asyncio.wait(
            {start_wait, stream_reading_task},
            timeout=start_timeout_s,
            return_when=asyncio.FIRST_COMPLETED,
        )

        if start_wait in done:
            prod_task = asyncio.create_task(
                produce_frames(broadcaster, out_dir, frame_q, stop_event)
            )
            await stream_reading_task
        else:
            if stream_reading_task in done:
                err = stream_reading_task.exception()
                if err:
                    logger.error(
                        "Stream reading failed before start for %r: %r",
                        broadcaster.login,
                        err,
                    )
                else:
                    logger.error(
                        "Stream reading ended before start for %r",
                        broadcaster.login,
                    )
            else:
                logger.error(
                    "Timed out waiting for stream start for %r after %.1fs",
                    broadcaster.login,
                    start_timeout_s,
                )
            for task in pending:
                task.cancel()
            return False
    except Exception as e:
        logger.error("Error in stream reading for %r: %r", broadcaster.login, e)
    finally:
        stop_event.set()
        stderr_monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await stderr_monitor_task

        if prod_task is not None:
            prod_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await prod_task

        if proc.poll() is None:
            proc.terminate()
        proc.wait()
        if proc.stderr:
            remaining_stderr = proc.stderr.read()
            if remaining_stderr:
                logger.warning("Final ffmpeg stderr for %r: %s", broadcaster.login, remaining_stderr.decode('utf-8', errors='ignore').strip())
        logger.info("Image extraction completed for %r", broadcaster.login)
    return True


def from_stream_to_image_converter(
    broadcaster: User,
    converter_process: subprocess.Popen,
    started_event: asyncio.Event,
    loop: asyncio.AbstractEventLoop,
) -> None:
    broadcast_url = f"https://www.twitch.tv/{broadcaster.login}"
    session = streamlink.Streamlink()
    available_streams: tp.Dict[str, tp.Any] = session.streams(broadcast_url)
    stream: tp.Optional[tp.Any] = None

    preferred = ["480p", "360p", "720p60", "720p", "best", "worst"]

    for name in preferred:
        if name in available_streams and name != "audio_only":
            logger.info("Selected stream: %r", name)
            stream = available_streams.get(name)
            stream_name = name
            break

    if stream is None:
        for name, s in available_streams.items():
            if name == "audio_only":
                continue
            logger.info("Selected fallback stream: %r", name)
            stream = s
            stream_name = name
            break
                

    if stream is None:
        raise NoStreamError(str(broadcaster.login))

    with stream.open() as fd:
        logger.info(
            "Opened stream %r of broadcaster %r",
            stream_name,
            broadcaster.login,
        )
        loop.call_soon_threadsafe(started_event.set)
        assert converter_process.stdin is not None

        while True:
            chunk = fd.read(8192)
            if not chunk:
                converter_process.stdin.close()
                logger.info(
                    "EOF for stream %r of broadcaster %r",
                    stream_name,
                    broadcaster.login,
                )
                break
            converter_process.stdin.write(chunk)
            converter_process.stdin.flush()

