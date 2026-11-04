import unittest
from datetime import date

from bot.calendar_rules import PeriodError, closed_period_for, is_weekend, parse_periods


class ClosedPeriodTest(unittest.TestCase):
    def setUp(self):
        self.periods = parse_periods("22/12-14/01=recesso; 15/07-31/07")

    def test_period_crossing_new_year(self):
        for day in (date(2026, 12, 22), date(2026, 12, 31), date(2027, 1, 1), date(2027, 1, 14)):
            with self.subTest(day=day):
                self.assertEqual(closed_period_for(day, self.periods).label, "recesso")

    def test_period_within_the_year(self):
        self.assertIsNotNone(closed_period_for(date(2026, 7, 20), self.periods))

    def test_outside_periods(self):
        for day in (date(2026, 12, 21), date(2027, 1, 15), date(2026, 8, 1)):
            with self.subTest(day=day):
                self.assertIsNone(closed_period_for(day, self.periods))

    def test_describe(self):
        self.assertEqual(self.periods[0].describe(), "de 22/12 a 14/01 (recesso)")
        self.assertEqual(self.periods[1].describe(), "de 15/07 a 31/07")

    def test_empty_and_invalid(self):
        self.assertEqual(parse_periods(""), ())
        for raw in ("22/12", "32/12-01/01", "22-12/01/01", "29/02-30/02"):
            with self.subTest(raw=raw), self.assertRaises(PeriodError):
                parse_periods(raw)

    def test_leap_day_is_accepted(self):
        self.assertEqual(len(parse_periods("29/02-01/03")), 1)

    def test_weekend(self):
        self.assertTrue(is_weekend(date(2026, 11, 7)))  # sábado
        self.assertFalse(is_weekend(date(2026, 11, 6)))  # sexta


if __name__ == "__main__":
    unittest.main()
