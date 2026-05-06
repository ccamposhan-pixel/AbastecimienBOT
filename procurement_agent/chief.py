from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .report import format_clp
from .standardize import parse_number


SUMMARY_CANDIDATES = [
    "andes_refined_summary.json",
    "andes_analysis_summary.json",
    "opportunities.json",
]
SUPPLIER_CANDIDATES = [
    "andes_supplier_targets_refined.csv",
    "andes_supplier_negotiation_targets.csv",
]
PRODUCT_CANDIDATES = [
    "andes_product_savings_refined.csv",
    "andes_product_savings_opportunities.csv",
]
DESAT_CANDIDATES = [
    "andes_desatomization_refined.csv",
    "andes_desatomization_opportunities.csv",
]


@dataclass(frozen=True)
class ValidationFinding:
    level: str
    source: str
    message: str


@dataclass(frozen=True)
class AgentBrief:
    agent: str
    role: str
    verdict: str
    observations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChiefDecision:
    priority: int
    topic: str
    owner_agent: str
    action: str
    objective_clp: float
    pressure_pct: float | None
    evidence: str
    guardrail: str


@dataclass(frozen=True)
class ChiefReview:
    question: str
    verdict: str
    summary: dict[str, Any]
    findings: list[ValidationFinding]
    briefs: list[AgentBrief]
    decisions: list[ChiefDecision]
    source_paths: dict[str, str]


@dataclass(frozen=True)
class ProcurementArtifacts:
    reports_dir: Path
    summary: dict[str, Any]
    suppliers: list[dict[str, str]]
    products: list[dict[str, str]]
    desatomization: list[dict[str, str]]
    paths: dict[str, Path]

    @classmethod
    def load(cls, reports_dir: str | Path) -> "ProcurementArtifacts":
        root = Path(reports_dir)
        paths = {
            "summary": _first_existing(root, SUMMARY_CANDIDATES),
            "suppliers": _first_existing(root, SUPPLIER_CANDIDATES),
            "products": _first_existing(root, PRODUCT_CANDIDATES),
            "desatomization": _first_existing(root, DESAT_CANDIDATES),
        }
        summary = _load_summary(paths["summary"]) if paths["summary"] else {}
        return cls(
            reports_dir=root,
            summary=summary,
            suppliers=_read_csv(paths["suppliers"]),
            products=_read_csv(paths["products"]),
            desatomization=_read_csv(paths["desatomization"]),
            paths={key: value for key, value in paths.items() if value is not None},
        )


