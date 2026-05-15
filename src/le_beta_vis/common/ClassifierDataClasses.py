"""Request/response DTOs for the ClassifierService ZMQ protocol.

Each class maps to a specific JSON message exchanged over the Classifier IPC
sockets.  All classes are frozen dataclasses with conversion helpers
(``to_classifier_dict`` for requests, ``from_classifier_dict`` for responses).
"""

from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass(frozen=True)
class ClassificationRequest:
    """Payload for an classification request"""
    model: str
    # the clusters list should be of ClassificationRequestCluster objects with their own methods
    clusters: List["ClassificationRequestCluster"]

    def to_classifier_dict(self) -> Dict[str, Any]:
        """Builds the JSON dict expected by the classifier socket"""
        clusters: List[Dict[str, Any]] = []
        for cluster in self.clusters:
            if isinstance(cluster, ClassificationRequestCluster):
                clusters.append(cluster.to_cluster_dict())
            elif isinstance(cluster, dict):
                clusters.append(cluster)
        return {
            "Model": self.model,
            "Clusters": clusters,
        }

    @staticmethod
    def from_classifier_dict(d: Dict[str, Any]) -> "ClassificationRequest":
        """Parses one classification request."""
        raw_clusters = d.get("Clusters") or []
        clusters: List[ClassificationRequestCluster] = []
        for cluster in raw_clusters:
            if isinstance(cluster, ClassificationRequestCluster):
                clusters.append(cluster)
            elif isinstance(cluster, dict):
                clusters.append(
                    ClassificationRequestCluster.from_cluster_dict(cluster)
                )
        return ClassificationRequest(
            model=d.get("Model", ""),
            clusters=clusters,
        )
    
@dataclass(frozen=True)
class ClassificationRequestCluster:
    """Cluster payload for classification requests"""
    data: List[List[float]]
    cluster_id: int
    sigmaX: float
    sigmaY: float
    total_energy: float
    total_pixels: int

    def to_cluster_dict(self) -> Dict[str, Any]:
        """Builds the JSON dict expected of a single cluster"""
        return {
            "data": self.data,
            "cluster_id": self.cluster_id,
            "sigmaX": self.sigmaX,
            "sigmaY": self.sigmaY,
            "total_energy": self.total_energy,
            "total_pixels": self.total_pixels
        }
    
    @staticmethod
    def from_cluster_dict(d: Dict[str, Any]) -> "ClassificationRequestCluster":
        """Parses on classification request cluster"""
        return ClassificationRequestCluster(
            data=d.get("data", []),
            cluster_id=d.get("cluster_id", 0),
            sigmaX=d.get("sigmaX", 0.0),
            sigmaY=d.get("sigmaY", 0.0),
            total_energy=d.get("total_energy", 0.0),
            total_pixels=d.get("total_pixels", 0)
        )