from __future__ import annotations

import pandas as pd

from hola_multiagent.agents.pharma_representative import PharmaRepresentativeAgent


def test_pharma_representative_keeps_bridion_out_of_generic_target():
    agent = PharmaRepresentativeAgent()
    purchases = pd.DataFrame(
        [
            {
                "NOMBRE_PRODUCTO": "SUGAMMADEX 200MG/2ML FCO. AMP.",
                "CANTIDAD_FACTURA": 10,
                "PUNIT": 24500,
                "PTOTAL": 245000,
                "NOMBRE_PROVEEDOR_HOMOLOGADO": "SYNTHON CHILE",
                "CLINICA": "CONCEPCION",
            },
            {
                "NOMBRE_PRODUCTO": "SUGAMMADEX 200MG FRASCO AMPOLLA (BRIDION)",
                "CANTIDAD_FACTURA": 10,
                "PUNIT": 45000,
                "PTOTAL": 450000,
                "NOMBRE_PROVEEDOR_HOMOLOGADO": "MERCK SHARP",
                "CLINICA": "CONCEPCION",
            },
        ]
    )

    result = agent.sugammadex_opportunity(purchases, target_non_bridion=19500)

    generic = result[result["segmento"] == "NO_BRIDION_TARGET"].iloc[0]
    bridion = result[result["segmento"] == "BRIDION_PROTEGIDO"].iloc[0]
    assert generic["ahorro_estimado_clp"] == 50000
    assert pd.isna(bridion["target"])
    assert bridion["ahorro_estimado_clp"] == 0


def test_pharma_representative_summarizes_vademecum():
    agent = PharmaRepresentativeAgent()
    vademecum = pd.DataFrame(
        [
            {
                "Registro ISP": "F-1",
                "Vigencia": "Vigente",
                "Nombre generico": "SUGAMMADEX",
                "Codigo ATC": "V03AB35",
                "Equivalencia": "EQUIVALENTE TERAPEUTICO",
            }
        ]
    )

    summary = agent.vademecum_summary(vademecum)

    values = dict(zip(summary["indicador"], summary["valor"]))
    assert values["registros_total"] == 1
    assert values["registros_vigentes"] == 1
    assert values["con_nombre_generico"] == 1
