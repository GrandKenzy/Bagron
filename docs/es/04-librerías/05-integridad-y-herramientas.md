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

Calcula una huella canónica SHA-256 vinculando los archivos fuente `.bg` y la
metadata del paquete (`author`, `name`, `version`), y escribe o actualiza
automáticamente el campo `signature` dentro de `meta.toml`. Esta huella detecta
alteraciones o corrupción cuando se conserva una referencia confiable, pero no
autentica criptográficamente al autor: cualquiera que modifique las fuentes
podría recalcularla.

Al empaquetar o instalar una librería desde un directorio de fuentes, Bagron
rechaza por defecto una huella ausente o inválida. `--allow-unverified` permite
continuar solo para desarrollo local o fuentes cuya confianza se haya confirmado
por otro medio.

## Extracción

```powershell
bagron unpack libs/Math.lib unpacked
```

La extracción rechaza entradas absolutas o con `..` que salgan del destino.
Durante una compilación, `extract_library()` usa una carpeta de caché por
SHA-256 del archivo `.lib` y crea un marcador `.complete` cuando la extracción
terminó. Antes de reutilizarla vuelve a comprobar los archivos y sus hashes.

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

Para una fuente local sin huella válida, la excepción debe solicitarse
explícitamente:

```powershell
bagron install --library --v1 ruta/a/libreria --allow-unverified
```

Los paquetes descargados desde Central requieren HTTPS y un checksum SHA-256
registrado. La instalación se detiene si falta el checksum, no coincide o el
registro proporciona un nombre que no puede convertirse en un archivo seguro.
El contenedor `.lib` también se verifica antes de reemplazar una copia existente.
`bagron package install ... --allow-unverified` queda reservado para registros
privados o pruebas controladas.

## Paquetes locales y Central

`package install` conserva una librería válida con el mismo nombre en
`BAGRON_ROOT/libs`; no consulta Central ni sustituye su archivo aunque se
solicite otra versión. Usa `package update` cuando quieras reemplazarla
explícitamente con la versión resuelta por Central:

```powershell
# Instala solo si string.lib todavía no existe en libs/
bagron package install string

# Descarga y reemplaza string.lib de forma atómica
bagron package update string

# Solicita una versión concreta para la actualización
bagron package update string@1.1.9
```

Todos los comandos `package` usan `BAGRON_ROOT/libs` por defecto. Para guardar
un paquete en otra ubicación, indica `--select`:

```powershell
bagron package install string --select .\libs
bagron package list --select .\libs
```

La opción histórica `--dir` sigue siendo aceptada como alias de `--select`.

Puedes administrar las librerías ya presentes y traer artefactos que tengas en
el equipo sin subirlos al registro:

```powershell
# Muestra nombre, versión, formato y archivo de las librerías verificadas
bagron package list

# Importa un archivo .lib o todos los .lib directos de una carpeta
bagron package pull ruta/a/string.lib
bagron package pull ruta/a/mis-libs

# Elimina una librería local
bagron package uninstall string
```

`pull` verifica el contenedor antes de publicarlo de forma atómica y, igual que
la instalación desde Central, actualiza el lockfile asociado al destino.
`uninstall` elimina esa entrada solo si ninguna otra dependencia bloqueada
requiere la librería.

## Lockfile

Si el proyecto contiene `bagron.lock`, cada compilación exige que las
librerías seleccionadas coincidan con su nombre, versión, formato y SHA-256.
Una instalación nueva desde Central, `update` y `pull` actualizan ese archivo
después de validar y publicar el paquete. Las operaciones globales usan
`BAGRON_ROOT/bagron.lock`; cuando se indica `--select`, usan el
`bagron.lock` del proyecto llamador. `uninstall` elimina una entrada
únicamente cuando no deja dependencias bloqueadas incompletas.
Los proyectos que administran sus archivos `.lib` directamente pueden continuar
sin lockfile.

Central puede entregar metadatos TUF firmados con Ed25519. Bagron comprueba la
fecha de expiración, el tamaño, el hash, el nombre, la versión y el formato del
artefacto. La exigencia global se activa para una instalación controlada con
`BAGRON_REQUIRE_CENTRAL_SIGNATURES=1` cuando el catálogo ya esté firmado.

> [!NOTE]
> `bagron install --module` queda reservado para proyectos que todavía
> mantengan módulos fuente locales; no forma parte del runtime global de Bagron.
