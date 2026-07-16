"""Protocol-specific configuration builders."""

from sb_manager.protocols.hysteria2 import (
    Hysteria2ConnectionInfo,
    Hysteria2ConnectionSpec,
    Hysteria2InboundSpec,
    Hysteria2Protocol,
)
from sb_manager.protocols.reality import (
    RealityConnectionInfo,
    RealityConnectionSpec,
    RealityInboundSpec,
    RealityMaterial,
    RealityProtocol,
)
from sb_manager.protocols.shadowsocks import (
    ShadowsocksConnectionInfo,
    ShadowsocksConnectionSpec,
    ShadowsocksInboundSpec,
    ShadowsocksProtocol,
)
from sb_manager.protocols.trojan import (
    TrojanConnectionInfo,
    TrojanConnectionSpec,
    TrojanInboundSpec,
    TrojanProtocol,
)
from sb_manager.protocols.tuic import (
    TuicConnectionInfo,
    TuicConnectionSpec,
    TuicInboundSpec,
    TuicProtocol,
)
from sb_manager.protocols.vless_tls import (
    VlessTlsConnectionInfo,
    VlessTlsConnectionSpec,
    VlessTlsInboundSpec,
    VlessTlsProtocol,
)

__all__ = [
    "AnyTlsConnectionInfo",
    "AnyTlsConnectionSpec",
    "AnyTlsInboundSpec",
    "AnyTlsProtocol",
    "Hysteria2ConnectionInfo",
    "Hysteria2ConnectionSpec",
    "Hysteria2InboundSpec",
    "Hysteria2Protocol",
    "RealityConnectionInfo",
    "RealityConnectionSpec",
    "RealityInboundSpec",
    "RealityMaterial",
    "RealityProtocol",
    "ShadowsocksConnectionInfo",
    "ShadowsocksConnectionSpec",
    "ShadowsocksInboundSpec",
    "ShadowsocksProtocol",
    "TrojanConnectionInfo",
    "TrojanConnectionSpec",
    "TrojanInboundSpec",
    "TrojanProtocol",
    "TuicConnectionInfo",
    "TuicConnectionSpec",
    "TuicInboundSpec",
    "TuicProtocol",
    "VlessTlsConnectionInfo",
    "VlessTlsConnectionSpec",
    "VlessTlsInboundSpec",
    "VlessTlsProtocol",
]
from sb_manager.protocols.anytls import (
    AnyTlsConnectionInfo,
    AnyTlsConnectionSpec,
    AnyTlsInboundSpec,
    AnyTlsProtocol,
)
