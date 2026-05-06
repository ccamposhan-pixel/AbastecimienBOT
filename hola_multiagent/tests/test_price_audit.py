from __future__ import annotations

from hola_multiagent.agents.price_audit import PriceAuditAgent


def test_price_audit_detects_deviation_duplicate_and_uom(dataframes):
    agent = PriceAuditAgent()
    anomalies = agent.detect_anomalies(
        dataframes["purchase_orders"],
        dataframes["homologation"],
    )
    anomaly_types = set(anomalies["anomaly_type"])
    assert "PRECIO_DESVIADO" in anomaly_types
    assert "DUPLICADO" in anomaly_types
    assert "UOM_MISMATCH" in anomaly_types
    assert anomalies["estimated_impact_CLP"].iloc[0] >= anomalies["estimated_impact_CLP"].iloc[-1]
