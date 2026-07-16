"""Purpose-first protocol recommendations for the guided profile wizard."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ProfilePurpose(str, Enum):
    """The operator outcome used to rank supported protocol choices."""

    GENERAL = "general"
    LOW_LATENCY = "low-latency"
    RESTRICTED_NETWORK = "restricted-network"
    COMPATIBILITY = "compatibility"


class ProtocolVariant(str, Enum):
    """One exact guided form, including transport when the protocol needs it."""

    VLESS_REALITY = "vless-reality"
    SHADOWSOCKS = "shadowsocks-2022"
    HYSTERIA2 = "hysteria2"
    TROJAN = "trojan"
    ANYTLS = "anytls"
    TUIC = "tuic"
    VLESS_WEBSOCKET = "vless-websocket"
    VLESS_GRPC = "vless-grpc"
    VMESS_WEBSOCKET = "vmess-websocket"
    VMESS_GRPC = "vmess-grpc"


@dataclass(frozen=True, slots=True)
class ProtocolRecommendation:
    """One ranked choice with enough evidence to make its cost visible."""

    variant: ProtocolVariant
    reason: str
    tradeoff: str


@dataclass(frozen=True, slots=True)
class ProfileRecommendationReport:
    """An ordered protocol shortlist for one operator purpose."""

    purpose: ProfilePurpose
    recommendations: tuple[ProtocolRecommendation, ...]


class ProfileRecommendationAdvisor(Protocol):
    """Public application seam consumed by the purpose-first TUI."""

    def recommend(self, purpose: ProfilePurpose) -> ProfileRecommendationReport: ...


class ProfileRecommendationService:
    """Keep recommendation policy and operator copy out of Textual screens."""

    def recommend(self, purpose: ProfilePurpose) -> ProfileRecommendationReport:
        if purpose is ProfilePurpose.COMPATIBILITY:
            return ProfileRecommendationReport(
                purpose=purpose,
                recommendations=(
                    ProtocolRecommendation(
                        variant=ProtocolVariant.TROJAN,
                        reason="密码认证与标准 TLS 组合便于对照既有 TLS 客户端",
                        tradeoff="需要可解析的域名和可用证书",
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.SHADOWSOCKS,
                        reason="协议认知广，manager 使用官方推荐的 AEAD 2022 方法",
                        tradeoff="旧客户端可能不支持 Shadowsocks 2022",
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.VMESS_WEBSOCKET,
                        reason="仅在需要兼容既有 VMess 客户端时保留",
                        tradeoff="新部署不默认推荐，并需要 TLS 与 WebSocket",
                    ),
                ),
            )
        if purpose is ProfilePurpose.RESTRICTED_NETWORK:
            return ProfileRecommendationReport(
                purpose=purpose,
                recommendations=(
                    ProtocolRecommendation(
                        variant=ProtocolVariant.VLESS_REALITY,
                        reason="Reality 使用 TCP，且不要求管理自有 TLS 证书",
                        tradeoff="不保证适用于所有受限网络; 客户端必须支持 Reality",
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.ANYTLS,
                        reason="TLS、填充和多路复用组合提供另一种 TCP 方案",
                        tradeoff="需要域名、证书和支持 AnyTLS 的较新客户端",
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.VLESS_WEBSOCKET,
                        reason="TLS WebSocket 适合明确需要 HTTP 兼容传输的场景",
                        tradeoff="配置项更多，且同样不保证适用于所有受限网络",
                    ),
                ),
            )
        if purpose is ProfilePurpose.LOW_LATENCY:
            return ProfileRecommendationReport(
                purpose=purpose,
                recommendations=(
                    ProtocolRecommendation(
                        variant=ProtocolVariant.HYSTERIA2,
                        reason="QUIC 与专用拥塞控制适合存在丢包的移动链路",
                        tradeoff="必须能稳定使用 UDP; UDP 代理流量特征也更明显",
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.TUIC,
                        reason="QUIC 传输支持多路复用和可选拥塞控制策略",
                        tradeoff="需要 UDP、TLS 和支持 TUIC 的客户端",
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.VLESS_REALITY,
                        reason="不依赖 UDP，可作为移动网络中的 TCP 备选",
                        tradeoff="高丢包链路没有 Hysteria2 的专用拥塞控制",
                    ),
                ),
            )
        return ProfileRecommendationReport(
            purpose=purpose,
            recommendations=(
                ProtocolRecommendation(
                    variant=ProtocolVariant.VLESS_REALITY,
                    reason="无需管理自有 TLS 证书，向导所需信息最少",
                    tradeoff="客户端必须支持 VLESS Reality",
                ),
                ProtocolRecommendation(
                    variant=ProtocolVariant.SHADOWSOCKS,
                    reason="配置字段少，并使用官方推荐的 AEAD 2022 方法",
                    tradeoff="客户端必须支持 Shadowsocks 2022",
                ),
                ProtocolRecommendation(
                    variant=ProtocolVariant.TROJAN,
                    reason="使用标准 TLS 证书路径，适合作为常规 TLS 方案",
                    tradeoff="需要可解析的域名和可用证书",
                ),
            ),
        )
