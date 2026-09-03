from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Any

from aqt import mw

from .config import get_config
from .constants import ADDON_NAME, VERSION
from .licensing import license_status
from .radar import Recommendation, display_deck_name, recommendations


def _ago(days: int) -> str:
    if days == 0: return "hoje"
    if days == 1: return "há 1 dia"
    return f"há {days} dias"


def _when(rec: Recommendation) -> tuple[str, str, str]:
    if rec.days_until < 0:
        n = abs(rec.days_until); return "ATRASADO", "red", f"há {n}d"
    if rec.days_until == 0: return "HOJE", "red", "revisar hoje"
    if rec.days_until == 1: return "AMANHÃ", "yellow", "amanhã"
    return "EM BREVE", "green", f"em {rec.days_until}d"


def _row(rec: Recommendation, show_reasons: bool) -> str:
    label, cls, timing = _when(rec); s = rec.last_session
    reason = f" · {escape(rec.reason)}" if show_reasons else ""
    return f"""
    <div class="sr-row">
      <div class="sr-main">
        <div class="sr-name">{escape(display_deck_name(rec.deck_name))}</div>
        <div class="sr-meta">Última sessão {_ago(rec.days_since)} · {s.reviews} respostas · Prioridade {rec.priority}/100{reason}</div>
      </div>
      <div class="sr-status"><span class="sr-pill {cls}">{label}</span><span>{timing}</span></div>
      <div class="sr-actions">
        <button class="sr-open" onclick="pycmd('sr_open:{rec.deck_id}')">Abrir</button>
        <div class="sr-secondary-actions">
          <button class="sr-review" onclick="pycmd('sr_smart:{rec.deck_id}')">⚡ Revisão</button>
          <button onclick="pycmd('sr_snooze:{rec.deck_id}')">⏰ Adiar</button>
          <button class="sr-muted" onclick="pycmd('sr_ignore:{rec.deck_id}')">Ocultar</button>
        </div>
      </div>
    </div>"""


