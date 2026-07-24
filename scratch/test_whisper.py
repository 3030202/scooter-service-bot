import asyncio
import os
from openai import AsyncOpenAI

API_KEY = "v1.cP221wTBTN7IfK_4bPUlbc0NYVlbe53HvqHJOv17R2qPIY4830wnTCRwbAb0nayPEgaTl7X_7Aw168XMK5mR9qy5jb9sMy39bchiNbxIMxCB6Tt4I1V1tEgwR9ptYEcF"
BASE_URL = "https://gpt.mwsapis.ru/projects/d0g4h/openai/v1"
MODEL = "whisper-large-v3"

async def test_transcribe():
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    # Create a dummy small ogg/wav file to test transcription endpoint
    dummy_path = "/tmp/test_audio.ogg"
    with open(dummy_path, "wb") as f:
        f.write(b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
    
    try:
        print(f"Testing audio transcriptions with model: {MODEL}...")
        with open(dummy_path, "rb") as audio:
            res = await client.audio.transcriptions.create(
                model=MODEL,
                file=("speech.ogg", audio, "audio/ogg"),
            )
        print("Success:", res)
    except Exception as e:
        print(f"Error ({type(e).__name__}): {e}")

if __name__ == "__main__":
    asyncio.run(test_transcribe())
