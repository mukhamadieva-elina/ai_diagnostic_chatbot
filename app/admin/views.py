import logging

from sqladmin import ModelView
from starlette.requests import Request

from models.db import Scenario, ScenarioStep, ChatSession, Report
from services import llm

logger = logging.getLogger(__name__)


class ScenarioAdmin(ModelView, model=Scenario):
    name = "Сценарий"
    name_plural = "Сценарии"
    icon = "fa-solid fa-list-check"

    column_list = [Scenario.id, Scenario.name, Scenario.is_active, Scenario.gigachat_file_id]
    column_labels = {Scenario.gigachat_file_id: "GigaChat file_id"}
    column_searchable_list = [Scenario.name]
    column_sortable_list = [Scenario.id, Scenario.name]
    form_columns = ["name", "description", "is_active", "system_prompt"]
    form_args = {
        "system_prompt": {
            "label": "Системный промт для GigaChat",
            "description": (
                "Инструкция для AI. После сохранения автоматически загрузится "
                "в хранилище GigaChat и будет передаваться через attachments. "
                "Если оставить пустым — будет использован стандартный промт."
            ),
            "render_kw": {"rows": 14, "style": "font-family: monospace; font-size: 13px;"},
        },
        "description": {
            "label": "Описание сценария",
            "render_kw": {"rows": 3},
        },
    }

    async def after_model_change(self, data: dict, model: Scenario, is_created: bool, request: Request) -> None:
        """
        Хук после сохранения сценария.
        Если system_prompt заполнен — загружает его как файл в GigaChat
        и сохраняет полученный file_id. Старый файл при этом удаляется.
        """
        new_prompt = (model.system_prompt or "").strip()

        if not new_prompt:
            # Промт очищен — удаляем старый файл из GigaChat если был
            if model.gigachat_file_id:
                try:
                    await llm.delete_file(model.gigachat_file_id)
                except Exception as e:
                    logger.warning("Не удалось удалить старый файл GigaChat: %s", e)
                model.gigachat_file_id = None
                await self.session_maker()  # обновляем запись
            return

        try:
            # Удаляем предыдущий файл если он есть
            if model.gigachat_file_id:
                try:
                    await llm.delete_file(model.gigachat_file_id)
                except Exception as e:
                    logger.warning("Не удалось удалить старый файл GigaChat %s: %s", model.gigachat_file_id, e)

            # Загружаем новый файл
            file_id = await llm.upload_prompt_file(new_prompt, model.name)
            model.gigachat_file_id = file_id

            # Сохраняем file_id в БД через сессию
            async with self.session_maker() as session:
                await session.merge(model)
                await session.commit()

            logger.info("Сценарий '%s': промт загружен в GigaChat, file_id=%s", model.name, file_id)

        except Exception as e:
            logger.error("Не удалось загрузить промт в GigaChat для сценария '%s': %s", model.name, e)


class ScenarioStepAdmin(ModelView, model=ScenarioStep):
    name = "Шаг сценария"
    name_plural = "Шаги сценариев"
    icon = "fa-solid fa-comment-dots"

    column_list = [ScenarioStep.id, ScenarioStep.scenario, ScenarioStep.order_index, ScenarioStep.message_text]
    column_sortable_list = [ScenarioStep.scenario_id, ScenarioStep.order_index]
    column_default_sort = [("scenario_id", False), ("order_index", False)]
    form_columns = ["scenario", "order_index", "message_text"]


class ChatSessionAdmin(ModelView, model=ChatSession):
    name = "Сессия"
    name_plural = "Сессии диалогов"
    icon = "fa-solid fa-comments"

    column_list = [
        ChatSession.id, ChatSession.scenario, ChatSession.status,
        ChatSession.contact_name, ChatSession.contact_email,
        ChatSession.created_at,
    ]
    column_sortable_list = [ChatSession.created_at, ChatSession.status]
    can_create = False
    can_edit = False


class ReportAdmin(ModelView, model=Report):
    name = "Отчёт"
    name_plural = "Отчёты"
    icon = "fa-solid fa-file-pdf"

    column_list = [
        Report.id, Report.session_id, Report.created_at,
        Report.sent_to_bitrix, Report.bitrix_deal_id,
    ]
    column_sortable_list = [Report.created_at, Report.sent_to_bitrix]
    can_create = False
    can_edit = False
