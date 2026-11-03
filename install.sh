#!/usr/bin/env bash
set -euo pipefail

# Instalador POSIX: puede ejecutarse desde un paquete extraído o directamente
# desde GitHub sin exigir que el usuario clone el repositorio.
script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Error: se requiere python3 para instalar Bagron.' >&2
    exit 1
fi

if [[ -f "$script_dir/installer.py" ]]; then
    exec python3 "$script_dir/installer.py" --local "$@"
fi

version="${BAGRON_VERSION:-1.0.3}"
installer_url="${BAGRON_INSTALLER_URL:-https://raw.githubusercontent.com/GrandKenzy/Bagron/${version}/installer.py}"
temporary_dir="$(mktemp -d)"
trap 'rm -rf "$temporary_dir"' EXIT
installer_path="$temporary_dir/installer.py"

if command -v curl >/dev/null 2>&1; then
    curl --fail --location --silent --show-error "$installer_url" --output "$installer_path"
elif command -v wget >/dev/null 2>&1; then
    wget --quiet --output-document="$installer_path" "$installer_url"
else
    python3 - "$installer_url" "$installer_path" <<'PY'
import pathlib
import sys
import urllib.request

urllib.request.urlretrieve(sys.argv[1], pathlib.Path(sys.argv[2]))
PY
fi

exec python3 "$installer_path" "$@"
