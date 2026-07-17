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
    RecommendationRationale,
)
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText

PURPOSE_LABELS: dict[ProfilePurpose, UiText] = {
    ProfilePurpose.GENERAL: UiText.PROFILE_RECOMMENDATION_PURPOSE_GENERAL,
    ProfilePurpose.LOW_LATENCY: UiText.PROFILE_RECOMMENDATION_PURPOSE_LOW_LATENCY,
    ProfilePurpose.RESTRICTED_NETWORK: (UiText.PROFILE_RECOMMENDATION_PURPOSE_RESTRICTED_NETWORK),
    ProfilePurpose.COMPATIBILITY: UiText.PROFILE_RECOMMENDATION_PURPOSE_COMPATIBILITY,
}

VARIANT_LABELS: dict[ProtocolVariant, UiText] = {
    ProtocolVariant.VLESS_REALITY: UiText.PROFILE_RECOMMENDATION_VARIANT_VLESS_REALITY,
    ProtocolVariant.SHADOWSOCKS: UiText.PROFILE_RECOMMENDATION_VARIANT_SHADOWSOCKS,
    ProtocolVariant.HYSTERIA2: UiText.PROFILE_RECOMMENDATION_VARIANT_HYSTERIA2,
    ProtocolVariant.TROJAN: UiText.PROFILE_RECOMMENDATION_VARIANT_TROJAN,
    ProtocolVariant.ANYTLS: UiText.PROFILE_RECOMMENDATION_VARIANT_ANYTLS,
    ProtocolVariant.TUIC: UiText.PROFILE_RECOMMENDATION_VARIANT_TUIC,
    ProtocolVariant.VLESS_WEBSOCKET: (UiText.PROFILE_RECOMMENDATION_VARIANT_VLESS_WEBSOCKET),
    ProtocolVariant.VLESS_GRPC: UiText.PROFILE_RECOMMENDATION_VARIANT_VLESS_GRPC,
    ProtocolVariant.VMESS_WEBSOCKET: (UiText.PROFILE_RECOMMENDATION_VARIANT_VMESS_WEBSOCKET),
    ProtocolVariant.VMESS_GRPC: UiText.PROFILE_RECOMMENDATION_VARIANT_VMESS_GRPC,
}

RATIONALE_COPY: dict[RecommendationRationale, tuple[UiText, UiText]] = {
    RecommendationRationale.GENERAL_VLESS_REALITY: (
        UiText.PROFILE_RECOMMENDATION_GENERAL_VLESS_REALITY_REASON,
        UiText.PROFILE_RECOMMENDATION_GENERAL_VLESS_REALITY_TRADEOFF,
    ),
    RecommendationRationale.GENERAL_SHADOWSOCKS: (
        UiText.PROFILE_RECOMMENDATION_GENERAL_SHADOWSOCKS_REASON,
        UiText.PROFILE_RECOMMENDATION_GENERAL_SHADOWSOCKS_TRADEOFF,
    ),
    RecommendationRationale.GENERAL_TROJAN: (
        UiText.PROFILE_RECOMMENDATION_GENERAL_TROJAN_REASON,
        UiText.PROFILE_RECOMMENDATION_GENERAL_TROJAN_TRADEOFF,
    ),
    RecommendationRationale.LOW_LATENCY_HYSTERIA2: (
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_HYSTERIA2_REASON,
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_HYSTERIA2_TRADEOFF,
    ),
    RecommendationRationale.LOW_LATENCY_TUIC: (
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_TUIC_REASON,
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_TUIC_TRADEOFF,
    ),
    RecommendationRationale.LOW_LATENCY_VLESS_REALITY: (
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_VLESS_REALITY_REASON,
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_VLESS_REALITY_TRADEOFF,
    ),
    RecommendationRationale.RESTRICTED_NETWORK_VLESS_REALITY: (
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_VLESS_REALITY_REASON,
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_VLESS_REALITY_TRADEOFF,
    ),
    RecommendationRationale.RESTRICTED_NETWORK_ANYTLS: (
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_ANYTLS_REASON,
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_ANYTLS_TRADEOFF,
    ),
    RecommendationRationale.RESTRICTED_NETWORK_VLESS_WEBSOCKET: (
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_VLESS_WEBSOCKET_REASON,
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_VLESS_WEBSOCKET_TRADEOFF,
    ),
    RecommendationRationale.COMPATIBILITY_TROJAN: (
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_TROJAN_REASON,
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_TROJAN_TRADEOFF,
    ),
    RecommendationRationale.COMPATIBILITY_SHADOWSOCKS: (
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_SHADOWSOCKS_REASON,
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_SHADOWSOCKS_TRADEOFF,
    ),
    RecommendationRationale.COMPATIBILITY_VMESS_WEBSOCKET: (
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_VMESS_WEBSOCKET_REASON,
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_VMESS_WEBSOCKET_TRADEOFF,
    ),
}


