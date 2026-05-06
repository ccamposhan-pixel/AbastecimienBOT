from __future__ import annotations

from collections.abc import Iterable

from .config import COLUMN_ALIASES, CURRENCY_ALIASES, UNIT_ALIASES, UNIT_CONVERSIONS
from .models import PurchaseRecord, RawTable, StandardizationIssue, StandardizationResult
from .text import compact_key, normalize_key, normalize_text


def parse_number(value: object, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        # Evita propagar NaN que rompe ordenamientos y cálculos.
        if isinstance(value, float) and value != value:  # NaN
            return default
        return float(value)

    text = str(value).strip()
    if not text:
        return default

    cleaned = "".join(ch for ch in text if ch.isdigit() or ch in ",.-")
    if not cleaned or cleaned in {"-", ".", ","}:
        return default

    sign = -1.0 if cleaned.startswith("-") else 1.0
    cleaned = cleaned.replace("-", "")

    if "." in cleaned and "," in cleaned:
        decimal_sep = "." if cleaned.rfind(".") > cleaned.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        cleaned = cleaned.replace(thousands_sep, "")
        cleaned = cleaned.replace(decimal_sep, ".")
    elif "," in cleaned:
        cleaned = _normalize_single_separator(cleaned, ",")
    elif "." in cleaned:
        cleaned = _normalize_single_separator(cleaned, ".")

    try:
        return sign * float(cleaned)
    except ValueError:
        return default


def _normalize_single_separator(value: str, separator: str) -> str:
    parts = value.split(separator)
    if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
        return "".join(parts)
    if len(parts) == 2 and len(parts[1]) <= 2:
        return ".".join(parts)
    return "".join(parts[:-1]) + "." + parts[-1] if len(parts[-1]) <= 2 else "".join(parts)


def normalize_unit(value: object) -> tuple[str, float]:
    key = compact_key(value or "unit")
    for canonical, aliases in UNIT_ALIASES.items():
        if key in {compact_key(alias) for alias in aliases}:
            return UNIT_CONVERSIONS[canonical]
    return ("unit", 1.0)


def normalize_currency(value: object) -> str:
    key = compact_key(value or "CLP")
    for canonical, aliases in CURRENCY_ALIASES.items():
        if key in {compact_key(alias) for alias in aliases}:
            return canonical
    return key.upper() if key else "CLP"


def standardize_tables(
    tables: Iterable[RawTable],
    fx_to_clp: dict[str, float] | None = None,
) -> StandardizationResult:
    fx_rates = {"CLP": 1.0, **(fx_to_clp or {})}
    records: list[PurchaseRecord] = []
    issues: list[StandardizationIssue] = []

    for table in tables:
        if not table.rows:
            issues.append(StandardizationIssue(table.source_file, 0, "warning", "CSV sin filas."))
            continue

        column_map = _build_column_map(table.rows[0].keys())
        required = ["supplier", "description"]
        missing = [name for name in required if name not in column_map]
        if missing:
            issues.append(
                StandardizationIssue(
                    table.source_file,
                    0,
                    "error",
                    f"Faltan columnas obligatorias: {', '.join(missing)}.",
                )
            )
            continue

        for row_number, row in enumerate(table.rows, start=2):
            record = _standardize_row(table.source_file, row_number, row, column_map, fx_rates, issues)
            if record is not None:
                records.append(record)

    return StandardizationResult(records=records, issues=issues)


def _build_column_map(columns: Iterable[str]) -> dict[str, str]:
    available = {normalize_key(column): column for column in columns}
    compact_available = {compact_key(column): column for column in columns}
    column_map: dict[str, str] = {}

    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize_key(alias)
            compact_alias = compact_key(alias)
            if normalized_alias in available:
                column_map[canonical] = available[normalized_alias]
                break
            if compact_alias in compact_available:
                column_map[canonical] = compact_available[compact_alias]
                break

    return column_map


def _value(row: dict[str, str], column_map: dict[str, str], canonical: str, default: str = "") -> str:
    source_column = column_map.get(canonical)
    if source_column is None:
        return default
    value = row.get(source_column)
    return str(value).strip() if value is not None else default


def _standardize_row(
    source_file: str,
    row_number: int,
    row: dict[str, str],
    column_map: dict[str, str],
    fx_rates: dict[str, float],
    issues: list[StandardizationIssue],
) -> PurchaseRecord | None:
    supplier = _value(row, column_map, "supplier")
    description = _value(row, column_map, "description")
    if not supplier or not description:
        issues.append(StandardizationIssue(source_file, row_number, "warning", "Fila omitida sin proveedor o descripcion."))
        return None

    quantity = parse_number(_value(row, column_map, "quantity"), default=1.0)
    unit_price = parse_number(_value(row, column_map, "unit_price"), default=None)
    total = parse_number(_value(row, column_map, "total"), default=None)

    if quantity is None or quantity <= 0:
        issues.append(StandardizationIssue(source_file, row_number, "warning", "Fila omitida con cantidad invalida."))
        return None

    if unit_price is None and total is not None:
        unit_price = total / quantity
    if total is None and unit_price is not None:
        total = unit_price * quantity
    if unit_price is None or total is None:
        issues.append(StandardizationIssue(source_file, row_number, "warning", "Fila omitida sin precio unitario ni total."))
        return None

    currency = normalize_currency(_value(row, column_map, "currency", "CLP"))
    if currency not in fx_rates:
        issues.append(
            StandardizationIssue(
                source_file,
                row_number,
                "warning",
                f"Fila omitida: falta tipo de cambio a CLP para {currency}. Use --fx {currency}=valor.",
            )
        )
        return None

    normalized_unit, unit_factor = normalize_unit(_value(row, column_map, "unit", "unit"))
    quantity_base = quantity * unit_factor
    if quantity_base <= 0:
        issues.append(StandardizationIssue(source_file, row_number, "warning", "Fila omitida con unidad invalida."))
        return None

    fx = fx_rates[currency]
    total_spend_clp = total * fx
    unit_price_clp_base = total_spend_clp / quantity_base

    return PurchaseRecord(
        source_file=source_file,
        row_number=row_number,
        supplier=supplier,
        item_code=_value(row, column_map, "item_code"),
        description=description,
        category=_value(row, column_map, "category", "Sin categoria") or "Sin categoria",
        quantity=quantity,
        unit=_value(row, column_map, "unit", "unit"),
        unit_price=unit_price,
        total=total,
        currency=currency,
        date=_value(row, column_map, "date"),
        normalized_supplier=normalize_text(supplier),
        normalized_description=normalize_text(description),
        normalized_unit=normalized_unit,
        quantity_base=quantity_base,
        unit_price_clp_base=unit_price_clp_base,
        total_spend_clp=total_spend_clp,
    )
