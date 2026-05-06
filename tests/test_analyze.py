import unittest

from procurement_agent.analyze import analyze_records
from procurement_agent.ingest import RawTable
from procurement_agent.standardize import standardize_tables


class AnalyzeTests(unittest.TestCase):
    def test_analysis_finds_price_savings_for_same_code(self):
        table = RawTable(
            source_file="memory.csv",
            rows=[
                {
                    "proveedor": "Proveedor A",
                    "codigo_producto": "ABC",
                    "descripcion": "Insumo ABC",
                    "categoria": "Clinico",
                    "cantidad": "10",
                    "unidad": "unidad",
                    "precio_unitario": "100",
                    "moneda": "CLP",
                },
                {
                    "proveedor": "Proveedor B",
                    "codigo_producto": "ABC",
                    "descripcion": "Insumo ABC",
                    "categoria": "Clinico",
                    "cantidad": "10",
                    "unidad": "unidad",
                    "precio_unitario": "150",
                    "moneda": "CLP",
                },
            ],
        )

        standardized = standardize_tables([table])
        result = analyze_records(standardized.records)

        self.assertEqual(len(result.item_opportunities), 1)
        self.assertEqual(result.item_opportunities[0].potential_savings_clp, 500.0)
        self.assertEqual(result.item_opportunities[0].best_supplier, "Proveedor A")


if __name__ == "__main__":
    unittest.main()
