import asyncio
import logging
import os
from pathlib import Path
from string import Template

from openai import AsyncOpenAI
from dotenv import load_dotenv

from models import User, db
from models.audio import AudioTranscription
from models.image_annotations import ImageAnnotation
from models.context import StreamContext

from utils import minutes_in_ms, now_ms

load_dotenv()

PROMPTS_DIR = Path(__file__).parent / "prompts"

logger = logging.getLogger("context_parser")


async def save_context(broadcaster: User) -> None:
    base_url = (os.environ.get("LLM_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
    if base_url in {"https://api.deepseek.com", "https://api.openai.com"}:
        base_url = f"{base_url}/v1"
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    system_prompt_path = PROMPTS_DIR / "system.txt"
    new_context_prompt_path = PROMPTS_DIR / "new_context.txt"
    continue_context_prompt_path = PROMPTS_DIR / "continue_context.txt"
    
    system_prompt = system_prompt_path.read_text().strip()
    new_context_template = Template(new_context_prompt_path.read_text())
    continue_context_template = Template(continue_context_prompt_path.read_text())

    while True:
        current_ms = now_ms()

        images = list(ImageAnnotation.select().where(
            (ImageAnnotation.time_ms > current_ms - minutes_in_ms(2)) &
            (ImageAnnotation.broadcaster == broadcaster)
        ))

        speech = list(AudioTranscription.select().where(
            (AudioTranscription.start_ms > current_ms - minutes_in_ms(2)) &
            (AudioTranscription.broadcaster == broadcaster)
        ))

        if not images or not speech:
            logger.debug("No images or speech. Building context skipped.")
            await asyncio.sleep(30)
            continue

        last_context = StreamContext.select().where(
            (StreamContext.broadcaster == broadcaster)
        ).order_by(StreamContext.time_ms.desc()).first()

        speech_sum = '\n'.join(m.text for m in speech)
        frames_sum = '\n'.join(m.annotation for m in images)

        if last_context and last_context.time_ms > current_ms - minutes_in_ms(5):
            prompt = continue_context_template.substitute(
                old_context=last_context.text,
                speech_sum=speech_sum,
                frames_sum=frames_sum
            )
        else:
            prompt = new_context_template.substitute(
                speech_sum=speech_sum,
                frames_sum=frames_sum
            )

        try:
            response = await client.chat.completions.create(
                model=os.environ.get("LLM_MODEL") or "deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=False
            )

            context = response.choices[0].message.content

            StreamContext.create(
                broadcaster=broadcaster,
                text=context,
                time_ms=current_ms
            )
            
            logger.info("Saved context for broadcaster %r", broadcaster.login)

        except Exception as e:
            logger.error("Error generating context for broadcaster %r: %r", broadcaster.login, e)

        await asyncio.sleep(120)
