import unittest
from datetime import date, datetime, time

from bot.calendar_rules import parse_periods
from bot.schedule import (
    ScheduleError,
    ScheduleRequest,
    SlotTable,
    build_request,
    describe,
    on_duty,
    parse_day,
    parse_time,
    unique_names,
)
from tests.helpers import ROWS, SLOTS, TZ

# Terça-feira, 03/11/2026, 09:00
NOW = datetime(2026, 11, 3, 9, 0, tzinfo=TZ)
CLOSED = parse_periods("22/12-14/01=recesso")


def request(day, at, now=NOW):
    return build_request(day, at, now, SLOTS, CLOSED)


class ParseDayTest(unittest.TestCase):
    def test_relative_words(self):
        self.assertEqual(parse_day("hoje", NOW.date()), date(2026, 11, 3))
        self.assertEqual(parse_day("Amanhã", NOW.date()), date(2026, 11, 4))
        self.assertEqual(parse_day("amanha", NOW.date()), date(2026, 11, 4))

    def test_day_and_month(self):
        self.assertEqual(parse_day("10/11", NOW.date()), date(2026, 11, 10))

    def test_full_date_returns_date(self):
        self.assertEqual(parse_day("10/11/2026", NOW.date()), date(2026, 11, 10))

    def test_past_day_and_month_rolls_to_next_year(self):
        self.assertEqual(parse_day("20/01", date(2026, 12, 15)), date(2027, 1, 20))

    def test_invalid(self):
        for text in ("32/01", "amanhãzinho", "2026-11-10"):
            with self.subTest(text=text), self.assertRaises(ScheduleError):
                parse_day(text, NOW.date())


class ParseTimeTest(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(parse_time("14:30"), time(14, 30))
        self.assertEqual(parse_time("14h"), time(14, 0))
        self.assertEqual(parse_time("14h30"), time(14, 30))
        self.assertEqual(parse_time("9"), time(9, 0))

    def test_invalid(self):
        for text in ("25:00", "14:75", "meio-dia", "14:3"):
            with self.subTest(text=text), self.assertRaises(ScheduleError):
                parse_time(text)


class SlotTableTest(unittest.TestCase):
    def test_default_slot_boundaries(self):
        self.assertEqual(SLOTS.slot_for(time(7, 0)), "M12")
        self.assertEqual(SLOTS.slot_for(time(8, 54)), "M12")
        self.assertEqual(SLOTS.slot_for(time(8, 55)), "M34")
        self.assertEqual(SLOTS.slot_for(time(15, 0)), "T34")
        self.assertEqual(SLOTS.slot_for(time(22, 0)), "N34")

    def test_outside_working_hours(self):
        for value in (time(6, 59), time(22, 15), time(23, 0)):
            with self.subTest(value=value), self.assertRaisesRegex(ScheduleError, "07:00 às 22:15"):
                SLOTS.slot_for(value)

    def test_custom_slots_are_sorted(self):
        slots = SlotTable.parse("tarde=13:00, manha=08:00", "18:00")
        self.assertEqual(list(slots.starts), ["MANHA", "TARDE"])
        self.assertEqual(slots.slot_for(time(12, 59)), "MANHA")
        self.assertEqual(slots.slot_for(time(17, 0)), "TARDE")

    def test_invalid_slots(self):
        for raw, end in (("", "18:00"), ("manha", "18:00"), ("manha=8h", "18:00"), ("manha=08:00", "07:00")):
            with self.subTest(raw=raw, end=end), self.assertRaises(ValueError):
                SlotTable.parse(raw, end)


class BuildRequestTest(unittest.TestCase):
    def test_valid_request(self):
        self.assertEqual(request("hoje", "15:00"), ScheduleRequest(day=date(2026, 11, 3), at=time(15, 0), slot="T34"))

    def test_slot_code_is_accepted(self):
        result = request("amanhã", "t34")
        self.assertEqual(result.slot, "T34")
        self.assertIsNone(result.at)

    def test_needs_two_hours_in_advance_on_the_same_day(self):
        with self.assertRaisesRegex(ScheduleError, "2 horas"):
            request("hoje", "10:30")

    def test_other_day_ignores_current_hour(self):
        # Antes, a antecedência era checada só pela hora, ignorando a data.
        self.assertEqual(request("amanhã", "07:30").slot, "M12")

    def test_past_date(self):
        with self.assertRaisesRegex(ScheduleError, "passada"):
            request("02/11/2026", "15:00")

    def test_weekend(self):
        with self.assertRaisesRegex(ScheduleError, "fim de semana"):
            request("07/11", "15:00")

    def test_recess(self):
        with self.assertRaisesRegex(ScheduleError, "de 22/12 a 14/01 \\(recesso\\)"):
            request("05/01/2027", "15:00")

    def test_describe(self):
        self.assertEqual(describe(request("hoje", "15:00")), "03/11/2026 às 15:00")
        self.assertEqual(describe(request("amanhã", "M34")), "04/11/2026 às M34")


class SheetLookupTest(unittest.TestCase):
    def lookup(self, day: date, slot: str) -> list[str]:
        return on_duty(ROWS, ScheduleRequest(day=day, at=None, slot=slot))

    def test_single_person(self):
        self.assertEqual(self.lookup(date(2026, 11, 2), "M12"), ["Ana"])  # segunda

    def test_multiple_people(self):
        self.assertEqual(self.lookup(date(2026, 11, 5), "M12"), ["Ana", "Bruno"])
        self.assertEqual(self.lookup(date(2026, 11, 3), "T34"), ["Bruno", "Ana"])

    def test_empty_cell(self):
        self.assertEqual(self.lookup(date(2026, 11, 3), "M12"), [])

    def test_missing_slot_or_short_row(self):
        self.assertEqual(self.lookup(date(2026, 11, 3), "N34"), [])
        self.assertEqual(self.lookup(date(2026, 11, 6), "N12"), [])  # linha curta

    def test_unique_names_ignores_headers_and_x(self):
        self.assertEqual(unique_names(ROWS, SLOTS), ["Ana", "Bruno", "Carla"])


if __name__ == "__main__":
    unittest.main()
