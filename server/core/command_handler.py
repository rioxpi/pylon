import os
import select
import struct
import sys
import termios
import tty


class CommandHandler:
    def __init__(self):
        pass

    def receive_exact(self, conn, size):
        buffer = b""
        while len(buffer) < size:
            chunk = conn.recv(size - len(buffer))
            if not chunk:
                return None
            buffer += chunk
        return buffer

    def handle_command(self, command: str, conn):
        print(f"Handling: {command}")
        if command in ["exit", "quit", "drop"]:
            header = struct.pack("!II", 4, 0)
            conn.sendall(header)
            print("Closing session")
        elif command.startswith("upload "):
            try:
                local_path = command.split(" ", 1)[1]
                if not os.path.exists(local_path):
                    print("ERROR: File not found")

                filename = os.path.basename(local_path)
                filename_bytes = filename.encode("utf-8")

                with open(local_path, "rb") as f:
                    file_bytes = f.read()

                payload = (
                    struct.pack("!I", len(filename_bytes)) + filename_bytes + file_bytes
                )
                header = struct.pack("!II", 2, len(payload))

                conn.sendall(header + payload)
                print(f"Sending '{filename}'")

                resp_h = self.receive_exact(conn, 8)
                r_id, r_len = struct.unpack("!II", resp_h)
                msg = self.receive_exact(conn, r_len).decode()
                print(f"Output: {msg}")
            except Exception as e:
                print(f"Error: {e}")
        elif command.startswith("download "):
            try:
                remote_path = command.split(" ", 1)[1]
                payload = remote_path.encode()
                header = struct.pack("!II", 3, len(payload))

                conn.sendall(header + payload)

                resp_h = self.receive_exact(conn, 8)
                if not resp_h:
                    print("No response")

                r_id, r_len = struct.unpack("!II", resp_h)

                if r_id == 5:
                    err_msg = self.receive_exact(conn, r_len).decode()
                    print(f"Agent error {err_msg}")
                elif r_id == 3:
                    file_bytes = self.receive_exact(conn, r_len)
                    out_name = f"downloaded-{os.path.basename(remote_path)}"
                    with open(out_name, "wb") as f:
                        f.write(file_bytes)
                    print(f"Saved as {out_name}")
            except Exception as e:
                print(f"Error: {e}")
        elif command == "shell":
            header = struct.pack("!II", 6, 0)
            conn.sendall(header)
            print("Running shell, type 'exit' to return")

            old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())

            eof_seq = b"\xff\xff\xff\xff_EOF_"
            temp_buffer = b""
            try:
                while True:
                    r, w, x = select.select([conn, sys.stdin], [], [])

                    if conn in r:
                        data = conn.recv(4096)
                        if not data:
                            return

                        temp_buffer += data

                        if eof_seq in temp_buffer:
                            before_eof = temp_buffer.split(eof_seq)[0]
                            if before_eof:
                                sys.stdout.buffer.write(before_eof)
                                sys.stdout.flush()

                            else:
                                sys.stdout.buffer.write(data)
                                sys.stdout.flush()

                                if len(temp_buffer) > len(eof_seq):
                                    temp_buffer = temp_buffer[-len(eof_seq) :]

                            if sys.stdin in r:
                                user_input = os.read(sys.stdin.fileno(), 4096)
                                if not user_input:
                                    return
                                conn.sendall(user_input)
            except Exception as e:
                pass
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                print("Session ended")

        payload = command.encode()
        header = struct.pack("!II", 1, len(payload))  # 1 - shell execution
        conn.sendall(header + payload)
        print(f"Sent {command}")

        resp_header_raw = self.receive_exact(conn, 8)
        if not resp_header_raw:
            print("Agent disconnected")
            return

        resp_id, resp_len = struct.unpack("!II", resp_header_raw)
        print(f"Response header: ID={resp_id}, len={resp_len} bytes")

        if resp_len > 0:
            result_raw = self.receive_exact(conn, resp_len)
            print("Response:\n" + "-" * 30)
            print(result_raw.decode(errors="ignore").strip())
            print("-" * 30)
