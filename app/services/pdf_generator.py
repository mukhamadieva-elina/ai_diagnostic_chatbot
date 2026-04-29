import html
import io
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import settings

_BASE_DIR = Path(__file__).parent.parent.parent
_FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"
_BG_PATH = _BASE_DIR / "AI_Booster_Background.png"

_TEXT_COLOR = colors.HexColor("#1D1D1D")
_ACCENT_HEX = "#787AFF"
_ACCENT_COLOR = colors.HexColor(_ACCENT_HEX)
_BLOCK_BG = colors.HexColor("#EDEEFF")

# Section gap: space inserted before every H1 (except the first)
_SECTION_GAP = 1.2 * cm


def _register_fonts() -> tuple[str, str, str]:
    light_path = _FONT_DIR / "ALSGorizont-Light.ttf"
    bold_path = _FONT_DIR / "ALSGorizont-Bold.ttf"
    if light_path.exists() and bold_path.exists():
        try:
            pdfmetrics.registerFont(TTFont("ALSGorizont", str(light_path)))
            pdfmetrics.registerFont(TTFont("ALSGorizont-Bold", str(bold_path)))
            pdfmetrics.registerFont(TTFont("ALSGorizont-Light", str(light_path)))
            pdfmetrics.registerFontFamily(
                "ALSGorizont",
                normal="ALSGorizont",
                bold="ALSGorizont-Bold",
                italic="ALSGorizont",
                boldItalic="ALSGorizont-Bold",
            )
            return "ALSGorizont", "ALSGorizont-Bold", "ALSGorizont-Light"
        except Exception:
            pass
    return "Helvetica", "Helvetica-Bold", "Helvetica"


_FONT, _FONT_BOLD, _FONT_LIGHT = _register_fonts()


def _apply_highlights(text: str) -> str:
    """Escape XML entities, then colour-highlight 'AI Booster' and markdown spans."""
    text = html.escape(text, quote=False)
    text = re.sub(
        r'\bAI Booster\b',
        f'<font name="{_FONT_BOLD}" color="{_ACCENT_HEX}">AI Booster</font>',
        text,
    )
    text = re.sub(r'\*\*(.+?)\*\*', rf'<font color="{_ACCENT_HEX}">\1</font>', text)
    text = re.sub(r'\*(.+?)\*', rf'<font color="{_ACCENT_HEX}">\1</font>', text)
    return text


def _build_styles() -> dict:
    return {
        "h1": ParagraphStyle(
            "H1",
            fontName=_FONT_BOLD,
            fontSize=18,
            textColor=_TEXT_COLOR,
            alignment=0,
            leftIndent=0,
            spaceBefore=0,
            spaceAfter=24,
            leading=18,
        ),
        "h2": ParagraphStyle(
            "H2",
            fontName=_FONT_BOLD,
            fontSize=14,
            textColor=_TEXT_COLOR,
            alignment=0,
            leftIndent=0,
            spaceBefore=12,
            spaceAfter=0,
            leading=14,
        ),
        "body": ParagraphStyle(
            "Body",
            fontName=_FONT_LIGHT,
            fontSize=14,
            textColor=_TEXT_COLOR,
            alignment=0,
            leftIndent=0,
            spaceBefore=6,
            spaceAfter=0,
            leading=14,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            fontName=_FONT_LIGHT,
            fontSize=14,
            textColor=_TEXT_COLOR,
            alignment=0,
            leftIndent=0.6 * cm,
            firstLineIndent=-0.6 * cm,
            spaceBefore=6,
            spaceAfter=0,
            leading=14,
        ),
        "level_badge": ParagraphStyle(
            "LevelBadge",
            fontName=_FONT_BOLD,
            fontSize=18,
            textColor=_ACCENT_COLOR,
            alignment=0,
            spaceBefore=8,
            spaceAfter=8,
            leading=18,
        ),
        "footer": ParagraphStyle(
            "Footer",
            fontName=_FONT_LIGHT,
            fontSize=8,
            textColor=colors.HexColor("#888888"),
            alignment=1,
        ),
    }


# ── LLM response parsing ────────────────────────────────────────────────────

_SECTION_ALIASES: dict[str, list[str]] = {
    "problem":         ["ОСНОВНАЯ ПРОБЛЕМА", "РЕЗЮМЕ ПРОБЛЕМЫ"],
    "level":           ["УРОВЕНЬ ЦИФРОВОЙ ЗРЕЛОСТИ", "УРОВЕНЬ ЗРЕЛОСТИ"],
    "state":           ["ТЕКУЩЕЕ СОСТОЯНИЕ", "АНАЛИЗ СИТУАЦИИ", "АНАЛИЗ"],
    "recommendations": ["РЕКОМЕНДАЦИИ"],
}


