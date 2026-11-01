# Baseline de compilación con Gram editable

Se registra la línea base previa a la migración explícita de la sesión de
Bagron hacia el modelo de `Session` de Gram `3.0.0`. La dependencia continúa
siendo editable desde `~/Desktop/Gram`; no se fija un tag ni un commit.

## Protocolo

- Comando: `vnma run main.py examples/canon/_main.bg`
- Plataforma: Windows
- Python: `3.14.7`
- Gram: `3.0.0-4-g2be2e9d-dirty`
- Muestras: cinco compilaciones completas, con salida descartada
- Alcance: arranque de `vnma`, lexer/parser de Gram, frontend semántico,
  generación LLVM, enlace y creación del ejecutable

## Resultado observado

| Muestra | Tiempo (s) | Salida |
| ---: | ---: | --- |
| 1 | 10.010 | correcta |
| 2 | 9.270 | correcta |
| 3 | 8.908 | correcta |
| 4 | 14.342 | correcta |
| 5 | 10.955 | correcta |

- Mínimo: `8.908 s`
- Mediana: `10.010 s`
- Promedio: `10.697 s`
- Máximo: `14.342 s`

Se conserva como referencia el recuerdo previo de una compilación de
aproximadamente `5–7 s`, pero no se reprodujo en estas muestras. La medición
incluye todo el proceso de compilación y no aísla el coste de Gram; por eso
servirá para detectar regresiones globales, no para atribuir una mejora
exclusivamente al parser.

## Verificación posterior a la migración de sesión

Después de mover el registro de keywords, grupos y configuración a
`BAGRON_SESSION`, se repitió exactamente el mismo comando:

| Muestra | Tiempo (s) | Salida |
| ---: | ---: | --- |
| 1 | 6.011 | correcta |
| 2 | 6.749 | correcta |
| 3 | 5.612 | correcta |
| 4 | 7.567 | correcta |
| 5 | 7.013 | correcta |

- Mínimo: `5.612 s`
- Mediana: `6.749 s`
- Promedio: `6.590 s`
- Máximo: `7.567 s`

El resultado vuelve a caer dentro del rango histórico de `5–7 s`. No se
atribuye una mejora causal a la migración porque las muestras pre y post no
son suficientemente controladas para separar el efecto de la sesión de la
variación de arranque, cachés y carga del entorno.

La migración conserva el backend Python de Gram y no activa AOT. El registro
léxico usa `Session.add_group()`, `Session.add_keyword()` y `Session.config`;
la desactivación de `**` conserva la API de símbolos de Gram porque `Session`
todavía no expone una operación pública equivalente.

## Benchmark reproducible de compilación total

Se añadió [`benchmarks/compile_baseline.py`](../benchmarks/compile_baseline.py)
para repetir el baseline sin medir solo una fase. El script incluye el
arranque de `vnma`, lexer/parser de Gram, análisis semántico, generación LLVM,
enlace y creación del ejecutable. No activa Gram AOT.

Comando registrado:

```text
python benchmarks/compile_baseline.py
```

Configuración por defecto: una compilación de calentamiento y cinco muestras
reportadas sobre `examples/canon/_main.bg`. El script también permite
`--warmup 0` para comparar arranques fríos y `--samples N` para ampliar la
muestra.

### Baseline reproducible actual

- Gram editable: `3.0.0-5-g968dcf7`
- Muestras: `9.879`, `6.992`, `7.674`, `7.739`, `7.812` segundos
- Mínimo: `6.992 s`
- Mediana: `7.739 s`
- Promedio: `8.019 s`
- Máximo: `9.879 s`

Para comparar una mejora, se debe conservar el mismo target, número de
muestras, calentamiento, plataforma y revisión de Gram. La métrica principal
será la mediana; mínimo y máximo sirven para observar variación del entorno.

## Eliminación de la activación global legacy

`core/compiler/control.py` dejó de llamar a `BAGRON_SESSION.load()` antes de
cada compilación. Gram `3.0.0` ya resuelve la configuración, el léxico y el
parser desde la propia sesión en `Session.tokenize()` y `Session.parse()`;
mantener esa activación solo añadía una sincronización global innecesaria.

No quedan usos de `BAGRON_SESSION.load()` en el código de Bagron.

Con el mismo comando y protocolo del benchmark reproducible, sobre Gram
`3.0.0-5-g968dcf7`, se obtuvo:

- Muestras: `5.969`, `6.153`, `6.017`, `6.303`, `5.816` segundos
- Mínimo: `5.816 s`
- Mediana: `6.017 s`
- Promedio: `6.052 s`
- Máximo: `6.303 s`

La mediana observada bajó desde `7.739 s` a `6.017 s`. Es una mejora
compatible con la eliminación de la sincronización global, aunque se debe
confirmar con más ejecuciones si se necesita atribución estadística estricta.

