"""
Интеграция с Bitrix24 CRM.
Сейчас — заглушка. Когда получите доступы, заполните переменные окружения:
  BITRIX_PORTAL, BITRIX_USER_ID, BITRIX_WEBHOOK_TOKEN
и раскомментируйте логику ниже.
"""
import logging
from pathlib import Path

import httpx

from config import settings

logger = logging.getLogger(__name__)


async def push_deal(
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    scenario_name: str,
    pdf_path: str,
    session_id: str,
) -> str | None:
    """
    Создаёт сделку в Bitrix24 и прикрепляет PDF.
    Возвращает ID сделки или None при ошибке / незаполненном конфиге.
    """
    if not settings.bitrix_configured:
        logger.info("Bitrix24 не настроен — пропускаем интеграцию.")
        return None

    base_url = (
        f"https://{settings.bitrix_portal}/rest/"
        f"{settings.bitrix_user_id}/{settings.bitrix_webhook_token}"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Создаём контакт
        contact_resp = await client.post(f"{base_url}/crm.contact.add.json", json={
            "fields": {
                "NAME": contact_name,
                "EMAIL": [{"VALUE": contact_email, "VALUE_TYPE": "WORK"}],
                "PHONE": [{"VALUE": contact_phone, "VALUE_TYPE": "WORK"}],
                "SOURCE_ID": "WEB",
            }
        })
        contact_resp.raise_for_status()
        contact_id = contact_resp.json().get("result")

        # 2. Создаём сделку
        deal_resp = await client.post(f"{base_url}/crm.deal.add.json", json={
            "fields": {
                "TITLE": f"AI-диагностика: {scenario_name} — {contact_name}",
                "CONTACT_ID": contact_id,
                "SOURCE_ID": "WEB",
                "COMMENTS": f"Сессия диагностики: {session_id}",
                "STAGE_ID": "NEW",
            }
        })
        deal_resp.raise_for_status()
        deal_id = str(deal_resp.json().get("result"))

        # 3. Прикрепляем PDF к сделке
        pdf_bytes = Path(pdf_path).read_bytes()
        pdf_name = Path(pdf_path).name
        attach_resp = await client.post(f"{base_url}/crm.deal.update.json", json={
            "id": deal_id,
            "fields": {
                "UF_CRM_FILES": [{
                    "fileData": [pdf_name, pdf_bytes.hex()],
                }]
            },
        })
        # Не кидаем исключение если прикрепление не удалось — сделка уже создана
        if attach_resp.status_code != 200:
            logger.warning("Не удалось прикрепить PDF к сделке Bitrix: %s", attach_resp.text)

    logger.info("Сделка Bitrix24 создана: %s", deal_id)
    return deal_id