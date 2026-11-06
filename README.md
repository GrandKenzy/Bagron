# Bagron

<p align="center">
  <img src="badge/banner.jpeg" alt="Bagron Programming Language" />
</p>

<p align="center">
  <b>Bagron es un lenguaje compilado y estáticamente tipado cuya implementación actual genera código nativo mediante LLVM.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.1.3-blue.svg" alt="Versión">
  <img src="https://img.shields.io/badge/backend-LLVM%20IR-orange.svg" alt="Backend LLVM IR">
  <img src="https://img.shields.io/badge/license-Apache--2.0-purple.svg" alt="Licencia">
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
artefactos nativos para los targets implementados está disponible. Bagron
también puede generar ejecutables ELF para Android mediante el NDK, en los
targets `aarch64-linux-android<api>` y `x86_64-linux-android<api>`.

La compilación requiere la biblioteca AOT/FFI de Gram configurada; el frontend
no activa silenciosamente un parser alternativo si falta.

El comportamiento estricto forma parte del flujo normal. La CLI actual no
expone un modo global `strict`; `@unsafe` es una excepción localizada por
función y no elimina las reglas de tipos, ABI ni de `main`.

Las pruebas rápidas viven en `tests/light/` y las pruebas costosas o de
backend en `tests/aggressive/`, con los archivos de soporte de integración en
`tests/aggressive/fixtures/`. Se ejecutan por ruta con `vnma test <ruta>`;
`vnma test tests/light` es la comprobación habitual y
`vnma test tests/aggressive` cubre los casos integrales.

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

* **Targets multiplataforma:** Las cláusulas `System`, `Arch` y `ARCHB`
  distinguen el sistema objetivo, la arquitectura normalizada y su ancho en
  bits. Android requiere un triple LLVM explícito y un Android NDK disponible;
  Bagron genera ELF nativo, no APK.

* **CLI verificable:** `bagron --version` muestra la versión canónica del
  compilador y `bagron --help` lista las operaciones disponibles.

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
  enlaza un ejecutable nativo para targets de sistema; con `System "baremetal"` genera
  objetos ELF `.o`, un linker script y un binario plano `.bin`. El perfil
  `Boot "multiboot2"` añade la ISO `.iso`; requiere `grub-mkrescue` y
  `xorriso` en `PATH` o instalados dentro de WSL. `Boot "none"` deja la
  imagen plana sin empaquetarla.
* **Android NDK (opcional):** Necesario solo para targets Android. Define
  `ANDROID_NDK_HOME` o `ANDROID_NDK_ROOT` apuntando al NDK instalado; Bagron
  resuelve automáticamente `clang`, `ld.lld` y el sysroot de la API indicada
  por el triple.

---

## Herramientas

El compilador se apoya en dos herramientas del mismo ecosistema:

