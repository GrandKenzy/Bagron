# Modularización del emisor de expresiones LLVM

Fecha: 2026-10-29

`core/backend/llvm/functions/expressions.py` pasó a ser el paquete
`core/backend/llvm/functions/expressions/`, con un `__init__.py` que conserva
`ExpressionEmitterMixin` como interfaz de composición.

Las responsabilidades quedaron separadas en `memory.py`, `values.py`,
`operators.py` y `calls.py`, sin cambiar el comportamiento del backend ni el
import usado por `FunctionEmitter`.
