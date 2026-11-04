# telegram-shift-bot

[![CI](https://github.com/BigLeno/telegram-shift-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/BigLeno/telegram-shift-bot/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Bot do Telegram para equipes que trabalham em **escala de plantão**. A escala fica numa planilha do
Google Sheets e o bot faz a ponte entre quem precisa de atendimento e quem está de plantão no horário
pedido.

Serve para monitorias, suporte de TI, laboratórios, incubadoras, centros acadêmicos e qualquer equipe
com revezamento por turnos. Turnos, períodos sem atendimento e textos são configuráveis.

## Como funciona

```
Usuário:  agendar amanhã 14:30 dúvida sobre o projeto
Bot → pessoas de plantão no turno T34:
          Maria quer agendar um atendimento em 04/11/2026 às 14:30. Responda sim ou não.
Plantonista: sim
Bot → usuário:  Ana aceitou o seu pedido para 04/11/2026 às 14:30.
```

- O bot lê a escala, descobre quem está de plantão naquele dia e turno e envia o pedido a todos.
  A primeira resposta (`sim` ou `não`) fecha o pedido.
- Recusa datas passadas, fins de semana, horários fora do expediente e pedidos com menos de 2 h de
  antecedência.
- Suspende os agendamentos nos períodos configurados (recesso, férias) e pode indicar um contato
  para urgências.

## Comandos

| Comando | Descrição |
| --- | --- |
| `/start`, `/ajuda` | Lista os comandos |
| `/agendar` | Explica o formato `agendar <data> <horário> <assunto>` |
| `agendar 10/03 14:30 assunto` | Envia o pedido a quem está de plantão. Aceita `hoje`, `amanhã`, `dd/mm`, `dd/mm/aaaa` e horários como `14:30`, `14h` ou o código do turno (`T34`) |
| `/equipe` | Lista quem aparece na escala |
| `/gestores` | Lista os gestores (opcional) |
| `/escalas` e `escala manha` | Envia a imagem de uma escala |
| `/sobre` | Texto configurável sobre a equipe |

## Arquitetura

```
bot/
├── __main__.py          # ponto de entrada (python -m bot)
├── config.py            # variáveis de ambiente, usuários, turnos e períodos
├── telegram_bot.py      # comandos do bot (cliente do Telegram injetado, testável)
├── schedule.py          # datas, turnos e leitura da escala
├── calendar_rules.py    # períodos sem agendamento e dias úteis
├── pending_requests.py  # fila de pedidos em JSON, com escrita atômica
├── sheets.py            # Google Sheets (somente leitura)
└── small_talk.py        # respostas para conversa informal
```

A lógica de datas, turnos, escala e fila não depende do Telegram nem do Google e é testada
isoladamente. Os comandos são testados com um cliente falso do Telegram.

## Como rodar

Requisitos: Python 3.10+ e um projeto no Google Cloud com a API do Google Sheets ativada.

```bash
git clone https://github.com/BigLeno/telegram-shift-bot.git
cd telegram-shift-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencha os valores
```

1. Crie o bot com o [@BotFather](https://t.me/BotFather) e coloque o token em `TELEGRAM_TOKEN`.
2. No Google Cloud Console, crie uma credencial OAuth do tipo *Desktop*, baixe o JSON e salve em
   `secrets/client_secret.json`.
3. Cadastre as pessoas em `USERS` (`id:nome:papel`, papéis `admin` ou `membro`). O nome deve ser igual
   ao da planilha.
4. Rode `python -m bot`. Na primeira execução, o navegador abre para autorizar a leitura da planilha
   e o `secrets/token.json` é criado.

## Configuração

Todas as opções estão comentadas no [`.env.example`](.env.example). As principais:

| Variável | Exemplo | Descrição |
| --- | --- | --- |
| `SCHEDULE_RANGE` | `Escala!A2:F10` | Intervalo da escala na planilha |
| `SLOTS` | `MANHA=08:00,TARDE=13:00` | Turnos e horário de início de cada um |
| `SLOTS_END` | `18:00` | Fim do último turno |
| `CLOSED_PERIODS` | `22/12-14/01=recesso;15/07-31/07=férias` | Períodos anuais sem agendamento |
| `TIMEZONE` | `America/Sao_Paulo` | Fuso usado para validar a antecedência |
| `BOT_NAME`, `ABOUT_TEXT`, `URGENT_CONTACT` | | Textos exibidos pelo bot |
| `MANAGERS_RANGE` | `Escala!A13:F14` | Habilita o `/gestores` |

O padrão de `SLOTS` são turnos de aula de 50 minutos (`M12` a `N34`), comuns em universidades.

### Planilha

A primeira coluna é o código do turno e as cinco seguintes, segunda a sexta. Use `X` para horário
sem ninguém e `/` para mais de um nome. Linhas cujo primeiro valor não é um turno são ignoradas.

| Turno | Segunda | Terça | Quarta | Quinta | Sexta |
| --- | --- | --- | --- | --- | --- |
| MANHA | Ana | X | Bruno | Ana / Bruno | X |
| TARDE | Carla | Bruno | X | X | Carla |

### Imagens da escala

O bot envia qualquer `.png` da pasta `SCHEDULE_IMAGES_DIR`: `escala manha` envia `manha.png`. As imagens
em `assets/escalas` são exemplos com nomes fictícios, gerados por `scripts/gerar_imagens_exemplo.py`.
Em produção, use uma pasta fora do repositório.

### Em produção

O arquivo [`deploy/shift-bot.service`](deploy/shift-bot.service) mantém o bot rodando com systemd e o
reinicia após falhas.

## Privacidade

- Segredos (`.env`, `secrets/`) e dados de execução (`data/`) não são versionados.
- O acesso à planilha é somente leitura.
- O encaminhamento de mensagens ao administrador vem desligado (`FORWARD_MESSAGES_TO_ADMIN=false`).
  Se for ativado, avise os usuários.

## Testes

```bash
python -m unittest -v
```

A CI roda lint (ruff) e os testes em Python 3.10, 3.12 e 3.13 a cada push e pull request.

## Licença

[MIT](LICENSE) © 2023 Rutileno Gabriel
