# Snell v6 Preview-Core Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class Snell v6 profiles that can be deployed only with a Snell-capable sing-box Preview core, including safe downgrade prevention and an official Surge client policy payload.

**Architecture:** Extend the existing deep protocol catalog with a Snell v6 vertical slice, then introduce one pure version policy plus an active-core guard shared by every profile mutation service. Bind core-update plans to the desired-state revision so an incompatible Stable target cannot replace a core while an applied Snell profile exists. Deepen connection handoff from URI-only data to typed payloads before adding Snell's Surge policy output.

**Tech Stack:** Python 3.10+, dataclasses and Protocol seams, Textual 8, pytest/pytest-asyncio, Ruff, mypy, setuptools, sing-box `check`, JSON desired state, conventional commits.

**Design spec:** `docs/superpowers/specs/2026-07-18-snell-v6-preview-support-design.md`

**Baseline commit:** `2d6814f`

---

## File and Responsibility Map

### New focused modules

- `src/sb_manager/protocols/snell.py`: pure Snell v6 inbound and Surge policy serialization.
- `src/sb_manager/seams/snell_material.py`: public secret-generation protocol.
- `src/sb_manager/adapters/snell_material.py`: CSPRNG-backed URL-safe PSK adapter.
- `src/sb_manager/application/protocol_compatibility.py`: pure exact-version policy, typed failures, active-core inspection guard, and target-core blockers.
- `tests/protocols/test_snell.py`: pure serializer fixtures.
- `tests/contracts/test_snell_material_source.py`: secure adapter contract.
- `tests/behavior/test_protocol_compatibility.py`: version boundary and active/target policy behavior.
- `tests/acceptance/test_connection_share_journey.py`: typed URI/Surge reveal behavior.
- `docs/adr/0025-core-version-protocol-capabilities.md`: capability and downgrade decision.
- `docs/acceptance/2026-07-18-snell-v6-preview-support.md`: deterministic and real-core evidence.

### Existing modules extended in place

- `src/sb_manager/domain/installation.py`: add `ProtocolKind.SNELL_V6`.
- `src/sb_manager/domain/protocol_material.py`: add validated `SnellV6Material` to the tagged union.
- `src/sb_manager/protocols/catalog.py`: typed connection payloads and `SnellV6Handler`.
- `src/sb_manager/adapters/json_file_state.py`: tagged Snell material persistence.
- `src/sb_manager/application/manager.py`: generated-value identity and read-only planning gate.
- `src/sb_manager/application/profile_apply.py`: confirmation-time active-core recheck.
- `src/sb_manager/application/profile_availability.py`: resume planning and confirmation rechecks.
- `src/sb_manager/application/profile_editing.py`: projected active-profile compatibility check.
- `src/sb_manager/application/profile_removal.py`: allow recovery removals while rejecting projections that retain incompatible active Snell.
- `src/sb_manager/application/core_update.py`: target-version blockers and desired-state-revision binding.
- `src/sb_manager/application/network_inventory.py`: Snell TCP transport identity.
- `src/sb_manager/privileged/config_policy.py`: exact Snell v6 allowlist.
- `src/sb_manager/ui/connection_share.py`: render the payload kind truthfully.
- `src/sb_manager/application/profile_recommendation.py`: Snell variant and explicit Preview tradeoff.
- `src/sb_manager/ui/screens/profile_creation.py`: Snell definition, non-blocking capability planning, and typed incompatibility screen.
- `src/sb_manager/ui/screens/profile_recommendation.py`: direct and ranked Snell choices.
- `src/sb_manager/ui/screens/core_update.py` and `src/sb_manager/ui/screens/core_channels.py`: incompatible-target guidance.
- `src/sb_manager/ui/copy_catalog.py` and `src/sb_manager/ui/labels.py`: stable Simplified Chinese labels.
- `src/sb_manager/cli.py`: compose one core inspector/guard and the Snell handler.
- `tests/integration/test_real_sing_box.py`: opt-in Stable/Preview acceptance through the configured binary.
- `docs/adr/0002-deep-protocol-catalog.md`, `docs/SDD.md`, `docs/MANUAL.md`, `docs/SUPPORT.md`, and `README.md`: synchronized architecture and operator guidance.

## Task 1: Replace the URI-Only Connection Handoff with Typed Payloads

**Model tier:** Standard; small cross-cutting refactor with exact compatibility requirements.

**Files:**
- Modify: `src/sb_manager/protocols/catalog.py:78-94` and each handler's `ProfileConnectionInfo` construction
- Modify: `src/sb_manager/ui/connection_share.py`
- Modify: `src/sb_manager/ui/copy_catalog.py`
- Modify: `tests/protocols/test_catalog.py`
- Create: `tests/acceptance/test_connection_share_journey.py`

- [ ] **Step 1: Write failing catalog tests for typed URI payloads**

Add assertions to `tests/protocols/test_catalog.py` for an existing Shadowsocks profile:

```python
from sb_manager.protocols.catalog import ConnectionPayloadKind


def test_existing_protocol_connection_info_is_a_typed_uri_payload() -> None:
    materialized = shadowsocks_catalog().materialize(shadowsocks_profile(), listen_port=8388)

    assert materialized.connection_info is not None
    assert materialized.connection_info.payload.kind is ConnectionPayloadKind.URI
    assert materialized.connection_info.payload.content.startswith("ss://")
```

Repeat the payload-kind assertion in the existing catalog parametrization for
Reality, Hysteria2, Trojan, AnyTLS, TUIC, VLESS TLS, and VMess TLS. Preserve each
existing exact URI expectation.

- [ ] **Step 2: Write a failing reveal-panel test for URI and Surge labels**

In `tests/acceptance/test_connection_share_journey.py`, mount
`ConnectionSharePanel` twice with explicit payloads and assert both labels and
content:

```python
class ConnectionShareTestApp(App[None]):
    def __init__(self, info: ProfileConnectionInfo) -> None:
        super().__init__()
        self._info = info

    def compose(self) -> ComposeResult:
        yield ConnectionSharePanel(self._info)


@pytest.mark.parametrize(
    ("kind", "content", "expected_label"),
    (
        (ConnectionPayloadKind.URI, "ss://example", "连接 URI"),
        (
            ConnectionPayloadKind.SURGE_POLICY,
            "Snell-abc = snell, proxy.example.com, 443, psk=secret, version=6",
            "Surge 策略",
        ),
    ),
)
async def test_connection_payload_is_hidden_then_revealed_with_its_real_kind(
    kind: ConnectionPayloadKind,
    content: str,
    expected_label: str,
) -> None:
    info = ProfileConnectionInfo(
        server_address="proxy.example.com",
        server_port=443,
        payload=ConnectionPayload(kind=kind, content=content),
    )
    async with ConnectionShareTestApp(info).run_test() as pilot:
        assert len(pilot.app.screen.query("#connection-share-payload")) == 0
        await pilot.click("#reveal-connection-share")
        await pilot.pause()
        assert str(
            pilot.app.screen.query_one("#connection-share-label", Label).render()
        ) == expected_label
        assert pilot.app.screen.query_one("#connection-share-payload", TextArea).text == content
```

- [ ] **Step 3: Run the focused tests and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/protocols/test_catalog.py tests/acceptance/test_connection_share_journey.py -q
```

Expected: collection fails because `ConnectionPayloadKind`, `ConnectionPayload`,
and `ProfileConnectionInfo.payload` do not exist.

- [ ] **Step 4: Add the typed connection values**

Replace the URI field in `src/sb_manager/protocols/catalog.py` with:

```python
class ConnectionPayloadKind(str, Enum):
    URI = "uri"
    SURGE_POLICY = "surge-policy"


