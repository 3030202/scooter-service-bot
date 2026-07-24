import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any, Sequence

from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.db.models import ServiceCatalogItem
from app.services.ai_provider_service import get_active_ai_service_client
from app.services.ai_prompts import DIAGNOSIS_SYSTEM_PROMPT, build_diagnosis_user_prompt


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
        self.fallback_client = AsyncOpenAI(api_key=settings.ai_api_key, base_url=settings.ai_base_url)
        self.client = self.fallback_client

    async def transcribe_voice(self, path: str, session: Any = None) -> str:
        target_path = path
        wav_path = None
        try:
            if path.endswith(".ogg") or path.endswith(".oga"):
                wav_path = path + ".wav"
                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y", "-i", path, "-ar", "16000", "-ac", "1", wav_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode == 0 and os.path.exists(wav_path):
                    target_path = wav_path

            client, model_name = await get_active_ai_service_client(session)
            with open(target_path, "rb") as audio:
                result = await client.audio.transcriptions.create(
                    model=settings.ai_transcribe_model,
                    file=audio,
                )
            text = getattr(result, "text", "") or ""
            return text.strip()
        except Exception as exc:
            logger.exception("Voice transcription failed: {}", exc)
            return ""
        finally:
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

    async def analyze_ticket(
        self,
        description: str,
        image_paths: list[str],
        catalog_items: Sequence[ServiceCatalogItem] | None = None,
        session: Any = None,
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

        prompt = build_diagnosis_user_prompt(description, catalog_str)

        if session is not None:
            client, model_name = await get_active_ai_service_client(session)
        else:
            client, model_name = self.client, settings.ai_text_model

        max_attempts = 3
        delay = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": DIAGNOSIS_SYSTEM_PROMPT,
                        },
                        {"role": "user", "content": [{"type": "text", "text": prompt}, *images]},
                    ],
                    temperature=0.2,
                )
                content = response.choices[0].message.content or "{}"

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
