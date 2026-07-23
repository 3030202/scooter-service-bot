import asyncio
import base64
import json
from pathlib import Path
from typing import Any, Sequence

from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.db.models import ServiceCatalogItem


class AIDiagnosisResult(BaseModel):
    fault: str = Field(description="Краткая формулировка неисправности")
    reasoning: str = Field(description="Объяснение причин неисправности")
    matched_catalog_codes: list[str] = Field(
        default_factory=list, description="Коды рекомендуемых работ из каталога сервиса"
    )
    price_min: float = Field(default=1000.0, description="Минимальная ориентировочная стоимость в рублях")
    price_max: float = Field(default=3000.0, description="Максимальная ориентировочная стоимость в рублях")
    eta: str = Field(default="1-2 дня", description="Ориентировочный срок выполнения работ")
    parts: list[str] = Field(default_factory=list, description="Необходимые запчасти")
    risk_level: str = Field(default="medium", description="Уровень риска эксплуатации: low, medium, high")
    recommended_checklist: list[str] = Field(
        default_factory=list, description="Рекомендуемые шаги проверки для мастера"
    )


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

    async def analyze_ticket(
        self, description: str, image_paths: list[str], catalog_items: Sequence[ServiceCatalogItem] | None = None
    ) -> AIDiagnosisResult:
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

        catalog_context_lines = []
        if catalog_items:
            for item in catalog_items:
                catalog_context_lines.append(
                    f"- code: '{item.code}', title: '{item.title}', base_price: {item.base_price} RUB"
                )
        catalog_str = "\n".join(catalog_context_lines) if catalog_context_lines else "Доступные работы: battery_diag, controller_repair, tire_tube, brake_service, display_throttle"

        prompt = f"""
Ты главный технический диагност сервисного центра электротранспорта.
Проанализируй симптомы поломки и фотографии самоката.

Каталог доступных сервисных работ:
{catalog_str}

Верни СТРОГО JSON-объект следующей структуры:
{{
  "fault": "вероятная неисправность",
  "reasoning": "краткое экспертное объяснение причины",
  "matched_catalog_codes": ["code1", "code2"],
  "price_min": 1000,
  "price_max": 3000,
  "eta": "1-2 дня",
  "parts": ["деталь 1"],
  "risk_level": "low|medium|high",
  "recommended_checklist": ["проверить напряжение", "осмотреть контакты"]
}}

Описание проблемы от клиента:
{description}
""".strip()

        # Retry loop with exponential backoff (up to 3 attempts)
        max_attempts = 3
        delay = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=settings.ai_text_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Ты инженер-диагност электротранспорта. "
                                "Отвечай строго в формате JSON, соответствующем запрошенной схеме."
                            ),
                        },
                        {"role": "user", "content": [{"type": "text", "text": prompt}, *images]},
                    ],
                    temperature=0.2,
                )
                content = response.choices[0].message.content or "{}"

                # Handle possible markdown wrapping ```json ... ```
                cleaned = content.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                return AIDiagnosisResult.model_validate_json(cleaned)

            except Exception as exc:
                logger.warning(f"AI analysis attempt {attempt}/{max_attempts} failed: {exc}")
                if attempt < max_attempts:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    logger.error("All AI analysis retry attempts exhausted, returning fallback diagnosis")

        return AIDiagnosisResult(
            fault="Требуется ручная диагностика",
            reasoning="AI-анализ временно недоступен или вернул некорректные данные. Назначен мастер для очной проверки.",
            matched_catalog_codes=[],
            price_min=1000.0,
            price_max=3000.0,
            eta="после очной диагностики",
            parts=[],
            risk_level="medium",
            recommended_checklist=["Осмотреть корпус и разъемы", "Проверить контакты питания"],
        )
