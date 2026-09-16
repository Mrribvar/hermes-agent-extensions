"""
Integration Layer - Hermes Phase 8, Task 8

Knowledge Graph integrates Read-Only with existing governance modules:
- Architecture Sentinel
- Health Score Engine
- Change Detection
- Capability Registry
- Project Registry
- Decision Memory

No runtime behavior changes. No automation. Read-only integration.
"""

import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import governance modules
from governance.knowledge_graph import KnowledgeGraph, Node, NodeType, Edge, RelationshipType
from governance.project_registry import ProjectRegistry, ProjectEntry
from governance.decision_memory import DecisionMemory, DecisionRecord
from governance.risk_classifier import RiskClassifier, RiskLevel
from governance.governance_engine import GovernanceEngine, GovernanceReport, Severity


class GovernanceIntegration:
    """
    Read-only integration between Knowledge Graph and governance modules.

    Syncs data from existing modules into the Knowledge Graph.
    No writes back to existing modules.
    No cron, no automation, no runtime changes.
    """

    def __init__(self, kg: KnowledgeGraph = None):
        self.kg = kg or KnowledgeGraph()
        self.project_registry = None
        self.decision_memory = None
        self.experience_memory = None
        self.risk_classifier = None
        self.governance_engine = None

    def register_project_registry(self, pr: ProjectRegistry) -> None:
        """Register project registry for integration"""
        self.project_registry = pr

    def register_decision_memory(self, dm: DecisionMemory) -> None:
        """Register decision memory for integration"""
        self.decision_memory = dm

    def register_risk_classifier(self, rc: RiskClassifier) -> None:
        """Register risk classifier for integration"""
        self.risk_classifier = rc

    def register_governance_engine(self, ge: GovernanceEngine) -> None:
        """Register governance engine for integration"""
        self.governance_engine = ge

    def sync_all(self) -> Dict[str, Any]:
        """
        Sync all governance data into the Knowledge Graph.

        Returns summary of what was synced.
        """
        synced = {
            "projects": 0,
            "decisions": 0,
            "risk_assessments": 0,
            "governance_reports": 0,
            "nodes_created": 0,
            "edges_created": 0,
            "timestamp": datetime.now().isoformat()
        }

        # Sync Project Registry
        if self.project_registry:
            count = self._sync_projects()
            synced["projects"] = count

        # Sync Decision Memory
        if self.decision_memory:
            count = self._sync_decisions()
            synced["decisions"] = count

        # Sync Risk Classifier
        if self.risk_classifier:
            count = self._sync_risk_assessments()
            synced["risk_assessments"] = count

        # Sync Governance Engine
        if self.governance_engine:
            count = self._sync_governance_reports()
            synced["governance_reports"] = count

        # Create cross-reference edges
        edges = self._create_cross_reference_edges()
        synced["edges_created"] = edges

        synced["nodes_created"] = synced["projects"] + synced["decisions"] + synced["risk_assessments"] + synced["governance_reports"]

        # Persist all accumulated graph mutations in one atomic write.
        if synced["nodes_created"] or synced["edges_created"]:
            self.kg.save()

        return synced

    def _sync_projects(self) -> int:
        """Sync project registry into knowledge graph"""
        if not self.project_registry:
            return 0

        count = 0
        for proj in self.project_registry.get_all():
            # Create Project node
            node = Node(
                id=f"project_{proj.name}",
                type=NodeType.PROJECT,
                label=proj.name,
                properties={
                    "status": proj.status,
                    "health": proj.health,
                    "owner": proj.owner,
                    "dependencies": proj.dependencies,
                    "next_action": proj.next_action,
                    "last_activity": proj.last_activity
                },
                source="project_registry"
            )
            existing = self.kg.get_node(node.id)
            if not existing:
                self.kg.add_node(node)
                count += 1

            # Create edges for dependencies
            for dep in proj.dependencies:
                dep_node_id = f"module_{dep}"
                dep_node = self.kg.get_node(dep_node_id)
                if not dep_node:
                    dep_node = Node(
                        id=dep_node_id,
                        type=NodeType.MODULE,
                        label=dep,
                        properties={"type": "dependency"},
                        source="project_registry"
                    )
                    self.kg.add_node(dep_node)

                # Create depends_on edge
                edge_id = f"edge_{proj.name}_depends_{dep}"
                edge = Edge(
                    id=edge_id,
                    source=f"project_{proj.name}",
                    target=dep_node_id,
                    type=RelationshipType.DEPENDS_ON,
                    properties={"critical": True, "source": "project_registry"}
                )
                try:
                    self.kg.add_edge(edge)
                except ValueError:
                    pass  # Edge already exists

        return count

    def _sync_decisions(self) -> int:
        """Sync decision memory into knowledge graph"""
        if not self.decision_memory:
            return 0

        count = 0
        for decision in self.decision_memory.get_all():
            node = Node(
                id=f"decision_{decision.id}",
                type=NodeType.DECISION,
                label=decision.decision,
                properties={
                    "date": decision.date,
                    "reason": decision.reason,
                    "impact": decision.impact,
                    "rollback": decision.rollback,
                    "result": decision.result
                },
                source="decision_memory"
            )
            existing = self.kg.get_node(node.id)
            if not existing:
                self.kg.add_node(node)
                count += 1

        # Also sync experiences
        if self.experience_memory:
            for exp in self.experience_memory.get_all():
                exp_node = Node(
                    id=f"exp_{exp.id}",
                    type=NodeType.EXPERIENCE,
                    label=exp.problem[:60],
                    properties={
                        "problem": exp.problem,
                        "analysis": exp.analysis,
                        "solution": exp.solution,
                        "result": exp.result,
                        "confidence": exp.confidence,
                        "lessons_learned": exp.lessons_learned,
                        "future_recommendation": exp.future_recommendation,
                        "tags": exp.tags
                    },
                    source="experience_memory"
                )
                existing_exp = self.kg.get_node(exp_node.id)
                if not existing_exp:
                    self.kg.add_node(exp_node)
                    count += 1

        return count

    def _sync_risk_assessments(self) -> int:
        """Sync risk classifier assessments into knowledge graph"""
        if not self.risk_classifier:
            return 0

        count = 0
        for assessment in self.risk_classifier.assessments:
            node = Node(
                id=f"risk_{assessment.change_id}",
                type=NodeType.CONFIG,
                label=f"Risk: {assessment.change_type}",
                properties={
                    "risk_level": assessment.risk_level.value,
                    "reason": assessment.reason,
                    "evidence": assessment.evidence,
                    "rollback_available": assessment.rollback_available,
                    "rollback_method": assessment.rollback_method
                },
                source="risk_classifier"
            )
            existing = self.kg.get_node(node.id)
            if not existing:
                self.kg.add_node(node)
                count += 1

        return count

    def _sync_governance_reports(self) -> int:
        """Sync governance reports into knowledge graph"""
        if not self.governance_engine:
            return 0

        count = 0
        for report in self.governance_engine.reports:
            node = Node(
                id=f"gov_report_{report.issue}_{report.project}",
                type=NodeType.CONFIG,
                label=f"Governance: {report.issue}",
                properties={
                    "severity": report.severity.value,
                    "evidence": report.evidence,
                    "recommendation": report.recommendation,
                    "action_required": report.action_required,
                    "project": report.project
                },
                source="governance_engine"
            )
            existing = self.kg.get_node(node.id)
            if not existing:
                self.kg.add_node(node)
                count += 1

        return count

    def _create_cross_reference_edges(self) -> int:
        """Create cross-reference edges between synced data"""
        edge_count = 0

        # Link decisions to related projects
        if self.decision_memory and self.project_registry:
            for decision in self.decision_memory.get_all():
                decision_node = self.kg.get_node(f"decision_{decision.id}")
                if not decision_node:
                    continue

                for proj in self.project_registry.get_all():
                    if proj.name.lower() in decision.decision.lower() or \
                       proj.name.lower() in decision.reason.lower() or \
                       proj.name.lower() in decision.impact.lower():
                        edge_id = f"edge_decision_{decision.id}_project_{proj.name}"
                        try:
                            edge = Edge(
                                id=edge_id,
                                source=f"decision_{decision.id}",
                                target=f"project_{proj.name}",
                                type=RelationshipType.RELATED_TO,
                                properties={"source": "integration"}
                            )
                            self.kg.add_edge(edge)
                            edge_count += 1
                        except ValueError:
                            pass

        return edge_count

    def get_integration_status(self) -> Dict[str, Any]:
        """Get status of all integrations"""
        return {
            "project_registry_connected": self.project_registry is not None,
            "decision_memory_connected": self.decision_memory is not None,
            "risk_classifier_connected": self.risk_classifier is not None,
            "governance_engine_connected": self.governance_engine is not None,
            "knowledge_graph_nodes": len(self.kg.nodes),
            "knowledge_graph_edges": len(self.kg.edges),
            "graph_stats": self.kg.stats(),
            "runtime_behavior_changed": False,
            "automation_active": False,
            "cron_active": False
        }