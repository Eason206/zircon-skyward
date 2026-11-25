/* Component tests inside QEMU. No Android init or vendor drivers are started. */
#include <errno.h>
#include <fcntl.h>
#include <linux/loop.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

int qemu_interactive(void);

static void result(const char *name, int code) {
    printf("\nQEMU_TEST_END %s %d\n", name, code);
    fflush(stdout);
}

static int run(const char *name, const char *program, char *const args[]) {
    printf("QEMU_TEST_BEGIN %s\n", name);
    fflush(stdout);
    pid_t child = fork();
    if (child == 0) {
        alarm(20);
        execv(program, args);
        perror(program);
        _exit(127);
    }
    int status = 0;
    int code = 127;
    if (child > 0 && waitpid(child, &status, 0) == child)
        code = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
    result(name, code);
    return code;
}

static int attach_loop(int number, off_t size) {
    char image[64], node[32];
    snprintf(image, sizeof(image), "/qemu/loop%d.img", number);
    snprintf(node, sizeof(node), "/dev/loop%d", number);
    int file = open(image, O_CREAT | O_RDWR | O_TRUNC, 0600);
    if (file < 0 || ftruncate(file, size) != 0) {
        perror("create QEMU test disk");
        if (file >= 0) close(file);
        return -1;
    }
    int loop = open(node, O_RDWR);
    if (loop < 0 || ioctl(loop, LOOP_SET_FD, file) != 0) {
        perror("attach QEMU loop disk");
        close(file);
        if (loop >= 0) close(loop);
        return -1;
    }
    close(file);
    return loop;
}

static void roundtrip(const char *name, const char *node, const char *filesystem) {
    printf("QEMU_TEST_BEGIN %s\n", name);
    fflush(stdout);
    const char *text = "zircon QEMU filesystem roundtrip\n";
    int code = 1;
    mkdir("/qemu/mount", 0755);
    if (mount(node, "/qemu/mount", filesystem, 0, NULL) == 0) {
        FILE *file = fopen("/qemu/mount/proof.txt", "w");
        if (file) {
            fputs(text, file);
            fclose(file);
            sync();
            if (umount("/qemu/mount") == 0 && mount(node, "/qemu/mount", filesystem, 0, NULL) == 0) {
                char read_back[128] = {0};
                file = fopen("/qemu/mount/proof.txt", "r");
                if (file) {
                    fread(read_back, 1, sizeof(read_back) - 1, file);
                    fclose(file);
                    code = strcmp(read_back, text) != 0;
                    if (!code) printf("persisted bytes matched after unmount and remount\n");
                }
            }
        }
        umount("/qemu/mount");
    }
    if (code) perror("QEMU filesystem roundtrip");
    result(name, code);
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    mkdir("/proc", 0755);
    mkdir("/sys", 0755);
    mkdir("/tmp", 0777);
    mount("proc", "/proc", "proc", 0, NULL);
    mount("sysfs", "/sys", "sysfs", 0, NULL);
    setenv("PATH", "/system/bin", 1);
    setenv("LD_LIBRARY_PATH", "/system/lib64", 1);
    setenv("HOME", "/", 1);
    if (access("/qemu/interactive", F_OK) == 0) return qemu_interactive();
    printf("QEMU_COMPONENT_INIT_STARTED\n");

    int ext4 = attach_loop(0, (off_t)64 << 20);
    int f2fs = attach_loop(1, (off_t)256 << 20);
    int vendor_a = attach_loop(2, (off_t)64 << 20);
    int vendor_b = attach_loop(3, (off_t)64 << 20);
    mkdir("/dev/block", 0755);
    mkdir("/dev/block/by-name", 0755);
    symlink("/dev/loop1", "/dev/block/by-name/userdata");
    symlink("/dev/loop2", "/dev/block/by-name/vendor_boot_a");
    symlink("/dev/loop3", "/dev/block/by-name/vendor_boot_b");
    symlink("/qemu/super-metadata.bin", "/dev/block/by-name/super");

    char *help[] = {"skyward", "--help", NULL};
    char *version[] = {"skyward", "--version", NULL};
    char *info[] = {"skyward", "info", "--config", "/skyward/device.toml", NULL};
    char *identify[] = {"skyward", "identify", "/qemu/skyward.img", NULL};
    char *lp[] = {"skyward", "lp", "--super", "/qemu/super-metadata.bin", "--slot", "0", NULL};
    char *unzip[] = {"unzip", "-p", "/qemu/sample.zip", "hello.txt", NULL};
    char *zstd[] = {"zstd", "-d", "-c", "/qemu/sample.zst", NULL};
    run("cli_help", "/system/bin/recovery", help);
    run("cli_version", "/system/bin/recovery", version);
    run("zircon_config", "/system/bin/recovery", info);
    run("vendor_boot_identify", "/system/bin/recovery", identify);
    run("logical_partition_metadata", "/system/bin/recovery", lp);
    run("unzip_stream", "/system/bin/recovery", unzip);
    run("zstd_stream", "/system/bin/recovery", zstd);

    char *mkext4[] = {"skyward", "mkfs", "/dev/loop0", "ext4", NULL};
    char *ckext4[] = {"e2fsck", "-f", "-n", "/dev/loop0", NULL};
    if (ext4 >= 0) {
        if (run("ext4_format", "/system/bin/recovery", mkext4) == 0) {
            roundtrip("ext4_roundtrip", "/dev/loop0", "ext4");
            run("ext4_fsck", "/first_stage_ramdisk/system/bin/e2fsck", ckext4);
        }
        ioctl(ext4, LOOP_CLR_FD, 0);
        close(ext4);
    }

    char *mkf2fs[] = {"skyward", "mkfs", "/dev/loop1", "f2fs", NULL};
    char *ckf2fs[] = {"fsck.f2fs", "-f", "/dev/loop1", NULL};
    if (f2fs >= 0) {
        if (run("f2fs_format", "/system/bin/recovery", mkf2fs) == 0) {
            roundtrip("f2fs_roundtrip", "/dev/loop1", "f2fs");
            run("f2fs_fsck", "/system/bin/fsck.f2fs", ckf2fs);
        }
        ioctl(f2fs, LOOP_CLR_FD, 0);
        close(f2fs);
    }

    if (vendor_a >= 0) { ioctl(vendor_a, LOOP_CLR_FD, 0); close(vendor_a); }
    if (vendor_b >= 0) { ioctl(vendor_b, LOOP_CLR_FD, 0); close(vendor_b); }

    printf("QEMU_COMPONENT_SUITE_COMPLETE\n");
    sync();
    reboot(RB_POWER_OFF);
    for (;;) pause();
}
