import socket
import struct 

HOST = '127.0.0.1'
PORT = 9001

def receive_exact(conn, size):
    buffer = b""
    while len(buffer) < size:
        chunk = conn.recv(size - len(buffer))
        if not chunk:
            return None
        buffer += chunk
    return buffer

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"Listening for {HOST}:{PORT}")
    
    conn, addr = server.accept()
    print(f"Agent connection: {addr}")
    
    print("==== PYLON ====")
    
    try:
        while True:
            cmd = input("pylon >")
            
            if not cmd:
                continue
            
            if cmd in ['exit', 'quit']:
                header = struct.pack("!II", 4, 0)
                conn.sendall(header)
                print("Closing session")
                break
            

            payload = cmd.encode()
            header = struct.pack("!II", 1, len(payload)) # 1 - shell execution
            conn.sendall(header + payload)
            print(f'Sent {cmd}')
                    
            resp_header_raw = receive_exact(conn, 8)
            if not resp_header_raw:
                print("Agent disconnected")
                return
            
            resp_id, resp_len = struct.unpack("!II", resp_header_raw)
            print(f"Response header: ID={resp_id}, len={resp_len} bytes")
            
            if resp_len > 0:
                result_raw = receive_exact(conn, resp_len)
                print(f"Response:\n" + "-"*30)
                print(result_raw.decode(errors='ignore').strip())
                print("-" * 30)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
        server.close()
    
if __name__ == "__main__":
    main()