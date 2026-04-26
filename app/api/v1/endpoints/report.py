import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.deps import get_db
from models.db import ChatSession, Report

router = APIRouter(prefix="/report", tags=["report"])


@router.get("/{session_id}")
async def download_report(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Скачать PDF-отчёт по session_id."""
    result = await db.execute(
        select(Report).where(Report.session_id == session_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден или ещё не готов")

    pdf_path = Path(report.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Файл отчёта не найден на сервере")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"ai_booster_report_{session_id}.pdf",
    )