* **[Gram](https://github.com/GrandKenzy/Gram):** motor de parseo del frontend. Define las reglas gramaticales BNF combinatorias del lenguaje (`core/frontend/syntax/`). Se instala con vnma.
* **[vnma](https://github.com/GrandKenzy/vnma) (Vendor Manager):** gestor de dependencias y empaquetado para proyectos Python. Descarga, construye y extrae wheels compatibles con la plataforma directamente en el proyecto, con aislamiento de rutas en tiempo de ejecución y compatibilidad con binarios nativos.
  * Instala desde PyPI, rutas locales (monorepos) y repositorios Git.
  * Genera un `vnma.lock` determinista con versiones, orígenes y metadatos binarios, para builds reproducibles.
  * Instalación: `pip install vnma`.

Para comprobar una instalación de Bagron:

```powershell
bagron --version
```

## Instalación

### Windows

Desde una copia del repositorio:

```powershell
python installer.py
```

El instalador crea `bagron.cmd` y `bagron.ps1` y registra la carpeta `bin/`
en el PATH del usuario.

Desde el release puedes descargar el instalador compilado
`Bagron-1.1.3-Setup.exe` y ejecutarlo directamente. La release solo publica
este instalador ejecutable; las fuentes permanecen disponibles en GitHub.

El instalador compilado incluye un runtime portable de Python 3.14 con
`vnma`, Gram, `llvmlite` y el parser AOT ya preparados. Los extrae en
`.runtime/` y `vendor/` sin ejecutar `pip`, descargar Gram o reconstruir el
parser; no necesita Python, vnma ni Gram instalados globalmente. LLVM/Clang/LLD
sigue siendo necesario para compilar programas nativos.

La ejecución directa desde una copia del repositorio (`python installer.py`)
sigue siendo una ruta de desarrollo y usa Python 3.14+ del sistema para crear
su runtime local.

### Linux

El instalador Linux compilado incluye un runtime portable de Python 3.14 con
`vnma`, Gram, `llvmlite` y el parser AOT ya preparados. Los extrae en
`.runtime/` y `vendor/` sin red ni reconstrucción; no requiere Python, vnma ni
Gram globales. LLVM/Clang/LLD sigue siendo necesario para compilar programas;
los proyectos que usen `net` con HTTPS necesitan `libcurl.so.4`. Puede ejecutarse directamente desde el
release publicado:

```bash
curl -fsSL https://raw.githubusercontent.com/GrandKenzy/Bagron/1.1.3/install.sh | bash
```

Desde el release puedes descargar el instalador compilado
`Bagron-1.1.3-linux-x86_64`, hacerlo ejecutable y ejecutarlo:

```bash
chmod +x Bagron-1.1.3-linux-x86_64
./Bagron-1.1.3-linux-x86_64
```

La release solo publica este ejecutable Linux. El instalador coloca los
lanzador `bagron` en `~/.local/bin`; si esa carpeta no está en el
PATH, añádela en el perfil de tu shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Para desinstalar una instalación Linux usando el Python incluido:

```bash
"$HOME/Bagron/.runtime/bin/python" "$HOME/Bagron/installer.py" --uninstall
```

## Instaladores preconstruidos

Los instaladores de la release 1.1.3 incorporan los componentes preparados
por GitHub Actions para cada plataforma: fuentes del compilador, Python 3.14
portable, `vnma`, dependencias locales (Gram y `llvmlite`) y la biblioteca
Gram AOT junto con su manifiesto. Su instalación no necesitará descargar
Gram ni ejecutar `vnma install` o reconstruir el parser; el instalador
comprobará el bundle antes de crear los lanzadores. La ruta de instalación
desde fuentes seguirá disponible para desarrolladores.

El empaquetado omite alias duplicados del runtime: Linux reconstruye los
enlaces simbólicos relativos de Python y sus bibliotecas, mientras que Windows
crea enlaces físicos cuando el sistema de archivos lo admite (o conserva
copias independientes como alternativa). Se verifican las rutas del manifiesto
antes de restaurarlas; esto no modifica el Python global del usuario.

**Importante:** instalar sin Internet no equivale a compilar sin herramientas
externas. Para generar y enlazar ejecutables nativos siguen siendo necesarias
las herramientas LLVM/Clang/LLD correspondientes; Android necesita su NDK.
Las releases anteriores a 1.1.3 conservan el mecanismo anterior.

## Extensión para VS Code

El repositorio incluye el paquete [`bagron-language-support.vsix`](tools/vscode/bagron-language-support.vsix).
Consulta la [guía de instalación del VSIX](docs/es/01-Arquitectura/03-instalacion-vscode.md)
para instalarlo manualmente o mediante `bagron --vscode install`.

## Android

El soporte Android se orienta primero a ejecutables nativos para pruebas en
dispositivo o emulador. Consulta la [guía del entorno Android](docs/es/01-Arquitectura/05-android.md)
para preparar el NDK, seleccionar `aarch64-linux-android35` o
`x86_64-linux-android35`, verificar el ELF y desplegarlo con `adb`.

---

## Licencia

Este proyecto está bajo la Licencia Apache 2.0 con el rider de no-derivados y uso comercial.
Consulta el archivo `LICENSE` para más detalles.

<p align="center">
  <img src="badge/footer.jpeg" alt="Bagron, a Discentra Community project" />
</p>

