# Integridad y herramientas

## Inspección

```powershell
bagron inspect libs/Math.lib
```

`inspect` muestra cabecera, formato, versión de librería, manifiesto,
exportaciones, módulos IR y artefactos nativos.

## Verificación

```powershell
# Verifica un archivo de paquete .lib empaquetado
bagron verify libs/Math.lib

# Verifica la firma de metadatos de un directorio de fuentes frente a su meta.toml
bagron verify ruta/a/libreria
```

`verify` comprueba hashes de manifiesto, símbolos, IR u objetos y fuente
empaquetada en archivos `.lib`. Cuando se aplica sobre un directorio de librería,
valida que la firma declarada en `meta.toml` coincida exactamente con los fuentes
`.bg` y la metadata del paquete.

## Firma de metadatos

```powershell
bagron sign ruta/a/libreria
```

Calcula la firma canónica SHA-256 vinculando los archivos fuente `.bg` y la metadata
del paquete (`author`, `name`, `version`), y escribe o actualiza automáticamente
el campo `signature` dentro de `meta.toml`. Además, al empaquetar una librería con
`bagron library` o instalarla con `bagron install`, Bagron sincroniza y valida
automáticamente esta firma.

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

El comando CLI `bagron install` instala librerías completas dentro de la
carpeta local `libs/`, sustituyendo cualquier versión previa:

```powershell
# Instala una librería como lib1 en libs/
bagron install --library --v1 ruta/a/libreria [--name Nombre] [--version 1.0.0]

# Compila e instala una librería como lib2 nativa en libs/
bagron install --library --v2 ruta/a/libreria [--name Nombre] [--version 1.0.0]

# Copia un archivo .lib existente directamente en libs/
bagron install --library ruta/a/paquete.lib

```

> [!NOTE]
> `bagron install --module` queda reservado para proyectos que todavía
> mantengan módulos fuente locales; no forma parte del runtime global de Bagron.
