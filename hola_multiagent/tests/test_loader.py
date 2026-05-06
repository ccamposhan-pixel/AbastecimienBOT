from __future__ import annotations

from hola_multiagent.data.loader import DataLoader


def test_loader_loads_all_files(dataframes):
    assert dataframes["stock"].shape == (55, 5)
    assert dataframes["purchase_orders"].shape[0] == 53
    assert dataframes["consumption"].shape[0] == 155
    assert dataframes["homologation"].shape[0] == 59


def test_loader_normalizes_columns_and_pending_qty(dataframes):
    assert "qty_available" in dataframes["stock"].columns
    assert "qty_pending" in dataframes["purchase_orders"].columns
    row = dataframes["purchase_orders"].loc[dataframes["purchase_orders"]["po_id"] == "PO-1002"].iloc[0]
    assert row["qty_pending"] == 300


def test_alias_map_normalizes_spanish_headers():
    loader = DataLoader()
    assert loader.normalize_column(" cod_articulo ") == "sku"
    assert loader.normalize_column("precio_unitario") == "unit_price"
    assert loader.normalize_column("centro costo") == "cost_center"
