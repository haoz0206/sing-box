from typing import cast

from textual.widgets import Static

from sb_manager.application.host_readiness import (
    HostReadinessItem,
    HostReadinessItemCode,
    HostReadinessReport,
    ReadinessState,
)
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools, ManagerAppInterfaceTools
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


class HostReadinessMarkerCatalog:
    """Render markers for Host Readiness copy while delegating established keys."""

    def text(self, key: UiText, /, **values: object) -> str:
        markers = {
            "host_readiness.title": "目录主机准备度",
            "host_readiness.summary.ready": "目录已满足前置条件",
            "host_readiness.recheck": "目录完成调整后复检",
            "host_readiness.state.ready": "[目录就绪]",
            "host_readiness.state.attention": "[目录注意]",
            "host_readiness.state.action_required": "[目录需处理]",
            "host_readiness.details.unavailable": "目录无诊断",
        }
        if key.value == "host_readiness.summary.action_required":
            return f"目录待处理<{values['count']}>"
        if key.value == "host_readiness.item.title":
            return f"目录检查<{values['state']}|{values['title']}>"
        if key.value == "host_readiness.item.guidance":
            return f"目录下一步<{values['guidance']}>"
        if marker := markers.get(key.value):
            return marker
        return SIMPLIFIED_CHINESE.text(key, **values)


class FixedHostReadiness:
    def __init__(self, report: HostReadinessReport) -> None:
        self.report = report

    def inspect(self) -> HostReadinessReport:
        return self.report


def required_helper_report() -> HostReadinessReport:
    return HostReadinessReport(
        items=(
            HostReadinessItem(
                code=HostReadinessItemCode.PRIVILEGED_HELPER,
                state=ReadinessState.ACTION_REQUIRED,
                title="最小权限 helper",
                summary="最小权限 helper 尚不可用",
                diagnostics="helper unavailable",
                guidance="安装最小权限策略后重新检查。",
            ),
        )
    )


async def test_host_readiness_framing_copy_comes_from_the_interface_catalog() -> None:
    app = ManagerApp(
        host_tools=ManagerAppHostTools(
            host_readiness=FixedHostReadiness(required_helper_report()),
        ),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, HostReadinessMarkerCatalog()),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#view-readiness")

        assert app.screen.query_one("#host-readiness-title", Static).content == ("目录主机准备度")
        assert app.screen.query_one("#host-readiness-summary", Static).content == ("目录待处理<1>")
        assert app.screen.query_one("#host-readiness-recheck", Static).content == (
            "目录完成调整后复检"
        )


async def test_host_readiness_check_copy_comes_from_catalog_and_evidence_stays_literal() -> None:
    report = HostReadinessReport(
        items=(
            HostReadinessItem(
                code=HostReadinessItemCode.PRIVILEGED_HELPER,
                state=ReadinessState.ATTENTION,
                title="[helper]",
                summary="[summary]",
                diagnostics="",
                guidance="[run policy]",
            ),
        )
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(host_readiness=FixedHostReadiness(report)),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, HostReadinessMarkerCatalog()),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#view-readiness")

        title = app.screen.query_one("#readiness-privileged-helper-title", Static)
        overall = app.screen.query_one("#host-readiness-summary", Static)
        summary = app.screen.query_one("#readiness-privileged-helper-summary", Static)
        diagnostics = app.screen.query_one("#readiness-privileged-helper-diagnostics", Static)
        guidance = app.screen.query_one("#readiness-privileged-helper-guidance", Static)

        assert title.content == "目录检查<[目录注意]|[helper]>"
        assert overall.content == "目录已满足前置条件"
        assert summary.content == "[summary]"
        assert diagnostics.content == "目录无诊断"
        assert guidance.content == "目录下一步<[run policy]>"
        assert title.render().plain == title.content
        assert summary.render().plain == summary.content
        assert diagnostics.render().plain == diagnostics.content
        assert guidance.render().plain == guidance.content
