"""
Knowledge Graph Engine - Hermes Phase 8

Node and Edge definitions for the knowledge graph.
Supports persistence, versioning, and querying.
"""

import json
import os
import tempfile
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class NodeType(str, Enum):
    PROJECT = "Project"
    MODULE = "Module"
    PACKAGE = "Package"
    DIRECTORY = "Directory"
    FILE = "File"
    SKILL = "Skill"
    TOOL = "Tool"
    DATABASE = "Database"
    GATEWAY = "Gateway"
    PROVIDER = "Provider"
    RUNTIME = "Runtime"
    MEMORY = "Memory"
    TASK = "Task"
    DECISION = "Decision"
    EXPERIENCE = "Experience"
    API = "API"
    CONFIG = "Config"
    USER_PROJECT = "UserProject"


class RelationshipType(str, Enum):
    DEPENDS_ON = "depends_on"
    IMPORTS = "imports"
    USES = "uses"
    READS = "reads"
    WRITES = "writes"
    CREATES = "creates"
    EXECUTES = "executes"
    BELONGS_TO = "belongs_to"
    OWNS = "owns"
    RELATED_TO = "related_to"
    GENERATED_BY = "generated_by"
    ARCHIVED_FROM = "archived_from"
    REPLACES = "replaces"
    REFERENCES = "references"


