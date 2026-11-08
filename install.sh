#!/usr/bin/env bash
set -euo pipefail

# Bootstrap POSIX: el instalador ELF contiene su propio Python portable.
# Solo se conserva la ruta de desarrollo cuando este archivo se ejecuta desde
# un checkout real y el usuario la solicita explícitamente. Si llega por
# `curl | bash`, o no se define BAGRON_LOCAL_INSTALL=1, siempre debe
# descargarse el instalador portable.
script_source="${BASH_SOURCE[0]:-}"
script_dir=""
if [[ -n "$script_source" && -f "$script_source" ]]; then
    script_dir="$(CDPATH= cd -- "$(dirname -- "$script_source")" && pwd)"
fi

if [[ "${BAGRON_LOCAL_INSTALL:-0}" == "1" \
    && -n "$script_dir" \
    && -f "$script_dir/installer.py" \
    && -f "$script_dir/main.py" \
    && -d "$script_dir/core" \
    && -d "$script_dir/tools" ]]; then
    local_python="$script_dir/.runtime/bin/python"
    if [[ -x "$local_python" ]]; then
        exec "$local_python" "$script_dir/installer.py" --local "$@"
    fi
    if command -v python3 >/dev/null 2>&1; then
        exec python3 "$script_dir/installer.py" --local "$@"
    fi
fi

version="${BAGRON_VERSION:-1.1.6}"
host_system="$(uname -s 2>/dev/null || true)"
host_machine="$(uname -m 2>/dev/null || true)"
if [[ "$host_system" != "Linux" || "$host_machine" != "x86_64" && "$host_machine" != "amd64" ]]; then
    printf '%s\n' "Error: el instalador portable publicado solo admite Linux x86_64 (host detectado: ${host_system:-desconocido}/${host_machine:-desconocida})." >&2
    printf '%s\n' 'Usa BAGRON_LOCAL_INSTALL=1 desde un checkout con Python compatible o publica un artefacto para este target.' >&2
    exit 1
fi
installer_url="${BAGRON_INSTALLER_URL:-https://github.com/GrandKenzy/Bagron/releases/download/${version}/Bagron-${version}-linux-x86_64}"
temporary_dir="$(mktemp -d)"
trap 'rm -rf "$temporary_dir"' EXIT
installer_path="$temporary_dir/Bagron-${version}-linux-x86_64"

if command -v curl >/dev/null 2>&1; then
    curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error "$installer_url" --output "$installer_path"
elif command -v wget >/dev/null 2>&1; then
    wget --https-only --quiet --output-document="$installer_path" "$installer_url"
else
    printf '%s\n' 'Error: se necesita curl o wget para descargar el instalador portable.' >&2
    exit 1
fi

chmod +x "$installer_path"
exec "$installer_path" "$@"
