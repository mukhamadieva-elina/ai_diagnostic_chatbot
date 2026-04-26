import uuid
from datetime import datetime, timedelta, timezone

import httpx

from config import settings

_GIGACHAT_TOKEN_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_GIGACHAT_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

_cached_token: str | None = None
_token_expires_at: datetime | None = None


async def _get_token() -> str:
    global _cached_token, _token_expires_at

    if _cached_token and _token_expires_at and datetime.now(timezone.utc) < _token_expires_at:
        return _cached_token

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {settings.gigachat_auth_token}",
    }
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            _GIGACHAT_TOKEN_URL,
            headers=headers,
            data={"scope": "GIGACHAT_API_PERS"},
            follow_redirects=True,
        )
        response.raise_for_status()
        data = response.json()

    _cached_token = data["access_token"]
    # GigaChat токены живут 30 минут; обновляем за 2 минуты до истечения
    _token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=28)
    return _cached_token


_SYSTEM_PROMPT = """Ты — эксперт по цифровой трансформации и развитию бизнеса от компании AI Booster.
Твоя задача — провести диагностику компании на основе диалога с представителем компании \
и подготовить структурированный отчёт.

Отчёт должен содержать:
1. РЕЗЮМЕ ПРОБЛЕМЫ — краткое описание ключевой проблемы (2-3 предложения).
2. АНАЛИЗ СИТУАЦИИ — разбор ответов пользователя, выявление корневых причин.
3. УРОВЕНЬ ЦИФРОВОЙ ЗРЕЛОСТИ — оценка по шкале от 1 до 5 по каждому из направлений: \
Процессы, Данные, Технологии, Персонал. Укажи итоговый балл для каждого направления \
в формате "Направление: N/5".
4. РЕКОМЕНДАЦИИ — конкретные первые шаги для решения проблемы (3-5 пунктов).
5. ПРИОРИТЕТ — какой шаг сделать первым и почему.

Пиши деловым, но понятным языком. Избегай воды и общих фраз."""


async def generate_report(dialog_text: str) -> str:
    token = await _get_token()
    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": dialog_text},
        ],
        "stream": False,
        "temperature": 0.7,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
        response = await client.post(_GIGACHAT_CHAT_URL, headers=headers, json=payload)
        response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]