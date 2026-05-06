from __future__ import annotations

from typing import Mapping

import pandas as pd

from .base_agent import AgentResponse, BaseAgent
from .materials_analyst import MaterialsAnalystAgent
from ..config.settings import Settings, settings as default_settings


class CoveragePlannerAgent(BaseAgent):
    name = "CoveragePlannerAgent"
    role_description = "Supervisor de Compra / Planner"
    system_prompt = (
        "Evalua cobertura, reposicion, rotacion, alzas de consumo y errores de compra "
        "para materiales hospitalarios, priorizando criticidad clinica."
    )

    def __init__(self, app_settings: Settings = default_settings) -> None:
        self.settings = app_settings
        self.materials_agent = MaterialsAnalystAgent(app_settings)

    def run(
        self,
        query: str,
        context: dict,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> AgentResponse:
        stock = self._get_dataframe(dataframes, "stock")
        orders = self._get_dataframe(dataframes, "purchase_orders")
        consumption = self._get_dataframe(dataframes, "consumption")
        homologation = self._get_dataframe(dataframes, "homologation")

        if stock.empty:
            return self._empty_response(
                "No hay datos de stock disponibles para calcular cobertura.",
                confidence=0.0,
                alerts=["Falta stock.csv"],
            )

        dashboard = self.build_dashboard(stock, orders, consumption, homologation)
        reorder = self.build_reorder_suggestions(dashboard)
        alerts_table = self.build_alert_summary(dashboard)

        critical_count = int((dashboard["status"] == "CRITICO").sum())
        alert_count = int((dashboard["status"] == "ALERTA").sum())
        output_parts = [
            (
                "Se calculo cobertura considerando stock disponible, ordenes abiertas, "
                "consumo 90d/30d, rotacion y criticidad clinica."
            ),
            f"**Resultado:** {critical_count} SKU(s) criticos y {alert_count} SKU(s) en alerta.",
            "\n**Dashboard priorizado:**",
            dashboard.head(15).to_markdown(index=False),
        ]
        if not reorder.empty:
            output_parts.extend(["\n**Sugerencias de reposicion:**", reorder.head(15).to_markdown(index=False)])
        if not alerts_table.empty:
            output_parts.extend(["\n**Alertas consolidadas:**", alerts_table.head(15).to_markdown(index=False)])

        alerts = []
        if critical_count:
            alerts.append(f"{critical_count} SKU(s) con estado CRITICO")
        if not alerts_table.empty:
            alerts.append("Existen alertas de consumo, sobrestock o error de compra")

        return AgentResponse(
            agent_name=self.name,
            output="\n".join(output_parts),
            confidence=0.88,
            alerts=alerts,
            tables=[dashboard, reorder, alerts_table],
            sources=["stock", "purchase_orders", "consumption", "homologation"],
            assumptions=[
                f"Lead time fijo: {self.settings.lead_time_days} dias.",
                f"Buffer de seguridad: {self.settings.safety_buffer_days} dias.",
            ],
        )

    def build_dashboard(
        self,
        stock: pd.DataFrame,
        orders: pd.DataFrame,
        consumption: pd.DataFrame,
        homologation: pd.DataFrame,
    ) -> pd.DataFrame:
        analysis_date = self._analysis_date(consumption, orders)
        stock_by_sku = self._stock_by_sku(stock)
        consumption_stats = self._consumption_stats(consumption, analysis_date)
        order_stats = self._order_stats(orders, analysis_date)
        material_stats = self._material_stats(homologation)

        dashboard = (
            stock_by_sku.merge(consumption_stats, on="sku", how="left")
            .merge(order_stats, on="sku", how="left")
            .merge(material_stats, on="sku", how="left")
        )

        fill_zero = [
            "avg_daily_consumption_90d",
            "avg_daily_consumption_30d",
            "consumption_90d",
            "consumption_180d",
            "qty_ordered_90d",
            "in_transit",
            "open_po_lines_30d",
        ]
        for column in fill_zero:
            if column in dashboard.columns:
                dashboard[column] = dashboard[column].fillna(0)

        dashboard["criticality"] = dashboard["criticality"].fillna("PENDIENTE")
        dashboard["rotation_class"] = dashboard.apply(self._rotation_class, axis=1)
        dashboard["coverage_days"] = dashboard.apply(self._coverage_days, axis=1)
        dashboard["spike_ratio"] = dashboard.apply(self._spike_ratio, axis=1)
        dashboard["spike_flag"] = dashboard["spike_ratio"] > self.settings.spike_multiplier
        dashboard["spike_absolute_qty_diff_30d"] = (
            (dashboard["avg_daily_consumption_30d"] - dashboard["avg_daily_consumption_90d"]) * 30
        ).clip(lower=0).round(2)
        horizon_days = self.settings.lead_time_days + self.settings.safety_buffer_days
        dashboard["estimated_stock_impact_current_trend"] = (
            (dashboard["avg_daily_consumption_30d"] - dashboard["avg_daily_consumption_90d"])
            * horizon_days
        ).clip(lower=0).round(2)
        dashboard["purchasing_error_flag"] = dashboard.apply(self._purchasing_error_flag, axis=1)
        dashboard["reorder_alert"] = dashboard["coverage_days"] < horizon_days
        dashboard["risk_reason"] = dashboard.apply(self._risk_reason, axis=1)
        dashboard["status"] = dashboard.apply(self._status, axis=1)

        dashboard["coverage_days"] = dashboard["coverage_days"].round(1)
        dashboard["avg_daily_consumption_90d"] = dashboard["avg_daily_consumption_90d"].round(2)
        dashboard["avg_daily_consumption_30d"] = dashboard["avg_daily_consumption_30d"].round(2)
        dashboard["spike_ratio"] = dashboard["spike_ratio"].round(2)

        criticality_rank = {"CRITICO": 0, "ESENCIAL": 1, "PENDIENTE": 2, "GENERAL": 3}
        status_rank = {"CRITICO": 0, "ALERTA": 1, "OK": 2}
        dashboard["_criticality_rank"] = dashboard["criticality"].map(criticality_rank).fillna(9)
        dashboard["_status_rank"] = dashboard["status"].map(status_rank).fillna(9)
        dashboard = dashboard.sort_values(
            ["_criticality_rank", "_status_rank", "coverage_days", "sku"],
            ascending=[True, True, True, True],
        )
        return dashboard[
            [
                "sku",
                "description",
                "qty_available",
                "in_transit",
                "avg_daily_consumption_90d",
                "avg_daily_consumption_30d",
                "coverage_days",
                "rotation_class",
                "criticality",
                "status",
                "spike_flag",
                "purchasing_error_flag",
                "risk_reason",
                "spike_ratio",
                "spike_absolute_qty_diff_30d",
                "estimated_stock_impact_current_trend",
            ]
        ].reset_index(drop=True)

    def build_reorder_suggestions(self, dashboard: pd.DataFrame) -> pd.DataFrame:
        horizon_days = self.settings.lead_time_days + self.settings.safety_buffer_days
        reorder = dashboard[dashboard["reorder_alert"] if "reorder_alert" in dashboard.columns else dashboard["coverage_days"] < horizon_days].copy()
        if reorder.empty:
            reorder = dashboard[dashboard["coverage_days"] < horizon_days].copy()
        if reorder.empty:
            return pd.DataFrame(
                columns=["sku", "description", "suggested_qty", "justification", "criticality"]
            )

        reorder["suggested_qty"] = (
            reorder["avg_daily_consumption_90d"] * horizon_days
            - reorder["qty_available"]
            - reorder["in_transit"]
        ).clip(lower=0).round(0).astype(int)
        reorder["justification"] = reorder.apply(
            lambda row: (
                f"Cobertura {row['coverage_days']} dias vs umbral {horizon_days}; "
                f"criticidad {row['criticality']}."
            ),
            axis=1,
        )
        return reorder[
            ["sku", "description", "suggested_qty", "justification", "criticality", "status"]
        ].reset_index(drop=True)

    def build_alert_summary(self, dashboard: pd.DataFrame) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        for _, row in dashboard.iterrows():
            if row["status"] in {"CRITICO", "ALERTA"} or row["spike_flag"] or row["purchasing_error_flag"]:
                rows.append(
                    {
                        "sku": row["sku"],
                        "description": row["description"],
                        "criticality": row["criticality"],
                        "status": row["status"],
                        "risk_reason": row["risk_reason"],
                        "recommended_action": self._recommended_action(row),
                    }
                )
        return pd.DataFrame(
            rows,
            columns=[
                "sku",
                "description",
                "criticality",
                "status",
                "risk_reason",
                "recommended_action",
            ],
        )

    def _analysis_date(self, consumption: pd.DataFrame, orders: pd.DataFrame) -> pd.Timestamp:
        dates = []
        if not consumption.empty and "date" in consumption.columns:
            dates.extend(consumption["date"].dropna().tolist())
        if not orders.empty and "order_date" in orders.columns:
            dates.extend(orders["order_date"].dropna().tolist())
        return max(dates) if dates else pd.Timestamp.today().normalize()

    def _stock_by_sku(self, stock: pd.DataFrame) -> pd.DataFrame:
        descriptions = stock.groupby("sku")["description"].first().reset_index()
        quantities = stock.groupby("sku")["qty_available"].sum().reset_index()
        return descriptions.merge(quantities, on="sku", how="left")

    def _consumption_stats(self, consumption: pd.DataFrame, analysis_date: pd.Timestamp) -> pd.DataFrame:
        if consumption.empty:
            return pd.DataFrame(columns=["sku"])

        data = consumption.copy()
        start_90 = analysis_date - pd.Timedelta(days=89)
        start_30 = analysis_date - pd.Timedelta(days=29)
        start_180 = analysis_date - pd.Timedelta(days=179)

        recent_90 = data[data["date"] >= start_90]
        recent_30 = data[data["date"] >= start_30]
        recent_180 = data[data["date"] >= start_180]

        stats = pd.DataFrame({"sku": data["sku"].drop_duplicates()})
        consumption_90 = recent_90.groupby("sku")["qty_consumed"].sum().reset_index(name="consumption_90d")
        consumption_30 = recent_30.groupby("sku")["qty_consumed"].sum().reset_index(name="consumption_30d")
        consumption_180 = recent_180.groupby("sku")["qty_consumed"].sum().reset_index(name="consumption_180d")
        month_count = (
            recent_90.assign(month=recent_90["date"].dt.to_period("M").astype(str))
            .groupby("sku")["month"]
            .nunique()
            .reset_index(name="months_consumed_90d")
        )

        for frame in (consumption_90, consumption_30, consumption_180, month_count):
            stats = stats.merge(frame, on="sku", how="left")

        stats["avg_daily_consumption_90d"] = stats["consumption_90d"].fillna(0) / 90
        stats["avg_daily_consumption_30d"] = stats["consumption_30d"].fillna(0) / 30
        return stats

    def _order_stats(self, orders: pd.DataFrame, analysis_date: pd.Timestamp) -> pd.DataFrame:
        if orders.empty:
            return pd.DataFrame(columns=["sku"])

        data = orders.copy()
        open_orders = data[data["status"].str.lower().fillna("") != "received"]
        in_transit = open_orders.groupby("sku")["qty_pending"].sum().reset_index(name="in_transit")

        start_90 = analysis_date - pd.Timedelta(days=89)
        start_30 = analysis_date - pd.Timedelta(days=29)
        recent_90 = data[data["order_date"] >= start_90]
        recent_30_open = open_orders[open_orders["order_date"] >= start_30]

        ordered_90 = recent_90.groupby("sku")["qty_ordered"].sum().reset_index(name="qty_ordered_90d")
        open_lines_30 = recent_30_open.groupby("sku")["po_id"].count().reset_index(name="open_po_lines_30d")

        stats = pd.DataFrame({"sku": data["sku"].drop_duplicates()})
        return stats.merge(in_transit, on="sku", how="left").merge(ordered_90, on="sku", how="left").merge(
            open_lines_30, on="sku", how="left"
        )

    def _material_stats(self, homologation: pd.DataFrame) -> pd.DataFrame:
        if homologation.empty:
            return pd.DataFrame(columns=["sku", "criticality"])
        if "criticality" not in homologation.columns:
            homologation = self.materials_agent.enrich_catalog(homologation)
        rank = {"CRITICO": 0, "ESENCIAL": 1, "PENDIENTE": 2, "GENERAL": 3}
        material = homologation.copy()
        material["_rank"] = material["criticality"].map(rank).fillna(9)
        return material.sort_values("_rank").groupby("sku").first().reset_index()[["sku", "criticality"]]

    def _rotation_class(self, row: pd.Series) -> str:
        consumption_90d = row.get("consumption_90d", 0) or 0
        consumption_180d = row.get("consumption_180d", 0) or 0
        months = row.get("months_consumed_90d", 0) or 0
        if consumption_180d == 0:
            return "SIN_MOVIMIENTO"
        if consumption_90d == 0:
            return "BAJA"
        if months >= 3:
            return "ALTA"
        return "MEDIA"

    def _coverage_days(self, row: pd.Series) -> float:
        avg = float(row.get("avg_daily_consumption_90d", 0) or 0)
        available = float(row.get("qty_available", 0) or 0)
        in_transit = float(row.get("in_transit", 0) or 0)
        if avg <= 0:
            return float("inf") if available + in_transit > 0 else 0.0
        return (available + in_transit) / avg

    def _spike_ratio(self, row: pd.Series) -> float:
        avg90 = float(row.get("avg_daily_consumption_90d", 0) or 0)
        avg30 = float(row.get("avg_daily_consumption_30d", 0) or 0)
        if avg90 <= 0:
            return float("inf") if avg30 > 0 else 0.0
        return avg30 / avg90

    def _purchasing_error_flag(self, row: pd.Series) -> bool:
        consumption_90d = float(row.get("consumption_90d", 0) or 0)
        qty_ordered_90d = float(row.get("qty_ordered_90d", 0) or 0)
        coverage_days = float(row.get("coverage_days", 0) or 0)
        open_po_lines_30d = float(row.get("open_po_lines_30d", 0) or 0)
        over_order = consumption_90d > 0 and qty_ordered_90d > consumption_90d * self.settings.overstock_ratio
        overstock = coverage_days > self.settings.overstock_days
        duplicate_no_movement = open_po_lines_30d > 1 and consumption_90d == 0
        low_rotation_with_open_po = row.get("rotation_class") in {"BAJA", "SIN_MOVIMIENTO"} and float(row.get("in_transit", 0) or 0) > 0
        return bool(over_order or overstock or duplicate_no_movement or low_rotation_with_open_po)

    def _risk_reason(self, row: pd.Series) -> str:
        reasons = []
        horizon_days = self.settings.lead_time_days + self.settings.safety_buffer_days
        if row.get("coverage_days", 0) < horizon_days:
            reasons.append("Cobertura bajo umbral de reposicion")
        if row.get("spike_flag", False):
            reasons.append("Alza de consumo detectada; revisar causa clinica, estacional o error de registro")
        if row.get("purchasing_error_flag", False):
            reasons.append("Posible error de compra o sobrestock")
        if row.get("rotation_class") in {"BAJA", "SIN_MOVIMIENTO"} and float(row.get("in_transit", 0) or 0) > 0:
            reasons.append("Baja rotacion con OC abierta")
        return "; ".join(reasons) if reasons else "Sin alerta relevante"

    def _status(self, row: pd.Series) -> str:
        horizon_days = self.settings.lead_time_days + self.settings.safety_buffer_days
        if row.get("coverage_days", 0) < horizon_days and row.get("criticality") == "CRITICO":
            return "CRITICO"
        if row.get("coverage_days", 0) < horizon_days / 2:
            return "CRITICO"
        if row.get("coverage_days", 0) < horizon_days or row.get("spike_flag") or row.get("purchasing_error_flag"):
            return "ALERTA"
        return "OK"

    def _recommended_action(self, row: pd.Series) -> str:
        if row["status"] == "CRITICO":
            return "Priorizar compra o reasignacion interna inmediata."
        if row["spike_flag"]:
            return "Validar consumo con unidad clinica y ajustar forecast."
        if row["purchasing_error_flag"]:
            return "Revisar OC abierta, rotacion y necesidad real antes de recibir."
        return "Monitorear en ciclo semanal de abastecimiento."
