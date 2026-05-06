from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from .base_agent import AgentResponse
from .chief_agent import AGENT_DISPLAY_NAMES, ChiefAgent
from .coverage_planner import CoveragePlannerAgent
from .database_analyst import DatabaseAnalystAgent
from .materials_analyst import MaterialsAnalystAgent
from ..config.settings import Settings, settings as default_settings
from ..llm.discussion import run_panel_discussion


@dataclass(frozen=True)
class ReviewFinding:
    reviewer: str
    verdict: str
    detail: str
    severity: str


class ConsensusChiefAgent(ChiefAgent):
    name = "ConsensusChiefAgent"
    role_description = "Jefe de Abastecimiento Virtual con mesa de consenso"

    def __init__(self, app_settings: Settings = default_settings) -> None:
        super().__init__(app_settings=app_settings)
        self.database_reviewer = DatabaseAnalystAgent(app_settings)
        self.coverage_reviewer = CoveragePlannerAgent(app_settings)
        self.materials_reviewer = MaterialsAnalystAgent(app_settings)

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
        execution_context["consensus_mode"] = True

        primary_responses = self._run_agents(selected_agents, query, execution_context, dataframes)
        review_findings = self._run_review_panel(query, primary_responses, dataframes)

        panel_providers = context.get("llm_panel_providers")
        panel_messages = []
        if panel_providers:
            try:
                primary_answer = "\n\n".join(response.output for response in primary_responses if response.output)
                panel_messages = run_panel_discussion(
                    settings=self.settings,
                    providers=panel_providers,
                    question=query,
                    primary_answer=primary_answer,
                )
            except Exception:
                panel_messages = []

        output = self._synthesize_consensus(query, rationale, primary_responses, review_findings, panel_messages)

        self.history.append({"role": "user", "content": query})
        self.history.append({"role": "assistant", "content": output})

        confidence = self._consensus_confidence(primary_responses, review_findings)
        alerts = [alert for response in primary_responses for alert in response.alerts]
        alerts.extend(
            finding.detail for finding in review_findings if finding.severity in {"HIGH", "CRITICAL"}
        )
        tables = [table for response in primary_responses for table in response.tables]
        sources = sorted({source for response in primary_responses for source in response.sources})
        assumptions = [item for response in primary_responses for item in response.assumptions]
        assumptions.append("Modo consenso: revisores independientes validan datos, riesgo clinico y coherencia.")
        if panel_providers:
            assumptions.append("Panel LLM: se consultan revisores externos (Claude/Gemini) si hay API keys.")

        return AgentResponse(
            agent_name=self.name,
            output=output,
            confidence=confidence,
            alerts=alerts,
            tables=tables,
            sources=sources,
            assumptions=assumptions,
        )

    def _run_review_panel(
        self,
        query: str,
        primary_responses: list[AgentResponse],
        dataframes: Mapping[str, pd.DataFrame],
    ) -> list[ReviewFinding]:
        reviewers = [
            self._review_data_quality,
            self._review_financial_consistency,
            self._review_clinical_risk,
            self._review_cross_agent_disagreement,
        ]
        findings: list[ReviewFinding] = []
        with ThreadPoolExecutor(max_workers=len(reviewers)) as executor:
            futures = [
                executor.submit(reviewer, query, primary_responses, dataframes)
                for reviewer in reviewers
            ]
            for future in as_completed(futures):
                findings.extend(future.result())

        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "OK": 4}
        return sorted(findings, key=lambda item: severity_order.get(item.severity, 9))

    def _review_data_quality(
        self,
        query: str,
        primary_responses: list[AgentResponse],
        dataframes: Mapping[str, pd.DataFrame],
    ) -> list[ReviewFinding]:
        quality = self.database_reviewer.quality_report(dataframes)
        if quality.empty:
            return [
                ReviewFinding(
                    reviewer="Revisor de Datos",
                    verdict="OK",
                    detail="No se detectaron alertas estructurales de calidad de datos.",
                    severity="OK",
                )
            ]

        high_count = int((quality["severity"] == "HIGH").sum())
        severity = "HIGH" if high_count else "MEDIUM"
        return [
            ReviewFinding(
                reviewer="Revisor de Datos",
                verdict="OBSERVACION",
                detail=(
                    f"Se detectaron {len(quality)} alerta(s) de calidad de datos; "
                    f"{high_count} de severidad alta."
                ),
                severity=severity,
            )
        ]

    def _review_financial_consistency(
        self,
        query: str,
        primary_responses: list[AgentResponse],
        dataframes: Mapping[str, pd.DataFrame],
    ) -> list[ReviewFinding]:
        text = "\n".join(response.output for response in primary_responses).lower()
        financial_query = any(
            term in query.lower()
            for term in ("precio", "sobrecosto", "ahorro", "proveedor", "negociacion", "contrato")
        )
        if financial_query and "clp" not in text:
            return [
                ReviewFinding(
                    reviewer="Revisor Financiero",
                    verdict="ERROR",
                    detail="La consulta financiera no explicita impacto en CLP.",
                    severity="HIGH",
                )
            ]
        return [
            ReviewFinding(
                reviewer="Revisor Financiero",
                verdict="OK",
                detail="La salida financiera explicita impacto o no aplica calculo CLP.",
                severity="OK",
            )
        ]

    def _review_clinical_risk(
        self,
        query: str,
        primary_responses: list[AgentResponse],
        dataframes: Mapping[str, pd.DataFrame],
    ) -> list[ReviewFinding]:
        stock = dataframes.get("stock", pd.DataFrame())
        orders = dataframes.get("purchase_orders", pd.DataFrame())
        consumption = dataframes.get("consumption", pd.DataFrame())
        homologation = dataframes.get("homologation", pd.DataFrame())
        if stock.empty or consumption.empty:
            return [
                ReviewFinding(
                    reviewer="Revisor Clinico",
                    verdict="SIN_DATOS",
                    detail="No hay datos suficientes para validacion clinica de cobertura.",
                    severity="MEDIUM",
                )
            ]

        dashboard = self.coverage_reviewer.build_dashboard(stock, orders, consumption, homologation)
        critical = dashboard[
            (dashboard["criticality"] == "CRITICO")
            & (dashboard["status"].isin(["CRITICO", "ALERTA"]))
        ]
        if critical.empty:
            return [
                ReviewFinding(
                    reviewer="Revisor Clinico",
                    verdict="OK",
                    detail="No se detectaron SKUs clinicamente criticos en alerta.",
                    severity="OK",
                )
            ]
        return [
            ReviewFinding(
                reviewer="Revisor Clinico",
                verdict="RIESGO",
                detail=f"{len(critical)} SKU(s) criticos tienen estado CRITICO o ALERTA.",
                severity="HIGH",
            )
        ]

    def _review_cross_agent_disagreement(
        self,
        query: str,
        primary_responses: list[AgentResponse],
        dataframes: Mapping[str, pd.DataFrame],
    ) -> list[ReviewFinding]:
        if len(primary_responses) <= 1:
            return [
                ReviewFinding(
                    reviewer="Revisor de Consenso",
                    verdict="OK",
                    detail="Solo un agente primario fue requerido; no hay conflicto inter-agente.",
                    severity="OK",
                )
            ]

        low_confidence = [response.agent_name for response in primary_responses if response.confidence < 0.75]
        failed = [response.agent_name for response in primary_responses if response.confidence <= 0.0]
        if failed:
            return [
                ReviewFinding(
                    reviewer="Revisor de Consenso",
                    verdict="ERROR",
                    detail="Agentes sin respuesta confiable: " + ", ".join(failed),
                    severity="CRITICAL",
                )
            ]
        if low_confidence:
            return [
                ReviewFinding(
                    reviewer="Revisor de Consenso",
                    verdict="OBSERVACION",
                    detail="Agentes con confianza bajo umbral: " + ", ".join(low_confidence),
                    severity="MEDIUM",
                )
            ]
        return [
            ReviewFinding(
                reviewer="Revisor de Consenso",
                verdict="OK",
                detail="Los agentes primarios entregaron respuestas compatibles y confianza suficiente.",
                severity="OK",
            )
        ]

    def _synthesize_consensus(
        self,
        query: str,
        rationale: str,
        primary_responses: list[AgentResponse],
        review_findings: list[ReviewFinding],
        panel_messages: list[object] | None = None,
    ) -> str:
        contributors = ", ".join(response.agent_name for response in primary_responses)
        reviewer_names = ", ".join(sorted({finding.reviewer for finding in review_findings}))
        blocking = [finding for finding in review_findings if finding.severity in {"CRITICAL", "HIGH"}]
        consensus_status = "CON_OBSERVACIONES" if blocking else "VALIDADO"

        sections = [
            "## Mesa de consenso",
            f"**Consulta:** {query}",
            f"**Estado del consenso:** {consensus_status}",
            f"**Agentes primarios:** {contributors or 'Sin agentes ejecutados'}",
            f"**Revisores independientes:** {reviewer_names}",
            f"**Racional de enrutamiento:** {rationale}",
            "\n### Informe al Jefe",
        ]

        if blocking:
            sections.append(
                "La recomendacion es util, pero debe leerse con observaciones de control antes de ejecutar."
            )
        else:
            sections.append("Los analistas y revisores convergen sin discrepancias materiales.")

        sections.append("\n### Hallazgos de analistas")
        for response in primary_responses:
            sections.append(f"\n#### {response.agent_name}")
            sections.append(response.output)

        sections.append("\n### Revision independiente")
        review_rows = pd.DataFrame(
            [
                {
                    "reviewer": finding.reviewer,
                    "verdict": finding.verdict,
                    "severity": finding.severity,
                    "detail": finding.detail,
                }
                for finding in review_findings
            ]
        )
        sections.append(review_rows.to_markdown(index=False))

        sections.append("\n### Decision del Jefe")
        if blocking:
            sections.append(
                "Avanzar con las acciones priorizadas, pero levantar primero las observaciones de datos, "
                "riesgo clinico o consistencia financiera marcadas como HIGH/CRITICAL."
            )
        else:
            sections.append("Avanzar con la recomendacion; mantener monitoreo semanal de indicadores.")

        if panel_messages:
            sections.append("\n### Panel multi-modelo (Claude/Gemini)")
            for message in panel_messages:
                provider = getattr(message, "provider", "llm")
                model = getattr(message, "model", "")
                content = getattr(message, "content", "")
                header = f"#### {provider}{' - ' + model if model else ''}"
                sections.append("\n" + header)
                sections.append(content)

        return "\n\n".join(sections)

    def _consensus_confidence(
        self,
        primary_responses: list[AgentResponse],
        review_findings: list[ReviewFinding],
    ) -> float:
        base = min((response.confidence for response in primary_responses), default=0.6)
        penalty = 0.0
        for finding in review_findings:
            if finding.severity == "CRITICAL":
                penalty += 0.3
            elif finding.severity == "HIGH":
                penalty += 0.15
            elif finding.severity == "MEDIUM":
                penalty += 0.05
        return max(0.0, min(1.0, base - penalty))


def route_names(agent_keys: list[str]) -> list[str]:
    return [AGENT_DISPLAY_NAMES.get(agent_key, agent_key) for agent_key in agent_keys]
