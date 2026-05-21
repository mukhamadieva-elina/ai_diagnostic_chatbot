from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from sqladmin import Admin

from admin.auth import AdminBasicAuthMiddleware
from admin.views import GlobalSettingsAdmin, ScenarioAdmin, ScenarioStepAdmin, ChatSessionAdmin, ReportAdmin, ValidationSettingsAdmin
from api.v1.router import router as api_router
from db.connection import engine

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="AI Booster — Диагностический бот",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.add_middleware(AdminBasicAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ограничьте до домена лендинга в проде
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/", include_in_schema=False)
async def serve_landing():
    return FileResponse(STATIC_DIR / "landing.html", headers={"Cache-Control": "no-cache"})

@app.get("/chat", include_in_schema=False)
async def serve_frontend():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

admin = Admin(app, engine, title="AI Booster Admin")
admin.add_view(GlobalSettingsAdmin)
admin.add_view(ScenarioAdmin)
admin.add_view(ScenarioStepAdmin)
admin.add_view(ValidationSettingsAdmin)
admin.add_view(ChatSessionAdmin)
admin.add_view(ReportAdmin)
