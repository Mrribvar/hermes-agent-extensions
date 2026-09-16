"""
Impact Analysis Engine - Hermes Phase 8

Before any change, predicts impact:
- Which modules break if a file is removed?
- Which projects are affected?
- Which tools stop working?
- Which databases are impacted?
- Rollback plan
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ImpactResult:
    """Result of an impact analysis"""
    target: str
    target_type: str
    affected_modules: List[str] = field(default_factory=list)
    affected_projects: List[str] = field(default_factory=list)
    affected_tools: List[str] = field(default_factory=list)
    affected_databases: List[str] = field(default_factory=list)
    affected_skills: List[str] = field(default_factory=list)
    affected_apis: List[str] = field(default_factory=list)
    severity: str = "unknown"  # low, medium, high, critical
    rollback_plan: str = ""
    rollback_available: bool = True
    confidence: float = 0.0  # 0.0 - 1.0
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "target_type": self.target_type,
            "affected_modules": self.affected_modules,
            "affected_projects": self.affected_projects,
            "affected_tools": self.affected_tools,
            "affected_databases": self.affected_databases,
            "affected_skills": self.affected_skills,
            "affected_apis": self.affected_apis,
            "severity": self.severity,
            "rollback_plan": self.rollback_plan,
            "rollback_available": self.rollback_available,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


class ImpactAnalysisEngine:
    """
    Impact Analysis Engine.

    Answers: "If X changes/removes, what breaks?"
    Uses Knowledge Graph to trace dependencies.
    """

    def __init__(self, knowledge_graph=None, project_registry=None):
        self.kg = knowledge_graph
        self.project_registry = project_registry

    def analyze_file_removal(self, file_path: str) -> ImpactResult:
        """Analyze impact of removing a file"""
        result = ImpactResult(
            target=file_path,
            target_type="File",
            rollback_plan=f"Restore {file_path} from backup or git",
            rollback_available=True
        )

        if not self.kg:
            result.severity = "unknown"
            result.confidence = 0.0
            result.reasoning = "No knowledge graph available — impact cannot be traced"
            return result

        # Find the file node
        file_nodes = self.kg.get_nodes_by_label(file_path)
        if not file_nodes:
            result.severity = "low"
            result.confidence = 0.3
            result.reasoning = f"File '{file_path}' not found in knowledge graph — may be untracked"
            return result

        for file_node in file_nodes:
            # Trace all outgoing edges (what depends on this file)
            outgoing = self.kg.get_edges_by_source(file_node.id)
            for edge in outgoing:
                target_node = self.kg.get_node(edge.target)
                if not target_node:
                    continue

                self._classify_impact(target_node, edge.type.value, result)

            # Trace incoming edges (what this file depends on)
            incoming = self.kg.get_edges_by_target(file_node.id)
            for edge in incoming:
                source_node = self.kg.get_node(edge.source)
                if source_node:
                    result.affected_modules.append(source_node.label)

        # Determine severity
        result.severity = self._determine_severity(result)
        result.confidence = self._calculate_confidence(result)

        # Generate reasoning
        result.reasoning = self._generate_reasoning(result)

        return result

    def analyze_skill_removal(self, skill_name: str) -> ImpactResult:
        """Analyze impact of removing a skill"""
        result = ImpactResult(
            target=skill_name,
            target_type="Skill",
            rollback_plan=f"Restore {skill_name} from skills archive",
            rollback_available=True
        )

        if not self.kg:
            result.severity = "unknown"
            result.confidence = 0.0
            return result

        skill_nodes = self.kg.get_nodes_by_label(skill_name)
        if not skill_nodes:
            result.severity = "low"
            result.confidence = 0.3
            return result

        for skill_node in skill_nodes:
            outgoing = self.kg.get_edges_by_source(skill_node.id)
            for edge in outgoing:
                target_node = self.kg.get_node(edge.target)
                if target_node:
                    self._classify_impact(target_node, edge.type.value, result)

        result.severity = self._determine_severity(result)
        result.confidence = self._calculate_confidence(result)
        result.reasoning = self._generate_reasoning(result)

        return result

    def analyze_project_removal(self, project_name: str) -> ImpactResult:
        """Analyze impact of removing an entire project"""
        result = ImpactResult(
            target=project_name,
            target_type="Project",
            rollback_plan=f"Restore {project_name} from project registry and backups",
            rollback_available=True
        )

        if not self.kg:
            result.severity = "high"
            result.confidence = 0.4
            return result

        proj_nodes = self.kg.get_nodes_by_label(project_name)
        if not proj_nodes:
            result.severity = "medium"
            result.confidence = 0.3
            return result

        for proj_node in proj_nodes:
            outgoing = self.kg.get_edges_by_source(proj_node.id)
            for edge in outgoing:
                target_node = self.kg.get_node(edge.target)
                if target_node:
                    self._classify_impact(target_node, edge.type.value, result)

            # Also check incoming edges (what belongs to this project)
            incoming = self.kg.get_edges_by_target(proj_node.id)
            for edge in incoming:
                source_node = self.kg.get_node(edge.source)
                if source_node:
                    result.affected_modules.append(source_node.label)

        result.severity = self._determine_severity(result)
        result.confidence = self._calculate_confidence(result)
        result.reasoning = self._generate_reasoning(result)

        return result

    def _classify_impact(self, node, edge_type: str, result: ImpactResult) -> None:
        """Classify an affected node into the right category"""
        node_type = node.type.value if hasattr(node.type, 'value') else str(node.type)

        if node_type == "Module":
            result.affected_modules.append(node.label)
        elif node_type == "Project":
            if node.label not in result.affected_projects:
                result.affected_projects.append(node.label)
        elif node_type == "Tool":
            result.affected_tools.append(node.label)
        elif node_type == "Database":
            result.affected_databases.append(node.label)
        elif node_type == "Skill":
            result.affected_skills.append(node.label)
        elif node_type == "API":
            result.affected_apis.append(node.label)
        else:
            # Generic classification based on relationship
            if edge_type in ("depends_on", "imports", "uses"):
                result.affected_modules.append(node.label)

    def _determine_severity(self, result: ImpactResult) -> str:
        """Determine overall severity from affected components"""
        total_affected = (len(result.affected_modules) +
                         len(result.affected_projects) +
                         len(result.affected_tools) +
                         len(result.affected_databases) +
                         len(result.affected_skills) +
                         len(result.affected_apis))

        if total_affected == 0:
            return "low"
        elif total_affected <= 2:
            return "medium"
        elif total_affected <= 5:
            return "high"
        else:
            return "critical"

    def _calculate_confidence(self, result: ImpactResult) -> float:
        """Calculate confidence in the analysis"""
        total = len(result.affected_modules) + len(result.affected_projects)
        if total == 0:
            return 0.3
        return min(round(0.5 + (total * 0.1), 2), 1.0)

    def _generate_reasoning(self, result: ImpactResult) -> str:
        """Generate human-readable reasoning"""
        parts = []

        if result.affected_modules:
            parts.append(f"Modules affected: {', '.join(result.affected_modules)}")
        if result.affected_projects:
            parts.append(f"Projects affected: {', '.join(result.affected_projects)}")
        if result.affected_tools:
            parts.append(f"Tools affected: {', '.join(result.affected_tools)}")
        if result.affected_databases:
            parts.append(f"Databases affected: {', '.join(result.affected_databases)}")
        if result.affected_skills:
            parts.append(f"Skills affected: {', '.join(result.affected_skills)}")
        if result.affected_apis:
            parts.append(f"APIs affected: {', '.join(result.affected_apis)}")

        if not parts:
            return "No direct dependencies found. Impact is limited."

        return f"Impact analysis: {'; '.join(parts)}. Severity: {result.severity}."

    def batch_analyze(self, targets: List[Dict[str, str]]) -> List[ImpactResult]:
        """Analyze multiple targets at once"""
        results = []
        for target in targets:
            target_type = target.get("type", "File")
            target_name = target.get("name", "")

            if target_type == "File":
                results.append(self.analyze_file_removal(target_name))
            elif target_type == "Skill":
                results.append(self.analyze_skill_removal(target_name))
            elif target_type == "Project":
                results.append(self.analyze_project_removal(target_name))
            else:
                results.append(self.analyze_file_removal(target_name))

        return results