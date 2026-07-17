import pytest

from sb_manager.application.profile_recommendation import (
    ProfilePurpose,
    ProfileRecommendationService,
    ProtocolVariant,
    RecommendationRationale,
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
    assert report.recommendations[0].rationale is RecommendationRationale.GENERAL_VLESS_REALITY


def test_low_latency_recommendations_expose_udp_dependency() -> None:
    report = ProfileRecommendationService().recommend(ProfilePurpose.LOW_LATENCY)

    assert tuple(item.variant for item in report.recommendations) == (
        ProtocolVariant.HYSTERIA2,
        ProtocolVariant.TUIC,
        ProtocolVariant.VLESS_REALITY,
    )
    assert report.recommendations[0].rationale is RecommendationRationale.LOW_LATENCY_HYSTERIA2


def test_restricted_network_recommendations_do_not_promise_universal_bypass() -> None:
    report = ProfileRecommendationService().recommend(ProfilePurpose.RESTRICTED_NETWORK)

    assert tuple(item.variant for item in report.recommendations) == (
        ProtocolVariant.VLESS_REALITY,
        ProtocolVariant.ANYTLS,
        ProtocolVariant.VLESS_WEBSOCKET,
    )
    assert (
        report.recommendations[0].rationale
        is RecommendationRationale.RESTRICTED_NETWORK_VLESS_REALITY
    )


def test_compatibility_recommendations_keep_legacy_choice_as_an_explicit_tradeoff() -> None:
    report = ProfileRecommendationService().recommend(ProfilePurpose.COMPATIBILITY)

    assert tuple(item.variant for item in report.recommendations) == (
        ProtocolVariant.TROJAN,
        ProtocolVariant.SHADOWSOCKS,
        ProtocolVariant.VMESS_WEBSOCKET,
    )
    assert (
        report.recommendations[2].rationale is RecommendationRationale.COMPATIBILITY_VMESS_WEBSOCKET
    )


@pytest.mark.parametrize("purpose", tuple(ProfilePurpose))
def test_every_purpose_returns_three_distinct_explained_variants(
    purpose: ProfilePurpose,
) -> None:
    report = ProfileRecommendationService().recommend(purpose)

    assert len(report.recommendations) == EXPECTED_RECOMMENDATION_COUNT
    assert len({item.variant for item in report.recommendations}) == EXPECTED_RECOMMENDATION_COUNT
    assert len({item.rationale for item in report.recommendations}) == EXPECTED_RECOMMENDATION_COUNT
