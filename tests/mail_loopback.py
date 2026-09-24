"""Loopback IMAP, POP3, and SMTP for the stdlib client. Not a public server."""

from __future__ import annotations

import base64
import re
import socket
import threading


class LoopbackMail:
    def __init__(self, *, user: str, secret: str, messages: list[bytes]) -> None:
        self.user = user
        self.secret = secret
        self.messages = list(messages)
        self.sent: list[bytes] = []
        self.imap_port = 0
        self.pop3_port = 0
        self.smtp_port = 0
        self._sockets: list[socket.socket] = []

    def start(self) -> "LoopbackMail":
        self.imap_port = self._serve(self._imap)
        self.pop3_port = self._serve(self._pop3)
        self.smtp_port = self._serve(self._smtp)
        return self

    def close(self) -> None:
        for sock in self._sockets:
            try:
                sock.close()
            except OSError:
                pass

    def _serve(self, handler) -> int:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(8)
        sock.settimeout(0.4)
        self._sockets.append(sock)
        port = int(sock.getsockname()[1])
        threading.Thread(target=self._accept, args=(sock, handler), daemon=True).start()
        return port

    def _accept(self, sock: socket.socket, handler) -> None:
        while True:
            try:
                conn, _addr = sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            threading.Thread(target=self._run, args=(conn, handler), daemon=True).start()

    def _run(self, conn: socket.socket, handler) -> None:
        try:
            handler(conn)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _imap(self, conn: socket.socket) -> None:
        reader = conn.makefile("rb")

        def send(line: str) -> None:
            conn.sendall(line.encode("utf-8") + b"\r\n")

        def read() -> str | None:
            line = reader.readline()
            if not line:
                return None
            return line.decode("utf-8", errors="replace").rstrip("\r\n")

        send("* OK rpmail loopback ready")
        authed = False
        while True:
            line = read()
            if line is None:
                return
            parts = line.split(" ", 2)
            if len(parts) < 2:
                continue
            tag, cmd = parts[0], parts[1].upper()
            rest = parts[2] if len(parts) > 2 else ""
            if cmd == "CAPABILITY":
                send("* CAPABILITY IMAP4rev1")
                send(f"{tag} OK CAPABILITY completed")
            elif cmd == "LOGIN":
                user, secret = _login_args(rest)
                if user == self.user and secret == self.secret:
                    authed = True
                    send(f"{tag} OK LOGIN completed")
                else:
                    send(f"{tag} NO LOGIN failed")
            elif cmd == "LIST":
                if not authed:
                    send(f"{tag} NO LOGIN required")
                    continue
                send('* LIST (\\HasNoChildren) "/" "INBOX"')
                send('* LIST (\\HasNoChildren) "/" "Sent"')
                send(f"{tag} OK LIST completed")
            elif cmd in ("SELECT", "EXAMINE"):
                if not authed:
                    send(f"{tag} NO LOGIN required")
                    continue
                send(f"* {len(self.messages)} EXISTS")
                send("* 0 RECENT")
                send("* OK [UIDVALIDITY 1] UIDs valid")
                send("* FLAGS (\\Seen)")
                send(f"{tag} OK [READ-WRITE] SELECT completed")
            elif cmd == "SEARCH":
                ids = " ".join(str(i) for i in range(1, len(self.messages) + 1))
                send(f"* SEARCH {ids}".rstrip())
                send(f"{tag} OK SEARCH completed")
            elif cmd == "FETCH":
                if not authed:
                    send(f"{tag} NO LOGIN required")
                    continue
                for index in _fetch_ids(rest, len(self.messages)):
                    payload = self.messages[index - 1]
                    send(f"* {index} FETCH (RFC822 {{{len(payload)}}}")
                    conn.sendall(payload + b")\r\n")
                send(f"{tag} OK FETCH completed")
            elif cmd == "LOGOUT":
                send("* BYE")
                send(f"{tag} OK LOGOUT completed")
                return
            elif cmd == "NOOP":
                send(f"{tag} OK NOOP completed")
            else:
                send(f"{tag} BAD {cmd}")

    def _pop3(self, conn: socket.socket) -> None:
        reader = conn.makefile("rb")

        def send(line: str) -> None:
            conn.sendall(line.encode("utf-8") + b"\r\n")

        def read() -> str | None:
            line = reader.readline()
            if not line:
                return None
            return line.decode("utf-8", errors="replace").rstrip("\r\n")

        send("+OK rpmail pop3 ready")
        authed = False
        user = ""
        while True:
            line = read()
            if line is None:
                return
            cmd, _, arg = line.partition(" ")
            cmd = cmd.upper()
            if cmd == "USER":
                user = arg
                send("+OK")
            elif cmd == "PASS":
                if user == self.user and arg == self.secret:
                    authed = True
                    send("+OK")
                else:
                    send("-ERR")
            elif cmd == "STAT":
                if not authed:
                    send("-ERR")
                    continue
                total = sum(len(m) for m in self.messages)
                send(f"+OK {len(self.messages)} {total}")
            elif cmd == "LIST":
                if not authed:
                    send("-ERR")
                    continue
                send(f"+OK {len(self.messages)} messages")
                for index, payload in enumerate(self.messages, start=1):
                    send(f"{index} {len(payload)}")
                send(".")
            elif cmd == "RETR":
                if not authed:
                    send("-ERR")
                    continue
                index = int(arg)
                payload = self.messages[index - 1]
                send("+OK")
                _write_dotstuffed(conn, payload)
            elif cmd == "QUIT":
                send("+OK")
                return
            elif cmd == "CAPA":
                send("+OK")
                send("USER")
                send(".")
            else:
                send("-ERR")

    def _smtp(self, conn: socket.socket) -> None:
        reader = conn.makefile("rb")

        def send(line: str) -> None:
            conn.sendall(line.encode("utf-8") + b"\r\n")

        def read() -> str | None:
            line = reader.readline()
            if not line:
                return None
            return line.decode("utf-8", errors="replace").rstrip("\r\n")

        send("220 rpmail smtp ready")
        authed = False
        while True:
            line = read()
            if line is None:
                return
            head, _, arg = line.partition(" ")
            cmd = head.upper()
            if cmd in ("EHLO", "HELO"):
                send("250-rpmail")
                send("250 AUTH PLAIN")
            elif cmd == "AUTH":
                token = arg.split(" ", 1)[1] if arg.upper().startswith("PLAIN ") else ""
                if not token and arg.upper() == "PLAIN":
                    send("334")
                    token = read() or ""
                user, secret = _plain_auth(token)
                if user == self.user and secret == self.secret:
                    authed = True
                    send("235 ok")
                else:
                    send("535 denied")
            elif cmd == "MAIL":
                if not authed:
                    send("530 auth")
                    continue
                send("250 ok")
            elif cmd == "RCPT":
                send("250 ok")
            elif cmd == "DATA":
                if not authed:
                    send("530 auth")
                    continue
                send("354 end with dot")
                chunks: list[bytes] = []
                while True:
                    data_line = reader.readline()
                    if not data_line or data_line in (b".\r\n", b".\n"):
                        break
                    if data_line.startswith(b".."):
                        data_line = data_line[1:]
                    chunks.append(data_line)
                self.sent.append(b"".join(chunks))
                send("250 queued")
            elif cmd == "QUIT":
                send("221 bye")
                return
            elif cmd == "RSET":
                send("250 ok")
            elif cmd == "NOOP":
                send("250 ok")
            else:
                send("500 bad")


