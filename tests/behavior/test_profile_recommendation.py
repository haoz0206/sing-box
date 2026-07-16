import pytest

from sb_manager.application.profile_recommendation import (
    ProfilePurpose,
    ProfileRecommendationService,
    ProtocolVariant,
)

EXPECTED_RECOMMENDATION_COUNT = 3


def test_general_service_recommendations_start_with_low_setup_complexity() -> None:
    report = ProfileRecommendationService().recommend(ProfilePurpose.GENERAL)

    assert report.purpose is ProfilePurpose.GENERAL
    assert tuple(item.variant for item in report.recommendations) == (
        ProtocolVariant.VLESS_REALITY,
        ProtocolVariant.SHADOWSOCKS,
        ProtocolVariant.TROJAN,
    )
    assert report.recommendations[0].reason == "无需管理自有 TLS 证书，向导所需信息最少"
    assert report.recommendations[0].tradeoff == "客户端必须支持 VLESS Reality"


def test_low_latency_recommendations_expose_udp_dependency() -> None:
    report = ProfileRecommendationService().recommend(ProfilePurpose.LOW_LATENCY)

    assert tuple(item.variant for item in report.recommendations) == (
        ProtocolVariant.HYSTERIA2,
        ProtocolVariant.TUIC,
        ProtocolVariant.VLESS_REALITY,
    )
    assert report.recommendations[0].reason == "QUIC 与专用拥塞控制适合存在丢包的移动链路"
    assert report.recommendations[0].tradeoff == ("必须能稳定使用 UDP; UDP 代理流量特征也更明显")


def test_restricted_network_recommendations_do_not_promise_universal_bypass() -> None:
    report = ProfileRecommendationService().recommend(ProfilePurpose.RESTRICTED_NETWORK)

    assert tuple(item.variant for item in report.recommendations) == (
        ProtocolVariant.VLESS_REALITY,
        ProtocolVariant.ANYTLS,
        ProtocolVariant.VLESS_WEBSOCKET,
    )
    assert report.recommendations[0].reason == "Reality 使用 TCP，且不要求管理自有 TLS 证书"
    assert report.recommendations[0].tradeoff == (
        "不保证适用于所有受限网络; 客户端必须支持 Reality"
    )


def test_compatibility_recommendations_keep_legacy_choice_as_an_explicit_tradeoff() -> None:
    report = ProfileRecommendationService().recommend(ProfilePurpose.COMPATIBILITY)

    assert tuple(item.variant for item in report.recommendations) == (
        ProtocolVariant.TROJAN,
        ProtocolVariant.SHADOWSOCKS,
        ProtocolVariant.VMESS_WEBSOCKET,
    )
    assert report.recommendations[2].reason == "仅在需要兼容既有 VMess 客户端时保留"
    assert report.recommendations[2].tradeoff == "新部署不默认推荐，并需要 TLS 与 WebSocket"


@pytest.mark.parametrize("purpose", tuple(ProfilePurpose))
def test_every_purpose_returns_three_distinct_explained_variants(
    purpose: ProfilePurpose,
) -> None:
    report = ProfileRecommendationService().recommend(purpose)

    assert len(report.recommendations) == EXPECTED_RECOMMENDATION_COUNT
    assert len({item.variant for item in report.recommendations}) == EXPECTED_RECOMMENDATION_COUNT
    assert all(item.reason and item.tradeoff for item in report.recommendations)
