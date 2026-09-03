from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from typing import Any

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDate,
    QDateEdit,
    QDialog,
    QFormLayout,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)
from aqt.utils import askUser, qconnect, showInfo, tooltip

from .analytics_ui import AnalyticsDialog
from .config import get_config, write_config
from .constants import ADDON_NAME, DEFAULT_CONFIG, VERSION
from .licensing import activate_license, deactivate_license, has_pro_access, license_status, verify_license
from .purchase_ui import open_pro_dialog
from .radar import display_deck_name, recommendations
from .review import cleanup_empty_temporary_decks, start_focus_review


class MainDialog(QDialog):
    """Central hub opened from Tools → Study Radar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent or mw)
        self.setWindowTitle(f"{ADDON_NAME} — Painel")
        self.resize(520, 390)
        root = QVBoxLayout(self)

        status = license_status()
        title = QLabel(f"<h2 style='margin-bottom:2px'>🧠 Study Radar</h2><div style='opacity:.72'>v{VERSION} · {'⭐ ' if status.active else ''}{escape(status.label)}</div>")
        title.setWordWrap(True)
        root.addWidget(title)

        intro = QLabel("Acesse as funções do Study Radar em um único lugar.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        settings = QPushButton("⚙ Configurações")
        license_btn = QPushButton("⭐ Comprar / Ativar Pro")
        focus = QPushButton("⏱ Sessão Foco")
        analytics = QPushButton("📊 Analytics")
        cleanup = QPushButton("🧹 Limpar sessões vazias")
        diagnostics = QPushButton("🩺 Diagnóstico")

        for btn in (settings, license_btn, focus, analytics, cleanup, diagnostics):
            btn.setMinimumHeight(44)

        grid.addWidget(settings, 0, 0)
        grid.addWidget(license_btn, 0, 1)
        grid.addWidget(focus, 1, 0)
        grid.addWidget(analytics, 1, 1)
        grid.addWidget(cleanup, 2, 0)
        grid.addWidget(diagnostics, 2, 1)
        root.addLayout(grid)

        if not status.active:
            focus.setToolTip("Recurso Study Radar Pro")
            analytics.setToolTip("Analytics básico disponível no Free; recursos avançados no Pro")

        qconnect(settings.clicked, lambda: open_settings_dialog(0))
        qconnect(license_btn.clicked, open_pro_settings)
        qconnect(focus.clicked, open_focus_dialog)
        qconnect(analytics.clicked, open_analytics_dialog)
        qconnect(cleanup.clicked, self._cleanup)
        qconnect(diagnostics.clicked, open_diagnostics)

        root.addStretch(1)
        close = QPushButton("Fechar")
        close.setMinimumHeight(36)
        qconnect(close.clicked, self.close)
        root.addWidget(close)

    def _cleanup(self) -> None:
        removed = cleanup_empty_temporary_decks(announce=False)
        if removed:
            showInfo(
                f"{removed} sessão{'ões' if removed != 1 else ''} temporária{'s' if removed != 1 else ''} vazia{'s' if removed != 1 else ''} removida{'s' if removed != 1 else ''}.",
                title=ADDON_NAME,
            )
        else:
            showInfo("Não há sessões temporárias vazias para remover.", title=ADDON_NAME)



class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent or mw)
        self.setWindowTitle(f"{ADDON_NAME} — Configurações")
        self.resize(640, 610)
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self._build_general_tab()
        self._build_intervals_tab()
        self._build_decks_tab()
        self._build_pro_tab()
        self._build_about_tab()

        buttons = QHBoxLayout()
        reset = QPushButton("Restaurar padrões")
        cancel = QPushButton("Cancelar")
        save = QPushButton("Salvar")
        save.setDefault(True)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)
        qconnect(reset.clicked, self._load_defaults)
        qconnect(cancel.clicked, self.close)
        qconnect(save.clicked, self._save)
        self._load_current()

    def _build_general_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        box = QGroupBox("Radar"); form = QFormLayout(box)
        self.history_days = QSpinBox(); self.history_days.setRange(30, 3650); self.history_days.setSuffix(" dias")
        self.max_rows = QSpinBox(); self.max_rows.setRange(1, 50)
        self.minimum_reviews = QSpinBox(); self.minimum_reviews.setRange(1, 200); self.minimum_reviews.setSuffix(" cards")
        self.upcoming_days = QSpinBox(); self.upcoming_days.setRange(0, 90); self.upcoming_days.setSuffix(" dias")
        self.smart_cards = QSpinBox(); self.smart_cards.setRange(5, 200); self.smart_cards.setSuffix(" cards")
        self.focus_seconds = QSpinBox(); self.focus_seconds.setRange(10, 120); self.focus_seconds.setSuffix(" s/card")
        self.name_mode = QComboBox(); self.name_mode.addItem("Nome completo", "full"); self.name_mode.addItem("Últimos 2 níveis", "last2"); self.name_mode.addItem("Somente o último nível", "leaf")
        self.show_reasons = QCheckBox("Mostrar o motivo da recomendação")
        form.addRow("Histórico analisado:", self.history_days)
        form.addRow("Máximo de baralhos:", self.max_rows)
        form.addRow("Sessão válida a partir de:", self.minimum_reviews)
        form.addRow("Mostrar próximos:", self.upcoming_days)
        form.addRow("Revisão rápida:", self.smart_cards)
        form.addRow("Velocidade estimada:", self.focus_seconds)
        form.addRow("Nome dos subbaralhos:", self.name_mode)
        form.addRow("Detalhes:", self.show_reasons)
        layout.addWidget(box)

        cleanup_box = QGroupBox("Sessões temporárias")
        cleanup_layout = QVBoxLayout(cleanup_box)
        self.auto_cleanup_temp = QCheckBox("Excluir automaticamente o baralho temporário quando a sessão terminar")
        self.cleanup_on_startup = QCheckBox("Limpar sessões temporárias vazias ao abrir o Anki")
        cleanup_now = QPushButton("Limpar sessões vazias agora")
        cleanup_layout.addWidget(self.auto_cleanup_temp)
        cleanup_layout.addWidget(self.cleanup_on_startup)
        cleanup_layout.addWidget(cleanup_now)
        qconnect(cleanup_now.clicked, self._cleanup_now)
        layout.addWidget(cleanup_box); layout.addStretch(1)
        self.tabs.addTab(page, "Geral")

    def _build_intervals_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        help_label = QLabel("Intervalos-base do tema. Again/Hard encurtam a próxima recomendação automaticamente."); help_label.setWordWrap(True)
        layout.addWidget(help_label)
        preset_box = QGroupBox("Perfis rápidos"); preset_layout = QHBoxLayout(preset_box)
        for label, vals in [
            ("Intensivo", [1,2,4,7,14,21,30,45]),
            ("Equilibrado", [2,4,7,14,21,30,45,60]),
            ("Relaxado", [3,7,14,21,30,45,60,90]),
        ]:
            btn = QPushButton(label)
            qconnect(btn.clicked, lambda _=False, v=vals: self._set_intervals(v))
            preset_layout.addWidget(btn)
        layout.addWidget(preset_box)
        box = QGroupBox("Intervalos"); form = QFormLayout(box)
        self.interval_boxes: list[QSpinBox] = []
        for i in range(8):
            spin = QSpinBox(); spin.setRange(1, 730); spin.setSuffix(" dias")
            self.interval_boxes.append(spin); form.addRow(f"Após a {i+1}ª sessão:", spin)
        layout.addWidget(box); layout.addStretch(1)
        self.tabs.addTab(page, "Intervalos")

    def _build_decks_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        help_label = QLabel("Baralhos ignorados não aparecem no Radar. Você pode reativá-los a qualquer momento."); help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.ignored_list = QListWidget(); layout.addWidget(self.ignored_list)
        row = QHBoxLayout(); unignore = QPushButton("Reativar selecionado"); clear = QPushButton("Reativar todos")
        row.addWidget(unignore); row.addWidget(clear); row.addStretch(1); layout.addLayout(row)
        qconnect(unignore.clicked, self._unignore_selected); qconnect(clear.clicked, self._clear_ignored)
        self.tabs.addTab(page, "Baralhos")

    def _build_pro_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        self.pro_status = QLabel(); self.pro_status.setWordWrap(True); layout.addWidget(self.pro_status)

        license_box = QGroupBox("Study Radar Pro")
        license_layout = QVBoxLayout(license_box)
        license_text = QLabel(
            "Compre, ative, verifique ou desative sua licença na central Pro. "
            "Pagamentos aprovados pelo Mercado Pago são detectados e ativados automaticamente."
        )
        license_text.setWordWrap(True)
        manage_license = QPushButton("⭐ Abrir central Pro")
        manage_license.setMinimumHeight(38)
        qconnect(manage_license.clicked, open_pro_dialog)
        license_layout.addWidget(license_text)
        license_layout.addWidget(manage_license)
        layout.addWidget(license_box)

        exam_box = QGroupBox("Modo Prova — Pro"); exam_form = QFormLayout(exam_box)
        self.exam_enabled = QCheckBox("Antecipar revisões conforme a prova se aproxima")
        self.exam_date = QDateEdit(); self.exam_date.setCalendarPopup(True); self.exam_date.setDisplayFormat("dd/MM/yyyy")
        self.exam_intensity = QSpinBox(); self.exam_intensity.setRange(1,3)
        exam_form.addRow(self.exam_enabled); exam_form.addRow("Data da prova:", self.exam_date); exam_form.addRow("Intensidade (1–3):", self.exam_intensity)
        layout.addWidget(exam_box); layout.addStretch(1)
        self.tabs.addTab(page, "Pro")
        self._pro_controls = [self.exam_enabled, self.exam_date, self.exam_intensity]

    def _build_about_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        text = QLabel(
            f"<h3>{ADDON_NAME} v{VERSION}</h3>"
            "<p>O Radar recomenda quando revisitar cada baralho com base no histórico real de estudo. "
            "Ele não substitui o agendador do Anki.</p>"
            "<p><b>Revisão Rápida:</b> seleciona cards problemáticos. "
            "<b>Sessão Foco Pro:</b> escolhe automaticamente o que revisar pelo tempo disponível. "
            "<b>Modo Prova Pro:</b> antecipa recomendações conforme a prova se aproxima.</p>"
            "<p>As sessões inteligentes usam baralho filtrado em modo de pré-visualização, sem reagendar os cards.</p>"
        ); text.setWordWrap(True); layout.addWidget(text); layout.addStretch(1); self.tabs.addTab(page, "Sobre")

    def _set_intervals(self, vals: list[int]) -> None:
        for spin, value in zip(self.interval_boxes, vals): spin.setValue(value)

    def _load_current(self) -> None:
        self._apply(get_config())

    def _load_defaults(self) -> None:
        self._apply(dict(DEFAULT_CONFIG)); tooltip("Padrões carregados. Clique em Salvar para aplicar.")

    def _apply(self, cfg: dict[str, Any]) -> None:
        self.history_days.setValue(int(cfg.get("history_days", 730)))
        self.max_rows.setValue(int(cfg.get("max_rows", 10)))
        self.minimum_reviews.setValue(int(cfg.get("minimum_session_reviews", 10)))
        self.upcoming_days.setValue(int(cfg.get("show_upcoming_days", 7)))
        self.smart_cards.setValue(int(cfg.get("smart_review_cards", 25)))
        self.focus_seconds.setValue(int(cfg.get("focus_avg_seconds_per_card", 30)))
        idx = self.name_mode.findData(str(cfg.get("display_deck_names", "full"))); self.name_mode.setCurrentIndex(max(0, idx))
        self.show_reasons.setChecked(bool(cfg.get("show_reasons", True)))
        self.auto_cleanup_temp.setChecked(bool(cfg.get("auto_cleanup_temp_decks", True)))
        self.cleanup_on_startup.setChecked(bool(cfg.get("cleanup_temp_on_startup", True)))
        vals = cfg.get("base_intervals_days", [2,4,7,14,21,30,45,60])
        try: vals = [int(v) for v in vals]
        except Exception: vals = [2,4,7,14,21,30,45,60]
        while len(vals) < 8: vals.append(vals[-1])
        self._set_intervals(vals[:8])
        self.exam_enabled.setChecked(bool(cfg.get("exam_mode_enabled", False)))
        raw = str(cfg.get("exam_date", ""))
        try:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            d = date.today() + timedelta(days=30)
        self.exam_date.setDate(QDate(d.year, d.month, d.day)); self.exam_intensity.setValue(int(cfg.get("exam_intensity", 2)))
        self._refresh_ignored(cfg); self._refresh_pro_status()

    def _refresh_ignored(self, cfg: dict[str, Any] | None = None) -> None:
        cfg = cfg or get_config(); ignored = {int(v) for v in cfg.get("ignored_deck_ids", []) if str(v).isdigit()}
        self.ignored_list.clear()
        names = {int(i.id): str(i.name) for i in mw.col.decks.all_names_and_ids(include_filtered=False)}
        for did in sorted(ignored, key=lambda d: names.get(d, str(d)).casefold()):
            self.ignored_list.addItem(f"{did} — {display_deck_name(names.get(did, '(baralho removido)'))}")
        self.ignored_list.setProperty("ignored_ids", sorted(ignored))

    def _unignore_selected(self) -> None:
        row = self.ignored_list.currentRow()
        ids = list(self.ignored_list.property("ignored_ids") or [])
        if row < 0 or row >= len(ids): return
        target = int(ids[row]); cfg = get_config(); cfg["ignored_deck_ids"] = [int(v) for v in cfg.get("ignored_deck_ids", []) if int(v) != target]
        write_config(cfg); self._refresh_ignored(cfg)

    def _clear_ignored(self) -> None:
        cfg = get_config(); cfg["ignored_deck_ids"] = []; write_config(cfg); self._refresh_ignored(cfg)

    def _refresh_pro_status(self) -> None:
        status = license_status()
        self.pro_status.setText(f"<b>Status:</b> {'⭐ ' if status.active else ''}{status.label}<br>{escape(status.detail)}")
        for w in getattr(self, "_pro_controls", []): w.setEnabled(status.active)

    def _activate(self) -> None:
        open_pro_dialog()

    def _verify(self) -> None:
        open_pro_dialog()

    def _deactivate(self) -> None:
        open_pro_dialog()

    def _buy(self) -> None:
        open_pro_dialog()

    def _cleanup_now(self) -> None:
        removed = cleanup_empty_temporary_decks(announce=False)
        if removed:
            showInfo(f"{removed} sessão{'ões' if removed != 1 else ''} temporária{'s' if removed != 1 else ''} vazia{'s' if removed != 1 else ''} removida{'s' if removed != 1 else ''}.", title=ADDON_NAME)
        else:
            showInfo("Não há sessões temporárias vazias para remover.", title=ADDON_NAME)

    def _save(self) -> None:
        intervals = [s.value() for s in self.interval_boxes]
        if any(b < a for a,b in zip(intervals, intervals[1:])):
            showInfo("Os intervalos não podem diminuir de uma etapa para a seguinte.", title=ADDON_NAME); return
        cfg = get_config()
        cfg.update({
            "history_days": self.history_days.value(), "max_rows": self.max_rows.value(),
            "minimum_session_reviews": self.minimum_reviews.value(), "show_upcoming_days": self.upcoming_days.value(),
            "smart_review_cards": self.smart_cards.value(), "focus_avg_seconds_per_card": self.focus_seconds.value(),
            "display_deck_names": str(self.name_mode.currentData()), "show_reasons": self.show_reasons.isChecked(),
            "auto_cleanup_temp_decks": self.auto_cleanup_temp.isChecked(),
            "cleanup_temp_on_startup": self.cleanup_on_startup.isChecked(),
            "base_intervals_days": intervals,
            "exam_mode_enabled": self.exam_enabled.isChecked() if has_pro_access() else False,
            "exam_date": self.exam_date.date().toString("yyyy-MM-dd"), "exam_intensity": self.exam_intensity.value(),
        })
        write_config(cfg); tooltip("Configurações salvas")
        try:
            if getattr(mw, "state", "") == "deckBrowser": mw.deckBrowser.refresh()
        except Exception: pass
        self.close()


def open_main_dialog() -> None:
    existing = getattr(mw, "_study_radar_main", None)
    try:
        if existing and existing.isVisible():
            existing.raise_(); existing.activateWindow(); return
    except Exception:
        pass
    dlg = MainDialog(); mw._study_radar_main = dlg
    dlg.show(); dlg.raise_(); dlg.activateWindow()


def open_diagnostics() -> None:
    try:
        cfg = get_config()
        status = license_status()
        recs = recommendations(include_hidden=True)
        try:
            from anki.decks import FilteredDeckConfig  # noqa: F401
            from aqt.operations.scheduling import add_or_update_filtered_deck  # noqa: F401
            filtered_api = "OK"
        except Exception as exc:
            filtered_api = f"INDISPONÍVEL: {exc}"
        text = (
            f"Study Radar {VERSION}\n"
            f"Licença: {status.role} ({'ativa' if status.active else 'inativa'})\n"
            f"Baralhos analisados: {len(recs)}\n"
            f"Histórico: {cfg.get('history_days')} dias\n"
            f"API de baralho filtrado: {filtered_api}\n"
            f"Estado do Anki: {getattr(mw, 'state', 'desconhecido')}"
        )
        showInfo(text, title="Study Radar — Diagnóstico")
    except Exception as exc:
        showInfo(f"Falha no diagnóstico: {exc}", title=ADDON_NAME)



def open_settings_dialog(tab_index: int = 0) -> None:
    existing = getattr(mw, "_study_radar_settings", None)
    try:
        if existing and existing.isVisible():
            try: existing.tabs.setCurrentIndex(tab_index)
            except Exception: pass
            existing.raise_(); existing.activateWindow(); return
    except Exception: pass
    dlg = SettingsDialog(); mw._study_radar_settings = dlg
    try: dlg.tabs.setCurrentIndex(tab_index)
    except Exception: pass
    dlg.show(); dlg.raise_(); dlg.activateWindow()


def open_analytics_dialog() -> None:
    dlg = AnalyticsDialog(); mw._study_radar_analytics = dlg; dlg.show(); dlg.raise_(); dlg.activateWindow()


def open_focus_dialog() -> None:
    if not has_pro_access(): showInfo("Sessão Foco é um recurso Study Radar Pro.", title=ADDON_NAME); return
    minutes, ok = QInputDialog.getInt(mw, "Study Radar Pro — Sessão Foco", "Quanto tempo você tem para estudar?", 30, 10, 180, 5)
    if ok: start_focus_review(minutes)


def snooze_deck(deck_id: int) -> None:
    options = ["Amanhã", "3 dias", "7 dias"]
    choice, ok = QInputDialog.getItem(mw, "Adiar recomendação", "Quando este baralho deve voltar ao Radar?", options, 0, False)
    if not ok: return
    days = {"Amanhã": 1, "3 dias": 3, "7 dias": 7}[choice]
    cfg = get_config(); data = dict(cfg.get("snoozed_until", {}) or {}); data[str(deck_id)] = (date.today()+timedelta(days=days)).isoformat(); cfg["snoozed_until"] = data; write_config(cfg)
    tooltip(f"Baralho adiado por {days} dia{'s' if days != 1 else ''}"); _refresh_deck_browser()


def ignore_deck(deck_id: int) -> None:
    name = mw.col.decks.name_if_exists(deck_id) or "este baralho"
    if not askUser(f"Ignorar {display_deck_name(name)} no Study Radar?", title=ADDON_NAME): return
    cfg = get_config(); ignored = {int(v) for v in cfg.get("ignored_deck_ids", []) if str(v).isdigit()}; ignored.add(deck_id); cfg["ignored_deck_ids"] = sorted(ignored); write_config(cfg); tooltip("Baralho ignorado"); _refresh_deck_browser()


def _refresh_deck_browser() -> None:
    try:
        if getattr(mw, "state", "") == "deckBrowser": mw.deckBrowser.refresh()
    except Exception: pass


def open_pro_settings() -> None:
    open_pro_dialog()
