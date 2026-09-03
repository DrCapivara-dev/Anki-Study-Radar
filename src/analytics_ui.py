from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
from typing import Iterable

from aqt import mw
from aqt.qt import (
    QColor,
    QDialog,
    QFont,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPainter,
    QPalette,
    QPen,
    QPointF,
    QPolygonF,
    QPixmap,
    QPushButton,
    QRectF,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    Qt,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import qconnect, tooltip

from .analytics import AnalyticsSnapshot, DailyActivity, build_snapshot
from .config import get_config
from .constants import ADDON_NAME
from .licensing import has_pro_access
from .radar import Recommendation, display_deck_name
from .review import start_focus_review, start_smart_review


def _text_color(widget: QWidget) -> QColor:
    return widget.palette().color(QPalette.ColorRole.Text)


def _muted_color(widget: QWidget) -> QColor:
    try:
        return widget.palette().color(QPalette.ColorRole.PlaceholderText)
    except Exception:
        c = _text_color(widget)
        c.setAlpha(150)
        return c


def _track_color(widget: QWidget) -> QColor:
    c = widget.palette().color(QPalette.ColorRole.Mid)
    c.setAlpha(90)
    return c


def _priority_color(value: int) -> QColor:
    if value >= 90:
        return QColor("#ef5350")
    if value >= 75:
        return QColor("#ff9800")
    if value >= 55:
        return QColor("#f1c40f")
    return QColor("#43a047")


def _short(label: str, max_chars: int = 34) -> str:
    if len(label) <= max_chars:
        return label
    return label[: max_chars - 1].rstrip() + "…"


class HorizontalBarChart(QWidget):
    def __init__(self, data: Iterable[tuple[str, int]], *, max_value: int | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.data = list(data)
        self.max_value = max_value
        self.setMinimumHeight(max(210, 42 + 34 * len(self.data)))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        left = min(245, max(150, int(w * 0.38)))
        right = 42
        top = 18
        row_h = max(28, int((h - top - 14) / max(1, len(self.data))))
        bar_x = left
        bar_w = max(40, w - left - right)
        maxv = self.max_value or max([v for _l, v in self.data] + [1])
        text = _text_color(self)
        muted = _muted_color(self)
        track = _track_color(self)
        fm = p.fontMetrics()
        for i, (label, value) in enumerate(self.data):
            y = top + i * row_h
            label_rect = QRectF(4, y, left - 14, row_h - 4)
            p.setPen(text)
            p.drawText(label_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), fm.elidedText(label, Qt.TextElideMode.ElideRight, int(label_rect.width())))
            track_rect = QRectF(bar_x, y + 7, bar_w, max(10, row_h - 18))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(track)
            p.drawRoundedRect(track_rect, 5, 5)
            ratio = 0.0 if maxv <= 0 else max(0.0, min(1.0, float(value) / float(maxv)))
            fill = QRectF(track_rect.x(), track_rect.y(), max(3.0 if value > 0 else 0.0, track_rect.width() * ratio), track_rect.height())
            p.setBrush(_priority_color(int(round(value * 100 / maxv))) if self.max_value is None else _priority_color(value))
            p.drawRoundedRect(fill, 5, 5)
            p.setPen(muted)
            p.drawText(QRectF(w - right + 4, y, right - 4, row_h - 4), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), str(value))


