import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from bot.pending_requests import PendingRequestStore
from bot.sheets import SheetsError
from bot.telegram_bot import ShiftBot
from tests.helpers import ROWS, TZ, make_settings, message

NOW = datetime(2026, 11, 3, 9, 0, tzinfo=TZ)  # terça-feira


class FakeClient:
    def __init__(self):
        self.handlers = []
        self.sent = []  # (chat_id, texto)

    def message_handler(self, commands=None, func=None, content_types=None):
        def decorator(handler):
            self.handlers.append((commands, func, handler))
            return handler

        return decorator

    def reply_to(self, msg, text):
        self.sent.append((msg.chat.id, text))

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))

    def send_photo(self, chat_id, photo):
        self.sent.append((chat_id, f"<foto {Path(photo.name).name}>"))

    def dispatch(self, msg):
        """Imita o telebot: o primeiro handler que casar trata a mensagem."""
        text = msg.text or ""
        for commands, func, handler in self.handlers:
            if commands:
                if text.startswith("/") and text[1:].split()[0].split("@")[0].lower() in commands:
                    return handler(msg)
            elif func(msg):
                return handler(msg)


class FakeSheet:
    def __init__(self, rows=ROWS, fail=False):
        self.rows, self.fail = rows, fail

    def values(self, cell_range):
        if self.fail:
            raise SheetsError("Não foi possível acessar a planilha. Tente novamente mais tarde.")
        if cell_range == "gestores":
            return [["Gestora Um", "Gestor Dois"], ["Gestor Dois"]]
        return self.rows


class ShiftBotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.settings = make_settings(tmp)
        self.client = FakeClient()
        self.store = PendingRequestStore(self.settings.pending_requests_file)
        self.now = NOW
        self.bot = ShiftBot(self.client, self.settings, FakeSheet(), self.store, now=lambda: self.now)
        self.bot.register()

    def tearDown(self):
        self.tmp.cleanup()

    def send(self, text, **kwargs):
        self.client.sent.clear()
        self.client.dispatch(message(text, **kwargs))
        return self.client.sent

    def test_help_and_start(self):
        [(chat, text)] = self.send("/ajuda")
        self.assertEqual(chat, 99)
        self.assertIn("/agendar", text)
        self.assertIn("/gestores", text)
        [(_, text)] = self.send("/start")
        self.assertIn("Bot Teste", text)

    def test_managers_command_hidden_when_not_configured(self):
        self.bot.settings = make_settings(Path(self.tmp.name), managers_range="")
        [(_, text)] = self.send("/ajuda")
        self.assertNotIn("/gestores", text)
        [(_, text)] = self.send("/gestores")
        self.assertIn("não está configurada", text)

    def test_about_uses_configured_text(self):
        [(_, text)] = self.send("/sobre")
        self.assertIn("Bot Teste", text)
        self.bot.settings = make_settings(Path(self.tmp.name), about_text="Equipe de suporte")
        [(_, text)] = self.send("/sobre")
        self.assertEqual(text, "Equipe de suporte")

    def test_schedule_notifies_people_on_duty(self):
        sent = self.send("agendar hoje 15:00 dúvida sobre o edital", username="maria")
        recipients = [chat for chat, _ in sent]
        self.assertEqual(recipients, [3, 2, 99])  # Bruno, Ana (T34 terça) e a confirmação
        self.assertIn("Maria Silva (@maria) quer agendar", sent[0][1])
        self.assertIn("03/11/2026 às 15:00", sent[0][1])
        self.assertIn("dúvida sobre o edital", sent[0][1])

    def test_schedule_without_anyone_on_duty(self):
        [(_, text)] = self.send("agendar hoje M12 reunião")
        self.assertIn("Não há ninguém de plantão", text)

    def test_schedule_validation_message(self):
        [(_, text)] = self.send("agendar hoje 10:00 reunião")
        self.assertIn("2 horas", text)

    def test_schedule_invalid_format(self):
        [(_, text)] = self.send("agendar amanhã")
        self.assertIn("Formato inválido", text)

    def test_schedule_blocked_during_closed_period(self):
        self.now = datetime(2026, 12, 23, 9, 0, tzinfo=TZ)
        [(_, text)] = self.send("agendar 10/02/2027 15:00 reunião")
        self.assertEqual(text, "Os agendamentos estão suspensos de 22/12 a 14/01 (recesso).")
        self.bot.settings = make_settings(Path(self.tmp.name), urgent_contact="suporte@exemplo.com")
        [(_, text)] = self.send("agendar 10/02/2027 15:00 reunião")
        self.assertIn("Caso seja urgente: suporte@exemplo.com", text)

    def test_member_accepts_request(self):
        self.send("agendar hoje 15:00 mentoria")
        sent = self.send("Sim", user_id=2, first_name="Ana", last_name=None)
        self.assertEqual(sent[0][0], 99)
        self.assertIn("Ana aceitou o seu pedido", sent[0][1])
        self.assertIn("Resposta enviada", sent[1][1])
        # O pedido saiu da fila das duas pessoas
        [(_, text)] = self.send("não", user_id=3, first_name="Bruno")
        self.assertIn("Não há pedidos", text)

    def test_member_declines_request(self):
        self.send("agendar hoje 15:00 mentoria")
        sent = self.send("não", user_id=3, first_name="Bruno")
        self.assertIn("Bruno não pôde aceitar", sent[0][1])

    def test_yes_from_unregistered_user_is_small_talk(self):
        self.send("agendar hoje 15:00 mentoria")
        [(chat, text)] = self.send("sim", user_id=50)
        self.assertEqual(chat, 50)
        self.assertNotIn("Resposta enviada", text)
        self.assertIsNotNone(self.store.pop_oldest_for("Ana"))

    def test_words_containing_sim_do_not_answer_requests(self):
        self.send("agendar hoje 15:00 mentoria")
        self.send("assim não dá", user_id=2)
        self.assertIsNotNone(self.store.pop_oldest_for("Ana"))

    def test_lists(self):
        [(_, text)] = self.send("/equipe")
        self.assertIn("1. Ana\n  2. Bruno\n  3. Carla", text)
        [(_, text)] = self.send("/gestores")
        self.assertIn("1. Gestor Dois\n  2. Gestora Um", text)

    def test_sheet_error_is_reported(self):
        self.bot.sheet = FakeSheet(fail=True)
        [(_, text)] = self.send("/equipe")
        self.assertIn("Não foi possível acessar a planilha", text)

    def test_roster_images(self):
        [(_, text)] = self.send("/escalas")
        self.assertIn("Nenhuma imagem", text)

        self.settings.schedule_images_dir.mkdir()
        for name in ("noite", "manha"):
            (self.settings.schedule_images_dir / f"{name}.png").write_bytes(b"png")
        [(_, text)] = self.send("/escalas")
        self.assertEqual(text, "Envie a escala desejada:\n  escala manha\n  escala noite")
        [(_, text)] = self.send("escala Noite")
        self.assertEqual(text, "<foto noite.png>")
        [(_, text)] = self.send("horarios madrugada")
        self.assertIn("escala manha", text)

    def test_unexpected_error_is_handled(self):
        self.bot.sheet = None
        [(_, text)] = self.send("/equipe")
        self.assertIn("erro inesperado", text)

    def test_forwarding_to_admin_is_opt_in(self):
        self.assertEqual(len(self.send("bom dia")), 1)
        self.bot.settings = make_settings(Path(self.tmp.name), forward_messages_to_admin=True)
        sent = self.send("bom dia")
        self.assertEqual(sent[0], (1, "Maria Silva: bom dia"))


if __name__ == "__main__":
    unittest.main()
