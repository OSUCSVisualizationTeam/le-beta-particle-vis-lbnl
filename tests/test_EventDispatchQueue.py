"""Unit tests for EventDispatchQueue — per-event-type queue + worker thread.

These tests are deliberately timing-sensitive in a few places (coalesce
windows, throttle).  They use generous waits against ``threading.Event``
instead of ``sleep`` + polling wherever possible.
"""

import threading
import time
from typing import List

import pytest

from le_beta_vis.common.EventDispatchQueue import (
    EventDispatchQueue,
    OverflowPolicy,
)
from le_beta_vis.common.EventEnvelope import EventEnvelope


def _envelope(name: str = "test.event", **payload) -> EventEnvelope:
    return EventEnvelope(name=name, payload=payload or {"x": 1})


def _wait_for(condition, timeout_s: float = 2.0) -> bool:
    """Polls ``condition()`` until it returns True or timeout elapses."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.005)
    return False


class _SnapshotStub:
    """Mimics the (snapshot_single, snapshot_batch) callbacks the
    EventHandler passes.  Uses a lock so tests can mutate the lists
    safely while the dispatcher reads them."""

    def __init__(self):
        self.singles: List = []
        self.batches: List = []
        self._lock = threading.Lock()

    def get_single(self, _event_name: str):
        with self._lock:
            return list(self.singles)

    def get_batch(self, _event_name: str):
        with self._lock:
            return list(self.batches)


@pytest.fixture
def stub():
    return _SnapshotStub()


@pytest.fixture
def make_queue(stub):
    created: List[EventDispatchQueue] = []

    def _factory(**kwargs):
        defaults = dict(
            event_name="test.event",
            snapshot_single=stub.get_single,
            snapshot_batch=stub.get_batch,
            max_size=5,
            overflow_policy=OverflowPolicy.DROP_OLDEST,
            coalesce_ms=0,
            throttle_ms=0,
        )
        defaults.update(kwargs)
        q = EventDispatchQueue(**defaults)
        created.append(q)
        return q

    yield _factory

    for q in created:
        q.shutdown(timeout_ms=500)


class TestBasicDelivery:

    def test_single_callback_receives_envelope(self, stub, make_queue):
        received: List[EventEnvelope] = []
        evt = threading.Event()

        def cb(env):
            received.append(env)
            evt.set()

        stub.singles.append(cb)
        q = make_queue()
        q.enqueue(_envelope())

        assert evt.wait(timeout=1.0)
        assert len(received) == 1
        assert received[0].name == "test.event"

    def test_multiple_callbacks_fire_in_order(self, stub, make_queue):
        order = []
        done = threading.Event()

        def make_cb(i):
            def cb(env):
                order.append(i)
                if len(order) == 3:
                    done.set()
            return cb

        stub.singles.extend([make_cb(0), make_cb(1), make_cb(2)])
        q = make_queue()
        q.enqueue(_envelope())

        assert done.wait(timeout=1.0)
        assert order == [0, 1, 2]

    def test_preserves_per_envelope_order(self, stub, make_queue):
        received: List[int] = []
        done = threading.Event()

        def cb(env):
            received.append(env.payload["i"])
            if len(received) == 5:
                done.set()

        stub.singles.append(cb)
        q = make_queue(max_size=10)
        for i in range(5):
            q.enqueue(_envelope(i=i))

        assert done.wait(timeout=1.0)
        assert received == [0, 1, 2, 3, 4]


class TestExceptionIsolation:

    def test_raising_callback_does_not_stop_worker(self, stub, make_queue):
        received: List[int] = []
        done = threading.Event()

        def bad_cb(env):
            raise RuntimeError("boom")

        def good_cb(env):
            received.append(env.payload["i"])
            if len(received) == 2:
                done.set()

        stub.singles.extend([bad_cb, good_cb])
        q = make_queue()
        q.enqueue(_envelope(i=0))
        q.enqueue(_envelope(i=1))

        assert done.wait(timeout=1.0)
        assert received == [0, 1]


class TestOverflowPolicies:

    def test_drop_oldest_keeps_latest(self, stub, make_queue):
        gate = threading.Event()
        received: List[int] = []
        done = threading.Event()

        def cb(env):
            # Block on the first envelope so the queue fills up.
            gate.wait(timeout=2.0)
            received.append(env.payload["i"])
            if len(received) >= 3:
                done.set()

        stub.singles.append(cb)
        q = make_queue(max_size=2, overflow_policy=OverflowPolicy.DROP_OLDEST)

        # Fill beyond capacity while the worker is blocked on i=0.
        for i in range(6):
            q.enqueue(_envelope(i=i))
            time.sleep(0.005)  # give the worker a chance to pull i=0

        gate.set()
        assert done.wait(timeout=2.0)
        # The worker processed i=0 first (it was already dequeued when we
        # started flooding), then the two most recent items remaining in
        # the queue.  With drop_oldest we expect the last two we enqueued.
        assert received[0] == 0
        assert received[-1] == 5
        assert q.dropped_total > 0

    def test_drop_newest_drops_new_arrivals_when_full(
        self, stub, make_queue
    ):
        gate = threading.Event()
        received: List[int] = []
        done = threading.Event()

        def cb(env):
            gate.wait(timeout=2.0)
            received.append(env.payload["i"])
            if len(received) >= 3:
                done.set()

        stub.singles.append(cb)
        q = make_queue(max_size=2, overflow_policy=OverflowPolicy.DROP_NEWEST)

        for i in range(6):
            q.enqueue(_envelope(i=i))
            time.sleep(0.005)

        gate.set()
        assert done.wait(timeout=2.0)
        # DROP_NEWEST: we keep the first ones that made it in.
        assert received[0] == 0
        assert q.dropped_total > 0


class TestThrottle:

    def test_throttle_drops_envelopes_within_window(self, stub, make_queue):
        received: List[int] = []

        def cb(env):
            received.append(env.payload["i"])

        stub.singles.append(cb)
        q = make_queue(max_size=20, throttle_ms=100)

        # Fire 10 envelopes in rapid succession; only a subset should be
        # delivered because subsequent envelopes arrive inside the throttle
        # window.
        for i in range(10):
            q.enqueue(_envelope(i=i))

        assert _wait_for(lambda: len(received) >= 1, timeout_s=1.0)
        time.sleep(0.2)  # let the worker drain
        assert len(received) < 10


class TestCoalesce:

    def test_batch_callback_receives_list(self, stub, make_queue):
        batches: List[List[EventEnvelope]] = []
        done = threading.Event()

        def batch_cb(batch):
            batches.append(batch)
            done.set()

        stub.batches.append(batch_cb)
        q = make_queue(max_size=20, coalesce_ms=100)

        for i in range(5):
            q.enqueue(_envelope(i=i))
            time.sleep(0.005)

        assert done.wait(timeout=1.0)
        assert len(batches) == 1
        assert len(batches[0]) >= 2  # at least some coalesced
        assert [e.payload["i"] for e in batches[0]][0] == 0


class TestShutdown:

    def test_shutdown_joins_worker_thread(self, stub):
        q = EventDispatchQueue(
            event_name="shutdown.test",
            snapshot_single=stub.get_single,
            snapshot_batch=stub.get_batch,
            max_size=5,
        )
        q.shutdown(timeout_ms=500)
        # Thread should no longer be alive after shutdown.
        assert not q._thread.is_alive()

    def test_post_shutdown_enqueue_is_noop(self, stub):
        received: List[EventEnvelope] = []
        stub.singles.append(lambda env: received.append(env))
        q = EventDispatchQueue(
            event_name="shutdown.test",
            snapshot_single=stub.get_single,
            snapshot_batch=stub.get_batch,
        )
        q.shutdown(timeout_ms=500)
        q.enqueue(_envelope())
        time.sleep(0.05)
        assert received == []
