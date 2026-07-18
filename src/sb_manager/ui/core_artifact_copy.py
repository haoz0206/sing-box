"""Map typed artifact evidence to validated interface copy and widgets."""

from collections.abc import Iterator

from textual.widgets import Static

from sb_manager.application.core_update import CoreUpdateWarning
from sb_manager.seams.artifact_source import CoreArtifactTrustMode, PlannedCoreArtifact
from sb_manager.ui.copy_catalog import CopyCatalog, UiText

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


def artifact_evidence_widgets(
    copy_catalog: CopyCatalog,
    artifact: PlannedCoreArtifact,
    *,
    field_id_prefix: str,
) -> Iterator[Static]:
    """Compose shared frozen-artifact fields without owning screen layout."""

    yield Static(
        copy_catalog.text(UiText.CORE_UPDATE_PLAN_ASSET, asset=artifact.asset_name),
        id=f"{field_id_prefix}-asset",
        markup=False,
    )
    yield Static(
        copy_catalog.text(UiText.CORE_UPDATE_PLAN_SHA256, sha256=artifact.sha256),
        id=f"{field_id_prefix}-sha256",
        markup=False,
    )
    yield Static(
        copy_catalog.text(
            UiText.CORE_UPDATE_PLAN_TRUST,
            trust=copy_catalog.text(TRUST_COPY[artifact.trust_mode]),
        ),
        id=f"{field_id_prefix}-trust",
        markup=False,
    )


def artifact_warning_widgets(
    copy_catalog: CopyCatalog,
    warnings: tuple[CoreUpdateWarning, ...],
    *,
    warning_id_prefix: str,
) -> Iterator[Static]:
    """Compose typed artifact warnings under a caller-owned DOM prefix."""

    for index, warning in enumerate(warnings):
        yield Static(
            copy_catalog.text(WARNING_COPY[warning]),
            id=f"{warning_id_prefix}-{index}",
            markup=False,
        )
