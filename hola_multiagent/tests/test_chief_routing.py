from __future__ import annotations

from hola_multiagent.agents.chief_agent import ChiefAgent


def test_chief_routes_coverage_query():
    chief = ChiefAgent(agents={})
    route = chief._route_with_keywords("revisar stock cobertura y agotamiento")
    assert route["agents"] == ["coverage_planner"]


def test_chief_routes_ambiguous_query_to_multiple_agents():
    chief = ChiefAgent(agents={})
    route = chief._route_with_keywords("hay sobrecosto de precio y oportunidad de ahorro con proveedor")
    assert "price_audit" in route["agents"]
    assert "negotiation_analyst" in route["agents"]


def test_chief_routes_pharma_and_supplies_representatives():
    chief = ChiefAgent(agents={})
    route = chief._route_with_keywords(
        "validar vademecum isp de sugammadex no bridion y propuesta jfv de insumos"
    )
    assert "pharma_representative" in route["agents"]
    assert "supplies_representative" in route["agents"]


def test_chief_keeps_conversation_history(dataframes):
    chief = ChiefAgent()
    response = chief.run("mostrar resumen de datos", context={}, dataframes=dataframes)
    assert "Agentes participantes" in response.output
    assert len(chief.history) == 2
