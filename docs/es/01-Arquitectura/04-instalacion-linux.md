# Instalación de Bagron en Linux

La distribución Linux de Bagron se entrega como un instalador ELF compilado.
El instalador coloca los lanzadores POSIX en la instalación del usuario y la
release no publica paquetes fuente comprimidos.

## Requisitos

- LLVM, Clang y LLD disponibles en el PATH.
- `libcurl.so.4` si el proyecto usa el módulo `net` con `https://`.

El instalador ELF incluye un runtime portable de Python con `pip`, por lo que
no necesita Python instalado globalmente. La ejecución de `installer.py` desde
una copia del repositorio sí usa un Python local compatible como herramienta de
desarrollo.

En Debian o Ubuntu, las herramientas base pueden instalarse con:

```bash
sudo apt update
sudo apt install clang lld libcurl4
```

## Instalación desde Internet

```bash
curl -fsSL https://raw.githubusercontent.com/GrandKenzy/Bagron/1.1.6/install.sh | bash
```

El comando descarga el instalador ELF, que instala Bagron en `~/Bagron` y
extrae el runtime Python, vnma, Gram, llvmlite y el parser AOT ya preparados.
La instalación no ejecuta pip, descarga Gram ni reconstruye el parser.

Aunque se ejecute desde una carpeta que contenga otra copia de Bagron, el
script descargado por `curl | bash` no reutiliza ese checkout ni el Python del
sistema: siempre descarga el instalador ELF portable.

El modo de desarrollo desde un checkout es opt-in:

```bash
BAGRON_LOCAL_INSTALL=1 ./install.sh
```

- `~/.local/bin/bagron`
- `~/.local/bin/Bagron`

Si `~/.local/bin` no está en el PATH de la sesión actual:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Para comprobar la instalación:

```bash
cd "$HOME/Bagron"
bagron --help
bagron --execute examples/01_basico.bg -o build/ejemplo
```

## Instalación desde el ejecutable compilado

Descarga `Bagron-1.1.6-linux-x86_64` desde el release, hazlo ejecutable y
ejecútalo:

```bash
chmod +x Bagron-1.1.6-linux-x86_64
./Bagron-1.1.6-linux-x86_64
```

La instalación crea `~/Bagron/libs/` vacía. Instala las dependencias del
proyecto explícitamente con `bagron package install` o aporta archivos `.lib`
locales.

Para desinstalar usando el Python portable incluido:

```bash
"$HOME/Bagron/.runtime/bin/python" "$HOME/Bagron/installer.py" --uninstall
```

Una instalación existente puede actualizarse a la última release estable de
GitHub con el lanzador instalado:

```bash
bagron --update
```
