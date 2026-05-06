# AbastecimienBOT
Agente local para analizar bases de precios y compras. Estandariza proveedores,
productos, unidades, monedas y precios para detectar:

- productos comparables comprados a distintos precios;
- oportunidades de ahorro usando el mejor precio observado;
- categorias con muchos proveedores pequenos;
- recomendaciones de consolidacion y desatomizacion.

## Uso rapido

```bash
python3 -m procurement_agent analyze data/sample_purchases.csv --out reports
```

Luego puedes pedir al jefe IA que controle los resultados del analista y convoque
una mesa interna:

```bash
python3 -m procurement_agent chief --reports reports --question "Validar propuesta antes de comite"
```

O en un solo paso:

```bash
python3 -m procurement_agent run data/sample_purchases.csv --out reports --question "Validar propuesta antes de comite"
```

Con monedas distintas a CLP:

```bash
python3 -m procurement_agent analyze data/compras --out reports --fx USD=950,EUR=1050
```

Modo autónomo (watch): re-ejecuta el análisis cuando aparezcan o cambien CSV en una carpeta, guardando cada corrida en una subcarpeta con timestamp.

```bash
python3 -m procurement_agent watch data/compras --out reports --fx USD=950 --interval-seconds 30 --chief
```

## Entrada esperada

El agente acepta un CSV unico o una carpeta con varios CSV. Reconoce columnas con
nombres comunes en espanol o ingles:

- proveedor: `proveedor`, `supplier`, `vendor`, `razon_social`
- producto: `descripcion`, `producto`, `glosa`, `detalle`
- codigo: `codigo_producto`, `sku`, `item_code`
- categoria: `categoria`, `familia`, `rubro`
- cantidad: `cantidad`, `qty`, `volumen`
- unidad: `unidad`, `uom`, `um`
- precio: `precio_unitario`, `precio`, `costo_unitario`
- total: `monto`, `total`, `subtotal`
- moneda: `moneda`, `currency`
- fecha: `fecha`, `date`

Si no hay precio unitario pero existe monto total y cantidad, lo calcula.

## Salidas

El comando genera tres archivos en la carpeta de salida:

- `standardized_prices.csv`: datos normalizados a CLP y unidad base.
- `opportunities.json`: resultado estructurado para integrar con otros sistemas.
- `report.md`: resumen ejecutivo con oportunidades priorizadas.

El comando `chief` genera:

- `chief_memo.md`: memo del Jefe de Compras IA.
- `chief_board_minutes.json`: minuta estructurada de la mesa de agentes.

## Logica actual

1. Normaliza nombres de columnas, textos, monedas y unidades.
2. Convierte precios a CLP con los tipos de cambio entregados por `--fx`.
3. Agrupa productos por codigo; si no hay codigo, usa similitud de descripcion
   dentro de la misma categoria y unidad base.
4. Calcula dispersion de precios y ahorro potencial por llevar volumen al mejor
   precio observado.
5. Identifica categorias con fragmentacion de proveedores y cola larga.

## Jefe de Compras IA

El jefe es el unico punto de contacto del usuario. Su trabajo no es recalcular
la base, sino controlar al analista y coordinar agentes internos:

- `Analista`: resume hallazgos y cuantifica impacto.
- `Controlador`: valida archivos, cobertura, consistencia y supuestos.
- `Negociador`: convierte oportunidades en conversaciones comerciales.
- `Desatomizador`: propone contratos marco y reduccion de cola larga.
- `Riesgos`: levanta cautelas por empaque, contrato, calidad y continuidad.

El veredicto del jefe puede ser:

- `Aprobado`: cifras consistentes para iniciar gestion.
- `Aprobado condicionado`: se puede negociar, pero requiere validaciones.
- `No aprobado`: faltan insumos o hay inconsistencias criticas.

## Siguientes mejoras naturales

- conectar a ERP, data lake o base SQL;
- agregar reglas por contrato, SLA, calidad o plazo de pago;
- incorporar aprobacion humana de homologaciones de producto;
- usar un LLM para explicar recomendaciones y generar planes de negociacion;
- agregar dashboard web para revisar oportunidades y marcar decisiones.
