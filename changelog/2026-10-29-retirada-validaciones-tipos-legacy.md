# Retirada de validaciones de tipos legacy

Fecha: 2026-10-29

Se eliminaron de la resolución de tipos las comprobaciones específicas para
`int`, `uint` y `wsize`, porque ya no forman parte de las keywords de Bagron.

`Len_t` y `Size_t` se mantienen como parámetros especiales de expansión y sus
validaciones semánticas no cambian.
