import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from config import settings

logger = logging.getLogger(__name__)

_GIGACHAT_TOKEN_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_GIGACHAT_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
_GIGACHAT_FILES_URL = "https://gigachat.devices.sberbank.ru/api/v1/files"

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
    _token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=28)
    return _cached_token


DEFAULT_SYSTEM_PROMPT = """Ты — эксперт по цифровой трансформации от компании AI Booster.
Проведи диагностику компании на основе диалога и сформируй структурированный отчёт.

Используй СТРОГО следующую структуру — четыре раздела с заголовками первого уровня:

# ОСНОВНАЯ ПРОБЛЕМА
Краткое описание ключевой проблемы (2-3 предложения). Без воды.

# УРОВЕНЬ ЦИФРОВОЙ ЗРЕЛОСТИ
Оцени каждое направление по шкале 1-5 в формате "Направление: N/5":
Процессы: N/5
Данные: N/5
Технологии: N/5
Персонал: N/5

# ТЕКУЩЕЕ СОСТОЯНИЕ
Анализ ситуации: что происходит в компании, корневые причины проблем (3-5 предложений).

# РЕКОМЕНДАЦИИ
- Рекомендация 1
- Рекомендация 2
- Рекомендация 3
Конкретные первые шаги (3-5 пунктов).

Пиши деловым, понятным языком. Без воды и общих фраз."""


async def upload_prompt_file(prompt_text: str, scenario_name: str) -> str:
    """
    Загружает текст промта как .txt файл в хранилище GigaChat.
    Возвращает file_id для использования в attachments.
    """
    token = await _get_token()
    filename = f"prompt_{scenario_name.replace(' ', '_')}.txt"

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        response = await client.post(
            _GIGACHAT_FILES_URL,
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, prompt_text.encode("utf-8"), "text/plain")},
            data={"purpose": "general"},
        )
        response.raise_for_status()

    file_id = response.json()["id"]
    logger.info("Промт сценария '%s' загружен в GigaChat, file_id: %s", scenario_name, file_id)
    return file_id


async def delete_file(file_id: str) -> None:
    """Удаляет файл из хранилища GigaChat (вызывается при замене промта)."""
    token = await _get_token()
    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        response = await client.delete(
            f"{_GIGACHAT_FILES_URL}/{file_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code not in (200, 204):
        logger.warning("Не удалось удалить файл %s из GigaChat: %s", file_id, response.text)


async def generate_report(
    dialog_text: str,
    system_prompt: str | None = None,
    prompt_file_id: str | None = None,
    global_default_prompt: str | None = None,
) -> str:
    """
    Генерирует отчёт через GigaChat.

    Приоритет промта:
      1. prompt_file_id        — файл сценария в хранилище GigaChat (attachments)
      2. system_prompt         — кастомный промт сценария (text)
      3. global_default_prompt — глобальный дефолт из БД
      4. DEFAULT_SYSTEM_PROMPT — хардкод-запасной вариант
    """
    token = await _get_token()

    if prompt_file_id:
        payload = {
            "model": "GigaChat-2-Max",
            "messages": [
                {
                    "role": "user",
                    "content": dialog_text,
                    "attachments": [prompt_file_id],
                },
            ],
            "stream": False,
            "temperature": 0.7,
        }
    else:
        effective_prompt = system_prompt or global_default_prompt or DEFAULT_SYSTEM_PROMPT
        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": effective_prompt},
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


_VALIDATION_PROMPT_TEMPLATE = (
    "Определи тип ответа пользователя. Ответь ТОЛЬКО одним словом: TYPE1, TYPE2 или TYPE3.\n\n"
    "ТИП 1 — НЕОСМЫСЛЕННЫЙ: случайные символы/буквы, ответ не по теме вопроса, "
    "намеренное уклонение («пропустить», «не хочу отвечать», «неважно»).\n"
    "ТИП 2 — НИЗКИЙ УРОВЕНЬ: пользователь не владеет темой, короткие ответы без контекста "
    "(«не знаю», «хз», «сложно сказать», «всё плохо», «нормально», «никак», «не думали об этом»).\n"
    "ТИП 3 — ОСМЫСЛЕННЫЙ: описывает реальную ситуацию в компании, ответ относится к вопросу, "
    "даже короткий но содержательный («CRM не используем», «всё в Excel», «менеджеры работают по-своему»).\n\n"
    "Вопрос: {question}\n"
    "Ответ: {answer}"
)


async def validate_answer(question: str, answer: str, prompt_template: str | None = None) -> str:
    """
    Классифицирует ответ пользователя на диагностический вопрос.
    Возвращает 'TYPE1', 'TYPE2' или 'TYPE3'.
    При ошибке возвращает 'TYPE3' (пропускаем, не блокируем диалог).
    """
    try:
        token = await _get_token()
        template = prompt_template or _VALIDATION_PROMPT_TEMPLATE
        prompt = template.format(question=question, answer=answer)
        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 10,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            response = await client.post(_GIGACHAT_CHAT_URL, headers=headers, json=payload)
            response.raise_for_status()

        text = response.json()["choices"][0]["message"]["content"].strip().upper()
        if "TYPE1" in text:
            return "TYPE1"
        if "TYPE2" in text:
            return "TYPE2"
        return "TYPE3"
    except Exception as e:
        logger.warning("Валидация ответа не удалась, считаем TYPE3: %s", e)
        return "TYPE3"
