# Instalación de la extensión para VS Code

Bagron incluye el paquete [`bagron-language-support.vsix`](../../../tools/vscode/bagron-language-support.vsix),
que aporta resaltado, diagnósticos y comandos del lenguaje en Visual Studio
Code.

## Instalación automática

Con Bagron instalado y `code` disponible en el `PATH`, ejecuta:

```powershell
Bagron --vscode install
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