class ChiefProcurementAgent:
    """Single user-facing controller for procurement analysis outputs."""

    def review(self, artifacts: ProcurementArtifacts, question: str = "") -> ChiefReview:
        findings = ControllerAgent().validate(artifacts)
        briefs = [
            AnalystAgent().brief(artifacts),
            ControllerAgent().brief(artifacts, findings),
            NegotiationAgent().brief(artifacts),
            DesatomizationAgent().brief(artifacts),
            RiskAgent().brief(artifacts, findings),
        ]
        decisions = self._build_decisions(artifacts)
        verdict = self._verdict(findings)
        return ChiefReview(
            question=question,
            verdict=verdict,
            summary=artifacts.summary,
            findings=findings,
            briefs=briefs,
            decisions=decisions,
            source_paths={key: str(value) for key, value in artifacts.paths.items()},
        )

    def _verdict(self, findings: list[ValidationFinding]) -> str:
        if any(finding.level == "error" for finding in findings):
            return "No aprobado: faltan insumos o hay inconsistencias criticas."
        if any(finding.level == "warning" for finding in findings):
            return "Aprobado condicionado: se puede negociar, pero con validaciones previas."
        return "Aprobado: cifras consistentes para iniciar gestion."

    def _build_decisions(self, artifacts: ProcurementArtifacts) -> list[ChiefDecision]:
        decisions: list[ChiefDecision] = []
        suppliers = _top_rows(artifacts.suppliers, "objective_savings", 8)
        for index, supplier in enumerate(suppliers, start=1):
            name = supplier.get("supplier", "Proveedor sin nombre")
            objective = _number(supplier.get("objective_savings"))
            pressure = _number(supplier.get("pressure_pct_addressable"))
            addressable = _number(supplier.get("addressable_spend"))
            focus = supplier.get("top_products", "")
            guardrail = "Validar empaque, contrato, calidad, plazo y criticidad clinica antes de cerrar."
            if pressure >= 0.45:
                guardrail = "Objetivo agresivo: validar equivalencia tecnica y usarlo como techo de negociacion."
            decisions.append(
                ChiefDecision(
                    priority=index,
                    topic=f"Negociacion con {name}",
                    owner_agent="Agente negociador",
                    action=(
                        f"Pedir {format_clp(objective)} de mejora sobre gasto atacable "
                        f"de {format_clp(addressable)}."
                    ),
                    objective_clp=objective,
                    pressure_pct=pressure,
                    evidence=focus or "Oportunidades por precio comparable/JFV.",
                    guardrail=guardrail,
                )
            )

        offset = len(decisions)
        for index, row in enumerate(_top_rows(artifacts.desatomization, "tail_spend", 5), start=1):
            family = row.get("family", "Familia sin nombre")
            target = _first_number(row, ["target_3pct", "desat_savings_target_3pct"])
            target_suppliers = _first_number(row, ["target_supplier_count"])
            current_suppliers = _first_number(row, ["supplier_count"])
            tail_spend = _first_number(row, ["tail_spend"])
            decisions.append(
                ChiefDecision(
                    priority=offset + index,
                    topic=f"Desatomizacion {family}",
                    owner_agent="Agente de desatomizacion",
                    action=(
                        f"Llevar de {current_suppliers:.0f} proveedores a meta {target_suppliers:.0f}; "
                        f"capturar al menos {format_clp(target)} sobre cola larga."
                    ),
                    objective_clp=target,
                    pressure_pct=None,
                    evidence=f"Spend cola larga: {format_clp(tail_spend)}. Candidatos: {row.get('candidates', row.get('candidate_suppliers', 'No informado'))}",
                    guardrail="Mantener excepciones documentadas por exclusividad, consignacion o continuidad operacional.",
                )
            )
        return decisions


class AnalystAgent:
    def brief(self, artifacts: ProcurementArtifacts) -> AgentBrief:
        summary = artifacts.summary
        observations = [
            f"Gasto analizado: {_summary_clp(summary, 'total_spend', 'total_spend_clp')}.",
            f"Ahorro precio objetivo: {_summary_clp(summary, 'objective_price_savings', 'combined_objective_supplier_savings', 'estimated_savings_clp')}.",
            f"Proveedores en base: {_summary_value(summary, 'suppliers', 'supplier_count')}.",
        ]
        top_supplier = _top_rows(artifacts.suppliers, "objective_savings", 1)
        top_product = _top_rows(artifacts.products, "objective_savings", 1)
        if top_supplier:
            observations.append(
                f"Mayor conversacion comercial: {top_supplier[0].get('supplier', 'N/A')} "
                f"por {format_clp(_number(top_supplier[0].get('objective_savings')))}."
            )
        if top_product:
            observations.append(
                f"Producto foco inicial: {top_product[0].get('product', top_product[0].get('representative_description', 'N/A'))}."
            )
        return AgentBrief(
            agent="Analista",
            role="Cuantifica oportunidades y prioriza hallazgos.",
            verdict="La oportunidad existe y esta priorizada por impacto.",
            observations=observations,
            recommendations=[
                "Usar objetivo defendible como pedido formal y stretch como rango de negociacion.",
                "Mantener trazabilidad por producto, proveedor y familia antes de comprometer ahorro.",
            ],
        )


