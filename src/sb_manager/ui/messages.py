"""UI-level requests that keep screens independent from application internals."""

from textual.message import Message


class DashboardRefreshRequested(Message):
    """Rebuild the root dashboard and restart all configured observations."""
