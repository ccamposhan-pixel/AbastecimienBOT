from __future__ import annotations

import re
import unicodedata
from typing import Mapping

import pandas as pd

from .base_agent import AgentResponse, BaseAgent
from ..config.settings import Settings, settings as default_settings


class DatabaseAnalystAgent(BaseAgent):
    name = "DatabaseAnalystAgent"
    role_description = "Analista de Base de Datos"
    system_prompt = (
        "Responde preguntas de negocio usando operaciones pandas sobre CSV cargados, "
        "entregando tablas, resumen ejecutivo y alertas de calidad de datos."
    )

    def __init__(self, app_settings: Settings = default_settings) -> None:
        self.settings = app_settings

    def run(
        self,
        query: str,
        context: dict,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> AgentResponse:
        normalized = self._normalize(query)
        table, interpretation, sources = self.answer_query(normalized, dataframes)
        quality = self.quality_report(dataframes)

        output_parts = [interpretation]
        if not table.empty:
            output_parts.extend(["\n**Resultado:**", table.head(30).to_markdown(index=False)])
        if not quality.empty:
            output_parts.extend(["\n**Alertas de calidad de datos:**", quality.head(12).to_markdown(index=False)])

        alerts = []
        if not quality.empty:
            alerts.append(f"{len(quality)} alerta(s) de calidad de datos")

        return AgentResponse(
            agent_name=self.name,
            output="\n".join(output_parts),
            confidence=0.82,
            alerts=alerts,
            tables=[table, quality],
            sources=sources,
            assumptions=[
                "Las consultas naturales se resuelven con patrones pandas deterministas.",
                "Para consultas no reconocidas se entrega resumen de datasets.",
            ],
        )

    def answer_query(
        self,
        query: str,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> tuple[pd.DataFrame, str, list[str]]:
        stock = self._get_dataframe(dataframes, "stock")
        orders = self._get_dataframe(dataframes, "purchase_orders")
        consumption = self._get_dataframe(dataframes, "consumption")
        homologation = self._get_dataframe(dataframes, "homologation")

        sku = self._extract_sku(query)
        if sku:
            table = self._sku_view(sku, stock, orders, consumption, homologation)
            return table, f"Vista integrada para {sku}.", [
                "stock",
                "purchase_orders",
                "consumption",
                "homologation",
            ]

        if any(term in query for term in ("orden", "oc", "po", "abierta", "pendiente")) and not orders.empty:
            table = orders.copy()
            if any(term in query for term in ("abierta", "pendiente", "transito")):
                table = table[table["status"].str.lower().fillna("") != "received"]
            table = table.sort_values("expected_arrival", na_position="last")
            return table, f"Consulta sobre ordenes de compra: {len(table)} fila(s) encontradas.", [
                "purchase_orders"
            ]

        if any(term in query for term in ("consumo", "consumido", "rotacion")) and not consumption.empty:
            table = (
                consumption.groupby("sku")
                .agg(total_consumed=("qty_consumed", "sum"), cost_centers=("cost_center", "nunique"))
                .reset_index()
                .sort_values("total_consumed", ascending=False)
            )
            return table, "Ranking de consumo acumulado por SKU.", ["consumption"]

        if any(term in query for term in ("proveedor", "proveedores")) and not homologation.empty:
            table = (
                homologation.groupby("supplier", dropna=False)
                .agg(skus=("sku", "nunique"), avg_unit_price=("unit_price", "mean"))
                .reset_index()
                .sort_values("skus", ascending=False)
            )
            table["avg_unit_price"] = table["avg_unit_price"].round(0)
            return table, "Resumen de proveedores por cobertura de catalogo homologado.", [
                "homologation"
            ]

        if any(term in query for term in ("precio", "precios", "unitario")) and not homologation.empty:
            table = (
                homologation.groupby("category", dropna=False)
                .agg(skus=("sku", "nunique"), avg_price=("unit_price", "mean"), max_price=("unit_price", "max"))
                .reset_index()
                .sort_values("avg_price", ascending=False)
            )
            table[["avg_price", "max_price"]] = table[["avg_price", "max_price"]].round(0)
            return table, "Resumen de precios homologados por categoria.", ["homologation"]

        if any(term in query for term in ("stock", "inventario", "bodega")) and not stock.empty:
            table = (
                stock.groupby("warehouse")
                .agg(skus=("sku", "nunique"), qty_available=("qty_available", "sum"))
                .reset_index()
                .sort_values("qty_available", ascending=False)
            )
            return table, "Resumen de stock disponible por bodega.", ["stock"]

        return self._dataset_overview(dataframes)

    def quality_report(self, dataframes: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
        rows: list[dict[str, object]] = []

        for name, dataframe in dataframes.items():
            if dataframe.empty:
                rows.append(
                    {
                        "dataset": name,
                        "issue": "DATASET_VACIO",
                        "detail": "Archivo no disponible o sin filas.",
                        "severity": "HIGH",
                    }
                )
                continue
            null_counts = dataframe.isna().sum()
            for column, count in null_counts.items():
                if int(count) > 0:
                    rows.append(
                        {
                            "dataset": name,
                            "issue": "VALORES_NULOS",
                            "detail": f"{column}: {int(count)} nulo(s).",
                            "severity": "MEDIUM",
                        }
                    )

        homologation = self._get_dataframe(dataframes, "homologation")
        if not homologation.empty:
            duplicates = (
                homologation.groupby(["generic_name", "brand", "uom"], dropna=True)["sku"]
                .nunique()
                .reset_index(name="sku_count")
            )
            duplicate_count = int((duplicates["sku_count"] > 1).sum())
            if duplicate_count:
                rows.append(
                    {
                        "dataset": "homologation",
                        "issue": "SKU_DUPLICADO_POTENCIAL",
                        "detail": f"{duplicate_count} grupo(s) con producto equivalente y codigos distintos.",
                        "severity": "HIGH",
                    }
                )
            uom_conflicts = (
                homologation.groupby("sku")["uom"].nunique().reset_index(name="uom_count")
            )
            conflict_count = int((uom_conflicts["uom_count"] > 1).sum())
            if conflict_count:
                rows.append(
                    {
                        "dataset": "homologation",
                        "issue": "UOM_INCONSISTENTE",
                        "detail": f"{conflict_count} SKU(s) con mas de una unidad de medida.",
                        "severity": "HIGH",
                    }
                )

        orders = self._get_dataframe(dataframes, "purchase_orders")
        if not orders.empty and not homologation.empty:
            unmatched = set(orders["sku"].dropna()) - set(homologation["sku"].dropna())
            if unmatched:
                rows.append(
                    {
                        "dataset": "purchase_orders",
                        "issue": "SKU_SIN_HOMOLOGACION",
                        "detail": ", ".join(sorted(unmatched)[:10]),
                        "severity": "HIGH",
                    }
                )

        stock = self._get_dataframe(dataframes, "stock")
        if not stock.empty and not homologation.empty:
            unmatched_stock = set(stock["sku"].dropna()) - set(homologation["sku"].dropna())
            if unmatched_stock:
                rows.append(
                    {
                        "dataset": "stock",
                        "issue": "SKU_SIN_HOMOLOGACION",
                        "detail": ", ".join(sorted(unmatched_stock)[:10]),
                        "severity": "MEDIUM",
                    }
                )

        return pd.DataFrame(rows, columns=["dataset", "issue", "detail", "severity"])

    def _sku_view(
        self,
        sku: str,
        stock: pd.DataFrame,
        orders: pd.DataFrame,
        consumption: pd.DataFrame,
        homologation: pd.DataFrame,
    ) -> pd.DataFrame:
        rows = []
        if not stock.empty:
            stock_row = stock[stock["sku"] == sku]
            rows.append(
                {
                    "metric": "stock_disponible",
                    "value": float(stock_row["qty_available"].sum()) if not stock_row.empty else 0,
                    "source": "stock",
                }
            )
        if not orders.empty:
            sku_orders = orders[orders["sku"] == sku]
            rows.append(
                {
                    "metric": "ordenes_compra",
                    "value": len(sku_orders),
                    "source": "purchase_orders",
                }
            )
            rows.append(
                {
                    "metric": "qty_pendiente",
                    "value": float(sku_orders["qty_pending"].sum()) if "qty_pending" in sku_orders else 0,
                    "source": "purchase_orders",
                }
            )
        if not consumption.empty:
            sku_consumption = consumption[consumption["sku"] == sku]
            rows.append(
                {
                    "metric": "consumo_total",
                    "value": float(sku_consumption["qty_consumed"].sum()),
                    "source": "consumption",
                }
            )
        if not homologation.empty:
            sku_hom = homologation[homologation["sku"] == sku]
            rows.append(
                {
                    "metric": "proveedores_homologados",
                    "value": sku_hom["supplier"].nunique(dropna=True),
                    "source": "homologation",
                }
            )
        return pd.DataFrame(rows)

    def _dataset_overview(
        self,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> tuple[pd.DataFrame, str, list[str]]:
        rows = [
            {
                "dataset": name,
                "rows": len(dataframe),
                "columns": len(dataframe.columns),
                "sku_count": dataframe["sku"].nunique() if "sku" in dataframe.columns else pd.NA,
            }
            for name, dataframe in dataframes.items()
        ]
        return pd.DataFrame(rows), "Resumen general de datasets cargados.", list(dataframes.keys())

    def _extract_sku(self, query: str) -> str | None:
        match = re.search(r"sku[-_\s]?\d{4}", query, flags=re.IGNORECASE)
        if not match:
            return None
        raw = match.group(0).upper().replace("_", "-").replace(" ", "-")
        if not raw.startswith("SKU-"):
            raw = raw.replace("SKU", "SKU-")
        return raw

    def _normalize(self, query: str) -> str:
        text = unicodedata.normalize("NFKD", query.lower().strip())
        return "".join(char for char in text if not unicodedata.combining(char))
