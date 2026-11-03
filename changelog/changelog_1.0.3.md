# Changelog 1.0.3

## Distribución Linux

- El instalador de Bagron ahora genera lanzadores POSIX (`bagron` y `Bagron`)
  con permisos ejecutables.
- Las instalaciones Linux crean enlaces en `~/.local/bin` y la desinstalación
  retira únicamente los enlaces asociados a esa instalación.
- Las descargas del instalador están fijadas al tag de la versión en lugar de
  seguir silenciosamente la rama `main`.
- Se añade `install.sh` para instalar desde Internet o desde un paquete
  extraído.
- Se añade el paquete reproducible `Bagron-1.0.3-linux-x86_64.tar.gz` y un
  workflow de GitHub Actions que prueba Windows/Linux y publica sus artefactos.
- El workflow construye el parser AOT de Gram para ambos sistemas; el paquete
  Linux incluye `libbagron_aot.so` y su manifiesto, y el instalador puede
  reconstruirlo cuando esos binarios no están disponibles.

## Documentación

- README y documentación de arquitectura incluyen requisitos, instalación y
  desinstalación en Linux.
- La documentación conserva la instalación del VSIX de VS Code para ambos
  sistemas.
