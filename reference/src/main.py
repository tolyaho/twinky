import asyncio
import logging

from models import User
from parsers.image_annotations import save_images, start_workers
from parsers.chat import save_chat
from parsers.audio import save_audio
from parsers.context.parser import save_context
from parsers.message_reasons.parser import save_reasons
from parsers.chat_summaries.builder import save_summaries


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    broadcaster, _ = User.get_or_create(login='qoqsik')

    frame_q = asyncio.Queue(maxsize=50)
    worker_tasks = start_workers(frame_q, n=4, max_inflight=2)

    tasks = list(worker_tasks)
    tasks.extend([
        save_context(broadcaster),
        save_images(broadcaster, frame_q=frame_q),
        save_chat(broadcaster),
        save_audio(broadcaster),
        save_reasons(broadcaster),
        save_summaries(broadcaster),
    ])

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
