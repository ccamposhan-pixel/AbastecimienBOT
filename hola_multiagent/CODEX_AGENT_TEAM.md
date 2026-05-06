# Equipo De Abastecimiento Via Codex

Este proyecto queda configurado para operar primero con Codex, no con Claude.

## Como Trabaja En Modo Codex

Codex actua como coordinador humano-en-el-loop dentro del workspace:

1. Recibe la consulta en el chat.
2. Decide que agente corresponde usar.
3. Ejecuta el modulo Python local cuando conviene obtener calculos.
4. Interpreta la salida en registro ejecutivo chileno.
5. Puede modificar reglas, datos mock, tests o documentacion si el usuario lo pide.

El CLI usa el mismo equipo de agentes, pero con routing deterministico local. No llama a Claude ni requiere API externa.

## Atajo De Conversacion

En el chat de Codex, no necesitas escribir el prompt largo. Usa cualquiera de estas formas:

```text
Equipo: revisar cobertura critica
```

```text
Mesa: revisar precio, ahorro, cobertura y errores posibles
```

```text
Abastecimiento: detectar sobrecostos de precio
```

```text
PriceAuditAgent: revisar desviaciones de precio
```

Tambien puedes escribir la consulta directa cuando el contexto sea claro:

```text
Que SKUs debo reponer primero?
```

Regla operativa: si el mensaje menciona abastecimiento, stock, cobertura, precio, proveedor, ahorro, criticidad, materiales, OC o datos, Codex debe asumir que se debe usar este equipo. Si empieza con `Mesa:` o `Consenso:`, debe usar modo consenso.

## Sala Fija

Existe un archivo de sala para no repetir contexto:

```text
SALA_EQUIPO.md
```

Escribe tu pregunta bajo `## Consulta` y ejecuta:

```powershell
python equipo.py --room SALA_EQUIPO.md --consensus
```

Tambien puedes pedirlo en el chat:

```text
Equipo: usa SALA_EQUIPO.md
```

## Mesa De Consenso

El modo consenso hace que el Jefe no entregue solo la primera respuesta. El flujo es:

1. ChiefAgent clasifica la consulta.
2. Los agentes primarios ejecutan en paralelo cuando hay mas de un dominio.
3. Revisores independientes controlan:
   - calidad de datos,
   - consistencia financiera,
   - riesgo clinico,
   - discrepancias entre agentes.
4. ConsensusChiefAgent informa consensos, observaciones y decision final.

Comando:

```powershell
python equipo.py --consensus --query "revisar precio, ahorro y proveedor"
```

## Comando Base

```powershell
python -m interface.cli --query "revisar cobertura critica y alertas de reposicion"
```

Atajo local:

```powershell
python equipo.py "revisar cobertura critica y alertas de reposicion"
```

Por defecto, `python equipo.py "consulta"` usa modo consenso.

Modo conversacion local:

```powershell
python equipo.py
```

## Prompt Largo Opcional

```text
Codex, usa el equipo de agentes de abastecimiento de este repo.
Consulta: [pegar pregunta]

Primero decide routing, luego ejecuta el CLI o el agente especifico si necesitas datos,
y responde como memo ejecutivo para CFO/CEO en espanol chileno.
```

## Agentes Disponibles

| Agente | Uso principal |
|---|---|
| ChiefAgent | Orquestacion y routing |
| DatabaseAnalystAgent | Consultas pandas y calidad de datos |
| MaterialsAnalystAgent | Criticidad clinica y validacion de catalogo |
| CoveragePlannerAgent | Cobertura, reposicion, spikes y sobrestock |
| PriceAuditAgent | Sobrecostos, UoM, duplicados y exposicion CLP |
| NegotiationAnalystAgent | Oportunidades de ahorro y negociacion |
| PharmaRepresentativeAgent | Representante QF para farmacos, vademecum, ISP, principio activo, marca protegida y sustitucion segura |
| SuppliesRepresentativeAgent | Representante de insumos con perfil enfermeria para ficha tecnica, factor de empaque, equivalencia y riesgo de uso |

## Pilares De Valor

Desde abril 2026 el equipo separa tres tableros:

| Pilar | Como se reporta |
|---|---|
| Ahorro | Baja real de precio contra baseline, minimo, promedio ponderado o ultimo precio validado |
| Avoidance | Reajustes evitados o reducidos, como Arthrex: solicitud 5,0% cerrada en 1,5% |
| DOH | Liberacion de capital de trabajo por bajar dias de inventario; no se mezcla con ahorro P&L |

Regla QF vigente: el target de Sugammadex CLP 19.500 aplica solo a presentaciones no-Bridion, salvo validacion clinica expresa.

## Configuracion Actual

```text
LLM_PROVIDER=codex
CODEX_MODE=workspace
```

Esto significa que el sistema no intenta llamar a Anthropic. Si en una etapa futura se quiere conectar un proveedor LLM por API, debe implementarse como adaptador opcional sin cambiar la logica de negocio de los agentes.
