import unittest

from bot import small_talk


class SmallTalkTest(unittest.TestCase):
    def test_known_question_with_typos_and_accents(self):
        self.assertEqual(small_talk.reply_to("Qual o seu nome?", "Plantão TI"), "Sou o Plantão TI!")
        self.assertEqual(small_talk.reply_to("qual o seu nomee", "Plantão TI"), "Sou o Plantão TI!")
        self.assertIn("Bom dia", small_talk.reply_to("BOM DIA!"))

    def test_unknown_text(self):
        self.assertIn("/ajuda", small_talk.reply_to("asdfgh qwerty"))


if __name__ == "__main__":
    unittest.main()