## Estandarización de combinadores para AOT

- `_SAME_LINE` fue sustituido por `cmb.SameLine`, que conserva la restricción
  de continuidad de línea y forma parte del conjunto compilable de Gram.
- `_OPTIONAL_ARRAY_DIMENSION` fue eliminado. `Enclosed(...,
  allow_empty=True)` resuelve correctamente `[]` y `[expresión]`, pero omite
  los delimitadores y cambia la forma del AST que Bagron usa para calcular
  `array_lengths`; `Separator` tampoco aplica porque modela listas y devuelve
  `ArrayNode`.
- `ARRAY_SUFFIX` usa ahora un `Alt` de dos `Seq` estándar: `[]` o
  `[Ref(VALUE)]`. La alternativa conserva los tokens `LBRACKET`/`RBRACKET`,
  mantiene el AST existente y queda dentro del contrato cerrado de AOT.

El sondeo manual de `BAGRON_SESSION.export_c_parser()` recorrió las 75 reglas
de Bagron y generó `gram_ast.*` y `gram_parser.*` sin rechazar combinadores.
Esto demuestra que la gramática ya es exportable a C, pero todavía no implica
paridad semántica ni activa AOT en el compilador.

Después del cambio, con Gram editable `3.0.0-5-g968dcf7` y el benchmark total
reproducible:

- Muestras: `6.455`, `5.495`, `5.725`, `5.457`, `5.669` segundos
- Mínimo: `5.457 s`
- Mediana: `5.669 s`
- Promedio: `5.760 s`
- Máximo: `6.455 s`

## Paso 1: sondeo del parser AOT nativo

Se exportó el parser completo de Bagron con `emit_driver=True` y
`emit_cli=True` en `build/aot_probe/`. El exportador produjo `gram_ast.*`,
`gram_parser.*`, `gram_ir.*`, `gram_driver.*` y `gram_cli.c`, con grammar ID
`0x3e06d0857d33b820`.

Los C generados y el runtime nativo de Gram se compilaron con Clang en
Windows. La compilación terminó correctamente; solo emitió advertencias de
uso de `fopen` considerado obsoleto por el CRT de Windows. La ejecución se
hizo con la orden `check`, que valida únicamente lexer y parser nativos.

El corpus directo de `examples/**/*.bg` dio `8/12` archivos correctos. Los
cuatro restantes contenían bloques `#prep ... #end`; esos bloques se extraen
antes de tokenizar en el flujo Python de Bagron, pero la CLI nativa aislada no
incluye todavía ese preprocesador. Al repetir el mismo corpus después de esa
extracción previa, el resultado fue `12/12` correctos.

Este paso confirma que la gramática exportada y el parser C compilan y
reconocen las entradas parser-ready del corpus. No activa AOT en producción ni
demuestra todavía paridad del AST, integración semántica o soporte nativo de
`#prep`; esas comprobaciones pertenecen a los pasos posteriores.

El sondeo necesitó cargar explícitamente el exportador de Gram porque el
paquete `Bagron/tools` puede ocultar `Gram/tools` cuando ambos están en el
`PYTHONPATH`. Es una consideración de tooling para automatizar el export, no
un cambio aplicado al runtime de producción.

## Paso 2: puente GIR a AST de Bagron

Se añadió `core/frontend/aot.py` con `ast_from_gir()`, un adaptador que recibe
un `GirView` y reconstruye el AST que produce la sesión Python de Bagron. El
adaptador reutiliza los tokens de la misma fuente para conservar tokens,
literales y posiciones, y convierte también las expresiones Pratt a
`ASTUnaryOp`/`ASTBinaryOp`.

El GIR de Gram representa de forma uniforme las listas como `ARRAY` y expande
las reglas `nodeable=False`. Por eso el adaptador restaura explícitamente las
listas transparentes de `TYPE`, los `ArrayNode` semánticos y las repeticiones
de la raíz que Bagron necesita para sus pasadas posteriores. Esta decisión es
deliberadamente específica de Bagron: la paridad genérica del GIR de Gram no
garantiza por sí sola la forma exacta que consume el procesador de Bagron.

Para que la raíz no introduzca un nodo artificial, `ENTRYPOINT` quedó marcado
como `nodeable = False`, igual que la lista que devuelve el parser Python.

La validación compiló el parser C y su runtime con Clang, generó GIR para los
12 archivos parser-ready del corpus de ejemplos y comprobó la reconstrucción
contra el AST Python:

- parser nativo/GIR compilado: `12/12`;
- paridad estructural Python↔GIR→AST: `12/12`.