@dataclass(frozen=True, slots=True)
class ConnectionPayload:
    kind: ConnectionPayloadKind
    content: str

    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("Connection payload cannot be empty")


@dataclass(frozen=True, slots=True)
class ProfileConnectionInfo:
    server_address: str
    server_port: int
    payload: ConnectionPayload
```

Import `Enum`, then change every existing handler to construct:

```python
connection_info = ProfileConnectionInfo(
    server_address=specific.server_address,
    server_port=specific.server_port,
    payload=ConnectionPayload(
        kind=ConnectionPayloadKind.URI,
        content=specific.share_uri,
    ),
)
```

Do not change any protocol-specific URI serializer.

- [ ] **Step 5: Make the shared reveal panel payload-aware**

In `src/sb_manager/ui/connection_share.py`, rename URI-local variables and widget
ID to payload-neutral names and select the label key by kind:

```python
payload = self._connection_info.payload
label_key = (
    UiText.CONNECTION_SHARE_LABEL_URI
    if payload.kind is ConnectionPayloadKind.URI
    else UiText.CONNECTION_SHARE_LABEL_SURGE_POLICY
)
payload_area = TextArea(
    payload.content,
    id="connection-share-payload",
    read_only=True,
    soft_wrap=True,
)
```

Add `CONNECTION_SHARE_LABEL_URI` and
`CONNECTION_SHARE_LABEL_SURGE_POLICY` to the enum, expected-field mapping, and
Simplified Chinese catalog. Remove the generic URI-only label key only after all
callers and tests use the typed keys.

- [ ] **Step 6: Run focused and regression tests**

Run:

```bash
rtk .venv/bin/pytest tests/protocols tests/behavior/test_profile_apply.py tests/behavior/test_profile_details.py tests/acceptance/test_connection_share_journey.py tests/acceptance/test_first_profile_journey.py -q
```

Expected: all tests pass and existing URI contents remain byte-for-byte unchanged.

- [ ] **Step 7: Commit the deepened client-artifact seam**

```bash
rtk git add src/sb_manager/protocols/catalog.py src/sb_manager/ui/connection_share.py src/sb_manager/ui/copy_catalog.py tests/protocols/test_catalog.py tests/acceptance/test_connection_share_journey.py tests/acceptance/test_first_profile_journey.py tests/behavior/test_profile_apply.py tests/behavior/test_profile_details.py
rtk git commit -m "refactor: type protocol connection payloads"
```

## Task 2: Add the Snell v6 Material, Serializer, Persistence, and Catalog Slice

**Model tier:** Standard; protocol slice is isolated but carries credential and persistence invariants.

**Files:**
- Create: `src/sb_manager/protocols/snell.py`
- Create: `src/sb_manager/seams/snell_material.py`
- Create: `src/sb_manager/adapters/snell_material.py`
- Create: `tests/protocols/test_snell.py`
- Create: `tests/contracts/test_snell_material_source.py`
- Modify: `src/sb_manager/domain/installation.py`
- Modify: `src/sb_manager/domain/protocol_material.py`
- Modify: `src/sb_manager/protocols/catalog.py`
- Modify: `src/sb_manager/adapters/json_file_state.py`
- Modify: `src/sb_manager/application/manager.py`
- Modify: `src/sb_manager/application/network_inventory.py`
- Modify: `src/sb_manager/cli.py`
- Modify: `tests/contracts/test_state_store.py`
- Modify: `tests/protocols/test_catalog.py`
- Modify: `tests/commands/test_cli.py`

- [ ] **Step 1: Write failing pure Snell v6 serializer tests**

Create `tests/protocols/test_snell.py` with exact structure assertions:

```python
def test_snell_v6_builds_the_bounded_managed_inbound() -> None:
    assert SnellV6Protocol().build_inbound(
        SnellV6InboundSpec(tag="profile-7", listen_port=18443, psk=VALID_PSK)
    ) == {
        "type": "snell",
        "tag": "profile-7",
        "listen": "::",
        "listen_port": 18443,
        "version": 6,
        "psk": VALID_PSK,
        "mode": "default",
    }


def test_snell_v6_builds_a_stable_injection_safe_surge_policy() -> None:
    info = SnellV6Protocol().build_connection_info(
        SnellV6ConnectionSpec(
            profile_id="profile-7",
            server_address="proxy.example.com",
            server_port=18443,
            psk=VALID_PSK,
        )
    )
    stable_id = sha256(b"profile-7").hexdigest()[:12]
    assert info.surge_policy == (
        f"Snell-{stable_id} = snell, proxy.example.com, 18443, "
        f"psk={VALID_PSK}, version=6"
    )
```

Also test that profile display names never enter the policy, and that invalid
PSK length/alphabet raises `ValueError` without echoing the secret.

- [ ] **Step 2: Write failing material adapter, persistence, and catalog tests**

Use a fixed random source in `tests/contracts/test_snell_material_source.py`:

```python
class FixedRandomSource:
    def token_bytes(self, byte_count: int) -> bytes:
        assert byte_count == 32
        return bytes(range(32))


def test_secure_snell_material_source_generates_unpadded_urlsafe_psk() -> None:
    material = SecureSnellV6MaterialSource(random_source=FixedRandomSource()).generate()
    assert material.psk == base64.urlsafe_b64encode(bytes(range(32))).decode().rstrip("=")
    assert len(material.psk) == 43
```

Extend state-store tests with a `SnellV6Material(psk=VALID_PSK)` round trip and
malformed tagged payload rejection. Extend catalog tests to prove generation,
idempotent reuse, applied-profile missing material rejection, cross-protocol
material rejection, inbound equality, and `SURGE_POLICY` payload equality.

- [ ] **Step 3: Run the new tests and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/protocols/test_snell.py tests/contracts/test_snell_material_source.py tests/contracts/test_state_store.py tests/protocols/test_catalog.py -q
```

Expected: collection fails because the Snell modules, enum member, material, and
handler do not exist.

- [ ] **Step 4: Add the validated material and secure generation seam**

In `src/sb_manager/domain/protocol_material.py`, add:

```python
SNELL_V6_PSK_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


@dataclass(frozen=True, slots=True)
class SnellV6Material:
    psk: str

    def __post_init__(self) -> None:
        if SNELL_V6_PSK_PATTERN.fullmatch(self.psk) is None:
            raise ValueError("Managed Snell v6 PSK must be 43 URL-safe characters")
```

Add it to `ProtocolMaterial`, add `ProtocolKind.SNELL_V6 = "snell-v6"`, and
create the seam:

```python
class SnellV6MaterialSource(Protocol):
    def generate(self) -> SnellV6Material: ...
```

The adapter implementation is:

```python
SNELL_V6_PSK_BYTES = 32


class SecureSnellV6MaterialSource:
    def __init__(self, *, random_source: RandomSource) -> None:
        self._random_source = random_source

    def generate(self) -> SnellV6Material:
        encoded = base64.urlsafe_b64encode(
            self._random_source.token_bytes(SNELL_V6_PSK_BYTES)
        ).decode()
        return SnellV6Material(psk=encoded.rstrip("="))
```

- [ ] **Step 5: Implement the pure Snell protocol**

Create frozen `SnellV6InboundSpec`, `SnellV6ConnectionSpec`, and
`SnellV6ConnectionInfo` dataclasses in `src/sb_manager/protocols/snell.py`.
Implement only these fixed artifacts:

