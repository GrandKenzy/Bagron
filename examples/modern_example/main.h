typedef unsigned long long uint64_t;
typedef unsigned int uint32_t;
typedef unsigned short uint16_t;
typedef unsigned char uint8_t;
typedef signed _BitInt(128) int128_t;
typedef unsigned _BitInt(256) uint256_t;
typedef uint64_t size_t, uintptr_t;

_Static_assert(sizeof(uint64_t) == 8, "uint64_t must be 8 bytes");
static_assert(alignof(max_align_t) >= 8);

struct HalDevice;
union HalRegister;
enum HalStatus : uint32_t;

enum [[nodiscard]] HalStatus : uint32_t {
    HAL_OK = 0,
    HAL_BUSY = (1U << 0),
    HAL_TIMEOUT = (1U << 1) | (1U << 2),
    HAL_ERR_MASK = (uint32_t)~0U,
};

typedef int (__stdcall *HalIrqHandler)(struct HalDevice * restrict dev, uint32_t irq_flags);
typedef HalIrqHandler (*HalDispatchTable)[16];

struct __attribute__((aligned(64), packed)) HalDevice {
    _Atomic(uint32_t) ref_count;
    volatile uint32_t mode : 3, : 0, enabled : 1, error_code : 4;
    union {
        uint8_t raw_regs[64];
        struct {
            uintptr_t mmio_base;
            size_t mmio_size;
            _Atomic const void * restrict dma_channel;
        } mapped;
    } io;
    int (*on_reset)(struct HalDevice *self, int hard_reset);
    HalIrqHandler irq_vector[8];
    _Static_assert(sizeof(uintptr_t) >= 4, "pointer size check");
    uint8_t dma_tail[];
};

typedef struct HalDevice HalDevice, *HalDevicePtr, **HalDeviceHandle;

_Alignas(64) _Thread_local static constexpr uint32_t hal_default_lut[4] = {
    [0] = 0x01U,
    [1] = (1U << 4),
    [2] = sizeof(struct HalDevice),
    [3] = (uint32_t)-1,
};

static const struct HalConfig {
    uint32_t version;
    const char *name;
    uint32_t limits[2];
} hal_global_config = {
    .version = 3,
    .name = "EasyC-HAL-" "v3",
    .limits = { [0] = 128, [1] = 4096 },
};

extern typeof(hal_default_lut[0]) hal_active_mask;
extern typeof_unqual(const uint64_t) hal_tick_counter __asm__("__hal_tick_counter");

void (*hal_signal(int sig, void (*handler)(int)))(int);

int (*(*(*hal_query_pipeline(const char * restrict name, void (*cleanup)(void *)))[8])(uint32_t, ...))[4];

int (hal_format_msg)(char buffer[restrict static const 256], size_t max_len, const char * restrict fmt, ...);

void hal_sort_devices(void *base, size_t count, size_t elem_size, int (*compar)(const void *, const void *), uint32_t scratch[const *]);

[[nodiscard, gnu::hot]]
__extension__ __declspec(dllexport)
extern __inline__ enum HalStatus __attribute__((visibility("default")))
hal_device_io_ctl(struct HalDevice * _Atomic restrict dev, uint32_t cmd, void * restrict arg) __asm__("hal_device_io_ctl_v2") __attribute__((nothrow));