class ForecastChart(QWidget):
    def __init__(self, data: list[tuple[str, int]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.data = data
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        left, right, top, bottom = 34, 12, 24, 46
        plot_w = max(1, w - left - right)
        plot_h = max(1, h - top - bottom)
        maxv = max([v for _l, v in self.data] + [1])
        text, muted, track = _text_color(self), _muted_color(self), _track_color(self)
        p.setPen(QPen(track, 1))
        p.drawLine(QPointF(float(left), float(top + plot_h)), QPointF(float(left + plot_w), float(top + plot_h)))
        n = max(1, len(self.data))
        slot = plot_w / n
        bar_w = min(52.0, slot * 0.62)
        for i, (label, value) in enumerate(self.data):
            x = left + i * slot + (slot - bar_w) / 2
            bh = 0.0 if maxv <= 0 else plot_h * value / maxv
            rect = QRectF(x, top + plot_h - bh, bar_w, bh)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_priority_color(100 if value == maxv and value > 0 else 60))
            if value > 0:
                p.drawRoundedRect(rect, 5, 5)
            p.setPen(text)
            p.drawText(QRectF(x - 10, max(0.0, rect.y() - 23), bar_w + 20, 20), int(Qt.AlignmentFlag.AlignCenter), str(value))
            p.setPen(muted)
            p.drawText(QRectF(left + i * slot, top + plot_h + 8, slot, 24), int(Qt.AlignmentFlag.AlignCenter), label)


class DonutChart(QWidget):
    COLORS = [QColor("#ef5350"), QColor("#ff9800"), QColor("#43a047"), QColor("#42a5f5")]

    def __init__(self, counts: dict[str, int], retention: float | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.counts = counts
        self.retention = retention
        self.setMinimumHeight(270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        total = sum(self.counts.values())
        diameter = min(180, h - 48, int(w * 0.45))
        rect = QRectF(24, (h - diameter) / 2, diameter, diameter)
        if total > 0:
            start = 90 * 16
            for color, key in zip(self.COLORS, ["Again", "Hard", "Good", "Easy"]):
                value = int(self.counts.get(key, 0))
                span = -round(360 * 16 * value / total)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)
                p.drawPie(rect, start, span)
                start += span
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_track_color(self))
            p.drawEllipse(rect)
        hole = QRectF(rect.x() + diameter * 0.25, rect.y() + diameter * 0.25, diameter * 0.5, diameter * 0.5)
        p.setBrush(self.palette().color(QPalette.ColorRole.Window))
        p.drawEllipse(hole)
        p.setPen(_text_color(self))
        center = "—" if self.retention is None else f"{round(self.retention * 100)}%"
        font = QFont(p.font()); font.setPointSize(max(14, font.pointSize() + 5)); font.setBold(True); p.setFont(font)
        p.drawText(hole, int(Qt.AlignmentFlag.AlignCenter), center)
        font.setPointSize(max(8, font.pointSize() - 7)); font.setBold(False); p.setFont(font)
        p.setPen(_muted_color(self))
        p.drawText(QRectF(hole.x() - 20, hole.center().y() + 18, hole.width() + 40, 20), int(Qt.AlignmentFlag.AlignCenter), "sem Again")

        legend_x = rect.right() + 36
        legend_y = max(32, (h - 4 * 44) / 2)
        p.setFont(self.font())
        for i, key in enumerate(["Again", "Hard", "Good", "Easy"]):
            y = legend_y + i * 44
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.COLORS[i]); p.drawEllipse(QRectF(legend_x, y + 5, 12, 12))
            p.setPen(_text_color(self)); p.drawText(QRectF(legend_x + 22, y, max(40, w - legend_x - 80), 24), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), key)
            value = int(self.counts.get(key, 0)); pct = (100 * value / total) if total else 0.0
            p.setPen(_muted_color(self)); p.drawText(QRectF(w - 92, y, 76, 24), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), f"{pct:.0f}%")