```python
class SnellV6Protocol:
    def build_inbound(self, spec: SnellV6InboundSpec) -> dict[str, object]:
        SnellV6Material(psk=spec.psk)
        return {
            "type": "snell",
            "tag": spec.tag,
            "listen": "::",
            "listen_port": spec.listen_port,
            "version": 6,
            "psk": spec.psk,
            "mode": "default",
        }

    def build_connection_info(
        self,
        spec: SnellV6ConnectionSpec,
    ) -> SnellV6ConnectionInfo:
        SnellV6Material(psk=spec.psk)
        stable_id = sha256(spec.profile_id.encode()).hexdigest()[:12]
        return SnellV6ConnectionInfo(
            server_address=spec.server_address,
            server_port=spec.server_port,
            psk=spec.psk,
            surge_policy=(
                f"Snell-{stable_id} = snell, {spec.server_address}, "
                f"{spec.server_port}, psk={spec.psk}, version=6"
            ),
        )
```

Do not add `users`, `userkey`, TLS, transport, multiplex, or configurable mode.

- [ ] **Step 6: Persist and materialize the Snell slice**

Add `TaggedSnellV6MaterialData` with kind `snell-v6` to
`src/sb_manager/adapters/json_file_state.py`. Extend both serializer directions
with exact branches:

```python
if isinstance(material, SnellV6Material):
    return {"kind": "snell-v6", "psk": material.psk}

if data["kind"] == "snell-v6":
    return SnellV6Material(psk=data["psk"])
```

Add `SnellV6Handler` beside `ShadowsocksHandler`. It must generate material only
for drafts, reuse persisted material, create the exact inbound, and return:

```python
ProfileConnectionInfo(
    server_address=specific.server_address,
    server_port=specific.server_port,
    payload=ConnectionPayload(
        kind=ConnectionPayloadKind.SURGE_POLICY,
        content=specific.surge_policy,
    ),
)
```

Register the secure source in `create_protocol_catalog`, add Snell's generated
PSK identity to `GENERATED_VALUES_BY_PROTOCOL`, and map Snell to TCP in
`_TRANSPORTS_BY_PROTOCOL`.

- [ ] **Step 7: Run focused tests and production-composition tests**

Run:

```bash
rtk .venv/bin/pytest tests/protocols/test_snell.py tests/contracts/test_snell_material_source.py tests/contracts/test_state_store.py tests/protocols/test_catalog.py tests/behavior/test_profile_planning.py tests/commands/test_cli.py -q
```

Expected: all tests pass; no TLS or transport intent is required for Snell.

- [ ] **Step 8: Commit the protocol vertical slice**

```bash
rtk git add src/sb_manager/domain/installation.py src/sb_manager/domain/protocol_material.py src/sb_manager/protocols/snell.py src/sb_manager/protocols/catalog.py src/sb_manager/seams/snell_material.py src/sb_manager/adapters/snell_material.py src/sb_manager/adapters/json_file_state.py src/sb_manager/application/manager.py src/sb_manager/application/network_inventory.py src/sb_manager/cli.py tests/protocols/test_snell.py tests/contracts/test_snell_material_source.py tests/contracts/test_state_store.py tests/protocols/test_catalog.py tests/behavior/test_profile_planning.py tests/commands/test_cli.py
rtk git commit -m "feat: add Snell v6 protocol artifacts"
```

## Task 3: Introduce Exact-Version Protocol Compatibility and Gate Planning

**Model tier:** Highest available; version ordering and fail-closed behavior are architecture and safety decisions.

**Files:**
- Create: `src/sb_manager/application/protocol_compatibility.py`
- Create: `tests/behavior/test_protocol_compatibility.py`
- Modify: `src/sb_manager/application/manager.py`
- Modify: `src/sb_manager/cli.py`
- Modify: `tests/behavior/test_profile_planning.py`
- Modify: `tests/behavior/test_draft_persistence.py`

- [ ] **Step 1: Write failing exact boundary tests**

Create a parametrized matrix in
`tests/behavior/test_protocol_compatibility.py`:

```python
@pytest.mark.parametrize(
    ("version", "supported"),
    (
        ("1.13.14", False),
        ("1.14.0-alpha.37", False),
        ("1.14.0-alpha.38", True),
        ("1.14.0-alpha.47", True),
        ("1.14.0-beta.1", True),
        ("1.14.0-rc.1", True),
        ("1.14.0", True),
        ("1.15.0-alpha.1", True),
        ("not-a-version", False),
    ),
)
def test_snell_v6_support_uses_the_exact_introduction_boundary(
    version: str,
    supported: bool,
) -> None:
    assert ProtocolCompatibilityPolicy().supports(ProtocolKind.SNELL_V6, version) is supported
```

Add tests proving all existing protocols are supported without inspecting a
core, unavailable/unknown observations raise `CoreVersionUnknown`, and a Stable
observation raises `ProtocolUnsupportedByCore` with no secret data.

- [ ] **Step 2: Write failing Manager planning tests**

In `tests/behavior/test_profile_planning.py`, use fixed inspectors:

```python
def test_snell_planning_rejects_stable_before_a_draft_or_secret_exists() -> None:
    manager = Manager(
        state_store=store,
        core_compatibility=ActiveCoreProtocolCompatibility(
            inspector=FixedCoreInspector("1.13.14")
        ),
    )
    with pytest.raises(ProtocolUnsupportedByCore):
        manager.plan_profile(snell_request())
    assert store.load().profiles == ()


def test_snell_planning_accepts_a_capable_preview() -> None:
    manager = Manager(
        state_store=store,
        core_compatibility=ActiveCoreProtocolCompatibility(
            inspector=FixedCoreInspector("1.14.0-alpha.47")
        ),
    )
    assert manager.plan_profile(snell_request()).protocol is ProtocolKind.SNELL_V6
```

- [ ] **Step 3: Run the tests and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/behavior/test_protocol_compatibility.py tests/behavior/test_profile_planning.py -q
```

Expected: collection fails because the compatibility types do not exist.

- [ ] **Step 4: Implement the pure version policy**

In `src/sb_manager/application/protocol_compatibility.py`, use an anchored parser
for sing-box's official prerelease shapes. The core decision must be equivalent
to:

```python
SNELL_V6_INTRODUCTION = "1.14.0-alpha.38"
_VERSION = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<stage>alpha|beta|rc)\.(?P<number>\d+))?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


def _supports_snell_v6(version: str) -> bool:
    match = _VERSION.fullmatch(version)
    if match is None:
        return False
    release = tuple(int(match[name]) for name in ("major", "minor", "patch"))
    if release != (1, 14, 0):
        return release > (1, 14, 0)
    stage = match["stage"]
    if stage is None or stage in {"beta", "rc"}:
        return True
    return stage == "alpha" and int(match["number"]) >= 38
```

`ProtocolCompatibilityPolicy.supports` returns `True` immediately for existing
protocol kinds. Add typed `ProtocolCompatibilityError`, `CoreVersionUnknown`,
`ProtocolUnsupportedByCore`, `CoreVersionChanged`, and
`CoreTargetIncompatibleWithDesiredState` errors with structured protocol,
version, threshold, and blocking profile fields.

Use concrete constructors so the UI never parses error text:

```python
class ProtocolCompatibilityError(RuntimeError):
    """A requested profile/core combination is not supported."""


class CoreVersionUnknown(ProtocolCompatibilityError):
    def __init__(self, *, protocol: ProtocolKind) -> None:
        self.protocol = protocol
        self.observed_version: str | None = None
        self.minimum_version = SNELL_V6_INTRODUCTION
        super().__init__(f"Core version is unavailable for {protocol.value}")