class ProfilePurposeScreen(Screen[ProtocolVariant | None]):
    """Ask about operator intent before exposing protocol terminology."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        advisor: ProfileRecommendationAdvisor,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.advisor = advisor
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profile-purpose"):
            yield Static(
                self.copy.text(UiText.PROFILE_RECOMMENDATION_PURPOSE_TITLE),
                id="profile-purpose-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_RECOMMENDATION_PURPOSE_GUIDANCE),
                id="profile-purpose-guidance",
                markup=False,
            )
            yield Button(
                self.copy.text(
                    UiText.PROFILE_RECOMMENDATION_PURPOSE_CHOICE_RECOMMENDED,
                    purpose=self.copy.text(PURPOSE_LABELS[ProfilePurpose.GENERAL]),
                ),
                id="purpose-general",
                variant="primary",
            )
            yield Button(
                self.copy.text(PURPOSE_LABELS[ProfilePurpose.LOW_LATENCY]),
                id="purpose-low-latency",
            )
            yield Button(
                self.copy.text(PURPOSE_LABELS[ProfilePurpose.RESTRICTED_NETWORK]),
                id="purpose-restricted-network",
            )
            yield Button(
                self.copy.text(PURPOSE_LABELS[ProfilePurpose.COMPATIBILITY]),
                id="purpose-compatibility",
            )
            yield Button(
                self.copy.text(UiText.PROFILE_RECOMMENDATION_PURPOSE_CHOOSE_DIRECTLY),
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
        try:
            report = self.advisor.recommend(purpose)
        except Exception:
            self.app.push_screen(
                ProfileRecommendationErrorScreen(self.copy),
                self.finish_selection,
            )
            return
        self.app.push_screen(
            ProfileRecommendationScreen(report, self.copy),
            self.finish_selection,
        )

    def finish_selection(self, variant: ProtocolVariant | None) -> None:
        if variant is not None:
            self.dismiss(variant)

    @on(Button.Pressed, "#choose-protocol-directly")
    def choose_protocol_directly(self) -> None:
        self.app.push_screen(
            DirectProtocolSelectionScreen(self.copy),
            self.finish_selection,
        )


class ProfileRecommendationErrorScreen(Screen[ProtocolVariant | None]):
    """Keep an unavailable recommendation policy from blocking advanced setup."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profile-recommendation-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_RECOMMENDATION_ERROR_TITLE),
                id="profile-recommendation-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_RECOMMENDATION_ERROR_DETAILS),
                id="profile-recommendation-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_RECOMMENDATION_ERROR_SAFETY),
                id="profile-recommendation-error-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.PROFILE_RECOMMENDATION_ERROR_CHOOSE_DIRECTLY),
                id="recommendation-error-choose-directly",
                variant="primary",
            )
        yield Footer()

    @on(Button.Pressed, "#recommendation-error-choose-directly")
    def choose_protocol_directly(self) -> None:
        self.app.push_screen(
            DirectProtocolSelectionScreen(self.copy),
            self.finish_selection,
        )

    def finish_selection(self, variant: ProtocolVariant | None) -> None:
        if variant is not None:
            self.dismiss(variant)