def _parse_llm_sections(text: str) -> dict[str, str]:
    """Split LLM markdown into named sections by top-level headings."""
    raw: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        if line.startswith("# "):
            if current_key is not None:
                raw[current_key] = "\n".join(current_lines).strip()
            current_key = line[2:].strip().upper()
            current_lines = []
        else:
            if current_key is not None:
                current_lines.append(line)

    if current_key is not None:
        raw[current_key] = "\n".join(current_lines).strip()

    result: dict[str, str] = {}
    for canonical, aliases in _SECTION_ALIASES.items():
        for alias in aliases:
            if alias in raw:
                result[canonical] = raw[alias]
                break

    return result


def _section_to_flowables(text: str, styles: dict) -> list:
    """Convert plain section text (no H1) into ReportLab flowables."""
    elements = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or re.match(r'^[-*_]{3,}$', stripped):
            continue
        if stripped.startswith("### "):
            elements.append(Paragraph(_apply_highlights(stripped[4:]), styles["h2"]))
        elif stripped.startswith("## "):
            elements.append(Paragraph(_apply_highlights(stripped[3:]), styles["h2"]))
        elif re.match(r'^[-*•]\s', stripped):
            content = _apply_highlights(stripped[2:])
            elements.append(Paragraph(f"• {content}", styles["bullet"]))
        elif re.match(r'^\d+[.)]\s', stripped):
            content = _apply_highlights(re.sub(r'^\d+[.)]\s+', "", stripped))
            elements.append(Paragraph(f"• {content}", styles["bullet"]))
        else:
            elements.append(Paragraph(_apply_highlights(stripped), styles["body"]))
    return elements


# ── Visual helpers ──────────────────────────────────────────────────────────

def _draw_background(canvas, _doc) -> None:
    if _BG_PATH.exists():
        canvas.saveState()
        canvas.drawImage(
            str(_BG_PATH), 0, 0,
            width=A4[0], height=A4[1],
            preserveAspectRatio=False,
            mask="auto",
        )
        canvas.restoreState()


def _make_ai_booster_block(flowables: list, width: float) -> Table | None:
    """Wrap content in a left-accented highlight box."""
    if not flowables:
        return None
    rows = [[f] for f in flowables]
    t = Table(rows, colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _BLOCK_BG),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING",    (0, 0), (0, 0), 10),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("LINEBEFORE",    (0, 0), (0, -1), 3, _ACCENT_COLOR),
        ("INNERGRID",     (0, 0), (-1, -1), 0, colors.white),
    ]))
    return t


def _maturity_level_name(scores: dict[str, float]) -> str:
    avg = sum(scores.values()) / len(scores) if scores else 0
    if avg < 2.0:
        return "Начальный уровень"
    if avg < 3.0:
        return "Развивающийся уровень"
    if avg < 4.0:
        return "Зрелый уровень"
    return "Передовой уровень"


def _parse_maturity_scores(llm_text: str) -> dict[str, float]:
    dimensions = {"Процессы": 0.0, "Данные": 0.0, "Технологии": 0.0, "Персонал": 0.0}
    for dim in dimensions:
        match = re.search(rf"{dim}[:\s]+(\d[\.,]?\d?)\s*/\s*5", llm_text, re.IGNORECASE)
        dimensions[dim] = float(match.group(1).replace(",", ".")) if match else 2.5
    return dimensions


