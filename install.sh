#!/usr/bin/env bash
set -euo pipefail

# Bootstrap POSIX: el instalador ELF contiene su propio Python portable.
# Desde una copia del repositorio se conserva la ruta de desarrollo con Python
# del sistema; desde GitHub se descarga directamente el ejecutable compilado.
script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$script_dir/installer.py" ]]; then
    local_python="$script_dir/.runtime/bin/python"
    if [[ -x "$local_python" ]]; then
        exec "$local_python" "$script_dir/installer.py" --local "$@"
    fi
    if command -v python3 >/dev/null 2>&1; then
        exec python3 "$script_dir/installer.py" --local "$@"
    fi
fi

version="${BAGRON_VERSION:-1.0.3}"
installer_url="${BAGRON_INSTALLER_URL:-https://github.com/GrandKenzy/Bagron/releases/download/${version}/Bagron-${version}-linux-x86_64}"
temporary_dir="$(mktemp -d)"
trap 'rm -rf "$temporary_dir"' EXIT
installer_path="$temporary_dir/Bagron-${version}-linux-x86_64"

if command -v curl >/dev/null 2>&1; then
    curl --fail --location --silent --show-error "$installer_url" --output "$installer_path"
elif command -v wget >/dev/null 2>&1; then
    wget --quiet --output-document="$installer_path" "$installer_url"
else
    printf '%s\n' 'Error: se necesita curl o wget para descargar el instalador portable.' >&2
    exit 1
fi

chmod +x "$installer_path"
exec "$installer_path" "$@"
