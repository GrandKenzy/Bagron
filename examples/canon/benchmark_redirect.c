// Referencia C del benchmark de redireccion de Bagron.
// Construye los mismos registros en un buffer y en un archivo Win32.

#define WIN32_LEAN_AND_MEAN

#include <windows.h>

#include <stdint.h>
#include <stdio.h>

static LARGE_INTEGER qpc_frequency;
static volatile unsigned char buffer_sink;

static void initialize_clock(void) {
    QueryPerformanceFrequency(&qpc_frequency);
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

static size_t serialize_int64(char *output, int64_t value) {
    uint64_t magnitude;
    size_t digits = 0;
    size_t position;

    if (value < 0) {
        output[0] = '-';
        magnitude = (uint64_t)(-(value + 1)) + 1;
        position = 1;
    } else {
        magnitude = (uint64_t)value;
        position = 0;
    }

    if (magnitude == 0) {
        output[position++] = '0';
    } else {
        while (magnitude > 0) {
            output[position + digits] = (char)('0' + magnitude % 10);
            magnitude /= 10;
            digits += 1;
        }
        for (size_t left = position; left < position + digits / 2; ++left) {
            size_t right = position + digits - 1 - (left - position);
            char temporary = output[left];
            output[left] = output[right];
            output[right] = temporary;
        }
        position += digits;
    }
    output[position] = '\0';
    return position;
}

static size_t build_record(char *output, int64_t value) {
    static const char prefix[] = "value=";
    char digits[32];
    size_t position = 0;
    size_t digit_index = 0;

    while (prefix[digit_index] != '\0') {
        output[position++] = prefix[digit_index++];
    }
    serialize_int64(digits, value);
    digit_index = 0;
    while (digits[digit_index] != '\0') {
        output[position++] = digits[digit_index++];
    }
    output[position++] = '\n';
    output[position] = '\0';
    return position;
}

__declspec(noinline)
static void consume_buffer(const char *buffer, size_t length) {
    unsigned char checksum = 0;
    for (size_t index = 0; index < length; ++index) {
        checksum ^= (unsigned char)buffer[index];
    }
    buffer_sink ^= checksum;
}

static int64_t measure_empty_loop(uint32_t iterations) {
    volatile uint32_t guard = 0;
    int64_t total = 0;

    for (uint32_t warmup = 0; warmup < 5; ++warmup) {
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            guard ^= index;
        }
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

static int64_t measure_buffer(
    uint32_t iterations,
    int64_t loop_cost,
    int64_t *minimum
) {
    char output[32768];
    char record[64];
    const int64_t value = 123456789;
    int64_t total = 0;
    int64_t best = 0;

    for (uint32_t warmup = 0; warmup < 5; ++warmup) {
        size_t output_position = 0;
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            size_t written = build_record(record, value);
            for (size_t copy_index = 0; copy_index < written; ++copy_index) {
                output[output_position++] = record[copy_index];
            }
        }
        consume_buffer(output, output_position);
        (void)start;
    }
    for (uint32_t sample = 0; sample < 10; ++sample) {
        size_t output_position = 0;
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            size_t written = build_record(record, value);
            for (size_t copy_index = 0; copy_index < written; ++copy_index) {
                output[output_position++] = record[copy_index];
            }
        }
        int64_t elapsed = time_us(start, time_ticks());
        consume_buffer(output, output_position);
        elapsed = elapsed > loop_cost ? elapsed - loop_cost : 0;
        if (sample == 0 || elapsed < best) {
            best = elapsed;
        }
        total += elapsed;
    }
    *minimum = best;
    return total / 10;
}

static int64_t measure_file(
    uint32_t iterations,
    int64_t loop_cost,
    int64_t *minimum
) {
    static const char path[] = "benchmark_redirect.c.out";
    char record[64];
    const int64_t value = 123456789;
    int64_t total = 0;
    int64_t best = 0;

    for (uint32_t warmup = 0; warmup < 5; ++warmup) {
        HANDLE handle = CreateFileA(
            path,
            GENERIC_WRITE,
            0,
            NULL,
            CREATE_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            NULL
        );
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            size_t written = build_record(record, value);
            WriteFile(handle, record, (DWORD)written, NULL, NULL);
        }
        (void)start;
        CloseHandle(handle);
    }
    for (uint32_t sample = 0; sample < 10; ++sample) {
        HANDLE handle = CreateFileA(
            path,
            GENERIC_WRITE,
            0,
            NULL,
            CREATE_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            NULL
        );
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            size_t written = build_record(record, value);
            WriteFile(handle, record, (DWORD)written, NULL, NULL);
        }
        int64_t elapsed = time_us(start, time_ticks());
        CloseHandle(handle);
        elapsed = elapsed > loop_cost ? elapsed - loop_cost : 0;
        if (sample == 0 || elapsed < best) {
            best = elapsed;
        }
        total += elapsed;
    }
    *minimum = best;
    return total / 10;
}

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
    int64_t minimum;
    int64_t average;

    initialize_clock();
    loop_cost = measure_empty_loop(iterations);
    fprintf(stderr, "empty_loop_avg_us=%lld\n", (long long)loop_cost);
    average = measure_buffer(iterations, loop_cost, &minimum);
    report("buffer", minimum, average, iterations);
    average = measure_file(iterations, loop_cost, &minimum);
    report("file", minimum, average, iterations);
    return 0;
}
