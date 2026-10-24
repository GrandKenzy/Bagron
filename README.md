# Easy-C ( EC )

<p align="center">
  <img src="badge/header.gif"/>
</p>

<p align="center">
  <b>EC es un lenguaje de programación moderno, limpio y estáticamente tipado, compilado directamente a LLVM IR por ECC (EasyC Compiler). Comparte IR con C y es totalmente interoperable con C y su entorno.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.3.0-blue.svg" alt="Versión">
  <img src="https://img.shields.io/badge/backend-LLVM%20IR-orange.svg" alt="Backend LLVM IR">
  <img src="https://img.shields.io/badge/interop-C99%20%2F%20C11-green.svg" alt="Interoperabilidad C">
  <img src="https://img.shields.io/badge/license-MIT-purple.svg" alt="Licencia">
  <img src="https://img.shields.io/badge/status-active-brightgreen.svg" alt="Estado">
</p>

---

## ¿Qué es EC?

**EC** (Easy-C) combina la elegancia sintáctica, la POO y la legibilidad de lenguajes como Python con la velocidad, el control de bajo nivel y la interoperabilidad nativa de **C**.

En lugar de depender de una máquina virtual pesada o de un runtime complejo con recolección de basura, **ECC** (EasyC Compiler) procesa el código fuente, valida tipos y ámbitos estáticamente y emite **LLVM IR** directamente. No existe ningún paso intermedio que genere código C ni trucos de traducción: tanto C como EC se compilan bajo la misma IR por LLVM, por lo que ambos lenguajes conviven en el mismo programa de forma natural.

---

## Características Principales

* **Compilación directa a LLVM IR:** ECC no genera C intermedio. EC y C se compilan bajo la misma IR, y LLVM se encarga de la optimización y la generación de código nativo.

* **Interoperabilidad total con C y su entorno:** Consumo directo de cualquier biblioteca C, sus headers, binarios y convenciones de enlace, sin capas de conversión.

* **Sintaxis Minimalista e Intuitiva:** Basada en indentación limpia, sin puntos y coma obligatorios ni sobrecarga de paréntesis.

* **Cero Costo de Abstracción:** Las estructuras y llamadas mapean directamente a instrucciones de LLVM IR, sin capas intermedias innecesarias.

* **Constantes por Convención:** Todo identificador en **MAYÚSCULAS** es tratado como constante inmutable en tiempo de compilación.

* **Estructuras, Enumeraciones y Clases:**
  * `struct`: Estructuras planas con layout de memoria compatible con C.
  * `enum`: Enumeraciones fuertemente tipadas y con nombres cualificados (`EventType.QUIT`).
  * `class`: Tipos orientados a objetos con ciclo de vida RAII (`__init__`, `@method`, `destroy`).

* **Control de Flujo Expresivo:**
  * Condicionales: `if`, `elif`, `else`, `not`.
  * Bucles condicionales: `while condicion:`.
  * Iteración numérica directa sin listas en memoria: `for i ran 100:`.

* **Integración con Headers C y Modernización:** Consumo directo de bibliotecas C mediante sus headers tradicionales, y modernizados mediante archivos `.ch`, que permiten llamadas a otros headers, binarios y linking (`@header`, `@link`, `@bin`).

* **Toolchain Integrada:** Compilador, ejecutor instantáneo, limpiador de caché y generador automático de extensión para Visual Studio Code (`.vsix`).

---

## Compatibilidad con GCC y MSVC (planeado)

Se planea que ECC soporte las directivas propias de **GNU C Compiler (GCC)** y de **MSVC**, de modo que el compilador reconozca ambos entornos y pueda procesar código que ya se ejecutaba con esos compiladores (atributos, pragmas y macros específicos de cada uno). Esta característica está en el roadmap y aún no forma parte de la versión actual.

---

## Requisitos / Requirements

* **Python:** 3.13 o superior (requerido para soporte avanzado de f-strings PEP 701).
* **LLVM:** ECC emite LLVM IR directamente, por lo que no depende de un compilador C externo para compilar código EC.

---

## Herramientas

ECC se apoya en dos herramientas del mismo ecosistema:

* **[Gram](https://github.com/GrandKenzy/Gram):** motor de parseo del frontend de ECC. Define las reglas gramaticales BNF combinatorias del lenguaje (`core/frontend/*/syntax/`). Se instala con vnma.
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