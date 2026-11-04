"""Interpretação de datas e horários e consulta à escala da planilha.

A escala vem da planilha como uma lista de linhas: a primeira coluna é o código do turno e as
cinco seguintes, segunda a sexta. Uma célula com "X" significa que não há ninguém de plantão;
vários nomes vêm separados por "/".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from bot.calendar_rules import ClosedPeriod, closed_period_for, is_weekend

MIN_ADVANCE = timedelta(hours=2)
EMPTY_CELL = "X"

# Padrão: turnos de aula de 50 min usados em muitas universidades (M12 = manhã, 1º e 2º horários).
DEFAULT_SLOTS = "M12=07:00,M34=08:55,M56=10:50,T12=13:00,T34=14:55,T56=16:50,N12=18:45,N34=20:35"
DEFAULT_SLOTS_END = "22:15"


class ScheduleError(ValueError):
    """Pedido de agendamento inválido. A mensagem é exibida ao usuário."""


@dataclass(frozen=True)
class SlotTable:
    """Turnos da escala. Cada turno vai do seu início até o início do próximo (o último, até `end`)."""

    starts: dict[str, time] = field(default_factory=dict)
    end: time = time(23, 59)

    @classmethod
    def parse(cls, raw: str = DEFAULT_SLOTS, end: str = DEFAULT_SLOTS_END) -> SlotTable:
        """Lê turnos no formato "CODIGO=hh:mm", separados por vírgula."""
        starts = {}
        for entry in filter(None, (item.strip() for item in raw.split(","))):
            code, _, start = entry.partition("=")
            code = code.strip().upper()
            if not code or not re.fullmatch(r"\d{1,2}:\d{2}", start.strip()):
                raise ValueError(f'Turno inválido: "{entry}". Use CODIGO=hh:mm.')
            starts[code] = parse_time(start)
        if not starts:
            raise ValueError("Nenhum turno configurado.")
        ordered = dict(sorted(starts.items(), key=lambda item: item[1]))
        end_time = parse_time(end)
        if end_time <= max(ordered.values()):
            raise ValueError("O fim do expediente precisa ser depois do início do último turno.")
        return cls(starts=ordered, end=end_time)

    @property
    def opening(self) -> time:
        return next(iter(self.starts.values()))

    def slot_for(self, at: time) -> str:
        """Turno que contém o horário informado."""
        if at < self.opening or at >= self.end:
            raise ScheduleError(
                f"Fora do horário de atendimento ({self.opening:%H:%M} às {self.end:%H:%M})."
            )
        return [code for code, start in self.starts.items() if at >= start][-1]


@dataclass(frozen=True)
class ScheduleRequest:
    day: date
    at: time | None
    slot: str


def parse_day(text: str, today: date) -> date:
    """Aceita "hoje", "amanhã", "dd/mm" ou "dd/mm/aaaa"."""
    value = text.strip().lower()
    if value == "hoje":
        return today
    if value in ("amanhã", "amanha"):
        return today + timedelta(days=1)

    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", value):
        candidates = [value]
    elif re.fullmatch(r"\d{1,2}/\d{1,2}", value):
        # "05/01" digitado em dezembro se refere ao ano seguinte.
        candidates = [f"{value}/{today.year}", f"{value}/{today.year + 1}"]
    else:
        candidates = []

    parsed = None
    for candidate in candidates:
        try:
            parsed = datetime.strptime(candidate, "%d/%m/%Y").date()
        except ValueError:
            continue
        if len(candidates) == 1 or parsed >= today:
            return parsed
    if parsed is not None:
        return parsed  # data passada; build_request recusa com mensagem própria

    raise ScheduleError("Data inválida. Use hoje, amanhã, dd/mm ou dd/mm/aaaa.")


def parse_time(text: str) -> time:
    """Aceita "14:30", "14h", "14h30" e "14"."""
    match = re.fullmatch(r"(\d{1,2})(?:[:hH](\d{2})?)?", text.strip())
    if not match:
        raise ScheduleError("Horário inválido. Use o formato hh:mm, por exemplo 14:30.")
    hour, minute = int(match.group(1)), int(match.group(2) or 0)
    if hour > 23 or minute > 59:
        raise ScheduleError("Horário inválido. Use o formato hh:mm, por exemplo 14:30.")
    return time(hour, minute)


def build_request(
    day_text: str,
    time_text: str,
    now: datetime,
    slots: SlotTable,
    closed_periods: tuple[ClosedPeriod, ...] = (),
) -> ScheduleRequest:
    """Valida o pedido "agendar <dia> <horário>" em relação ao momento atual."""
    day = parse_day(day_text, now.date())

    if day < now.date():
        raise ScheduleError("Não é possível agendar para uma data passada.")
    if period := closed_period_for(day, closed_periods):
        raise ScheduleError(f"Não há agendamentos {period.describe()}. Por favor, escolha outra data.")
    if is_weekend(day):
        raise ScheduleError("Não há atendimento no fim de semana. Escolha um dia de segunda a sexta.")

    slot_code = time_text.strip().upper()
    if slot_code in slots.starts:
        return ScheduleRequest(day=day, at=None, slot=slot_code)

    at = parse_time(time_text)
    slot = slots.slot_for(at)
    if datetime.combine(day, at) - now.replace(tzinfo=None) < MIN_ADVANCE:
        raise ScheduleError("Agende com pelo menos 2 horas de antecedência.")
    return ScheduleRequest(day=day, at=at, slot=slot)


def on_duty(rows: list[list[str]], request: ScheduleRequest) -> list[str]:
    """Pessoas de plantão no turno e no dia do pedido. Lista vazia se não houver."""
    column = request.day.weekday() + 1  # coluna 0 é o turno; 1 a 5, segunda a sexta
    for row in rows:
        if not row or row[0].strip().upper() != request.slot:
            continue
        cell = row[column].strip() if column < len(row) else ""
        if not cell or cell.upper() == EMPTY_CELL:
            return []
        return [name.strip() for name in cell.split("/") if name.strip()]
    return []


def unique_names(rows: list[list[str]], slots: SlotTable) -> list[str]:
    """Todos os nomes que aparecem na escala, sem repetição e em ordem alfabética."""
    names = set()
    for row in rows:
        if not row or row[0].strip().upper() not in slots.starts:
            continue
        for cell in row[1:6]:
            if cell.strip().upper() == EMPTY_CELL:
                continue
            names.update(name.strip() for name in cell.split("/") if name.strip())
    return sorted(names, key=str.casefold)


def describe(request: ScheduleRequest) -> str:
    when = request.at.strftime("%H:%M") if request.at else request.slot
    return f"{request.day.strftime('%d/%m/%Y')} às {when}"
