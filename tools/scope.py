import os, socket, sys, time
class Scope:
    def __init__(self, host=os.environ.get("SCOPE_HOST", "192.168.1.100"), port=5555, timeout=10):
        self.s = socket.create_connection((host, port), timeout=timeout)
        # Drain anything left over from a previous, interrupted transfer.
        self.s.settimeout(0.5)
        try:
            while self.s.recv(1 << 20): pass
        except socket.timeout:
            pass
        self.s.settimeout(timeout)
    def w(self, cmd):
        self.s.sendall((cmd + "\n").encode())
    def q(self, cmd):
        self.w(cmd)
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = self.s.recv(65536)
            if not chunk: break
            buf += chunk
        return buf.decode(errors="replace").strip()
    def qbin(self, cmd):
        self.w(cmd)
        hdr = b""
        while len(hdr) < 2: hdr += self.s.recv(2 - len(hdr))
        assert hdr[:1] == b"#", hdr
        n = int(hdr[1:2])
        ln = b""
        while len(ln) < n: ln += self.s.recv(n - len(ln))
        total = int(ln)
        data = b""
        while len(data) < total + 1:
            data += self.s.recv(min(1 << 20, total + 1 - len(data)))
        return data[:total]
if __name__ == "__main__":
    sc = Scope()
    for c in sys.argv[1:]:
        print(c, "->", sc.q(c) if "?" in c else (sc.w(c) or "ok"))
