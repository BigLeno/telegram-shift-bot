"""Comandos do bot no Telegram.

A lógica de cada comando fica em métodos desta classe, que recebem a mensagem e usam um
cliente do Telegram injetado. Isso permite testar os comandos com um cliente falso.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from bot import small_talk
from bot.calendar_rules import closed_period_for
from bot.config import Settings
from bot.pending_requests import PendingRequestStore
from bot.schedule import ScheduleError, build_request, describe, on_duty, unique_names
from bot.sheets import SheetsError

logger = logging.getLogger(__name__)

ROSTER_WORDS = {"escala", "escalas", "horario", "horarios", "horário", "horários"}
YES = {"sim", "s", "aceito"}
NO = {"não", "nao", "n", "recuso"}

SCHEDULE_HELP = (
    "Para agendar, envie: agendar <data> <horário> <assunto>\n"
    "Exemplos:\n"
    "  agendar 10/03 14:30 dúvida sobre o projeto\n"
    "  agendar amanhã {slot} reunião de acompanhamento"
)


class SheetReader(Protocol):
    def values(self, cell_range: str) -> list[list[str]]: ...


class ShiftBot:
    def __init__(
        self,
        client,
        settings: Settings,
        sheet: SheetReader,
        pending: PendingRequestStore,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.sheet = sheet
        self.pending = pending
        self.now = now or (lambda: datetime.now(settings.timezone))

    # Registro dos handlers. O telebot usa o primeiro handler que casar, então a ordem importa.
    def register(self) -> None:
        handlers = [
            (self.start, {"commands": ["start"]}),
            (self.help, {"commands": ["ajuda", "help"]}),
            (self.about, {"commands": ["sobre"]}),
            (self.schedule_help, {"commands": ["agendar"]}),
            (self.list_team, {"commands": ["equipe"]}),
            (self.list_managers, {"commands": ["gestores"]}),
            (self.roster_help, {"commands": ["escalas", "horarios"]}),
            (self.schedule, {"func": lambda m: _first_word(m) == "agendar"}),
            (self.send_roster_image, {"func": lambda m: _first_word(m) in ROSTER_WORDS}),
            (self.answer_request, {"func": self._is_member_answer}),
            (self.chat, {"func": lambda m: True, "content_types": ["text"]}),
        ]
        for handler, filters in handlers:
            self.client.message_handler(**filters)(self._logged(handler))

    def notify_admin(self, text: str) -> None:
        try:
            self.client.send_message(self.settings.admin.id, text)
        except Exception:
            logger.exception("Não foi possível avisar o administrador")

    # Comandos
    def start(self, message) -> None:
        self.client.reply_to(message, f"Olá! Aqui é o {self.settings.bot_name}.\n\n{self._help_text()}")

    def help(self, message) -> None:
        self.client.reply_to(message, self._help_text())

    def about(self, message) -> None:
        text = self.settings.about_text or (
            f"{self.settings.bot_name}: consulta a escala de plantão e encaminha pedidos de atendimento."
        )
        self.client.reply_to(message, text)

    def schedule_help(self, message) -> None:
        if self._reply_if_closed(message):
            return
        self.client.reply_to(message, self._schedule_help())

    def list_team(self, message) -> None:
        try:
            names = unique_names(self.sheet.values(self.settings.schedule_range), self.settings.slots)
        except SheetsError as error:
            self.client.reply_to(message, str(error))
            return
        self.client.reply_to(message, _numbered("Equipe de plantão:", names))

    def list_managers(self, message) -> None:
        if not self.settings.managers_range:
            self.client.reply_to(message, "A lista de gestores não está configurada.")
            return
        try:
            rows = self.sheet.values(self.settings.managers_range)
        except SheetsError as error:
            self.client.reply_to(message, str(error))
            return
        names = sorted({cell.strip() for row in rows for cell in row if cell.strip()}, key=str.casefold)
        self.client.reply_to(message, _numbered("Gestores:", names))

    def roster_help(self, message) -> None:
        names = [image.stem for image in self._roster_images()]
        if not names:
            self.client.reply_to(message, "Nenhuma imagem de escala foi cadastrada.")
            return
        options = "\n".join(f"  escala {name}" for name in names)
        self.client.reply_to(message, f"Envie a escala desejada:\n{options}")

    def send_roster_image(self, message) -> None:
        parts = message.text.split()
        wanted = parts[1].lower() if len(parts) > 1 else ""
        image = next((image for image in self._roster_images() if image.stem.lower() == wanted), None)
        if image is None:
            self.roster_help(message)
            return
        with image.open("rb") as photo:
            self.client.send_photo(message.chat.id, photo)

    def schedule(self, message) -> None:
        if self._reply_if_closed(message):
            return
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            self.client.reply_to(message, "Formato inválido.\n\n" + self._schedule_help())
            return
        _, day_text, time_text, content = parts

        try:
            request = build_request(
                day_text, time_text, self.now(), self.settings.slots, self.settings.closed_periods
            )
            names = on_duty(self.sheet.values(self.settings.schedule_range), request)
        except (ScheduleError, SheetsError) as error:
            self.client.reply_to(message, str(error))
            return

        recipients = [user for name in names if (user := self.settings.find_user_by_name(name))]
        if not recipients:
            self.client.reply_to(message, "Não há ninguém de plantão neste horário. Tente outro horário.")
            return

        requester = _display_name(message.from_user)
        when = describe(request)
        self.pending.add(
            requester_chat_id=message.chat.id,
            requester_name=requester,
            when=when,
            content=content,
            recipients=[user.name for user in recipients],
        )
        for user in recipients:
            self.client.send_message(
                user.id,
                f"Olá, {user.name}! {requester} quer agendar um atendimento com você em {when}.\n"
                f"Assunto: {content}\n\nResponda sim ou não.",
            )
        self.client.reply_to(message, "Pedido enviado a quem está de plantão. Você receberá a resposta por aqui.")

    def answer_request(self, message) -> None:
        user = self.settings.find_user_by_id(message.from_user.id)
        request = self.pending.pop_oldest_for(user.name)
        if request is None:
            self.client.reply_to(message, "Não há pedidos de agendamento aguardando sua resposta.")
            return

        accepted = message.text.strip().lower() in YES
        result = "aceitou" if accepted else "não pôde aceitar"
        self.client.send_message(
            request.requester_chat_id,
            f"Olá, {request.requester_name}! {user.name} {result} o seu pedido para {request.when}.\n"
            f"Assunto: {request.content}",
        )
        self.client.reply_to(message, "Resposta enviada. Obrigado!")

    def chat(self, message) -> None:
        self.client.reply_to(message, small_talk.reply_to(message.text, self.settings.bot_name))

    # Auxiliares
    def _help_text(self) -> str:
        lines = [
            "Comandos disponíveis:",
            "/agendar - Explica como agendar um atendimento",
            "/escalas - Exibe as escalas de plantão",
            "/equipe - Lista quem participa da escala",
        ]
        if self.settings.managers_range:
            lines.append("/gestores - Lista os gestores")
        lines += ["/sobre - Informações sobre o bot", "/ajuda - Exibe esta mensagem"]
        return "\n".join(lines)

    def _schedule_help(self) -> str:
        return SCHEDULE_HELP.format(slot=list(self.settings.slots.starts)[-1])

    def _roster_images(self) -> list[Path]:
        folder = self.settings.schedule_images_dir
        return sorted(folder.glob("*.png")) if folder.is_dir() else []

    def _is_member_answer(self, message) -> bool:
        text = (message.text or "").strip().lower()
        return text in YES | NO and self.settings.find_user_by_id(message.from_user.id) is not None

    def _reply_if_closed(self, message) -> bool:
        period = closed_period_for(self.now().date(), self.settings.closed_periods)
        if period is None:
            return False
        text = f"Os agendamentos estão suspensos {period.describe()}."
        if self.settings.urgent_contact:
            text += f"\n\nCaso seja urgente: {self.settings.urgent_contact}"
        self.client.reply_to(message, text)
        return True

    def _logged(self, handler):
        def wrapper(message):
            logger.info("%s: chat=%s", handler.__name__, message.chat.id)
            if self.settings.forward_messages_to_admin and message.chat.id != self.settings.admin.id:
                self.notify_admin(f"{_display_name(message.from_user)}: {message.text}")
            try:
                handler(message)
            except Exception:
                logger.exception("Erro ao tratar a mensagem")
                self.client.reply_to(message, "Ocorreu um erro inesperado. Tente novamente mais tarde.")

        wrapper.__name__ = handler.__name__
        return wrapper


def _first_word(message) -> str:
    text = (message.text or "").strip().lower()
    return text.split(maxsplit=1)[0] if text else ""


def _display_name(user) -> str:
    name = " ".join(part for part in (user.first_name, user.last_name) if part)
    if user.username:
        return f"{name} (@{user.username})" if name else f"@{user.username}"
    return name or str(user.id)


def _numbered(title: str, names: list[str]) -> str:
    if not names:
        return f"{title}\nNenhum nome encontrado na planilha."
    return title + "\n" + "\n".join(f"  {index}. {name}" for index, name in enumerate(names, start=1))
