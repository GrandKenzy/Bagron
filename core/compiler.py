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
    if clean_mod.endswith('.lib.egl'):
        clean_mod = clean_mod[:-8]
    elif clean_mod.endswith('.egl'):
        clean_mod = clean_mod[:-4]
    backend = target[4:].lower() if target.lower().startswith('egl-') else target.lower()
    base_core_dir = Path(__file__).resolve().parent

    candidates = [
        # 1. Paquetes de librerías (.lib.egl)
        source_dir / 'libraries' / f'{clean_mod}.lib.egl',
        source_dir.parent / 'libraries' / f'{clean_mod}.lib.egl',
        source_dir / f'{clean_mod}.lib.egl',
        Path.cwd() / 'libraries' / f'{clean_mod}.lib.egl',
        Path.cwd() / f'{clean_mod}.lib.egl',
        source_dir / 'targets' / backend / 'libraries' / f'{clean_mod}.lib.egl',
        source_dir.parent / 'targets' / backend / 'libraries' / f'{clean_mod}.lib.egl',
        base_core_dir / 'backend' / backend / 'libraries' / f'{clean_mod}.lib.egl',
        Path.cwd() / 'core' / 'backend' / backend / 'libraries' / f'{clean_mod}.lib.egl',
        Path.cwd() / 'source' / 'targets' / backend / 'libraries' / f'{clean_mod}.lib.egl',

        # 2. Módulos y librerías en código fuente (.egl)
        source_dir / 'modules' / f'{clean_mod}.egl',
        source_dir / f'{clean_mod}.egl',
        source_dir / 'targets' / backend / 'libraries' / f'{clean_mod}.egl',
        source_dir.parent / 'targets' / backend / 'libraries' / f'{clean_mod}.egl',
        base_core_dir / 'backend' / backend / 'libraries' / f'{clean_mod}.egl',
        Path.cwd() / 'core' / 'backend' / backend / 'libraries' / f'{clean_mod}.egl',
        Path.cwd() / 'source' / 'targets' / backend / 'libraries' / f'{clean_mod}.egl',
    ]

    variants = [clean_mod[:-1]] if clean_mod.endswith('s') else [f'{clean_mod}s']
    for v in variants:
        candidates.extend([
            source_dir / 'libraries' / f'{v}.lib.egl',
            source_dir.parent / 'libraries' / f'{v}.lib.egl',
            Path.cwd() / 'libraries' / f'{v}.lib.egl',
            source_dir / f'{v}.lib.egl',
            Path.cwd() / f'{v}.lib.egl',
            source_dir / 'modules' / f'{v}.egl',
            source_dir / f'{v}.egl',
        ])

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
            toks = [t for t in getattr(node, 'tokens', []) if str(t.value) not in ('public', 'private', '__inline__')]
            if len(toks) >= 2:
                name_tok = toks[2] if (len(toks) > 2 and toks[1].value == '*') else toks[1]
                orig = str(name_tok.value)
                mangled = f'inmodule_{mod_name}_{orig}'
                symbol_map[orig] = mangled
                name_tok.value = mangled
        elif node.name in ('EGL_CLASS_DECL', 'class declaration'):
            toks = [t for t in getattr(node, 'tokens', []) if str(t.value) not in ('public', 'private', 'class', 'struct')]
            if toks:
                name_tok = toks[0]
                orig = str(name_tok.value)
                mangled = f'inmodule_{mod_name}_{orig}'
                symbol_map[orig] = mangled
                name_tok.value = mangled
        elif node.name in ('EGL_ENUM_DECL', 'enum declaration'):
            enum_name = None
            toks = [t for t in getattr(node, 'tokens', []) if str(t.value) not in ('public', 'private', 'enum')]
            if toks:
                name_tok = toks[0]
                orig = str(name_tok.value)
                mangled = f'inmodule_{mod_name}_{orig}'
                symbol_map[orig] = mangled
                name_tok.value = mangled
                enum_name = orig
            if enum_name:
                for item_node in node.find('EGL_ENUM_ITEM'):
                    for it in getattr(item_node, 'tokens', []):
                        val_it = str(it.value)
                        if getattr(it, 'token', None) == gram.Token.IDENT or (isinstance(it.value, str) and val_it not in ('=', ',')):
                            orig_item = val_it
                            mangled_item = f'inmodule_{mod_name}_{orig_item}'
                            symbol_map[orig_item] = mangled_item
                            symbol_map[f'{enum_name}.{orig_item}'] = mangled_item
                            it.value = mangled_item
                            break
    return symbol_map

