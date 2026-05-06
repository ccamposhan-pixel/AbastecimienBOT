# Multi-Agent Procurement Intelligence

Sistema multiagente para inteligencia de abastecimiento hospitalario en una red privada chilena. Opera con CSV en esta etapa, funciona primero en modo Codex/local y esta disenado para migrar la capa de datos a BigQuery sin modificar agentes.

## Arquitectura

```text
Usuario CLI
   |
   v
ChiefAgent - Jefe de Abastecimiento Virtual
   |
   +-- DatabaseAnalystAgent       consultas pandas y calidad de datos
   +-- MaterialsAnalystAgent      criticidad clinica y validacion catalogo
   +-- CoveragePlannerAgent       cobertura, reposicion, spikes, sobrestock
   +-- PriceAuditAgent            desviaciones de precio, UoM, duplicados
   +-- NegotiationAnalystAgent    oportunidades de ahorro y negociacion
   +-- PharmaRepresentativeAgent  QF, vademecum, ISP, principio activo, marca
   +-- SuppliesRepresentativeAgent enfermeria, ficha tecnica, factor empaque

DataLoader
   |
   +-- stock.csv
   +-- purchase_orders.csv
   +-- consumption.csv
   +-- homologation.csv
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Configura `.env`:

```text
LLM_PROVIDER=codex
CODEX_MODE=workspace

# Opcional: routing con LLM externo
# LLM_PROVIDER=anthropic   # Claude
# ANTHROPIC_API_KEY=...
# ANTHROPIC_MODEL=claude-sonnet-4-20250514
#
# LLM_PROVIDER=gemini      # Google Gemini
# GOOGLE_API_KEY=...
# GEMINI_MODEL=gemini-1.5-pro

