# Cómo funciona Bagron

Este documento resume cómo funciona el compilador y cuáles son sus límites.
No es una garantía formal de seguridad ni una promesa sobre funcionalidades
que todavía no estén implementadas.

## Qué es Bagron

Bagron es un lenguaje compilado y estáticamente tipado. La implementación
actual recibe archivos `.bg`, valida su semántica y genera código nativo a
través de LLVM. No hay una máquina virtual de Bagron ni un recolector de basura
integrado.

El control de memoria es explícito en los tipos que lo necesitan: un
`buffer` se reserva y libera con las operaciones previstas por el lenguaje,
mientras que un puntero crudo no lleva longitud ni propiedad implícitas. Los
punteros crudos, `extern` y el ensamblador son fronteras en las que el programa
puede salir de las comprobaciones estáticas de Bagron.

## Flujo de compilación

Para un módulo ejecutable, el flujo es, en términos prácticos, el siguiente:

1. Se preprocesan las directivas admitidas, como las condiciones de
   compilación, `#assembler` y `#link`.
2. Gram analiza el fuente mediante la interfaz AOT/FFI y produce GIR. Bagron
   convierte ese resultado en su árbol interno. La ruta actual requiere que
   la biblioteca nativa de esa interfaz esté disponible; no usa un parser
   Python alternativo silencioso cuando falta.
3. Se cargan los imports, se comprueban las rutas y los destinos de los
   módulos, y se registran sus declaraciones públicas y privadas.
4. Se ejecutan las comprobaciones semánticas: tipos, firmas, ámbitos, flujo,
   reglas de punteros y arrays, llamadas `@unsafe`, propiedad y metadatos
   implícitos como `Len_t`, `Size_t` y `Region_t`.
5. El backend genera LLVM IR y lo verifica. Según el perfil seleccionado,
   conserva ese IR o aplica optimizaciones; el IR resultante vuelve a
   verificarse antes de generar el objeto y enlazar el artefacto final.

Un módulo ejecutable debe tener `func main() int32:`. Su retorno entero es el
código de salida, salvo que el flujo termine mediante una función `Never`.
Los módulos importados no pueden cambiar el destino ni el perfil elegidos por
el módulo de entrada.

La interfaz de línea de comandos actual no expone una opción independiente
`strict`. Las opciones antiguas con ese nombre no deben documentarse como
parte del flujo vigente.

## Comprobaciones estrictas

En la implementación actual, las comprobaciones estrictas forman parte del
camino normal del compilador; no hay un modo permisivo paralelo. Entre otras
cosas:

- los enteros tienen anchura y signo explícitos; no existe un `int` o `uint`
  genérico;
- no se aceptan conversiones implícitas de signo ni estrechamientos, y los
  literales se comprueban contra el rango del tipo destino;
- los tipos nominales, las formas de arrays y sus metadatos deben coincidir;
- las condiciones requieren `bool`, sin convertir automáticamente un entero;
- las funciones no pueden devolver directamente un puntero crudo, un array o
  un `buffer`;
- el código seguro no puede llamar a una función `@unsafe`, `extern` o de
  ensamblador;
- los errores semánticos detienen la compilación antes de que el backend
  produzca el artefacto final.

`@unsafe` es una excepción localizada por función, no un modo global de
compilación. Permite operaciones que el compilador no puede probar, como
determinados accesos mediante punteros o índices dinámicos de arrays, pero no
elimina las reglas de tipos, formas, firmas, metadatos ni el contrato de
`main`.

## Seguridad real

### Lo que sí comprueba el código seguro

- La procedencia conocida de las direcciones que se usan en operaciones
  seguras.
- Los índices literales de arrays y los índices dinámicos cuando existe una
  prueba de rango aplicable al array y al camino de control concretos.
- Los límites de un `buffer` en tiempo de ejecución; un índice literal fuera
  de su capacidad se rechaza en compilación.
- Que una función segura no llame a código marcado como inseguro.
- Reglas conservadoras de propiedad para `buffer` y handles `opaque`,
  incluyendo estados consumidos o cerrados.
- Trampas para casos que el backend detecta en ejecución, como una
  desreferencia nula, un paso inválido o ciertos límites de destino.

### Lo que no garantiza

Bagron no es un lenguaje formalmente probado ni garantiza ausencia de todos
los errores de memoria, errores lógicos, carreras, fallos del sistema o
comportamientos incorrectos en código extranjero. En particular:

