import json
import tempfile
import unittest
from pathlib import Path

from procurement_agent.chief import ProcurementArtifacts, ChiefProcurementAgent, run_chief_review


class ChiefAgentTests(unittest.TestCase):
    def test_chief_generates_review_and_flags_high_pressure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "andes_refined_summary.json").write_text(
                json.dumps(
                    {
                        "total_spend": 1000000,
                        "objective_price_savings": 100000,
                        "desat_3pct": 30000,
                        "proposal_defensible": 130000,
                        "desc_h_spend": 50000,
                        "jfv_spend": 40000,
                    }
                ),
                encoding="utf-8",
            )
            (root / "andes_supplier_targets_refined.csv").write_text(
                "supplier,total_spend,addressable_spend,objective_savings,pressure_pct_addressable,top_products\n"
                "Proveedor A,500000,100000,55000,0.55,Producto foco\n",
                encoding="utf-8",
            )
            (root / "andes_product_savings_refined.csv").write_text(
                "product,family,key_type,suppliers,clinics,objective_savings\n"
                "Producto foco,Insumos,SKU clinica,2,1,55000\n",
                encoding="utf-8",
            )
            (root / "andes_desatomization_refined.csv").write_text(
                "family,total_spend,supplier_count,target_supplier_count,tail_spend,target_3pct,candidates\n"
                "Sin familia homologada,300000,20,5,100000,3000,Proveedor A\n",
                encoding="utf-8",
            )

            artifacts = ProcurementArtifacts.load(root)
            review = ChiefProcurementAgent().review(artifacts, "Validar ahorro")

            self.assertIn("Aprobado condicionado", review.verdict)
            self.assertTrue(any("presion alta" in finding.message for finding in review.findings))
            self.assertTrue(review.decisions)

    def test_run_chief_review_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "andes_refined_summary.json").write_text(
                json.dumps({"total_spend": 1000, "objective_price_savings": 10}),
                encoding="utf-8",
            )
            (root / "andes_supplier_targets_refined.csv").write_text(
                "supplier,total_spend,addressable_spend,objective_savings,pressure_pct_addressable,top_products\n",
                encoding="utf-8",
            )
            (root / "andes_product_savings_refined.csv").write_text(
                "product,family,key_type,suppliers,clinics,objective_savings\n",
                encoding="utf-8",
            )
            (root / "andes_desatomization_refined.csv").write_text(
                "family,total_spend,supplier_count,target_supplier_count,tail_spend,target_3pct,candidates\n",
                encoding="utf-8",
            )

            paths = run_chief_review(root, root, "Test")

            self.assertTrue(paths["memo"].exists())
            self.assertTrue(paths["minutes_json"].exists())


if __name__ == "__main__":
    unittest.main()
