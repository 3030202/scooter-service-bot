import asyncio
from openai import AsyncOpenAI

API_KEY = "v1.cP221wTBTN7IfK_4bPUlbc0NYVlbe53HvqHJOv17R2qPIY4830wnTCRwbAb0nayPEgaTl7X_7Aw168XMK5mR9qy5jb9sMy39bchiNbxIMxCB6Tt4I1V1tEgwR9ptYEcF"
BASE_URL = "https://gpt.mwsapis.ru/projects/d0g4h/openai/v1"

async def test_models():
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    try:
        models = await client.models.list()
        print("Available models:")
        for m in models.data:
            print(f"- {m.id}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    asyncio.run(test_models())
