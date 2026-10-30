// Referencia C del benchmark comparable de redireccion de Bagron.
// La serializacion escribe directamente en la region destino; el recorrido
// observable se realiza fuera de la ventana medida, igual que en Bagron.

#define WIN32_LEAN_AND_MEAN

#include <windows.h>

#include <stdint.h>
#include <stdio.h>

enum { SAMPLES = 10 };

static volatile unsigned char buffer_sink;
static volatile uint32_t control_sink;

static int64_t time_ticks(void) {
    LARGE_INTEGER value;
    QueryPerformanceCounter(&value);
    return value.QuadPart;
}

static size_t serialize_int64_at(
    char *output,
    size_t output_length,
    size_t position,
    int64_t value
) {
    uint64_t magnitude;
    size_t digits = 0;
    size_t required;

    if (position >= output_length) {
        return 0;
    }

    if (value < 0) {
        magnitude = (uint64_t)(-(value + 1)) + 1;
    } else {
        magnitude = (uint64_t)value;
    }

    if (magnitude == 0) {
        digits = 1;
    } else {
        while (magnitude > 0) {
            magnitude /= 10;
            digits += 1;
        }
    }

    required = digits + (value < 0 ? 1 : 0) + 1;
    if (required > output_length - position) {
        return 0;
    }
    if (value < 0) {
        output[position++] = '-';
    }

    size_t write_position = position + digits - 1;
    magnitude = value < 0
        ? (uint64_t)(-(value + 1)) + 1
        : (uint64_t)value;
    if (magnitude == 0) {
        output[write_position] = '0';
    } else {
        while (magnitude > 0) {
            output[write_position--] = (char)('0' + magnitude % 10);
            magnitude /= 10;
        }
    }
    output[position + digits] = '\0';
    return digits + (value < 0 ? 1 : 0);
}

static size_t build_record(
    char *output,
    size_t output_length,
    size_t position,
    int64_t value
) {
    if (position >= output_length || output_length - position < 9) {
        return 0;
    }
    output[position++] = 'v';
    output[position++] = 'a';
    output[position++] = 'l';
    output[position++] = 'u';
    output[position++] = 'e';
    output[position++] = '=';
    size_t written = serialize_int64_at(output, output_length, position, value);
    if (written == 0) {
        return 0;
    }
    position += written;
    output[position++] = '\n';
    output[position] = '\0';
    return position;
}

__declspec(noinline)
static void consume_buffer(const char *buffer, size_t length) {
    for (size_t index = 0; index < length; ++index) {
        buffer_sink = (unsigned char)buffer[index];
    }
}

static int64_t median_ticks(int64_t samples[SAMPLES]) {
    for (size_t left = 0; left < SAMPLES; ++left) {
        for (size_t right = left + 1; right < SAMPLES; ++right) {
            if (samples[right] < samples[left]) {
                int64_t temporary = samples[left];
                samples[left] = samples[right];
                samples[right] = temporary;
            }
        }
    }
    return (samples[4] + samples[5]) / 2;
}

static int64_t measure_control(uint32_t iterations, int64_t *minimum) {
    int64_t samples[SAMPLES];
    int64_t best = 0;

    for (uint32_t warmup = 0; warmup < 5; ++warmup) {
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            control_sink ^= index;
        }
        (void)start;
    }
    for (uint32_t sample = 0; sample < SAMPLES; ++sample) {
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            control_sink ^= index;
        }
        samples[sample] = time_ticks() - start;
        if (sample == 0 || samples[sample] < best) {
            best = samples[sample];
        }
    }
    *minimum = best;
    return median_ticks(samples);
}

static int64_t measure_buffer(uint32_t iterations, int64_t *minimum) {
    char output[32768];
    int64_t samples[SAMPLES];
    int64_t best = 0;

    for (uint32_t warmup = 0; warmup < 5; ++warmup) {
        size_t output_position = 0;
        int64_t value = 123456789;
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            output_position = build_record(
                output, sizeof output, output_position, value++
            );
        }
        (void)start;
        consume_buffer(output, output_position);
    }
    for (uint32_t sample = 0; sample < SAMPLES; ++sample) {
        size_t output_position = 0;
        int64_t value = 123456789;
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            output_position = build_record(
                output, sizeof output, output_position, value++
            );
        }
        samples[sample] = time_ticks() - start;
        consume_buffer(output, output_position);
        if (sample == 0 || samples[sample] < best) {
            best = samples[sample];
        }
    }
    *minimum = best;
    return median_ticks(samples);
}

static int64_t measure_file(uint32_t iterations, int64_t *minimum) {
    static const char path[] = "benchmark_redirect.c.out";
    char record[64];
    int64_t samples[SAMPLES];
    int64_t best = 0;

    for (uint32_t warmup = 0; warmup < 5; ++warmup) {
        int64_t value = 123456789;
        HANDLE handle = CreateFileA(
            path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
            FILE_ATTRIBUTE_NORMAL, NULL
        );
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            size_t written = build_record(record, sizeof record, 0, value++);
            WriteFile(handle, record, (DWORD)written, NULL, NULL);
        }
        (void)start;
        CloseHandle(handle);
    }
    for (uint32_t sample = 0; sample < SAMPLES; ++sample) {
        int64_t value = 123456789;
        HANDLE handle = CreateFileA(
            path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
            FILE_ATTRIBUTE_NORMAL, NULL
        );
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            size_t written = build_record(record, sizeof record, 0, value++);
            WriteFile(handle, record, (DWORD)written, NULL, NULL);
        }
        samples[sample] = time_ticks() - start;
        CloseHandle(handle);
        if (sample == 0 || samples[sample] < best) {
            best = samples[sample];
        }
    }
    *minimum = best;
    return median_ticks(samples);
}

static void report(
    const char *label,
    int64_t minimum,
    int64_t median,
    int64_t iterations
) {
    fprintf(
        stderr,
        "%s min_ticks=%lld median_ticks=%lld per_call_ticks=%lld\n",
        label,
        (long long)minimum,
        (long long)median,
        (long long)(median / iterations)
    );
}

int main(void) {
    const uint32_t iterations = 1000;
    int64_t minimum;
    int64_t median;

    median = measure_control(iterations, &minimum);
    report("control", minimum, median, iterations);
    median = measure_buffer(iterations, &minimum);
    report("buffer", minimum, median, iterations);
    median = measure_file(iterations, &minimum);
    report("file", minimum, median, iterations);
    return 0;
}
