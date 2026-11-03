# Modelo y estructura de una librería

Una librería Bagron es un archivo `.lib` binario con cabecera fija, manifiesto
JSON, tabla de símbolos y un ZIP protegido. El origen se separa del proyecto
consumidor:

```text
Math/
└── source/
    ├── arithmetic.bg
    └── constants.bg
```

El paquete terminado se coloca normalmente en `libs/`:

```text
project/
├── main.bg
└── libs/
    └── Math.lib
```

El módulo de entrada declara la dependencia con un alias estable:

```bg
library "Math.lib" as Math
```

La directiva `library` solo se permite en el módulo principal. Los módulos de
la librería exportan símbolos `public`; los `private` se usan para validar el
paquete, pero no quedan disponibles al consumidor.
