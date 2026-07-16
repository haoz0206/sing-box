"""Host port observations backed by operating-system sockets."""

import socket


class SocketPortSource:
    """Probe the same IPv6 wildcard address used by generated inbounds."""

    def is_available(self, port: int) -> bool:
        with self._socket() as candidate:
            try:
                candidate.bind(("::", port))
            except OSError:
                return False
        return True

    def choose_available(self) -> int:
        with self._socket() as candidate:
            candidate.bind(("::", 0))
            return int(candidate.getsockname()[1])

    @staticmethod
    def _socket() -> socket.socket:
        candidate = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        candidate.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        return candidate
