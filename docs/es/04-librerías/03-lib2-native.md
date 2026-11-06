# `lib2`: objeto nativo

Se crea con `--v2`:

```powershell
bagron library --v2 source -o libs/Math.lib --name Math --version 2.0.0
```

Cada módulo se valida y se emite a un objeto nativo para el target solicitado.
El paquete conserva el objeto, la tabla de símbolos, el manifiesto de target y
los objetos o bibliotecas nativos asociados. El consumidor enlaza esos
artefactos con su propio ejecutable.

`lib2` no analiza de nuevo el `source/` al consumirse: usa la tabla y el objeto
serializados. Por eso el target de la librería debe ser compatible con el del
proyecto consumidor.

El objeto compilado y el manifiesto son verificados antes de producir
el archivo `.lib` final.