class ControllerAgent:
    def validate(self, artifacts: ProcurementArtifacts) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        self._validate_files(artifacts, findings)
        self._validate_summary(artifacts, findings)
        self._validate_suppliers(artifacts, findings)
        self._validate_products(artifacts, findings)
        self._validate_desatomization(artifacts, findings)
        if not findings:
            findings.append(ValidationFinding("info", "control", "Sin hallazgos de control relevantes."))
        return findings

    def brief(self, artifacts: ProcurementArtifacts, findings: list[ValidationFinding]) -> AgentBrief:
        severe = [finding for finding in findings if finding.level in {"error", "warning"}]
        observations = [f"{finding.level.upper()} {finding.source}: {finding.message}" for finding in findings[:8]]
        verdict = "Control aprobado." if not severe else "Control aprobado con condiciones."
        return AgentBrief(
            agent="Controlador",
            role="Audita consistencia, cobertura y supuestos.",
            verdict=verdict,
            observations=observations,
            recommendations=[
                "No ejecutar cambios automaticos si la familia o empaque no estan homologados.",
                "Toda negociacion sobre 45% de presion debe pasar por validacion tecnica.",
            ],
        )

    def _validate_files(self, artifacts: ProcurementArtifacts, findings: list[ValidationFinding]) -> None:
        expected = {
            "summary": "resumen ejecutivo",
            "suppliers": "targets de proveedor",
            "products": "oportunidades por producto",
            "desatomization": "desatomizacion",
        }
        for key, label in expected.items():
            if key not in artifacts.paths:
                findings.append(ValidationFinding("error", "archivos", f"Falta archivo de {label}."))

    def _validate_summary(self, artifacts: ProcurementArtifacts, findings: list[ValidationFinding]) -> None:
        summary = artifacts.summary
        if not summary:
            findings.append(ValidationFinding("error", "summary", "No hay resumen JSON para auditar."))
            return

        total = _first_number(summary, ["total_spend", "total_spend_clp"])
        if total <= 0:
            findings.append(ValidationFinding("error", "summary", "El gasto total es cero o invalido."))

        objective = _first_number(summary, ["objective_price_savings", "combined_objective_supplier_savings"])
        desat = _first_number(summary, ["desat_3pct", "desat_savings_3pct"])
        proposal = _first_number(summary, ["proposal_defensible"])
        if proposal and objective and desat and abs((objective + desat) - proposal) > max(1000, proposal * 0.005):
            findings.append(
                ValidationFinding(
                    "warning",
                    "summary",
                    "La propuesta total no cuadra exactamente con ahorro precio + desatomizacion.",
                )
            )

        desc_spend = _first_number(summary, ["desc_h_spend"])
        jfv_spend = _first_number(summary, ["jfv_spend"])
        if total and desc_spend and desc_spend / total < 0.10:
            findings.append(
                ValidationFinding(
                    "warning",
                    "cobertura",
                    f"Descripcion homologada cubre solo {desc_spend / total:.1%} del gasto.",
                )
            )
        if total and jfv_spend and jfv_spend / total < 0.10:
            findings.append(
                ValidationFinding(
                    "warning",
                    "cobertura",
                    f"Precio/codigo JFV cubre solo {jfv_spend / total:.1%} del gasto.",
                )
            )

    def _validate_suppliers(self, artifacts: ProcurementArtifacts, findings: list[ValidationFinding]) -> None:
        if not artifacts.suppliers:
            findings.append(ValidationFinding("error", "proveedores", "No hay targets de proveedores."))
            return
        for row in artifacts.suppliers[:50]:
            supplier = row.get("supplier", "Proveedor sin nombre")
            objective = _number(row.get("objective_savings"))
            addressable = _number(row.get("addressable_spend"))
            pressure = _number(row.get("pressure_pct_addressable"))
            if objective > 0 and addressable <= 0:
                findings.append(
                    ValidationFinding("error", "proveedores", f"{supplier} tiene objetivo sin gasto atacable.")
                )
            if pressure > 0.45:
                findings.append(
                    ValidationFinding(
                        "warning",
                        "proveedores",
                        f"{supplier} requiere presion alta ({pressure:.1%}); validar antes de negociar como compromiso.",
                    )
                )

    def _validate_products(self, artifacts: ProcurementArtifacts, findings: list[ValidationFinding]) -> None:
        if not artifacts.products:
            findings.append(ValidationFinding("error", "productos", "No hay oportunidades por producto."))
            return
        for row in artifacts.products[:30]:
            product = row.get("product", row.get("representative_description", "Producto sin nombre"))
            key_type = row.get("key_type", row.get("confidence", ""))
            clinics = _number(row.get("clinics"))
            suppliers = _number(row.get("suppliers"))
            if key_type == "SKU clinica" and clinics <= 1:
                findings.append(
                    ValidationFinding(
                        "warning",
                        "productos",
                        f"{product} usa benchmark SKU de una clinica; requiere validacion de homologacion.",
                    )
                )
            if suppliers <= 1 and key_type != "DESC homologada":
                findings.append(
                    ValidationFinding(
                        "info",
                        "productos",
                        f"{product} tiene un solo proveedor en el set comparable; usar como renegociacion, no sustitucion directa.",
                    )
                )

    def _validate_desatomization(self, artifacts: ProcurementArtifacts, findings: list[ValidationFinding]) -> None:
        if not artifacts.desatomization:
            findings.append(ValidationFinding("error", "desatomizacion", "No hay tabla de desatomizacion."))
            return
        for row in artifacts.desatomization[:20]:
            family = row.get("family", "")
            if family.lower().startswith("sin familia"):
                findings.append(
                    ValidationFinding(
                        "warning",
                        "desatomizacion",
                        "Existe una bolsa relevante sin familia homologada; debe ser mandato de datos antes de licitar.",
                    )
                )
                return


