from pathlib import Path

import pytest

from sb_manager.adapters.proc_listeners import ProcListenerSource
from sb_manager.seams.listener_source import (
    ListenerEndpoint,
    ListenerInspectionError,
    ListenerTransport,
)

HEADER = "  sl  local_address rem_address   st tx_queue rx_queue tr tm retrnsmt uid timeout inode\n"


def write_table(path: Path, *rows: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + "".join(rows), encoding="ascii")


def row(*, port: int, state: str, inode: int) -> str:
    return (
        f"  0: 00000000000000000000000000000000:{port:04X} "
        f"00000000000000000000000000000000:0000 {state} "
        f"00000000:00000000 00:00000000 00000000 0 0 {inode}\n"
    )


def add_process(proc_root: Path, *, pid: int, name: str, inode: int) -> None:
    process = proc_root / str(pid)
    fd_directory = process / "fd"
    fd_directory.mkdir(parents=True)
    (process / "comm").write_text(f"{name}\n", encoding="utf-8")
    (fd_directory / "7").symlink_to(f"socket:[{inode}]")


def empty_other_tables(proc_root: Path) -> None:
    for name in ("tcp6", "udp", "udp6"):
        write_table(proc_root / "net" / name)


def test_reads_only_requested_listeners_and_resolves_process_owners(tmp_path: Path) -> None:
    write_table(
        tmp_path / "net" / "tcp",
        row(port=4433, state="0A", inode=101),
        row(port=9000, state="01", inode=102),
        row(port=9999, state="0A", inode=103),
    )
    empty_other_tables(tmp_path)
    add_process(tmp_path, pid=123, name="sing-box", inode=101)
    source = ProcListenerSource(proc_root=tmp_path)
    requested = ListenerEndpoint(port=4433, transport=ListenerTransport.TCP)

    inspection = source.inspect((requested,))

    assert len(inspection.observations) == 1
    observed = inspection.observations[0]
    assert observed.endpoint == requested
    assert observed.ownership_complete is True
    assert [(owner.pid, owner.process_name) for owner in observed.owners] == [(123, "sing-box")]


def test_combines_ipv4_and_ipv6_socket_owners_for_one_endpoint(tmp_path: Path) -> None:
    write_table(tmp_path / "net" / "tcp", row(port=4433, state="0A", inode=101))
    write_table(tmp_path / "net" / "tcp6", row(port=4433, state="0A", inode=202))
    write_table(tmp_path / "net" / "udp")
    write_table(tmp_path / "net" / "udp6")
    add_process(tmp_path, pid=123, name="sing-box", inode=101)
    add_process(tmp_path, pid=456, name="caddy", inode=202)
    source = ProcListenerSource(proc_root=tmp_path)

    inspection = source.inspect((ListenerEndpoint(port=4433, transport=ListenerTransport.TCP),))

    assert [(owner.pid, owner.process_name) for owner in inspection.observations[0].owners] == [
        (123, "sing-box"),
        (456, "caddy"),
    ]


def test_udp_unconnected_socket_is_reported_as_listener(tmp_path: Path) -> None:
    write_table(tmp_path / "net" / "tcp")
    write_table(tmp_path / "net" / "tcp6")
    write_table(tmp_path / "net" / "udp", row(port=8443, state="07", inode=303))
    write_table(tmp_path / "net" / "udp6")
    add_process(tmp_path, pid=789, name="sing-box", inode=303)
    endpoint = ListenerEndpoint(port=8443, transport=ListenerTransport.UDP)

    inspection = ProcListenerSource(proc_root=tmp_path).inspect((endpoint,))

    assert inspection.observations[0].endpoint == endpoint


def test_socket_without_visible_process_keeps_ownership_unknown(tmp_path: Path) -> None:
    write_table(tmp_path / "net" / "tcp", row(port=4433, state="0A", inode=101))
    empty_other_tables(tmp_path)
    endpoint = ListenerEndpoint(port=4433, transport=ListenerTransport.TCP)

    inspection = ProcListenerSource(proc_root=tmp_path).inspect((endpoint,))

    assert inspection.observations[0].owners == ()
    assert inspection.observations[0].ownership_complete is False


def test_process_names_drop_control_characters_before_reaching_diagnostics(
    tmp_path: Path,
) -> None:
    write_table(tmp_path / "net" / "tcp", row(port=4433, state="0A", inode=101))
    empty_other_tables(tmp_path)
    add_process(tmp_path, pid=123, name="worker\x1b[red]", inode=101)
    endpoint = ListenerEndpoint(port=4433, transport=ListenerTransport.TCP)

    inspection = ProcListenerSource(proc_root=tmp_path).inspect((endpoint,))

    assert inspection.observations[0].owners[0].process_name == "worker�[red]"


def test_process_descriptor_scan_budget_degrades_ownership_to_unknown(
    tmp_path: Path,
) -> None:
    write_table(tmp_path / "net" / "tcp", row(port=4433, state="0A", inode=101))
    empty_other_tables(tmp_path)
    add_process(tmp_path, pid=123, name="sing-box", inode=999)
    (tmp_path / "123" / "fd" / "8").symlink_to("socket:[101]")
    endpoint = ListenerEndpoint(port=4433, transport=ListenerTransport.TCP)

    inspection = ProcListenerSource(proc_root=tmp_path, max_descriptors=1).inspect((endpoint,))

    assert inspection.observations[0].ownership_complete is False


def test_unavailable_proc_socket_tables_raise_typed_error(tmp_path: Path) -> None:
    with pytest.raises(ListenerInspectionError, match="Unable to read Linux socket table"):
        ProcListenerSource(proc_root=tmp_path).inspect(
            (ListenerEndpoint(port=4433, transport=ListenerTransport.TCP),)
        )
