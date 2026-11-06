# `lib1`: fuente validada y snapshot semántico

Se crea con `--v1`:

```powershell
bagron library --v1 source -o libs/Math.lib --name Math --version 1.0.0
```

El compilador valida el árbol de `.bg` con el pipeline normal. El paquete
conserva módulos fuente, targets, tabla de exports, snapshot del frontend e IR
serializado. No necesita que el origen exponga un `main`.

Una aplicación consume una exportación mediante namespace:

```bg
library "Math.lib" as Math

func main() int32:
    return Math.square(3)
```

La identidad combina nombre, versión y hash estable del contenido. La carga se
realiza una vez por paquete y los nombres internos se separan por identidad de
librería para evitar colisiones entre APIs iguales.