class ProtocolUnsupportedByCore(ProtocolCompatibilityError):
    def __init__(
        self,
        *,
        protocol: ProtocolKind,
        observed_version: str,
        minimum_version: str,
    ) -> None:
        self.protocol = protocol
        self.observed_version = observed_version
        self.minimum_version = minimum_version
        super().__init__(
            f"{protocol.value} requires {minimum_version}; observed {observed_version}"
        )


class CoreVersionChanged(ProtocolCompatibilityError):
    def __init__(self, *, expected_version: str, observed_version: str) -> None:
        self.expected_version = expected_version
        self.observed_version = observed_version
        super().__init__(
            f"Core version changed from {expected_version} to {observed_version}"
        )


class CoreTargetIncompatibleWithDesiredState(ProtocolCompatibilityError):
    def __init__(
        self,
        *,
        target_version: str,
        blocking_profile_ids: tuple[str, ...],
        blocking_profile_names: tuple[str, ...],
    ) -> None:
        self.target_version = target_version
        self.blocking_profile_ids = blocking_profile_ids
        self.blocking_profile_names = blocking_profile_names
        super().__init__(f"Core {target_version} is incompatible with applied profiles")
```

Expose the pure enforcement methods used by later tasks with these signatures:

```python
class ProtocolCompatibilityPolicy:
    def supports(self, protocol: ProtocolKind, version: str) -> bool:
        return protocol is not ProtocolKind.SNELL_V6 or _supports_snell_v6(version)

    def require_supported(self, protocol: ProtocolKind, version: str) -> None:
        if not self.supports(protocol, version):
            raise ProtocolUnsupportedByCore(
                protocol=protocol,
                observed_version=version,
                minimum_version=SNELL_V6_INTRODUCTION,
            )

    def blocking_profiles(
        self,
        profiles: Iterable[ManagedProfile],
        *,
        target_version: str,
    ) -> tuple[ManagedProfile, ...]:
        return tuple(
            profile
            for profile in profiles
            if profile.status is ProfileStatus.APPLIED
            and profile.enabled
            and not self.supports(profile.protocol, target_version)
        )

    def require_profiles_supported(
        self,
        profiles: Iterable[ManagedProfile],
        *,
        target_version: str,
    ) -> None:
        blockers = self.blocking_profiles(profiles, target_version=target_version)
        if blockers:
            raise CoreTargetIncompatibleWithDesiredState(
                target_version=target_version,
                blocking_profile_ids=tuple(profile.profile_id for profile in blockers),
                blocking_profile_names=tuple(profile.profile_name for profile in blockers),
            )
```

- [ ] **Step 5: Implement the active-core guard**

The guard probes only when Snell is present:

```python
class ActiveCoreProtocolCompatibility:
    def __init__(
        self,
        *,
        inspector: CoreStatusInspector | None,
        policy: ProtocolCompatibilityPolicy | None = None,
    ) -> None:
        self._inspector = inspector
        self._policy = policy or ProtocolCompatibilityPolicy()

    def require_protocol(
        self,
        protocol: ProtocolKind,
        *,
        expected_version: str | None = None,
    ) -> str | None:
        if protocol is not ProtocolKind.SNELL_V6:
            return None
        if self._inspector is None:
            raise CoreVersionUnknown(protocol=protocol)
        observation = self._inspector.inspect()
        if not observation.available or observation.version is None:
            raise CoreVersionUnknown(protocol=protocol)
        self._policy.require_supported(protocol, observation.version)
        if expected_version is not None and observation.version != expected_version:
            raise CoreVersionChanged(
                expected_version=expected_version,
                observed_version=observation.version,
            )
        return observation.version

    def require_profiles(
        self,
        profiles: Iterable[ManagedProfile],
        *,
        expected_version: str | None = None,
    ) -> str | None:
        active = tuple(
            profile
            for profile in profiles
            if profile.status is ProfileStatus.APPLIED and profile.enabled
        )
        if any(profile.protocol is ProtocolKind.SNELL_V6 for profile in active):
            return self.require_protocol(
                ProtocolKind.SNELL_V6,
                expected_version=expected_version,
            )
        return None
```

The pure policy also exposes `blocking_profiles(profiles, target_version)` and
returns only applied, enabled Snell profile IDs/names when the target is
unsupported.

- [ ] **Step 6: Gate Manager planning and compose the production inspector**

Add an optional guard to `Manager.__init__`, defaulting to an instance with no
inspector so Snell fails closed while existing protocols remain unaffected.
Add `observed_core_version: str | None` to `ProfilePlan` and capture it after
form validation but before generated values or draft persistence:

```python
observed_core_version = self._core_compatibility.require_protocol(request.protocol)
```

Set the returned `ProfilePlan.observed_core_version` field to that exact value.

`create_app`, instantiate `SingBoxCoreStatusInspector` once, construct one
`ActiveCoreProtocolCompatibility`, and pass the same guard to Manager. Reuse the
inspector for host readiness instead of constructing a second adapter.

- [ ] **Step 7: Run focused behavior and composition tests**

Run:

```bash
rtk .venv/bin/pytest tests/behavior/test_protocol_compatibility.py tests/behavior/test_profile_planning.py tests/behavior/test_draft_persistence.py tests/commands/test_cli.py -q
```

Expected: Stable/unknown Snell planning fails read-only; Preview planning passes;
existing protocol planning does not call the inspector.

- [ ] **Step 8: Commit compatibility planning**

```bash
rtk git add src/sb_manager/application/protocol_compatibility.py src/sb_manager/application/manager.py src/sb_manager/cli.py tests/behavior/test_protocol_compatibility.py tests/behavior/test_profile_planning.py tests/behavior/test_draft_persistence.py tests/commands/test_cli.py
rtk git commit -m "feat: gate Snell planning by core version"
```

## Task 4: Recheck Active-Core Compatibility Across Profile Mutations

**Model tier:** Highest available; this slice protects every configuration mutation and recovery path.

**Files:**
- Modify: `src/sb_manager/application/profile_apply.py`
- Modify: `src/sb_manager/application/profile_availability.py`
- Modify: `src/sb_manager/application/profile_editing.py`
- Modify: `src/sb_manager/application/profile_removal.py`
- Modify: `src/sb_manager/ui/screens/profile_creation.py`
- Modify: `src/sb_manager/cli.py`
- Modify: `tests/behavior/test_profile_apply.py`
- Modify: `tests/behavior/test_profile_availability.py`
- Modify: `tests/behavior/test_profile_editing.py`
- Modify: `tests/behavior/test_profile_removal.py`
- Modify: `tests/acceptance/test_first_profile_journey.py`

- [ ] **Step 1: Write failing apply and resume recheck tests**

Add tests where a Snell draft/paused profile was created under Preview but the
fixed inspector now reports Stable at confirmation:

```python
def test_snell_apply_rechecks_the_active_core_before_material_or_host_mutation() -> None:
    service = profile_apply_service(
        installation=snell_draft_without_material(),
        core_version="1.13.14",
        applier=ApplierThatMustNotBeCalled(),
    )
    with pytest.raises(ProtocolUnsupportedByCore):
        service.apply_profile(confirmed_request())
    assert material_source.calls == 0


def test_snell_resume_rechecks_the_active_core_before_port_or_apply() -> None:
    service = availability_service(
        installation=paused_snell_profile(),
        core_version="1.13.14",
        applier=ApplierThatMustNotBeCalled(),
    )
    with pytest.raises(ProtocolUnsupportedByCore):
        service.plan_change(resume_request())
