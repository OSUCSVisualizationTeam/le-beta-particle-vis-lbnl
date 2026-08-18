"""Tests for ServicesManager shutdown ordering."""

from unittest.mock import MagicMock

from le_beta_vis.backend.ServicesManager import ServicesManager


def test_stop_all_stops_polling_before_eps():
    """Polling must stop before EPS: it drains in-flight ingestion work that
    talks to EPS over ZMQ, and that only returns promptly while EPS is
    still alive to reply."""
    # Bypass __init__ (which constructs a real EPSRunner — touches the
    # config file and binds a ZMQ socket) since only stop_all()'s call
    # ordering is under test here.
    manager = ServicesManager.__new__(ServicesManager)
    manager.EPS = MagicMock()
    manager.Polling = MagicMock()

    call_order = []
    manager.Polling.stop.side_effect = lambda: call_order.append("Polling")
    manager.EPS.stop.side_effect = lambda: call_order.append("EPS")

    manager.stop_all()

    assert call_order == ["Polling", "EPS"]
