from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher

from .models import (
    AnalysisResult,
    AnalysisSummary,
    ItemOpportunity,
    PurchaseRecord,
    StandardizationIssue,
    SupplierOpportunity,
)
from .text import normalize_text


def analyze_records(
    records: list[PurchaseRecord],
    issues: list[StandardizationIssue] | None = None,
    similarity_threshold: float = 0.86,
    long_tail_spend_share: float = 0.02,
) -> AnalysisResult:
    issues = issues or []
    total_spend = sum(record.total_spend_clp for record in records)
    suppliers = {record.normalized_supplier for record in records}
    categories = {normalize_text(record.category) for record in records}

    item_opportunities = _find_item_opportunities(records, similarity_threshold)
    supplier_opportunities = _find_supplier_opportunities(records, long_tail_spend_share)

    supplier_spend = defaultdict(float)
    for record in records:
        supplier_spend[record.normalized_supplier] += record.total_spend_clp
    long_tail_supplier_count = sum(
        1 for spend in supplier_spend.values() if total_spend and spend / total_spend <= long_tail_spend_share
    )
    long_tail_spend = sum(
        spend for spend in supplier_spend.values() if total_spend and spend / total_spend <= long_tail_spend_share
    )

    estimated_savings = sum(opportunity.potential_savings_clp for opportunity in item_opportunities)
    estimated_savings_pct = estimated_savings / total_spend if total_spend else 0.0

    summary = AnalysisSummary(
        record_count=len(records),
        supplier_count=len(suppliers),
        category_count=len(categories),
        total_spend_clp=total_spend,
        estimated_savings_clp=estimated_savings,
        estimated_savings_pct=estimated_savings_pct,
        long_tail_supplier_count=long_tail_supplier_count,
        long_tail_spend_clp=long_tail_spend,
    )
    return AnalysisResult(summary, item_opportunities, supplier_opportunities, issues)


def _find_item_opportunities(records: list[PurchaseRecord], similarity_threshold: float) -> list[ItemOpportunity]:
    clusters = _cluster_records(records, similarity_threshold)
    opportunities: list[ItemOpportunity] = []

    for item_key, cluster in clusters.items():
        suppliers = {record.normalized_supplier: record.supplier for record in cluster}
        if len(suppliers) < 2:
            continue

        best_record = min(cluster, key=lambda record: record.unit_price_clp_base)
        max_record = max(cluster, key=lambda record: record.unit_price_clp_base)
        best_price = best_record.unit_price_clp_base
        max_price = max_record.unit_price_clp_base
        potential_savings = sum(
            max(0.0, record.unit_price_clp_base - best_price) * record.quantity_base for record in cluster
        )

        if potential_savings <= 0:
            continue

        affected_suppliers = sorted(
            {record.supplier for record in cluster if record.unit_price_clp_base > best_price}
        )
        opportunities.append(
            ItemOpportunity(
                item_key=item_key,
                representative_description=_representative_description(cluster),
                category=_representative_category(cluster),
                normalized_unit=best_record.normalized_unit,
                supplier_count=len(suppliers),
                record_count=len(cluster),
                total_spend_clp=sum(record.total_spend_clp for record in cluster),
                best_supplier=best_record.supplier,
                best_unit_price_clp=best_price,
                max_unit_price_clp=max_price,
                price_spread_pct=(max_price / best_price - 1.0) if best_price else 0.0,
                potential_savings_clp=potential_savings,
                affected_suppliers=affected_suppliers,
            )
        )

    return sorted(opportunities, key=lambda opportunity: opportunity.potential_savings_clp, reverse=True)


def _cluster_records(records: list[PurchaseRecord], similarity_threshold: float) -> dict[str, list[PurchaseRecord]]:
    clusters: dict[str, list[PurchaseRecord]] = {}
    representatives: dict[str, PurchaseRecord] = {}

    for record in records:
        if record.item_code:
            key = f"code:{normalize_text(record.item_code)}:{record.normalized_unit}"
            clusters.setdefault(key, []).append(record)
            representatives.setdefault(key, record)
            continue

        matched_key = None
        for key, representative in representatives.items():
            if representative.normalized_unit != record.normalized_unit:
                continue
            if normalize_text(representative.category) != normalize_text(record.category):
                continue
            score = SequenceMatcher(None, representative.normalized_description, record.normalized_description).ratio()
            if score >= similarity_threshold:
                matched_key = key
                break

        if matched_key is None:
            matched_key = f"desc:{len(clusters) + 1}:{record.normalized_unit}"
            representatives[matched_key] = record
            clusters[matched_key] = []

        clusters[matched_key].append(record)

    return clusters


def _representative_description(records: list[PurchaseRecord]) -> str:
    return max(records, key=lambda record: record.total_spend_clp).description


def _representative_category(records: list[PurchaseRecord]) -> str:
    category_spend = defaultdict(float)
    category_label: dict[str, str] = {}
    for record in records:
        key = normalize_text(record.category)
        category_spend[key] += record.total_spend_clp
        category_label[key] = record.category
    winning_key = max(category_spend, key=category_spend.get)
    return category_label[winning_key]


def _find_supplier_opportunities(
    records: list[PurchaseRecord],
    long_tail_spend_share: float,
) -> list[SupplierOpportunity]:
    by_category: dict[str, list[PurchaseRecord]] = defaultdict(list)
    for record in records:
        by_category[normalize_text(record.category)].append(record)

    opportunities: list[SupplierOpportunity] = []
    for _, category_records in by_category.items():
        category_total = sum(record.total_spend_clp for record in category_records)
        if category_total <= 0:
            continue

        spend_by_supplier: dict[str, float] = defaultdict(float)
        supplier_labels: dict[str, str] = {}
        for record in category_records:
            spend_by_supplier[record.normalized_supplier] += record.total_spend_clp
            supplier_labels[record.normalized_supplier] = record.supplier

        if len(spend_by_supplier) < 3:
            continue

        leading_supplier_key = max(spend_by_supplier, key=spend_by_supplier.get)
        long_tail = {
            supplier: spend
            for supplier, spend in spend_by_supplier.items()
            if spend / category_total <= long_tail_spend_share
        }
        if not long_tail:
            sorted_spend = sorted(spend_by_supplier.items(), key=lambda item: item[1])
            candidate_count = max(1, len(sorted_spend) // 3)
            long_tail = dict(sorted_spend[:candidate_count])

        long_tail_spend = sum(long_tail.values())
        if long_tail_spend <= 0:
            continue

        category = _representative_category(category_records)
        leading_supplier = supplier_labels[leading_supplier_key]
        recommendation = (
            f"Reducir atomizacion en {category}: evaluar traspasar compras menores hacia "
            f"{leading_supplier} o licitar un contrato marco para la familia."
        )
        opportunities.append(
            SupplierOpportunity(
                category=category,
                supplier_count=len(spend_by_supplier),
                total_spend_clp=category_total,
                leading_supplier=leading_supplier,
                leading_supplier_spend_clp=spend_by_supplier[leading_supplier_key],
                long_tail_supplier_count=len(long_tail),
                long_tail_spend_clp=long_tail_spend,
                recommendation=recommendation,
            )
        )

    return sorted(opportunities, key=lambda opportunity: opportunity.long_tail_spend_clp, reverse=True)
