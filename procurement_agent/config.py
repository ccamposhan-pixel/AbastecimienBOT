"""Configuration used by the procurement agent."""

COLUMN_ALIASES = {
    "supplier": [
        "supplier",
        "vendor",
        "provider",
        "proveedor",
        "nombre proveedor",
        "nombre_proveedor",
        "razon social",
        "razon_social",
        "rut proveedor",
        "rut_proveedor",
    ],
    "item_code": [
        "item_code",
        "sku",
        "codigo",
        "codigo producto",
        "codigo_producto",
        "cod producto",
        "cod_producto",
        "id_producto",
    ],
    "description": [
        "description",
        "descripcion",
        "producto",
        "item",
        "insumo",
        "material",
        "servicio",
        "glosa",
        "detalle",
    ],
    "category": [
        "category",
        "categoria",
        "familia",
        "rubro",
        "linea",
        "grupo",
    ],
    "quantity": [
        "quantity",
        "cantidad",
        "qty",
        "volumen",
        "unidades",
    ],
    "unit": [
        "unit",
        "unidad",
        "uom",
        "um",
        "medida",
        "unidad medida",
        "unidad_medida",
    ],
    "unit_price": [
        "unit_price",
        "precio_unitario",
        "precio unitario",
        "precio",
        "valor_unitario",
        "valor unitario",
        "costo_unitario",
        "costo unitario",
        "precio compra",
        "precio_compra",
    ],
    "total": [
        "total",
        "monto",
        "monto_total",
        "monto total",
        "importe",
        "valor_total",
        "valor total",
        "subtotal",
    ],
    "currency": [
        "currency",
        "moneda",
        "divisa",
    ],
    "date": [
        "date",
        "fecha",
        "fecha compra",
        "fecha_compra",
        "fecha_oc",
        "fecha oc",
    ],
}

UNIT_ALIASES = {
    "unit": ["unit", "unidad", "un", "und", "u", "ea", "each", "pieza", "pza"],
    "kg": ["kg", "kilo", "kilos", "kilogramo", "kilogramos"],
    "g": ["g", "gr", "gramo", "gramos"],
    "l": ["l", "lt", "lts", "litro", "litros"],
    "ml": ["ml", "mililitro", "mililitros", "cc"],
    "m": ["m", "metro", "metros"],
    "cm": ["cm", "centimetro", "centimetros"],
}

UNIT_CONVERSIONS = {
    "unit": ("unit", 1.0),
    "kg": ("kg", 1.0),
    "g": ("kg", 0.001),
    "l": ("l", 1.0),
    "ml": ("l", 0.001),
    "m": ("m", 1.0),
    "cm": ("m", 0.01),
}

CURRENCY_ALIASES = {
    "CLP": ["clp", "peso", "pesos", "$", "ch$", "chl"],
    "USD": ["usd", "us$", "dolar", "dolares"],
    "EUR": ["eur", "euro", "euros"],
    "UF": ["uf"],
}

DEFAULT_FX_TO_CLP = {"CLP": 1.0}

STOPWORDS = {
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "para",
    "por",
    "con",
    "sin",
    "en",
    "y",
    "x",
    "un",
    "una",
}
