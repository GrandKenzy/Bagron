# Instalación de Bagron en Linux

La distribución Linux de Bagron se entrega como un paquete fuente reproducible
que instala sus dependencias mediante `vnma` y genera lanzadores POSIX.

## Requisitos

- Python 3.14 o superior.
- `vnma`, instalable con `python3 -m pip install vnma`.
- LLVM, Clang y LLD disponibles en el PATH.
- `libcurl.so.4` si el proyecto usa el módulo `net` con `https://`.

En Debian o Ubuntu, las herramientas base pueden instalarse con:

```bash
sudo apt update
sudo apt install python3 python3-pip clang lld libcurl4
python3 -m pip install vnma
```

## Instalación desde Internet

```bash
curl -fsSL https://raw.githubusercontent.com/GrandKenzy/Bagron/1.0.3/install.sh | bash
```

El comando instala Bagron en `~/Bagron`, resuelve Gram y llvmlite, y crea:

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

## Instalación desde el paquete

Descarga `Bagron-1.0.3-linux-x86_64.tar.gz` desde el release, extráelo y
ejecuta:

```bash
tar -xzf Bagron-1.0.3-linux-x86_64.tar.gz
cd Bagron-1.0.3
./install.sh
```

Para desinstalar:

```bash
python3 "$HOME/Bagron/installer.py" --uninstall
```
