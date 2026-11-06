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
