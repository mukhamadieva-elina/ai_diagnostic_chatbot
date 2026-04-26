from fastapi import APIRouter

from api.v1.endpoints import chat, report

router = APIRouter(prefix="/api/v1")
router.include_router(chat.router)
router.include_router(report.router)
