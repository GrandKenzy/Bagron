from pathlib import Path
from typing import Any
from core.externs.cache import load_cached_symbols, save_cached_symbols
from core.externs.parser import parse_externs

class ExternsManager:
    def __init__(self):
        self.active_target = 'egl-c'
        self.namespaces: dict[str, dict[str, dict]] = {}
        self.namespace_headers: dict[str, str] = {}
        self.base_dir = Path(__file__).resolve().parent.parent
        self.source_dir: Path | None = None
        self.link_flags: list[str] = []
        self.bin_files: list[str] = []
        self.lib_dirs: list[Path] = []
        self.include_dirs: list[Path] = []

    def set_source_dir(self, path: Path | str):
        self.source_dir = Path(path).resolve()

    def clear(self):
        self.namespaces.clear()
        self.namespace_headers.clear()
        self.link_flags.clear()
        self.bin_files.clear()
        self.lib_dirs.clear()
        self.include_dirs.clear()

    def _merge_meta(self, target_meta: dict, new_meta: dict, base_dir: Path):
        if new_meta.get('header'):
            target_meta['header'] = new_meta['header']
        for lk in new_meta.get('links', []):
            if lk not in target_meta.get('links', []):
                target_meta.setdefault('links', []).append(lk)
            if lk not in self.link_flags:
                self.link_flags.append(lk)
        for bn in new_meta.get('bins', []):
            if bn not in target_meta.get('bins', []):
                target_meta.setdefault('bins', []).append(bn)
            if bn not in self.bin_files:
                self.bin_files.append(bn)
        for ld in new_meta.get('lib_dirs', []):
            p = (base_dir / ld).resolve() if not Path(ld).is_absolute() else Path(ld).resolve()
            if p not in self.lib_dirs:
                self.lib_dirs.append(p)
        for idir in new_meta.get('include_dirs', []):
            p = (base_dir / idir).resolve() if not Path(idir).is_absolute() else Path(idir).resolve()
            if p not in self.include_dirs:
                self.include_dirs.append(p)

    def set_target(self, target: str):
        self.active_target = str(target).strip('"\'')

    def get_backend_name(self) -> str:
        target = self.active_target.lower()
        if target.startswith('egl-'):
            return target[4:]
        return target

    def normalize_header(self, header: str) -> str:
        clean = str(header).strip('"\'< >')
        if clean.endswith('.h'):
            clean = clean[:-2]
        return clean

    def find_extern_file(self, header: str) -> Path | None:
        backend = self.get_backend_name()
        clean = self.normalize_header(header)
        candidate = self.base_dir / 'backend' / backend / 'externs' / f'{clean}.externs.egl'
        if candidate.is_file():
            return candidate
        alt_candidate = Path.cwd() / 'core' / 'backend' / backend / 'externs' / f'{clean}.externs.egl'
        if alt_candidate.is_file():
            return alt_candidate
        return None

    def find_extends_file(self, header: str) -> Path | None:
        backend = self.get_backend_name()
        clean = self.normalize_header(header)
        candidates = []
        if self.source_dir:
            candidates.append(self.source_dir / 'targets' / backend / 'extends' / f'{clean}.externs.egl')
            candidates.append(self.source_dir.parent / 'targets' / backend / 'extends' / f'{clean}.externs.egl')
        candidates.append(Path.cwd() / 'source' / 'targets' / backend / 'extends' / f'{clean}.externs.egl')
        for c in candidates:
            if c.is_file():
                return c
        return None

    def load_include(self, header: str, alias: str | None = None) -> dict[str, dict]:
        clean_header = self.normalize_header(header)
        c_header = f'{clean_header}.h'
        backend = self.get_backend_name()
        extern_file = self.find_extern_file(clean_header)
        extends_file = self.find_extends_file(clean_header)

        if not extern_file and not extends_file:
            raise RuntimeError(f"Librería externa '{clean_header}' no encontrada en backend/{backend}/externs ni extends.")

        symbols: dict[str, dict] = {}
        meta: dict[str, Any] = {'header': None, 'links': [], 'bins': [], 'lib_dirs': [], 'include_dirs': []}
        if extern_file:
            cached = load_cached_symbols(extern_file)
            if cached is None:
                bs, b_meta = parse_externs(extern_file)
                save_cached_symbols(extern_file, bs, b_meta)
            else:
                bs, b_meta = cached
            symbols.update(bs)
            self._merge_meta(meta, b_meta, extern_file.parent)

        if extends_file:
            es, e_meta = parse_externs(extends_file)
            symbols.update(es)
            self._merge_meta(meta, e_meta, extends_file.parent)

        if meta.get('header'):
            c_header = meta['header']

        import core.backend.c as c_backend
        c_backend.add_include(c_header)

        if alias:
            self.namespaces[alias] = symbols
            self.namespace_headers[alias] = c_header

        return symbols

    def has_namespace(self, ns_name: str) -> bool:
        return ns_name in self.namespaces

    def get_namespace(self, ns_name: str) -> dict[str, dict] | None:
        return self.namespaces.get(ns_name)

    def has_symbol(self, ns_name: str, symbol: str) -> bool:
        ns = self.namespaces.get(ns_name)
        if ns is None:
            return False
        return symbol in ns

    def get_symbol(self, ns_name: str, symbol: str) -> dict | None:
        ns = self.namespaces.get(ns_name)
        if ns is None:
            return None
        return ns.get(symbol)

    def get_header_for_namespace(self, ns_name: str) -> str | None:
        return self.namespace_headers.get(ns_name)

    def find_backend_symbol(self, symbol_name: str) -> tuple[dict, str] | None:
        for ns_name, syms in self.namespaces.items():
            if symbol_name in syms:
                return syms[symbol_name], self.namespace_headers.get(ns_name, '')

        backend = self.get_backend_name()
        externs_dir = self.base_dir / 'backend' / backend / 'externs'
        if not externs_dir.is_dir():
            externs_dir = Path.cwd() / 'core' / 'backend' / backend / 'externs'
        if externs_dir.is_dir():
            for egl_file in externs_dir.glob('*.externs.egl'):
                cached = load_cached_symbols(egl_file)
                if cached is None:
                    symbols, meta = parse_externs(egl_file)
                    save_cached_symbols(egl_file, symbols, meta)
                else:
                    symbols, meta = cached
                self._merge_meta({}, meta, egl_file.parent)
                clean_name = egl_file.stem
                if clean_name.endswith('.externs'):
                    clean_name = clean_name[:-8]
                h_name = meta.get('header') or f'{clean_name}.h'
                self.namespaces[clean_name] = symbols
                self.namespace_headers[clean_name] = h_name
                if symbol_name in symbols:
                    return symbols[symbol_name], h_name
        return None

    def collect_target_conventions(self) -> dict[str, Any]:
        backend = self.get_backend_name()
        res = {
            'include_dirs': list(self.include_dirs),
            'lib_dirs': list(self.lib_dirs),
            'link_flags': list(self.link_flags),
            'bin_files': list(self.bin_files),
        }
        search_dirs = []
        if self.source_dir:
            search_dirs.append(self.source_dir)
            search_dirs.append(self.source_dir / 'targets' / backend)
            search_dirs.append(self.source_dir.parent / 'targets' / backend)
        search_dirs.append(Path.cwd() / 'source' / 'targets' / backend)
        search_dirs.append(Path.cwd() / 'targets' / backend)
        search_dirs.append(Path.cwd() / 'libs')

        for base in search_dirs:
            if not base.exists():
                continue
            inc = base / 'include' if (base / 'include').is_dir() else (base if base.name == 'include' else None)
            if inc and inc.is_dir() and inc.resolve() not in res['include_dirs']:
                res['include_dirs'].append(inc.resolve())

            lib = base / 'lib' if (base / 'lib').is_dir() else (base if base.name == 'lib' else None)
            if lib and lib.is_dir() and lib.resolve() not in res['lib_dirs']:
                res['lib_dirs'].append(lib.resolve())

            bin_dir = base / 'bin' if (base / 'bin').is_dir() else (base if base.name == 'bin' else None)
            if bin_dir and bin_dir.is_dir():
                for f in bin_dir.glob('*'):
                    if f.suffix.lower() in ('.dll', '.so', '.dylib') and str(f.resolve()) not in res['bin_files']:
                        res['bin_files'].append(str(f.resolve()))

        return res

    def bind_args(self, sym_info: dict, call_args: list, call_kwargs: dict | None = None) -> dict[str, Any]:
        call_kwargs = dict(call_kwargs or {})
        params = sym_info.get('params', [])
        result = {}
        for idx, p in enumerate(params):
            p_name = p['name']
            if idx < len(call_args):
                result[p_name] = call_args[idx]
            elif p_name in call_kwargs:
                result[p_name] = call_kwargs.pop(p_name)
            elif p.get('has_default'):
                result[p_name] = p.get('default')
            else:
                result[p_name] = None
        for k, v in call_kwargs.items():
            result[k] = v
        return result

    def validate_call(self, ns_name: str, symbol: str, args: list, kwargs: dict | None = None) -> dict:
        if ns_name not in self.namespaces:
            raise RuntimeError(f"Namespace '{ns_name}' no ha sido incluido o registrado")
        ns = self.namespaces[ns_name]
        if symbol not in ns:
            raise RuntimeError(f"El símbolo '{symbol}' no existe en la librería/namespace '{ns_name}'")
        sym_info = ns[symbol]
        params = sym_info.get('params', [])
        required = [p for p in params if not p.get('has_default')]
        kwargs = kwargs or {}
        total_given = len(args) + len(kwargs)
        if total_given < len(required):
            raise RuntimeError(f"Llamada a '{ns_name}.{symbol}' requiere al menos {len(required)} argumentos, pero recibió {total_given}")
        if total_given > len(params):
            raise RuntimeError(f"Llamada a '{ns_name}.{symbol}' recibe máximo {len(params)} argumentos, pero recibió {total_given}")
        return sym_info

manager = ExternsManager()

__all__ = ['ExternsManager', 'manager']
