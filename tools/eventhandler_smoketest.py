"""End-to-end smoke test for the EventHandler pub/sub pipeline.

Runs standalone — no Qt, no backend.  Exercises the full path a real
backend will use:

    ZMQEventHandlerClient  (PUB, binds temp IPC endpoint)
            │  publish(envelope)
            ▼
    ZMQ IPC socket
            │
            ▼
    ZMQEventHandlerSource  (SUB, connects to endpoint)
            │  dispatch(envelope)
            ▼
    EventHandler  (registry + per-event-type worker queue)
            │
            ▼
    Registered callback  (prints the received envelope)

Publishing is done through the **public**
:class:`ZMQEventHandlerClient` API — the same code path the classifier
will eventually use — not by poking at ``zmq.Socket`` directly.

Run with:

    uv run python tools/eventhandler_smoketest.py

Expected output: 20 lines printed, roughly one every 500 ms, each
showing the deserialized envelope.  A summary line prints at the end
confirming how many envelopes the frontend callback received.
"""

import logging
import os
import tempfile
import threading
import time
from typing import Any, Dict

import zmq

from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.EventHandler import EventHandler
from le_beta_vis.common.ZMQEventHandlerClient import ZMQEventHandlerClient
from le_beta_vis.common.ZMQEventHandlerSource import ZMQEventHandlerSource


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("smoketest")


_NUM_EVENTS = 20
_PUBLISH_INTERVAL_S = 0.5
_EVENT_NAME = "cluster.classified"


class _InMemoryConfig:
    """Minimal ConfigurationService stub — just enough for the
    EventHandler and ZMQEventHandlerSource to read their defaults."""

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {
            "event_handler:default_queue_size": 100,
            "event_handler:default_overflow_policy": "drop_oldest",
            "event_handler:default_coalesce_ms": 0,
            "event_handler:default_throttle_ms": 0,
            "event_handler:worker_join_timeout_ms": 1000,
            "event_handler:reconnect_backoff_ms_min": 50,
            "event_handler:reconnect_backoff_ms_max": 500,
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def get_int(
        self, key: str, default: int, *, minimum=None, maximum=None
    ) -> int:
        value = int(self._store.get(key, default))
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value


def _fake_cluster_payload(i: int) -> Dict[str, Any]:
    return {
        "fits_id": 1000 + i,
        "cluster_id": i,
        "total_energy": 12.5 + i * 0.1,
        "sigmaX": 1.7,
        "sigmaY": 1.9,
        "classification": "Tritium",
        "cnn_classification": 0.92,
        "nrg_classification": 0.88,
        "bdt_classification": 0.81,
    }


def main() -> None:
    # Use a per-run IPC endpoint so concurrent smoketests don't collide
    # and so nothing is left over in /tmp if the run is interrupted.
    ipc_dir = tempfile.mkdtemp(prefix="eventhandler-smoketest-")
    endpoint = f"ipc://{os.path.join(ipc_dir, 'events.ipc')}"
    logger.info("Using IPC endpoint %s", endpoint)

    config = _InMemoryConfig()
    handler = EventHandler(config)

    received_count = 0
    received_gate = threading.Event()

    def on_cluster_classified(envelope: EventEnvelope) -> None:
        nonlocal received_count
        received_count += 1
        logger.info(
            "[recv %02d] name=%s id=%s source=%s payload=%s",
            received_count,
            envelope.name,
            envelope.id[:8],
            envelope.source,
            envelope.payload,
        )
        if received_count >= _NUM_EVENTS:
            received_gate.set()

    handler.register_callback(_EVENT_NAME, on_cluster_classified)

    # Use a dedicated ZMQ context so the publisher and subscriber
    # share memory-level visibility through ZMQ's inproc/IPC paths.
    ctx = zmq.Context.instance()

    source = ZMQEventHandlerSource(
        endpoint=endpoint,
        event_handler=handler,
        config=config,
        context=ctx,
    )

    with ZMQEventHandlerClient(
        endpoint,
        bind_or_connect="bind",
        context=ctx,
    ) as client:
        # Order matters: bind the PUB *first*, then start the SUB.
        # If the SUB is started first it connects to a non-existent
        # endpoint, then has to auto-reconnect once the PUB binds —
        # the first publish races that reconnect and is silently
        # dropped (ZMQ's "slow joiner" problem).
        source.start()
        # Small settle so the SUB's subscription message reaches the
        # freshly-bound PUB before the first publish.
        time.sleep(0.5)

        for i in range(_NUM_EVENTS):
            envelope = EventEnvelope(
                name=_EVENT_NAME,
                payload=_fake_cluster_payload(i),
                source="smoketest.publisher",
            )
            client.publish(envelope)
            logger.info("[sent %02d] id=%s", i + 1, envelope.id[:8])
            time.sleep(_PUBLISH_INTERVAL_S)

        # Let any in-flight envelopes drain.
        if not received_gate.wait(timeout=3.0):
            logger.warning(
                "Timed out waiting for all envelopes; "
                "received %d/%d",
                received_count,
                _NUM_EVENTS,
            )

        # Shut down the SUB source *before* leaving the with-block so
        # the recv thread doesn't see the PUB's IPC endpoint unlink as
        # a socket error.
        source.shutdown(timeout_ms=500)

    handler.shutdown(timeout_ms=1000)

    logger.info(
        "SUMMARY: published=%d received=%d",
        _NUM_EVENTS,
        received_count,
    )
    if received_count == 0:
        raise SystemExit(
            "Smoke test failed: no envelopes reached the callback"
        )


if __name__ == "__main__":
    main()
