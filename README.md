# Bagron

<p align="center">
  <img src="badge/banner.jpeg" alt="Bagron Programming Language" />
</p>

<p align="center">
  <b>Bagron es un lenguaje compilado y estáticamente tipado cuya implementación actual genera código nativo mediante LLVM.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.1.6-blue.svg" alt="Versión">
  <img src="https://img.shields.io/badge/backend-LLVM%20IR-orange.svg" alt="Backend LLVM IR">
  <img src="https://img.shields.io/badge/license-Apache--2.0-purple.svg" alt="Licencia">
  <img src="https://img.shields.io/badge/status-active-brightgreen.svg" alt="Estado">
</p>

---

## ¿Qué es Bagron?

**Bagron** recibe archivos `.bg`, valida tipos, ámbitos, flujo, propiedad
(`ownership`) y reglas de acceso, y genera LLVM IR antes de producir el objeto
y enlazar el programa para el destino elegido. El parser actual es Gram, a
través de su interfaz AOT/FFI.

Bagron no usa una máquina virtual ni incluye un recolector de basura. Los
`buffer` siguen reglas explícitas de propiedad y liberación; los punteros
crudos, `extern` y el ensamblador son fronteras que pueden quedar fuera de las
comprobaciones estáticas.

La explicación completa del flujo y de los límites de seguridad está en
[Cómo funciona Bagron](docs/es/01-Funcionamiento.md).

## Primer programa

Un programa mínimo necesita una función `main` que devuelva `int32`:

```bg
func main() int32:
    return 0
```

Guárdalo como `hola.bg` y compílalo con:

```powershell
bagron hola.bg -o build/hola --execute
```

Puedes ver más ejemplos en [`examples/`](examples/README.md) y consultar el
[índice de la documentación](docs/es/index.md) para conocer cada parte del
lenguaje.

---

## Estado actual

El compilador analiza el código, emite LLVM IR y genera artefactos nativos para
los destinos implementados. Bagron
también puede generar ejecutables ELF para Android mediante el NDK, en los
destinos `aarch64-linux-android<api>` y `x86_64-linux-android<api>`.

Para compilar, la biblioteca AOT/FFI de Gram debe estar disponible; si falta,
el frontend muestra un error en lugar de cambiar silenciosamente de parser.

Las comprobaciones estrictas forman parte del flujo normal. La CLI actual no
expone un modo global `strict`; `@unsafe` es una excepción localizada por
función y no elimina las reglas de tipos, ABI ni de `main`.

---

## Características principales

* **Compilación a código nativo:** Bagron emite LLVM IR, lo verifica y genera el artefacto nativo del destino seleccionado.

* **Punto de entrada obligatorio:** Cada módulo ejecutable debe declarar `func main() int32:`. Su retorno entero se usa como código de salida, salvo que el flujo termine mediante una llamada `Never`. Los métodos de clase no cuentan como punto de entrada.

* **Sintaxis indentada:** Los fuentes usan archivos `.bg` y bloques delimitados por indentación.

* **Validación semántica:** El frontend comprueba tipos, variables y ámbitos antes de emitir LLVM IR.

* **Datos globales visibles:** Las funciones y métodos resuelven automáticamente
  las variables globales públicas de su módulo y de los módulos importados;
  `private` sigue bloqueando el acceso entre módulos. La declaración `global`
  no forma parte de la sintaxis.

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

* **Estructuras, enumeraciones y clases:**
  * `struct`, `mold` y `flags`: Tipos nominales emitidos a LLVM con acceso a
    miembros; `mold` comparte almacenamiento como una unión y `flags` usa una
    base entera explícita (`flags Nombre uint8:`) con campos de bits.
  * `enum`: Enumeraciones con base entera `int32` por defecto o un tipo entero explícito, además de valores implícitos/explícitos.
  * `class`: Tipos nominales respaldados por `struct`, con métodos, herencia
    estática, conversión mediante `__frontend__`, hooks opcionales y el
    decorador `@frozen`. Consulta la [guía de clases](docs/es/06-clases/index.md)
    para los detalles de construcción, privacidad y destrucción.

