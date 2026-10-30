//! Win32 reference for `benchmark_redirect.bg`.
//!
//! The protocol intentionally mirrors the Bagron and C versions: serialization
//! writes directly to the destination region, the buffer is consumed after the
//! measured region, and file writes remain inside it.

#![allow(unsafe_op_in_unsafe_fn)]

use std::ffi::c_void;
use std::ptr::{null_mut, read_volatile, write_volatile};

const SAMPLES: usize = 10;
const ITERATIONS: u32 = 1_000;
const GENERIC_WRITE: u32 = 0x4000_0000;
const CREATE_ALWAYS: u32 = 2;
const FILE_ATTRIBUTE_NORMAL: u32 = 0x80;
type Handle = *mut c_void;

static mut BUFFER_SINK: u8 = 0;
static mut CONTROL_SINK: u32 = 0;

unsafe extern "system" {
    fn QueryPerformanceCounter(value: *mut i64) -> i32;
    fn CreateFileA(
        path: *const i8,
        desired_access: u32,
        share_mode: u32,
        security_attributes: *mut c_void,
        creation_disposition: u32,
        flags_and_attributes: u32,
        template_file: Handle,
    ) -> Handle;
    fn CloseHandle(handle: Handle) -> i32;
    fn WriteFile(
        handle: Handle,
        buffer: *const c_void,
        bytes_to_write: u32,
        bytes_written: *mut u32,
        overlapped: *mut c_void,
    ) -> i32;
}

unsafe fn time_ticks() -> i64 {
    let mut value = 0;
    QueryPerformanceCounter(&mut value);
    value
}

fn serialize_int64_at(output: &mut [u8], position: usize, value: i64) -> usize {
    let mut magnitude: u64;
    let mut digits = 0;

    if position >= output.len() {
        return 0;
    }

    if value < 0 {
        magnitude = (-(value + 1)) as u64 + 1;
    } else {
        magnitude = value as u64;
    }

    if magnitude == 0 {
        digits = 1;
    } else {
        while magnitude > 0 {
            magnitude /= 10;
            digits += 1;
        }
    }

    let required = digits + usize::from(value < 0) + 1;
    if required > output.len() - position {
        return 0;
    }
    let mut write_position = position;
    if value < 0 {
        output[write_position] = b'-';
        write_position += 1;
    }
    write_position += digits - 1;
    magnitude = if value < 0 {
        (-(value + 1)) as u64 + 1
    } else {
        value as u64
    };
    if magnitude == 0 {
        output[write_position] = b'0';
    } else {
        while magnitude > 0 {
            output[write_position] = b'0' + (magnitude % 10) as u8;
            magnitude /= 10;
            write_position -= 1;
        }
    }
    output[position + digits + usize::from(value < 0)] = 0;
    digits + usize::from(value < 0)
}

fn build_record(output: &mut [u8], position: usize, value: i64) -> usize {
    if position >= output.len() || output.len() - position < 9 {
        return 0;
    }
    output[position..position + 6].copy_from_slice(b"value=");
    let mut position = position + 6;
    let written = serialize_int64_at(output, position, value);
    if written == 0 {
        return 0;
    }
    position += written;
    output[position] = b'\n';
    position += 1;
    output[position] = 0;
    position
}

#[inline(never)]
unsafe fn consume_buffer(output: &[u8; 32_768], length: usize) {
    for &byte in output.iter().take(length) {
        write_volatile(&raw mut BUFFER_SINK, byte);
    }
}

fn median_ticks(samples: &mut [i64; SAMPLES]) -> i64 {
    for left in 0..SAMPLES {
        for right in left + 1..SAMPLES {
            if samples[right] < samples[left] {
                samples.swap(left, right);
            }
        }
    }
    (samples[4] + samples[5]) / 2
}

