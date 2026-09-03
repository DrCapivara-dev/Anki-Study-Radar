# Anki Study Radar v1.2.0

## Mercado Pago + ativação Pro integrada

Esta versão conecta o add-on ao backend do Study Radar Pro.

### Novidades
- **Comprar Pro** dentro do Study Radar.
- Checkout Pro aberto com segurança no navegador.
- Acompanhamento do pagamento em segundo plano.
- Detecção automática do status `approved`.
- Ativação automática da licença comercial no computador atual.
- Compra pendente retomada ao reabrir o Anki.
- Central Pro para comprar, ativar chave, verificar e desativar dispositivo.
- Até 2 dispositivos por licença PRO.
- Correção da integração dos endpoints `/licenses/activate`, `/verify` e `/deactivate` com o backend real.
- OWNER offline continua funcionando.

### Segurança
O Access Token do Mercado Pago não existe dentro do add-on. O add-on conversa apenas com o backend público do Study Radar. Após a ativação, a chave SR-PRO não é persistida; fica salvo somente o activation token do dispositivo.

### Instalação
Instale o `.ankiaddon` por cima da versão anterior e reinicie o Anki.