def render_radar() -> str:
    try: recs = recommendations()
    except Exception as exc: return f"<div class='sr-card'><b>{ADDON_NAME}</b><br>Erro: {escape(str(exc))}</div>"
    cfg = get_config(); show_upcoming = max(0, int(cfg.get("show_upcoming_days", 7))); max_rows = max(1, int(cfg.get("max_rows", 10)))
    visible = [r for r in recs if r.days_until <= show_upcoming][:max_rows]; due = [r for r in recs if r.days_until <= 0]
    lic = license_status(); badge = f"<span class='sr-pro'>{'⭐ '+lic.label if lic.active else 'Free'}</span>"
    if due:
        headline = f"{len(due)} tema{'s' if len(due)!=1 else ''} para revisar hoje"
        focus_line = f"Em foco: <b>{escape(display_deck_name(due[0].deck_name))}</b>"
    elif recs:
        next_rec = recs[0]
        headline = "Tudo em dia por enquanto"
        when = "amanhã" if next_rec.days_until == 1 else f"em {next_rec.days_until} dias"
        focus_line = f"Próximo: <b>{escape(display_deck_name(next_rec.deck_name))}</b> · {when}"
    else:
        headline = "Ainda não há histórico suficiente"
        focus_line = ""
    exam_line = ""
    if lic.active and bool(cfg.get("exam_mode_enabled", False)):
        try:
            exam = datetime.strptime(str(cfg.get("exam_date", "")), "%Y-%m-%d").date(); days = (exam-date.today()).days
            if days >= 0: exam_line = f"<div class='sr-exam'>🎯 Modo Prova ativo · prova em {days} dia{'s' if days!=1 else ''}</div>"
        except Exception: pass
    rows = "".join(_row(r, bool(cfg.get("show_reasons", True))) for r in visible) or "<div class='sr-empty'>Nenhuma recomendação dentro da janela configurada.</div>"
    if lic.active:
        pro_actions = "<button onclick=\"pycmd('sr_focus')\">⏱ Sessão Foco</button><button onclick=\"pycmd('sr_analytics')\">📊 Analytics</button>"
    else:
        pro_actions = "<button onclick=\"pycmd('sr_analytics')\">📊 Analytics</button><button onclick=\"pycmd('sr_license')\">⭐ Ativar Pro</button>"
    return f"""
    <style>
      .sr-card{{margin:18px auto 14px;max-width:1100px;padding:16px 18px;border:1px solid rgba(128,128,128,.25);border-radius:14px;background:rgba(128,128,128,.06);box-sizing:border-box}}
      .sr-head{{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}}
      .sr-title-line{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
      .sr-title{{font-size:19px;font-weight:750;line-height:1.2}}
      .sr-headline{{font-size:13px;font-weight:650;opacity:.72;margin-top:4px;line-height:1.3}}
      .sr-focus{{font-size:13px;opacity:.72;line-height:1.35;margin-top:4px}}
      .sr-focus b{{font-weight:700;opacity:1}}
      .sr-top-actions{{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}}
      .sr-card button{{border:1px solid rgba(100,120,190,.42);border-radius:8px;padding:6px 9px;cursor:pointer;font-weight:600;margin:0!important;box-sizing:border-box!important;min-width:0}}
      .sr-pro{{font-size:11px;padding:3px 7px;border-radius:999px;background:rgba(100,120,220,.12)}}
      .sr-exam{{margin:9px 0;padding:7px 9px;border-radius:8px;background:rgba(180,100,220,.10);font-size:12px}}
      .sr-row{{display:grid;grid-template-columns:minmax(280px,1fr) 120px 350px;gap:14px;align-items:center;padding:11px 0;border-top:1px solid rgba(128,128,128,.16)}}
      .sr-name{{font-weight:680;font-size:15px;overflow-wrap:anywhere}}
      .sr-meta{{font-size:12px;opacity:.68;margin-top:3px}}
      .sr-status{{display:flex;flex-direction:column;gap:3px;font-size:11px;opacity:.85}}
      .sr-pill{{display:inline-block;width:max-content;font-size:10px;font-weight:800;padding:4px 7px;border-radius:999px}}
      .red{{background:rgba(220,60,60,.17);color:#d94b4b}} .yellow{{background:rgba(220,160,30,.17);color:#c28a13}} .green{{background:rgba(45,160,95,.15);color:#32965c}}
      .sr-actions{{display:flex;flex-direction:column;gap:9px;width:100%;min-width:0}}
      .sr-open{{display:block;width:100%;padding:9px 12px!important;font-size:13px;font-weight:800!important;text-align:center;background:rgba(100,120,220,.14);border-color:rgba(105,125,220,.55)!important}}
      .sr-secondary-actions{{display:flex;align-items:stretch;gap:9px;width:100%;min-width:0}}
      .sr-secondary-actions button{{flex:1 1 0;width:auto!important;min-width:0!important;white-space:nowrap;padding:7px 8px!important}}
      .sr-review{{font-weight:700!important}}
      .sr-muted{{opacity:.72}}
      .sr-empty{{padding:10px 0;opacity:.65}}
      @media(max-width:800px){{
        .sr-row{{grid-template-columns:1fr;gap:8px}}
        .sr-head{{flex-direction:column}}
        .sr-top-actions{{justify-content:flex-start}}
        .sr-actions{{max-width:none}}
      }}
    </style>
    <div class="sr-card">
      <div class="sr-head">
        <div>
          <div class="sr-title-line"><span class="sr-title">🧠 Study Radar</span>{badge}</div>
          <div class="sr-headline">{headline}</div>
          {f'<div class="sr-focus">{focus_line}</div>' if focus_line else ''}
        </div>
        <div class="sr-top-actions">{pro_actions}<button onclick="pycmd('sr_settings')">⚙ Configurações</button></div>
      </div>
      {exam_line}{rows}
      <div style="font-size:10px;opacity:.38;margin-top:8px">v{VERSION}</div>
    </div>"""