```

Add matching Preview success cases.

Add a version-race test where planning observes `1.14.0-alpha.47` and
confirmation observes `1.14.0-alpha.48`. Although both support Snell, the
confirmed operation must raise `CoreVersionChanged` before material generation,
port selection, projection, or apply.

- [ ] **Step 2: Write failing full-projection recovery tests**

Cover these exact cases in editing/removal/availability tests:

- editing an applied Snell profile under Stable is rejected before apply;
- editing another applied profile while an active Snell remains under Stable is rejected;
- pausing the last active Snell under Stable is allowed because the projected config removes it;
- removing the last active Snell under Stable is allowed;
- removing another profile while active Snell remains is rejected;
- draft and already-paused Snell do not trigger an inspector probe.
- edit, removal, and resume plans that retain active Snell freeze the exact
  observed core version and reject a different supported Preview at confirm.

Use recording guards or `ApplierThatMustNotBeCalled` to prove the host boundary
is not crossed.

- [ ] **Step 3: Run the focused tests and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/behavior/test_profile_apply.py tests/behavior/test_profile_availability.py tests/behavior/test_profile_editing.py tests/behavior/test_profile_removal.py -q
```

Expected: new tests fail because services do not accept or call the guard.

- [ ] **Step 4: Inject one active-core guard into all mutation services**

Add `core_compatibility: ActiveCoreProtocolCompatibility` to each production
service constructor. Introduce a read-only apply plan because apply currently
has no application plan object:

```python
@dataclass(frozen=True, slots=True)
class ProfileApplyPlan:
    profile_id: str
    profile_name: str
    expected_revision: int
    observed_core_version: str | None


class ProfileApplier(Protocol):
    def plan_profile(self, profile_id: str) -> ProfileApplyPlan: ...

    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult: ...
```

`ProfileApplyService.plan_profile` loads the profile, captures the current exact
version with `require_protocol`, and returns the plan without generating
material or mutating state. Add `expected_core_version: str | None` to
`ApplyProfileRequest`. At confirmation, require the same version before choosing
a port or materializing:

```python
current_version = self._core_compatibility.require_protocol(
    profile.protocol,
    expected_version=request.expected_core_version,
)
if profile.protocol is ProtocolKind.SNELL_V6 and current_version is None:
    raise CoreVersionUnknown(protocol=profile.protocol)
```

Add `observed_core_version: str | None` to `ProfileAvailabilityPlan`,
`ProfileEditPlan`, and `ProfileRemovalPlan`. For each operation that rebuilds
the whole document, planning captures the version from the exact projected
profile tuple, and confirmation compares against it before projection:

```python
observed_core_version = self._core_compatibility.require_profiles(projected_profiles)
```

Store that value in the returned operation plan. During confirmation execute:

```python
self._core_compatibility.require_profiles(
    projected_profiles,
    expected_version=plan.observed_core_version,
)
document = self._configuration_projector.project(projected_profiles)
```

In `ProfileAvailabilityService.plan_change`, call `require_protocol` only for a
resume target. During confirmation, call `require_profiles` after constructing
the projected tuple; this intentionally allows pausing the incompatible Snell
profile. Apply the same projected-tuple rule to edit and removal planning and
confirmation.

Update `DraftSavedScreen` and every other draft-apply entry point to call
`profile_applier.plan_profile(profile_id)` and pass the resulting
`ProfileApplyPlan` into `ApplyConfirmationScreen`. Construct
`ApplyProfileRequest.expected_core_version` from that plan. Task 7 moves this
potentially slow read-only planning call into a worker and adds typed copy; this
slice first establishes the application invariant and complete request data.

- [ ] **Step 5: Update production composition and test factories**

Pass the single guard created in `create_app` to `ProfileApplyService`,
`ProfileAvailabilityService`, `ProfileEditingService`, and
`ProfileRemovalService`. Test factories should use an inspector that raises if
called for existing protocols, and an explicit Preview/Stable inspector for
Snell cases.

- [ ] **Step 6: Run profile lifecycle regressions**

Run:

```bash
rtk .venv/bin/pytest tests/behavior/test_profile_apply.py tests/behavior/test_profile_availability.py tests/behavior/test_profile_editing.py tests/behavior/test_profile_removal.py tests/acceptance/test_first_profile_journey.py tests/acceptance/test_profile_availability_journey.py tests/acceptance/test_profile_editing_journey.py tests/acceptance/test_profile_removal_journey.py -q
```

Expected: all tests pass; recovery pause/removal works even after an external
downgrade, while every projected config retaining Snell fails before mutation.

- [ ] **Step 7: Commit the mutation boundary**

```bash
rtk git add src/sb_manager/application/profile_apply.py src/sb_manager/application/profile_availability.py src/sb_manager/application/profile_editing.py src/sb_manager/application/profile_removal.py src/sb_manager/ui/screens/profile_creation.py src/sb_manager/cli.py tests/behavior/test_profile_apply.py tests/behavior/test_profile_availability.py tests/behavior/test_profile_editing.py tests/behavior/test_profile_removal.py tests/acceptance/test_first_profile_journey.py tests/acceptance/test_profile_availability_journey.py tests/acceptance/test_profile_editing_journey.py tests/acceptance/test_profile_removal_journey.py
rtk git commit -m "feat: recheck Snell compatibility before profile mutation"
```

## Task 5: Prevent Incompatible Core Activation and Stale Downgrades

**Model tier:** Highest available; desired-state binding and core activation are security-sensitive host boundaries.

**Files:**
- Modify: `src/sb_manager/application/core_update.py`
- Modify: `src/sb_manager/cli.py`
- Modify: `tests/behavior/test_core_update.py`
- Modify: `tests/behavior/test_core_channels.py`
- Modify: `tests/acceptance/test_core_update_journey.py`
- Modify: `tests/acceptance/test_core_channel_journey.py`

- [ ] **Step 1: Write failing exact-update blocker and stale-plan tests**

In `tests/behavior/test_core_update.py`, cover both planning and execution:

```python
def test_exact_stable_update_is_blocked_by_an_applied_snell_profile() -> None:
    service = core_update_service(state=installation_with_active_snell())
    with pytest.raises(CoreTargetIncompatibleWithDesiredState) as captured:
        service.plan(stable_request("1.13.14"))
    assert captured.value.blocking_profile_ids == ("profile-7",)
    assert artifact_source.acquire_calls == []


def test_core_update_rejects_a_changed_desired_state_before_acquisition() -> None:
    plan = service.plan(preview_request("1.14.0-alpha.47"))
    store.save(installation_with_new_revision_and_active_snell())
    with pytest.raises(CoreDesiredStateChangedError):
        service.execute(plan, confirmed=True)
    assert artifact_source.acquire_calls == []
```

Also prove draft and paused Snell profiles do not block Stable.

- [ ] **Step 2: Write failing retained-channel switch tests**

In `tests/behavior/test_core_channels.py`, prove a retained Stable switch is
blocked by active Snell during planning and rechecked during execution. Prove a
retained Preview target succeeds and a pause/removal followed by a fresh plan
allows Stable.