def scan_declarations(ast: gram.ASTProgram) -> dict[str, str]:
    declarations = {}
    for node in ast.walk():
        if node.name in ('EGL_DECLARE', 'declare'):
            vals = [str(getattr(v, 'value', v)) for v in node.values if str(getattr(v, 'value', v)) != 'declare']
            if 'as' in vals:
                as_idx = vals.index('as')
                target = '.'.join(vals[:as_idx])
                alias = vals[as_idx + 1] if as_idx + 1 < len(vals) else ''
                if target and alias:
                    declarations[alias] = target
    return declarations

def rewrite_mangled_calls(
    ast: gram.ASTProgram,
    mangled_map: dict[str, str],
    module_aliases: dict[str, str],
    local_symbols: dict[str, str] | None = None,
    unqualified_map: dict[str, str] | None = None,
    symbol_origins: dict[str, list[str]] | None = None
):
    for node in ast.walk():
        if node.name in ('EGL_CALL', 'call') and getattr(node, 'tokens', None):
            for t in node.tokens:
                name_str = str(t.value)
                if local_symbols:
                    if f'{name_str}_create' in local_symbols:
                        t.value = local_symbols[f'{name_str}_create']
                        break
                    elif name_str in local_symbols:
                        t.value = local_symbols[name_str]
                        break
                if unqualified_map and name_str in unqualified_map:
                    t.value = unqualified_map[name_str]
                    break
                if unqualified_map and f'{name_str}_create' in unqualified_map:
                    t.value = unqualified_map[f'{name_str}_create']
                    break
                if symbol_origins and len(symbol_origins.get(name_str, [])) > 1:
                    origins_str = ', '.join(symbol_origins[name_str])
                    raise SyntaxError(
                        f"Símbolo ambiguo '{name_str}': está definido en múltiples módulos ({origins_str}). "
                        f"Usa una llamada cualificada (ej: '{symbol_origins[name_str][0]}.{name_str}') o 'declare' para desambiguar."
                    )
                if f'{name_str}_create' in mangled_map:
                    t.value = mangled_map[f'{name_str}_create']
                    break
                elif name_str in mangled_map:
                    t.value = mangled_map[name_str]
                    break
        elif node.name in ('EGL_METHOD_CALL', 'method call') and len(getattr(node, 'tokens', [])) >= 3:
            target = str(node.tokens[0].value)
            method = str(node.tokens[2].value)
            actual_mod = module_aliases.get(target, target)
            qualified_key = f'{actual_mod}.{method}'
            if f'{qualified_key}_create' in mangled_map:
                new_func = mangled_map[f'{qualified_key}_create']
                node.name = 'EGL_CALL'
                tok = node.tokens[0]
                tok.value = new_func
                node.tokens = [tok]
            elif qualified_key in mangled_map:
                new_func = mangled_map[qualified_key]
                node.name = 'EGL_CALL'
                tok = node.tokens[0]
                tok.value = new_func
                node.tokens = [tok]
        elif node.name in ('EGL_TYPE_SPEC', 'type spec'):
            toks_str = [str(t.value) for t in getattr(node, 'tokens', []) if str(t.value) != '*']
            full_type = ''.join(toks_str)
            matched_t = None
            if unqualified_map and full_type in unqualified_map:
                matched_t = unqualified_map[full_type]
            elif full_type in mangled_map:
                matched_t = mangled_map[full_type]

            if matched_t:
                tok = node.tokens[0]
                tok.value = matched_t
                stars = [t for t in node.tokens if str(t.value) == '*']
                node.tokens = [tok] + stars
            else:
                for t in getattr(node, 'tokens', []):
                    val_str = str(t.value)
                    if unqualified_map and val_str in unqualified_map:
                        t.value = unqualified_map[val_str]
                    elif val_str in mangled_map:
                        t.value = mangled_map[val_str]
        elif node.name in ('EGL_MEMBER_ACCESS', 'member access') and getattr(node, 'tokens', None):
            vals_str = [str(getattr(v, 'value', v)) for v in getattr(node, 'values', [])]
            joined = '.'.join(vals_str)
            target = vals_str[0] if vals_str else ''
            member = vals_str[-1] if vals_str else ''
            actual_target = module_aliases.get(target, target)
            qual = f'{actual_target}.{member}' if len(vals_str) == 2 else joined

            matched_item = None
            if joined in mangled_map:
                matched_item = mangled_map[joined]
            elif qual in mangled_map:
                matched_item = mangled_map[qual]
            elif unqualified_map and joined in unqualified_map:
                matched_item = unqualified_map[joined]
            elif unqualified_map and member in unqualified_map and (target in mangled_map or actual_target in mangled_map):
                matched_item = unqualified_map[member]

            if matched_item:
                tok = node.tokens[0]
                tok.value = matched_item
                node.tokens = [tok]
                node.children = []

