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

* **Compilación directa a LLVM IR:** El compilador no genera pasos intermedios superfluos; emite LLVM IR directamente para optimización y generación de código de máquina nativo.

* **Sintaxis Minimalista e Intuitiva:** Basada en indentación limpia (`.bg`), sin puntos y coma obligatorios ni sobrecarga de paréntesis innecesarios.

* **Cero Costo de Abstracción:** Las estructuras y llamadas mapean directamente a instrucciones de LLVM IR, optimizando el rendimiento al máximo.

* **Constantes explícitas:** `const tipo` expresa un valor constante; los punteros separan la constancia del puntero y del valor apuntado.

* **Estructuras, Enumeraciones y Clases:**
  * `struct`: Estructuras planas de memoria directa.
  * `enum`: Enumeraciones fuertemente tipadas y con nombres cualificados (`EventType.QUIT`).
  * `class`: Tipos orientados a objetos con ciclo de vida RAII (`__init__`, `@method`, `destroy`).

* **Control de Flujo Expresivo:**
  * Condicionales: `if`, `elif`, `else`, `not`.
  * Bucles condicionales: `while condicion:`.
  * Iteración numérica tipada: `for i: int8 ran (1, 100, 1):`.

* **Toolchain Integrada:** Compilador, analizador sintáctico y herramientas para el flujo de trabajo de desarrollo.

---

## Requisitos / Requirements

* **Python:** 3.13 o superior.
* **LLVM:** Emisión de LLVM IR directa.

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
