# Seguridad de recursión

Bagron ahora analiza el grafo de llamadas después de resolver las funciones y
detecta recursión directa, mutua e indirecta mediante sus componentes cíclicos.
Una función que participe en un ciclo sin declararlo produce un error de
compilación; el ciclo debe marcarse explícitamente con `@recursive` en cada
función participante.

La recursión directa de cola que usa un marco simple se transforma en un bucle
LLVM. No se generan comprobaciones de profundidad en runtime y la optimización
se mantiene conservadora: no se aplica a métodos, variables locales ni firmas
con metadatos de longitud, tamaño, signo, región, `chain` u otras expansiones
de ABI. Las formas recursivas restantes requieren `@recursive` y conservan su
comportamiento normal de pila.

```bg
func countdown(value: int32) int32:
    if value > 0:
        return countdown(value - 1)
    return 0
```

Los ciclos de llamadas de tres o más funciones y la recursión que atraviesa
`buffer[]` quedan cubiertos por la validación estricta; la anotación opcional
`max_depth` se reserva para una etapa posterior.
