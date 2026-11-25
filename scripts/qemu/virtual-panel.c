/* QEMU-only adapter: expose the virtual connector as an embedded panel.
 * The Skyward executable and the kernel's DRM operations remain unchanged.
 */
#include <dlfcn.h>
#include <errno.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdint.h>
#include <sys/ioctl.h>

struct connector_info {
    uint64_t encoders, modes, properties, property_values;
    uint32_t mode_count, property_count, encoder_count, encoder;
    uint32_t id, type, type_id, connection;
    uint32_t width_mm, height_mm, subpixel, padding;
};

static int (*real_ioctl)(int, int, ...);
static pthread_once_t ready = PTHREAD_ONCE_INIT;

static void find_ioctl(void) {
    real_ioctl = (int (*)(int, int, ...))dlsym(RTLD_NEXT, "ioctl");
}

int ioctl(int fd, int request, ...) {
    pthread_once(&ready, find_ioctl);
    if (!real_ioctl) { errno = ENOSYS; return -1; }
    /* SET_MASTER and DROP_MASTER have no third argument. */
    if ((uint32_t)request == 0x641e || (uint32_t)request == 0x641f)
        return real_ioctl(fd, request);
    va_list args;
    va_start(args, request);
    void *argument = va_arg(args, void *);
    va_end(args);
    int result = real_ioctl(fd, request, argument);
    /* DRM_IOCTL_MODE_GETCONNECTOR, Virtual -> EmbeddedDisplayPort. */
    if (result == 0 && (uint32_t)request == 0xc05064a7 && argument) {
        struct connector_info *connector = argument;
        if (connector->type == 15) connector->type = 14;
    }
    return result;
}
