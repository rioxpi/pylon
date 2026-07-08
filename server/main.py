import socket
import struct 

HOST = '127.0.0.1'
PORT = 9001

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"Listening for {HOST}:{PORT}")
    
    conn, addr = server.accept()
    print(f"Agent connection: {addr}")
    
    try:
        payload = b"whoami"
        cmd_id = 1
        data_len = len(payload)
        
        header = struct.pack("!II", cmd_id, data_len)
        conn.sendall(header + payload)
        print(f'Sent ID={cmd_id}, len={data_len}, ({payload})')
        
        response = conn.recv(4096)
        
        print(f"Response: \n{response.decode(errors='ignore')}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
        server.close()
    
if __name__ == "__main__":
    main()