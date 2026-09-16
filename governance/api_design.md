"""
Hermes Command Center API Design - Hermes Phase 7

This document defines the proposed REST API endpoints for the Hermes Command Center.
Implementation is deferred until governance layer is fully validated.

Base URL: /api/v1/command

Endpoints:
---------
GET  /health
GET  /projects
GET  /skills
GET  /decisions
GET  /changes
GET  /recommendations

Each endpoint returns JSON with consistent structure:
{
  "status": "ok" | "error",
  "data": {...},
  "timestamp": "ISO-8601",
  "governance_approved": true | false
}

All endpoints are READ-ONLY in Phase 7 (no automation).
"""

ENDPOINTS = {
    "GET /health": {
        "description": "System health overview",
        "parameters": {},
        "response": {
            "status": "ok",
            "data": {
                "overall_health": "good" | "warning" | "critical",
                "uptime": "ISO timestamp",
                "governance_layer": "active",
                "autonomous_mode": "disabled",
                "pending_approvals": 0,
                "open_issues": 0
            }
        },
        "phase_7_status": "design_only"
    },

    "GET /projects": {
        "description": "List all tracked projects with status and health",
        "parameters": {
            "status": "filter by project status (active, paused, archived)",
            "health": "filter by health (good, warning, critical)"
        },
        "response": {
            "status": "ok",
            "data": {
                "total": 6,
                "projects": [
                    {
                        "name": "example-project",
                        "status": "active",
                        "health": "good",
                        "dependencies": ["website", "seo"],
                        "owner": "operator",
                        "last_activity": "ISO timestamp",
                        "next_action": "string"
                    }
                ]
            }
        },
        "phase_7_status": "design_only"
    },

    "GET /skills": {
        "description": "List all registered skills with their status",
        "parameters": {
            "include_disabled": "bool - include disabled skills",
            "category": "string - filter by skill category"
        },
        "response": {
            "status": "ok",
            "data": {
                "total_skills": "int",
                "active_skills": "int",
                "skills": [
                    {
                        "name": "string",
                        "status": "active | disabled | deprecated",
                        "category": "string",
                        "last_used": "ISO timestamp",
                        "health_score": "int (0-100)"
                    }
                ]
            }
        },
        "phase_7_status": "design_only"
    },

    "GET /decisions": {
        "description": "Retrieve decision history from decision_memory",
        "parameters": {
            "limit": "int - max results (default 50)",
            "offset": "int - pagination offset",
            "result": "filter by result (pending, successful, failed)"
        },
        "response": {
            "status": "ok",
            "data": {
                "total": "int",
                "decisions": [
                    {
                        "id": "string",
                        "date": "ISO timestamp",
                        "decision": "string",
                        "reason": "string",
                        "impact": "string",
                        "rollback": "string",
                        "result": "pending | successful | failed"
                    }
                ]
            }
        },
        "phase_7_status": "design_only"
    },

    "GET /changes": {
        "description": "Retrieve recent change detection events",
        "parameters": {
            "limit": "int - max results",
            "risk_level": "filter by SAFE | LOW_RISK | MEDIUM_RISK | HIGH_RISK",
            "since": "ISO timestamp - changes after this date"
        },
        "response": {
            "status": "ok",
            "data": {
                "total": "int",
                "changes": [
                    {
                        "change_id": "string",
                        "change_type": "string",
                        "risk_level": "SAFE | LOW_RISK | MEDIUM_RISK | HIGH_RISK",
                        "timestamp": "ISO timestamp",
                        "status": "pending_approval | approved | rejected"
                    }
                ]
            }
        },
        "phase_7_status": "design_only"
    },

    "GET /recommendations": {
        "description": "Get governance recommendations from analysis",
        "parameters": {
            "project": "filter by project name",
            "severity": "filter by LOW | MEDIUM | HIGH | CRITICAL"
        },
        "response": {
            "status": "ok",
            "data": {
                "total_recommendations": "int",
                "recommendations": [
                    {
                        "id": "string",
                        "type": "string",
                        "severity": "string",
                        "reason": "string",
                        "recommendation": "string",
                        "action_required": "manual_approval | auto_approved | blocked"
                    }
                ]
            }
        },
        "phase_7_status": "design_only"
    }
}

# Phase 7 constraint: All endpoints are READ-ONLY.
# No POST/PUT/DELETE until governance layer is validated and autonomous mode is enabled.