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


class RecommendationRationale(str, Enum):
    """Stable recommendation evidence rendered by the presentation catalog."""

    GENERAL_VLESS_REALITY = "general.vless-reality"
    GENERAL_SHADOWSOCKS = "general.shadowsocks"
    GENERAL_TROJAN = "general.trojan"
    LOW_LATENCY_HYSTERIA2 = "low-latency.hysteria2"
    LOW_LATENCY_TUIC = "low-latency.tuic"
    LOW_LATENCY_VLESS_REALITY = "low-latency.vless-reality"
    RESTRICTED_NETWORK_VLESS_REALITY = "restricted-network.vless-reality"
    RESTRICTED_NETWORK_ANYTLS = "restricted-network.anytls"
    RESTRICTED_NETWORK_VLESS_WEBSOCKET = "restricted-network.vless-websocket"
    COMPATIBILITY_TROJAN = "compatibility.trojan"
    COMPATIBILITY_SHADOWSOCKS = "compatibility.shadowsocks"
    COMPATIBILITY_VMESS_WEBSOCKET = "compatibility.vmess-websocket"


@dataclass(frozen=True, slots=True)
class ProtocolRecommendation:
    """One ranked choice with enough evidence to make its cost visible."""

    variant: ProtocolVariant
    rationale: RecommendationRationale


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
                        rationale=RecommendationRationale.COMPATIBILITY_TROJAN,
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.SHADOWSOCKS,
                        rationale=RecommendationRationale.COMPATIBILITY_SHADOWSOCKS,
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.VMESS_WEBSOCKET,
                        rationale=RecommendationRationale.COMPATIBILITY_VMESS_WEBSOCKET,
                    ),
                ),
            )
        if purpose is ProfilePurpose.RESTRICTED_NETWORK:
            return ProfileRecommendationReport(
                purpose=purpose,
                recommendations=(
                    ProtocolRecommendation(
                        variant=ProtocolVariant.VLESS_REALITY,
                        rationale=RecommendationRationale.RESTRICTED_NETWORK_VLESS_REALITY,
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.ANYTLS,
                        rationale=RecommendationRationale.RESTRICTED_NETWORK_ANYTLS,
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.VLESS_WEBSOCKET,
                        rationale=RecommendationRationale.RESTRICTED_NETWORK_VLESS_WEBSOCKET,
                    ),
                ),
            )
        if purpose is ProfilePurpose.LOW_LATENCY:
            return ProfileRecommendationReport(
                purpose=purpose,
                recommendations=(
                    ProtocolRecommendation(
                        variant=ProtocolVariant.HYSTERIA2,
                        rationale=RecommendationRationale.LOW_LATENCY_HYSTERIA2,
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.TUIC,
                        rationale=RecommendationRationale.LOW_LATENCY_TUIC,
                    ),
                    ProtocolRecommendation(
                        variant=ProtocolVariant.VLESS_REALITY,
                        rationale=RecommendationRationale.LOW_LATENCY_VLESS_REALITY,
                    ),
                ),
            )
        return ProfileRecommendationReport(
            purpose=purpose,
            recommendations=(
                ProtocolRecommendation(
                    variant=ProtocolVariant.VLESS_REALITY,
                    rationale=RecommendationRationale.GENERAL_VLESS_REALITY,
                ),
                ProtocolRecommendation(
                    variant=ProtocolVariant.SHADOWSOCKS,
                    rationale=RecommendationRationale.GENERAL_SHADOWSOCKS,
                ),
                ProtocolRecommendation(
                    variant=ProtocolVariant.TROJAN,
                    rationale=RecommendationRationale.GENERAL_TROJAN,
                ),
            ),
        )
