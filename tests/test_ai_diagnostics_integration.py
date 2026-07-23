import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import ServiceCatalogItem, Ticket, TicketStatus, User
from app.services.ai import AIDiagnosisResult, AIService


def test_ai_diagnosis_result_pydantic_schema():
    raw_json = json.dumps({
        "fault": "Неисправность аккумулятора и контроллера",
        "reasoning": "Обнаружен перегрев BMS и окисление контактов",
        "matched_catalog_codes": ["battery_diag", "controller_repair"],
        "price_min": 2000.0,
        "price_max": 5000.0,
        "eta": "1-2 дня",
        "parts": ["BMS плата 36V", "Силовой разъем XT60"],
        "risk_level": "high",
        "recommended_checklist": ["Проверить напряжение банок", "Замерить фазные токи"]
    })

    result = AIDiagnosisResult.model_validate_json(raw_json)
    assert result.fault == "Неисправность аккумулятора и контроллера"
    assert result.matched_catalog_codes == ["battery_diag", "controller_repair"]
    assert result.price_min == 2000.0
    assert result.risk_level == "high"
    assert len(result.recommended_checklist) == 2


@pytest.mark.asyncio
async def test_ai_service_analyze_ticket_success():
    ai_service = AIService()
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({
                    "fault": "Прокол камеры заднего колеса",
                    "reasoning": "Давление упало до нуля",
                    "matched_catalog_codes": ["tire_tube"],
                    "price_min": 600.0,
                    "price_max": 1200.0,
                    "eta": "1-2 часа",
                    "parts": ["Камера 8.5 дюймов"],
                    "risk_level": "low",
                    "recommended_checklist": ["Осмотреть покрышку изнутри"]
                })
            )
        )
    ]

    with patch.object(ai_service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_completion

        catalog_item = ServiceCatalogItem(id=1, code="tire_tube", title="Замена камеры", base_price=600)
        result = await ai_service.analyze_ticket("Спустило колесо на ходу", [], catalog_items=[catalog_item])

        assert isinstance(result, AIDiagnosisResult)
        assert result.fault == "Прокол камеры заднего колеса"
        assert result.matched_catalog_codes == ["tire_tube"]
        assert result.price_min == 600.0


@pytest.mark.asyncio
async def test_ai_service_retry_and_fallback():
    ai_service = AIService()

    with patch.object(ai_service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create, \
         patch("asyncio.sleep", new_callable=AsyncMock):

        mock_create.side_effect = Exception("OpenAI API rate limit exceeded")

        result = await ai_service.analyze_ticket("Не включается самокат", [])

        assert mock_create.call_count == 3
        assert isinstance(result, AIDiagnosisResult)
        assert result.fault == "Требуется ручная диагностика"
        assert result.matched_catalog_codes == []