- `@unsafe`, `@assembler` y `extern` atraviesan la frontera de las pruebas
  estáticas. La validez de direcciones externas, ciclos de vida, ABI y efectos del
  código extranjero queda bajo responsabilidad del programa y de su entorno.
- Un puntero crudo no contiene por sí mismo longitud, propiedad ni una prueba
  de que el objeto siga vivo.
- `@unsafe` no vuelve válido un puntero nulo o colgante; solamente permite que
  el cuerpo realice operaciones que el modo seguro no puede justificar.
- Una verificación del compilador no convierte el programa en resistente a
  entradas maliciosas, fallos de lógica o defectos del propio compilador.

Por tanto, “seguro” en Bagron significa “sujeto a las comprobaciones estáticas
y dinámicas implementadas para esa operación”, no “seguro frente a errores de
memoria en cualquier circunstancia”.

## Memoria y propiedad

El compilador mantiene estados de propiedad (`ownership`) durante el análisis;
esos estados
son metadatos semánticos y no se emiten como campos ocultos en el ABI.

- Un `buffer` posee almacenamiento y capacidad. Las variables locales y
  globales empiezan como propietarias; los parámetros se reciben como
  prestados. `Del` consume un buffer propietario y una segunda utilización o
  liberación se rechaza.
- No hay copia implícita de `buffer`. Los merges de ramas y los bucles se
  tratan conservadoramente cuando no puede probarse que el estado siga siendo
  válido.
- Un `buffer` derivado no puede cruzar un `extern` como si fuera un puntero
  ABI ordinario.
- Los handles `opaque` también tienen estados de propietario, prestado y
  cerrado; las operaciones `close_*` consumen el handle propietario.

Estas reglas no introducen un recolector de basura. La liberación del
almacenamiento se realiza mediante las operaciones y hooks definidos por el
lenguaje y su backend.

## Perfiles de optimización

El perfil se selecciona con `clause Optimizations` en el módulo de entrada:

| Perfil | Comportamiento actual |
| --- | --- |
| `dev` | Conserva el IR emitido por Bagron después de verificarlo; sirve para inspección y comparación. |
| `prod` | Es el perfil predeterminado. Aplica el pipeline de optimización de producción y expande los `inline` explícitos admitidos. |
| `high` | Usa un nivel de generación de código más alto y un pipeline más agresivo. |

Los perfiles cambian el IR y el coste de generación, no las reglas
semánticas ni el límite entre código seguro e inseguro. Todos pasan por la
verificación de LLVM correspondiente.

## Módulos, destinos y ABI

Los imports se resuelven dentro de la raíz del proyecto y se rechazan las
rutas absolutas, el traversal y los enlaces que terminen fuera de esa raíz.
Los ciclos de imports son errores. Las cláusulas `System`, `Arch`, `Boot` y
`ABI` de los módulos se contrastan con el destino elegido por el módulo de
entrada. Baremetal AMD64 requiere `clause ABI "sysv_amd64"`; la ABI no se
infiere ni permite convenciones definidas por el usuario.

`extern` declara una firma ABI para código fuera de Bagron. Sus restricciones
son deliberadas: no todos los tipos del lenguaje son tipos ABI, y los
descriptores administrados no se pueden tratar como punteros extranjeros sin
una representación compatible declarada. `extern`, al igual que el
ensamblador, se considera una llamada insegura desde una función segura.

## Límites actuales relevantes

- La ruta principal depende de Gram y de su biblioteca AOT/FFI instalada.
- El análisis estricto es el comportamiento normal, pero `@unsafe` y las
  fronteras extranjeras siguen existiendo por diseño.
- No hay recolector de basura, `int` genérico, retorno directo de punteros
  crudos, ni conversiones implícitas generales para hacer más permisivo el
  lenguaje.
- Los detalles de destinos, perfiles, tipos, arrays, punteros, propiedad y
  ABI deben consultarse en sus documentos específicos; este archivo resume
  sus contratos y no los sustituye.

## Documentación relacionada

- [Tipos](02-Básico/01-Tipos.md)
- [Especificadores y calificadores](02-Básico/03-Especificadores%20y%20Calificadores.md)
- [Punteros](02-Básico/05-Punteros.md)
- [Módulos e imports](02-Básico/07-Módulos%20e%20Imports.md)
- [Buffers y propiedad](02-Básico/08-buffer.md)

