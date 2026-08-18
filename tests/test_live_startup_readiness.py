"""Live/manual-verification tests for EPS startup-readiness broadcasting.

Everything else in this feature is unit-tested with mocks. Mocks can't
catch the regression class this design specifically depends on: real
socket binding to the right endpoint, envelopes actually surviving a real
ZMQ PUB/SUB round trip, and — the one that matters most — the "slow
joiner" mitigation actually preventing the race it was designed to
prevent. These tests touch real ``zmq`` sockets and (for one test) a real
``EventPersistence`` background thread — not mocked. No ``QApplication``
is used, so — unlike ``test_live_ipc_fallback.py``'s dialog-rendering
test — none of these need a ``--ignore`` entry in
``python-package-conda.yml``; the ``skipif`` gate alone is sufficient in
headless CI.

Skipped by default; set ``LBNLVIS_LIVE_TESTS=1`` to run:

    LBNLVIS_LIVE_TESTS=1 uv run pytest tests/test_live_startup_readiness.py -v

Follows the ``tests/test_live_ipc_fallback.py`` convention (see that
file's docstring).
"""

import os
import threading
import time
from unittest.mock import patch

import pytest
import zmq

from le_beta_vis.backend.EventPersistenceService import EventPersistence
from le_beta_vis.common.EPSStartupSignals import (
    EPS_STARTUP_STATUS_EVENT,
    EPSStartupSignals,
)
from le_beta_vis.common.EventHandler import EventHandler
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)
from le_beta_vis.common.ZMQEventHandlerSource import ZMQEventHandlerSource
from le_beta_vis.frontend.viewmodels.StartupReadinessViewModel import (
    StartupReadinessViewModel,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("LBNLVIS_LIVE_TESTS") != "1",
    reason="Live/manual-verification test; set LBNLVIS_LIVE_TESTS=1 to run.",
)

_POLL_DEADLINE_S = 5.0
_POLL_INTERVAL_S = 0.05


def _wait_for_ready(vm: StartupReadinessViewModel):
    deadline = time.monotonic() + _POLL_DEADLINE_S
    snapshot = vm.poll()
    while not snapshot.ready and time.monotonic() < deadline:
        time.sleep(_POLL_INTERVAL_S)
        snapshot = vm.poll()
    return snapshot


def _build_subscriber(config, endpoint, context):
    """Builds a real EventHandler + ZMQEventHandlerSource + ViewModel
    subscribed to the status endpoint, mirroring app.py's startup-phase
    wiring exactly."""
    event_handler = EventHandler(config)
    vm = StartupReadinessViewModel(config, event_handler)
    source = ZMQEventHandlerSource(
        endpoint=endpoint,
        event_handler=event_handler,
        config=config,
        subscriptions=[EPS_STARTUP_STATUS_EVENT],
        context=context,
    )
    source.start()
    return vm, event_handler, source


def test_live_status_broadcast_roundtrip(tmp_path):
    """Real publisher, real subscriber, real ZMQ PUB/SUB round trip."""
    scratch_yaml = tmp_path / "startup_readiness_live_test.yaml"
    config = YAMLBackedConfigurationService(yaml_path=scratch_yaml)
    endpoint = f"ipc://{tmp_path}/status.ipc"
    config.set("eps:status_pub_endpoint", endpoint)

    ctx = zmq.Context()
    signals = EPSStartupSignals(config, source="eps", context=ctx)
    vm, event_handler, source = _build_subscriber(config, endpoint, ctx)

    try:
        # Give the SUB socket a moment to connect + subscribe before the
        # first publish — mirrors app.py starting the subscriber before
        # ServicesManager, the other half of the slow-joiner mitigation
        # being exercised for real here.
        time.sleep(0.1)
        signals.publish_status(db_connected=True, sockets_bound=True)

        snapshot = _wait_for_ready(vm)
        assert snapshot.ready
        assert snapshot.degraded is False
        assert snapshot.db_connected is True
        assert snapshot.sockets_bound is True
    finally:
        source.shutdown()
        event_handler.shutdown()
        signals.close()
        ctx.term()


