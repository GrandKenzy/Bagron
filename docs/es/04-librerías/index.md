# Librerías `.lib`

## Índice

1. [Modelo y estructura](01-modelo-y-estructura.md)
2. [lib1: fuente validada](02-lib1-source.md)
3. [lib2: objeto nativo](03-lib2-native.md)
4. [Consumo y namespaces](04-consumo-y-namespaces.md)
5. [Integridad y herramientas](05-integridad-y-herramientas.md)

La interfaz actual para crear y gestionar paquetes `.lib` es:

```powershell
bagron library --v1 source -o libs/Math.lib --name Math --version 1.0.0
bagron library --v2 source -o libs/Math.lib --name Math --version 2.0.0
bagron inspect libs/Math.lib
bagron verify libs/Math.lib
bagron unpack libs/Math.lib unpacked
```

`package` y `package2` ya no son comandos válidos.

## `lib1`: fuente validada

`--v1` conserva módulos, tabla pública, snapshot frontend, IR serializado y
dependencias nativas. La validación usa la semántica normal, pero no exige un
`main` del usuario.

Una aplicación importa la librería desde el módulo de entrada:

```bg
library "Math.lib" as Math

func main() int32:
    return Math.square(3)
```

El paquete se resuelve bajo `libs/` del proyecto y solo exporta declaraciones
`public`.

## `lib2`: objeto nativo

`--v2` compila los módulos a un objeto nativo y empaqueta símbolos, target y
dependencias para el enlace final. El consumidor aporta su propio `main` y un
target compatible. La biblioteca garantiza nombres estables y validación de ABI.

`verify` comprueba cabecera, manifiesto, secciones y hashes. `unpack` rechaza
entradas ZIP que escapen del destino mediante `..`.
