import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from format import format_money


class FormatMoneyTest(unittest.TestCase):
    def test_renders_dollars(self) -> None:
        self.assertEqual("$12.34", format_money(1234))

    def test_renders_negative_yuan(self) -> None:
        self.assertEqual("-\u00a59.00", format_money(-900, "CNY"))

    def test_unknown_currency_falls_back_to_code(self) -> None:
        self.assertEqual("CHF 1.00", format_money(100, "CHF"))


if __name__ == "__main__":
    unittest.main()
