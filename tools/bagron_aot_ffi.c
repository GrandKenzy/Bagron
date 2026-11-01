/*
 * ABI mínimo para consumir el driver GIR de Gram desde Python.
 *
 * El wrapper no analiza semántica ni emite LLVM: solo expone source -> GIR y
 * la liberación del blob que asigna gram_compile_source_to_ir().
 */
#include "gram_driver.h"

#include <stdint.h>
#include <string.h>

#if defined(_WIN32)
#define BAGRON_EXPORT __declspec(dllexport)
#else
#define BAGRON_EXPORT __attribute__((visibility("default")))
#endif

BAGRON_EXPORT int bagron_compile_source_to_gir(
    const char *source,
    size_t source_len,
    uint8_t **out_data,
    size_t *out_size,
    uint32_t *out_line,
    uint32_t *out_column,
    uint32_t *out_offset,
    char *out_message,
    size_t out_message_size
) {
    if (!out_data || !out_size) return GRAM_DRIVER_ERR_ARGS;

    *out_data = NULL;
    *out_size = 0;
    GramDriverError error;
    memset(&error, 0, sizeof(error));
    GramIrBlob blob;
    blob.data = NULL;
    blob.size = 0;
    GramDriverStatus status = gram_compile_source_to_ir(
        source,
        source_len,
        &blob,
        &error
    );

    if (out_line) *out_line = error.line;
    if (out_column) *out_column = error.column;
    if (out_offset) *out_offset = error.offset;
    if (out_message && out_message_size > 0) {
        size_t message_len = strlen(error.message);
        if (message_len >= out_message_size) message_len = out_message_size - 1;
        memcpy(out_message, error.message, message_len);
        out_message[message_len] = '\0';
    }

    if (status != GRAM_DRIVER_OK) {
        gram_ir_blob_free(&blob);
        return (int)status;
    }
    *out_data = blob.data;
    *out_size = blob.size;
    return GRAM_DRIVER_OK;
}

BAGRON_EXPORT void bagron_free_gir(uint8_t *data) {
    GramIrBlob blob;
    blob.data = data;
    blob.size = 0;
    gram_ir_blob_free(&blob);
}
