from __future__ import annotations

from hola_multiagent.agents.coverage_planner import CoveragePlannerAgent


def test_coverage_detects_spike_and_prioritizes_criticality(dataframes):
    agent = CoveragePlannerAgent()
    dashboard = agent.build_dashboard(
        dataframes["stock"],
        dataframes["purchase_orders"],
        dataframes["consumption"],
        dataframes["homologation"],
    )
    spike_skus = set(dashboard.loc[dashboard["spike_flag"], "sku"])
    assert "SKU-0003" in spike_skus
    assert dashboard.iloc[0]["criticality"] == "CRITICO"


def test_coverage_flags_no_movement_open_po(dataframes):
    agent = CoveragePlannerAgent()
    dashboard = agent.build_dashboard(
        dataframes["stock"],
        dataframes["purchase_orders"],
        dataframes["consumption"],
        dataframes["homologation"],
    )
    row = dashboard.loc[dashboard["sku"] == "SKU-0054"].iloc[0]
    assert row["rotation_class"] == "SIN_MOVIMIENTO"
    assert row["purchasing_error_flag"] is True or bool(row["purchasing_error_flag"])