- [ ] **Step 3: Run the tests and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/behavior/test_core_update.py tests/behavior/test_core_channels.py -q
```

Expected: new blocker fields and revision checks are absent.

- [ ] **Step 4: Bind exact update plans to desired state**

Add `expected_state_revision: int` to `CoreUpdatePlan` and require a `StateStore`
plus `ProtocolCompatibilityPolicy` in `CoreUpdateService`. During `plan`, load
once and reject target blockers using `request.version` before network artifact
inspection. After inspection, require that the returned exact version still
matches the request, then freeze the same revision:

```python
installation = self._state_store.load()
self._compatibility.require_profiles_supported(
    installation.profiles,
    target_version=request.version,
)
artifact = self._artifact_source.inspect(artifact_request)
return CoreUpdatePlan(
    artifact=artifact,
    mutates_host=False,
    warnings=tuple(warnings),
    expected_state_revision=installation.revision,
)
```

At the start of confirmed `execute`, reload state, require exact revision
equality, and rerun target compatibility before `artifact_source.acquire`.
Raise a dedicated `CoreDesiredStateChangedError` rather than reusing profile
workflow text.

```python
class CoreDesiredStateChangedError(RuntimeError):
    def __init__(self, *, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Desired state changed from revision {expected} to {actual}"
        )
```

- [ ] **Step 5: Bind retained channel plans and recheck target compatibility**

Add `expected_state_revision` to `CoreChannelPlan`. `CoreChannelService` receives
the same state store and pure policy. Every plan kind records the observed
revision; retained switching calls `require_profiles_supported` for
`plan.version` during planning and again after revision comparison during
execution. Acquisition plans delegate to the already bound exact plan.

Do not put state or protocol policy into the privileged core switcher; it still
accepts only exact verified identities.

- [ ] **Step 6: Update composition and UI-facing acceptance fixtures**

Pass `state_store` and the pure policy into `CoreUpdateService` and
`CoreChannelService`. Update fixed plans in acceptance tests with explicit
revision values. Add journey assertions that incompatible review reports the
blocking profile names and never invokes acquire/switch.

- [ ] **Step 7: Run core update and channel regressions**

Run:

```bash
rtk .venv/bin/pytest tests/behavior/test_core_update.py tests/behavior/test_core_channels.py tests/acceptance/test_core_update_journey.py tests/acceptance/test_core_channel_journey.py tests/commands/test_cli.py -q
```

Expected: Stable is unavailable only while applied/enabled Snell exists; stale
plans stop before download or privileged switching.

- [ ] **Step 8: Commit safe downgrade prevention**

```bash
rtk git add src/sb_manager/application/core_update.py src/sb_manager/cli.py tests/behavior/test_core_update.py tests/behavior/test_core_channels.py tests/acceptance/test_core_update_journey.py tests/acceptance/test_core_channel_journey.py tests/commands/test_cli.py
rtk git commit -m "feat: prevent incompatible Snell core downgrades"
```

## Task 6: Allow Only the Bounded Snell v6 Privileged Schema

**Model tier:** Highest available; privileged allowlist and secret validation.

**Files:**
- Modify: `src/sb_manager/privileged/config_policy.py`
- Modify: `tests/privileged/test_managed_config_policy.py`
- Modify: `tests/privileged/test_config_apply_service.py`

- [ ] **Step 1: Write failing allowlist tests**

Add an exact valid fixture:

```python
def snell_inbound() -> dict[str, object]:
    return {
        "type": "snell",
        "tag": "profile-7",
        "listen": "::",
        "listen_port": 18443,
        "version": 6,
        "psk": "0123456789ab",
        "mode": "default",
    }


def test_policy_accepts_the_exact_snell_v6_shape() -> None:
    ManagedConfigurationPolicy().validate(managed_document(snell_inbound()))
```

Parametrize rejected mutations for version `5`, boolean version, missing
version, modes `unshaped` and `unsafe-raw`, PSKs of 11 and 256 ASCII bytes,
non-ASCII PSK, `users`, `userkey`, `tls`, `transport`, and one unknown field.
Assert `PrivilegedInputError` and no configuration/runtime mutation.

- [ ] **Step 2: Run privileged tests and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/privileged/test_managed_config_policy.py tests/privileged/test_config_apply_service.py -q
```

Expected: valid Snell is rejected as an unsupported inbound.

- [ ] **Step 3: Implement the exact Snell validator**

Register `"snell": self._validate_snell` and implement:

```python
def _validate_snell(
    self,
    inbound: dict[str, object],
) -> tuple[str, int, tuple[str, str] | None]:
    tag, port = self._validate_common(
        inbound,
        inbound_type="snell",
        fields={"type", "tag", "listen", "listen_port", "version", "psk", "mode"},
    )
    version = self._integer(inbound["version"], role="snell version")
    if version != 6 or inbound["mode"] != "default":
        raise PrivilegedInputError("Managed snell version or mode is invalid")
    psk = self._nonempty_string(inbound["psk"], role="snell psk")
    try:
        encoded = psk.encode("ascii")
    except UnicodeEncodeError as error:
        raise PrivilegedInputError("Managed snell psk must be ASCII") from error
    if not 12 <= len(encoded) <= 255:
        raise PrivilegedInputError("Managed snell psk length is invalid")
    return tag, port, None
```

Error messages must never interpolate `psk`.

- [ ] **Step 4: Prove policy rejection happens before host transaction**

Add one config-apply service test using `RuntimeThatMustNotBeCalled`, an invalid
Snell field, and assertions that neither the target config nor working staged
files remain.

- [ ] **Step 5: Run privileged and transactional regressions**

Run:

```bash
rtk .venv/bin/pytest tests/privileged/test_managed_config_policy.py tests/privileged/test_config_apply_service.py tests/behavior/test_transactional_apply.py -q
```

Expected: exact v6/default passes; every broader shape fails before mutation.

- [ ] **Step 6: Commit the privileged allowlist**

```bash
rtk git add src/sb_manager/privileged/config_policy.py tests/privileged/test_managed_config_policy.py tests/privileged/test_config_apply_service.py
rtk git commit -m "feat: allow bounded Snell v6 configuration"
```

## Task 7: Add Snell to Recommendations, Guided TUI, and Capability Guidance

**Model tier:** Standard for the UI slice; highest available reviewer for stale-worker and secret-disclosure checks.

**Files:**
- Modify: `src/sb_manager/application/profile_recommendation.py`
- Modify: `src/sb_manager/ui/screens/profile_recommendation.py`
- Modify: `src/sb_manager/ui/screens/profile_creation.py`
- Modify: `src/sb_manager/ui/screens/core_update.py`
- Modify: `src/sb_manager/ui/screens/core_channels.py`
- Modify: `src/sb_manager/ui/copy_catalog.py`
- Modify: `src/sb_manager/ui/labels.py`
- Modify: `tests/behavior/test_profile_recommendation.py`
- Modify: `tests/acceptance/test_profile_recommendation_journey.py`
- Modify: `tests/acceptance/test_first_profile_journey.py`
- Modify: `tests/acceptance/test_core_update_journey.py`
- Modify: `tests/acceptance/test_core_channel_journey.py`

- [ ] **Step 1: Write failing recommendation and direct-picker tests**

Add `ProtocolVariant.SNELL_V6` and a compatibility rationale expectation to the
tests before production code:

```python
def test_compatibility_choices_include_snell_with_preview_tradeoff() -> None:
    report = ProfileRecommendationService().recommend(ProfilePurpose.COMPATIBILITY)
    snell = next(item for item in report.recommendations if item.variant is ProtocolVariant.SNELL_V6)
    assert snell.rationale is RecommendationRationale.COMPATIBILITY_SNELL_V6
```

In the journey test, open direct protocol selection and assert a button named
`snell-v6` exists with copy containing both `Snell v6` and `Preview / 1.14+`.

- [ ] **Step 2: Write failing Stable/Preview guided-flow tests**

Extend `tests/acceptance/test_first_profile_journey.py` with:

- Stable: select Snell, enter valid values, preview, observe the typed
  incompatibility screen, confirm no draft and no generated PSK disclosure;
