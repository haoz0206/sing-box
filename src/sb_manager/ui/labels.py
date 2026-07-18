"""Stable operator-facing labels shared by Textual screens."""

from sb_manager.domain.installation import ProtocolKind

PROTOCOL_LABELS: dict[ProtocolKind, str] = {
    ProtocolKind.VLESS_REALITY: "VLESS Reality",
    ProtocolKind.SHADOWSOCKS: "Shadowsocks 2022",
    ProtocolKind.HYSTERIA2: "Hysteria2",
    ProtocolKind.TROJAN: "Trojan",
    ProtocolKind.ANYTLS: "AnyTLS",
    ProtocolKind.TUIC: "TUIC",
    ProtocolKind.VLESS_TLS: "VLESS TLS",
    ProtocolKind.VMESS_TLS: "VMess TLS",
    ProtocolKind.SNELL_V6: "Snell v6",
}
