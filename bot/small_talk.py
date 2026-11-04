"""Respostas para conversa informal, com tolerância a pequenos erros de digitação."""

from __future__ import annotations

import unicodedata
from difflib import get_close_matches

HELP_HINT = "Digite /ajuda para ver o que posso fazer."

ANSWERS = {
    "quem é você": "Sou o {bot_name}. Ajudo a consultar a escala de plantão e a agendar atendimentos.",
    "qual o seu nome": "Sou o {bot_name}!",
    "o que você faz": "Encontro quem está de plantão e envio seu pedido de atendimento. " + HELP_HINT,
    "qual a sua função": "Encontro quem está de plantão e envio seu pedido de atendimento. " + HELP_HINT,
    "como agendar": "Envie: agendar <data> <horário> <assunto>. Por exemplo: agendar amanhã 14:30 reunião.",
    "obrigado": "Por nada! " + HELP_HINT,
    "obrigada": "Por nada! " + HELP_HINT,
    "bom dia": "Bom dia! " + HELP_HINT,
    "boa tarde": "Boa tarde! " + HELP_HINT,
    "boa noite": "Boa noite! " + HELP_HINT,
    "oi": "Olá! " + HELP_HINT,
    "olá": "Olá! " + HELP_HINT,
}

_FALLBACK = "Não entendi. " + HELP_HINT


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.replace("?", " ").replace("!", " ").split())


_NORMALIZED = {_normalize(question): answer for question, answer in ANSWERS.items()}


def reply_to(text: str, bot_name: str = "Bot de Plantão") -> str:
    match = get_close_matches(_normalize(text), _NORMALIZED.keys(), n=1, cutoff=0.75)
    return _NORMALIZED[match[0]].format(bot_name=bot_name) if match else _FALLBACK
