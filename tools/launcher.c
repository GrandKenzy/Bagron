#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

static int file_exists(const wchar_t* path) {
    DWORD attr = GetFileAttributesW(path);
    return (attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY));
}

int wmain(int argc, wchar_t** argv) {
    wchar_t exePath[MAX_PATH];
    if (GetModuleFileNameW(NULL, exePath, MAX_PATH) == 0) {
        fwprintf(stderr, L"[EGL Error] No se pudo obtener la ruta del ejecutable.\n");
        return 1;
    }

    // Obtener directorio bin/
    wchar_t* lastSlash = wcsrchr(exePath, L'\\');
    if (!lastSlash) lastSlash = wcsrchr(exePath, L'/');
    if (lastSlash) *lastSlash = L'\0';

    // 1. Localizar egl.py buscando en exePath, su padre y su abuelo
    wchar_t rootDir[MAX_PATH];
    wcscpy(rootDir, exePath);

    wchar_t scriptPath[MAX_PATH];
    int foundScript = 0;

    // Buscar en directorio actual
    swprintf(scriptPath, MAX_PATH, L"%ls\\egl.py", rootDir);
    if (file_exists(scriptPath)) {
        foundScript = 1;
    } else {
        // Buscar en padre
        wchar_t* slash1 = wcsrchr(rootDir, L'\\');
        if (!slash1) slash1 = wcsrchr(rootDir, L'/');
        if (slash1) {
            *slash1 = L'\0';
            swprintf(scriptPath, MAX_PATH, L"%ls\\egl.py", rootDir);
            if (file_exists(scriptPath)) {
                foundScript = 1;
            } else {
                // Buscar en abuelo
                wchar_t* slash2 = wcsrchr(rootDir, L'\\');
                if (!slash2) slash2 = wcsrchr(rootDir, L'/');
                if (slash2) {
                    *slash2 = L'\0';
                    swprintf(scriptPath, MAX_PATH, L"%ls\\egl.py", rootDir);
                    if (file_exists(scriptPath)) {
                        foundScript = 1;
                    }
                }
            }
        }
    }

    if (!foundScript) {
        fwprintf(stderr, L"[EGL Error] No se encontro 'egl.py' en las carpetas cercanas a: %ls\n", exePath);
        return 1;
    }

    // 2. Localizar intérprete de Python
    wchar_t pythonExe[MAX_PATH];
    pythonExe[0] = L'\0';

    // Prioridad A: python/python.exe embebido en la instalación
    wchar_t embedPython[MAX_PATH];
    swprintf(embedPython, MAX_PATH, L"%ls\\python\\python.exe", rootDir);
    if (file_exists(embedPython)) {
        wcscpy(pythonExe, embedPython);
    }

    // Prioridad B: .egl/python/python.exe
    if (pythonExe[0] == L'\0') {
        wchar_t dotEglPython[MAX_PATH];
        swprintf(dotEglPython, MAX_PATH, L"%ls\\.egl\\python\\python.exe", rootDir);
        if (file_exists(dotEglPython)) {
            wcscpy(pythonExe, dotEglPython);
        }
    }

    // Prioridad C: python.exe del sistema
    if (pythonExe[0] == L'\0') {
        wchar_t searchPath[MAX_PATH];
        DWORD res = SearchPathW(NULL, L"python.exe", NULL, MAX_PATH, searchPath, NULL);
        if (res > 0 && file_exists(searchPath)) {
            wcscpy(pythonExe, searchPath);
        }
    }

    if (pythonExe[0] == L'\0') {
        fwprintf(stderr, L"[EGL Error] No se encontro un interprete de Python 3.13+ instalado.\n");
        fwprintf(stderr, L"Ejecuta el instalador de Easy-C para configurar el entorno automaticamente.\n");
        return 1;
    }

    // 3. Construir la línea de comandos
    // Longitud estimada
    size_t cmdLen = wcslen(pythonExe) + wcslen(scriptPath) + 64;
    for (int i = 1; i < argc; i++) {
        cmdLen += wcslen(argv[i]) * 2 + 4;
    }

    wchar_t* cmdLine = (wchar_t*)malloc(cmdLen * sizeof(wchar_t));
    if (!cmdLine) {
        fwprintf(stderr, L"[EGL Error] Memoria insuficiente.\n");
        return 1;
    }

    swprintf(cmdLine, cmdLen, L"\"%ls\" \"%ls\"", pythonExe, scriptPath);
    for (int i = 1; i < argc; i++) {
        wcscat(cmdLine, L" ");
        int hasSpace = (wcschr(argv[i], L' ') != NULL || wcschr(argv[i], L'\t') != NULL || wcslen(argv[i]) == 0);
        if (hasSpace) wcscat(cmdLine, L"\"");
        wcscat(cmdLine, argv[i]);
        if (hasSpace) wcscat(cmdLine, L"\"");
    }

    // 4. Iniciar proceso hijo
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    BOOL success = CreateProcessW(
        NULL,
        cmdLine,
        NULL,
        NULL,
        TRUE,
        0,
        NULL,
        NULL,
        &si,
        &pi
    );

    free(cmdLine);

    if (!success) {
        DWORD err = GetLastError();
        fwprintf(stderr, L"[EGL Error] Fallo al iniciar Easy-C (Error %lu)\n", err);
        return 1;
    }

    // 5. Esperar a que el proceso termine y devolver su código de salida exacto
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD exitCode = 0;
    GetExitCodeProcess(pi.hProcess, &exitCode);

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    return (int)exitCode;
}
