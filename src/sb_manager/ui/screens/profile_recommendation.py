"""Purpose-first protocol recommendation and advanced selection screens."""

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.profile_recommendation import (
    ProfilePurpose,
    ProfileRecommendationAdvisor,
    ProfileRecommendationReport,
    ProtocolVariant,
)

PURPOSE_LABELS: dict[ProfilePurpose, str] = {
    ProfilePurpose.GENERAL: "通用搭建",
    ProfilePurpose.LOW_LATENCY: "移动网络与低延迟",
    ProfilePurpose.RESTRICTED_NETWORK: "受限网络中的连接选择",
    ProfilePurpose.COMPATIBILITY: "兼容既有客户端",
}

VARIANT_LABELS: dict[ProtocolVariant, str] = {
    ProtocolVariant.VLESS_REALITY: "VLESS Reality",
    ProtocolVariant.SHADOWSOCKS: "Shadowsocks 2022",
    ProtocolVariant.HYSTERIA2: "Hysteria2",
    ProtocolVariant.TROJAN: "Trojan",
    ProtocolVariant.ANYTLS: "AnyTLS",
    ProtocolVariant.TUIC: "TUIC",
    ProtocolVariant.VLESS_WEBSOCKET: "VLESS TLS · WebSocket",
    ProtocolVariant.VLESS_GRPC: "VLESS TLS · gRPC",
    ProtocolVariant.VMESS_WEBSOCKET: "VMess TLS · WebSocket",
    ProtocolVariant.VMESS_GRPC: "VMess TLS · gRPC",
}


class ProfilePurposeScreen(Screen[ProtocolVariant | None]):
    """Ask about operator intent before exposing protocol terminology."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, advisor: ProfileRecommendationAdvisor) -> None:
        super().__init__()
        self.advisor = advisor

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profile-purpose"):
            yield Static("你主要想优化什么?", id="profile-purpose-title")
            yield Static(
                "先按使用目的缩小选择范围; 推荐会同时说明限制，不会自动应用配置。",
                id="profile-purpose-guidance",
            )
            yield Button(
                "通用搭建 · 推荐",
                id="purpose-general",
                variant="primary",
            )
            yield Button("移动网络与低延迟", id="purpose-low-latency")
            yield Button(
                "受限网络中的连接选择",
                id="purpose-restricted-network",
            )
            yield Button("兼容既有客户端", id="purpose-compatibility")
            yield Button(
                "直接选择协议 · 高级",
                id="choose-protocol-directly",
            )
        yield Footer()

    @on(
        Button.Pressed,
        "#purpose-general, #purpose-low-latency, "
        "#purpose-restricted-network, #purpose-compatibility",
    )
    def show_recommendations(self, event: Button.Pressed) -> None:
        purposes = {
            "purpose-general": ProfilePurpose.GENERAL,
            "purpose-low-latency": ProfilePurpose.LOW_LATENCY,
            "purpose-restricted-network": ProfilePurpose.RESTRICTED_NETWORK,
            "purpose-compatibility": ProfilePurpose.COMPATIBILITY,
        }
        purpose = purposes[event.button.id or ""]
        self.app.push_screen(
            ProfileRecommendationScreen(self.advisor.recommend(purpose)),
            self.finish_selection,
        )

    def finish_selection(self, variant: ProtocolVariant | None) -> None:
        if variant is not None:
            self.dismiss(variant)

    @on(Button.Pressed, "#choose-protocol-directly")
    def choose_protocol_directly(self) -> None:
        self.app.push_screen(
            DirectProtocolSelectionScreen(),
            self.finish_selection,
        )


class ProfileRecommendationScreen(Screen[ProtocolVariant | None]):
    """Present ranked choices with reasons and costs before selection."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, report: ProfileRecommendationReport) -> None:
        super().__init__()
        self.report = report

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profile-recommendation"):
            yield Static(
                f"{PURPOSE_LABELS[self.report.purpose]}的推荐顺序",
                id="profile-recommendation-title",
            )
            yield Static(
                "推荐只帮助缩小选择，不承诺连通性或适用于所有网络。",
                id="profile-recommendation-caveat",
            )
            for index, recommendation in enumerate(self.report.recommendations):
                label = VARIANT_LABELS[recommendation.variant]
                yield Static(
                    f"{index + 1}. {label}{' · 首选' if index == 0 else ''}",
                    id=f"recommendation-{index}-name",
                )
                yield Static(
                    f"适合原因：{recommendation.reason}",
                    id=f"recommendation-{index}-reason",
                )
                yield Static(
                    f"需要注意：{recommendation.tradeoff}",
                    id=f"recommendation-{index}-tradeoff",
                )
                yield Button(
                    f"使用 {label}",
                    id=f"select-recommendation-{index}",
                    name=recommendation.variant.value,
                    classes="recommendation-choice",
                    variant="primary" if index == 0 else "default",
                )
        yield Footer()

    @on(Button.Pressed, ".recommendation-choice")
    def select_recommendation(self, event: Button.Pressed) -> None:
        if event.button.name is not None:
            self.dismiss(ProtocolVariant(event.button.name))


class DirectProtocolSelectionScreen(Screen[ProtocolVariant | None]):
    """Expose every exact guided variant for operators who already chose."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]
    CHOICES: ClassVar[tuple[tuple[ProtocolVariant, str, str], ...]] = (
        (ProtocolVariant.VLESS_REALITY, "vless-reality", "VLESS Reality"),
        (ProtocolVariant.SHADOWSOCKS, "shadowsocks", "Shadowsocks 2022 · 简洁稳定"),
        (ProtocolVariant.HYSTERIA2, "hysteria2", "Hysteria2 · 移动网络"),
        (ProtocolVariant.TROJAN, "trojan", "Trojan · TLS 兼容"),
        (ProtocolVariant.ANYTLS, "anytls", "AnyTLS · 抗 TLS 嵌套指纹"),
        (ProtocolVariant.TUIC, "tuic", "TUIC · QUIC 低延迟"),
        (
            ProtocolVariant.VLESS_WEBSOCKET,
            "vless-websocket",
            "VLESS TLS · WebSocket/CDN",
        ),
        (ProtocolVariant.VLESS_GRPC, "vless-grpc", "VLESS TLS · gRPC"),
        (
            ProtocolVariant.VMESS_WEBSOCKET,
            "vmess-websocket",
            "VMess TLS · 旧客户端兼容",
        ),
        (ProtocolVariant.VMESS_GRPC, "vmess-grpc", "VMess TLS · gRPC 兼容"),
    )

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="protocol-selection"):
            yield Static("直接选择协议", id="protocol-selection-title")
            yield Static(
                "这里不再排序; 请只选择你确认客户端和网络都支持的协议。",
                id="protocol-selection-guidance",
            )
            for variant, button_id, label in self.CHOICES:
                yield Button(
                    label,
                    id=f"protocol-{button_id}",
                    name=variant.value,
                    classes="direct-protocol-choice",
                )
        yield Footer()

    @on(Button.Pressed, ".direct-protocol-choice")
    def select_protocol(self, event: Button.Pressed) -> None:
        if event.button.name is not None:
            self.dismiss(ProtocolVariant(event.button.name))
