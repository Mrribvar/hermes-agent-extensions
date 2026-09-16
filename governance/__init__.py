"""Hermes Governance Layer — Decision, Risk, and Control System

Exports all governance classes for plugin and runtime use.
"""
__version__ = "0.11.0"

from governance.governance_engine import GovernanceEngine
from governance.knowledge_graph import KnowledgeGraph
from governance.decision_memory import DecisionMemory, DecisionRecord
from governance.experience_memory import ExperienceMemory, ExperienceRecord
from governance.risk_classifier import RiskClassifier, RiskAssessment
from governance.approval_workflow import ApprovalWorkflow, ApprovalRequest
from governance.project_registry import ProjectRegistry
from governance.dependency_intelligence import DependencyIntelligence
from governance.impact_analysis import ImpactAnalysisEngine
from governance.graph_builder import GraphBuilder
from governance.recommendation_engine import RecommendationEngine
from governance.architecture_query import ArchitectureQueryEngine

__all__ = [
    "GovernanceEngine",
    "KnowledgeGraph",
    "DecisionMemory",
    "DecisionRecord",
    "ExperienceMemory",
    "ExperienceRecord",
    "RiskClassifier",
    "RiskAssessment",
    "ApprovalWorkflow",
    "ApprovalRequest",
    "ProjectRegistry",
    "DependencyIntelligence",
    "ImpactAnalysisEngine",
    "GraphBuilder",
    "RecommendationEngine",
    "ArchitectureQueryEngine",
]