def test_live_late_subscriber_still_converges(tmp_path):
    """Regression tripwire for the slow-joiner fix itself.

    The publisher starts broadcasting *before* any subscriber exists —
    the exact scenario the broadcast-burst mitigation exists to survive.
    If this test starts failing, the broadcast window or interval was
    likely narrowed without checking it still covers realistic ZMQ
    connect/subscribe latency.
    """
    scratch_yaml = tmp_path / "startup_readiness_live_test_late.yaml"
    config = YAMLBackedConfigurationService(yaml_path=scratch_yaml)
    endpoint = f"ipc://{tmp_path}/status_late.ipc"
    config.set("eps:status_pub_endpoint", endpoint)

    broadcast_interval_s = 0.05
    broadcast_window_s = 1.0

    ctx = zmq.Context()
    signals = EPSStartupSignals(config, source="eps", context=ctx)

    stop_broadcasting = threading.Event()

    def _broadcast_loop():
        deadline = time.monotonic() + broadcast_window_s
        while not stop_broadcasting.is_set() and time.monotonic() < deadline:
            signals.publish_status(db_connected=True, sockets_bound=True)
            stop_broadcasting.wait(timeout=broadcast_interval_s)

    broadcaster = threading.Thread(target=_broadcast_loop, daemon=True)
    broadcaster.start()

    try:
        # Deliberately reversed ordering: let the publisher run for a bit
        # broadcasting into the void before any subscriber connects.
        time.sleep(broadcast_interval_s * 3)

        vm, event_handler, source = _build_subscriber(config, endpoint, ctx)
        try:
            snapshot = _wait_for_ready(vm)
            assert snapshot.ready
            assert snapshot.db_connected is True
            assert snapshot.sockets_bound is True
        finally:
            source.shutdown()
            event_handler.shutdown()
    finally:
        stop_broadcasting.set()
        broadcaster.join(timeout=2.0)
        signals.close()
        ctx.term()


def _kill_event_persistence(config, context):
    command_socket = context.socket(zmq.REQ)
    command_socket.setsockopt(zmq.RCVTIMEO, 2000)
    command_socket.setsockopt(zmq.LINGER, 0)
    command_socket.connect(config.get("eps:command_ipc"))
    command_socket.send_json({"Command": "Kill"})
    try:
        command_socket.recv_json()
    except Exception:
        pass
    command_socket.close()


def test_live_db_retry_gives_up_and_serves_anyway(tmp_path):
    """Real EventPersistence, pointed at credentials nothing will accept.

    Fails fast and predictably without requiring a real MySQL server to
    be absent: a reachable local MySQL rejects the bogus
    user/password/database quickly (access denied); an unreachable one
    refuses the connection quickly. Either way `mysql.connector.Error`
    fires well within the small configured retry budget, proving the
    "keep the lights on" contract — bounded retries, then serve anyway —
    against real retry/backoff timing instead of a mocked `time.sleep`.
    """
    scratch_yaml = tmp_path / "eps_live_retry_test.yaml"
    config = YAMLBackedConfigurationService(yaml_path=scratch_yaml)
    config.set("global:db:hostname", "127.0.0.1")
    config.set("global:db:username", "definitely_not_a_real_user_xyz")
    config.set("global:db:password", "wrong")
    config.set("global:db:database", "definitely_not_a_real_db_xyz")
    config.set("eps:db_connect_retry_max_attempts", 2)
    config.set("eps:db_connect_retry_backoff_ms", 20)
    status_endpoint = f"ipc://{tmp_path}/status.ipc"
    config.set("eps:status_pub_endpoint", status_endpoint)
    config.set("eps:fits_ipc", f"ipc://{tmp_path}/fits.ipc")
    config.set("eps:cluster_ipc", f"ipc://{tmp_path}/cluster.ipc")
    config.set("eps:command_ipc", f"ipc://{tmp_path}/command.ipc")

    ctx = zmq.Context()
    signals = EPSStartupSignals(config, source="eps", context=ctx)
    vm, event_handler, source = _build_subscriber(config, status_endpoint, ctx)
    time.sleep(0.1)

    # EventPersistence always constructs its own YAMLBackedConfigurationService
    # internally (no config injection) — redirect that construction to our
    # scratch-file instance so this test never touches the developer's real
    # on-disk config. Everything else (mysql.connector, ZMQ binds, the retry
    # loop, EPSStartupSignals) runs for real, unmocked.
    with patch(
        "le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService",
        return_value=config,
    ):
        ep_thread = threading.Thread(
            target=EventPersistence,
            kwargs={"startup_signals": signals},
            daemon=True,
        )
        ep_thread.start()

        try:
            snapshot = _wait_for_ready(vm)
            assert snapshot.ready
            assert snapshot.sockets_bound is True
            assert snapshot.db_connected is False
        finally:
            _kill_event_persistence(config, ctx)
            ep_thread.join(timeout=2.0)

    source.shutdown()
    event_handler.shutdown()
    signals.close()
    ctx.term()
