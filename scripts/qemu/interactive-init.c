/* QEMU-only virtual hardware setup and tablet/keyboard to touch/key bridge. */
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <linux/loop.h>
#include <linux/uinput.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static int load_modules(void) {
    FILE *list = fopen("/qemu/module-order.txt", "r");
    if (!list) return -1;
    char name[256], path[300];
    while (fgets(name, sizeof(name), list)) {
        name[strcspn(name, "\r\n")] = 0;
        snprintf(path, sizeof(path), "/qemu/modules/%s", name);
        int fd = open(path, O_RDONLY);
        if (fd < 0 || (syscall(SYS_finit_module, fd, "", 0) != 0 && errno != EEXIST)) {
            perror(path);
            if (fd >= 0) close(fd);
            fclose(list);
            return -1;
        }
        close(fd);
    }
    fclose(list);
    return 0;
}

static int make_device(const char *name, int touch) {
    int fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
    if (fd < 0) return -1;
    ioctl(fd, UI_SET_EVBIT, EV_SYN);
    ioctl(fd, UI_SET_EVBIT, EV_KEY);
    if (touch) {
        ioctl(fd, UI_SET_KEYBIT, BTN_TOUCH);
        ioctl(fd, UI_SET_EVBIT, EV_ABS);
        ioctl(fd, UI_SET_PROPBIT, INPUT_PROP_DIRECT);
        const int codes[] = {ABS_MT_SLOT, ABS_MT_TRACKING_ID, ABS_MT_POSITION_X, ABS_MT_POSITION_Y};
        const int maxima[] = {0, 65535, 1219, 2711};
        for (int k = 0; k < 4; ++k) {
            ioctl(fd, UI_SET_ABSBIT, codes[k]);
            struct uinput_abs_setup axis = {0};
            axis.code = codes[k];
            axis.absinfo.maximum = maxima[k];
            if (ioctl(fd, UI_ABS_SETUP, &axis) != 0) { close(fd); return -1; }
        }
    } else {
        const int keys[] = {KEY_VOLUMEUP, KEY_VOLUMEDOWN, KEY_POWER, KEY_BACK};
        for (int k = 0; k < 4; ++k) ioctl(fd, UI_SET_KEYBIT, keys[k]);
    }
    struct uinput_setup setup = {0};
    setup.id.bustype = BUS_VIRTUAL;
    setup.id.vendor = 0x1234;
    setup.id.product = touch ? 1 : 2;
    snprintf(setup.name, sizeof(setup.name), "%s", name);
    if (ioctl(fd, UI_DEV_SETUP, &setup) != 0 || ioctl(fd, UI_DEV_CREATE) != 0) {
        close(fd); return -1;
    }
    return fd;
}

static void event(int fd, unsigned short type, unsigned short code, int value) {
    struct input_event input = {0};
    gettimeofday(&input.time, NULL);
    input.type = type; input.code = code; input.value = value;
    if (write(fd, &input, sizeof(input)) != (ssize_t)sizeof(input)) perror("virtual input");
}

static void bridge(int touch, int keys) {
    int tablet = -1, keyboard = -1;
    DIR *dir = opendir("/dev/input");
    if (!dir) _exit(1);
    struct dirent *item;
    while ((item = readdir(dir))) {
        if (strncmp(item->d_name, "event", 5) != 0) continue;
        char path[300], name[128] = {0};
        snprintf(path, sizeof(path), "/dev/input/%s", item->d_name);
        int fd = open(path, O_RDONLY);
        if (fd < 0) continue;
        ioctl(fd, EVIOCGNAME(sizeof(name)), name);
        if (strstr(name, "Virtio Tablet")) tablet = fd;
        else if (strstr(name, "Virtio Keyboard")) keyboard = fd;
        else close(fd);
    }
    closedir(dir);
    if (tablet < 0) { printf("QEMU tablet was not found\n"); _exit(1); }
    struct input_absinfo ax = {0}, ay = {0};
    ioctl(tablet, EVIOCGABS(ABS_X), &ax);
    ioctl(tablet, EVIOCGABS(ABS_Y), &ay);
    struct pollfd wait[] = {{tablet, POLLIN, 0}, {keyboard, POLLIN, 0}};
    int x = 0, y = 0, down = 0, old_down = 0, tracking = 1;
    for (;;) {
        if (poll(wait, 2, -1) <= 0) continue;
        for (int k = 0; k < 2; ++k) {
            if (!(wait[k].revents & POLLIN)) continue;
            struct input_event input;
            if (read(wait[k].fd, &input, sizeof(input)) != (ssize_t)sizeof(input)) continue;
            if (k == 1 && input.type == EV_KEY) {
                int code = input.code == KEY_UP ? KEY_VOLUMEUP : input.code == KEY_DOWN ? KEY_VOLUMEDOWN :
                           input.code == KEY_ENTER ? KEY_POWER : input.code == KEY_ESC ? KEY_BACK : 0;
                if (code) { event(keys, EV_KEY, code, input.value); event(keys, EV_SYN, SYN_REPORT, 0); }
                continue;
            }
            if (k != 0) continue;
            if (input.type == EV_ABS && input.code == ABS_X)
                x = (int)((int64_t)(input.value - ax.minimum) * 1219 / (ax.maximum - ax.minimum));
            if (input.type == EV_ABS && input.code == ABS_Y)
                y = (int)((int64_t)(input.value - ay.minimum) * 2711 / (ay.maximum - ay.minimum));
            if (input.type == EV_KEY && (input.code == BTN_LEFT || input.code == BTN_TOUCH)) down = input.value != 0;
            if (input.type == EV_SYN && input.code == SYN_REPORT && (down || old_down)) {
                event(touch, EV_ABS, ABS_MT_SLOT, 0);
                if (down && !old_down) event(touch, EV_ABS, ABS_MT_TRACKING_ID, tracking++ & 65535);
                if (!down && old_down) event(touch, EV_ABS, ABS_MT_TRACKING_ID, -1);
                event(touch, EV_ABS, ABS_MT_POSITION_X, x);
                event(touch, EV_ABS, ABS_MT_POSITION_Y, y);
                event(touch, EV_KEY, BTN_TOUCH, down);
                event(touch, EV_SYN, SYN_REPORT, 0);
                old_down = down;
            }
        }
    }
}

