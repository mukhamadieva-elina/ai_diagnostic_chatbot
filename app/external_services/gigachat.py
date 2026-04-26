import json

import requests

import uuid
import httpx


async def get_giga_token(auth_data: str):
    # Тот самый URL из вашего curl
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

    # RqUID должен быть уникальным для каждого запроса
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': str(uuid.uuid4()),
        'Authorization': f'Basic {auth_data}'
    }

    # --data-urlencode преобразуется в обычный словарь для параметра data
    payload = {
        'scope': 'GIGACHAT_API_PERS'
    }

    async with httpx.AsyncClient(verify=False) as client:
        try:
            # -L в curl — это follow_redirects=True (у httpx по умолчанию False)
            print(123)
            response = await client.post(
                url,
                headers=headers,
                data=payload,
                follow_redirects=True
            )
            response.raise_for_status()
            print(123)
            data = response.json()
            print(data)
            return data.get('access_token')
        except Exception as e:
            print(f"Ошибка при получении токена: {e}")
            return None


async def get_giga_answer(token: str, dialog_context: str, promt: str = None):
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

    payload = {
        "model": "GigaChat",
        "messages": [
            {
                "role": "system",
                "content": "Ты — эксперт по цифровой трансформации и развитию бизнеса. "
                           "Твоя задача — провести диагностику компании по сценарию 'Снижение продаж' "
                           "и определить уровень цифровой зрелости на основе ответов пользователя."
            },
            {
                "role": "user",
                "content": dialog_context
            }
        ],
        "stream": False
    }

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {token}'
    }

    # Используем httpx вместо requests
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()  # Выдаст ошибку, если статус не 200

            result = response.json()
            # Возвращаем только текст ответа, а не весь JSON
            return result['choices'][0]['message']['content']

        except Exception as e:
            print(f"Ошибка в get_giga_answer: {e}")
            return f"Ошибка ИИ: {e}"