* **Módulos y dependencias nativas:** `import` carga archivos `.bg`; `extern`
  declara firmas ABI y `#link "./directorio"` añade rutas locales, relativas y
  acotadas al proyecto para librerías compiladas sin alterar el entorno global.

* **Control de flujo:**
  * Condicionales: `if`, `elif`, `else`, `not`.
  * Bucles condicionales: `while condicion:`.
  * Iteración numérica tipada con `ran` y recorrido de arrays con `for i: int32 in values:`.

* **Destinos multiplataforma:** Las cláusulas `System`, `Arch` y `ARCHB`
  distinguen el sistema objetivo, la arquitectura normalizada y su ancho en
  bits. Android requiere un triple LLVM explícito y un Android NDK disponible;
  Bagron genera ELF nativo, no APK.

* **CLI verificable:** `bagron --version` muestra la versión canónica del
  compilador y `bagron --help` lista las operaciones disponibles.

* **Herramientas del proyecto:** Bagron usa Gram para el parseo y vnma para
  gestionar dependencias y binarios.

## Seguridad y límites

El código seguro no puede realizar ciertas operaciones cuya corrección no
puede probarse, como desreferenciar punteros de procedencia desconocida,
acceder dinámicamente a arrays sin una prueba de rango o llamar a una función
insegura. Los `buffer` tienen comprobaciones de capacidad y los accesos nulos
detectados por el backend producen una trampa.

Esto no convierte a Bagron en un lenguaje formalmente seguro frente a errores
de memoria. `@unsafe`, `@assembler` y `extern` permiten cruzar la frontera
estática; la validez de direcciones, ciclos de vida, ABI y código extranjero
queda fuera de esa garantía.
Los perfiles `dev`, `prod` y `high` cambian optimización, no las reglas de
seguridad.

---

## Requisitos

* **Python:** 3.14 o superior.
* **llvmlite:** 0.50.0, gestionado mediante vnma.
* **LLVM/Clang/LLD:** La compilación genera y verifica `.ll`, produce `.obj` y
  enlaza un ejecutable nativo para los destinos de sistema. Con `System "baremetal"`
  genera objetos ELF `.o`, un linker script y un binario plano `.bin`. El perfil
  `Boot "multiboot2"` añade la ISO `.iso`; requiere `grub-mkrescue` y
  `xorriso` en `PATH` o instalados dentro de WSL. `Boot "none"` deja la
  imagen plana sin empaquetarla.
* **Android NDK (opcional):** Solo es necesario para destinos Android. Define
  `ANDROID_NDK_HOME` o `ANDROID_NDK_ROOT` apuntando al NDK instalado; Bagron
  resuelve automáticamente `clang`, `ld.lld` y el sysroot de la API indicada
  por el triple.

---

## Herramientas del ecosistema

Bagron se apoya principalmente en dos herramientas:

