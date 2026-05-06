from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import unicodedata
from typing import Mapping

import pandas as pd

from .base_agent import AgentResponse, BaseAgent
from ..config.settings import Settings, settings as default_settings
from ..llm.providers import client_from_settings


ROUTING_KEYWORDS: dict[str, tuple[str, ...]] = {
    "coverage_planner": (
        "stock",
        "cobertura",
        "agotamiento",
        "lead time",
        "reposicion",
        "reponer",
        "quiebre",
        "sobre stock",
        "sobrestock",
        "inventario",
    ),
    "price_audit": (
        "precio",
        "factura",
        "sobrecosto",
        "desvio",
        "desviacion",
        "error",
        "anomalia",
        "uom",
    ),
    "negotiation_analyst": (
        "ahorro",
        "negociacion",
        "proveedor",
        "descuento",
        "contrato",
        "consolidacion",
    ),
    "database_analyst": (
        "datos",
        "consulta",
        "cuantos",
        "cuantas",
        "lista",
        "tabla",
        "exportar",
        "mostrar",
        "resumen",
    ),
    "materials_analyst": (
        "codigo",
        "material",
        "criticidad",
        "clasificar",
        "validar",
        "clinico",
        "farmaceutico",
    ),
    "pharma_representative": (
        "farmaco",
        "farmacos",
        "medicamento",
        "medicamentos",
        "vademecum",
        "isp",
        "registro sanitario",
        "principio activo",
        "qf",
        "sugammadex",
        "bridion",
        "compuesto",
    ),
    "supplies_representative": (
        "insumo",
        "insumos",
        "enfermeria",
        "ficha tecnica",
        "requerimiento tecnico",
        "jfv",
        "factor empaque",
        "empaque",
        "arthrex",
        "dispositivo",
        "material quirurgico",
    ),
    "email_triage": (
        "correo",
        "correos",
        "email",
        "emails",
        "mail",
        "inbox",
        "buzon",
        "responder correo",
        "respuestas sugeridas",
        "deadline",
        "deadlines",
    ),
}


AGENT_DISPLAY_NAMES: dict[str, str] = {
    "coverage_planner": "CoveragePlannerAgent",
    "price_audit": "PriceAuditAgent",
    "negotiation_analyst": "NegotiationAnalystAgent",
    "database_analyst": "DatabaseAnalystAgent",
    "materials_analyst": "MaterialsAnalystAgent",
    "pharma_representative": "PharmaRepresentativeAgent",
    "supplies_representative": "SuppliesRepresentativeAgent",
    "email_triage": "EmailTriageAgent",
}


