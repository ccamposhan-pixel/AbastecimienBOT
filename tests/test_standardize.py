import unittest

from procurement_agent.ingest import RawTable
from procurement_agent.standardize import parse_number, standardize_tables


class StandardizeTests(unittest.TestCase):
    def test_parse_number_handles_chilean_and_decimal_formats(self):
        self.assertEqual(parse_number("$1.250"), 1250.0)
        self.assertEqual(parse_number("1.250,50"), 1250.5)
        self.assertEqual(parse_number("1,250.50"), 1250.5)
        self.assertEqual(parse_number("95"), 95.0)

    def test_standardize_computes_unit_price_from_total(self):
        table = RawTable(
            source_file="memory.csv",
            rows=[
                {
                    "proveedor": "Proveedor A",
                    "descripcion": "Guante nitrilo M",
                    "cantidad": "10",
                    "unidad": "unidad",
                    "monto": "1000",
                    "moneda": "CLP",
                }
            ],
        )

        result = standardize_tables([table])

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].unit_price_clp_base, 100.0)
        self.assertEqual(result.records[0].total_spend_clp, 1000.0)


if __name__ == "__main__":
    unittest.main()
