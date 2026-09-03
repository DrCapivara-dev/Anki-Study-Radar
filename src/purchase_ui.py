from __future__ import annotations

from concurrent.futures import Future
from html import escape
import webbrowser
from typing import Any, Callable

from aqt import mw
from aqt.qt import (
    QApplication,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import askUser, qconnect, showInfo, tooltip

from .constants import ADDON_NAME
from .licensing import (
    account_status,
    activate_account_device,
    activate_checkout_license,
    activate_license,
    change_account_password,
    check_checkout_status,
    checkout_state,
    clear_pending_checkout,
    create_checkout,
    deactivate_license,
    fetch_license_key,
    has_pro_access,
    license_status,
    login_account,
    logout_account,
    refresh_account,
    register_account,
    verify_license,
)


class ProDialog(QDialog):
    """Study Radar account, purchase and activation center."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent or mw)
        self.setWindowTitle("Study Radar — Conta e Pro")
        self.resize(620, 650)
        self._busy = False
        self._closing = False
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(5000)
        qconnect(self._poll_timer.timeout, self._check_purchase)

        root = QVBoxLayout(self)
        title = QLabel("<span style='font-size:23px;font-weight:750'>🧠 Study Radar</span>")
        subtitle = QLabel("Sua conta, assinatura Lifetime e dispositivo em um único lugar.")
        subtitle.setWordWrap(True); subtitle.setStyleSheet("opacity:.72")
        root.addWidget(title); root.addWidget(subtitle)

        self.status_card = QGroupBox("Status")
        status_layout = QVBoxLayout(self.status_card)
        self.status_label = QLabel(); self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        root.addWidget(self.status_card)

        # Login / register / legacy key
        self.auth_tabs = QTabWidget()
        login_page = QWidget(); login_form = QFormLayout(login_page)
        self.login_email = QLineEdit(); self.login_email.setPlaceholderText("voce@email.com")
        self.login_password = QLineEdit(); self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_btn = QPushButton("Entrar")
        login_form.addRow("E-mail:", self.login_email); login_form.addRow("Senha:", self.login_password); login_form.addRow(self.login_btn)
        qconnect(self.login_btn.clicked, self._login)
        self.auth_tabs.addTab(login_page, "Entrar")

        register_page = QWidget(); register_form = QFormLayout(register_page)
        self.register_email = QLineEdit(); self.register_email.setPlaceholderText("voce@email.com")
        self.register_password = QLineEdit(); self.register_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.register_password2 = QLineEdit(); self.register_password2.setEchoMode(QLineEdit.EchoMode.Password)
        self.register_btn = QPushButton("Criar conta")
        register_form.addRow("E-mail:", self.register_email)
        register_form.addRow("Senha (mín. 8):", self.register_password)
        register_form.addRow("Confirmar senha:", self.register_password2)
        register_form.addRow(self.register_btn)
        qconnect(self.register_btn.clicked, self._register)
        self.auth_tabs.addTab(register_page, "Criar conta")

        key_page = QWidget(); key_form = QFormLayout(key_page)
        self.key_input = QLineEdit(); self.key_input.setPlaceholderText("SR-PRO-... / OWNER")
        self.activate_key_btn = QPushButton("Ativar chave manualmente")
        key_note = QLabel("Compatibilidade com chaves antigas e com a chave OWNER. Novas compras usam conta e senha.")
        key_note.setWordWrap(True); key_note.setStyleSheet("opacity:.68")
        key_form.addRow(key_note); key_form.addRow("Chave:", self.key_input); key_form.addRow(self.activate_key_btn)
        qconnect(self.activate_key_btn.clicked, self._activate_manual)
        self.auth_tabs.addTab(key_page, "Tenho uma chave")
        root.addWidget(self.auth_tabs)

        # Logged account card
        self.account_box = QGroupBox("Minha conta")
        account_layout = QVBoxLayout(self.account_box)
        self.account_label = QLabel(); self.account_label.setWordWrap(True)
        account_layout.addWidget(self.account_label)
        account_actions = QHBoxLayout()
        self.refresh_account_btn = QPushButton("↻ Atualizar")
        self.change_password_btn = QPushButton("Alterar senha")
        self.logout_btn = QPushButton("Sair da conta")
        account_actions.addWidget(self.refresh_account_btn); account_actions.addWidget(self.change_password_btn); account_actions.addWidget(self.logout_btn)
        account_layout.addLayout(account_actions)
        qconnect(self.refresh_account_btn.clicked, self._refresh_account)
        qconnect(self.change_password_btn.clicked, self._change_password)
        qconnect(self.logout_btn.clicked, self._logout)
        root.addWidget(self.account_box)

        # Existing Pro, not yet on this PC
        self.device_box = QGroupBox("Ativar neste computador")
        device_layout = QVBoxLayout(self.device_box)
        self.device_text = QLabel("Sua conta possui o Pro, mas este computador ainda não está ativado. O plano permite 1 dispositivo por vez.")
        self.device_text.setWordWrap(True)
        self.activate_device_btn = QPushButton("⭐ Ativar Pro neste PC")
        device_layout.addWidget(self.device_text); device_layout.addWidget(self.activate_device_btn)
        qconnect(self.activate_device_btn.clicked, self._activate_device)
        root.addWidget(self.device_box)

        # Purchase card
        self.purchase_box = QGroupBox("Comprar Study Radar Pro")
        purchase_layout = QVBoxLayout(self.purchase_box)
        pitch = QLabel(
            "<b>Lifetime — R$ 20,00</b> · 1 dispositivo. A compra fica vinculada à conta conectada. "
            "Após a aprovação do Mercado Pago, o Pro é ativado automaticamente neste PC."
        )
        pitch.setWordWrap(True); purchase_layout.addWidget(pitch)
        self.purchase_progress = QLabel(""); self.purchase_progress.setWordWrap(True); self.purchase_progress.setStyleSheet("opacity:.75")
        purchase_layout.addWidget(self.purchase_progress)
        buy_row = QHBoxLayout()
        self.buy_btn = QPushButton("🛒 Comprar Pro")
        self.open_checkout_btn = QPushButton("Abrir checkout")
        self.check_btn = QPushButton("↻ Verificar pagamento")
        self.cancel_checkout_btn = QPushButton("Cancelar tentativa")
        for b in (self.buy_btn, self.open_checkout_btn, self.check_btn, self.cancel_checkout_btn): buy_row.addWidget(b)
        purchase_layout.addLayout(buy_row)
        qconnect(self.buy_btn.clicked, self._start_purchase)
        qconnect(self.open_checkout_btn.clicked, self._open_existing_checkout)
        qconnect(self.check_btn.clicked, self._check_purchase)
        qconnect(self.cancel_checkout_btn.clicked, self._cancel_checkout)
        root.addWidget(self.purchase_box)

        # License / device management
        self.license_key_box = QGroupBox("Sua licença")
        license_layout = QVBoxLayout(self.license_key_box)
        license_help = QLabel("A conta é a forma principal de acesso. A chave abaixo serve para suporte/recuperação. O Pro permanece limitado a 1 dispositivo.")
        license_help.setWordWrap(True); license_help.setStyleSheet("opacity:.72")
        self.license_key_display = QLineEdit(); self.license_key_display.setReadOnly(True); self.license_key_display.setPlaceholderText("Clique em ‘Mostrar chave’")
        key_actions = QHBoxLayout()
        self.show_key_btn = QPushButton("👁 Mostrar chave"); self.copy_key_btn = QPushButton("📋 Copiar chave"); self.copy_key_btn.setEnabled(False)
        key_actions.addWidget(self.show_key_btn); key_actions.addWidget(self.copy_key_btn)
        license_layout.addWidget(license_help); license_layout.addWidget(self.license_key_display); license_layout.addLayout(key_actions)
        qconnect(self.show_key_btn.clicked, self._show_license_key); qconnect(self.copy_key_btn.clicked, self._copy_license_key)
        root.addWidget(self.license_key_box)

        self.manage_box = QGroupBox("Dispositivo")
        manage_layout = QHBoxLayout(self.manage_box)
        self.verify_btn = QPushButton("✓ Verificar Pro")
        self.deactivate_btn = QPushButton("Desativar este PC")
        manage_layout.addWidget(self.verify_btn); manage_layout.addWidget(self.deactivate_btn)
        qconnect(self.verify_btn.clicked, self._verify); qconnect(self.deactivate_btn.clicked, self._deactivate)
        root.addWidget(self.manage_box)

        root.addStretch(1)
        self._refresh()
        pending = checkout_state()
        if pending.get("session_token") and not has_pro_access():
            self._poll_timer.start(); QTimer.singleShot(900, self._check_purchase)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._closing = True; self._poll_timer.stop(); super().closeEvent(event)

    def _refresh(self, message: str | None = None) -> None:
        lic = license_status(); acct = account_status()
        owner = lic.active and lic.role == "OWNER"
        self.auth_tabs.setVisible(not acct.logged_in and not owner)
        self.account_box.setVisible(acct.logged_in)

        if owner:
            self.status_label.setText("<b>⭐ Owner ativo</b> · LIFETIME<br>Acesso total do proprietário")
            self.purchase_box.setVisible(False); self.device_box.setVisible(False)
            self.license_key_box.setVisible(False); self.manage_box.setVisible(True)
            self.verify_btn.setEnabled(True); self.deactivate_btn.setEnabled(True)
            return

        if acct.logged_in:
            plan = escape(acct.plan) if acct.plan else "Free"
            pro_text = "<b>PRO Lifetime</b>" if acct.has_pro else "Free"
            self.account_label.setText(
                f"<b>{escape(acct.email)}</b><br>Plano: {pro_text} · Dispositivo ativo: {acct.active_devices}/{acct.max_devices}"
            )
        else:
            self.account_label.clear()

        if lic.active:
            plan = f" · {escape(lic.plan)}" if lic.plan else ""
            self.status_label.setText(f"<b>⭐ {escape(lic.label)} ativo</b>{plan}<br>{escape(lic.detail)}")
        elif acct.logged_in and acct.has_pro:
            self.status_label.setText("<b>Conta Pro</b><br>O Pro pertence à sua conta, mas este PC ainda não está ativado.")
        elif acct.logged_in:
            self.status_label.setText("<b>Conta Free</b><br>Entre no Pro quando quiser; a compra será vinculada a esta conta.")
        else:
            self.status_label.setText("<b>Free</b><br>Entre ou crie uma conta para comprar o Study Radar Pro.")

        self.device_box.setVisible(acct.logged_in and acct.has_pro and not lic.active)
        self.purchase_box.setVisible(acct.logged_in and not acct.has_pro)
        commercial_active = lic.active and lic.role in {"PRO", "TESTER"}
        self.license_key_box.setVisible(commercial_active)
        self.manage_box.setVisible(lic.active)
        self.verify_btn.setEnabled(lic.active); self.deactivate_btn.setEnabled(lic.active)

        pending = checkout_state()
        has_pending = bool(pending.get("session_token")) and acct.logged_in and not acct.has_pro
        self.open_checkout_btn.setVisible(has_pending); self.check_btn.setVisible(has_pending); self.cancel_checkout_btn.setVisible(has_pending); self.buy_btn.setVisible(not has_pending)
        if message:
            self.purchase_progress.setText(escape(message))
        elif has_pending:
            self.purchase_progress.setText(f"Compra em andamento · status: <b>{escape(str(pending.get('status','pending_payment')))}</b>.")
        elif acct.logged_in and not acct.has_pro:
            self.purchase_progress.setText("O checkout seguro será aberto no navegador.")
        if lic.active:
            self._poll_timer.stop()

    def _run(self, task: Callable[[], Any], done: Callable[[Any], None]) -> None:
        if self._busy: return
        self._busy = True; self._set_network_buttons(False)
        def on_done(future: Future) -> None:
            self._busy = False
            if self._closing: return
            self._set_network_buttons(True)
            try: result = future.result()
            except Exception as exc:
                showInfo(f"Falha inesperada: {exc}", title=ADDON_NAME); return
            done(result)
        mw.taskman.run_in_background(task, on_done)

    def _set_network_buttons(self, enabled: bool) -> None:
        for b in (self.login_btn, self.register_btn, self.activate_key_btn, self.refresh_account_btn, self.change_password_btn,
                  self.logout_btn, self.activate_device_btn, self.buy_btn, self.check_btn, self.verify_btn,
                  self.deactivate_btn, self.show_key_btn):
            b.setEnabled(enabled)

    def _after_auth(self, result: Any) -> None:
        ok, message = result
        if not ok:
            showInfo(str(message), title=ADDON_NAME); self._refresh(); return
        # If this account already owns Pro, try to activate this same device.
        if account_status().has_pro:
            self._run(activate_account_device, lambda r: self._finish_device_activation(r, "Login realizado."))
            return
        self._refresh(str(message))

    def _login(self) -> None:
        email = self.login_email.text().strip(); password = self.login_password.text()
        if not email or not password:
            showInfo("Digite e-mail e senha.", title=ADDON_NAME); return
        self._run(lambda: login_account(email, password), self._after_auth)

    def _register(self) -> None:
        email = self.register_email.text().strip(); p1 = self.register_password.text(); p2 = self.register_password2.text()
        if p1 != p2:
            showInfo("As senhas não coincidem.", title=ADDON_NAME); return
        if len(p1) < 8:
            showInfo("A senha precisa ter pelo menos 8 caracteres.", title=ADDON_NAME); return
        self._run(lambda: register_account(email, p1), self._after_auth)

    def _refresh_account(self) -> None:
        self._run(refresh_account, lambda r: (showInfo(str(r[1]), title=ADDON_NAME) if not r[0] else None, self._refresh())[1])

    def _logout(self) -> None:
        if not askUser("Sair da conta neste Anki? Isso não libera o dispositivo no servidor. Para trocar de PC, use ‘Desativar este PC’ primeiro.", title=ADDON_NAME): return
        self._run(logout_account, lambda r: (showInfo(str(r[1]), title=ADDON_NAME), self._refresh()))

    def _change_password(self) -> None:
        dlg = QDialog(self); dlg.setWindowTitle("Alterar senha"); form = QFormLayout(dlg)
        current = QLineEdit(); current.setEchoMode(QLineEdit.EchoMode.Password)
        new1 = QLineEdit(); new1.setEchoMode(QLineEdit.EchoMode.Password)
        new2 = QLineEdit(); new2.setEchoMode(QLineEdit.EchoMode.Password)
        save = QPushButton("Salvar nova senha"); cancel = QPushButton("Cancelar"); row = QHBoxLayout(); row.addWidget(save); row.addWidget(cancel)
        form.addRow("Senha atual:", current); form.addRow("Nova senha:", new1); form.addRow("Confirmar:", new2); form.addRow(row)
        qconnect(cancel.clicked, dlg.reject)
        def submit():
            if new1.text() != new2.text(): showInfo("As novas senhas não coincidem.", title=ADDON_NAME); return
            if len(new1.text()) < 8: showInfo("A nova senha precisa ter pelo menos 8 caracteres.", title=ADDON_NAME); return
            dlg.accept(); self._run(lambda: change_account_password(current.text(), new1.text()), lambda r: showInfo(str(r[1]), title=ADDON_NAME))
        qconnect(save.clicked, submit); dlg.exec()

    def _activate_device(self) -> None:
        self._run(activate_account_device, lambda r: self._finish_device_activation(r, None))

    def _finish_device_activation(self, result: Any, prefix: str | None) -> None:
        ok, message = result
        if not ok:
            showInfo(str(message), title=ADDON_NAME); self._refresh(); return
        tooltip("⭐ Study Radar Pro ativado")
        self._refresh(f"{prefix+' ' if prefix else ''}{message}")
        try:
            if getattr(mw, "state", "") == "deckBrowser": mw.deckBrowser.refresh()
        except Exception: pass

    def _start_purchase(self) -> None:
        if not account_status().logged_in:
            showInfo("Entre ou crie uma conta antes de comprar.", title=ADDON_NAME); return
        self.purchase_progress.setText("Criando checkout vinculado à sua conta…")
        def done(result: Any) -> None:
            ok, data = result
            if not ok:
                self.purchase_progress.setText(f"Não foi possível iniciar a compra: {escape(str(data))}"); return
            url = str(data.get("checkout_url", ""))
            if url: webbrowser.open(url)
            self._refresh("Checkout aberto. Aguardando a aprovação do pagamento…")
            self._poll_timer.start(); QTimer.singleShot(2500, self._check_purchase)
        self._run(lambda: create_checkout(account_status().email), done)

    def _open_existing_checkout(self) -> None:
        url = str(checkout_state().get("checkout_url", ""))
        if url: webbrowser.open(url)
        else: showInfo("O link deste checkout não está mais disponível.", title=ADDON_NAME)

    def _check_purchase(self) -> None:
        if self._busy or has_pro_access(): return
        if not checkout_state().get("session_token"):
            self._poll_timer.stop(); self._refresh(); return
        self.purchase_progress.setText("Verificando o pagamento…")
        def done(result: Any) -> None:
            ok, data = result
            if not ok:
                self.purchase_progress.setText(f"Não foi possível verificar agora: {escape(str(data))}"); return
            status = str(data.get("status", "pending_payment"))
            if status == "approved":
                self.purchase_progress.setText("Pagamento aprovado. Vinculando o Pro à sua conta…")
                self._activate_purchase(data); return
            if status == "expired":
                self._poll_timer.stop(); self.purchase_progress.setText("Checkout expirado. Cancele a tentativa e gere uma nova."); return
            friendly = {"pending_payment":"Pagamento ainda pendente…", "pending":"Pagamento ainda pendente…", "manual_review":"Pagamento em análise.", "rejected":"Pagamento não aprovado."}.get(status, f"Status: {status}")
            self.purchase_progress.setText(friendly)
        self._run(check_checkout_status, done)

    def _activate_purchase(self, data: dict[str, Any]) -> None:
        def done(result: Any) -> None:
            ok, message = result
            if not ok:
                self.purchase_progress.setText(f"Pagamento aprovado, mas a ativação falhou: {escape(str(message))}"); return
            self._poll_timer.stop(); self._refresh(str(message)); tooltip("⭐ Study Radar Pro ativado")
            try:
                if getattr(mw, "state", "") == "deckBrowser": mw.deckBrowser.refresh()
            except Exception: pass
        self._run(lambda: activate_checkout_license(data), done)

    def _cancel_checkout(self) -> None:
        if not askUser("Cancelar esta tentativa local? Isso não cancela um pagamento já realizado.", title=ADDON_NAME): return
        clear_pending_checkout(); self._poll_timer.stop(); self._refresh("Tentativa local removida.")

    def _activate_manual(self) -> None:
        key = self.key_input.text().strip()
        if not key: showInfo("Digite a chave.", title=ADDON_NAME); return
        def done(result: Any) -> None:
            ok, message = result; showInfo(str(message), title=ADDON_NAME)
            if ok:
                self.key_input.clear(); clear_pending_checkout(); self._refresh()
        self._run(lambda: activate_license(key), done)

    def _show_license_key(self) -> None:
        self.license_key_display.setText("Consultando…"); self.copy_key_btn.setEnabled(False)
        def done(result: Any) -> None:
            ok, value = result
            if not ok:
                self.license_key_display.clear(); showInfo(str(value), title=ADDON_NAME); return
            self.license_key_display.setText(str(value).strip().upper()); self.copy_key_btn.setEnabled(True)
        self._run(fetch_license_key, done)

    def _copy_license_key(self) -> None:
        key = self.license_key_display.text().strip()
        if key and key != "Consultando…": QApplication.clipboard().setText(key); tooltip("📋 Chave copiada")

    def _verify(self) -> None:
        self._run(verify_license, lambda r: (showInfo(str(r[1]), title=ADDON_NAME), self._refresh()))

    def _deactivate(self) -> None:
        if not askUser("Desativar o Pro neste computador? Sua conta continuará sendo Pro e poderá ser ativada em outro PC.", title=ADDON_NAME): return
        self._run(deactivate_license, lambda r: (showInfo(str(r[1]), title=ADDON_NAME), self._refresh()))


def open_pro_dialog() -> None:
    existing = getattr(mw, "_study_radar_pro_dialog", None)
    try:
        if existing and existing.isVisible(): existing.raise_(); existing.activateWindow(); return
    except Exception: pass
    dlg = ProDialog(); mw._study_radar_pro_dialog = dlg; dlg.show(); dlg.raise_(); dlg.activateWindow()
