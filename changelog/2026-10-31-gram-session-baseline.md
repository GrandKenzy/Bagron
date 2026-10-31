# Baseline de compilación con Gram editable

Se registra la línea base previa a la migración explícita de la sesión de
Bagron hacia el modelo de `Session` de Gram `3.0.0`. La dependencia continúa
siendo editable desde `~/Desktop/Gram`; no se fija un tag ni un commit.

## Protocolo

- Comando: `vnma run main.py examples/canon/_main.bg`
- Plataforma: Windows
- Python: `3.14.7`
- Gram: `3.0.0-4-g2be2e9d-dirty`
- Muestras: cinco compilaciones completas, con salida descartada
- Alcance: arranque de `vnma`, lexer/parser de Gram, frontend semántico,
  generación LLVM, enlace y creación del ejecutable

## Resultado observado

| Muestra | Tiempo (s) | Salida |
| ---: | ---: | --- |
| 1 | 10.010 | correcta |
| 2 | 9.270 | correcta |
| 3 | 8.908 | correcta |
| 4 | 14.342 | correcta |
| 5 | 10.955 | correcta |

- Mínimo: `8.908 s`
- Mediana: `10.010 s`
- Promedio: `10.697 s`
- Máximo: `14.342 s`

Se conserva como referencia el recuerdo previo de una compilación de
aproximadamente `5–7 s`, pero no se reprodujo en estas muestras. La medición
incluye todo el proceso de compilación y no aísla el coste de Gram; por eso
servirá para detectar regresiones globales, no para atribuir una mejora
exclusivamente al parser.

## Verificación posterior a la migración de sesión

Después de mover el registro de keywords, grupos y configuración a
`BAGRON_SESSION`, se repitió exactamente el mismo comando:

| Muestra | Tiempo (s) | Salida |
| ---: | ---: | --- |
| 1 | 6.011 | correcta |
| 2 | 6.749 | correcta |
| 3 | 5.612 | correcta |
| 4 | 7.567 | correcta |
| 5 | 7.013 | correcta |

- Mínimo: `5.612 s`
- Mediana: `6.749 s`
- Promedio: `6.590 s`
- Máximo: `7.567 s`

El resultado vuelve a caer dentro del rango histórico de `5–7 s`. No se
atribuye una mejora causal a la migración porque las muestras pre y post no
son suficientemente controladas para separar el efecto de la sesión de la
variación de arranque, cachés y carga del entorno.

La migración conserva el backend Python de Gram y no activa AOT. El registro
léxico usa `Session.add_group()`, `Session.add_keyword()` y `Session.config`;
la desactivación de `**` conserva la API de símbolos de Gram porque `Session`
todavía no expone una operación pública equivalente.