class RetentionTrendChart(QWidget):
    def __init__(self, data: list[tuple[str, float | None]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.data = data
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        left, right, top, bottom = 46, 18, 28, 44
        plot = QRectF(left, top, max(1, w - left - right), max(1, h - top - bottom))
        muted = _muted_color(self)
        p.setPen(QPen(_track_color(self), 1))
        for pct in [60, 70, 80, 90, 100]:
            y = plot.bottom() - (pct - 50) / 50 * plot.height()
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(muted)
            p.drawText(QRectF(0, y - 10, left - 8, 20), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), f"{pct}%")
            p.setPen(QPen(_track_color(self), 1))
        points: list[QPointF] = []
        n = max(1, len(self.data))
        for i, (label, value) in enumerate(self.data):
            x = plot.left() + (plot.width() * i / max(1, n - 1))
            p.setPen(muted)
            p.drawText(QRectF(x - 40, plot.bottom() + 8, 80, 22), int(Qt.AlignmentFlag.AlignCenter), label)
            if value is None:
                continue
            pct = max(0.5, min(1.0, value))
            y = plot.bottom() - ((pct * 100 - 50) / 50) * plot.height()
            points.append(QPointF(x, y))
        if len(points) >= 2:
            p.setPen(QPen(QColor("#6c7cff"), 3))
            p.drawPolyline(QPolygonF(points))
        for pt in points:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#8b9aff")); p.drawEllipse(pt, 5, 5)


class ActivityChart(QWidget):
    def __init__(self, data: list[DailyActivity], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.data = data[-14:]
        self.setMinimumHeight(235)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height(); left, right, top, bottom = 30, 12, 22, 40
        plot_h = h - top - bottom; plot_w = w - left - right
        maxv = max([d.reviews for d in self.data] + [1]); n = max(1, len(self.data)); slot = plot_w / n; bar_w = max(5.0, min(22.0, slot * .58))
        p.setPen(QPen(_track_color(self), 1)); p.drawLine(QPointF(float(left), float(top + plot_h)), QPointF(float(left + plot_w), float(top + plot_h)))
        for i, d in enumerate(self.data):
            bh = plot_h * d.reviews / maxv; x = left + i * slot + (slot - bar_w) / 2
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#6c7cff")); p.drawRoundedRect(QRectF(x, top + plot_h - bh, bar_w, bh), 4, 4)
            if i % 2 == 0 or i == len(self.data) - 1:
                p.setPen(_muted_color(self)); p.drawText(QRectF(left + i * slot - 10, top + plot_h + 7, slot + 20, 22), int(Qt.AlignmentFlag.AlignCenter), d.day.strftime("%d/%m"))


class AnalyticsDialog(QDialog):
    def __init__(self) -> None:
        super().__init__(mw)
        self.pro_active = has_pro_access()
        self.setWindowTitle("Study Radar Pro — Analytics" if self.pro_active else "Study Radar — Analytics")
        self.resize(1180, 780)
        self.setMinimumSize(960, 650)
        self.snapshot = build_snapshot()
        self.setStyleSheet(
            """
            QFrame#srMetricCard, QFrame#srInsightCard, QFrame#srUpgradeCard {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 10px;
            }
            QFrame#srUpgradeCard {
                border: 1px solid rgba(210,160,40,.55);
            }
            QGroupBox {
                border: 1px solid palette(mid);
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: 600;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QTableWidget { border: 1px solid palette(mid); border-radius: 8px; gridline-color: palette(mid); }
            QHeaderView::section { padding: 7px; border: 0; border-bottom: 1px solid palette(mid); }
            QPushButton { min-height: 30px; padding: 3px 10px; }
            QPushButton#srProButton {
                font-weight: 700;
                min-height: 36px;
                padding: 5px 14px;
                border: 1px solid rgba(220,170,40,.75);
            }
            """
        )
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        badge = "<span style='font-size:11px;background:#6b4b00;color:#ffd66b;padding:3px 7px;border-radius:8px'>Pro</span>" if self.pro_active else "<span style='font-size:11px;background:#284665;color:#bcdcff;padding:3px 7px;border-radius:8px'>Free</span>"
        title = QLabel(f"<span style='font-size:22px;font-weight:700'>📊 Analytics</span>&nbsp;&nbsp;{badge}")
        subtitle_text = "Transformando seu histórico em decisões de estudo." if self.pro_active else "Uma visão rápida do seu ritmo de revisão."
        subtitle = QLabel(subtitle_text)
        subtitle.setStyleSheet("opacity:.7")
        title_col.addWidget(title); title_col.addWidget(subtitle)
        header.addLayout(title_col); header.addStretch(1)
        if not self.pro_active:
            activate = QPushButton("⭐ Ativar Pro")
            activate.setObjectName("srProButton")
            qconnect(activate.clicked, self._open_pro_activation)
            header.addWidget(activate)
        refresh = QPushButton("↻ Atualizar")
        qconnect(refresh.clicked, self._reload)
        header.addWidget(refresh)
        root.addLayout(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        if self.pro_active:
            self._build_overview()
            self._build_performance()
            self._build_decks()
            self._build_insights()
        else:
            self._build_free_overview()

        close = QPushButton("Fechar")
        qconnect(close.clicked, self.close)
        root.addWidget(close)

    def _open_pro_activation(self) -> None:
        # Local import avoids a module import cycle with ui.py.
        try:
            from .ui import open_pro_settings
            open_pro_settings()
        except Exception:
            pass

    def _build_free_overview(self) -> None:
        s = self.snapshot
        scroll, page, layout = self._scroll_page()

        metrics = QGridLayout(); metrics.setHorizontalSpacing(10); metrics.setVerticalSpacing(10)
        retention = "—" if s.retention_30d is None else f"{round(s.retention_30d*100)}%"
        free_cards = [
            ("TEMAS ACOMPANHADOS", str(s.tracked_topics), "com sessões válidas"),
            ("EM ATENÇÃO", str(s.attention_topics), "precisam de revisão"),
            ("RETENÇÃO APROX. 30D", retention, "visão geral"),
            ("CARGA EM 7 DIAS", str(s.due_total_7d), "cards já agendados"),
        ]
        for i, data in enumerate(free_cards):
            metrics.addWidget(self._metric_card(*data), 0, i)
        layout.addLayout(metrics)

        charts = QGridLayout(); charts.setHorizontalSpacing(12); charts.setVerticalSpacing(12)
        priority_data = [(display_deck_name(r.deck_name), r.priority) for r in sorted(s.recs, key=lambda r: -r.priority)[:5]]
        charts.addWidget(self._chart_box("Onde focar", HorizontalBarChart(priority_data, max_value=100), "Seus temas com maior prioridade agora."), 0, 0)
        charts.addWidget(self._chart_box("Carga futura — 7 dias", ForecastChart(s.due_7d), "Quantidade de cards já agendados."), 0, 1)
        charts.setColumnStretch(0, 1); charts.setColumnStretch(1, 1)
        layout.addLayout(charts)

        upgrade = QFrame(); upgrade.setObjectName("srUpgradeCard")
        up = QGridLayout(upgrade); up.setContentsMargins(18, 16, 18, 16); up.setHorizontalSpacing(18); up.setVerticalSpacing(10)
        copy = QVBoxLayout()
        title = QLabel("<span style='font-size:18px;font-weight:750'>🔒 Desbloqueie o Analytics Pro</span>")
        copy.addWidget(title)
        desc = QLabel("Mais gráficos, tendências, previsões e recomendações personalizadas a partir do seu histórico.")
        desc.setWordWrap(True); desc.setStyleSheet("opacity:.78")
        copy.addWidget(desc)
        locked = QLabel("🔒 Desempenho e retenção semanal<br>🔒 Baralhos detalhados e pontos fracos<br>🔒 Insights e plano sugerido de estudo<br>🔒 Tendências, streak e consolidação da memória")
        locked.setTextFormat(Qt.TextFormat.RichText); locked.setStyleSheet("opacity:.80; line-height:1.45")
        copy.addWidget(locked)
        activate = QPushButton("⭐ Ativar Pro")
        activate.setObjectName("srProButton"); activate.setMaximumWidth(190)
        qconnect(activate.clicked, self._open_pro_activation)
        copy.addWidget(activate, 0, Qt.AlignmentFlag.AlignLeft)
        copy.addStretch(1)
        up.addLayout(copy, 0, 0)

        preview_box = QVBoxLayout()
        preview_title = QLabel("<b>Prévia do Analytics Pro</b>")
        preview_title.setStyleSheet("opacity:.82")
        preview_box.addWidget(preview_title)
        preview = QLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumSize(360, 245)
        preview.setStyleSheet("background:rgba(0,0,0,.14);border:1px solid palette(mid);border-radius:8px;padding:6px")
        path = Path(__file__).resolve().parent / "assets" / "analytics_pro_preview.png"
        pix = QPixmap(str(path))
        if not pix.isNull():
            pix = pix.scaled(470, 360, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            preview.setPixmap(pix)
        else:
            preview.setText("Prévia do dashboard Pro")
        preview_box.addWidget(preview)
        up.addLayout(preview_box, 0, 1)
        up.setColumnStretch(0, 3); up.setColumnStretch(1, 4)
        layout.addWidget(upgrade)

        foot = QLabel("O Analytics Grátis oferece o essencial. Ative o Pro para desbloquear o dashboard completo e os insights avançados.")
        foot.setWordWrap(True); foot.setStyleSheet("opacity:.58; font-size:10px")
        layout.addWidget(foot)
        layout.addStretch(1)
        self.tabs.addTab(scroll, "Visão geral")

    def _scroll_page(self) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        page = QWidget(); layout = QVBoxLayout(page); layout.setSpacing(12); layout.setContentsMargins(12, 12, 12, 12)
        scroll.setWidget(page)
        return scroll, page, layout

    def _metric_card(self, title: str, value: str, detail: str = "") -> QFrame:
        card = QFrame(); card.setObjectName("srMetricCard"); card.setMinimumHeight(92)
        lay = QVBoxLayout(card); lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(3)
        t = QLabel(title); t.setStyleSheet("font-size:11px; opacity:.68")
        v = QLabel(value); v.setStyleSheet("font-size:22px; font-weight:700")
        d = QLabel(detail); d.setStyleSheet("font-size:10px; opacity:.62"); d.setWordWrap(True)
        lay.addWidget(t); lay.addWidget(v); lay.addWidget(d); lay.addStretch(1)
        return card

    def _chart_box(self, title: str, widget: QWidget, subtitle: str = "") -> QGroupBox:
        box = QGroupBox(title); lay = QVBoxLayout(box)
        if subtitle:
            lab = QLabel(subtitle); lab.setWordWrap(True); lab.setStyleSheet("opacity:.64; font-size:10px"); lay.addWidget(lab)
        lay.addWidget(widget)
        return box

    def _build_overview(self) -> None:
        s = self.snapshot
        scroll, page, layout = self._scroll_page()
        metrics = QGridLayout(); metrics.setHorizontalSpacing(10); metrics.setVerticalSpacing(10)
        retention = "—" if s.retention_30d is None else f"{round(s.retention_30d*100)}%"
        trend_detail = "30 dias"
        if s.trend_7d is not None:
            sign = "+" if s.trend_7d >= 0 else ""
            trend_detail = f"{sign}{s.trend_7d*100:.1f} pp vs. semana anterior"
        cards = [
            ("TEMAS ACOMPANHADOS", str(s.tracked_topics), "com sessões válidas"),
            ("PRECISAM DE ATENÇÃO", str(s.attention_topics), "atrasados ou prioridade ≥80"),
            ("RETENÇÃO APROX. 30D", retention, trend_detail),
            ("SEQUÊNCIA ATIVA", f"{s.current_streak} dia{'s' if s.current_streak != 1 else ''}", f"{s.active_days_30d}/30 dias ativos"),
            ("REVISÕES PRÓX. 7D", str(s.due_total_7d), "cards já agendados"),
            ("CARGA ESTIMADA", f"{s.estimated_minutes_7d} min", "com sua velocidade configurada"),
        ]
        for i, data in enumerate(cards): metrics.addWidget(self._metric_card(*data), i // 3, i % 3)
        layout.addLayout(metrics)

        chart_grid = QGridLayout(); chart_grid.setHorizontalSpacing(12); chart_grid.setVerticalSpacing(12)
        priority_data = [(display_deck_name(r.deck_name), r.priority) for r in sorted(s.recs, key=lambda r: -r.priority)[:7]]
        priority_chart = HorizontalBarChart(priority_data, max_value=100)
        forecast_chart = ForecastChart(s.due_7d)
        chart_grid.addWidget(self._chart_box("Onde focar", priority_chart, "Temas com maior prioridade no Radar."), 0, 0)
        chart_grid.addWidget(self._chart_box("Carga futura — 7 dias", forecast_chart, "Quantidade de cards de revisão já agendados."), 0, 1)
        activity = ActivityChart(s.activity_35d)
        chart_grid.addWidget(self._chart_box("Atividade recente — 14 dias", activity, "Quantidade de respostas por dia."), 1, 0, 1, 2)
        chart_grid.setColumnStretch(0, 1); chart_grid.setColumnStretch(1, 1)
        layout.addLayout(chart_grid); layout.addStretch(1)
        self.tabs.addTab(scroll, "Visão geral")

    def _build_performance(self) -> None:
        s = self.snapshot
        scroll, page, layout = self._scroll_page()
        grid = QGridLayout(); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(12)
        grid.addWidget(self._chart_box("Respostas — 30 dias", DonutChart(s.answer_counts_30d, s.retention_30d), "Distribuição de Again / Hard / Good / Easy."), 0, 0)
        grid.addWidget(self._chart_box("Retenção semanal", RetentionTrendChart(s.weekly_retention), "Percentual de respostas que não foram Again."), 0, 1)
        interval_chart = HorizontalBarChart(s.interval_buckets)
        card_chart = HorizontalBarChart(s.card_types)
        grid.addWidget(self._chart_box("Consolidação da memória", interval_chart, f"Intervalo médio: {s.average_interval_days:.1f}d · maior: {s.longest_interval_days}d"), 1, 0)
        grid.addWidget(self._chart_box("Tipos de cards", card_chart, "Visão geral do estado atual da coleção."), 1, 1)
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        layout.addLayout(grid); layout.addStretch(1)
        self.tabs.addTab(scroll, "Desempenho")

    def _build_decks(self) -> None:
        s = self.snapshot
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(10, 10, 10, 10)
        info = QLabel("Detalhamento por tema. Clique no cabeçalho para organizar visualmente os dados.")
        info.setStyleSheet("opacity:.65"); layout.addWidget(info)
        recs = sorted(s.all_recs, key=lambda r: (-r.priority, r.days_until, r.deck_name.casefold()))
        table = QTableWidget(len(recs), 9)
        table.setAlternatingRowColors(True); table.setSortingEnabled(False)
        table.setHorizontalHeaderLabels(["Baralho", "Prioridade", "Situação", "Última sessão", "Again", "Hard", "Sessões", "Intervalo", "Motivo"])
        for row, rec in enumerate(recs):
            situation = "Hoje" if rec.days_until == 0 else (f"{abs(rec.days_until)}d atrasado" if rec.days_until < 0 else f"em {rec.days_until}d")
            vals = [
                display_deck_name(rec.deck_name), str(rec.priority), situation, f"{rec.days_since}d atrás",
                f"{round(rec.last_session.again_rate*100)}%", f"{round(rec.last_session.hard_rate*100)}%",
                str(rec.meaningful_sessions), f"{rec.interval_days}d", rec.reason,
            ]
            for col, value in enumerate(vals): table.setItem(row, col, QTableWidgetItem(value))
        header = table.horizontalHeader()
        try:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for col in range(1, 8): header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        except Exception:
            table.resizeColumnsToContents()
        table.setSortingEnabled(True)
        layout.addWidget(table, 1)
        self.tabs.addTab(page, "Baralhos")

    def _insight_card(self, title: str, body: str, button_text: str | None = None, callback=None) -> QFrame:
        frame = QFrame(); frame.setObjectName("srInsightCard")
        lay = QVBoxLayout(frame); lay.setContentsMargins(16, 13, 16, 13)
        t = QLabel(f"<b>{escape(title)}</b>"); t.setStyleSheet("font-size:14px"); lay.addWidget(t)
        b = QLabel(body); b.setWordWrap(True); b.setTextFormat(Qt.TextFormat.RichText); b.setStyleSheet("opacity:.84"); lay.addWidget(b)
        if button_text and callback:
            btn = QPushButton(button_text); btn.setMaximumWidth(220); qconnect(btn.clicked, callback); lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft)
        return frame

    def _build_insights(self) -> None:
        s = self.snapshot
        scroll, page, layout = self._scroll_page()
        recs = sorted(s.recs, key=lambda r: (-r.priority, r.days_until, r.deck_name.casefold()))
        if recs:
            top = recs[0]
            body = (
                f"Seu principal ponto de atenção é <b>{escape(display_deck_name(top.deck_name))}</b>. "
                f"Prioridade <b>{top.priority}/100</b> · {escape(top.reason)}."
            )
            layout.addWidget(self._insight_card("🎯 Melhor próximo passo", body, "⚡ Revisar agora", lambda _=False, did=top.deck_id: start_smart_review(did)))
        else:
            layout.addWidget(self._insight_card("🎯 Melhor próximo passo", "Não há temas ativos com sessão válida suficiente para gerar uma recomendação."))

        if recs:
            cfg = get_config(); base_cards = max(5, int(cfg.get("smart_review_cards", 25)))
            lines: list[str] = []
            for i, rec in enumerate(recs[:3], start=1):
                suggested = max(10, round(base_cards * max(0.55, rec.priority / 100)))
                lines.append(f"<b>{i}.</b> {escape(display_deck_name(rec.deck_name))} — ~{suggested} cards · prioridade {rec.priority}/100")
            layout.addWidget(self._insight_card("🧠 Plano sugerido para hoje", "<br>".join(lines)))

        if s.due_7d:
            peak_label, peak_count = max(s.due_7d, key=lambda x: x[1])
            if peak_count > 0:
                load_body = f"O maior pico previsto é <b>{escape(peak_label)}</b>, com aproximadamente <b>{peak_count} cards</b> já agendados."
            else:
                load_body = "Não há uma carga relevante de cards de revisão agendada para os próximos 7 dias."
            layout.addWidget(self._insight_card("📅 Carga de revisão", load_body))

        if s.trend_7d is None:
            trend_body = "Ainda não há respostas suficientes nas duas últimas semanas para calcular uma tendência confiável."
        elif s.trend_7d >= 0.03:
            trend_body = f"Sua retenção aproximada melhorou <b>{s.trend_7d*100:.1f} pontos percentuais</b> em relação à semana anterior."
        elif s.trend_7d <= -0.03:
            trend_body = f"Sua retenção aproximada caiu <b>{abs(s.trend_7d)*100:.1f} pontos percentuais</b>. Vale reduzir a carga de novos cards e reforçar os temas mais fracos."
        else:
            trend_body = "Seu desempenho está relativamente estável em relação à semana anterior."
        layout.addWidget(self._insight_card("📈 Tendência", trend_body))

        weak = [r for r in recs if r.last_session.again_rate >= .10 or r.last_session.hard_rate >= .15 or r.days_until < 0][:5]
        if weak:
            weak_lines = [
                f"• <b>{escape(display_deck_name(r.deck_name))}</b> — Again {round(r.last_session.again_rate*100)}% · Hard {round(r.last_session.hard_rate*100)}% · {escape(r.reason)}"
                for r in weak
            ]
            layout.addWidget(self._insight_card("⚠ Pontos fracos", "<br>".join(weak_lines)))

        focus_body = f"Com a velocidade configurada, os próximos 7 dias representam cerca de <b>{s.estimated_minutes_7d} minutos</b> de revisões já agendadas."
        layout.addWidget(self._insight_card("⏱ Sessão Foco", focus_body, "Criar Sessão Foco de 30 min", lambda _=False: start_focus_review(30)))
        layout.addStretch(1)
        self.tabs.addTab(scroll, "Insights")

    def _reload(self) -> None:
        # Recreating the dialog is safer than trying to mutate every chart/table in place.
        try:
            self.close()
            dlg = AnalyticsDialog(); mw._study_radar_analytics = dlg; dlg.show(); dlg.raise_(); dlg.activateWindow()
            tooltip("Analytics atualizado")
        except Exception:
            pass
