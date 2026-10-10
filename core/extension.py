from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import gram
import gram.vsix
from gram.vsix.core import find_vscode_executable
from gram.vsix.extract import SyntaxMetadata, extract_metadata
from gram.vsix.generate import generate_icon_png, package_vsix

EASYC_PUBLISHER = "easy-c"
EASYC_EXT_NAME = "easy-c"
EASYC_DISPLAY_NAME = "Easy-C (EGL) Language Support"
EASYC_VERSION = "1.0.0"
EASYC_LANGUAGE_ID = "easy-c"
EASYC_SCOPE_NAME = "source.egl"
EASYC_THEME_NAME = "Easy-C Noble Dark"
EASYC_EXTENSIONS = [".egl", ".externs.egl"]

def generate_language_configuration() -> dict[str, Any]:
    return {
        "comments": {
            "lineComment": ";"
        },
        "brackets": [
            ["{", "}"],
            ["[", "]"],
            ["(", ")"]
        ],
        "autoClosingPairs": [
            {"open": "{", "close": "}"},
            {"open": "[", "close": "]"},
            {"open": "(", "close": ")"},
            {"open": '"', "close": '"', "notIn": ["string"]},
            {"open": "'", "close": "'", "notIn": ["string", "comment"]}
        ],
        "surroundingPairs": [
            ["{", "}"],
            ["[", "]"],
            ["(", ")"],
            ['"', '"'],
            ["'", "'"]
        ],
        "indentationRules": {
            "increaseIndentPattern": r"^.*:\s*(;.*)?$",
            "decreaseIndentPattern": r"^\s*(elif|else)\b.*:"
        }
    }

def generate_easyc_textmate_grammar(metadata: SyntaxMetadata) -> dict[str, Any]:
    patterns: list[dict[str, Any]] = []

    patterns.append({
        "name": f"comment.line.semicolon.{EASYC_LANGUAGE_ID}",
        "match": r";.*$"
    })

    patterns.append({
        "name": f"string.quoted.triple.double.{EASYC_LANGUAGE_ID}",
        "begin": r'"""',
        "end": r'"""',
        "patterns": [
            {"name": f"constant.character.escape.{EASYC_LANGUAGE_ID}", "match": r"\\."}
        ]
    })
    patterns.append({
        "name": f"string.quoted.triple.single.{EASYC_LANGUAGE_ID}",
        "begin": r"'''",
        "end": r"'''",
        "patterns": [
            {"name": f"constant.character.escape.{EASYC_LANGUAGE_ID}", "match": r"\\."}
        ]
    })

    patterns.append({
        "name": f"string.quoted.double.{EASYC_LANGUAGE_ID}",
        "begin": r'"',
        "end": r'"',
        "patterns": [
            {"name": f"constant.character.escape.{EASYC_LANGUAGE_ID}", "match": r"\\."}
        ]
    })
    patterns.append({
        "name": f"string.quoted.single.{EASYC_LANGUAGE_ID}",
        "begin": r"'",
        "end": r"'",
        "patterns": [
            {"name": f"constant.character.escape.{EASYC_LANGUAGE_ID}", "match": r"\\."}
        ]
    })

    patterns.append({
        "name": f"constant.numeric.hex.{EASYC_LANGUAGE_ID}",
        "match": r"\b0[xX][0-9a-fA-F]+\b"
    })
    patterns.append({
        "name": f"constant.numeric.float.{EASYC_LANGUAGE_ID}",
        "match": r"\b[0-9]+\.[0-9]+([eE][+-]?[0-9]+)?\b"
    })
    patterns.append({
        "name": f"constant.numeric.integer.{EASYC_LANGUAGE_ID}",
        "match": r"\b[0-9]+\b"
    })

    patterns.append({
        "name": f"constant.language.{EASYC_LANGUAGE_ID}",
        "match": r"\b(Null|None|true|false|True|False)\b"
    })

    patterns.append({
        "name": f"entity.name.tag.decorator.{EASYC_LANGUAGE_ID}",
        "match": r"@[A-Za-z_][A-Za-z0-9_]*"
    })

    patterns.append({
        "name": f"variable.language.this.{EASYC_LANGUAGE_ID}",
        "match": r"\b(this|self)\b"
    })

    patterns.append({
        "name": f"entity.name.function.call.{EASYC_LANGUAGE_ID}",
        "match": r"\b([A-Za-z_][A-Za-z0-9_]*)(?=\s*\()"
    })

    for kw_name in metadata.keywords.keys():
        clean_kw = re.escape(kw_name)
        patterns.append({
            "name": f"keyword.other.{kw_name.lower()}.{EASYC_LANGUAGE_ID}",
            "match": rf"\b{clean_kw}\b"
        })

    patterns.append({
        "name": f"keyword.operator.{EASYC_LANGUAGE_ID}",
        "match": r"(:=|==|!=|<=|>=|->|\+\+|--|\+=|-=|\*=|/=|%=|\*\*=|and|or|not|=|\+|-|\*|/|%|\||\^|&|~|<|>|!)"
    })

    patterns.append({
        "name": f"punctuation.separator.{EASYC_LANGUAGE_ID}",
        "match": r"([\{\}\(\)\[\],:;\.])"
    })

    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "Easy-C",
        "scopeName": EASYC_SCOPE_NAME,
        "patterns": patterns
    }

