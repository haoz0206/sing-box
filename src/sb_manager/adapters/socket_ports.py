"""Host port observations backed by operating-system sockets."""

import socket
from collections.abc import Collection

MAX_AUTOMATIC_PORT_ATTEMPTS = 128


class SocketPortSource:
    """Probe the same IPv6 wildcard address used by generated inbounds."""

    def is_available(self, port: int) -> bool:
        with self._socket() as candidate:
            try:
                candidate.bind(("::", port))
            except OSError:
                return False
        return True

    def choose_available(self, *, excluded_ports: Collection[int] = ()) -> int:
        excluded = set(excluded_ports)
        for _ in range(MAX_AUTOMATIC_PORT_ATTEMPTS):
            with self._socket() as candidate:
                candidate.bind(("::", 0))
                port = int(candidate.getsockname()[1])
            if port not in excluded:
                return port
        raise OSError("Unable to select an unreserved automatic port")

    @staticmethod
    def _socket() -> socket.socket:
        candidate = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        candidate.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        return candidate
