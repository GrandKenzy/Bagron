# Frontend AOT de Gram para Bagron

Bagron consume las unidades `.bg` generadas por `Gram.Session.export_bagron_parser`.
El compilador selecciona primero las cláusulas `#if OS/ARCH` del host y después
parsea el GIR producido por Gram; esto permite que el mismo runtime generado
seleccione Windows o Linux sin leer siempre la primera cláusula del archivo.

El runtime de archivos usa Win32 en Windows y POSIX (`open`, `read`, `write`,
`lseek`) en Linux. macOS se rechaza con un diagnóstico de target no soportado.

Los intrínsecos internos `__bagron_argc()` y
`__bagron_arg_copy(index, buffer, capacity)` conectan el wrapper nativo
`main(int argc, char** argv)` con el `func main() int32` del lenguaje.
