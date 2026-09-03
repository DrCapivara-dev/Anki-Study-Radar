# Changelog

## 1.3.0 — 2026-09-03
- Added Study Radar account registration and login with email/password.
- Purchases can be linked to the authenticated account.
- PRO Lifetime is now limited to one active device.
- Added account status, logout and password-change controls.
- Account-owned Pro can be activated without typing the SR-PRO key.
- Kept OWNER and legacy manual-key activation compatibility.
- Added account session storage without storing passwords locally.


## v1.2.1
- Added **Sua licença** panel to the Pro hub.
- Commercial PRO/TESTER users can securely **Mostrar chave** and **Copiar chave** after activation.
- After a successful purchase, the newly generated `SR-PRO-...` key is shown immediately so the customer can save it.
- Reopening Anki no longer requires the reusable key to be stored in plaintext: the add-on retrieves it from the backend only after validating the current activation token.
- OWNER keys remain private/offline and are never returned by the commercial backend.
- Requires Study Radar Backend v1.0.4+ for key retrieval after reopening the app.

## v1.2.0 — Mercado Pago + licenças integradas

- Compra do Study Radar Pro diretamente pelo add-on.
- Integração com o backend oficial e Checkout Pro do Mercado Pago.
- Polling de pagamento em segundo plano sem travar o Anki.
- Ativação automática após pagamento aprovado.
- Retomada de checkout pendente ao reabrir o Anki.
- Ativação manual por chave SR-PRO.
- Verificação e desativação de licença compatíveis com a API v1 do backend.
- Armazenamento local apenas do activation token após ativação comercial.
- Compatibilidade preservada com a licença OWNER offline.

## v1.1.2
- Added **Analytics Free**: Analytics is now visible and usable for every Study Radar user.
- Free users get a basic overview with tracked topics, attention count, approximate 30-day retention, 7-day review load, focus ranking and forecast.
- Added a polished **Unlock Analytics Pro** area inside the Free dashboard.
- Bundled a visual preview of the full Pro dashboard so Free users can see what the upgrade unlocks.
- Free users now see both **Analytics** and **Ativar Pro** on the Study Radar home panel.
- OWNER/TESTER/PRO users keep the complete Analytics experience with Visão geral, Desempenho, Baralhos and Insights.
- Preserves the PyQt 6.9 chart compatibility fix from v1.1.1.

## v1.1.1
- Fixed a crash in **Analytics → Desempenho → Retenção semanal** on Anki 25.09.x / PyQt 6.9.
- Updated `QPainter.drawLine()` calls to use `QPointF`, avoiding float-overload errors in Qt 6.9.
- Applied the same geometry-safe drawing style to chart baseline rendering for forward compatibility.
- No changes to study scheduling, FSRS behavior, licensing, Smart Review, or analytics calculations.

## v1.1.0
- Rebuilt **Study Radar Pro Analytics** as a visual decision dashboard instead of a simple table.
- Added **Visão geral** with summary cards for tracked topics, attention items, approximate 30-day retention, active streak, 7-day due load and estimated study time.
- Added priority ranking chart (**Onde focar**).
- Added 7-day review forecast chart and 14-day activity chart.
- Added **Desempenho** tab with Again/Hard/Good/Easy donut chart, weekly retention trend, interval consolidation and card-type distribution.
- Expanded **Baralhos** tab with sortable detailed deck analytics.
- Added **Insights** tab with best next step, suggested daily plan, weak points, future-load warning and retention trend.
- Added direct **Revisar agora** and **Sessão Foco 30 min** actions inside Analytics.
- Uses only local Anki collection data; no external analytics service is required.
- Preserves all v1.0.4 Radar, Smart Review, cleanup, licensing and FSRS-safe filtered-deck behavior.

## v1.0.4
- Simplified Anki's **Tools** menu to a single **Study Radar** entry.
- Added a central Study Radar control panel with shortcuts to Settings, License/Pro, Focus Session, Analytics, temporary-session cleanup and Diagnostics.
- Removed the individual Study Radar actions from the Tools menu.
- Preserved all v1.0.3 Radar layout, review logic, filtered-deck cleanup, licensing and FSRS-safe behavior.

## v1.0.3
- Fixed secondary action buttons appearing glued together or overlapping in Anki's deck screen.
- Added explicit spacing between **Revisão**, **Adiar** and **Ocultar**.
- Explicitly resets inherited Anki button margins and uses flex sizing for stable alignment.
- Kept **Abrir** centered as the primary full-width action.
- No changes to review scheduling, licensing, temporary-deck cleanup, or FSRS behavior.

## v1.0.2
- Redesigned each deck action area so **Abrir** is the clear primary action.
- Moved **Revisão**, **Adiar** and **Ocultar** to a compact secondary row below **Abrir**.
- Removed the explanatory “organiza temas sem substituir o FSRS” sentence from the home panel.
- Replaced the prominent “Prioridade” header line with a lighter **Em foco** summary.
- Reduced header text weight and visual noise for a cleaner daily dashboard.
- Kept all v1.0.1 temporary-session cleanup protections.

## v1.0.1
- Automatically removes Study Radar temporary filtered decks after the final card leaves the session.
- Safely cleans only empty filtered decks created under the Study Radar temporary-deck namespace.
- Optional cleanup of empty Study Radar sessions when Anki starts.
- Added manual **Tools → Study Radar — Limpar sessões temporárias vazias** action.
- Added cleanup controls to the graphical settings window.
- Keeps normal decks and cards untouched.

## 1.0.0 — 2026-09-03
- First consolidated stable-candidate release.
- Added Free/Pro architecture.
- Added OWNER/TESTER/PRO licensing foundation.
- Added graphical Pro activation screen.
- Added Focus Session Pro.
- Added Advanced Analytics Pro.
- Added Exam Mode Pro.
- Added snooze and ignore-deck actions.
- Added display modes for hierarchical deck names.
- Added interval presets.
- Added diagnostics menu.
- Preserved Quick Review preview-mode behavior.
- Prepared backend URL and purchase URL configuration for future Mercado Pago integration.

## 0.3.0
- Added Smart Review / Quick Review and priority score.

## 0.2.0
- Added graphical settings window.

## 0.1.1
- Cleaner subdeck display names.
