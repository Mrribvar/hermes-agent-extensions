"""
Dependency Intelligence - Hermes Phase 8

Extracts and analyzes dependencies for each project:
- Critical Files
- Required Skills
- Required Tools
- Required Databases
- Required Providers
- Runtime Dependencies
- Config Dependencies
- Risk Score
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class DependencyType(str, Enum):
    CRITICAL_FILE = "critical_file"
    REQUIRED_SKILL = "required_skill"
    REQUIRED_TOOL = "required_tool"
    REQUIRED_DATABASE = "required_database"
    REQUIRED_PROVIDER = "required_provider"
    RUNTIME_DEPENDENCY = "runtime_dependency"
    CONFIG_DEPENDENCY = "config_dependency"


@dataclass
class DependencyInfo:
    """Information about a single dependency"""
    name: str
    dep_type: DependencyType
    critical: bool = False
    health_status: str = "unknown"
    last_checked: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.dep_type.value,
            "critical": self.critical,
            "health_status": self.health_status,
            "last_checked": self.last_checked,
            "notes": self.notes
        }


@dataclass
class ProjectDependencyProfile:
    """Complete dependency profile for a project"""
    project_name: str
    critical_files: List[DependencyInfo] = field(default_factory=list)
    required_skills: List[DependencyInfo] = field(default_factory=list)
    required_tools: List[DependencyInfo] = field(default_factory=list)
    required_databases: List[DependencyInfo] = field(default_factory=list)
    required_providers: List[DependencyInfo] = field(default_factory=list)
    runtime_dependencies: List[DependencyInfo] = field(default_factory=list)
    config_dependencies: List[DependencyInfo] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 - 1.0
    risk_factors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "critical_files": [d.to_dict() for d in self.critical_files],
            "required_skills": [d.to_dict() for d in self.required_skills],
            "required_tools": [d.to_dict() for d in self.required_tools],
            "required_databases": [d.to_dict() for d in self.required_databases],
            "required_providers": [d.to_dict() for d in self.required_providers],
            "runtime_dependencies": [d.to_dict() for d in self.runtime_dependencies],
            "config_dependencies": [d.to_dict() for d in self.config_dependencies],
            "risk_score": self.risk_score,
            "risk_factors": self.risk_factors
        }

    @property
    def total_dependencies(self) -> int:
        return (len(self.critical_files) + len(self.required_skills) +
                len(self.required_tools) + len(self.required_databases) +
                len(self.required_providers) + len(self.runtime_dependencies) +
                len(self.config_dependencies))

    @property
    def critical_count(self) -> int:
        return len(self.critical_files)

    @property
    def broken_dependencies(self) -> List[DependencyInfo]:
        """Return dependencies with health_status != 'healthy'"""
        all_deps = (self.critical_files + self.required_skills +
                    self.required_tools + self.required_databases +
                    self.required_providers + self.runtime_dependencies +
                    self.config_dependencies)
        return [d for d in all_deps if d.health_status not in ("healthy", "unknown")]


class DependencyIntelligence:
    """
    Extracts and analyzes project dependencies from available data sources.

    Reads from:
    - Project Registry
    - Capability Registry
    - Knowledge Graph (when available)
    - File system (critical files)

    Generates dependency profiles with risk scores.
    """

    def __init__(self, project_registry=None, knowledge_graph=None):
        self.project_registry = project_registry
        self.knowledge_graph = knowledge_graph
        self.profiles: Dict[str, ProjectDependencyProfile] = {}

    def analyze_project(self, project_name: str) -> ProjectDependencyProfile:
        """
        Analyze dependencies for a single project.

        Uses available data sources to build a complete dependency profile.
        """
        profile = ProjectDependencyProfile(project_name=project_name)

        # Get project info from registry if available
        if self.project_registry:
            proj = self.project_registry.get(project_name)
            if proj:
                # Extract dependencies from registry
                for dep in proj.dependencies:
                    dep_info = DependencyInfo(
                        name=dep,
                        dep_type=DependencyType.CONFIG_DEPENDENCY,
                        critical=True,
                        health_status="healthy",
                        notes=f"Project dependency from registry"
                    )
                    profile.config_dependencies.append(dep_info)

                # Update risk based on project health
                if proj.health == "critical":
                    profile.risk_score = max(profile.risk_score, 0.8)
                    profile.risk_factors.append(f"Project health is critical: {proj.health}")
                elif proj.health == "warning":
                    profile.risk_score = max(profile.risk_score, 0.5)
                    profile.risk_factors.append(f"Project health is warning: {proj.health}")

        # Analyze knowledge graph if available
        if self.knowledge_graph:
            self._analyze_graph_dependencies(project_name, profile)

        # Calculate final risk score
        profile.risk_score = self._calculate_risk_score(profile)

        self.profiles[project_name] = profile
        return profile

    def _analyze_graph_dependencies(self, project_name: str, profile: ProjectDependencyProfile) -> None:
        """Analyze dependencies from knowledge graph"""
        # Find project node
        project_nodes = self.knowledge_graph.get_nodes_by_label(project_name)
        if not project_nodes:
            return

        for proj_node in project_nodes:
            # Get all edges from this project
            outgoing = self.knowledge_graph.get_edges_by_source(proj_node.id)
            for edge in outgoing:
                target_node = self.knowledge_graph.get_node(edge.target)
                if not target_node:
                    continue

                dep_info = DependencyInfo(
                    name=target_node.label,
                    dep_type=self._classify_dependency_type(target_node.type.value),
                    critical=edge.type.value in ("depends_on", "imports", "uses"),
                    health_status="healthy",
                    notes=f"Connected via {edge.type.value}"
                )

                self._add_dependency_to_profile(profile, dep_info)

    def _classify_dependency_type(self, node_type_value: str) -> DependencyType:
        """Classify a node type into a dependency type"""
        type_map = {
            "File": DependencyType.CRITICAL_FILE,
            "Skill": DependencyType.REQUIRED_SKILL,
            "Tool": DependencyType.REQUIRED_TOOL,
            "Database": DependencyType.REQUIRED_DATABASE,
            "Provider": DependencyType.REQUIRED_PROVIDER,
            "Runtime": DependencyType.RUNTIME_DEPENDENCY,
            "Config": DependencyType.CONFIG_DEPENDENCY,
            "Module": DependencyType.CRITICAL_FILE,
            "Package": DependencyType.RUNTIME_DEPENDENCY,
            "API": DependencyType.REQUIRED_TOOL,
            "Gateway": DependencyType.RUNTIME_DEPENDENCY,
        }
        return type_map.get(node_type_value, DependencyType.CONFIG_DEPENDENCY)

    def _add_dependency_to_profile(self, profile: ProjectDependencyProfile, dep: DependencyInfo) -> None:
        """Add a dependency to the correct list in the profile"""
        dep_type = dep.dep_type
        if dep_type == DependencyType.CRITICAL_FILE:
            profile.critical_files.append(dep)
        elif dep_type == DependencyType.REQUIRED_SKILL:
            profile.required_skills.append(dep)
        elif dep_type == DependencyType.REQUIRED_TOOL:
            profile.required_tools.append(dep)
        elif dep_type == DependencyType.REQUIRED_DATABASE:
            profile.required_databases.append(dep)
        elif dep_type == DependencyType.REQUIRED_PROVIDER:
            profile.required_providers.append(dep)
        elif dep_type == DependencyType.RUNTIME_DEPENDENCY:
            profile.runtime_dependencies.append(dep)
        elif dep_type == DependencyType.CONFIG_DEPENDENCY:
            profile.config_dependencies.append(dep)

    def _calculate_risk_score(self, profile: ProjectDependencyProfile) -> float:
        """Calculate risk score for a project based on dependencies"""
        risk = 0.0

        # More dependencies = higher risk
        total = profile.total_dependencies
        if total > 10:
            risk += 0.3
        elif total > 5:
            risk += 0.2
        elif total > 2:
            risk += 0.1

        # Critical files increase risk
        critical = profile.critical_count
        if critical > 5:
            risk += 0.3
        elif critical > 2:
            risk += 0.2
        elif critical > 0:
            risk += 0.1

        # Broken dependencies increase risk
        broken = len(profile.broken_dependencies)
        if broken > 0:
            risk += 0.4

        # Cap at 1.0
        return min(round(risk, 2), 1.0)

    def analyze_all_projects(self) -> Dict[str, ProjectDependencyProfile]:
        """Analyze dependencies for all registered projects"""
        if not self.project_registry:
            return {}

        for project in self.project_registry.get_all():
            self.analyze_project(project.name)

        return self.profiles

    def get_profile(self, project_name: str) -> Optional[ProjectDependencyProfile]:
        """Get cached dependency profile for a project"""
        return self.profiles.get(project_name)

    def get_high_risk_projects(self, threshold: float = 0.5) -> List[ProjectDependencyProfile]:
        """Get all projects with risk score above threshold"""
        return [p for p in self.profiles.values() if p.risk_score >= threshold]

    def get_all_profiles(self) -> Dict[str, ProjectDependencyProfile]:
        """Get all dependency profiles"""
        return self.profiles.copy()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all dependency analysis"""
        total_projects = len(self.profiles)
        high_risk = len(self.get_high_risk_projects(0.5))
        total_deps = sum(p.total_dependencies for p in self.profiles.values())
        total_critical = sum(p.critical_count for p in self.profiles.values())
        total_broken = sum(len(p.broken_dependencies) for p in self.profiles.values())

        return {
            "total_projects": total_projects,
            "total_dependencies": total_deps,
            "total_critical_files": total_critical,
            "broken_dependencies": total_broken,
            "high_risk_projects": high_risk,
            "profiles": {name: p.to_dict() for name, p in self.profiles.items()}
        }