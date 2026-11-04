"""Períodos sem agendamento (recesso, férias, horário reduzido) e dias úteis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


class PeriodError(ValueError):
    """Período mal configurado."""


@dataclass(frozen=True)
class ClosedPeriod:
    """Intervalo anual sem agendamento, de start a end (dia e mês), podendo atravessar a virada do ano."""

    start: tuple[int, int]  # (mês, dia)
    end: tuple[int, int]
    label: str = ""

    def contains(self, day: date) -> bool:
        current = (day.month, day.day)
        if self.start <= self.end:
            return self.start <= current <= self.end
        return current >= self.start or current <= self.end

    def describe(self) -> str:
        text = f"de {_format(self.start)} a {_format(self.end)}"
        return f"{text} ({self.label})" if self.label else text


def parse_periods(raw: str) -> tuple[ClosedPeriod, ...]:
    """Lê períodos no formato "dd/mm-dd/mm=rótulo", separados por ponto e vírgula.

    Exemplo: "22/12-14/01=recesso;15/01-23/02=horário reduzido". O rótulo é opcional.
    """
    periods = []
    for entry in filter(None, (item.strip() for item in raw.split(";"))):
        span, _, label = entry.partition("=")
        match = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})\s*", span)
        if not match:
            raise PeriodError(f'Período inválido: "{entry}". Use dd/mm-dd/mm=rótulo.')
        start_day, start_month, end_day, end_month = map(int, match.groups())
        for day, month in ((start_day, start_month), (end_day, end_month)):
            try:
                date(2024, month, day)  # ano bissexto, para aceitar 29/02
            except ValueError as error:
                raise PeriodError(f'Data inválida no período "{entry}".') from error
        periods.append(ClosedPeriod((start_month, start_day), (end_month, end_day), label.strip()))
    return tuple(periods)


def closed_period_for(day: date, periods: tuple[ClosedPeriod, ...]) -> ClosedPeriod | None:
    return next((period for period in periods if period.contains(day)), None)


def is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def _format(month_day: tuple[int, int]) -> str:
    month, day = month_day
    return f"{day:02d}/{month:02d}"
