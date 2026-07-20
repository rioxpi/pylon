import socket
import struct

class NetProtocol:
    def __init__(self, conn) -> None:
        self.conn = conn
    
    def _receive_exact(self, conn, size):
        buffer = b""
        while len(buffer) < size:
            chunk = conn.recv(size - len(buffer))
            if not chunk:
                return None
            buffer += chunk
        return buffer
    
    def execute_command(self, payload : bytes | str, id : int) -> str:
        if isinstance(payload, str):
            payload = payload.encode()
        header = struct.pack("!II", id, len(payload))
        self.conn.sendall(header + payload)
        
        resp_header_raw = self._receive_exact(self.conn, 8)
        if not resp_header_raw:
            print('Agent disconnected')
            return ""
        
        res_id, res_len = struct.unpack("!II", resp_header_raw)
        if res_len > 0:
            result_raw = self._receive_exact(self.conn, res_len)
            return result_raw.decode(errors="ignore").strip()
        
        return ""
        