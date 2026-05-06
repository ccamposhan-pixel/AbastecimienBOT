# Protocolo de homologacion de materiales NetSuite

## 1. Objetivo

Cerrar al 30.04.2026 una matriz unica de homologacion de materiales para las clinicas Andes Salud, usando como base los codigos de Puerto Montt contenidos en el archivo `202605 Materiales NetSuite.xls`.

La homologacion debe permitir identificar, para cada clinica, si el material local corresponde exactamente a un codigo existente de Puerto Montt, si requiere validacion central, si debe crearse como nuevo codigo o si no aplica/no se utiliza.

## 2. Alcance

Base de referencia:

- Archivo: `202605 Materiales NetSuite.xls`
- Hoja: `Artculos`
- Registros de articulos: 13.232
- Columnas base: `Codigo UPC`, `Nombre`, `Nombre para mostrar`, `Subtipo`, `Descripcion`, `Precio base`, `Programa fiscal`, `Codigo de impuestos de retencion predeterminado`, `Concepto de facturacion`, `Comentario`

Clinicas consideradas:

- Puerto Montt: base maestra de codigos.
- Chillan: homologacion directa contra base Puerto Montt.
- Talca: utilizara como punto de partida los codigos/criterios de Chillan y debera informar solo diferencias, faltantes o dudas.
- Concepcion: homologacion directa contra base Puerto Montt.
- Calama: homologacion directa contra base Puerto Montt.
- Punta Arenas: homologacion directa contra base Puerto Montt.

Nota de control: aunque se mencionan 5 clinicas, el universo operativo informado incluye 6 sedes. Para este proceso se consideran 5 clinicas por homologar, ya que Puerto Montt actua como base.

## 3. Autoridad y gobierno del proceso

La autoridad central del proceso sera Mathias.

Funciones de Mathias:

- Definir criterio unico de homologacion.
- Resolver discrepancias entre clinicas.
- Aprobar o rechazar homologaciones dudosas.
- Autorizar solicitudes de creacion de codigo nuevo.
- Congelar la matriz final al cierre del proceso.

Ninguna clinica debe crear, modificar o eliminar codigos maestros sin aprobacion de Mathias.

## 4. Participantes y responsabilidades

### Mesa central

Responsabilidades:

- Preparar y distribuir la matriz de homologacion.
- Consolidar respuestas de las clinicas.
- Validar completitud y consistencia.
- Levantar dudas a Mathias en bloque, priorizadas por criticidad.
- Emitir la version final congelada.

### QF de Farmacia de cada clinica

Responsabilidades:

- Validar equivalencias tecnicas de medicamentos e insumos.
- Revisar concentracion, forma farmaceutica, presentacion, unidad, via de administracion, dimensiones, esterilidad y uso clinico cuando aplique.
- Marcar diferencias que impidan una homologacion 1:1.
- Informar productos locales que no existan en la base Puerto Montt.

### Farmacia venta publico de cada clinica

Responsabilidades:

- Validar productos de venta publico, productos con sufijo o uso FP, convenios, descuentos y conceptos asociados a farmacia.
- Identificar articulos que no correspondan a materiales homologables, por ejemplo descuentos, reembolsos, servicios o conceptos administrativos.
- Confirmar codigos locales vigentes y productos no utilizados.

### Responsable local de cada clinica

Responsabilidades:

- Coordinar a QF Farmacia y Farmacia venta publico.
- Entregar la matriz completa dentro del plazo.
- Asegurar que las dudas esten documentadas con observacion suficiente.

## 5. Principios de homologacion

1. La base Puerto Montt es la referencia inicial, no necesariamente la verdad final.
2. Se homologa producto contra producto, no solo por nombre parecido.
3. Una homologacion 1:1 exige coincidencia tecnica y operacional.
4. Si falta informacion, se marca como duda; no se fuerza la homologacion.
5. Las decisiones excepcionales se documentan y quedan aprobadas por Mathias.
6. Los codigos duplicados, vacios o administrativos se escalan a la mesa central.
7. La clinica informa su realidad local; Mathias define el estandar final.

## 6. Estados permitidos

Cada linea revisada por una clinica debe quedar en uno de estos estados:

- `Homologado 1:1`: corresponde exactamente al codigo Puerto Montt.
- `Homologado con observacion`: corresponde, pero requiere aclaracion menor.
- `No usado en clinica`: el material no se utiliza localmente.
- `No existe en base PM`: existe localmente, pero no se encuentra equivalente en Puerto Montt.
- `Requiere codigo nuevo`: no hay equivalente seguro y debe evaluarse creacion.
- `Duda tecnica`: requiere definicion de QF/Mathias.
- `No homologable / administrativo`: descuento, servicio, reembolso, convenio u otro concepto que no corresponde a material.

## 7. Criterios minimos para homologacion 1:1

### Medicamentos

Debe coincidir:

- Principio activo.
- Concentracion.
- Forma farmaceutica.
- Presentacion y cantidad por envase.
- Via de administracion cuando aplique.
- Condicion especial, por ejemplo controlado, refrigerado, esteril, unidosis o multidosis.
- Marca, solo cuando la marca sea clinicamente relevante o el articulo sea comercialmente especifico.

No se debe homologar 1:1 si cambia dosis, volumen, cantidad de comprimidos, forma farmaceutica, via, concentracion o condicion de almacenamiento critica.

### Insumos clinicos

Debe coincidir:

- Tipo de insumo.
- Medida, calibre, French, largo, talla o dimension.
- Materialidad cuando sea relevante.
- Esteril/no esteril.
- Uso adulto/pediatrico/neonatal.
- Lado derecho/izquierdo cuando aplique.
- Compatibilidad o referencia tecnica cuando aplique.

