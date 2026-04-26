import io
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import settings

# Регистрируем шрифт с поддержкой кириллицы
_FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"
_DEJAVU_PATH = _FONT_DIR / "DejaVuSans.ttf"
_DEJAVU_BOLD_PATH = _FONT_DIR / "DejaVuSans-Bold.ttf"


def _register_fonts() -> str:
    """Регистрирует шрифт и возвращает его имя."""
    if _DEJAVU_PATH.exists():
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", str(_DEJAVU_PATH)))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(_DEJAVU_BOLD_PATH)))
            return "DejaVu"
        except Exception:
            pass
    return "Helvetica"


_FONT = _register_fonts()
_FONT_BOLD = "DejaVu-Bold" if _FONT == "DejaVu" else "Helvetica-Bold"

_BRAND_BLUE = colors.HexColor("#1A3C6E")
_BRAND_ACCENT = colors.HexColor("#2196F3")
_LIGHT_GRAY = colors.HexColor("#F5F5F5")


def _build_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title", fontName=_FONT_BOLD, fontSize=20, textColor=_BRAND_BLUE,
            spaceAfter=6, leading=24,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", fontName=_FONT, fontSize=12, textColor=colors.gray,
            spaceAfter=12,
        ),
        "section": ParagraphStyle(
            "Section", fontName=_FONT_BOLD, fontSize=13, textColor=_BRAND_BLUE,
            spaceBefore=16, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body", fontName=_FONT, fontSize=10, leading=15, spaceAfter=6,
        ),
        "qa_question": ParagraphStyle(
            "QAQuestion", fontName=_FONT_BOLD, fontSize=9, textColor=_BRAND_BLUE,
            spaceBefore=6, spaceAfter=2,
        ),
        "qa_answer": ParagraphStyle(
            "QAAnswer", fontName=_FONT, fontSize=9, leftIndent=12, spaceAfter=2,
        ),
    }


def _parse_maturity_scores(llm_text: str) -> dict[str, float]:
    """Извлекает оценки цифровой зрелости из текста LLM."""
    dimensions = {
        "Процессы": 0.0, "Данные": 0.0, "Технологии": 0.0, "Персонал": 0.0,
    }
    for dim in dimensions:
        match = re.search(rf"{dim}[:\s]+(\d[\.,]?\d?)\s*/\s*5", llm_text, re.IGNORECASE)
        if match:
            dimensions[dim] = float(match.group(1).replace(",", "."))
        else:
            dimensions[dim] = 2.5  # нейтральное значение по умолчанию
    return dimensions


def _make_radar_chart(scores: dict[str, float]) -> io.BytesIO:
    labels = list(scores.keys())
    values = list(scores.values())
    n = len(labels)

    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    values_closed = values + [values[0]]
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw={"polar": True})
    ax.plot(angles_closed, values_closed, color="#2196F3", linewidth=2)
    ax.fill(angles_closed, values_closed, color="#2196F3", alpha=0.25)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["1", "2", "3", "4", "5"], fontsize=7)
    ax.grid(color="gray", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_title("Цифровая зрелость", pad=15, fontsize=10, fontweight="bold", color="#1A3C6E")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_bar_chart(scores: dict[str, float]) -> io.BytesIO:
    labels = list(scores.keys())
    values = list(scores.values())

    fig, ax = plt.subplots(figsize=(5, 2.5))
    bar_colors = ["#2196F3" if v >= 3 else "#FF7043" for v in values]
    bars = ax.barh(labels, values, color=bar_colors, height=0.5)
    ax.set_xlim(0, 5)
    ax.set_xlabel("Баллов из 5", fontsize=8)
    ax.axvline(x=3, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}", va="center", fontsize=8)
    ax.set_title("Оценка по направлениям", fontsize=9, fontweight="bold", color="#1A3C6E")
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    good = mpatches.Patch(color="#2196F3", label="≥ 3 — удовлетворительно")
    bad = mpatches.Patch(color="#FF7043", label="< 3 — требует внимания")
    ax.legend(handles=[good, bad], fontsize=7, loc="lower right")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_pdf(
    session_id: uuid.UUID,
    scenario_name: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    dialog_entries: list[dict],  # [{"question": str, "answer": str}]
    llm_response: str,
) -> str:
    """Генерирует PDF-отчёт и возвращает путь к файлу."""
    reports_dir = Path(settings.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    filename = f"report_{session_id}.pdf"
    filepath = reports_dir / filename

    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    styles = _build_styles()
    story = []

    # --- Шапка ---
    story.append(Paragraph("AI Booster", styles["title"]))
    story.append(Paragraph("AI-диагностика бизнес-проблемы", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BRAND_BLUE, spaceAfter=12))

    # --- Мета-информация ---
    generated_at = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    meta_data = [
        ["Клиент:", contact_name or "—"],
        ["Email:", contact_email or "—"],
        ["Телефон:", contact_phone or "—"],
        ["Сценарий:", scenario_name],
        ["Дата отчёта:", generated_at],
    ]
    meta_table = Table(meta_data, colWidths=[4 * cm, 12 * cm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), _FONT_BOLD),
        ("FONTNAME", (1, 0), (1, -1), _FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), _BRAND_BLUE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT_GRAY),
        ("ROUNDEDCORNERS", [4]),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.5 * cm))

    # --- Диалог ---
    story.append(Paragraph("Диалог с диагностом", styles["section"]))
    for entry in dialog_entries:
        story.append(Paragraph(f"Вопрос: {entry['question']}", styles["qa_question"]))
        story.append(Paragraph(f"Ответ: {entry['answer'] or '—'}", styles["qa_answer"]))
    story.append(Spacer(1, 0.3 * cm))

    # --- Анализ LLM ---
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=8))
    story.append(Paragraph("AI-анализ и рекомендации", styles["section"]))
    for line in llm_response.split("\n"):
        line = line.strip()
        if line:
            story.append(Paragraph(line, styles["body"]))
    story.append(Spacer(1, 0.5 * cm))

    # --- Графики ---
    scores = _parse_maturity_scores(llm_response)

    radar_buf = _make_radar_chart(scores)
    bar_buf = _make_bar_chart(scores)

    chart_row = [[
        Image(radar_buf, width=7 * cm, height=7 * cm),
        Image(bar_buf, width=9 * cm, height=5 * cm),
    ]]
    chart_table = Table(chart_row, colWidths=[8 * cm, 10 * cm])
    chart_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(Paragraph("Визуализация цифровой зрелости", styles["section"]))
    story.append(chart_table)

    # --- Подвал ---
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Отчёт сгенерирован AI Booster · ai-booster.ru",
        ParagraphStyle("footer", fontName=_FONT, fontSize=8, textColor=colors.gray, alignment=1),
    ))

    doc.build(story)
    return str(filepath)