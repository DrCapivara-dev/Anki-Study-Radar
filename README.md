# 🧠 Anki Study Radar

**Anki Study Radar** helps you decide **which deck/topic to revisit today** based on your actual review history.

Instead of changing Anki's scheduler, Study Radar adds a thematic layer on top of it: Anki/FSRS schedules individual cards, while Study Radar helps you decide which **deck or subject** deserves attention.

## v1.3.0 — Conta Study Radar + 1 dispositivo

The commercial flow now uses a **Study Radar account** instead of relying on a reusable license key as the primary login method.

### Account system
- Create an account with **email + password** inside the add-on.
- Passwords are never stored by the add-on; only a revocable account session token is stored locally.
- The backend stores only a salted **scrypt password hash**, never plaintext passwords.
- Mercado Pago purchases are linked to the authenticated Study Radar account.
- Once payment is approved, the account becomes **PRO Lifetime** and the current PC can be activated automatically.
- Commercial PRO is limited to **1 active device at a time**.
- Use **Desativar este PC** before moving the account to another computer.
- Change password directly from the Study Radar account center.
- The SR-PRO key remains available for support/recovery and legacy compatibility.
- OWNER activation remains offline and unchanged.

### Analytics experience
- Analytics Free remains available to everyone.
- Analytics Pro includes overview, performance, deck-level analysis and actionable insights.

### Core features
- Automatic deck discovery and clean subdeck names.
- Priority score 0–100 using actual review history.
- Again / Hard / Good / Easy analysis.
- Quick Review, Focus Session, Exam Mode and temporary-deck cleanup.
- Friendly graphical settings and diagnostics.

## Scheduling safety
Quick Review and Focus Session use Anki filtered decks in **preview mode** (`reschedule = false`). Study Radar is designed not to replace FSRS or rewrite normal card scheduling.

## Installation
1. Download `Anki_Study_Radar_v1.3.0.ankiaddon` from Releases.
2. Open Anki Desktop.
3. Go to **Tools → Add-ons → Install from file**.
4. Restart Anki.

## Configuration
Use **Tools → Study Radar** to open the central control panel. From there, open **Configurações** or any other Study Radar tool. The normal Anki Add-ons **Config** button still opens the friendly settings window directly.

## Privacy
Study Radar analyzes the local Anki collection. The OWNER license works locally. Commercial licensing sends only purchase/license/device activation data to the Study Radar backend; card contents are not sent.

## Important: owner key
The private OWNER key is **not part of this repository**. Never commit or publish it.

## Author
**DrCapivara-dev**

Feedback and bug reports are welcome.


## Conta, compra e ativação integrada

A partir da **v1.2.0**, o Study Radar Pro pode ser comprado diretamente pelo add-on. O Anki solicita ao backend uma sessão do Checkout Pro do Mercado Pago, abre o checkout no navegador, acompanha o pagamento e, quando aprovado, ativa automaticamente a licença neste computador.

- Checkout criado pelo backend; o Access Token do Mercado Pago nunca fica no add-on.
- Compra pendente é retomada automaticamente ao reabrir o Anki.
- A conta PRO comercial permite 1 dispositivo ativo por vez.
- Após a ativação, a chave SR-PRO não é mantida localmente; o add-on guarda apenas o token de ativação.
- A licença OWNER privada continua compatível.


### Chave comercial
Depois da ativação, clientes PRO podem abrir **Study Radar Pro → Sua licença → Mostrar chave / Copiar chave** para guardar a licença e usar em suporte/recuperação. A chave reutilizável não precisa ficar salva permanentemente em texto simples no estado local do add-on.