def _login_args(rest: str) -> tuple[str, str]:
    tokens = [a or b for a, b in re.findall(r'"((?:\\.|[^"\\])*)"|(\S+)', rest)]
    cleaned = [token.replace('\\"', '"').replace("\\\\", "\\") for token in tokens]
    if len(cleaned) < 2:
        return "", ""
    return cleaned[0], cleaned[1]


def _fetch_ids(rest: str, count: int) -> list[int]:
    token = rest.split(" ", 1)[0]
    if ":" in token:
        start_s, end_s = token.split(":", 1)
        start = int(start_s)
        end = count if end_s == "*" else int(end_s)
        return [i for i in range(start, end + 1) if 1 <= i <= count]
    if token.isdigit():
        index = int(token)
        return [index] if 1 <= index <= count else []
    return []


def _write_dotstuffed(conn: socket.socket, payload: bytes) -> None:
    text = payload.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    for line in text.split(b"\r\n"):
        if line.startswith(b"."):
            conn.sendall(b"." + line + b"\r\n")
        else:
            conn.sendall(line + b"\r\n")
    conn.sendall(b".\r\n")


def _plain_auth(token: str) -> tuple[str, str]:
    try:
        raw = base64.b64decode(token.strip())
    except Exception:
        return "", ""
    parts = raw.split(b"\x00")
    if len(parts) < 3:
        return "", ""
    return parts[1].decode("utf-8", errors="replace"), parts[2].decode("utf-8", errors="replace")