class NegotiationAgent:
    def brief(self, artifacts: ProcurementArtifacts) -> AgentBrief:
        suppliers = _top_rows(artifacts.suppliers, "objective_savings", 5)
        observations = []
        recommendations = []
        for row in suppliers:
            supplier = row.get("supplier", "Proveedor sin nombre")
            objective = _number(row.get("objective_savings"))
            pressure = _number(row.get("pressure_pct_addressable"))
            observations.append(f"{supplier}: pedir {format_clp(objective)} ({pressure:.1%} del gasto atacable).")
            recommendations.append(
                f"Con {supplier}, abrir con P25/JFV como evidencia y cerrar con nota de credito o lista marco."
            )
        return AgentBrief(
            agent="Negociador",
            role="Transforma hallazgos en conversaciones comerciales.",
            verdict="Priorizar proveedores con objetivo alto y evidencia por item.",
            observations=observations,
            recommendations=recommendations[:5],
        )


class DesatomizationAgent:
    def brief(self, artifacts: ProcurementArtifacts) -> AgentBrief:
        rows = _top_rows(artifacts.desatomization, "tail_spend", 5)
        observations = []
        recommendations = []
        for row in rows:
            family = row.get("family", "Familia sin nombre")
            current = _first_number(row, ["supplier_count"])
            target = _first_number(row, ["target_supplier_count"])
            tail = _first_number(row, ["tail_spend"])
            observations.append(f"{family}: {current:.0f} proveedores, meta {target:.0f}, cola {format_clp(tail)}.")
            recommendations.append(f"Licitar o renegociar contrato marco para {family}.")
        return AgentBrief(
            agent="Desatomizador",
            role="Reduce fragmentacion y propone contratos marco.",
            verdict="La cola larga justifica gobierno de proveedores por familia.",
            observations=observations,
            recommendations=recommendations,
        )


class RiskAgent:
    def brief(self, artifacts: ProcurementArtifacts, findings: list[ValidationFinding]) -> AgentBrief:
        warnings = [finding for finding in findings if finding.level == "warning"]
        observations = [
            "Riesgo principal: confundir sobreprecio real con diferencia de empaque, contrato o criticidad.",
            "Riesgo operativo: desatomizar sin excepciones puede cortar continuidad clinica.",
        ]
        observations.extend(f"{finding.source}: {finding.message}" for finding in warnings[:5])
        return AgentBrief(
            agent="Riesgos",
            role="Identifica limites de ejecucion y aprobaciones requeridas.",
            verdict="Ejecutar por etapas con validacion de duenos tecnicos.",
            observations=observations,
            recommendations=[
                "Separar quick wins de items que requieren homologacion tecnica.",
                "Definir matriz de excepciones: exclusividad, consignacion, urgencia, contrato vigente y continuidad clinica.",
            ],
        )


