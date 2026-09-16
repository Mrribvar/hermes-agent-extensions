"""
Graph Builder - Hermes Phase 8, Task 2

Builds the Knowledge Graph from available data sources:
- Project Registry
- Decision Memory
- Risk Classifier
- Governance Engine
- Capability Registry (from hermes-agent)
- File system scan (non-invasive)

No data is guessed. Only what exists is added.
"""

import json
import os
from typing import Dict, Any, List

from governance.knowledge_graph import KnowledgeGraph, Node, NodeType, Edge, RelationshipType
from governance.project_registry import ProjectRegistry
from governance.decision_memory import DecisionMemory
from governance.risk_classifier import RiskClassifier
from governance.governance_engine import GovernanceEngine


class GraphBuilder:
    """
    Builds the Knowledge Graph from all available data sources.

    Sources are read-only. No modifications to source data.
    """

    def __init__(self, kg: KnowledgeGraph = None):
        self.kg = kg or KnowledgeGraph()
        self.build_log: List[str] = []

    def build_from_project_registry(self, project_registry: ProjectRegistry) -> int:
        """Build nodes and edges from project registry"""
        count = 0
        self.build_log.append("Starting build from Project Registry...")

        for proj in project_registry.get_all():
            # Create Project node
            node = Node(
                id=f"proj_{proj.name}",
                type=NodeType.PROJECT,
                label=proj.name,
                properties={
                    "status": proj.status,
                    "health": proj.health,
                    "owner": proj.owner,
                    "next_action": proj.next_action,
                    "last_activity": proj.last_activity
                },
                source="project_registry"
            )
            self.kg.add_node(node)
            count += 1

            # Create edges for dependencies
            for dep in proj.dependencies:
                dep_node = Node(
                    id=f"mod_{dep}",
                    type=NodeType.MODULE,
                    label=dep,
                    properties={"parent_project": proj.name},
                    source="project_registry"
                )
                self.kg.add_node(dep_node)

                edge = Edge(
                    id=f"edge_{proj.name}_dep_{dep}",
                    source=f"proj_{proj.name}",
                    target=f"mod_{dep}",
                    type=RelationshipType.DEPENDS_ON,
                    properties={"source": "project_registry", "critical": True}
                )
                try:
                    self.kg.add_edge(edge)
                except ValueError:
                    pass

        self.build_log.append(f"  Added {count} project nodes from Project Registry")
        return count

    def build_from_decision_memory(self, decision_memory: DecisionMemory) -> int:
        """Build nodes from decision memory"""
        count = 0
        self.build_log.append("Starting build from Decision Memory...")

        for decision in decision_memory.get_all():
            node = Node(
                id=f"dec_{decision.id}",
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
            self.kg.add_node(node)
            count += 1

        self.build_log.append(f"  Added {count} decision nodes from Decision Memory")
        return count

    def build_from_risk_classifier(self, risk_classifier: RiskClassifier) -> int:
        """Build nodes from risk classifier assessments"""
        count = 0
        self.build_log.append("Starting build from Risk Classifier...")

        for assessment in risk_classifier.assessments:
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
            self.kg.add_node(node)
            count += 1

        self.build_log.append(f"  Added {count} risk nodes from Risk Classifier")
        return count

    def build_from_governance_engine(self, governance_engine: GovernanceEngine) -> int:
        """Build nodes from governance engine reports"""
        count = 0
        self.build_log.append("Starting build from Governance Engine...")

        for report in governance_engine.reports:
            node = Node(
                id=f"gov_{report.issue}_{report.project}",
                type=NodeType.CONFIG,
                label=f"Governance Issue: {report.issue}",
                properties={
                    "severity": report.severity.value,
                    "evidence": report.evidence,
                    "recommendation": report.recommendation,
                    "action_required": report.action_required,
                    "project": report.project
                },
                source="governance_engine"
            )
            self.kg.add_node(node)
            count += 1

        self.build_log.append(f"  Added {count} governance nodes from Governance Engine")
        return count

    def build_from_capability_registry(self) -> int:
        """
        Build nodes from hermes-agent capability registry.

        Scans the hermes-agent directory for existing modules,
        skills, tools, and providers. Read-only — no modifications.
        """
        count = 0
        self.build_log.append("Starting build from Capability Registry...")

        hermes_agent_path = os.environ.get("HERMES_AGENT_PATH", os.path.expanduser("~/hermes-agent"))

        # Scan for skills directory
        skills_path = os.path.join(hermes_agent_path, "skills")
        if os.path.exists(skills_path):
            skill_dirs = [d for d in os.listdir(skills_path)
                         if os.path.isdir(os.path.join(skills_path, d))]
            for skill_dir in skill_dirs:
                node = Node(
                    id=f"skill_{skill_dir}",
                    type=NodeType.SKILL,
                    label=skill_dir,
                    properties={
                        "location": f"skills/{skill_dir}",
                        "type": "skill_directory"
                    },
                    source="capability_registry_scan"
                )
                self.kg.add_node(node)
                count += 1

        # Scan for tools directory
        tools_path = os.path.join(hermes_agent_path, "tools")
        if os.path.exists(tools_path):
            tool_files = [f for f in os.listdir(tools_path)
                         if f.endswith('.py')]
            for tool_file in tool_files:
                node = Node(
                    id=f"tool_{tool_file.replace('.py', '')}",
                    type=NodeType.TOOL,
                    label=tool_file.replace('.py', ''),
                    properties={
                        "location": f"tools/{tool_file}",
                        "type": "python_tool"
                    },
                    source="capability_registry_scan"
                )
                self.kg.add_node(node)
                count += 1

        # Scan for providers directory
        providers_path = os.path.join(hermes_agent_path, "providers")
        if os.path.exists(providers_path):
            provider_dirs = [d for d in os.listdir(providers_path)
                            if os.path.isdir(os.path.join(providers_path, d))]
            for prov_dir in provider_dirs:
                node = Node(
                    id=f"provider_{prov_dir}",
                    type=NodeType.PROVIDER,
                    label=prov_dir,
                    properties={
                        "location": f"providers/{prov_dir}",
                        "type": "provider"
                    },
                    source="capability_registry_scan"
                )
                self.kg.add_node(node)
                count += 1

        # Scan for gateway
        gateway_path = os.path.join(hermes_agent_path, "gateway")
        if os.path.exists(gateway_path):
            node = Node(
                id="gateway_main",
                type=NodeType.GATEWAY,
                label="gateway",
                properties={"location": "gateway/", "type": "messaging_gateway"},
                source="capability_registry_scan"
            )
            self.kg.add_node(node)
            count += 1

        self.build_log.append(f"  Added {count} capability nodes from scan")
        return count

    def build_from_file_system(self, base_path: str = None) -> int:
        """
        Scan file system for project-related files.

        Non-invasive — only reads directory structure, no modifications.
        """
        count = 0
        base = base_path or os.path.expanduser("~")

        self.build_log.append(f"Scanning file system at {base}...")

        # Key project directories
        project_dirs = [
            "hermes",
            "hermes-agent",
            "Seo-3D",
            "ai_video_maker",
            "Agriculture_Content_Engine_v2.0_FREEZE",
            "AgricIDaniel",
            "Business_Intelligence_Project",
            "Hermes_archive",
            "Hermes_Desktop",
            "ui-ux-pro-max-skill",
            "computer_tricks",
            "seo_project"
        ]

        for dir_name in project_dirs:
            dir_path = os.path.join(base, dir_name)
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                # Create Directory node
                node = Node(
                    id=f"dir_{dir_name}",
                    type=NodeType.DIRECTORY,
                    label=dir_name,
                    properties={
                        "path": dir_path,
                        "type": "project_directory"
                    },
                    source="filesystem_scan"
                )
                self.kg.add_node(node)
                count += 1

                # Count files in directory
                file_count = sum(1 for _ in os.walk(dir_path)
                                for f in _[2] if not f.startswith('.'))
                node.update_property("file_count", file_count)

        self.build_log.append(f"  Added {count} directory nodes from file system scan")
        return count

    def build_all(self) -> Dict[str, Any]:
        """Build the complete knowledge graph from all sources"""
        self.build_log = []
        self.build_log.append("=" * 60)
        self.build_log.append("Knowledge Graph Builder - Starting Full Build")
        self.build_log.append("=" * 60)

        total_nodes_before = len(self.kg.nodes)

        # Build from each source
        counts = {}

        # 1. Project Registry
        try:
            pr = ProjectRegistry()
            counts["project_registry"] = self.build_from_project_registry(pr)
        except Exception as e:
            self.build_log.append(f"  ERROR in Project Registry: {e}")
            counts["project_registry"] = 0

        # 2. Decision Memory
        try:
            dm = DecisionMemory()
            counts["decision_memory"] = self.build_from_decision_memory(dm)
        except Exception as e:
            self.build_log.append(f"  ERROR in Decision Memory: {e}")
            counts["decision_memory"] = 0

        # 3. Risk Classifier (may be empty if no assessments yet)
        try:
            rc = RiskClassifier()
            counts["risk_classifier"] = self.build_from_risk_classifier(rc)
        except Exception as e:
            self.build_log.append(f"  ERROR in Risk Classifier: {e}")
            counts["risk_classifier"] = 0

        # 4. Governance Engine (may be empty)
        try:
            ge = GovernanceEngine()
            counts["governance_engine"] = self.build_from_governance_engine(ge)
        except Exception as e:
            self.build_log.append(f"  ERROR in Governance Engine: {e}")
            counts["governance_engine"] = 0

        # 5. Capability Registry (scan)
        try:
            counts["capability_registry"] = self.build_from_capability_registry()
        except Exception as e:
            self.build_log.append(f"  ERROR in Capability Registry: {e}")
            counts["capability_registry"] = 0

        # 6. File System
        try:
            counts["filesystem"] = self.build_from_file_system()
        except Exception as e:
            self.build_log.append(f"  ERROR in File System scan: {e}")
            counts["filesystem"] = 0

        total_nodes_after = len(self.kg.nodes)
        total_edges = len(self.kg.edges)
        new_nodes = total_nodes_after - total_nodes_before

        # Persist the full build in one atomic write.
        if new_nodes or total_edges:
            self.kg.save()

        summary = {
            "build_log": self.build_log,
            "nodes_added_by_source": counts,
            "total_nodes": total_nodes_after,
            "total_edges": total_edges,
            "new_nodes_this_build": new_nodes,
            "graph_stats": self.kg.stats()
        }

        self.build_log.append("=" * 60)
        self.build_log.append(f"Build Complete: {total_nodes_after} nodes, {total_edges} edges")
        self.build_log.append("=" * 60)

        return summary

    def get_build_log(self) -> List[str]:
        """Get the build log"""
        return self.build_log.copy()