import asyncio
import os
import pathlib
from dotenv import load_dotenv
from llm import LlmClient

env_path = pathlib.Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)

async def main():
    print("base:", os.getenv("LLM_BASE_URL"))
    async with LlmClient() as c:
        s, j, _ = await c.content(
            system_msg="you are a helpful assistant",
            user_msg="say ok",
            max_tokens=20,
        )
        print("text:", s)
        print("json:", j)

        s, j, _ = await c.content(
            json_mode=True,
            system_msg='return only a json object, no extra text',
            user_msg='make {"ok": true, "n": 1}',
            max_tokens=60,
        )
        print("text2:", s)
        print("json2:", j)

        out = await c.batch([
            {
                "system_msg": "you are a helpful assistant",
                "user_msg": "say hello in one word",
                "max_tokens": 10,
            },
            {
                "json_mode": True,
                "system_msg": "return only a json object",
                "user_msg": 'make {"x": 2, "y": 3}',
                "max_tokens": 60,
            },
        ])

        for i, (s, j, _) in enumerate(out):
            print("batch", i, "text:", s)
            print("batch", i, "json:", j)

if __name__ == "__main__":
    asyncio.run(main())