class ProfileRecommendationScreen(Screen[ProtocolVariant | None]):
    """Present ranked choices with reasons and costs before selection."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        report: ProfileRecommendationReport,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.report = report
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profile-recommendation"):
            yield Static(
                self.copy.text(
                    UiText.PROFILE_RECOMMENDATION_RANKING_TITLE,
                    purpose=self.copy.text(PURPOSE_LABELS[self.report.purpose]),
                ),
                id="profile-recommendation-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_RECOMMENDATION_RANKING_CAVEAT),
                id="profile-recommendation-caveat",
                markup=False,
            )
            for index, recommendation in enumerate(self.report.recommendations):
                label = self.copy.text(VARIANT_LABELS[recommendation.variant])
                reason_key, tradeoff_key = RATIONALE_COPY[recommendation.rationale]
                yield Static(
                    self.copy.text(
                        (
                            UiText.PROFILE_RECOMMENDATION_RANKING_CHOICE_PRIMARY
                            if index == 0
                            else UiText.PROFILE_RECOMMENDATION_RANKING_CHOICE
                        ),
                        rank=index + 1,
                        label=label,
                    ),
                    id=f"recommendation-{index}-name",
                    markup=False,
                )
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_RECOMMENDATION_RANKING_REASON,
                        reason=self.copy.text(reason_key),
                    ),
                    id=f"recommendation-{index}-reason",
                    markup=False,
                )
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_RECOMMENDATION_RANKING_TRADEOFF,
                        tradeoff=self.copy.text(tradeoff_key),
                    ),
                    id=f"recommendation-{index}-tradeoff",
                    markup=False,
                )
                yield Button(
                    self.copy.text(
                        UiText.PROFILE_RECOMMENDATION_RANKING_SELECT,
                        label=label,
                    ),
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

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]
    CHOICES: ClassVar[tuple[tuple[ProtocolVariant, str, UiText], ...]] = (
        (
            ProtocolVariant.VLESS_REALITY,
            "vless-reality",
            UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_VLESS_REALITY,
        ),
        (
            ProtocolVariant.SHADOWSOCKS,
            "shadowsocks",
            UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_SHADOWSOCKS,
        ),
        (
            ProtocolVariant.HYSTERIA2,
            "hysteria2",
            UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_HYSTERIA2,
        ),
        (
            ProtocolVariant.TROJAN,
            "trojan",
            UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_TROJAN,
        ),
        (
            ProtocolVariant.ANYTLS,
            "anytls",
            UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_ANYTLS,
        ),
        (
            ProtocolVariant.TUIC,
            "tuic",
            UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_TUIC,
        ),
        (
            ProtocolVariant.VLESS_WEBSOCKET,
            "vless-websocket",
            UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_VLESS_WEBSOCKET,
        ),
        (
            ProtocolVariant.VLESS_GRPC,
            "vless-grpc",
            UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_VLESS_GRPC,
        ),
        (
            ProtocolVariant.VMESS_WEBSOCKET,
            "vmess-websocket",
            UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_VMESS_WEBSOCKET,
        ),
        (
            ProtocolVariant.VMESS_GRPC,
            "vmess-grpc",
            UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_VMESS_GRPC,
        ),
    )

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="protocol-selection"):
            yield Static(
                self.copy.text(UiText.PROFILE_RECOMMENDATION_DIRECT_TITLE),
                id="protocol-selection-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_RECOMMENDATION_DIRECT_GUIDANCE),
                id="protocol-selection-guidance",
                markup=False,
            )
            for variant, button_id, label_key in self.CHOICES:
                yield Button(
                    self.copy.text(label_key),
                    id=f"protocol-{button_id}",
                    name=variant.value,
                    classes="direct-protocol-choice",
                )
        yield Footer()

    @on(Button.Pressed, ".direct-protocol-choice")
    def select_protocol(self, event: Button.Pressed) -> None:
        if event.button.name is not None:
            self.dismiss(ProtocolVariant(event.button.name))
