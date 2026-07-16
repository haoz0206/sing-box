"""Linux /proc adapter for listener presence and process ownership evidence."""

from collections import defaultdict
from collections.abc import Collection
from itertools import islice
from pathlib import Path
from unicodedata import category

from sb_manager.seams.listener_source import (
    ListenerEndpoint,
    ListenerInspection,
    ListenerInspectionError,
    ListenerObservation,
    ListenerOwner,
    ListenerTransport,
)

_TABLES = {
    ListenerTransport.TCP: (("tcp", "0A"), ("tcp6", "0A")),
    ListenerTransport.UDP: (("udp", "07"), ("udp6", "07")),
}
_SOCKET_PREFIX = "socket:["
_MIN_SOCKET_TABLE_FIELDS = 10
_MAX_PROCESS_NAME_LENGTH = 64
_DEFAULT_MAX_PROCESSES = 8192
_DEFAULT_MAX_DESCRIPTORS = 131_072


class ProcListenerSource:
    """Read kernel socket tables and map their inodes to visible processes."""

    def __init__(
        self,
        *,
        proc_root: Path = Path("/proc"),
        max_processes: int = _DEFAULT_MAX_PROCESSES,
        max_descriptors: int = _DEFAULT_MAX_DESCRIPTORS,
    ) -> None:
        if max_processes < 1 or max_descriptors < 1:
            raise ValueError("Linux process and descriptor scan limits must be positive")
        self._proc_root = proc_root
        self._max_processes = max_processes
        self._max_descriptors = max_descriptors

    def inspect(self, endpoints: Collection[ListenerEndpoint]) -> ListenerInspection:
        requested = frozenset(endpoints)
        if not requested:
            return ListenerInspection(observations=())
        inodes_by_endpoint: dict[ListenerEndpoint, set[int]] = defaultdict(set)
        try:
            for transport in ListenerTransport:
                transport_endpoints = {
                    endpoint for endpoint in requested if endpoint.transport is transport
                }
                if not transport_endpoints:
                    continue
                for table_name, listener_state in _TABLES[transport]:
                    self._read_table(
                        self._proc_root / "net" / table_name,
                        transport=transport,
                        listener_state=listener_state,
                        requested=transport_endpoints,
                        inodes_by_endpoint=inodes_by_endpoint,
                    )
        except OSError as error:
            raise ListenerInspectionError(f"Unable to read Linux socket table: {error}") from error

        target_inodes = set().union(*inodes_by_endpoint.values())
        owners_by_inode, process_scan_complete = self._read_process_owners(target_inodes)
        observations = []
        for endpoint in sorted(
            inodes_by_endpoint,
            key=lambda item: (item.port, item.transport.value),
        ):
            endpoint_inodes = inodes_by_endpoint[endpoint]
            owners = tuple(
                sorted(
                    {
                        owner
                        for inode in endpoint_inodes
                        for owner in owners_by_inode.get(inode, ())
                    },
                    key=lambda owner: owner.pid,
                )
            )
            all_inodes_resolved = bool(owners) and all(
                owners_by_inode.get(inode) for inode in endpoint_inodes
            )
            observations.append(
                ListenerObservation(
                    endpoint=endpoint,
                    owners=owners,
                    ownership_complete=process_scan_complete and all_inodes_resolved,
                )
            )
        return ListenerInspection(observations=tuple(observations))

    @staticmethod
    def _read_table(
        path: Path,
        *,
        transport: ListenerTransport,
        listener_state: str,
        requested: set[ListenerEndpoint],
        inodes_by_endpoint: dict[ListenerEndpoint, set[int]],
    ) -> None:
        with path.open(encoding="ascii") as table:
            next(table, None)
            for line in table:
                fields = line.split()
                if len(fields) < _MIN_SOCKET_TABLE_FIELDS or fields[3] != listener_state:
                    continue
                try:
                    port = int(fields[1].rsplit(":", maxsplit=1)[1], 16)
                    inode = int(fields[9])
                except (IndexError, ValueError):
                    continue
                endpoint = ListenerEndpoint(port=port, transport=transport)
                if endpoint in requested:
                    inodes_by_endpoint[endpoint].add(inode)

    def _read_process_owners(
        self,
        target_inodes: set[int],
    ) -> tuple[dict[int, set[ListenerOwner]], bool]:
        owners_by_inode: dict[int, set[ListenerOwner]] = defaultdict(set)
        if not target_inodes:
            return owners_by_inode, True
        scan_complete = True
        try:
            processes, process_listing_complete = _bounded_entries(
                self._proc_root,
                limit=self._max_processes,
            )
        except OSError as error:
            raise ListenerInspectionError(f"Unable to inspect Linux processes: {error}") from error
        scan_complete = process_listing_complete
        remaining_descriptors = self._max_descriptors
        for process in processes:
            if not process.name.isdigit():
                continue
            if remaining_descriptors == 0:
                scan_complete = False
                break
            process_complete, descriptors_inspected = self._read_process(
                process,
                target_inodes=target_inodes,
                owners_by_inode=owners_by_inode,
                descriptor_limit=remaining_descriptors,
            )
            remaining_descriptors -= descriptors_inspected
            scan_complete = process_complete and scan_complete
        return owners_by_inode, scan_complete

    @staticmethod
    def _read_process(
        process: Path,
        *,
        target_inodes: set[int],
        owners_by_inode: dict[int, set[ListenerOwner]],
        descriptor_limit: int,
    ) -> tuple[bool, int]:
        try:
            descriptors, listing_complete = _bounded_entries(
                process / "fd",
                limit=descriptor_limit,
            )
        except FileNotFoundError:
            return True, 0
        except OSError:
            return False, 0
        complete = listing_complete
        matched_inodes: set[int] = set()
        for descriptor in descriptors:
            try:
                target = str(descriptor.readlink())
            except FileNotFoundError:
                continue
            except OSError:
                complete = False
                continue
            inode = _socket_inode(target)
            if inode in target_inodes:
                matched_inodes.add(inode)
        if not matched_inodes:
            return complete, len(descriptors)
        try:
            process_name = _sanitize_process_name(
                (process / "comm").read_text(encoding="utf-8").strip()
            )
        except OSError:
            process_name = None
            complete = False
        owner = ListenerOwner(pid=int(process.name), process_name=process_name)
        for inode in matched_inodes:
            owners_by_inode[inode].add(owner)
        return complete, len(descriptors)


def _socket_inode(target: str) -> int | None:
    if not target.startswith(_SOCKET_PREFIX) or not target.endswith("]"):
        return None
    try:
        return int(target[len(_SOCKET_PREFIX) : -1])
    except ValueError:
        return None


def _sanitize_process_name(process_name: str) -> str | None:
    sanitized = "".join(
        "�" if category(character).startswith("C") else character for character in process_name
    )[:_MAX_PROCESS_NAME_LENGTH]
    return sanitized or None


def _bounded_entries(path: Path, *, limit: int) -> tuple[tuple[Path, ...], bool]:
    entries = tuple(islice(path.iterdir(), limit + 1))
    return entries[:limit], len(entries) <= limit
