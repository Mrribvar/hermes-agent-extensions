"""
Architecture Query Engine - Hermes Phase 8

Answers natural-language-style questions about the architecture:
- This file belongs to which project?
- This skill is used where?
- This tool has what dependencies?
- This database is used by which components?
- If this project is removed, what happens?
- Which files have no owner?
- What are the circular dependencies?
"""

import json
import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class QueryResult:
    """Result of an architecture query"""
    query: str
    result_type: str  # node, edge, list, boolean, summary
    data: Any = None
    confidence: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "result_type": self.result_type,
            "data": self.data,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


class ArchitectureQueryEngine:
    """
    Query engine for the Hermes architecture.

    Provides natural-language-style queries over the Knowledge Graph.
    """

    def __init__(self, knowledge_graph=None, project_registry=None,
                 decision_memory=None, experience_memory=None):
        self.kg = knowledge_graph
        self.project_registry = project_registry
        self.decision_memory = decision_memory
        self.experience_memory = experience_memory

    def query(self, question: str) -> QueryResult:
        """
        Main entry point. Routes question to appropriate handler.

        Supported query patterns:
        - "This file belongs to which project?"
        - "This skill is used where?"
        - "This tool has what dependencies?"
        - "This database is used by which components?"
        - "If this project is removed, what happens?"
        - "Which files have no owner?"
        - "What are the circular dependencies?"
        - "What is the health of [project]?"
        - "List all [type] nodes"
        """
        q = question.lower().strip()

        if "belongs to" in q or "part of project" in q:
            return self._query_file_project(q)
        elif "skill is used" in q or "where is skill" in q or "skill used where" in q:
            return self._query_skill_usage(q)
        elif "tool has" in q and "dependenc" in q:
            return self._query_tool_dependencies(q)
        elif "database is used" in q or "database used by" in q:
            return self._query_database_usage(q)
        elif "removed" in q or "delete" in q or "what happens" in q:
            return self._query_removal_impact(q)
        elif "no owner" in q or "orphan" in q or "unowned" in q:
            return self._query_orphan_files(q)
        elif "circular" in q or "cycle" in q:
            return self._query_circular_deps(q)
        elif "health of" in q or "status of" in q:
            return self._query_project_health(q)
        elif "list all" in q or "show all" in q:
            return self._query_list_all(q)
        elif "related to" in q or "connected to" in q:
            return self._query_related(q)
        else:
            return QueryResult(
                query=question,
                result_type="unknown",
                data=None,
                confidence=0.0,
                reasoning="Query pattern not recognized. Supported patterns: file->project, skill usage, tool dependencies, database usage, removal impact, orphan files, circular deps, project health, list all, related nodes."
            )

    def _query_file_project(self, q: str) -> QueryResult:
        """Find which project a file belongs to"""
        if not self.kg:
            return QueryResult(query=q, result_type="error", data="No knowledge graph available")

        # Extract file name from query
        file_name = self._extract_entity(q, ["file", "belongs", "project"])

        nodes = self.kg.get_nodes_by_label(file_name) if file_name else []
        if not nodes:
            return QueryResult(
                query=q, result_type="list", data=[],
                confidence=0.3,
                reasoning=f"File '{file_name}' not found in knowledge graph"
            )

        # Find project nodes connected to this file
        projects = []
        for node in nodes:
            related = self.kg.get_related_nodes(node.id)
            for rel in related:
                if rel.type.value in ("Project", "UserProject", "Directory"):
                    projects.append(rel.label)

        return QueryResult(
            query=q, result_type="list", data=list(set(projects)),
            confidence=0.8 if projects else 0.3,
            reasoning=f"Found {len(set(projects))} project(s) for file '{file_name}'"
        )

    def _query_skill_usage(self, q: str) -> QueryResult:
        """Find where a skill is used"""
        if not self.kg:
            return QueryResult(query=q, result_type="error", data="No knowledge graph available")

        skill_name = self._extract_entity(q, ["skill", "used", "where"])
        nodes = self.kg.get_nodes_by_label(skill_name) if skill_name else []

        usages = []
        for node in nodes:
            outgoing = self.kg.get_edges_by_source(node.id)
            for edge in outgoing:
                target = self.kg.get_node(edge.target)
                if target:
                    usages.append({"target": target.label, "relationship": edge.type.value})

        return QueryResult(
            query=q, result_type="list", data=usages,
            confidence=0.8 if usages else 0.3,
            reasoning=f"Found {len(usages)} usage(s) for skill '{skill_name}'"
        )

    def _query_tool_dependencies(self, q: str) -> QueryResult:
        """Find dependencies of a tool"""
        if not self.kg:
            return QueryResult(query=q, result_type="error", data="No knowledge graph available")

        tool_name = self._extract_entity(q, ["tool", "dependenc"])
        nodes = self.kg.get_nodes_by_label(tool_name) if tool_name else []

        deps = []
        for node in nodes:
            outgoing = self.kg.get_edges_by_source(node.id)
            for edge in outgoing:
                if edge.type.value in ("depends_on", "uses", "imports"):
                    target = self.kg.get_node(edge.target)
                    if target:
                        deps.append({"dependency": target.label, "type": edge.type.value})

        return QueryResult(
            query=q, result_type="list", data=deps,
            confidence=0.8 if deps else 0.3,
            reasoning=f"Found {len(deps)} dependency/dependencies for tool '{tool_name}'"
        )

    def _query_database_usage(self, q: str) -> QueryResult:
        """Find which components use a database"""
        if not self.kg:
            return QueryResult(query=q, result_type="error", data="No knowledge graph available")

        db_name = self._extract_entity(q, ["database", "used by"])
        nodes = self.kg.get_nodes_by_label(db_name) if db_name else []

        users = []
        for node in nodes:
            incoming = self.kg.get_edges_by_target(node.id)
            for edge in incoming:
                source = self.kg.get_node(edge.source)
                if source:
                    users.append({"component": source.label, "relationship": edge.type.value})

        return QueryResult(
            query=q, result_type="list", data=users,
            confidence=0.8 if users else 0.3,
            reasoning=f"Found {len(users)} component(s) using database '{db_name}'"
        )

    def _query_removal_impact(self, q: str) -> QueryResult:
        """Analyze impact of removing a project/file/skill"""
        if not self.kg:
            return QueryResult(query=q, result_type="error", data="No knowledge graph available")

        target = self._extract_entity(q, ["removed", "delete", "project", "file", "skill"])

        # Find matching nodes
        nodes = self.kg.get_nodes_by_label(target) if target else []
        if not nodes:
            return QueryResult(
                query=q, result_type="summary",
                data={"message": f"No node matching '{target}' found"},
                confidence=0.3,
                reasoning=f"No node found for '{target}'"
            )

        impact_summary = {
            "target": target,
            "nodes_found": len(nodes),
            "outgoing_edges": 0,
            "incoming_edges": 0,
            "affected_components": []
        }

        for node in nodes:
            outgoing = self.kg.get_edges_by_source(node.id)
            incoming = self.kg.get_edges_by_target(node.id)
            impact_summary["outgoing_edges"] += len(outgoing)
            impact_summary["incoming_edges"] += len(incoming)

            for edge in outgoing:
                t = self.kg.get_node(edge.target)
                if t:
                    impact_summary["affected_components"].append(t.label)

        return QueryResult(
            query=q, result_type="summary", data=impact_summary,
            confidence=0.7,
            reasoning=f"Removal of '{target}' would affect {len(impact_summary['affected_components'])} components"
        )

    def _query_orphan_files(self, q: str) -> QueryResult:
        """Find files with no owner or no connections"""
        if not self.kg:
            return QueryResult(query=q, result_type="error", data="No knowledge graph available")

        orphans = []
        for node in self.kg.nodes.values():
            if node.type.value == "File":
                outgoing = self.kg.get_edges_by_source(node.id)
                incoming = self.kg.get_edges_by_target(node.id)
                if not outgoing and not incoming:
                    owner = node.properties.get("owner", "none")
                    orphans.append({"file": node.label, "owner": owner, "node_id": node.id})

        return QueryResult(
            query=q, result_type="list", data=orphans,
            confidence=0.9,
            reasoning=f"Found {len(orphans)} orphan files with no connections"
        )

    def _query_circular_deps(self, q: str) -> QueryResult:
        """Find circular dependencies"""
        if not self.kg:
            return QueryResult(query=q, result_type="error", data="No knowledge graph available")

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
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.discard(node_id)

        for node_id in self.kg.nodes:
            if node_id not in visited:
                dfs(node_id, [])

        return QueryResult(
            query=q, result_type="list", data=cycles,
            confidence=0.95,
            reasoning=f"Found {len(cycles)} circular dependency cycle(s)"
        )

    def _query_project_health(self, q: str) -> QueryResult:
        """Get health status of a project"""
        if not self.project_registry:
            return QueryResult(query=q, result_type="error", data="No project registry available")

        proj_name = self._extract_entity(q, ["health of", "status of"])
        proj = self.project_registry.get(proj_name) if proj_name else None

        if not proj:
            return QueryResult(
                query=q, result_type="summary",
                data={"message": f"Project '{proj_name}' not found"},
                confidence=0.3,
                reasoning=f"Project '{proj_name}' not in registry"
            )

        return QueryResult(
            query=q, result_type="summary",
            data={
                "project": proj.name,
                "status": proj.status,
                "health": proj.health,
                "dependencies": proj.dependencies,
                "next_action": proj.next_action
            },
            confidence=0.95,
            reasoning=f"Project '{proj_name}' is {proj.status} with health={proj.health}"
        )

    def _query_list_all(self, q: str) -> QueryResult:
        """List all nodes of a given type"""
        if not self.kg:
            return QueryResult(query=q, result_type="error", data="No knowledge graph available")

        # Extract type from query
        type_map = {
            "project": "Project",
            "skill": "Skill",
            "tool": "Tool",
            "database": "Database",
            "provider": "Provider",
            "file": "File",
            "module": "Module",
            "api": "API",
            "config": "Config",
            "runtime": "Runtime",
            "memory": "Memory",
            "decision": "Decision",
            "experience": "Experience"
        }

        result_type = "unknown"
        for key, val in type_map.items():
            if key in q:
                result_type = val
                break

        if result_type == "unknown":
            return QueryResult(
                query=q, result_type="error",
                data="Could not determine node type from query. Try: 'list all projects', 'list all skills', etc."
            )

        nodes = self.kg.get_nodes_by_type_value(result_type)
        return QueryResult(
            query=q, result_type="list",
            data=[n.to_dict() for n in nodes],
            confidence=0.9,
            reasoning=f"Found {len(nodes)} {result_type} node(s)"
        )

    def _query_related(self, q: str) -> QueryResult:
        """Find related nodes"""
        if not self.kg:
            return QueryResult(query=q, result_type="error", data="No knowledge graph available")

        entity = self._extract_entity(q, ["related to", "connected to"])
        nodes = self.kg.get_nodes_by_label(entity) if entity else []

        related = []
        for node in nodes:
            connected = self.kg.get_related_nodes(node.id)
            for c in connected:
                related.append({
                    "node": c.label,
                    "type": c.type.value,
                    "via": "bidirectional"
                })

        return QueryResult(
            query=q, result_type="list", data=related,
            confidence=0.8 if related else 0.3,
            reasoning=f"Found {len(related)} related node(s) for '{entity}'"
        )

    def _extract_entity(self, query: str, keywords: List[str]) -> str:
        """Extract entity name from a query string"""
        # Simple extraction: find text after keywords
        for kw in keywords:
            idx = query.find(kw)
            if idx != -1:
                # Get text after this keyword
                after = query[idx + len(kw):].strip()
                # Remove trailing question marks and common words
                for stop_word in ["?", "is", "are", "the", "which", "what", "where", "who"]:
                    after = after.split(stop_word)[0].strip()
                # Clean up
                after = after.strip("? .,;")
                if after:
                    return after
        return ""

    def get_supported_queries(self) -> List[str]:
        """List all supported query patterns"""
        return [
            "Which project does this file belong to?",
            "Where is this skill used?",
            "What are the dependencies of this tool?",
            "Which components use this database?",
            "What happens if this project is removed?",
            "Which files have no owner?",
            "What are the circular dependencies?",
            "What is the health of [project]?",
            "List all [type] nodes",
            "What is related to [entity]?"
        ]