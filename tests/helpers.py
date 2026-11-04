from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from bot.calendar_rules import parse_periods
from bot.config import Settings, parse_users
from bot.schedule import SlotTable

TZ = ZoneInfo("America/Sao_Paulo")
SLOTS = SlotTable.parse()

# Escala no formato da planilha: turno + segunda a sexta.
ROWS = [
    ["Turno", "Segunda", "Terça", "Quarta", "Quinta", "Sexta"],
    ["M12", "Ana", "X", "Bruno", "Ana / Bruno", "X"],
    ["M34", "Bruno", "Ana", "X", "Bruno", "Ana"],
    ["T34", "Carla", "Bruno/Ana", "X", "X", "Carla"],
    [],
    ["N12", "X", "X", "Carla", "X"],
]


def make_settings(tmp: Path, **overrides) -> Settings:
    values = dict(
        telegram_token="token",
        users=parse_users("1:Admin:admin,2:Ana:membro,3:Bruno:membro,4:Carla:membro"),
        spreadsheet_id="sheet",
        schedule_range="escala",
        managers_range="gestores",
        google_client_secret=tmp / "client_secret.json",
        google_token=tmp / "token.json",
        pending_requests_file=tmp / "pending.json",
        schedule_images_dir=tmp / "escalas",
        timezone=TZ,
        slots=SLOTS,
        closed_periods=parse_periods("22/12-14/01=recesso"),
        bot_name="Bot Teste",
    )
    values.update(overrides)
    return Settings(**values)


def message(text: str, user_id: int = 99, first_name: str = "Maria", last_name: str | None = "Silva",
            username: str | None = None):
    user = SimpleNamespace(id=user_id, first_name=first_name, last_name=last_name, username=username)
    return SimpleNamespace(text=text, from_user=user, chat=SimpleNamespace(id=user_id))
