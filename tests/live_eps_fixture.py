"""Shared fixture for real ViewModel -> EPS -> MySQL round-trip tests (issue #205).

Runs a real ``EventPersistence`` instance in-thread against a real MySQL
database and hands back a real ``ZMQBasedEventRepository`` pointed at it --
no ZMQ or database mocking anywhere in this module. Follows the exact
in-thread launch pattern already proven in
``tests/test_live_startup_readiness.py::test_live_db_retry_gives_up_and_serves_anyway``:
``EventPersistence`` always constructs its own ``YAMLBackedConfigurationService``
internally (there is no config-injection point), so that construction site is
patched to return a scratch, tmp_path-scoped config instead -- the only patch
anywhere in this module. Everything else (ZMQ binds, the MySQL connection, the
startup-readiness broadcast/poll handshake) runs for real.

Plain importable module rather than a ``conftest.py`` -- this repo has no
``conftest.py`` anywhere; shared test doubles are imported explicitly per
file (see ``tests/mock_configuration_service.py``, ``tests/MockThumbnailLoaderService.py``).
"""

import dataclasses
import threading
import time
import uuid
from typing import Iterator
from unittest.mock import patch

import mysql.connector
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
from le_beta_vis.common.ZMQBasedEventRepository import ZMQBasedEventRepository
from le_beta_vis.common.ZMQEventHandlerSource import ZMQEventHandlerSource
from le_beta_vis.frontend.viewmodels.StartupReadinessViewModel import (
    StartupReadinessViewModel,
)

# Matches global:db:* defaults in defaults.yaml, which also match the
# CI job's DB_USER=root/DB_PASS=root/DB_NAME=lbnlfits env vars -- same
# constants tests/test_BulkClusterInsert_integration.py already uses.
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "root"
DB_NAME = "lbnlfits"

_POLL_DEADLINE_S = 5.0
_POLL_INTERVAL_S = 0.05


def raw_connection() -> mysql.connector.MySQLConnection:
    """Fresh direct MySQL connection for seed/cleanup SQL outside of EPS."""
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )


def unique_marker(scenario: str) -> str:
    """Per-run identifying tag embedded in seeded rows (e.g. in fileName).

    Not used to drive cleanup deletes -- those target the exact row ids captured at seed time -- but makes any row left behind
    by a crashed test run trivially identifiable by hand.
    """
    return f"epsrt_{scenario}_{uuid.uuid4().hex[:8]}"


@dataclasses.dataclass
class LiveEPS:
    """Handle to a live, in-thread EPS instance and its real repository."""

    config: YAMLBackedConfigurationService
    repository: ZMQBasedEventRepository
    context: zmq.Context


def _wait_for_ready(vm: StartupReadinessViewModel):
    deadline = time.monotonic() + _POLL_DEADLINE_S
    snapshot = vm.poll()
    while not snapshot.ready and time.monotonic() < deadline:
        time.sleep(_POLL_INTERVAL_S)
        snapshot = vm.poll()
    return snapshot


def _build_subscriber(config, endpoint, context):
    """Real EventHandler + ZMQEventHandlerSource + ViewModel subscribed to the EPS startup-status endpoint, mirroring app.py's
    startup-phase wiring."""
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


def _kill_event_persistence(config, context) -> None:
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


@pytest.fixture
def live_eps(tmp_path) -> Iterator[LiveEPS]:
    """Starts a real EventPersistence in-thread against a real MySQL, yields a LiveEPS(config, repository, context) handle, and
    tears both down."""
    scratch_yaml = tmp_path / "eps_regression_config.yaml"
    config = YAMLBackedConfigurationService(yaml_path=scratch_yaml)
    config.set("global:db:hostname", DB_HOST)
    config.set("global:db:username", DB_USER)
    config.set("global:db:password", DB_PASSWORD)
    config.set("global:db:database", DB_NAME)

    status_endpoint = f"ipc://{tmp_path}/status.ipc"
    config.set("eps:status_pub_endpoint", status_endpoint)
    config.set("eps:fits_ipc", f"ipc://{tmp_path}/fits.ipc")
    config.set("eps:cluster_ipc", f"ipc://{tmp_path}/cluster.ipc")
    config.set("eps:command_ipc", f"ipc://{tmp_path}/command.ipc")

    ctx = zmq.Context()
    signals = EPSStartupSignals(config, source="eps", context=ctx)
    vm, event_handler, source = _build_subscriber(config, status_endpoint, ctx)
    # Slow-joiner mitigation: give the SUB socket a moment to connect before
    # EPS starts broadcasting readiness, mirroring app.py's startup ordering.
    time.sleep(0.1)

    # EventPersistence always constructs its own YAMLBackedConfigurationService
    # internally (no config injection) -- redirect that construction to our
    # scratch instance so this fixture never touches a developer's on-disk
    # config. Everything else (mysql.connector, ZMQ binds, the readiness
    # broadcast/poll loop) runs for real, unmocked.
    patcher = patch(
        "le_beta_vis.backend.EventPersistenceService.YAMLBackedConfigurationService",
        return_value=config,
    )
    patcher.start()
    ep_thread = threading.Thread(
        target=EventPersistence,
        kwargs={"startup_signals": signals},
        daemon=True,
    )
    ep_thread.start()

    try:
        snapshot = _wait_for_ready(vm)
        if not (snapshot.ready and snapshot.db_connected):
            pytest.fail(
                "live_eps fixture: EPS did not reach a ready, DB-connected "
                f"state within {_POLL_DEADLINE_S}s (ready={snapshot.ready}, "
                f"db_connected={snapshot.db_connected}). Is a MySQL server "
                f"with the {DB_NAME!r} schema reachable at {DB_HOST!r}?"
            )
        repository = ZMQBasedEventRepository(config=config, context=ctx)
        yield LiveEPS(config=config, repository=repository, context=ctx)
    finally:
        _kill_event_persistence(config, ctx)
        ep_thread.join(timeout=2.0)
        patcher.stop()
        source.shutdown()
        event_handler.shutdown()
        signals.close()
        ctx.term()
