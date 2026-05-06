from __future__ import annotations

from typing import Mapping

import pandas as pd

from .base_agent import AgentResponse, BaseAgent
from ..config.settings import Settings, settings as default_settings


class PriceAuditAgent(BaseAgent):
    name = "PriceAuditAgent"
    role_description = "Analista de Sobrecostos y Precios Erroneos"
    system_prompt = (
        "Detecta desviaciones de precio, diferencias de unidad de medida, duplicados "
        "y precios no registrados con impacto financiero en CLP."
    )

    def __init__(self, app_settings: Settings = default_settings) -> None:
        self.settings = app_settings

    def run(
        self,
        query: str,
        context: dict,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> AgentResponse:
        orders = self._get_dataframe(dataframes, "purchase_orders")
        homologation = self._get_dataframe(dataframes, "homologation")
        if orders.empty or homologation.empty:
            return self._empty_response(
                "No hay datos suficientes para auditar precios. Se requieren OCs y homologacion.",
                confidence=0.0,
                alerts=["Faltan purchase_orders.csv u homologation.csv"],
            )

        anomalies = self.detect_anomalies(orders, homologation)
        total_exposure = float(anomalies["estimated_impact_CLP"].fillna(0).sum()) if not anomalies.empty else 0.0

        output_parts = [
            (
                "Se auditaron precios de OC contra precio de referencia homologado, "
                "unidad de medida y duplicidad operacional."
            ),
            f"**Exposicion estimada total:** CLP {total_exposure:,.0f}",
            f"**Umbral de desviacion aplicado:** +/- {self.settings.price_deviation_pct:.1%}",
        ]
        if anomalies.empty:
            output_parts.append("No se detectaron anomalias con los criterios configurados.")
        else:
            output_parts.extend(["\n**Reporte de anomalias:**", anomalies.head(20).to_markdown(index=False)])

        alerts = []
        if total_exposure > 0:
            alerts.append(f"Exposicion estimada por anomalias: CLP {total_exposure:,.0f}")
        if not anomalies.empty:
            alerts.append(f"{len(anomalies)} anomalia(s) detectada(s)")

        return AgentResponse(
            agent_name=self.name,
            output="\n".join(output_parts),
            confidence=0.9,
            alerts=alerts,
            tables=[anomalies],
            sources=["purchase_orders", "homologation"],
            assumptions=[
                "El impacto se calcula sobre qty_ordered cuando no existe factura recibida.",
                "La referencia prioriza SKU+proveedor; si no existe, usa mediana por SKU.",
            ],
        )

    def detect_anomalies(self, orders: pd.DataFrame, homologation: pd.DataFrame) -> pd.DataFrame:
        reference = self._reference_prices(homologation)
        audited = orders.copy().merge(reference, on=["sku", "supplier"], how="left")
        generic_reference = self._generic_reference_prices(homologation)
        audited = audited.merge(generic_reference, on="sku", how="left")

        audited["reference_price"] = audited["reference_price"].fillna(audited["sku_reference_price"])
        audited["reference_uom"] = audited["reference_uom"].fillna(audited["sku_reference_uom"])
        audited["deviation_pct"] = (
            (audited["unit_price"] - audited["reference_price"]) / audited["reference_price"]
        )

        rows: list[dict[str, object]] = []
        for _, row in audited.iterrows():
            rows.extend(self._row_anomalies(row))

        duplicate_rows = self._duplicate_anomalies(orders)
        rows.extend(duplicate_rows)

        result = pd.DataFrame(
            rows,
            columns=[
                "PO_id",
                "SKU",
                "supplier",
                "anomaly_type",
                "deviation_pct",
                "estimated_impact_CLP",
                "recommended_action",
            ],
        )
        if result.empty:
            return result
        return result.sort_values("estimated_impact_CLP", ascending=False).reset_index(drop=True)

    def _reference_prices(self, homologation: pd.DataFrame) -> pd.DataFrame:
        clean = homologation.dropna(subset=["unit_price"]).copy()
        return (
            clean.groupby(["sku", "supplier"])
            .agg(reference_price=("unit_price", "median"), reference_uom=("uom", "first"))
            .reset_index()
        )

    def _generic_reference_prices(self, homologation: pd.DataFrame) -> pd.DataFrame:
        clean = homologation.dropna(subset=["unit_price"]).copy()
        return (
            clean.groupby("sku")
            .agg(sku_reference_price=("unit_price", "median"), sku_reference_uom=("uom", "first"))
            .reset_index()
        )

    def _row_anomalies(self, row: pd.Series) -> list[dict[str, object]]:
        anomalies: list[dict[str, object]] = []
        reference = row.get("reference_price")
        price = row.get("unit_price")
        qty = float(row.get("qty_ordered", 0) or 0)

        if pd.isna(reference):
            anomalies.append(
                self._anomaly(
                    row,
                    "PRECIO_NO_REGISTRADO",
                    pd.NA,
                    0.0,
                    "Registrar precio de referencia antes de liberar nueva compra.",
                )
            )
            return anomalies

        if pd.isna(price):
            anomalies.append(
                self._anomaly(
                    row,
                    "PRECIO_NO_REGISTRADO",
                    pd.NA,
                    0.0,
                    "Completar precio unitario de OC para auditoria.",
                )
            )
        else:
            deviation = (float(price) - float(reference)) / float(reference)
            if abs(deviation) > self.settings.price_deviation_pct:
                impact = abs(float(price) - float(reference)) * qty
                anomalies.append(
                    self._anomaly(
                        row,
                        "PRECIO_DESVIADO",
                        deviation,
                        impact,
                        "Solicitar nota de credito, bloqueo de pago o renegociacion segun estado OC.",
                    )
                )

        row_uom = str(row.get("uom", "")).lower()
        reference_uom = str(row.get("reference_uom", "")).lower()
        if reference_uom and row_uom and row_uom != reference_uom:
            anomalies.append(
                self._anomaly(
                    row,
                    "UOM_MISMATCH",
                    pd.NA,
                    0.0,
                    "Validar conversion de unidad antes de recepcion o pago.",
                )
            )

        return anomalies

    def _duplicate_anomalies(self, orders: pd.DataFrame) -> list[dict[str, object]]:
        required = ["sku", "supplier", "order_date", "qty_ordered"]
        if not set(required).issubset(orders.columns):
            return []

        duplicates = orders[orders.duplicated(required, keep=False)].copy()
        rows: list[dict[str, object]] = []
        for _, row in duplicates.iterrows():
            impact = float(row.get("unit_price", 0) or 0) * float(row.get("qty_ordered", 0) or 0)
            rows.append(
                self._anomaly(
                    row,
                    "DUPLICADO",
                    pd.NA,
                    impact,
                    "Validar duplicidad de OC y anular linea si no corresponde.",
                )
            )
        return rows

    def _anomaly(
        self,
        row: pd.Series,
        anomaly_type: str,
        deviation_pct: object,
        estimated_impact: float,
        recommended_action: str,
    ) -> dict[str, object]:
        return {
            "PO_id": row.get("po_id", row.get("PO_id")),
            "SKU": row.get("sku", row.get("SKU")),
            "supplier": row.get("supplier"),
            "anomaly_type": anomaly_type,
            "deviation_pct": deviation_pct,
            "estimated_impact_CLP": round(float(estimated_impact), 0),
            "recommended_action": recommended_action,
        }