class ChiefAgent(BaseAgent):
    name = "ChiefAgent"
    role_description = "Jefe de Abastecimiento Virtual"
    system_prompt = (
        "Eres el Jefe de Abastecimiento Virtual de una red hospitalaria chilena. "
        "Clasifica la intencion del usuario, enruta a los agentes especialistas "
        "y sintetiza una respuesta ejecutiva en espanol."
    )

    def __init__(
        self,
        agents: Mapping[str, BaseAgent] | None = None,
        app_settings: Settings = default_settings,
    ) -> None:
        self.settings = app_settings
        self.history: list[dict[str, str]] = []
        self.agents = dict(agents or self._build_default_agents())

    def run(
        self,
        query: str,
        context: dict,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> AgentResponse:
        routing = self.route(query)
        selected_agents = routing["agents"]
        rationale = routing["rationale"]

        execution_context = dict(context)
        execution_context["conversation_history"] = list(self.history)
        execution_context["settings"] = self.settings

        responses = self._run_agents(selected_agents, query, execution_context, dataframes)
        output = self._synthesize(query, rationale, responses)

        self.history.append({"role": "user", "content": query})
        self.history.append({"role": "assistant", "content": output})

        confidence = min((response.confidence for response in responses), default=0.6)
        alerts = [alert for response in responses for alert in response.alerts]
        tables = [table for response in responses for table in response.tables]
        sources = sorted({source for response in responses for source in response.sources})
        assumptions = [item for response in responses for item in response.assumptions]

        return AgentResponse(
            agent_name=self.name,
            output=output,
            confidence=confidence,
            alerts=alerts,
            tables=tables,
            sources=sources,
            assumptions=assumptions,
        )

    def route(self, query: str) -> dict[str, object]:
        llm_result = self._route_with_llm(query)
        if llm_result:
            return llm_result
        return self._route_with_keywords(query)

    def _build_default_agents(self) -> dict[str, BaseAgent]:
        from .coverage_planner import CoveragePlannerAgent
        from .database_analyst import DatabaseAnalystAgent
        from .email_triage_agent import EmailTriageAgent
        from .materials_analyst import MaterialsAnalystAgent
        from .negotiation_analyst import NegotiationAnalystAgent
        from .pharma_representative import PharmaRepresentativeAgent
        from .price_audit import PriceAuditAgent
        from .supplies_representative import SuppliesRepresentativeAgent

        return {
            "coverage_planner": CoveragePlannerAgent(self.settings),
            "price_audit": PriceAuditAgent(self.settings),
            "negotiation_analyst": NegotiationAnalystAgent(self.settings),
            "database_analyst": DatabaseAnalystAgent(self.settings),
            "materials_analyst": MaterialsAnalystAgent(self.settings),
            "pharma_representative": PharmaRepresentativeAgent(self.settings),
            "supplies_representative": SuppliesRepresentativeAgent(self.settings),
            "email_triage": EmailTriageAgent(self.settings),
        }

    def _route_with_llm(self, query: str) -> dict[str, object] | None:
        if self.settings.llm_provider not in {"anthropic", "gemini"}:
            return None

        try:
            llm_client = client_from_settings(self.settings, self.settings.llm_provider)
            model = (
                self.settings.anthropic_model
                if self.settings.llm_provider == "anthropic"
                else self.settings.gemini_model
            )
            system = (
                "Clasifica consultas de abastecimiento hospitalario. "
                "Responde solo JSON valido con estas claves: agents, rationale. "
                "agents debe ser una lista con valores permitidos: "
                "coverage_planner, price_audit, negotiation_analyst, "
                "database_analyst, materials_analyst, pharma_representative, "
                "supplies_representative, email_triage. Si hay ambiguedad o dominio "
                "cruzado, incluye multiples agentes."
            )
            _, parsed = llm_client.generate_json(
                model=model,
                max_tokens=300,
                temperature=0.0,
                system=system,
                user=query,
            )
            agents = [
                agent for agent in parsed.get("agents", []) if agent in self.agents
            ]
            if not agents:
                return None
            return {
                "agents": agents,
                "rationale": str(parsed.get("rationale", "Clasificacion LLM.")),
                "method": "llm",
            }
        except Exception:
            return None

    def _route_with_keywords(self, query: str) -> dict[str, object]:
        normalized = self._normalize_text(query)
        matches: list[str] = []
        matched_terms: dict[str, list[str]] = {}

        for agent_key, keywords in ROUTING_KEYWORDS.items():
            terms = [keyword for keyword in keywords if keyword in normalized]
            if terms:
                matches.append(agent_key)
                matched_terms[agent_key] = terms[:3]

        if not matches:
            matches = ["database_analyst", "coverage_planner"]
            rationale = (
                "Consulta ambigua; se deriva a analisis de datos y cobertura para "
                "levantar evidencia base."
            )
        elif len(matches) == 1:
            agent_name = AGENT_DISPLAY_NAMES[matches[0]]
            terms = ", ".join(matched_terms[matches[0]])
            rationale = f"Routing por palabras clave hacia {agent_name}: {terms}."
        else:
            agent_names = ", ".join(AGENT_DISPLAY_NAMES[agent] for agent in matches)
            rationale = f"Consulta multi-dominio; se invocan agentes: {agent_names}."

        return {"agents": matches, "rationale": rationale, "method": "keywords"}

    def _run_agents(
        self,
        selected_agents: list[str],
        query: str,
        context: dict,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> list[AgentResponse]:
        responses: list[AgentResponse] = []
        with ThreadPoolExecutor(max_workers=max(1, len(selected_agents))) as executor:
            futures = {
                executor.submit(self.agents[agent_key].run, query, context, dataframes): agent_key
                for agent_key in selected_agents
            }
            for future in as_completed(futures):
                agent_key = futures[future]
                try:
                    responses.append(future.result())
                except Exception as exc:
                    responses.append(
                        AgentResponse(
                            agent_name=AGENT_DISPLAY_NAMES.get(agent_key, agent_key),
                            output=(
                                "El agente no pudo completar su analisis. "
                                f"Detalle tecnico: {exc}"
                            ),
                            confidence=0.0,
                            alerts=["Falla de ejecucion en agente especialista"],
                        )
                    )

        order = {agent: index for index, agent in enumerate(selected_agents)}
        responses.sort(key=lambda response: order.get(self._response_key(response), 999))
        return responses

    def _synthesize(
        self,
        query: str,
        rationale: str,
        responses: list[AgentResponse],
    ) -> str:
        contributors = ", ".join(response.agent_name for response in responses)
        sections = [
            "## Respuesta ejecutiva",
            f"**Consulta:** {query}",
            f"**Agentes participantes:** {contributors or 'Sin agentes ejecutados'}",
            f"**Racional de enrutamiento:** {rationale}",
        ]

        for response in responses:
            sections.append(f"\n### {response.agent_name}")
            sections.append(response.output)
            if response.alerts:
                sections.append("Alertas: " + "; ".join(response.alerts[:5]))
            if response.assumptions:
                sections.append("Supuestos: " + "; ".join(response.assumptions[:5]))

        return "\n\n".join(sections)

    def _response_key(self, response: AgentResponse) -> str:
        for key, display in AGENT_DISPLAY_NAMES.items():
            if response.agent_name == display:
                return key
        return response.agent_name.lower()

    def _normalize_text(self, text: str) -> str:
        lowered = text.lower()
        lowered = unicodedata.normalize("NFKD", lowered)
        lowered = "".join(char for char in lowered if not unicodedata.combining(char))
        lowered = re.sub(r"[^\w\s]", " ", lowered)
        return re.sub(r"\s+", " ", lowered).strip()
