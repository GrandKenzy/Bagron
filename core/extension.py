"""VS Code extension packaging for EGL, backed by Gram's generic VSIX generators."""
from __future__ import annotations

import inspect
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import core.initiator.keywords as _egl_keywords
import core.initiator.rules as egl_rules
from gram.core.combinators.base import RuleItem
from gram.vsix import (
    build_extension_directory,
    extract_metadata,
    find_vscode_executable,
    package_vsix,
)
try:
    from gram.vsix.configuration import LanguageConfiguration
except ModuleNotFoundError as exc:
    if exc.name != "gram.vsix.configuration":
        raise
    raise ImportError(
        "La copia de Gram instalada en .egl/vendor es anterior al generador VSIX "
        "que necesita EGL. Actualízala con 'egl install gram' y vuelve a ejecutar "
        "'egl extension'."
    ) from exc


_REQUIRED_VSIX_OPTIONS = {
    "language_id",
    "scope_name",
    "grammar_name",
    "grammar_file",
    "theme_file",
    "language_configuration",
    "include_lsp",
    "include_hover",
    "additional_files",
}
_available_options = set(inspect.signature(build_extension_directory).parameters)
if not _REQUIRED_VSIX_OPTIONS.issubset(_available_options):
    missing_options = ", ".join(sorted(_REQUIRED_VSIX_OPTIONS - _available_options))
    raise ImportError(
        "La copia de Gram instalada en .egl/vendor no incluye el generador VSIX "
        f"actualizado (faltan: {missing_options}). Actualízala con 'egl install gram' "
        "y vuelve a ejecutar 'egl extension'."
    )


EGL_PUBLISHER = "GrandKenzy"
EGL_EXT_NAME = "egl"
EGL_DISPLAY_NAME = "Easy Global Language (EGL) Support"
EGL_VERSION = "1.0.0"
EGL_LANGUAGE_ID = "egl"
EGL_SCOPE_NAME = "source.egl"
EGL_THEME_NAME = "EGL Noble Dark"
EGL_EXTENSIONS = [".egl", ".externs.egl", ".lib.egl"]

EGL_SNIPPETS = {
    "Main Function": {
        "prefix": "main",
        "body": ["int main():", "    ${1:pass}", "    return 0"],
        "description": "Función principal de EGL",
    },
    "Function Declaration": {
        "prefix": "func",
        "body": ["${1:void} ${2:nombre_funcion}(${3:params}):", "    ${4:pass}"],
        "description": "Declaración de función en EGL",
    },
    "Struct Declaration": {
        "prefix": "struct",
        "body": ["public struct Type ${1:Nombre}:", "    ${2:__int_t__ value}"],
        "description": "Declaración de estructura de tipo",
    },
    "Class Declaration": {
        "prefix": "class",
        "body": [
            "public class ${1:Nombre}:",
            "    void __init__(self):",
            "        ${2:pass}",
        ],
        "description": "Declaración de clase en EGL",
    },
    "Include Statement": {
        "prefix": "include",
        "body": ['include "${1:stdio}" as ${2:C_STDIO}'],
        "description": "Inclusión de librería del backend",
    },
    "Import Statement": {
        "prefix": "import",
        "body": ["import ${1:modulo}"],
        "description": "Importación de módulo EGL",
    },
}

EGL_TOKEN_COLORS = [
    {
        "name": "EGL Comments",
        "scope": ["comment.line.semicolon.egl"],
        "settings": {"foreground": "#6A9955", "fontStyle": "italic"},
    },
    {
        "name": "EGL Strings",
        "scope": [
            "string.quoted.double.egl",
            "string.quoted.single.egl",
            "string.quoted.triple.double.egl",
            "string.quoted.triple.single.egl",
        ],
        "settings": {"foreground": "#88B04B"},
    },
    {
        "name": "EGL Numbers",
        "scope": [
            "constant.numeric.hex.egl",
            "constant.numeric.float.egl",
            "constant.numeric.integer.egl",
        ],
        "settings": {"foreground": "#D19A66"},
    },
    {
        "name": "EGL Constants",
        "scope": ["constant.language.egl"],
        "settings": {"foreground": "#48C78E", "fontStyle": "bold"},
    },
    {
        "name": "EGL Decorators",
        "scope": ["entity.name.tag.decorator.egl"],
        "settings": {"foreground": "#E5C07B", "fontStyle": "bold"},
    },
    {
        "name": "EGL Self and This",
        "scope": ["variable.language.this.egl"],
        "settings": {"foreground": "#5DADE2", "fontStyle": "italic"},
    },
    {
        "name": "EGL Function Calls",
        "scope": ["entity.name.function.call.egl"],
        "settings": {"foreground": "#F39C12"},
    },
    {
        "name": "EGL Operators",
        "scope": ["keyword.operator.egl"],
        "settings": {"foreground": "#ABB2BF"},
    },
    {
        "name": "EGL Punctuation",
        "scope": ["punctuation.separator.egl"],
        "settings": {"foreground": "#ABB2BF"},
    },
]

