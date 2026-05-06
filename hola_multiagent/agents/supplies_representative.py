from __future__ import annotations

import re
import unicodedata
from typing import Mapping

import pandas as pd

from .base_agent import AgentResponse, BaseAgent
from ..config.settings import Settings, settings as default_settings


HIGH_RISK_SUPPLY_TERMS = (
    "cateter",
    "implante",
    "protesis",
    "sutura",
    "set",
    "introductor",
    "valvula",
    "electrodo",
    "malla",
)


class SuppliesRepresentativeAgent(BaseAgent):
    name = "SuppliesRepresentativeAgent"
    role_description = "Representante de Insumos con perfil de enfermeria"
    system_prompt = (
        "Valida insumos y dispositivos desde requerimientos tecnicos de enfermeria: "
        "uso clinico, factor de empaque, esterilidad, compatibilidad, medidas, "
        "riesgo de sustitucion y respaldo proveedor."
    )

    def __init__(self, app_settings: Settings = default_settings) -> None:
        self.settings = app_settings

    def run(
        self,
        query: str,
        context: dict,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> AgentResponse:
        jfv = self._get_dataframe(dataframes, "jfv_revision")
        supplies = self._get_dataframe(dataframes, "insumos")

        tables: list[pd.DataFrame] = []
        alerts: list[str] = []
        output_parts = [
            "Revision enfermeria/insumos: se valida oportunidad comercial contra "
            "requerimiento tecnico, factor de empaque, equivalencia y riesgo de uso."
        ]

        if not jfv.empty:
            summary = self.jfv_summary(jfv)
            risk = self.jfv_risk_review(jfv)
            tables.extend([summary, risk])
            output_parts.extend(
                [
                    "\n**Resumen propuesta JFV:**",
                    summary.to_markdown(index=False),
                    "\n**Productos a validar tecnicamente:**",
                    risk.head(12).to_markdown(index=False),
                ]
            )
            if not risk.empty:
                alerts.append("Existen homologaciones de insumos que requieren validacion tecnica.")
        else:
            alerts.append("No se recibio revision JFV estructurada para validar insumos.")

        if not supplies.empty:
            catalog = self.catalog_summary(supplies)
            tables.append(catalog)
            output_parts.extend(["\n**Resumen maestro insumos:**", catalog.to_markdown(index=False)])

        return AgentResponse(
            agent_name=self.name,
            output="\n".join(output_parts),
            confidence=0.84 if tables else 0.6,
            alerts=alerts,
            tables=tables,
            sources=["jfv_revision", "insumos"],
            assumptions=[
                "Las ofertas de insumos se validan contra equivalencia tecnica, no solo precio.",
                "Factor de empaque y unidad de uso son condiciones bloqueantes para calcular ahorro.",
            ],
        )

    def jfv_summary(self, revision: pd.DataFrame) -> pd.DataFrame:
        df = self._normalize_columns(revision)
        consider_col = self._first_existing(df, ("considerar",))
        convenient_col = self._first_existing(df, ("conviene",))
        min_saving_col = self._first_existing(df, ("ahorro_vs_minimo", "ahorro_minimo"))
        avg_saving_col = self._first_existing(df, ("ahorro_vs_promedio", "ahorro_promedio"))
        product_col = self._first_existing(df, ("nombre_producto", "desc_db", "desc_jfv"))

        considered = self._truthy(df[consider_col]) if consider_col else pd.Series(True, index=df.index)
        convenient = self._truthy(df[convenient_col]) if convenient_col else pd.Series(True, index=df.index)
        valid = considered & convenient

        min_saving = pd.to_numeric(df[min_saving_col], errors="coerce").fillna(0) if min_saving_col else pd.Series(0, index=df.index)
        avg_saving = pd.to_numeric(df[avg_saving_col], errors="coerce").fillna(0) if avg_saving_col else pd.Series(0, index=df.index)

        return pd.DataFrame(
            [
                {"indicador": "lineas_revision", "valor": len(df)},
                {"indicador": "lineas_consideradas", "valor": int(considered.sum())},
                {"indicador": "lineas_convenientes", "valor": int(valid.sum())},
                {"indicador": "productos_unicos", "valor": int(df[product_col].nunique()) if product_col else 0},
                {"indicador": "ahorro_vs_minimo_clp", "valor": round(float(min_saving[valid].sum()))},
                {"indicador": "ahorro_vs_promedio_clp", "valor": round(float(avg_saving[valid].sum()))},
            ]
        )

    def jfv_risk_review(self, revision: pd.DataFrame) -> pd.DataFrame:
        df = self._normalize_columns(revision)
        product_col = self._first_existing(df, ("nombre_producto", "desc_db", "desc_jfv"))
        jfv_col = self._first_existing(df, ("desc_jfv", "descripcion_codigo_jfv"))
        consider_col = self._first_existing(df, ("considerar",))
        convenient_col = self._first_existing(df, ("conviene",))
        relation_col = self._first_existing(df, ("relacion_precios",))
        avg_saving_col = self._first_existing(df, ("ahorro_vs_promedio", "ahorro_promedio"))

        if product_col is None:
            return pd.DataFrame()

        considered = self._truthy(df[consider_col]) if consider_col else pd.Series(True, index=df.index)
        convenient = self._truthy(df[convenient_col]) if convenient_col else pd.Series(True, index=df.index)
        work = df[considered & convenient].copy()
        if work.empty:
            return pd.DataFrame()

        work["_text"] = (
            work[product_col].astype("string").fillna("")
            + " "
            + (work[jfv_col].astype("string").fillna("") if jfv_col else "")
        ).map(self._norm_text)
        work["_risk"] = work["_text"].map(self._technical_risk)
        if relation_col:
            work["_relation"] = pd.to_numeric(work[relation_col], errors="coerce")
        else:
            work["_relation"] = pd.NA
        if avg_saving_col:
            work["_saving"] = pd.to_numeric(work[avg_saving_col], errors="coerce").fillna(0)
        else:
            work["_saving"] = 0

        selected = work[(work["_risk"] != "BAJO") | (work["_relation"].fillna(1).abs() > 1.5)]
        selected = selected.sort_values("_saving", ascending=False)
        columns = {
            product_col: "producto_andes",
            jfv_col: "producto_jfv" if jfv_col else None,
        }
        output = pd.DataFrame()
        output["producto_andes"] = selected[product_col]
        output["producto_jfv"] = selected[jfv_col] if jfv_col else pd.NA
        output["riesgo_tecnico"] = selected["_risk"]
        output["relacion_precios"] = selected["_relation"]
        output["ahorro_vs_promedio_clp"] = selected["_saving"].round()
        output["accion_requerida"] = output["riesgo_tecnico"].map(self._required_action)
        return output.reset_index(drop=True)

    def catalog_summary(self, supplies: pd.DataFrame) -> pd.DataFrame:
        df = self._normalize_columns(supplies)
        code_cols = [column for column in df.columns if "codigo" in column or column == "cod"]
        material_cols = [column for column in df.columns if "material" in column or "descripcion" in column]
        return pd.DataFrame(
            [
                {"indicador": "filas_maestro_insumos", "valor": len(df)},
                {"indicador": "columnas_codigo", "valor": len(code_cols)},
                {"indicador": "columnas_material", "valor": len(material_cols)},
            ]
        )

    def _technical_risk(self, text: str) -> str:
        if any(term in text for term in HIGH_RISK_SUPPLY_TERMS):
            return "ALTO"
        if any(term in text for term in ("guante", "mascarilla", "bata", "jeringa", "suero")):
            return "MEDIO"
        return "BAJO"

    def _required_action(self, risk: str) -> str:
        if risk == "ALTO":
            return "Validar ficha tecnica, esterilidad, medidas y prueba usuaria."
        if risk == "MEDIO":
            return "Validar factor de empaque, unidad de uso y equivalencia operacional."
        return "Puede avanzar con control de precio y proveedor habilitado."

    def _normalize_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        normalized = dataframe.copy()
        normalized.columns = [self._slug(column) for column in normalized.columns]
        return normalized

    def _first_existing(self, dataframe: pd.DataFrame, columns: tuple[str, ...]) -> str | None:
        for column in columns:
            if column in dataframe.columns:
                return column
        return None

    def _truthy(self, series: pd.Series) -> pd.Series:
        text = series.astype("string").fillna("").map(self._norm_text)
        return text.isin({"true", "verdadero", "si", "yes", "ok", "1", "x"}) | (series == True)

    def _slug(self, value: object) -> str:
        text = self._norm_text(value)
        return re.sub(r"[^a-z0-9]+", "_", text).strip("_")

    def _norm_text(self, value: object) -> str:
        if pd.isna(value):
            return ""
        text = str(value).strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(char for char in text if not unicodedata.combining(char))
        return re.sub(r"\s+", " ", text)
