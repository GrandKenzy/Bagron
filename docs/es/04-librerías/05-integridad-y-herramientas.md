# Integridad y herramientas

## Inspección

```powershell
bagron inspect libs/Math.lib
```

`inspect` muestra cabecera, formato, versión de librería, manifiesto,
exportaciones, módulos IR y artefactos nativos.

## Verificación

```powershell
bagron verify libs/Math.lib
```

`verify` comprueba hashes de manifiesto, símbolos, IR u objetos y fuente
empaquetada. También valida que cada entrada declarada tenga un nombre seguro.

## Extracción

```powershell
bagron unpack libs/Math.lib unpacked
```

La extracción rechaza entradas absolutas o con `..` que salgan del destino.
Durante una compilación, `extract_library()` usa una carpeta de caché por
`package_id` y crea un marcador `.complete` cuando la extracción terminó.

Cualquier alteración en los archivos empaquetados o divergencia en los hashes
detiene el proceso de verificación y previene el consumo de una biblioteca corrupta.

## Instalación local (temporal)

El comando CLI `bagron install` permite empaquetar o copiar librerías y módulos directamente dentro de las carpetas locales del proyecto (`libs/` o `modules/`), sustituyendo cualquier versión previa:

```powershell
# Instala una librería como lib1 en libs/
bagron install --library --v1 ruta/a/libreria [--name Nombre] [--version 1.0.0]

# Compila e instala una librería como lib2 nativa en libs/
bagron install --library --v2 ruta/a/libreria [--name Nombre] [--version 1.0.0]

# Copia un archivo .lib existente directamente en libs/
bagron install --library ruta/a/paquete.lib

# Instala un módulo (.bg o carpeta de módulo) directamente en modules/
bagron install --module ruta/a/modulo.bg
```

> [!NOTE]
> Este comando es una funcionalidad temporal orientada a facilitar el flujo de trabajo y la gestión local de librerías y módulos mientras se estandariza el mecanismo definitivo de distribución y paquetes.
