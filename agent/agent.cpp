#include <iostream>
#include <vector>
#include <string>
#include <sys/socket.h>
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
        ssize_t bytes_read  = recv(sock, buffer + total_read, size - total_read, 0);
        if (bytes_read <= 0) return false;
        total_read += bytes_read;
    }
    return true;
}

int main() {
    const char* server_ip = "127.0.0.1";
    int port = 9001;

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        std::cerr << "Couldn't create socket\n";
        return 1;
    }

    sockaddr_in server_addr{};
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    inet_pton(AF_INET, server_ip, &server_addr.sin_addr);

    std::cout << "Connecting to the server...\n";
    if (connect(sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        std::cerr << "Connection failed\n";
        close(sock);
        return 1;
    }
    std::cout << "Connected\n";

    PacketHeader header{};
    if (!read_exact(sock, reinterpret_cast<uint8_t*>(&header), sizeof(header))) {
        std::cerr << "Error during receiving header!\n";
        close(sock);
        return 1;
    }

    header.command_id = ntohl(header.command_id);
    header.data_len = ntohl(header.data_len);

    std::cout << "Received header: ID = " << header.command_id << " len = " << header.data_len << " bytes\n";

    if (header.data_len > 0) {
        std::vector<uint8_t> payload_buffer(header.data_len);
        if (!read_exact(sock, payload_buffer.data(), header.data_len)) {
            std::cerr << "Error during receiving data\n";
            close(sock);
            return 1;
        }

        std::string command(payload_buffer.begin(), payload_buffer.end());
        std::cout << "Command has been executed: " << command << "\n";

        std::string mock_reply = "ACK: Received command " + command;
        send(sock, mock_reply.c_str(), mock_reply.size(), 0);

    }

    close(sock);
    return 0;
}