EGL_TEXTMATE_PATTERNS = [
    {
        "name": "entity.name.tag.decorator.egl",
        "match": r"@[A-Za-z_][A-Za-z0-9_]*",
    },
    {
        "name": "variable.language.this.egl",
        "match": r"\b(this|self)\b",
    },
    {
        "name": "entity.name.function.call.egl",
        "match": r"\b[A-Za-z_][A-Za-z0-9_]*(?=\s*\()",
    },
]

EGL_ICON_THEME = {
    "iconDefinitions": {
        "_egl": {"iconPath": "./egl.svg"},
        "_externs": {"iconPath": "./externs.svg"},
        "_lib": {"iconPath": "./lib.svg"},
    },
    "fileExtensions": {
        "egl": "_egl",
        "externs.egl": "_externs",
        "lib.egl": "_lib",
    },
}

EGL_ASSETS: dict[str, str | bytes] = {
    "icons/egl-icon-theme.json": json.dumps(EGL_ICON_THEME, indent=2),
    "icons/egl.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="13" fill="#252033" stroke="#A78BFA" stroke-width="2"/>
  <path d="M4 16h24M16 3c4 4 6 8 6 13s-2 9-6 13c-4-4-6-8-6-13s2-9 6-13Z" fill="none" stroke="#C4B5FD" stroke-width="1.4"/>
  <rect x="8" y="12" width="16" height="8" rx="2" fill="#252033"/>
  <text x="16" y="18" fill="#F5F3FF" font-family="Segoe UI, sans-serif" font-size="7" font-weight="700" text-anchor="middle">egl</text>
</svg>
""",
    "icons/externs.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <path d="M7 2h13l6 6v22H7z" fill="#202A35" stroke="#67C7D4" stroke-linejoin="round" stroke-width="2"/>
  <path d="M20 2v7h6" fill="none" stroke="#67C7D4" stroke-linejoin="round" stroke-width="2"/>
  <text x="16" y="21" fill="#C8F3F5" font-family="Segoe UI, sans-serif" font-size="7" font-weight="700" text-anchor="middle">sym</text>
</svg>
""",
    "icons/lib.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <path d="M7 2h13l6 6v22H7z" fill="#282238" stroke="#B69CFF" stroke-linejoin="round" stroke-width="2"/>
  <path d="M20 2v7h6" fill="none" stroke="#B69CFF" stroke-linejoin="round" stroke-width="2"/>
  <text x="16" y="21" fill="#E9DFFF" font-family="Segoe UI, sans-serif" font-size="8" font-weight="700" text-anchor="middle">lib</text>
</svg>
""",
}

EGL_README = """# EGL Language Support

Soporte para archivos EGL en Visual Studio Code: resaltado de sintaxis, comentarios, delimitadores, snippets y documentación emergente al pasar el cursor sobre `clause`. La extensión también incluye el tema opcional **EGL Noble Dark** y el tema de iconos **EGL File Icons**.

## Activar EGL Noble Dark

1. Abre la paleta de comandos con `Ctrl+Shift+P` (`Cmd+Shift+P` en macOS).
2. Ejecuta **Preferences: Color Theme**.
3. Selecciona **EGL Noble Dark**.

El tema de colores de VS Code se aplica a toda la ventana. Para conservar el tema actual, puedes personalizar solo los tokens EGL desde `settings.json`:

```json
{
  "editor.tokenColorCustomizations": {
    "textMateRules": [
      {
        "scope": "keyword.other.class.egl",
        "settings": { "foreground": "#6630E4" }
      }
    ]
  }
}
```

## Activar los iconos de archivo EGL

1. Abre la paleta de comandos con `Ctrl+Shift+P` (`Cmd+Shift+P` en macOS).
2. Ejecuta **Preferences: File Icon Theme**.
3. Selecciona **EGL File Icons**.

La selección del tema de iconos es independiente del tema de colores.

## Instalar desde la CLI

Genera el paquete VSIX con `egl extension` y luego instálalo con `egl extension --install`. La instalación desinstala primero la versión actual de `GrandKenzy.egl`, si está instalada. La selección de los temas de color e iconos sigue siendo opcional y manual.
"""


def _egl_metadata():
    metadata = extract_metadata(include_native=True)
    metadata.rules.clear()
    egl_keywords = (
        set(_egl_keywords.KEYWORDS)
        | set(_egl_keywords.TYPES)
        | {
            word
            for words in _egl_keywords.KEYWORDS_BY_GROUP.values()
            for word in words
        }
    )
    metadata.keywords = {
        name: keyword
        for name, keyword in metadata.keywords.items()
        if name in egl_keywords
    }
    seen: set[type[RuleItem]] = set()
    for rule in vars(egl_rules).values():
        if (
            isinstance(rule, type)
            and issubclass(rule, RuleItem)
            and rule is not RuleItem
            and rule not in seen
        ):
            metadata.add_rule(rule)
            seen.add(rule)
    metadata.keywords["clause"].description = "\n\n".join(
        part for part in (
            egl_rules.EGL_CLAUSE.description,
            inspect.cleandoc(egl_rules.EGL_CLAUSE.docs),
        )
        if part
    )
    metadata.file_extensions = list(EGL_EXTENSIONS)
    return metadata


def build_EGL_extension_directory(output_dir: str | Path) -> Path:
    metadata = _egl_metadata()
    language_configuration = (
        LanguageConfiguration()
        .LineComment(";")
        .IndentationRules(
            increase=r"^.*:\s*(;.*)?$",
            decrease=r"^\s*(elif|else)\b.*:",
        )
    )
    return build_extension_directory(
        output_dir=output_dir,
        metadata=metadata,
        ext_id=EGL_EXT_NAME,
        ext_name=EGL_DISPLAY_NAME,
        publisher=EGL_PUBLISHER,
        version=EGL_VERSION,
        theme_name=EGL_THEME_NAME,
        language_id=EGL_LANGUAGE_ID,
        scope_name=EGL_SCOPE_NAME,
        grammar_name="EGL",
        grammar_file="EGL.tmLanguage.json",
        theme_file="EGL-noble.json",
        language_aliases=["EGL", "egl"],
        language_configuration=language_configuration,
        theme_editor_colors={
            "editor.background": "#000000",
            "editor.foreground": "#D8DEE9",
            "editorCursor.foreground": "#E5C07B",
            "editor.lineHighlightBackground": "#1E2228",
            "editorLineNumber.foreground": "#4B5263",
            "editorLineNumber.activeForeground": "#E5C07B",
            "editor.selectionBackground": "#C7FDF483",
        },
        additional_token_colors=EGL_TOKEN_COLORS,
        additional_textmate_patterns=EGL_TEXTMATE_PATTERNS,
        token_label_prefix="EGL",
        include_default_theme_colors=False,
        snippets=EGL_SNIPPETS,
        include_default_snippets=False,
        include_rule_snippets=False,
        include_lsp=False,
        include_hover=True,
        extension_description="Sintaxis, snippets e iconos de archivo EGL, con tema de color opcional.",
        additional_contributions={
            "iconThemes": [{
                "id": "egl-file-icons",
                "label": "EGL File Icons",
                "path": "./icons/egl-icon-theme.json",
            }],
        },
        additional_files=EGL_ASSETS,
        readme_content=EGL_README,
    )


def compile_extension(output_vsix: str | Path | None = None) -> Path:
    temp_build = Path(tempfile.gettempdir()) / "egl_vsix_build"
    if temp_build.exists():
        shutil.rmtree(temp_build)

    build_EGL_extension_directory(temp_build)
    target_vsix = (
        Path(output_vsix).resolve()
        if output_vsix is not None
        else Path.cwd() / f"{EGL_EXT_NAME}-{EGL_VERSION}.vsix"
    )
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

    extension_id = f"{EGL_PUBLISHER}.{EGL_EXT_NAME}"
    try:
        listed = subprocess.run(
            [code_bin, "--list-extensions"],
            capture_output=True,
            text=True,
            check=False,
        )
        if listed.returncode != 0:
            err = listed.stderr.strip() or listed.stdout.strip()
            return False, f"No se pudo comprobar si {extension_id} está instalada: {err}"

        installed_ids = {line.strip().casefold() for line in listed.stdout.splitlines()}
        if extension_id.casefold() in installed_ids:
            removed = subprocess.run(
                [code_bin, "--uninstall-extension", extension_id],
                capture_output=True,
                text=True,
                check=False,
            )
            if removed.returncode != 0:
                err = removed.stderr.strip() or removed.stdout.strip()
                return False, (
                    f"Fallo al desinstalar {extension_id} antes de reinstalar "
                    f"(código {removed.returncode}): {err}"
                )

        installed = subprocess.run(
            [code_bin, "--install-extension", str(target_vsix), "--force"],
            capture_output=True,
            text=True,
            check=False,
        )
        if installed.returncode == 0:
            return True, f"Extensión {extension_id} instalada limpiamente en VS Code desde: {target_vsix}"
        err = installed.stderr.strip() or installed.stdout.strip()
        return False, f"Fallo al instalar en VS Code (código {installed.returncode}): {err}"
    except OSError as exc:
        return False, f"Error ejecutando code CLI: {exc}"
