from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RawTable:
    source_file: str
    rows: list[dict[str, str]]


@dataclass(frozen=True)
class StandardizationIssue:
    source_file: str
    row_number: int
    level: str
    message: str


@dataclass(frozen=True)
class PurchaseRecord:
    source_file: str
    row_number: int
    supplier: str
    item_code: str
    description: str
    category: str
    quantity: float
    unit: str
    unit_price: float
    total: float
    currency: str
    date: str
    normalized_supplier: str
    normalized_description: str
    normalized_unit: str
    quantity_base: float
    unit_price_clp_base: float
    total_spend_clp: float


@dataclass(frozen=True)
class StandardizationResult:
    records: list[PurchaseRecord]
    issues: list[StandardizationIssue]


@dataclass(frozen=True)
class ItemOpportunity:
    item_key: str
    representative_description: str
    category: str
    normalized_unit: str
    supplier_count: int
    record_count: int
    total_spend_clp: float
    best_supplier: str
    best_unit_price_clp: float
    max_unit_price_clp: float
    price_spread_pct: float
    potential_savings_clp: float
    affected_suppliers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SupplierOpportunity:
    category: str
    supplier_count: int
    total_spend_clp: float
    leading_supplier: str
    leading_supplier_spend_clp: float
    long_tail_supplier_count: int
    long_tail_spend_clp: float
    recommendation: str


@dataclass(frozen=True)
class AnalysisSummary:
    record_count: int
    supplier_count: int
    category_count: int
    total_spend_clp: float
    estimated_savings_clp: float
    estimated_savings_pct: float
    long_tail_supplier_count: int
    long_tail_spend_clp: float


@dataclass(frozen=True)
class AnalysisResult:
    summary: AnalysisSummary
    item_opportunities: list[ItemOpportunity]
    supplier_opportunities: list[SupplierOpportunity]
    issues: list[StandardizationIssue]
