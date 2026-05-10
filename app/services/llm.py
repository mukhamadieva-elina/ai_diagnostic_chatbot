import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from config import settings

logger = logging.getLogger(__name__)

_GIGACHAT_TOKEN_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_GIGACHAT_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

_cached_token: str | None = None
_token_expires_at: datetime | None = None

_http_client: httpx.AsyncClient = httpx.AsyncClient(verify=False, timeout=60.0)


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
    response = await _http_client.post(
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


_MATURITY_CHART_SUFFIX = """

---

ФОРМАТ ОТЧЁТА — строго четыре раздела. Заголовки только одиночным # точно как указано ниже (без номеров, без дополнительных слов в заголовке):

# ОСНОВНАЯ ПРОБЛЕМА
2-3 предложения о ключевой проблеме компании.

# УРОВЕНЬ ЦИФРОВОЙ ЗРЕЛОСТИ
Оценки по вопросам 1–5 ТОЛЬКО в виде маркированного списка (НЕ таблицей, без пояснений и цитат — только уровень):
- Вопрос 1 (тема): Уровень
- Вопрос 2 (тема): Уровень
- Вопрос 3 (тема): Уровень
- Вопрос 4 (тема): Уровень
- Вопрос 5 (тема): Уровень
Итого: низких — N, средних — N, высоких — N
Общий уровень: Название
Контекст:
- Вопрос 6: краткое резюме
- Вопрос 7: краткое резюме
Затем в конце раздела (без подзаголовков) ровно четыре строки:



Процессы: N/5
Данные: N/5
Технологии: N/5
Персонал: N/5

# ТЕКУЩЕЕ СОСТОЯНИЕ
3-5 предложений: анализ ситуации, корневые причины.

# РЕКОМЕНДАЦИИ
3-5 конкретных шагов маркированным списком."""


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


async def generate_report(
    dialog_text: str,
    scenario_prompt: str | None = None,
    global_default_prompt: str | None = None,
) -> str:
    """
    Генерирует отчёт через GigaChat.

    Итоговый промт = универсальный (global_default_prompt или DEFAULT_SYSTEM_PROMPT)
    + промт сценария (scenario_prompt), если он задан — объединяются через разделитель.
    """
    token = await _get_token()

    base_prompt = global_default_prompt or DEFAULT_SYSTEM_PROMPT
    if scenario_prompt:
        effective_prompt = f"{base_prompt}\n\n---\n\n{scenario_prompt}"
    else:
        effective_prompt = base_prompt
    effective_prompt = f"{effective_prompt}{_MATURITY_CHART_SUFFIX}"

    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": effective_prompt},
            {"role": "user", "content": dialog_text},
        ],
        "stream": False,
        "temperature": 0.7,
        "max_tokens": 2000,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    response = await _http_client.post(_GIGACHAT_CHAT_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


_VALIDATION_PROMPT_TEMPLATE = (
    "Определи тип ответа пользователя. Ответь ТОЛЬКО одним словом: TYPE1, TYPE2 или TYPE3.\n\n"
    "ТИП 1 — НЕОСМЫСЛЕННЫЙ: случайные символы/буквы, ответ не по теме вопроса, "
    "намеренное уклонение («пропустить», «не хочу отвечать», «неважно»).\n"
    "ТИП 2 — НИЗКИЙ УРОВЕНЬ: пользователь не владеет темой, короткие ответы без контекста "
    "(«не знаю», «сложно сказать», «всё плохо», «нормально», «никак», «не думали об этом»).\n"
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
        response = await _http_client.post(_GIGACHAT_CHAT_URL, headers=headers, json=payload)
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
