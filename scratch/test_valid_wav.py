import asyncio
import wave
import struct
from openai import AsyncOpenAI

API_KEY = "v1.cP221wTBTN7IfK_4bPUlbc0NYVlbe53HvqHJOv17R2qPIY4830wnTCRwbAb0nayPEgaTl7X_7Aw168XMK5mR9qy5jb9sMy39bchiNbxIMxCB6Tt4I1V1tEgwR9ptYEcF"
BASE_URL = "https://gpt.mwsapis.ru/projects/d0g4h/openai/v1"
MODEL = "whisper-large-v3"

def create_valid_wav(path):
    with wave.open(path, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        # 1 second of audio
        for _ in range(16000):
            wav_file.writeframes(struct.pack("<h", 0))

async def test_transcribe():
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    wav_path = "/tmp/test_speech.wav"
    create_valid_wav(wav_path)
    
    try:
        print(f"Testing audio transcriptions with model: {MODEL} on valid WAV...")
        with open(wav_path, "rb") as audio:
            res = await client.audio.transcriptions.create(
                model=MODEL,
                file=audio,
            )
        print("Success:", res)
    except Exception as e:
        print(f"Error ({type(e).__name__}): {e}")

if __name__ == "__main__":
    asyncio.run(test_transcribe())
