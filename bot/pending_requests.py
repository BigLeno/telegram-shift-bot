"""Pedidos de agendamento aguardando resposta de quem está de plantão, guardados num arquivo JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class PendingRequest:
    id: str
    requester_chat_id: int
    requester_name: str
    when: str
    content: str
    recipients: list[str]


class PendingRequestStore:
    """Fila de pedidos. Cada pedido é fechado pela primeira pessoa de plantão que aceitar ou recusar."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def add(self, requester_chat_id: int, requester_name: str, when: str,
            content: str, recipients: list[str]) -> PendingRequest:
        request = PendingRequest(
            id=str(uuid4()),
            requester_chat_id=requester_chat_id,
            requester_name=requester_name,
            when=when,
            content=content,
            recipients=recipients,
        )
        items = self._load()
        items.append(asdict(request))
        self._save(items)
        return request

    def pop_oldest_for(self, name: str) -> PendingRequest | None:
        """Remove e devolve o pedido mais antigo destinado a esta pessoa."""
        items = self._load()
        wanted = name.casefold()
        for index, item in enumerate(items):
            if wanted in (recipient.casefold() for recipient in item["recipients"]):
                del items[index]
                self._save(items)
                return PendingRequest(**item)
        return None

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as file:
            return json.load(file)

    def _save(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(items, file, ensure_ascii=False, indent=2)
        temporary.replace(self.path)  # troca atômica: o arquivo nunca fica pela metade
