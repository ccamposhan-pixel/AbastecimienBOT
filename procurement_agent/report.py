from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .models import AnalysisResult, PurchaseRecord


def write_outputs(result: AnalysisResult, records: list[PurchaseRecord], output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    standardized_path = root / "standardized_prices.csv"
    opportunities_path = root / "opportunities.json"
    report_path = root / "report.md"

    _write_standardized_csv(standardized_path, records)
    opportunities_path.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path.write_text(render_markdown(result), encoding="utf-8")

    return {
        "standardized_csv": standardized_path,
        "opportunities_json": opportunities_path,
        "report": report_path,
    }


def render_markdown(result: AnalysisResult) -> str:
    summary = result.summary
    lines = [
        "# Reporte de eficiencia de proveedores",
        "",
        "## Resumen ejecutivo",
        "",
        f"- Registros analizados: {summary.record_count}",
        f"- Proveedores unicos: {summary.supplier_count}",
        f"- Categorias: {summary.category_count}",
        f"- Gasto total estandarizado: {format_clp(summary.total_spend_clp)}",
        f"- Ahorro estimado por mejores precios comparables: {format_clp(summary.estimated_savings_clp)} "
        f"({summary.estimated_savings_pct:.1%})",
        f"- Proveedores de cola larga: {summary.long_tail_supplier_count}",
        f"- Gasto en cola larga: {format_clp(summary.long_tail_spend_clp)}",
        "",
        "## Mejores oportunidades por precio",
        "",
    ]

    if result.item_opportunities:
        lines.extend(
            [
                "| Producto comparable | Categoria | Proveedores | Mejor proveedor | Precio min CLP/base | Spread | Ahorro estimado |",
                "| --- | --- | ---: | --- | ---: | ---: | ---: |",
            ]
        )
        for opportunity in result.item_opportunities[:20]:
            lines.append(
                "| "
                f"{opportunity.representative_description} | "
                f"{opportunity.category} | "
                f"{opportunity.supplier_count} | "
                f"{opportunity.best_supplier} | "
                f"{format_clp(opportunity.best_unit_price_clp)} | "
                f"{opportunity.price_spread_pct:.1%} | "
                f"{format_clp(opportunity.potential_savings_clp)} |"
            )
    else:
        lines.append("No se detectaron oportunidades con proveedores comparables.")

    lines.extend(["", "## Consolidacion y desatomizacion", ""])
    if result.supplier_opportunities:
        lines.extend(
            [
                "| Categoria | Proveedores | Lider actual | Gasto lider | Proveedores cola | Gasto cola | Recomendacion |",
                "| --- | ---: | --- | ---: | ---: | ---: | --- |",
            ]
        )
        for opportunity in result.supplier_opportunities[:20]:
            lines.append(
                "| "
                f"{opportunity.category} | "
                f"{opportunity.supplier_count} | "
                f"{opportunity.leading_supplier} | "
                f"{format_clp(opportunity.leading_supplier_spend_clp)} | "
                f"{opportunity.long_tail_supplier_count} | "
                f"{format_clp(opportunity.long_tail_spend_clp)} | "
                f"{opportunity.recommendation} |"
            )
    else:
        lines.append("No se detectaron categorias con fragmentacion suficiente para recomendar consolidacion.")

    lines.extend(["", "## Calidad de datos", ""])
    if result.issues:
        for issue in result.issues[:50]:
            lines.append(f"- {issue.level.upper()} {issue.source_file}:{issue.row_number} - {issue.message}")
    else:
        lines.append("Sin advertencias relevantes.")

    lines.extend(
        [
            "",
            "## Lectura recomendada",
            "",
            "- Validar contratos, descuentos por volumen, plazos y calidad antes de ejecutar cambios.",
            "- Revisar codigos maestros para mejorar el matching de productos comparables.",
            "- Cargar tipos de cambio reales con `--fx` cuando existan monedas distintas a CLP.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_standardized_csv(path: Path, records: list[PurchaseRecord]) -> None:
    fieldnames = [
        "source_file",
        "row_number",
        "supplier",
        "item_code",
        "description",
        "category",
        "quantity",
        "unit",
        "unit_price",
        "total",
        "currency",
        "date",
        "normalized_unit",
        "quantity_base",
        "unit_price_clp_base",
        "total_spend_clp",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({field: getattr(record, field) for field in fieldnames})


def format_clp(value: float) -> str:
    rounded = round(value)
    return f"CLP {rounded:,.0f}".replace(",", ".")
