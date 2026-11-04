import json
import tempfile
import unittest
from pathlib import Path

from bot.pending_requests import PendingRequestStore


class PendingRequestStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "data" / "pending.json"
        self.store = PendingRequestStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, requester: str, recipients: list[str]):
        return self.store.add(1, requester, "03/11/2026 às 15:00", "assunto", recipients)

    def test_empty_store(self):
        self.assertIsNone(self.store.pop_oldest_for("Ana"))

    def test_pops_oldest_request_for_that_person(self):
        first = self.add("Maria", ["Bruno"])
        second = self.add("João", ["Ana", "Bruno"])
        third = self.add("Lia", ["Ana"])

        self.assertEqual(self.store.pop_oldest_for("ana").id, second.id)
        self.assertEqual(self.store.pop_oldest_for("Ana").id, third.id)
        self.assertIsNone(self.store.pop_oldest_for("Ana"))
        self.assertEqual(self.store.pop_oldest_for("Bruno").id, first.id)

    def test_persists_utf8_json(self):
        self.add("Conceição", ["Ana"])
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data[0]["requester_name"], "Conceição")
        self.assertFalse(self.path.with_suffix(".tmp").exists())


if __name__ == "__main__":
    unittest.main()
