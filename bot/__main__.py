"""Ponto de entrada: python -m bot"""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv
from telebot import TeleBot

from bot.config import ConfigError, Settings
from bot.pending_requests import PendingRequestStore
from bot.sheets import ScheduleSheet
from bot.telegram_bot import ShiftBot

logger = logging.getLogger("bot")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()

    try:
        settings = Settings.from_env()
    except ConfigError as error:
        logger.error("%s", error)
        return 1

    client = TeleBot(settings.telegram_token, parse_mode=None)
    bot = ShiftBot(
        client=client,
        settings=settings,
        sheet=ScheduleSheet(settings.spreadsheet_id, settings.google_client_secret, settings.google_token),
        pending=PendingRequestStore(settings.pending_requests_file),
    )
    bot.register()
    bot.notify_admin("Bot iniciado.")
    logger.info("Bot iniciado")

    try:
        # infinity_polling reconecta sozinho após falhas de rede.
        client.infinity_polling(timeout=20, long_polling_timeout=20)
    finally:
        bot.notify_admin("Bot finalizado.")
        logger.info("Bot finalizado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
