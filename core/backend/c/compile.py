from pathlib import Path
import shutil
import subprocess
import sys

SUPPORTED_COMPILERS: tuple[str, ...] = ('gcc', 'clang', 'cl', 'msvc', 'tcc')
DEFAULT_COMPILER: str = 'gcc'

CLI_COMPILER_PARAMS: dict[str, str] = {
    'compiler': 'Compilador C a utilizar (gcc, clang, cl, msvc, tcc)',
    'include_dirs': 'Lista de rutas de cabeceras C (-I)',
    'lib_dirs': 'Lista de rutas de bibliotecas C (-L)',
    'link_libraries': 'Lista de bibliotecas a enlazar (-l)',
    'bin_files': 'Lista de binarios dinámicos a desplegar junto al ejecutable',
    'extra_flags': 'Flags adicionales para el compilador',
}

def detect_available_compiler() -> str:
    for candidate in ('gcc', 'clang', 'cl', 'tcc'):
        if shutil.which(candidate):
            return candidate
    from core.backend.c.download import find_portable_gcc
    portable = find_portable_gcc()
    if portable:
        return str(portable)
    return DEFAULT_COMPILER

def _deploy_bin_files(bin_files: list[Path | str], dest_dir: Path, search_folders: list[Path]) -> None:
    copied: set[str] = set()
    for bin_item in bin_files:
        bin_path = Path(bin_item)
        if not bin_path.is_file():
            found = None
            for sf in search_folders:
                c1 = sf / bin_path.name
                if c1.is_file():
                    found = c1
                    break
                c2 = sf.parent / 'bin' / bin_path.name
                if c2.is_file():
                    found = c2
                    break
            if found:
                bin_path = found
        if bin_path.is_file():
            dest_file = dest_dir / bin_path.name
            if dest_file.name not in copied:
                copied.add(dest_file.name)
                if bin_path.resolve() != dest_file.resolve():
                    shutil.copy2(bin_path, dest_file)
                    print(f"[Backend C] Binario desplegado: '{bin_path.name}' -> '{dest_dir.name}'", flush=True)

def compile(
    source_file: Path | str,
    output_file: Path | str | None = None,
    compiler: str | None = None,
    include_dirs: list[Path | str] | None = None,
    lib_dirs: list[Path | str] | None = None,
    link_libraries: list[str] | None = None,
    bin_files: list[Path | str] | None = None,
    extra_flags: list[str] | None = None,
    verbose: bool = False
) -> tuple[int, Path]:
    src_path = Path(source_file).resolve()
    if output_file:
        exe_path = Path(output_file).resolve()
    else:
        exe_suffix = '.exe' if sys.platform == 'win32' else ''
        exe_path = src_path.with_suffix(exe_suffix)

    active_compiler = compiler or detect_available_compiler()
    resolved_compiler_bin = shutil.which(active_compiler)
    if not resolved_compiler_bin:
        from core.backend.c.download import find_portable_gcc
        portable = find_portable_gcc()
        if portable and active_compiler in ('gcc', 'mingw'):
            resolved_compiler_bin = str(portable)
        else:
            resolved_compiler_bin = active_compiler
    compiler_lower = Path(str(active_compiler)).stem.lower()

    inc_list = [Path(p).resolve() for p in (include_dirs or [])]
    lib_list = [Path(p).resolve() for p in (lib_dirs or [])]
    links = list(link_libraries or [])
    flags = list(extra_flags or [])

    is_msvc = compiler_lower in ('cl', 'cl.exe', 'msvc')

    if is_msvc:
        cmd = [resolved_compiler_bin, '/nologo', str(src_path), f'/Fe:{exe_path}']
        for inc in inc_list:
            cmd.append(f'/I{inc}')
        cmd.append('/link')
        for ld in lib_list:
            cmd.append(f'/LIBPATH:{ld}')
        for lk in links:
            lk_str = str(lk)
            if lk_str.startswith('-l'):
                lk_str = lk_str[2:]
            if not (lk_str.endswith('.lib') or lk_str.endswith('.a')):
                lk_str = f'{lk_str}.lib'
            cmd.append(lk_str)
        cmd.extend(flags)
    else:
        cmd = [resolved_compiler_bin, str(src_path), '-o', str(exe_path)]
        for inc in inc_list:
            cmd.extend(['-I', str(inc)])
        for ld in lib_list:
            cmd.extend(['-L', str(ld)])
        for lk in links:
            flag = lk if lk.startswith('-l') else f'-l{lk}'
            cmd.append(flag)
        cmd.extend(flags)

    print(f"[Backend C] Compilando con {active_compiler}: '{exe_path.name}'...", flush=True)
    if verbose:
        print(f"[Backend C] Comando: {' '.join(cmd)}", flush=True)

    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"[Backend C] Error en la compilación con {active_compiler} (código de salida {res.returncode}).", flush=True)
        return res.returncode, exe_path

    if bin_files:
        search_dirs = inc_list + lib_list
        _deploy_bin_files(bin_files, exe_path.parent, search_dirs)

    return 0, exe_path