def generate_easyc_theme(metadata: SyntaxMetadata) -> dict[str, Any]:
    token_colors: list[dict[str, Any]] = [
        {
            "name": "Easy-C Comments",
            "scope": [f"comment.line.semicolon.{EASYC_LANGUAGE_ID}"],
            "settings": {"foreground": "#6A9955", "fontStyle": "italic"}
        },
        {
            "name": "Easy-C Strings",
            "scope": [
                f"string.quoted.double.{EASYC_LANGUAGE_ID}",
                f"string.quoted.single.{EASYC_LANGUAGE_ID}",
                f"string.quoted.triple.double.{EASYC_LANGUAGE_ID}",
                f"string.quoted.triple.single.{EASYC_LANGUAGE_ID}"
            ],
            "settings": {"foreground": "#88B04B"}
        },
        {
            "name": "Easy-C Numbers",
            "scope": [
                f"constant.numeric.hex.{EASYC_LANGUAGE_ID}",
                f"constant.numeric.float.{EASYC_LANGUAGE_ID}",
                f"constant.numeric.integer.{EASYC_LANGUAGE_ID}"
            ],
            "settings": {"foreground": "#D19A66"}
        },
        {
            "name": "Easy-C Constants",
            "scope": [f"constant.language.{EASYC_LANGUAGE_ID}"],
            "settings": {"foreground": "#48C78E", "fontStyle": "bold"}
        },
        {
            "name": "Easy-C Decorators",
            "scope": [f"entity.name.tag.decorator.{EASYC_LANGUAGE_ID}"],
            "settings": {"foreground": "#E5C07B", "fontStyle": "bold"}
        },
        {
            "name": "Easy-C Self and This",
            "scope": [f"variable.language.this.{EASYC_LANGUAGE_ID}"],
            "settings": {"foreground": "#5DADE2", "fontStyle": "italic"}
        },
        {
            "name": "Easy-C Function Calls",
            "scope": [f"entity.name.function.call.{EASYC_LANGUAGE_ID}"],
            "settings": {"foreground": "#F39C12"}
        },
        {
            "name": "Easy-C Operators",
            "scope": [f"keyword.operator.{EASYC_LANGUAGE_ID}"],
            "settings": {"foreground": "#ABB2BF"}
        },
        {
            "name": "Easy-C Punctuation",
            "scope": [f"punctuation.separator.{EASYC_LANGUAGE_ID}"],
            "settings": {"foreground": "#ABB2BF"}
        }
    ]

    for kw_name, kw_meta in metadata.keywords.items():
        if kw_meta.hex_color and kw_meta.hex_color.upper() != "#FFFFFF":
            token_colors.append({
                "name": f"Easy-C Keyword: {kw_name}",
                "scope": [f"keyword.other.{kw_name.lower()}.{EASYC_LANGUAGE_ID}"],
                "settings": {
                    "foreground": kw_meta.hex_color
                }
            })

    return {
        "name": EASYC_THEME_NAME,
        "type": "dark",
        "colors": {
            "editor.background": "#16191D",
            "editor.foreground": "#D8DEE9",
            "editorCursor.foreground": "#E5C07B",
            "editor.lineHighlightBackground": "#1E2228",
            "editorLineNumber.foreground": "#4B5263",
            "editorLineNumber.activeForeground": "#E5C07B",
            "editor.selectionBackground": "#283344"
        },
        "tokenColors": token_colors
    }

def generate_easyc_snippets() -> dict[str, Any]:
    return {
        "Main Function": {
            "prefix": "main",
            "body": [
                "int main():",
                "    ${1:pass}",
                "    return 0"
            ],
            "description": "Función principal de Easy-C"
        },
        "Function Declaration": {
            "prefix": "func",
            "body": [
                "${1:void} ${2:nombre_funcion}(${3:params}):",
                "    ${4:pass}"
            ],
            "description": "Declaración de función en Easy-C"
        },
        "Struct Declaration": {
            "prefix": "struct",
            "body": [
                "public struct Type ${1:Nombre}:",
                "    ${2:__int_t__ value}"
            ],
            "description": "Declaración de estructura de tipo"
        },
        "Class Declaration": {
            "prefix": "class",
            "body": [
                "public class ${1:Nombre}:",
                "    void __init__(self):",
                "        ${2:pass}"
            ],
            "description": "Declaración de clase en Easy-C"
        },
        "Clause Target": {
            "prefix": "clause",
            "body": [
                "clause Target '${1:egl-c}'"
            ],
            "description": "Cláusula de Target"
        },
        "Include Statement": {
            "prefix": "include",
            "body": [
                "include \"${1:stdio}\" as ${2:C_STDIO}"
            ],
            "description": "Inclusión de librería del backend"
        },
        "Import Statement": {
            "prefix": "import",
            "body": [
                "import ${1:modulo}"
            ],
            "description": "Importación de módulo EGL"
        }
    }

