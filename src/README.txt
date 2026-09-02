ANKI STUDY RADAR — v0.1.1

O que faz
---------
Mostra na tela inicial do Anki quais baralhos/temas merecem ser revisitados hoje.
Os nomes exibidos são lidos diretamente dos nomes dos baralhos existentes na coleção do usuário.

Como decide
-----------
1. Agrupa o histórico de respostas por baralho e por dia.
2. Ignora sessões muito pequenas para que responder 1 ou 2 cards não "zere" o radar.
3. A primeira sessão válida sugere uma nova revisão temática em aproximadamente 2 dias.
4. Conforme o baralho é revisitado, o intervalo-base cresce: 2, 4, 7, 14, 21, 30, 45 e 60 dias.
5. Muitos Again/Hard encurtam o intervalo recomendado; desempenho muito bom pode ampliá-lo um pouco.

Importante
----------
- O add-on NÃO altera o FSRS, intervalos, estados ou vencimentos dos cards.
- Ele apenas recomenda QUAL BARALHO vale a pena revisitar como tema.
- "Abrir baralho" seleciona o baralho no Anki e abre sua tela normal.
- Como o histórico padrão do Anki registra o baralho real de cada card, em estruturas com subbaralhos o radar tende a mostrar o subbaralho em que os cards estão salvos.
- A regra é heurística e não é uma curva de esquecimento clinicamente validada.

Instalação
----------
1. Abra o Anki Desktop.
2. Ferramentas > Extensões/Add-ons.
3. Use "Instalar a partir de arquivo" (ou dê duplo clique no .ankiaddon, dependendo da versão).
4. Selecione Anki_Study_Radar_v0.1.1.ankiaddon.
5. Reinicie o Anki.

Versão: 0.1.1
