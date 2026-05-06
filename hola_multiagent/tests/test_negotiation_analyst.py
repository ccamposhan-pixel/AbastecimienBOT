from __future__ import annotations

from hola_multiagent.agents.negotiation_analyst import NegotiationAnalystAgent


def test_negotiation_returns_ranked_opportunities(dataframes):
    agent = NegotiationAnalystAgent()
    opportunities = agent.find_opportunities(
        dataframes["purchase_orders"],
        dataframes["homologation"],
        dataframes["consumption"],
    )
    assert not opportunities.empty
    assert opportunities["estimated_savings_CLP"].iloc[0] >= opportunities["estimated_savings_CLP"].iloc[-1]
    assert "CONSOLIDACION_DE_VOLUMEN" in set(opportunities["opportunity_type"])
