import base64
import json
from pathlib import Path
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from app.config import settings


class AIService:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.ai_api_key, base_url=settings.ai_base_url)

    async def transcribe_voice(self, path: str) -> str:
        try:
            with open(path, "rb") as audio:
                result = await self.client.audio.transcriptions.create(
                    model=settings.ai_transcribe_model,
                    file=audio,
                )
            return getattr(result, "text", "") or ""
        except Exception as exc:
            logger.exception("Voice transcription failed: {}", exc)
            return ""

    async def analyze_ticket(self, description: str, image_paths: list[str]) -> dict[str, Any]:
        images = []
        for path in image_paths:
            try:
                b64 = base64.b64encode(Path(path).read_bytes()).decode("utf-8")
                images.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })
            except Exception as exc:
                logger.warning("Cannot attach image {}: {}", path, exc)

        prompt = f"""
Ты эксперт сервисного центра электротранспорта.
Проанализируй описание и фото. Верни СТРОГО JSON:
{{
  "fault": "вероятная неисправность",
  "reasoning": "краткое объяснение",
  "price_min": 0,
  "price_max": 0,
  "eta": "например: 1-2 дня",
  "parts": ["деталь 1", "деталь 2"],
  "risk_level": "low|medium|high"
}}

Прайс-ориентиры:
- диагностика: 1000-2000 RUB
- замена подшипников: 2500-6000 RUB
- ремонт/замена мотор-колеса: 5000-18000 RUB
- контроллер: 4000-12000 RUB
- АКБ/BMS: 5000-25000 RUB
- тормоза/колодки: 1500-5000 RUB

Описание клиента:
{description}
""".strip()

        try:
            response = await self.client.chat.completions.create(
                model=settings.ai_text_model,
                messages=[
                    {"role": "system", "content": "Ты технический диагност. Отвечай только валидным JSON без markdown."},
                    {"role": "user", "content": [{"type": "text", "text": prompt}, *images]},
                ],
                temperature=0.2,
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as exc:
            logger.exception("AI analysis failed: {}", exc)
            return {
                "fault": "Требуется ручная диагностика",
                "reasoning": "AI-анализ временно недоступен или модель вернула некорректный ответ.",
                "price_min": 1000,
                "price_max": 3000,
                "eta": "после очной диагностики",
                "parts": [],
                "risk_level": "medium",
            }
