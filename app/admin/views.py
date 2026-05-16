import logging

from sqladmin import ModelView

from models.db import GlobalSettings, Scenario, ScenarioStep, ChatSession, Report, ValidationSettings

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
            "label": "Универсальный промт GigaChat (для всех сценариев)",
            "description": (
                "Базовая инструкция для AI — применяется ко всем сценариям. "
                "Если у сценария задан дополнительный промт, он добавляется к этому через разделитель. "
                "Укажите в промте, какие разделы должен содержать отчёт — каждый раздел начинается "
                "с заголовка первого уровня, например: # ОСНОВНАЯ ПРОБЛЕМА, # РЕКОМЕНДАЦИИ. "
                "PDF сформирует ровно те разделы, которые вернёт GigaChat."
            ),
            "render_kw": {"rows": 18, "style": "font-family: monospace; font-size: 13px;"},
        },
        "next_step_text": {
            "label": "Мотивационный блок в конце PDF-отчёта",
            "description": (
                "Фиксированный текст-приглашение, который печатается в конце каждого отчёта без заголовка. "
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

    column_list = [Scenario.id, Scenario.name, Scenario.is_active]
    column_searchable_list = [Scenario.name]
    column_sortable_list = [Scenario.id, Scenario.name]
    form_columns = ["name", "description", "is_active", "system_prompt"]
    form_args = {
        "system_prompt": {
            "label": "Дополнительный промт сценария",
            "description": (
                "Уточнения для AI, специфичные для данного сценария. "
                "Объединяется с универсальным промтом и передаётся в GigaChat вместе. "
                "Здесь можно переопределить или дополнить список разделов отчёта — "
                "укажите нужные заголовки в формате # НАЗВАНИЕ РАЗДЕЛА, "
                "и PDF сформирует именно их. "
                "Если оставить пустым — используется только универсальный промт."
            ),
            "render_kw": {"rows": 14, "style": "font-family: monospace; font-size: 13px;"},
        },
        "description": {
            "label": "Описание сценария",
            "render_kw": {"rows": 3},
        },
    }


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
                "Если включено: когда пользователь отвечает «не знаю», «нормально» и т.п., "
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
