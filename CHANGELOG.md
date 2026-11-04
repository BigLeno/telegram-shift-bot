# Changelog

## 2.0.0 (2026-11)

Reescrita como bot genérico, configurável para qualquer equipe com escala de plantão.

- Pacote `bot/` com módulos separados por responsabilidade e entrada via `python -m bot`.
- Turnos (`SLOTS`), períodos sem agendamento (`CLOSED_PERIODS`), fuso e textos configuráveis.
- Pessoas cadastradas em uma variável (`USERS=id:nome:papel,...`), com validação ao iniciar.
- Respostas `sim`/`não` aceitas só de pessoas cadastradas e por palavra exata.
- Cada pedido vai para quem está de plantão naquele turno, e a fila grava de forma atômica.
- Correções de datas: períodos que atravessam o ano, `dd/mm/aaaa`, 29/02, datas do ano seguinte e
  antecedência mínima considerando o dia e o fuso.
- Imagens de escala lidas da pasta configurada, com exemplos de nomes fictícios.
- Reconexão automática com `infinity_polling`.
- Google Sheets somente leitura e encaminhamento de mensagens ao administrador opcional.
- Dependências enxutas, testes automatizados, CI no GitHub Actions e serviço systemd.

## 1.x (2023)

- Primeira versão, feita para a escala de bolsistas de uma incubadora universitária: consulta da
  escala, agendamento, listas de equipe e gestores, imagens da escala, recesso e horário reduzido.