@dataclass
class Node:
    """A node in the knowledge graph"""
    id: str
    type: NodeType
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    version: int = 1
    source: str = "unknown"

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def update_property(self, key: str, value: Any) -> None:
        self.properties[key] = value
        self.updated_at = datetime.now().isoformat()
        self.version += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "properties": self.properties,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "source": self.source
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        return cls(
            id=data["id"],
            type=NodeType(data["type"]),
            label=data["label"],
            properties=data.get("properties", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            version=data.get("version", 1),
            source=data.get("source", "unknown")
        )


@dataclass
class Edge:
    """A directed edge between two nodes"""
    id: str
    source: str
    target: str
    type: RelationshipType
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    version: int = 1

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "type": self.type.value,
            "properties": self.properties,
            "created_at": self.created_at,
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Edge":
        return cls(
            id=data["id"],
            source=data["source"],
            target=data["target"],
            type=RelationshipType(data["type"]),
            properties=data.get("properties", {}),
            created_at=data.get("created_at", ""),
            version=data.get("version", 1)
        )


class KnowledgeGraph:
    """
    Central Knowledge Graph for Hermes.

    Stores all entities (nodes) and their relationships (edges).
    Supports versioning and persistence.

    Persistence strategy (Phase 10.8.1):
      - Mutations are in-memory only by default (no auto-save per operation).
      - Call ``save()`` explicitly, or use ``add_nodes_bulk()`` /
        ``add_edges_bulk()`` which auto-save after the batch completes.
      - ``_auto_save`` can be toggled on for single-op callers that want the
        old per-mutation write behaviour.
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.expanduser("~/.hermes/governance/knowledge_graph.json")
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}
        self._dirty = False
        self._ensure_storage_dir()
        self._load()

    def _ensure_storage_dir(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    def mark_dirty(self) -> None:
        """Mark graph as needing persistence."""
        self._dirty = True

    def is_dirty(self) -> bool:
        """Check if graph has unsaved changes."""
        return self._dirty

    # --- Node Operations ---

    def add_node(self, node: Node) -> Node:
        """Add or update a node (in-memory only; call save() to persist)"""
        self.nodes[node.id] = node
        self._dirty = True
        return node

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID"""
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> List[Node]:
        """Get all nodes of a specific type"""
        return [n for n in self.nodes.values() if n.type == node_type]

    def get_nodes_by_type_value(self, type_value: str) -> List[Node]:
        """Get all nodes matching a type string value"""
        return [n for n in self.nodes.values() if n.type.value == type_value]

    def get_nodes_by_label(self, label: str) -> List[Node]:
        """Search nodes by label (partial match)"""
        label_lower = label.lower()
        return [n for n in self.nodes.values() if label_lower in n.label.lower()]

    def get_nodes_by_property(self, key: str, value: Any) -> List[Node]:
        """Find nodes where property key matches value"""
        results = []
        for n in self.nodes.values():
            prop_val = n.properties.get(key)
            if isinstance(prop_val, list):
                if value in prop_val:
                    results.append(n)
            elif prop_val == value:
                results.append(n)
        return results

    def add_nodes_bulk(self, nodes: List[Node]) -> List[Node]:
        """Add many nodes in one batch, then persist once. Returns the nodes added."""
        for node in nodes:
            self.nodes[node.id] = node
        self._dirty = True
        if nodes:
            self.save()
        return nodes

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all its edges"""
        if node_id not in self.nodes:
            return False

        edges_to_remove = [
            e_id for e_id, e in self.edges.items()
            if e.source == node_id or e.target == node_id
        ]
        for e_id in edges_to_remove:
            del self.edges[e_id]

        del self.nodes[node_id]
        self._dirty = True
        self.save()
        return True

    def update_node(self, node_id: str, **kwargs) -> bool:
        """Update node properties"""
        if node_id not in self.nodes:
            return False

        node = self.nodes[node_id]
        for key, value in kwargs.items():
            if hasattr(node, key):
                setattr(node, key, value)
            elif key == "properties":
                node.properties.update(value)

        node.updated_at = datetime.now().isoformat()
        node.version += 1
        self._dirty = True
        self.save()
        return True

    # --- Edge Operations ---

    def add_edge(self, edge: Edge) -> Edge:
        """Add an edge between two nodes"""
        if edge.source not in self.nodes:
            raise ValueError(f"Source node {edge.source} does not exist")
        if edge.target not in self.nodes:
            raise ValueError(f"Target node {edge.target} does not exist")

        self.edges[edge.id] = edge
        self._dirty = True
        return edge

    def add_edges_bulk(self, edges: List[Edge]) -> List[Edge]:
        """Add many edges in one batch, then persist once. Returns edges added."""
        for edge in edges:
            if edge.source not in self.nodes:
                raise ValueError(f"Source node {edge.source} does not exist")
            if edge.target not in self.nodes:
                raise ValueError(f"Target node {edge.target} does not exist")
            self.edges[edge.id] = edge
        self._dirty = True
        if edges:
            self.save()
        return edges

    def get_edge(self, edge_id: str) -> Optional[Edge]:
        """Get an edge by ID"""
        return self.edges.get(edge_id)

    def get_edges_by_source(self, node_id: str) -> List[Edge]:
        """Get all outgoing edges from a node"""
        return [e for e in self.edges.values() if e.source == node_id]

    def get_edges_by_target(self, node_id: str) -> List[Edge]:
        """Get all incoming edges to a node"""
        return [e for e in self.edges.values() if e.target == node_id]

    def get_edges_by_type(self, rel_type: RelationshipType) -> List[Edge]:
        """Get all edges of a specific relationship type"""
        return [e for e in self.edges.values() if e.type == rel_type]

    def get_edges_by_type_value(self, type_value: str) -> List[Edge]:
        """Get edges matching a relationship type string"""
        return [e for e in self.edges.values() if e.type.value == type_value]

    def get_related_nodes(self, node_id: str, rel_type: RelationshipType = None) -> List[Node]:
        """Get all nodes connected to a given node"""
        related = set()
        for edge in self.edges.values():
            if edge.source == node_id:
                related.add(edge.target)
                if rel_type and edge.type != rel_type:
                    related.discard(edge.target)
            elif edge.target == node_id:
                related.add(edge.source)
                if rel_type and edge.type != rel_type:
                    related.discard(edge.source)

        return [self.nodes[nid] for nid in related if nid in self.nodes]

    def remove_edge(self, edge_id: str) -> bool:
        """Remove an edge"""
        if edge_id not in self.edges:
            return False
        del self.edges[edge_id]
        self._dirty = True
        self.save()
        return True

    # --- Query Operations ---

    def query(self, node_types: List[NodeType] = None,
              relationship_types: List[RelationshipType] = None,
              property_filters: Dict[str, Any] = None) -> Dict[str, List]:
        """
        Query the graph with filters.
        Returns: {"nodes": [...], "edges": [...]}
        """
        result_nodes = list(self.nodes.values())
        result_edges = list(self.edges.values())

        if node_types:
            type_values = [t.value if isinstance(t, NodeType) else t for t in node_types]
            result_nodes = [n for n in result_nodes if n.type.value in type_values]

        if relationship_types:
            rel_values = [r.value if isinstance(r, RelationshipType) else r for r in relationship_types]
            result_edges = [e for e in result_edges if e.type.value in rel_values]

        if property_filters:
            for key, value in property_filters.items():
                result_nodes = [
                    n for n in result_nodes
                    if n.properties.get(key) == value
                ]

        return {"nodes": [n.to_dict() for n in result_nodes], "edges": [e.to_dict() for e in result_edges]}

    def traverse(self, start_node_id: str, depth: int = 1,
                 rel_type: RelationshipType = None) -> List[Dict[str, Any]]:
        """Traverse the graph from a starting node"""
        if start_node_id not in self.nodes:
            return []

        results = []
        visited = {start_node_id}
        current_level = [start_node_id]

        for _ in range(depth):
            next_level = []
            for node_id in current_level:
                for edge in self.edges.values():
                    neighbor = None
                    if edge.source == node_id and edge.target not in visited:
                        neighbor = edge.target
                    elif edge.target == node_id and edge.source not in visited:
                        neighbor = edge.source

                    if neighbor and (rel_type is None or edge.type == rel_type):
                        visited.add(neighbor)
                        next_level.append(neighbor)
                        results.append({
                            "from": node_id,
                            "to": neighbor,
                            "relationship": edge.type.value,
                            "edge_id": edge.id
                        })
            current_level = next_level

        return results

    # --- Persistence ---

    def save(self) -> None:
        """Persist graph to storage file (atomic write).

        Called explicitly or after bulk operations.  The two-step write
        (temp → rename) ensures a crash mid-write never leaves a half-written
        file on disk.
        """
        self._ensure_storage_dir()
        data = {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "version": self._graph_version(),
            "last_updated": datetime.now().isoformat()
        }

        dir_name = os.path.dirname(self.storage_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.storage_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        self._dirty = False

    def _load(self) -> None:
        """Load graph from storage file"""
        if not os.path.exists(self.storage_path):
            return

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)

            for node_data in data.get("nodes", []):
                node = Node.from_dict(node_data)
                self.nodes[node.id] = node

            for edge_data in data.get("edges", []):
                edge = Edge.from_dict(edge_data)
                self.edges[edge.id] = edge
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load knowledge graph: {e}")

    def _graph_version(self) -> int:
        """Calculate current graph version"""
        if not self.nodes and not self.edges:
            return 1
        max_ver = 1
        for n in self.nodes.values():
            max_ver = max(max_ver, n.version)
        for e in self.edges.values():
            max_ver = max(max_ver, e.version)
        return max_ver

    # --- Statistics ---

    def stats(self) -> Dict[str, Any]:
        """Get graph statistics"""
        type_counts = {}
        for n in self.nodes.values():
            t = n.type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        rel_counts = {}
        for e in self.edges.values():
            r = e.type.value
            rel_counts[r] = rel_counts.get(r, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes_by_type": type_counts,
            "edges_by_type": rel_counts,
            "orphan_nodes": [n.id for n in self.nodes.values()
                             if not any(e.source == n.id or e.target == n.id for e in self.edges.values())],
            "graph_version": self._graph_version()
        }
