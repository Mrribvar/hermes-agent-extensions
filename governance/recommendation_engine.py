"""
Recommendation Engine - Hermes Phase 8

Generates recommendations based on Knowledge Graph analysis:
- Unused Files
- Dead Code
- Duplicate Components
- Architecture Improvements
- Performance Improvements
- Risk Reduction
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Recommendation:
    """A single recommendation"""
    id: str
    category: str  # unused_files, dead_code, duplicates, architecture, performance, risk
    title: str
    description: str
    evidence: str
    confidence: float  # 0.0 - 1.0
    impact: str  # low, medium, high, critical
    priority: str  # low, medium, high, urgent
    affected_nodes: List[str] = field(default_factory=list)
    suggested_action: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "impact": self.impact,
            "priority": self.priority,
            "affected_nodes": self.affected_nodes,
            "suggested_action": self.suggested_action,
            "created_at": self.created_at
        }


class RecommendationEngine:
    """
    Generates recommendations by analyzing the Knowledge Graph.

    Categories:
    - unused_files: Files with no incoming/outgoing edges
    - dead_code: Modules/packages with no dependents
    - duplicate_components: Nodes with similar labels/properties
    - architecture_improvements: Structural issues in the graph
    - performance_improvements: Bottlenecks and inefficiencies
    - risk_reduction: High-risk nodes that need attention
    """

    def __init__(self, knowledge_graph=None, project_registry=None, decision_memory=None):
        self.kg = knowledge_graph
        self.project_registry = project_registry
        self.decision_memory = decision_memory
        self.recommendations: List[Recommendation] = []

    def generate_all(self) -> List[Recommendation]:
        """Generate all categories of recommendations"""
        self.recommendations = []

        if self.kg:
            self._find_unused_files()
            self._find_dead_code()
            self._find_duplicates()
            self._find_architecture_improvements()
            self._find_performance_improvements()
            self._find_risk_reductions()

        return self.recommendations

    def _find_unused_files(self) -> None:
        """Find files that are not referenced by any other node"""
        if not self.kg:
            return

        file_nodes = self.kg.get_nodes_by_type_value("File")
        for node in file_nodes:
            outgoing = self.kg.get_edges_by_source(node.id)
            incoming = self.kg.get_edges_by_target(node.id)

            if not outgoing and not incoming:
                rec = Recommendation(
                    id=f"rec_{datetime.now().strftime('%Y%m%d%H%M%S')}_{node.id[:6]}",
                    category="unused_files",
                    title=f"Unused file: {node.label}",
                    description=f"File '{node.label}' exists but has no connections to any other component.",
                    evidence=f"Node {node.id} has 0 incoming and 0 outgoing edges",
                    confidence=0.8,
                    impact="low",
                    priority="low",
                    affected_nodes=[node.id],
                    suggested_action="Review if this file is still needed. If not, archive it."
                )
                self.recommendations.append(rec)

    def _find_dead_code(self) -> None:
        """Find modules/packages with no dependents"""
        if not self.kg:
            return

        module_nodes = self.kg.get_nodes_by_type_value("Module")
        for node in module_nodes:
            incoming = self.kg.get_edges_by_target(node.id)

            if not incoming:
                rec = Recommendation(
                    id=f"rec_{datetime.now().strftime('%Y%m%d%H%M%S')}_{node.id[:6]}",
                    category="dead_code",
                    title=f"Dead module: {node.label}",
                    description=f"Module '{node.label}' is not used by any other component.",
                    evidence=f"Node {node.id} has 0 incoming edges",
                    confidence=0.7,
                    impact="medium",
                    priority="medium",
                    affected_nodes=[node.id],
                    suggested_action="Consider removing or archiving this module if it serves no purpose."
                )
                self.recommendations.append(rec)

    def _find_duplicates(self) -> None:
        """Find potential duplicate components"""
        if not self.kg:
            return

        # Group nodes by label and find duplicates
        label_groups: Dict[str, List] = {}
        for node in self.kg.nodes.values():
            key = node.label.lower().strip()
            if key not in label_groups:
                label_groups[key] = []
            label_groups[key].append(node)

        for label, nodes in label_groups.items():
            if len(nodes) > 1:
                node_ids = [n.id for n in nodes]
                rec = Recommendation(
                    id=f"rec_{datetime.now().strftime('%Y%m%d%H%M%S')}_{label[:6]}",
                    category="duplicate_components",
                    title=f"Potential duplicate: {label}",
                    description=f"Found {len(nodes)} nodes with label '{label}'. These may be duplicates.",
                    evidence=f"Nodes: {', '.join(node_ids)}",
                    confidence=0.6,
                    impact="medium",
                    priority="medium",
                    affected_nodes=node_ids,
                    suggested_action="Review and consolidate duplicate components."
                )
                self.recommendations.append(rec)

    def _find_architecture_improvements(self) -> None:
        """Find architectural issues in the graph"""
        if not self.kg:
            return

        # Check for orphan nodes (nodes with no relationships)
        orphan_count = 0
        for node in self.kg.nodes.values():
            outgoing = self.kg.get_edges_by_source(node.id)
            incoming = self.kg.get_edges_by_target(node.id)
            if not outgoing and not incoming:
                orphan_count += 1

        if orphan_count > 3:
            rec = Recommendation(
                id=f"rec_{datetime.now().strftime('%Y%m%d%H%M%S')}_orphans",
                category="architecture_improvements",
                title=f"High orphan count: {orphan_count} disconnected nodes",
                description="Many nodes in the knowledge graph have no connections. This suggests incomplete mapping or isolated components.",
                evidence=f"{orphan_count} orphan nodes detected",
                confidence=0.75,
                impact="medium",
                priority="high",
                suggested_action="Map connections for orphan nodes or archive them if truly unused."
            )
            self.recommendations.append(rec)

        # Check for nodes with too many dependencies (hub nodes)
        for node in self.kg.nodes.values():
            outgoing = self.kg.get_edges_by_source(node.id)
            if len(outgoing) > 10:
                rec = Recommendation(
                    id=f"rec_{datetime.now().strftime('%Y%m%d%H%M%S')}_hub_{node.id[:6]}",
                    category="architecture_improvements",
                    title=f"Hub node: {node.label} has {len(outgoing)} dependencies",
                    description=f"Node '{node.label}' is a high-dependency hub. Changes here have wide impact.",
                    evidence=f"{len(outgoing)} outgoing edges from {node.id}",
                    confidence=0.8,
                    impact="high",
                    priority="high",
                    affected_nodes=[node.id],
                    suggested_action="Consider refactoring to reduce coupling. Add caching or abstraction layer."
                )
                self.recommendations.append(rec)

    def _find_performance_improvements(self) -> None:
        """Find performance-related recommendations"""
        if not self.kg:
            return

        # Check for circular dependencies (performance anti-pattern)
        circular = self._detect_circular_dependencies()
        if circular:
            rec = Recommendation(
                id=f"rec_{datetime.now().strftime('%Y%m%d%H%M%S')}_circular",
                category="performance_improvements",
                title=f"Circular dependencies detected: {len(circular)} cycles",
                description="Circular dependencies can cause performance issues and make the system harder to understand.",
                evidence=f"Cycles: {len(circular)}",
                confidence=0.9,
                impact="high",
                priority="high",
                affected_nodes=[e for cycle in circular for e in cycle],
                suggested_action="Break circular dependencies by introducing interfaces or event-driven communication."
            )
            self.recommendations.append(rec)

    def _find_risk_reductions(self) -> None:
        """Find high-risk areas that need attention"""
        if not self.kg:
            return

        # Check for nodes with HIGH_RISK relationships
        high_risk_edges = self.kg.get_edges_by_type_value("depends_on")
        critical_nodes = []
        for edge in high_risk_edges:
            source_node = self.kg.get_node(edge.source)
            if source_node and source_node.type.value in ("Database", "Config", "Runtime"):
                critical_nodes.append(source_node.id)

        if critical_nodes:
            rec = Recommendation(
                id=f"rec_{datetime.now().strftime('%Y%m%d%H%M%S')}_risk",
                category="risk_reduction",
                title=f"Critical dependencies found: {len(set(critical_nodes))} high-risk nodes",
                description="Core system components have direct dependencies that could cascade failures.",
                evidence=f"{len(set(critical_nodes))} critical nodes with depends_on relationships",
                confidence=0.7,
                impact="high",
                priority="urgent",
                affected_nodes=list(set(critical_nodes)),
                suggested_action="Add monitoring, alerting, and automated health checks for critical dependencies."
            )
            self.recommendations.append(rec)

    def _detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies in the graph using DFS"""
        if not self.kg:
            return []

        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node_id: str, path: List[str]) -> None:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            for edge in self.kg.get_edges_by_source(node_id):
                neighbor = edge.target
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.discard(node_id)

        for node_id in self.kg.nodes:
            if node_id not in visited:
                dfs(node_id, [])

        return cycles

    def get_recommendations_by_category(self, category: str) -> List[Recommendation]:
        """Filter recommendations by category"""
        return [r for r in self.recommendations if r.category == category]

    def get_recommendations_by_priority(self, priority: str) -> List[Recommendation]:
        """Filter recommendations by priority"""
        return [r for r in self.recommendations if r.priority == priority]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all recommendations"""
        by_category: Dict[str, int] = {}
        by_priority: Dict[str, int] = {}
        by_impact: Dict[str, int] = {}

        for rec in self.recommendations:
            by_category[rec.category] = by_category.get(rec.category, 0) + 1
            by_priority[rec.priority] = by_priority.get(rec.priority, 0) + 1
            by_impact[rec.impact] = by_impact.get(rec.impact, 0) + 1

        return {
            "total_recommendations": len(self.recommendations),
            "by_category": by_category,
            "by_priority": by_priority,
            "by_impact": by_impact,
            "average_confidence": round(
                sum(r.confidence for r in self.recommendations) / len(self.recommendations), 2
            ) if self.recommendations else 0.0
        }