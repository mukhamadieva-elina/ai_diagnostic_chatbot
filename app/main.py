from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqladmin import Admin

from admin.views import ScenarioAdmin, ScenarioStepAdmin, ChatSessionAdmin, ReportAdmin
from api.v1.router import router as api_router
from db.connection import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="AI Booster — Диагностический бот",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ограничьте до домена лендинга в проде
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)

admin = Admin(app, engine, title="AI Booster Admin")
admin.add_view(ScenarioAdmin)
admin.add_view(ScenarioStepAdmin)
admin.add_view(ChatSessionAdmin)
admin.add_view(ReportAdmin)
