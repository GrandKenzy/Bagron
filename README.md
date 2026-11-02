# Bagron

<p align="center">
  <img src="badge/header.gif"/>
</p>

<p align="center">
  <b>Bagron es un lenguaje compilado y estáticamente tipado cuya implementación actual genera código nativo mediante LLVM.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue.svg" alt="Versión">
  <img src="https://img.shields.io/badge/backend-LLVM%20IR-orange.svg" alt="Backend LLVM IR">
  <img src="https://img.shields.io/badge/license-MIT-purple.svg" alt="Licencia">
  <img src="https://img.shields.io/badge/status-active-brightgreen.svg" alt="Estado">
</p>

---

## ¿Qué es Bagron?

**Bagron** recibe archivos `.bg`, valida tipos, ámbitos, flujo, ownership y
reglas de acceso, y genera LLVM IR antes de producir objetos y enlazar el
artefacto para el target elegido. El parser de la ruta actual es Gram mediante
su interfaz AOT/FFI.

No usa una máquina virtual de Bagron ni un recolector de basura integrado. Los
`buffer` siguen reglas explícitas de ownership y liberación; los punteros
crudos, `extern` y el ensamblador son fronteras que pueden salir de las
comprobaciones estáticas.

La explicación completa del flujo y de los límites de seguridad está en
[Cómo funciona Bagron](docs/es/01-Funcionamiento.md).

---

## Estado actual

La ruta principal de análisis estático, emisión de LLVM IR y generación de
artefactos nativos para los targets implementados está disponible. La
compilación requiere la biblioteca AOT/FFI de Gram configurada; el frontend no
activa silenciosamente un parser alternativo si falta.

El comportamiento estricto forma parte del flujo normal. La CLI actual no
expone un modo global `strict`; `@unsafe` es una excepción localizada por
función y no elimina las reglas de tipos, ABI ni de `main`.

---

## Características Principales

* **Compilación directa a LLVM IR:** El compilador emite LLVM IR mediante `llvmlite` para su verificación y generación de código nativo.

* **Punto de entrada obligatorio:** Cada módulo ejecutable debe declarar `func main() int32:`; su expresión entera de retorno se usa como código de salida, salvo que el flujo termine mediante una llamada `Never`. Los métodos de clase no cuentan como entrypoint.

* **Sintaxis indentada:** Los fuentes usan archivos `.bg` y bloques delimitados por indentación.

* **Validación semántica:** El frontend registra y valida tipos, variables y scopes antes de emitir LLVM IR.

* **Datos globales visibles:** Las funciones y métodos resuelven automáticamente
  los globals públicos de su módulo y de módulos importados; `private` sigue
  bloqueando el acceso entre módulos. La declaración `global` no forma parte
  de la sintaxis.

* **Terminación explícita:** `Never` es un tipo de retorno para funciones que
  no regresan; una llamada a una función `Never` termina el flujo actual y no
  puede usarse como valor ni como almacenamiento.

* **Constantes explícitas:** `const tipo` expresa un valor constante; los punteros separan la constancia del puntero y del valor apuntado.

* **Memoria explícita:** `$valor` obtiene una dirección, `(p)` la
  desreferencia y `((pp))` permite varios niveles. `&` conserva el AND
  bitwise; los arrays se indexan con GEP LLVM y los punteros nulos se atrapan
  en tiempo de ejecución. Las operaciones sobre procedencia desconocida y
  los índices dinámicos requieren `@unsafe`; `@assembler` ya implica ese
  decorador.

