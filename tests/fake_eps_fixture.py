"""Shared fixture for real-socket ZMQBasedEventRepository tests (issue #196).

Starts a real ``zmq.REP`` socket in a daemon thread and replies with canned,
protocol-shaped JSON mirroring ``EventPersistenceService.cluster_event``'s
dispatch (see ``src/le_beta_vis/backend/EventPersistenceService.py``), so
tests exercise the real ZMQ round trip and real JSON serialization -- unlike
``tests/test_ZMQBasedEventRepository.py``, which mocks the socket entirely --
without needing a real ``EventPersistence`` process or MySQL. Follows the
``tmp_path``-scoped ``ipc://`` + daemon-thread launch/teardown pattern from
``tests/live_eps_fixture.py`` (issue #205); lighter-weight since there is no
real ``EventPersistence`` to start or config-injection patch to apply.

Plain importable module rather than a ``conftest.py`` -- this repo has no
``conftest.py`` anywhere; shared test doubles are imported explicitly per
file (see ``tests/mock_configuration_service.py``, ``tests/MockThumbnailLoaderService.py``).
"""

import dataclasses
import queue
import threading
from typing import Any, Dict, Iterator, List

import pytest
import zmq

from mock_configuration_service import MockConfigurationService

from le_beta_vis.common.ZMQBasedEventRepository import ZMQBasedEventRepository

_POLL_TIMEOUT_MS = 100


class _FakeEPSState:
    """In-memory stand-in for the EPS ``clusters`` table."""

    def __init__(self) -> None:
        self.next_cluster_id = 1
        self.classifications: Dict[int, str] = {}

    def store(self) -> int:
        cluster_id = self.next_cluster_id
        self.next_cluster_id += 1
        return cluster_id


def _handle_request(request: Dict[str, Any], state: _FakeEPSState) -> Dict[str, Any]:
    """Builds a canned reply shaped like ``EventPersistenceService.cluster_event``'s dispatch."""
    action = request.get("Action")
    if action == "Storage":
        return {"result": "success", "cluster_id": state.store()}
    if action == "UpdateClassification":
        state.classifications[request.get("cluster_id")] = request.get("classification")
        return {"result": "success"}
    if action in ("Retrieval", "PagedRetrieval", "RecentRetrieval"):
        response: Dict[str, Any] = {"result": "success", "clusters": []}
        if action == "PagedRetrieval":
            response["limit"] = request.get("limit", 0)
            response["offset"] = request.get("offset", 0)
        return response
    return {"result": "failure", "error": f"Unknown Action: {action!r}"}


def _fake_eps_loop(
    socket: zmq.Socket,
    state: _FakeEPSState,
    requests: List[Dict[str, Any]],
    responses: "queue.Queue[Dict[str, Any]]",
    stop_event: threading.Event,
) -> None:
    """REP loop: records each request, replies with a queued override if one is waiting, otherwise a canned reply."""
    poller = zmq.Poller()
    poller.register(socket, zmq.POLLIN)
    while not stop_event.is_set():
        ready = dict(poller.poll(timeout=_POLL_TIMEOUT_MS))
        if socket not in ready:
            continue
        request = socket.recv_json()
        requests.append(request)
        try:
            reply = responses.get_nowait()
        except queue.Empty:
            reply = _handle_request(request, state)
        socket.send_json(reply)


@dataclasses.dataclass
class FakeEPS:
    """Handle to an in-process fake EPS and the real repository pointed at it.

    ``requests`` captures every request the fake server received, in order, for wire-format assertions. ``responses`` lets a
    test force the *next* reply (e.g. a failure response) instead of the default canned one.
    """

    config: MockConfigurationService
    repository: ZMQBasedEventRepository
    requests: List[Dict[str, Any]]
    responses: "queue.Queue[Dict[str, Any]]"


@pytest.fixture
def fake_eps(tmp_path) -> Iterator[FakeEPS]:
    """Binds a real ``zmq.REP`` socket backed by an in-memory fake EPS, yields a ``FakeEPS`` handle, and tears both down."""
    config = MockConfigurationService()
    endpoint = f"ipc://{tmp_path}/cluster.ipc"
    config.set("eps:cluster_ipc", endpoint)

    ctx = zmq.Context()
    socket = ctx.socket(zmq.REP)
    socket.bind(endpoint)

    state = _FakeEPSState()
    requests: List[Dict[str, Any]] = []
    responses: "queue.Queue[Dict[str, Any]]" = queue.Queue()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_fake_eps_loop,
        args=(socket, state, requests, responses, stop_event),
        daemon=True,
    )
    thread.start()

    repository = ZMQBasedEventRepository(config=config, context=ctx)
    try:
        yield FakeEPS(config=config, repository=repository, requests=requests, responses=responses)
    finally:
        stop_event.set()
        thread.join(timeout=2.0)
        socket.close()
        ctx.term()