- unknown core: same fail-closed behavior with install/activate Preview guidance;
- Preview alpha.47: plan, save draft, confirm apply, reveal `Surge 策略`, and
  assert exact `version=6` content;
- core changes from Preview to Stable between plan and confirm: apply error is
  pre-mutation and the secret remains hidden.

- [ ] **Step 3: Run the TUI tests and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/behavior/test_profile_recommendation.py tests/acceptance/test_profile_recommendation_journey.py tests/acceptance/test_first_profile_journey.py tests/acceptance/test_core_update_journey.py tests/acceptance/test_core_channel_journey.py -q
```

Expected: Snell variants/copy/screens are missing and generic errors are shown.

- [ ] **Step 4: Add Snell recommendation, definition, and stable labels**

Add:

```python
class ProtocolVariant(str, Enum):
    SNELL_V6 = "snell-v6"


class RecommendationRationale(str, Enum):
    COMPATIBILITY_SNELL_V6 = "compatibility.snell-v6"
```

Append a Snell recommendation to the compatibility report without removing any
existing choice. Add `SNELL_V6_PROFILE` to `GUIDED_PROFILES_BY_VARIANT`, with no
TLS or transport fields. Add `ProtocolKind.SNELL_V6: "Snell v6"` to shared
labels and direct-choice mappings.

The Simplified Chinese guidance must say the active core must report
`1.14.0-alpha.38` or newer, Stable 1.13.x cannot apply it, only v6/default mode
is generated, and the client artifact is a Surge policy rather than a URI.

- [ ] **Step 5: Make capability planning non-blocking and typed**

The current form calls `manager.plan_profile` synchronously; the core probe has a
10-second bound. Move planning to a generation-bound Textual worker:

```python
@on(Button.Pressed, "#preview-plan")
def preview_plan(self) -> None:
    request = PlanProfileRequest(
        profile_name=profile_name,
        protocol=self.definition.protocol,
        listen_port=listen_port,
        server_address=server_address,
        tls=tls,
        transport=transport,
    )
    self._planning_generation += 1
    self.query_one("#preview-plan", Button).disabled = True
    self._plan_profile_worker(request, self._planning_generation)


@work(thread=True, exclusive=True)
def _plan_profile_worker(self, request: PlanProfileRequest, generation: int) -> None:
    try:
        plan = self.manager.plan_profile(request)
    except ProtocolCompatibilityError as error:
        self.app.call_from_thread(self._show_compatibility_error, generation, error)
    except PlanValidationError as error:
        self.app.call_from_thread(self._show_validation, generation, error)
    except Exception:
        self.app.call_from_thread(self._show_unexpected_error, generation)
    else:
        self.app.call_from_thread(self._show_plan, generation, plan)
```

Each UI callback must ignore a stale generation or unmounted screen, restore the
button only for the current generation, and never render exception text. Add a
dedicated typed incompatibility screen that renders protocol, observed version
when known, minimum version, no-mutation safety, and recovery action.

Concretely, retain the existing `profile_name`, `server_address`, TLS, transport,
port parsing, visible-error reset, and `PlanProfileRequest(...)` construction in
`preview_plan`. Replace only the current synchronous call to `_plan_profile`
and subsequent `push_screen` with the generation increment and worker dispatch
shown above. Delete `_plan_profile` after its validation and error branches have
moved into the worker callbacks.

Apply planning must also be non-blocking. When the user selects `apply-draft`,
disable that button, run `profile_applier.plan_profile(profile_id)` in a
threaded, generation-bound worker, and open `ApplyConfirmationScreen` only with
the returned `ProfileApplyPlan`. A `ProtocolCompatibilityError` opens the same
typed incompatibility screen; an unclassified read failure uses the existing
read-only planning failure copy. Confirmation passes the plan's exact revision
and `observed_core_version` into `ApplyProfileRequest`, so a Preview-to-Preview
or Preview-to-Stable race is rejected by the application service.

- [ ] **Step 6: Render incompatible core targets with blocker identities**

Catch `CoreTargetIncompatibleWithDesiredState` separately in exact-update and
channel planning screens. Render the exact target version and joined blocking
profile display names from structured fields. Do not show material, inbound
JSON, or raw exception strings. Preserve existing generic planning failure for
unclassified errors.

- [ ] **Step 7: Run TUI and copy-catalog regressions**

Run:

```bash
rtk .venv/bin/pytest tests/behavior/test_profile_recommendation.py tests/acceptance/test_profile_recommendation_journey.py tests/acceptance/test_first_profile_journey.py tests/acceptance/test_core_update_journey.py tests/acceptance/test_core_channel_journey.py tests/commands/test_cli.py -q
```

Expected: Stable and unknown-core Snell flows remain read-only; Preview reaches
apply and reveals a Surge-labelled payload; stale workers cannot open a plan.

- [ ] **Step 8: Commit the guided Snell experience**

```bash
rtk git add src/sb_manager/application/profile_recommendation.py src/sb_manager/ui/screens/profile_recommendation.py src/sb_manager/ui/screens/profile_creation.py src/sb_manager/ui/screens/core_update.py src/sb_manager/ui/screens/core_channels.py src/sb_manager/ui/copy_catalog.py src/sb_manager/ui/labels.py tests/behavior/test_profile_recommendation.py tests/acceptance/test_profile_recommendation_journey.py tests/acceptance/test_first_profile_journey.py tests/acceptance/test_core_update_journey.py tests/acceptance/test_core_channel_journey.py tests/commands/test_cli.py
rtk git commit -m "feat: guide Preview-only Snell v6 setup"
```

## Task 8: Verify Official Cores and Synchronize Architecture and User Documentation

**Model tier:** Medium for mechanical documentation updates; highest available for official-core evidence and final normative review.

**Files:**
- Modify: `tests/integration/test_real_sing_box.py`
- Create: `docs/adr/0025-core-version-protocol-capabilities.md`
- Create: `docs/acceptance/2026-07-18-snell-v6-preview-support.md`
- Modify: `docs/adr/0002-deep-protocol-catalog.md`
- Modify: `docs/SDD.md`
- Modify: `docs/MANUAL.md`
- Modify: `docs/SUPPORT.md`
- Modify: `README.md`

- [ ] **Step 1: Write opt-in Stable/Preview real-core tests**

Use the existing `real_sing_box_binary` fixture and inspect its exact version.
Add two complementary tests:

```python
def materialized_snell_document(real_sing_box_binary: Path) -> dict[str, object]:
    materialized = create_protocol_catalog(
        sing_box_binary=real_sing_box_binary,
        reality_server_name="www.cloudflare.com",
    ).materialize(
        ManagedProfile(
            profile_name="snell-v6-release-fixture",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.DRAFT,
            profile_id="profile-snell-v6",
            server_address="proxy.example.com",
        ),
        listen_port=18443,
    )
    return {
        "inbounds": [materialized.inbound],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }


def write_document(tmp_path: Path, document: dict[str, object]) -> Path:
    config_path = tmp_path / "snell-v6.json"
    config_path.write_text(json.dumps(document), encoding="utf-8")
    return config_path


@pytest.mark.integration
def test_real_snell_capable_core_accepts_generated_v6_config(
    real_sing_box_binary: Path,
    tmp_path: Path,
) -> None:
    version = SingBoxCoreStatusInspector(binary=real_sing_box_binary).inspect().version
    if version is None or not ProtocolCompatibilityPolicy().supports(
        ProtocolKind.SNELL_V6, version
    ):
        pytest.skip("configured core predates Snell v6 support")
    document = materialized_snell_document(real_sing_box_binary)
    ManagedConfigurationPolicy().validate(document)
    config_path = write_document(tmp_path, document)
    result = SingBoxConfigValidator(binary=real_sing_box_binary).validate(config_path)
    assert result.valid, result.diagnostics


