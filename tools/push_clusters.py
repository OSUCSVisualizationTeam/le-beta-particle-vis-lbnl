"""Publishes synthetic cluster.classified events over ZMQ.

Usage::

    uv run python tools/push_clusters.py [--count N] [--interval SECONDS] [--endpoint IPC]

The script BINDS a ZMQ PUB socket so it must start before (or
concurrently with) the application's ZMQEventHandlerSource, which
CONNECTS as a SUB subscriber.  The default endpoint matches the
application configuration default.

Examples::

    # 100 events at 1s interval (default)
    uv run python tools/push_clusters.py

    # 50 events at 0.5s interval
    uv run python tools/push_clusters.py --count 50 --interval 0.5

    # Custom endpoint
    uv run python tools/push_clusters.py --endpoint ipc:///tmp/CustomEvents.ipc
"""

import argparse
import random
import time

from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.ZMQEventHandlerClient import ZMQEventHandlerClient

_DEFAULT_ENDPOINT = "ipc:///tmp/EPCEvents.ipc"
_DEFAULT_COUNT = 100
_DEFAULT_INTERVAL = 1.0
_EVENT_NAME = "cluster.classified"
_SOURCE = "tools.push_clusters"

# Eight synthetic cluster templates with varying properties.
_CLUSTER_SPECS = [
    {
        "sigmaX": 1.2,
        "sigmaY": 1.3,
        "total_energy": 800.0,
        "classification": "TRITIUM",
        "cnn_classification": 0.92,
        "nrg_classification": 0.88,
        "bdt_classification": 0.90,
    },
    {
        "sigmaX": 2.5,
        "sigmaY": 2.8,
        "total_energy": 4500.0,
        "classification": "MUON",
        "cnn_classification": 0.15,
        "nrg_classification": 0.10,
        "bdt_classification": 0.12,
    },
    {
        "sigmaX": 1.0,
        "sigmaY": 1.1,
        "total_energy": 600.0,
        "classification": "TRITIUM",
        "cnn_classification": 0.85,
        "nrg_classification": 0.91,
        "bdt_classification": 0.87,
    },
    {
        "sigmaX": 3.0,
        "sigmaY": 1.5,
        "total_energy": 2200.0,
        "classification": "COMPTON",
        "cnn_classification": 0.30,
        "nrg_classification": 0.25,
        "bdt_classification": 0.28,
    },
    {
        "sigmaX": 1.8,
        "sigmaY": 1.7,
        "total_energy": 1200.0,
        "classification": "TRITIUM",
        "cnn_classification": 0.78,
        "nrg_classification": 0.82,
        "bdt_classification": 0.80,
    },
    {
        "sigmaX": 4.0,
        "sigmaY": 3.5,
        "total_energy": 8000.0,
        "classification": "ALPHA",
        "cnn_classification": 0.05,
        "nrg_classification": 0.08,
        "bdt_classification": 0.06,
    },
    {
        "sigmaX": 1.5,
        "sigmaY": 1.4,
        "total_energy": 950.0,
        "classification": "TRITIUM",
        "cnn_classification": 0.97,
        "nrg_classification": 0.95,
        "bdt_classification": 0.96,
    },
    {
        "sigmaX": 2.0,
        "sigmaY": 2.2,
        "total_energy": 3000.0,
        "classification": "GAMMA",
        "cnn_classification": 0.40,
        "nrg_classification": 0.35,
        "bdt_classification": 0.38,
    },
]


def _build_payload(spec: dict, index: int) -> dict:
    """Creates a payload dict with slight energy variation."""
    energy_jitter = random.uniform(0.8, 1.2)
    return {
        "fits_id": index % 5 + 1,
        "cluster_id": index,
        "sigmaX": spec["sigmaX"],
        "sigmaY": spec["sigmaY"],
        "total_energy": spec["total_energy"] * energy_jitter,
        "classification": spec["classification"],
        "cnn_classification": spec["cnn_classification"],
        "nrg_classification": spec["nrg_classification"],
        "bdt_classification": spec["bdt_classification"],
    }


def main() -> None:
    """Parses arguments and publishes synthetic cluster events."""
    parser = argparse.ArgumentParser(
        description="Publish synthetic cluster.classified events over ZMQ.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=_DEFAULT_COUNT,
        help=f"Number of events to publish (default: {_DEFAULT_COUNT})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=_DEFAULT_INTERVAL,
        help=f"Seconds between events (default: {_DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=_DEFAULT_ENDPOINT,
        help=f"ZMQ PUB endpoint (default: {_DEFAULT_ENDPOINT})",
    )
    args = parser.parse_args()

    print(f"Binding PUB socket to {args.endpoint}")
    print(f"Publishing {args.count} events at {args.interval}s interval")
    print("Press Ctrl+C to stop early\n")

    client = ZMQEventHandlerClient(
        args.endpoint,
        bind_or_connect="bind",
    )

    try:
        for i in range(args.count):
            spec = _CLUSTER_SPECS[i % len(_CLUSTER_SPECS)]
            payload = _build_payload(spec, i)
            envelope = EventEnvelope(
                name=_EVENT_NAME,
                payload=payload,
                source=_SOURCE,
            )
            client.publish(envelope)
            print(
                f"[{i + 1}/{args.count}] "
                f"{payload['classification']:>10s}  "
                f"energy={payload['total_energy']:8.1f}  "
                f"CNN={payload['cnn_classification']:.2f}"
            )
            if i < args.count - 1:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        client.close()
        print("Done.")


if __name__ == "__main__":
    main()