DATA_SOURCE=csv
STOCK_FILE=data/mock/stock.csv
ORDERS_FILE=data/mock/purchase_orders.csv
CONSUMPTION_FILE=data/mock/consumption.csv
HOMOLOGATION_FILE=data/mock/homologation.csv
LEAD_TIME_DAYS=7
SAFETY_BUFFER_DAYS=7
SPIKE_MULTIPLIER=1.25
PRICE_DEVIATION_PCT=0.03
OVERSTOCK_RATIO=2.5
OVERSTOCK_DAYS=180
```

Ejecutar CLI:

```powershell
python -m hola_multiagent
```

Atajo:

```powershell
python equipo.py
```

Consulta unica:

```powershell
python -m hola_multiagent --query "revisar cobertura critica y alertas de reposicion"
```

Consulta unica con atajo:

```powershell
python equipo.py "revisar cobertura critica y alertas de reposicion"
```

Consulta desde sala fija:

```powershell
python equipo.py --room SALA_EQUIPO.md --consensus
```

Modo panel multi-modelo (discusión Claude vs Gemini): agrega `--llm-panel anthropic,gemini` (requiere API keys en `.env`).

```powershell
python equipo.py --consensus --llm-panel anthropic,gemini --query "revisar precio, ahorro y proveedor"
```

El modo `codex` sigue siendo deterministico/local y puede operar el equipo directamente desde el workspace.

Guia de trabajo con Codex: ver `CODEX_AGENT_TEAM.md`.

## Agente De Correo

El proyecto incluye un agente de triage de correos que:

1. Lee correos desde CSV o IMAP.
2. Resume pendientes y puntos criticos.
3. Lista tareas con prioridad y deadlines detectados.
4. Sugiere borradores de respuesta sin enviar nada automaticamente.

Prueba local con correos mock:

```powershell
python -m interface.email_cli --source csv --file data/mock/emails.csv
```

Exportar no leidos desde Outlook de escritorio sin Graph:

```powershell
powershell -ExecutionPolicy Bypass -File tools/export_unread_outlook.ps1 -OutputPath data/outlook_unread.csv
python -m interface.email_cli --source csv --file data/outlook_unread.csv
```

Para recorrer todas las carpetas del buzon local:

```powershell
powershell -ExecutionPolicy Bypass -File tools/export_unread_outlook.ps1 -AllFolders -OutputPath data/outlook_unread.csv
```

Guardar el informe:

```powershell
python -m interface.email_cli --source csv --file data/mock/emails.csv --output reports/email_triage.md
```

Guardar informe visual en HTML:

```powershell
python -m interface.email_cli --source csv --file data/mock/emails.csv --output reports/email_triage.html
```

Conexion recomendada para Outlook.com / Microsoft 365 usando Microsoft Graph:

```powershell
python -m interface.email_cli --source graph --folder inbox --limit 50 --unread-only
```

La primera vez mostrara un codigo de Microsoft. Abre la URL indicada, inicia sesion
con tu cuenta Outlook y acepta el permiso `Mail.Read`. El token queda cacheado en
`.msal_token_cache.json` para no pedir login en cada corrida.

Variables para Microsoft Graph:

```text
MSGRAPH_CLIENT_ID=
MSGRAPH_TENANT_ID=consumers
MSGRAPH_FOLDER=inbox
MSGRAPH_SCOPES=Mail.Read User.Read
MSGRAPH_TOKEN_CACHE=.msal_token_cache.json
```

Para una cuenta personal `@outlook.com`, `@hotmail.com` o `@live.com`, usa
`MSGRAPH_TENANT_ID=consumers`. Para correo corporativo Microsoft 365, usa el
tenant id de tu organizacion, o `common` / `organizations` si tu administrador lo permite.

Conexion IMAP a otro buzon real o a tenants que aun lo permitan:

```powershell
python -m interface.email_cli --source imap --folder INBOX --limit 50 --unread-only
```

Variables opcionales para IMAP:

```text
EMAIL_IMAP_SERVER=imap.gmail.com
EMAIL_IMAP_PORT=993
EMAIL_IMAP_SSL=true
EMAIL_USERNAME=usuario@example.com
EMAIL_PASSWORD=
EMAIL_FOLDER=INBOX
```

Outlook requiere autenticacion moderna/OAuth2 para POP, IMAP y SMTP. Por eso,
para Outlook se recomienda `--source graph`; IMAP queda como fallback para
servidores tradicionales. Por seguridad, el agente solo lee y propone respuestas;
el envio debe agregarse como una accion separada con aprobacion humana.

En el chat puedes usar formato corto:

```text
Equipo: detectar sobrecostos de precio
```

Para evaluaciones importantes, usa mesa de consenso:

```powershell
python equipo.py --consensus --query "revisar precio, ahorro y proveedor"
```

## Consultas De Ejemplo

| Consulta | Routing esperado |
|---|---|
| revisar stock y cobertura critica | CoveragePlannerAgent |
| que SKUs tienen riesgo de agotamiento | CoveragePlannerAgent |
| detectar sobrecostos de precio | PriceAuditAgent |
| hay errores de UoM en las ordenes | PriceAuditAgent |
| oportunidades de ahorro por proveedor | NegotiationAnalystAgent |
| que contratos o descuentos deberiamos negociar | NegotiationAnalystAgent |
| validar vademecum ISP y principio activo | PharmaRepresentativeAgent |
| revisar Sugammadex no Bridion contra target | PharmaRepresentativeAgent |
| validar propuesta JFV y factor de empaque | SuppliesRepresentativeAgent |
| homologar insumos con ficha tecnica | SuppliesRepresentativeAgent |
| mostrar resumen de datos cargados | DatabaseAnalystAgent |
| lista ordenes abiertas pendientes | DatabaseAnalystAgent |
| clasificar criticidad de materiales | MaterialsAnalystAgent |
| revisar precio, ahorro y proveedor por SKU | PriceAuditAgent + NegotiationAnalystAgent + DatabaseAnalystAgent |

## Umbrales Configurables

| Variable | Default | Racional clinico/operacional |
|---|---:|---|
| `LEAD_TIME_DAYS` | 7 | Tiempo minimo estimado para reposicion; se usa fijo hasta tener lead time real por proveedor. |
| `SAFETY_BUFFER_DAYS` | 7 | Buffer para evitar quiebres ante consumo clinico variable o atrasos logisticos. |
| `SPIKE_MULTIPLIER` | 1.25 | Detecta alzas de consumo 30d sobre tendencia 90d, util para brotes, estacionalidad o errores de registro. |
| `PRICE_DEVIATION_PCT` | 0.03 | Tolerancia de +/-3% contra precio homologado antes de revisar pago o OC. |
| `OVERSTOCK_RATIO` | 2.5 | Marca compras 90d por sobre 2,5 veces el consumo 90d; indica riesgo de capital inmovilizado. |
| `OVERSTOCK_DAYS` | 180 | Cobertura mayor a 180 dias se considera sobrestock para insumos hospitalarios no estrategicos. |

## Migracion CSV A BigQuery

La regla de diseno es: los agentes reciben `dataframes: dict[str, pd.DataFrame]`. Por lo tanto, para migrar a BigQuery:

1. Crear un nuevo loader, por ejemplo `data/bigquery_loader.py`.
2. Mantener las mismas claves: `stock`, `purchase_orders`, `consumption`, `homologation`.
3. Normalizar columnas con las mismas reglas que `DataLoader`.
4. Retornar DataFrames pandas con los mismos nombres de columnas canonicos.
5. Cambiar `DATA_SOURCE=bigquery` y resolver en la capa de interfaz.

Mientras el contrato de salida sea el mismo, no se modifican agentes.

## Limitaciones

- La etapa actual no usa base de datos ni SQL.
- Las consultas naturales del `DatabaseAnalystAgent` son deterministicas y cubren patrones frecuentes.
- La criticidad clinica usa diccionario local extendible; los casos no clasificados quedan como `PENDIENTE`.
- No existe aun lead time real por proveedor/SKU.
- Los impactos financieros usan OC y precio unitario; no hay conciliacion real contra factura.

## Roadmap

1. Integrar BigQuery como capa de datos intercambiable.
2. Agregar FastAPI para exponer endpoints de consulta y dashboard.
3. Incorporar Streamlit o frontend ejecutivo.
4. Incorporar lead time historico por proveedor.
5. Agregar conciliacion factura-OC-recepcion.
6. Crear controles de aprobacion para OC con riesgo de sobrestock o precio desviado.
7. Agregar memoria persistente de decisiones, supuestos y acciones cerradas.