def _make_radar_chart(scores: dict[str, float]) -> io.BytesIO:
    labels = list(scores.keys())
    values = list(scores.values())
    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    values_c = values + [values[0]]
    angles_c = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw={"polar": True})
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    ax.plot(angles_c, values_c, color=_ACCENT_HEX, linewidth=2)
    ax.fill(angles_c, values_c, color=_ACCENT_HEX, alpha=0.25)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["1", "2", "3", "4", "5"], fontsize=7)
    ax.grid(color="gray", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_title("Цифровая зрелость", pad=15, fontsize=10, fontweight="bold", color="#1D1D1D")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_bar_chart(scores: dict[str, float]) -> io.BytesIO:
    labels = list(scores.keys())
    values = list(scores.values())

    fig, ax = plt.subplots(figsize=(5, 2.5))
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    bar_colors = [_ACCENT_HEX if v >= 3 else "#FF7043" for v in values]
    bars = ax.barh(labels, values, color=bar_colors, height=0.5)
    ax.set_xlim(0, 5)
    ax.set_xlabel("Баллов из 5", fontsize=8)
    ax.axvline(x=3, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}", va="center", fontsize=8)
    ax.set_title("Оценка по направлениям", fontsize=9, fontweight="bold", color="#1D1D1D")
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    good = mpatches.Patch(color=_ACCENT_HEX, label="≥ 3 — удовлетворительно")
    bad = mpatches.Patch(color="#FF7043", label="< 3 — требует внимания")
    ax.legend(handles=[good, bad], fontsize=7, loc="lower right")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Public API ──────────────────────────────────────────────────────────────

def generate_pdf(
    session_id: uuid.UUID,
    scenario_name: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    dialog_entries: list[dict],
    llm_response: str,
    next_step_text: str = "",
) -> str:
    """Generate a styled PDF report and return its file path."""
    reports_dir = Path(settings.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    filepath = reports_dir / f"report_{session_id}.pdf"

    usable_width = A4[0] - 3.5 * cm - 2 * cm

    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        topMargin=3 * cm,
        bottomMargin=2 * cm,
        leftMargin=3.5 * cm,
        rightMargin=2 * cm,
    )

    styles = _build_styles()
    story: list = []

    def gap() -> Spacer:
        return Spacer(1, _SECTION_GAP)

    def section_h1(title: str) -> Paragraph:
        return Paragraph(_apply_highlights(title), styles["h1"])

    # ── 1. Заголовок и клиент ───────────────────────────────────────────────
    story.append(section_h1("AI Booster"))
    story.append(Paragraph("AI-диагностика бизнес-проблемы", styles["body"]))
    story.append(Spacer(1, 6 * mm))

    client_lines = []
    if contact_name:
        client_lines.append(
            f'<font name="{_FONT_BOLD}">Клиент:</font> {html.escape(contact_name)}'
        )
    if contact_email:
        client_lines.append(
            f'<font name="{_FONT_BOLD}">Email:</font> {html.escape(contact_email)}'
        )
    if contact_phone:
        client_lines.append(
            f'<font name="{_FONT_BOLD}">Телефон:</font> {html.escape(contact_phone)}'
        )
    client_lines.append(
        f'<font name="{_FONT_BOLD}">Сценарий:</font> {html.escape(scenario_name)}'
    )
    client_lines.append(
        f'<font name="{_FONT_BOLD}">Дата:</font> '
        f'{datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")}'
    )
    for line in client_lines:
        story.append(Paragraph(line, styles["body"]))

    # ── 2. Диалог с диагностом ──────────────────────────────────────────────
    if dialog_entries:
        story.append(gap())
        story.append(section_h1("Диалог с диагностом"))
        for entry in dialog_entries:
            question = html.escape(entry.get("question", ""))
            answer = html.escape(entry.get("answer", "") or "—")
            story.append(Paragraph(
                f'<font name="{_FONT_BOLD}">Вопрос:</font> {question}',
                styles["body"],
            ))
            story.append(Paragraph(
                f'<font name="{_FONT_BOLD}">Ответ:</font> {answer}',
                styles["body"],
            ))

    # ── Parse LLM sections ──────────────────────────────────────────────────
    sections = _parse_llm_sections(llm_response)
    scores = _parse_maturity_scores(llm_response)

    # ── 3. Основная проблема ────────────────────────────────────────────────
    story.append(gap())
    story.append(section_h1("Основная проблема"))
    if "problem" in sections:
        story.extend(_section_to_flowables(sections["problem"], styles))
    else:
        story.append(Paragraph(_apply_highlights(llm_response.split("\n")[0]), styles["body"]))

    # ── 4. Уровень цифровой зрелости ────────────────────────────────────────
    story.append(gap())
    story.append(section_h1("Уровень цифровой зрелости"))
    story.append(Paragraph(_maturity_level_name(scores), styles["level_badge"]))
    if "level" in sections:
        story.extend(_section_to_flowables(sections["level"], styles))

    radar_buf = _make_radar_chart(scores)
    bar_buf = _make_bar_chart(scores)
    chart_table = Table(
        [[Image(radar_buf, width=7 * cm, height=7 * cm),
          Image(bar_buf, width=9 * cm, height=5 * cm)]],
        colWidths=[usable_width * 0.44, usable_width * 0.56],
    )
    chart_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(Spacer(1, 4 * mm))
    story.append(chart_table)

    # ── 5. Текущее состояние ────────────────────────────────────────────────
    if "state" in sections:
        story.append(gap())
        story.append(section_h1("Текущее состояние"))
        story.extend(_section_to_flowables(sections["state"], styles))

    # ── 6. Рекомендации ─────────────────────────────────────────────────────
    if "recommendations" in sections:
        story.append(gap())
        story.append(section_h1("Рекомендации"))
        story.extend(_section_to_flowables(sections["recommendations"], styles))

    # Fallback: если LLM не вернул структурированные разделы
    if not sections:
        story.append(gap())
        story.append(section_h1("AI-анализ и рекомендации"))
        for line in llm_response.split("\n"):
            line = line.strip()
            if line:
                story.append(Paragraph(_apply_highlights(line), styles["body"]))

    # ── 7. Следующий шаг (фиксированный текст из настроек) ──────────────────
    if next_step_text.strip():
        story.append(gap())
        story.append(section_h1("Следующий шаг"))
        block = _make_ai_booster_block(
            _section_to_flowables(next_step_text, styles),
            usable_width,
        )
        if block:
            story.append(block)

    # ── Подвал ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph(
        _apply_highlights("Отчёт сгенерирован AI Booster · ai-booster.ru"),
        styles["footer"],
    ))

    doc.build(story, onFirstPage=_draw_background, onLaterPages=_draw_background)
    return str(filepath)
