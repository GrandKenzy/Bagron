// Referencia C del benchmark comparable de redireccion de Bagron.
// El recorrido observable se realiza fuera de la ventana medida, igual que en Bagron.

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
    char record[64];
    int64_t samples[SAMPLES];
    int64_t best = 0;

    for (uint32_t warmup = 0; warmup < 5; ++warmup) {
        size_t output_position = 0;
        int64_t value = 123456789;
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            size_t written = build_record(record, value++);
            for (size_t copy_index = 0; copy_index < written; ++copy_index) {
                output[output_position++] = record[copy_index];
            }
        }
        (void)start;
        consume_buffer(output, output_position);
    }
    for (uint32_t sample = 0; sample < SAMPLES; ++sample) {
        size_t output_position = 0;
        int64_t value = 123456789;
        int64_t start = time_ticks();
        for (uint32_t index = 0; index < iterations; ++index) {
            size_t written = build_record(record, value++);
            for (size_t copy_index = 0; copy_index < written; ++copy_index) {
                output[output_position++] = record[copy_index];
            }
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
            size_t written = build_record(record, value++);
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
            size_t written = build_record(record, value++);
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
