from __future__ import annotations

from hola_multiagent.agents.materials_analyst import MaterialsAnalystAgent


def test_materials_classifies_seed_dictionary(dataframes):
    agent = MaterialsAnalystAgent()
    enriched = agent.enrich_catalog(dataframes["homologation"])
    assert enriched.loc[enriched["sku"] == "SKU-0003", "criticality"].iloc[0] == "CRITICO"
    assert enriched.loc[enriched["sku"] == "SKU-0041", "criticality"].iloc[0] == "GENERAL"
    assert enriched.loc[enriched["sku"] == "SKU-0053", "criticality"].iloc[0] == "PENDIENTE"


def test_materials_validation_flags_missing_and_duplicates(dataframes):
    agent = MaterialsAnalystAgent()
    enriched = agent.enrich_catalog(dataframes["homologation"])
    report = agent.validation_report(enriched)
    assert "CATEGORIA_NULA" in set(report["reason"])
    assert "PRECIO_NULO" in set(report["reason"])
    assert "SKU_DUPLICADO_POTENCIAL" in set(report["reason"])
