# Easy-C (EGL)

<p align="center">
  <b>Un lenguaje de programación moderno, limpio y estáticamente tipado que compila a código C monolítico de alto rendimiento (C99/C11).</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.2.0-blue.svg" alt="Versión">
  <img src="https://img.shields.io/badge/target-C99%20%2F%20C11-green.svg" alt="Target C">
  <img src="https://img.shields.io/badge/license-MIT-purple.svg" alt="Licencia">
  <img src="https://img.shields.io/badge/status-active-brightgreen.svg" alt="Estado">
</p>

---

## 🚀 ¿Qué es Easy-C?

**Easy-C (EGL)** combina la elegancia sintáctica y la legibilidad de lenguajes como Python con la velocidad, el control de bajo nivel y la interoperabilidad nativa de **C**.

En lugar de depender de una máquina virtual pesada o de un runtime complejo con recolección de basura, Easy-C procesa el código fuente, valida tipos y ámbitos estáticamente, y emite un único archivo de código C monolítico optimizado (`program.c`) listo para ser compilado con GCC, Clang o MSVC.

---

## ✨ Características Principales

* 🎯 **Sintaxis Minimalista e Intuitiva:** Basada en indentación limpia, sin puntos y coma obligatorios ni sobrecarga de paréntesis.
* ⚡ **Cero Costo de Abstracción:** El código generado en C no introduce capas intermedias innecesarias; las estructuras y llamadas mapean directamente a instrucciones nativas.
* 🧩 **Tipos de Datos Autodefinidos (`Type`):** El compilador solo conoce primitivas de máquina (`__int_t__`, `__void_p_t__`, `__bool_t__`). Toda la semántica visible (`int`, `uint32`, `float`, `char`, `bool`, `ptr`, etc.) se define en la propia librería estándar en EGL (`standard.egl`) mediante `public struct Type`.
* 🔒 **Constantes por Convención:** Todo identificador en **MAYÚSCULAS** es tratado como constante inmutable en tiempo de compilación.
* 📦 **Estructuras, Enumeraciones y Clases:**
  * `struct`: Estructuras planas de C con layout de memoria compatible.
  * `enum`: Enumeraciones fuertemente tipadas y con nombres cualificados (`EventType.QUIT`).
  * `class`: Tipos orientados a objetos con ciclo de vida RAII (`__init__`, `@method`, `destroy`).
* 🔄 **Control de Flujo Expresivo:**
  * Condicionales: `if`, `elif`, `else`, `not`.
  * Bucles condicionales: `while condicion:`.
  * Iteración numérica directa sin listas en memoria: `for i ran 100:`.
* 🔗 **Interoperabilidad Nativa con C:** Consumo directo de cualquier biblioteca C mediante contratos de firmas foráneas (`.externs.egl`), con directivas de enlace automático (`@header`, `@link`, `@bin`).
* 🛠️ **Toolchain Integrada:** Compilador, ejecutor instantáneo, limpiador de caché y generador automático de extensión para Visual Studio Code (`.vsix`) con tema Noble Dark y resaltado de sintaxis TextMate.

---

## 📥 Requisitos

* **Python:** 3.10 o superior.
* **Compilador C:** GCC, Clang o TCC accesible en el PATH del sistema (para el flag `--build` / `--run`).

---

## 🛠️ Instalación y Uso Rápido

Clona el repositorio:

```bash
git clone https://github.com/GrandKenzy/Easy-C.git
cd Easy-C
```

### Comandos de la CLI (`egl.py` / `egl.bat`)

```bash
# Compilar el proyecto en 'source' y generar 'program.c':
python egl.py compile source

# Compilar a C y construir el ejecutable binario con GCC:
python egl.py compile source --build

# Compilar, construir y ejecutar directamente el programa:
python egl.py run source

# Limpiar toda la caché del proyecto (.cache, __pycache__, .pyc):
python egl.py cache clear

# Generar e instalar la extensión oficial para Visual Studio Code:
python egl.py extension --install
```

