# Anki Study Radar — configurações

A partir da versão 0.2.0, você **não precisa editar este JSON manualmente**.

Abra no Anki:

**Ferramentas → Study Radar Settings...**

Ou clique no botão **⚙ Configurações** dentro do próprio Radar.

## Opções

- `history_days`: quantos dias de histórico o radar analisa.
- `max_rows`: máximo de baralhos mostrados na tela inicial.
- `minimum_session_reviews`: número mínimo de respostas no dia para considerar uma sessão válida. Em baralhos menores, o limite é reduzido automaticamente ao número de cards existentes.
- `base_intervals_days`: sequência-base de revisão temática. A primeira sessão sugere retorno em 2 dias; sessões posteriores expandem o intervalo. O desempenho em Again/Hard pode antecipar a sugestão.
- `show_upcoming_days`: também mostra baralhos cuja revisão temática está chegando dentro desse número de dias.

O Study Radar não altera os intervalos dos cards e não substitui o FSRS/agendador do Anki. Ele funciona como uma camada de recomendação por baralho/tema.