* **Estructuras, Enumeraciones y Clases:**
  * `struct`, `mold` y `flags`: Tipos nominales emitidos a LLVM con acceso a
    miembros; `mold` comparte almacenamiento como una unión y `flags` usa una
    base entera explícita (`flags Nombre uint8:`) con campos de bits.
  * `enum`: Enumeraciones con base entera `int32` por defecto o un tipo entero explícito, además de valores implícitos/explícitos.
  * `class`: Tipos nominales respaldados por `struct`; sus atributos se definen
    con un unico iniciador `func __init__(...) void:` o
    `func __frontend__(...) void:`. El segundo permite conversiones como
    `element: Clase = "Hola"`. Sus métodos se declaran indentados dentro de la
    clase y reciben la instancia implícitamente; `@static` queda encapsulado
    en la clase. Admite herencia simple estática (`class Hija(Padre):`): los
    campos se aplanan en el layout y los métodos se resuelven en compilación;
    `super.__init__(...)` inicializa explícitamente al padre. No hay vtables ni
    estado de herencia en runtime. Incluye hooks mágicos opcionales:
    `__ongetter__(nombre: chain, longitud: Len_t) int32` y
    `__onsetter__(nombre: chain, longitud: Len_t) int32`; deben retornar `1`
    para permitir el flujo y `0` para detenerlo. `__eq__() bool` se usa
    automáticamente cuando una instancia aparece como condición y, si no se
    declara, la condición vale `false`. Estos hooks solo se insertan desde
    fuera de la clase; los accesos internos no los disparan. `@after` mueve
    cualquiera de esos dos hooks después de la lectura o escritura. Las
    operaciones matemáticas pueden sobrecargarse con `__add__`, `__sub__`,
    `__mul__`, `__div__`/`__truediv__`, `__mod__`, `__pos__` y `__neg__`;
    también se reconocen los operadores bitwise equivalentes. `Del instancia`
    llama a `__deletion__() void` si la clase lo define; sin ese método, `Del`
    no ejecuta ninguna acción automática. `@frozen` permite inicializar sus
    atributos únicamente en `__init__` o `__frontend__`; después rechaza
    escrituras directas, compuestas y alias de puntero conocidos. La
    congelación es superficial y se propaga por la herencia.

* **Modulos y dependencias nativas:** `import` carga archivos `.bg`; `extern`
  declara firmas ABI y `#link "./directorio"` añade rutas locales, relativas y
  acotadas al proyecto para librerías compiladas sin alterar el entorno global.

* **Control de Flujo Expresivo:**
  * Condicionales: `if`, `elif`, `else`, `not`.
  * Bucles condicionales: `while condicion:`.
  * Iteración numérica tipada con `ran` y recorrido de arrays con `for i: int32 in values:`.

* **Herramientas del proyecto:** El compilador usa Gram para el parseo y vnma para gestionar dependencias y binarios.

## Seguridad y límites

El código seguro no puede realizar ciertas operaciones cuya corrección no
puede probarse, como desreferenciar punteros de procedencia desconocida,
acceder dinámicamente a arrays sin una prueba de rango o llamar a una función
insegura. Los `buffer` tienen comprobaciones de capacidad y los accesos nulos
detectados por el backend producen una trampa.

Esto no convierte a Bagron en un lenguaje formalmente memory-safe. `@unsafe`,
`@assembler` y `extern` permiten cruzar la frontera estática; la validez de
direcciones, lifetimes, ABI y código extranjero queda fuera de esa garantía.
Los perfiles `dev`, `prod` y `high` cambian optimización, no las reglas de
seguridad.

---

## Requisitos / Requirements

* **Python:** 3.14 o superior.
* **llvmlite:** 0.50.0, gestionado mediante vnma.
* **LLVM/Clang/LLD:** La compilación genera y verifica `.ll`, produce `.obj` y
  enlaza un `.exe` para targets de sistema; con `System "baremetal"` genera
  objetos ELF `.o`, un linker script y un binario plano `.bin`. El perfil
  `Boot "multiboot2"` añade la ISO `.iso`; requiere `grub-mkrescue` y
  `xorriso` en `PATH` o instalados dentro de WSL. `Boot "none"` deja la
  imagen plana sin empaquetarla.

---

## Herramientas

El compilador se apoya en dos herramientas del mismo ecosistema:

* **[Gram](https://github.com/GrandKenzy/Gram):** motor de parseo del frontend. Define las reglas gramaticales BNF combinatorias del lenguaje (`core/frontend/syntax/`). Se instala con vnma.
* **[vnma](https://github.com/GrandKenzy/vnma) (Vendor Manager):** gestor de dependencias y empaquetado para proyectos Python. Descarga, construye y extrae wheels compatibles con la plataforma directamente en el proyecto, con aislamiento de rutas en tiempo de ejecución y compatibilidad con binarios nativos.
  * Instala desde PyPI, rutas locales (monorepos) y repositorios Git.
  * Genera un `vnma.lock` determinista con versiones, orígenes y metadatos binarios, para builds reproducibles.
  * Instalación: `pip install vnma`.

---

---

## Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo de licencia para más detalles.

<p align="center">
  <img src="badge/footer.jpeg"/>
</p>

