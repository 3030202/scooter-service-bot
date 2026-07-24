DIAGNOSIS_SYSTEM_PROMPT = """
Ты главный технический диагност сервисного центра электротранспорта (электросамокаты, гироскутеры, моноколеса).
Отвечай строго в формате JSON, соответствующем запрошенной схеме.
""".strip()


def build_diagnosis_user_prompt(description: str, catalog_str: str) -> str:
    return f"""
Проанализируй симптомы поломки и фотографии электротранспорта.

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
