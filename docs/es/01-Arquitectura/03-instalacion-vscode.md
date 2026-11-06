# Instalación de la extensión para VS Code

El repositorio incluye el paquete [`bagron-language-support.vsix`](../../../tools/vscode/bagron-language-support.vsix),
que aporta resaltado, Hover, Definition, autocompletado, documentación
secuencial y comandos del lenguaje en Visual Studio Code.

La extensión reconoce la sintaxis actual de Bagron, incluidos métodos, tipos
nominales, funciones inline, bloques ASM y literales agregados como
`Point{ .x = 10 }`. Su formateador es conservador y solo elimina espacios
finales; no reindenta automáticamente código cuya indentación tiene significado.

El autocompletado, Hover y Definition siguen las mismas raíces principales que
el compilador: `modules/` y la raíz del proyecto, fuentes `lib1` ya extraídas y
`modules/`/`libs/` de la instalación de Bagron. También reconoce
`library "archivo.lib" as Alias` y `library nombre_global as Alias`, obtiene
sus exports con `bagron inspect` y permite completar los miembros de `Alias`
sin ejecutar código de la librería.

La extensión usa `bagron` como comando predeterminado. `Bagron: Compilar y
ejecutar` llama a `bagron <entrada> --execute` y selecciona el `main.bg` del
workspace cuando existe; `Bagron: Ejecutar archivo actual` conserva como
objetivo el archivo abierto. Si la instalación usa una ubicación personalizada,
configura `bagron.installRoot`. `bagron.compilerPath` permite sustituir
únicamente la ruta del lanzador.

## Instalación automática

Con Bagron instalado y `code` disponible en el `PATH`, ejecuta:

```powershell
bagron --vscode install
```

El comando desinstala la versión anterior de la extensión, si existe, e
instala el VSIX incluido con la distribución.

## Instalación manual

Desde la raíz del repositorio o de la carpeta de la distribución:

```powershell
code --install-extension .\tools\vscode\bagron-language-support.vsix --force
```

También puedes abrir VS Code, seleccionar `Extensions: Install from VSIX...`
en la paleta de comandos y elegir `tools/vscode/bagron-language-support.vsix`.

Las releases de Bagron publican únicamente los instaladores ejecutables. Para
instalar la extensión desde una copia del repositorio, usa la ruta local
`tools/vscode/bagron-language-support.vsix` con el mismo comando.

Para comprobar la instalación, abre un archivo `.bg` y verifica que VS Code
muestre el modo de lenguaje de Bagron en la barra de estado. Para reinstalar
una versión concreta, usa siempre el VSIX de ese release y conserva la opción
`--force`.
