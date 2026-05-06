from __future__ import annotations

from typing import Mapping

import pandas as pd

from .base_agent import AgentResponse, BaseAgent
from ..config.settings import Settings, settings as default_settings


CRITICAL_KEYWORDS = (
    "medicamentos inyectables",
    "suero",
    "anestesico",
    "material de curacion",
    "cateter",
    "set de infusion",
    "antiseptico",
    "material respiratorio",
    "ventilador",
)

ESSENTIAL_KEYWORDS = (
    "guantes de procedimiento",
    "guantes",
    "mascarilla",
    "bata",
    "reactivo de laboratorio",
    "tira reactiva",
    "material laboratorio",
    "material quirurgico",
    "material clinico general",
)

GENERAL_KEYWORDS = (
    "papel de impresora",
    "material de oficina",
    "aseo",
    "servicios generales",
)


class MaterialsAnalystAgent(BaseAgent):
    name = "MaterialsAnalystAgent"
    role_description = "Analista de Materiales con perfil clinico y farmaceutico"
    system_prompt = (
        "Clasifica criticidad de materiales hospitalarios considerando seguridad "
        "del paciente, dependencia clinica, posibilidad de sustitucion y riesgo "
        "operacional."
    )

    def __init__(self, app_settings: Settings = default_settings) -> None:
        self.settings = app_settings

    def run(
        self,
        query: str,
        context: dict,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> AgentResponse:
        homologation = self._get_dataframe(dataframes, "homologation")
        if homologation.empty:
            return self._empty_response(
                "No hay maestro de homologacion disponible para validar materiales.",
                confidence=0.0,
                alerts=["Falta homologation.csv"],
            )

        enriched = self.enrich_catalog(homologation)
        validation = self.validation_report(enriched)
        summary = (
            enriched.groupby("criticality", dropna=False)["sku"]
            .nunique()
            .reset_index(name="sku_count")
            .sort_values(["criticality"])
        )
        pending = enriched[enriched["criticality"] == "PENDIENTE"]

        output_parts = [
            "Se enriquecio el maestro de homologacion con criticidad clinica y "
            "validaciones de calidad de datos.",
            "\n**Resumen por criticidad:**",
            summary.to_markdown(index=False),
            "\n**Items pendientes de validacion humana:** "
            f"{pending['sku'].nunique()} SKU(s).",
        ]
        if not validation.empty:
            output_parts.extend(
                [
                    "\n**Principales alertas de catalogo:**",
                    validation.head(10).to_markdown(index=False),
                ]
            )

        alerts = []
        if not pending.empty:
            alerts.append("Existen SKUs con criticidad PENDIENTE para validacion clinica")
        if not validation.empty:
            alerts.append("Se detectaron brechas de calidad en homologation.csv")

        return AgentResponse(
            agent_name=self.name,
            output="\n".join(output_parts),
            confidence=0.84,
            alerts=alerts,
            tables=[enriched, validation, summary],
            sources=["homologation"],
            assumptions=[
                "La criticidad se calcula localmente con diccionario clinico extendible para operacion via Codex.",
                "LOW confidence se marca siempre como PENDIENTE.",
            ],
        )

    def enrich_catalog(self, homologation: pd.DataFrame) -> pd.DataFrame:
        enriched = homologation.copy()
        classifications = enriched.apply(self._classify_row, axis=1)
        enriched["criticality"] = [item[0] for item in classifications]
        enriched["criticality_confidence"] = [item[1] for item in classifications]
        enriched["criticality_reason"] = [item[2] for item in classifications]
        return enriched

    def validation_report(self, enriched: pd.DataFrame) -> pd.DataFrame:
        findings: list[dict[str, object]] = []

        for _, row in enriched.iterrows():
            sku = row.get("sku")
            if pd.isna(row.get("generic_name")) or str(row.get("generic_name")).strip() == "":
                findings.append(self._finding(sku, "GENERIC_NAME_NULO", "Completar nombre generico."))
            if pd.isna(row.get("category")) or str(row.get("category")).strip() == "":
                findings.append(self._finding(sku, "CATEGORIA_NULA", "Completar categoria clinica."))
            if pd.isna(row.get("supplier")) or str(row.get("supplier")).strip() == "":
                findings.append(self._finding(sku, "PROVEEDOR_NULO", "Asignar proveedor vigente."))
            if pd.isna(row.get("unit_price")):
                findings.append(self._finding(sku, "PRECIO_NULO", "Registrar precio unitario de referencia."))
            if row.get("criticality") == "PENDIENTE":
                findings.append(
                    self._finding(
                        sku,
                        "CRITICIDAD_PENDIENTE",
                        "Validar criticidad con QF o supervision clinica.",
                        confidence=row.get("criticality_confidence", "LOW"),
                    )
                )

        duplicate_cols = ["generic_name", "brand", "uom"]
        available_cols = [column for column in duplicate_cols if column in enriched.columns]
        if len(available_cols) == len(duplicate_cols):
            duplicate_groups = (
                enriched.dropna(subset=available_cols)
                .groupby(available_cols)["sku"]
                .nunique()
                .reset_index(name="sku_count")
            )
            duplicate_groups = duplicate_groups[duplicate_groups["sku_count"] > 1]
            for _, duplicate in duplicate_groups.iterrows():
                skus = enriched[
                    (enriched["generic_name"] == duplicate["generic_name"])
                    & (enriched["brand"] == duplicate["brand"])
                    & (enriched["uom"] == duplicate["uom"])
                ]["sku"].drop_duplicates()
                findings.append(
                    {
                        "sku": ", ".join(skus.astype(str).tolist()),
                        "reason": "SKU_DUPLICADO_POTENCIAL",
                        "confidence": "HIGH",
                        "recommended_action": "Revisar homologacion y consolidar codigos equivalentes.",
                    }
                )

        return pd.DataFrame(
            findings,
            columns=["sku", "reason", "confidence", "recommended_action"],
        )

    def _classify_row(self, row: pd.Series) -> tuple[str, str, str]:
        text = " ".join(
            str(row.get(column, "")).lower()
            for column in ("generic_name", "category")
            if not pd.isna(row.get(column))
        )

        if any(keyword in text for keyword in CRITICAL_KEYWORDS):
            return "CRITICO", "HIGH", "Regla clinica: impacto directo en continuidad asistencial."
        if any(keyword in text for keyword in ESSENTIAL_KEYWORDS):
            return "ESENCIAL", "HIGH", "Regla clinica: alta relevancia operacional con sustitucion posible."
        if any(keyword in text for keyword in GENERAL_KEYWORDS):
            return "GENERAL", "HIGH", "Regla operacional: bajo impacto clinico directo."

        return "PENDIENTE", "LOW", "Datos insuficientes o sin coincidencia en diccionario."

    def _finding(
        self,
        sku: object,
        reason: str,
        recommended_action: str,
        confidence: object = "HIGH",
    ) -> dict[str, object]:
        return {
            "sku": sku,
            "reason": reason,
            "confidence": confidence,
            "recommended_action": recommended_action,
        }