static int data_disk(void) {
    int file = open("/qemu/userdata.img", O_CREAT | O_RDWR | O_TRUNC, 0600);
    if (file < 0 || ftruncate(file, (off_t)256 << 20) != 0) return -1;
    int loop = open("/dev/loop1", O_RDWR);
    if (loop < 0 || ioctl(loop, LOOP_SET_FD, file) != 0) return -1;
    close(file);
    mkdir("/dev/block", 0755); mkdir("/dev/block/by-name", 0755);
    symlink("/dev/loop1", "/dev/block/by-name/userdata");
    symlink("/qemu/super-metadata.bin", "/dev/block/by-name/super");
    pid_t child = fork();
    if (child == 0) {
        char *args[] = {"skyward", "mkfs", "/dev/loop1", "f2fs", NULL};
        execv("/system/bin/recovery", args); _exit(127);
    }
    int status = 0;
    waitpid(child, &status, 0);
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) return -1;
    mkdir("/data", 0755);
    if (mount("/dev/loop1", "/data", "f2fs", 0, NULL) != 0) return -1;
    mkdir("/data/media", 0755); mkdir("/data/media/0", 0755);
    unlink("/sdcard");
    mkdir("/sdcard", 0755);
    mount("/data/media/0", "/sdcard", NULL, MS_BIND, NULL);
    FILE *demo = fopen("/sdcard/QEMU-demo.txt", "w");
    if (demo) { fputs("Skyward is running in an ARM64 QEMU virt machine.\nThis is a virtual, unencrypted data disk.\n", demo); fclose(demo); }
    return loop;
}

int qemu_interactive(void) {
    printf("QEMU_INTERACTIVE_INIT_STARTED\n");
    if (mount("devtmpfs", "/dev", "devtmpfs", 0, "mode=0755") != 0) { perror("devtmpfs"); return 1; }
    mkdir("/dev/socket", 0755);
    if (load_modules() != 0) return 1;
    mkdir("/vendor/etc", 0755);
    FILE *fstab = fopen("/vendor/etc/fstab.qemu", "w");
    if (fstab) { fputs("/dev/block/by-name/userdata /data f2fs noatime,nosuid,nodev wait,check,formattable,quota\n", fstab); fclose(fstab); }
    if (data_disk() < 0) { perror("virtual userdata"); return 1; }
    mkdir("/metadata", 0755);
    mount("tmpfs", "/metadata", "tmpfs", 0, "mode=0755");
    mkdir("/metadata/skyward", 0755);
    FILE *settings = fopen("/metadata/skyward/settings.json", "w");
    if (settings) {
        fputs("{\"language\":\"zh-Hans\",\"spoken\":\"zh-Hans\",\"file_transfer\":false,\"screen_off\":0,\"time_zone\":\"Asia/Almaty\",\"follow_system_time_zone\":false}\n", settings);
        fclose(settings);
    }
    FILE *epoch = fopen("/qemu/epoch", "r");
    long long seconds = 0;
    if (epoch) { if (fscanf(epoch, "%lld", &seconds) == 1) { struct timespec now = {(time_t)seconds, 0}; clock_settime(CLOCK_REALTIME, &now); } fclose(epoch); }
    int touch = make_device("QEMU Skyward virtual touchscreen", 1);
    int keys = make_device("QEMU Skyward virtual keys", 0);
    if (touch < 0 || keys < 0) { perror("uinput"); return 1; }
    usleep(300000);
    if (fork() == 0) bridge(touch, keys);
    printf("QEMU_VIRTUAL_TOUCH_AND_KEYS_READY\n");
    char *args[] = {"skyward", "ui", "--config", "/skyward/device.toml", "--font", "/skyward/MiSansVF.ttf",
                    "--mono", "/skyward/KirkMono-Regular.ttf", "--simulate-wlan", NULL};
    pid_t child = fork();
    if (child == 0) {
        setenv("LD_PRELOAD", "/qemu/virtual-panel.so", 1);
        execv("/system/bin/recovery", args); perror("Skyward UI"); _exit(127);
    }
    int status = 0;
    waitpid(child, &status, 0);
    printf("QEMU_SKYWARD_UI_EXITED %d\n", status);
    for (;;) pause();
}
