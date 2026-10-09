import os
import re
import sys
import platform
from pathlib import Path
from typing import Any
import gram
import core
import core.grammar
from core.processor import objects
from core.externs.manager import manager
from core.backend import c

def get_default_arch() -> str:
    m = platform.machine().lower()
    if m in ('amd64', 'x86_64', 'x64'):
        return 'amd64'
    if m in ('arm64', 'aarch64'):
        return 'arm64'
    if m in ('i386', 'i686', 'x86'):
        return 'x86'
    return m

def get_default_system() -> str:
    s = platform.system().lower()
    if s == 'windows':
        return 'win'
    if s == 'linux':
        return 'linux'
    if s == 'darwin':
        return 'darwin'
    return s

def resolve_source_and_main(source_path: str | Path) -> tuple[Path, Path]:
    p = Path(source_path).resolve()
    if p.is_file() and p.name == 'main.egl':
        return p.parent, p
    if p.is_file():
        return p.parent, p
    main_candidate = p / 'main.egl'
    if main_candidate.is_file():
        return p, main_candidate
    nested_source = p / 'source' / 'main.egl'
    if nested_source.is_file():
        return p / 'source', nested_source
    raise FileNotFoundError(f"No se encontró 'main.egl' en la ruta especificada: {source_path}")

def find_module_file(mod_name: str, source_dir: Path, target: str) -> Path | None:
    clean_mod = mod_name.strip('"\'')
    if clean_mod.endswith('.egl'):
        clean_mod = clean_mod[:-4]
    backend = target[4:].lower() if target.lower().startswith('egl-') else target.lower()
    base_core_dir = Path(__file__).resolve().parent

    candidates = [
        source_dir / 'modules' / f'{clean_mod}.egl',
        source_dir / f'{clean_mod}.egl',
        source_dir / 'targets' / backend / 'libraries' / f'{clean_mod}.egl',
        source_dir.parent / 'targets' / backend / 'libraries' / f'{clean_mod}.egl',
        base_core_dir / 'backend' / backend / 'libraries' / f'{clean_mod}.egl',
        Path.cwd() / 'core' / 'backend' / backend / 'libraries' / f'{clean_mod}.egl',
        Path.cwd() / 'source' / 'targets' / backend / 'libraries' / f'{clean_mod}.egl',
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None

def extract_clauses(ast: gram.ASTProgram) -> dict[str, str]:
    clauses = {}
    for node in ast.walk(0):
        if node.name in ('EGL_CLAUSE', 'clause') and len(node.values) >= 3:
            key = str(node.values[1].value if hasattr(node.values[1], 'value') else node.values[1]).strip()
            val = str(node.values[2].value if hasattr(node.values[2], 'value') else node.values[2]).strip('"\'')
            clauses[key] = val
    return clauses

def apply_default_clauses(clauses: dict[str, str]) -> dict[str, str]:
    if 'Target' not in clauses:
        raise ValueError("La cláusula 'Target' es obligatoria en main.egl (ejemplo: clause Target 'egl-c').")
    if 'Arch' not in clauses:
        clauses['Arch'] = get_default_arch()
    if 'System' not in clauses:
        clauses['System'] = get_default_system()
    if 'Visibility' not in clauses:
        clauses['Visibility'] = 'public'
    if 'StackLimit' not in clauses:
        clauses['StackLimit'] = '16384'
    return clauses

def scan_module_imports(ast: gram.ASTProgram) -> list[tuple[str, str | None]]:
    imports = []
    for node in ast.walk(0):
        if node.name in ('EGL_IMPORT', 'import'):
            vals = [str(v.value if hasattr(v, 'value') else v).strip('"\'') for v in node.values]
            if 'import' in vals:
                vals.remove('import')
            if not vals:
                continue
            mod_name = vals[0]
            alias = None
            if 'as' in vals:
                as_idx = vals.index('as')
                if as_idx + 1 < len(vals):
                    alias = vals[as_idx + 1]
            imports.append((mod_name, alias))
    return imports

def mangle_module_symbols(mod_ast: gram.ASTProgram, mod_name: str) -> dict[str, str]:
    symbol_map = {}
    for node in mod_ast.walk():
        if node.name in ('EGL_FUNC_DECL', 'func declaration'):
            for t in getattr(node, 'tokens', []):
                val_s = str(t.value)
                if getattr(t, 'token', None) == gram.Token.IDENT or (isinstance(t.value, str) and val_s not in ('public', 'private', '__inline__', 'void', 'int', 'int8', 'int16', 'int32', 'int64', 'uint', 'uint8', 'uint16', 'uint32', 'uint64', 'float', 'double', 'char', 'bool', 'str', 'ptr')):
                    orig = val_s
                    mangled = f'inmodule_{mod_name}_{orig}'
                    symbol_map[orig] = mangled
                    t.value = mangled
                    break
        elif node.name in ('EGL_CLASS_DECL', 'class declaration'):
            for t in getattr(node, 'tokens', []):
                val_s = str(t.value)
                if getattr(t, 'token', None) == gram.Token.IDENT or (isinstance(t.value, str) and val_s not in ('public', 'private', 'class')):
                    orig = val_s
                    mangled = f'inmodule_{mod_name}_{orig}'
                    symbol_map[orig] = mangled
                    t.value = mangled
                    break
    return symbol_map

def rewrite_mangled_calls(ast: gram.ASTProgram, mangled_map: dict[str, str], module_aliases: dict[str, str]):
    for node in ast.walk():
        if node.name in ('EGL_CALL', 'call') and getattr(node, 'tokens', None):
            for t in node.tokens:
                name_str = str(t.value)
                if name_str in mangled_map:
                    t.value = mangled_map[name_str]
                    break
        elif node.name in ('EGL_METHOD_CALL', 'method call') and len(getattr(node, 'tokens', [])) >= 3:
            target = str(node.tokens[0].value)
            method = str(node.tokens[2].value)
            actual_mod = module_aliases.get(target, target)
            qualified_key = f'{actual_mod}.{method}'
            if qualified_key in mangled_map:
                new_func = mangled_map[qualified_key]
                node.name = 'EGL_CALL'
                tok = node.tokens[0]
                tok.value = new_func
                node.tokens = [tok]

def compile_project(
    source_path: str | Path,
    output_file: str | Path = 'program.c',
    entrypoint_func: str | None = None
) -> Path:
    source_dir, main_file = resolve_source_and_main(source_path)
    manager.set_source_dir(source_dir)
    manager.clear()
    objects.clear()
    c.clear()

    main_source = main_file.read_text(encoding='utf-8')
    main_ast = gram.process(core.grammar.grammar, source_or_file=main_source)

    clauses = extract_clauses(main_ast)
    clauses = apply_default_clauses(clauses)
    target = clauses['Target']
    manager.set_target(target)

    loaded_modules: set[str] = set()
    all_mangled_symbols: dict[str, str] = {}
    module_aliases: dict[str, str] = {}
    pending_imports = scan_module_imports(main_ast)

    module_asts: list[tuple[str, gram.ASTProgram]] = []

    while pending_imports:
        mod_name, alias = pending_imports.pop(0)
        if alias:
            module_aliases[alias] = mod_name
        module_aliases[mod_name] = mod_name
        if mod_name in loaded_modules:
            continue
        loaded_modules.add(mod_name)

        mod_file = find_module_file(mod_name, source_dir, target)
        if not mod_file:
            backend = target[4:].lower() if target.lower().startswith('egl-') else target.lower()
            raise FileNotFoundError(f"No se encontró el módulo o librería '{mod_name}' en 'source/modules/{mod_name}.egl' ni en las librerías del target '{backend}'.")

        mod_code = mod_file.read_text(encoding='utf-8')
        mod_ast = gram.process(core.grammar.grammar, source_or_file=mod_code)

        mod_clauses = extract_clauses(mod_ast)
        if 'Target' in mod_clauses and mod_clauses['Target'] != target:
            raise ValueError(f"El módulo '{mod_name}' tiene un Target ('{mod_clauses['Target']}') diferente al Target principal ('{target}').")

        mod_symbols = mangle_module_symbols(mod_ast, mod_name)
        for s_name, m_name in mod_symbols.items():
            all_mangled_symbols[s_name] = m_name
            all_mangled_symbols[f'{mod_name}.{s_name}'] = m_name
            if alias:
                all_mangled_symbols[f'{alias}.{s_name}'] = m_name

        more_imports = scan_module_imports(mod_ast)
        for mi in more_imports:
            if mi[0] not in loaded_modules:
                pending_imports.append(mi)

        module_asts.append((mod_name, mod_ast))

    for mod_name, mod_ast in module_asts:
        rewrite_mangled_calls(mod_ast, all_mangled_symbols, module_aliases)
    rewrite_mangled_calls(main_ast, all_mangled_symbols, module_aliases)

    for mod_name, mod_ast in module_asts:
        core.processor.process(mod_ast)
    core.processor.process(main_ast)

    c.process(objects.get_items())

    all_items = list(objects.get_items().keys())

    user_defined_main = any(isinstance(it, objects.Function) and it.name == 'main' for it in all_items)

    headers = list(dict.fromkeys(c.includes))
    typedef_list = list(dict.fromkeys(getattr(c, 'typedefs', [])))

    forward_decls: list[str] = []
    func_impls: list[str] = []
    main_body_lines: list[str] = []

    for item in all_items:
        if isinstance(item, objects.Function):
            f_code = getattr(item, 'compiled', '').strip()
            if f_code:
                if item.name == 'main':
                    func_impls.append(f_code)
                else:
                    first_brace = f_code.find('{')
                    sig = f_code[:first_brace].strip() if first_brace != -1 else ''
                    if sig:
                        forward_decls.append(f'{sig};')
                    func_impls.append(f_code)
        elif isinstance(item, (objects.TypeDecl, objects.ClassDecl)):
            continue
        else:
            line = getattr(item, 'compiled', '').strip()
            if line:
                main_body_lines.append(f'    {line}')

    output_lines = []
    for h in headers:
        output_lines.append(h)
    if headers:
        output_lines.append('')

    for td in typedef_list:
        output_lines.append(td)
    if typedef_list:
        output_lines.append('')

    for fwd in forward_decls:
        output_lines.append(fwd)
    if forward_decls:
        output_lines.append('')

    for fn in func_impls:
        output_lines.append(fn)
        output_lines.append('')

    if not user_defined_main:
        output_lines.append('int main(int argc, char** argv) {')
        for b_line in main_body_lines:
            output_lines.append(b_line)
        output_lines.append('    return 0;')
        output_lines.append('}')

    final_c_code = '\n'.join(output_lines) + '\n'

    out_path = Path(output_file).resolve()
    out_path.write_text(final_c_code, encoding='utf-8')
    return out_path