No se debe homologar 1:1 si solo coincide la familia del producto pero cambia dimension, esterilidad, talla, uso o referencia critica.

### Productos de farmacia venta publico

Debe coincidir:

- Producto comercial o generico.
- Presentacion.
- Contenido/cantidad.
- Condicion de venta.
- Codigo local vigente.

Los descuentos, reembolsos, convenios y conceptos administrativos deben marcarse como `No homologable / administrativo`, salvo instruccion distinta de Mathias.

## 8. Procedimiento operativo

### Paso 1: Preparacion de matriz

La mesa central prepara una matriz por clinica con las columnas base de Puerto Montt y las columnas de respuesta local:

- Clinica.
- Codigo PM.
- Nombre PM.
- Subtipo PM.
- Programa fiscal PM.
- Codigo local clinica.
- Nombre local clinica.
- Presentacion / unidad local.
- Existe en clinica.
- Estado de homologacion.
- Codigo homologado/propuesto.
- Observacion clinica.
- Responsable revision.
- Fecha revision.
- Estado Mathias.
- Observacion Mathias.

### Paso 2: Distribucion y kickoff

La mesa central envia la matriz el 27.04.2026 a responsables locales, QF Farmacia y Farmacia venta publico.

Instrucciones de envio:

- No modificar columnas de Puerto Montt.
- Completar solo columnas de respuesta local.
- Usar un unico responsable de devolucion por clinica.
- Documentar dudas en la columna `Observacion clinica`.
- No dejar estados en blanco.

### Paso 3: Revision en paralelo por clinica

Cada clinica revisa su matriz en paralelo.

Priorizacion recomendada:

1. Medicamentos e insumos de uso frecuente.
2. Productos de farmacia venta publico.
3. Materiales criticos o de alto impacto operacional.
4. Conceptos administrativos, descuentos, reembolsos y no homologables.
5. Dudas o productos faltantes.

Talca debe iniciar desde la validacion de Chillan y reportar diferencias, faltantes o excepciones propias.

### Paso 4: Consolidacion central

La mesa central consolida las respuestas y clasifica:

- Coincidencias directas.
- Diferencias entre clinicas.
- Productos sin codigo local.
- Productos sin equivalente Puerto Montt.
- Codigos PM vacios o duplicados.
- Conceptos administrativos o no homologables.

Hallazgos de control detectados en la base inicial:

- 130 lineas sin `Codigo UPC`.
- 110 valores de `Codigo UPC` aparecen repetidos.
- La mayoria de columnas complementarias de NetSuite vienen vacias, por lo que la decision debe apoyarse en nombre, presentacion, subtipo, uso local y validacion QF.

Estos casos deben quedar observados y ser revisados por Mathias antes del cierre.

### Paso 5: Resolucion de dudas

La mesa central envia a Mathias un listado priorizado con:

- Codigo PM.
- Nombre PM.
- Clinica.
- Codigo local.
- Estado propuesto.
- Motivo de duda.
- Recomendacion de la clinica.

Mathias resuelve con uno de estos resultados:

- Aprobado.
- Observado, requiere ajuste.
- Rechazado.
- Crear codigo nuevo.
- Excluir/no homologable.

### Paso 6: Cierre y congelamiento

La mesa central emite la matriz final congelada el 30.04.2026.

La version final debe incluir:

- Fecha y hora de cierre.
- Responsable de aprobacion central.
- Estado final por clinica.
- Dudas pendientes, si existieran, con responsable y fecha comprometida.
- Bitacora de cambios relevantes.

## 9. Cronograma recomendado

| Fecha | Hora limite | Actividad | Responsable |
| --- | ---: | --- | --- |
| 27.04.2026 | 18:00 | Envio de matriz e instrucciones | Mesa central |
| 28.04.2026 | 12:00 | Primera revision de medicamentos e insumos criticos | Clinicas / QF |
| 28.04.2026 | 17:00 | Primera consolidacion de dudas | Mesa central |
| 29.04.2026 | 12:00 | Devolucion completa por clinica | Responsables locales |
| 29.04.2026 | 18:00 | Resolucion de discrepancias priorizadas | Mathias |
| 30.04.2026 | 12:00 | Matriz final revisada | Mesa central |
| 30.04.2026 | 18:00 | Cierre y congelamiento | Mathias / Mesa central |

## 10. Reglas de comunicacion

- Un canal central unico para dudas y cambios.
- Cada clinica debe consolidar internamente antes de enviar.
- Las dudas se levantan con evidencia: codigo, nombre, presentacion y razon de la duda.
- No se aceptan cambios por chat sin registro en matriz o bitacora.
- Mathias debe recibir bloques de decision, no consultas atomizadas sin contexto.

## 11. Controles de calidad antes del cierre

La mesa central debe validar:

- Todas las clinicas tienen matriz devuelta.
- No hay estados en blanco.
- Todo `Requiere codigo nuevo` tiene justificacion.
- Todo `Duda tecnica` tiene resolucion o responsable asignado.
- Las lineas sin `Codigo UPC` fueron revisadas.
- Los codigos duplicados fueron revisados.
- Los conceptos administrativos fueron identificados.
- Talca fue contrastada contra Chillan y se registraron excepciones.
- La aprobacion final de Mathias quedo registrada.

## 12. Entregables

1. Matriz de homologacion por clinica.
2. Listado de dudas y decisiones de Mathias.
3. Listado de codigos nuevos requeridos.
4. Listado de articulos no utilizados o no homologables.
5. Matriz final congelada al 30.04.2026.