def run_chief_review(
    reports_dir: str | Path = "reports",
    output_dir: str | Path | None = None,
    question: str = "",
) -> dict[str, Path]:
    artifacts = ProcurementArtifacts.load(reports_dir)
    review = ChiefProcurementAgent().review(artifacts, question)
    root = Path(output_dir) if output_dir else Path(reports_dir)
    root.mkdir(parents=True, exist_ok=True)

    json_path = root / "chief_board_minutes.json"
    markdown_path = root / "chief_memo.md"
    json_path.write_text(json.dumps(asdict(review), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_chief_markdown(review), encoding="utf-8")
    return {"minutes_json": json_path, "memo": markdown_path}


def render_chief_markdown(review: ChiefReview) -> str:
    lines = [
        "# Jefe de Compras IA",
        "",
        "## Veredicto del jefe",
        "",
        review.verdict,
        "",
    ]
    if review.question:
        lines.extend(["## Solicitud recibida", "", review.question, ""])

    lines.extend(
        [
            "## Cifras bajo control",
            "",
            f"- Gasto analizado: {_summary_clp(review.summary, 'total_spend', 'total_spend_clp')}",
            f"- Ahorro precio objetivo: {_summary_clp(review.summary, 'objective_price_savings', 'combined_objective_supplier_savings', 'estimated_savings_clp')}",
            f"- Ahorro desatomizacion 3%: {_summary_clp(review.summary, 'desat_3pct', 'desat_savings_3pct')}",
            f"- Propuesta defendible: {_summary_clp(review.summary, 'proposal_defensible')}",
            f"- Stretch: {_summary_clp(review.summary, 'proposal_stretch', 'stretch_internal_savings')}",
            "",
            "## Decisiones y mandatos",
            "",
            "| Prioridad | Tema | Responsable | Accion | Objetivo | Presion | Control |",
            "| ---: | --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for decision in review.decisions:
        pressure = "" if decision.pressure_pct is None else f"{decision.pressure_pct:.1%}"
        lines.append(
            "| "
            f"{decision.priority} | "
            f"{decision.topic} | "
            f"{decision.owner_agent} | "
            f"{decision.action} | "
            f"{format_clp(decision.objective_clp)} | "
            f"{pressure} | "
            f"{decision.guardrail} |"
        )

    lines.extend(["", "## Hallazgos de control", ""])
    for finding in review.findings:
        lines.append(f"- {finding.level.upper()} {finding.source}: {finding.message}")

    lines.extend(["", "## Mesa de discusion", ""])
    for brief in review.briefs:
        lines.extend([f"### {brief.agent}", "", f"Rol: {brief.role}", "", f"Veredicto: {brief.verdict}", ""])
        if brief.observations:
            lines.append("Observaciones:")
            lines.extend(f"- {observation}" for observation in brief.observations)
            lines.append("")
        if brief.recommendations:
            lines.append("Recomendaciones:")
            lines.extend(f"- {recommendation}" for recommendation in brief.recommendations)
            lines.append("")

    lines.extend(
        [
            "## Protocolo de comunicacion",
            "",
            "- El usuario habla solo con el Jefe de Compras IA.",
            "- El jefe convoca agentes internos, contrasta hallazgos y responde con decisiones trazables.",
            "- Ningun ahorro se marca como ejecutado sin validacion de datos, contrato, empaque y responsable tecnico.",
            "",
            "## Fuentes usadas",
            "",
        ]
    )
    for label, path in review.source_paths.items():
        lines.append(f"- {label}: `{path}`")

    return "\n".join(lines) + "\n"


def _first_existing(root: Path, candidates: list[str]) -> Path | None:
    for candidate in candidates:
        path = root / candidate
        if path.exists():
            return path
    return None


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_summary(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "summary" in raw and isinstance(raw["summary"], dict):
        summary = raw["summary"]
        return {
            "total_spend_clp": summary.get("total_spend_clp", 0),
            "estimated_savings_clp": summary.get("estimated_savings_clp", 0),
            "supplier_count": summary.get("supplier_count", 0),
            "record_count": summary.get("record_count", 0),
            "long_tail_spend_clp": summary.get("long_tail_spend_clp", 0),
        }
    return raw if isinstance(raw, dict) else {}


def _top_rows(rows: list[dict[str, str]], key: str, limit: int) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: _number(row.get(key)), reverse=True)[:limit]


def _number(value: Any) -> float:
    parsed = parse_number(value, default=0.0)
    if parsed is None:
        return 0.0
    return 0.0 if (isinstance(parsed, float) and math.isnan(parsed)) else float(parsed)


def _first_number(source: dict[str, Any], keys: list[str]) -> float:
    for key in keys:
        value = _number(source.get(key))
        if value:
            return value
    return 0.0


def _summary_value(summary: dict[str, Any], *keys: str) -> str:
    value = _first_number(summary, list(keys))
    return f"{value:,.0f}".replace(",", ".") if value else "No informado"


def _summary_clp(summary: dict[str, Any], *keys: str) -> str:
    value = _first_number(summary, list(keys))
    return format_clp(value) if value else "No informado"
