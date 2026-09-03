# Study Radar v1.3.1 — Production

Esta é a primeira versão pública conectada ao ambiente comercial real do Study Radar.

## Mudanças
- Backend padrão alterado para o ambiente de produção.
- Checkout Pro passa a usar o fluxo real configurado no servidor.
- Mantido login por e-mail e senha.
- PRO Lifetime continua limitado a **1 dispositivo ativo por vez**.
- Migração automática remove localmente sessões de conta, checkout e ativações comerciais originadas do antigo ambiente de teste.
- A licença OWNER offline é preservada.
- Novos estados de conta/checkout registram o backend de origem para impedir mistura entre ambientes.

## Segurança
Nenhum Access Token do Mercado Pago, segredo do Webhook, senha do banco ou chave privada do backend está incluído no add-on.
