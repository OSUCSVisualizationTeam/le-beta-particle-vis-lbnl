"""Reads real clusters from the EPS database and publishes them as events.

Connects to the Event Persistence Service (EPS) via ZMQ, fetches real
cluster records, and re-publishes them as ``cluster.classified`` events
on the EventHandler PUB/SUB bus.  Useful for testing the Live Mode
screensaver with production-like data without a running classifier.

Configuration is loaded from ``~/mlccd_viz.yaml`` by default (the same
file the application uses).  EPS IPC endpoints and timeouts are read
from that config.

Usage::

    # Default: 5000 clusters from ~/mlccd_viz.yaml, 0.5s interval
    uv run python tools/push_clusters_from_db.py

    # Custom count and interval
    uv run python tools/push_clusters_from_db.py --count 200 --interval 0.2

    # Explicit config file
    uv run python tools/push_clusters_from_db.py --config /path/to/mlccd_viz.yaml

    # Override EPS endpoints without touching the config file
    uv run python tools/push_clusters_from_db.py \\
        --cluster-ipc ipc:///tmp/EPCCluster.ipc \\
        --event-endpoint ipc:///tmp/EPCEvents.ipc
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)
from le_beta_vis.common.ZMQBasedEventRepository import ZMQBasedEventRepository
from le_beta_vis.common.ZMQEventHandlerClient import ZMQEventHandlerClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("push_clusters_from_db")

_DEFAULT_COUNT = 5000
_DEFAULT_INTERVAL = 0.5
_EVENT_NAME = "cluster.classified"
_SOURCE = "tools.push_clusters_from_db"


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Fetch real clusters from the EPS database and publish "
            "them as cluster.classified events over ZMQ."
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=_DEFAULT_COUNT,
        help=f"Max clusters to publish (default: {_DEFAULT_COUNT})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=_DEFAULT_INTERVAL,
        help=f"Seconds between events (default: {_DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to mlccd_viz.yaml (default: ~/mlccd_viz.yaml)",
    )
    parser.add_argument(
        "--cluster-ipc",
        type=str,
        default=None,
        help="Override eps:cluster_ipc (EPS cluster socket address)",
    )
    parser.add_argument(
        "--event-endpoint",
        type=str,
        default=None,
        help="Override event_handler:zmq_pub_endpoint (PUB socket)",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=None,
        help="Override eps:timeout_ms (ZMQ request timeout)",
    )
    parser.add_argument(
        "--no-data",
        action="store_true",
        default=False,
        help="Omit cluster data from payloads (test FITS fallback)",
    )
    return parser.parse_args()


def _load_config(
    config_path: Optional[str],
    cluster_ipc: Optional[str],
    event_endpoint: Optional[str],
    timeout_ms: Optional[int],
) -> YAMLBackedConfigurationService:
    """Load the YAML configuration, applying CLI overrides."""
    if config_path is not None:
        path = Path(config_path)
        if not path.exists():
            logger.error("Config file not found: %s", path)
            sys.exit(1)
        config = YAMLBackedConfigurationService(yaml_path=path)
    else:
        config = YAMLBackedConfigurationService()

    if cluster_ipc is not None:
        config.set("eps:cluster_ipc", cluster_ipc)
    if event_endpoint is not None:
        config.set("event_handler:zmq_pub_endpoint", event_endpoint)
    if timeout_ms is not None:
        config.set("eps:timeout_ms", timeout_ms)

    return config


def _fetch_clusters(
    config: YAMLBackedConfigurationService,
    max_count: int,
) -> List[Cluster]:
    """Fetch clusters from the EPS database."""
    repo = ZMQBasedEventRepository(config)
    logger.info(
        "Fetching clusters from EPS at %s ...",
        config.get("eps:cluster_ipc", "ipc:///tmp/EPCCluster.ipc"),
    )
    clusters = repo.fetch_events()
    if not clusters:
        logger.warning("No clusters returned from the EPS")
        return []
    logger.info("EPS returned %d clusters", len(clusters))
    return clusters[:max_count]


def _cluster_to_payload(cluster: Cluster, include_data: bool) -> Dict:
    """Convert a Cluster to the EventEnvelope payload format."""
    payload = {
        "fits_id": cluster.fitsId,
        "cluster_id": cluster.clusterId,
        "sigmaX": cluster.sigmaX,
        "sigmaY": cluster.sigmaY,
        "total_energy": cluster.energy,
        "classification": cluster.classification,
        "cnn_classification": cluster.cnnClassification,
        "nrg_classification": cluster.nrgClassification,
        "bdt_classification": cluster.bdtClassification,
    }
    if include_data and cluster.fitsFilename:
        payload["fits_filename"] = cluster.fitsFilename
    if cluster.hdu_id is not None:
        payload["hdu_id"] = cluster.hdu_id
    if cluster.boundingBox is not None:
        payload["bounding_box"] = {
            "top": cluster.boundingBox.top,
            "left": cluster.boundingBox.left,
            "bottom": cluster.boundingBox.bottom,
            "right": cluster.boundingBox.right,
        }
    return payload


def _publish_clusters(
    clusters: List[Cluster],
    endpoint: str,
    interval: float,
    include_data: bool,
) -> None:
    """Publish clusters as EventEnvelopes at the given interval."""
    total = len(clusters)
    print(f"Binding PUB socket to {endpoint}")
    print(f"Publishing {total} clusters at {interval}s interval")
    print(f"Data included: {include_data}")
    print("Press Ctrl+C to stop early\n")

    client = ZMQEventHandlerClient(endpoint, bind_or_connect="bind")
    try:
        for i, cluster in enumerate(clusters):
            payload = _cluster_to_payload(cluster, include_data)
            envelope = EventEnvelope(
                name=_EVENT_NAME,
                payload=payload,
                source=_SOURCE,
            )
            client.publish(envelope)
            cls = cluster.classification or "UNKNOWN"
            print(
                f"[{i + 1:5d}/{total}] "
                f"{cls:>14s}  "
                f"energy={cluster.energy:10.1f}  "
                f"fits_id={cluster.fitsId or 0}"
            )
            if i < total - 1:
                time.sleep(interval)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        client.close()


def main() -> None:
    """Entry point: load config, fetch clusters, publish events."""
    args = _parse_args()
    config = _load_config(
        args.config,
        args.cluster_ipc,
        args.event_endpoint,
        args.timeout_ms,
    )

    clusters = _fetch_clusters(config, args.count)
    if not clusters:
        print("No clusters to publish. Is the EPS running?")
        sys.exit(1)

    endpoint = str(
        config.get(
            "event_handler:zmq_pub_endpoint",
            "ipc:///tmp/EPCEvents.ipc",
        )
    )
    _publish_clusters(
        clusters,
        endpoint,
        args.interval,
        include_data=not args.no_data,
    )
    print(f"\nDone. Published {len(clusters)} clusters.")


if __name__ == "__main__":
    main()
