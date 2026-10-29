# Bagron

<p align="center">
  <img src="badge/header.gif"/>
</p>

<p align="center">
  <b>Bagron es un lenguaje de programación moderno, limpio y estáticamente tipado, compilado directamente a LLVM IR.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.3.0-blue.svg" alt="Versión">
  <img src="https://img.shields.io/badge/backend-LLVM%20IR-orange.svg" alt="Backend LLVM IR">
  <img src="https://img.shields.io/badge/license-MIT-purple.svg" alt="Licencia">
  <img src="https://img.shields.io/badge/status-active-brightgreen.svg" alt="Estado">
</p>

---

## ¿Qué es Bagron?

**Bagron** combina la elegancia sintáctica, la orientación a objetos y la legibilidad de lenguajes de alto nivel con la velocidad, el control de bajo nivel y el alto rendimiento.

En lugar de depender de una máquina virtual pesada o de un runtime complejo con recolección de basura, el compilador de **Bagron** procesa el código fuente, valida tipos y ámbitos estáticamente y emite **LLVM IR** directamente. No existe ningún paso intermedio que genere código intermedio superfluo: LLVM se encarga de la optimización y la generación de código nativo para la arquitectura de destino.

---

## Características Principales

* **Compilación directa a LLVM IR:** El compilador emite LLVM IR mediante `llvmlite` para su verificación y futura generación de código nativo.

* **Punto de entrada obligatorio:** Cada módulo ejecutable debe declarar `func main() int32:`; su expresión entera de retorno se usa como código de salida, salvo que el flujo termine mediante una llamada `Never`. Los métodos de clase no cuentan como entrypoint.

* **Sintaxis Minimalista e Intuitiva:** Basada en indentación limpia (`.bg`), sin puntos y coma obligatorios ni sobrecarga de paréntesis innecesarios.

* **Validación semántica:** El frontend registra y valida tipos, variables y scopes antes de emitir LLVM IR.

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
    no ejecuta ninguna acción automática.

* **Modulos y dependencias nativas:** `import` carga archivos `.bg`; `include
  "header" link "library"` resuelve headers y bibliotecas del sistema, y
  `extern "library":` declara firmas ABI que LLVM enlaza directamente.

* **Control de Flujo Expresivo:**
  * Condicionales: `if`, `elif`, `else`, `not`.
  * Bucles condicionales: `while condicion:`.
  * Iteración numérica tipada: `for i: int8 ran (1, 100, 1):`.

* **Toolchain Integrada:** Compilador, analizador sintáctico y herramientas para el flujo de trabajo de desarrollo.

---

## Requisitos / Requirements

* **Python:** 3.14 o superior.
* **llvmlite:** 0.50.0, gestionado mediante vnma.
* **LLVM/Clang/LLD:** La compilación genera y verifica `.ll`, produce `.obj` y enlaza un `.exe` para el entrypoint mínimo `main`.

---

## Herramientas

El compilador se apoya en dos herramientas del mismo ecosistema:

* **[Gram](https://github.com/GrandKenzy/Gram):** motor de parseo del frontend. Define las reglas gramaticales BNF combinatorias del lenguaje (`core/frontend/syntax/`). Se instala con vnma.
* **[vnma](https://github.com/GrandKenzy/vnma) (Vendor Manager):** gestor de dependencias y empaquetado para proyectos Python. Descarga, construye y extrae wheels compatibles con la plataforma directamente en el proyecto, con aislamiento de rutas en tiempo de ejecución y compatibilidad con binarios nativos.
  * Instala desde PyPI, rutas locales (monorepos) y repositorios Git.
  * Genera un `vnma.lock` determinista con versiones, orígenes y metadatos binarios, para builds reproducibles.
  * Instalación: `pip install vnma`.

---

## Instalación y Uso Rápido

* NOTA: La instalación, uso rápido y ejemplos está en discusión.

## Documentación

* NOTA: Por definir

---

## Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo de licencia para más detalles.

<p align="center">
  <img src="badge/footer.jpeg"/>
</p>
