from sqladmin import ModelView

from models.db import Scenario, ScenarioStep, ChatSession, Report


class ScenarioAdmin(ModelView, model=Scenario):
    name = "Сценарий"
    name_plural = "Сценарии"
    icon = "fa-solid fa-list-check"

    column_list = [Scenario.id, Scenario.name, Scenario.is_active]
    column_searchable_list = [Scenario.name]
    column_sortable_list = [Scenario.id, Scenario.name]
    form_excluded_columns = ["steps", "sessions"]


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
