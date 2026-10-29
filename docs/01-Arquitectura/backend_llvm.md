# Backend LLVM

El backend actual consume los símbolos semánticos producidos por
`core/frontend` y no vuelve a interpretar el AST ni la sintaxis antigua.

## Primera etapa

La primera etapa genera `build/<modulo>.ll`, `build/<modulo>.obj` y
`build/<modulo>.exe` para:

- variables globales escalares;
- enteros de ancho fijo `Bint<n>` y `uBint<n>`;
- booleanos y números de punto flotante;
- arrays globales y locales inicializados con literales, con tamaños inferidos;
  los `char[n]` reservan una celda final para `NUL` sin generar checks en
  runtime;
- referencias a globals `const` que puedan plegarse estáticamente.
- tipos agregados nominales `struct`, `mold` y `flags`, con inicialización
  determinista, acceso a miembros y asignaciones locales;
- funciones auxiliares con parámetros y retornos enteros, `middle`, `float`,
  `double`, `void` o punteros, llamadas y operaciones aritméticas/bitwise
  básicas;
- parámetros especiales `Len_t` y `Size_t`: el frontend exige datos con
  metadatos calculables en compilación y el backend baja los valores como
  `i64` constantes adicionales;
- `Len_t` también puede expandirse para un `chain` constante; la longitud
  emitida incluye su `NUL`, y la biblioteca de salida descuenta ese byte para
  escribir el texto visible sin escanearlo;
- las funciones seguras que reciben arrays deben declarar su `Len_t`; las
  funciones `@unsafe` pueden optar por una firma de bajo nivel sin esa
  expansión;
- declaraciones `extern` como `declare` LLVM, llamadas a sus símbolos y
  enlace de las bibliotecas registradas;
- direccionamiento explícito `$`, desreferenciación parentizada, acceso por
  índice y acceso a miembros mediante GEP, con trampa para punteros nulos;
- conversiones constantes de `char` a `chain`, emitidas como regiones LLVM
  `private constant` sin asignaciones ni llamadas durante la ejecución;
- `if`, `elif`, `else`, `while` y `for` numérico con comparaciones, condiciones
  lógicas y anidación;
- `break` y `continue` dentro de bucles;
- frontera de memoria segura: `@unsafe` habilita desreferenciación de
  procedencia desconocida, índices dinámicos y llamadas a funciones inseguras;
  `@assembler` implica `@unsafe`;
- `main() int` como función interna LLVM `i32` y wrapper nativo `main() i32`.

Los bloques `#prep assembler "dialecto"` de funciones `@assembler` se extraen
antes del parser, se expanden con los registros ABI de Windows x64 y se
ensamblan a objetos dentro de `build/prep/` para enlazarlos con LLVM. Intel y
AT&T son los dialectos soportados; los parámetros enteros se mapean por ancho a
los alias de `RCX/RDX/R8/R9` y los restantes a sus offsets de stack ABI. El
resultado actual de `return asm` es el entero retornado por `EAX`.

Las firmas `extern` usan la convención C del target LLVM seleccionado por
`Arch`/`System`; en Windows x64 esto corresponde a la ABI C de Windows. La
primera fase admite retornos y parámetros enteros, `middle`, `float`, `double`,
`void` y punteros, con `void*` representado como `i8*`.
`Len_t` y `Size_t` no forman parte de las firmas `extern`, porque sus
argumentos expandidos solo pueden ser insertados por el compilador de Bagron.

Los globals sin inicializador se emiten con valor cero. Las direcciones de
globals y de elementos/campos estáticos se emiten como inicializadores GEP;
las referencias a globals mutables por valor, ciclos de inicialización y
`callptr` quedan fuera de esta primera emisión. Las variables locales se
materializan con `alloca`, `load` y `store`; los parámetros también se copian
a slots locales para permitir su asignación. El wrapper nativo devuelve
directamente el `int` producido por `main`.

Las definiciones semánticas de `enum`, `struct`, `mold` y `flags` pueden
coexistir con el módulo y con `main`. Los enums se representan según su tipo
base (`i8`, `i16`, `i32`, etc.); los agregados se emiten como tipos
identificados LLVM. `struct` conserva campos ordenados, `mold` reserva un
buffer del tamaño máximo y lo proyecta al tipo del miembro solicitado, y
`flags` usa un entero base explícito con máscaras, desplazamientos y
read-modify-write. Los carriers internos de alineación permiten expresar
`__align__`, mientras `@packed` reduce los accesos de miembros a alineación de
un byte y `volatile` produce cargas y stores `volatile` verificables por LLVM.

## Inicialización de LLVM

EasyC usa `llvmlite` desde el entorno gestionado por vnma. El backend inicializa
los registros de targets y el asm printer, crea un `ir.Module`, configura el
triple y el data layout, y finalmente verifica el texto mediante
`binding.parse_assembly(...).verify()`.

`Arch` acepta `auto` por defecto, además de `x86`, `amd`, `arm` o un triple LLVM.
`auto` usa la arquitectura del host. Un target que LLVM no pueda resolver es un
error; no se hace fallback silencioso.

## Limitaciones actuales

El backend todavía no traduce clases ni `callptr`; las funciones de entrada
siguen requiriendo exactamente `main() int`. `middle`, `float` y `double` se
representan respectivamente como `half`, `float` y `double` en LLVM, aunque la
ABI concreta de una plataforma puede promover o pasar `half` de otra forma.
Las variables locales emitibles pueden ser escalares enteros, punteros, arrays o
agregados nominales; sus declaraciones, lecturas, asignaciones y asignaciones
compuestas generan instrucciones LLVM.
Las estructuras de control generan bloques LLVM explícitos y mantienen una pila
de destinos para que `break` y `continue` respeten el bucle anidado actual.
En funciones seguras no se insertan comprobaciones de límites: los índices de
arrays deben ser demostrables en compilación. Los punteros recibidos como
parámetros pueden reenviarse, pero su desreferenciación, el indexado crudo y
el acceso a procedencia desconocida requieren `@unsafe`; la frontera de
llamadas impide que una función segura invoque una función insegura.
El backend no genera `program.c` ni headers C.
