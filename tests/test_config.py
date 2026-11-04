import unittest
from pathlib import Path

from bot.config import PROJECT_ROOT, ConfigError, Settings, parse_users

ENV = {
    "TELEGRAM_TOKEN": "123:abc",
    "USERS": "10:Ana:admin, 20:Bruno:membro",
    "SPREADSHEET_ID": "planilha",
    "SCHEDULE_RANGE": "Escala!A2:F10",
}


class ParseUsersTest(unittest.TestCase):
    def test_parses_users(self):
        users = parse_users("10:Ana:admin,20:Bruno Lima:membro,")
        self.assertEqual(
            [(u.id, u.name, u.role) for u in users],
            [(10, "Ana", "admin"), (20, "Bruno Lima", "membro")],
        )

    def test_invalid_entries(self):
        for raw in ("", "10:Ana", "abc:Ana:admin", "10:Ana:chefe"):
            with self.subTest(raw=raw), self.assertRaises(ConfigError):
                parse_users(raw)


class SettingsTest(unittest.TestCase):
    def test_defaults(self):
        settings = Settings.from_env(ENV)
        self.assertEqual(settings.admin.name, "Ana")
        self.assertEqual(settings.pending_requests_file, PROJECT_ROOT / "data" / "pending_requests.json")
        self.assertEqual(str(settings.timezone), "America/Sao_Paulo")
        self.assertEqual(list(settings.slots.starts)[0], "M12")
        self.assertEqual(settings.closed_periods, ())
        self.assertEqual(settings.bot_name, "Bot de Plantão")
        self.assertFalse(settings.forward_messages_to_admin)

    def test_custom_texts_slots_and_periods(self):
        env = {
            **ENV,
            "SLOTS": "manha=08:00,tarde=13:00",
            "SLOTS_END": "18:00",
            "CLOSED_PERIODS": "22/12-06/01=férias coletivas",
            "BOT_NAME": "Plantão TI",
            "ABOUT_TEXT": "Linha 1\\nLinha 2",
        }
        settings = Settings.from_env(env)
        self.assertEqual(list(settings.slots.starts), ["MANHA", "TARDE"])
        self.assertEqual(settings.closed_periods[0].label, "férias coletivas")
        self.assertEqual(settings.bot_name, "Plantão TI")
        self.assertEqual(settings.about_text, "Linha 1\nLinha 2")

    def test_invalid_optional_values(self):
        for name, value in (("SLOTS", "manha"), ("CLOSED_PERIODS", "01/13-02/13"), ("TIMEZONE", "Lua/Base")):
            with self.subTest(name=name), self.assertRaises(ConfigError):
                Settings.from_env({**ENV, name: value})

    def test_absolute_paths_and_flags(self):
        env = {**ENV, "SCHEDULE_IMAGES_DIR": "/srv/imagens", "FORWARD_MESSAGES_TO_ADMIN": "true"}
        settings = Settings.from_env(env)
        self.assertEqual(settings.schedule_images_dir, Path("/srv/imagens"))
        self.assertTrue(settings.forward_messages_to_admin)

    def test_missing_variable(self):
        with self.assertRaisesRegex(ConfigError, "TELEGRAM_TOKEN"):
            Settings.from_env({k: v for k, v in ENV.items() if k != "TELEGRAM_TOKEN"})

    def test_requires_admin(self):
        with self.assertRaisesRegex(ConfigError, "admin"):
            Settings.from_env({**ENV, "USERS": "20:Bruno:membro"})

    def test_find_user(self):
        settings = Settings.from_env(ENV)
        self.assertEqual(settings.find_user_by_name(" bruno ").id, 20)
        self.assertEqual(settings.find_user_by_id(10).name, "Ana")
        self.assertIsNone(settings.find_user_by_id(99))


if __name__ == "__main__":
    unittest.main()