* **[Gram](https://github.com/GrandKenzy/Gram):** motor de parseo del frontend y fuente de las reglas gramaticales del lenguaje. Se instala con vnma.
* **[vnma](https://github.com/GrandKenzy/vnma):** gestor de dependencias y empaquetado para proyectos Python. Descarga y prepara las dependencias dentro del proyecto, con rutas aisladas y soporte para binarios nativos.
  * Instala desde PyPI, rutas locales (monorepos) y repositorios Git.
  * Genera un `vnma.lock` determinista con versiones, orígenes y metadatos binarios para compilaciones reproducibles.
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

Desde una instalación existente puedes actualizar a la última versión estable
publicada en GitHub con:

```powershell
bagron --update
```

La actualización descarga el instalador de la plataforma, conserva la carpeta
de destino y reemplaza solo los componentes administrados por Bagron. Para
desinstalar limpiamente la instalación y retirar sus lanzadores usa:

```powershell
bagron --uninstall
```

Desde la versión publicada puedes descargar el instalador compilado
`Bagron-1.1.6-Setup.exe` y ejecutarlo directamente. La versión publicada solo incluye
este instalador ejecutable; las fuentes permanecen disponibles en GitHub.

El instalador compilado incluye un entorno portable de Python 3.14 con
`vnma`, Gram, `llvmlite` y el parser AOT ya preparados. Los extrae en
`.runtime/` y `vendor/` sin ejecutar `pip`, descargar Gram o reconstruir el
parser; no necesita Python, vnma ni Gram instalados globalmente. LLVM/Clang/LLD
sigue siendo necesario para compilar programas nativos.

La ejecución directa desde una copia del repositorio (`python installer.py`)
sigue siendo una ruta de desarrollo y usa Python 3.14+ del sistema para crear
su entorno local.

### Linux

El instalador compilado para Linux incluye un entorno portable de Python 3.14 con
`vnma`, Gram, `llvmlite` y el parser AOT ya preparados. Los extrae en
`.runtime/` y `vendor/` sin red ni reconstrucción; no requiere Python, vnma ni
Gram instalados globalmente. LLVM/Clang/LLD sigue siendo necesario para
compilar programas; los proyectos que usen `net` con HTTPS necesitan
`libcurl.so.4`. Puedes instalarlo desde la versión publicada:

```bash
curl -fsSL https://raw.githubusercontent.com/GrandKenzy/Bagron/1.1.6/install.sh | bash
```

Desde la versión publicada puedes descargar el instalador compilado
`Bagron-1.1.6-linux-x86_64`, darle permisos de ejecución y ejecutarlo:

```bash
chmod +x Bagron-1.1.6-linux-x86_64
./Bagron-1.1.6-linux-x86_64
```

La versión publicada incluye este ejecutable para Linux. El instalador coloca el
lanzador `bagron` en `~/.local/bin`; si esa carpeta no está en el
PATH, añádela en el perfil de tu shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Para desinstalar una instalación Linux usando el Python incluido:

```bash
"$HOME/Bagron/.runtime/bin/python" "$HOME/Bagron/installer.py" --uninstall
```

También puedes actualizar desde el lanzador instalado:

```bash
bagron --update
```

## Instaladores preconstruidos

Los instaladores de la versión 1.1.6 incorporan los componentes preparados
por GitHub Actions para cada plataforma: fuentes del compilador, Python 3.14
portable, `vnma`, las dependencias locales (Gram y `llvmlite`) y la biblioteca
Gram AOT junto con su manifiesto. Su instalación no necesitará descargar
Gram ni ejecutar `vnma install` o reconstruir el parser; el instalador
comprobará el bundle antes de crear los lanzadores. La ruta de instalación
desde fuentes seguirá disponible para desarrolladores.

La instalación crea `libs/` como directorio estable, pero lo deja vacío: los
paquetes BagronLab ya no se distribuyen por defecto. `bagron package install`
instala por defecto en `BAGRON_ROOT/libs`; usa `--select <ruta>` para elegir
otro destino. También puedes proporcionar tus propios archivos `.lib` locales.

`bagron package install` conserva una librería ya instalada. Usa
`bagron package update Nombre` para reemplazarla desde Central,
`bagron package pull ruta/a/lib.lib` para importar un artefacto local,
`bagron package list` para consultar las librerías instaladas y
`bagron package uninstall Nombre` para retirarlas. Todos usan
`BAGRON_ROOT/libs` por defecto; `--select <ruta>` permite administrar otro
directorio.

El empaquetado omite alias duplicados del entorno de ejecución: Linux reconstruye
los enlaces simbólicos relativos de Python y sus bibliotecas, mientras que Windows
crea enlaces físicos cuando el sistema de archivos lo admite (o conserva
copias independientes como alternativa). Se verifican las rutas del manifiesto
antes de restaurarlas; esto no modifica el Python global del usuario.

**Importante:** instalar sin Internet no equivale a compilar sin herramientas
externas. Para generar y enlazar ejecutables nativos siguen siendo necesarias
las herramientas LLVM/Clang/LLD correspondientes; Android necesita su NDK.
Las versiones anteriores a 1.1.4 conservan el mecanismo anterior.

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

Este proyecto se distribuye bajo la Licencia Apache 2.0 y las condiciones
adicionales de no derivados y uso comercial indicadas en `LICENSE`.
Consulta el archivo `LICENSE` para más detalles.

<p align="center">
  <img src="badge/footer.jpeg" alt="Bagron, a Discentra Community project" />
</p>