@pytest.mark.integration
def test_real_legacy_core_is_rejected_by_snell_capability_policy(
    real_sing_box_binary: Path,
) -> None:
    observation = SingBoxCoreStatusInspector(binary=real_sing_box_binary).inspect()
    if observation.version is None or ProtocolCompatibilityPolicy().supports(
        ProtocolKind.SNELL_V6, observation.version
    ):
        pytest.skip("configured core already supports Snell v6")
    with pytest.raises(ProtocolUnsupportedByCore):
        ProtocolCompatibilityPolicy().require_supported(
            ProtocolKind.SNELL_V6, observation.version
        )
```

- [ ] **Step 2: Run deterministic integration structure tests**

Run:

```bash
rtk .venv/bin/pytest tests/integration/test_real_sing_box.py -q
```

Expected: without authorization the module is skipped by its existing fixture;
collection and static fixture construction succeed.

- [ ] **Step 3: Run against an authorized official Stable binary**

Run with the actual local path supplied by the operator:

```bash
rtk env SB_MANAGER_REAL_SING_BOX=/absolute/path/to/sing-box-1.13 .venv/bin/pytest tests/integration/test_real_sing_box.py::test_real_legacy_core_is_rejected_by_snell_capability_policy -q
```

Expected: PASS and no configuration apply or service mutation occurs.

- [ ] **Step 4: Run against an authorized official Preview binary**

Run with the actual local path supplied by the operator:

```bash
rtk env SB_MANAGER_REAL_SING_BOX=/absolute/path/to/sing-box-1.14-preview .venv/bin/pytest tests/integration/test_real_sing_box.py::test_real_snell_capable_core_accepts_generated_v6_config -q
```

Expected: PASS; `sing-box check` accepts the generated v6/default inbound.

- [ ] **Step 5: Record the architecture decision**

Create ADR-0025 with these accepted rules:

- exact observed/planned version is capability truth, never channel name;
- Snell threshold is `1.14.0-alpha.38`;
- unknown versions fail closed only for version-gated protocols;
- all projected profile mutations recheck active compatibility;
- core plans bind desired-state revision and reject active Snell blockers;
- draft/paused Snell does not block Stable; applied/enabled Snell does;
- privileged policy validates shape but performs no version discovery.

Amend ADR-0002 to replace URI-only connection information with typed payloads
and record Snell as a catalog handler.

- [ ] **Step 6: Update operator and maintainer documentation**

Synchronize all listed docs with exact, non-conflicting statements:

- only Snell v6/default/single-PSK is supported;
- Stable 1.13.x cannot apply or resume Snell;
- activate Preview first, then plan again;
- pause/remove every applied Snell profile before switching back to Stable;
- copy the revealed Surge policy and rename it in Surge if desired;
- no `snell://`, v5, multi-user, QUIC proxy, or unsafe mode support;
- deterministic and external test commands remain distinct.

Link the official sing-box inbound/outbound/changelog and Surge policy sources
already cited by the design spec. Record exact tested binary versions and hashes
in acceptance evidence; do not present dated evidence as a production constant.

- [ ] **Step 7: Run documentation consistency checks**

Run:

```bash
rtk rg -n "Snell|snell" README.md docs src/sb_manager/ui/copy_catalog.py
rtk proxy git diff --check
```

Expected: every user-facing reference says v6 and Preview/core threshold; there
is no claim of v5, custom URI, automatic switching, or Stable support.

- [ ] **Step 8: Commit official-core acceptance and documentation**

```bash
rtk git add tests/integration/test_real_sing_box.py docs/adr/0025-core-version-protocol-capabilities.md docs/adr/0002-deep-protocol-catalog.md docs/acceptance/2026-07-18-snell-v6-preview-support.md docs/SDD.md docs/MANUAL.md docs/SUPPORT.md README.md
rtk git commit -m "docs: document Preview-only Snell v6 support"
```

## Task 9: Full Verification, Completion Audit, and Final Review

**Model tier:** Highest available; completion evidence, security review, and cross-slice consistency.

**Files:**
- Verify all files changed since `2d6814f`
- Modify only files required to fix verified failures or acceptance gaps

- [ ] **Step 1: Format and prove formatting is stable**

Run:

```bash
rtk .venv/bin/ruff format .
rtk .venv/bin/ruff format --check .
```

Expected: the check reports all files formatted after the first command.

- [ ] **Step 2: Run lint and strict typing**

Run:

```bash
rtk .venv/bin/ruff check .
rtk .venv/bin/mypy src
```

Expected: no Ruff violations and no mypy issues.

- [ ] **Step 3: Run the complete deterministic suite**

Run:

```bash
rtk .venv/bin/pytest -q
```

Expected: all deterministic tests pass; opt-in external tests skip unless an
authorized binary path is supplied.

- [ ] **Step 4: Build the distributable package**

Run:

```bash
rtk .venv/bin/python -m build
```

Expected: source distribution and wheel build successfully.

- [ ] **Step 5: Re-run authorized real-core evidence**

Run both exact commands from Task 8 using the actual official Stable and Preview
binary paths. Expected: the Stable policy-rejection test passes and Preview
`sing-box check` passes. If either binary is unavailable, report that external
evidence as missing and do not claim full real-core verification.

- [ ] **Step 6: Audit every acceptance criterion against authoritative evidence**

Run:

```bash
rtk git diff --stat 2d6814f..HEAD
rtk git log --oneline 2d6814f..HEAD
rtk git status --short
```

Then verify directly that:

- only `ProtocolKind.SNELL_V6` exists and every emitted inbound has version 6;
- PSKs are generated once, persisted, redacted, and reused;
- Stable/unknown/pre-alpha.38 paths fail before secret generation or host mutation;
- Preview alpha.38+ applies and produces the same PSK in inbound and Surge policy;
- every profile reconfiguration retaining active Snell rechecks the exact core;
- pause/removal recovery works under an externally downgraded core;
- exact and retained core activation reject active Snell blockers and stale state;
- the privileged helper permits only v6/default/single-PSK fields;
- existing protocol URI bytes and Stable behavior remain unchanged;
- TUI work is non-blocking, stale-safe, typed, and secret-safe;
- docs and real-core evidence match production behavior.

- [ ] **Step 7: Run per-slice two-stage reviews**

For each implementation commit, use a fresh specification reviewer against the
complete task text, fix every gap, rerun focused tests, then use a fresh
standards/quality reviewer. Reviewers do not edit the implementation. Mechanical
test or documentation fixes may use medium/lower capacity; compatibility,
privileged policy, and final review use the highest appropriate tier.

- [ ] **Step 8: Run a final cross-slice review**

Review the whole range `2d6814f..HEAD` for:

- design-spec compliance;
- deep-module boundaries and absence of duplicated version parsing;
- version comparison correctness at alpha.37/alpha.38/beta/rc/final boundaries;
- stale plan and mutation ordering;
- PSK disclosure in errors, logs, reprs, fixtures, and TUI;
- privileged exact-field enforcement;
- regressions to existing connection URI content and profile lifecycle behavior.

Fix findings in focused commits with the same RED/GREEN verification discipline.

- [ ] **Step 9: Finish the development branch**

Invoke `superpowers:verification-before-completion` using fresh command output,
then `superpowers:finishing-a-development-branch` to offer merge, push/PR, or
workspace retention. Do not mark the goal complete until every deterministic
criterion and all explicitly authorized external-core checks have authoritative
evidence.
