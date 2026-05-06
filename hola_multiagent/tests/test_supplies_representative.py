from __future__ import annotations

import pandas as pd

from hola_multiagent.agents.supplies_representative import SuppliesRepresentativeAgent


def test_supplies_representative_summarizes_jfv_offer():
    agent = SuppliesRepresentativeAgent()
    revision = pd.DataFrame(
        [
            {
                "NOMBRE_PRODUCTO": "GUANTE PROCEDIMIENTO NITRILO TALLA M",
                "DESC JFV": "Guante nitrilo caja 100",
                "Considerar": True,
                "Conviene": "SI",
                "Ahorro vs minimo": 1000,
                "Ahorro vs promedio": 2500,
            },
            {
                "NOMBRE_PRODUCTO": "CATETER VENOSO CENTRAL",
                "DESC JFV": "Cateter alternativo",
                "Considerar": False,
                "Conviene": "SI",
                "Ahorro vs minimo": 9999,
                "Ahorro vs promedio": 9999,
            },
        ]
    )

    summary = agent.jfv_summary(revision)

    values = dict(zip(summary["indicador"], summary["valor"]))
    assert values["lineas_revision"] == 2
    assert values["lineas_convenientes"] == 1
    assert values["ahorro_vs_promedio_clp"] == 2500


def test_supplies_representative_flags_high_risk_supplies():
    agent = SuppliesRepresentativeAgent()
    revision = pd.DataFrame(
        [
            {
                "NOMBRE_PRODUCTO": "CATETER VENOSO CENTRAL",
                "DESC JFV": "Cateter venoso central esteril",
                "Considerar": True,
                "Conviene": "SI",
                "Relacion precios": 0.8,
                "Ahorro vs promedio": 10000,
            }
        ]
    )

    risk = agent.jfv_risk_review(revision)

    assert risk.iloc[0]["riesgo_tecnico"] == "ALTO"
    assert "ficha tecnica" in risk.iloc[0]["accion_requerida"].lower()
