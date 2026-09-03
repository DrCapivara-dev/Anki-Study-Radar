# Anki Study Radar

Use **Ferramentas → Study Radar** para abrir o painel principal.

As configurações comuns são editadas pela interface gráfica. A aba **Pro** leva à central de conta, compra e ativação.

## Backend comercial

A **v1.3.1** é a primeira build pública de produção e usa o backend comercial em `https://study-radar-backend-prod.onrender.com`. O add-on cria o Checkout Pro do Mercado Pago pelo backend, acompanha o pagamento e, quando aprovado, vincula o **Pro Lifetime** à conta Study Radar e ativa **1 dispositivo por vez**.

Ao atualizar da build de testes v1.3.0, sessões de conta, checkout e ativações comerciais do antigo ambiente de teste são removidas localmente para evitar mistura entre testes e vendas reais. A chave **OWNER** offline é preservada.

A configuração JSON continua disponível para usuários avançados. Não altere `license_api_url` salvo se estiver usando um servidor próprio compatível.

## Chave comercial

Clientes PRO podem abrir **Study Radar → Conta e Pro → Sua licença → Mostrar chave / Copiar chave**. A chave reutilizável não precisa ficar armazenada permanentemente em texto simples no Anki.