> **En Windows**, puedes usar directamente el lanzador `egl.bat`:
> ```cmd
> egl.bat compile source --build
> egl.bat run source
> egl.bat cache clear
> ```

---

## 💡 Ejemplos de Código

### 1. Hola Mundo y Funciones

```easy-c
clause Target 'egl-c'
import standard

int sumar(int a, int b):
    return a + b

int resultado = sumar(15, 27)
print("El resultado es:", resultado)
```

### 2. Iteración y Bucles

```easy-c
clause Target 'egl-c'
import standard

; Iteración numérica directa con ran
for i ran 5:
    print("Iteración:", i)

; Bucle while
int contador = 0
while contador < 3:
    print("Contador:", contador)
    contador = contador + 1
```

### 3. Ventana Gráfica y Eventos con SDL3

Easy-C permite integrar librerías como **SDL3** de forma idiomática y elegante:

```easy-c
clause Target 'egl-c'

import sdl3
import standard

declare sdl3.Window as Window
declare sdl3.Event as Event
declare sdl3.FRect as FRect
declare sdl3.EventType as EventType

; Inicialización del subsistema
sdl3.init(0)

; Creación de ventana y rectángulo
Window ventana = Window("Easy-C SDL3 - Rectangulo y Eventos", 640, 480)
FRect rect = FRect(220.0, 165.0, 200.0, 150.0)

bool running = true
Event event

; Bucle principal de eventos y renderizado
while running:
    while sdl3.poll_event(&event):
        if event.type == EventType.QUIT:
            running = false

    sdl3.set_draw_color(ventana._renderer, 30, 30, 45, 255)
    sdl3.clear(ventana._renderer)
    sdl3.set_draw_color(ventana._renderer, 80, 180, 240, 255)
    sdl3.fill_rect(ventana._renderer, &rect)
    sdl3.present(ventana._renderer)
    sdl3.delay(16)

; Liberación limpia de recursos
ventana.destroy()
sdl3.quit()
```

---

## 📂 Estructura del Proyecto

```text
Easy-C/
├── core/
│   ├── backend/c/          # Generador de C, emitidores y librerías base (standard.egl)
│   ├── initiator/rules/    # Reglas gramaticales BNF combinatorias (gram)
│   ├── processor/          # Analizador semántico, objetos del AST y sistema de tipos
│   ├── externs/            # Parser de contratos foráneos y gestor de enlaces
│   ├── cli.py              # Interfaz de línea de comandos (CLI)
│   ├── compiler.py         # Orquestador del compilador y ensamblado monolítico
│   └── extension.py        # Generador dinámico de extensión VSIX para VS Code
├── docs/                   # Documentación técnica completa y exhaustiva
├── source/
│   ├── main.egl            # Punto de entrada de la aplicación
│   └── targets/c/          # Extensiones de librerías nativas (SDL3, WinAPI)
├── deudas/                 # Registro y seguimiento de refactorizaciones técnicas
├── egl.py                  # Script principal ejecutable
└── egl.bat                 # Lanzador rápido para Windows
```

---

## 📖 Documentación

El repositorio cuenta con una suite completa de documentación técnica en la carpeta [`docs/`](./docs/):

* **[Arquitectura del Compilador](./docs/01-Arquitectura/index.md):** Frontend gramatical, procesador semántico y emisión de backend C.
* **[Módulos, Externs y Extends](./docs/02-Modulos-y-Externs/index.md):** Sistema de módulos, resolución de dependencias y aislamiento de espacios de nombres.
* **[Integración de Librerías Compiladas](./docs/02-Modulos-y-Externs/librerias_compiladas.md):** Guía paso a paso para enlazar bibliotecas nativas C/C++ usando SDL3 como ejemplo.
* **[CLI y Herramientas](./docs/03-Guia-del-Colaborador/cli_y_herramientas.md):** Guía detallada de comandos de consola, flags del compilador y empaquetado VSIX.
* **[Referencia de Tipos y Palabras Clave](./docs/04-Referencia/tipos_y_palabras_clave.md):** Matriz de tipos nativos, propiedades mágicas y operadores del lenguaje.

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo de licencia para más detalles.
