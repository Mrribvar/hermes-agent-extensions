"""
Project Registry - Hermes Phase 7

Extended capability registry for project tracking.
Each project has:
{
  name,
  status,
  health,
  dependencies,
  owner,
  last_activity,
  next_action
}
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class ProjectEntry:
    """A single project in the registry"""
    name: str
    status: str = "unknown"
    health: str = "unknown"
    dependencies: List[str] = field(default_factory=list)
    owner: str = "system"
    last_activity: str = ""
    next_action: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "health": self.health,
            "dependencies": self.dependencies,
            "owner": self.owner,
            "last_activity": self.last_activity,
            "next_action": self.next_action,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectEntry":
        return cls(
            name=data.get("name", ""),
            status=data.get("status", "unknown"),
            health=data.get("health", "unknown"),
            dependencies=data.get("dependencies", []),
            owner=data.get("owner", "system"),
            last_activity=data.get("last_activity", ""),
            next_action=data.get("next_action", ""),
            metadata=data.get("metadata", {})
        )


class ProjectRegistry:
    """
    Extended capability registry for project tracking.

    Tracks all Hermes-related projects with their status,
    health, dependencies, and next actions.
    """

    # Default projects from Task 5
    DEFAULT_PROJECTS = [
        {
            "name": "example-project",
            "status": "active",
            "health": "good",
            "dependencies": ["website", "seo", "content"],
            "owner": "operator",
            "last_activity": "",
            "next_action": "Monitor SEO performance and content updates"
        },
        {
            "name": "sample-app",
            "status": "active",
            "health": "good",
            "dependencies": ["content", "marketing"],
            "owner": "operator",
            "last_activity": "",
            "next_action": "Continue product content generation"
        },
        {
            "name": "data-pipeline",
            "status": "active",
            "health": "good",
            "dependencies": ["Agriculture_Content_Engine_v2.0_FREEZE"],
            "owner": "operator",
            "last_activity": "",
            "next_action": "Monitor content pipeline health"
        },
        {
            "name": "seo-tool",
            "status": "active",
            "health": "good",
            "dependencies": ["seo_project", "keywords_research.json"],
            "owner": "operator",
            "last_activity": "",
            "next_action": "Review keyword research and 3D SEO strategy"
        },
        {
            "name": "media-tool",
            "status": "active",
            "health": "good",
            "dependencies": ["media-tool"],
            "owner": "operator",
            "last_activity": "",
            "next_action": "Monitor video generation pipeline"
        },
        {
            "name": "hermes",
            "status": "active",
            "health": "good",
            "dependencies": ["hermes-agent", "hermes_cli", "skills", "plugins"],
            "owner": "system",
            "last_activity": "",
            "next_action": "Phase 7 governance layer completion"
        }
    ]

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.expanduser("~/.hermes/governance/projects.json")
        self.projects: Dict[str, ProjectEntry] = {}
        self._ensure_storage_dir()
        self._load()
        self._seed_defaults()

    def _ensure_storage_dir(self) -> None:
        """Create storage directory if it doesn't exist"""
        dir_path = os.path.dirname(self.storage_path)
        os.makedirs(dir_path, exist_ok=True)

    def _load(self) -> None:
        """Load projects from storage file"""
        if not os.path.exists(self.storage_path):
            return

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    entry = ProjectEntry.from_dict(item)
                    self.projects[entry.name] = entry
            elif isinstance(data, dict):
                for key, item in data.items():
                    entry = ProjectEntry.from_dict(item)
                    self.projects[entry.name] = entry
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load project registry: {e}")

    def _save(self) -> None:
        """Save projects to storage file"""
        self._ensure_storage_dir()

        data = [entry.to_dict() for entry in self.projects.values()]

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _seed_defaults(self) -> None:
        """Seed default projects if registry is empty"""
        if self.projects:
            return

        for proj_data in self.DEFAULT_PROJECTS:
            entry = ProjectEntry(
                name=proj_data["name"],
                status=proj_data["status"],
                health=proj_data["health"],
                dependencies=proj_data["dependencies"],
                owner=proj_data["owner"],
                last_activity=proj_data.get("last_activity", ""),
                next_action=proj_data["next_action"]
            )
            self.projects[entry.name] = entry

        self._save()

    def get(self, name: str) -> Optional[ProjectEntry]:
        """Get a project by name"""
        return self.projects.get(name)

    def get_all(self) -> List[ProjectEntry]:
        """Get all projects"""
        return list(self.projects.values())

    def update(self, name: str, **kwargs) -> bool:
        """Update a project's fields"""
        if name not in self.projects:
            return False

        project = self.projects[name]

        for key, value in kwargs.items():
            if hasattr(project, key):
                setattr(project, key, value)

        self._save()
        return True

    def add(self, name: str, **kwargs) -> ProjectEntry:
        """Add a new project"""
        entry = ProjectEntry(name=name, **kwargs)
        self.projects[name] = entry
        self._save()
        return entry

    def remove(self, name: str) -> bool:
        """Remove a project from registry"""
        if name not in self.projects:
            return False

        del self.projects[name]
        self._save()
        return True

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all projects"""
        total = len(self.projects)
        by_status = {}
        by_health = {}

        for proj in self.projects.values():
            by_status[proj.status] = by_status.get(proj.status, 0) + 1
            by_health[proj.health] = by_health.get(proj.health, 0) + 1

        return {
            "total_projects": total,
            "by_status": by_status,
            "by_health": by_health,
            "projects": [p.to_dict() for p in self.projects.values()]
        }

    def get_health_report(self) -> Dict[str, Any]:
        """Get health report across all projects"""
        health_counts = {"good": 0, "warning": 0, "critical": 0, "unknown": 0}
        for proj in self.projects.values():
            h = proj.health.lower()
            if h in health_counts:
                health_counts[h] += 1
            else:
                health_counts["unknown"] += 1

        return {
            "overall": "healthy" if health_counts.get("critical", 0) == 0 else "attention_needed",
            "health_distribution": health_counts,
            "total_projects": len(self.projects)
        }