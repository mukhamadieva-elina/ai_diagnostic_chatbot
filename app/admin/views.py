import logging

from sqladmin import ModelView
from starlette.requests import Request

from models.db import GlobalSettings, Scenario, ScenarioStep, ChatSession, Report, ValidationSettings
from services import llm

logger = logging.getLogger(__name__)


class GlobalSettingsAdmin(ModelView, model=GlobalSettings):
    name = "Глобальные настройки"
    name_plural = "Глобальные настройки"
    icon = "fa-solid fa-gear"

    column_list = [GlobalSettings.id]
    column_labels = {
        GlobalSettings.default_system_prompt: "Дефолтный промт (для всех сценариев)",
        GlobalSettings.next_step_text: "Текст блока «Следующий шаг» в PDF",
    }

    form_columns = ["default_system_prompt", "next_step_text"]
    form_args = {
        "default_system_prompt": {
            "label": "Дефолтный промт GigaChat (для всех сценариев)",
            "description": (
                "Применяется, если у сценария не задан собственный промт. "
                "Должен содержать инструкцию для AI с четырьмя разделами: "
                "# ОСНОВНАЯ ПРОБЛЕМА, # УРОВЕНЬ ЦИФРОВОЙ ЗРЕЛОСТИ, "
                "# ТЕКУЩЕЕ СОСТОЯНИЕ, # РЕКОМЕНДАЦИИ."
            ),
            "render_kw": {"rows": 18, "style": "font-family: monospace; font-size: 13px;"},
        },
        "next_step_text": {
            "label": "Текст блока «Следующий шаг» в PDF-отчёте",
            "description": (
                "Фиксированный текст-приглашение, который печатается в конце каждого отчёта. "
                "Отображается в выделенном блоке. Поддерживает маркированные списки (- пункт)."
            ),
            "render_kw": {"rows": 8},
        },
    }

    # Синглтон — создание и удаление запрещены
    can_create = False
    can_delete = False


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
                async with self.session_maker() as session:
                    await session.merge(model)
                    await session.commit()
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


class ValidationSettingsAdmin(ModelView, model=ValidationSettings):
    name = "Настройки валидации"
    name_plural = "Настройки валидации ответов"
    icon = "fa-solid fa-sliders"

    column_list = [
        ValidationSettings.enabled,
        ValidationSettings.type1_enabled,
        ValidationSettings.type2_enabled,
    ]
    column_labels = {
        ValidationSettings.enabled: "Валидация включена",
        ValidationSettings.type1_enabled: "Неосмысленный ответ — повторять вопрос",
        ValidationSettings.type2_enabled: "Слабый ответ — отмечать в отчёте",
        ValidationSettings.type1_message: "Сообщение при неосмысленном ответе",
        ValidationSettings.type2_answer_tag: "Пометка к слабому ответу для ИИ",
        ValidationSettings.classification_prompt: "Промт для классификации ответов",
    }

    form_columns = [
        "enabled",
        "type1_enabled",
        "type1_message",
        "type2_enabled",
        "type2_answer_tag",
        "classification_prompt",
    ]
    form_args = {
        "enabled": {
            "label": "Валидация включена",
            "description": "Если выключено — все ответы принимаются без проверки.",
        },
        "type1_enabled": {
            "label": "Неосмысленный ответ — повторять вопрос",
            "description": (
                "Если включено: когда пользователь пишет случайные символы, "
                "уклоняется от ответа или отвечает совсем не по теме — "
                "бот не переходит к следующему вопросу, а просит ответить заново."
            ),
        },
        "type1_message": {
            "label": "Сообщение при неосмысленном ответе",
            "description": (
                "Текст, который увидит пользователь. "
                "В конце автоматически добавляется повторный вопрос — "
                "оставьте {question} там, где он должен появиться."
            ),
            "render_kw": {"rows": 4},
        },
        "type2_enabled": {
            "label": "Слабый ответ — отмечать в отчёте",
            "description": (
                "Если включено: когда пользователь отвечает «не знаю», «хз», «нормально» и т.п., "
                "бот принимает ответ и идёт дальше, но добавляет к нему пометку. "
                "ИИ видит эту пометку при генерации отчёта и учитывает низкое качество ответа."
            ),
        },
        "type2_answer_tag": {
            "label": "Пометка к слабому ответу для ИИ",
            "description": (
                "Эта строка добавляется к ответу пользователя невидимо для него, "
                "но видна ИИ при составлении отчёта. Например: "
                "«[Пользователь не владеет темой]»."
            ),
        },
        "classification_prompt": {
            "label": "Промт для классификации ответов",
            "description": (
                "Инструкция для ИИ, который определяет тип каждого ответа. "
                "Переменные {question} и {answer} подставляются автоматически — "
                "не удаляйте их из текста."
            ),
            "render_kw": {"rows": 14, "style": "font-family: monospace; font-size: 13px;"},
        },
    }

    # Это синглтон — создание и удаление запрещены
    can_create = False
    can_delete = False


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
