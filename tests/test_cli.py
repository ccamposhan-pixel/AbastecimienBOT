import unittest

from procurement_agent.cli import parse_fx


class CliTests(unittest.TestCase):
    def test_parse_fx_accepts_local_number_formats(self):
        self.assertEqual(parse_fx("USD=950.5"), {"USD": 950.5})
        self.assertEqual(parse_fx("EUR=950,5"), {"EUR": 950.5})
        self.assertEqual(parse_fx("UF=38.000"), {"UF": 38000.0})


if __name__ == "__main__":
    unittest.main()