def generate_easyc_package_json() -> dict[str, Any]:
    return {
        "name": EASYC_EXT_NAME,
        "displayName": EASYC_DISPLAY_NAME,
        "description": "Soporte oficial de sintaxis para Easy-C (EGL) con paleta Noble Dark, snippets y TextMate.",
        "version": EASYC_VERSION,
        "publisher": EASYC_PUBLISHER,
        "icon": "icon.png",
        "engines": {
            "vscode": "^1.70.0"
        },
        "categories": [
            "Programming Languages",
            "Themes",
            "Snippets"
        ],
        "contributes": {
            "languages": [
                {
                    "id": EASYC_LANGUAGE_ID,
                    "aliases": ["Easy-C", "EGL", "egl"],
                    "extensions": EASYC_EXTENSIONS,
                    "configuration": "./language-configuration.json"
                }
            ],
            "grammars": [
                {
                    "language": EASYC_LANGUAGE_ID,
                    "scopeName": EASYC_SCOPE_NAME,
                    "path": "./syntaxes/easy-c.tmLanguage.json"
                }
            ],
            "themes": [
                {
                    "label": EASYC_THEME_NAME,
                    "uiTheme": "vs-dark",
                    "path": "./themes/easy-c-noble.json"
                }
            ],
            "snippets": [
                {
                    "language": EASYC_LANGUAGE_ID,
                    "path": "./snippets/snippets.json"
                }
            ]
        }
    }

def build_easyc_extension_directory(output_dir: Path | str) -> Path:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    metadata = extract_metadata(include_native=True)

    syntaxes_dir = out / "syntaxes"
    syntaxes_dir.mkdir(parents=True, exist_ok=True)
    themes_dir = out / "themes"
    themes_dir.mkdir(parents=True, exist_ok=True)
    snippets_dir = out / "snippets"
    snippets_dir.mkdir(parents=True, exist_ok=True)

    pkg_data = generate_easyc_package_json()
    (out / "package.json").write_text(json.dumps(pkg_data, indent=2, ensure_ascii=False), encoding="utf-8")

    lang_cfg = generate_language_configuration()
    (out / "language-configuration.json").write_text(json.dumps(lang_cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    tm_grammar = generate_easyc_textmate_grammar(metadata)
    (syntaxes_dir / "easy-c.tmLanguage.json").write_text(json.dumps(tm_grammar, indent=2, ensure_ascii=False), encoding="utf-8")

    theme_cfg = generate_easyc_theme(metadata)
    (themes_dir / "easy-c-noble.json").write_text(json.dumps(theme_cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    snippets_cfg = generate_easyc_snippets()
    (snippets_dir / "snippets.json").write_text(json.dumps(snippets_cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    generate_icon_png(out / "icon.png")

    readme_content = "# Easy-C (EGL) Language Support\n\nSoporte oficial para Easy-C con resaltado de sintaxis Noble Dark y snippets para Visual Studio Code.\n"
    (out / "README.md").write_text(readme_content, encoding="utf-8")

    return out

def compile_extension(output_vsix: str | Path | None = None) -> Path:
    temp_build = Path(tempfile.gettempdir()) / "easy_c_vsix_build"
    if temp_build.exists():
        shutil.rmtree(temp_build, ignore_errors=True)

    build_easyc_extension_directory(temp_build)

    if output_vsix is not None:
        target_vsix = Path(output_vsix).resolve()
    else:
        target_vsix = Path.cwd() / f"{EASYC_EXT_NAME}-{EASYC_VERSION}.vsix"

    target_vsix.parent.mkdir(parents=True, exist_ok=True)
    package_vsix(temp_build, output_vsix=target_vsix)
    return target_vsix

def install_extension(vsix_path: str | Path | None = None) -> tuple[bool, str]:
    target_vsix = Path(vsix_path).resolve() if vsix_path else compile_extension()
    if not target_vsix.exists():
        return False, f"El archivo .vsix no existe: {target_vsix}"

    code_bin = find_vscode_executable()
    if not code_bin:
        return False, "Visual Studio Code CLI ('code') no fue encontrado en el sistema o PATH."

    try:
        res = subprocess.run(
            [code_bin, "--install-extension", str(target_vsix), "--force"],
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode == 0:
            return True, f"Extensión instalada exitosamente en VS Code desde: {target_vsix}"
        err = res.stderr.strip() or res.stdout.strip()
        return False, f"Fallo al instalar en VS Code (código {res.returncode}): {err}"
    except Exception as exc:
        return False, f"Error ejecutando code CLI: {exc}"
