from __future__ import annotations

from typing import Mapping

import pandas as pd

from .base_agent import AgentResponse, BaseAgent
from ..config.settings import Settings, settings as default_settings


class NegotiationAnalystAgent(BaseAgent):
    name = "NegotiationAnalystAgent"
    role_description = "Analista de Negociaciones"
    system_prompt = (
        "Identifica oportunidades de ahorro y negociacion con base financiera: "
        "consolidacion de volumen, desviaciones contra referencia, aumentos de precio "
        "y palancas contractuales."
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
        consumption = self._get_dataframe(dataframes, "consumption")
        if orders.empty or homologation.empty:
            return self._empty_response(
                "No hay datos suficientes para estimar oportunidades de negociacion.",
                confidence=0.0,
                alerts=["Faltan purchase_orders.csv u homologation.csv"],
            )

        opportunities = self.find_opportunities(orders, homologation, consumption)
        total_savings = (
            float(opportunities["estimated_savings_CLP"].fillna(0).sum())
            if not opportunities.empty
            else 0.0
        )

        output_parts = [
            "Se evaluaron oportunidades por brecha de precio, consolidacion de volumen y tendencia de aumentos.",
            f"**Ahorro potencial estimado:** CLP {total_savings:,.0f}",
        ]
        if opportunities.empty:
            output_parts.append("No se identificaron oportunidades materiales con la informacion disponible.")
        else:
            output_parts.extend(["\n**Ranking de oportunidades:**", opportunities.head(20).to_markdown(index=False)])

        return AgentResponse(
            agent_name=self.name,
            output="\n".join(output_parts),
            confidence=0.86,
            alerts=[f"Ahorro potencial estimado: CLP {total_savings:,.0f}"] if total_savings else [],
            tables=[opportunities],
            sources=["purchase_orders", "homologation", "consumption"],
            assumptions=[
                "El ahorro se estima contra mejor precio homologado o mejor precio OC disponible.",
                "La recomendacion requiere validacion clinica cuando implique sustitucion.",
            ],
        )

    def find_opportunities(
        self,
        orders: pd.DataFrame,
        homologation: pd.DataFrame,
        consumption: pd.DataFrame,
    ) -> pd.DataFrame:
        opportunities = []
        opportunities.extend(self._price_gap_opportunities(orders, homologation))
        opportunities.extend(self._consolidation_opportunities(orders, homologation))
        opportunities.extend(self._price_increase_opportunities(orders))

        result = pd.DataFrame(
            opportunities,
            columns=[
                "rank_basis",
                "SKU",
                "supplier",
                "opportunity_type",
                "annualized_volume",
                "current_avg_price",
                "target_price",
                "estimated_savings_CLP",
                "recommended_lever",
                "calculation_method",
            ],
        )
        if result.empty:
            return result.drop(columns=["rank_basis"], errors="ignore")
        result = result.groupby(
            [
                "SKU",
                "supplier",
                "opportunity_type",
                "annualized_volume",
                "current_avg_price",
                "target_price",
                "recommended_lever",
                "calculation_method",
            ],
            dropna=False,
        )["estimated_savings_CLP"].max().reset_index()
        return result.sort_values("estimated_savings_CLP", ascending=False).reset_index(drop=True)

    def _price_gap_opportunities(self, orders: pd.DataFrame, homologation: pd.DataFrame) -> list[dict[str, object]]:
        clean_hom = homologation.dropna(subset=["unit_price"]).copy()
        target = clean_hom.groupby("sku")["unit_price"].min().reset_index(name="target_price")
        order_summary = (
            orders.groupby(["sku", "supplier"])
            .agg(
                ordered_volume=("qty_ordered", "sum"),
                current_avg_price=("unit_price", "mean"),
            )
            .reset_index()
            .merge(target, on="sku", how="left")
        )
        rows = []
        for _, row in order_summary.dropna(subset=["target_price"]).iterrows():
            current = float(row["current_avg_price"])
            target_price = float(row["target_price"])
            if current <= target_price:
                continue
            volume = float(row["ordered_volume"])
            savings = (current - target_price) * volume
            if savings <= 0:
                continue
            rows.append(
                {
                    "rank_basis": savings,
                    "SKU": row["sku"],
                    "supplier": row["supplier"],
                    "opportunity_type": "BRECHA_VS_MEJOR_REFERENCIA",
                    "annualized_volume": round(volume, 0),
                    "current_avg_price": round(current, 0),
                    "target_price": round(target_price, 0),
                    "estimated_savings_CLP": round(savings, 0),
                    "recommended_lever": "Amenaza de sustitucion homologada y compromiso de volumen.",
                    "calculation_method": "(precio promedio OC - mejor precio homologado) * volumen OC.",
                }
            )
        return rows

    def _consolidation_opportunities(self, orders: pd.DataFrame, homologation: pd.DataFrame) -> list[dict[str, object]]:
        supplier_counts = orders.groupby("sku")["supplier"].nunique().reset_index(name="supplier_count")
        multi_supplier_skus = supplier_counts[supplier_counts["supplier_count"] > 1]["sku"]
        rows = []
        for sku in multi_supplier_skus:
            sku_orders = orders[orders["sku"] == sku]
            if sku_orders.empty:
                continue
            best_price = float(sku_orders["unit_price"].min())
            volume = float(sku_orders["qty_ordered"].sum())
            avg_price = float(sku_orders["unit_price"].mean())
            savings = max(0.0, (avg_price - best_price) * volume)
            if savings <= 0:
                continue
            supplier = sku_orders.sort_values("unit_price").iloc[0]["supplier"]
            rows.append(
                {
                    "rank_basis": savings,
                    "SKU": sku,
                    "supplier": "MULTIPLES",
                    "opportunity_type": "CONSOLIDACION_DE_VOLUMEN",
                    "annualized_volume": round(volume, 0),
                    "current_avg_price": round(avg_price, 0),
                    "target_price": round(best_price, 0),
                    "estimated_savings_CLP": round(savings, 0),
                    "recommended_lever": f"Consolidar volumen con proveedor benchmark ({supplier}) y ventana contractual.",
                    "calculation_method": "(precio promedio multi-proveedor - mejor precio OC) * volumen total.",
                }
            )
        return rows

    def _price_increase_opportunities(self, orders: pd.DataFrame) -> list[dict[str, object]]:
        if "order_date" not in orders.columns:
            return []
        rows = []
        sorted_orders = orders.sort_values("order_date")
        grouped = sorted_orders.groupby(["sku", "supplier"])
        for (sku, supplier), group in grouped:
            if len(group) < 2:
                continue
            first = float(group.iloc[0]["unit_price"])
            last = float(group.iloc[-1]["unit_price"])
            if first <= 0 or last <= first * 1.03:
                continue
            volume = float(group["qty_ordered"].sum())
            savings = (last - first) * volume
            rows.append(
                {
                    "rank_basis": savings,
                    "SKU": sku,
                    "supplier": supplier,
                    "opportunity_type": "AUMENTO_DE_PRECIO_ACELERADO",
                    "annualized_volume": round(volume, 0),
                    "current_avg_price": round(last, 0),
                    "target_price": round(first, 0),
                    "estimated_savings_CLP": round(savings, 0),
                    "recommended_lever": "Congelar precio con contrato marco y revisar condiciones de pago.",
                    "calculation_method": "(ultimo precio - primer precio) * volumen OC del periodo.",
                }
            )
        return rows
