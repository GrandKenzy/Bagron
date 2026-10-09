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

    def set_source_dir(self, path: Path | str):
        self.source_dir = Path(path).resolve()

    def clear(self):
        self.namespaces.clear()
        self.namespace_headers.clear()

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
        if extern_file:
            bs = load_cached_symbols(extern_file)
            if bs is None:
                bs = parse_externs(extern_file)
                save_cached_symbols(extern_file, bs)
            symbols.update(bs)

        if extends_file:
            es = parse_externs(extends_file)
            symbols.update(es)

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
                symbols = load_cached_symbols(egl_file)
                if symbols is None:
                    symbols = parse_externs(egl_file)
                    save_cached_symbols(egl_file, symbols)
                clean_name = egl_file.stem
                if clean_name.endswith('.externs'):
                    clean_name = clean_name[:-8]
                self.namespaces[clean_name] = symbols
                self.namespace_headers[clean_name] = f'{clean_name}.h'
                if symbol_name in symbols:
                    return symbols[symbol_name], f'{clean_name}.h'
        return None

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
