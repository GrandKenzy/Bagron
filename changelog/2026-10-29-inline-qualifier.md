# `inline` explícito en perfiles optimizados

En `prod` y `high`, las funciones Bagron declaradas con `inline` reciben
`alwaysinline` y el backend ejecuta `AlwaysInliner` antes del pipeline local.
`dev` conserva `inlinehint` para diagnóstico. Las declaraciones externas y los
cuerpos ASM no se modifican.

El benchmark canónico marca `build_record` y `serialize_int64` como `inline`,
para que la serialización pueda expandirse en sus rutas calientes.
