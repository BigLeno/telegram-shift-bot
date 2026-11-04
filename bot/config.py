"""Configuração do bot, lida das variáveis de ambiente (arquivo .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bot.calendar_rules import ClosedPeriod, PeriodError, parse_periods
from bot.schedule import DEFAULT_SLOTS, DEFAULT_SLOTS_END, ScheduleError, SlotTable

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ROLES = {"admin", "membro"}


class ConfigError(Exception):
    """Configuração ausente ou inválida."""


@dataclass(frozen=True)
class User:
    id: int
    name: str
    role: str


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    users: tuple[User, ...]
    spreadsheet_id: str
    schedule_range: str
    google_client_secret: Path
    google_token: Path
    pending_requests_file: Path
    schedule_images_dir: Path
    timezone: ZoneInfo
    slots: SlotTable = field(default_factory=SlotTable.parse)
    closed_periods: tuple[ClosedPeriod, ...] = ()
    managers_range: str = ""
    bot_name: str = "Bot de Plantão"
    about_text: str = ""
    urgent_contact: str = ""
    forward_messages_to_admin: bool = False

    @property
    def admin(self) -> User:
        return next(user for user in self.users if user.role == "admin")

    def find_user_by_id(self, user_id: int) -> User | None:
        return next((user for user in self.users if user.id == user_id), None)

    def find_user_by_name(self, name: str) -> User | None:
        wanted = name.strip().casefold()
        return next((user for user in self.users if user.name.casefold() == wanted), None)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if env is None else env)

        def get(name: str, default: str = "") -> str:
            return env.get(name, "").strip() or default

        def required(name: str) -> str:
            value = get(name)
            if not value:
                raise ConfigError(f"Variável de ambiente obrigatória ausente: {name}")
            return value

        def path(name: str, default: str) -> Path:
            value = Path(get(name, default))
            return value if value.is_absolute() else PROJECT_ROOT / value

        users = parse_users(required("USERS"))
        if not any(user.role == "admin" for user in users):
            raise ConfigError("USERS precisa ter pelo menos um usuário com o papel 'admin'.")

        try:
            slots = SlotTable.parse(get("SLOTS", DEFAULT_SLOTS), get("SLOTS_END", DEFAULT_SLOTS_END))
            closed_periods = parse_periods(get("CLOSED_PERIODS"))
            timezone = ZoneInfo(get("TIMEZONE", "America/Sao_Paulo"))
        except (ValueError, ScheduleError, PeriodError, ZoneInfoNotFoundError) as error:
            raise ConfigError(str(error)) from error

        return cls(
            telegram_token=required("TELEGRAM_TOKEN"),
            users=users,
            spreadsheet_id=required("SPREADSHEET_ID"),
            schedule_range=required("SCHEDULE_RANGE"),
            google_client_secret=path("GOOGLE_CLIENT_SECRET_FILE", "secrets/client_secret.json"),
            google_token=path("GOOGLE_TOKEN_FILE", "secrets/token.json"),
            pending_requests_file=path("PENDING_REQUESTS_FILE", "data/pending_requests.json"),
            schedule_images_dir=path("SCHEDULE_IMAGES_DIR", "assets/escalas"),
            timezone=timezone,
            slots=slots,
            closed_periods=closed_periods,
            managers_range=get("MANAGERS_RANGE"),
            bot_name=get("BOT_NAME", "Bot de Plantão"),
            about_text=get("ABOUT_TEXT").replace("\\n", "\n"),
            urgent_contact=get("URGENT_CONTACT"),
            forward_messages_to_admin=get("FORWARD_MESSAGES_TO_ADMIN").lower() in ("1", "true", "sim", "yes"),
        )


def parse_users(raw: str) -> tuple[User, ...]:
    """Lê usuários no formato "id:nome:papel", separados por vírgula.

    Exemplo: "123456:Ana:admin,789012:Bruno:membro".
    O nome deve ser igual ao que aparece na planilha da escala.
    """
    users = []
    for entry in filter(None, (item.strip() for item in raw.split(","))):
        parts = [part.strip() for part in entry.split(":")]
        if len(parts) != 3:
            raise ConfigError(f'Usuário inválido em USERS: "{entry}". Use o formato id:nome:papel.')
        user_id, name, role = parts
        if not user_id.lstrip("-").isdigit():
            raise ConfigError(f'ID do Telegram inválido em USERS: "{user_id}".')
        if role not in ROLES:
            raise ConfigError(f'Papel inválido em USERS: "{role}". Use um de: {", ".join(sorted(ROLES))}.')
        users.append(User(id=int(user_id), name=name, role=role))

    if not users:
        raise ConfigError("USERS não tem nenhum usuário.")
    return tuple(users)
