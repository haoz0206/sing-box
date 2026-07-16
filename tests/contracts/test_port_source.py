import socket

from sb_manager.adapters.socket_ports import SocketPortSource

MAX_TCP_PORT = 65_535


def test_socket_port_source_detects_an_occupied_ipv6_wildcard_port() -> None:
    source = SocketPortSource()
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as occupied_socket:
        occupied_socket.bind(("::", 0))
        occupied_socket.listen()
        occupied_port = int(occupied_socket.getsockname()[1])

        assert not source.is_available(occupied_port)

    assert source.is_available(occupied_port)
    selected_port = source.choose_available()
    assert 1 <= selected_port <= MAX_TCP_PORT
    assert source.is_available(selected_port)
