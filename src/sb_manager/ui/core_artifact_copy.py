"""Map typed artifact evidence to validated interface copy identities."""

from sb_manager.application.core_update import CoreUpdateWarning
from sb_manager.seams.artifact_source import CoreArtifactTrustMode
from sb_manager.ui.copy_catalog import UiText

WARNING_COPY: dict[CoreUpdateWarning, UiText] = {
    CoreUpdateWarning.PRERELEASE_COMPATIBILITY_RISK: (UiText.CORE_UPDATE_PLAN_WARNING_PRERELEASE),
    CoreUpdateWarning.DIGEST_PINNED_MUTABLE_RELEASE: (
        UiText.CORE_UPDATE_PLAN_WARNING_MUTABLE_RELEASE
    ),
}

TRUST_COPY: dict[CoreArtifactTrustMode, UiText] = {
    CoreArtifactTrustMode.IMMUTABLE_RELEASE: UiText.CORE_UPDATE_TRUST_IMMUTABLE,
    CoreArtifactTrustMode.DIGEST_PINNED_STABLE: UiText.CORE_UPDATE_TRUST_DIGEST_PINNED,
}