def compile_project(
    source_path: str | Path,
    output_file: str | Path = 'program.c',
    entrypoint_func: str | None = None,
    is_library: bool = False
) -> Path:
    source_dir, main_file = resolve_source_and_main(source_path)
    from core.processor.type_system import clear as clear_types
    manager.set_source_dir(source_dir)
    manager.clear()
    objects.clear()
    c.clear()
    clear_types()

    main_source = main_file.read_text(encoding='utf-8')
    main_ast = gram.process(core.grammar.grammar, source_or_file=main_source)

    clauses = extract_clauses(main_ast)
    clauses = apply_default_clauses(clauses)
    target = clauses['Target']
    manager.set_target(target)

    loaded_modules: set[str] = set()
    all_mangled_symbols: dict[str, str] = {}
    unqualified_symbols: dict[str, str] = {}
    symbol_origins: dict[str, list[str]] = {}
    module_symbol_maps: dict[str, dict[str, str]] = {}
    module_aliases: dict[str, str] = {}
    imported_lib_headers: list[str] = []
    imported_lib_sources: list[str] = []
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

        if mod_file.name.endswith('.lib.egl'):
            import zipfile
            import json
            with zipfile.ZipFile(mod_file, 'r') as zf:
                manifest_data = json.loads(zf.read('manifest.json').decode('utf-8'))
                symbols_data = json.loads(zf.read('symbols.json').decode('utf-8'))
                lib_c_code = zf.read('library.c').decode('utf-8') if 'library.c' in zf.namelist() else ''
                lib_h_code = zf.read('library.h').decode('utf-8') if 'library.h' in zf.namelist() else ''

            if 'target' in manifest_data and manifest_data['target'] != target:
                raise ValueError(f"La librería '{mod_name}' tiene un Target ('{manifest_data['target']}') diferente al Target principal ('{target}').")

            conventions_links = manifest_data.get('links', [])
            for lk in conventions_links:
                if lk not in manager.link_flags:
                    manager.link_flags.append(lk)
            for bn in manifest_data.get('bin_files', []):
                if bn not in manager.bin_files:
                    manager.bin_files.append(bn)
            for inc in manifest_data.get('include_dirs', []):
                p_inc = Path(inc).resolve()
                if p_inc not in manager.include_dirs:
                    manager.include_dirs.append(p_inc)
            for ld in manifest_data.get('lib_dirs', []):
                p_ld = Path(ld).resolve()
                if p_ld not in manager.lib_dirs:
                    manager.lib_dirs.append(p_ld)

            from core.processor.type_system import register_type, CUSTOM_TYPES

            mod_symbols = {}
            for fn in symbols_data.get('functions', []):
                fn_name = fn['name']
                c_fn_name = fn.get('c_name', fn_name)
                mod_symbols[fn_name] = c_fn_name
                param_list = [{'type': p.get('type', 'any'), 'name': p.get('name', '')} for p in fn.get('parameters', [])]
                sym_info = {
                    'return_type': fn.get('return_type', 'void'),
                    'is_pointer': '*' in fn.get('return_type', ''),
                    'params': param_list
                }
                manager.register_symbol(mod_name, fn_name, sym_info)
                manager.register_symbol(mod_name, c_fn_name, sym_info)
                if alias:
                    manager.register_symbol(alias, fn_name, sym_info)
                    manager.register_symbol(alias, c_fn_name, sym_info)

            for st in symbols_data.get('structs', []):
                st_name = st['name']
                c_st_name = st.get('c_name', st_name)
                mod_symbols[st_name] = c_st_name
                mod_symbols[f'{st_name}_create'] = f'{c_st_name}_create'
                register_type(st_name, c_st_name, field_name='self')
                if st_name in CUSTOM_TYPES:
                    CUSTOM_TYPES[st_name]['is_class'] = True
                    CUSTOM_TYPES[st_name]['is_packed'] = st.get('is_packed', False)
                register_type(f'{mod_name}.{st_name}', c_st_name, field_name='self')
                if f'{mod_name}.{st_name}' in CUSTOM_TYPES:
                    CUSTOM_TYPES[f'{mod_name}.{st_name}']['is_class'] = True
                    CUSTOM_TYPES[f'{mod_name}.{st_name}']['is_packed'] = st.get('is_packed', False)
                if alias:
                    register_type(f'{alias}.{st_name}', c_st_name, field_name='self')
                    if f'{alias}.{st_name}' in CUSTOM_TYPES:
                        CUSTOM_TYPES[f'{alias}.{st_name}']['is_class'] = True
                        CUSTOM_TYPES[f'{alias}.{st_name}']['is_packed'] = st.get('is_packed', False)

            for en in symbols_data.get('enums', []):
                en_name = en['name']
                c_en_name = en.get('c_name', en_name)
                mod_symbols[en_name] = c_en_name
                members = en.get('members', {})
                if isinstance(members, list):
                    members = {m: idx for idx, m in enumerate(members)}
                for m_k, m_v in members.items():
                    mod_symbols[m_k] = m_v
                    mod_symbols[f'{en_name}.{m_k}'] = m_v

            for tp in symbols_data.get('types', []):
                tp_name = tp['name']
                c_tp_name = tp.get('c_name', tp_name)
                mod_symbols[tp_name] = c_tp_name
                register_type(tp_name, c_tp_name)

            module_symbol_maps[mod_name] = mod_symbols
            for s_name, m_name in mod_symbols.items():
                all_mangled_symbols[f'{mod_name}.{s_name}'] = m_name
                if alias:
                    all_mangled_symbols[f'{alias}.{s_name}'] = m_name
                symbol_origins.setdefault(s_name, []).append(mod_name)
                if len(symbol_origins[s_name]) == 1:
                    unqualified_symbols[s_name] = m_name
                else:
                    if s_name in unqualified_symbols:
                        del unqualified_symbols[s_name]

            if lib_h_code:
                imported_lib_headers.append(lib_h_code)
            if lib_c_code:
                imported_lib_sources.append(lib_c_code)
            continue

        mod_code = mod_file.read_text(encoding='utf-8')
        mod_ast = gram.process(core.grammar.grammar, source_or_file=mod_code)

        mod_clauses = extract_clauses(mod_ast)
        if 'Target' in mod_clauses and mod_clauses['Target'] != target:
            raise ValueError(f"El módulo '{mod_name}' tiene un Target ('{mod_clauses['Target']}') diferente al Target principal ('{target}').")

        mod_symbols = mangle_module_symbols(mod_ast, mod_name)
        module_symbol_maps[mod_name] = mod_symbols
        for s_name, m_name in mod_symbols.items():
            all_mangled_symbols[f'{mod_name}.{s_name}'] = m_name
            if alias:
                all_mangled_symbols[f'{alias}.{s_name}'] = m_name
            symbol_origins.setdefault(s_name, []).append(mod_name)
            if len(symbol_origins[s_name]) == 1:
                unqualified_symbols[s_name] = m_name
            else:
                if s_name in unqualified_symbols:
                    del unqualified_symbols[s_name]

        more_imports = scan_module_imports(mod_ast)
        for mi in more_imports:
            if mi[0] not in loaded_modules:
                pending_imports.append(mi)

        module_asts.append((mod_name, mod_ast))

    main_declarations = scan_declarations(main_ast)
    for mod_name, mod_ast in module_asts:
        main_declarations.update(scan_declarations(mod_ast))

    from core.processor.type_system import register_type, CUSTOM_TYPES
    for alias, target in main_declarations.items():
        matched_sym = None
        for sym_k, sym_v in all_mangled_symbols.items():
            if sym_k.lower() == target.lower():
                matched_sym = sym_v
                break
        if not matched_sym:
            matched_sym = all_mangled_symbols.get(target)

        if matched_sym:
            all_mangled_symbols[alias] = matched_sym
            all_mangled_symbols[f'{alias}_create'] = f'{matched_sym}_create'
            all_mangled_symbols[f'{target}_create'] = f'{matched_sym}_create'
            unqualified_symbols[alias] = matched_sym
            register_type(alias, matched_sym)
            if alias in CUSTOM_TYPES:
                CUSTOM_TYPES[alias]['c_type'] = matched_sym
                CUSTOM_TYPES[alias]['is_class'] = True
            for sym_k, sym_v in list(all_mangled_symbols.items()):
                if sym_k.startswith(f'{target}.'):
                    member_name = sym_k[len(target) + 1:]
                    all_mangled_symbols[f'{alias}.{member_name}'] = sym_v
                    if alias in CUSTOM_TYPES:
                        CUSTOM_TYPES[alias].setdefault('enum_members', {})[member_name] = sym_v
                        CUSTOM_TYPES[alias]['is_enum'] = True

    for s_name, m_name in list(unqualified_symbols.items()):
        if m_name in CUSTOM_TYPES:
            CUSTOM_TYPES[s_name] = CUSTOM_TYPES[m_name]
    for s_name, m_name in list(all_mangled_symbols.items()):
        if m_name in CUSTOM_TYPES:
            CUSTOM_TYPES[s_name] = CUSTOM_TYPES[m_name]

    for mod_name, mod_ast in module_asts:
        rewrite_mangled_calls(
            mod_ast,
            all_mangled_symbols,
            module_aliases,
            local_symbols=module_symbol_maps.get(mod_name),
            unqualified_map=unqualified_symbols,
            symbol_origins=symbol_origins
        )
    rewrite_mangled_calls(
        main_ast,
        all_mangled_symbols,
        module_aliases,
        local_symbols=None,
        unqualified_map=unqualified_symbols,
        symbol_origins=symbol_origins
    )

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
        elif isinstance(item, objects.ClassDecl):
            for fn in getattr(item, 'generated_functions', []):
                f_code = getattr(fn, 'compiled', '').strip()
                if f_code:
                    first_brace = f_code.find('{')
                    sig = f_code[:first_brace].strip() if first_brace != -1 else ''
                    if sig and f'{sig};' not in forward_decls:
                        forward_decls.append(f'{sig};')
                    if f_code not in func_impls:
                        func_impls.append(f_code)
        elif isinstance(item, (objects.TypeDecl, objects.EnumDecl)):
            continue
        else:
            code = getattr(item, 'compiled', '').strip()
            if code:
                for sub_line in code.split('\n'):
                    main_body_lines.append(f'    {sub_line}')

    if is_library:
        import zipfile
        import json

        lib_name = Path(output_file).name
        if lib_name.endswith('.lib.egl'):
            lib_name = lib_name[:-8]
        elif lib_name.endswith('.egl'):
            lib_name = lib_name[:-4]

        public_functions = []
        public_structs = []
        public_enums = []
        public_types = []

        for item in all_items:
            if isinstance(item, objects.Function):
                if getattr(item, 'privacity', 'public') == 'public' and item.name != 'main':
                    param_list = []
                    for p in getattr(item, 'parameters', []):
                        if isinstance(p, (tuple, list)):
                            param_list.append({'type': p[0], 'name': p[1]})
                        else:
                            param_list.append({'type': getattr(p, 'type', 'any'), 'name': getattr(p, 'name', '')})
                    public_functions.append({
                        'name': item.name,
                        'c_name': item.name,
                        'return_type': getattr(item, 'return_type', 'void'),
                        'parameters': param_list,
                        'is_inline': getattr(item, 'is_inline', False)
                    })
            elif isinstance(item, objects.ClassDecl):
                if getattr(item, 'privacity', 'public') == 'public':
                    public_structs.append({
                        'name': item.name,
                        'c_name': item.name,
                        'is_packed': getattr(item, 'is_packed', False),
                        'fields': getattr(item, 'fields', []),
                        'methods': [
                            {'name': m_name, 'return_type': m_obj.return_type}
                            for m_name, m_obj in getattr(item, 'methods', {}).items()
                            if getattr(m_obj, 'privacity', 'public') == 'public'
                        ]
                    })
            elif isinstance(item, objects.EnumDecl):
                if getattr(item, 'privacity', 'public') == 'public':
                    public_enums.append({
                        'name': item.name,
                        'c_name': item.name,
                        'members': getattr(item, 'members', {})
                    })
            elif isinstance(item, objects.TypeDecl):
                if getattr(item, 'privacity', 'public') == 'public':
                    public_types.append({
                        'name': item.name,
                        'c_name': item.name,
                        'dtype': getattr(item, 'dtype', None)
                    })

        conventions = manager.collect_target_conventions()
        manifest_data = {
            'format': 'egl-library',
            'version': '1.0.0',
            'name': lib_name,
            'target': target,
            'backend': manager.get_backend_name(),
            'links': conventions.get('link_flags', []),
            'include_dirs': [str(d) for d in conventions.get('include_dirs', [])],
            'lib_dirs': [str(d) for d in conventions.get('lib_dirs', [])],
            'bin_files': [str(b) for b in conventions.get('bin_files', [])],
        }

        symbols_data = {
            'functions': public_functions,
            'structs': public_structs,
            'enums': public_enums,
            'types': public_types
        }

        guard_name = f'EGL_LIB_{lib_name.upper().replace("-", "_").replace(".", "_")}_H'
        h_lines = [
            f'#ifndef {guard_name}',
            f'#define {guard_name}',
            ''
        ]
        for h in headers:
            h_lines.append(h)
        if headers:
            h_lines.append('')
        for td in typedef_list:
            h_lines.append(td)
        if typedef_list:
            h_lines.append('')
        for fwd in forward_decls:
            h_lines.append(fwd)
        if forward_decls:
            h_lines.append('')
        h_lines.append(f'#endif // {guard_name}\n')
        lib_h_code = '\n'.join(h_lines)

        c_lines = [
            '#include "library.h"',
            ''
        ]
        for fn in func_impls:
            if not fn.strip().startswith('int main('):
                c_lines.append(fn)
                c_lines.append('')
        lib_c_code = '\n'.join(c_lines)

        out_path = Path(output_file).resolve()
        if not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(out_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('manifest.json', json.dumps(manifest_data, indent=2))
            zf.writestr('symbols.json', json.dumps(symbols_data, indent=2))
            zf.writestr('library.h', lib_h_code)
            zf.writestr('library.c', lib_c_code)
            for f in source_dir.rglob('*'):
                if f.is_file() and not f.name.endswith('.lib.egl') and not f.name.endswith('.exe') and '__pycache__' not in f.parts:
                    rel_p = f.relative_to(source_dir)
                    zf.write(f, arcname=str(Path('source') / rel_p))

        objects.clear()
        c.clear()
        clear_types()
        return out_path

    output_lines = []
    for h in headers:
        output_lines.append(h)
    if headers:
        output_lines.append('')

    for td in typedef_list:
        output_lines.append(td)
    if typedef_list:
        output_lines.append('')

    for lib_h in imported_lib_headers:
        output_lines.append(lib_h)
        output_lines.append('')

    for fwd in forward_decls:
        output_lines.append(fwd)
    if forward_decls:
        output_lines.append('')

    for lib_c in imported_lib_sources:
        clean_lib_c = re.sub(r'#include\s+["<]library\.h[">]', '', lib_c)
        output_lines.append(clean_lib_c.strip())
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
    objects.clear()
    c.clear()
    clear_types()
    return out_path