unsafe fn measure_control(iterations: u32, minimum: &mut i64) -> i64 {
    let mut samples = [0i64; SAMPLES];
    let mut best = 0;

    for _ in 0..5 {
        let start = time_ticks();
        for index in 0..iterations {
            let current = read_volatile(&raw const CONTROL_SINK);
            write_volatile(&raw mut CONTROL_SINK, current ^ index);
        }
        let _ = start;
    }
    for (sample, slot) in samples.iter_mut().enumerate() {
        let start = time_ticks();
        for index in 0..iterations {
            let current = read_volatile(&raw const CONTROL_SINK);
            write_volatile(&raw mut CONTROL_SINK, current ^ index);
        }
        *slot = time_ticks() - start;
        if sample == 0 || *slot < best {
            best = *slot;
        }
    }
    *minimum = best;
    median_ticks(&mut samples)
}

unsafe fn measure_buffer(iterations: u32, minimum: &mut i64) -> i64 {
    let mut output = [0u8; 32_768];
    let mut samples = [0i64; SAMPLES];
    let mut best = 0;

    for _ in 0..5 {
        let mut output_position = 0;
        let mut value = 123_456_789;
        let start = time_ticks();
        for _ in 0..iterations {
            output_position = build_record(&mut output, output_position, value);
            value += 1;
        }
        let _ = start;
        consume_buffer(&output, output_position);
    }
    for (sample, slot) in samples.iter_mut().enumerate() {
        let mut output_position = 0;
        let mut value = 123_456_789;
        let start = time_ticks();
        for _ in 0..iterations {
            output_position = build_record(&mut output, output_position, value);
            value += 1;
        }
        *slot = time_ticks() - start;
        consume_buffer(&output, output_position);
        if sample == 0 || *slot < best {
            best = *slot;
        }
    }
    *minimum = best;
    median_ticks(&mut samples)
}

unsafe fn measure_file(iterations: u32, minimum: &mut i64) -> i64 {
    let path = b"benchmark_redirect.rs.out\0";
    let mut record = [0u8; 64];
    let mut samples = [0i64; SAMPLES];
    let mut best = 0;

    for _ in 0..5 {
        let mut value = 123_456_789;
        let handle = CreateFileA(
            path.as_ptr() as *const i8,
            GENERIC_WRITE,
            0,
            null_mut(),
            CREATE_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            null_mut(),
        );
        let start = time_ticks();
        for _ in 0..iterations {
            let written = build_record(&mut record, 0, value);
            value += 1;
            WriteFile(
                handle,
                record.as_ptr() as *const c_void,
                written as u32,
                null_mut(),
                null_mut(),
            );
        }
        let _ = start;
        CloseHandle(handle);
    }
    for (sample, slot) in samples.iter_mut().enumerate() {
        let mut value = 123_456_789;
        let handle = CreateFileA(
            path.as_ptr() as *const i8,
            GENERIC_WRITE,
            0,
            null_mut(),
            CREATE_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            null_mut(),
        );
        let start = time_ticks();
        for _ in 0..iterations {
            let written = build_record(&mut record, 0, value);
            value += 1;
            WriteFile(
                handle,
                record.as_ptr() as *const c_void,
                written as u32,
                null_mut(),
                null_mut(),
            );
        }
        *slot = time_ticks() - start;
        CloseHandle(handle);
        if sample == 0 || *slot < best {
            best = *slot;
        }
    }
    *minimum = best;
    median_ticks(&mut samples)
}

fn report(label: &str, minimum: i64, median: i64) {
    eprintln!(
        "{label} min_ticks={minimum} median_ticks={median} per_call_ticks={}",
        median / i64::from(ITERATIONS),
    );
}

fn main() {
    unsafe {
        let mut minimum = 0;
        let median = measure_control(ITERATIONS, &mut minimum);
        report("control", minimum, median);
        let median = measure_buffer(ITERATIONS, &mut minimum);
        report("buffer", minimum, median);
        let median = measure_file(ITERATIONS, &mut minimum);
        report("file", minimum, median);
    }
}