El puente todavía no está conectado a `CompilerState.process_source()` ni al
backend. El siguiente paso de AOT será integrarlo detrás de una ruta opt-in,
comparar diagnósticos y resultados semánticos, y conservar el parser Python
como fallback antes de considerar activarlo por defecto. Los bloques `#prep`
siguen requiriendo la extracción previa del preprocesador de Bagron.

## Fase 3: integración AOT opt-in y benchmark inicial

`CompilerState.process_source()` ya puede seleccionar el parser C mediante la
opción opt-in `--aot` de `main.py`. El ejecutable exportado por Gram se indica
con `--aot-parser <ruta>` o mediante `BAGRON_AOT_PARSER`. El flujo escribe la
fuente parser-ready en un temporal, solicita GIR al driver nativo, reconstruye
el AST con `ast_from_gir()` y continúa por las mismas pasadas semánticas y el
mismo backend LLVM que la ruta Python.

La ruta no cambia el comportamiento predeterminado. Si el parser no está
configurado o falla, `--aot` registra una advertencia y vuelve a Python;
`--aot-strict` convierte esa condición en un error para las comparaciones
diferenciales y los benchmarks. Los binarios generados no se guardan en el
repositorio.

Comprobación de integración:

```text
vnma run main.py --aot --aot-strict --aot-parser build/aot_probe/bagron_aot.exe examples/canon/_main.bg
```

La compilación completa de `examples/canon/_main.bg`, incluyendo imports,
análisis semántico, LLVM, enlace y ejecutable, terminó correctamente por la
ruta nativa.

Benchmark inicial con Gram `3.0.0-5-g968dcf7`, un calentamiento y tres muestras
por ruta:

| Ruta | Muestras (s) | Mediana | Promedio |
| --- | --- | ---: | ---: |
| Python | `5.905`, `5.967`, `6.871` | `5.967 s` | `6.247 s` |
| AOT | `3.409`, `3.163`, `3.552` | `3.409 s` | `3.375 s` |

La mediana observada fue aproximadamente un `43%` menor con AOT en esta
ejecución. Es una señal inicial; hace falta ampliar muestras y repetir en
condiciones controladas antes de activar AOT por defecto.

La comparación adicional de LLVM IR produjo diferencias únicamente en los
índices numéricos que llvmlite asigna a tipos anónimos en cada ejecución. Tras
normalizar esos sufijos, el IR generado por Python y AOT fue idéntico para
`examples/canon/_main.bg`. Por tanto, la paridad de backend del corpus probado
queda cubierta; la equivalencia de diagnósticos sintácticos y el muestreo
estadístico ampliado siguen siendo trabajo de la fase siguiente.

## Fase 4: benchmark y diagnósticos ampliados

Se repitió el benchmark con un calentamiento y cinco muestras por ruta, usando
el mismo target y Gram `3.0.0-5-g968dcf7`:

| Ruta | Muestras (s) | Mínimo | Mediana | Promedio | Máximo |
| --- | --- | ---: | ---: | ---: | ---: |
| Python | `7.757`, `7.863`, `7.031`, `7.231`, `9.532` | `7.031` | `7.757` | `7.883` | `9.532` |
| AOT | `4.300`, `4.063`, `3.725`, `4.309`, `3.950` | `3.725` | `4.063` | `4.069` | `4.309` |

La mediana AOT fue `3.694 s` menor, una reducción observada de `47.6%` frente
a Python. La diferencia de dispersión también bajó en esta tanda, aunque el
benchmark sigue siendo local y no sustituye una medición repetida en CI.

La matriz diferencial de sintaxis quedó ampliada a:

- `12/12` fuentes válidas aceptadas por Python y AOT;
- `5/5` fuentes inválidas rechazadas por Python y AOT.

La comparación es de aceptación/rechazo; los textos y códigos exactos de los
diagnósticos todavía no están unificados porque el driver C de Gram y el
diagnóstico Python exponen formatos distintos. Esa es la siguiente tarea de
endurecimiento antes de activar AOT como ruta predeterminada.

## Fase 5: construcción reproducible del frontend AOT

Se añadió `tools/build_aot_parser.py` para exportar la sesión de Bagron,
compilar las unidades C de Gram con Clang y producir `build/aot/bagron_aot.exe`
(o su equivalente nativo). El artefacto contiene lexer, parser, arena AST y
serialización GIR; no contiene ni reemplaza el procesador semántico ni el
backend LLVM de Bagron.

`AotParser.from_config()` descubre ese artefacto local después de la
construcción. También se mantienen `--aot-parser` y `BAGRON_AOT_PARSER` para
CI o rutas personalizadas. Si el artefacto no existe, `--aot` conserva el
fallback Python y `--aot-strict` falla explícitamente.

Comando reproducible:

```text
python tools/build_aot_parser.py
vnma run main.py --aot --aot-strict examples/canon/_main.bg
```
