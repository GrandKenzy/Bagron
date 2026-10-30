// Referencia nativa del benchmark de consola de Bagron.
// Mantiene la misma carga: 5 calentamientos, 10 muestras y 1000 llamadas.

#define WIN32_LEAN_AND_MEAN

#include <windows.h>

#include <stdint.h>
#include <stdio.h>

static HANDLE stdout_handle;
static LARGE_INTEGER qpc_frequency;
static const char write_chars_value[] = "B";
static const unsigned char printb_value[] = {65};

static void initialize_clock(void) {
    QueryPerformanceFrequency(&qpc_frequency);
    stdout_handle = GetStdHandle(STD_OUTPUT_HANDLE);
}

static int64_t time_ticks(void) {
    LARGE_INTEGER value;
    QueryPerformanceCounter(&value);
    return value.QuadPart;
}

static int64_t time_us(int64_t start, int64_t end) {
    int64_t elapsed = end - start;
    int64_t seconds;
    int64_t remainder;

    if (elapsed < 0 || qpc_frequency.QuadPart <= 0) {
        return 0;
    }
    seconds = elapsed / qpc_frequency.QuadPart;
    remainder = elapsed % qpc_frequency.QuadPart;
    return seconds * 1000000
        + (remainder * 1000000) / qpc_frequency.QuadPart;
}

static void write_stdout(const void *buffer, size_t count) {
    if (count == 0 || count > UINT32_MAX) {
        return;
    }
    WriteFile(stdout_handle, buffer, (DWORD)count, NULL, NULL);
}

static void write_chars(const char *buffer, size_t count) {
    write_stdout(buffer, count);
}

static void printb_raw(const unsigned char *buffer, size_t count) {
    write_stdout(buffer, count);
}

static void printb_hex(const unsigned char *buffer, size_t count) {
    static const char digits[] = "0123456789ABCDEF";
    char encoded[512];
    size_t position = 0;

    for (size_t index = 0; index < count; ++index) {
        unsigned char value = buffer[index];
        encoded[position++] = digits[value / 16];
        encoded[position++] = digits[value % 16];
        if (position == sizeof(encoded)) {
            write_stdout(encoded, position);
            position = 0;
        }
    }
    write_stdout(encoded, position);
}

static void write_text(const char *text) {
    write_stdout(text, 1);
}

static int64_t measure_empty_loop(uint32_t iterations) {
    volatile uint32_t guard = 0;
    int64_t total = 0;

    for (uint32_t warmup = 0; warmup < 5; ++warmup) {
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            guard ^= index;
        }
        (void)time_ticks();
        (void)start;
    }
    for (uint32_t sample = 0; sample < 10; ++sample) {
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            guard ^= index;
        }
        total += time_us(start, time_ticks());
    }
    return total / 10;
}

#define MEASURE_OPERATION(NAME, BODY) \
    static int64_t measure_##NAME( \
        uint32_t iterations, int64_t loop_cost, int64_t *minimum \
    ) { \
        int64_t total = 0; \
        int64_t best = 0; \
        for (uint32_t warmup = 0; warmup < 5; ++warmup) { \
            int64_t start = time_ticks(); \
            for (uint32_t index = 0; index < iterations; ++index) { \
                BODY \
            } \
            (void)time_ticks(); \
            (void)start; \
        } \
        for (uint32_t sample = 0; sample < 10; ++sample) { \
            int64_t start = time_ticks(); \
            for (uint32_t index = 0; index < iterations; ++index) { \
                BODY \
            } \
            int64_t elapsed = time_us(start, time_ticks()); \
            elapsed = elapsed > loop_cost ? elapsed - loop_cost : 0; \
            if (sample == 0 || elapsed < best) { \
                best = elapsed; \
            } \
            total += elapsed; \
        } \
        *minimum = best; \
        return total / 10; \
    }

MEASURE_OPERATION(write_chars, {
    write_chars(write_chars_value, 1);
})

MEASURE_OPERATION(printb_raw, {
    printb_raw(printb_value, 1);
})

MEASURE_OPERATION(printb_hex, {
    printb_hex(printb_value, 1);
})

MEASURE_OPERATION(write_text, {
    write_text("B");
})

static void report(
    const char *label,
    int64_t minimum,
    int64_t average,
    int64_t iterations
) {
    fprintf(
        stderr,
        "%s min_us=%lld avg_us=%lld per_call_us=%lld\n",
        label,
        (long long)minimum,
        (long long)average,
        (long long)(average / iterations)
    );
}

int main(void) {
    const uint32_t iterations = 1000;
    int64_t loop_cost;
    int64_t minimum = 0;
    int64_t average;

    initialize_clock();
    loop_cost = measure_empty_loop(iterations);
    fprintf(stderr, "empty_loop_avg_us=%lld\n", (long long)loop_cost);

    average = measure_write_chars(iterations, loop_cost, &minimum);
    report("write_chars", minimum, average, iterations);
    average = measure_printb_raw(iterations, loop_cost, &minimum);
    report("printb_raw", minimum, average, iterations);
    average = measure_printb_hex(iterations, loop_cost, &minimum);
    report("printb_hex", minimum, average, iterations);
    average = measure_write_text(iterations, loop_cost, &minimum);
    report("write_text", minimum, average, iterations);
    return 0;
}
