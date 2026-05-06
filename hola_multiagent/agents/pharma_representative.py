from __future__ import annotations

import re
import unicodedata
from typing import Mapping

import pandas as pd

from .base_agent import AgentResponse, BaseAgent
from ..config.settings import Settings, settings as default_settings


PROTECTED_BRANDS = ("bridion",)


class PharmaRepresentativeAgent(BaseAgent):
    name = "PharmaRepresentativeAgent"
    role_description = "Representante de Farmacos con perfil QF y dominio de vademecum"
    system_prompt = (
        "Valida medicamentos desde mirada QF: principio activo, marca, registro ISP, "
        "vigencia, equivalencia terapeutica, presentacion, dosis, via y sustitucion "
        "segura antes de proponer homologacion o negociacion."
    )

    def __init__(self, app_settings: Settings = default_settings) -> None:
        self.settings = app_settings

    def run(
        self,
        query: str,
        context: dict,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> AgentResponse:
        vademecum = self._get_dataframe(dataframes, "vademecum")
        purchases = self._get_dataframe(dataframes, "purchase_orders")
        if purchases.empty:
            purchases = self._get_dataframe(dataframes, "compras")

        tables: list[pd.DataFrame] = []
        alerts: list[str] = []
        output_parts = [
            "Revision QF: se valida homologacion de farmacos separando principio activo, "
            "marca protegida, presentacion, dosis y vigencia regulatoria."
        ]

        if not vademecum.empty:
            summary = self.vademecum_summary(vademecum)
            tables.append(summary)
            output_parts.extend(["\n**Resumen vademecum/ISP:**", summary.to_markdown(index=False)])
        else:
            alerts.append("No se recibio vademecum estructurado; usar validacion QF manual.")

        if not purchases.empty:
            sugammadex = self.sugammadex_opportunity(purchases)
            if not sugammadex.empty:
                tables.append(sugammadex)
                output_parts.extend(
                    [
                        "\n**Sugammadex: separacion no-Bridion vs Bridion:**",
                        sugammadex.to_markdown(index=False),
                    ]
                )
                if (sugammadex["segmento"] == "BRIDION_PROTEGIDO").any():
                    alerts.append("Sugammadex target CLP 19.500 no aplica automaticamente a Bridion.")

        return AgentResponse(
            agent_name=self.name,
            output="\n".join(output_parts),
            confidence=0.86 if tables else 0.62,
            alerts=alerts,
            tables=tables,
            sources=["vademecum", "purchase_orders"],
            assumptions=[
                "La sustitucion de farmacos requiere validacion QF si cambia marca, forma, dosis, via o equivalencia.",
                "Bridion se trata como marca protegida hasta aprobacion clinica explicita.",
            ],
        )

    def vademecum_summary(self, vademecum: pd.DataFrame) -> pd.DataFrame:
        df = self._normalize_columns(vademecum)
        rows = len(df)
        vigente_col = self._first_existing(df, ("vigencia", "estado"))
        generic_col = self._first_existing(df, ("nombre_generico", "principio_activo"))
        atc_col = self._first_existing(df, ("codigo_atc", "atc"))
        equivalence_col = self._first_existing(df, ("equivalencia", "equivalencia_terapeutica"))

        if vigente_col:
            vigencia = df[vigente_col].astype("string").map(self._norm_text)
            vigente = int((vigencia == "vigente").sum())
            no_vigente = int((vigencia == "no vigente").sum())
        else:
            vigente = 0
            no_vigente = 0
        with_generic = int(df[generic_col].notna().sum()) if generic_col else 0
        with_atc = int(df[atc_col].notna().sum()) if atc_col else 0
        with_equivalence = int(df[equivalence_col].notna().sum()) if equivalence_col else 0

        return pd.DataFrame(
            [
                {"indicador": "registros_total", "valor": rows},
                {"indicador": "registros_vigentes", "valor": int(vigente)},
                {"indicador": "registros_no_vigentes", "valor": int(no_vigente)},
                {"indicador": "con_nombre_generico", "valor": with_generic},
                {"indicador": "con_codigo_atc", "valor": with_atc},
                {"indicador": "con_equivalencia", "valor": with_equivalence},
            ]
        )

    def sugammadex_opportunity(
        self,
        purchases: pd.DataFrame,
        target_non_bridion: float = 19_500,
    ) -> pd.DataFrame:
        df = self._normalize_columns(purchases)
        product_col = self._first_existing(df, ("nombre_producto", "description", "desc_homologada", "producto"))
        qty_col = self._first_existing(df, ("cantidad_factura", "qty_ordered", "cantidad_recibido", "qty"))
        price_col = self._first_existing(df, ("punit", "unit_price", "precio_unitario", "precio"))
        amount_col = self._first_existing(df, ("ptotal", "amount", "total"))
        supplier_col = self._first_existing(df, ("nombre_proveedor_homologado", "nombre_proveedor", "supplier"))
        clinic_col = self._first_existing(df, ("clinica", "clinic"))

        required = [product_col, qty_col, price_col]
        if any(column is None for column in required):
            return pd.DataFrame()

        work = df[df[product_col].map(self._norm_text).str.contains("sugammadex", na=False)].copy()
        if work.empty:
            return pd.DataFrame()

        work["_qty"] = pd.to_numeric(work[qty_col], errors="coerce").fillna(0)
        work["_price"] = pd.to_numeric(work[price_col], errors="coerce")
        if amount_col:
            work["_amount"] = pd.to_numeric(work[amount_col], errors="coerce")
        else:
            work["_amount"] = work["_qty"] * work["_price"]
        work["_segment"] = work[product_col].map(self._segment_sugammadex)
        work["_savings"] = 0.0
        non_bridion = work["_segment"] == "NO_BRIDION_TARGET"
        work.loc[non_bridion, "_savings"] = (
            (work.loc[non_bridion, "_price"] - target_non_bridion).clip(lower=0)
            * work.loc[non_bridion, "_qty"]
        )

        groups = []
        for segment, group in work.groupby("_segment", dropna=False):
            qty = float(group["_qty"].sum())
            amount = float(group["_amount"].sum())
            weighted = amount / qty if qty else 0.0
            groups.append(
                {
                    "segmento": segment,
                    "cantidad": qty,
                    "gasto_clp": round(amount),
                    "precio_pond": round(weighted),
                    "target": target_non_bridion if segment == "NO_BRIDION_TARGET" else pd.NA,
                    "ahorro_estimado_clp": round(float(group["_savings"].sum())),
                    "proveedores": group[supplier_col].nunique() if supplier_col else pd.NA,
                    "clinicas": group[clinic_col].nunique() if clinic_col else pd.NA,
                }
            )
        return pd.DataFrame(groups).sort_values("ahorro_estimado_clp", ascending=False)

    def _segment_sugammadex(self, value: object) -> str:
        text = self._norm_text(value)
        if any(brand in text for brand in PROTECTED_BRANDS):
            return "BRIDION_PROTEGIDO"
        return "NO_BRIDION_TARGET"

    def _normalize_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        normalized = dataframe.copy()
        normalized.columns = [self._slug(column) for column in normalized.columns]
        return normalized

    def _first_existing(self, dataframe: pd.DataFrame, columns: tuple[str, ...]) -> str | None:
        for column in columns:
            if column in dataframe.columns:
                return column
        return None

    def _contains(self, series: pd.Series, pattern: str) -> pd.Series:
        return series.astype("string").map(self._norm_text).str.contains(pattern, na=False)

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
